from typing import Any, Dict, Optional, Tuple, List
import logging
from app.config import GEMINI_API_KEY, GEMINI_MODEL, LOG_LLM_DEBUG


class DialogChain:
    _logger = logging.getLogger(__name__)
    BASIC_ORDER: List[Tuple[str, str]] = [
        ("full_name", "Could you please confirm your full name?"),
        ("age", "How old are you?"),
        ("academic_level", "What is your current academic level (e.g., Matric, Intermediate, O/A Levels, Bachelor's, Master's)?"),
        ("recent_grades", "What are your recent grades or GPA/percentage?"),
        ("field_of_study", "Which field of study or subject area are you interested in?"),
        ("preferred_countries", "Do you have any preferred study destination countries?"),
        ("english_tests", "Have you taken or planned any English tests (IELTS/TOEFL/PTE)?"),
        ("financial", "How do you plan to fund your studies (self-funded, scholarship, budget range)?"),
        ("career_goals", "What are your long-term academic or career goals?"),
        ("email", "Could you share your email address?"),
        ("phone", "And your phone number, please?"),
    ]

    @classmethod
    def _find_next_missing_field(cls, profile: Dict[str, Any]) -> Optional[Tuple[str, str]]:
        completed = set(profile.get("completed_fields") or [])
        # If user already confirmed preferred field, don't re-ask
        if profile.get("field_of_study"):
            completed.add("field_of_study")
        for field_key, question in cls.BASIC_ORDER:
            if field_key in completed:
                continue
            value = profile.get(field_key)
            if value in (None, "") or (isinstance(value, list) and len(value) == 0) or (isinstance(value, dict) and len(value) == 0):
                return field_key, question
        return None

    @staticmethod
    def _llm_chain_available() -> bool:
        return bool(GEMINI_API_KEY)

    @classmethod
    def _llm_respond(
        cls, profile: Dict[str, Any], last_user_message: str, expected_field: Optional[str]
    ) -> Optional[Tuple[str, Optional[str], List[str]]]:
        try:
            if not cls._llm_chain_available():
                return None
            # Lazy import to avoid hard dependency when no key present
            from langchain.prompts import ChatPromptTemplate
            from langchain_core.output_parsers import JsonOutputParser
            from langchain_google_genai import ChatGoogleGenerativeAI
            from pydantic import BaseModel

            class DialogOut(BaseModel):
                bot_message: str
                next_question_id: Optional[str] = None
                quick_replies: Optional[List[str]] = None

            model = ChatGoogleGenerativeAI(model=GEMINI_MODEL or "gemini-1.5-pro", api_key=GEMINI_API_KEY, temperature=0.3)
            parser = JsonOutputParser(pydantic_object=DialogOut)
            prompt = ChatPromptTemplate.from_messages([
                (
                    "system",
                    "You are a warm, concise educational consultant helping a student with study abroad intake. "
                    "Based on the current profile and the student's latest message, reply naturally. "
                    "If key fields are missing, politely ask ONE next question. "
                    "Return strict JSON with fields: bot_message, next_question_id (or null), quick_replies (or null). "
                    "Use next_question_id like 'ask_age' or 'ask_field_of_study' matching these keys: full_name, age, academic_level, recent_grades, field_of_study, preferred_countries, english_tests, financial, career_goals, email, phone."
                    "\nRules: "
                    "- Do NOT infer field_of_study from the degree (e.g., BS in AI). Ask explicitly unless the user clearly states their interest. If degree and field look same, ask a confirmation question and present options (e.g., AI, Computer Science, Engineering, Business). "
                    "- If user indicates 'not yet' for English tests, treat english_tests as completed for now and move forward to preferences or next missing field. "
                    "- Avoid re-asking any field listed in profile.completed_fields. "
                ),
                (
                    "user",
                    "Current profile JSON:\n{profile_json}\n\nLast student message:\n{last_message}\n\nFocus field (may be empty): {expected_field}\nReturn ONLY the JSON."
                ),
            ])
            if LOG_LLM_DEBUG:
                try:
                    key_tail = GEMINI_API_KEY[-10:] if GEMINI_API_KEY else ""
                    DialogChain._logger.info("**API key being used:** %s (model=%s)", key_tail, GEMINI_MODEL or "gemini-1.5-pro")
                except Exception:
                    pass
            chain = prompt | model | parser
            for _ in range(3):
                payload = {
                    "profile_json": profile,
                    "last_message": last_user_message,
                    "expected_field": expected_field or "",
                }
                if LOG_LLM_DEBUG:
                    DialogChain._logger.info("Dialog LLM prompt payload=%s", payload)
                try:
                    out = chain.invoke(payload)
                    # Handle both dict (JsonOutputParser) and pydantic model objects
                    if isinstance(out, dict):
                        bot_message = out.get("bot_message")
                        next_question_id = out.get("next_question_id")
                        quick_replies = out.get("quick_replies") or []
                    else:
                        bot_message = getattr(out, "bot_message", None)
                        next_question_id = getattr(out, "next_question_id", None)
                        quick_replies = getattr(out, "quick_replies", []) or []

                    if not bot_message:
                        raise ValueError("Dialog parser returned no bot_message")
                    if LOG_LLM_DEBUG and out is not None:
                        try:
                            raw_out = out if isinstance(out, dict) else out.dict()
                            DialogChain._logger.info("Dialog LLM raw output=%s", raw_out)
                        except Exception:
                            DialogChain._logger.info("Dialog LLM raw output (repr)=%r", out)
                    if LOG_LLM_DEBUG:
                        DialogChain._logger.info("Dialog LLM success: next=%s quick=%s", next_question_id, quick_replies[:3])
                    return bot_message, next_question_id, quick_replies
                except Exception as e:
                    DialogChain._logger.warning("Dialog LLM error; falling back", exc_info=True)
            DialogChain._logger.info("Dialog LLM failed after retries; falling back")
            return None
        except Exception:
            DialogChain._logger.warning("Dialog LLM error; falling back", exc_info=True)
            return None

    @classmethod
    def next_question(cls, profile: Dict[str, Any], last_user_message: str = "", expected_field: Optional[str] = None) -> Tuple[str, Optional[str], List[str]]:
        # Try LLM first
        llm = cls._llm_respond(profile, last_user_message, expected_field)
        if llm:
            return llm

        # Fallback to rules
        next_item = cls._find_next_missing_field(profile)
        if next_item:
            field_key, question = next_item
            return question, f"ask_{field_key}", []
        return "Thanks! I have your basic details. We can proceed to the next steps soon.", None, []


