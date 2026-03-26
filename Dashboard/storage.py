import json
import pandas as pd
from config import PORTFOLIO_FILE
from utils import safe_float


def ensure_portfolio_columns(df: pd.DataFrame) -> pd.DataFrame:
    clean = pd.DataFrame(df).copy()
    schema = {
        'Asset': '',
        'Units': 0.0,
        'Price Per Unit': 0.0,
        'Total Price': 0.0,
    }

    for col, default in schema.items():
        if col not in clean.columns:
            clean[col] = default

    clean = clean[['Asset', 'Units', 'Price Per Unit', 'Total Price']]
    clean['Asset'] = clean['Asset'].astype(str).replace('nan', '').str.strip()
    clean['Units'] = pd.to_numeric(clean['Units'], errors='coerce').fillna(0.0)
    clean['Price Per Unit'] = pd.to_numeric(clean['Price Per Unit'], errors='coerce').fillna(0.0)
    clean['Total Price'] = pd.to_numeric(clean['Total Price'], errors='coerce').fillna(0.0)
    return clean


def load_portfolio() -> pd.DataFrame:
    if not PORTFOLIO_FILE.exists():
        return ensure_portfolio_columns(pd.DataFrame())

    try:
        with PORTFOLIO_FILE.open('r', encoding='utf-8') as f:
            data = json.load(f)
        return ensure_portfolio_columns(pd.DataFrame(data))
    except Exception:
        return ensure_portfolio_columns(pd.DataFrame())


def save_portfolio(df: pd.DataFrame) -> None:
    clean = ensure_portfolio_columns(df)
    clean = clean[
        (clean['Asset'] != '')
        | (clean['Units'] != 0)
        | (clean['Price Per Unit'] != 0)
        | (clean['Total Price'] != 0)
    ].copy()

    with PORTFOLIO_FILE.open('w', encoding='utf-8') as f:
        json.dump(clean.to_dict('records'), f, indent=2)


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
