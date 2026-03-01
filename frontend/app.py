"""AgentForge Healthcare Assistant — Streamlit Chat UI."""

import streamlit as st

from api_client import (
    check_health,
    delete_conversation,
    get_conversation_history,
    get_conversations,
    send_feedback,
    send_message,
    stream_message,
)

# ── Page config ──────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="AgentForge Healthcare",
    page_icon="🏥",
    layout="wide",
)

# ── Session state init ───────────────────────────────────────────────────────

if "messages" not in st.session_state:
    st.session_state.messages = []
if "conversation_id" not in st.session_state:
    st.session_state.conversation_id = None

# ── Sidebar ──────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("🏥 AgentForge")
    st.caption("Healthcare AI Assistant powered by OpenEMR")

    # Health check
    health = check_health()
    if health.get("status") == "ok":
        st.success("Backend: Online", icon="✅")
    else:
        st.error(f"Backend: Offline — {health.get('detail', 'unknown')}", icon="❌")

    st.divider()

    # ── Conversation History ──
    st.subheader("Conversations")

    if st.button("+ New Conversation", use_container_width=True):
        st.session_state.messages = []
        st.session_state.conversation_id = None
        st.rerun()

    conversations = get_conversations()
    for conv in conversations:
        is_active = conv["id"] == st.session_state.conversation_id
        label = conv.get("title") or "Untitled"
        if len(label) > 40:
            label = label[:40] + "..."

        col1, col2 = st.columns([8, 1])
        with col1:
            btn_label = f"> {label}" if is_active else label
            if st.button(btn_label, key=f"conv_{conv['id']}", use_container_width=True, disabled=is_active):
                history = get_conversation_history(conv["id"])
                if "error" not in history:
                    st.session_state.conversation_id = conv["id"]
                    st.session_state.messages = [
                        {"role": m["role"], "content": m["content"], "metadata": {}, "feedback": None}
                        for m in history.get("messages", [])
                    ]
                    st.rerun()
        with col2:
            if st.button("x", key=f"del_{conv['id']}"):
                delete_conversation(conv["id"])
                if st.session_state.conversation_id == conv["id"]:
                    st.session_state.messages = []
                    st.session_state.conversation_id = None
                st.rerun()

    st.divider()

    # Verification detail toggle
    show_details = st.toggle("Show verification details", value=False)

    st.divider()

    # Quick-start examples
    st.subheader("Try an example")

    examples = [
        ("📋 Patient Summary", "Get patient summary for John Smith"),
        ("💊 Drug Interactions", "Check Robert Chen's medications for drug interactions"),
        ("🩺 Symptom Check", "What could cause chest pain and shortness of breath?"),
        ("👨‍⚕️ Find a Doctor", "Find me a cardiologist"),
        ("📅 Appointments", "What appointments are available with Dr. Wilson on 2026-02-25?"),
        ("🛡️ FDA Safety", "Look up FDA safety information for Warfarin"),
        ("❤️ Record Vitals", "Record blood pressure 120/80 and heart rate 72 for John Smith"),
    ]

    for label, prompt in examples:
        if st.button(label, use_container_width=True):
            st.session_state.pending_example = prompt

    st.divider()
    st.caption(
        "Built with LangGraph + OpenEMR FHIR API\n\n"
        "⚠️ For educational purposes only.\n"
        "Not for clinical decision-making."
    )


# ── Helper: render metadata ──────────────────────────────────────────────────

def render_metadata(metadata: dict, show_verification: bool) -> None:
    """Render confidence badge, disclaimers, and optional verification details."""
    confidence = metadata.get("confidence")
    disclaimers = metadata.get("disclaimers", [])
    tool_calls = metadata.get("tool_calls", [])
    verification = metadata.get("verification", {})
    token_usage = metadata.get("token_usage", {})
    latency_ms = metadata.get("latency_ms")

    # Confidence badge
    if confidence is not None:
        if confidence >= 0.7:
            color, label = "green", "High"
        elif confidence >= 0.4:
            color, label = "orange", "Moderate"
        else:
            color, label = "red", "Low"
        st.markdown(
            f"**Confidence:** :{color}[{label} ({confidence:.0%})]"
        )

    # Tool calls summary
    if tool_calls:
        tools_used = ", ".join(tc["tool"] for tc in tool_calls)
        st.caption(f"🔧 Tools used: {tools_used}")

    # Latency and token usage
    perf_parts = []
    if latency_ms is not None:
        perf_parts.append(f"⏱ {latency_ms/1000:.1f}s")
    if token_usage:
        total_tok = token_usage.get("input", 0) + token_usage.get("output", 0)
        if total_tok > 0:
            perf_parts.append(f"🪙 {total_tok:,} tokens")
    if perf_parts:
        st.caption(" · ".join(perf_parts))

    # Disclaimers
    for disclaimer in disclaimers:
        st.warning(disclaimer, icon="⚠️")

    # Verification details (expandable)
    if show_verification and verification:
        with st.expander("Verification Details"):
            # Drug safety
            drug = verification.get("drug_safety", {})
            if drug:
                icon = "✅" if drug.get("passed") else "❌"
                st.markdown(f"**Drug Safety:** {icon}")
                for flag in drug.get("flags", []):
                    st.error(
                        f"**{flag['severity'].upper()}**: {flag['drugs'][0]} + "
                        f"{flag['drugs'][1]} — {flag['issue']}"
                    )

            # Confidence scoring breakdown
            scoring = verification.get("confidence_scoring", {})
            if scoring:
                factors = scoring.get("factors", {})
                cols = st.columns(4)
                labels = [
                    ("Tools", "tools_used"),
                    ("Data", "data_richness"),
                    ("Hedging", "response_hedging"),
                    ("Errors", "tool_error_rate"),
                ]
                for col, (lbl, key) in zip(cols, labels):
                    val = factors.get(key, 0)
                    col.metric(lbl, f"{val:.0%}")

            # Claim verification
            claims = verification.get("claim_verification", {})
            if claims and claims.get("total_claims", 0) > 0:
                grounded = claims.get("grounded_claims", 0)
                total = claims.get("total_claims", 0)
                rate = claims.get("grounding_rate", 0)
                st.markdown(
                    f"**Claims grounded:** {grounded}/{total} ({rate:.0%})"
                )
                for detail in claims.get("details", []):
                    icon = "✅" if detail["grounded"] else "⚠️"
                    source = f" — *{detail['source_tool']}*" if detail.get("source_tool") else ""
                    st.markdown(f"  {icon} {detail['claim']}{source}")

            # Overall safety
            overall = verification.get("overall_safe")
            if overall is not None:
                st.markdown(
                    f"**Overall:** {'✅ Safe' if overall else '⚠️ Review needed'}"
                )


# ── Helper: feedback buttons ─────────────────────────────────────────────────

def render_feedback_buttons(msg_idx: int) -> None:
    """Render thumbs-up / thumbs-down buttons for a message."""
    existing = st.session_state.messages[msg_idx].get("feedback")
    if existing:
        icon = "👍" if existing == "up" else "👎"
        st.caption(f"Feedback: {icon}")
        return

    col1, col2, _ = st.columns([1, 1, 10])
    with col1:
        if st.button("👍", key=f"up_{msg_idx}"):
            send_feedback(st.session_state.conversation_id, "up")
            st.session_state.messages[msg_idx]["feedback"] = "up"
            st.rerun()
    with col2:
        if st.button("👎", key=f"down_{msg_idx}"):
            send_feedback(st.session_state.conversation_id, "down")
            st.session_state.messages[msg_idx]["feedback"] = "down"
            st.rerun()


# ── Helper: send and display (streaming) ────────────────────────────────────

def send_and_display(user_prompt: str) -> None:
    """Send a message to the backend and stream the response."""
    st.session_state.messages.append({"role": "user", "content": user_prompt})

    with st.chat_message("user"):
        st.markdown(user_prompt)

    with st.chat_message("assistant"):
        status_placeholder = st.empty()
        text_placeholder = st.empty()
        status_placeholder.caption("Thinking...")

        full_text = ""
        tool_calls_seen: list[dict] = []
        final_metadata: dict = {}
        had_error = False

        try:
            for event in stream_message(user_prompt, st.session_state.conversation_id):
                evt_type = event.get("event", "")
                evt_data = event.get("data", {})

                if evt_type == "thinking":
                    st.session_state.conversation_id = evt_data.get(
                        "conversation_id", st.session_state.conversation_id
                    )

                elif evt_type == "tool_call":
                    tool_name = evt_data.get("tool", "unknown")
                    tool_calls_seen.append(evt_data)
                    status_placeholder.caption(f"Calling tool: {tool_name}...")

                elif evt_type == "token":
                    text = evt_data.get("text", "")
                    full_text += text
                    text_placeholder.markdown(full_text + "▌")

                elif evt_type == "done":
                    full_text = evt_data.get("response", full_text)
                    final_metadata = {
                        "confidence": evt_data.get("confidence"),
                        "disclaimers": evt_data.get("disclaimers", []),
                        "tool_calls": evt_data.get("tool_calls", tool_calls_seen),
                        "verification": evt_data.get("verification", {}),
                        "token_usage": evt_data.get("token_usage", {}),
                        "latency_ms": evt_data.get("latency_ms"),
                    }

                elif evt_type == "error":
                    had_error = True
                    error_msg = evt_data.get("message", "Unknown error")
                    status_placeholder.empty()
                    st.error(f"Error: {error_msg}")

            # Clear status and show final text
            status_placeholder.empty()

            if not had_error:
                text_placeholder.markdown(full_text)
                render_metadata(final_metadata, show_details)

                msg_idx = len(st.session_state.messages)
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": full_text,
                    "metadata": final_metadata,
                    "feedback": None,
                })
                render_feedback_buttons(msg_idx)

        except Exception as e:
            status_placeholder.empty()
            # Fall back to non-streaming on any streaming error
            try:
                result = send_message(user_prompt, st.session_state.conversation_id)
                response = result.get("response", "No response received.")
                st.session_state.conversation_id = result.get("conversation_id")

                text_placeholder.markdown(response)

                metadata = {
                    "confidence": result.get("confidence"),
                    "disclaimers": result.get("disclaimers", []),
                    "tool_calls": result.get("tool_calls", []),
                    "verification": result.get("verification", {}),
                    "token_usage": result.get("token_usage", {}),
                    "latency_ms": result.get("latency_ms"),
                }
                render_metadata(metadata, show_details)

                msg_idx = len(st.session_state.messages)
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": response,
                    "metadata": metadata,
                    "feedback": None,
                })
                render_feedback_buttons(msg_idx)

            except Exception as fallback_error:
                st.error(f"Error communicating with backend: {fallback_error}")


# ── Main chat area ───────────────────────────────────────────────────────────

st.title("Healthcare Assistant")

# Display conversation history
for idx, msg in enumerate(st.session_state.messages):
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

        # Show metadata for assistant messages
        if msg["role"] == "assistant" and msg.get("metadata"):
            render_metadata(msg["metadata"], show_details)
            render_feedback_buttons(idx)

# ── Handle pending example from sidebar ──────────────────────────────────────

if "pending_example" in st.session_state:
    user_prompt = st.session_state.pop("pending_example")
    send_and_display(user_prompt)

# ── Chat input ───────────────────────────────────────────────────────────────

if prompt := st.chat_input("Ask about patients, medications, symptoms, or providers..."):
    send_and_display(prompt)
