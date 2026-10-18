"""
Supabase client initialization and database service functions.
All DB interaction goes through this module.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()


from models import PatientCreate, PatientUpdate

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Client initialization
# ---------------------------------------------------------------------------

_supabase_client: Optional[Client] = None


def get_db() -> Client:
    """Return a cached Supabase client, creating it on first call."""
    global _supabase_client
    if _supabase_client is None:
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        if not url or not key:
            raise RuntimeError(
                "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY environment variables must be set"
            )
        _supabase_client = create_client(url, key)
        logger.info("Supabase client initialized (project: %s)", url)
    return _supabase_client


TABLE = "patients"


# ---------------------------------------------------------------------------
# Service functions
# ---------------------------------------------------------------------------

def serialize_patient(row: dict) -> dict:
    """Convert date fields to strings for consistent serialization."""
    if row.get("date_of_birth") and not isinstance(row["date_of_birth"], str):
        row["date_of_birth"] = row["date_of_birth"].isoformat()
    return row


def get_patients_service(
    last_name: Optional[str] = None,
    date_of_birth: Optional[str] = None,
    phone_number: Optional[str] = None,
) -> list[dict]:
    """List all active patients with optional filters."""
    db = get_db()
    query = db.table(TABLE).select("*").is_("deleted_at", "null")

    if last_name:
        query = query.ilike("last_name", f"%{last_name}%")
    if date_of_birth:
        query = query.eq("date_of_birth", date_of_birth)
    if phone_number:
        query = query.eq("phone_number", phone_number)

    response = query.order("created_at", desc=True).execute()
    logger.info("get_patients_service returned %d records", len(response.data))
    return response.data


def get_patient_by_id_service(patient_id: str) -> Optional[dict]:
    """Fetch a single active patient by UUID."""
    db = get_db()
    response = (
        db.table(TABLE)
        .select("*")
        .eq("patient_id", patient_id)
        .is_("deleted_at", "null")
        .limit(1)
        .execute()
    )
    if not response.data:
        return None
    logger.info("get_patient_by_id_service: found patient %s", patient_id)
    return response.data[0]


def create_patient_service(payload: PatientCreate) -> dict:
    """Insert a new patient record and return it."""
    db = get_db()
    data = payload.model_dump()
    # Convert date to ISO string for supabase
    data["date_of_birth"] = data["date_of_birth"].isoformat()

    logger.info(
        "create_patient_service: inserting patient %s %s, phone=%s",
        data["first_name"],
        data["last_name"],
        data["phone_number"],
    )
    response = db.table(TABLE).insert(data).execute()
    created = response.data[0]
    logger.info("create_patient_service: created patient_id=%s", created["patient_id"])
    return created


def update_patient_service(patient_id: str, payload: PatientUpdate) -> Optional[dict]:
    """Partially update an existing active patient."""
    db = get_db()

    # Only update provided (non-None) fields
    updates = payload.non_null_fields()
    if "date_of_birth" in updates and hasattr(updates["date_of_birth"], "isoformat"):
        updates["date_of_birth"] = updates["date_of_birth"].isoformat()

    if not updates:
        # Nothing to update — return current record
        return get_patient_by_id_service(patient_id)

    logger.info(
        "update_patient_service: updating patient_id=%s fields=%s",
        patient_id,
        list(updates.keys()),
    )

    response = (
        db.table(TABLE)
        .update(updates)
        .eq("patient_id", patient_id)
        .is_("deleted_at", "null")
        .execute()
    )
    if not response.data:
        return None
    updated = response.data[0]
    logger.info("update_patient_service: updated patient_id=%s", patient_id)
    return updated


def soft_delete_patient_service(patient_id: str) -> Optional[dict]:
    """Soft-delete a patient by setting deleted_at to now."""
    db = get_db()
    now_utc = datetime.now(timezone.utc).isoformat()

    logger.info("soft_delete_patient_service: deleting patient_id=%s", patient_id)
    response = (
        db.table(TABLE)
        .update({"deleted_at": now_utc})
        .eq("patient_id", patient_id)
        .is_("deleted_at", "null")
        .execute()
    )
    if not response.data:
        return None
    deleted = response.data[0]
    logger.info("soft_delete_patient_service: soft-deleted patient_id=%s", patient_id)
    return deleted


def check_existing_patient_service(phone_number: str) -> Optional[dict]:
    """Check if an active patient exists with the given 10-digit phone number."""
    db = get_db()
    response = (
        db.table(TABLE)
        .select("patient_id, first_name, last_name, phone_number, email, date_of_birth, sex, address_line_1, city, state, zip_code")
        .eq("phone_number", phone_number)
        .is_("deleted_at", "null")
        .limit(1)
        .execute()
    )
    if not response.data:
        logger.info("check_existing_patient_service: no patient found for phone=%s", phone_number)
        return None
    patient = response.data[0]
    logger.info(
        "check_existing_patient_service: found patient %s %s for phone=%s",
        patient["first_name"],
        patient["last_name"],
        phone_number,
    )
    return patient
