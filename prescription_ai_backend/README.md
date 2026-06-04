# AI Prescription Explainer & Safety Assistant — Gemini Edition (v2)

> Upload a prescription image → get an instant AI-powered safety report powered by **Google Gemini**.

---

## What changed from v1

| v1 (removed) | v2 (Gemini-only) |
|---|---|
| OpenAI GPT-4o | Google Gemini 1.5 Flash |
| LangChain agents | Direct `google-generativeai` SDK calls |
| ChromaDB vector store | ❌ Removed — no RAG needed |
| OpenAI embeddings | ❌ Removed |
| `agents/` directory | ❌ Removed |
| `database/` directory | ❌ Removed |
| `prompts/` directory | ❌ Removed (prompt lives in `gemini_service.py`) |
| Multiple service classes | Single `GeminiService` |

---

## Architecture

```
POST /api/v1/upload
  └─► Tesseract OCR (OpenCV pre-processing)
  └─► Save image + .meta sidecar (JSON)
  └─► Return prescription_id + detected_medicines

GET /api/v1/analysis/{prescription_id}
  └─► Load .meta sidecar (OCR text)
  └─► GeminiService.analyse_prescription(ocr_text, age, language)
        └─► google-generativeai → gemini-1.5-flash
        └─► Returns structured JSON
  └─► Map to FullAnalysisResponse
```

### Data flow diagram

```
Prescription Image
       │
       ▼
  [Tesseract OCR]
  OpenCV pre-processing
       │
       ▼
  Raw OCR Text  ──────────────────────────────►  .meta sidecar (UUID.meta)
       │                                               │
       │    ◄──────────────────────────────────────────┘
       ▼
  [Google Gemini 1.5 Flash]
  Structured JSON prompt
       │
       ▼
  {medicines: [{name, dosage, frequency, duration,
                side_effects, serious_side_effects,
                alternatives, age_warnings,
                causes_drowsiness, lifestyle_recommendations,
                dosage_safety_assessment, severity_level}]}
       │
       ▼
  FullAnalysisResponse  →  Frontend
```

---

## Gemini JSON Schema

For each medicine detected, Gemini returns:

```json
{
  "medicine_name": "Amoxicillin",
  "dosage": "500mg",
  "frequency": "Three times daily",
  "duration": "7 days",
  "use_case": "Bacterial infections",
  "side_effects": ["Diarrhoea", "Nausea"],
  "serious_side_effects": ["Anaphylaxis"],
  "alternatives": ["Azithromycin", "Clarithromycin"],
  "age_warnings": [],
  "causes_drowsiness": false,
  "lifestyle_recommendations": ["Complete the full course."],
  "dosage_safety_assessment": {
    "is_safe": true,
    "prescribed_dose": "500mg TID",
    "standard_dose": "250–500mg every 8 hours",
    "notes": []
  },
  "severity_level": "low"
}
```

---

## Quick Start

### 1. Prerequisites

```bash
# Ubuntu / Debian
sudo apt install tesseract-ocr tesseract-ocr-eng

# macOS
brew install tesseract
```

### 2. Get a Gemini API Key

- Visit https://aistudio.google.com/app/apikey
- Create a free API key (Gemini 1.5 Flash is free-tier eligible)

### 3. Configure

```bash
cp .env.example .env
# Edit .env — set GEMINI_API_KEY=your-key-here
```

### 4. Run

```bash
bash run.sh
```

API: **http://localhost:8000**  
Swagger: **http://localhost:8000/docs**

---

## API Reference

### `POST /api/v1/upload`

| Field | Type | Required | Description |
|---|---|---|---|
| `file` | File | ✅ | JPEG, PNG, TIFF, BMP, WEBP |
| `patient_age` | int | ❌ | Enables age-specific Gemini warnings |
| `language` | string | ❌ | ISO 639-1 code (default: `en`) |

**Response:**
```json
{
  "prescription_id": "uuid",
  "detected_medicines": ["Amoxicillin"],
  "raw_text": "...",
  "ocr_confidence": 0.87,
  "message": "..."
}
```

---

### `GET /api/v1/analysis/{prescription_id}`

Runs Gemini analysis on the stored OCR text.

**Query params:** `patient_age`, `language`

---

### `POST /api/v1/analysis`

```json
{
  "prescription_id": "uuid",
  "patient_age": 8,
  "language": "en",
  "medicines": ["Aspirin"]
}
```

---

### `GET /api/v1/health`

Returns Gemini key status, Tesseract path, disk space.

---

## Docker

```bash
docker build -t prescription-ai-gemini .

docker run -p 8000:8000 \
  -e GEMINI_API_KEY=your-key \
  -v $(pwd)/uploads:/home/appuser/app/uploads \
  prescription-ai-gemini
```

---

## Testing

```bash
bash run.sh          # starts app with hot-reload
# in another terminal:
pytest app/tests/ -v
```

---

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `GEMINI_API_KEY` | ✅ | — | Google Gemini API key |
| `GEMINI_MODEL` | ❌ | `gemini-1.5-flash` | Gemini model name |
| `TESSERACT_CMD` | ✅ | `/usr/bin/tesseract` | Path to Tesseract binary |
| `UPLOAD_DIR` | ❌ | `./uploads` | Image upload directory |
| `DEFAULT_LANGUAGE` | ❌ | `en` | Fallback language |

---

## Supported Languages

`en` English · `ta` Tamil · `hi` Hindi · `fr` French · `es` Spanish · `de` German · `zh` Chinese · `ar` Arabic

---

## Safety Disclaimer

> This tool is for **educational and informational purposes only**.
> It does **not** constitute medical advice. Always consult a qualified
> healthcare professional before making any decisions about medications.
