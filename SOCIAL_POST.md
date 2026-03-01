# Social Post Drafts

## LinkedIn

Built an AI healthcare assistant that plugs into OpenEMR (open-source EHR) and answers clinical questions using real patient data.

What it does:
- Natural language queries against FHIR R4 patient records
- Drug interaction checking with severity ratings
- Symptom-to-condition analysis with triage urgency
- Provider search and appointment availability
- 3-layer verification: drug safety checks, confidence scoring, and hallucination detection

The stack: LangGraph agent + Claude Sonnet 4 + FastAPI + Streamlit, deployed on AWS Lightsail with a full OpenEMR instance. 57 eval cases across happy path, edge cases, adversarial, and multi-step reasoning — 100% pass rate.

Open sourced the eval dataset for anyone building healthcare AI agents: github.com/rohanthomas1202/healthcare-agent-eval

Built during Gauntlet Week 2 (AgentForge).

#AI #Healthcare #OpenSource #LangGraph #Anthropic #Claude

---

## X (Twitter)

Built an AI healthcare agent on OpenEMR — answers clinical questions using real FHIR patient data with 3 verification layers for safety. 57 evals, 100% pass rate.

Eval dataset open sourced: github.com/rohanthomas1202/healthcare-agent-eval

#AgentForge #HealthcareAI
