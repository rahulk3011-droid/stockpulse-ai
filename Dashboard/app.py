import json
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st
import yfinance as yf

# ============================================================
# PAGE CONFIG + ACCESS LOCK
# ============================================================
st.set_page_config(page_title="Investment Dashboard", layout="wide")

token = st.query_params.get("token", "")
if isinstance(token, list):
    token = token[0] if token else ""

if token != "stockpulse123":
    st.error("Access Denied 🚫")
    st.info("Please log in through the StockPulse AI website.")
    st.stop()

# ============================================================
# STYLE
# ============================================================
st.markdown(
    """
    <style>
    .block-container {
        padding-top: 1rem;
        padding-bottom: 1rem;
    }
    .small-note {
        color: #9aa0a6;
        font-size: 0.9rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ============================================================
# FILES
# ============================================================
PORTFOLIO_FILE = Path("portfolio.json")

# ============================================================
# WATCHLIST
# ============================================================
INDUSTRY_GROUPS = {
    "AI / Software": {
        "Palantir": "PLTR",
        "Snowflake": "SNOW",
        "C3.ai": "AI",
        "BigBear.ai": "BBAI",
        "SoundHound AI": "SOUN",
    },
    "Semiconductors / Chips": {
        "NVIDIA": "NVDA",
        "AMD": "AMD",
        "Arm Holdings": "ARM",
        "BrainChip": "BRN.AX",
        "Weebit Nano": "WBT.AX",
        "Archer Materials": "AXE.AX",
    },
    "Biotech / Gene Editing": {
        "CRISPR Therapeutics": "CRSP",
        "Intellia Therapeutics": "NTLA",
        "Editas Medicine": "EDIT",
        "Beam Therapeutics": "BEAM",
    },
    "Space / Satellite": {
        "Rocket Lab": "RKLB",
        "AST SpaceMobile": "ASTS",
    },
    "Defense / Drone": {
        "DroneShield": "DRO.AX",
        "Elsight": "ELS.AX",
    },
    "Battery / Energy": {
        "Novonix": "NVX.AX",
        "Altech Batteries": "ATC.AX",
        "Arafura Rare Earths": "ARU.AX",
        "Ionic Rare Earths": "IXR.AX",
        "Lake Resources": "LKE.AX",
        "Sayona Mining": "SYA.AX",
        "88 Energy": "88E.AX",
        "Invictus Energy": "IVZ.AX",
        "ChargePoint": "CHPT",
        "Blink Charging": "BLNK",
        "Workhorse Group": "WKHS",
    },
    "Big Players": {
        "Microsoft": "MSFT",
        "Alphabet (Google)": "GOOGL",
        "Meta": "META",
        "Amazon": "AMZN",
        "NVIDIA": "NVDA",
    },
    "Long-Term ETFs": {
        "Vanguard Diversified High Growth ETF": "VDHG.AX",
        "Vanguard Australian Shares ETF": "VAS.AX",
        "Vanguard International Shares ETF": "VGS.AX",
    },
    "Crypto": {
        "Bitcoin": "BTC-AUD",
        "Ethereum": "ETH-AUD",
        "XRP": "XRP-AUD",
        "Solana": "SOL-AUD",
    },
}

IPO_RADAR = pd.DataFrame(
    [
        {"Company": "SpaceX", "Theme": "Space", "Status": "Private / Watch"},
        {"Company": "Anthropic", "Theme": "AI", "Status": "Private / Watch"},
        {"Company": "OpenAI", "Theme": "AI", "Status": "Private / Watch"},
        {"Company": "Databricks", "Theme": "AI Data", "Status": "Private / Watch"},
        {"Company": "Scale AI", "Theme": "AI Infrastructure", "Status": "Private / Watch"},
    ]
)

ASSET_TO_SYMBOL = {}
ASSET_TO_GROUP = {}
SYMBOL_TO_ASSET = {}

for group_name, assets in INDUSTRY_GROUPS.items():
    for asset_name, ticker in assets.items():
        ASSET_TO_SYMBOL[asset_name] = ticker
        ASSET_TO_GROUP[asset_name] = group_name
        SYMBOL_TO_ASSET[ticker] = asset_name

ALL_TICKERS = list(dict.fromkeys(ASSET_TO_SYMBOL.values()))

# ============================================================
# HELPERS
# ============================================================
def safe_float(value, default=0.0):
    try:
        if pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def money(value: float) -> str:
    value = safe_float(value)
    if abs(value) < 10:
        return f"${value:,.4f}"
    return f"${value:,.2f}"


def pct_text(value: float) -> str:
    return f"{safe_float(value):,.2f}%"


def market_from_ticker(ticker: str) -> str:
    if ticker.endswith(".AX"):
        return "ASX"
    if "-AUD" in ticker or "-USD" in ticker:
        return "Crypto"
    return "US"


def action_from_signal(signal: str) -> str:
    if signal == "🔵 BLUE":
        return "Watch Closely"
    if signal == "🟢 GREEN":
        return "Buy Zone"
    if signal == "🟡 YELLOW":
        return "Wait"
    return "Avoid For Now"


def signal_and_reason(day_pct: float, week_pct: float, month_pct: float, volume_ratio: float):
    reasons = []

    if day_pct >= 6:
        reasons.append("strong daily move")
    if week_pct >= 10:
        reasons.append("strong weekly trend")
    if month_pct >= 15:
        reasons.append("good monthly strength")
    if volume_ratio >= 2:
        reasons.append("heavy volume")
    if day_pct > 0:
        reasons.append("buyers in control")

    if day_pct >= 6 and week_pct >= 10 and volume_ratio >= 2:
        return "🔵 BLUE", ", ".join(reasons[:3]) or "explosive setup"
    if day_pct >= 2 or (week_pct >= 5 and volume_ratio >= 1.2):
        return "🟢 GREEN", ", ".join(reasons[:3]) or "positive setup"
    if day_pct > -2:
        return "🟡 YELLOW", ", ".join(reasons[:3]) or "mixed setup"
    return "🔴 RED", "weak price action"


def ensure_portfolio_columns(df: pd.DataFrame) -> pd.DataFrame:
    clean = pd.DataFrame(df).copy()
    schema = {
        "Asset": "",
        "Units": 0.0,
        "Price Per Unit": 0.0,
        "Total Price": 0.0,
    }

    for col, default in schema.items():
        if col not in clean.columns:
            clean[col] = default

    clean = clean[["Asset", "Units", "Price Per Unit", "Total Price"]]
    clean["Asset"] = clean["Asset"].astype(str).replace("nan", "").str.strip()
    clean["Units"] = pd.to_numeric(clean["Units"], errors="coerce").fillna(0.0)
    clean["Price Per Unit"] = pd.to_numeric(clean["Price Per Unit"], errors="coerce").fillna(0.0)
    clean["Total Price"] = pd.to_numeric(clean["Total Price"], errors="coerce").fillna(0.0)
    return clean


def load_portfolio() -> pd.DataFrame:
    if not PORTFOLIO_FILE.exists():
        return ensure_portfolio_columns(pd.DataFrame())

    try:
        with PORTFOLIO_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return ensure_portfolio_columns(pd.DataFrame(data))
    except Exception:
        return ensure_portfolio_columns(pd.DataFrame())


def save_portfolio(df: pd.DataFrame) -> None:
    clean = ensure_portfolio_columns(df)
    clean = clean[
        (clean["Asset"] != "")
        | (clean["Units"] != 0)
        | (clean["Price Per Unit"] != 0)
        | (clean["Total Price"] != 0)
    ].copy()

    with PORTFOLIO_FILE.open("w", encoding="utf-8") as f:
        json.dump(clean.to_dict("records"), f, indent=2)


def fill_trade_values(units: float, price_per_unit: float, total_price: float):
    units = safe_float(units)
    price_per_unit = safe_float(price_per_unit)
    total_price = safe_float(total_price)

    positive_count = sum(x > 0 for x in [units, price_per_unit, total_price])

    if positive_count < 2:
        return units, price_per_unit, total_price

    if units == 0 and price_per_unit > 0 and total_price > 0:
        units = total_price / price_per_unit if price_per_unit else 0.0
    elif price_per_unit == 0 and units > 0 and total_price > 0:
        price_per_unit = total_price / units if units else 0.0
    elif total_price == 0 and units > 0 and price_per_unit > 0:
        total_price = units * price_per_unit

    return units, price_per_unit, total_price


@st.cache_data(ttl=1800)
def download_market_data(tickers):
    return yf.download(
        tickers=tickers,
        period="6mo",
        interval="1d",
        auto_adjust=True,
        group_by="ticker",
        progress=False,
        threads=True,
    )


@st.cache_data(ttl=1800)
def get_asset_info(ticker):
    try:
        info = yf.Ticker(ticker).info
        return info if isinstance(info, dict) else {}
    except Exception:
        return {}


@st.cache_data(ttl=1800)
def get_asset_history(ticker, period):
    try:
        hist = yf.Ticker(ticker).history(period=period, auto_adjust=True)
        return hist if isinstance(hist, pd.DataFrame) else pd.DataFrame()
    except Exception:
        return pd.DataFrame()


def build_market_table(raw) -> pd.DataFrame:
    rows = []

    for ticker in ALL_TICKERS:
        try:
            df = raw[ticker].dropna().copy()
        except Exception:
            continue

        if df.empty or len(df) < 3:
            continue

        current_price = safe_float(df["Close"].iloc[-1])
        previous_close = safe_float(df["Close"].iloc[-2])
        week_close = safe_float(df["Close"].iloc[-6]) if len(df) >= 6 else previous_close
        month_close = safe_float(df["Close"].iloc[-22]) if len(df) >= 22 else previous_close
        high_52 = safe_float(df["High"].tail(126).max())
        low_52 = safe_float(df["Low"].tail(126).min())
        volume = safe_float(df["Volume"].iloc[-1]) if "Volume" in df.columns else 0.0
        avg_volume = safe_float(df["Volume"].tail(20).mean()) if "Volume" in df.columns else 0.0
        volume_ratio = volume / avg_volume if avg_volume else 0.0

        day_pct = ((current_price / previous_close) - 1) * 100 if previous_close else 0.0
        week_pct = ((current_price / week_close) - 1) * 100 if week_close else 0.0
        month_pct = ((current_price / month_close) - 1) * 100 if month_close else 0.0

        signal, reason = signal_and_reason(day_pct, week_pct, month_pct, volume_ratio)
        asset_name = SYMBOL_TO_ASSET.get(ticker, ticker)
        group_name = ASSET_TO_GROUP.get(asset_name, "Other")

        rows.append(
            {
                "Industry": group_name,
                "Asset": asset_name,
                "Ticker": ticker,
                "Market": market_from_ticker(ticker),
                "Current Price": current_price,
                "Previous Close": previous_close,
                "Day %": day_pct,
                "Week %": week_pct,
                "Month %": month_pct,
                "52W High": high_52,
                "52W Low": low_52,
                "Volume Ratio": volume_ratio,
                "Signal": signal,
                "Action": action_from_signal(signal),
                "Why": reason,
            }
        )

    market = pd.DataFrame(rows)
    if market.empty:
        return market
    return market.sort_values(["Industry", "Asset"]).reset_index(drop=True)


def style_signal_table(df: pd.DataFrame):
    def signal_style(val):
        text = str(val)
        if "🔵" in text or "BLUE" in text:
            return "background-color: #0b57d0; color: white; font-weight: bold;"
        if "🟢" in text or "GREEN" in text:
            return "background-color: #1f6f2c; color: white; font-weight: bold;"
        if "🟡" in text or "YELLOW" in text:
            return "background-color: #8a6d1d; color: white; font-weight: bold;"
        return "background-color: #8b1e1e; color: white; font-weight: bold;"

    return df.style.map(signal_style, subset=["Signal"]) if "Signal" in df.columns else df.style


def apply_filters(df, search_text, industry_filter, signal_filter, market_filter, max_price):
    out = df.copy()

    if search_text.strip():
        q = search_text.strip().lower()
        out = out[
            out["Asset"].str.lower().str.contains(q, na=False)
            | out["Ticker"].str.lower().str.contains(q, na=False)
        ]

    if industry_filter != "All":
        out = out[out["Industry"] == industry_filter]

    if signal_filter != "All":
        out = out[out["Signal"] == signal_filter]

    if market_filter != "All":
        out = out[out["Market"] == market_filter]

    out = out[out["Current Price"] <= max_price]
    return out.copy()


def best_of_group(df: pd.DataFrame, group_name: str):
    group_df = df[df["Industry"] == group_name].copy()
    if group_df.empty:
        return None

    sort_map = {"🔵 BLUE": 4, "🟢 GREEN": 3, "🟡 YELLOW": 2, "🔴 RED": 1}
    group_df["rank_score"] = group_df["Signal"].map(sort_map).fillna(0)
    group_df = group_df.sort_values(["rank_score", "Day %", "Week %"], ascending=[False, False, False])
    return group_df.iloc[0]


def render_group_tab(group_name: str, filtered_df: pd.DataFrame, market_df: pd.DataFrame, chart_period: str):
    group_df = filtered_df[filtered_df["Industry"] == group_name].copy()

    if group_df.empty:
        st.info("No stocks in this industry match your current filters.")
        return

    display = group_df[
        ["Asset", "Ticker", "Market", "Current Price", "Day %", "Week %", "Month %", "Signal", "Action", "Why"]
    ].copy()
    display["Current Price"] = display["Current Price"].map(money)
    display["Day %"] = display["Day %"].map(pct_text)
    display["Week %"] = display["Week %"].map(pct_text)
    display["Month %"] = display["Month %"].map(pct_text)

    st.dataframe(style_signal_table(display), use_container_width=True, hide_index=True)

    st.markdown("### Quick View")
    selected_asset = st.selectbox(
        f"Choose a stock in {group_name}",
        group_df["Asset"].tolist(),
        key=f"pick_{group_name}",
    )
    selected_ticker = ASSET_TO_SYMBOL[selected_asset]
    asset_row = market_df.loc[market_df["Ticker"] == selected_ticker].iloc[0]
    asset_info = get_asset_info(selected_ticker)
    asset_history = get_asset_history(selected_ticker, chart_period)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Price", money(asset_row["Current Price"]))
    c2.metric("Day %", pct_text(asset_row["Day %"]))
    c3.metric("Signal", asset_row["Signal"])
    c4.metric("Action", asset_row["Action"])

    st.write(f"**Why:** {asset_row['Why']}")

    if not asset_history.empty and "Close" in asset_history.columns:
        st.line_chart(asset_history[["Close"]], height=280)

    with st.expander("Business Summary", expanded=False):
        st.write(asset_info.get("longBusinessSummary", "No summary available."))

# ============================================================
# APP
# ============================================================
st.title("Investment Dashboard")
st.caption("Protected dashboard access via StockPulse AI website.")

with st.sidebar:
    st.header("Control Panel")

    search_text = st.text_input("Search stock / company", placeholder="BrainChip, PLTR, NVDA...")
    industry_options = ["All"] + list(INDUSTRY_GROUPS.keys())
    industry_filter = st.selectbox("Industry", industry_options)
    signal_filter = st.selectbox("Signal", ["All", "🔵 BLUE", "🟢 GREEN", "🟡 YELLOW", "🔴 RED"])
    market_filter = st.selectbox("Market", ["All", "ASX", "US", "Crypto"])
    max_price = st.number_input("Max price", min_value=1.0, value=100000.0, step=1.0)
    chart_period = st.selectbox("Chart period", ["1mo", "3mo", "6mo", "1y"], index=2)

    if st.button("Refresh data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    st.markdown("---")
    st.subheader("My Holdings")
    loaded_portfolio = load_portfolio()
    quick_holdings = [x for x in loaded_portfolio["Asset"].astype(str).str.strip().tolist() if x]
    if quick_holdings:
        for item in quick_holdings:
            st.write(f"• {item}")
    else:
        st.caption("No holdings saved yet.")

with st.spinner("Loading market data..."):
    raw_market = download_market_data(ALL_TICKERS)
    market_df = build_market_table(raw_market)

if market_df.empty:
    st.error("Could not load market data. Please try again.")
    st.stop()

filtered_df = apply_filters(
    market_df,
    search_text=search_text,
    industry_filter=industry_filter,
    signal_filter=signal_filter,
    market_filter=market_filter,
    max_price=max_price,
)

k1, k2, k3, k4 = st.columns(4)
k1.metric("Assets Showing", len(filtered_df))
k2.metric("Blue Alerts", int(filtered_df["Signal"].eq("🔵 BLUE").sum()))
k3.metric("Green", int(filtered_df["Signal"].eq("🟢 GREEN").sum()))
k4.metric("Red", int(filtered_df["Signal"].eq("🔴 RED").sum()))

tabs = st.tabs(
    [
        "Home",
        "AI / Software",
        "Semiconductors / Chips",
        "Biotech / Gene Editing",
        "Space / Satellite",
        "Defense / Drone",
        "Battery / Energy",
        "Big Players",
        "Long-Term ETFs",
        "Crypto",
        "Portfolio",
        "IPO Radar",
    ]
)

with tabs[0]:
    st.subheader("Best in Each Industry")

    best_rows = []
    for group_name in INDUSTRY_GROUPS.keys():
        best_row = best_of_group(filtered_df, group_name)
        if best_row is None:
            continue
        best_rows.append(
            {
                "Industry": group_name,
                "Stock": best_row["Asset"],
                "Ticker": best_row["Ticker"],
                "Price": money(best_row["Current Price"]),
                "Signal": best_row["Signal"],
                "Action": best_row["Action"],
                "Why": best_row["Why"],
            }
        )

    if best_rows:
        best_df = pd.DataFrame(best_rows)
        st.dataframe(style_signal_table(best_df), use_container_width=True, hide_index=True)
    else:
        st.info("No stocks match your current filters.")

    st.markdown("### Top Opportunities Right Now")
    home_top = filtered_df[
        ["Industry", "Asset", "Ticker", "Current Price", "Day %", "Week %", "Signal", "Action", "Why"]
    ].copy()
    home_top = home_top.sort_values(["Day %", "Week %"], ascending=[False, False]).head(12)
    home_top["Current Price"] = home_top["Current Price"].map(money)
    home_top["Day %"] = home_top["Day %"].map(pct_text)
    home_top["Week %"] = home_top["Week %"].map(pct_text)
    st.dataframe(style_signal_table(home_top), use_container_width=True, hide_index=True)

with tabs[1]:
    st.subheader("AI / Software")
    render_group_tab("AI / Software", filtered_df, market_df, chart_period)

with tabs[2]:
    st.subheader("Semiconductors / Chips")
    render_group_tab("Semiconductors / Chips", filtered_df, market_df, chart_period)

with tabs[3]:
    st.subheader("Biotech / Gene Editing")
    render_group_tab("Biotech / Gene Editing", filtered_df, market_df, chart_period)

with tabs[4]:
    st.subheader("Space / Satellite")
    render_group_tab("Space / Satellite", filtered_df, market_df, chart_period)

with tabs[5]:
    st.subheader("Defense / Drone")
    render_group_tab("Defense / Drone", filtered_df, market_df, chart_period)

with tabs[6]:
    st.subheader("Battery / Energy")
    render_group_tab("Battery / Energy", filtered_df, market_df, chart_period)

with tabs[7]:
    st.subheader("Big Players")
    render_group_tab("Big Players", filtered_df, market_df, chart_period)

with tabs[8]:
    st.subheader("Long-Term ETFs")
    render_group_tab("Long-Term ETFs", filtered_df, market_df, chart_period)

with tabs[9]:
    st.subheader("Crypto")
    render_group_tab("Crypto", filtered_df, market_df, chart_period)

with tabs[10]:
    st.subheader("My Portfolio")
    st.caption("Add, edit, delete, save, and load holdings directly here.")

    if "portfolio_table" not in st.session_state:
        st.session_state["portfolio_table"] = load_portfolio()

    action_col1, action_col2 = st.columns(2)
    with action_col1:
        save_clicked = st.button("Save Portfolio", key="save_portfolio_btn")
    with action_col2:
        load_clicked = st.button("Load Portfolio", key="load_portfolio_btn")

    if load_clicked:
        st.session_state["portfolio_table"] = load_portfolio()

    portfolio_input = st.data_editor(
        ensure_portfolio_columns(st.session_state["portfolio_table"]),
        key="portfolio_table_editor",
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "Asset": st.column_config.SelectboxColumn(
                "Asset",
                options=list(ASSET_TO_SYMBOL.keys()),
                required=False,
            ),
            "Units": st.column_config.NumberColumn("Units", format="%.8f"),
            "Price Per Unit": st.column_config.NumberColumn("Price Per Unit", format="%.8f"),
            "Total Price": st.column_config.NumberColumn("Total Price", format="%.2f"),
        },
    )

    st.session_state["portfolio_table"] = ensure_portfolio_columns(portfolio_input).copy()

    if save_clicked:
        save_portfolio(st.session_state["portfolio_table"])
        st.success("Portfolio saved.")

    rows = []
    source_portfolio = ensure_portfolio_columns(st.session_state["portfolio_table"])

    for _, row in source_portfolio.iterrows():
        asset = str(row["Asset"]).strip()
        if not asset:
            continue

        units, price_per_unit, total_price = fill_trade_values(
            row["Units"],
            row["Price Per Unit"],
            row["Total Price"],
        )

        ticker = ASSET_TO_SYMBOL.get(asset, "")
        group_name = ASSET_TO_GROUP.get(asset, "")
        market_match = market_df[market_df["Ticker"] == ticker]

        if market_match.empty:
            current_price = 0.0
            previous_close = 0.0
            signal = "🔴 RED"
            action = "Avoid For Now"
        else:
            market_row = market_match.iloc[0]
            current_price = safe_float(market_row["Current Price"])
            previous_close = safe_float(market_row["Previous Close"])
            signal = str(market_row["Signal"])
            action = str(market_row["Action"])

        value = units * current_price
        day_pl = units * (current_price - previous_close)
        pnl = value - total_price
        return_pct = ((value / total_price) - 1) * 100 if total_price > 0 else 0.0

        rows.append(
            {
                "Name": asset,
                "Industry": group_name,
                "Units": units,
                "Buy Price": price_per_unit,
                "Total Cost": total_price,
                "Current Price": current_price,
                "Value": value,
                "Day P&L": day_pl,
                "P&L": pnl,
                "Return %": return_pct,
                "Signal": signal,
                "Action": action,
            }
        )

    portfolio_df = pd.DataFrame(rows)

    if portfolio_df.empty:
        st.info("Add your holdings above.")
    else:
        total_cost = portfolio_df["Total Cost"].sum()
        market_value = portfolio_df["Value"].sum()
        day_pl_total = portfolio_df["Day P&L"].sum()
        pnl_total = portfolio_df["P&L"].sum()
        return_total = ((market_value / total_cost) - 1) * 100 if total_cost > 0 else 0.0

        s1, s2, s3, s4, s5 = st.columns(5)
        s1.metric("Total Cost", money(total_cost))
        s2.metric("Market Value", money(market_value))
        s3.metric("Day P&L", money(day_pl_total))
        s4.metric("P&L", money(pnl_total))
        s5.metric("Return %", pct_text(return_total))

        display_portfolio = portfolio_df[
            ["Name", "Industry", "Units", "Buy Price", "Total Cost", "Current Price", "Value", "Day P&L", "P&L", "Signal", "Action"]
        ].copy()

        display_portfolio["Buy Price"] = display_portfolio["Buy Price"].map(money)
        display_portfolio["Total Cost"] = display_portfolio["Total Cost"].map(money)
        display_portfolio["Current Price"] = display_portfolio["Current Price"].map(money)
        display_portfolio["Value"] = display_portfolio["Value"].map(money)
        display_portfolio["Day P&L"] = display_portfolio["Day P&L"].map(money)
        display_portfolio["P&L"] = display_portfolio["P&L"].map(money)

        st.dataframe(style_signal_table(display_portfolio), use_container_width=True, hide_index=True)

with tabs[11]:
    st.subheader("IPO Radar")
    st.dataframe(IPO_RADAR, use_container_width=True, hide_index=True)

st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")