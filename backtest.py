"""
Backtesting: Testet die Strategie gegen historische Kursdaten,
BEVOR überhaupt Paper-Trading gestartet wird.

Ausgabe: Sharpe Ratio, Max Drawdown, Win-Rate, Gesamtrendite.

Nutzung:
    python backtest.py --days 365
"""
import argparse
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone

import config
from data import get_recent_bars
from strategy import generate_signal
from logger_setup import get_logger

logger = get_logger("backtest")


def run_backtest(symbol: str, days: int, starting_cash: float = 10000.0):
    df = get_recent_bars(symbol, lookback_days=days)
    if df.empty:
        logger.error("Keine historischen Daten verfügbar für Backtest.")
        return

    cash = starting_cash
    position_qty = 0
    entry_price = 0.0
    equity_curve = []
    trades = []

    for i in range(config.LONG_WINDOW + 1, len(df)):
        window_df = df.iloc[: i + 1]
        signal_type = generate_signal(window_df)
        price = float(window_df["close"].iloc[-1])

        if signal_type == "BUY" and position_qty == 0:
            position_qty = int(config.MAX_POSITION_SIZE_USD // price)
            if position_qty > 0:
                cash -= position_qty * price
                entry_price = price

        elif signal_type == "SELL" and position_qty > 0:
            proceeds = position_qty * price
            cash += proceeds
            pnl = (price - entry_price) * position_qty
            trades.append(pnl)
            position_qty = 0

        current_equity = cash + (position_qty * price)
        equity_curve.append(current_equity)

    # Offene Position am Ende glattstellen für saubere Auswertung
    if position_qty > 0:
        final_price = float(df["close"].iloc[-1])
        cash += position_qty * final_price
        trades.append((final_price - entry_price) * position_qty)

    equity_series = pd.Series(equity_curve)
    returns = equity_series.pct_change().dropna()

    total_return_pct = (cash - starting_cash) / starting_cash * 100
    win_rate = (sum(1 for t in trades if t > 0) / len(trades) * 100) if trades else 0
    sharpe = (returns.mean() / returns.std() * np.sqrt(252)) if returns.std() > 0 else 0

    running_max = equity_series.cummax()
    drawdown = (equity_series - running_max) / running_max
    max_drawdown_pct = drawdown.min() * 100 if not drawdown.empty else 0

    print("\n" + "=" * 50)
    print(f"BACKTEST ERGEBNISSE: {symbol} ({days} Tage)")
    print("=" * 50)
    print(f"Startkapital:        {starting_cash:,.2f} USD")
    print(f"Endkapital:          {cash:,.2f} USD")
    print(f"Gesamtrendite:       {total_return_pct:.2f}%")
    print(f"Anzahl Trades:       {len(trades)}")
    print(f"Win-Rate:            {win_rate:.1f}%")
    print(f"Sharpe Ratio:        {sharpe:.2f}")
    print(f"Max Drawdown:        {max_drawdown_pct:.2f}%")
    print("=" * 50)
    print("Hinweis: Vergangene Ergebnisse garantieren keine zukünftige Performance.\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backtest der Trading-Strategie")
    parser.add_argument("--symbol", default=config.SYMBOL)
    parser.add_argument("--days", type=int, default=180)
    args = parser.parse_args()

    run_backtest(args.symbol, args.days)
