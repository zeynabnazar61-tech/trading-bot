"""
Platziert die tatsächlichen Orders über die Alpaca API.
Enthält Fehlerbehandlung für Verbindungsprobleme/API-Fehler,
damit der Bot bei einem Problem nicht abstürzt, sondern es sauber loggt.
"""
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce

import config
from logger_setup import get_logger
from notifier import send_telegram

logger = get_logger("executor")

_client = TradingClient(config.ALPACA_API_KEY, config.ALPACA_SECRET_KEY, paper=config.ALPACA_PAPER)


def get_open_position(symbol: str = config.SYMBOL):
    """Gibt die aktuelle offene Position zurück, oder None falls keine vorhanden."""
    try:
        return _client.get_open_position(symbol)
    except Exception:
        return None  # keine offene Position vorhanden


def place_market_order(symbol: str, qty: int, side: OrderSide):
    """Platziert eine Market-Order mit Fehlerbehandlung."""
    if qty <= 0:
        logger.warning(f"Ungültige Ordergröße ({qty}) -> Order übersprungen.")
        return None

    order_request = MarketOrderRequest(
        symbol=symbol,
        qty=qty,
        side=side,
        time_in_force=TimeInForce.DAY,
    )

    try:
        order = _client.submit_order(order_request)
        msg = f"Order platziert: {side.value.upper()} {qty}x {symbol}"
        logger.info(msg)
        send_telegram(msg)
        return order
    except Exception as e:
        error_msg = f"FEHLER bei Order ({side.value} {qty}x {symbol}): {e}"
        logger.error(error_msg)
        send_telegram(error_msg)
        return None


def buy(symbol: str, qty: int):
    return place_market_order(symbol, qty, OrderSide.BUY)


def sell(symbol: str, qty: int):
    return place_market_order(symbol, qty, OrderSide.SELL)


def close_position(symbol: str = config.SYMBOL):
    """Schließt die komplette offene Position (z.B. bei Stop-Loss/Take-Profit)."""
    try:
        _client.close_position(symbol)
        msg = f"Position in {symbol} geschlossen."
        logger.info(msg)
        send_telegram(msg)
    except Exception as e:
        logger.error(f"Fehler beim Schließen der Position: {e}")


def get_account_info():
    """Gibt Kontostand und Kaufkraft zurück - nützlich zum Monitoring."""
    try:
        account = _client.get_account()
        return {
            "cash": float(account.cash),
            "portfolio_value": float(account.portfolio_value),
            "buying_power": float(account.buying_power),
        }
    except Exception as e:
        logger.error(f"Fehler beim Abrufen der Kontodaten: {e}")
        return None
