"""Seed OpenEMR with test data via FHIR API + direct DB inserts.

Creates 3 test patients with conditions, medications, and allergies,
plus 3 practitioners with specialties (via PractitionerRole DB inserts).

Run: cd agentforge-healthcare && ./venv/Scripts/python.exe scripts/seed_data.py
"""

import asyncio
import subprocess
import time
from typing import Optional

import httpx


# --- Configuration ---
BASE_URL = "https://localhost:9300"
TOKEN_URL = f"{BASE_URL}/oauth2/default/token"
FHIR_URL = f"{BASE_URL}/apis/default/fhir"

# From .env / memory
CLIENT_ID = "Xkkz8itnTxUSZacmtgeVEHckBfIoZbq2Pa6mNFPGC2g"
CLIENT_SECRET = "NIs4l6mPdf3Qpz5gHo2f4NP8tDm8jQ2xTPuQBDEs4av1YRTzZvpk_L48JTwE-gUpWwlrPDciC-MU30LdjN6_CA"
USERNAME = "admin"
PASSWORD = "pass"

# Write scopes for seeding
WRITE_SCOPES = (
    "openid api:fhir "
    "user/Patient.read user/Patient.write "
    "user/Condition.read user/Condition.write "
    "user/MedicationRequest.read user/MedicationRequest.write "
    "user/AllergyIntolerance.read user/AllergyIntolerance.write "
    "user/Immunization.read user/Immunization.write "
    "user/Observation.read user/Observation.write "
    "user/Encounter.read user/Encounter.write "
    "user/Practitioner.read user/Practitioner.write "
    "user/Organization.read"
)

# Docker container name for OpenEMR (used for DB inserts)
OPENEMR_CONTAINER = None  # Auto-detected


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

        # Conditions: Type 2 Diabetes, Hypertension
        await create_resource(client, token, "Condition", {
            "resourceType": "Condition",
            "subject": {"reference": f"Patient/{p1_id}"},
            "code": {"coding": [{"system": "http://hl7.org/fhir/sid/icd-10-cm", "code": "E11.9", "display": "Type 2 diabetes mellitus without complications"}]},
            "clinicalStatus": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/condition-clinical", "code": "active"}]},
            "verificationStatus": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/condition-ver-status", "code": "confirmed"}]},
        })
        await create_resource(client, token, "Condition", {
            "resourceType": "Condition",
            "subject": {"reference": f"Patient/{p1_id}"},
            "code": {"coding": [{"system": "http://hl7.org/fhir/sid/icd-10-cm", "code": "I10", "display": "Essential hypertension"}]},
            "clinicalStatus": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/condition-clinical", "code": "active"}]},
            "verificationStatus": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/condition-ver-status", "code": "confirmed"}]},
        })

        # Medications: Metformin, Lisinopril, Atorvastatin
        await create_resource(client, token, "MedicationRequest", {
            "resourceType": "MedicationRequest",
            "status": "active",
            "intent": "order",
            "subject": {"reference": f"Patient/{p1_id}"},
            "medicationCodeableConcept": {"coding": [{"system": "http://www.nlm.nih.gov/research/umls/rxnorm", "code": "860975", "display": "Metformin 500 MG Oral Tablet"}], "text": "Metformin 500mg"},
            "dosageInstruction": [{"text": "Take 1 tablet twice daily with meals"}],
        })
        await create_resource(client, token, "MedicationRequest", {
            "resourceType": "MedicationRequest",
            "status": "active",
            "intent": "order",
            "subject": {"reference": f"Patient/{p1_id}"},
            "medicationCodeableConcept": {"coding": [{"system": "http://www.nlm.nih.gov/research/umls/rxnorm", "code": "314076", "display": "Lisinopril 10 MG Oral Tablet"}], "text": "Lisinopril 10mg"},
            "dosageInstruction": [{"text": "Take 1 tablet daily in the morning"}],
        })
        await create_resource(client, token, "MedicationRequest", {
            "resourceType": "MedicationRequest",
            "status": "active",
            "intent": "order",
            "subject": {"reference": f"Patient/{p1_id}"},
            "medicationCodeableConcept": {"coding": [{"system": "http://www.nlm.nih.gov/research/umls/rxnorm", "code": "259255", "display": "Atorvastatin 20 MG Oral Tablet"}], "text": "Atorvastatin 20mg"},
            "dosageInstruction": [{"text": "Take 1 tablet daily at bedtime"}],
        })

        # Allergy: Penicillin
        await create_resource(client, token, "AllergyIntolerance", {
            "resourceType": "AllergyIntolerance",
            "patient": {"reference": f"Patient/{p1_id}"},
            "code": {"coding": [{"system": "http://www.nlm.nih.gov/research/umls/rxnorm", "code": "7980", "display": "Penicillin"}], "text": "Penicillin"},
            "type": "allergy",
            "category": ["medication"],
            "criticality": "high",
            "clinicalStatus": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/allergyintolerance-clinical", "code": "active"}]},
        })
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
            # Conditions: Asthma, Anxiety
            await create_resource(client, token, "Condition", {
                "resourceType": "Condition",
                "subject": {"reference": f"Patient/{p2_id}"},
                "code": {"coding": [{"system": "http://hl7.org/fhir/sid/icd-10-cm", "code": "J45.909", "display": "Unspecified asthma, uncomplicated"}]},
                "clinicalStatus": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/condition-clinical", "code": "active"}]},
                "verificationStatus": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/condition-ver-status", "code": "confirmed"}]},
            })
            await create_resource(client, token, "Condition", {
                "resourceType": "Condition",
                "subject": {"reference": f"Patient/{p2_id}"},
                "code": {"coding": [{"system": "http://hl7.org/fhir/sid/icd-10-cm", "code": "F41.1", "display": "Generalized anxiety disorder"}]},
                "clinicalStatus": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/condition-clinical", "code": "active"}]},
                "verificationStatus": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/condition-ver-status", "code": "confirmed"}]},
            })

            # Medications: Albuterol, Sertraline
            await create_resource(client, token, "MedicationRequest", {
                "resourceType": "MedicationRequest",
                "status": "active",
                "intent": "order",
                "subject": {"reference": f"Patient/{p2_id}"},
                "medicationCodeableConcept": {"coding": [{"system": "http://www.nlm.nih.gov/research/umls/rxnorm", "code": "245314", "display": "Albuterol 0.09 MG/ACTUAT Metered Dose Inhaler"}], "text": "Albuterol Inhaler"},
                "dosageInstruction": [{"text": "2 puffs every 4-6 hours as needed for wheezing"}],
            })
            await create_resource(client, token, "MedicationRequest", {
                "resourceType": "MedicationRequest",
                "status": "active",
                "intent": "order",
                "subject": {"reference": f"Patient/{p2_id}"},
                "medicationCodeableConcept": {"coding": [{"system": "http://www.nlm.nih.gov/research/umls/rxnorm", "code": "312938", "display": "Sertraline 50 MG Oral Tablet"}], "text": "Sertraline 50mg"},
                "dosageInstruction": [{"text": "Take 1 tablet daily in the morning"}],
            })

            # Allergies: Sulfa drugs, Latex
            await create_resource(client, token, "AllergyIntolerance", {
                "resourceType": "AllergyIntolerance",
                "patient": {"reference": f"Patient/{p2_id}"},
                "code": {"coding": [{"system": "http://www.nlm.nih.gov/research/umls/rxnorm", "code": "10831", "display": "Sulfamethoxazole"}], "text": "Sulfa drugs"},
                "type": "allergy",
                "category": ["medication"],
                "criticality": "high",
                "clinicalStatus": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/allergyintolerance-clinical", "code": "active"}]},
            })
            await create_resource(client, token, "AllergyIntolerance", {
                "resourceType": "AllergyIntolerance",
                "patient": {"reference": f"Patient/{p2_id}"},
                "code": {"text": "Latex"},
                "type": "allergy",
                "category": ["environment"],
                "criticality": "low",
                "clinicalStatus": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/allergyintolerance-clinical", "code": "active"}]},
            })
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
            # Conditions: CAD, AFib, GERD
            await create_resource(client, token, "Condition", {
                "resourceType": "Condition",
                "subject": {"reference": f"Patient/{p3_id}"},
                "code": {"coding": [{"system": "http://hl7.org/fhir/sid/icd-10-cm", "code": "I25.10", "display": "Atherosclerotic heart disease of native coronary artery without angina pectoris"}]},
                "clinicalStatus": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/condition-clinical", "code": "active"}]},
                "verificationStatus": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/condition-ver-status", "code": "confirmed"}]},
            })
            await create_resource(client, token, "Condition", {
                "resourceType": "Condition",
                "subject": {"reference": f"Patient/{p3_id}"},
                "code": {"coding": [{"system": "http://hl7.org/fhir/sid/icd-10-cm", "code": "I48.91", "display": "Unspecified atrial fibrillation"}]},
                "clinicalStatus": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/condition-clinical", "code": "active"}]},
                "verificationStatus": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/condition-ver-status", "code": "confirmed"}]},
            })
            await create_resource(client, token, "Condition", {
                "resourceType": "Condition",
                "subject": {"reference": f"Patient/{p3_id}"},
                "code": {"coding": [{"system": "http://hl7.org/fhir/sid/icd-10-cm", "code": "K21.0", "display": "Gastro-esophageal reflux disease with esophagitis"}]},
                "clinicalStatus": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/condition-clinical", "code": "active"}]},
                "verificationStatus": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/condition-ver-status", "code": "confirmed"}]},
            })

            # Medications: Warfarin, Metoprolol, Omeprazole, Aspirin (interaction case!)
            await create_resource(client, token, "MedicationRequest", {
                "resourceType": "MedicationRequest",
                "status": "active",
                "intent": "order",
                "subject": {"reference": f"Patient/{p3_id}"},
                "medicationCodeableConcept": {"coding": [{"system": "http://www.nlm.nih.gov/research/umls/rxnorm", "code": "855288", "display": "Warfarin Sodium 5 MG Oral Tablet"}], "text": "Warfarin 5mg"},
                "dosageInstruction": [{"text": "Take 1 tablet daily, monitor INR"}],
            })
            await create_resource(client, token, "MedicationRequest", {
                "resourceType": "MedicationRequest",
                "status": "active",
                "intent": "order",
                "subject": {"reference": f"Patient/{p3_id}"},
                "medicationCodeableConcept": {"coding": [{"system": "http://www.nlm.nih.gov/research/umls/rxnorm", "code": "866924", "display": "Metoprolol Tartrate 25 MG Oral Tablet"}], "text": "Metoprolol 25mg"},
                "dosageInstruction": [{"text": "Take 1 tablet twice daily"}],
            })
            await create_resource(client, token, "MedicationRequest", {
                "resourceType": "MedicationRequest",
                "status": "active",
                "intent": "order",
                "subject": {"reference": f"Patient/{p3_id}"},
                "medicationCodeableConcept": {"coding": [{"system": "http://www.nlm.nih.gov/research/umls/rxnorm", "code": "198053", "display": "Omeprazole 20 MG Delayed Release Oral Capsule"}], "text": "Omeprazole 20mg"},
                "dosageInstruction": [{"text": "Take 1 capsule daily before breakfast"}],
            })
            await create_resource(client, token, "MedicationRequest", {
                "resourceType": "MedicationRequest",
                "status": "active",
                "intent": "order",
                "subject": {"reference": f"Patient/{p3_id}"},
                "medicationCodeableConcept": {"coding": [{"system": "http://www.nlm.nih.gov/research/umls/rxnorm", "code": "318272", "display": "Aspirin 81 MG Delayed Release Oral Tablet"}], "text": "Aspirin 81mg"},
                "dosageInstruction": [{"text": "Take 1 tablet daily"}],
            })
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
