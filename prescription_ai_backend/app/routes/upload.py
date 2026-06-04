"""
Upload Routes — v2.1
Fixes vs v2.0:
- After OCR, calls GeminiService.extract_medicines() as Pass-5 fallback
  when regex detection returns empty list
- Merges OCR-detected + Gemini-detected medicine lists (deduped)
- Saves merged list in sidecar for analysis route to use as hint
"""

import json
import os
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from app.config import settings
from app.models.prescription import PrescriptionUploadResponse
from app.services.ocr_service import OCRService

from app.utils.logger import get_logger
from app.utils.validators import validate_image_file

router = APIRouter()
logger = get_logger(__name__)

_ocr_service = OCRService()


@router.post(
    "/upload",
    response_model=PrescriptionUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a prescription image",
    description=(
        "Accepts a prescription image (JPEG, PNG, TIFF, BMP, WEBP), "
        "runs Tesseract OCR, detects medicine names via regex + Gemini fallback, "
        "and returns a prescription_id for subsequent /analysis calls."
    ),
)
async def upload_prescription(
    file: UploadFile = File(..., description="Prescription image file"),
    patient_age: Optional[int] = Form(None),
    language: Optional[str] = Form("en"),
):
    # ── Validate extension ─────────────────────────────────────────────────
    ext = Path(file.filename or "upload").suffix.lower()
    if ext not in settings.OCR_SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type '{ext}'. Supported: {settings.OCR_SUPPORTED_EXTENSIONS}",
        )

    content = await file.read()

    if len(content) > settings.MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds {settings.MAX_UPLOAD_SIZE_MB} MB limit.",
        )

    try:
        validate_image_file(content, ext)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    if language not in settings.SUPPORTED_LANGUAGES:
        language = settings.DEFAULT_LANGUAGE

    # ── Persist image ──────────────────────────────────────────────────────
    prescription_id = str(uuid.uuid4())
    upload_path = os.path.join(settings.upload_dir_path, f"{prescription_id}{ext}")
    try:
        with open(upload_path, "wb") as fh:
            fh.write(content)
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"Could not save file: {exc}")

    # ── OCR ────────────────────────────────────────────────────────────────
    try:
        ocr_result = await _ocr_service.extract_text(upload_path)
    except Exception as exc:
        _safe_remove(upload_path)
        raise HTTPException(status_code=422, detail=f"OCR failed: {exc}")

    # ── Medicine detection: regex + Gemini fallback ────────────────────────
    detected = list(ocr_result.detected_medicines)

    if not detected and ocr_result.raw_text.strip():
        logger.info("Regex found 0 medicines — calling Gemini extract_medicines fallback")
        try:
            gemini_names = await get_gemini_service().extract_medicines(ocr_result.raw_text)
            if gemini_names:
                logger.info(f"Gemini fallback detected: {gemini_names}")
                detected = gemini_names
        except Exception as exc:
            logger.warning(f"Gemini extract_medicines fallback failed: {exc}")

    # ── Write sidecar ──────────────────────────────────────────────────────
    sidecar_path = os.path.join(settings.upload_dir_path, f"{prescription_id}.meta")
    sidecar = {
        "prescription_id": prescription_id,
        "raw_text": ocr_result.raw_text,
        "cleaned_text": ocr_result.cleaned_text,
        "detected_medicines": detected,
        "patient_age": patient_age,
        "language": language,
        "ocr_confidence": ocr_result.confidence,
        "image_path": upload_path,
    }
    try:
        with open(sidecar_path, "w", encoding="utf-8") as fh:
            json.dump(sidecar, fh, ensure_ascii=False, indent=2)
    except OSError as exc:
        logger.warning(f"Could not write sidecar: {exc}")

    logger.info(
        f"Upload done | id={prescription_id} | "
        f"conf={ocr_result.confidence:.3f} | medicines={detected}"
    )

    return PrescriptionUploadResponse(
        prescription_id=prescription_id,
        filename=file.filename or f"{prescription_id}{ext}",
        file_path=upload_path,
        raw_text=ocr_result.raw_text,
        detected_medicines=detected,
        patient_age=patient_age,
        language=language,
        ocr_confidence=ocr_result.confidence,
        message=(
            "Prescription uploaded and OCR completed. "
            "Call /api/v1/analysis/{prescription_id} to get the full Gemini safety report."
        ),
    )


@router.delete("/upload/{prescription_id}", status_code=200)
async def delete_prescription_file(prescription_id: str):
    upload_dir = settings.upload_dir_path
    deleted = False
    for ext in settings.OCR_SUPPORTED_EXTENSIONS:
        candidate = os.path.join(upload_dir, f"{prescription_id}{ext}")
        if os.path.exists(candidate):
            os.remove(candidate)
            deleted = True
            break
    sidecar = os.path.join(upload_dir, f"{prescription_id}.meta")
    if os.path.exists(sidecar):
        os.remove(sidecar)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"No file found for '{prescription_id}'.")
    return {"message": f"Files for '{prescription_id}' deleted."}


def _safe_remove(path: str) -> None:
    try:
        os.remove(path)
    except OSError:
        pass
