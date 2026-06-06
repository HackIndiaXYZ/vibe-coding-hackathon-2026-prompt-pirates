
<div align="center">

```
██████╗ ██╗  ██╗██╗     ███████╗███╗   ██╗███████╗
██╔══██╗╚██╗██╔╝██║     ██╔════╝████╗  ██║██╔════╝
██████╔╝ ╚███╔╝ ██║     █████╗  ██╔██╗ ██║███████╗
██╔══██╗ ██╔██╗ ██║     ██╔══╝  ██║╚██╗██║╚════██║
██║  ██║██╔╝ ██╗███████╗███████╗██║ ╚████║███████║
╚═╝  ╚═╝╚═╝  ╚═╝╚══════╝╚══════╝╚═╝  ╚═══╝╚══════╝
```

### 🔬 AI-Powered Prescription OCR & Medicine Safety Platform

[![Next.js](https://img.shields.io/badge/Next.js-15.5-black?style=for-the-badge&logo=next.js)](https://nextjs.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.0-3178C6?style=for-the-badge&logo=typescript&logoColor=white)](https://typescriptlang.org)
[![Tests](https://img.shields.io/badge/Tests-38%2F38_Passing-brightgreen?style=for-the-badge&logo=pytest)](/)
[![License](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)](LICENSE)

> Upload a prescription image → Extract medicine names via OCR → Get AI-powered safety analysis, drug interactions, and dosage guidance — all in seconds.

</div>

---

## ✨ What is RxLens?

**RxLens** is a full-stack medical intelligence platform that scans handwritten or printed prescriptions using Tesseract OCR, then performs deep medicine safety analysis using your choice of LLM provider (OpenAI GPT-4o, Google Gemini, Ollama, HuggingFace, or zero-dependency Template mode).

```
📸 Upload Prescription Image
         ↓
🔍 Tesseract OCR Extraction
         ↓
🧠 RAG-Enhanced LLM Analysis  ←──── ChromaDB Vector Store
         ↓
💊 Safety Report: Interactions • Warnings • Dosage • Explanations
         ↓
📜 PostgreSQL History Storage
```

### 🏗️ Tech Stack at a Glance

| Layer | Technology |
|-------|-----------|
| **Frontend** | Next.js 15, React 19, TypeScript, TailwindCSS, Framer Motion |
| **Backend** | FastAPI, Python 3.11+, Pydantic v2, Uvicorn |
| **OCR** | Tesseract 5 / EasyOCR |
| **LLM** | OpenAI GPT-4o · Gemini · Ollama · HuggingFace · Template |
| **Vector DB** | ChromaDB (RAG-based medicine knowledge) |
| **Database** | PostgreSQL 16 (prescription history) |
| **Embeddings** | sentence-transformers `all-MiniLM-L6-v2` |

---

## 📋 Table of Contents

- [Prerequisites](#-prerequisites)
- [Quick Start — All Platforms](#-quick-start)
  - [🐧 Linux](#-linux)
  - [🍎 macOS](#-macos)
  - [🪟 Windows](#-windows)
- [Environment Configuration](#️-environment-configuration)
- [LLM Provider Setup](#-llm-provider-setup)
- [Running with Docker](#-running-with-docker-recommended)
- [Database Setup](#-database-setup)
- [Seeding the Vector Store](#-seeding-the-vector-store)
- [Project Structure](#-project-structure)
- [API Reference](#-api-reference)
- [Running Tests](#-running-tests)
- [Troubleshooting](#-troubleshooting)

---

## 🛠️ Prerequisites

Before you begin, ensure the following are installed:

| Tool | Version | Check Command |
|------|---------|---------------|
| **Node.js** | 20+ | `node --version` |
| **npm** | 9+ | `npm --version` |
| **Python** | 3.11.x | `python --version` |
| **Git** | Any | `git --version` |
| **PostgreSQL** | 14+ | `psql --version` |
| **Tesseract OCR** | 5.x | `tesseract --version` |

> 💡 **Tip:** Python 3.13 is **not yet supported** due to upstream dependency constraints. Use **Python 3.11** (ideally via `pyenv`).

---

## 🚀 Quick Start

### 🐧 Linux

#### Step 1 — System Dependencies

```bash
# Ubuntu / Debian
sudo apt update && sudo apt install -y \
  python3.11 python3.11-venv python3.11-dev \
  tesseract-ocr tesseract-ocr-eng \
  postgresql postgresql-contrib \
  nodejs npm git curl

# Fedora / RHEL
sudo dnf install -y python3.11 python3.11-devel \
  tesseract nodejs npm postgresql postgresql-server git

# Arch Linux
sudo pacman -S python tesseract tesseract-data-eng nodejs npm postgresql git
```

#### Step 2 — Clone the Repository

```bash
git clone https://github.com/your-username/rxlens.git
cd rxlens
```

> If you received the project as a ZIP, extract it and `cd` into the folder.

#### Step 3 — Backend Setup

```bash
# Navigate to backend
cd backend-share

# Create a virtual environment with Python 3.11
python3.11 -m venv venv
source venv/bin/activate

# Upgrade pip and install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Copy environment file
cp .env.example .env
# ↑ Edit .env now — see "Environment Configuration" section below
```

#### Step 4 — Frontend Setup

```bash
# In a new terminal, navigate to frontend
cd rxlens   # the Next.js app folder

# Install dependencies
npm install

# Copy environment file
cp .env.local.example .env.local
# Set NEXT_PUBLIC_API_URL=http://localhost:8000
```

#### Step 5 — PostgreSQL Setup

```bash
# Start PostgreSQL
sudo systemctl start postgresql
sudo systemctl enable postgresql

# Create database and user
sudo -u postgres psql -c "CREATE DATABASE prescription_db;"
sudo -u postgres psql -c "CREATE USER postgres WITH PASSWORD 'postgres';"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE prescription_db TO postgres;"

# Run migrations (from backend directory, venv activated)
cd backend-share
alembic upgrade head
```

#### Step 6 — Run the Application

```bash
# Terminal 1: Start backend
cd backend-share
source venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Terminal 2: Start frontend
cd rxlens
npm run dev
```

🎉 **Open** [http://localhost:3000](http://localhost:3000) — You're live!

---

### 🍎 macOS

#### Step 1 — Install Homebrew (if not installed)

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

#### Step 2 — Install System Dependencies

```bash
brew install tesseract node postgresql@16 git
brew services start postgresql@16
```

#### Step 3 — Install Python 3.11 via pyenv

> ⚠️ macOS ships with Python 3.13 via Homebrew which **breaks dependencies**. Use pyenv.

```bash
# Install pyenv
brew install pyenv

# Add pyenv to your shell (bash)
echo 'export PYENV_ROOT="$HOME/.pyenv"' >> ~/.bashrc
echo 'export PATH="$PYENV_ROOT/bin:$PATH"' >> ~/.bashrc
echo 'eval "$(pyenv init -)"' >> ~/.bashrc
source ~/.bashrc

# OR for zsh (default on macOS)
echo 'export PYENV_ROOT="$HOME/.pyenv"' >> ~/.zshrc
echo 'export PATH="$PYENV_ROOT/bin:$PATH"' >> ~/.zshrc
echo 'eval "$(pyenv init -)"' >> ~/.zshrc
source ~/.zshrc

# Install Python 3.11.9
pyenv install 3.11.9
pyenv global 3.11.9

# Verify
python --version  # Should print: Python 3.11.9
```

#### Step 4 — Backend Setup

```bash
cd backend-share

# Create virtualenv
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# → Edit .env with your API keys and settings
```

#### Step 5 — Frontend Setup

```bash
cd rxlens
npm install
cp .env.local.example .env.local
# NEXT_PUBLIC_API_URL=http://localhost:8000
```

#### Step 6 — PostgreSQL Setup

```bash
# Create the database
psql postgres -c "CREATE DATABASE prescription_db;"
psql postgres -c "CREATE USER postgres WITH PASSWORD 'postgres';"
psql postgres -c "GRANT ALL PRIVILEGES ON DATABASE prescription_db TO postgres;"

# Run migrations
cd backend-share
source venv/bin/activate
alembic upgrade head
```

#### Step 7 — Run the Application

```bash
# Terminal 1: Backend
cd backend-share && source venv/bin/activate
uvicorn app.main:app --reload --port 8000

# Terminal 2: Frontend
cd rxlens
npm run dev
```

🎉 **Open** [http://localhost:3000](http://localhost:3000)

---

### 🪟 Windows

#### Step 1 — Install Prerequisites

**Node.js** — Download from [nodejs.org](https://nodejs.org) (LTS version)

**Python 3.11** — Download from [python.org](https://python.org/downloads/release/python-3119/)
> ⚠️ During installation, check **"Add Python to PATH"**

**Git** — Download from [git-scm.com](https://git-scm.com)

**Tesseract OCR** — Download the Windows installer from:
[UB-Mannheim/tesseract](https://github.com/UB-Mannheim/tesseract/wiki)

> After installing Tesseract, add it to PATH:
> `C:\Program Files\Tesseract-OCR`

**PostgreSQL** — Download from [postgresql.org/download/windows](https://www.postgresql.org/download/windows/)

#### Step 2 — Open PowerShell as Administrator and Clone

```powershell
git clone https://github.com/your-username/rxlens.git
cd rxlens
```

#### Step 3 — Backend Setup

```powershell
cd backend-share

# Create virtual environment
python -m venv venv
venv\Scripts\Activate.ps1

# If script execution is blocked, run:
# Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

pip install --upgrade pip
pip install -r requirements.txt

# Copy and configure environment
copy .env.example .env
notepad .env   # Edit your settings
```

#### Step 4 — Frontend Setup

```powershell
# New terminal window
cd rxlens
npm install
copy .env.local.example .env.local
notepad .env.local   # Set NEXT_PUBLIC_API_URL=http://localhost:8000
```

#### Step 5 — PostgreSQL Setup

```powershell
# Open pgAdmin OR use psql from the PostgreSQL bin folder:
psql -U postgres -c "CREATE DATABASE prescription_db;"

# Run migrations
cd backend-share
venv\Scripts\Activate.ps1
alembic upgrade head
```

#### Step 6 — Update Tesseract Path in .env

```env
# Windows path example
TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
```

#### Step 7 — Run the Application

```powershell
# PowerShell Window 1: Backend
cd backend-share
venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# PowerShell Window 2: Frontend
cd rxlens
npm run dev
```

🎉 **Open** [http://localhost:3000](http://localhost:3000)

---

## ⚙️ Environment Configuration

### Backend — `backend-share/.env`

```env
# ── LLM Provider ──────────────────────────────────────────────────────────
# Choose ONE: gemini | openai | ollama | huggingface | template
MODEL_PROVIDER=openai
MODEL_NAME=gpt-4o                       # or gemini-1.5-flash, etc.

# ── API Keys (fill in only the provider you use) ──────────────────────────
OPENAI_API_KEY=sk-...your-key-here...
GEMINI_API_KEY=AIza...your-key-here...
OLLAMA_BASE_URL=http://localhost:11434  # if using Ollama locally

# ── OCR ────────────────────────────────────────────────────────────────────
OCR_PROVIDER=tesseract
TESSERACT_CMD=/usr/bin/tesseract        # Linux/macOS
# TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe  # Windows

# ── Database ───────────────────────────────────────────────────────────────
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/prescription_db

# ── Vector DB (RAG) ────────────────────────────────────────────────────────
VECTOR_DB_ENABLED=true
CHROMA_PERSIST_DIR=./chroma_db

# ── App ────────────────────────────────────────────────────────────────────
ENVIRONMENT=development
SECRET_KEY=change-me-in-production
PORT=8000
```

### Frontend — `rxlens/.env.local`

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

---

## 🤖 LLM Provider Setup

RxLens supports **5 different LLM providers** — swap them by changing a single env variable.

### Option A — Template Mode (Zero Setup, Recommended for Testing)
```env
MODEL_PROVIDER=template
```
> Fully functional without any API keys. Uses rule-based templates for medicine analysis.

### Option B — OpenAI GPT-4o
```env
MODEL_PROVIDER=openai
MODEL_NAME=gpt-4o
OPENAI_API_KEY=sk-...
```
Get your key at [platform.openai.com](https://platform.openai.com/api-keys)

### Option C — Google Gemini
```env
MODEL_PROVIDER=gemini
MODEL_NAME=gemini-1.5-flash
GEMINI_API_KEY=AIza...
```
Get your key at [aistudio.google.com](https://aistudio.google.com/app/apikey)

### Option D — Ollama (Fully Local, No API Key)
```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Pull a model
ollama pull llama3.2
```
```env
MODEL_PROVIDER=ollama
MODEL_NAME=llama3.2
OLLAMA_BASE_URL=http://localhost:11434
```

### Option E — HuggingFace Local Model
```env
MODEL_PROVIDER=huggingface
HF_MODEL_PATH=mistralai/Mistral-7B-Instruct-v0.3
HF_DEVICE=cuda     # or cpu / mps (Apple Silicon)
HF_LOAD_IN_4BIT=true  # Reduces VRAM usage
```

---

## 🐳 Running with Docker (Recommended)

The fastest way to get everything running — no manual PostgreSQL setup required.

### Prerequisites
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running

### Steps

```bash
# 1. Clone the repository
git clone https://github.com/your-username/rxlens.git
cd rxlens/backend-share

# 2. Copy and configure env
cp .env.example .env
# Edit .env — set your MODEL_PROVIDER and API keys

# 3. Build and launch backend + PostgreSQL
docker-compose up --build

# 4. In a new terminal — run the frontend
cd ../rxlens
npm install
cp .env.local.example .env.local
npm run dev
```

**Services started by Docker:**

| Service | URL |
|---------|-----|
| FastAPI Backend | http://localhost:8000 |
| API Docs (Swagger) | http://localhost:8000/docs |
| PostgreSQL | localhost:5432 |
| Next.js Frontend | http://localhost:3000 |

### Stop Everything
```bash
docker-compose down
# To also delete database volume:
docker-compose down -v
```

---

## 🗄️ Database Setup

### Run Migrations

```bash
cd backend-share
source venv/bin/activate  # (or venv\Scripts\Activate.ps1 on Windows)

# Apply all migrations
alembic upgrade head

# Check current migration status
alembic current

# Roll back one migration
alembic downgrade -1
```

### Create a New Migration (after schema changes)

```bash
alembic revision --autogenerate -m "describe your change"
alembic upgrade head
```

---

## 🌱 Seeding the Vector Store

The RAG system uses ChromaDB pre-loaded with medicine data. Run the seeder once after setup:

```bash
cd backend-share
source venv/bin/activate

python scripts/seed_vector_store.py
```

> This reads `data/medicine_seed.json` and populates ChromaDB at `./chroma_db/`. Run it once — it's idempotent.

If `VECTOR_DB_ENABLED=false` or ChromaDB is unavailable, the app gracefully falls back to template-based analysis.

---

## 📁 Project Structure

```
rxlens/
│
├── 📂 rxlens/                      # Next.js 15 Frontend
│   ├── src/
│   │   ├── app/
│   │   │   ├── page.tsx            # Home / landing
│   │   │   ├── upload/             # Prescription upload page
│   │   │   ├── results/            # Analysis results page
│   │   │   └── history/            # Prescription history
│   │   ├── components/
│   │   │   ├── ui/                 # Reusable UI primitives
│   │   │   ├── upload/             # Upload components
│   │   │   ├── results/            # Result display components
│   │   │   └── shared/             # Shared layout components
│   │   ├── hooks/                  # Custom React hooks
│   │   ├── lib/                    # Utilities & API client
│   │   └── types/                  # TypeScript type definitions
│   ├── .env.local                  # Frontend env (gitignored)
│   └── package.json
│
└── 📂 backend-share/               # FastAPI Backend
    ├── app/
    │   ├── main.py                 # App entry point
    │   ├── core/
    │   │   ├── settings.py         # All configuration
    │   │   ├── database.py         # Async SQLAlchemy
    │   │   ├── dependencies.py     # FastAPI DI
    │   │   └── rate_limit.py       # Sliding window rate limiter
    │   ├── providers/
    │   │   ├── openai_provider.py
    │   │   ├── gemini_provider.py
    │   │   ├── ollama_provider.py
    │   │   ├── huggingface_provider.py
    │   │   ├── template_provider.py  # Zero-dependency fallback
    │   │   └── ocr_provider.py
    │   ├── services/
    │   │   ├── llm_service.py      # LLM abstraction layer
    │   │   ├── analysis_service.py # Core medicine analysis
    │   │   └── vector_store_service.py  # ChromaDB RAG
    │   ├── api/routes/
    │   │   ├── upload.py           # POST /api/v1/upload
    │   │   ├── analysis.py         # POST /api/v1/analyze
    │   │   ├── prescriptions.py    # GET /api/v1/prescriptions
    │   │   └── health.py           # GET /api/v1/health
    │   ├── models/                 # SQLAlchemy ORM models
    │   ├── schemas/                # Pydantic request/response schemas
    │   └── repositories/          # DB access layer
    ├── alembic/                    # DB migrations
    ├── data/medicine_seed.json     # Vector store seed data
    ├── scripts/seed_vector_store.py
    ├── tests/                      # Pytest test suite (38/38 ✅)
    ├── docker-compose.yml
    ├── Dockerfile
    ├── requirements.txt
    └── .env.example
```

---

## 📡 API Reference

Once the backend is running, visit **http://localhost:8000/docs** for the full interactive Swagger UI.

### Core Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Service info & health |
| `GET` | `/api/v1/health` | Detailed health check |
| `POST` | `/api/v1/upload` | Upload prescription image |
| `POST` | `/api/v1/analyze` | Analyze extracted medicines |
| `GET` | `/api/v1/prescriptions` | Fetch prescription history |
| `GET` | `/api/v1/prescriptions/{id}` | Get single prescription |

### Example — Upload & Analyze

```bash
# Upload a prescription image
curl -X POST http://localhost:8000/api/v1/upload \
  -F "file=@prescription.jpg"

# Returns: { "session_id": "abc123", "extracted_text": "...", "medicines": [...] }

# Analyze extracted medicines
curl -X POST http://localhost:8000/api/v1/analyze \
  -H "Content-Type: application/json" \
  -d '{"session_id": "abc123", "medicines": ["Metformin 500mg", "Aspirin 75mg"]}'
```

---

## 🧪 Running Tests

```bash
cd backend-share
source venv/bin/activate  # (venv\Scripts\Activate.ps1 on Windows)

# Run all tests
pytest

# Run with coverage report
pytest --cov=app --cov-report=term-missing

# Run a specific test file
pytest tests/test_api.py -v

# Run tests matching a keyword
pytest -k "test_upload" -v
```

**Current Status: ✅ 38/38 tests passing**

---

## 🔧 Troubleshooting

### ❌ `python: command not found` or wrong Python version

```bash
# Use pyenv (recommended)
pyenv install 3.11.9 && pyenv global 3.11.9

# Or explicitly call:
python3.11 -m venv venv
```

### ❌ `ModuleNotFoundError` on startup

```bash
# Make sure venv is activated
source venv/bin/activate  # Linux/macOS
venv\Scripts\Activate.ps1  # Windows

pip install -r requirements.txt
```

### ❌ `TesseractNotFoundError`

```bash
# Linux
sudo apt install tesseract-ocr

# macOS
brew install tesseract

# Windows — install from UB-Mannheim and update .env:
TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
```

### ❌ `could not connect to server` (PostgreSQL)

```bash
# Linux
sudo systemctl start postgresql

# macOS
brew services start postgresql@16

# Verify
psql -U postgres -c "\l"
```

### ❌ ChromaDB / Vector Store Errors

These are **non-fatal** — the app continues without RAG. To fix:

```bash
# Ensure chromadb is installed
pip install chromadb==0.5.3

# Re-run the seeder
python scripts/seed_vector_store.py
```

To disable entirely:
```env
VECTOR_DB_ENABLED=false
```

### ❌ Frontend `ECONNREFUSED` (can't reach backend)

Ensure the backend is running on port 8000 and `.env.local` has:
```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### ❌ `asyncpg` install fails on Python 3.13

This is the known incompatibility. Install Python 3.11 and recreate your venv:
```bash
pyenv install 3.11.9
pyenv local 3.11.9
python -m venv venv --clear
source venv/bin/activate
pip install -r requirements.txt
```

---

## 🗺️ Development Workflow

```bash
# Run backend in watch mode
uvicorn app.main:app --reload

# Run frontend in dev mode
npm run dev

# Type-check frontend
npx tsc --noEmit

# Lint backend
ruff check app/
black app/ --check

# Format backend
black app/
ruff check app/ --fix
```

---

## 🚢 Production Deployment

### Backend
```bash
# Production mode (no reload, workers scaled)
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4

# Or with gunicorn
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker
```

Update `.env` for production:
```env
ENVIRONMENT=production
DEBUG=false
SECRET_KEY=your-super-secret-random-string-here
```

### Frontend
```bash
npm run build
npm run start
# Or deploy to Vercel — vercel.json is already configured ✅
```

---

## 🙏 Acknowledgements

- [FastAPI](https://fastapi.tiangolo.com) — Modern Python web framework
- [Next.js](https://nextjs.org) — The React framework for production
- [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) — Open-source OCR engine
- [ChromaDB](https://trychroma.com) — AI-native vector database
- [sentence-transformers](https://sbert.net) — State-of-the-art embeddings

---

<div align="center">

Built with ❤️ | **RxLens v2.0.0** — 38/38 tests passing 🟢

*Scan smarter. Stay safer.*

</div>
