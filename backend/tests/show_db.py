import json
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.models.session import Session as SessionModel
from app.models.message import Message
from app.models.document import Document
from app.models.student_profile import StudentProfile
from app.models.academic_history import AcademicHistory
from app.models.english_test import EnglishTest
from app.models.study_preference import StudyPreference


def dump_table(name: str, rows):
    print(f"\n=== {name} ({len(rows)}) ===")
    for r in rows:
        try:
            d = r.__dict__.copy()
            d.pop('_sa_instance_state', None)
            print(json.dumps(d, default=str, indent=2))
        except Exception:
            print(r)


def main():
    db: Session = SessionLocal()
    try:
        sessions = db.query(SessionModel).order_by(SessionModel.created_at.asc()).all()
        print(f"\n######## DATABASE DUMP ({len(sessions)} sessions) ########")
        for s in sessions:
            sid = str(s.id)
            print("\n======================================================")
            print(f"Session: {sid}")
            print("------------------------------------------------------")
            dump_table("session", [s])
            # Pretty print session.profile JSON separately for clarity
            try:
                print("\n--- session.profile (pretty) ---")
                profile_obj = s.profile
                if isinstance(profile_obj, str):
                    try:
                        profile_obj = json.loads(profile_obj)
                    except Exception:
                        pass
                print(json.dumps(profile_obj, default=str, indent=2))
            except Exception:
                pass
            msgs = db.query(Message).filter(Message.session_id == s.id).order_by(Message.created_at.asc()).all()
            dump_table("messages", msgs)
            docs = db.query(Document).filter(Document.session_id == s.id).all()
            dump_table("documents", docs)
            prof = db.query(StudentProfile).filter(StudentProfile.session_id == s.id).all()
            dump_table("student_profiles", prof)
            ah = db.query(AcademicHistory).filter(AcademicHistory.session_id == s.id).order_by(AcademicHistory.created_at.asc()).all()
            dump_table("academic_history", ah)
            et = db.query(EnglishTest).filter(EnglishTest.session_id == s.id).order_by(EnglishTest.created_at.asc()).all()
            dump_table("english_tests", et)
            sp = db.query(StudyPreference).filter(StudyPreference.session_id == s.id).all()
            dump_table("study_preferences", sp)
    finally:
        db.close()


if __name__ == "__main__":
    main()
