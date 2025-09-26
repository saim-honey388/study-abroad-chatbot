from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks
import os
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.models.session import Session as SessionModel
from app.models.message import Message
from app.models.document import Document
from app.models.student_profile import StudentProfile
from app.models.academic_history import AcademicHistory
from app.models.english_test import EnglishTest
from app.models.study_preference import StudyPreference
from app.utils.merge_utils import merge_profile
from app.services.extractor import ExtractorChain
from app.services.dialog import DialogChain
from app.services.document_processor import process_document
from app.config import GEMINI_API_KEY, ENV, DEBUG

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def _persist_extracted(db: Session, session_id, extracted: dict) -> None:
    """Persist selected extracted fields to normalized tables in a minimal, idempotent way."""
    if not extracted:
        return

    # Student profile upsert
    prof = db.query(StudentProfile).filter(StudentProfile.session_id == session_id).first()
    if prof is None:
        prof = StudentProfile(session_id=session_id)
    changed = False
    for key in ("full_name", "age", "email", "phone"):
        if key in extracted and extracted[key] is not None:
            setattr(prof, key, extracted[key])
            changed = True
    if changed:
        db.add(prof)

    # Academic history: upsert a single record per session (trust LLM normalized fields)
    level = extracted.get("academic_level")
    grades = extracted.get("recent_grades") or extracted.get("grades")
    institution = extracted.get("institution") or extracted.get("university") or extracted.get("university_name")
    year_completed = extracted.get("year_completed")
    major = extracted.get("major")
    if level or grades or institution or year_completed or major:
        ah = db.query(AcademicHistory).filter(AcademicHistory.session_id == session_id).order_by(AcademicHistory.created_at.desc()).first()
        if ah is None:
            ah = AcademicHistory(session_id=session_id)
        if level:
            ah.level = level
        if grades:
            ah.grades = grades
        if institution:
            ah.institution = institution
        if year_completed:
            ah.year_completed = year_completed
        if major:
            ah.major = major
        db.add(ah)

    # English tests list (upsert by test_name)
    tests = extracted.get("english_tests") or []
    if isinstance(tests, list):
        for t in tests:
            if not isinstance(t, dict):
                continue
            test_name = t.get("test_name")
            overall_score = t.get("overall_score")
            test_date = t.get("test_date")
            if not (test_name or overall_score or test_date):
                continue
            et = None
            if test_name:
                et = db.query(EnglishTest).filter(EnglishTest.session_id == session_id, EnglishTest.test_name == test_name).first()
            if et is None:
                et = EnglishTest(session_id=session_id, test_name=test_name)
            if overall_score is not None:
                et.overall_score = overall_score
            # Parse date string if present
            try:
                if isinstance(test_date, str):
                    from datetime import date
                    et.test_date = date.fromisoformat(test_date)
            except Exception:
                pass
            db.add(et)

    # Study preferences: upsert single record per session
    pref_changed = False
    sp = db.query(StudyPreference).filter(StudyPreference.session_id == session_id).first()
    if sp is None:
        sp = StudyPreference(session_id=session_id)
    target_level = extracted.get("target_level")
    if target_level:
        sp.target_level = target_level
        pref_changed = True
    field_of_study = extracted.get("field_of_study") or extracted.get("preferred_subject") or extracted.get("subject")
    if field_of_study:
        sp.field_of_study = field_of_study
        pref_changed = True
    preferred_countries = extracted.get("preferred_countries")
    if preferred_countries:
        if isinstance(preferred_countries, list):
            sp.preferred_countries = ",".join(preferred_countries)
        elif isinstance(preferred_countries, str):
            sp.preferred_countries = preferred_countries
        pref_changed = True
    funding = extracted.get("funding_type") or extracted.get("funding")
    if funding:
        sp.funding_type = funding
        pref_changed = True
    # Budget heuristic parsing from strings like "10k - 20k"
    budget_min = extracted.get("budget_min")
    budget_max = extracted.get("budget_max")
    budget_text = extracted.get("budget") or extracted.get("budget_range")
    if (budget_min is None or budget_max is None) and isinstance(budget_text, str):
        import re
        nums = [int(n.replace(",", "")) for n in re.findall(r"\d+", budget_text)]
        if len(nums) == 1:
            budget_min = budget_min or nums[0]
        elif len(nums) >= 2:
            budget_min = budget_min or nums[0]
            budget_max = budget_max or nums[1]
    if budget_min is not None:
        sp.budget_min = budget_min
        pref_changed = True
    if budget_max is not None:
        sp.budget_max = budget_max
        pref_changed = True
    if pref_changed:
        db.add(sp)

    db.flush()

class StartRequest(BaseModel):
    name: str
    phone: str
    email: str

@router.post("/start")
def start_chat(data: StartRequest, db: Session = Depends(get_db)):
    profile = {
        "full_name": data.name,
        "phone": {"raw": data.phone, "verified": False},
        "email": {"raw": data.email, "verified": False},
        "academic_history": [],
        "preferred_subjects": [],
        "preferred_countries": [],
        "english_tests": [],
        "financial": {},
        "career_goals": "",
        "documents": [],
        "last_updated": None
    }
    session = SessionModel(profile=profile)
    db.add(session)
    db.commit()
    db.refresh(session)
    return {"session_id": str(session.id), "bot_message": "Hi! Welcome to the Study Abroad Intake. Let's start with your current academic level."}


class MessageRequest(BaseModel):
    session_id: str
    text: str


class MessageResponse(BaseModel):
    bot_message: str
    profile: dict
    next_question_id: str | None
    quick_replies: list[str] | None = None


@router.post("/message", response_model=MessageResponse)
def send_message(payload: MessageRequest, db: Session = Depends(get_db)):
    session = db.query(SessionModel).filter(SessionModel.id == payload.session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Save user message
    user_msg = Message(session_id=session.id, sender="user", text=payload.text, metadata_json={})
    db.add(user_msg)
    db.commit()

    # Determine the next missing field BEFORE extraction to guide LLM/rules
    _, expected_question_id, _ = DialogChain.next_question(session.profile)
    expected_field = None
    if expected_question_id and expected_question_id.startswith("ask_"):
        expected_field = expected_question_id.replace("ask_", "")

    # Extract and merge
    extracted_fields, _ = ExtractorChain.extract(
        payload.text,
        session.profile,
        expected_field=expected_question_id.replace("ask_", "") if expected_question_id else None
    )
    updated_profile = merge_profile(session.profile, extracted_fields)
    # Mark completed fields to prevent re-asking
    try:
        completed = set(updated_profile.get("completed_fields") or [])
        for k, v in (extracted_fields or {}).items():
            if v is not None and k not in ("english_tests",):
                completed.add(k)
        # Special case: english_tests non-empty marks as completed
        if isinstance(extracted_fields.get("english_tests"), list):
            if len(extracted_fields["english_tests"]) > 0:
                completed.add("english_tests")
        updated_profile["completed_fields"] = list(completed)
    except Exception:
        pass
    session.profile = updated_profile
    db.add(session)
    # Persist normalized tables
    _persist_extracted(db, session.id, extracted_fields)
    db.commit()
    db.refresh(session)

    # Dialog
    bot_message, next_question_id, quick_replies = DialogChain.next_question(session.profile, last_user_message=payload.text, expected_field=expected_field)

    # Sanitize quick replies to be list[str] for response model compatibility
    sanitized_quick: list[str] = []
    if isinstance(quick_replies, list):
        for item in quick_replies:
            if isinstance(item, str):
                sanitized_quick.append(item)
            elif isinstance(item, dict):
                title = item.get("title") or item.get("text")
                sanitized_quick.append(title if isinstance(title, str) else str(item))
            else:
                sanitized_quick.append(str(item))

    # Save bot message
    bot_msg = Message(session_id=session.id, sender="bot", text=bot_message, metadata_json={"next_question_id": next_question_id, "quick_replies": sanitized_quick})
    db.add(bot_msg)
    db.commit()

    return MessageResponse(bot_message=bot_message, profile=session.profile, next_question_id=next_question_id, quick_replies=sanitized_quick)


@router.post("/upload-document")
def upload_document(
    background_tasks: BackgroundTasks,
    session_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    contents = file.file.read()
    storage_dir = "/tmp/uploads"
    os.makedirs(storage_dir, exist_ok=True)
    file_path = f"{storage_dir}/{session_id}_{file.filename}"
    with open(file_path, "wb") as f:
        f.write(contents)

    document = Document(session_id=session.id, s3_key=file_path, filename=file.filename, doc_type=file.content_type)
    db.add(document)
    db.commit()
    db.refresh(document)

    background_tasks.add_task(process_document, str(session.id), str(document.id), file_path, file.content_type)

    return {"status": "queued", "document_id": str(document.id)}


@router.get("/debug/llm-key")
def debug_llm_key():
    if not DEBUG:
        raise HTTPException(status_code=403, detail="LLM key debug endpoint is disabled")
    return {"gemini_api_key": GEMINI_API_KEY or ""}
