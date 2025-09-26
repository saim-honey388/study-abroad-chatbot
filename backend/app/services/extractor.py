from typing import Any, Dict, Tuple, Optional, List
import logging
from pydantic import BaseModel, Field, EmailStr
from app.config import GEMINI_API_KEY, GEMINI_MODEL
from app.utils.validators import normalize_phone
from app.config import LOG_LLM_DEBUG, GEMINI_MODEL, GEMINI_API_KEY
import json


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
    financial: Optional[FinancialInfo] = None
    budget_min: Optional[int] = None
    budget_max: Optional[int] = None
    career_goals: Optional[str] = None

    # Meta: which fields are confidently completed by this turn
    completed_fields: Optional[List[str]] = None


def _build_llm_chain():
    try:
        if not GEMINI_API_KEY:
            return None, None, None
        from langchain.prompts import ChatPromptTemplate
        from langchain_core.output_parsers import JsonOutputParser
        from langchain_google_genai import ChatGoogleGenerativeAI

        model = ChatGoogleGenerativeAI(model=GEMINI_MODEL, api_key=GEMINI_API_KEY, temperature=0)
        parser = JsonOutputParser(pydantic_object=IntakeFields)
        prompt = ChatPromptTemplate.from_messages([
            (
                "system",
                "You are a precise educational intake assistant. "
                "Extract ONLY the requested fields into ONE strict JSON object that matches the schema exactly, already normalized for database storage.\n\n"
                "Rules:\n"
                "- Always return ALL schema fields, even if null.\n"
                "- If information is missing or not provided, set that field to null (not empty string/array).\n"
                "- Reuse existing values from the provided profile when present, unless the new message clearly updates/contradicts them.\n"
                "- Never invent or guess values.\n"
                "- If multiple values appear for the same field, keep the most recent/clearly stated one.\n"
                "- Normalize synonyms and formats: BS/BSc → \"Bachelor's\"; canonicalize country names (e.g., UK→United Kingdom).\n"
                "- Do NOT infer field_of_study from degree/program mentioned (e.g., 'BS in AI'). Only set field_of_study if the student explicitly states their interest.\n"
                "- If the message says 'this year' or relative time, resolve to the correct numeric year using the current year (from system_time). Example: if system_time is 2025-09..., 'this year' = 2025, 'last year' = 2024.\n"
                "- For budget text like '10k - 20k', output numeric budget_min=10000 and budget_max=20000 (currency-agnostic).\n"
                "- For English tests, include an item with test_name and overall_score if stated.\n"
                "- Do NOT include extra keys or any text outside JSON.\n"
                "- Output strictly valid JSON only (no markdown).\n\n"
                "Schema fields (exact keys and order):\n"
                "full_name (string|null),\n"
                "age (int|null),\n"
                "email (string|null),\n"
                "phone (string|null),\n"
                "academic_level (string|null),\n"
                "recent_grades (string|null),\n"
                "institution (string|null),\n"
                "year_completed (int|null),\n"
                "major (string|null),\n"
                "field_of_study (string|null),\n"
                "preferred_countries (list[string]|null),\n"
                "target_level (string|null),  # Do not copy current academic_level here; only set if the student explicitly states their intended study level.\n"
                "english_tests (list[object]|null; object: test_name (string|null), overall_score (float|null), test_date (string|null ISO)),\n"
                "financial (object|null; funding_type (string|null), budget_range (string|null)),\n"
                "budget_min (int|null),\n"
                "budget_max (int|null),\n"
                "career_goals (string|null),\n"
                "completed_fields (list[string]|null)."
            ),
            (
                "user",
                "Current profile JSON (may already contain some fields):\n{profile_json}\n\n"
                "Student message:\n{text}\n\n"
                "If 'expected_field' is provided, focus on extracting that field primarily: {expected_field}.\n"
                "system_time: provide the current year in any relative-year resolution.\n"
                "Return ONLY one JSON object with exactly the schema keys (no extra keys), in the exact order listed."
            ),
        ])
        if LOG_LLM_DEBUG:
            try:
                from logging import getLogger
                key_tail = GEMINI_API_KEY[-10:] if GEMINI_API_KEY else ""
                getLogger(__name__).info("**API key being used:** %s (model=%s)", key_tail, GEMINI_MODEL)
            except Exception:
                pass
        return prompt, model, parser
    except Exception:
        return None, None, None


class ExtractorChain:
    _prompt = None
    _model = None
    _parser = None
    _logger = logging.getLogger(__name__)

    @classmethod
    def _ensure_chain(cls) -> None:
        if cls._prompt is None:
            cls._prompt, cls._model, cls._parser = _build_llm_chain()

    @staticmethod
    def _rule_based_extract(text: str, expected_field: Optional[str]) -> Dict[str, Any]:
        import re
        lowered = text.lower()
        extracted: Dict[str, Any] = {}

        # Helper regexes
        age_match = re.search(r"\b(1[3-9]|[2-5][0-9])\b\s*(years? old|yo|yrs)?", lowered)
        email_match = re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text)
        phone_digits = normalize_phone(text)

        # Academic levels simple keywords
        academic_map = {
            "matric": "Matric",
            "intermediate": "Intermediate",
            "o levels": "O Levels",
            "o-levels": "O Levels",
            "a levels": "A Levels",
            "a-levels": "A Levels",
            "bachelor": "Bachelor's",
            "bachelors": "Bachelor's",
            "bachelor's": "Bachelor's",
            "bs": "Bachelor's",
            "b.s": "Bachelor's",
            "bsc": "Bachelor's",
            "b.sc": "Bachelor's",
            "bcs": "Bachelor's",
            "masters": "Master's",
            "master": "Master's",
            "ms": "Master's",
        }
        academic_level = None
        for key, val in academic_map.items():
            if key in lowered:
                academic_level = val
                break

        # Countries naive list
        countries = [
            "usa", "united states", "uk", "united kingdom", "canada", "australia", "germany", "france", "italy", "spain",
        ]
        found_countries = list({c.title() for c in countries if c in lowered}) or None

        # Field-specific extraction if expected_field is provided
        def set_if(v_name: str, v):
            if v is not None:
                extracted[v_name] = v

        if expected_field == "age":
            set_if("age", int(age_match.group(1)) if age_match else None)
        elif expected_field == "email":
            set_if("email", email_match.group(0) if email_match else None)
        elif expected_field == "phone":
            set_if("phone", phone_digits)
        elif expected_field == "academic_level":
            set_if("academic_level", academic_level)
        elif expected_field == "preferred_countries":
            set_if("preferred_countries", found_countries)
        elif expected_field == "english_tests":
            if "ielts" in lowered:
                extracted["english_tests"] = [{"test_name": "IELTS"}]
        elif expected_field == "full_name":
            # naive: look for patterns like "my name is X" or "i am X"
            m = re.search(r"my name is ([A-Za-z\s'.-]{3,})", text, flags=re.I)
            if not m:
                m = re.search(r"i am ([A-Za-z\s'.-]{3,})", text, flags=re.I)
            set_if("full_name", m.group(1).strip() if m else None)
        elif expected_field == "recent_grades":
            m = re.search(r"(\b[1-9]\.\d{1,2}\b|\b\d{2,3}%\b|\bGPA\s*[:=]?\s*[0-4](?:\.\d{1,2})?\b)", text, flags=re.I)
            set_if("recent_grades", m.group(0) if m else None)
        elif expected_field == "field_of_study":
            # naive keyword buckets including common abbreviations
            fos_map = [
                ("artificial intelligence", "Artificial Intelligence"),
                (" ai ", "Artificial Intelligence"),
                ("computer science", "Computer Science"),
                (" cs ", "Computer Science"),
                ("data science", "Data Science"),
                ("data", "Data"),
                ("software engineering", "Software Engineering"),
                ("engineering", "Engineering"),
                ("business", "Business"),
                ("finance", "Finance"),
                ("medicine", "Medicine"),
                ("law", "Law"),
                ("arts", "Arts"),
                ("design", "Design"),
                ("psychology", "Psychology"),
            ]
            padded = f" {lowered} "
            for needle, label in fos_map:
                if needle in padded:
                    set_if("field_of_study", label)
                    break
        elif expected_field == "financial":
            if "scholar" in lowered:
                set_if("financial", {"funding_type": "scholarship"})
            elif any(k in lowered for k in ["self", "own funds", "my parents"]):
                set_if("financial", {"funding_type": "self-funded"})

        # If no expected_field, try to populate multiple basics opportunistically
        if not extracted:
            # Try to infer academic level from degree phrases like "did my BS in ..."
            deg_match = re.search(r"\b(b\.?s|bsc|bcs|bachelor'?s|masters?|ms|m\.s)\b", lowered)
            if deg_match and not academic_level:
                token = deg_match.group(1)
                if token in ("bs", "b.s", "bsc", "bcs", "bachelor's", "bachelors"):
                    set_if("academic_level", "Bachelor's")
                elif token in ("ms", "m.s", "masters", "master"):
                    set_if("academic_level", "Master's")
            if age_match:
                set_if("age", int(age_match.group(1)))
            if email_match:
                set_if("email", email_match.group(0))
            if phone_digits:
                set_if("phone", phone_digits)
            if academic_level:
                set_if("academic_level", academic_level)
            if found_countries:
                set_if("preferred_countries", found_countries)
            if "ielts" in lowered and "english_tests" not in extracted:
                extracted["english_tests"] = [{"test_name": "IELTS"}]

        return extracted

    @classmethod
    def extract(cls, text: str, profile: Dict[str, Any], expected_field: Optional[str] = None) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        cls._ensure_chain()

        # Try LLM chain if available
        if cls._prompt and cls._model and cls._parser:
            for attempt in range(3):
                try:
                    chain = cls._prompt | cls._model | cls._parser
                    from datetime import datetime
                    payload = {
                        "text": text,
                        "profile_json": profile,
                        "expected_field": expected_field or "",
                        "system_time": datetime.utcnow().isoformat(),
                    }
                    if LOG_LLM_DEBUG:
                        cls._logger.info("Extractor LLM prompt payload=%s", payload)
                    result = chain.invoke(payload)
                    # Accept both dict and pydantic model
                    if isinstance(result, dict):
                        data = {k: v for k, v in result.items() if v is not None}
                    else:
                        data = result.dict(exclude_none=True)

                    if LOG_LLM_DEBUG:
                        cls._logger.debug(f"Extractor LLM raw output (Attempt {attempt+1}): {json.dumps(data, indent=2)}")
                    # Backend minimal post-processing: normalize phone only
                    if "phone" in data and data["phone"]:
                        normalized = normalize_phone(data["phone"]) or data["phone"]
                        data["phone"] = normalized
                    cls._logger.info("Extractor LLM success: fields=%s", list(data.keys()))
                    if expected_field:
                        if expected_field in data and data[expected_field] is not None:
                            return data, profile
                        else:
                            cls._logger.info("Extractor LLM retry: expected_field=%s not found", expected_field)
                            continue
                    return data, profile
                except Exception:
                    cls._logger.warning("Extractor LLM error; retrying", exc_info=True)
                    continue

        # Fallback rule-based
        data = cls._rule_based_extract(text, expected_field)
        cls._logger.info("Extractor fallback used: fields=%s", list(data.keys()))
        return data, profile


