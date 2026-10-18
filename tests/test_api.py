"""
Comprehensive automated test suite for Voice AI Patient Registration System.
Tests all REST endpoints, validation errors, envelope structures, and Vapi webhooks.
"""

import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

# Sample valid patient payload
VALID_PATIENT = {
    "first_name": "Alexander",
    "last_name": "Hamilton",
    "date_of_birth": "01/11/1980",
    "sex": "Male",
    "phone_number": "(202) 555-0143",  # Needs normalization to 2025550143
    "email": "alexander.hamilton@treasury.gov",
    "address_line_1": "55 Wall Street",
    "address_line_2": "Suite 100",
    "city": "New York",
    "state": "ny",  # Needs uppercase normalization to NY
    "zip_code": "10005",
    "insurance_provider": "UnitedHealthcare",
    "insurance_member_id": "UHC-998877",
    "preferred_language": "English",
    "emergency_contact_name": "Elizabeth Hamilton",
    "emergency_contact_phone": "202-555-0199",
}


# ============================================================================
# 1. Root & Health Check Tests
# ============================================================================

def test_root_dashboard_html():
    """Verify GET / returns a 200 HTML page with dashboard elements."""
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Wellness Partners" in response.text
    assert "Voice AI Patient Registration" in response.text
    assert "patients-tbody" in response.text


def test_health_endpoint():
    """Verify GET /health returns 200 with standard envelope."""
    response = client.get("/health")
    assert response.status_code == 200
    json_data = response.json()
    assert json_data["error"] is None
    assert json_data["data"]["status"] == "ok"


# ============================================================================
# 2. Patient Creation & Validation Tests
# ============================================================================

def test_create_patient_success():
    """Verify creating a valid patient returns 201 with patient_id and normalized data."""
    response = client.post("/patients", json=VALID_PATIENT)
    assert response.status_code == 201
    res = response.json()
    assert res["error"] is None
    data = res["data"]
    assert "patient_id" in data
    assert data["first_name"] == "Alexander"
    assert data["last_name"] == "Hamilton"
    assert data["phone_number"] == "2025550143"  # Normalized
    assert data["state"] == "NY"  # Uppercase
    assert data["date_of_birth"] == "1980-01-11"
    assert data["deleted_at"] is None


def test_create_patient_validation_future_dob():
    """Verify creation fails with 422 when DOB is in the future."""
    bad_patient = VALID_PATIENT.copy()
    bad_patient["date_of_birth"] = "12/31/2099"
    response = client.post("/patients", json=bad_patient)
    assert response.status_code == 422
    res = response.json()
    assert res["data"] is None
    assert res["error"]["code"] == "VALIDATION_ERROR"
    assert any("future" in str(d).lower() for d in res["error"]["details"])


def test_create_patient_validation_invalid_phone():
    """Verify creation fails when phone is fewer than 10 digits."""
    bad_patient = VALID_PATIENT.copy()
    bad_patient["phone_number"] = "555-12"
    response = client.post("/patients", json=bad_patient)
    assert response.status_code == 422
    res = response.json()
    assert res["data"] is None
    assert res["error"]["code"] == "VALIDATION_ERROR"


def test_create_patient_validation_invalid_state():
    """Verify creation fails with an invalid state code like 'ZZ'."""
    bad_patient = VALID_PATIENT.copy()
    bad_patient["state"] = "ZZ"
    response = client.post("/patients", json=bad_patient)
    assert response.status_code == 422
    res = response.json()
    assert res["data"] is None
    assert res["error"]["code"] == "VALIDATION_ERROR"


def test_create_patient_validation_invalid_sex():
    """Verify creation fails with non-enum sex."""
    bad_patient = VALID_PATIENT.copy()
    bad_patient["sex"] = "Alien"
    response = client.post("/patients", json=bad_patient)
    assert response.status_code == 422
    res = response.json()
    assert res["data"] is None
    assert res["error"]["code"] == "VALIDATION_ERROR"


def test_create_patient_validation_invalid_zip():
    """Verify creation fails with invalid zip code."""
    bad_patient = VALID_PATIENT.copy()
    bad_patient["zip_code"] = "ABCDE"
    response = client.post("/patients", json=bad_patient)
    assert response.status_code == 422
    res = response.json()
    assert res["data"] is None
    assert res["error"]["code"] == "VALIDATION_ERROR"


# ============================================================================
# 3. GET /patients and Filtering Tests
# ============================================================================

def test_list_patients():
    """Verify GET /patients returns list in standard envelope."""
    response = client.get("/patients")
    assert response.status_code == 200
    res = response.json()
    assert res["error"] is None
    assert isinstance(res["data"], list)
    assert len(res["data"]) >= 2  # Seed data present


def test_filter_patients_by_last_name():
    """Verify filter by last_name."""
    response = client.get("/patients?last_name=Mitchell")
    assert response.status_code == 200
    res = response.json()
    assert res["error"] is None
    assert len(res["data"]) >= 1
    assert any(p["last_name"] == "Mitchell" for p in res["data"])


def test_filter_patients_by_phone():
    """Verify filter by phone number."""
    response = client.get("/patients?phone_number=(212) 555-0134")
    assert response.status_code == 200
    res = response.json()
    assert res["error"] is None
    assert len(res["data"]) >= 1
    assert res["data"][0]["phone_number"] == "2125550134"


# ============================================================================
# 4. GET /patients/{id}, PUT, and DELETE Tests
# ============================================================================

def test_crud_lifecycle_and_soft_delete():
    """Test full CRUD lifecycle including partial update and soft delete verification."""
    # 1. Create a test patient
    create_payload = VALID_PATIENT.copy()
    create_payload["first_name"] = "Temporary"
    create_payload["last_name"] = "TestUser"
    create_payload["phone_number"] = "4155550999"

    res_create = client.post("/patients", json=create_payload).json()
    patient_id = res_create["data"]["patient_id"]
    assert patient_id is not None

    # 2. Get by ID
    res_get = client.get(f"/patients/{patient_id}")
    assert res_get.status_code == 200
    assert res_get.json()["data"]["first_name"] == "Temporary"

    # 3. Partial PUT update
    update_payload = {
        "city": "San Francisco",
        "zip_code": "94102",
        "insurance_provider": "Kaiser Permanente"
    }
    res_update = client.put(f"/patients/{patient_id}", json=update_payload)
    assert res_update.status_code == 200
    updated = res_update.json()["data"]
    assert updated["city"] == "San Francisco"
    assert updated["zip_code"] == "94102"
    assert updated["insurance_provider"] == "Kaiser Permanente"
    assert updated["first_name"] == "Temporary"  # Unchanged field preserved

    # 4. Soft delete
    res_delete = client.delete(f"/patients/{patient_id}")
    assert res_delete.status_code == 200
    assert res_delete.json()["error"] is None

    # 5. Verify patient is now excluded from GET /patients/{id} (returns 404)
    res_get_deleted = client.get(f"/patients/{patient_id}")
    assert res_get_deleted.status_code == 404
    assert res_get_deleted.json()["error"]["code"] == "NOT_FOUND"

    # 6. Verify patient is not in GET /patients list
    res_list = client.get("/patients").json()
    assert not any(p["patient_id"] == patient_id for p in res_list["data"])


def test_get_patient_invalid_uuid():
    """Verify 422 when invalid UUID format passed."""
    response = client.get("/patients/not-a-uuid")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_get_patient_not_found():
    """Verify 404 when non-existent UUID passed."""
    response = client.get("/patients/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


# ============================================================================
# 5. Vapi Webhook Tests
# ============================================================================

def test_vapi_webhook_check_existing_patient_found():
    """Verify check_existing_patient returns FOUND for seed patient phone."""
    payload = {
        "message": {
            "type": "tool-calls",
            "toolCalls": [
                {
                    "id": "call_123",
                    "function": {
                        "name": "check_existing_patient",
                        "arguments": {"phone_number": "2125550134"}
                    }
                }
            ]
        }
    }
    response = client.post("/vapi/webhook", json=payload)
    assert response.status_code == 200
    res = response.json()
    assert "results" in res
    result_str = res["results"][0]["result"]
    assert "FOUND:" in result_str
    assert "Sarah" in result_str


def test_vapi_webhook_check_existing_patient_not_found():
    """Verify check_existing_patient returns NOT_FOUND for unknown phone."""
    payload = {
        "message": {
            "type": "tool-calls",
            "toolCalls": [
                {
                    "id": "call_124",
                    "function": {
                        "name": "check_existing_patient",
                        "arguments": {"phone_number": "9995551212"}
                    }
                }
            ]
        }
    }
    response = client.post("/vapi/webhook", json=payload)
    assert response.status_code == 200
    res = response.json()
    result_str = res["results"][0]["result"]
    assert "NOT_FOUND:" in result_str


def test_vapi_webhook_register_patient_validation_error():
    """Verify register_patient returns VALIDATION_ERROR string gracefully without crashing."""
    payload = {
        "message": {
            "type": "tool-calls",
            "toolCalls": [
                {
                    "id": "call_125",
                    "function": {
                        "name": "register_patient",
                        "arguments": {
                            "first_name": "Test",
                            "last_name": "Caller",
                            "date_of_birth": "01/01/2099",  # Future date!
                            "sex": "Female",
                            "phone_number": "5551234567",
                            "address_line_1": "100 Main St",
                            "city": "Dallas",
                            "state": "TX",
                            "zip_code": "75001"
                        }
                    }
                }
            ]
        }
    }
    response = client.post("/vapi/webhook", json=payload)
    assert response.status_code == 200
    res = response.json()
    result_str = res["results"][0]["result"]
    assert "VALIDATION_ERROR:" in result_str
    assert "future" in result_str.lower()


def test_vapi_webhook_toolCallList_format():
    """Verify toolCallList format (used by newer Vapi versions) works correctly."""
    payload = {
        "message": {
            "type": "tool-calls",
            "toolCallList": [
                {
                    "id": "test_list_1",
                    "type": "function",
                    "function": {
                        "name": "check_existing_patient",
                        "arguments": {"phone_number": "5551234567"}
                    }
                }
            ]
        }
    }
    response = client.post("/vapi/webhook", json=payload)
    assert response.status_code == 200
    res = response.json()
    assert len(res["results"]) == 1
    assert res["results"][0]["toolCallId"] == "test_list_1"
    assert "NOT_FOUND:" in res["results"][0]["result"]


