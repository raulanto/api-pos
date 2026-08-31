from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import Column, DateTime, Boolean
from sqlalchemy.sql import func
from typing import Any

class Base(DeclarativeBase):
    pass

class TimestampMixin:
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False)

class SoftDeleteMixin:
    activo = Column(Boolean, default=True, nullable=False)
