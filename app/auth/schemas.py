from datetime import datetime
from typing import Optional, Any, Dict
from pydantic import BaseModel, EmailStr, Field, field_validator


class UserRegisterRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=150, description="Full name of the user")
    email: EmailStr = Field(..., description="Valid email address")
    password: str = Field(..., min_length=6, max_length=128, description="Plaintext password")
    preferred_language: str = Field(default="en", max_length=10, description="Preferred language code (e.g., en, hi)")
    role: Optional[str] = Field(default="CITIZEN", description="Requested role (Public registration is restricted to CITIZEN)")

    @field_validator("role")
    def validate_public_registration_role(cls, v: Optional[str]) -> str:
        if v and v.upper() in ["OFFICER", "ADMIN"]:
            raise ValueError(
                "Security policy violation: OFFICER and ADMIN accounts cannot be self-created via public registration."
            )
        return "CITIZEN"


class UserLoginRequest(BaseModel):
    email: EmailStr = Field(..., description="Registered email address")
    password: str = Field(..., description="Plaintext password")


class UserResponse(BaseModel):
    id: int
    name: str
    email: str
    role: str
    preferred_language: str
    department_id: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_minutes: int
    user: UserResponse


class UserUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=150, description="Updated full name")
    preferred_language: Optional[str] = Field(None, max_length=10, description="Updated language code (en, ta, hi)")