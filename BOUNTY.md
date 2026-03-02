# BOUNTY.md — AgentForge Healthcare: Clinical Intelligence Suite

## Customer

**Small and rural primary care practices** (1-5 physicians) and **Federally Qualified Health Centers (FQHCs)** who use OpenEMR as their EHR system.

These practices serve 1,400+ FQHCs and thousands of small clinics across the US that rely on OpenEMR — the most widely used open-source EHR. They manage complex, polymedicated patients without dedicated pharmacists, lack enterprise clinical decision support (CDS) systems, and must report quality measures to HRSA for continued federal funding.

**The pain is real and measurable:**

- **Drug safety**: PCPs manually look up drug warnings on FDA.gov — each lookup takes 5-10 minutes, and interactions get missed when patients are on 5+ medications
- **Insurance coverage**: Staff spend 2+ hours/day calling payers to verify formulary coverage, leading to rejected prescriptions and patient delays
- **Preventive care**: USPSTF screenings are tracked on paper or spreadsheets — FQHCs report 30-40% of eligible screenings are missed, jeopardizing HRSA funding
- **Lab interpretation**: Lab trends are scattered across faxed reports and patient portals — PCPs lack real-time trend analysis for chronic disease management (diabetes, CKD, heart failure)
- **Clinical trials**: Rural patients have near-zero access to clinical trial matching — a service reserved for academic medical centers

These practices cannot afford enterprise CDS systems ($3K-50K+/year for Lexicomp, UpToDate, Epic CDS modules). They need an intelligent assistant embedded in their existing EHR workflow.

## Features

### 1. FDA Drug Safety Intelligence (`fda_drug_safety`)

Queries the **openFDA API** (real-time, no API key required) to provide comprehensive drug safety intelligence:

- **Boxed Warnings (Black Box)** — The most critical FDA safety alerts
- **Contraindications** — When a drug should NOT be used
- **Warnings & Precautions** — General safety information
- **Drug Interactions** — Known interactions from FDA-approved labeling
- **Adverse Reactions** — Reported side effects from clinical trials and post-market data
- **FAERS Data** — Top 10 real-world adverse events with report counts from the FDA Adverse Event Reporting System

**Patient Cross-Reference:** When a patient name is provided, the tool automatically fetches the patient's current medications from OpenEMR via FHIR and cross-references them against the FDA drug interaction text, flagging any matches.

**EHR Documentation:** Optionally stores the safety report in OpenEMR as an encounter with a SOAP note (`store_in_ehr=True`), creating an audit trail for drug safety reviews.

**CRUD:** CREATE (encounter + SOAP note) · READ (FDA data + FHIR medications)

### 2. Record Patient Vitals (`record_vitals`)

Records vital signs directly into OpenEMR via the Standard REST API:

- Blood pressure (systolic/diastolic), heart rate, temperature
- Weight, height, respiratory rate, oxygen saturation
- Clinical notes

Validates that at least one measurement is provided, resolves the patient via FHIR, and POSTs the vitals record to OpenEMR's REST endpoint.

**CRUD:** CREATE (POST vitals) · READ (FHIR patient lookup)

### 3. Allergy Safety Checker (`allergy_check`)

Checks if medications are safe for a patient given their documented allergies in OpenEMR:

- **3-level conflict detection**: DIRECT match (exact substance), CLASS match (same drug class), and CROSS-REACTIVE match (known cross-reactivity between drug classes)
- **15 allergy-drug class mappings** covering penicillins, cephalosporins, sulfa drugs, NSAIDs, aspirin, codeine, ACE inhibitors, fluoroquinolones, morphine, iodine contrast, and more
- **Auto-fetch**: If no medication list is provided, automatically retrieves the patient's current prescriptions from OpenEMR FHIR

This tool feeds directly into the **Allergy Safety Verifier** — one of the four verification layers that runs on every agent response.

**CRUD:** READ (FHIR allergies + medications)

### 4. Drug Recall Monitor (`drug_recall_check`)

Queries the **openFDA Drug Enforcement API** (real-time) to check for active FDA recalls and enforcement actions:

- Searches by both generic and brand name
- Returns recall class (I/II/III), reason, recalling firm, distribution pattern
- **Patient mode**: When given a patient name, fetches all current medications from OpenEMR and checks each one for active recalls

**CRUD:** READ (openFDA enforcement data + FHIR medications)

### 5. Clinical Trials Finder (`clinical_trials_search`)

Searches **ClinicalTrials.gov API v2** (real-time) for actively recruiting clinical trials:

- Filters by condition, location, and recruitment status
- Returns trial title, NCT ID, phase, interventions, enrollment count, sponsor, eligibility criteria, and study locations
- **Patient mode**: When given a patient name, fetches active conditions from OpenEMR and searches for trials matching the patient's diagnoses

Brings clinical trial access to rural patients who would otherwise never know about relevant studies.

**CRUD:** READ (ClinicalTrials.gov API + FHIR conditions)

### 6. USPSTF Preventive Care Gap Tracker (`care_gap_analysis` + `update_care_gap`)

Analyzes which evidence-based preventive screenings a patient is due or overdue for, based on USPSTF Grade A/B recommendations:

- **15 screening protocols** seeded from USPSTF guidelines (colorectal cancer, breast cancer, cervical cancer, lung cancer, diabetes, hypertension, depression, statin use, hepatitis C, HIV, osteoporosis, and more)
- **Age and sex filtering** — Only shows applicable screenings (e.g., mammography for women 50-74, prostate screening for men)
- **Status tracking** — Due, overdue, completed, declined
- **Auto-creation** — Gap records are auto-generated when applicable protocols are found for a patient
- **Update workflow** — Mark screenings as completed (with automatic next-due calculation based on frequency), declined, or reset

**CRUD:**
- **CREATE:** Auto-generates `patient_care_gaps` records for applicable protocols
- **READ:** Retrieves all gaps for a patient with status and due dates
- **UPDATE:** Marks screenings as completed/declined, calculates next due date
- **DELETE/RESET:** Resets a gap back to "due" status

**Custom MariaDB tables:** `screening_protocols`, `patient_care_gaps`

### 7. Insurance Formulary & Coverage Check (`insurance_coverage_check`)

Checks whether a medication is covered by a patient's insurance plan:

- **Formulary tier** — Generic (Tier 1), Preferred Brand (Tier 2), Non-Preferred (Tier 3), Specialty (Tier 4)
- **Copay amount** — Estimated out-of-pocket cost
- **Prior authorization** — Whether PA is required
- **Step therapy** — Whether lower-tier alternatives must be tried first
- **Quantity limits** — Maximum supply restrictions
- **Generic alternatives** — Lower-cost equivalent suggestions
- **Cross-plan comparison** — Shows coverage on other available plans
- **All-medications mode** — When no specific drug is given, checks all of the patient's current prescriptions

**3 insurance plans seeded** with ~42 formulary items: Medicare Part D Basic, Blue Cross PPO, Medicaid Standard — covering common medications at different tiers and copays.

**CRUD:**
- **CREATE:** Logs every coverage check to `coverage_checks` table (audit trail)
- **READ:** Looks up formulary coverage, cross-plan comparison
- **UPDATE:** Formulary tiers and copays can be updated
- **DELETE:** Discontinued drugs can be removed from formulary

**Custom MariaDB tables:** `insurance_plans`, `formulary_items`, `patient_insurance`, `coverage_checks`

### 8. Lab Results Trend Analyzer (`lab_results_analysis`)

Retrieves and analyzes lab results with clinical interpretation:

- **20 reference ranges** for common lab tests (HbA1c, glucose, lipid panel, kidney/liver function, hematology, cardiac markers, electrolytes, thyroid)
- **Status classification** — Normal, High, Low, Critical High, Critical Low
- **Trend detection** — Improving, worsening, or stable (5% threshold) based on historical values
- **Category filtering** — Filter by metabolic, renal, lipid, hematology, hepatic, cardiac, or specific test name
- **Clinical significance** — Each test includes evidence-based interpretation notes
- **History display** — Shows last 5 results for flagged tests

**~50 lab results seeded** across 3 patients with clinically interesting patterns:
- **John Smith:** Improving HbA1c trend (8.1% → 7.8% → 7.2%), elevated glucose/lipids (diabetic profile)
- **Sarah Johnson:** Mostly normal labs (healthy baseline)
- **Robert Chen:** High INR (on Warfarin), elevated BNP (heart failure), declining eGFR (worsening kidney function)

**CRUD:** READ (lab results + reference ranges joined by LOINC code)

**Custom MariaDB tables:** `patient_lab_results`, `lab_reference_ranges`

### 9. Multi-Step Agent Reasoning

The LangGraph agent autonomously chains multiple tools for complex clinical workflows:

- **Patient meds → FDA safety**: Fetch a patient's medication list, then look up FDA safety data with cross-referencing
- **FDA safety → EHR documentation**: Look up drug safety, then store the report as a clinical note
- **Care gap → update**: Check screenings, then mark them as completed
- **Insurance + interactions**: Check coverage and drug interactions together
- **Lab results → care gaps**: Review lab trends, then check preventive screenings
- **Complete safety review**: Patient summary → drug interactions → allergy check → recall status → FDA safety (5-tool chain)

## Data Sources

| Source | Type | Used By | Description |
|--------|------|---------|-------------|
| **openFDA Drug Label API** | External REST API | `fda_drug_safety` | Boxed warnings, contraindications, interactions, adverse reactions. Free, no auth, 240 req/min |
| **openFDA FAERS API** | External REST API | `fda_drug_safety` | Real-world adverse event reports with counts |
| **openFDA Enforcement API** | External REST API | `drug_recall_check` | Active drug recalls and enforcement actions |
| **ClinicalTrials.gov API v2** | External REST API | `clinical_trials_search` | Recruiting clinical trials by condition/location |
| **OpenEMR FHIR R4 API** | Internal API | All tools | Patient records, medications, conditions, allergies, observations (OAuth2 secured) |
| **OpenEMR Standard REST API** | Internal API | `record_vitals`, `fda_drug_safety` | Vitals recording, encounter/SOAP note creation |
| **OpenEMR MariaDB** | Internal DB | Care gaps, insurance, labs | 8 custom tables extending OpenEMR's data model |
| **Local knowledge bases** | Embedded | Interactions, allergies | ~50 drug interaction pairs, 18 symptom→70+ condition mappings, 15 allergy-drug class maps |

### Custom MariaDB Tables (8 tables added to OpenEMR)

| Table | Purpose | Operations |
|-------|---------|------------|
| `screening_protocols` | 15 USPSTF Grade A/B recommendations with age/sex eligibility, frequency | READ |
| `patient_care_gaps` | Per-patient screening status tracking (due/overdue/completed/declined) | CREATE, READ, UPDATE |
| `insurance_plans` | 3 insurance plans (Medicare, Blue Cross, Medicaid) | READ |
| `formulary_items` | ~42 formulary entries with tiers, copays, PA requirements, generic alternatives | READ, UPDATE |
| `patient_insurance` | Patient-to-plan enrollment mapping | READ |
| `coverage_checks` | Audit log of every insurance coverage lookup | CREATE, READ |
| `patient_lab_results` | ~50 lab results with LOINC codes, values, dates across 3 patients | READ |
| `lab_reference_ranges` | 20 standard reference ranges with critical thresholds by sex | READ |

All tables live in the same OpenEMR MariaDB database and are accessed via an async connection pool (`aiomysql`), going through the application's data layer — not side-channeled.

## CRUD Operations

| Operation | What | API/DB |
|-----------|------|--------|
| **CREATE** | Record vitals via REST API, create encounters + SOAP notes, auto-generate care gap records, log coverage check audit trail | OpenEMR REST API + MariaDB |
| **READ** | Patient records, medications, conditions, allergies via FHIR; FDA labels/recalls/trials via external APIs; formulary coverage, care gaps, lab results + reference ranges via MariaDB | FHIR R4 + External APIs + MariaDB |
| **UPDATE** | Mark screenings completed/declined (with next-due calculation), update care gap status, update formulary tiers | MariaDB |
| **DELETE/RESET** | Reset care gaps to "due" status, remove discontinued formulary drugs | MariaDB |

## Safety Architecture

### Input Sanitization Layer

All 14 tool functions pass inputs through centralized sanitizers (`app/agent/input_sanitizer.py`) before processing — defense-in-depth against prompt injection, SQL injection, and malformed inputs:

- **Patient names**: Strips non-alphabetic chars, caps 200 chars
- **Drug names**: Removes dosage suffixes, Lucene query injection chars
- **Free text**: Strips 12+ prompt injection patterns (SYSTEM:, ignore instructions, etc.)
- **Lists**: Caps at 50 items, sanitizes each entry

### EHR Abstraction Layer

Both `FHIRClient` and `MockFHIRClient` inherit from `BaseEHRProvider` ABC (`app/ehr_provider.py`), defining a portable interface for EHR data access. Swapping to Epic or Cerner requires implementing one class — no tool code changes needed.

### Verification Pipeline (6 Layers)

Every agent response passes through a 6-layer deterministic verification pipeline before reaching the user:

#### Layer 1: Drug Safety Verifier
- Cross-checks the LLM's response against a local database of ~50 drug interaction pairs
- **Contradiction detection**: Flags if the response says drugs are "safe together" when the DB shows they interact
- **Missing check detection**: Flags if 2+ drugs are mentioned but the interaction tool was never called

#### Layer 2: Allergy Safety Verifier
- Extracts documented allergies from tool outputs (patient_summary, allergy_check)
- Checks if the LLM recommends drugs from a conflicting drug class without proper warning
- Uses the 15-entry allergy-drug class map with cross-reactivity awareness

#### Layer 3: Confidence Scorer
- Computes a deterministic 0.0-1.0 score based on 4 weighted factors:
  - Tool usage (30%) — Were tools called and did they return data?
  - Data richness (30%) — Did tool outputs contain substantive content?
  - Response hedging (20%) — Penalizes uncertainty language
  - Error rate (20%) — Fraction of tool calls without errors
- Scores below 0.3 trigger a LOW CONFIDENCE warning

#### Layer 4: Claim Verifier (Hallucination Detection)
- Extracts factual claims from the response using 8 regex patterns (conditions, medications, allergies, vitals, demographics)
- Checks each claim is "grounded" in tool output (≥60% of key terms must appear in at least one tool's output)
- Flags ungrounded claims as potential hallucinations

#### Layer 5: PHI Detection
- Scans agent responses for Protected Health Information patterns
- **Critical** (blocks response): SSN (`###-##-####`)
- **High** (strong warning): Medical Record Number references
- **Moderate** (informational): Phone numbers, email addresses, street addresses, labeled DOB
- Matched values are partially redacted in logs

#### Layer 6: Dosage Limit Checker
- Extracts dosage mentions from responses (e.g., "5000 mg of acetaminophen")
- Checks against FDA maximum recommended daily doses for 28 common medications
- Flags dosages exceeding FDA limits (e.g., 5000 mg acetaminophen → max 4000 mg/day)

**Overall Safety Formula:**
```
overall_safe = drug_safety.passed AND allergy_safety.passed AND confidence >= 0.3
               AND claims.passed AND phi_detection.passed AND dosage_check.passed
```

All 6 verifiers are deterministic (no LLM calls), fault-tolerant (each wrapped in try/except with safe defaults), and run on every response. Verification results are displayed in the frontend's verification panel with color-coded badges.

## Observability

### LangSmith Integration
- Every agent invocation is traced end-to-end in LangSmith
- Full visibility into: tool calls, LLM inputs/outputs, latency per step, token counts, errors
- Project: `agentforge-healthcare`

### SQLite Metrics Store
Every request is persisted to SQLite with:
- Conversation ID, timestamp, latency (ms)
- Input/output token counts
- Tool calls made (JSON array)
- Errors (if any)

### API Endpoints
- `GET /api/metrics` — Aggregated observability dashboard: total requests, avg latency, token usage, tool usage counts, error count, feedback summary
- `POST /api/feedback` — Thumbs up/down rating per response with optional comments

### Frontend Observability
The custom chat UI displays per-response:
- Confidence badge (High ≥0.7 / Medium ≥0.3 / Low <0.3)
- Tool calls with arguments
- Latency and token count
- Expandable verification details panel
- Thumbs up/down feedback buttons

## Evaluation

**92 test cases** across 4 categories, including **35 dedicated bounty cases** (bounty_01 through bounty_35):

| Category | Count | Description |
|----------|-------|-------------|
| Happy path | 42 | Standard queries for all 14 tools |
| Multi-step | 21 | 2-5 tool chains, complex clinical workflows |
| Edge cases | 18 | Unknown drugs/patients, empty data, boundary conditions |
| Adversarial | 11 | Prompt injection, dangerous advice requests, scope violations |

### Bounty Test Coverage (35 cases)

| Feature | Cases | IDs |
|---------|-------|-----|
| FDA Drug Safety | 8 | bounty_01-03, 05-06, 08, 17 |
| Clinical Trials | 4 | bounty_09-10, 16, 20 |
| Allergy Check | 5 | bounty_11-13, 18-19 |
| Drug Recall | 2 | bounty_14-15 |
| Record Vitals | 2 | bounty_04, 07 |
| Care Gaps | 5 | bounty_21-25 |
| Insurance Coverage | 5 | bounty_26-30 |
| Lab Results | 5 | bounty_31-35 |

### Results (65/92 executed)

| Metric | Value |
|--------|-------|
| **Pass rate** | **65/65 (100%)** |
| Categories passed | happy_path: 26/26, multi_step: 14/14, edge_case: 14/14, adversarial: 11/11 |
| Avg confidence | 0.86 |
| Avg latency | 12.7s |
| Verification safe | 56/65 (86%) |

Each test case validates: correct tool selection (`expected_tools`), response content (`must_contain` / `must_not_contain`), confidence thresholds, verification safety, and latency limits.

## Impact

- **Time savings**: Eliminates 5-10 minutes per manual FDA.gov drug lookup, 2+ hours/day verifying insurance coverage, and manual screening tracking on paper
- **Patient safety**: Automatically surfaces boxed warnings, critical lab values, allergy conflicts, active drug recalls, and overdue screenings — before the provider makes a decision
- **Clinical trial access**: Gives rural patients access to trial matching that was previously only available at academic medical centers
- **Quality reporting**: Auto-tracks USPSTF quality measures required by FQHCs for HRSA funding — directly impacts whether the clinic keeps its federal funding
- **Cost reduction**: Replaces enterprise CDS subscriptions ($3K+/yr Lexicomp, $50K+/yr Epic CDS) with an AI assistant at ~$0.012/query (~$1.04/user/month)
- **Chronic disease management**: Trend analysis on lab results helps PCPs proactively manage diabetes (HbA1c trends), CKD (eGFR decline), and heart failure (BNP levels)
- **Audit trail**: Creates documentation for drug safety reviews, coverage checks, and screening compliance — critical for malpractice defense and regulatory audits
- **6-layer verification**: Every response is independently verified for drug safety, allergy conflicts, confidence, hallucination grounding, PHI leakage, and dosage limits — reducing risk of AI-caused harm in clinical settings
- **Input sanitization**: Centralized defense-in-depth against prompt injection, SQL injection, and malformed inputs across all 14 tools
- **EHR portability**: Abstract `BaseEHRProvider` interface makes the system portable to Epic, Cerner, or other EHR backends without changing tool code
