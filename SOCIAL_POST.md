# Social Post Drafts

## LinkedIn

Built an AI healthcare assistant that plugs into OpenEMR (open-source EHR) and answers clinical questions using real patient data.

What it does:
- Natural language queries against FHIR R4 patient records
- Drug interaction checking with severity ratings
- Symptom-to-condition analysis with triage urgency
- Provider search and appointment availability
- 3-layer verification: drug safety checks, confidence scoring, and hallucination detection

The stack: LangGraph agent + Claude Sonnet 4 + FastAPI + Streamlit, deployed on Railway. 57 eval cases across happy path, edge cases, adversarial, and multi-step reasoning — 100% pass rate.

Open sourced the eval dataset for anyone building healthcare AI agents: github.com/rohanthomas1202/healthcare-agent-eval

Built during Gauntlet Week 2 (AgentForge).

#AI #Healthcare #OpenSource #LangGraph #Anthropic #Claude

---

## X (Twitter)

Built an AI agent that talks to OpenEMR's FHIR API to answer clinical questions — patient summaries, drug interactions, symptom analysis, appointment scheduling.

3 verification layers catch unsafe responses before they reach users. 57 eval cases, 100% pass rate.

Open sourced the eval dataset: github.com/rohanthomas1202/healthcare-agent-eval

Stack: LangGraph + Claude Sonnet 4 + FastAPI + Streamlit on Railway

#AgentForge #HealthcareAI #OpenSource
