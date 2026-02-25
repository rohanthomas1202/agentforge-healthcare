"""Agent state definition for LangGraph.

The state is the data that flows through the graph. Each node in the graph
can read and update the state. LangGraph manages state persistence across turns.
"""

from typing import Annotated, Any, Optional, Sequence

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class AgentState(dict):
    """State that flows through the LangGraph agent.

    Attributes:
        messages: Conversation history (LangGraph manages append via add_messages).
        tool_calls_log: Record of all tool invocations for observability.
        confidence: Current response confidence score (0-100).
        disclaimers: Safety disclaimers to include in the response.
    """

    messages: Annotated[Sequence[BaseMessage], add_messages]
    tool_calls_log: list[dict[str, Any]]
    confidence: Optional[float]
    disclaimers: list[str]
