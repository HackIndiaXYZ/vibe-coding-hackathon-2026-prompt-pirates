"""
Analysis Routes — Ollama edition
Same API surface as the Gemini version.
Only the service import changes: get_gemini_service → get_ollama_service
"""

import json
import os
from typing import Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.config import settings
from app.models.response import (
    DosageSafetyAssessment,
    FullAnalysisResponse,
    MedicineAnalysis,
)
from app.services.ollama_service import get_ollama_service
from app.utils.logger import get_logger

router = APIRouter()
logger = get_logger(__name__)


class AnalysisRequest(BaseModel):
    prescription_id: str
    patient_age: Optional[int] = None
    language: Optional[str] = "en"
    medicines: Optional[list[str]] = None


@router.get(
    "/analysis/{prescription_id}",
    response_model=FullAnalysisResponse,
    summary="Run full Ollama prescription analysis",
    description=(
        "Loads OCR text from the sidecar saved during /upload, "
        "sends it to the local Ollama model, and returns a structured "
        "FullAnalysisResponse with per-medicine safety details."
    ),
)
async def analyse_prescription(
    prescription_id: str,
    patient_age: Optional[int] = None,
    language: Optional[str] = "en",
):
    return await _run_analysis(prescription_id, patient_age, language or "en", None)


@router.post(
    "/analysis",
    response_model=FullAnalysisResponse,
    summary="Run full Ollama prescription analysis (POST)",
)
async def analyse_prescription_post(body: AnalysisRequest):
    return await _run_analysis(
        body.prescription_id,
        body.patient_age,
        body.language or "en",
        body.medicines,
    )


# ── Pipeline ───────────────────────────────────────────────────────────────

async def _run_analysis(
    prescription_id: str,
    patient_age: Optional[int],
    language: str,
    medicines_override: Optional[list[str]],
) -> FullAnalysisResponse:

    if language not in settings.SUPPORTED_LANGUAGES:
        language = settings.DEFAULT_LANGUAGE

    # Load sidecar
    sidecar_path = os.path.join(settings.upload_dir_path, f"{prescription_id}.meta")
    if not os.path.exists(sidecar_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"No prescription found for id '{prescription_id}'. "
                "Please upload the image first via POST /api/v1/upload."
            ),
        )

    try:
        with open(sidecar_path, encoding="utf-8") as fh:
            sidecar = json.load(fh)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to read sidecar: {exc}")

    raw_text: str = sidecar.get("raw_text", "")
    if not raw_text.strip():
        raise HTTPException(
            status_code=422, detail="OCR extracted no text from the uploaded image."
        )

    if patient_age is None:
        patient_age = sidecar.get("patient_age")
    if language == settings.DEFAULT_LANGUAGE:
        language = sidecar.get("language", settings.DEFAULT_LANGUAGE)

    if medicines_override:
        override_str = ", ".join(m.strip() for m in medicines_override if m.strip())
        raw_text = f"[MEDICINE LIST: {override_str}]\n\n{raw_text}"

    logger.info(
        f"Calling Ollama ({settings.OLLAMA_MODEL}) | "
        f"prescription_id={prescription_id} | age={patient_age} | lang={language}"
    )

    svc = get_ollama_service()
    result = await svc.analyse_prescription(
        ocr_text=raw_text,
        patient_age=patient_age,
        language=language,
    )

    if "_error" in result:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Ollama error: {result['_error']}",
        )

    # Map to Pydantic models
    analyses: list[MedicineAnalysis] = []
    for item in result.get("medicines", []):
        try:
            dsa_raw = item.get("dosage_safety_assessment", {})
            dsa = DosageSafetyAssessment(
                is_safe=bool(dsa_raw.get("is_safe", True)),
                prescribed_dose=str(dsa_raw.get("prescribed_dose", "")),
                standard_dose=str(dsa_raw.get("standard_dose", "")),
                notes=_to_list(dsa_raw.get("notes", [])),
            )
            analyses.append(MedicineAnalysis(
                medicine_name=str(item.get("medicine_name", "Unknown")),
                dosage=str(item.get("dosage", "")),
                frequency=str(item.get("frequency", "")),
                duration=str(item.get("duration", "")),
                use_case=str(item.get("use_case", "")),
                side_effects=_to_list(item.get("side_effects", [])),
                serious_side_effects=_to_list(item.get("serious_side_effects", [])),
                alternatives=_to_list(item.get("alternatives", [])),
                age_warnings=_to_list(item.get("age_warnings", [])),
                causes_drowsiness=bool(item.get("causes_drowsiness", False)),
                lifestyle_recommendations=_to_list(item.get("lifestyle_recommendations", [])),
                dosage_safety_assessment=dsa,
                severity_level=_safe_severity(item.get("severity_level", "low")),
            ))
        except Exception as exc:
            logger.warning(f"Skipping malformed medicine entry: {exc}")

    any_drowsy  = any(a.causes_drowsiness for a in analyses)
    any_unsafe  = any(not a.dosage_safety_assessment.is_safe for a in analyses)
    any_age_war = any(bool(a.age_warnings) for a in analyses)

    rank = {"low": 0, "medium": 1, "high": 2, "critical": 3}
    overall_sev = max((a.severity_level for a in analyses), key=lambda s: rank.get(s, 0), default="low")

    parts = [f"Analysed {len(analyses)} medicine(s)."]
    if any_drowsy:  parts.append("⚠ Drowsiness risk.")
    if any_unsafe:  parts.append("⚠ Dosage concern.")
    if any_age_war: parts.append("⚠ Age-specific warning.")

    return FullAnalysisResponse(
        prescription_id=prescription_id,
        patient_age=patient_age,
        language=language,
        medicines=analyses,
        overall_drowsiness_warning=any_drowsy,
        overall_dosage_concern=any_unsafe,
        overall_age_warning=any_age_war,
        overall_severity=overall_sev,
        total_medicines_analysed=len(analyses),
        summary=" ".join(parts),
    )


def _to_list(v) -> list:
    if isinstance(v, list): return v
    if isinstance(v, str) and v: return [v]
    return []

def _safe_severity(v: str) -> str:
    return v.lower() if v.lower() in {"low","medium","high","critical"} else "low"
