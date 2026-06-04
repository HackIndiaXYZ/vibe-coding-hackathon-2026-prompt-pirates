"""Image validation helpers — check magic bytes to prevent spoofed uploads."""

# Magic byte signatures for supported image types
_MAGIC: dict = {
    ".jpg":  [(0, b"\xff\xd8\xff")],
    ".jpeg": [(0, b"\xff\xd8\xff")],
    ".png":  [(0, b"\x89PNG")],
    ".bmp":  [(0, b"BM")],
    ".webp": [(0, b"RIFF"), (8, b"WEBP")],
    ".tiff": [(0, b"II*\x00"), (0, b"MM\x00*")],
}


def validate_image_file(content: bytes, ext: str) -> None:
    """
    Validate that `content` matches the expected magic bytes for `ext`.
    Raises ValueError on mismatch.
    """
    checks = _MAGIC.get(ext.lower(), [])
    for offset, signature in checks:
        if not content[offset: offset + len(signature)] == signature:
            raise ValueError(
                f"File content does not match expected format for '{ext}'. "
                "The file may be corrupt or the extension may be wrong."
            )


# ── Input validators ───────────────────────────────────────────────────────

import re as _re
from typing import Optional as _Optional
from app.config import settings as _settings

_UNSAFE_CHARS = _re.compile(r"[<>{}\[\];\"'\\]")


def validate_medicine_name(name: str) -> str:
    """
    Validate and clean a medicine name.
    Raises ValueError for empty, too-long, or injection-like strings.
    """
    name = name.strip()
    if not name:
        raise ValueError("Medicine name must not be empty.")
    if len(name) > 100:
        raise ValueError("Medicine name exceeds 100 characters.")
    if _UNSAFE_CHARS.search(name):
        raise ValueError(f"Medicine name contains invalid characters: {name!r}")
    return name


def validate_patient_age(age: _Optional[int]) -> _Optional[int]:
    """Validate patient age is in [0, 120] or None."""
    if age is None:
        return None
    if not isinstance(age, int) or age < 0 or age > 120:
        raise ValueError(f"Patient age must be between 0 and 120 (got {age}).")
    return age


def validate_language_code(code: str) -> str:
    """Return code if supported, otherwise fall back to DEFAULT_LANGUAGE."""
    if code and code in _settings.SUPPORTED_LANGUAGES:
        return code
    return _settings.DEFAULT_LANGUAGE
