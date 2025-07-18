import uuid

from geoalchemy2 import Geography
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .database import Base


class User(Base):
    __tablename__ = "users"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(Text, unique=True, nullable=False)
    userid = Column(Text, unique=True, nullable=False)  # Clerk User ID
    is_admin = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    alerts = relationship("Alert", back_populates="user")
    warnings = relationship(
        "Warning", back_populates="user", foreign_keys="[Warning.user_id]"
    )
    issued_warnings = relationship(
        "Warning", back_populates="issuer", foreign_keys="[Warning.issued_by]"
    )
    featured_items = relationship("FeaturedItem", back_populates="user")
    reviews = relationship("AdminReview", back_populates="admin")


class Alert(Base):
    __tablename__ = "alerts"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    description = Column(Text, nullable=False)
    type = Column(String, nullable=False)  # 'alert', 'news', 'sale', 'help', 'event'
    status = Column(
        String, nullable=False, default="pending"
    )  # 'pending', 'ai_reviewed', 'reviewed'
    location = Column(Geography(geometry_type="POINT", srid=4326), nullable=False)
    severity = Column(Integer, nullable=False, default=1)
    attachments = Column(JSONB, nullable=False, default=[])
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship("User", back_populates="alerts")
    reviews = relationship(
        "AdminReview", back_populates="alert", cascade="all, delete-orphan"
    )


class AdminReview(Base):
    __tablename__ = "admin_reviews"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    alert_id = Column(UUID(as_uuid=True), ForeignKey("alerts.id"), nullable=False)
    admin_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    vote = Column(Boolean, nullable=False)  # TRUE for approve, FALSE for reject
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    alert = relationship("Alert", back_populates="reviews")
    admin = relationship("User", back_populates="reviews")

    __table_args__ = (UniqueConstraint("alert_id", "admin_id", name="_alert_admin_uc"),)


class Warning(Base):
    __tablename__ = "warnings"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    reason = Column(Text, nullable=False)
    issued_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", foreign_keys=[user_id], back_populates="warnings")
    issuer = relationship(
        "User", foreign_keys=[issued_by], back_populates="issued_warnings"
    )


class FeaturedItem(Base):
    __tablename__ = "featured_items"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    title = Column(Text, nullable=False)
    description = Column(Text)
    attachments = Column(JSONB, nullable=False, default=[])
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False)

    user = relationship("User", back_populates="featured_items")
