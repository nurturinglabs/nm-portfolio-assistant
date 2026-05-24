"""Claude-powered text-to-SQL: generates SQL, runs it, returns narrative + insight."""

import json
import re
from typing import Optional

import anthropic
import streamlit as st

from schema_context import SCHEMA_CONTEXT
from snowflake_client import run_query

CLAUDE_MODEL = "claude-sonnet-4-20250514"
MAX_RETRIES = 2

SYSTEM_PROMPT = f"""You are a portfolio analytics assistant for Northwestern Mutual's investment team.
You have access to two Snowflake databases:

1. NM_ANALYTICS.RAW_MARTS — NM Series Fund portfolios from SEC NPORT-P filings (Feb 2026)
   Tables: MART_PORTFOLIO_SUMMARY, MART_RISK_METRICS, MART_SECTOR_ALLOCATION, MART_TOP_HOLDINGS

2. BERKSHIRE_ANALYTICS.RAW_MARTS — Berkshire Hathaway 13F holdings (Q2 2024 – Q1 2026)
   Tables: MART_CONCENTRATION_METRICS, MART_DRIFT_ANALYSIS, MART_PORTFOLIO_SNAPSHOT, MART_SECTOR_ROTATION

{SCHEMA_CONTEXT}

RULES:
- Always generate valid Snowflake SQL.
- Always include LIMIT 50 unless the user asks for all records.
- Never use SELECT * — always name columns explicitly.
- Always CAST numeric columns to FLOAT when doing arithmetic.
- Always fully qualify table names as DATABASE.SCHEMA.TABLE.
- Use ILIKE '%term%' for fuzzy text matches (e.g. company or sector names).
- Format currency values in billions (B) or millions (M) in your narrative.
- Never make up data — only answer from actual query results.
- ALWAYS generate SQL — never answer from general knowledge or training data.
- If you think you know the answer without querying, you are WRONG — always query.
- Every response MUST include a "sql" key with a real executable query.
- "I don't know" is acceptable — "here is what it probably is" is NOT acceptable.
- If a question is ambiguous, pick the most reasonable interpretation and query it.
- NEVER hardcode dates — always use a subquery to get the latest date dynamically:
    NM latest date:           (SELECT MAX(FILING_DATE) FROM NM_ANALYTICS.RAW_MARTS.MART_TOP_HOLDINGS)
    Berkshire latest quarter: (SELECT MAX(QUARTER) FROM BERKSHIRE_ANALYTICS.RAW_MARTS.MART_DRIFT_ANALYSIS)
- If a query returns 0 rows, tell the user the query returned no results and suggest why.
- Before filtering by date, always use MAX(FILING_DATE) subquery — never hardcode a date string.
- If a question genuinely cannot be answered from the available tables, set "sql" to ""
  and explain clearly in the narrative why (do NOT fabricate an answer).

DATABASE ROUTING RULES (critical — resolve this first before writing any SQL):

STEP 1 — Identify which database the question is about:
- Keywords → NM_ANALYTICS: "NM", "Northwestern Mutual", "portfolio", "series fund",
  "Index 500", "Index 400", "Balanced Portfolio", "A/P", "Active/Passive",
  "NPORT", "sector allocation", "fixed income", "bond", "equity portfolio".
- Keywords → BERKSHIRE_ANALYTICS: "Berkshire", "Buffett", "Warren", "13F",
  "Apple", "Coca-Cola", "American Express", "AXP", "KO", "OXY", "Occidental",
  "Chevron", "drift", "HHI", "concentration index", "quarter", "Q1", "Q2", "Q3", "Q4".
- If the question mentions both → query both databases and combine the narrative.
- If ambiguous → default to NM_ANALYTICS and note the assumption.

STEP 2 — Select the right table within that database:

TABLE SELECTION RULES (critical):
- "over time", "trend", "changed", "historical", "quarters", "last N quarters" → time-series tables
    Berkshire time-series:     MART_DRIFT_ANALYSIS (one row per holding per quarter, all 8 quarters)
    Berkshire concentration:   MART_CONCENTRATION_METRICS (one row per quarter)
    Berkshire sector trends:   MART_SECTOR_ROTATION (one row per sector per quarter)
- "current", "latest", "now", "today", "snapshot" → snapshot tables
    Berkshire current state:   MART_PORTFOLIO_SNAPSHOT (latest quarter only)
    NM current state:          MART_TOP_HOLDINGS, MART_PORTFOLIO_SUMMARY
- NM "sector allocation" questions → MART_SECTOR_ALLOCATION (it has SECTOR_NAME).
- NM "top holdings" / individual-stock questions → MART_TOP_HOLDINGS.
- NM holdings do NOT have individual sector tags — use MART_SECTOR_ALLOCATION only for sector-level totals.
- "Apple weight over 8 quarters" →
    SELECT QUARTER, PCT_OF_PORTFOLIO, VALUE_USD
    FROM BERKSHIRE_ANALYTICS.RAW_MARTS.MART_DRIFT_ANALYSIS
    WHERE ISSUER_NAME ILIKE '%APPLE%'
    ORDER BY FILING_DATE;
- "Top tech holding in NM" → CANNOT be answered directly (MART_TOP_HOLDINGS has no sector column).
  Explain this limitation and suggest what IS available (e.g. tech sector totals from MART_SECTOR_ALLOCATION).

RESPONSE FORMAT:
Return ONLY a single JSON object with these three keys (no prose before or after):
  "sql":       the SQL query you want to execute (or "" only if truly not answerable)
  "narrative": 2–3 sentence plain-English answer (you will refine this after seeing results)
  "insight":   one key takeaway starting with a verb (e.g. "Driven by...", "Notable shift...")
"""

FOLLOWUP_PROMPT_TEMPLATE = """You previously generated SQL for the user's question. Here are the actual query results.

Original question: {question}
SQL executed: {sql}
Result rows (up to 25 shown): {results_preview}
Total row count: {row_count}

Now produce the FINAL JSON response using the actual numbers from the results.
Return ONLY a JSON object with keys "sql", "narrative", "insight".
- "sql": echo the SQL exactly as run
- "narrative": 2–3 sentences using real numbers from the results, formatted in B/M
- "insight": one verb-led sentence highlighting the most important finding
"""

RETRY_PROMPT_TEMPLATE = """The SQL you generated failed with this error:

SQL: {sql}
Error: {error}

Fix the SQL and return a new JSON response with keys "sql", "narrative", "insight".
Return ONLY the JSON object."""


@st.cache_resource(show_spinner=False)
def _get_client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=st.secrets["anthropic"]["api_key"])


def _extract_json(text: str) -> Optional[dict]:
    """Pull the first JSON object out of Claude's response."""
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


def _call_claude(messages: list) -> str:
    client = _get_client()
    resp = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=1500,
        system=SYSTEM_PROMPT,
        messages=messages,
    )
    return resp.content[0].text


def ask_portfolio_assistant(question: str, chat_history: list) -> dict:
    """Convert NL question -> SQL -> Snowflake results -> narrative answer.

    Returns dict with keys: sql, results (DataFrame), narrative, insight, error.
    """
    # Build conversation history for Claude (text-only, last 6 exchanges to bound tokens)
    history_msgs = []
    for turn in chat_history[-12:]:
        role = turn.get("role")
        if role not in ("user", "assistant"):
            continue
        content = turn.get("content") or turn.get("narrative") or ""
        if not content:
            continue
        history_msgs.append({"role": role, "content": str(content)})

    messages = history_msgs + [{"role": "user", "content": question}]

    # --- Round 1: ask Claude for SQL ---
    try:
        raw = _call_claude(messages)
    except Exception as exc:
        return {"sql": "", "results": None, "narrative": "",
                "insight": "", "error": f"Claude API error: {exc}"}

    parsed = _extract_json(raw)
    if not parsed:
        return {"sql": "", "results": None,
                "narrative": raw.strip(), "insight": "",
                "error": "Could not parse JSON from model response."}

    sql = (parsed.get("sql") or "").strip()
    narrative = parsed.get("narrative", "") or ""
    insight = parsed.get("insight", "") or ""

    if not sql:
        # Claude declined to answer with SQL
        return {"sql": "", "results": None, "narrative": narrative,
                "insight": insight, "error": None}

    # --- Execute SQL, retrying up to MAX_RETRIES on failure ---
    df = None
    last_error = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            df = run_query(sql)
            last_error = None
            break
        except Exception as exc:
            last_error = str(exc)
            if attempt == MAX_RETRIES:
                break
            retry_msg = RETRY_PROMPT_TEMPLATE.format(sql=sql, error=last_error)
            messages = messages + [
                {"role": "assistant", "content": raw},
                {"role": "user", "content": retry_msg},
            ]
            try:
                raw = _call_claude(messages)
            except Exception as call_exc:
                last_error = f"Claude API error during retry: {call_exc}"
                break
            parsed = _extract_json(raw) or {}
            sql = (parsed.get("sql") or sql).strip()
            narrative = parsed.get("narrative", narrative) or narrative
            insight = parsed.get("insight", insight) or insight

    if last_error is not None:
        return {"sql": sql, "results": None, "narrative": narrative,
                "insight": insight, "error": last_error}

    # --- Round 2: refine narrative with the real results ---
    if df is not None and not df.empty:
        preview = df.head(25).to_dict(orient="records")
        followup = FOLLOWUP_PROMPT_TEMPLATE.format(
            question=question,
            sql=sql,
            results_preview=json.dumps(preview, default=str),
            row_count=len(df),
        )
        try:
            followup_raw = _call_claude(
                messages + [
                    {"role": "assistant", "content": raw},
                    {"role": "user", "content": followup},
                ]
            )
            followup_parsed = _extract_json(followup_raw)
            if followup_parsed:
                narrative = followup_parsed.get("narrative", narrative) or narrative
                insight = followup_parsed.get("insight", insight) or insight
        except Exception:
            # Keep the original narrative if refinement fails
            pass
    elif df is not None and df.empty:
        narrative = narrative or "No data found for that query."
        insight = insight or ""

    return {"sql": sql, "results": df, "narrative": narrative,
            "insight": insight, "error": None}
