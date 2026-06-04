"""
Ollama Service — v3.0
Local LLM integration via the Ollama Python SDK.
Drop-in replacement for gemini_service.py — same public interface.

Supports any model pulled via `ollama pull <model>`.
Recommended: llama3.2:3b, llama3.1:8b, mistral:7b, phi3:mini
"""

import json
import logging
import asyncio
from typing import Optional

import ollama
from ollama import AsyncClient

from app.config import settings

logger = logging.getLogger(__name__)

# ── Prompts ────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a senior clinical pharmacist and medical AI assistant.
Your ONLY job is to analyse prescription text and return a valid JSON object.
You MUST return ONLY raw JSON. No markdown. No code fences. No explanations.
No text before or after the JSON. Start your response with { and end with }."""

USER_PROMPT_TEMPLATE = """Analyse this prescription and return structured JSON.

PRESCRIPTION TEXT:
---
{ocr_text}
---

Patient Age: {patient_age}
Response language: {language}

Return ONLY this JSON structure with no extra text:

{{
  "medicines": [
    {{
      "medicine_name": "exact name from prescription",
      "dosage": "e.g. 500mg",
      "frequency": "e.g. Once daily / Twice daily / Three times daily",
      "duration": "e.g. 7 days / 2 weeks / ongoing",
      "use_case": "what this medicine treats",
      "side_effects": ["side effect 1", "side effect 2"],
      "serious_side_effects": ["serious side effect 1"],
      "alternatives": ["alternative 1", "alternative 2"],
      "age_warnings": ["warning for this patient age if any"],
      "causes_drowsiness": false,
      "lifestyle_recommendations": ["recommendation 1", "recommendation 2"],
      "dosage_safety_assessment": {{
        "is_safe": true,
        "prescribed_dose": "dose as written",
        "standard_dose": "normal recommended dose",
        "notes": ["any concern"]
      }},
      "severity_level": "low"
    }}
  ]
}}

Rules:
- severity_level must be: low, medium, high, or critical
- causes_drowsiness must be true or false (boolean, not string)
- All arrays must exist even if empty []
- Extract EVERY medicine visible in the prescription text
- If the text is garbled, use your medical knowledge to identify likely medicines
- Output all text values in {language}"""

LANGUAGE_NAMES = {
    "en": "English", "ta": "Tamil", "hi": "Hindi",
    "fr": "French", "es": "Spanish", "de": "German",
    "zh": "Chinese (Simplified)", "ar": "Arabic",
}


class OllamaService:
    """
    Local LLM service using Ollama.
    Uses the async Ollama client with structured JSON output.

    Usage:
        svc = OllamaService()
        result = await svc.analyse_prescription(ocr_text, patient_age=45)
    """

    def __init__(self):
        self._client = AsyncClient(host=settings.OLLAMA_BASE_URL)
        self._model = settings.OLLAMA_MODEL
        logger.info(
            f"OllamaService initialised | model={self._model} | "
            f"base_url={settings.OLLAMA_BASE_URL}"
        )

    async def analyse_prescription(
        self,
        ocr_text: str,
        patient_age: Optional[int] = None,
        language: str = "en",
    ) -> dict:
        """
        Send OCR text to local Ollama model and return parsed JSON.
        Falls back gracefully on timeout or parse errors.
        """
        if not ocr_text or not ocr_text.strip():
            logger.warning("OllamaService received empty OCR text.")
            return {"medicines": []}

        age_str = str(patient_age) if patient_age is not None else "Not specified"
        lang_name = LANGUAGE_NAMES.get(language, "English")

        prompt = USER_PROMPT_TEMPLATE.format(
            ocr_text=ocr_text[:4000],   # stay within context window
            patient_age=age_str,
            language=lang_name,
        )

        logger.info(
            f"Sending to Ollama ({self._model}) | "
            f"prompt_chars={len(prompt)} | age={age_str} | lang={lang_name}"
        )

        try:
            response = await asyncio.wait_for(
                self._client.chat(
                    model=self._model,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user",   "content": prompt},
                    ],
                    options={
                        "temperature":    settings.OLLAMA_TEMPERATURE,
                        "num_predict":    settings.OLLAMA_NUM_PREDICT,
                        "top_p":          settings.OLLAMA_TOP_P,
                        "repeat_penalty": settings.OLLAMA_REPEAT_PENALTY,
                    },
                    format="json",   # Ollama structured-output mode (Ollama ≥ 0.1.9)
                ),
                timeout=settings.OLLAMA_TIMEOUT,
            )

            raw_text = response["message"]["content"]
            logger.debug(f"Ollama raw response ({len(raw_text)} chars): {raw_text[:200]}")
            return self._parse_response(raw_text)

        except asyncio.TimeoutError:
            msg = (
                f"Ollama timed out after {settings.OLLAMA_TIMEOUT}s. "
                f"Consider using a smaller model (e.g. phi3:mini) or increasing OLLAMA_TIMEOUT."
            )
            logger.error(msg)
            return {"medicines": [], "_error": msg}

        except ollama.ResponseError as exc:
            # Model not pulled yet
            if "model" in str(exc).lower() and "not found" in str(exc).lower():
                msg = (
                    f"Model '{self._model}' not found. "
                    f"Run: ollama pull {self._model}"
                )
            else:
                msg = f"Ollama API error: {exc}"
            logger.error(msg)
            return {"medicines": [], "_error": msg}

        except Exception as exc:
            logger.error(f"Ollama call failed: {exc}", exc_info=True)
            return {"medicines": [], "_error": str(exc)}

    # ── JSON parsing ───────────────────────────────────────────────────────

    def _parse_response(self, raw: str) -> dict:
        """
        Parse Ollama JSON response.
        Handles:
        - Clean JSON (ideal)
        - JSON wrapped in ```json ... ``` fences
        - JSON embedded in explanatory text (extract first {...} block)
        """
        cleaned = raw.strip()

        # Strip markdown fences
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            cleaned = "\n".join(
                ln for ln in lines if not ln.strip().startswith("```")
            ).strip()

        # Try direct parse first
        try:
            data = json.loads(cleaned)
            return self._normalise(data)
        except json.JSONDecodeError:
            pass

        # Try to extract first {...} block from the text
        start = cleaned.find("{")
        end   = cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                data = json.loads(cleaned[start:end + 1])
                return self._normalise(data)
            except json.JSONDecodeError:
                pass

        logger.error(f"Could not parse Ollama JSON. Raw (first 400): {raw[:400]}")
        return {"medicines": [], "_parse_error": "JSON decode failed"}

    @staticmethod
    def _normalise(data: dict) -> dict:
        """Ensure 'medicines' key always exists."""
        if "medicines" not in data:
            if isinstance(data, list):
                return {"medicines": data}
            return {"medicines": [data]}
        return data

    # ── Health check ───────────────────────────────────────────────────────

    async def health_check(self) -> dict:
        """
        Verify Ollama is reachable and the configured model is available.
        Returns dict with 'ok' bool and 'message' string.
        """
        try:
            models_response = await self._client.list()
            available = [m["name"] for m in models_response.get("models", [])]
            model_ready = any(
                self._model in m or m.startswith(self._model.split(":")[0])
                for m in available
            )
            return {
                "ok": True,
                "ollama_reachable": True,
                "model_ready": model_ready,
                "model": self._model,
                "available_models": available,
                "message": (
                    f"Model '{self._model}' ready."
                    if model_ready
                    else f"Model '{self._model}' NOT pulled. Run: ollama pull {self._model}"
                ),
            }
        except Exception as exc:
            return {
                "ok": False,
                "ollama_reachable": False,
                "model_ready": False,
                "model": self._model,
                "available_models": [],
                "message": (
                    f"Cannot reach Ollama at {settings.OLLAMA_BASE_URL}. "
                    f"Is Ollama running? Error: {exc}"
                ),
            }


# ── Module-level singleton ─────────────────────────────────────────────────

_ollama_service: Optional[OllamaService] = None


def get_ollama_service() -> OllamaService:
    """Return (or lazily create) the module-level OllamaService singleton."""
    global _ollama_service
    if _ollama_service is None:
        _ollama_service = OllamaService()
    return _ollama_service
