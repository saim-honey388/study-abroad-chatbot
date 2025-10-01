from typing import Any, Dict, Optional, Tuple, List
import logging
from app.config import GEMINI_API_KEY, GEMINI_MODEL, LOG_LLM_DEBUG, OPENAI_API_KEY, OPENAI_MODEL, ANTHROPIC_API_KEY, ANTHROPIC_MODEL, LLM_PROVIDER
import time


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
        return bool(OPENAI_API_KEY or GEMINI_API_KEY or ANTHROPIC_API_KEY)

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
            llm = None
            provider = ""
            # Log what we're about to try
            try:
                DialogChain._logger.info("LLM provider selection (dialog): openai_present=%s gemini_present=%s", bool(OPENAI_API_KEY), bool(GEMINI_API_KEY))
            except Exception:
                pass
            try:
                # Honor explicit provider if set; otherwise prefer OpenAI, then Google, then Anthropic
                pref = (LLM_PROVIDER or "").strip()
                DialogChain._logger.info(
                    "LLM provider selection (dialog): provider_pref=%s openai=%s gemini=%s anthropic=%s",
                    pref or "",
                    bool(OPENAI_API_KEY),
                    bool(GEMINI_API_KEY),
                    bool(ANTHROPIC_API_KEY),
                )
                if pref == "openai" and OPENAI_API_KEY:
                    from langchain_openai import ChatOpenAI
                    llm = ChatOpenAI(model=OPENAI_MODEL or "gpt-4o-mini", api_key=OPENAI_API_KEY, temperature=0.3, max_retries=0, timeout=30, model_kwargs={"response_format": {"type": "json_object"}})
                    provider = "openai"
                elif pref == "google" and GEMINI_API_KEY:
                    from langchain_google_genai import ChatGoogleGenerativeAI
                    llm = ChatGoogleGenerativeAI(model=GEMINI_MODEL or "gemini-1.5-pro", api_key=GEMINI_API_KEY, temperature=0.3)
                    provider = "gemini"
                elif pref == "anthropic" and ANTHROPIC_API_KEY:
                    from langchain_anthropic import ChatAnthropic
                    llm = ChatAnthropic(model=ANTHROPIC_MODEL, api_key=ANTHROPIC_API_KEY, temperature=0.3)
                    provider = "anthropic"
                elif OPENAI_API_KEY:
                    from langchain_openai import ChatOpenAI
                    llm = ChatOpenAI(model=OPENAI_MODEL or "gpt-4o-mini", api_key=OPENAI_API_KEY, temperature=0.3, max_retries=0, timeout=30, model_kwargs={"response_format": {"type": "json_object"}})
                    provider = "openai"
                elif GEMINI_API_KEY:
                    from langchain_google_genai import ChatGoogleGenerativeAI
                    llm = ChatGoogleGenerativeAI(model=GEMINI_MODEL or "gemini-1.5-pro", api_key=GEMINI_API_KEY, temperature=0.3)
                    provider = "gemini"
                elif ANTHROPIC_API_KEY:
                    from langchain_anthropic import ChatAnthropic
                    llm = ChatAnthropic(model=ANTHROPIC_MODEL, api_key=ANTHROPIC_API_KEY, temperature=0.3)
                    provider = "anthropic"
            except Exception as e:
                llm = None
                try:
                    DialogChain._logger.warning("Dialog LLM init error: %s", str(e), exc_info=True)
                except Exception:
                    pass
            from pydantic import BaseModel

            class DialogOut(BaseModel):
                bot_message: str
                next_question_id: Optional[str] = None
                quick_replies: Optional[List[str]] = None

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
                    "- ALWAYS provide quick_replies as an array of 3-5 relevant options when asking questions. Examples: ['Yes', 'No', 'Not sure'] or ['USA', 'UK', 'Canada', 'Germany'] or ['Bachelor's', 'Master's', 'PhD']"
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
                    if provider == "openai":
                        DialogChain._logger.info("Using OpenAI model=%s", OPENAI_MODEL)
                    elif provider == "gemini":
                        key_tail = GEMINI_API_KEY[-10:] if GEMINI_API_KEY else ""
                        DialogChain._logger.info("Using Gemini model=%s key_tail=%s", GEMINI_MODEL or "gemini-1.5-pro", key_tail)
                    elif provider == "anthropic":
                        DialogChain._logger.info("Using Anthropic model=%s", ANTHROPIC_MODEL)
                except Exception:
                    pass
            # Console print of provider and model for visibility
            try:
                selected_model = (
                    (OPENAI_MODEL or "gpt-4o-mini") if provider == "openai" else (
                    (GEMINI_MODEL or "gemini-1.5-pro") if provider == "gemini" else (
                    ANTHROPIC_MODEL if provider == "anthropic" else "n/a"))
                )
                print(f"[LLM] dialog provider={provider or 'none'} model={selected_model}")
            except Exception:
                pass
            if llm is None:
                DialogChain._logger.warning(
                    "LLM provider not initialized (dialog) pref=%s openai=%s gemini=%s anthropic=%s",
                    (LLM_PROVIDER or ""), bool(OPENAI_API_KEY), bool(GEMINI_API_KEY), bool(ANTHROPIC_API_KEY)
                )
                return None
            chain = prompt | llm | parser
            for _ in range(3):
                payload = {
                    "profile_json": profile,
                    "last_message": last_user_message,
                    "expected_field": expected_field or "",
                }
                if LOG_LLM_DEBUG:
                    DialogChain._logger.info("Dialog LLM prompt payload=%s", payload)
                try:
                    t0 = time.perf_counter()
                    out = chain.invoke(payload)
                    duration_ms = (time.perf_counter() - t0) * 1000.0
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
                    if not next_question_id:
                        # Force a clear next question using rules if LLM was generic
                        fallback = DialogChain._find_next_missing_field(profile)
                        if fallback:
                            missing_key, question = fallback
                            next_question_id = f"ask_{missing_key}"
                            # If bot_message looks generic, replace it with the rule-based question
                            if len((bot_message or "").strip()) < 20 or "assist you" in bot_message.lower():
                                bot_message = question
                    if LOG_LLM_DEBUG:
                        DialogChain._logger.info("Dialog LLM success in %.1f ms: next=%s quick=%s", duration_ms, next_question_id, quick_replies[:3])
                    return bot_message, next_question_id, quick_replies
                except Exception as e:
                    if LOG_LLM_DEBUG:
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


