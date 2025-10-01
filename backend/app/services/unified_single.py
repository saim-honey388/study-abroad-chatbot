from typing import Any, Dict, List, Optional, Tuple
import logging
import time
import traceback
import sys

from app.config import (
    GEMINI_API_KEY,
    GEMINI_MODEL,
    OPENAI_API_KEY,
    OPENAI_MODEL,
    ANTHROPIC_API_KEY,
    ANTHROPIC_MODEL,
    LLM_PROVIDER,
    LOG_LLM_DEBUG,
)
from app.utils.profile_utils import normalize_profile_shape, split_incomplete_fields
from app.schemas.intake import IntakeFields

_logger = logging.getLogger(__name__)

BASIC_ORDER: List[Tuple[str, str]] = [
    ("full_name", "Could you please confirm your full name?"),
    ("age", "How old are you?"),
    ("academic_level", "What is your current academic level (e.g., Matric, Intermediate, O/A Levels, Bachelor's, Master's)?"),
    ("recent_grades", "What are your recent grades or GPA/percentage?"),
    ("field_of_study", "Which field of study or subject area are you interested in?"),
    ("preferred_countries", "Do you have any preferred study destination countries?"),
    ("english_tests", "Have you taken or planned any English tests (IELTS/TOEFL/PTE)?"),
    ("financial", "How do you plan to fund your tuition and living expenses (self-funded, scholarship, mixed)?"),
    ("target_level", "What study level are you aiming for next (Bachelor's, Master's, PhD)?"),
    ("career_goals", "What are your long-term academic or career goals?"),
    ("email", "Could you share your email address?"),
    ("phone", "And your phone number, please?"),
]


def _find_next_missing_field(profile: Dict[str, Any]) -> Optional[Tuple[str, str]]:
    completed = set((profile or {}).get("completed_fields") or [])
    def _is_empty(v: Any) -> bool:
        if v is None: return True
        if isinstance(v, str) and v.strip() == "": return True
        if isinstance(v, (list, dict)) and len(v) == 0: return True
        return False
    for key, question in BASIC_ORDER:
        if key in completed:
            continue
        if _is_empty((profile or {}).get(key)):
            return key, question
    return None


def _question_for(next_question_id: Optional[str]) -> Optional[str]:
    if not next_question_id:
        return None
    field_key = str(next_question_id).replace("ask_", "")
    mapping = {k: q for k, q in BASIC_ORDER}
    return mapping.get(field_key)


def _select_llm():
    try:
        pref = (LLM_PROVIDER or "").strip()
        if pref == "openai" and OPENAI_API_KEY:
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                model=OPENAI_MODEL or "gpt-3.5-turbo-0125",
                api_key=OPENAI_API_KEY,
                temperature=0,
                max_retries=0,
                timeout=30,
                model_kwargs={"response_format": {"type": "json_object"}},
            ), "openai", (OPENAI_MODEL or "gpt-3.5-turbo-0125")
        if pref == "google" and GEMINI_API_KEY:
            from langchain_google_genai import ChatGoogleGenerativeAI
            return ChatGoogleGenerativeAI(model=GEMINI_MODEL or "gemini-1.5-pro", api_key=GEMINI_API_KEY, temperature=0), "gemini", (GEMINI_MODEL or "gemini-1.5-pro")
        if pref == "anthropic" and ANTHROPIC_API_KEY:
            from langchain_anthropic import ChatAnthropic
            return ChatAnthropic(model=ANTHROPIC_MODEL, api_key=ANTHROPIC_API_KEY, temperature=0), "anthropic", ANTHROPIC_MODEL

        if OPENAI_API_KEY:
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                model=OPENAI_MODEL or "gpt-3.5-turbo-0125",
                api_key=OPENAI_API_KEY,
                temperature=0,
                max_retries=0,
                timeout=30,
                model_kwargs={"response_format": {"type": "json_object"}},
            ), "openai", (OPENAI_MODEL or "gpt-3.5-turbo-0125")
        if GEMINI_API_KEY:
            from langchain_google_genai import ChatGoogleGenerativeAI
            return ChatGoogleGenerativeAI(model=GEMINI_MODEL or "gemini-1.5-pro", api_key=GEMINI_API_KEY, temperature=0), "gemini", (GEMINI_MODEL or "gemini-1.5-pro")
        if ANTHROPIC_API_KEY:
            from langchain_anthropic import ChatAnthropic
            return ChatAnthropic(model=ANTHROPIC_MODEL, api_key=ANTHROPIC_API_KEY, temperature=0), "anthropic", ANTHROPIC_MODEL
    except Exception as e:
        try:
            _logger.warning("Unified LLM init error: %s", str(e), exc_info=True)
        except Exception:
            pass
    return None, None, "n/a"


# Note: All inference should be handled by the LLM per system prompt; no heuristic enrichment here.


def respond(profile: Dict[str, Any], text: str) -> Tuple[str, Optional[str], List[str], IntakeFields]:
    try:
        from langchain.prompts import ChatPromptTemplate
        from langchain_core.output_parsers import JsonOutputParser
        from pydantic import BaseModel

        normalized = normalize_profile_shape(profile)
        incomplete_fields, _ = split_incomplete_fields(normalized)

        # Fast-path: for short greetings, skip LLM and ask next missing directly
        t_lower = (text or "").strip().lower()
        if t_lower in {"hi", "hello", "hey", "salam", "hi!", "hello!", "hey!"}:
            nxt = _find_next_missing_field(normalized)
            bot_q = "Hi! Let's get started. Could you share your details?"
            next_id = None
            if nxt:
                k, bot_q = nxt
                next_id = f"ask_{k}"
            return bot_q, next_id, [], IntakeFields(**{k: None for k in IntakeFields.model_fields.keys()})

        class DialogOut(BaseModel):
            bot_message: str
            next_question_id: Optional[str] = None
            quick_replies: Optional[List[str]] = None

        class UnifiedOut(BaseModel):
            dialog: DialogOut
            intake: IntakeFields

        parser = JsonOutputParser(pydantic_object=UnifiedOut)

        allowed_next_ids = [
            "ask_full_name","ask_age","ask_academic_level","ask_recent_grades","ask_field_of_study",
            "ask_preferred_countries","ask_english_tests","ask_financial","ask_target_level","ask_career_goals","ask_email","ask_phone",
        ]

        # prompt = ChatPromptTemplate.from_messages([
        #     ("system",
        #      "You are a warm, concise educational intake assistant."
        #      " Use the student's message and the provided profile to:"
        #      " (1) reply naturally with ONE clear next question IF needed, and"
        #      " (2) return an updated intake JSON strictly matching the schema.\n\n"
        #      "Rules (strict and exhaustive):\n"
        #      "- Consider completed_fields authoritative; NEVER re-ask those.\n"
        #      "- When the student explicitly provides a field in their message (e.g., 'BS in AI from UMT this year'), you MUST set those fields in intake: academic_level=\"Bachelor's\"; major=\"AI\"; institution=\"UMT\"; year_completed=current year; and, if clearly implied, target_level=\"Master's\".\n"
        #      "- Whenever you set any non-null field in intake, you MUST also include that field's key in completed_fields. Always PRESERVE any existing completed_fields from the provided profile (merge, do not overwrite).\n"
        #      "- Merge policy: For all fields, if the profile already has a non-empty value and the student's message does NOT contradict it, KEEP the existing value; otherwise update clearly and add the field to completed_fields. Never delete previously completed fields.\n"
        #      "- Map degree synonyms: BS/BSc/Bachelor's => academic_level=\"Bachelor's\"; MS/MSc/Master's => academic_level=\"Master's\".\n"
        #      "- Resolve relative years: 'this year' => current year; 'last year' => current year - 1.\n"
        #      "- Ask ONLY ONE field per turn, and it MUST NOT be completed; do NOT repeat questions. Choose the next missing field logically (age → level → grades → field_of_study → preferred_countries → english_tests → financial → target_level → career_goals → email → phone).\n"
        #      "- next_question_id must be one of: " + ", ".join(allowed_next_ids) + " or null.\n"
        #      "- bot_message MUST be present (avoid using 'response'), 1-2 polite sentences, friendly and specific. If you ask a question (non-null next_question_id), you MUST include 3-5 relevant quick_replies for THAT field ONLY:\n"
        #      "  * ask_academic_level: options are academic levels only\n"
        #      "  * ask_recent_grades: options are grade/GPA ranges or 'Don't remember'\n"
        #      "  * ask_field_of_study: options are fields of study only\n"
        #      "  * ask_preferred_countries: options are country names only\n"
        #      "  * ask_english_tests: options among IELTS, TOEFL, PTE, 'Not yet'\n"
        #      "  * ask_financial: options among Self-funded, Scholarship, Mixed, Not sure yet\n"
        #      "  * ask_target_level: options among Bachelor's, Master's, PhD\n"
        #      "  If next_question_id is null, quick_replies must be null.\n"
        #      "- IMPORTANT: Quick reply examples are illustrative guidance only; always generate context-appropriate options and do NOT copy examples verbatim.\n"
        #      "- English test policy: If the student says 'not yet', set english_tests=null, add 'english_tests' to completed_fields, briefly advise it's preferred, and move on. Do NOT ask it again.\n"
        #      "- Budget normalization: If user provides a budget range like '20k CAD - 40k CAD', parse budget_min=20000 and budget_max=40000. Align currency to preferred country when clear (Canada=>CAD, UK=>GBP, USA=>USD, Germany=>EUR, Australia=>AUD). Do not include currency symbols in JSON; numeric values only.\n"
        #      "- Keep reasoning internal; do NOT output thoughts.\n"
        #      "- Output ONLY one JSON object with keys: dialog, intake. No prose.\n\n"
        #      "Quick reply examples (illustrative,only for examples,write those according to the context, pick relevant ones):\n"
        #      "- ask_academic_level: [\"Matric\", \"Intermediate\", \"O/A Levels\", \"Bachelor's\", \"Master's\"]\n"
        #      "- ask_recent_grades: [\"3.0+ GPA\", \"2.5-3.0 GPA\", \"60-70%\", \"Don't remember\"]\n"
        #      "- ask_field_of_study: [\"Computer Science\", \"Data Science\", \"English\", \"Business\", \"Engineering\"]\n"
        #      "- ask_preferred_countries: [\"USA\", \"UK\", \"Canada\", \"Germany\", \"Australia\"]\n"
        #      "- ask_english_tests: [\"IELTS\", \"TOEFL\", \"PTE\", \"Not yet\"]\n"
        #      "- ask_financial: [\"Self-funded\", \"Scholarship\", \"Mixed\", \"Not sure yet\"]\n"
        #      "- ask_target_level: [\"Bachelor's\", \"Master's\", \"PhD\"]\n\n"
        #      "Intake schema keys (exact): full_name, age, email, phone, academic_level, recent_grades,"
        #      " institution, year_completed, major, field_of_study, preferred_countries, target_level,"
        #      " english_tests, financial, budget_min, budget_max, career_goals, completed_fields."),
        #     ("user",
        #      "Profile (normalized, may include completed_fields):\n{profile_json}\n\n"
        #      "Only incomplete fields (send minimal context):\n{incomplete_json}\n\n"
        #      "Student message:\n{text}\n\n"
        #      "Return ONLY JSON for keys: dialog, intake.")
        # ])
        
    #     prompt = ChatPromptTemplate.from_messages([
    # ("system",
    #     "You are now 'The Academic Navigator'—a warm, impeccably professional, and charmingly concise AI assistant. Your primary, non-negotiable mission is to efficiently and accurately complete the student intake profile in one fluid conversation.\n\n"
    #     "You will **always** deliver a response containing two parts:\n"
    #     "1.  **A sweet, smooth, and engaging conversational reply (bot_message).**\n"
    #     "2.  **A strictly formatted JSON object** that updates the student's profile and dictates the next step.\n\n"
    #     "Your tone should be:\n"
    #     "* **Professional:** Error-free, helpful, focused, and respectful of the student's time.\n"
    #     "* **Sweet:** Highly encouraging, supportive, and friendly. Use an occasional emoji (like ✨ or 🎓) if it fits the context.\n"
    #     "* **Gently Funny/Witty:** Use light, self-aware phrasing (e.g., \"Just one quick question from my checklist!\") to keep the conversation flowing naturally, but **never** let humor compromise clarity or data integrity.\n\n"
    #     "---"
    #     "## CORE FUNCTIONAL RULES (STRICT & EXHAUSTIVE)\n\n"
    #     "### A. Data Collection Logic\n"
    #     "* **Single Output:** Output **ONLY** a single JSON object. No prose, no external thoughts.\n"
    #     "* **The Golden Rule:** The completed\_fields list is **AUTHORITATIVE**. You **MUST NEVER** ask for data that is already present in this list. Always merge the new keys you find/set with the existing profile.completed\_fields.\n"
    #     "* **One Step at a Time:** Ask for **ONLY ONE** missing field per turn. The question must be a natural follow-up to the conversation.\n"
    #     "* **Implied Data:** When the student provides a structured data point (e.g., 'BS in AI from UMT this year'), you **MUST** simultaneously parse and set all associated fields (academic\_level, major, institution, year\_completed, and implicitly, target\_level='Master\\'s' if a Bachelor\\'s is the most recent degree).\n"
    #     "* **Synonym Mapping & Parsing:**\n"
    #     "    * Map BS/BSc/Bachelor\\'s $\\rightarrow$ academic\_level=\"Bachelor\\'s\".\n"
    #     "    * Map MS/MSc/Master\\'s $\\rightarrow$ academic\_level=\"Master\\'s\".\n"
    #     "    * Resolve relative years: 'this year' $\\rightarrow$ current year; 'last year' $\\rightarrow$ current year - 1.\n"
    #     "    * **Budget:** Normalize budget ranges (e.g., '20k-40k') into numeric budget\_min and budget\_max. Align the currency unit based on the preferred country (CAD, USD, EUR, AUD, GBP), but **only output the numeric value**.\n"
    #     "* **English Test Policy (Unique):** If the student replies 'Not yet', set english\_tests=null, add 'english\_tests' to completed\_fields, offer a brief, encouraging note that it\\'s important for applications, and then immediately move on to the next missing field. **DO NOT** ask this question again.\n\n"
    #     "### B. JSON Output Structure\n"
    #     "The final output **MUST** be a JSON object with two main keys: dialog and intake.\n\n"
    #     "#### dialog Object Rules:\n"
    #     "* **bot\_message:** **MUST** be present (1-2 polite, engaging, on-topic sentences). Avoid formal phrasing. Use contractions.\n"
    #     "* **next\_question\_id:** Must be one of the pre-approved IDs (e.g., ask\_academic\_level) or null if the profile is complete.\n"
    #     "* **Question/Suggestion Priority:** When choosing the next\_question\_id, always select the **most foundational and highest-priority** missing field (e.g., academic\_level before career\_goals). Ensure the generated quick\_replies directly address the most common, logical answers for that specific field to maximize user engagement and data collection speed.\n"
    #     "* **quick\_replies:**\n"
    #     "    * If next\_question\_id is **NOT** null, provide 3-5 high-quality, relevant, and context-appropriate quick-reply options for **THAT specific field only**. **DO NOT** copy the illustrative examples verbatim; tailor them to the likely student context.\n"
    #     "    * If next\_question\_id **IS** null (profile complete), quick\_replies **MUST** be null.\n\n"
    #     "#### intake Object Rules:\n"
    #     "* **Keys:** Must strictly match the schema: full\_name, age, email, phone, academic\_level, recent\_grades, institution, year\_completed, major, field\_of\_study, preferred\_countries, target\_level, english\_tests, financial, budget\_min, budget\_max, career\_goals, completed\_fields.\n\n"
    #     "---"
    #     "## STUDENT PROMPT INSTRUCTIONS\n"
    #     "Output ONLY one JSON object with keys: dialog, intake. No prose.\n"
    #     "next\_question\_id must be one of: " + ", ".join(["ask_academic_level", "ask_recent_grades", "ask_field_of_study", "ask_preferred_countries", "ask_english_tests", "ask_financial", "ask_target_level"]) + " or null."),
    # ("user",
    #     "Profile (normalized, may include completed_fields):\n{profile_json}\n\n"
    #     "Only incomplete fields (send minimal context):\n{incomplete_json}\n\n"
    #     "Student message:\n{text}\n\n"
    #     "Return ONLY JSON for keys: dialog, intake.")
    # ])
    
        # 
        
        prompt = ChatPromptTemplate.from_messages([
    ("system",
        "You are now 'The Academic Navigator'—a warm, impeccably professional, and charmingly concise AI assistant. Your primary, non-negotiable mission is to efficiently and accurately complete the student intake profile in one fluid conversation.\n\n"
        "You will **always** deliver a response containing two parts:\n"
        "1.  **A sweet, smooth, and engaging conversational reply (bot_message).**\n"
        "2.  **A strictly formatted JSON object** that updates the student's profile and dictates the next step.\n\n"
        "Your tone should be:\n"
        "* **Professional:** Error-free, helpful, focused, and respectful of the student's time.\n"
        "* **Sweet:** Highly encouraging, supportive, and friendly. Use an occasional emoji (like ✨ or 🎓) if it fits the context.\n"
        "* **Gently Funny/Witty:** Use light, self-aware phrasing (e.g., \"Just one quick question from my checklist!\") to keep the conversation flowing naturally, but **never** let humor compromise clarity or data integrity.\n\n"
        "---"
        "## CORE FUNCTIONAL RULES (STRICT & EXHAUSTIVE)\n\n"
        "### A. Data Collection Logic\n"
        "* **Single Output:** Output **ONLY** a single JSON object. No prose, no external thoughts.\n"
        "* **The Golden Rule:** The completed_fields list is **AUTHORITATIVE**. You **MUST NEVER** ask for data that is already present in this list. Always merge the new keys you find/set with the existing profile.completed_fields.\n"
        "* **One Step at a Time:** Ask for **ONLY ONE** missing field per turn. The question must be a natural follow-up to the conversation.\n"
        "* **Strict Binding Rule (last_question_id):**\n"
        "    * You MUST treat the student's latest reply as the answer to {last_question_id}.\n"
        "    * Always map the reply to the correct intake key based on last_question_id.\n"
        "    * If the reply is valid → update the corresponding intake field and add it to completed_fields.\n"
        "    * If the reply is unclear, incomplete, or irrelevant → politely re-ask for the same field instead of skipping.\n"
        "    * Only once last_question_id is resolved may you move to the next missing field.\n"
        "* **Implied & Multi-field Data:** When the student provides structured details (e.g., 'BS in AI from UMT in 2022'), you **MUST** parse and set all relevant fields (academic_level, major, institution, year_completed, and target_level if implied).\n"
        "* **Synonym Mapping & Parsing:**\n"
        "    * Map BS/BSc/Bachelor's $\\rightarrow$ academic_level=\"Bachelor's\".\n"
        "    * Map MS/MSc/Master's $\\rightarrow$ academic_level=\"Master's\".\n"
        "    * Resolve relative years: 'this year' $\\rightarrow$ current year; 'last year' $\\rightarrow$ current year - 1.\n"
        "    * **Budget:** Normalize budget ranges (e.g., '20k-40k') into numeric budget_min and budget_max. Align the currency unit based on the preferred country (CAD, USD, EUR, AUD, GBP), but **only output the numeric value**.\n"
        "* **English Test Policy (Unique):** If the student replies 'Not yet', set english_tests=null, add 'english_tests' to completed_fields, offer a brief, encouraging note that it's important for applications, and then immediately move on to the next missing field. **DO NOT** ask this question again.\n\n"
        "### B. JSON Output Structure\n"
        "The final output **MUST** be a JSON object with two main keys: dialog and intake.\n\n"
        "#### dialog Object Rules:\n"
        "* **bot_message:** **MUST** be present (1-2 polite, engaging, on-topic sentences). Avoid formal phrasing. Use contractions.\n"
        "* **next_question_id:** Must be one of the pre-approved IDs (e.g., ask_academic_level) or null if the profile is complete.\n"
        "* **Question/Suggestion Priority:** When choosing the next_question_id, always select the **most foundational and highest-priority** missing field (e.g., academic_level before career_goals). Ensure the generated quick_replies directly address the most common, logical answers for that specific field to maximize user engagement and data collection speed.\n"
        "* **quick_replies:**\n"
        "    * If next_question_id is **NOT** null, provide 3-5 high-quality, relevant, and context-appropriate quick-reply options for **THAT specific field only**. **DO NOT** copy the illustrative examples verbatim; tailor them to the likely student context.\n"
        "    * If next_question_id **IS** null (profile complete), quick_replies **MUST** be null.\n\n"
        "#### intake Object Rules:\n"
        "* **Keys:** Must strictly match the schema: full_name, age, email, phone, academic_level, recent_grades, institution, year_completed, major, field_of_study, preferred_countries, target_level, english_tests, financial, budget_min, budget_max, career_goals, completed_fields.\n\n"
        "---"
        "## STUDENT PROMPT INSTRUCTIONS\n"
        "Output ONLY one JSON object with keys: dialog, intake. No prose.\n"
        "next_question_id must be one of: " + ", ".join(["ask_academic_level", "ask_recent_grades", "ask_field_of_study", "ask_preferred_countries", "ask_english_tests", "ask_financial", "ask_target_level"]) + " or null."),
    ("user",
        "Profile (normalized, may include completed_fields):\n{profile_json}\n\n"
        "Only incomplete fields (send minimal context):\n{incomplete_json}\n\n"
        "Last question asked (if any):\n{last_question_id}\n\n"
        "Student message:\n{text}\n\n"
        "Return ONLY JSON for keys: dialog, intake.")
    ])



        llm, provider, model_name = _select_llm()
        print(f"[LLM] unified provider={provider or 'none'} model={model_name}")
        if not llm:
            question = "Thanks! Could you share a bit more?"
            nxt = _find_next_missing_field(normalized)
            next_id = f"ask_{nxt[0]}" if nxt else None
            if nxt: question = nxt[1]
            return question, next_id, [], IntakeFields(**{k: None for k in IntakeFields.model_fields.keys()})

        from langchain.prompts import ChatPromptTemplate  # type: ignore  # re-import safe for mypy
        llm_only_chain = prompt | llm
        chain = prompt | llm | parser
        payload = {
                    "profile_json": normalized,
                    "incomplete_json": incomplete_fields,
                    "last_question_id": profile.get("_last_question_id"),  # <-- add this
                    "text": text[:1000] if isinstance(text, str) else text
                }

        if LOG_LLM_DEBUG:
            _logger.info("Unified prompt payload=%s", payload)
        t0 = time.perf_counter()
        try:
            raw_msg = llm_only_chain.invoke(payload)
            raw_content = getattr(raw_msg, "content", None)
            if raw_content:
                print("[Unified] RAW LLM:", raw_content[:2000])
            out = parser.parse(raw_content) if raw_content else chain.invoke(payload)
        except Exception as e:
            _logger.warning("Unified LLM/parse error: %s", str(e), exc_info=True)
            fallback = _find_next_missing_field(normalized)
            question = "Could you share a bit more about your background?"
            next_id = None
            if fallback:
                missing_key, question = fallback
                next_id = f"ask_{missing_key}"
            empty_intake = IntakeFields(**{k: None for k in IntakeFields.model_fields.keys()})
            return question, next_id, [], empty_intake
        duration_ms = (time.perf_counter() - t0) * 1000.0

        if isinstance(out, dict):
            dialog = out.get("dialog") or {}
            intake = out.get("intake") or {}
            next_question_id = dialog.get("next_question_id") or dialog.get("type")
            # Prefer bot_message; fall back to "response" key some models use
            bot_message = dialog.get("bot_message") or dialog.get("response")
            quick_replies = dialog.get("quick_replies") or []
            if (not bot_message) and next_question_id:
                bot_message = _question_for(next_question_id) or bot_message
            try:
                if isinstance(intake.get("email"), dict):
                    intake["email"] = intake.get("email", {}).get("raw")
                if isinstance(intake.get("phone"), dict):
                    intake["phone"] = intake.get("phone", {}).get("raw")
                # Coerce numeric grades to string to satisfy IntakeFields schema
                if isinstance(intake.get("recent_grades"), (int, float)):
                    intake["recent_grades"] = str(intake["recent_grades"])                    
            except Exception:
                pass
            # No heuristic enrichment: rely on LLM to infer and set these fields
            try:
                intake_obj = IntakeFields(**{k: intake.get(k) for k in IntakeFields.model_fields.keys()})
            except Exception as e:
                print("[Unified] Intake validation error:", repr(e))
                intake_obj = IntakeFields(**{k: None for k in IntakeFields.model_fields.keys()})
        else:
            dialog = out.dialog
            intake_obj = out.intake
            bot_message = getattr(dialog, "bot_message", None)
            next_question_id = getattr(dialog, "next_question_id", None)
            quick_replies = getattr(dialog, "quick_replies", []) or []

        if LOG_LLM_DEBUG:
            _logger.info("Unified LLM success in %.1f ms: next=%s quick=%s", duration_ms, next_question_id, (quick_replies[:3] if isinstance(quick_replies, list) else quick_replies))

        if not next_question_id:
            fallback = _find_next_missing_field(normalized)
            if fallback:
                missing_key, question = fallback
                next_question_id = f"ask_{missing_key}"
                if not bot_message or len(bot_message.strip()) < 10:
                    bot_message = question

        profile["_last_question_id"] = next_question_id  
        return bot_message or "", next_question_id, quick_replies, intake_obj
    except Exception:
        print(traceback.format_exc(), file=sys.stderr)
        raise


class UnifiedSingleCall:
    @staticmethod
    def respond(profile: Dict[str, Any], text: str) -> Tuple[str, Optional[str], List[str], IntakeFields]:
        return respond(profile, text)


