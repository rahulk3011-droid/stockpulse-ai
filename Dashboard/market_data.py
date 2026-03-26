import pandas as pd
import streamlit as st
import yfinance as yf

from signals import action_from_signal, signal_and_reason
from utils import market_from_ticker, safe_float


@st.cache_data(ttl=1800)
def download_market_data(tickers):
    raw = yf.download(
        tickers=tickers,
        period='6mo',
        interval='1d',
        auto_adjust=True,
        group_by='ticker',
        progress=False,
        threads=True,
    )
    return raw


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


def build_lookup_maps(industry_groups: dict):
    asset_to_symbol = {}
    asset_to_group = {}
    symbol_to_asset = {}

    for group_name, assets in industry_groups.items():
        for asset_name, ticker in assets.items():
            asset_to_symbol[asset_name] = ticker
            asset_to_group[asset_name] = group_name
            symbol_to_asset[ticker] = asset_name

    return asset_to_symbol, asset_to_group, symbol_to_asset


def build_market_table(raw, all_tickers, symbol_to_asset, asset_to_group) -> pd.DataFrame:
    rows = []

    for ticker in all_tickers:
        try:
            df = raw[ticker].dropna().copy()
        except Exception:
            continue

        if df.empty or len(df) < 3:
            continue

        current_price = safe_float(df['Close'].iloc[-1])
        previous_close = safe_float(df['Close'].iloc[-2])
        week_close = safe_float(df['Close'].iloc[-6]) if len(df) >= 6 else previous_close
        month_close = safe_float(df['Close'].iloc[-22]) if len(df) >= 22 else previous_close
        high_52 = safe_float(df['High'].tail(126).max())
        low_52 = safe_float(df['Low'].tail(126).min())
        volume = safe_float(df['Volume'].iloc[-1]) if 'Volume' in df.columns else 0.0
        avg_volume = safe_float(df['Volume'].tail(20).mean()) if 'Volume' in df.columns else 0.0
        volume_ratio = volume / avg_volume if avg_volume else 0.0

        day_pct = ((current_price / previous_close) - 1) * 100 if previous_close else 0.0
        week_pct = ((current_price / week_close) - 1) * 100 if week_close else 0.0
        month_pct = ((current_price / month_close) - 1) * 100 if month_close else 0.0

        signal, reason = signal_and_reason(day_pct, week_pct, month_pct, volume_ratio)
        asset_name = symbol_to_asset.get(ticker, ticker)
        group_name = asset_to_group.get(asset_name, 'Other')

        rows.append(
            {
                'Industry': group_name,
                'Asset': asset_name,
                'Ticker': ticker,
                'Market': market_from_ticker(ticker),
                'Current Price': current_price,
                'Previous Close': previous_close,
                'Day %': day_pct,
                'Week %': week_pct,
                'Month %': month_pct,
                '52W High': high_52,
                '52W Low': low_52,
                'Volume Ratio': volume_ratio,
                'Signal': signal,
                'Action': action_from_signal(signal),
                'Why': reason,
            }
        )

    market = pd.DataFrame(rows)
    if market.empty:
        return market
    return market.sort_values(['Industry', 'Asset']).reset_index(drop=True)


def apply_filters(df: pd.DataFrame, search_text: str, industry_filter: str, signal_filter: str, market_filter: str, max_price: float):
    out = df.copy()

    if search_text.strip():
        q = search_text.strip().lower()
        out = out[
            out['Asset'].str.lower().str.contains(q, na=False)
            | out['Ticker'].str.lower().str.contains(q, na=False)
        ]

    if industry_filter != 'All':
        out = out[out['Industry'] == industry_filter]

    if signal_filter != 'All':
        out = out[out['Signal'] == signal_filter]

    if market_filter != 'All':
        out = out[out['Market'] == market_filter]

    out = out[out['Current Price'] <= max_price]
    return out.copy()


def best_of_group(df: pd.DataFrame, group_name: str):
    group_df = df[df['Industry'] == group_name].copy()
    if group_df.empty:
        return None

    sort_map = {'🔵 BLUE': 4, '🟢 GREEN': 3, '🟡 YELLOW': 2, '🔴 RED': 1}
    group_df['rank_score'] = group_df['Signal'].map(sort_map).fillna(0)
    group_df = group_df.sort_values(['rank_score', 'Day %', 'Week %'], ascending=[False, False, False])
    return group_df.iloc[0]
