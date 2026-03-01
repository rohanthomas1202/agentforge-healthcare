"""LangGraph agent orchestrator.

This module defines the agent's reasoning loop:
1. Receive user message
2. LLM decides whether to call a tool or respond directly
3. If tool call -> execute tool -> feed result back to LLM
4. LLM synthesizes final response
5. Verification layer checks the response
"""

import asyncio
import json
import logging
import time
import uuid
from collections.abc import AsyncGenerator
from typing import Any, Optional

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode

from app.agent.state import AgentState
from app.config import settings
from app.database import create_conversation, load_messages, save_messages, update_conversation_title
from app.observability import record_request
from app.tools.registry import get_all_tools

logger = logging.getLogger(__name__)

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
- "FDA warnings for Warfarin" → call fda_drug_safety with drug_name="warfarin".
- "What are the side effects of metformin?" → call fda_drug_safety with drug_name="metformin".
- "Check FDA safety for Robert Chen's Warfarin" → call fda_drug_safety with \
drug_name="warfarin" and patient_identifier="Robert Chen".
- "Record blood pressure 120/80 for John Smith" → call record_vitals with \
systolic_bp=120, diastolic_bp=80, patient_identifier="John Smith".
- "FDA safety report for Warfarin and save to Robert Chen's record" → call fda_drug_safety \
with drug_name="warfarin", patient_identifier="Robert Chen", store_in_ehr=True.
- "Are there clinical trials for Robert Chen's conditions?" → call clinical_trials_search \
with patient_identifier="Robert Chen" to find trials matching his active conditions.
- "Find clinical trials for Type 2 Diabetes in Texas" → call clinical_trials_search with \
condition="Type 2 Diabetes", location="Texas".
- "Is amoxicillin safe for John Smith?" → call allergy_check with \
patient_identifier="John Smith", medications=["amoxicillin"] to cross-check against his \
documented Penicillin allergy (amoxicillin is a penicillin-class antibiotic).
- "Check John Smith's medications for allergy conflicts" → call allergy_check with \
patient_identifier="John Smith" to check all his current meds against his allergies.
- "Are any of Robert Chen's medications recalled?" → call drug_recall_check with \
patient_identifier="Robert Chen" to check all his meds for active FDA recalls.
- "Check if warfarin has been recalled" → call drug_recall_check with drug_name="warfarin".
- "Run a complete safety review for Robert Chen" → call patient_summary for his record, \
then drug_interaction_check on his meds, then allergy_check for allergy conflicts, \
then drug_recall_check for active recalls, then fda_drug_safety for any flagged drugs.
- "What preventive screenings is John Smith due for?" → call care_gap_analysis with \
patient_identifier="John Smith" to see all applicable USPSTF screenings and their status.
- "Mark colorectal cancer screening as completed for John Smith" → call update_care_gap \
with patient_identifier="John Smith", screening_name="Colorectal Cancer Screening", \
action="completed".
- "What screenings is Sarah Johnson overdue for?" → call care_gap_analysis to see her \
personalized screening recommendations based on age and sex.

Think step by step. After each tool result, decide if you need more information before \
giving a final answer. Combine results from multiple tools into a coherent response.

You have access to tools that query the OpenEMR FHIR R4 API for real patient data, \
the openFDA API for drug safety intelligence and recall data, ClinicalTrials.gov for \
recruiting studies, allergy-drug cross-checking, can record vitals back into the EHR, \
and analyze preventive care gaps based on USPSTF Grade A/B recommendations."""

# Maximum tool call iterations to prevent infinite loops
MAX_AGENT_ITERATIONS = 10

# Max conversation history messages to keep in context
MAX_HISTORY_MESSAGES = 50

# Agent response timeout (seconds)
RESPONSE_TIMEOUT = 120


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


def _classify_error(exc: Exception) -> str:
    """Classify an exception into a user-friendly error category."""
    msg = str(exc).lower()
    if "rate limit" in msg or "429" in msg:
        return "rate_limit"
    if "401" in msg or "403" in msg or "auth" in msg:
        return "auth"
    if "timeout" in msg:
        return "timeout"
    return "generic"


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
    is_new = False
    if not conversation_id:
        conversation_id = str(uuid.uuid4())
        is_new = True

    if is_new:
        create_conversation(conversation_id)
        history = []
    else:
        history = load_messages(conversation_id)
        if not history:
            create_conversation(conversation_id)

    # Truncate long conversation histories to prevent context overflow
    if len(history) > MAX_HISTORY_MESSAGES:
        history = history[-MAX_HISTORY_MESSAGES:]

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

    try:
        result = await asyncio.wait_for(
            _agent_graph.ainvoke(initial_state),
            timeout=RESPONSE_TIMEOUT,
        )
    except asyncio.TimeoutError:
        latency_ms = (time.time() - t_start) * 1000
        logger.error(
            "Agent timed out after %.1fs",
            RESPONSE_TIMEOUT,
            extra={"conversation_id": conversation_id, "latency_ms": latency_ms},
        )
        record_request(
            conversation_id=conversation_id,
            latency_ms=latency_ms,
            token_usage={"input": 0, "output": 0},
            tool_calls=[],
            error="timeout",
        )
        return {
            "response": (
                "I'm sorry, but my response took too long to generate. "
                "This can happen with complex queries. Please try again "
                "or simplify your question."
            ),
            "conversation_id": conversation_id,
            "tool_calls": [],
            "confidence": None,
            "disclaimers": [],
            "verification": {},
            "token_usage": {},
            "latency_ms": round(latency_ms, 1),
        }
    except Exception as exc:
        latency_ms = (time.time() - t_start) * 1000
        error_type = _classify_error(exc)
        logger.error(
            "Agent error (%s): %s",
            error_type,
            exc,
            exc_info=True,
            extra={"conversation_id": conversation_id},
        )
        record_request(
            conversation_id=conversation_id,
            latency_ms=latency_ms,
            token_usage={"input": 0, "output": 0},
            tool_calls=[],
            error=error_type,
        )

        user_messages = {
            "rate_limit": (
                "The AI service is currently experiencing high demand. "
                "Please wait a moment and try again."
            ),
            "auth": (
                "There's a configuration issue with the AI service. "
                "Please contact support."
            ),
            "timeout": (
                "The request timed out. Please try a simpler query."
            ),
            "generic": (
                "I encountered an unexpected error processing your request. "
                "Please try again. If the issue persists, contact support."
            ),
        }
        return {
            "response": user_messages.get(error_type, user_messages["generic"]),
            "conversation_id": conversation_id,
            "tool_calls": [],
            "confidence": None,
            "disclaimers": [],
            "verification": {},
            "token_usage": {},
            "latency_ms": round(latency_ms, 1),
        }

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

    # Persist conversation history to SQLite (exclude system prompt)
    updated_history = [m for m in ai_messages if not isinstance(m, SystemMessage)]
    try:
        save_messages(conversation_id, updated_history)
    except Exception:
        logger.exception("Failed to save conversation history — response still returned")

    # Auto-generate title from first user message
    if is_new:
        title = message[:80].strip()
        if len(message) > 80:
            title += "..."
        update_conversation_title(conversation_id, title)

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


def _sse(event: str, data: dict) -> str:
    """Format a Server-Sent Event string."""
    return f"data: {json.dumps({'event': event, 'data': data})}\n\n"


async def run_agent_stream(
    message: str, conversation_id: Optional[str] = None
) -> AsyncGenerator[str, None]:
    """Stream the agent's response as Server-Sent Events.

    Yields SSE-formatted strings with events:
      - thinking: agent started processing
      - tool_call: a tool is being called
      - token: incremental text token
      - done: final response with full metadata
      - error: an error occurred
    """
    # Get or create conversation
    is_new = False
    if not conversation_id:
        conversation_id = str(uuid.uuid4())
        is_new = True

    if is_new:
        create_conversation(conversation_id)
        history = []
    else:
        history = load_messages(conversation_id)
        if not history:
            create_conversation(conversation_id)

    if len(history) > MAX_HISTORY_MESSAGES:
        history = history[-MAX_HISTORY_MESSAGES:]

    messages = [SystemMessage(content=SYSTEM_PROMPT)] + history + [HumanMessage(content=message)]

    initial_state = {
        "messages": messages,
        "tool_calls_log": [],
        "confidence": None,
        "disclaimers": [],
    }

    yield _sse("thinking", {"conversation_id": conversation_id})

    t_start = time.time()
    full_text = ""
    tool_calls: list[dict] = []

    try:
        async for event in _agent_graph.astream_events(initial_state, version="v2"):
            kind = event.get("event", "")

            # Tool start events
            if kind == "on_tool_start":
                tool_name = event.get("name", "unknown")
                tool_input = event.get("data", {}).get("input", {})
                tool_calls.append({"tool": tool_name, "args": tool_input})
                yield _sse("tool_call", {"tool": tool_name, "args": tool_input})

            # Streaming tokens from the chat model
            elif kind == "on_chat_model_stream":
                chunk = event.get("data", {}).get("chunk")
                if chunk:
                    content = getattr(chunk, "content", "")
                    if content:
                        if isinstance(content, list):
                            text = "".join(
                                block.get("text", "") if isinstance(block, dict) else str(block)
                                for block in content
                            )
                        else:
                            text = content
                        if text:
                            full_text += text
                            yield _sse("token", {"text": text})

    except asyncio.TimeoutError:
        latency_ms = (time.time() - t_start) * 1000
        logger.error("Agent stream timed out", extra={"conversation_id": conversation_id})
        record_request(
            conversation_id=conversation_id,
            latency_ms=latency_ms,
            token_usage={"input": 0, "output": 0},
            tool_calls=tool_calls,
            error="timeout",
        )
        yield _sse("error", {"message": "Response timed out. Please try again."})
        return
    except Exception as exc:
        latency_ms = (time.time() - t_start) * 1000
        error_type = _classify_error(exc)
        logger.error("Agent stream error (%s): %s", error_type, exc, exc_info=True)
        record_request(
            conversation_id=conversation_id,
            latency_ms=latency_ms,
            token_usage={"input": 0, "output": 0},
            tool_calls=tool_calls,
            error=error_type,
        )
        yield _sse("error", {"message": "An error occurred. Please try again."})
        return

    latency_ms = (time.time() - t_start) * 1000

    # If no streamed text, fall back to getting the full response
    if not full_text:
        try:
            result = await _agent_graph.ainvoke(initial_state)
            ai_messages = result["messages"]
            fallback_content = ai_messages[-1].content
            full_text = "".join(
                b.get("text", "") if isinstance(b, dict) else str(b)
                for b in fallback_content
            ) if isinstance(fallback_content, list) else fallback_content
        except Exception:
            yield _sse("error", {"message": "Failed to get response."})
            return

    # Run verification
    from app.verification.pipeline import run_verification_pipeline

    verification_result = run_verification_pipeline(
        response_text=full_text,
        messages=[],
        tool_calls=tool_calls,
    )

    # Persist conversation
    try:
        # Build message list for saving: history + new user msg + assistant response
        from langchain_core.messages import AIMessage
        save_msgs = list(history) + [HumanMessage(content=message), AIMessage(content=full_text)]
        save_messages(conversation_id, save_msgs)
    except Exception:
        logger.exception("Failed to save streamed conversation history")

    if is_new:
        title = message[:80].strip()
        if len(message) > 80:
            title += "..."
        update_conversation_title(conversation_id, title)

    # Build disclaimers
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

    record_request(
        conversation_id=conversation_id,
        latency_ms=latency_ms,
        token_usage={"input": 0, "output": 0},
        tool_calls=tool_calls,
    )

    # Final done event with metadata
    yield _sse("done", {
        "response": full_text,
        "conversation_id": conversation_id,
        "tool_calls": tool_calls,
        "confidence": verification_result["confidence"],
        "disclaimers": disclaimers,
        "verification": verification_result.get("verification", {}),
        "latency_ms": round(latency_ms, 1),
    })
