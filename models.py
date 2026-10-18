"""
Pydantic v2 models and validators for the Voice AI Patient Registration System.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

US_STATES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "DC", "FL",
    "GA", "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME",
    "MD", "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH",
    "NJ", "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI",
    "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
}

NAME_PATTERN = re.compile(r"^[A-Za-z\-\'\s]{1,50}$")
PHONE_PATTERN = re.compile(r"^\d{10}$")
ZIP_PATTERN = re.compile(r"^\d{5}$|^\d{5}-\d{4}$")
EMAIL_PATTERN = re.compile(r"^[^@]+@[^@]+\.[^@]+$")
INSURANCE_ID_PATTERN = re.compile(r"^[A-Za-z0-9\-]+$")


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class SexEnum(str, Enum):
    MALE = "Male"
    FEMALE = "Female"
    OTHER = "Other"
    DECLINE = "Decline to Answer"


# ---------------------------------------------------------------------------
# Helper validators (reusable)
# ---------------------------------------------------------------------------

def validate_name(v: str, field_name: str) -> str:
    v = v.strip()
    if not v:
        raise ValueError(f"{field_name} cannot be empty")
    if len(v) > 50:
        raise ValueError(f"{field_name} must be 50 characters or fewer")
    if not NAME_PATTERN.match(v):
        raise ValueError(
            f"{field_name} must contain only letters, hyphens, apostrophes, and spaces"
        )
    return v


def normalize_phone(v: str) -> str:
    """Strip common formatting chars and validate 10-digit US phone."""
    v = re.sub(r"[\s\-\(\)\+\.]", "", v)
    # Remove leading country code +1 or 1
    if v.startswith("1") and len(v) == 11:
        v = v[1:]
    if not PHONE_PATTERN.match(v):
        raise ValueError(
            "Phone number must be a valid U.S. 10-digit number (e.g., 5551234567)"
        )
    return v


def parse_dob(v) -> date:
    """Accept date objects or MM/DD/YYYY / YYYY-MM-DD strings."""
    if isinstance(v, date) and not isinstance(v, datetime):
        parsed = v
    elif isinstance(v, datetime):
        parsed = v.date()
    elif isinstance(v, str):
        v = v.strip()
        for fmt in ("%m/%d/%Y", "%Y-%m-%d"):
            try:
                parsed = datetime.strptime(v, fmt).date()
                break
            except ValueError:
                continue
        else:
            raise ValueError(
                "date_of_birth must be in MM/DD/YYYY or YYYY-MM-DD format"
            )
    else:
        raise ValueError("date_of_birth must be a date string or date object")

    if parsed > date.today():
        raise ValueError("date_of_birth cannot be in the future")
    return parsed


# ---------------------------------------------------------------------------
# Request / Create schema
# ---------------------------------------------------------------------------

class PatientCreate(BaseModel):
    first_name: str = Field(..., min_length=1, max_length=50)
    last_name: str = Field(..., min_length=1, max_length=50)
    date_of_birth: date
    sex: SexEnum
    phone_number: str
    email: Optional[str] = None
    address_line_1: str = Field(..., min_length=1)
    address_line_2: Optional[str] = None
    city: str = Field(..., min_length=1, max_length=100)
    state: str = Field(..., min_length=2, max_length=2)
    zip_code: str
    insurance_provider: Optional[str] = None
    insurance_member_id: Optional[str] = None
    preferred_language: str = "English"
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None

    @field_validator("first_name")
    @classmethod
    def validate_first_name(cls, v: str) -> str:
        return validate_name(v, "first_name")

    @field_validator("last_name")
    @classmethod
    def validate_last_name(cls, v: str) -> str:
        return validate_name(v, "last_name")

    @field_validator("date_of_birth", mode="before")
    @classmethod
    def validate_date_of_birth(cls, v) -> date:
        return parse_dob(v)

    @field_validator("phone_number", mode="before")
    @classmethod
    def validate_phone_number(cls, v: str) -> str:
        return normalize_phone(str(v))

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip().lower()
        if not EMAIL_PATTERN.match(v):
            raise ValueError("email must be a valid email address")
        return v

    @field_validator("state")
    @classmethod
    def validate_state(cls, v: str) -> str:
        v = v.strip().upper()
        if v not in US_STATES:
            raise ValueError(
                f"state must be a valid 2-letter U.S. state abbreviation (e.g., NY, CA)"
            )
        return v

    @field_validator("zip_code")
    @classmethod
    def validate_zip_code(cls, v: str) -> str:
        v = v.strip()
        if not ZIP_PATTERN.match(v):
            raise ValueError(
                "zip_code must be a 5-digit ZIP (e.g., 10001) or ZIP+4 (e.g., 10001-1234)"
            )
        return v

    @field_validator("insurance_member_id")
    @classmethod
    def validate_insurance_member_id(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        if not INSURANCE_ID_PATTERN.match(v):
            raise ValueError(
                "insurance_member_id must be alphanumeric with optional hyphens"
            )
        return v

    @field_validator("emergency_contact_phone", mode="before")
    @classmethod
    def validate_emergency_contact_phone(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == "":
            return None
        return normalize_phone(str(v))

    @field_validator("address_line_1", "address_line_2", "city",
                     "insurance_provider", "preferred_language",
                     "emergency_contact_name", mode="before")
    @classmethod
    def strip_strings(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        return v.strip() or None


# ---------------------------------------------------------------------------
# Update schema (all fields optional — PATCH-style inside PUT)
# ---------------------------------------------------------------------------

class PatientUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    date_of_birth: Optional[date] = None
    sex: Optional[SexEnum] = None
    phone_number: Optional[str] = None
    email: Optional[str] = None
    address_line_1: Optional[str] = None
    address_line_2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    insurance_provider: Optional[str] = None
    insurance_member_id: Optional[str] = None
    preferred_language: Optional[str] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None

    @field_validator("first_name")
    @classmethod
    def validate_first_name(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        return validate_name(v, "first_name")

    @field_validator("last_name")
    @classmethod
    def validate_last_name(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        return validate_name(v, "last_name")

    @field_validator("date_of_birth", mode="before")
    @classmethod
    def validate_date_of_birth(cls, v) -> Optional[date]:
        if v is None:
            return v
        return parse_dob(v)

    @field_validator("phone_number", mode="before")
    @classmethod
    def validate_phone_number(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        return normalize_phone(str(v))

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip().lower()
        if not EMAIL_PATTERN.match(v):
            raise ValueError("email must be a valid email address")
        return v

    @field_validator("state")
    @classmethod
    def validate_state(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip().upper()
        if v not in US_STATES:
            raise ValueError("state must be a valid 2-letter U.S. state abbreviation")
        return v

    @field_validator("zip_code")
    @classmethod
    def validate_zip_code(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        if not ZIP_PATTERN.match(v):
            raise ValueError("zip_code must be a 5-digit or ZIP+4 format")
        return v

    @field_validator("insurance_member_id")
    @classmethod
    def validate_insurance_member_id(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        if not INSURANCE_ID_PATTERN.match(v):
            raise ValueError(
                "insurance_member_id must be alphanumeric with optional hyphens"
            )
        return v

    @field_validator("emergency_contact_phone", mode="before")
    @classmethod
    def validate_emergency_contact_phone(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == "":
            return None
        return normalize_phone(str(v))

    def non_null_fields(self) -> dict:
        """Return only the fields that were explicitly set (non-None)."""
        return {k: v for k, v in self.model_dump().items() if v is not None}


# ---------------------------------------------------------------------------
# Response schema
# ---------------------------------------------------------------------------

class PatientResponse(BaseModel):
    patient_id: UUID
    first_name: str
    last_name: str
    date_of_birth: date
    sex: str
    phone_number: str
    email: Optional[str]
    address_line_1: str
    address_line_2: Optional[str]
    city: str
    state: str
    zip_code: str
    insurance_provider: Optional[str]
    insurance_member_id: Optional[str]
    preferred_language: str
    emergency_contact_name: Optional[str]
    emergency_contact_phone: Optional[str]
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime]

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# API envelope
# ---------------------------------------------------------------------------

class ErrorDetail(BaseModel):
    code: str
    message: str
    details: Optional[list] = None


class APIResponse(BaseModel):
    data: Optional[object] = None
    error: Optional[ErrorDetail] = None
