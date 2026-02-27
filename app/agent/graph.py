"""LangGraph agent orchestrator.

This module defines the agent's reasoning loop:
1. Receive user message
2. LLM decides whether to call a tool or respond directly
3. If tool call → execute tool → feed result back to LLM
4. LLM synthesizes final response
5. Verification layer checks the response
"""

import time
import uuid
from typing import Any, Optional

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode

from app.agent.state import AgentState
from app.config import settings
from app.observability import record_request
from app.tools.registry import get_all_tools

# System prompt for the healthcare agent
SYSTEM_PROMPT = """You are a knowledgeable healthcare assistant powered by OpenEMR, \
a certified Electronic Health Records system. You help patients and healthcare \
providers with medical information, appointment scheduling, medication management, \
and health record queries.

IMPORTANT RULES:
1. Always use the available tools to look up real data — never make up patient records, \
medications, or clinical data.
2. For any medical advice, ALWAYS include a disclaimer to consult a healthcare provider.
3. If you're unsure or the data is incomplete, say so clearly and state your confidence level.
4. Never recommend specific treatments or diagnoses — redirect to professionals.
5. Protect patient privacy — only share information when appropriately requested.
6. When checking drug interactions, always flag severity levels clearly.
7. If a request seems unsafe (e.g., dangerous drug combinations, harmful dosages), \
refuse and explain why.

MULTI-STEP REASONING:
You can and should chain multiple tool calls when a query requires it. Examples:
- "Check John Smith's medications for interactions" → first call patient_summary to get \
the medication list, then call drug_interaction_check with those medications.
- "I need to see a cardiologist next week" → first call provider_search with \
specialty="cardiology", then call appointment_availability with the provider's name.
- "Is my patient safe on their current meds?" → call patient_summary for their record, \
then drug_interaction_check on their medications.
- "What could cause my headache and when can I see a doctor?" → call symptom_lookup for \
possible conditions, then provider_search to find relevant specialists.

Think step by step. After each tool result, decide if you need more information before \
giving a final answer. Combine results from multiple tools into a coherent response.

You have access to tools that query the OpenEMR FHIR R4 API for real patient data."""

# Maximum tool call iterations to prevent infinite loops
MAX_AGENT_ITERATIONS = 10

# In-memory conversation store (will be replaced with proper persistence later)
_conversations: dict[str, list] = {}


def _create_llm():
    """Create the LLM instance based on configuration."""
    if settings.default_llm == "claude":
        return ChatAnthropic(
            model="claude-sonnet-4-20250514",
            anthropic_api_key=settings.anthropic_api_key,
            max_tokens=4096,
            temperature=0,
        )
    else:
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model="gpt-4o",
            openai_api_key=settings.openai_api_key,
            max_tokens=4096,
            temperature=0,
        )


def _build_graph():
    """Build the LangGraph state machine for the agent."""
    tools = get_all_tools()
    llm = _create_llm()
    llm_with_tools = llm.bind_tools(tools)

    def call_model(state: AgentState) -> dict:
        """LLM reasoning node — decides to call tools or respond."""
        messages = state["messages"]
        response = llm_with_tools.invoke(messages)
        return {"messages": [response]}

    def should_continue(state: AgentState) -> str:
        """Routing function — check if LLM wants to call tools.

        Also enforces a max iteration limit to prevent infinite loops
        in multi-step reasoning chains.
        """
        last_message = state["messages"][-1]
        if not last_message.tool_calls:
            return END

        # Count how many tool call rounds have happened
        tool_call_count = sum(
            1 for m in state["messages"]
            if hasattr(m, "tool_calls") and m.tool_calls
        )
        if tool_call_count >= MAX_AGENT_ITERATIONS:
            return END

        return "tools"

    # Build the graph
    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("agent", call_model)
    graph.add_node("tools", ToolNode(tools))

    # Set entry point
    graph.set_entry_point("agent")

    # Add edges
    graph.add_conditional_edges("agent", should_continue, {"tools": "tools", END: END})
    graph.add_edge("tools", "agent")  # After tool execution, go back to LLM

    return graph.compile()


# Compile the graph once at module load
_agent_graph = _build_graph()


async def run_agent(
    message: str, conversation_id: Optional[str] = None
) -> dict[str, Any]:
    """Run the agent on a user message.

    Args:
        message: The user's natural language query.
        conversation_id: Optional ID to continue an existing conversation.

    Returns:
        Dict with response text, conversation_id, tool calls log, etc.
    """
    # Get or create conversation
    if not conversation_id:
        conversation_id = str(uuid.uuid4())

    history = _conversations.get(conversation_id, [])

    # Build messages: system prompt + history + new message
    messages = [SystemMessage(content=SYSTEM_PROMPT)] + history + [HumanMessage(content=message)]

    # Run the graph with latency tracking
    initial_state = {
        "messages": messages,
        "tool_calls_log": [],
        "confidence": None,
        "disclaimers": [],
    }

    t_start = time.time()
    result = await _agent_graph.ainvoke(initial_state)
    latency_ms = (time.time() - t_start) * 1000

    # Extract the final response
    ai_messages = result["messages"]
    final_message = ai_messages[-1]

    # Extract token usage from LLM response metadata
    token_usage = {"input": 0, "output": 0}
    for msg in ai_messages:
        meta = getattr(msg, "response_metadata", {}) or {}
        usage = meta.get("usage", {})
        if usage:
            token_usage["input"] += usage.get("input_tokens", 0)
            token_usage["output"] += usage.get("output_tokens", 0)
        # LangChain unified usage_metadata
        umeta = getattr(msg, "usage_metadata", None)
        if umeta:
            token_usage["input"] += umeta.get("input_tokens", 0)
            token_usage["output"] += umeta.get("output_tokens", 0)

    # Log tool calls from the conversation
    tool_calls = []
    for msg in ai_messages:
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            for tc in msg.tool_calls:
                tool_calls.append(
                    {"tool": tc["name"], "args": tc["args"]}
                )

    # Run verification pipeline on the response
    from app.verification.pipeline import run_verification_pipeline

    verification_result = run_verification_pipeline(
        response_text=final_message.content,
        messages=ai_messages,
        tool_calls=tool_calls,
    )

    # Update conversation history (exclude system prompt)
    _conversations[conversation_id] = [
        m for m in ai_messages if not isinstance(m, SystemMessage)
    ]

    # Build disclaimers — merge keyword-based + verification disclaimers
    disclaimers = []
    if any(
        kw in message.lower()
        for kw in ["medication", "drug", "prescri", "dose", "interact", "symptom", "diagnos"]
    ):
        disclaimers.append(
            "This information is for educational purposes only. "
            "Always consult a qualified healthcare provider for medical advice."
        )
    for d in verification_result.get("disclaimers", []):
        if d not in disclaimers:
            disclaimers.append(d)

    # Record observability metrics
    record_request(
        conversation_id=conversation_id,
        latency_ms=latency_ms,
        token_usage=token_usage,
        tool_calls=tool_calls,
    )

    return {
        "response": final_message.content,
        "conversation_id": conversation_id,
        "tool_calls": tool_calls,
        "confidence": verification_result["confidence"],
        "disclaimers": disclaimers,
        "verification": verification_result.get("verification", {}),
        "token_usage": token_usage,
        "latency_ms": round(latency_ms, 1),
    }
