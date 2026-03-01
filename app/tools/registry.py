"""Tool registry — central place that collects all agent tools.

Each tool module in app/tools/ defines LangChain tools using the @tool decorator.
This registry imports them all and provides them to the LangGraph agent.
"""

from langchain_core.tools import BaseTool

from app.tools.allergy_checker import allergy_check
from app.tools.appointment_availability import appointment_availability
from app.tools.clinical_trials import clinical_trials_search
from app.tools.drug_interaction import drug_interaction_check
from app.tools.drug_recall import drug_recall_check
from app.tools.fda_drug_safety import fda_drug_safety
from app.tools.patient_summary import patient_summary
from app.tools.provider_search import provider_search
from app.tools.record_vitals import record_vitals
from app.tools.symptom_lookup import symptom_lookup


def get_all_tools() -> list[BaseTool]:
    """Return all registered tools for the agent."""
    tools = [
        patient_summary,
        drug_interaction_check,
        symptom_lookup,
        provider_search,
        appointment_availability,
        fda_drug_safety,
        record_vitals,
        clinical_trials_search,
        allergy_check,
        drug_recall_check,
    ]
    return tools
