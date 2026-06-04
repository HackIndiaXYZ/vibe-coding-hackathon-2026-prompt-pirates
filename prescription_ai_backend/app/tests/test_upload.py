"""
Tests for Upload Route — Gemini Architecture
Tests the /api/v1/upload endpoint including:
- Valid image upload
- Invalid file type rejection
- Oversized file rejection
- OCR text extraction
- Medicine detection
"""

import io
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from PIL import Image

# Patch Gemini service init before importing the app
with patch("app.services.gemini_service.genai.configure"):
    from app.main import app


# ── Fixtures ───────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def client():
    """Synchronous test client."""
    with TestClient(app) as c:
        yield c


@pytest.fixture
def sample_jpeg_bytes() -> bytes:
    img = Image.new("RGB", (200, 100), color=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


@pytest.fixture
def sample_png_bytes() -> bytes:
    img = Image.new("RGB", (200, 100), color=(240, 240, 240))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def make_upload_files(content: bytes, filename: str = "test.jpg", content_type: str = "image/jpeg"):
    return {"file": (filename, io.BytesIO(content), content_type)}


# ── Tests ──────────────────────────────────────────────────────────────────

class TestUploadEndpoint:

    def test_health_endpoint(self, client):
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "version" in data

    def test_root_endpoint(self, client):
        response = client.get("/")
        assert response.status_code == 200
        assert "service" in response.json()

    @patch("app.routes.upload._ocr_service")
    def test_upload_valid_jpeg(self, mock_ocr, client, sample_jpeg_bytes):
        mock_result = MagicMock()
        mock_result.raw_text = "Rx\nAmoxicillin 500mg TID\nParacetamol 1g PRN"
        mock_result.detected_medicines = ["Amoxicillin", "Paracetamol"]
        mock_result.confidence = 0.88
        mock_ocr.extract_text = AsyncMock(return_value=mock_result)

        response = client.post(
            "/api/v1/upload",
            files=make_upload_files(sample_jpeg_bytes, "test.jpg"),
            data={"patient_age": "35", "language": "en"},
        )

        assert response.status_code == 201
        data = response.json()
        assert "prescription_id" in data
        assert len(data["prescription_id"]) == 36
        assert data["patient_age"] == 35
        assert data["language"] == "en"
        assert "detected_medicines" in data

    @patch("app.routes.upload._ocr_service")
    def test_upload_valid_png(self, mock_ocr, client, sample_png_bytes):
        mock_result = MagicMock()
        mock_result.raw_text = "Ibuprofen 400mg BD"
        mock_result.detected_medicines = ["Ibuprofen"]
        mock_result.confidence = 0.75
        mock_ocr.extract_text = AsyncMock(return_value=mock_result)

        response = client.post(
            "/api/v1/upload",
            files=make_upload_files(sample_png_bytes, "rx.png", "image/png"),
        )
        assert response.status_code == 201

    def test_upload_invalid_extension(self, client):
        response = client.post(
            "/api/v1/upload",
            files={"file": ("prescription.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf")},
        )
        assert response.status_code == 415

    def test_upload_oversized_file(self, client):
        oversized = b"\xff\xd8\xff" + b"0" * (11 * 1024 * 1024)
        response = client.post(
            "/api/v1/upload",
            files={"file": ("big.jpg", io.BytesIO(oversized), "image/jpeg")},
        )
        assert response.status_code == 413

    @patch("app.routes.upload._ocr_service")
    def test_upload_ocr_failure_returns_422(self, mock_ocr, client, sample_jpeg_bytes):
        mock_ocr.extract_text = AsyncMock(side_effect=RuntimeError("Tesseract not found"))
        response = client.post(
            "/api/v1/upload",
            files=make_upload_files(sample_jpeg_bytes),
        )
        assert response.status_code == 422

    @patch("app.routes.upload._ocr_service")
    def test_upload_default_language_fallback(self, mock_ocr, client, sample_jpeg_bytes):
        mock_result = MagicMock()
        mock_result.raw_text = "Metformin 500mg"
        mock_result.detected_medicines = ["Metformin"]
        mock_result.confidence = 0.80
        mock_ocr.extract_text = AsyncMock(return_value=mock_result)

        response = client.post(
            "/api/v1/upload",
            files=make_upload_files(sample_jpeg_bytes),
            data={"language": "klingon"},
        )
        assert response.status_code == 201
        assert response.json()["language"] == "en"

    @patch("app.routes.upload._ocr_service")
    def test_upload_response_structure(self, mock_ocr, client, sample_jpeg_bytes):
        mock_result = MagicMock()
        mock_result.raw_text = "Atorvastatin 40mg OD"
        mock_result.detected_medicines = ["Atorvastatin"]
        mock_result.confidence = 0.92
        mock_ocr.extract_text = AsyncMock(return_value=mock_result)

        response = client.post("/api/v1/upload", files=make_upload_files(sample_jpeg_bytes))
        data = response.json()
        for field in ["prescription_id", "filename", "file_path", "raw_text",
                      "detected_medicines", "language", "ocr_confidence", "message"]:
            assert field in data, f"Missing field: {field}"

    def test_delete_nonexistent_returns_404(self, client):
        response = client.delete("/api/v1/upload/00000000-0000-0000-0000-000000000000")
        assert response.status_code == 404
