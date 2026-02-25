"""Mock FHIR client that serves data from mock_data.py.

Drop-in replacement for FHIRClient when USE_MOCK_DATA=true.
Implements the same interface (search, get_resource, get, close)
so all tools work unchanged.
"""

from __future__ import annotations

from typing import Any, Optional

from app.mock_data import (
    ALLERGIES,
    APPOINTMENTS,
    CONDITIONS,
    IMMUNIZATIONS,
    MEDICATION_REQUESTS,
    OBSERVATIONS,
    PATIENTS,
    PRACTITIONER_ROLES,
    PRACTITIONERS,
)


class MockFHIRClient:
    """In-memory FHIR client backed by static mock data."""

    def __init__(self):
        # Index patients and practitioners by ID for fast lookup
        self._patients = {p["id"]: p for p in PATIENTS}
        self._practitioners = {p["id"]: p for p in PRACTITIONERS}

    async def get(self, path: str, params: Optional[dict] = None) -> dict[str, Any]:
        """Mimic FHIRClient.get() — supports metadata and resource reads."""
        if path == "metadata":
            return {"fhirVersion": "4.0.1", "status": "active"}

        # Handle direct resource reads like "Patient/p-john-smith"
        if "/" in path:
            resource_type, resource_id = path.split("/", 1)
            return await self.get_resource(resource_type, resource_id)

        # Otherwise treat as search
        entries = await self.search(path, params)
        return {"entry": [{"resource": e} for e in entries]}

    async def get_resource(self, resource_type: str, resource_id: str) -> dict[str, Any]:
        """Get a single resource by type and ID."""
        if resource_type == "Patient":
            if resource_id in self._patients:
                return self._patients[resource_id]
            raise Exception(f"Patient/{resource_id} not found")

        if resource_type == "Practitioner":
            if resource_id in self._practitioners:
                return self._practitioners[resource_id]
            raise Exception(f"Practitioner/{resource_id} not found")

        raise Exception(f"{resource_type}/{resource_id} not found")

    async def search(
        self, resource_type: str, params: Optional[dict] = None
    ) -> list[dict[str, Any]]:
        """Search for resources with FHIR-style parameters."""
        params = params or {}

        if resource_type == "Patient":
            return self._search_patients(params)
        if resource_type == "Condition":
            return self._search_by_patient_ref(CONDITIONS, params)
        if resource_type == "MedicationRequest":
            return self._search_by_patient_ref(MEDICATION_REQUESTS, params)
        if resource_type == "AllergyIntolerance":
            return self._search_by_patient_ref(ALLERGIES, params)
        if resource_type == "Immunization":
            return self._search_by_patient_ref(IMMUNIZATIONS, params)
        if resource_type == "Observation":
            return self._search_by_patient_ref(OBSERVATIONS, params)
        if resource_type == "Practitioner":
            return self._search_practitioners(params)
        if resource_type == "PractitionerRole":
            return self._search_practitioner_roles(params)
        if resource_type == "Appointment":
            return self._search_appointments(params)

        return []

    async def post(self, path: str, json_body: dict) -> dict[str, Any]:
        """Mock POST — not needed for read-only deployed version."""
        return {"id": "mock-created", "resourceType": path}

    async def create_resource(self, resource_type: str, resource: dict) -> dict[str, Any]:
        """Mock create — not needed for read-only deployed version."""
        return {"id": "mock-created", "resourceType": resource_type}

    async def request(self, method: str, path: str, **kwargs) -> dict[str, Any]:
        """Generic request handler."""
        return await self.get(path, kwargs.get("params"))

    async def close(self):
        """No-op — nothing to close."""
        pass

    # ── Private search helpers ───────────────────────────────────────────────

    def _search_patients(self, params: dict) -> list[dict]:
        results = []
        given = params.get("given", "").lower()
        family = params.get("family", "").lower()
        name = params.get("name", "").lower()

        for p in PATIENTS:
            p_given = " ".join(p["name"][0].get("given", [])).lower()
            p_family = p["name"][0].get("family", "").lower()
            p_full = f"{p_given} {p_family}"

            if given and family:
                if given in p_given and family in p_family:
                    results.append(p)
            elif family:
                if family in p_family:
                    results.append(p)
            elif given:
                if given in p_given:
                    results.append(p)
            elif name:
                if name in p_full or name in p_given or name in p_family:
                    results.append(p)
            else:
                results.append(p)

        return results

    def _search_by_patient_ref(self, resources: list[dict], params: dict) -> list[dict]:
        """Filter resources by patient reference."""
        patient_id = params.get("patient", "")
        if not patient_id:
            return resources

        ref = f"Patient/{patient_id}"
        return [
            r for r in resources
            if r.get("subject", r.get("patient", {})).get("reference") == ref
            or r.get("subject", r.get("patient", {})).get("reference", "").endswith(f"/{patient_id}")
        ]

    def _search_practitioners(self, params: dict) -> list[dict]:
        results = []
        given = params.get("given", "").lower()
        family = params.get("family", "").lower()
        name = params.get("name", "").lower()

        for p in PRACTITIONERS:
            p_given = " ".join(p["name"][0].get("given", [])).lower()
            p_family = p["name"][0].get("family", "").lower()

            if given and family:
                if given in p_given and family in p_family:
                    results.append(p)
            elif family:
                if family in p_family:
                    results.append(p)
            elif given:
                if given in p_given:
                    results.append(p)
            elif name:
                p_full = f"{p_given} {p_family}"
                if name in p_full:
                    results.append(p)
            else:
                results.append(p)

        return results

    def _search_practitioner_roles(self, params: dict) -> list[dict]:
        specialty = params.get("specialty", "").lower()
        practitioner = params.get("practitioner", "")

        results = []
        for role in PRACTITIONER_ROLES:
            # Filter by specialty code or text
            if specialty:
                for spec in role.get("specialty", []):
                    codings = spec.get("coding", [])
                    for coding in codings:
                        if (specialty == coding.get("code", "").lower()
                                or specialty in coding.get("display", "").lower()):
                            results.append(role)
                            break

            # Filter by practitioner reference
            elif practitioner:
                ref = role.get("practitioner", {}).get("reference", "")
                if practitioner in ref or ref.endswith(practitioner):
                    results.append(role)
            else:
                results.append(role)

        return results

    def _search_appointments(self, params: dict) -> list[dict]:
        date = params.get("date", "")
        patient_id = params.get("patient", "")

        results = []
        for appt in APPOINTMENTS:
            start = appt.get("start", "")

            # Date filter
            if date:
                # Handle FHIR date prefix (ge = greater or equal)
                check_date = date
                if date.startswith("ge"):
                    check_date = date[2:]
                    appt_date = start.split("T")[0] if "T" in start else start
                    if appt_date < check_date:
                        continue
                else:
                    appt_date = start.split("T")[0] if "T" in start else start
                    if appt_date != date:
                        continue

            # Patient filter
            if patient_id:
                found = False
                for p in appt.get("participant", []):
                    ref = p.get("actor", {}).get("reference", "")
                    if f"Patient/{patient_id}" in ref:
                        found = True
                        break
                if not found:
                    continue

            results.append(appt)

        return results
