"""AgentForge Healthcare Assistant — Streamlit Chat UI."""

import streamlit as st

from api_client import check_health, send_message

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
    ]

    for label, prompt in examples:
        if st.button(label, use_container_width=True):
            st.session_state.pending_example = prompt

    st.divider()

    # New conversation button
    if st.button("🔄 New Conversation", use_container_width=True):
        st.session_state.messages = []
        st.session_state.conversation_id = None
        st.rerun()

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


# ── Helper: send and display ─────────────────────────────────────────────────

def send_and_display(user_prompt: str) -> None:
    """Send a message to the backend and display the response."""
    st.session_state.messages.append({"role": "user", "content": user_prompt})

    with st.chat_message("user"):
        st.markdown(user_prompt)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                result = send_message(user_prompt, st.session_state.conversation_id)
                response = result.get("response", "No response received.")
                st.session_state.conversation_id = result.get("conversation_id")

                st.markdown(response)

                metadata = {
                    "confidence": result.get("confidence"),
                    "disclaimers": result.get("disclaimers", []),
                    "tool_calls": result.get("tool_calls", []),
                    "verification": result.get("verification", {}),
                }

                render_metadata(metadata, show_details)

                st.session_state.messages.append({
                    "role": "assistant",
                    "content": response,
                    "metadata": metadata,
                })

            except Exception as e:
                st.error(f"Error communicating with backend: {e}")


# ── Main chat area ───────────────────────────────────────────────────────────

st.title("Healthcare Assistant")

# Display conversation history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

        # Show metadata for assistant messages
        if msg["role"] == "assistant" and msg.get("metadata"):
            render_metadata(msg["metadata"], show_details)

# ── Handle pending example from sidebar ──────────────────────────────────────

if "pending_example" in st.session_state:
    user_prompt = st.session_state.pop("pending_example")
    send_and_display(user_prompt)

# ── Chat input ───────────────────────────────────────────────────────────────

if prompt := st.chat_input("Ask about patients, medications, symptoms, or providers..."):
    send_and_display(prompt)
