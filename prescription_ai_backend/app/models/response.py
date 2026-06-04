"""
Response Pydantic Models
Structured output models for the Gemini-powered analysis pipeline.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class DosageSafetyAssessment(BaseModel):
    """Structured dosage safety assessment returned by Gemini."""
    is_safe: bool = Field(True, description="True if prescribed dosage is within safe limits")
    prescribed_dose: str = Field("", description="Dosage as detected on the prescription")
    standard_dose: str = Field("", description="Standard recommended dosage for patient profile")
    notes: List[str] = Field(default_factory=list, description="Additional dosage safety notes")


class MedicineAnalysis(BaseModel):
    """
    Complete Gemini analysis result for a single medicine.
    All fields map 1-to-1 with the JSON Gemini returns.
    """
    medicine_name: str = Field(..., description="Name of the medicine")

    # Core prescription fields
    dosage: str = Field("", description="Dosage as stated on the prescription (e.g. 500mg)")
    frequency: str = Field("", description="Frequency of administration (e.g. TID, once daily)")
    duration: str = Field("", description="Course duration (e.g. 7 days)")

    # Explanation
    use_case: str = Field("", description="Primary therapeutic use / indication")

    # Side effects
    side_effects: List[str] = Field(default_factory=list, description="Common side effects")
    serious_side_effects: List[str] = Field(
        default_factory=list, description="Serious / rare side effects requiring medical attention"
    )

    # Alternatives
    alternatives: List[str] = Field(
        default_factory=list, description="Suggested therapeutic alternatives"
    )

    # Warnings
    age_warnings: List[str] = Field(
        default_factory=list, description="Age-specific safety warnings"
    )
    causes_drowsiness: bool = Field(False, description="True if this medicine causes drowsiness")

    # Lifestyle
    lifestyle_recommendations: List[str] = Field(
        default_factory=list,
        description="Dietary, activity, or behavioural recommendations while taking this medicine",
    )

    # Dosage safety
    dosage_safety_assessment: DosageSafetyAssessment = Field(
        default_factory=DosageSafetyAssessment,
        description="Structured dosage safety assessment",
    )

    # Risk level (derived by Gemini)
    severity_level: str = Field(
        "low", description="Overall risk level: low | medium | high | critical"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "medicine_name": "Amoxicillin",
                "dosage": "500mg",
                "frequency": "Three times daily",
                "duration": "7 days",
                "use_case": "Bacterial infections: ear, chest, and urinary tract.",
                "side_effects": ["Diarrhoea", "Nausea", "Rash"],
                "serious_side_effects": ["Anaphylaxis", "Stevens-Johnson Syndrome"],
                "alternatives": ["Azithromycin", "Clarithromycin"],
                "age_warnings": [],
                "causes_drowsiness": False,
                "lifestyle_recommendations": [
                    "Complete the full course even if you feel better.",
                    "Take with or without food.",
                ],
                "dosage_safety_assessment": {
                    "is_safe": True,
                    "prescribed_dose": "500mg TID",
                    "standard_dose": "250–500mg every 8 hours",
                    "notes": [],
                },
                "severity_level": "low",
            }
        }
    }


class FullAnalysisResponse(BaseModel):
    """
    Top-level response for a full prescription analysis.
    Contains per-medicine analyses and aggregate safety flags.
    """
    prescription_id: str = Field(..., description="Prescription UUID from upload step")
    patient_age: Optional[int] = Field(None, description="Patient age in years")
    language: str = Field("en", description="Language of the response")

    # Per-medicine analyses
    medicines: List[MedicineAnalysis] = Field(
        default_factory=list, description="Individual Gemini analysis for each medicine"
    )

    # Aggregate flags
    overall_drowsiness_warning: bool = Field(
        False, description="True if any medicine causes drowsiness"
    )
    overall_dosage_concern: bool = Field(
        False, description="True if any dosage appears unsafe"
    )
    overall_age_warning: bool = Field(
        False, description="True if any age-specific warning is triggered"
    )
    overall_severity: str = Field(
        "low", description="Highest severity level across all medicines"
    )
    total_medicines_analysed: int = Field(0, description="Count of medicines analysed")
    summary: str = Field("", description="Human-readable summary of the analysis")


class ErrorResponse(BaseModel):
    """Standard error response."""
    error: str
    message: str
    path: Optional[str] = None
    details: Optional[dict] = None
