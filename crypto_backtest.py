"""
Backtest der Krypto-Trend-Strategie (SMA-Crossover + Trendfilter aus crypto_advisor.py).

Rechnet fuer jeden beobachteten Coin durch, wie sich die Strategie in der
Vergangenheit geschlagen haette - im Vergleich zu simplem Buy&Hold.
Handelt NICHT automatisch, nur zur Einschaetzung ob die Signale ueberhaupt
etwas taugen, bevor man ihnen mit echtem Geld vertraut.

Ausfuehren mit: python crypto_backtest.py
"""
import pandas as pd

from crypto_advisor import (
    COINS,
    COIN_SHORT_WINDOW,
    COIN_LONG_WINDOW,
    COIN_TREND_WINDOW,
    COIN_MIN_CROSSOVER_MARGIN_PCT,
    get_coin_history,
)
from logger_setup import get_logger

logger = get_logger("crypto_backtest")

BACKTEST_DAYS = 365
STARTING_CAPITAL = 1000.0  # virtuelle Testsumme, nicht dein echtes Geld


def backtest_coin(coin_id: str, symbol: str, days: int = BACKTEST_DAYS,
                   starting_capital: float = STARTING_CAPITAL) -> dict:
    df = get_coin_history(coin_id, days=days)
    if len(df) < COIN_TREND_WINDOW + 2:
        return {"symbol": symbol, "error": "nicht genug Kurshistorie"}

    df["sma_short"] = df["close"].rolling(window=COIN_SHORT_WINDOW).mean()
    df["sma_long"] = df["close"].rolling(window=COIN_LONG_WINDOW).mean()
    df["sma_trend"] = df["close"].rolling(window=COIN_TREND_WINDOW).mean()

    cash = starting_capital
    coins_held = 0.0
    in_position = False
    trades = 0

    for i in range(1, len(df)):
        prev_short, prev_long = df["sma_short"].iloc[i - 1], df["sma_long"].iloc[i - 1]
        curr_short, curr_long = df["sma_short"].iloc[i], df["sma_long"].iloc[i]
        curr_trend = df["sma_trend"].iloc[i]
        curr_price = df["close"].iloc[i]

        if pd.isna(prev_short) or pd.isna(prev_long) or pd.isna(curr_trend):
            continue

        crossed_up = prev_short <= prev_long and curr_short > curr_long
        crossed_down = prev_short >= prev_long and curr_short < curr_long
        gap_pct = abs(curr_short - curr_long) / curr_long if curr_long else 0

        if gap_pct < COIN_MIN_CROSSOVER_MARGIN_PCT:
            continue

        uptrend = curr_price > curr_trend
        downtrend = curr_price < curr_trend

        if crossed_up and uptrend and not in_position:
            coins_held = cash / curr_price
            cash = 0.0
            in_position = True
            trades += 1
        elif crossed_down and downtrend and in_position:
            cash = coins_held * curr_price
            coins_held = 0.0
            in_position = False
            trades += 1

    final_price = df["close"].iloc[-1]
    final_value = cash + coins_held * final_price
    strategy_return_pct = (final_value / starting_capital - 1) * 100

    buy_hold_value = starting_capital / df["close"].iloc[0] * final_price
    buy_hold_return_pct = (buy_hold_value / starting_capital - 1) * 100

    return {
        "symbol": symbol,
        "trades": trades,
        "strategy_return_pct": strategy_return_pct,
        "buy_hold_return_pct": buy_hold_return_pct,
        "strategy_besser": strategy_return_pct > buy_hold_return_pct,
    }


def main():
    logger.info(f"Backtest ueber die letzten {BACKTEST_DAYS} Tage, virtuelle Startsumme {STARTING_CAPITAL}€.")
    for coin_id, symbol in COINS.items():
        try:
            result = backtest_coin(coin_id, symbol)
        except Exception as e:
            logger.error(f"Backtest fuer {symbol} fehlgeschlagen: {e}")
            continue

        if "error" in result:
            logger.info(f"{symbol}: {result['error']}")
            continue

        besser = "Strategie schlaegt Buy&Hold" if result["strategy_besser"] else "Buy&Hold war besser"
        logger.info(
            f"{symbol}: Strategie {result['strategy_return_pct']:+.2f}% | "
            f"Buy&Hold {result['buy_hold_return_pct']:+.2f}% | "
            f"{result['trades']} Trades | {besser}"
        )


if __name__ == "__main__":
    main()
