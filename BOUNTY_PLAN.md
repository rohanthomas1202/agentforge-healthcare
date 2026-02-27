# $500 Bounty Implementation Plan — FDA Drug Safety Intelligence

## Bounty Requirements
1. New data source relevant to healthcare (OpenEMR domain)
2. Agent accesses data **through OpenEMR's API**
3. **Stateful CRUD data** tied to that data source stored in OpenEMR
4. **BOUNTY.md** documenting: customer, features, data source, impact

## What Wins
"The most impactful customer use case, a real data source integrated into the app, and a reliable agent with evals, observability, and verification."

---

## Customer
**Small/rural primary care practices** (1-5 physicians) managing complex polymedicated patients without dedicated pharmacists or enterprise clinical decision support (CDS) systems. They use OpenEMR and manually look up drug safety on FDA.gov — time-consuming and often skipped during busy clinic days.

## New Data Source: openFDA API
- **Drug Label API**: `https://api.fda.gov/drug/label.json` — boxed warnings, contraindications, drug interactions, adverse reactions from FDA-approved labels
- **Drug Adverse Events API**: `https://api.fda.gov/drug/event.json` — post-market surveillance data (FAERS) with real adverse event counts
- **Free, no auth needed**, 240 req/min rate limit, real US government data
- Search by generic name: `?search=openfda.generic_name:metformin&limit=1`
- Adverse events count: `?search=patient.drug.openfda.generic_name:WARFARIN&count=patient.reaction.reactionmeddrapt.exact`

### FDA Label Fields Available
| Field | Description | Example |
|-------|-------------|---------|
| `boxed_warning` | Black box warnings (most critical) | "Lactic Acidosis" for Metformin |
| `contraindications` | When NOT to use the drug | Renal impairment for Metformin |
| `warnings_and_cautions` | General warnings (newer format) | Various |
| `warnings` | General warnings (older format) | Various |
| `drug_interactions` | Known drug interactions | From FDA label text |
| `adverse_reactions` | Reported side effects | Clinical trial + post-market |
| `dosage_and_administration` | How to take the drug | Dosing info |
| `indications_and_usage` | What the drug treats | Approved uses |

**Note:** Some drugs use `warnings_and_cautions`, others use `warnings`. Code should check both. Not all drugs have `boxed_warning` (e.g., atorvastatin doesn't).

---

## New Features: 2 Agent Tools

### Tool 1: `fda_drug_safety` (Centerpiece)
**File:** `app/tools/fda_drug_safety.py`

**What it does:**
1. Queries openFDA Drug Label API for drug's safety profile
2. Queries openFDA Adverse Events API for top reported reactions
3. If patient specified, cross-references FDA data with patient's current meds from OpenEMR
4. Optionally stores the safety report in OpenEMR as an encounter + SOAP note (CREATE operation)

**Parameters:**
- `drug_name` (required): Generic medication name (e.g., "metformin", "warfarin")
- `patient_identifier` (optional): Patient name for cross-reference
- `store_in_ehr` (optional, default False): Store report as clinical note in OpenEMR

**Key functions:**
- `_fetch_fda_label(drug_name)` → calls label API, extracts safety fields
- `_fetch_adverse_events(drug_name)` → calls events API, top 10 reactions with counts
- `_fetch_patient_meds(identifier)` → reuses FHIR patient/medication search
- `_store_safety_report_in_ehr(patient_id, drug, report)` → creates encounter + SOAP note via Standard REST API
- `_format_safety_report(...)` → structured text for LLM consumption

### Tool 2: `record_vitals` (CRUD Demo)
**File:** `app/tools/record_vitals.py`

**What it does:**
Records patient vital signs directly into OpenEMR via Standard REST API.

**Parameters:**
- `patient_identifier` (required): Patient name or UUID
- `systolic_bp`, `diastolic_bp`, `heart_rate`, `temperature`, `weight`, `height`, `respiration`, `oxygen_saturation` (all optional, at least one required)
- `notes` (optional): Clinical notes

**OpenEMR endpoint:** `POST /apis/default/api/patient/{puuid}/vital`

---

## CRUD Operations Through OpenEMR API

| Operation | Implementation | API |
|-----------|---------------|-----|
| **CREATE** | Record vitals, create encounters, write SOAP notes with FDA data | Standard REST API POST |
| **READ** | Fetch patient records, medications, vitals | FHIR API GET (existing) |
| **UPDATE** | Update SOAP notes with follow-up safety reviews | Standard REST API PUT |
| **DELETE** | Mark conditions/allergies as resolved | Standard REST API DELETE |

---

## Implementation Steps

### Step 1: Update OAuth Client for Standard REST API (~10 min)
Add `api:oemr` + write scopes to OAuth client in OpenEMR's DB:
```sql
UPDATE oauth_clients
SET scope = CONCAT(scope, ' api:oemr user/vital.crus user/encounter.crus user/soap_note.crus user/medical_problem.cruds user/allergy.cruds user/medication.cruds')
WHERE client_name = 'AgentForge Final';
```
Test Standard API access with `GET /apis/default/api/patient`.

**Fallback if Unauthorized:** FDA tool still works (openFDA is external). Vitals tool returns graceful "not available in current config" message. The core bounty deliverable (openFDA data source + agent integration) works regardless of Standard API auth.

### Step 2: Add Standard REST API Client (~15 min)
**File:** `app/fhir_client.py`

Add `StandardApiClient` class below `FHIRClient`:
- Same OAuth2 pattern, targets `/apis/default/api/` instead of `/apis/default/fhir/`
- Requests `api:oemr` scope instead of `api:fhir`
- Methods: `post()`, `get()`, `put()`
- Export as `standard_api_client` singleton (None in mock mode)

### Step 3: Create `fda_drug_safety.py` (~35 min)
See Tool 1 description above. Key implementation details:
- Use `httpx.AsyncClient` for openFDA calls (already a dependency)
- Handle both `warnings_and_cautions` and `warnings` field names
- Strip HTML tags from FDA text (`re.sub(r'<[^>]+>', '', text)`)
- Truncate long FDA text to ~500 chars per section for LLM readability
- Patient cross-reference: check if any patient meds appear in FDA `drug_interactions` text

### Step 4: Create `record_vitals.py` (~20 min)
See Tool 2 description above. Key details:
- Validate at least one measurement provided
- Find patient via FHIR search (reuse existing pattern)
- POST to Standard REST API with vitals payload
- Return formatted confirmation

### Step 5: Register Tools + Update System Prompt (~10 min)
- **File:** `app/tools/registry.py` — Add imports + register both tools
- **File:** `app/agent/graph.py` — Add routing examples to SYSTEM_PROMPT:
  ```
  - "FDA warnings for Warfarin" → fda_drug_safety
  - "Record blood pressure 120/80 for John Smith" → record_vitals
  - "Check FDA safety for Robert Chen's Warfarin and save to record" → fda_drug_safety(store_in_ehr=True)
  ```

### Step 6: Add 8 Bounty Eval Cases (~15 min)
**File:** `evals/test_cases.json`

| ID | Category | Description |
|----|----------|-------------|
| bounty_01 | happy_path | FDA safety lookup for Warfarin |
| bounty_02 | happy_path | FDA safety lookup for Metformin |
| bounty_03 | happy_path | FDA safety + patient cross-reference (Robert Chen) |
| bounty_04 | happy_path | Record vitals (John Smith BP + HR) |
| bounty_05 | multi_step | FDA safety + record vitals combined |
| bounty_06 | edge_case | Unknown drug lookup (Fakemedicine123) |
| bounty_07 | edge_case | Record vitals with no measurements |
| bounty_08 | multi_step | Patient summary → FDA safety chain |

### Step 7: Frontend + BOUNTY.md (~15 min)
- **File:** `frontend/app.py` — Add "FDA Safety" and "Record Vitals" quick-start examples
- **File:** `BOUNTY.md` — Required deliverable (customer, features, data source, impact)

### Step 8: Test End-to-End (~15 min)
1. Verify openFDA queries work (Warfarin, Metformin, Lisinopril)
2. Test record_vitals with Standard REST API (or verify graceful fallback)
3. Test multi-step: "Check FDA safety for Robert Chen's Warfarin"
4. Run all eval cases (57 existing + 8 bounty = 65)
5. Verify frontend examples work

---

## Why This Wins the $500

1. **Real external data source** — openFDA is actual US government data, not mock/synthetic
2. **Meaningful CRUD** — writes clinical data (encounters, SOAP notes, vitals) back into the EHR
3. **Compelling customer story** — small practices need drug safety intelligence but can't afford Lexicomp ($3K+/yr) or UpToDate ($500+/yr)
4. **Agent intelligence** — multi-step reasoning: patient meds (FHIR) → FDA safety (openFDA) → documentation (REST API)
5. **Already has** 57+ evals (100% pass), 3 verification systems, full observability, deployed on Railway
6. **Quantifiable impact**: saves 5-10 min per drug lookup, creates audit trail, catches interactions physicians might miss

---

## Total Time Estimate: ~2-2.5 hours
