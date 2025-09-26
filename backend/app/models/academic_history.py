from sqlalchemy import Column, String, DateTime, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid
from app.db.session import Base

class AcademicHistory(Base):
    __tablename__ = "academic_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("sessions.id"), index=True, nullable=False)

    level = Column(String, nullable=True)          # e.g., Matric, Intermediate, Bachelor's
    institution = Column(String, nullable=True)
    grades = Column(String, nullable=True)         # GPA/percentage/letter
    major = Column(String, nullable=True)          # academic major/subject (e.g., Artificial Intelligence)
    year_completed = Column(Integer, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
