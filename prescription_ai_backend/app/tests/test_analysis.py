"""
Tests for Analysis Route — Gemini Architecture
Tests the /api/v1/analysis endpoint including:
- Missing prescription handling
- Gemini service integration
- Response schema validation
- Aggregate flag computation (drowsiness, dosage, age)
- Multi-medicine analysis
"""

import json
import os
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

with patch("app.services.gemini_service.genai.configure"):
    from app.main import app

SAMPLE_PID = "3fa85f64-5717-4562-b3fc-2c963f66afa6"

GEMINI_SINGLE_MEDICINE = {
    "medicines": [
        {
            "medicine_name": "Amoxicillin",
            "dosage": "500mg",
            "frequency": "Three times daily",
            "duration": "7 days",
            "use_case": "Bacterial infections",
            "side_effects": ["Diarrhoea", "Nausea"],
            "serious_side_effects": ["Anaphylaxis"],
            "alternatives": ["Azithromycin"],
            "age_warnings": [],
            "causes_drowsiness": False,
            "lifestyle_recommendations": ["Complete the full course."],
            "dosage_safety_assessment": {
                "is_safe": True,
                "prescribed_dose": "500mg TID",
                "standard_dose": "250–500mg every 8 hours",
                "notes": [],
            },
            "severity_level": "low",
        }
    ]
}

GEMINI_DROWSY_MEDICINE = {
    "medicines": [
        {
            "medicine_name": "Diazepam",
            "dosage": "5mg",
            "frequency": "Once daily",
            "duration": "2 weeks",
            "use_case": "Anxiety and muscle relaxation",
            "side_effects": ["Drowsiness", "Dizziness"],
            "serious_side_effects": ["Respiratory depression"],
            "alternatives": ["Lorazepam"],
            "age_warnings": ["Use with caution in elderly — fall risk"],
            "causes_drowsiness": True,
            "lifestyle_recommendations": ["Do not drive or operate machinery."],
            "dosage_safety_assessment": {
                "is_safe": True,
                "prescribed_dose": "5mg OD",
                "standard_dose": "2–10mg 2–4 times daily",
                "notes": [],
            },
            "severity_level": "medium",
        }
    ]
}


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def write_sidecar(pid: str, raw_text: str, upload_dir: str = "./uploads"):
    """Write a test sidecar metadata file."""
    os.makedirs(upload_dir, exist_ok=True)
    path = os.path.join(upload_dir, f"{pid}.meta")
    with open(path, "w") as f:
        json.dump({
            "prescription_id": pid,
            "raw_text": raw_text,
            "detected_medicines": [],
            "patient_age": None,
            "language": "en",
            "ocr_confidence": 0.85,
            "image_path": f"{upload_dir}/{pid}.jpg",
        }, f)
    return path


class TestAnalysisEndpoint:

    def test_analysis_missing_prescription_returns_404(self, client):
        """No sidecar → 404."""
        response = client.get(f"/api/v1/analysis/nonexistent-id-0000-0000-000000000000")
        assert response.status_code == 404

    def test_analysis_post_no_sidecar_returns_404(self, client):
        response = client.post(
            "/api/v1/analysis",
            json={"prescription_id": SAMPLE_PID},
        )
        assert response.status_code == 404

    @patch("app.routes.analysis.get_gemini_service")
    def test_analysis_get_returns_200(self, mock_get_svc, client, tmp_path):
        """GET analysis with valid sidecar returns 200 with medicines."""
        # Write sidecar
        sidecar = write_sidecar(SAMPLE_PID, "Amoxicillin 500mg TID x7 days", str(tmp_path))

        mock_svc = MagicMock()
        mock_svc.analyse_prescription = AsyncMock(return_value=GEMINI_SINGLE_MEDICINE)
        mock_get_svc.return_value = mock_svc

        with patch("app.routes.analysis.settings") as mock_settings:
            mock_settings.upload_dir_path = str(tmp_path)
            mock_settings.SUPPORTED_LANGUAGES = ["en", "hi", "ta"]
            mock_settings.DEFAULT_LANGUAGE = "en"

            response = client.get(f"/api/v1/analysis/{SAMPLE_PID}")

        os.remove(sidecar)
        assert response.status_code == 200
        data = response.json()
        assert data["prescription_id"] == SAMPLE_PID
        assert len(data["medicines"]) == 1
        assert data["medicines"][0]["medicine_name"] == "Amoxicillin"
        assert data["total_medicines_analysed"] == 1

    @patch("app.routes.analysis.get_gemini_service")
    def test_drowsiness_flag_propagates(self, mock_get_svc, client, tmp_path):
        """Drowsy medicine must set overall_drowsiness_warning=True."""
        pid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        sidecar = write_sidecar(pid, "Diazepam 5mg OD", str(tmp_path))

        mock_svc = MagicMock()
        mock_svc.analyse_prescription = AsyncMock(return_value=GEMINI_DROWSY_MEDICINE)
        mock_get_svc.return_value = mock_svc

        with patch("app.routes.analysis.settings") as mock_settings:
            mock_settings.upload_dir_path = str(tmp_path)
            mock_settings.SUPPORTED_LANGUAGES = ["en"]
            mock_settings.DEFAULT_LANGUAGE = "en"

            response = client.get(f"/api/v1/analysis/{pid}")

        os.remove(sidecar)
        assert response.status_code == 200
        data = response.json()
        assert data["overall_drowsiness_warning"] is True
        assert data["medicines"][0]["causes_drowsiness"] is True

    @patch("app.routes.analysis.get_gemini_service")
    def test_age_warning_propagates(self, mock_get_svc, client, tmp_path):
        """Age warning in any medicine sets overall_age_warning=True."""
        pid = "11111111-2222-3333-4444-555555555555"
        sidecar = write_sidecar(pid, "Diazepam 5mg OD", str(tmp_path))

        mock_svc = MagicMock()
        mock_svc.analyse_prescription = AsyncMock(return_value=GEMINI_DROWSY_MEDICINE)
        mock_get_svc.return_value = mock_svc

        with patch("app.routes.analysis.settings") as mock_settings:
            mock_settings.upload_dir_path = str(tmp_path)
            mock_settings.SUPPORTED_LANGUAGES = ["en"]
            mock_settings.DEFAULT_LANGUAGE = "en"

            response = client.get(f"/api/v1/analysis/{pid}", params={"patient_age": 72})

        os.remove(sidecar)
        assert response.status_code == 200
        data = response.json()
        assert data["overall_age_warning"] is True

    @patch("app.routes.analysis.get_gemini_service")
    def test_full_response_schema(self, mock_get_svc, client, tmp_path):
        """All required top-level fields must be present in the response."""
        pid = "abcdef12-3456-7890-abcd-ef1234567890"
        sidecar = write_sidecar(pid, "Amoxicillin 500mg TID", str(tmp_path))

        mock_svc = MagicMock()
        mock_svc.analyse_prescription = AsyncMock(return_value=GEMINI_SINGLE_MEDICINE)
        mock_get_svc.return_value = mock_svc

        with patch("app.routes.analysis.settings") as mock_settings:
            mock_settings.upload_dir_path = str(tmp_path)
            mock_settings.SUPPORTED_LANGUAGES = ["en"]
            mock_settings.DEFAULT_LANGUAGE = "en"

            response = client.get(f"/api/v1/analysis/{pid}")

        os.remove(sidecar)
        assert response.status_code == 200
        data = response.json()
        for field in [
            "prescription_id", "patient_age", "language", "medicines",
            "overall_drowsiness_warning", "overall_dosage_concern",
            "overall_age_warning", "overall_severity",
            "total_medicines_analysed", "summary",
        ]:
            assert field in data, f"Missing top-level field: {field}"

        med = data["medicines"][0]
        for field in [
            "medicine_name", "dosage", "frequency", "duration", "use_case",
            "side_effects", "serious_side_effects", "alternatives",
            "age_warnings", "causes_drowsiness", "lifestyle_recommendations",
            "dosage_safety_assessment", "severity_level",
        ]:
            assert field in med, f"Missing medicine field: {field}"

    @patch("app.routes.analysis.get_gemini_service")
    def test_gemini_api_error_returns_502(self, mock_get_svc, client, tmp_path):
        """Gemini returning _error key → 502 Bad Gateway."""
        pid = "ffffffff-ffff-ffff-ffff-ffffffffffff"
        sidecar = write_sidecar(pid, "Amoxicillin 500mg", str(tmp_path))

        mock_svc = MagicMock()
        mock_svc.analyse_prescription = AsyncMock(
            return_value={"medicines": [], "_error": "API quota exceeded"}
        )
        mock_get_svc.return_value = mock_svc

        with patch("app.routes.analysis.settings") as mock_settings:
            mock_settings.upload_dir_path = str(tmp_path)
            mock_settings.SUPPORTED_LANGUAGES = ["en"]
            mock_settings.DEFAULT_LANGUAGE = "en"

            response = client.get(f"/api/v1/analysis/{pid}")

        os.remove(sidecar)
        assert response.status_code == 502


class TestParserUnit:
    """Unit tests for parser utility functions."""

    def test_parse_dosage(self):
        from app.utils.parser import parse_dosage
        assert parse_dosage("Amoxicillin 500mg TID") == "500mg"
        assert parse_dosage("Paracetamol 1g PRN") == "1g"
        assert parse_dosage("No dosage here") is None

    def test_parse_dosage_mg(self):
        from app.utils.parser import parse_dosage_mg
        assert parse_dosage_mg("500mg") == 500.0
        assert parse_dosage_mg("1g") == 1000.0
        assert abs(parse_dosage_mg("250mcg") - 0.25) < 0.001

    def test_parse_frequency(self):
        from app.utils.parser import parse_frequency
        assert parse_frequency("Amoxicillin 500mg TID") == "Three times daily"
        assert parse_frequency("Paracetamol BD") == "Twice daily"
        assert parse_frequency("Aspirin OD") == "Once daily"

    def test_parse_patient_age(self):
        from app.utils.parser import parse_patient_age
        assert parse_patient_age("Patient Age: 45 years") == 45
        assert parse_patient_age("Age: 8") == 8
        assert parse_patient_age("No age info here") is None

    def test_clean_medicine_name(self):
        from app.utils.parser import clean_medicine_name
        assert clean_medicine_name("amoxicillin") == "Amoxicillin"
        assert clean_medicine_name("...PARACETAMOL...") == "Paracetamol"
        assert clean_medicine_name("  ibuprofen  ") == "Ibuprofen"


class TestValidatorsUnit:
    """Unit tests for validator utility functions."""

    def test_validate_medicine_name(self):
        from app.utils.validators import validate_medicine_name
        assert validate_medicine_name("Amoxicillin") == "Amoxicillin"
        assert validate_medicine_name("  Paracetamol  ") == "Paracetamol"
        with pytest.raises(ValueError):
            validate_medicine_name("")
        with pytest.raises(ValueError):
            validate_medicine_name("A" * 101)
        with pytest.raises(ValueError):
            validate_medicine_name("<script>alert(1)</script>")

    def test_validate_patient_age(self):
        from app.utils.validators import validate_patient_age
        assert validate_patient_age(None) is None
        assert validate_patient_age(25) == 25
        with pytest.raises(ValueError):
            validate_patient_age(-1)
        with pytest.raises(ValueError):
            validate_patient_age(121)

    def test_validate_language_code(self):
        from app.utils.validators import validate_language_code
        assert validate_language_code("en") == "en"
        assert validate_language_code("klingon") == "en"
        assert validate_language_code("") == "en"
