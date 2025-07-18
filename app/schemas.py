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

    class Config:
        from_attributes = True


# --- Admin Schemas ---
class AdminReviewCreate(BaseModel):
    vote: bool  # True for approve, False for reject


class AdminReviewResponse(BaseModel):
    message: str
    alert_id: uuid.UUID
    status: str
