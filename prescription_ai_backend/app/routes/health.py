"""
Health Routes — Ollama edition
Checks Ollama reachability and model availability.
"""

import os
import shutil
import time

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.config import settings
from app.utils.logger import get_logger

router  = APIRouter()
logger  = get_logger(__name__)
_START  = time.time()


class HealthResponse(BaseModel):
    status: str
    uptime_seconds: float
    version: str
    environment: str
    services: dict


@router.get("/health", response_model=HealthResponse, summary="Liveness probe")
async def health_check():
    from app.services.ollama_service import get_ollama_service
    uptime = round(time.time() - _START, 2)

    ollama_status = await get_ollama_service().health_check()
    disk = shutil.disk_usage("/")

    services = {
        "ollama_reachable": ollama_status["ollama_reachable"],
        "model":            ollama_status["model"],
        "model_ready":      ollama_status["model_ready"],
        "ollama_message":   ollama_status["message"],
        "available_models": ollama_status.get("available_models", []),
        "disk_free_gb":     round(disk.free / (1024 ** 3), 2),
        "tesseract_path":   settings.TESSERACT_CMD,
    }

    overall = "ok" if ollama_status["ok"] and ollama_status["model_ready"] else "degraded"
    return HealthResponse(
        status=overall,
        uptime_seconds=uptime,
        version=settings.APP_VERSION,
        environment=settings.ENVIRONMENT,
        services=services,
    )


@router.get("/ready", summary="Readiness probe")
async def readiness_check():
    from app.services.ollama_service import get_ollama_service
    status = await get_ollama_service().health_check()
    if not status["ollama_reachable"]:
        return JSONResponse(status_code=503, content={
            "status": "not_ready",
            "reason": f"Ollama unreachable at {settings.OLLAMA_BASE_URL}. Is Ollama running?"
        })
    if not status["model_ready"]:
        return JSONResponse(status_code=503, content={
            "status": "not_ready",
            "reason": f"Model not pulled. Run: ollama pull {settings.OLLAMA_MODEL}"
        })
    return {"status": "ready", "model": settings.OLLAMA_MODEL}
