"""Seed OpenEMR with test data via FHIR API + direct DB inserts.

Creates 3 test patients with conditions, medications, and allergies,
plus 3 practitioners with specialties (via PractitionerRole DB inserts).

Patients and Practitioners are created via FHIR POST.
Clinical data (conditions, medications, allergies) are inserted directly
into the MariaDB `lists` table because OpenEMR's FHIR API returns 404
for POST to Condition/MedicationRequest/AllergyIntolerance.

Run: cd agentforge-healthcare && ./venv/Scripts/python.exe scripts/seed_data.py
"""

import asyncio
import os
import subprocess
import time
from typing import Optional

import httpx


# --- Configuration (reads from env vars, falls back to local dev defaults) ---
BASE_URL = os.getenv("OPENEMR_BASE_URL", "https://localhost:9300")
TOKEN_URL = f"{BASE_URL}/oauth2/default/token"
FHIR_URL = f"{BASE_URL}/apis/default/fhir"

CLIENT_ID = os.getenv("OPENEMR_CLIENT_ID", "Xkkz8itnTxUSZacmtgeVEHckBfIoZbq2Pa6mNFPGC2g")
CLIENT_SECRET = os.getenv("OPENEMR_CLIENT_SECRET", "NIs4l6mPdf3Qpz5gHo2f4NP8tDm8jQ2xTPuQBDEs4av1YRTzZvpk_L48JTwE-gUpWwlrPDciC-MU30LdjN6_CA")
USERNAME = os.getenv("OPENEMR_USERNAME", "admin")
PASSWORD = os.getenv("OPENEMR_PASSWORD", "pass")

# Write scopes for seeding
WRITE_SCOPES = (
    "openid api:fhir "
    "user/Patient.read user/Patient.write "
    "user/Condition.read user/MedicationRequest.read "
    "user/AllergyIntolerance.read "
    "user/Practitioner.read user/Practitioner.write "
    "user/Organization.read"
)

# Docker container name for OpenEMR (used for DB inserts)
# Set OPENEMR_CONTAINER env var to override auto-detection (e.g., for docker compose)
OPENEMR_CONTAINER = os.getenv("OPENEMR_CONTAINER", None)


# --- DB Helper Functions for Clinical Data ---

def _get_pid_by_name(fname: str, lname: str) -> Optional[str]:
    """Get the integer PID from patient_data table by name."""
    result = _run_db_query(
        f"SELECT pid FROM patient_data WHERE fname='{fname}' AND lname='{lname}' LIMIT 1;"
    )
    lines = [l for l in result.strip().split("\n") if l and l != "pid"]
    return lines[0].strip() if lines else None


def _insert_condition(pid: str, title: str, icd_code: str):
    """Insert a condition into the lists table with UUID registration."""
    safe_title = title.replace("'", "\\'")
    sql = (
        f"INSERT INTO lists (date, type, title, diagnosis, activity, pid, `user`, groupname, uuid) "
        f"VALUES (NOW(), 'medical_problem', '{safe_title}', 'ICD10:{icd_code}', 1, {pid}, 'admin', 'Default', UNHEX(REPLACE(UUID(), '-', '')));"
    )
    _run_db_query(sql)
    _run_db_query(
        "INSERT INTO uuid_registry (uuid, table_name, table_id, created) "
        "SELECT uuid, 'lists', id, NOW() FROM lists WHERE id = (SELECT MAX(id) FROM lists);"
    )
    print(f"    Condition: {title} (ICD10:{icd_code})")


def _insert_medication(pid: str, title: str, dosage: str):
    """Insert a medication into the lists table with UUID registration."""
    safe_title = title.replace("'", "\\'")
    safe_dosage = dosage.replace("'", "\\'")
    sql = (
        f"INSERT INTO lists (date, type, title, activity, pid, `user`, groupname, comments, uuid) "
        f"VALUES (NOW(), 'medication', '{safe_title}', 1, {pid}, 'admin', 'Default', '{safe_dosage}', UNHEX(REPLACE(UUID(), '-', '')));"
    )
    _run_db_query(sql)
    _run_db_query(
        "INSERT INTO uuid_registry (uuid, table_name, table_id, created) "
        "SELECT uuid, 'lists', id, NOW() FROM lists WHERE id = (SELECT MAX(id) FROM lists);"
    )
    print(f"    Medication: {title}")


def _insert_allergy(pid: str, title: str, severity: str = "severe", reaction: str = ""):
    """Insert an allergy into the lists table with UUID registration."""
    safe_title = title.replace("'", "\\'")
    safe_reaction = reaction.replace("'", "\\'")
    severity_map = {"high": "severe", "low": "mild", "medium": "moderate"}
    sev = severity_map.get(severity, severity)
    sql = (
        f"INSERT INTO lists (date, type, title, activity, pid, `user`, groupname, severity_al, reaction, uuid) "
        f"VALUES (NOW(), 'allergy', '{safe_title}', 1, {pid}, 'admin', 'Default', '{sev}', '{safe_reaction}', UNHEX(REPLACE(UUID(), '-', '')));"
    )
    _run_db_query(sql)
    _run_db_query(
        "INSERT INTO uuid_registry (uuid, table_name, table_id, created) "
        "SELECT uuid, 'lists', id, NOW() FROM lists WHERE id = (SELECT MAX(id) FROM lists);"
    )
    print(f"    Allergy: {title} (severity: {sev})")


async def get_token(client: httpx.AsyncClient) -> str:
    """Get OAuth2 access token with write scopes."""
    resp = await client.post(TOKEN_URL, data={
        "grant_type": "password",
        "username": USERNAME,
        "password": PASSWORD,
        "user_role": "users",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "scope": WRITE_SCOPES,
    })
    resp.raise_for_status()
    return resp.json()["access_token"]


async def create_resource(client: httpx.AsyncClient, token: str, resource_type: str, data: dict) -> dict:
    """Create a FHIR resource and return the response."""
    resp = await client.post(
        f"{FHIR_URL}/{resource_type}",
        json=data,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/fhir+json",
        },
    )
    if resp.status_code >= 400:
        print(f"  ERROR creating {resource_type}: {resp.status_code} {resp.text[:200]}")
        return {}
    result = resp.json()
    # OpenEMR returns {"pid": N, "uuid": "..."} for Patient creates,
    # and {"uuid": "..."} for other resources — NOT a full FHIR resource.
    resource_id = result.get("uuid") or result.get("id") or "?"
    print(f"  Created {resource_type}/{resource_id}")
    return result


async def find_patient(client: httpx.AsyncClient, token: str, family: str, given: str) -> Optional[str]:
    """Search for an existing patient by name. Returns UUID if found."""
    resp = await client.get(
        f"{FHIR_URL}/Patient",
        params={"family": family, "given": given},
        headers={"Authorization": f"Bearer {token}"},
    )
    if resp.status_code != 200:
        return None
    entries = resp.json().get("entry", [])
    if entries:
        patient = entries[0].get("resource", {})
        pid = patient.get("id")
        print(f"  Found existing Patient: {given} {family} (ID: {pid})")
        return pid
    return None


async def get_or_create_patient(client: httpx.AsyncClient, token: str, data: dict) -> Optional[str]:
    """Find existing patient or create new one. Returns patient UUID."""
    name = data.get("name", [{}])[0]
    family = name.get("family", "")
    given = name.get("given", [""])[0]

    # Check if already exists
    existing_id = await find_patient(client, token, family, given)
    if existing_id:
        return existing_id

    # Create new
    result = await create_resource(client, token, "Patient", data)
    return result.get("uuid") or result.get("id")


async def seed():
    """Main seeding function."""
    async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
        print("Getting OAuth token with write scopes...")
        token = await get_token(client)
        print("Token obtained.\n")

        # ========== PATIENT 1: John Smith ==========
        print("=== Patient 1: John Smith ===")
        p1_id = await get_or_create_patient(client, token, {
            "resourceType": "Patient",
            "name": [{"use": "official", "family": "Smith", "given": ["John"]}],
            "birthDate": "1965-03-15",
            "gender": "male",
            "telecom": [
                {"system": "phone", "value": "555-0101"},
                {"system": "email", "value": "john.smith@email.com"},
            ],
            "address": [{"line": ["123 Main St"], "city": "Springfield", "state": "IL", "postalCode": "62701"}],
        })
        if not p1_id:
            print("Failed to find/create Patient 1. Aborting.")
            return

        # Get DB PID for direct inserts
        p1_pid = _get_pid_by_name("John", "Smith")
        if not p1_pid:
            print("  WARNING: Could not find DB PID for John Smith")
        else:
            # Check if clinical data already exists
            existing = _run_db_query(f"SELECT COUNT(*) as cnt FROM lists WHERE pid={p1_pid};")
            has_data = "0" not in existing if existing else False
            if has_data:
                print("  Clinical data already exists, skipping inserts")
            else:
                # Conditions: Type 2 Diabetes, Hypertension
                print("  Conditions:")
                _insert_condition(p1_pid, "Type 2 diabetes mellitus without complications", "E11.9")
                _insert_condition(p1_pid, "Essential hypertension", "I10")

                # Medications: Metformin, Lisinopril, Atorvastatin
                print("  Medications:")
                _insert_medication(p1_pid, "Metformin 500 MG Oral Tablet", "Take 1 tablet twice daily with meals")
                _insert_medication(p1_pid, "Lisinopril 10 MG Oral Tablet", "Take 1 tablet daily in the morning")
                _insert_medication(p1_pid, "Atorvastatin 20 MG Oral Tablet", "Take 1 tablet daily at bedtime")

                # Allergy: Penicillin
                print("  Allergies:")
                _insert_allergy(p1_pid, "Penicillin", "high", "Anaphylaxis")
        print()

        # ========== PATIENT 2: Sarah Johnson ==========
        print("=== Patient 2: Sarah Johnson ===")
        p2_id = await get_or_create_patient(client, token, {
            "resourceType": "Patient",
            "name": [{"use": "official", "family": "Johnson", "given": ["Sarah"]}],
            "birthDate": "1978-08-22",
            "gender": "female",
            "telecom": [
                {"system": "phone", "value": "555-0202"},
                {"system": "email", "value": "sarah.johnson@email.com"},
            ],
            "address": [{"line": ["456 Oak Ave"], "city": "Springfield", "state": "IL", "postalCode": "62702"}],
        })
        if not p2_id:
            print("Failed to find/create Patient 2. Continuing...")
        else:
            p2_pid = _get_pid_by_name("Sarah", "Johnson")
            if not p2_pid:
                print("  WARNING: Could not find DB PID for Sarah Johnson")
            else:
                existing = _run_db_query(f"SELECT COUNT(*) as cnt FROM lists WHERE pid={p2_pid};")
                has_data = "0" not in existing if existing else False
                if has_data:
                    print("  Clinical data already exists, skipping inserts")
                else:
                    # Conditions: Asthma, Anxiety
                    print("  Conditions:")
                    _insert_condition(p2_pid, "Unspecified asthma, uncomplicated", "J45.909")
                    _insert_condition(p2_pid, "Generalized anxiety disorder", "F41.1")

                    # Medications: Albuterol, Sertraline
                    print("  Medications:")
                    _insert_medication(p2_pid, "Albuterol 0.09 MG/ACTUAT Metered Dose Inhaler", "2 puffs every 4-6 hours as needed for wheezing")
                    _insert_medication(p2_pid, "Sertraline 50 MG Oral Tablet", "Take 1 tablet daily in the morning")

                    # Allergies: Sulfa drugs, Latex
                    print("  Allergies:")
                    _insert_allergy(p2_pid, "Sulfa drugs", "high", "Severe rash and fever")
                    _insert_allergy(p2_pid, "Latex", "low", "Contact dermatitis")
        print()

        # ========== PATIENT 3: Robert Chen ==========
        print("=== Patient 3: Robert Chen ===")
        p3_id = await get_or_create_patient(client, token, {
            "resourceType": "Patient",
            "name": [{"use": "official", "family": "Chen", "given": ["Robert"]}],
            "birthDate": "1952-11-30",
            "gender": "male",
            "telecom": [
                {"system": "phone", "value": "555-0303"},
            ],
            "address": [{"line": ["789 Elm St"], "city": "Springfield", "state": "IL", "postalCode": "62703"}],
        })
        if not p3_id:
            print("Failed to find/create Patient 3. Continuing...")
        else:
            p3_pid = _get_pid_by_name("Robert", "Chen")
            if not p3_pid:
                print("  WARNING: Could not find DB PID for Robert Chen")
            else:
                existing = _run_db_query(f"SELECT COUNT(*) as cnt FROM lists WHERE pid={p3_pid};")
                has_data = "0" not in existing if existing else False
                if has_data:
                    print("  Clinical data already exists, skipping inserts")
                else:
                    # Conditions: CAD, AFib, GERD
                    print("  Conditions:")
                    _insert_condition(p3_pid, "Atherosclerotic heart disease of native coronary artery without angina pectoris", "I25.10")
                    _insert_condition(p3_pid, "Unspecified atrial fibrillation", "I48.91")
                    _insert_condition(p3_pid, "Gastro-esophageal reflux disease with esophagitis", "K21.0")

                    # Medications: Warfarin, Metoprolol, Omeprazole, Aspirin (interaction case!)
                    print("  Medications:")
                    _insert_medication(p3_pid, "Warfarin Sodium 5 MG Oral Tablet", "Take 1 tablet daily, monitor INR")
                    _insert_medication(p3_pid, "Metoprolol Tartrate 25 MG Oral Tablet", "Take 1 tablet twice daily")
                    _insert_medication(p3_pid, "Omeprazole 20 MG Delayed Release Oral Capsule", "Take 1 capsule daily before breakfast")
                    _insert_medication(p3_pid, "Aspirin 81 MG Delayed Release Oral Tablet", "Take 1 tablet daily")

                    # No allergies for Robert Chen
        print()

        # ========== PRACTITIONERS ==========
        print("=== Seeding Practitioners ===")
        await seed_practitioners(client, token)
        print()

        # Verify
        print("=== Verification ===")
        resp = await client.get(f"{FHIR_URL}/Patient", headers={"Authorization": f"Bearer {token}"})
        patients = resp.json().get("entry", [])
        print(f"Total patients in system: {len(patients)}")
        for p in patients:
            r = p.get("resource", {})
            name = r.get("name", [{}])[0]
            print(f"  - {' '.join(name.get('given', []))} {name.get('family', '')} (ID: {r.get('id', '?')})")

        resp = await client.get(f"{FHIR_URL}/Practitioner", headers={"Authorization": f"Bearer {token}"})
        practitioners = resp.json().get("entry", [])
        print(f"Total practitioners in system: {len(practitioners)}")
        for p in practitioners:
            r = p.get("resource", {})
            name = r.get("name", [{}])[0]
            print(f"  - {' '.join(name.get('given', []))} {name.get('family', '')} (ID: {r.get('id', '?')})")

        print("\nSeed data complete!")


# ========== Practitioner Seeding ==========

# Practitioners to seed with their specialties and NUCC taxonomy codes.
PRACTITIONERS = [
    {
        "given": "Sarah", "family": "Wilson",
        "npi": "1234567890",
        "phone": "555-1001", "email": "sarah.wilson@springfieldclinic.com",
        "address": {"line": ["100 Medical Center Dr"], "city": "Springfield", "state": "IL", "postalCode": "62701"},
        "specialty_code": "207Q00000X",  # Family Medicine
        "role_code": "207Q00000X",
    },
    {
        "given": "Michael", "family": "Brown",
        "npi": "1234567891",
        "phone": "555-1002", "email": "michael.brown@springfieldclinic.com",
        "address": {"line": ["100 Medical Center Dr", "Cardiology Suite 200"], "city": "Springfield", "state": "IL", "postalCode": "62701"},
        "specialty_code": "207RC0000X",  # Cardiovascular Disease
        "role_code": "207R00000X",       # Internal Medicine (parent role)
    },
    {
        "given": "Emily", "family": "Davis",
        "npi": "1234567892",
        "phone": "555-1003", "email": "emily.davis@springfieldclinic.com",
        "address": {"line": ["100 Medical Center Dr", "Dermatology Clinic"], "city": "Springfield", "state": "IL", "postalCode": "62701"},
        "specialty_code": "207N00000X",  # Dermatology
        "role_code": "207N00000X",
    },
]


async def find_practitioner(client: httpx.AsyncClient, token: str, family: str, given: str) -> Optional[str]:
    """Search for an existing practitioner by name. Returns UUID if found."""
    resp = await client.get(
        f"{FHIR_URL}/Practitioner",
        params={"family": family, "given": given},
        headers={"Authorization": f"Bearer {token}"},
    )
    if resp.status_code != 200:
        return None
    entries = resp.json().get("entry", [])
    if entries:
        pract = entries[0].get("resource", {})
        pid = pract.get("id")
        print(f"  Found existing Practitioner: {given} {family} (ID: {pid})")
        return pid
    return None


async def seed_practitioners(client: httpx.AsyncClient, token: str) -> None:
    """Seed practitioners via FHIR POST and assign specialties via DB."""
    practitioner_db_ids = []

    for pract in PRACTITIONERS:
        # Check if already exists
        existing_id = await find_practitioner(client, token, pract["family"], pract["given"])
        if existing_id:
            practitioner_db_ids.append(pract)
            continue

        # Create via FHIR
        data = {
            "resourceType": "Practitioner",
            "name": [{"use": "official", "family": pract["family"], "given": [pract["given"]]}],
            "identifier": [{
                "type": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/v2-0203", "code": "NPI"}]},
                "value": pract["npi"],
            }],
            "telecom": [
                {"system": "phone", "value": pract["phone"]},
                {"system": "email", "value": pract["email"]},
            ],
            "address": [pract["address"]],
            "active": True,
        }
        result = await create_resource(client, token, "Practitioner", data)
        if result:
            practitioner_db_ids.append(pract)

    # Assign specialties via direct DB inserts
    print("\n  Assigning specialties via DB...")
    _seed_practitioner_roles_via_db(practitioner_db_ids)


def _get_openemr_container() -> str:
    """Find the OpenEMR Docker container name."""
    global OPENEMR_CONTAINER
    if OPENEMR_CONTAINER:
        return OPENEMR_CONTAINER
    result = subprocess.run(
        ["docker", "ps", "--format", "{{.Names}}"],
        capture_output=True, text=True
    )
    for name in result.stdout.strip().split("\n"):
        if "openemr" in name.lower():
            OPENEMR_CONTAINER = name
            return name
    raise RuntimeError("OpenEMR container not found. Is Docker running?")


def _run_db_query(sql: str) -> str:
    """Execute a MariaDB query inside the OpenEMR Docker container."""
    container = _get_openemr_container()
    result = subprocess.run(
        ["docker", "exec", container, "mariadb", "-u", "openemr", "-popenemr", "openemr", "-e", sql],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"  DB Error: {result.stderr.strip()}")
    return result.stdout


def _seed_practitioner_roles_via_db(practitioners: list[dict]) -> None:
    """Insert PractitionerRole entries into facility_user_ids table.

    OpenEMR's FHIR PractitionerRole endpoint reads from facility_user_ids
    and requires 3 entries per practitioner-facility pair:
    - field_id='provider_id' (base entry)
    - field_id='role_code' (NUCC taxonomy code from us-core-provider-role list)
    - field_id='specialty_code' (NUCC taxonomy code from us-core-provider-specialty list)
    """
    for pract in practitioners:
        name = f"{pract['given']} {pract['family']}"

        # Get the DB user ID for this practitioner
        result = _run_db_query(
            f"SELECT id FROM users WHERE fname='{pract['given']}' AND lname='{pract['family']}' AND active=1 LIMIT 1;"
        )
        lines = [l for l in result.strip().split("\n") if l and l != "id"]
        if not lines:
            print(f"  WARNING: Could not find DB user ID for {name}, skipping PractitionerRole")
            continue
        user_id = lines[0].strip()

        # Assign facility_id=3 (default facility)
        _run_db_query(f"UPDATE users SET facility_id=3 WHERE id={user_id};")

        # Check if entries already exist
        check = _run_db_query(
            f"SELECT COUNT(*) as cnt FROM facility_user_ids WHERE uid={user_id} AND facility_id=3 AND field_id='provider_id';"
        )
        if "0" not in check:
            print(f"  PractitionerRole already exists for {name}")
            continue

        # Insert the 3 required entries
        _run_db_query(f"""
            INSERT INTO facility_user_ids (uid, facility_id, field_id, field_value) VALUES
            ({user_id}, 3, 'provider_id', '{user_id}'),
            ({user_id}, 3, 'role_code', '{pract["role_code"]}'),
            ({user_id}, 3, 'specialty_code', '{pract["specialty_code"]}');
        """)
        print(f"  Created PractitionerRole for {name} (specialty: {pract['specialty_code']})")


if __name__ == "__main__":
    asyncio.run(seed())
