"""
Backtesting fuer die Trailing-Stop-Vergleichsvariante (ZOZ-40).
NUR fuer Backtest-Vergleiche - wird nicht in main.py eingebunden.

Gleicher Einstieg wie backtest.py (Golden Cross via strategy_trailing.generate_entry_signal),
aber Ausstieg ueber Trailing-Stop (TRAILING_STOP_PCT) mit hartem Stop-Loss
(STOP_LOSS_PCT) als Sicherheitsnetz statt festem Take-Profit / Death-Cross.

Nutzung:
    python backtest_trailing.py --symbol NVDA --days 730 --trailing-stop-pct 0.05
"""
import argparse
import pandas as pd
import numpy as np

import config
from data import get_recent_bars
from strategy_trailing import generate_entry_signal, should_exit_trailing, should_exit_hard_stop_loss
from logger_setup import get_logger

logger = get_logger("backtest_trailing")


def run_backtest(symbol: str, days: int, starting_cash: float = 10000.0,
                  trailing_stop_pct: float = None):
    if trailing_stop_pct is None:
        trailing_stop_pct = config.TRAILING_STOP_PCT

    df = get_recent_bars(symbol, lookback_days=days)
    if df.empty:
        logger.error("Keine historischen Daten verfügbar für Backtest.")
        return

    cash = starting_cash
    position_qty = 0
    entry_price = 0.0
    highest_price_since_entry = 0.0
    equity_curve = []
    trades = []

    min_len = max(config.LONG_WINDOW, config.TREND_WINDOW) + 1
    for i in range(min_len, len(df)):
        window_df = df.iloc[: i + 1]
        price = float(window_df["close"].iloc[-1])

        if position_qty == 0:
            signal_type = generate_entry_signal(window_df)
            if signal_type == "BUY":
                position_qty = int(config.MAX_POSITION_SIZE_USD // price)
                if position_qty > 0:
                    cash -= position_qty * price
                    entry_price = price
                    highest_price_since_entry = price
        else:
            highest_price_since_entry = max(highest_price_since_entry, price)
            exit_trailing = should_exit_trailing(highest_price_since_entry, price, trailing_stop_pct)
            exit_stop_loss = should_exit_hard_stop_loss(entry_price, price)

            if exit_trailing or exit_stop_loss:
                proceeds = position_qty * price
                cash += proceeds
                pnl = (price - entry_price) * position_qty
                trades.append(pnl)
                position_qty = 0
                entry_price = 0.0
                highest_price_since_entry = 0.0

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
    print(f"BACKTEST ERGEBNISSE (TRAILING-STOP): {symbol} ({days} Tage)")
    print(f"Trailing-Stop:       {trailing_stop_pct:.1%}")
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

    return {
        "total_return_pct": total_return_pct,
        "trades": len(trades),
        "win_rate": win_rate,
        "sharpe": sharpe,
        "max_drawdown_pct": max_drawdown_pct,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backtest der Trailing-Stop-Vergleichsvariante")
    parser.add_argument("--symbol", default=config.SYMBOL)
    parser.add_argument("--days", type=int, default=180)
    parser.add_argument("--trailing-stop-pct", type=float, default=config.TRAILING_STOP_PCT,
                         help="Trailing-Stop in Prozent, z.B. 0.05 fuer 5 Prozent")
    args = parser.parse_args()

    run_backtest(args.symbol, args.days, trailing_stop_pct=args.trailing_stop_pct)
