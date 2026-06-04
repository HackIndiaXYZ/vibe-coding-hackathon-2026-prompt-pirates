#!/usr/bin/env bash
# ============================================================
# AI Prescription Explainer — Ollama Edition (v3)
# ============================================================
set -euo pipefail

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; BLUE='\033[0;34m'; NC='\033[0m'
info()    { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*" >&2; }
section() { echo -e "\n${BLUE}━━━ $* ━━━${NC}"; }

cd "$(dirname "${BASH_SOURCE[0]}")"

section "AI Prescription Explainer — Ollama Edition v3.0"

# ── Ollama check ──────────────────────────────────────────
section "Ollama Check"
OLLAMA_URL="${OLLAMA_BASE_URL:-http://localhost:11434}"
OLLAMA_MODEL="${OLLAMA_MODEL:-llama3.2:3b}"

if command -v ollama &>/dev/null; then
    info "Ollama binary found ✓"
    if curl -sf "$OLLAMA_URL/api/tags" > /dev/null 2>&1; then
        info "Ollama server is running at $OLLAMA_URL ✓"
        # Check model is pulled
        if ollama list 2>/dev/null | grep -q "${OLLAMA_MODEL%%:*}"; then
            info "Model '${OLLAMA_MODEL}' is available ✓"
        else
            warn "Model '${OLLAMA_MODEL}' not found."
            warn "Pulling now... (this may take a few minutes)"
            ollama pull "$OLLAMA_MODEL" && info "Model pulled ✓" || warn "Pull failed — start manually"
        fi
    else
        warn "Ollama server not running. Starting it..."
        ollama serve &>/dev/null &
        sleep 3
        curl -sf "$OLLAMA_URL/api/tags" > /dev/null && info "Ollama started ✓" || warn "Could not start Ollama"
    fi
else
    warn "Ollama not installed."
    warn "  macOS/Linux: curl -fsSL https://ollama.com/install.sh | sh"
    warn "  Windows:     https://ollama.com/download"
fi

# ── Python check ──────────────────────────────────────────
section "Python Check"
PYTHON_BIN="${PYTHON_BIN:-python3}"
PV=$($PYTHON_BIN --version 2>&1 | awk '{print $2}')
info "Python $PV ✓"

# ── Tesseract check ───────────────────────────────────────
section "Tesseract Check"
if command -v tesseract &>/dev/null; then
    info "Tesseract: $(tesseract --version 2>&1 | head -1) ✓"
else
    warn "Tesseract not installed."
    warn "  Ubuntu: sudo apt install tesseract-ocr"
    warn "  macOS:  brew install tesseract"
fi

# ── Venv ──────────────────────────────────────────────────
section "Virtual Environment"
VENV="${VENV_DIR:-.venv}"
[[ ! -d "$VENV" ]] && $PYTHON_BIN -m venv "$VENV" && info "Created $VENV"
source "$VENV/bin/activate"
info "Activated ✓"

# ── Dependencies ──────────────────────────────────────────
section "Dependencies"
if [[ "${SKIP_INSTALL:-0}" != "1" ]]; then
    pip install --quiet --upgrade pip
    pip install --quiet -r requirements.txt
    info "Dependencies installed ✓"
fi

# ── .env ──────────────────────────────────────────────────
section "Configuration"
[[ ! -f ".env" ]] && cp .env.example .env && warn "Created .env from .env.example"
info ".env ready ✓"

mkdir -p uploads logs

# ── Start ─────────────────────────────────────────────────
section "Starting Server"
HOST="${HOST:-0.0.0.0}"; PORT="${PORT:-8000}"
info "Model:    $OLLAMA_MODEL"
info "Ollama:   $OLLAMA_URL"
info "API Docs: http://localhost:$PORT/docs"
info "Health:   http://localhost:$PORT/api/v1/health"
echo ""

uvicorn app.main:app --host "$HOST" --port "$PORT" \
    --reload --reload-dir app --log-level info
