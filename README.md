# AgentForge Healthcare

An AI-powered healthcare assistant built on [OpenEMR](https://www.open-emr.org/), the open-source Electronic Health Records system. Uses a LangGraph agent with 5 specialized tools to query real patient data via FHIR R4 APIs, with a 3-layer verification pipeline to ensure safe, grounded responses.

**Live Demo:** [agentforge-healthcare-production.up.railway.app](https://agentforge-healthcare-production.up.railway.app/)

## Documentation

| Document | Description |
|----------|-------------|
| [ARCHITECTURE.md](ARCHITECTURE.md) | Agent architecture, tools, verification pipeline, deployment |
| [COST_ANALYSIS.md](COST_ANALYSIS.md) | AI cost breakdown, production projections, optimization strategies |
| [DEMO_SCRIPT.md](DEMO_SCRIPT.md) | 5-minute demo walkthrough script |
| [Eval Dataset](https://github.com/rohanthomas1202/healthcare-agent-eval) | Open source eval dataset (57 cases, MIT license) |
| [OpenEMR Integration](https://github.com/rohanthomas1202/openemr/tree/master/agentforge) | Agent integrated into OpenEMR fork |

## Evaluation Results

**57/57 test cases passing (100%)** across 4 categories:

| Category | Passed | Rate | p50 Latency |
|----------|--------|------|-------------|
| Happy path | 25/25 | 100% | 11.5s |
| Edge case | 15/15 | 100% | 10.6s |
| Adversarial | 10/10 | 100% | 8.6s |
| Multi-step | 7/7 | 100% | 19.5s |

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
   +-----------+-----------+-----------+-----------+
   |           |           |           |           |
Patient    Drug        Symptom    Provider   Appointment
Summary    Interaction  Lookup     Search     Availability
   |           |           |           |           |
   +--------- OpenEMR FHIR R4 API ---+           |
              (OAuth2 authenticated)
        |
   Verification Pipeline
   ├── Drug Safety (contradiction detection)
   ├── Confidence Scoring (0.0-1.0)
   └── Claim Verification (hallucination detection)
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

## Tools

| Tool | Description |
|------|-------------|
| `patient_summary` | Retrieves a patient's demographics, conditions, medications, allergies, and immunizations |
| `drug_interaction_check` | Checks a list of medications against a database of ~50 known interaction pairs with severity levels |
| `symptom_lookup` | Maps symptoms to possible conditions using an 18-symptom knowledge base covering 70+ conditions |
| `provider_search` | Searches for practitioners by name or specialty via FHIR Practitioner/PractitionerRole resources |
| `appointment_availability` | Queries upcoming appointment slots for a given provider |

## Verification Systems

1. **Drug Safety Verifier** -- Scans the agent's response and tool outputs for dangerous drug combinations. Flags contradictions where the agent recommends medications that interact.

2. **Confidence Scorer** -- Assigns a 0.0-1.0 confidence score based on: number of tools called, data completeness, response specificity, and whether claims are grounded in tool outputs.

3. **Claim Verifier** -- Extracts factual claims from the response and checks each one against the raw tool outputs. Calculates a grounding rate and flags ungrounded (hallucinated) claims.

All three run via `run_verification_pipeline()` on every response before it reaches the user.

## Tech Stack

- **Agent Framework:** LangGraph (state machine-based reasoning loop)
- **LLM:** Claude Sonnet 4 (primary), GPT-4o (fallback)
- **Backend:** Python 3.11, FastAPI, uvicorn
- **Frontend:** Streamlit
- **EHR System:** OpenEMR (FHIR R4 API with OAuth2)
- **Observability:** LangSmith + custom metrics (token tracking, latency, feedback)
- **Deployment:** Railway (Docker, nginx, supervisord)
- **Evaluation:** 57 test cases, pytest-parametrized, 100% pass rate

## Project Structure

```
agentforge-healthcare/
├── app/
│   ├── main.py                  # FastAPI entry point
│   ├── config.py                # Settings from env vars
│   ├── fhir_client.py           # FHIR client with OAuth2 token management
│   ├── mock_fhir_client.py      # Mock client for deployed demo
│   ├── mock_data.py             # 10 synthetic patients (FHIR format)
│   ├── agent/
│   │   ├── graph.py             # LangGraph state machine
│   │   └── state.py             # Agent state definition
│   ├── api/
│   │   └── routes.py            # /api/health, /api/chat endpoints
│   ├── tools/
│   │   ├── registry.py          # Tool registry
│   │   ├── patient_summary.py
│   │   ├── drug_interaction.py
│   │   ├── symptom_lookup.py
│   │   ├── provider_search.py
│   │   ├── appointment_availability.py
│   │   ├── drug_interactions_db.py   # ~50 interaction pairs
│   │   ├── symptom_conditions_db.py  # 18 symptoms, 70+ conditions
│   │   └── fhir_helpers.py           # FHIR resource parsers
│   └── verification/
│       ├── pipeline.py          # Orchestrator
│       ├── drug_safety.py       # Drug interaction contradiction detection
│       ├── confidence.py        # 0.0-1.0 confidence scoring
│       └── claim_verifier.py    # Hallucination detection via grounding
├── frontend/
│   ├── app.py                   # Streamlit chat UI
│   └── api_client.py            # HTTP client for backend
├── evals/
│   ├── test_cases.json          # 57 test cases
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

57 test cases across 4 categories:

| Category | Count | Description |
|----------|-------|-------------|
| Happy path | 20+ | Standard queries that should work correctly |
| Edge cases | 10+ | Boundary conditions, missing data, unusual inputs |
| Adversarial | 10+ | Prompt injection, out-of-scope requests, unsafe queries |
| Multi-step | 10+ | Queries requiring chained tool calls |

Run evals:

```bash
python evals/test_eval.py
```

## Deployment

The app deploys as a single Docker container on Railway with nginx reverse-proxying to FastAPI (:8000) and Streamlit (:8501).

For real OpenEMR data in production, expose your local OpenEMR via ngrok and set the `OPENEMR_*_URL` env vars to the ngrok URL. For standalone demo mode, set `USE_MOCK_DATA=true`.

## License

MIT
