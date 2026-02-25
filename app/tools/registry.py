"""Tool registry — central place that collects all agent tools.

Each tool module in app/tools/ defines LangChain tools using the @tool decorator.
This registry imports them all and provides them to the LangGraph agent.
"""

from langchain_core.tools import BaseTool

from app.tools.appointment_availability import appointment_availability
from app.tools.drug_interaction import drug_interaction_check
from app.tools.patient_summary import patient_summary
from app.tools.provider_search import provider_search
from app.tools.symptom_lookup import symptom_lookup


def get_all_tools() -> list[BaseTool]:
    """Return all registered tools for the agent."""
    tools = [
        patient_summary,
        drug_interaction_check,
        symptom_lookup,
        provider_search,
        appointment_availability,
    ]
    return tools
