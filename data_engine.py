import yfinance as yf
import pandas as pd
from datetime import datetime
from typing import Optional


# =====================================
# SMART MONEY SCANNER PRO
# DATA ENGINE V1
# =====================================

DATA_SOURCE = "Yahoo Finance"
DEFAULT_PERIOD = "2y"
DEFAULT_INTERVAL = "1d"


def normalize_symbol(symbol: str, market: str) -> str:
    """Convert symbols to Yahoo Finance format."""

    symbol = symbol.strip().upper()

    if market == "TEL AVIV" and not symbol.endswith(".TA"):
        symbol += ".TA"

    return symbol


def download_stock_data(
    symbol: str,
    market: str = "NASDAQ",
    period: str = DEFAULT_PERIOD,
    interval: str = DEFAULT_INTERVAL
) -> Optional[pd.DataFrame]:

    ticker = normalize_symbol(symbol, market)

    try:
        data = yf.download(
            ticker,
            period=period,
            interval=interval,
            auto_adjust=False,
            progress=False,
            threads=False
        )

        if data is None or data.empty:
            return None

        # Handle Yahoo Finance multi-level columns
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)

        required = ["Open", "High", "Low", "Close", "Volume"]

        if not all(col in data.columns for col in required):
            return None

        data = data[required].copy()

        data = data.dropna()
        data = data[~data.index.duplicated(keep="last")]
        data = data.sort_index()

        # Keep only completed daily sessions
        if interval == "1d":
            today = pd.Timestamp(datetime.now().date())
            data = data[data.index.date < today.date()]

        if data.empty:
            return None

        data["Turnover"] = data["Close"] * data["Volume"]

        return data

    except Exception as error:
        print(f"Data error for {ticker}: {error}")
        return None


def download_multiple_stocks(
    symbols: list,
    market: str = "NASDAQ",
    period: str = DEFAULT_PERIOD,
    interval: str = DEFAULT_INTERVAL
) -> dict:

    results = {}

    for symbol in symbols:

        data = download_stock_data(
            symbol=symbol,
            market=market,
            period=period,
            interval=interval
        )

        if data is not None:
            results[symbol] = data

    return results


def get_data_status(data: Optional[pd.DataFrame]) -> dict:

    if data is None or data.empty:
        return {
            "status": "NO DATA",
            "last_update": None,
            "records": 0
        }

    return {
        "status": "AVAILABLE",
        "last_update": str(data.index[-1]),
        "records": len(data),
        "source": DATA_SOURCE
    }
