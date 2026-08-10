"""
Strategie: Moving Average Crossover MIT Trendfilter und Rauschfilter.
"""
import pandas as pd
import config
from logger_setup import get_logger

logger = get_logger("strategy")


def generate_signal(df: pd.DataFrame) -> str:
    """
    Erwartet ein DataFrame mit einer 'close' Spalte.
    Gibt "BUY", "SELL" oder "HOLD" zurueck.

    Verbesserungen gegenueber der einfachen Version:
    - Trendfilter (SMA100): BUY nur im Aufwaertstrend, SELL nur im Abwaertstrend.
    - Mindestabstand beim Crossover, um Rauschen (Whipsaws) zu vermeiden.
    """
    min_len = max(config.LONG_WINDOW, config.TREND_WINDOW) + 1
    if df.empty or len(df) < min_len:
        logger.info("Nicht genug Daten fuer ein Signal -> HOLD")
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
    crossed_down = prev_short >= prev_long and curr_short < curr_long

    # Rauschfilter: Abstand zwischen den Linien muss gross genug sein
    gap_pct = abs(curr_short - curr_long) / curr_long if curr_long else 0
    if gap_pct < config.MIN_CROSSOVER_MARGIN_PCT:
        logger.info(f"Crossover-Abstand zu gering ({gap_pct:.4%}) -> HOLD (Rauschfilter)")
        return "HOLD"

    # Trendfilter: nur in Trendrichtung handeln
    uptrend = curr_price > curr_trend
    downtrend = curr_price < curr_trend

    if crossed_up:
        if not uptrend:
            logger.info(
                f"Golden Cross erkannt, aber Preis ({curr_price:.2f}) unter Trend-SMA "
                f"({curr_trend:.2f}) -> HOLD (Trendfilter)"
            )
            return "HOLD"
        logger.info(f"Golden Cross BESTAETIGT: SMA{config.SHORT_WINDOW}={curr_short:.2f} > "
                    f"SMA{config.LONG_WINDOW}={curr_long:.2f}, im Aufwaertstrend")
        return "BUY"
    elif crossed_down:
        if not downtrend:
            logger.info(
                f"Death Cross erkannt, aber Preis ({curr_price:.2f}) ueber Trend-SMA "
                f"({curr_trend:.2f}) -> HOLD (Trendfilter)"
            )
            return "HOLD"
        logger.info(f"Death Cross BESTAETIGT: SMA{config.SHORT_WINDOW}={curr_short:.2f} < "
                    f"SMA{config.LONG_WINDOW}={curr_long:.2f}, im Abwaertstrend")
        return "SELL"

    return "HOLD"
