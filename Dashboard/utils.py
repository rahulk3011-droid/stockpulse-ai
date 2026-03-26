import pandas as pd


def safe_float(value, default: float = 0.0) -> float:
    try:
        if pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def money(value: float) -> str:
    value = safe_float(value)
    if abs(value) < 10:
        return f'${value:,.4f}'
    return f'${value:,.2f}'


def pct_text(value: float) -> str:
    return f'{safe_float(value):,.2f}%'


def market_from_ticker(ticker: str) -> str:
    if ticker.endswith('.AX'):
        return 'ASX'
    if '-AUD' in ticker or '-USD' in ticker:
        return 'Crypto'
    return 'US'
