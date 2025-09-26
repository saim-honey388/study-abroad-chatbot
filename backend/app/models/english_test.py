from sqlalchemy import Column, String, DateTime, ForeignKey, Float, Date
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid
from app.db.session import Base

class EnglishTest(Base):
    __tablename__ = "english_tests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("sessions.id"), index=True, nullable=False)

    test_name = Column(String, nullable=True)      # IELTS/TOEFL/PTE
    overall_score = Column(Float, nullable=True)
    test_date = Column(Date, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
