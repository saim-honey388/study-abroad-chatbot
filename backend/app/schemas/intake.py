from typing import Optional, List
from pydantic import BaseModel, Field, EmailStr


class EnglishTestRecord(BaseModel):
    test_name: Optional[str] = Field(None, description="IELTS/TOEFL/PTE/etc")
    overall_score: Optional[float] = None
    test_date: Optional[str] = Field(None, description="ISO date string if known")


class FinancialInfo(BaseModel):
    funding_type: Optional[str] = Field(None, description="self-funded|scholarship|mixed")
    budget_range: Optional[str] = None


class IntakeFields(BaseModel):
    # Profile basics
    full_name: Optional[str] = None
    age: Optional[int] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None

    # Academics (normalized)
    academic_level: Optional[str] = None  # e.g., "Bachelor's", "Master's"
    recent_grades: Optional[str] = None   # free-form like "CGPA: 3.18"
    institution: Optional[str] = None     # e.g., "UMT"
    year_completed: Optional[int] = None  # e.g., 2025
    major: Optional[str] = None           # e.g., "Artificial Intelligence"

    # Preferences (normalized)
    field_of_study: Optional[str] = None
    preferred_countries: Optional[List[str]] = None  # canonical country names
    target_level: Optional[str] = None
    english_tests: Optional[List[EnglishTestRecord]] = None
    financial: Optional[FinancialInfo] = None  # self-funded | scholarship | mixed
    budget_min: Optional[int] = None
    budget_max: Optional[int] = None
    career_goals: Optional[str] = None

    # Meta: which fields are confidently completed by this turn
    completed_fields: Optional[List[str]] = None


