import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator


class UserCreate(BaseModel):
    userid: str
    email: EmailStr
    is_admin: bool = False


class User(BaseModel):
    id: uuid.UUID
    userid: str
    email: EmailStr
    is_admin: bool

    class Config:
        from_attributes = True


# --- Location Schemas ---
class Location(BaseModel):
    type: Literal["Point"] = "Point"
    coordinates: list[float] = Field(..., min_length=2, max_length=2)

    @field_validator("coordinates")
    @classmethod
    def validate_coordinates(cls, v):
        if len(v) != 2:
            raise ValueError(
                "coordinates must contain exactly 2 values [longitude, latitude]"
            )
        lon, lat = v
        if not -180 <= lon <= 180:
            raise ValueError("longitude must be between -180 and 180")
        if not -90 <= lat <= 90:
            raise ValueError("latitude must be between -90 and 90")
        return v


# --- Alert Schemas ---
class AlertCreate(BaseModel):
    description: str = Field(..., min_length=1)
    type: Literal["alert", "news", "sale", "help", "event"]
    location: Location
    severity: int = Field(..., ge=1, le=5)
    attachments: list[str] = Field(default_factory=list)


class AlertResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    description: str
    type: str
    status: str
    severity: int
    attachments: list[str]
    created_at: datetime

    # Add this:
    user_email: str = None

    @classmethod
    def from_alert(cls, alert):
        return cls(
            id=alert.id,
            user_id=alert.user_id,
            description=alert.description,
            type=alert.type,
            status=alert.status,
            severity=alert.severity,
            attachments=alert.attachments,
            created_at=alert.created_at,
            user_email=alert.user.email if alert.user else "Anonymous",
        )


# --- Admin Schemas ---
class AdminReviewCreate(BaseModel):
    vote: bool  # True for approve, False for reject


class AdminReviewResponse(BaseModel):
    message: str
    alert_id: uuid.UUID
    status: str


class NotificationBase(BaseModel):
    title: str
    message: str
    type: str  # 'alert', 'admin', 'system'
    data: dict = {}


class NotificationCreate(NotificationBase):
    user_id: uuid.UUID


class NotificationResponse(NotificationBase):
    id: uuid.UUID
    user_id: uuid.UUID
    read: bool
    created_at: datetime

    class Config:
        from_attributes = True


class NotificationUpdate(BaseModel):
    read: bool | None = None


class NotificationSettings(BaseModel):
    push_enabled: bool = True
    nearby_alerts: bool = True
    admin_updates: bool = True
    system_notifications: bool = False
    email_notifications: bool = False
