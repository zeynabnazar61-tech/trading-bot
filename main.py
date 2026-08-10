"""
Hauptskript - startet die Trading-Schleife.

Ablauf pro Durchlauf:
1. Prüfen ob Risikomanagement Handel überhaupt erlaubt
2. Marktdaten holen
3. Strategie-Signal berechnen (BUY/SELL/HOLD)
4. Falls Signal + kein Risiko-Stopp -> Order platzieren
5. Warten, wiederholen

WICHTIG: Läuft standardmäßig im Paper-Trading Modus (config.ALPACA_PAPER=true).
Erst NACH ausgiebigem Test auf "false" stellen - und selbst dann mit Vorsicht!
"""
import time
import signal
import sys

import config
from logger_setup import get_logger
from risk_manager import RiskManager
import data
import strategy
import executor
from notifier import send_telegram

logger = get_logger("main")
risk_manager = RiskManager()

_running = True


def _handle_shutdown(signum, frame):
    """Sauberes Beenden mit Strg+C, statt hartem Abbruch."""
    global _running
    logger.info("Beende Bot sauber... (Strg+C erkannt)")
    _running = False


signal.signal(signal.SIGINT, _handle_shutdown)
signal.signal(signal.SIGTERM, _handle_shutdown)


def trading_cycle():
    """Ein einzelner Durchlauf der Handelslogik."""
    if not risk_manager.can_trade():
        return

    try:
        df = data.get_recent_bars(config.SYMBOL)
    except Exception as e:
        logger.error(f"Konnte Marktdaten nicht abrufen, überspringe Zyklus: {e}")
        return

    if df.empty:
        return

    signal_type = strategy.generate_signal(df)
    current_price = float(df["close"].iloc[-1])
    position = executor.get_open_position(config.SYMBOL)

    position_closed_this_cycle = False

    if signal_type == "BUY" and position is None:
        qty = risk_manager.calculate_position_size(current_price)
        if qty > 0:
            order = executor.buy(config.SYMBOL, qty)
            if order:
                risk_manager.record_trade()
                stop_loss = risk_manager.get_stop_loss_price(current_price)
                take_profit = risk_manager.get_take_profit_price(current_price)
                logger.info(f"Eingestiegen bei {current_price:.2f}. Stop-Loss: {stop_loss}, Take-Profit: {take_profit}")

    elif signal_type == "SELL" and position is not None:
        qty = int(float(position.qty))
        entry_price = float(position.avg_entry_price)
        order = executor.sell(config.SYMBOL, qty)
        if order:
            risk_manager.record_trade(pnl=(current_price - entry_price) * qty)
            position_closed_this_cycle = True

    else:
        logger.info(f"Kein Handlungsbedarf (Signal: {signal_type}, Position vorhanden: {position is not None})")

    # Stop-Loss / Take-Profit prüfen, falls Position offen ist (und nicht bereits
    # in diesem Zyklus per SELL-Signal geschlossen wurde, sonst doppelte PnL-Erfassung)
    if position is not None and not position_closed_this_cycle:
        entry_price = float(position.avg_entry_price)
        position_qty = int(float(position.qty))
        stop_loss = risk_manager.get_stop_loss_price(entry_price)
        take_profit = risk_manager.get_take_profit_price(entry_price)

        if current_price <= stop_loss:
            logger.warning(f"Stop-Loss ausgelöst bei {current_price:.2f} (Einstieg war {entry_price:.2f})")
            executor.close_position(config.SYMBOL)
            risk_manager.record_trade(pnl=(current_price - entry_price) * position_qty)
        elif current_price >= take_profit:
            logger.info(f"Take-Profit ausgelöst bei {current_price:.2f} (Einstieg war {entry_price:.2f})")
            executor.close_position(config.SYMBOL)
            risk_manager.record_trade(pnl=(current_price - entry_price) * position_qty)


def main():
    config.validate_config()
    logger.info(f"Bot gestartet. Symbol: {config.SYMBOL}, Paper-Trading: {config.ALPACA_PAPER}")
    send_telegram(f"🤖 Trading-Bot gestartet (Symbol: {config.SYMBOL}, Paper: {config.ALPACA_PAPER})")

    account = executor.get_account_info()
    if account:
        logger.info(f"Kontostand: {account}")

    while _running:
        try:
            trading_cycle()
        except Exception as e:
            # Fängt ALLES ab, damit der Bot nicht wegen eines einzelnen
            # Fehlers komplett abstürzt und unbeaufsichtigt offline bleibt.
            logger.error(f"Unerwarteter Fehler im Handelszyklus: {e}", exc_info=True)

        time.sleep(config.LOOP_INTERVAL_SECONDS)

    logger.info("Bot beendet.")
    send_telegram("🛑 Trading-Bot wurde beendet.")
    sys.exit(0)


if __name__ == "__main__":
    main()
