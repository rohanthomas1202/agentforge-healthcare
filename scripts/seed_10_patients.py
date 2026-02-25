"""Seed OpenEMR with 10 additional patients via FHIR API + direct DB inserts.

Each patient has a unique clinical profile with conditions, medications, and allergies.
Patients created via FHIR POST; clinical data via direct MariaDB inserts (FHIR POST
returns 404 for Condition/MedicationRequest/AllergyIntolerance in OpenEMR).

Run: cd agentforge-healthcare && ./venv/Scripts/python.exe scripts/seed_10_patients.py
"""

import asyncio
import subprocess
from typing import Optional

import httpx


# --- Configuration ---
BASE_URL = "https://localhost:9300"
TOKEN_URL = f"{BASE_URL}/oauth2/default/token"
FHIR_URL = f"{BASE_URL}/apis/default/fhir"

CLIENT_ID = "Xkkz8itnTxUSZacmtgeVEHckBfIoZbq2Pa6mNFPGC2g"
CLIENT_SECRET = "NIs4l6mPdf3Qpz5gHo2f4NP8tDm8jQ2xTPuQBDEs4av1YRTzZvpk_L48JTwE-gUpWwlrPDciC-MU30LdjN6_CA"
USERNAME = "admin"
PASSWORD = "pass"

WRITE_SCOPES = (
    "openid api:fhir "
    "user/Patient.read user/Patient.write "
    "user/Condition.read user/MedicationRequest.read "
    "user/AllergyIntolerance.read"
)

DOCKER_CONTAINER = None  # Auto-detected


# --- Docker/DB Helpers ---

def detect_container() -> str:
    global DOCKER_CONTAINER
    if DOCKER_CONTAINER:
        return DOCKER_CONTAINER
    result = subprocess.run(
        ["docker", "ps", "--format", "{{.Names}}"],
        capture_output=True, text=True,
    )
    for name in result.stdout.strip().split("\n"):
        if "openemr" in name.lower() and "mysql" not in name.lower() and "maria" not in name.lower() and "php" not in name.lower():
            DOCKER_CONTAINER = name
            return name
    raise RuntimeError("OpenEMR container not found. Is Docker running?")


def run_db(sql: str) -> str:
    container = detect_container()
    result = subprocess.run(
        ["docker", "exec", container, "mariadb", "-u", "openemr", "-popenemr", "openemr", "-N", "-e", sql],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"    DB ERROR: {result.stderr.strip()[:200]}")
        return ""
    return result.stdout.strip()


def get_pid_by_name(fname: str, lname: str) -> Optional[str]:
    result = run_db(f"SELECT pid FROM patient_data WHERE fname='{fname}' AND lname='{lname}' LIMIT 1;")
    return result.strip() if result else None


def insert_condition(pid: str, title: str, icd_code: str):
    # Escape single quotes in title
    safe_title = title.replace("'", "\\'")
    sql = (
        f"INSERT INTO lists (date, type, title, diagnosis, activity, pid, `user`, groupname, uuid) "
        f"VALUES (NOW(), 'medical_problem', '{safe_title}', 'ICD10:{icd_code}', 1, {pid}, 'admin', 'Default', UNHEX(REPLACE(UUID(), '-', '')));"
    )
    run_db(sql)
    # Register UUID
    run_db(
        "INSERT INTO uuid_registry (uuid, table_name, table_id, created) "
        "SELECT uuid, 'lists', id, NOW() FROM lists WHERE id = (SELECT MAX(id) FROM lists);"
    )
    print(f"    Condition: {title} (ICD10:{icd_code})")


def insert_medication(pid: str, title: str, dosage: str):
    safe_title = title.replace("'", "\\'")
    safe_dosage = dosage.replace("'", "\\'")
    sql = (
        f"INSERT INTO lists (date, type, title, activity, pid, `user`, groupname, comments, uuid) "
        f"VALUES (NOW(), 'medication', '{safe_title}', 1, {pid}, 'admin', 'Default', '{safe_dosage}', UNHEX(REPLACE(UUID(), '-', '')));"
    )
    run_db(sql)
    run_db(
        "INSERT INTO uuid_registry (uuid, table_name, table_id, created) "
        "SELECT uuid, 'lists', id, NOW() FROM lists WHERE id = (SELECT MAX(id) FROM lists);"
    )
    print(f"    Medication: {title}")


def insert_allergy(pid: str, title: str, severity: str = "severe", reaction: str = ""):
    safe_title = title.replace("'", "\\'")
    safe_reaction = reaction.replace("'", "\\'")
    # severity_al values: mild, moderate, severe
    severity_map = {"high": "severe", "low": "mild", "medium": "moderate"}
    sev = severity_map.get(severity, severity)
    sql = (
        f"INSERT INTO lists (date, type, title, activity, pid, `user`, groupname, severity_al, reaction, uuid) "
        f"VALUES (NOW(), 'allergy', '{safe_title}', 1, {pid}, 'admin', 'Default', '{sev}', '{safe_reaction}', UNHEX(REPLACE(UUID(), '-', '')));"
    )
    run_db(sql)
    run_db(
        "INSERT INTO uuid_registry (uuid, table_name, table_id, created) "
        "SELECT uuid, 'lists', id, NOW() FROM lists WHERE id = (SELECT MAX(id) FROM lists);"
    )
    print(f"    Allergy: {title} (severity: {sev})")


# --- FHIR Patient Creation ---

async def get_token(client: httpx.AsyncClient) -> str:
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


async def find_patient(client: httpx.AsyncClient, token: str, family: str, given: str) -> Optional[str]:
    resp = await client.get(
        f"{FHIR_URL}/Patient",
        params={"family": family, "given": given},
        headers={"Authorization": f"Bearer {token}"},
    )
    if resp.status_code != 200:
        return None
    entries = resp.json().get("entry", [])
    if entries:
        pid = entries[0].get("resource", {}).get("id")
        print(f"    Found existing: {given} {family} (UUID: {pid})")
        return pid
    return None


async def get_or_create_patient(client: httpx.AsyncClient, token: str, data: dict) -> Optional[str]:
    name = data.get("name", [{}])[0]
    family = name.get("family", "")
    given = name.get("given", [""])[0]

    existing = await find_patient(client, token, family, given)
    if existing:
        return existing

    resp = await client.post(
        f"{FHIR_URL}/Patient",
        json=data,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/fhir+json",
        },
    )
    if resp.status_code >= 400:
        print(f"    ERROR creating Patient: {resp.status_code} {resp.text[:200]}")
        return None
    result = resp.json()
    uuid = result.get("uuid") or result.get("id")
    print(f"    Created Patient/{uuid}")
    return uuid


# ============================================================
# 10 NEW PATIENTS — each with unique clinical profiles
# ============================================================

PATIENTS = [
    {
        "info": {
            "resourceType": "Patient",
            "name": [{"use": "official", "family": "Martinez", "given": ["Maria"]}],
            "birthDate": "1988-07-12",
            "gender": "female",
            "telecom": [
                {"system": "phone", "value": "555-0401"},
                {"system": "email", "value": "maria.martinez@email.com"},
            ],
            "address": [{"line": ["410 Cedar Lane"], "city": "Springfield", "state": "IL", "postalCode": "62704"}],
        },
        "conditions": [
            ("J45.20", "Mild intermittent asthma, uncomplicated"),
            ("E03.9", "Hypothyroidism, unspecified"),
        ],
        "medications": [
            ("Albuterol 0.09 MG/ACTUAT Metered Dose Inhaler", "2 puffs every 4-6 hours as needed"),
            ("Levothyroxine Sodium 50 MCG Oral Tablet", "Take 1 tablet daily on empty stomach"),
        ],
        "allergies": [
            ("Amoxicillin", "high", "Rash and hives"),
        ],
    },
    {
        "info": {
            "resourceType": "Patient",
            "name": [{"use": "official", "family": "Williams", "given": ["James"]}],
            "birthDate": "1955-01-20",
            "gender": "male",
            "telecom": [
                {"system": "phone", "value": "555-0402"},
                {"system": "email", "value": "james.williams@email.com"},
            ],
            "address": [{"line": ["822 Oak Ridge Dr"], "city": "Springfield", "state": "IL", "postalCode": "62705"}],
        },
        "conditions": [
            ("I50.9", "Heart failure, unspecified"),
            ("E11.65", "Type 2 diabetes mellitus with hyperglycemia"),
            ("N18.3", "Chronic kidney disease, stage 3"),
        ],
        "medications": [
            ("Furosemide 40 MG Oral Tablet", "Take 1 tablet daily in the morning"),
            ("Metformin 500 MG Oral Tablet", "Take 1 tablet twice daily with meals"),
            ("Lisinopril 10 MG Oral Tablet", "Take 1 tablet daily"),
            ("Carvedilol 12.5 MG Oral Tablet", "Take 1 tablet twice daily"),
        ],
        "allergies": [
            ("Iodine contrast dye", "high", "Anaphylaxis"),
            ("Shellfish", "low", "Mild stomach upset"),
        ],
    },
    {
        "info": {
            "resourceType": "Patient",
            "name": [{"use": "official", "family": "Patel", "given": ["Priya"]}],
            "birthDate": "1992-11-05",
            "gender": "female",
            "telecom": [
                {"system": "phone", "value": "555-0403"},
                {"system": "email", "value": "priya.patel@email.com"},
            ],
            "address": [{"line": ["156 Birch St"], "city": "Springfield", "state": "IL", "postalCode": "62706"}],
        },
        "conditions": [
            ("G43.909", "Migraine, unspecified, not intractable"),
            ("F32.1", "Major depressive disorder, single episode, moderate"),
        ],
        "medications": [
            ("Sumatriptan 50 MG Oral Tablet", "Take 1 tablet at onset of migraine, may repeat after 2 hours"),
            ("Sertraline 50 MG Oral Tablet", "Take 1 tablet daily in the morning"),
            ("Topiramate 25 MG Oral Tablet", "Take 1 tablet daily for migraine prevention"),
        ],
        "allergies": [
            ("Penicillin", "high", "Anaphylaxis"),
            ("Peanuts", "high", "Throat swelling"),
        ],
    },
    {
        "info": {
            "resourceType": "Patient",
            "name": [{"use": "official", "family": "Thompson", "given": ["David"]}],
            "birthDate": "1970-09-28",
            "gender": "male",
            "telecom": [
                {"system": "phone", "value": "555-0404"},
                {"system": "email", "value": "david.thompson@email.com"},
            ],
            "address": [{"line": ["789 Walnut Ave"], "city": "Springfield", "state": "IL", "postalCode": "62707"}],
        },
        "conditions": [
            ("M54.5", "Low back pain"),
            ("G47.33", "Obstructive sleep apnea"),
            ("E78.5", "Hyperlipidemia, unspecified"),
        ],
        "medications": [
            ("Naproxen 500 MG Oral Tablet", "Take 1 tablet twice daily with food as needed for pain"),
            ("Cyclobenzaprine 10 MG Oral Tablet", "Take 1 tablet at bedtime as needed for muscle spasm"),
            ("Atorvastatin 20 MG Oral Tablet", "Take 1 tablet daily at bedtime"),
        ],
        "allergies": [
            ("Codeine", "high", "Severe nausea and vomiting"),
        ],
    },
    {
        "info": {
            "resourceType": "Patient",
            "name": [{"use": "official", "family": "Kim", "given": ["Susan"]}],
            "birthDate": "1960-04-15",
            "gender": "female",
            "telecom": [
                {"system": "phone", "value": "555-0405"},
                {"system": "email", "value": "susan.kim@email.com"},
            ],
            "address": [{"line": ["234 Maple Court"], "city": "Springfield", "state": "IL", "postalCode": "62708"}],
        },
        "conditions": [
            ("M81.0", "Age-related osteoporosis without current pathological fracture"),
            ("M17.11", "Primary osteoarthritis, right knee"),
            ("I10", "Essential hypertension"),
        ],
        "medications": [
            ("Alendronate Sodium 70 MG Oral Tablet", "Take 1 tablet weekly on empty stomach with full glass of water"),
            ("Acetaminophen 500 MG Oral Tablet", "Take 1-2 tablets every 6 hours as needed for pain"),
            ("Amlodipine 5 MG Oral Tablet", "Take 1 tablet daily"),
            ("Calcium Carbonate 500 MG / Vitamin D3 200 UNT Oral Tablet", "Take 1 tablet twice daily with meals"),
        ],
        "allergies": [
            ("NSAIDs", "high", "GI bleeding"),
            ("Latex", "low", "Contact dermatitis"),
        ],
    },
    {
        "info": {
            "resourceType": "Patient",
            "name": [{"use": "official", "family": "Anderson", "given": ["Michael"]}],
            "birthDate": "1948-12-03",
            "gender": "male",
            "telecom": [
                {"system": "phone", "value": "555-0406"},
                {"system": "email", "value": "michael.anderson@email.com"},
            ],
            "address": [{"line": ["567 Elm Boulevard"], "city": "Springfield", "state": "IL", "postalCode": "62709"}],
        },
        "conditions": [
            ("J44.1", "Chronic obstructive pulmonary disease with acute exacerbation"),
            ("I25.10", "Atherosclerotic heart disease of native coronary artery"),
            ("E11.9", "Type 2 diabetes mellitus without complications"),
            ("I10", "Essential hypertension"),
        ],
        "medications": [
            ("Tiotropium Bromide Inhalation Spray", "Inhale 2 puffs once daily"),
            ("Albuterol 0.09 MG/ACTUAT Metered Dose Inhaler", "2 puffs every 4-6 hours as needed"),
            ("Metformin 500 MG Oral Tablet", "Take 1 tablet twice daily"),
            ("Aspirin 81 MG Delayed Release Oral Tablet", "Take 1 tablet daily"),
            ("Lisinopril 10 MG Oral Tablet", "Take 1 tablet daily"),
        ],
        "allergies": [
            ("Sulfa drugs", "high", "Severe rash and fever"),
        ],
    },
    {
        "info": {
            "resourceType": "Patient",
            "name": [{"use": "official", "family": "Rodriguez", "given": ["Elena"]}],
            "birthDate": "1985-06-18",
            "gender": "female",
            "telecom": [
                {"system": "phone", "value": "555-0407"},
                {"system": "email", "value": "elena.rodriguez@email.com"},
            ],
            "address": [{"line": ["901 Willow Way"], "city": "Springfield", "state": "IL", "postalCode": "62710"}],
        },
        "conditions": [
            ("O09.513", "Supervision of elderly multigravida, third trimester"),
            ("O24.419", "Gestational diabetes mellitus in pregnancy"),
            ("D50.9", "Iron deficiency anemia, unspecified"),
        ],
        "medications": [
            ("Prenatal Vitamins Oral Tablet", "Take 1 tablet daily"),
            ("Ferrous Sulfate 325 MG Oral Tablet", "Take 1 tablet daily with vitamin C"),
            ("Insulin Lispro 100 UNT/ML Injectable Solution", "Inject as directed before meals per sliding scale"),
        ],
        "allergies": [
            ("Erythromycin", "low", "Mild nausea"),
        ],
    },
    {
        "info": {
            "resourceType": "Patient",
            "name": [{"use": "official", "family": "Nguyen", "given": ["Kevin"]}],
            "birthDate": "1999-02-14",
            "gender": "male",
            "telecom": [
                {"system": "phone", "value": "555-0408"},
                {"system": "email", "value": "kevin.nguyen@email.com"},
            ],
            "address": [{"line": ["345 Spruce Lane"], "city": "Springfield", "state": "IL", "postalCode": "62711"}],
        },
        "conditions": [
            ("F90.2", "Attention-deficit hyperactivity disorder, combined type"),
            ("L20.9", "Atopic dermatitis, unspecified"),
        ],
        "medications": [
            ("Methylphenidate Hydrochloride 20 MG Extended Release Oral Tablet", "Take 1 tablet daily in the morning"),
            ("Triamcinolone Acetonide 0.1% Topical Cream", "Apply thin layer to affected areas twice daily"),
            ("Cetirizine 10 MG Oral Tablet", "Take 1 tablet daily for itching"),
        ],
        "allergies": [
            ("Dust mites", "low", "Sneezing and nasal congestion"),
            ("Cat dander", "low", "Itchy eyes and sneezing"),
        ],
    },
    {
        "info": {
            "resourceType": "Patient",
            "name": [{"use": "official", "family": "Brown", "given": ["Linda"]}],
            "birthDate": "1973-08-07",
            "gender": "female",
            "telecom": [
                {"system": "phone", "value": "555-0409"},
                {"system": "email", "value": "linda.brown@email.com"},
            ],
            "address": [{"line": ["678 Pine Ridge Rd"], "city": "Springfield", "state": "IL", "postalCode": "62712"}],
        },
        "conditions": [
            ("M06.9", "Rheumatoid arthritis, unspecified"),
            ("K21.0", "Gastro-esophageal reflux disease with esophagitis"),
            ("F41.1", "Generalized anxiety disorder"),
        ],
        "medications": [
            ("Methotrexate 2.5 MG Oral Tablet", "Take 3 tablets once weekly on the same day"),
            ("Folic Acid 1 MG Oral Tablet", "Take 1 tablet daily except methotrexate day"),
            ("Omeprazole 20 MG Delayed Release Oral Capsule", "Take 1 capsule daily before breakfast"),
            ("Sertraline 50 MG Oral Tablet", "Take 1 tablet daily in the morning"),
        ],
        "allergies": [
            ("Penicillin", "high", "Hives and swelling"),
            ("Aspirin", "high", "Bronchospasm"),
        ],
    },
    {
        "info": {
            "resourceType": "Patient",
            "name": [{"use": "official", "family": "Jackson", "given": ["Thomas"]}],
            "birthDate": "1942-03-22",
            "gender": "male",
            "telecom": [
                {"system": "phone", "value": "555-0410"},
                {"system": "email", "value": "thomas.jackson@email.com"},
            ],
            "address": [{"line": ["1200 Heritage Dr"], "city": "Springfield", "state": "IL", "postalCode": "62713"}],
        },
        "conditions": [
            ("G30.9", "Alzheimer disease, unspecified"),
            ("I48.91", "Unspecified atrial fibrillation"),
            ("I10", "Essential hypertension"),
            ("E78.0", "Pure hypercholesterolemia"),
        ],
        "medications": [
            ("Donepezil Hydrochloride 10 MG Oral Tablet", "Take 1 tablet daily at bedtime"),
            ("Warfarin Sodium 5 MG Oral Tablet", "Take 1 tablet daily, monitor INR regularly"),
            ("Amlodipine 5 MG Oral Tablet", "Take 1 tablet daily"),
            ("Rosuvastatin 10 MG Oral Tablet", "Take 1 tablet daily at bedtime"),
            ("Metoprolol Tartrate 25 MG Oral Tablet", "Take 1 tablet twice daily"),
        ],
        "allergies": [
            ("Amoxicillin", "high", "Severe rash"),
            ("Eggs", "low", "Mild GI upset"),
        ],
    },
]


async def seed_patient(client: httpx.AsyncClient, token: str, patient_data: dict, index: int) -> bool:
    """Seed a single patient with all their clinical data."""
    name = patient_data["info"]["name"][0]
    fname = name["given"][0]
    lname = name["family"]
    full_name = f"{fname} {lname}"

    print(f"\n{'='*50}")
    print(f"  Patient {index}: {full_name}")
    print(f"{'='*50}")

    # Create patient via FHIR (or find existing)
    uuid = await get_or_create_patient(client, token, patient_data["info"])
    if not uuid:
        print(f"  FAILED to create {full_name}")
        return False

    # Get the integer PID from the DB (needed for lists table inserts)
    pid = get_pid_by_name(fname, lname)
    if not pid:
        print(f"  WARNING: Could not find PID for {full_name} in DB")
        return False
    print(f"    PID: {pid}")

    # Check if clinical data already exists for this patient
    existing = run_db(f"SELECT COUNT(*) FROM lists WHERE pid={pid};")
    if existing and int(existing) > 0:
        print(f"    Clinical data already exists ({existing} records), skipping inserts")
        return True

    # Insert conditions via DB
    print("  Conditions:")
    for icd_code, display in patient_data.get("conditions", []):
        insert_condition(pid, display, icd_code)

    # Insert medications via DB
    print("  Medications:")
    for title, dosage in patient_data.get("medications", []):
        insert_medication(pid, title, dosage)

    # Insert allergies via DB
    print("  Allergies:")
    for allergy_data in patient_data.get("allergies", []):
        title, severity, reaction = allergy_data
        insert_allergy(pid, title, severity, reaction)

    return True


async def seed():
    """Main seeding function."""
    print(f"Using Docker container: {detect_container()}\n")

    async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
        print("Getting OAuth token...")
        token = await get_token(client)
        print("Token obtained.\n")

        success_count = 0
        for i, patient_data in enumerate(PATIENTS, start=1):
            ok = await seed_patient(client, token, patient_data, i)
            if ok:
                success_count += 1

        # Verification
        print(f"\n{'='*50}")
        print("VERIFICATION")
        print(f"{'='*50}")

        resp = await client.get(
            f"{FHIR_URL}/Patient",
            headers={"Authorization": f"Bearer {token}"},
        )
        if resp.status_code == 200:
            entries = resp.json().get("entry", [])
            print(f"\nTotal patients in OpenEMR: {len(entries)}")
            for e in entries:
                r = e.get("resource", {})
                names = r.get("name", [{}])
                if names:
                    n = names[0]
                    given = " ".join(n.get("given", []))
                    family = n.get("family", "")
                    print(f"  - {given} {family} (UUID: {r.get('id', '?')})")

        # Verify clinical data counts
        print(f"\nClinical data summary:")
        for patient_data in PATIENTS:
            name = patient_data["info"]["name"][0]
            fname = name["given"][0]
            lname = name["family"]
            pid = get_pid_by_name(fname, lname)
            if pid:
                count = run_db(f"SELECT COUNT(*) FROM lists WHERE pid={pid};")
                print(f"  {fname} {lname} (pid={pid}): {count} records")

        print(f"\nSuccessfully seeded {success_count}/10 patients with clinical data.")
        print("Done!")


if __name__ == "__main__":
    asyncio.run(seed())
