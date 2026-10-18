"""
FastAPI application — Voice AI Patient Registration System.

Routes:
  GET  /                     HTML live dashboard
  GET  /patients             List patients (with optional filters)
  GET  /patients/{id}        Get single patient
  POST /patients             Create patient
  PUT  /patients/{id}        Update patient (PATCH-style)
  DELETE /patients/{id}      Soft-delete patient
  POST /vapi/webhook         Vapi voice agent tool calls
"""

from __future__ import annotations

import json
import logging
import os
from datetime import date
from typing import Optional
from uuid import UUID

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse

load_dotenv()

from database import (
    check_existing_patient_service,
    create_patient_service,
    get_patient_by_id_service,
    get_patients_service,
    soft_delete_patient_service,
    update_patient_service,
)
from models import PatientCreate, PatientUpdate, normalize_phone

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Voice AI Patient Registration API",
    description="REST API for voice-based patient registration via Vapi",
    version="1.0.0",
)


# ---------------------------------------------------------------------------
# Error response helpers
# ---------------------------------------------------------------------------

def ok(data) -> dict:
    return {"data": data, "error": None}


def err(code: str, message: str, details=None) -> dict:
    return {"data": None, "error": {"code": code, "message": message, "details": details}}


# ---------------------------------------------------------------------------
# Custom exception handlers — enforce the {data, error} envelope everywhere
# ---------------------------------------------------------------------------

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    details = []
    for e in exc.errors():
        loc = " → ".join(str(x) for x in e["loc"] if x != "body")
        details.append({"field": loc, "message": e["msg"]})
    return JSONResponse(
        status_code=422,
        content=err("VALIDATION_ERROR", "Request validation failed", details),
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content=err("HTTP_ERROR", str(exc.detail)),
    )


# ---------------------------------------------------------------------------
# Root — HTML live dashboard
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the live patient registration dashboard."""
    with open("templates/index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    return ok({"status": "ok", "service": "Voice AI Patient Registration API"})


# ---------------------------------------------------------------------------
# GET /patients
# ---------------------------------------------------------------------------

@app.get("/patients")
async def list_patients(
    last_name: Optional[str] = Query(None),
    date_of_birth: Optional[str] = Query(None),
    phone_number: Optional[str] = Query(None),
):
    """List all active patients with optional filters."""
    try:
        # Normalize phone if provided
        normalized_phone = None
        if phone_number:
            try:
                normalized_phone = normalize_phone(phone_number)
            except ValueError as e:
                return JSONResponse(
                    status_code=400,
                    content=err("VALIDATION_ERROR", str(e)),
                )

        patients = get_patients_service(
            last_name=last_name,
            date_of_birth=date_of_birth,
            phone_number=normalized_phone,
        )
        return JSONResponse(status_code=200, content=ok(patients))
    except Exception as e:
        logger.exception("Error listing patients")
        return JSONResponse(
            status_code=500, content=err("INTERNAL_ERROR", "Failed to retrieve patients")
        )


# ---------------------------------------------------------------------------
# GET /patients/{patient_id}
# ---------------------------------------------------------------------------

@app.get("/patients/{patient_id}")
async def get_patient(patient_id: str):
    """Retrieve a single active patient by UUID."""
    try:
        UUID(patient_id)
    except ValueError:
        return JSONResponse(
            status_code=422,
            content=err("VALIDATION_ERROR", "patient_id must be a valid UUID"),
        )

    try:
        patient = get_patient_by_id_service(patient_id)
        if not patient:
            return JSONResponse(
                status_code=404,
                content=err("NOT_FOUND", f"Patient {patient_id} not found or has been deleted"),
            )
        return JSONResponse(status_code=200, content=ok(patient))
    except Exception as e:
        logger.exception("Error fetching patient %s", patient_id)
        return JSONResponse(
            status_code=500, content=err("INTERNAL_ERROR", "Failed to retrieve patient")
        )


# ---------------------------------------------------------------------------
# POST /patients
# ---------------------------------------------------------------------------

@app.post("/patients")
async def create_patient(payload: PatientCreate):
    """Create a new patient record."""
    try:
        logger.info(
            "POST /patients — creating patient: %s %s",
            payload.first_name,
            payload.last_name,
        )
        patient = create_patient_service(payload)
        return JSONResponse(status_code=201, content=ok(patient))
    except Exception as e:
        logger.exception("Error creating patient")
        return JSONResponse(
            status_code=500, content=err("INTERNAL_ERROR", f"Failed to create patient: {str(e)}")
        )


# ---------------------------------------------------------------------------
# PUT /patients/{patient_id}
# ---------------------------------------------------------------------------

@app.put("/patients/{patient_id}")
async def update_patient(patient_id: str, payload: PatientUpdate):
    """Update an existing patient (PATCH-style: only provided fields are changed)."""
    try:
        UUID(patient_id)
    except ValueError:
        return JSONResponse(
            status_code=422,
            content=err("VALIDATION_ERROR", "patient_id must be a valid UUID"),
        )

    try:
        # Check patient exists first
        existing = get_patient_by_id_service(patient_id)
        if not existing:
            return JSONResponse(
                status_code=404,
                content=err("NOT_FOUND", f"Patient {patient_id} not found or has been deleted"),
            )

        logger.info("PUT /patients/%s — updating fields: %s", patient_id, list(payload.non_null_fields().keys()))
        updated = update_patient_service(patient_id, payload)
        return JSONResponse(status_code=200, content=ok(updated))
    except Exception as e:
        logger.exception("Error updating patient %s", patient_id)
        return JSONResponse(
            status_code=500, content=err("INTERNAL_ERROR", f"Failed to update patient: {str(e)}")
        )


# ---------------------------------------------------------------------------
# DELETE /patients/{patient_id}  (soft delete)
# ---------------------------------------------------------------------------

@app.delete("/patients/{patient_id}")
async def delete_patient(patient_id: str):
    """Soft-delete a patient (sets deleted_at, does NOT hard-delete)."""
    try:
        UUID(patient_id)
    except ValueError:
        return JSONResponse(
            status_code=422,
            content=err("VALIDATION_ERROR", "patient_id must be a valid UUID"),
        )

    try:
        deleted = soft_delete_patient_service(patient_id)
        if not deleted:
            return JSONResponse(
                status_code=404,
                content=err("NOT_FOUND", f"Patient {patient_id} not found or already deleted"),
            )
        logger.info("DELETE /patients/%s — soft-deleted", patient_id)
        return JSONResponse(
            status_code=200,
            content=ok({"message": f"Patient {patient_id} has been deleted", "patient": deleted}),
        )
    except Exception as e:
        logger.exception("Error deleting patient %s", patient_id)
        return JSONResponse(
            status_code=500, content=err("INTERNAL_ERROR", "Failed to delete patient")
        )


# ---------------------------------------------------------------------------
# POST /vapi/webhook  — Vapi voice agent tool calls
# ---------------------------------------------------------------------------

@app.post("/vapi/webhook")
async def vapi_webhook(request: Request):
    """
    Handle Vapi Server URL / Custom Tool calls.
    Always returns HTTP 200 with { results: [{ toolCallId, result }] }.
    """
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            status_code=400,
            content=err("PARSE_ERROR", "Invalid JSON body"),
        )

    logger.info("POST /vapi/webhook — payload type: %s", body.get("type"))

    # Vapi sends different event types; we only act on tool-calls
    message = body.get("message", {})
    msg_type = message.get("type")

    # Handle end-of-call report — just log it
    if msg_type == "end-of-call-report":
        transcript = message.get("transcript", "")
        summary = message.get("summary", "")
        logger.info("END OF CALL REPORT — Summary: %s", summary)
        logger.info("END OF CALL TRANSCRIPT: %s", transcript[:500])
        return JSONResponse(status_code=200, content={"received": True})

    # Handle tool-calls
    tool_calls = message.get("toolCalls", [])
    if not tool_calls:
        # Also check top-level for older Vapi format
        tool_calls = body.get("toolCalls", [])

    results = []

    for call in tool_calls:
        tool_call_id = call.get("id", "")
        function_data = call.get("function", {})
        tool_name = function_data.get("name", "")
        raw_args = function_data.get("arguments", "{}")

        # Parse args
        if isinstance(raw_args, str):
            try:
                args = json.loads(raw_args)
            except json.JSONDecodeError:
                args = {}
        else:
            args = raw_args

        logger.info(
            "Vapi tool call: tool_call_id=%s name=%s args=%s",
            tool_call_id, tool_name, args,
        )

        result_str = _handle_tool_call(tool_name, args)
        logger.info("Vapi tool result: %s", result_str)

        results.append({"toolCallId": tool_call_id, "result": result_str})

    return JSONResponse(status_code=200, content={"results": results})


def _handle_tool_call(tool_name: str, args: dict) -> str:
    """Dispatch tool call to the appropriate service and return a result string."""

    # ------------------------------------------------------------------
    # check_existing_patient
    # ------------------------------------------------------------------
    if tool_name == "check_existing_patient":
        raw_phone = args.get("phone_number", "")
        if not raw_phone:
            return "VALIDATION_ERROR: phone_number is required to check for an existing patient."
        try:
            phone = normalize_phone(str(raw_phone))
        except ValueError as e:
            return f"VALIDATION_ERROR: {str(e)}"

        existing = check_existing_patient_service(phone)
        if existing:
            return (
                f"FOUND: Patient {existing['first_name']} {existing['last_name']} "
                f"(patient_id={existing['patient_id']}) already exists with this phone number. "
                f"Ask the caller if they would like to update their existing record."
            )
        return "NOT_FOUND: No existing patient found with this phone number. Proceed with registration."

    # ------------------------------------------------------------------
    # register_patient
    # ------------------------------------------------------------------
    elif tool_name == "register_patient":
        patient_id = args.get("patient_id")

        try:
            if patient_id:
                # Update existing patient
                payload = PatientUpdate(**{k: v for k, v in args.items() if k != "patient_id"})
                updated = update_patient_service(str(patient_id), payload)
                if not updated:
                    return f"ERROR: Patient {patient_id} not found or has been deleted."
                return (
                    f"SUCCESS: Patient {updated['first_name']} {updated['last_name']} "
                    f"updated with patient_id {updated['patient_id']}."
                )
            else:
                # Create new patient
                payload = PatientCreate(**args)
                created = create_patient_service(payload)
                logger.info("Vapi created patient: %s", created)
                return (
                    f"SUCCESS: Patient {created['first_name']} {created['last_name']} "
                    f"registered with patient_id {created['patient_id']}."
                )
        except Exception as e:
            logger.exception("Vapi register_patient error")
            return f"VALIDATION_ERROR: {str(e)}. Please ask the caller for a valid value and try again."

    # ------------------------------------------------------------------
    # update_patient
    # ------------------------------------------------------------------
    elif tool_name == "update_patient":
        patient_id = args.get("patient_id")
        if not patient_id:
            return "VALIDATION_ERROR: patient_id is required to update a patient."

        try:
            update_fields = {k: v for k, v in args.items() if k != "patient_id"}
            payload = PatientUpdate(**update_fields)
            updated = update_patient_service(str(patient_id), payload)
            if not updated:
                return f"ERROR: Patient {patient_id} not found or has been deleted."
            return (
                f"SUCCESS: Patient {updated['first_name']} {updated['last_name']} "
                f"(patient_id={updated['patient_id']}) has been updated successfully."
            )
        except Exception as e:
            logger.exception("Vapi update_patient error")
            return f"VALIDATION_ERROR: {str(e)}. Please re-ask the caller for the correct value."

    else:
        logger.warning("Unknown Vapi tool: %s", tool_name)
        return f"ERROR: Unknown tool '{tool_name}'. Supported tools: check_existing_patient, register_patient, update_patient."
