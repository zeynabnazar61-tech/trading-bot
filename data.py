"""
Marktdaten von Alpaca abrufen.
"""
from datetime import datetime, timedelta, timezone
import pandas as pd
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
from logger_setup import logger
import config

_client = StockHistoricalDataClient(config.ALPACA_API_KEY, config.ALPACA_SECRET_KEY)

def get_recent_bars(symbol: str = config.SYMBOL, lookback_days: int = 5) -> pd.DataFrame:
    """
    Holt die letzten Kerzen (Bars) fuer ein Symbol.
    Gibt ein DataFrame mit Spalten: open, high, low, close, volume zurueck.
    """
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=lookback_days)
    request = StockBarsRequest(
        symbol_or_symbols=symbol,
        timeframe=TimeFrame(config.TIMEFRAME_MINUTES, TimeFrameUnit.Minute),
        start=start,
        end=end,
        feed="iex",
    )
    try:
        bars = _client.get_stock_bars(request)
        df = bars.df
        if df.empty:
            logger.warning(f"Keine Daten fuer {symbol} erhalten.")
            return df
        if isinstance(df.index, pd.MultiIndex):
            df = df.xs(symbol, level=0)
        return df
    except Exception as e:
        logger.error(f"Fehler beim Abrufen der Daten: {e}")
        return pd.DataFrame()
