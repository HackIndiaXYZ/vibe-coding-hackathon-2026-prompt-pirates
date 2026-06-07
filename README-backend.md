# RxLens — Backend

FastAPI backend for the RxLens prescription analysis platform. Handles image ingestion, OCR text extraction, LLM-powered medicine safety analysis, and prescription history storage.

---

## Table of Contents

- [Overview](#overview)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Architecture](#architecture)
- [API Routes](#api-routes)
- [Provider System](#provider-system)
- [Services](#services)
- [Medicine Lookup Chain](#medicine-lookup-chain)
- [Templates](#templates)
- [Database](#database)
- [Rate Limiting](#rate-limiting)
- [Environment Variables](#environment-variables)

---

## Overview

The backend is a FastAPI application that receives prescription images, runs OCR to extract text, identifies medicine names, and then queries an LLM provider to generate a structured safety analysis for each medicine. It is designed to work with no database in the simplest case — prescription metadata is stored as JSON sidecar files alongside uploaded images.

---

## Tech Stack

| Concern | Library |
|---|---|
| Framework | FastAPI 0.111 + Uvicorn |
| Language | Python 3.11+ |
| Settings | Pydantic Settings v2 |
| Database | SQLAlchemy 2 (async) + asyncpg + Alembic |
| Vector DB | ChromaDB 0.5 |
| OCR | Tesseract (pytesseract) / EasyOCR |
| Embeddings | sentence-transformers (all-MiniLM-L6-v2) |
| LLM Providers | Gemini, OpenAI, Ollama, HuggingFace, Template |
| HTTP | httpx |
| Testing | pytest + pytest-asyncio |

---

## Project Structure

```
app/
├── main.py                         # FastAPI app factory + lifespan startup
├── api/
│   └── routes/
│       ├── upload.py               # POST /api/v1/upload — image ingest + OCR
│       ├── analysis.py             # GET/POST /api/v1/analysis — medicine analysis
│       ├── prescriptions.py        # GET /api/v1/prescriptions — history
│       └── health.py               # GET /api/v1/health — system status
├── core/
│   ├── settings.py                 # Pydantic Settings — all config from .env
│   ├── database.py                 # Async SQLAlchemy engine + session factory
│   ├── dependencies.py             # FastAPI Depends() factories
│   └── rate_limit.py               # Sliding-window rate limit middleware
├── providers/
│   ├── base.py                     # BaseLLMProvider abstract class
│   ├── factory.py                  # get_llm_provider() — cached provider singleton
│   ├── gemini_provider.py          # Google Gemini
│   ├── openai_provider.py          # OpenAI / OpenAI-compatible
│   ├── ollama_provider.py          # Ollama (local)
│   ├── huggingface_provider.py     # Local HuggingFace transformers
│   ├── template_provider.py        # Template fallback (no API key needed)
│   └── ocr_provider.py             # OCR abstraction (Tesseract / EasyOCR)
├── services/
│   ├── analysis_service.py         # Core analysis logic — LLM prompting + RAG
│   ├── llm_service.py              # LLMService — wraps any provider
│   └── vector_store_service.py     # ChromaDB wrapper — embed, store, retrieve
├── schemas/
│   └── responses.py                # Pydantic models for all request/response shapes
├── models/
│   └── db_models.py                # SQLAlchemy ORM models
├── repositories/
│   └── prescription_repository.py  # DB access layer (optional PostgreSQL path)
├── templates/
│   ├── template_service.py         # Template mode — no LLM needed
│   └── data/
│       ├── dosage_templates.yaml   # Dosage info per medicine class
│       ├── explanation_templates.yaml  # Explanation templates per class
│       └── warning_templates.yaml  # Warning templates per class
├── utils/
│   └── logger.py                   # Structured logger
alembic/                            # DB migration scripts
data/
└── medicine_seed.json              # Seed data for ChromaDB vector store
scripts/
└── seed_vector_store.py            # Script to populate ChromaDB from seed JSON
tests/
├── test_api.py
├── test_core.py
└── test_history_ratelimit.py
```

---

## Architecture

### Request lifecycle

```
Client uploads image
        │
        ▼
POST /api/v1/upload
  │  Validate file type + size
  │  Save image to ./uploads/<uuid>.<ext>
  │  OCR extraction (Tesseract or EasyOCR)
  │  LLM refinement of medicine names (non-fatal — falls back to raw OCR)
  │  Merge OCR + LLM medicine lists, deduplicate
  │  Save sidecar .meta JSON file
  └► Return UploadResponse { prescription_id, detected_medicines, ocr_confidence, ... }

        │
        ▼
POST /api/v1/analysis
  │  Read sidecar .meta to resolve medicine list (or accept override in body)
  │  For each medicine:
  │      ├── Query ChromaDB for RAG context (if enabled)
  │      ├── Call analysis_service.analyse_medicine()
  │      │       ├── Template mode: render YAML templates
  │      │       └── LLM mode: prompt provider with RAG context
  │      └── Parse + validate JSON response into MedicineAnalysis
  │  Aggregate: overall severity, drowsiness, dosage, age warnings
  └► Return FullAnalysisResponse
```

### Graceful degradation

Startup failures for ChromaDB and PostgreSQL are non-fatal — the app continues without them. If the LLM provider fails for a specific medicine, an error `MedicineAnalysis` record is inserted instead of crashing the entire analysis.

---

## API Routes

All routes are prefixed `/api/v1`. Interactive docs at `/docs` (Swagger) and `/redoc`.

### Upload

**`POST /api/v1/upload`**

Accepts a `multipart/form-data` file upload. Supported extensions: `.jpg`, `.jpeg`, `.png`, `.tiff`, `.bmp`, `.webp`. Max size controlled by `MAX_UPLOAD_SIZE_MB` (default 10 MB).

**Response:**
```json
{
  "prescription_id": "uuid",
  "filename": "original_name.jpg",
  "raw_text": "...",
  "cleaned_text": "...",
  "detected_medicines": ["Metformin", "Amlodipine"],
  "ocr_confidence": 0.87,
  "message": "Prescription uploaded. Found 2 medicine(s)."
}
```

---

### Analysis

**`POST /api/v1/analysis`**

Run full safety analysis. Supply `prescription_id` from the upload step. Optionally pass `patient_age`, `language`, or a `medicines` list override.

**Request body:**
```json
{
  "prescription_id": "uuid",
  "patient_age": 45,
  "language": "en",
  "medicines": null
}
```

**`GET /api/v1/analysis/{prescription_id}`**

Re-fetch analysis. Query params: `patient_age`, `language`. Reads the sidecar file to resolve the medicine list.

**Response (`FullAnalysisResponse`):**
```json
{
  "prescription_id": "uuid",
  "patient_age": 45,
  "language": "en",
  "medicines": [ { ...MedicineAnalysis } ],
  "overall_drowsiness_warning": false,
  "overall_dosage_concern": false,
  "overall_age_warning": false,
  "overall_severity": "medium",
  "total_medicines_analysed": 2,
  "provider_used": "gemini",
  "summary": "Analysed 2 medicine(s) using gemini."
}
```

Each `MedicineAnalysis` object contains: `explanation`, `use_case`, `mechanism`, `how_to_take`, `side_effects`, `serious_side_effects`, `causes_drowsiness`, `drowsiness_note`, `dosage_info`, `dosage_safe`, `dosage_notes`, `age_warnings`, `contraindications`, `alternatives`, `severity_level` (`low|medium|high|critical`), `drug_class`, `rag_sources`, `generated_by`.

---

### Prescriptions (History)

**`GET /api/v1/prescriptions`**

List all uploaded prescriptions sorted newest-first. Query params: `limit` (1–100, default 20), `offset` (default 0).

**`GET /api/v1/prescriptions/{prescription_id}`**

Retrieve metadata for a single prescription.

---

### Health

**`GET /api/v1/health`**

Returns system status: LLM provider health, vector DB document count, OCR provider, environment.

**`GET /api/v1/health/models`**

Lists models available to the configured API key (where supported by the provider).

---

## Provider System

All LLM providers implement `BaseLLMProvider` (abstract class in `providers/base.py`):

```python
class BaseLLMProvider:
    name: str
    async def generate(self, system: str, human: str) -> str: ...
    async def health_check(self) -> bool: ...
    async def embed(self, texts: list[str]) -> list[list[float]]: ...
```

The active provider is resolved at startup by `get_llm_provider()` (cached singleton) based on `MODEL_PROVIDER` in `.env`:

| `MODEL_PROVIDER` value | Provider | Requires |
|---|---|---|
| `gemini` | Google Gemini API | `GEMINI_API_KEY` |
| `openai` | OpenAI (or compatible) | `OPENAI_API_KEY` |
| `ollama` | Ollama local server | Ollama running at `OLLAMA_BASE_URL` |
| `huggingface` | Local HuggingFace model | `HF_MODEL_PATH` + transformers installed |
| `template` | YAML template system | Nothing — works offline |

Switching providers requires only changing `MODEL_PROVIDER` in `.env` and restarting.

---

## Services

### `AnalysisService`

The core orchestration service. It:

1. Takes a medicine name, optional patient age, and language
2. Queries `VectorStoreService` for RAG context (drug class hints, related documents)
3. Builds a structured prompt using `_ANALYSIS_SYSTEM` + `_ANALYSIS_HUMAN` templates
4. Calls `LLMService.generate()` and parses the JSON response
5. Falls back to `TemplateService` if the LLM response can't be parsed or template mode is enabled

Also handles OCR refinement (`refine_ocr()`) — takes raw OCR text and asks the LLM to correct and extract a clean medicine list.

### `LLMService`

Thin wrapper around `BaseLLMProvider`. Adds retry logic (via `tenacity`) and health checking.

### `VectorStoreService`

Manages the ChromaDB collection. On startup:
- Loads existing collection (or creates it)
- The `seed_vector_store.py` script can populate it from `data/medicine_seed.json`

At query time, embeds the medicine name using `sentence-transformers` and returns the top-K most similar documents as RAG context strings.

---

## Medicine Lookup Chain

When analysing a medicine, `AnalysisService` builds context through a cascading lookup:

```
1. Local ChromaDB (vector similarity search)
        │  hit → pass as RAG context to LLM
        │  miss ↓
2. LLM training knowledge (the model's own knowledge)
        │  if LLM returns unrecognised medicine →
3. Template fallback (YAML templates)
        │  if medicine class not in templates →
4. Generic error record (analysis unavailable)
```

This means the system works even when ChromaDB is empty or disabled — the LLM uses its training data, and if that fails, structured YAML templates provide a sensible fallback.

---

## Templates

`TemplateService` provides offline / zero-API-key operation. Templates are stored in `app/templates/data/`:

- `explanation_templates.yaml` — per-class patient-friendly explanations
- `dosage_templates.yaml` — dosage information by drug class
- `warning_templates.yaml` — standard warnings by drug class

The service maps medicine names to drug classes using `_NAME_TO_CLASS` (a lookup dict of common brand/generic names) and renders the appropriate template.

---

## Database

PostgreSQL is optional. If `DATABASE_URL` is not reachable, the app falls back to sidecar `.meta` JSON files stored next to uploaded images.

When PostgreSQL is available, Alembic manages schema migrations:

```bash
alembic upgrade head      # apply all migrations
alembic revision --autogenerate -m "description"  # create new migration
```

The `prescription_repository.py` implements the async DB access layer. All DB calls use `asyncpg` through SQLAlchemy's async session.

---

## Rate Limiting

`RateLimitMiddleware` implements an in-memory sliding window limiter. It is active in all environments except `test`. Default limits (configurable in `rate_limit.py`):

- Upload endpoint: tighter limit (upload is expensive)
- Analysis endpoint: per-IP sliding window
- Health + prescriptions: relaxed

Returns `HTTP 429` with a `Retry-After` header on breach.

---

## Environment Variables

Copy `.env.example` to `.env` and configure:

### Core

| Variable | Default | Description |
|---|---|---|
| `ENVIRONMENT` | `development` | `development` or `production`. Production hides internal error details. |
| `DEBUG` | `true` | Enable debug logging. |
| `HOST` | `0.0.0.0` | Bind address. |
| `PORT` | `8000` | Port to listen on. |
| `SECRET_KEY` | `change-me-in-production` | **Change this.** Used for signing. |
| `CORS_ORIGINS` | `["*"]` | Comma-separated allowed origins. Lock down in production. |

### LLM Provider

| Variable | Default | Description |
|---|---|---|
| `MODEL_PROVIDER` | `template` | Active LLM provider: `gemini`, `openai`, `ollama`, `huggingface`, `template`. |
| `MODEL_NAME` | *(empty)* | Model name override. Uses provider default if blank (e.g. `gemini-2.5-flash`, `gpt-4o`). |
| `MODEL_TEMPERATURE` | `0.2` | Sampling temperature. Lower = more deterministic. |
| `MODEL_MAX_TOKENS` | `2048` | Max tokens in LLM response. |

### Provider Credentials (set only the one you use)

| Variable | Description |
|---|---|
| `GEMINI_API_KEY` | Google AI Studio key. Required when `MODEL_PROVIDER=gemini`. |
| `OPENAI_API_KEY` | OpenAI key. Required when `MODEL_PROVIDER=openai`. |
| `OPENAI_BASE_URL` | Override for OpenAI-compatible APIs (e.g. Azure, local proxies). Default: `https://api.openai.com/v1`. |
| `OLLAMA_BASE_URL` | URL of running Ollama server. Default: `http://localhost:11434`. |
| `HF_MODEL_PATH` | HuggingFace repo ID or local path. E.g. `mistralai/Mistral-7B-Instruct-v0.3`. |
| `HF_DEVICE` | Device for HuggingFace model: `cpu`, `cuda`, `mps`. |
| `HF_LOAD_IN_4BIT` | `true` to use 4-bit quantisation (requires `bitsandbytes`). |

### OCR

| Variable | Default | Description |
|---|---|---|
| `OCR_PROVIDER` | `tesseract` | `tesseract` or `easyocr`. EasyOCR requires `pip install easyocr`. |
| `TESSERACT_CMD` | `/usr/bin/tesseract` | Path to Tesseract binary. On Windows: `C:\Program Files\Tesseract-OCR\tesseract.exe`. |
| `TESSERACT_LANG` | `eng` | Tesseract language code. Add `+hin` for Hindi, `+tam` for Tamil, etc. |

### Database

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@localhost:5432/prescription_db` | Async PostgreSQL DSN. The app continues without this — uses file sidecars as fallback. |
| `DB_POOL_SIZE` | `10` | SQLAlchemy connection pool size. |
| `DB_ECHO` | `false` | Log all SQL statements (useful for debugging). |

### Vector DB

| Variable | Default | Description |
|---|---|---|
| `VECTOR_DB_ENABLED` | `true` | Set `false` to disable ChromaDB entirely (LLM knowledge only). |
| `CHROMA_PERSIST_DIR` | `./chroma_db` | Directory where ChromaDB stores its data. |
| `CHROMA_COLLECTION_NAME` | `medicines` | Name of the ChromaDB collection. |
| `EMBEDDING_PROVIDER` | `local` | `local` (sentence-transformers) or `openai`. |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | Model for local embeddings. |
| `RAG_TOP_K` | `5` | Number of vector results to retrieve per medicine. |
| `RAG_SCORE_THRESHOLD` | `0.4` | Minimum similarity score to include a result as context. |

### Upload & Misc

| Variable | Default | Description |
|---|---|---|
| `UPLOAD_DIR` | `./uploads` | Directory for uploaded images and sidecar `.meta` files. |
| `MAX_UPLOAD_SIZE_MB` | `10` | Maximum upload size in megabytes. |
| `DEFAULT_LANGUAGE` | `en` | Fallback language for analysis output. |
| `LOG_LEVEL` | `INFO` | Logging verbosity: `DEBUG`, `INFO`, `WARNING`, `ERROR`. |
| `LOG_FILE` | *(empty)* | If set, log output is also written to this file path. |
