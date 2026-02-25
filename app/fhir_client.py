"""OpenEMR FHIR API client with automatic OAuth2 token management.

This module handles:
1. Getting an access token via OAuth2 password grant
2. Automatically refreshing the token when it expires
3. Making authenticated FHIR API requests
4. Returning parsed JSON responses

When USE_MOCK_DATA=true, a MockFHIRClient is used instead (no OpenEMR needed).
"""

import os
import time
from typing import Any, Optional

import httpx

from app.config import settings


class FHIRClient:
    """HTTP client for OpenEMR's FHIR R4 API with automatic OAuth2 auth."""

    def __init__(self):
        self._access_token: Optional[str] = None
        self._refresh_token: Optional[str] = None
        self._token_expires_at: float = 0
        # Disable SSL verification for local dev (self-signed cert)
        # ngrok-skip-browser-warning header prevents ngrok interstitial page
        self._http = httpx.AsyncClient(
            verify=False,
            timeout=30.0,
            headers={"ngrok-skip-browser-warning": "true"},
        )

    async def _get_token(self) -> str:
        """Get a valid access token, refreshing if needed."""
        now = time.time()

        # If token is still valid (with 60s buffer), reuse it
        if self._access_token and now < self._token_expires_at - 60:
            return self._access_token

        # Try refresh token first (if we have one)
        if self._refresh_token:
            try:
                return await self._refresh_access_token()
            except Exception:
                pass  # Fall through to password grant

        # Password grant — get a fresh token
        return await self._password_grant()

    async def _password_grant(self) -> str:
        """Get a new token using username/password credentials."""
        response = await self._http.post(
            settings.openemr_token_url,
            data={
                "grant_type": "password",
                "username": settings.openemr_username,
                "password": settings.openemr_password,
                "user_role": "users",
                "client_id": settings.openemr_client_id,
                "client_secret": settings.openemr_client_secret,
                "scope": (
                    "openid api:fhir "
                    "user/Patient.read user/Encounter.read "
                    "user/Condition.read user/AllergyIntolerance.read "
                    "user/MedicationRequest.read user/Medication.read "
                    "user/Immunization.read user/Appointment.read "
                    "user/Practitioner.read user/PractitionerRole.read "
                    "user/Organization.read "
                    "user/Location.read user/Observation.read "
                    "user/Coverage.read user/DocumentReference.read"
                ),
            },
        )
        response.raise_for_status()
        data = response.json()

        self._access_token = data["access_token"]
        self._refresh_token = data.get("refresh_token")
        self._token_expires_at = time.time() + data.get("expires_in", 3600)

        return self._access_token

    async def _refresh_access_token(self) -> str:
        """Refresh an expired access token using the refresh token."""
        response = await self._http.post(
            settings.openemr_token_url,
            data={
                "grant_type": "refresh_token",
                "refresh_token": self._refresh_token,
                "client_id": settings.openemr_client_id,
                "client_secret": settings.openemr_client_secret,
            },
        )
        response.raise_for_status()
        data = response.json()

        self._access_token = data["access_token"]
        self._refresh_token = data.get("refresh_token", self._refresh_token)
        self._token_expires_at = time.time() + data.get("expires_in", 3600)

        return self._access_token

    async def request(
        self, method: str, path: str, params: Optional[dict] = None,
        json_body: Optional[dict] = None,
    ) -> dict[str, Any]:
        """Make an authenticated FHIR API request.

        Args:
            method: HTTP method (GET, POST, PUT, etc.)
            path: FHIR resource path (e.g., "Patient", "Patient/uuid-here")
            params: Optional query parameters (e.g., {"name": "John"})
            json_body: Optional JSON body for POST/PUT requests.

        Returns:
            Parsed JSON response as a dictionary.

        Raises:
            httpx.HTTPStatusError: If the API returns an error status.
        """
        token = await self._get_token()
        url = f"{settings.openemr_fhir_url}/{path}"

        headers = {"Authorization": f"Bearer {token}"}
        if json_body is not None:
            headers["Content-Type"] = "application/fhir+json"

        response = await self._http.request(
            method,
            url,
            params=params,
            json=json_body,
            headers=headers,
        )
        response.raise_for_status()
        return response.json()

    async def get(self, path: str, params: Optional[dict] = None) -> dict[str, Any]:
        """Shorthand for GET requests."""
        return await self.request("GET", path, params)

    async def post(self, path: str, json_body: dict) -> dict[str, Any]:
        """Shorthand for POST requests (create resources)."""
        return await self.request("POST", path, json_body=json_body)

    async def create_resource(self, resource_type: str, resource: dict) -> dict[str, Any]:
        """Create a new FHIR resource.

        Args:
            resource_type: FHIR resource type (e.g., "Patient")
            resource: The resource data to create.

        Returns:
            The created resource with server-assigned ID.
        """
        return await self.post(resource_type, resource)

    async def search(
        self, resource_type: str, params: Optional[dict] = None
    ) -> list[dict[str, Any]]:
        """Search for FHIR resources and return the entries.

        Args:
            resource_type: FHIR resource type (e.g., "Patient", "Condition")
            params: Search parameters

        Returns:
            List of resource entries (the 'resource' field from each Bundle entry).
        """
        result = await self.get(resource_type, params)

        # FHIR search returns a Bundle with entries
        entries = result.get("entry", [])
        return [entry.get("resource", entry) for entry in entries]

    async def get_resource(self, resource_type: str, resource_id: str) -> dict[str, Any]:
        """Get a single FHIR resource by ID.

        Args:
            resource_type: FHIR resource type (e.g., "Patient")
            resource_id: The resource's UUID

        Returns:
            The FHIR resource as a dictionary.
        """
        return await self.get(f"{resource_type}/{resource_id}")

    async def close(self):
        """Close the HTTP client."""
        await self._http.aclose()


# Singleton instance — use MockFHIRClient when USE_MOCK_DATA is set
if os.getenv("USE_MOCK_DATA", "").lower() in ("true", "1", "yes"):
    from app.mock_fhir_client import MockFHIRClient
    fhir_client = MockFHIRClient()  # type: ignore[assignment]
    print("[startup] Using MOCK data (no OpenEMR connection)")
else:
    fhir_client = FHIRClient()
