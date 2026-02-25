"""Provider search tool — finds healthcare providers by name or specialty.

Queries OpenEMR's FHIR API for Practitioner and PractitionerRole resources
to search by name, specialty, or both.
"""

from typing import Optional

from langchain_core.tools import tool

from app.fhir_client import fhir_client
from app.tools.fhir_helpers import extract_practitioner, extract_practitioner_role

# Map common specialty names to NUCC taxonomy codes.
# OpenEMR's FHIR PractitionerRole only supports code-based specialty search.
SPECIALTY_CODES: dict[str, str] = {
    "cardiology": "207RC0000X",
    "cardiovascular": "207RC0000X",
    "cardiovascular disease": "207RC0000X",
    "heart": "207RC0000X",
    "family medicine": "207Q00000X",
    "family practice": "207Q00000X",
    "dermatology": "207N00000X",
    "skin": "207N00000X",
    "internal medicine": "207R00000X",
    "general practice": "208D00000X",
    "pediatrics": "208000000X",
    "emergency medicine": "207P00000X",
    "orthopedic surgery": "207X00000X",
    "orthopedics": "207X00000X",
    "neurology": "2084N0400X",
    "psychiatry": "2084P0800X",
    "obstetrics": "207V00000X",
    "gynecology": "207V00000X",
    "ob/gyn": "207V00000X",
    "urology": "208800000X",
    "ophthalmology": "207W00000X",
    "anesthesiology": "207L00000X",
    "allergy": "207K00000X",
    "immunology": "207K00000X",
    "surgery": "208600000X",
    "plastic surgery": "208200000X",
}


@tool
async def provider_search(
    name: Optional[str] = None,
    specialty: Optional[str] = None,
) -> str:
    """Search for healthcare providers (doctors, specialists) by name or specialty.

    Use this tool when:
    - A user asks to find a doctor or specialist
    - A user needs a provider in a specific specialty (e.g., cardiology, family practice)
    - A user wants contact information for a provider
    - A user asks who is available to see them

    Args:
        name: Provider name to search for (e.g., "Dr. Smith", "Wilson"). Partial names work.
        specialty: Medical specialty to search for (e.g., "cardiology", "family practice", "dermatology").
    """
    try:
        if not name and not specialty:
            return "Please provide a provider name or specialty to search for."

        providers = []

        if specialty and not name:
            providers = await _search_by_specialty(specialty)
        elif name and not specialty:
            providers = await _search_by_name(name)
        else:
            # Both provided — search by name, enrich with specialty from roles
            providers = await _search_by_name(name)
            # Also search by specialty and merge any new results
            specialty_providers = await _search_by_specialty(specialty)
            name_ids = {p["id"] for p in providers}
            for sp in specialty_providers:
                if sp["id"] not in name_ids:
                    providers.append(sp)

        if not providers:
            search_desc = []
            if name:
                search_desc.append(f"name '{name}'")
            if specialty:
                search_desc.append(f"specialty '{specialty}'")
            return (
                f"No providers found matching {' and '.join(search_desc)}. "
                "Try a broader search or check the spelling."
            )

        return _format_results(providers, name, specialty)

    except Exception as e:
        return f"Error searching for providers: {str(e)}"


async def _search_by_name(name: str) -> list[dict]:
    """Search for practitioners by name via FHIR Practitioner endpoint.

    Note: OpenEMR's FHIR Practitioner search returns 500 for the 'name' param,
    so we use 'family' and 'given' instead.
    """
    # Strip common prefixes like "Dr.", "Dr"
    clean_name = name.strip()
    for prefix in ["Dr.", "Dr ", "dr.", "dr "]:
        if clean_name.lower().startswith(prefix):
            clean_name = clean_name[len(prefix):].strip()

    parts = clean_name.split()

    if len(parts) >= 2:
        # Try given + family
        practitioners = await fhir_client.search(
            "Practitioner", {"given": parts[0], "family": parts[-1]}
        )
        if practitioners:
            results = [extract_practitioner(p) for p in practitioners]
            await _enrich_with_roles(results)
            return results

    # Single name — try as family name first (more common search), then given
    practitioners = await fhir_client.search("Practitioner", {"family": clean_name})
    if not practitioners:
        practitioners = await fhir_client.search("Practitioner", {"given": clean_name})

    results = [extract_practitioner(p) for p in practitioners]
    await _enrich_with_roles(results)
    return results


async def _search_by_specialty(specialty: str) -> list[dict]:
    """Search for practitioners by specialty via PractitionerRole endpoint."""
    # Map common names to NUCC taxonomy codes (OpenEMR requires codes, not text)
    code = SPECIALTY_CODES.get(specialty.lower().strip())
    search_term = code if code else specialty
    roles = await fhir_client.search("PractitionerRole", {"specialty": search_term})

    providers = []
    seen_ids = set()

    for role in roles:
        role_data = extract_practitioner_role(role)
        practitioner_ref = role.get("practitioner", {}).get("reference", "")

        if practitioner_ref and practitioner_ref.startswith("Practitioner/"):
            pract_id = practitioner_ref.replace("Practitioner/", "")
            if pract_id not in seen_ids:
                seen_ids.add(pract_id)
                try:
                    pract = await fhir_client.get_resource("Practitioner", pract_id)
                    provider = extract_practitioner(pract)
                    provider["specialty"] = role_data.get("specialty", specialty)
                    provider["organization"] = role_data.get("organization")
                    providers.append(provider)
                except Exception:
                    # Use what we have from the role
                    providers.append({
                        "id": pract_id,
                        "name": role.get("practitioner", {}).get("display", "Unknown"),
                        "specialty": role_data.get("specialty", specialty),
                        "organization": role_data.get("organization"),
                    })

    return providers


async def _enrich_with_roles(providers: list[dict]) -> None:
    """Add specialty and organization info from PractitionerRole resources."""
    for provider in providers:
        pract_id = provider.get("id")
        if not pract_id:
            continue
        try:
            roles = await fhir_client.search(
                "PractitionerRole", {"practitioner": f"Practitioner/{pract_id}"}
            )
            if roles:
                role_data = extract_practitioner_role(roles[0])
                provider["specialty"] = role_data.get("specialty")
                provider["organization"] = role_data.get("organization")
        except Exception:
            pass


def _format_results(
    providers: list[dict], name: Optional[str], specialty: Optional[str]
) -> str:
    """Format provider search results into a readable string."""
    lines = []
    lines.append("=== PROVIDER SEARCH RESULTS ===")

    search_desc = []
    if name:
        search_desc.append(f"Name: {name}")
    if specialty:
        search_desc.append(f"Specialty: {specialty}")
    lines.append(f"Search: {', '.join(search_desc)}")
    lines.append(f"Found {len(providers)} provider(s)\n")

    for idx, p in enumerate(providers, 1):
        lines.append(f"--- Provider {idx} ---")
        lines.append(f"  Name: {p.get('name', 'Unknown')}")
        if p.get("npi"):
            lines.append(f"  NPI: {p['npi']}")
        if p.get("specialty"):
            lines.append(f"  Specialty: {p['specialty']}")
        if p.get("organization"):
            lines.append(f"  Organization: {p['organization']}")
        if p.get("phone"):
            lines.append(f"  Phone: {p['phone']}")
        if p.get("email"):
            lines.append(f"  Email: {p['email']}")
        if p.get("address"):
            lines.append(f"  Address: {p['address']}")
        if p.get("active") is not None:
            status = "Active" if p["active"] else "Inactive"
            lines.append(f"  Status: {status}")
        lines.append(f"  Provider ID: {p.get('id', 'Unknown')}")
        lines.append("")

    lines.append("To schedule an appointment, use the appointment availability tool")
    lines.append("with a provider's name or ID.")

    return "\n".join(lines)
