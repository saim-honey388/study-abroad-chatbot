import os
from typing import Optional

from app.db.session import SessionLocal
from app.models.session import Session as SessionModel
from app.models.document import Document
from app.utils.merge_utils import merge_profile
from app.services.unified_single import UnifiedSingleCall


def _extract_text_from_file(file_path: str) -> str:
    # Placeholder: naive binary decode fallback
    try:
        with open(file_path, "rb") as f:
            data = f.read()
        return data.decode("utf-8", errors="ignore")
    except Exception:
        return ""


def process_document(session_id: str, document_id: str, file_path: str, doc_type: Optional[str] = None) -> None:
    db = SessionLocal()
    try:
        doc: Optional[Document] = db.query(Document).filter(Document.id == document_id).first()
        sess: Optional[SessionModel] = db.query(SessionModel).filter(SessionModel.id == session_id).first()
        if not doc or not sess:
            return

        text = _extract_text_from_file(file_path)
        # Reuse unified single call for extraction-only context; ignore dialog, keep intake
        _bot, _next_id, _qr, intake = UnifiedSingleCall.respond(profile=sess.profile, text=text)
        extracted_fields = {k: v for k, v in intake.dict(exclude_none=True).items()}
        updated_profile = merge_profile(sess.profile, extracted_fields)
        sess.profile = updated_profile
        doc.extracted_fields = extracted_fields or {}
        db.add(sess)
        db.add(doc)
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


