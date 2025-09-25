import os
from typing import Optional

from app.db.session import SessionLocal
from app.models.session import Session as SessionModel
from app.models.document import Document
from app.utils.merge_utils import merge_profile
from app.services.extractor import ExtractorChain


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
        extracted_fields, _ = ExtractorChain.extract(text, sess.profile)
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


