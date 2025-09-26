from sqlalchemy import Column, String, DateTime, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid
from app.db.session import Base

class StudyPreference(Base):
    __tablename__ = "study_preferences"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("sessions.id"), index=True, nullable=False)

    target_level = Column(String, nullable=True)         # e.g., Master's, PhD
    field_of_study = Column(String, nullable=True)
    preferred_countries = Column(String, nullable=True)  # comma-separated list
    funding_type = Column(String, nullable=True)         # self-funded | scholarship
    budget_min = Column(Integer, nullable=True)
    budget_max = Column(Integer, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
