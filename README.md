# AgentForge Healthcare

An AI-powered healthcare assistant built on [OpenEMR](https://www.open-emr.org/), the open-source Electronic Health Records system. Uses a LangGraph agent with 14 specialized tools to query real patient data via FHIR R4 APIs and custom MariaDB tables, with a 6-layer verification pipeline, input sanitization, and an EHR abstraction layer to ensure safe, grounded responses.

**Live Demo:** [http://54.236.183.203](http://54.236.183.203/)

## Documentation

| Document | Description |
|----------|-------------|
| [ARCHITECTURE.md](ARCHITECTURE.md) | Agent architecture, tools, verification pipeline, deployment |
| [COST_ANALYSIS.md](COST_ANALYSIS.md) | AI cost breakdown, production projections, optimization strategies |
| [DEMO_SCRIPT.md](DEMO_SCRIPT.md) | 5-minute demo walkthrough script |
| [BOUNTY.md](BOUNTY.md) | Bounty features: FDA safety, care gaps, insurance, lab results |
| [Eval Dataset](https://github.com/rohanthomas1202/healthcare-agent-eval) | Open source eval dataset (92 cases, MIT license) |
| [OpenEMR Integration](https://github.com/rohanthomas1202/openemr/tree/master/agentforge) | Agent integrated into OpenEMR fork |

## Evaluation Results

**92 test cases** across 4 categories covering all 14 tools:

| Category | Count | Description |
|----------|-------|-------------|
| Happy path | 35+ | Core tool functionality across all tools |
| Edge case | 15+ | Missing data, unknown inputs, boundary conditions |
| Adversarial | 11 | Prompt injection, unsafe queries, role overrides |
| Multi-step | 15+ | Complex reasoning chains across multiple tools |

## Architecture

```
User (Streamlit Chat UI)
        |
   nginx reverse proxy (:8080)
        |
   FastAPI backend (:8000)
        |
   LangGraph Agent (Claude / GPT-4)
        |
   14 Specialized Tools:
   ├── Patient Summary, Drug Interactions, Symptoms, Providers, Appointments
   ├── FDA Safety, Drug Recalls, Clinical Trials, Allergy Check, Vitals
   └── Care Gaps, Insurance Coverage, Lab Results, Update Care Gap
        |
   +--- OpenEMR FHIR R4 API ---+--- Custom MariaDB Tables ---+
        (OAuth2 authenticated)     (care gaps, insurance, labs)
        |
   Verification Pipeline (6 layers)
   ├── Drug Safety (contradiction detection)
   ├── Allergy Safety (cross-reactivity checks)
   ├── Confidence Scoring (0.0-1.0)
   ├── Claim Verification (hallucination detection)
   ├── PHI Detection (SSN, phone, email, address)
   └── Dosage Limit Checker (FDA max daily doses)
        |
   Response + metadata → User
```

### Agent Loop

1. User sends a natural language query
2. LLM decides which tool(s) to call (supports multi-step reasoning chains)
3. Tools execute against OpenEMR's FHIR R4 API with OAuth2 authentication
4. LLM synthesizes tool results into a coherent response
5. Verification pipeline checks the response for drug safety, confidence, and grounding
6. Response is returned with confidence score, disclaimers, and verification metadata

## Tools (14)

| Tool | Description |
|------|-------------|
| `patient_summary` | Retrieves demographics, conditions, medications, allergies, immunizations |
| `drug_interaction_check` | Checks medications against ~50 known interaction pairs with severity |
| `symptom_lookup` | Maps symptoms to 70+ conditions with triage urgency levels |
| `provider_search` | Searches practitioners by name or specialty via FHIR |
| `appointment_availability` | Queries appointment slots for a provider |
| `fda_drug_safety` | FDA boxed warnings, contraindications, FAERS adverse events |
| `record_vitals` | Records BP, heart rate, temperature, weight into OpenEMR |
| `clinical_trials_search` | Searches ClinicalTrials.gov for recruiting studies |
| `allergy_check` | Drug-allergy cross-reactivity detection |
| `drug_recall_check` | FDA recall alerts for medications |
| `care_gap_analysis` | USPSTF preventive screening gap tracker (15 protocols) |
| `update_care_gap` | Mark screenings as completed, declined, or reset |
| `insurance_coverage_check` | Formulary tier, copay, prior auth, generic alternatives |
| `lab_results_analysis` | Lab trends, reference ranges, critical value flagging |

## Safety & Verification

### Input Sanitization
All 14 tools pass inputs through centralized sanitizers (`app/agent/input_sanitizer.py`) — defense-in-depth against prompt injection, SQL injection, and malformed inputs.

### Verification Pipeline (6 Layers)

1. **Drug Safety Verifier** — Flags dangerous drug combinations and contradictions in the agent's response.
2. **Allergy Safety Verifier** — Checks if recommended drugs conflict with the patient's documented allergies, including cross-reactivity.
3. **Confidence Scorer** — 0.0-1.0 score based on tool usage, data completeness, response specificity, and grounding.
4. **Claim Verifier** — Extracts factual claims and checks each one is grounded in raw tool outputs (hallucination detection).
5. **PHI Detector** — Scans responses for Protected Health Information (SSN, phone, email, address, MRN, DOB). SSN blocks the response; others warn.
6. **Dosage Limit Checker** — Flags dosage mentions exceeding FDA maximum recommended daily doses for 28 common medications.

All six run via `run_verification_pipeline()` on every response. Each is wrapped in try/except with safe defaults — a single verifier crash never blocks the response.

### EHR Abstraction Layer
Both `FHIRClient` and `MockFHIRClient` inherit from `BaseEHRProvider` ABC — making the system portable to Epic, Cerner, or other EHR backends without changing tool code.

## Tech Stack

- **Agent Framework:** LangGraph (state machine-based reasoning loop)
- **LLM:** Claude Sonnet 4 (primary), GPT-4o (fallback)
- **Backend:** Python 3.11, FastAPI, uvicorn
- **Frontend:** Streamlit
- **EHR System:** OpenEMR (FHIR R4 API with OAuth2)
- **Observability:** LangSmith + custom metrics (token tracking, latency, feedback)
- **Deployment:** AWS Lightsail (Docker Compose: MariaDB + OpenEMR + AgentForge)
- **Evaluation:** 92 test cases, pytest-parametrized

## Project Structure

```
agentforge-healthcare/
├── app/
│   ├── main.py                  # FastAPI entry point
│   ├── config.py                # Settings from env vars
│   ├── ehr_provider.py           # BaseEHRProvider ABC (EHR abstraction layer)
│   ├── fhir_client.py           # FHIR client with OAuth2 token management
│   ├── mock_fhir_client.py      # Mock client for deployed demo
│   ├── mock_data.py             # 10 synthetic patients (FHIR format)
│   ├── agent/
│   │   ├── graph.py             # LangGraph state machine
│   │   ├── state.py             # Agent state definition
│   │   └── input_sanitizer.py   # Centralized input sanitization
│   ├── api/
│   │   └── routes.py            # /api/health, /api/chat endpoints
│   ├── openemr_db.py              # Async MariaDB connection pool
│   ├── tools/
│   │   ├── registry.py            # Tool registry (14 tools)
│   │   ├── patient_summary.py
│   │   ├── drug_interaction.py
│   │   ├── symptom_lookup.py
│   │   ├── provider_search.py
│   │   ├── appointment_availability.py
│   │   ├── fda_drug_safety.py
│   │   ├── record_vitals.py
│   │   ├── clinical_trials.py
│   │   ├── allergy_checker.py
│   │   ├── drug_recall.py
│   │   ├── care_gap_analysis.py
│   │   ├── insurance_coverage.py
│   │   ├── lab_results.py
│   │   ├── drug_interactions_db.py   # ~50 interaction pairs
│   │   ├── symptom_conditions_db.py  # 18 symptoms, 70+ conditions
│   │   └── fhir_helpers.py           # FHIR resource parsers
│   └── verification/
│       ├── pipeline.py          # Orchestrator (6-layer pipeline)
│       ├── drug_safety.py       # Drug interaction contradiction detection
│       ├── allergy_safety.py    # Allergy-drug cross-reactivity checks
│       ├── confidence.py        # 0.0-1.0 confidence scoring
│       ├── claim_verifier.py    # Hallucination detection via grounding
│       ├── phi_detector.py      # PHI pattern detection (SSN, phone, email)
│       └── dosage_checker.py    # FDA max daily dose verification
├── frontend/
│   ├── app.py                   # Streamlit chat UI
│   └── api_client.py            # HTTP client for backend
├── evals/
│   ├── test_cases.json          # 92 test cases
│   ├── results.json             # Evaluation results
│   ├── test_eval.py             # Test runner
│   └── helpers.py               # Eval utilities
├── deploy/
│   ├── nginx.conf               # Reverse proxy config
│   ├── supervisord.conf         # Process manager
│   └── start.sh                 # Container entry point
├── Dockerfile
├── railway.toml
└── requirements.txt
```

## Local Development

### Prerequisites

- Python 3.9+
- OpenEMR Docker instance running on `localhost:9300`
- Anthropic API key (and/or OpenAI API key)

### Setup

```bash
# Clone the repo
git clone https://github.com/rohanthomas1202/agentforge-healthcare.git
cd agentforge-healthcare

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your API keys and OpenEMR credentials
```

### Environment Variables

```env
# LLM
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...

# OpenEMR FHIR API
OPENEMR_BASE_URL=https://localhost:9300
OPENEMR_FHIR_URL=https://localhost:9300/apis/default/fhir
OPENEMR_TOKEN_URL=https://localhost:9300/oauth2/default/token
OPENEMR_CLIENT_ID=your-client-id
OPENEMR_CLIENT_SECRET=your-client-secret
OPENEMR_USERNAME=admin
OPENEMR_PASSWORD=pass

# Mock mode (no OpenEMR needed)
USE_MOCK_DATA=true

# Observability
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=ls__...
LANGCHAIN_PROJECT=agentforge-healthcare
```

### Running

```bash
# Start the backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Start the frontend (separate terminal)
streamlit run frontend/app.py --server.port 8501
```

### Seed Data (for real OpenEMR)

```bash
python scripts/seed_data.py
python scripts/seed_providers_appointments.py
```

## Evaluation

92 test cases across 4 categories covering all 14 tools:

| Category | Count | Description |
|----------|-------|-------------|
| Happy path | 35+ | Standard queries across all tools |
| Edge cases | 15+ | Boundary conditions, missing data, unknown inputs |
| Adversarial | 11 | Prompt injection, unsafe queries, role overrides |
| Multi-step | 15+ | Complex reasoning chains across multiple tools |

Run evals:

```bash
python evals/test_eval.py
```

## Deployment

The app deploys on AWS Lightsail as a 3-container Docker Compose stack:
- **MariaDB** — OpenEMR database
- **OpenEMR** — FHIR R4 API server (internal only, port 443)
- **AgentForge** — FastAPI + Streamlit + nginx (exposed on port 80)

The AgentForge container uses nginx to reverse-proxy to FastAPI (:8000) and Streamlit (:8501). OpenEMR communicates with the agent via Docker internal DNS (`https://openemr`).

## License

MIT
