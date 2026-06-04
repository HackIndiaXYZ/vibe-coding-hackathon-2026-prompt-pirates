"""
AI Prescription Explainer & Safety Assistant
FastAPI Entry Point — Ollama (local) edition v3.0
"""

import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.routes import analysis, health, upload
from app.utils.logger import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}...")

    from app.services.ollama_service import get_ollama_service
    svc = get_ollama_service()
    status = await svc.health_check()

    if not status["ollama_reachable"]:
        logger.warning(
            f"⚠  Ollama is NOT reachable at {settings.OLLAMA_BASE_URL}. "
            "Start Ollama before making analysis requests."
        )
    elif not status["model_ready"]:
        logger.warning(
            f"⚠  Model '{settings.OLLAMA_MODEL}' is not pulled. "
            f"Run:  ollama pull {settings.OLLAMA_MODEL}"
        )
    else:
        logger.info(f"✓  Ollama ready | model={settings.OLLAMA_MODEL}")

    yield
    logger.info("Shutdown complete.")


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        description=(
            "AI-powered prescription image analyser running fully locally via Ollama. "
            "Extracts text with Tesseract OCR, then sends it to a local LLM "
            "(llama3.2, mistral, phi3, etc.) for structured analysis: "
            "medicines, dosage, side effects, alternatives, age warnings, and more. "
            "No API keys. No internet required."
        ),
        version=settings.APP_VERSION,
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def timing_header(request: Request, call_next):
        t = time.perf_counter()
        resp = await call_next(request)
        resp.headers["X-Process-Time"] = f"{time.perf_counter() - t:.4f}s"
        return resp

    @app.exception_handler(Exception)
    async def global_exc(request: Request, exc: Exception):
        logger.error(f"Unhandled: {request.url} → {exc}", exc_info=True)
        return JSONResponse(status_code=500, content={
            "error": "internal_server_error",
            "message": str(exc),
        })

    app.include_router(health.router,   prefix="/api/v1", tags=["Health"])
    app.include_router(upload.router,   prefix="/api/v1", tags=["Upload"])
    app.include_router(analysis.router, prefix="/api/v1", tags=["Analysis"])

    @app.get("/", tags=["Root"])
    async def root():
        return {
            "service":      settings.APP_NAME,
            "version":      settings.APP_VERSION,
            "status":       "running",
            "model":        settings.OLLAMA_MODEL,
            "ollama_url":   settings.OLLAMA_BASE_URL,
            "docs":         "/docs",
            "architecture": "Ollama local LLM — no API keys needed",
        }

    return app


app = create_app()
