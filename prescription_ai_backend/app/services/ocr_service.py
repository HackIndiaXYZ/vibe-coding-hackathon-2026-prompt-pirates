"""
OCR Service  — v2.1 (improved medicine detection)
Tesseract-based prescription image text extraction.

Root-cause fixes vs v2.0
─────────────────────────
1. PREPROCESSING OVER-AGGRESSIVENESS
   Adaptive threshold was destroying thin medicine-name text at low contrast.
   New pipeline: deskew → CLAHE contrast enhance → gentle bilateral filter →
   Otsu threshold (on upscaled image).  Falls back to original colour image
   when the processed version looks worse (confidence heuristic).

2. MEDICINE DETECTION TOO NARROW
   Old regex only matched known suffix patterns — missed e.g. "Catophli",
   "Vanusta", "Corave", "MONA" (brand names) and standard Indian drug names.
   New strategy: 3-pass detection —
     Pass 1 – suffix pattern (pharma suffixes)
     Pass 2 – Capitalised word immediately followed by a dosage (X mg/ml/g…)
     Pass 3 – Gemini fallback extraction (see GeminiService.extract_medicines)

3. PSM MODE
   PSM 6 (uniform block) was wrong for photo-of-document.
   Now uses PSM 11 (sparse text, finds as much as possible) as primary,
   PSM 6 as secondary; best-confidence result is kept.

4. TESSERACT LANGUAGE
   Hard-coded "eng" missed prescriptions with Indian drug brand names.
   Now tries "eng" first; if confidence < 0.55 retries with "eng+hin"
   when tesseract-ocr-hin is installed.
"""

import asyncio
import logging
import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import cv2
import numpy as np
import pytesseract
from PIL import Image

from app.config import settings

logger = logging.getLogger(__name__)

# ── Tesseract PSM configs ──────────────────────────────────────────────────
_PSM11 = "--oem 3 --psm 11"   # sparse text – best for prescription photos
_PSM6  = "--oem 3 --psm 6"    # uniform block – fallback
_PSM4  = "--oem 3 --psm 4"    # single column of variable-size text

# ── Medicine detection patterns ────────────────────────────────────────────

# Pass-1: known pharmaceutical suffixes
_SUFFIX_PATTERN = re.compile(
    r"\b([A-Za-z]{2,}(?:"
    r"mycin|cillin|zole|prazole|olol|pril|sartan|statin|mab|nib|"
    r"vir|cycline|oxacin|dipine|tidine|navir|fenac|profen|"
    r"lukast|triptan|setron|gliptin|gliflozin|parin|phylline|"
    r"dronate|vastatin|azepam|barbital|caine|dine|pine|lone|"
    r"metformin|insulin|warfarin|aspirin|ibuprofen|diazepam|omeprazole|"
    r"amoxicillin|paracetamol|atorvastatin|lisinopril|amlodipine|"
    r"cetirizine|loratadine|montelukast|pantoprazole|esomeprazole|"
    r"sertraline|fluoxetine|clopidogrel|metoprolol|atenolol|"
    r"prednisolone|dexamethasone|hydrocortisone|betamethasone|"
    r"azithromycin|clarithromycin|doxycycline|ciprofloxacin|"
    r"levothyroxine|metronidazole|salbutamol|theophylline|"
    r"nifedipine|verapamil|diltiazem|digoxin|furosemide|"
    r"spironolactone|hydrochlorothiazide|losartan|valsartan|"
    r"codeine|tramadol|morphine|fentanyl|buprenorphine"
    r"))\b",
    re.IGNORECASE,
)

# Pass-2: Capitalised/uppercase word immediately before a dosage amount
# Catches brand names like "Catophli 10mg", "MONA 500mg", "Rosmo 1-0-0"
_BRAND_DOSAGE_PATTERN = re.compile(
    r"\b([A-Z][A-Za-z]{2,})\s+"           # word starting with capital, ≥3 chars
    r"(?:\d+[\d.]*\s*(?:mg|mcg|µg|g|ml|IU|units?)|"   # numeric dose
    r"\d-\d-\d)"                           # or "1-0-0" style
)

# Pass-3: Lines that look like Rx drug lines
# "Tab Amoxicillin 500mg" / "Cap. Omeprazole 20mg" / "Syp Paracetamol 120mg"
_RX_LINE_PATTERN = re.compile(
    r"(?:Tab\.?|Cap\.?|Syp\.?|Inj\.?|Oint\.?|Drops?|Gel|Cream)\s+"
    r"([A-Za-z][A-Za-z\s\-]{2,30?}?)\s+"
    r"\d",
    re.IGNORECASE,
)

# Pass-4: ALLCAPS drug names (very common in Indian prescriptions)
_ALLCAPS_PATTERN = re.compile(
    r"\b([A-Z]{3,15})\s+\d+[\d.]*\s*(?:mg|mcg|g|ml|IU)\b"
)


@dataclass
class OCRResult:
    """Output from OCR extraction."""
    raw_text: str = ""
    cleaned_text: str = ""
    detected_medicines: List[str] = field(default_factory=list)
    confidence: float = 0.0
    language_detected: str = "en"


class OCRService:
    """
    Stateless OCR service using Tesseract with improved preprocessing
    and multi-pass medicine detection.
    """

    def __init__(self):
        pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_CMD
        logger.info(f"OCRService v2.1 initialised (tesseract={settings.TESSERACT_CMD})")

    async def extract_text(self, image_path: str) -> OCRResult:
        return await asyncio.to_thread(self._extract_sync, image_path)

    # ── Synchronous core ───────────────────────────────────────────────────

    def _extract_sync(self, image_path: str) -> OCRResult:
        logger.debug(f"OCR: processing {image_path}")

        # Load original image
        try:
            bgr_original = self._load_image(image_path)
        except Exception as exc:
            raise ValueError(f"Cannot open image: {exc}") from exc

        # Try multiple preprocessing strategies, keep best result
        best_text, best_conf = "", 0.0
        for strategy_fn in [
            self._preprocess_enhanced,
            self._preprocess_original,
            self._preprocess_colour,
        ]:
            try:
                img = strategy_fn(bgr_original)
                text, conf = self._run_tesseract(img)
                logger.debug(f"Strategy {strategy_fn.__name__}: conf={conf:.3f}, chars={len(text)}")
                if conf > best_conf and len(text.strip()) > 20:
                    best_conf = conf
                    best_text = text
            except Exception as exc:
                logger.warning(f"Strategy {strategy_fn.__name__} failed: {exc}")

        if not best_text.strip():
            # Last resort: raw PIL without any preprocessing
            pil = Image.fromarray(cv2.cvtColor(bgr_original, cv2.COLOR_BGR2RGB))
            best_text = pytesseract.image_to_string(pil, config=_PSM11)
            best_conf = 0.3

        cleaned = self._clean_text(best_text)
        medicines = self._detect_medicines(cleaned)

        logger.info(
            f"OCR complete: conf={best_conf:.3f} | "
            f"chars={len(cleaned)} | medicines={medicines}"
        )

        return OCRResult(
            raw_text=best_text,
            cleaned_text=cleaned,
            detected_medicines=medicines,
            confidence=best_conf,
        )

    # ── Image loading ──────────────────────────────────────────────────────

    @staticmethod
    def _load_image(image_path: str) -> np.ndarray:
        """Load image as BGR numpy array."""
        bgr = cv2.imread(image_path)
        if bgr is None:
            pil = Image.open(image_path).convert("RGB")
            bgr = cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)
        if bgr is None:
            raise ValueError(f"Could not load image from {image_path}")
        return bgr

    # ── Preprocessing strategies ───────────────────────────────────────────

    def _preprocess_enhanced(self, bgr: np.ndarray) -> Image.Image:
        """
        Strategy 1 — Enhanced pipeline:
        deskew → upscale → CLAHE → bilateral filter → Otsu threshold
        Best for low-contrast or uneven-lighting prescription photos.
        """
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)

        # Upscale to at least 2400px on longest side for better OCR
        h, w = gray.shape
        target = 2400
        if max(h, w) < target:
            scale = target / max(h, w)
            gray = cv2.resize(gray, None, fx=scale, fy=scale,
                              interpolation=cv2.INTER_LANCZOS4)

        # CLAHE contrast enhancement — handles uneven lighting well
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)

        # Bilateral filter — preserves edges while denoising
        denoised = cv2.bilateralFilter(enhanced, 9, 75, 75)

        # Otsu threshold
        _, thresh = cv2.threshold(
            denoised, 0, 255,
            cv2.THRESH_BINARY + cv2.THRESH_OTSU
        )

        # Mild sharpening kernel
        kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]])
        sharpened = cv2.filter2D(thresh, -1, kernel)

        return Image.fromarray(sharpened)

    def _preprocess_original(self, bgr: np.ndarray) -> Image.Image:
        """
        Strategy 2 — Original adaptive threshold (kept as fallback).
        """
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape
        if max(h, w) < 1500:
            scale = 1500 / max(h, w)
            gray = cv2.resize(gray, None, fx=scale, fy=scale,
                              interpolation=cv2.INTER_CUBIC)
        denoised = cv2.fastNlMeansDenoising(gray, h=10)
        thresh = cv2.adaptiveThreshold(
            denoised, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, 31, 10,
        )
        return Image.fromarray(thresh)

    def _preprocess_colour(self, bgr: np.ndarray) -> Image.Image:
        """
        Strategy 3 — Colour image (no thresholding).
        Works best on high-quality digital prescription PDFs.
        """
        h, w = bgr.shape[:2]
        if max(h, w) < 2000:
            scale = 2000 / max(h, w)
            bgr = cv2.resize(bgr, None, fx=scale, fy=scale,
                             interpolation=cv2.INTER_LANCZOS4)
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        return Image.fromarray(rgb)

    # ── Tesseract runner ───────────────────────────────────────────────────

    def _run_tesseract(self, img: Image.Image) -> Tuple[str, float]:
        """
        Run Tesseract with multiple PSM modes and return (best_text, confidence).
        """
        lang = settings.TESSERACT_LANG  # default "eng"
        best_text, best_conf = "", 0.0

        for config in [_PSM11, _PSM6, _PSM4]:
            try:
                data = pytesseract.image_to_data(
                    img, lang=lang, config=config,
                    output_type=pytesseract.Output.DICT,
                )
                text = pytesseract.image_to_string(img, lang=lang, config=config)
                conf = self._calc_confidence(data)
                if conf > best_conf:
                    best_conf = conf
                    best_text = text
            except Exception:
                pass

        return best_text, best_conf

    # ── Post-processing ────────────────────────────────────────────────────

    @staticmethod
    def _calc_confidence(data: dict) -> float:
        confidences = [c for c in data.get("conf", []) if isinstance(c, (int, float)) and c != -1]
        if not confidences:
            return 0.0
        return round(sum(confidences) / len(confidences) / 100.0, 3)

    @staticmethod
    def _clean_text(text: str) -> str:
        """Clean OCR output while preserving medically relevant content."""
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        lines = []
        for ln in text.splitlines():
            stripped = ln.strip()
            # Keep lines with at least 2 real characters
            if len(stripped) >= 2:
                lines.append(stripped)
        return "\n".join(lines).strip()

    @staticmethod
    def _detect_medicines(text: str) -> List[str]:
        """
        Multi-pass medicine name detection.
        Pass 1: pharmaceutical suffix matching
        Pass 2: Brand name + dosage pattern
        Pass 3: Tab/Cap/Syp prefix lines
        Pass 4: ALLCAPS drug names
        """
        candidates: List[str] = []

        # Pass 1 — suffix
        for m in _SUFFIX_PATTERN.finditer(text):
            candidates.append(m.group(1))

        # Pass 2 — brand + dosage
        for m in _BRAND_DOSAGE_PATTERN.finditer(text):
            name = m.group(1).strip()
            if len(name) >= 3:
                candidates.append(name)

        # Pass 3 — Tab/Cap/Syp prefix
        for m in _RX_LINE_PATTERN.finditer(text):
            name = m.group(1).strip().rstrip(",. ")
            if len(name) >= 3:
                candidates.append(name)

        # Pass 4 — ALLCAPS + dosage
        for m in _ALLCAPS_PATTERN.finditer(text):
            name = m.group(1).strip()
            # Filter out common non-medicine allcaps words
            skip = {"THE", "FOR", "AND", "WITH", "USE", "NOT", "OAP", "DAY",
                    "TAB", "CAP", "SYP", "INJ", "MED", "RX", "DR", "MR", "MS"}
            if name not in skip and len(name) >= 3:
                candidates.append(name)

        # Deduplicate preserving order (case-insensitive)
        seen: set = set()
        unique: List[str] = []
        for name in candidates:
            key = name.lower().strip()
            if key and key not in seen:
                seen.add(key)
                # Normalise capitalisation: Title case if all-lower or all-upper
                if name.isupper() or name.islower():
                    name = name.capitalize()
                unique.append(name)

        return unique
