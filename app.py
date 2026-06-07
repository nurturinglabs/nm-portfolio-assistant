"""NM Portfolio Assistant — Streamlit chat UI for text-to-SQL portfolio analytics."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from nm_theme import (
    NM_NAVY,
    NM_YELLOW,
    NM_BLUE_MID,
    NM_BG_CARD,
    NM_TEXT_MAIN,
    NM_TEXT_MUTED,
    NM_BORDER,
    nm_header,
    nm_inject_css,
)
from snowflake_client import get_latest_quarter_berkshire, get_latest_quarter_nm
from text_to_sql import ask_portfolio_assistant

# -------------------- Brand constants (from nm_theme design system) --------------------
NM_BLUE = NM_BLUE_MID
BG_CARD = NM_BG_CARD
TEXT_MAIN = NM_TEXT_MAIN
TEXT_MUTED = NM_TEXT_MUTED
BORDER = NM_BORDER

SUGGESTED_QUESTIONS_NM = [
    "What are the top 5 holdings in Index 500 Stock Portfolio?",
    "Which portfolio has the highest concentration risk?",
    "Compare sector allocation: Balanced vs A/P Aggressive",
    "Which portfolios have more than 50% fixed income?",
]
SUGGESTED_QUESTIONS_BERKSHIRE = [
    "What new positions did Berkshire add in Q1 2026?",
    "How has Apple's weight changed over 8 quarters?",
    "Which sector grew most in the last quarter?",
    "What is the HHI concentration trend?",
]

WELCOME_MESSAGE = (
    "Hi! I can answer questions about NM's 5 portfolios (NPORT-P, Feb 2026) "
    "and Berkshire's 8 quarters of 13F holdings. What would you like to know?"
)

USER_INITIALS = "UN"


# -------------------- Page setup --------------------
st.set_page_config(
    page_title="NM · Portfolio Assistant",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)


def inject_css() -> None:
    """App-specific chat styling layered on top of the nm_theme design system.

    Brand colors, fonts, page background, full-width container, and the
    Streamlit chrome (header/footer/menu) are all handled by nm_inject_css().
    Only the chat-specific components live here.
    """
    st.markdown(
        f"""
        <style>
          /* keep room for the input row at the bottom */
          .block-container {{ padding-bottom: 5rem !important; }}

          /* -------- Chat bubbles -------- */
          .chat-row {{ display: flex; gap: 10px; margin: 14px 0; align-items: flex-start; }}
          .chat-row.user {{ justify-content: flex-end; }}

          .avatar {{
            width: 32px; height: 32px; border-radius: 50%;
            display: flex; align-items: center; justify-content: center;
            font-weight: 700; font-size: 12px; flex-shrink: 0;
          }}
          .avatar-nm {{ background: {NM_NAVY}; color: {NM_YELLOW}; }}
          .avatar-user {{ background: {NM_BLUE}; color: #fff; }}

          .bubble {{
            max-width: 78%;
            padding: 12px 16px;
            font-size: 14px;
            line-height: 1.55;
            color: {TEXT_MAIN};
          }}
          .bubble-assistant {{
            background: #F0F4FA;
            border-radius: 0 12px 12px 12px;
          }}
          .bubble-user {{
            background: {NM_NAVY};
            color: #fff;
            border-radius: 12px 0 12px 12px;
          }}

          /* -------- Insight chip -------- */
          .insight-chip {{
            display: inline-block;
            margin-top: 10px;
            padding: 8px 14px;
            background: #FFF8E6;
            color: #CC8800;
            border-radius: 8px;
            font-size: 13px;
            font-weight: 500;
            border: 1px solid #FFEBB3;
          }}

          /* -------- Data table card -------- */
          .data-card {{
            background: {BG_CARD};
            border: 1px solid {BORDER};
            border-radius: 8px;
            padding: 10px 12px;
            margin-top: 10px;
            overflow-x: auto;
          }}
          .data-card table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
          .data-card thead th {{
            text-align: left;
            font-size: 10px;
            text-transform: uppercase;
            letter-spacing: 0.6px;
            color: {TEXT_MUTED};
            padding: 8px 10px;
            border-bottom: 2px solid {NM_NAVY};
          }}
          .data-card tbody td {{
            padding: 8px 10px;
            border-bottom: 1px solid {BORDER};
            color: {TEXT_MAIN};
          }}
          .data-card tbody tr:last-child td {{ border-bottom: none; }}
          .data-card td.num {{ text-align: right; font-variant-numeric: tabular-nums; }}

          /* -------- Suggested-question chips -------- */
          .stButton > button {{
            background: #FFFFFF;
            color: {NM_NAVY};
            border: 1px solid {BORDER};
            border-radius: 999px;
            font-size: 12.5px;
            font-weight: 500;
            padding: 6px 14px;
            white-space: nowrap;
          }}
          .stButton > button:hover {{
            background: {NM_NAVY};
            color: {NM_YELLOW};
            border-color: {NM_NAVY};
          }}
          .ask-btn .stButton > button {{
            background: {NM_NAVY} !important;
            color: {NM_YELLOW} !important;
            border: none !important;
            border-radius: 20px !important;
            font-weight: 600;
            padding: 8px 22px;
          }}

          /* -------- Footer -------- */
          .nm-footer {{
            margin-top: 28px;
            padding: 10px 16px;
            border-top: 1px solid {BORDER};
            color: {TEXT_MUTED};
            font-size: 12px;
            text-align: center;
          }}

          /* -------- Misc -------- */
          .section-label {{
            font-size: 11px; text-transform: uppercase; letter-spacing: 0.7px;
            color: {TEXT_MUTED}; margin: 18px 0 8px 0; font-weight: 600;
          }}
          details summary {{ cursor: pointer; color: {NM_BLUE}; font-size: 12.5px; }}
        </style>
        """,
        unsafe_allow_html=True,
    )


# -------------------- State --------------------
def init_state() -> None:
    if "messages" not in st.session_state:
        st.session_state.messages = [
            {"role": "assistant", "content": WELCOME_MESSAGE,
             "results": None, "sql": "", "insight": ""}
        ]
    if "pending_question" not in st.session_state:
        st.session_state.pending_question = None


# -------------------- Helpers --------------------
def format_currency(val: float) -> str:
    if val is None or pd.isna(val):
        return ""
    av = abs(val)
    if av >= 1_000_000_000:
        return f"${val / 1_000_000_000:.2f}B"
    if av >= 1_000_000:
        return f"${val / 1_000_000:.2f}M"
    if av >= 1_000:
        return f"${val / 1_000:.1f}K"
    return f"${val:,.0f}"


def format_pct(val: float) -> str:
    if val is None or pd.isna(val):
        return ""
    return f"{val:.2f}%"


def is_numeric_col(series: pd.Series) -> bool:
    return pd.api.types.is_numeric_dtype(series)


def render_dataframe(df: pd.DataFrame) -> None:
    """Render a DataFrame as a styled HTML table inside a card."""
    if df is None or df.empty:
        return

    display_df = df.copy()
    for col in display_df.columns:
        lc = col.lower()
        if not is_numeric_col(display_df[col]):
            continue
        if "value_usd" in lc or "total_value" in lc or lc.endswith("_value") or "change_usd" in lc:
            display_df[col] = display_df[col].apply(format_currency)
        elif lc.endswith("_pct") or lc == "cumulative_pct" or "pct" in lc:
            display_df[col] = display_df[col].apply(format_pct)
        elif "millions" in lc:
            display_df[col] = display_df[col].apply(
                lambda v: "" if pd.isna(v) else f"${v:,.1f}M"
            )
        else:
            display_df[col] = display_df[col].apply(
                lambda v: "" if pd.isna(v) else (
                    f"{v:,.2f}" if isinstance(v, float) else f"{v:,}"
                )
            )

    show_df = display_df.head(10)
    extra = len(display_df) - len(show_df)

    numeric_cols = {c for c in df.columns if is_numeric_col(df[c])}

    head_cells = "".join(
        f"<th>{c.replace('_', ' ')}</th>" for c in show_df.columns
    )
    body_rows = []
    for _, row in show_df.iterrows():
        cells = "".join(
            f"<td class='{'num' if c in numeric_cols else ''}'>{row[c]}</td>"
            for c in show_df.columns
        )
        body_rows.append(f"<tr>{cells}</tr>")
    body_html = "".join(body_rows)

    st.markdown(
        f"<div class='data-card'><table>"
        f"<thead><tr>{head_cells}</tr></thead>"
        f"<tbody>{body_html}</tbody></table></div>",
        unsafe_allow_html=True,
    )
    if extra > 0:
        with st.expander(f"Show all {len(display_df)} rows"):
            st.dataframe(display_df, use_container_width=True, hide_index=True)


def render_assistant_message(msg: dict) -> None:
    narrative = msg.get("content", "")
    results = msg.get("results")
    insight = msg.get("insight", "")
    sql = msg.get("sql", "")
    error = msg.get("error")

    st.markdown(
        "<div class='chat-row'>"
        f"<div class='avatar avatar-nm'>NM</div>"
        f"<div class='bubble bubble-assistant'>{narrative}</div>"
        "</div>",
        unsafe_allow_html=True,
    )

    if error:
        st.error(f"Query error: {error}")

    if isinstance(results, pd.DataFrame) and not results.empty:
        render_dataframe(results)

    if insight:
        st.markdown(
            f"<div class='insight-chip'>💡 {insight}</div>",
            unsafe_allow_html=True,
        )

    if sql:
        with st.expander("▼ View SQL"):
            st.code(sql, language="sql")


def render_user_message(msg: dict) -> None:
    st.markdown(
        "<div class='chat-row user'>"
        f"<div class='bubble bubble-user'>{msg['content']}</div>"
        f"<div class='avatar avatar-user'>{USER_INITIALS}</div>"
        "</div>",
        unsafe_allow_html=True,
    )


# -------------------- Header --------------------
def render_header() -> None:
    try:
        nm_quarter = get_latest_quarter_nm()
        bk_quarter = get_latest_quarter_berkshire()
        quarter_label = f"NM {nm_quarter} · BRK {bk_quarter}"
    except Exception:
        quarter_label = "Live"

    nm_header(
        app_title="Portfolio Assistant",
        subtitle=f"{quarter_label} · Snowflake · Claude text-to-SQL",
        badges=[("● Live data", "green"), ("Snowflake", "blue")],
    )


# -------------------- Suggested questions --------------------
def render_suggestions() -> None:
    st.markdown("<div class='section-label'>Suggested questions</div>", unsafe_allow_html=True)
    cols = st.columns(4)
    for i, q in enumerate(SUGGESTED_QUESTIONS_NM):
        if cols[i].button(q, key=f"nm_sug_{i}"):
            st.session_state.pending_question = q
            st.rerun()
    cols = st.columns(4)
    for i, q in enumerate(SUGGESTED_QUESTIONS_BERKSHIRE):
        if cols[i].button(q, key=f"bk_sug_{i}"):
            st.session_state.pending_question = q
            st.rerun()


# -------------------- Input row --------------------
def render_input_row() -> None:
    with st.form("ask_form", clear_on_submit=True):
        c1, c2 = st.columns([8, 1])
        with c1:
            text = st.text_input(
                "question",
                placeholder="Ask anything about the portfolios...",
                label_visibility="collapsed",
            )
        with c2:
            st.markdown("<div class='ask-btn'>", unsafe_allow_html=True)
            submitted = st.form_submit_button("Ask")
            st.markdown("</div>", unsafe_allow_html=True)

        if submitted and text and text.strip():
            st.session_state.pending_question = text.strip()
            st.rerun()


# -------------------- Footer --------------------
def render_footer() -> None:
    st.markdown(
        "<div class='nm-footer'>"
        "🗄 Snowflake · RAW_MARTS &nbsp;|&nbsp; "
        "🔧 dbt · 46 tests passing &nbsp;|&nbsp; "
        "🤖 Claude · text-to-SQL"
        "</div>",
        unsafe_allow_html=True,
    )


# -------------------- Main --------------------
def main() -> None:
    nm_inject_css()
    inject_css()
    init_state()
    render_header()

    # Render existing chat history
    for msg in st.session_state.messages:
        if msg["role"] == "assistant":
            render_assistant_message(msg)
        else:
            render_user_message(msg)

    # Process any pending question (from suggestion chip or text input)
    if st.session_state.pending_question:
        question = st.session_state.pending_question
        st.session_state.pending_question = None
        st.session_state.messages.append({"role": "user", "content": question})

        render_user_message({"role": "user", "content": question})

        with st.spinner("Thinking..."):
            result = ask_portfolio_assistant(question, st.session_state.messages)

        assistant_msg = {
            "role": "assistant",
            "content": result.get("narrative") or "I couldn't produce an answer for that.",
            "results": result.get("results"),
            "sql": result.get("sql", ""),
            "insight": result.get("insight", ""),
            "error": result.get("error"),
        }
        st.session_state.messages.append(assistant_msg)
        render_assistant_message(assistant_msg)

    render_suggestions()
    render_input_row()
    render_footer()


if __name__ == "__main__":
    main()
