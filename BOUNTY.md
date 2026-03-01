# BOUNTY.md — AgentForge Healthcare: FDA Drug Safety Intelligence

## Customer

**Small and rural primary care practices** (1-5 physicians) who use OpenEMR as their EHR system and manage complex polymedicated patients without dedicated pharmacists or enterprise clinical decision support (CDS) systems.

These practices currently look up drug safety information manually on FDA.gov — a process that is time-consuming and often skipped during busy clinic days. Expensive enterprise alternatives like Lexicomp ($3K+/yr) or UpToDate ($500+/yr) are out of reach for many small practices.

## Features

### 1. FDA Drug Safety Lookup (`fda_drug_safety` tool)

Queries the **openFDA API** to provide comprehensive drug safety intelligence:

- **Boxed Warnings (Black Box)** — The most critical FDA safety alerts
- **Contraindications** — When a drug should NOT be used
- **Warnings & Precautions** — General safety information
- **Drug Interactions** — Known interactions from FDA-approved labeling
- **Adverse Reactions** — Reported side effects from clinical trials and post-market data
- **FAERS Data** — Top 10 real-world adverse events with report counts from the FDA Adverse Event Reporting System

**Patient Cross-Reference:** When a patient name is provided, the tool automatically fetches the patient's current medications from OpenEMR and cross-references them against the FDA drug interaction text, flagging any matches.

**EHR Documentation:** Optionally stores the safety report in OpenEMR as an encounter with a SOAP note, creating an audit trail for drug safety reviews.

### 2. Record Patient Vitals (`record_vitals` tool)

Records vital signs directly into OpenEMR via the Standard REST API:

- Blood pressure (systolic/diastolic)
- Heart rate
- Temperature
- Weight and height
- Respiratory rate
- Oxygen saturation
- Clinical notes

Validates that at least one measurement is provided and returns a formatted confirmation.

### 3. Multi-Step Agent Reasoning

The agent chains multiple tools for complex clinical workflows:

- **Patient meds → FDA safety**: Fetch a patient's medication list, then look up FDA safety data for a specific drug with cross-referencing
- **FDA safety → EHR documentation**: Look up drug safety, then store the report as a clinical note
- **FDA safety + vitals**: Perform a safety check and record vitals in a single interaction

## Data Source

**openFDA API** ([https://api.fda.gov](https://api.fda.gov)) — The US Food and Drug Administration's public API:

| Endpoint | Description | Data |
|----------|-------------|------|
| `/drug/label.json` | Drug Label API | FDA-approved labeling: boxed warnings, contraindications, interactions, adverse reactions, dosing |
| `/drug/event.json` | Drug Adverse Events API | Post-market surveillance from FAERS: real adverse event reports with counts |

- **Free**, no authentication required
- 240 requests/minute rate limit
- Real US government data — not mock or synthetic
- Searchable by generic drug name

## CRUD Operations

| Operation | Implementation | API |
|-----------|---------------|-----|
| **CREATE** | Record vitals, create encounters, write SOAP notes with FDA safety data | OpenEMR Standard REST API (POST) |
| **READ** | Fetch patient records, medications, conditions, allergies, labs | OpenEMR FHIR R4 API (GET) |
| **UPDATE** | Update SOAP notes with follow-up safety reviews | OpenEMR Standard REST API (PUT) |
| **DELETE** | Mark conditions/allergies as resolved | OpenEMR Standard REST API (DELETE) |

## Impact

- **Time savings**: Eliminates 5-10 minutes per manual FDA.gov drug lookup — multiply by dozens of lookups per day across a busy practice
- **Safety improvement**: Automatically surfaces boxed warnings and contraindications that might be missed during busy clinic days
- **Patient cross-referencing**: Flags when a patient's current medications appear in FDA drug interaction data — catches combinations physicians might miss
- **Audit trail**: Creates documentation in the EHR when safety checks are performed, supporting compliance and continuity of care
- **Cost reduction**: Replaces expensive enterprise CDS subscriptions (Lexicomp $3K+/yr, UpToDate $500+/yr) for basic drug safety intelligence
- **Quantifiable**: At ~$0.012/query, a practice making 50 lookups/day spends ~$0.60/day vs. thousands per year for commercial alternatives

## Evaluation

8 dedicated bounty test cases (bounty_01 through bounty_08) covering:

- Happy path: Warfarin safety, Metformin safety, patient cross-reference, vitals recording
- Edge cases: Unknown drug lookup, vitals with no measurements
- Multi-step: FDA safety + vitals combined, patient summary → FDA safety chain

Combined with the existing 57 test cases for a total of 65 evaluation scenarios.
