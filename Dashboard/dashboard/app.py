import os
import json
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests
import streamlit as st
import yfinance as yf

from scanner_engine import classify_setup, score_stock, scanner_label
from sector_engine import GICS_GROUPS, get_sector_stocks
from signals import action_from_signal, signal_and_reason
from utils import market_from_ticker

st.set_page_config(page_title="Investment Dashboard", layout="wide")

FLASK_BASE_URL = os.getenv("FLASK_BASE_URL", "http://127.0.0.1:5000")

token = st.query_params.get("token", "")
if isinstance(token, list):
    token = token[0] if token else ""

DEV_MODE = False  # set False later for production

if not token and not DEV_MODE:
    st.error("Access Denied 🚫")
    st.info("Please log in through the StockPulse AI website.")
    st.stop()

if DEV_MODE:
    user_email = "Dev User"
else:
    try:
        resp = requests.get(
            f"{FLASK_BASE_URL}/validate-token",
            params={"token": token},
            timeout=5,
        )
        if resp.status_code != 200 or not resp.json().get("valid"):
            st.error("Access Denied 🚫")
            st.info("Invalid or expired login session.")
            st.stop()
        user_email = resp.json().get("email", "User")
    except Exception:
        st.error("Could not verify login.")
        st.info("Make sure your Flask website is running first.")
        st.stop()

st.markdown(
    '''
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
    ''',
    unsafe_allow_html=True,
)

PORTFOLIO_FILE = Path("portfolio.json")

INDUSTRY_GROUPS = {group: assets.copy() for group, assets in GICS_GROUPS.items()}
for sector_name in list(INDUSTRY_GROUPS.keys()):
    auto_stocks = get_sector_stocks(sector_name)
    for asset_name, ticker in auto_stocks.items():
        if ticker not in INDUSTRY_GROUPS[sector_name].values():
            INDUSTRY_GROUPS[sector_name][asset_name] = ticker

IPO_RADAR = pd.DataFrame(
    [
        {"Company": "SpaceX", "Theme": "Space", "Status": "Private / Watch"},
        {"Company": "Anthropic", "Theme": "AI", "Status": "Private / Watch"},
        {"Company": "OpenAI", "Theme": "AI", "Status": "Private / Watch"},
        {"Company": "Databricks", "Theme": "AI Data", "Status": "Private / Watch"},
        {"Company": "Scale AI", "Theme": "AI Infrastructure", "Status": "Private / Watch"},
    ]
)

MARKET_INDICES = {
    "NASDAQ": "^IXIC",
    "S&P 500": "^GSPC",
    "Dow Jones": "^DJI",
    "ASX 200": "^AXJO",
    "FTSE 100": "^FTSE",
    "Nikkei 225": "^N225",
    "Hang Seng": "^HSI",
    "DAX": "^GDAXI",
    "WTI Oil": "CL=F",
    "Brent Oil": "BZ=F",
}

ASSET_TO_SYMBOL = {}
ASSET_TO_GROUP = {}
SYMBOL_TO_ASSET = {}

for group_name, assets in INDUSTRY_GROUPS.items():
    for asset_name, ticker in assets.items():
        ASSET_TO_SYMBOL[asset_name] = ticker
        ASSET_TO_GROUP[asset_name] = group_name
        SYMBOL_TO_ASSET[ticker] = asset_name

ALL_TICKERS = list(dict.fromkeys(ASSET_TO_SYMBOL.values()))

ETF_ALIASES = {
    "VAS": ("Vanguard Australian Shares ETF", "VAS.AX"),
    "VAS.AX": ("Vanguard Australian Shares ETF", "VAS.AX"),
    "VGS": ("Vanguard International Shares ETF", "VGS.AX"),
    "VGS.AX": ("Vanguard International Shares ETF", "VGS.AX"),
    "VDHG": ("Vanguard Diversified High Growth ETF", "VDHG.AX"),
    "VDHG.AX": ("Vanguard Diversified High Growth ETF", "VDHG.AX"),
    "IVV": ("iShares S&P 500 ETF", "IVV.AX"),
    "IVV.AX": ("iShares S&P 500 ETF", "IVV.AX"),
    "NDQ": ("BetaShares Nasdaq 100 ETF", "NDQ.AX"),
    "NDQ.AX": ("BetaShares Nasdaq 100 ETF", "NDQ.AX"),
}

def safe_float_local(value, default=0.0):
    try:
        if pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default

def money(value: float) -> str:
    value = safe_float_local(value)
    if abs(value) < 10:
        return f"${value:,.4f}"
    return f"${value:,.2f}"

def pct_text(value: float) -> str:
    return f"{safe_float_local(value):,.2f}%"

def market_badge(value: float) -> str:
    value = safe_float_local(value)
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.2f}%"

def ensure_portfolio_columns(df: pd.DataFrame) -> pd.DataFrame:
    clean = pd.DataFrame(df).copy()
    schema = {"Asset": "", "Units": 0.0, "Price Per Unit": 0.0, "Total Price": 0.0}
    for col, default in schema.items():
        if col not in clean.columns:
            clean[col] = default
    clean = clean[["Asset", "Units", "Price Per Unit", "Total Price"]]
    clean["Asset"] = clean["Asset"].astype(str).replace("nan", "").str.strip()
    clean["Units"] = pd.to_numeric(clean["Units"], errors="coerce").fillna(0.0)
    clean["Price Per Unit"] = pd.to_numeric(clean["Price Per Unit"], errors="coerce").fillna(0.0)
    clean["Total Price"] = pd.to_numeric(clean["Total Price"], errors="coerce").fillna(0.0)
    return clean

def normalize_portfolio_asset(asset_input: str):
    raw = str(asset_input).strip()
    if not raw:
        return "", "", ""
    upper = raw.upper()
    if upper in ETF_ALIASES:
        asset_name, ticker = ETF_ALIASES[upper]
        return asset_name, ticker, ASSET_TO_GROUP.get(asset_name, "Core ETFs")
    if raw in ASSET_TO_SYMBOL:
        return raw, ASSET_TO_SYMBOL[raw], ASSET_TO_GROUP.get(raw, "Other")
    if upper in SYMBOL_TO_ASSET:
        asset_name = SYMBOL_TO_ASSET[upper]
        return asset_name, upper, ASSET_TO_GROUP.get(asset_name, "Other")
    for asset_name, ticker in ASSET_TO_SYMBOL.items():
        if raw.lower() == asset_name.lower():
            return asset_name, ticker, ASSET_TO_GROUP.get(asset_name, "Other")
    return raw, "", "Other"

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
    units = safe_float_local(units)
    price_per_unit = safe_float_local(price_per_unit)
    total_price = safe_float_local(total_price)
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
        period="3mo",
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

@st.cache_data(ttl=1800)
def get_market_activity(index_map: dict):
    rows = []
    for name, ticker in index_map.items():
        try:
            hist = yf.Ticker(ticker).history(period="5d", auto_adjust=True)
            if hist.empty or len(hist) < 2:
                continue
            current_price = safe_float_local(hist["Close"].iloc[-1])
            previous_close = safe_float_local(hist["Close"].iloc[-2])
            day_pct = ((current_price / previous_close) - 1) * 100 if previous_close else 0.0
            rows.append({"Market": name, "Ticker": ticker, "Price": current_price, "Day %": day_pct})
        except Exception:
            continue
    return pd.DataFrame(rows)

def build_market_table(raw) -> pd.DataFrame:
    rows = []
    for ticker in ALL_TICKERS:
        try:
            df = raw[ticker].dropna().copy()
        except Exception:
            continue
        if df.empty or len(df) < 3:
            continue

        current_price = safe_float_local(df["Close"].iloc[-1])
        previous_close = safe_float_local(df["Close"].iloc[-2])
        week_close = safe_float_local(df["Close"].iloc[-6]) if len(df) >= 6 else previous_close
        month_close = safe_float_local(df["Close"].iloc[-22]) if len(df) >= 22 else previous_close
        high_52 = safe_float_local(df["High"].max())
        low_52 = safe_float_local(df["Low"].min())
        volume = safe_float_local(df["Volume"].iloc[-1]) if "Volume" in df.columns else 0.0
        avg_volume = safe_float_local(df["Volume"].tail(20).mean()) if "Volume" in df.columns else 0.0
        volume_ratio = volume / avg_volume if avg_volume else 0.0

        day_pct = ((current_price / previous_close) - 1) * 100 if previous_close else 0.0
        week_pct = ((current_price / week_close) - 1) * 100 if week_close else 0.0
        month_pct = ((current_price / month_close) - 1) * 100 if month_close else 0.0

        signal, reason = signal_and_reason(day_pct, week_pct, month_pct, volume_ratio)
        asset_name = SYMBOL_TO_ASSET.get(ticker, ticker)
        group_name = ASSET_TO_GROUP.get(asset_name, "Other")

        explosive, smart_money, breakout_watch = classify_setup(
            day_pct=day_pct, week_pct=week_pct, month_pct=month_pct,
            volume_ratio=volume_ratio, current_price=current_price, high_52=high_52,
        )
        scanner_tag = scanner_label(explosive, smart_money, breakout_watch)
        scanner_score = score_stock(
            day_pct=day_pct, week_pct=week_pct, month_pct=month_pct,
            volume_ratio=volume_ratio, current_price=current_price, high_52=high_52, signal=signal,
        )

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
                "Explosive": explosive,
                "Smart Money": smart_money,
                "Breakout Watch": breakout_watch,
                "Scanner Tag": scanner_tag,
                "Scanner Score": scanner_score,
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

def best_of_group(df, group_name: str):
    group_df = df[df["Industry"] == group_name].copy()
    if group_df.empty:
        return None
    sort_map = {"🔵 BLUE": 4, "🟢 GREEN": 3, "🟡 YELLOW": 2, "🔴 RED": 1}
    group_df["rank_score"] = group_df["Signal"].map(sort_map).fillna(0)
    group_df = group_df.sort_values(["rank_score", "Day %", "Week %"], ascending=[False, False, False])
    return group_df.iloc[0]

def render_group_tab(group_name: str, filtered_df, market_df, chart_period: str):
    group_df = filtered_df[filtered_df["Industry"] == group_name].copy()
    if group_df.empty:
        st.info("No stocks in this industry match your current filters.")
        return
    display = group_df[
        ["Asset", "Ticker", "Market", "Current Price", "Day %", "Week %", "Month %", "Signal", "Scanner Tag", "Scanner Score", "Action", "Why"]
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
    if st.button(f"Load details for {selected_asset}", key=f"load_{group_name}"):
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

st.title("Investment Dashboard")
st.caption(f"Protected dashboard access via StockPulse AI website. Logged in as {user_email}")

with st.sidebar:
    st.markdown("## ⚙️ Control Panel")
    search_text = st.text_input("Search stock / company", placeholder="NVIDIA, NVDA, BHP, Commonwealth Bank...")
    industry_options = ["All"] + list(INDUSTRY_GROUPS.keys())
    industry_filter = st.selectbox("Industry", industry_options)
    signal_filter = st.selectbox("Signal", ["All", "🔵 BLUE", "🟢 GREEN", "🟡 YELLOW", "🔴 RED"])
    market_filter = st.selectbox("Market", ["All", "ASX", "US", "Crypto"])
    max_price = st.number_input("Max price", min_value=1.0, value=100000.0, step=1.0)
    chart_period = st.selectbox("Chart period", ["1mo", "3mo", "6mo", "1y"], index=2)
    show_blue = st.checkbox("🔵 Explosive (Blue Only)", value=False)
    show_green = st.checkbox("🟢 Strong (Green Only)", value=False)
    show_red = st.checkbox("🔴 Avoid (Red Only)", value=False)
    st.markdown("---")
    if st.button("🚪 Logout", use_container_width=True):
        st.markdown(
            f'<meta http-equiv="refresh" content="0; url={FLASK_BASE_URL}/logout">',
            unsafe_allow_html=True
        )

with st.spinner("Loading market data..."):
    raw_market = download_market_data(ALL_TICKERS)
    market_df = build_market_table(raw_market)
    market_activity_df = get_market_activity(MARKET_INDICES)

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

if show_blue:
    filtered_df = filtered_df[filtered_df["Signal"] == "🔵 BLUE"]
if show_green:
    filtered_df = filtered_df[filtered_df["Signal"] == "🟢 GREEN"]
if show_red:
    filtered_df = filtered_df[filtered_df["Signal"] == "🔴 RED"]

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Assets Showing", len(filtered_df))
k2.metric("Blue Alerts", int(filtered_df["Signal"].eq("🔵 BLUE").sum()))
k3.metric("Explosive", int(filtered_df["Explosive"].sum()))
k4.metric("Smart Money", int(filtered_df["Smart Money"].sum()))
k5.metric("Breakout Watch", int(filtered_df["Breakout Watch"].sum()))

tabs = st.tabs(
    [
        "Home",
        "Information Technology",
        "Health Care",
        "Financials",
        "Consumer Discretionary",
        "Communication Services",
        "Industrials",
        "Consumer Staples",
        "Energy",
        "Materials",
        "Real Estate",
        "Utilities",
        "Core ETFs",
        "Portfolio",
        "IPO Radar",
    ]
)

with tabs[0]:
    st.subheader("Market Activity")
    if market_activity_df.empty:
        st.info("Market activity unavailable right now.")
    else:
        market_display = market_activity_df.copy()
        market_display["Price"] = market_display["Price"].map(money)
        market_display["Day %"] = market_display["Day %"].map(market_badge)
        st.dataframe(market_display, use_container_width=True, hide_index=True)

    st.markdown("### Best in Each Sector")
    best_rows = []
    for group_name in INDUSTRY_GROUPS.keys():
        best_row = best_of_group(filtered_df, group_name)
        if best_row is None:
            continue
        best_rows.append(
            {
                "Sector": group_name,
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

    st.markdown("### Scanner Alerts")
    scanner_view = filtered_df[
        [
            "Industry", "Asset", "Ticker", "Current Price", "Day %", "Week %",
            "Month %", "Volume Ratio", "Signal", "Scanner Tag", "Scanner Score", "Why",
        ]
    ].copy()
    scanner_view = scanner_view.sort_values(
        ["Scanner Score", "Day %", "Week %"],
        ascending=[False, False, False]
    ).head(15)
    scanner_view["Current Price"] = scanner_view["Current Price"].map(money)
    scanner_view["Day %"] = scanner_view["Day %"].map(pct_text)
    scanner_view["Week %"] = scanner_view["Week %"].map(pct_text)
    scanner_view["Month %"] = scanner_view["Month %"].map(pct_text)
    scanner_view["Volume Ratio"] = scanner_view["Volume Ratio"].map(lambda x: f"{x:.2f}x")
    st.dataframe(style_signal_table(scanner_view), use_container_width=True, hide_index=True)

    st.markdown("### Top Scanner Picks")
    top_scanner = filtered_df[filtered_df["Scanner Tag"] != "Normal"].copy()
    if top_scanner.empty:
        st.info("No scanner alerts right now.")
    else:
        top_scanner = top_scanner[
            ["Industry", "Asset", "Ticker", "Signal", "Scanner Tag", "Scanner Score", "Why"]
        ].sort_values(["Scanner Score"], ascending=[False]).head(10)
        st.dataframe(style_signal_table(top_scanner), use_container_width=True, hide_index=True)

with tabs[1]:
    st.subheader("Information Technology")
    render_group_tab("Information Technology", filtered_df, market_df, chart_period)
with tabs[2]:
    st.subheader("Health Care")
    render_group_tab("Health Care", filtered_df, market_df, chart_period)
with tabs[3]:
    st.subheader("Financials")
    render_group_tab("Financials", filtered_df, market_df, chart_period)
with tabs[4]:
    st.subheader("Consumer Discretionary")
    render_group_tab("Consumer Discretionary", filtered_df, market_df, chart_period)
with tabs[5]:
    st.subheader("Communication Services")
    render_group_tab("Communication Services", filtered_df, market_df, chart_period)
with tabs[6]:
    st.subheader("Industrials")
    render_group_tab("Industrials", filtered_df, market_df, chart_period)
with tabs[7]:
    st.subheader("Consumer Staples")
    render_group_tab("Consumer Staples", filtered_df, market_df, chart_period)
with tabs[8]:
    st.subheader("Energy")
    render_group_tab("Energy", filtered_df, market_df, chart_period)
with tabs[9]:
    st.subheader("Materials")
    render_group_tab("Materials", filtered_df, market_df, chart_period)
with tabs[10]:
    st.subheader("Real Estate")
    render_group_tab("Real Estate", filtered_df, market_df, chart_period)
with tabs[11]:
    st.subheader("Utilities")
    render_group_tab("Utilities", filtered_df, market_df, chart_period)
with tabs[12]:
    st.subheader("Core ETFs")
    render_group_tab("Core ETFs", filtered_df, market_df, chart_period)

with tabs[13]:
    st.subheader("My Portfolio")
    st.caption("You can type asset name, ticker, or ETF code like VAS / VGS / VDHG.")

    if "portfolio_table" not in st.session_state:
        st.session_state["portfolio_table"] = load_portfolio()

    top_a, top_b = st.columns(2)
    with top_a:
        if st.button("Load Portfolio", key="load_portfolio_btn"):
            st.session_state["portfolio_table"] = load_portfolio()
            st.rerun()
    with top_b:
        if st.button("Reset Unsaved Changes", key="reset_portfolio_btn"):
            st.session_state["portfolio_table"] = load_portfolio()
            st.rerun()

    with st.form("portfolio_form"):
        portfolio_input = st.data_editor(
            ensure_portfolio_columns(st.session_state["portfolio_table"]),
            key="portfolio_table_editor",
            num_rows="dynamic",
            use_container_width=True,
            column_config={
                "Asset": st.column_config.TextColumn("Asset"),
                "Units": st.column_config.NumberColumn("Units", format="%.8f"),
                "Price Per Unit": st.column_config.NumberColumn("Price Per Unit", format="%.8f"),
                "Total Price": st.column_config.NumberColumn("Total Price", format="%.2f"),
            },
        )

        save_clicked = st.form_submit_button("Save Portfolio", use_container_width=True)

        if save_clicked:
            cleaned = ensure_portfolio_columns(portfolio_input).copy()
            st.session_state["portfolio_table"] = cleaned
            save_portfolio(cleaned)
            st.success("Portfolio saved.")
            st.rerun()

    rows = []
    source_portfolio = ensure_portfolio_columns(st.session_state["portfolio_table"])

    for _, row in source_portfolio.iterrows():
        raw_asset = str(row["Asset"]).strip()
        if not raw_asset:
            continue

        units, price_per_unit, total_price = fill_trade_values(
            row["Units"], row["Price Per Unit"], row["Total Price"]
        )
        asset_name, ticker, group_name = normalize_portfolio_asset(raw_asset)
        market_match = market_df[market_df["Ticker"] == ticker] if ticker else pd.DataFrame()

        if market_match.empty:
            current_price = 0.0
            previous_close = 0.0
            signal = "🔴 RED"
            action = "Check symbol"
        else:
            market_row = market_match.iloc[0]
            current_price = safe_float_local(market_row["Current Price"])
            previous_close = safe_float_local(market_row["Previous Close"])
            signal = str(market_row["Signal"])
            action = str(market_row["Action"])

        value = units * current_price
        day_pl = units * (current_price - previous_close)
        pnl = value - total_price
        return_pct = ((value / total_price) - 1) * 100 if total_price > 0 else 0.0

        rows.append(
            {
                "Name": asset_name if asset_name else raw_asset,
                "Ticker": ticker if ticker else raw_asset.upper(),
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
            ["Name", "Ticker", "Industry", "Units", "Buy Price", "Total Cost", "Current Price", "Value", "Day P&L", "P&L", "Signal", "Action"]
        ].copy()
        display_portfolio["Buy Price"] = display_portfolio["Buy Price"].map(money)
        display_portfolio["Total Cost"] = display_portfolio["Total Cost"].map(money)
        display_portfolio["Current Price"] = display_portfolio["Current Price"].map(money)
        display_portfolio["Value"] = display_portfolio["Value"].map(money)
        display_portfolio["Day P&L"] = display_portfolio["Day P&L"].map(money)
        display_portfolio["P&L"] = display_portfolio["P&L"].map(money)
        st.dataframe(style_signal_table(display_portfolio), use_container_width=True, hide_index=True)

with tabs[14]:
    st.subheader("IPO Radar")
    st.dataframe(IPO_RADAR, use_container_width=True, hide_index=True)

st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
