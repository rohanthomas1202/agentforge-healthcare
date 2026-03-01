# BOUNTY.md — AgentForge Healthcare: Clinical Intelligence Suite

## Customer

**Small and rural primary care practices** (1-5 physicians) and **Federally Qualified Health Centers (FQHCs)** who use OpenEMR as their EHR system. These practices manage complex polymedicated patients without dedicated pharmacists, lack enterprise clinical decision support (CDS) systems, and must report quality measures to HRSA for funding.

They currently look up drug safety on FDA.gov manually, verify insurance coverage by phone, track preventive screenings on paper, and pull lab trends from separate portals — all time-consuming processes that lead to missed care gaps and delayed clinical decisions.

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

### 3. USPSTF Preventive Care Gap Tracker (`care_gap_analysis` + `update_care_gap` tools)

Analyzes which evidence-based preventive screenings a patient is due or overdue for, based on USPSTF Grade A/B recommendations:

- **15 screening protocols** seeded from USPSTF guidelines (colorectal cancer, breast cancer, cervical cancer, lung cancer, diabetes, hypertension, depression, statin use, hepatitis C, HIV, osteoporosis, and more)
- **Age and sex filtering** — Only shows applicable screenings (e.g., mammography for women 50-74, prostate screening for men)
- **Status tracking** — Due, overdue, completed, declined
- **Auto-creation** — Gap records are auto-generated when applicable protocols are found
- **Update workflow** — Mark screenings as completed (with next-due calculation), declined, or reset

**CRUD operations:**
- **CREATE:** Auto-generates gap records when applicable protocols found
- **READ:** `care_gap_analysis` retrieves all gaps for a patient
- **UPDATE:** `update_care_gap` marks screenings as completed/declined
- **DELETE/RESET:** `update_care_gap` with action="reset" resets a gap to due

### 4. Insurance Formulary & Coverage Check (`insurance_coverage_check` tool)

Checks whether a medication is covered by a patient's insurance plan:

- **Formulary tier** — Generic (Tier 1), Preferred Brand (Tier 2), Non-Preferred (Tier 3), Specialty (Tier 4)
- **Copay amount** — Estimated out-of-pocket cost
- **Prior authorization** — Whether PA is required
- **Step therapy** — Whether lower-tier alternatives must be tried first
- **Quantity limits** — Maximum supply restrictions
- **Generic alternatives** — Lower-cost equivalent suggestions
- **Cross-plan comparison** — Shows coverage on other available plans

**3 insurance plans seeded:** Medicare Part D Basic, Blue Cross PPO, Medicaid Standard with ~42 formulary items covering common medications at different tiers and copays.

**CRUD operations:**
- **CREATE:** Logs every coverage check for audit trail in `coverage_checks` table
- **READ:** Looks up formulary coverage for a medication
- **UPDATE:** Formulary items can be updated (tier/copay changes)
- **DELETE:** Discontinued drugs can be removed from formulary

### 5. Lab Results Trend Analyzer (`lab_results_analysis` tool)

Retrieves and analyzes lab results with clinical interpretation:

- **20 reference ranges** for common lab tests (HbA1c, glucose, lipid panel, kidney/liver function, hematology, cardiac markers, electrolytes, thyroid)
- **Status classification** — Normal, High, Low, Critical High, Critical Low
- **Trend detection** — Improving, worsening, or stable based on historical values
- **Category filtering** — Filter by metabolic, renal, lipid, hematology, hepatic, cardiac, or specific test name
- **Clinical significance** — Each test includes evidence-based interpretation notes
- **History display** — Shows last 5 results for flagged tests

**Sample data seeded:** ~50 lab results across 3 patients with clinically interesting patterns:
- **John Smith:** Improving HbA1c trend (8.1 -> 7.8 -> 7.2%), elevated glucose/lipids (diabetic profile)
- **Sarah Johnson:** Mostly normal labs (healthy baseline)
- **Robert Chen:** High INR (on Warfarin), elevated BNP (heart failure), declining eGFR (worsening kidney function)

### 6. Multi-Step Agent Reasoning

The agent chains multiple tools for complex clinical workflows:

- **Patient meds -> FDA safety**: Fetch a patient's medication list, then look up FDA safety data for a specific drug with cross-referencing
- **FDA safety -> EHR documentation**: Look up drug safety, then store the report as a clinical note
- **Care gap -> update**: Check screenings, then mark them as completed
- **Insurance + interactions**: Check coverage and drug interactions together
- **Lab results -> care gaps**: Review lab trends, then check preventive screenings
- **Complete safety review**: Patient summary -> drug interactions -> allergy check -> recall status -> FDA safety

## Data Sources

| Source | Type | Description |
|--------|------|-------------|
| **openFDA API** | External API | Drug safety: labels, adverse events, recalls. Free, no auth, 240 req/min |
| **ClinicalTrials.gov** | External API | Clinical trial search. Free, no auth |
| **OpenEMR FHIR R4** | Internal API | Patient records, medications, conditions, allergies, observations |
| **OpenEMR MariaDB** | Internal DB | Custom tables for care gaps, insurance formulary, lab reference ranges |
| **Local knowledge bases** | Embedded | Drug interactions (~50 pairs), symptom-condition mappings (18 symptoms, 70+ conditions) |

## CRUD Operations (Full)

| Operation | Implementation | API/DB |
|-----------|---------------|--------|
| **CREATE** | Record vitals, create encounters, write SOAP notes, log coverage checks, auto-create care gap records, insert lab results | OpenEMR REST API + MariaDB |
| **READ** | Patient records, medications, conditions, allergies, labs, formulary, care gaps, screening protocols, reference ranges | FHIR R4 API + MariaDB |
| **UPDATE** | Update SOAP notes, mark screenings completed/declined, update formulary tiers | OpenEMR REST API + MariaDB |
| **DELETE** | Mark conditions/allergies as resolved, reset care gaps, remove discontinued drugs | OpenEMR REST API + MariaDB |

## Impact

- **Time savings**: Eliminates 5-10 minutes per manual FDA.gov drug lookup, 2+ hours/day verifying insurance coverage, and manual screening tracking
- **Safety improvement**: Automatically surfaces boxed warnings, critical lab values, and overdue screenings
- **Patient cross-referencing**: Flags medication-allergy conflicts, drug interaction risks, and insurance coverage gaps
- **Quality reporting**: Auto-tracks USPSTF quality measures required by FQHCs for HRSA funding
- **Cost reduction**: Replaces expensive enterprise CDS subscriptions ($3K+/yr Lexicomp, $500+/yr UpToDate) for ~$0.012/query
- **Clinical decision support**: Trend analysis on lab results helps PCPs manage chronic disease patients (diabetes, CKD, heart failure)
- **Audit trail**: Creates documentation for drug safety reviews, coverage checks, and screening compliance

## Evaluation

35 dedicated bounty test cases (bounty_01 through bounty_35) covering:

- **FDA Safety (8):** Warfarin/Metformin lookups, patient cross-reference, unknown drugs, multi-step chains
- **Clinical Trials (4):** Condition search, patient condition matching, unknown conditions
- **Allergy Check (5):** Penicillin/NSAID cross-reactivity, current meds check, combined safety reviews
- **Drug Recall (2):** Individual drug and patient medication recall checks
- **Record Vitals (2):** Happy path recording and edge case (no measurements)
- **Care Gaps (5):** Patient analysis, female-specific screenings, update workflow, nonexistent patient, combined summary
- **Insurance (5):** Coverage check, cross-plan comparison, generic alternatives, non-formulary drug, combined queries
- **Lab Results (5):** Full panel, HbA1c trend, critical values, kidney function filter, nonexistent patient

Combined with the existing 57 test cases for a total of **92 evaluation scenarios**.
