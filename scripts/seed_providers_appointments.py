"""Seed OpenEMR with provider and appointment data for Phase 4 testing.

Creates:
- 3 healthcare providers (Practitioners) with specialties
- ~10 appointments across providers and patients (mix of past/future, booked/completed)

Practitioners are created via FHIR POST, specialties + appointments via direct DB.

Run: cd agentforge-healthcare && ./venv/Scripts/python.exe scripts/seed_providers_appointments.py
"""

import asyncio
import subprocess
from datetime import datetime, timedelta

import httpx

# --- Configuration (same creds as seed_data.py) ---
BASE_URL = "https://localhost:9300"
TOKEN_URL = f"{BASE_URL}/oauth2/default/token"
FHIR_URL = f"{BASE_URL}/apis/default/fhir"

CLIENT_ID = "Xkkz8itnTxUSZacmtgeVEHckBfIoZbq2Pa6mNFPGC2g"
CLIENT_SECRET = "NIs4l6mPdf3Qpz5gHo2f4NP8tDm8jQ2xTPuQBDEs4av1YRTzZvpk_L48JTwE-gUpWwlrPDciC-MU30LdjN6_CA"
USERNAME = "admin"
PASSWORD = "pass"

WRITE_SCOPES = (
    "openid api:fhir "
    "user/Practitioner.read user/Practitioner.write "
    "user/Appointment.read user/Patient.read "
    "user/Organization.read user/Location.read"
)


# --- Helpers ---


def detect_container():
    """Auto-detect the OpenEMR docker container name."""
    result = subprocess.run(
        ["docker", "ps", "--filter", "name=openemr", "--format", "{{.Names}}"],
        capture_output=True, text=True,
    )
    names = [n.strip() for n in result.stdout.strip().split("\n") if n.strip()]
    # Prefer the main openemr container (not mysql/phpmyadmin/etc.)
    for name in names:
        if "openemr" in name.lower() and "mysql" not in name.lower() and "maria" not in name.lower() and "php" not in name.lower():
            return name
    return names[0] if names else "openemr-dev-openemr-1"


DOCKER_CONTAINER = detect_container()


def run_db(sql: str) -> str:
    """Execute SQL in the OpenEMR MariaDB via docker exec."""
    cmd = [
        "docker", "exec", DOCKER_CONTAINER,
        "mariadb", "-u", "openemr", "-popenemr", "openemr",
        "-N", "-e", sql,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  DB ERROR: {result.stderr.strip()[:200]}")
        return ""
    return result.stdout.strip()


async def get_token(client: httpx.AsyncClient) -> str:
    """Get OAuth2 access token."""
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


async def find_practitioner(client, token, family, given):
    """Search for an existing practitioner by name. Returns UUID or None."""
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
        uuid = pract.get("id")
        print(f"  Found existing: {given} {family} (UUID: {uuid})")
        return uuid
    return None


async def create_practitioner(client, token, data):
    """Create a practitioner via FHIR POST. Returns UUID."""
    resp = await client.post(
        f"{FHIR_URL}/Practitioner",
        json=data,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/fhir+json",
        },
    )
    if resp.status_code >= 400:
        print(f"  ERROR: {resp.status_code} {resp.text[:200]}")
        return None
    result = resp.json()
    uuid = result.get("uuid") or result.get("id")
    name_data = data.get("name", [{}])[0]
    print(f"  Created: {' '.join(name_data.get('given', []))} {name_data.get('family', '')} (UUID: {uuid})")
    return uuid


async def get_or_create_practitioner(client, token, data):
    """Find or create a practitioner. Returns UUID."""
    name = data.get("name", [{}])[0]
    family = name.get("family", "")
    given = name.get("given", [""])[0]
    existing = await find_practitioner(client, token, family, given)
    if existing:
        return existing
    return await create_practitioner(client, token, data)


def get_user_id_by_uuid(uuid: str) -> str:
    """Look up integer user ID from UUID. Returns empty string on failure."""
    result = run_db(
        f"SELECT id FROM users WHERE uuid = UNHEX(REPLACE('{uuid}', '-', ''));"
    )
    return result.strip() if result else ""


def update_user_fields(user_id: str, specialty: str, npi: str):
    """Set specialty, NPI, and provider flags on a user record."""
    run_db(
        f"UPDATE users SET specialty='{specialty}', npi='{npi}', "
        f"authorized=1, active=1, cal_ui=1 WHERE id={user_id};"
    )
    print(f"  Updated user {user_id}: specialty='{specialty}', npi='{npi}'")


def seed_appointment(
    provider_id: str, patient_pid: str, event_date: str,
    start_time: str, end_time: str, title: str = "Office Visit",
    status: str = "+", catid: int = 5, comment: str = "",
):
    """Insert an appointment + uuid_registry entry via DB.

    Note: table uses 'uuid' (not 'pc_uuid'), and pc_multiple + pc_endDate are required.
    """
    # Step 1: Insert the appointment row with an inline-generated UUID
    insert_sql = (
        f"INSERT INTO openemr_postcalendar_events "
        f"(pc_catid, pc_multiple, pc_pid, pc_aid, pc_title, "
        f"pc_eventDate, pc_endDate, pc_startTime, pc_endTime, "
        f"pc_apptstatus, pc_facility, pc_hometext, uuid, pc_time, "
        f"pc_eventstatus, pc_sharing) "
        f"VALUES ({catid}, 0, {patient_pid}, {provider_id}, '{title}', "
        f"'{event_date}', '{event_date}', '{start_time}', '{end_time}', "
        f"'{status}', 3, '{comment}', "
        f"UNHEX(REPLACE(UUID(), '-', '')), NOW(), 1, 1);"
    )
    run_db(insert_sql)

    # Step 2: Register the UUID in uuid_registry (needed for FHIR API access)
    registry_sql = (
        "INSERT INTO uuid_registry (uuid, table_name, table_id, created) "
        "SELECT uuid, 'openemr_postcalendar_events', pc_eid, NOW() "
        "FROM openemr_postcalendar_events "
        "WHERE pc_eid = (SELECT MAX(pc_eid) FROM openemr_postcalendar_events);"
    )
    run_db(registry_sql)

    print(f"  Appointment: {event_date} {start_time}-{end_time} provider={provider_id} patient={patient_pid}")


async def seed():
    """Main seeding function."""
    print(f"Using Docker container: {DOCKER_CONTAINER}\n")

    async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
        print("Getting OAuth token...")
        token = await get_token(client)
        print("Token obtained.\n")

        # ============================================================
        # PRACTITIONERS
        # ============================================================

        print("=" * 50)
        print("CREATING PRACTITIONERS")
        print("=" * 50)

        # NPI identifier template for FHIR Practitioner
        def _npi_identifier(npi_value):
            return [{
                "system": "http://hl7.org/fhir/sid/us-npi",
                "type": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/v2-0203", "code": "NPI"}]},
                "value": npi_value,
            }]

        # Provider 1: Dr. Sarah Wilson — Family Practice
        print("\n--- Dr. Sarah Wilson (Family Practice) ---")
        wilson_uuid = await get_or_create_practitioner(client, token, {
            "resourceType": "Practitioner",
            "active": True,
            "identifier": _npi_identifier("1234567890"),
            "name": [{"use": "official", "family": "Wilson", "given": ["Sarah"], "prefix": ["Dr."]}],
            "telecom": [
                {"system": "phone", "value": "555-1001", "use": "work"},
                {"system": "email", "value": "sarah.wilson@springfieldclinic.com"},
            ],
            "address": [{
                "line": ["100 Medical Center Dr"],
                "city": "Springfield", "state": "IL", "postalCode": "62701",
            }],
        })

        # Provider 2: Dr. Michael Brown — Cardiology
        print("\n--- Dr. Michael Brown (Cardiology) ---")
        brown_uuid = await get_or_create_practitioner(client, token, {
            "resourceType": "Practitioner",
            "active": True,
            "identifier": _npi_identifier("1234567891"),
            "name": [{"use": "official", "family": "Brown", "given": ["Michael"], "prefix": ["Dr."]}],
            "telecom": [
                {"system": "phone", "value": "555-1002", "use": "work"},
                {"system": "email", "value": "michael.brown@springfieldclinic.com"},
            ],
            "address": [{
                "line": ["100 Medical Center Dr", "Cardiology Suite 200"],
                "city": "Springfield", "state": "IL", "postalCode": "62701",
            }],
        })

        # Provider 3: Dr. Emily Davis — Dermatology
        print("\n--- Dr. Emily Davis (Dermatology) ---")
        davis_uuid = await get_or_create_practitioner(client, token, {
            "resourceType": "Practitioner",
            "active": True,
            "identifier": _npi_identifier("1234567892"),
            "name": [{"use": "official", "family": "Davis", "given": ["Emily"], "prefix": ["Dr."]}],
            "telecom": [
                {"system": "phone", "value": "555-1003", "use": "work"},
                {"system": "email", "value": "emily.davis@springfieldclinic.com"},
            ],
            "address": [{
                "line": ["200 Skin Care Blvd"],
                "city": "Springfield", "state": "IL", "postalCode": "62702",
            }],
        })

        # ============================================================
        # SET SPECIALTIES VIA DB
        # ============================================================

        print("\n" + "=" * 50)
        print("SETTING SPECIALTIES + NPI VIA DB")
        print("=" * 50)

        providers = {}  # key -> integer user ID

        for uuid, key, specialty, npi in [
            (wilson_uuid, "wilson", "Family Practice", "1234567890"),
            (brown_uuid, "brown", "Cardiology", "1234567891"),
            (davis_uuid, "davis", "Dermatology", "1234567892"),
        ]:
            if uuid:
                user_id = get_user_id_by_uuid(uuid)
                if user_id:
                    update_user_fields(user_id, specialty, npi)
                    providers[key] = user_id
                else:
                    print(f"  WARNING: Could not find user ID for UUID {uuid}")

        # Also track admin provider
        admin_id = run_db("SELECT id FROM users WHERE username='admin' LIMIT 1;")
        if admin_id:
            providers["admin"] = admin_id.strip()
            print(f"  Admin provider: id={providers['admin']}")

        # ============================================================
        # GET PATIENT IDs
        # ============================================================

        print("\n" + "=" * 50)
        print("LOOKING UP PATIENT IDs")
        print("=" * 50)

        patients = {}
        for lname, key in [("Smith", "smith"), ("Johnson", "johnson"), ("Chen", "chen")]:
            pid = run_db(f"SELECT pid FROM patient_data WHERE lname='{lname}' LIMIT 1;")
            if pid:
                patients[key] = pid.strip()
                print(f"  {lname}: pid={patients[key]}")
            else:
                print(f"  WARNING: Patient {lname} not found (run seed_data.py first)")

        # ============================================================
        # APPOINTMENTS
        # ============================================================

        print("\n" + "=" * 50)
        print("CREATING APPOINTMENTS")
        print("=" * 50)

        # Clear old seeded appointments to avoid duplicates on re-run
        run_db(
            "DELETE FROM openemr_postcalendar_events "
            "WHERE pc_hometext LIKE '%[seeded]%';"
        )
        print("  Cleared previous seeded appointments.\n")

        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        day_after = (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d")
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

        # --- Dr. Wilson (Family Practice) — tomorrow, partially booked ---
        if providers.get("wilson") and patients.get("smith"):
            print("  Dr. Wilson — tomorrow:")
            seed_appointment(
                providers["wilson"], patients["smith"], tomorrow,
                "09:00:00", "09:30:00", "Office Visit", "+",
                comment="Follow-up diabetes management [seeded]",
            )
            seed_appointment(
                providers["wilson"], patients["smith"], tomorrow,
                "10:00:00", "10:30:00", "Office Visit", "+",
                comment="Blood pressure check [seeded]",
            )

        if providers.get("wilson") and patients.get("johnson"):
            seed_appointment(
                providers["wilson"], patients["johnson"], tomorrow,
                "11:00:00", "11:30:00", "Office Visit", "+",
                comment="Anxiety medication follow-up [seeded]",
            )
            seed_appointment(
                providers["wilson"], patients["johnson"], tomorrow,
                "14:00:00", "14:30:00", "Office Visit", "+",
                comment="Prescription renewal [seeded]",
            )

        # --- Dr. Brown (Cardiology) — tomorrow, busier schedule ---
        if providers.get("brown") and patients.get("chen"):
            print("\n  Dr. Brown — tomorrow:")
            seed_appointment(
                providers["brown"], patients["chen"], tomorrow,
                "09:00:00", "10:00:00", "Cardiology Consult", "+",
                comment="CAD follow-up and ECG review [seeded]",
            )
            seed_appointment(
                providers["brown"], patients["chen"], tomorrow,
                "10:30:00", "11:30:00", "Cardiology Consult", "+",
                comment="AFib medication adjustment [seeded]",
            )

        if providers.get("brown") and patients.get("smith"):
            seed_appointment(
                providers["brown"], patients["smith"], tomorrow,
                "13:00:00", "14:00:00", "Cardiology Consult", "+",
                comment="Hypertension evaluation [seeded]",
            )
            seed_appointment(
                providers["brown"], patients["smith"], tomorrow,
                "14:30:00", "15:30:00", "Cardiology Consult", "+",
                comment="Cardiac risk assessment [seeded]",
            )

        # --- Dr. Davis (Dermatology) — day after tomorrow ---
        if providers.get("davis") and patients.get("johnson"):
            print(f"\n  Dr. Davis — {day_after}:")
            seed_appointment(
                providers["davis"], patients["johnson"], day_after,
                "10:00:00", "10:30:00", "Dermatology Visit", "+",
                comment="Skin rash evaluation [seeded]",
            )

        if providers.get("davis") and patients.get("smith"):
            seed_appointment(
                providers["davis"], patients["smith"], day_after,
                "14:00:00", "14:30:00", "Dermatology Visit", "+",
                comment="Annual skin check [seeded]",
            )

        # --- Past appointment (completed) for patient history ---
        if providers.get("wilson") and patients.get("smith"):
            print(f"\n  Past appointment (completed) — {yesterday}:")
            seed_appointment(
                providers["wilson"], patients["smith"], yesterday,
                "09:00:00", "09:30:00", "Office Visit", "x",
                comment="Completed: routine checkup [seeded]",
            )

        # ============================================================
        # VERIFICATION
        # ============================================================

        print("\n" + "=" * 50)
        print("VERIFICATION")
        print("=" * 50)

        # Check practitioners via FHIR
        resp = await client.get(
            f"{FHIR_URL}/Practitioner",
            headers={"Authorization": f"Bearer {token}"},
        )
        if resp.status_code == 200:
            entries = resp.json().get("entry", [])
            print(f"\nPractitioners in FHIR: {len(entries)}")
            for e in entries:
                r = e.get("resource", {})
                names = r.get("name", [{}])
                if names:
                    n = names[0]
                    prefix = " ".join(n.get("prefix", []))
                    given = " ".join(n.get("given", []))
                    family = n.get("family", "")
                    print(f"  - {prefix} {given} {family} (UUID: {r.get('id', '?')})")

        # Check appointments via FHIR
        resp = await client.get(
            f"{FHIR_URL}/Appointment",
            params={"date": tomorrow},
            headers={"Authorization": f"Bearer {token}"},
        )
        if resp.status_code == 200:
            entries = resp.json().get("entry", [])
            print(f"\nAppointments for {tomorrow} via FHIR: {len(entries)}")
            for e in entries:
                r = e.get("resource", {})
                start = r.get("start", "?")
                end = r.get("end", "?")
                status = r.get("status", "?")
                participants = r.get("participant", [])
                provider = next(
                    (p["actor"].get("display", "?") for p in participants
                     if p["actor"].get("reference", "").startswith("Practitioner/")),
                    "?",
                )
                print(f"  - {start} to {end} [{status}] with {provider}")
        else:
            print(f"\nFHIR Appointment search returned {resp.status_code}")
            # Fallback: check via DB
            count = run_db(
                "SELECT COUNT(*) FROM openemr_postcalendar_events "
                "WHERE pc_hometext LIKE '%[seeded]%';"
            )
            print(f"  Seeded appointments in DB: {count}")

        print("\nProvider and appointment seed complete!")


if __name__ == "__main__":
    asyncio.run(seed())
