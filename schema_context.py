"""Full Snowflake schema context injected into Claude's system prompt."""

SCHEMA_CONTEXT = """
========================================================================
DATABASE 1: NM_ANALYTICS.RAW_MARTS
Northwestern Mutual Series Fund portfolios — SEC NPORT-P filings (Feb 2026)
========================================================================

Available portfolio names (do NOT invent others):
  - Index 500 Stock Portfolio
  - Index 400 Stock Portfolio
  - Balanced Portfolio
  - Active/Passive Balanced Portfolio
  - Active/Passive Aggressive Portfolio

------------------------------------------------------------------------
TABLE: NM_ANALYTICS.RAW_MARTS.MART_PORTFOLIO_SUMMARY
Grain: one row per portfolio per filing date.
Use for: AUM, risk profile, equity/fixed income split, top sector.

Columns:
  FILING_DATE              DATE    — Filing date
  PORTFOLIO_NAME           TEXT    — Full portfolio name
  TOTAL_VALUE_USD          NUMBER  — Total portfolio value in USD
  AUM_MILLIONS             NUMBER  — AUM in millions
  TOTAL_HOLDINGS           NUMBER  — Number of holdings
  TOP_5_CONCENTRATION_PCT  FLOAT   — % held by top 5 holdings
  LARGEST_HOLDING_PCT      FLOAT   — % held by largest single holding
  NM_INTERNAL_FUND_COUNT   NUMBER  — Count of internal NM fund holdings
  TOP_SECTOR               TEXT    — Name of largest sector
  TOP_SECTOR_PCT           NUMBER  — % in largest sector
  TOTAL_EQUITY_PCT         NUMBER  — Total equity allocation %
  TOTAL_FIXED_INCOME_PCT   NUMBER  — Total fixed income allocation %
  RISK_PROFILE             TEXT    — Risk category (Aggressive, Balanced, etc.)

Sample questions:
  - "Which portfolio has highest AUM?"
  - "What is the risk profile of each portfolio?"
  - "Which portfolio has most fixed income exposure?"

------------------------------------------------------------------------
TABLE: NM_ANALYTICS.RAW_MARTS.MART_RISK_METRICS
Grain: one row per portfolio per filing date.
Use for: beta, volatility, duration, concentration risk.

Columns:
  FILING_DATE              DATE    — Filing date
  PORTFOLIO_NAME           TEXT    — Full portfolio name
  AUM_MILLIONS             NUMBER  — AUM in millions
  RISK_PROFILE             TEXT    — Risk category
  TOP_5_CONCENTRATION_PCT  FLOAT   — Top 5 concentration %
  LARGEST_HOLDING_PCT      FLOAT   — Largest holding %
  TOTAL_EQUITY_PCT         NUMBER  — Equity %
  TOTAL_FIXED_INCOME_PCT   NUMBER  — Fixed income %
  EQUITY_BETA_PROXY        NUMBER  — Equity beta proxy
  VOLATILITY_ANN_PCT       FLOAT   — Annualised volatility %
  DURATION_YEARS_PROXY     NUMBER  — Duration in years (proxy)

Sample questions:
  - "Which portfolio has highest volatility?"
  - "What is the beta of each portfolio?"
  - "Compare duration across portfolios"

------------------------------------------------------------------------
TABLE: NM_ANALYTICS.RAW_MARTS.MART_SECTOR_ALLOCATION
Grain: one row per portfolio per sector per filing.
Use for: sector breakdown, equity vs fixed income by sector.

Columns:
  FILING_DATE                    DATE    — Filing date
  FILING_PERIOD                  TEXT    — Period label
  PORTFOLIO_NAME                 TEXT    — Full portfolio name
  SECTOR_NAME                    TEXT    — Sector name
  BROAD_CATEGORY                 TEXT    — Broad category (Equity, Fixed Income, etc.)
  PCT_ALLOCATION                 NUMBER  — % of portfolio in this sector
  SECTOR_VALUE_USD               NUMBER  — Sector value in USD
  SECTOR_VALUE_MILLIONS          NUMBER  — Sector value in millions
  SECTOR_RANK                    NUMBER  — Rank within portfolio (1 = largest)
  TOTAL_EQUITY_PCT_IN_PORTFOLIO  NUMBER  — Total equity % in portfolio

Sample questions:
  - "What is the tech allocation in Index 500?"
  - "Which sector is largest in Balanced Portfolio?"
  - "Compare sector allocation between two portfolios"

------------------------------------------------------------------------
TABLE: NM_ANALYTICS.RAW_MARTS.MART_TOP_HOLDINGS
Grain: one row per holding per portfolio per filing.
Use for: individual security analysis, concentration, country exposure.

Columns:
  FILING_DATE          DATE     — Filing date
  PORTFOLIO_NAME       TEXT     — Full portfolio name
  HOLDING_NAME         TEXT     — Security name
  TITLE                TEXT     — Full title
  CUSIP                TEXT     — CUSIP identifier
  ISIN                 TEXT     — ISIN identifier
  CURRENCY             TEXT     — Currency
  ASSET_CATEGORY       TEXT     — Asset type (EC = equity, DBT = debt, etc.)
  ISSUER_CATEGORY      TEXT     — Issuer type
  COUNTRY              TEXT     — Country of issuer
  VALUE_USD            FLOAT    — Value in USD
  PCT_OF_PORTFOLIO     FLOAT    — % of portfolio
  CONCENTRATION_TIER   TEXT     — Tier (Top 5, Top 10, etc.)
  HOLDING_RANK         NUMBER   — Rank within portfolio
  CUMULATIVE_PCT       FLOAT    — Cumulative % up to this holding
  IS_NM_INTERNAL_FUND  BOOLEAN  — True if NM internal fund
  AUM_MILLIONS         NUMBER   — Portfolio AUM in millions
  IS_TOP_10            BOOLEAN  — True if top 10 holding
  IS_TOP_5             BOOLEAN  — True if top 5 holding

Sample questions:
  - "What are the top 5 holdings in Index 500?"
  - "What is Apple's weight across all portfolios?"
  - "Which holdings are in top 5 of every portfolio?"

⚠️ LIMITATION: MART_TOP_HOLDINGS has NO SECTOR column per individual holding.
Questions like "top tech holding in NM" CANNOT be answered by joining with
MART_SECTOR_ALLOCATION because sector allocation is portfolio-level, not
holding-level. You must clearly state this limitation when asked sector-specific
holding questions for NM, and suggest what IS available (e.g. sector totals
from MART_SECTOR_ALLOCATION, or individual holdings without sector context).


========================================================================
DATABASE 2: BERKSHIRE_ANALYTICS.RAW_MARTS
Berkshire Hathaway 13F holdings — Q2 2024 through Q1 2026 (8 quarters)
========================================================================

------------------------------------------------------------------------
TABLE: BERKSHIRE_ANALYTICS.RAW_MARTS.MART_CONCENTRATION_METRICS
Grain: one row per quarter.
Use for: HHI, top N concentration over time.

Columns:
  QUARTER             TEXT    — Quarter label (e.g. 'Q1 2026')
  FILING_DATE         DATE    — Filing date
  TOTAL_VALUE_USD     NUMBER  — Total portfolio value
  TOTAL_HOLDINGS      NUMBER  — Number of holdings
  TOP_1_PCT           NUMBER  — % held by top 1 holding
  TOP_3_PCT           NUMBER  — % held by top 3 holdings
  TOP_5_PCT           NUMBER  — % held by top 5 holdings
  TOP_10_PCT          NUMBER  — % held by top 10 holdings
  TOP_20_PCT          NUMBER  — % held by top 20 holdings
  TOP_HOLDING_NAME    TEXT    — Name of largest holding
  TOP_HOLDING_PCT     NUMBER  — % of largest holding
  TOP_HOLDING_VALUE   NUMBER  — Value of largest holding
  HHI_SCORE           FLOAT   — Herfindahl-Hirschman Index score

Sample questions:
  - "How concentrated is Berkshire's portfolio?"
  - "What is the HHI trend over 8 quarters?"
  - "How much does the top holding represent?"

------------------------------------------------------------------------
TABLE: BERKSHIRE_ANALYTICS.RAW_MARTS.MART_DRIFT_ANALYSIS
Grain: one row per holding per quarter showing QoQ changes.
Use for: position changes, new entries, exits.

Columns:
  FILING_DATE        DATE    — Filing date
  QUARTER            TEXT    — Quarter label
  ISSUER_NAME        TEXT    — Company name
  CUSIP              TEXT    — CUSIP
  SECTOR             TEXT    — GICS sector
  VALUE_USD          NUMBER  — Current value
  PCT_OF_PORTFOLIO   NUMBER  — % of portfolio
  HOLDING_RANK       NUMBER  — Rank within quarter
  PREV_VALUE_USD     NUMBER  — Prior quarter value
  PREV_QUARTER       TEXT    — Prior quarter label
  VALUE_CHANGE_USD   NUMBER  — Dollar change from prior quarter
  SHARES_CHANGE      NUMBER  — Share count change
  DRIFT_FLAG         TEXT    — NEW / INCREASED / REDUCED / EXITED / UNCHANGED
  VALUE_CHANGE_PCT   NUMBER  — % change in value
  CHANGE_DIRECTION   TEXT    — up / down / flat

Sample questions:
  - "What positions did Berkshire add last quarter?"
  - "Which holdings were reduced most?"
  - "Show me all NEW positions in Q1 2026"

------------------------------------------------------------------------
TABLE: BERKSHIRE_ANALYTICS.RAW_MARTS.MART_PORTFOLIO_SNAPSHOT
Grain: latest quarter holdings with cumulative concentration.
Use for: current state analysis.

Columns:
  FILING_DATE        DATE     — Filing date
  QUARTER            TEXT     — Quarter label
  ISSUER_NAME        TEXT     — Company name
  CUSIP              TEXT     — CUSIP
  SECTOR             TEXT     — GICS sector
  INDUSTRY           TEXT     — Industry
  VALUE_USD          NUMBER   — Value in USD
  VALUE_000S         NUMBER   — Value in thousands
  SHARES             NUMBER   — Share count
  PCT_OF_PORTFOLIO   NUMBER   — % of portfolio
  HOLDING_RANK       NUMBER   — Rank (1 = largest)
  DRIFT_FLAG         TEXT     — Change flag vs prior quarter
  VALUE_CHANGE_USD   NUMBER   — Change in value
  TOTAL_VALUE_USD    NUMBER   — Total portfolio value
  TOTAL_HOLDINGS     NUMBER   — Total number of holdings
  CUMULATIVE_PCT     NUMBER   — Cumulative % up to this rank
  IS_TOP_5           BOOLEAN  — Top 5 flag
  IS_TOP_10          BOOLEAN  — Top 10 flag
  IS_TOP_20          BOOLEAN  — Top 20 flag

Sample questions:
  - "What are Berkshire's top 10 holdings?"
  - "What % of Berkshire is in financials?"
  - "Show me all holdings with over 5% weight"

------------------------------------------------------------------------
TABLE: BERKSHIRE_ANALYTICS.RAW_MARTS.MART_SECTOR_ROTATION
Grain: one row per sector per quarter with QoQ change.
Use for: rotation analysis and heatmap questions.

Columns:
  QUARTER                TEXT    — Quarter label
  FILING_DATE            DATE    — Filing date
  SECTOR                 TEXT    — GICS sector name
  SECTOR_VALUE_USD       NUMBER  — Sector value in USD
  SECTOR_PCT             NUMBER  — % of portfolio in sector
  HOLDING_COUNT          NUMBER  — Number of holdings in sector
  TOTAL_PORTFOLIO_VALUE  NUMBER  — Total portfolio value
  PREV_SECTOR_PCT        NUMBER  — Prior quarter sector %
  SECTOR_PCT_CHANGE      NUMBER  — Change in sector %
  SECTOR_RANK            NUMBER  — Rank within quarter

Sample questions:
  - "How has Berkshire's energy allocation changed?"
  - "Which sector grew most last quarter?"
  - "Compare financials allocation Q1 2025 vs Q1 2026"


========================================================================
DATA QUALITY NOTES
========================================================================
- All VALUE_USD and TOTAL_VALUE_USD columns are in RAW DOLLARS (not thousands).
- VALUE_000S in MART_PORTFOLIO_SNAPSHOT is in thousands.
- AUM_MILLIONS columns are already in millions.
- PCT columns are stored as percentages (e.g. 12.5 means 12.5%, not 0.125).
- Berkshire quarters available: Q2 2024, Q3 2024, Q4 2024, Q1 2025, Q2 2025, Q3 2025, Q4 2025, Q1 2026.
- NM has a single filing date in Feb 2026 (one snapshot, no time series).
- For Apple in Berkshire data, ISSUER_NAME is typically 'APPLE INC' — use ILIKE '%APPLE%'.
- Sector names in Berkshire follow GICS conventions (e.g. 'Information Technology', 'Financials').
"""
