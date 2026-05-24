"""Snowflake connection and query execution."""

from decimal import Decimal

import pandas as pd
import snowflake.connector
import streamlit as st


@st.cache_resource(show_spinner=False)
def get_connection():
    """Open a cached Snowflake connection using st.secrets['snowflake']."""
    cfg = st.secrets["snowflake"]
    return snowflake.connector.connect(
        account=cfg["account"],
        user=cfg["user"],
        password=cfg["password"],
        warehouse=cfg["warehouse"],
        database=cfg["database"],
        schema=cfg["schema"],
        role=cfg.get("role", "SYSADMIN"),
        client_session_keep_alive=True,
        login_timeout=60,
    )


def _coerce(value):
    if isinstance(value, Decimal):
        return float(value)
    return value


def run_query(sql: str) -> pd.DataFrame:
    """Execute SQL and return a DataFrame with lowercase columns and floats for decimals."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(sql)
        cols = [c[0].lower() for c in cur.description]
        rows = cur.fetchall()
    finally:
        cur.close()

    if not rows:
        return pd.DataFrame(columns=cols)

    coerced = [[_coerce(v) for v in row] for row in rows]
    return pd.DataFrame(coerced, columns=cols)


@st.cache_data(ttl=600, show_spinner=False)
def get_latest_quarter_nm() -> str:
    """Latest FILING_DATE in NM portfolio summary (ISO string)."""
    try:
        df = run_query(
            "SELECT MAX(FILING_DATE) AS latest "
            "FROM NM_ANALYTICS.RAW_MARTS.MART_PORTFOLIO_SUMMARY"
        )
        if df.empty or pd.isna(df.iloc[0]["latest"]):
            return "—"
        return str(df.iloc[0]["latest"])
    except Exception:
        return "—"


@st.cache_data(ttl=600, show_spinner=False)
def get_latest_quarter_berkshire() -> str:
    """Latest QUARTER label in Berkshire concentration metrics."""
    try:
        df = run_query(
            "SELECT QUARTER FROM BERKSHIRE_ANALYTICS.RAW_MARTS.MART_CONCENTRATION_METRICS "
            "ORDER BY FILING_DATE DESC LIMIT 1"
        )
        if df.empty:
            return "—"
        return str(df.iloc[0]["quarter"])
    except Exception:
        return "—"
