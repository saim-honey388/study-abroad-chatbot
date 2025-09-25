from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks
import os
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.models.session import Session as SessionModel
from app.models.message import Message
from app.models.document import Document
from app.utils.merge_utils import merge_profile
from app.services.extractor import ExtractorChain
from app.services.dialog import DialogChain
from app.services.document_processor import process_document

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

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
    extracted_fields, _ = ExtractorChain.extract(payload.text, session.profile, expected_field=expected_field)
    updated_profile = merge_profile(session.profile, extracted_fields)
    session.profile = updated_profile
    db.add(session)
    db.commit()
    db.refresh(session)

    # Dialog
    bot_message, next_question_id, quick_replies = DialogChain.next_question(session.profile, last_user_message=payload.text, expected_field=expected_field)

    # Save bot message
    bot_msg = Message(session_id=session.id, sender="bot", text=bot_message, metadata_json={"next_question_id": next_question_id, "quick_replies": quick_replies})
    db.add(bot_msg)
    db.commit()

    return MessageResponse(bot_message=bot_message, profile=session.profile, next_question_id=next_question_id, quick_replies=quick_replies)


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
