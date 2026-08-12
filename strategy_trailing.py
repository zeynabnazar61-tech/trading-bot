"""
Vergleichs-Variante (ZOZ-40, NUR fuer Backtest, NICHT live geschaltet):
Gleicher Einstieg wie strategy.py (Golden Cross mit Trend- und Rauschfilter),
aber Ausstieg ueber einen Trailing-Stop statt festem Take-Profit / Death-Cross.

strategy.py bleibt dabei unveraendert - diese Datei ist eine separate Kopie
mit angepasster Exit-Logik, die nur von backtest_trailing.py verwendet wird.
"""
import pandas as pd
import config
from logger_setup import get_logger

logger = get_logger("strategy_trailing")


def generate_entry_signal(df: pd.DataFrame) -> str:
    """
    Erwartet ein DataFrame mit einer 'close' Spalte.
    Gibt "BUY" oder "HOLD" zurueck (kein SELL - der Ausstieg laeuft
    ausschliesslich ueber den Trailing-Stop / harten Stop-Loss, siehe unten).

    Einstiegslogik ist identisch zu strategy.generate_signal():
    Golden Cross (SMA_SHORT kreuzt SMA_LONG von unten) + Trendfilter (SMA_TREND)
    + Rauschfilter (Mindestabstand beim Crossover).
    """
    min_len = max(config.LONG_WINDOW, config.TREND_WINDOW) + 1
    if df.empty or len(df) < min_len:
        return "HOLD"

    df = df.copy()
    df["sma_short"] = df["close"].rolling(window=config.SHORT_WINDOW).mean()
    df["sma_long"] = df["close"].rolling(window=config.LONG_WINDOW).mean()
    df["sma_trend"] = df["close"].rolling(window=config.TREND_WINDOW).mean()

    prev_short, prev_long = df["sma_short"].iloc[-2], df["sma_long"].iloc[-2]
    curr_short, curr_long = df["sma_short"].iloc[-1], df["sma_long"].iloc[-1]
    curr_price = df["close"].iloc[-1]
    curr_trend = df["sma_trend"].iloc[-1]

    if pd.isna(prev_short) or pd.isna(prev_long) or pd.isna(curr_trend):
        return "HOLD"

    crossed_up = prev_short <= prev_long and curr_short > curr_long

    gap_pct = abs(curr_short - curr_long) / curr_long if curr_long else 0
    if gap_pct < config.MIN_CROSSOVER_MARGIN_PCT:
        return "HOLD"

    uptrend = curr_price > curr_trend

    if crossed_up and uptrend:
        logger.info(f"Golden Cross BESTAETIGT: SMA{config.SHORT_WINDOW}={curr_short:.2f} > "
                    f"SMA{config.LONG_WINDOW}={curr_long:.2f}, im Aufwaertstrend")
        return "BUY"

    return "HOLD"


def should_exit_trailing(highest_price_since_entry: float, current_price: float,
                          trailing_stop_pct: float = None) -> bool:
    """
    Trailing-Stop: True, wenn der aktuelle Preis um mind. trailing_stop_pct
    unter das seit dem Einstieg erreichte Hoch gefallen ist.
    """
    if trailing_stop_pct is None:
        trailing_stop_pct = config.TRAILING_STOP_PCT
    if highest_price_since_entry <= 0:
        return False
    return current_price <= highest_price_since_entry * (1 - trailing_stop_pct)


def should_exit_hard_stop_loss(entry_price: float, current_price: float,
                                stop_loss_pct: float = None) -> bool:
    """
    Harter Stop-Loss (Sicherheitsnetz, bestehender STOP_LOSS_PCT ab Einstiegspreis),
    falls der Trailing-Stop aus irgendeinem Grund nicht greift.
    """
    if stop_loss_pct is None:
        stop_loss_pct = config.STOP_LOSS_PCT
    if entry_price <= 0:
        return False
    return current_price <= entry_price * (1 - stop_loss_pct)
