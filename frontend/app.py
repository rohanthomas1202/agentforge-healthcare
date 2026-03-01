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
if "streaming" not in st.session_state:
    st.session_state.streaming = False

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

    # Verification detail toggle (disabled during streaming to prevent rerun)
    show_details = st.toggle("Show verification details", value=False, disabled=st.session_state.streaming)

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
        ("🔍 Care Gaps", "What preventive screenings is John Smith due for?"),
        ("🏥 Insurance", "Is Metformin covered by John Smith's insurance?"),
        ("🧪 Lab Results", "Show me John Smith's lab results"),
    ]

    for label, prompt in examples:
        if st.button(label, use_container_width=True, disabled=st.session_state.streaming):
            st.session_state.pending_example = prompt

    st.divider()

    # ── Available Tools Reference ──
    with st.expander("🧰 Available Tools (14)", expanded=False):
        tools_info = [
            ("📋", "patient_summary", "Full patient record lookup"),
            ("💊", "drug_interaction_check", "Check drug-drug interactions"),
            ("🩺", "symptom_lookup", "Symptom → possible conditions"),
            ("👨‍⚕️", "provider_search", "Find providers by specialty"),
            ("📅", "appointment_availability", "Check appointment slots"),
            ("🛡️", "fda_drug_safety", "FDA adverse event reports"),
            ("⚠️", "drug_recall_check", "FDA recall alerts"),
            ("🔬", "clinical_trials_search", "ClinicalTrials.gov search"),
            ("💉", "allergy_check", "Drug-allergy cross-check"),
            ("❤️", "record_vitals", "Write vitals to EHR"),
            ("🔍", "care_gap_analysis", "USPSTF preventive care gaps"),
            ("✅", "update_care_gap", "Update screening status"),
            ("🏥", "insurance_coverage_check", "Formulary & copay lookup"),
            ("🧪", "lab_results_analysis", "Lab trends & reference ranges"),
        ]
        for icon, name, desc in tools_info:
            st.markdown(f"{icon} **{name}**  \n{desc}", unsafe_allow_html=True)

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


# ── Helper: feedback buttons (fragment to avoid full-page rerun) ─────────────

@st.fragment
def render_feedback_buttons(msg_idx: int) -> None:
    """Render thumbs-up / thumbs-down buttons for a message.

    Uses @st.fragment so clicking feedback doesn't trigger a full rerun,
    which would kill any in-progress streaming response.
    """
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
    with col2:
        if st.button("👎", key=f"down_{msg_idx}"):
            send_feedback(st.session_state.conversation_id, "down")
            st.session_state.messages[msg_idx]["feedback"] = "down"


# ── Helper: send and display (streaming) ────────────────────────────────────

def send_and_display(user_prompt: str) -> None:
    """Send a message to the backend and stream the response.

    Saves the assistant message to session state incrementally so that
    if a Streamlit rerun occurs mid-stream (e.g. widget click), the
    partial response is preserved and rendered from history.
    """
    st.session_state.messages.append({"role": "user", "content": user_prompt})

    # Pre-allocate the assistant message slot so reruns don't lose it
    assistant_idx = len(st.session_state.messages)
    st.session_state.messages.append({
        "role": "assistant",
        "content": "",
        "metadata": {},
        "feedback": None,
    })
    st.session_state.streaming = True

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
                    # Save partial content so reruns preserve it
                    st.session_state.messages[assistant_idx]["content"] = full_text

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
                    # Save final content and metadata
                    st.session_state.messages[assistant_idx]["content"] = full_text
                    st.session_state.messages[assistant_idx]["metadata"] = final_metadata

                elif evt_type == "error":
                    had_error = True
                    error_msg = evt_data.get("message", "Unknown error")
                    status_placeholder.empty()
                    st.error(f"Error: {error_msg}")

            # Clear status and show final text
            status_placeholder.empty()
            st.session_state.streaming = False

            if not had_error:
                text_placeholder.markdown(full_text)
                render_metadata(final_metadata, show_details)
                render_feedback_buttons(assistant_idx)
            else:
                # Remove the placeholder message on error
                if st.session_state.messages[assistant_idx]["content"] == "":
                    st.session_state.messages.pop(assistant_idx)

        except Exception as e:
            status_placeholder.empty()
            st.session_state.streaming = False
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
                # Update the pre-allocated slot
                st.session_state.messages[assistant_idx]["content"] = response
                st.session_state.messages[assistant_idx]["metadata"] = metadata

                render_metadata(metadata, show_details)
                render_feedback_buttons(assistant_idx)

            except Exception as fallback_error:
                st.error(f"Error communicating with backend: {fallback_error}")
                # Remove empty placeholder on total failure
                if st.session_state.messages[assistant_idx]["content"] == "":
                    st.session_state.messages.pop(assistant_idx)


# ── Custom CSS for suggestion cards ─────────────────────────────────────────

st.markdown("""
<style>
    /* Style the suggestion card buttons */
    div[data-testid="stVerticalBlock"] > div:has(> div > button[kind="secondary"][key^="card_"]) button,
    button[key^="card_"] {
        min-height: 90px !important;
        white-space: pre-wrap !important;
        text-align: left !important;
        border: 1px solid rgba(250, 250, 250, 0.1) !important;
    }
    /* Disclaimer banner */
    .disclaimer-banner {
        background: linear-gradient(90deg, #1a3a4a, #1a2a3a);
        border: 1px solid #2a5a6a;
        border-radius: 8px;
        padding: 10px 16px;
        margin-bottom: 16px;
        font-size: 0.85em;
        color: #e0e0e0;
    }
    .disclaimer-banner strong { color: #ffa726; }
</style>
""", unsafe_allow_html=True)

# ── Main chat area ───────────────────────────────────────────────────────────

st.title("Healthcare Assistant")

# Disclaimer banner
st.markdown(
    '<div class="disclaimer-banner">'
    '<strong>Educational purposes only.</strong> '
    'Not a substitute for professional medical advice. '
    'If experiencing a medical emergency, call 911 immediately.'
    '</div>',
    unsafe_allow_html=True,
)

# Display conversation history
for idx, msg in enumerate(st.session_state.messages):
    # Skip empty assistant placeholders from interrupted streams
    if msg["role"] == "assistant" and not msg.get("content"):
        continue

    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

        # Show metadata for assistant messages
        if msg["role"] == "assistant" and msg.get("metadata"):
            render_metadata(msg["metadata"], show_details)
            if not st.session_state.streaming:
                render_feedback_buttons(idx)

# ── Suggested query cards (shown when no messages yet) ───────────────────────

if not st.session_state.messages and "pending_example" not in st.session_state:
    st.markdown("#### What can I help you with?")
    st.caption("Click a card below or type your own question.")

    suggested_queries = [
        ("📋", "Clinical Decision Report",
         "Comprehensive multi-tool analysis",
         "Give me a full clinical decision report for John Smith including medications, interactions, FDA recalls, and care gaps"),
        ("💊", "Drug Interactions",
         "Check interaction between medications",
         "Check for interactions between Warfarin, Aspirin, and Metoprolol"),
        ("🩺", "Symptom Triage",
         "I have a persistent headache with fever",
         "What conditions could cause a persistent headache with fever?"),
        ("👨\u200d⚕️", "Find a Provider",
         "Find me a cardiologist",
         "Find me a cardiologist and check their availability"),
        ("🏥", "Insurance",
         "Does Blue Cross cover my medication?",
         "Is Metformin covered by John Smith's insurance?"),
        ("🧪", "Lab Results",
         "Scan patient lab values and trends",
         "Show me John Smith's lab results and flag any abnormal values"),
    ]

    # 2 rows of 3 cards
    for row_start in range(0, len(suggested_queries), 3):
        cols = st.columns(3)
        for col, (icon, title, desc, query) in zip(cols, suggested_queries[row_start:row_start + 3]):
            with col:
                if st.button(
                    f"{icon} **{title}**\n\n{desc}",
                    key=f"card_{title}",
                    use_container_width=True,
                ):
                    st.session_state.pending_example = query

    if "pending_example" in st.session_state:
        st.rerun()

# ── Handle pending example from sidebar ──────────────────────────────────────

if "pending_example" in st.session_state:
    user_prompt = st.session_state.pop("pending_example")
    send_and_display(user_prompt)

# ── Chat input ───────────────────────────────────────────────────────────────

if prompt := st.chat_input("Ask about patients, medications, symptoms, or providers..."):
    send_and_display(prompt)
