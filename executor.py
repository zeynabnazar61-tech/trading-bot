"""
Platziert die tatsächlichen Orders über die Alpaca API.
Enthält Fehlerbehandlung für Verbindungsprobleme/API-Fehler,
damit der Bot bei einem Problem nicht abstürzt, sondern es sauber loggt.
"""
import time

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce, OrderStatus

import config
from logger_setup import get_logger
from notifier import send_telegram

logger = get_logger("executor")

_client = TradingClient(config.ALPACA_API_KEY, config.ALPACA_SECRET_KEY, paper=config.ALPACA_PAPER)

# Endzustaende, in denen eine Order NICHT (mehr) gefuellt werden kann/wird.
# Konservativ weit gefasst, damit der Bot in keinem dieser Faelle faelschlich
# auf "irgendwann noch gefuellt" wartet oder gar record_trade() aufruft.
_TERMINAL_UNFILLED_STATUSES = {
    OrderStatus.REJECTED,
    OrderStatus.CANCELED,
    OrderStatus.EXPIRED,
    OrderStatus.DONE_FOR_DAY,
    OrderStatus.STOPPED,
    OrderStatus.SUSPENDED,
    OrderStatus.REPLACED,
}


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


def wait_for_order_fill(order, timeout_seconds: float = None, poll_interval_seconds: float = None):
    """
    Pollt den Order-Status ueber get_order_by_id(), bis die Order 'filled' ist
    oder ein Endzustand erreicht wird (z.B. 'rejected'/'canceled'), oder das
    Timeout erreicht ist.

    Gibt bei erfolgreichem Fill die aktualisierte Order (mit filled_qty/
    filled_avg_price) zurueck. Gibt None zurueck bei Timeout, Ablehnung oder
    Stornierung - der Aufrufer darf in diesem Fall KEIN record_trade() aufrufen,
    da der tatsaechliche Kontostand dann nicht sicher bekannt ist.
    """
    if order is None or getattr(order, "id", None) is None:
        return None

    if timeout_seconds is None:
        timeout_seconds = config.ORDER_FILL_TIMEOUT_SECONDS
    if poll_interval_seconds is None:
        poll_interval_seconds = config.ORDER_FILL_POLL_INTERVAL_SECONDS

    order_id = order.id
    max_attempts = max(1, int(timeout_seconds // poll_interval_seconds))
    last_status = getattr(order, "status", None)

    for attempt in range(1, max_attempts + 1):
        try:
            current = _client.get_order_by_id(order_id)
        except Exception as e:
            logger.error(
                f"Fehler beim Abfragen des Order-Status ({order_id}), "
                f"Versuch {attempt}/{max_attempts}: {e}"
            )
            current = None

        if current is not None:
            last_status = current.status
            if current.status == OrderStatus.FILLED:
                logger.info(
                    f"Order {order_id} gefuellt (Versuch {attempt}/{max_attempts}): "
                    f"filled_qty={current.filled_qty}, filled_avg_price={current.filled_avg_price}"
                )
                return current
            if current.status in _TERMINAL_UNFILLED_STATUSES:
                msg = (
                    f"Order {order_id} wurde NICHT ausgefuehrt (Status: {current.status}) "
                    "-> kein Trade wird erfasst."
                )
                logger.warning(msg)
                send_telegram(msg)
                return None

        if attempt < max_attempts:
            time.sleep(poll_interval_seconds)

    msg = (
        f"Timeout beim Warten auf Fill-Bestaetigung fuer Order {order_id} "
        f"nach {max_attempts} Versuchen (letzter bekannter Status: {last_status}) "
        "-> kein Trade wird erfasst. Order-/Kontostatus manuell pruefen!"
    )
    logger.error(msg)
    send_telegram(msg)
    return None


def buy(symbol: str, qty: int):
    return place_market_order(symbol, qty, OrderSide.BUY)


def sell(symbol: str, qty: int):
    return place_market_order(symbol, qty, OrderSide.SELL)


def close_position(symbol: str = config.SYMBOL):
    """Schließt die komplette offene Position (z.B. bei Stop-Loss/Take-Profit).

    Gibt die Order zurück (zum Warten auf Fill-Bestätigung via
    wait_for_order_fill), oder None bei einem API-Fehler.
    """
    try:
        order = _client.close_position(symbol)
        msg = f"Position in {symbol} geschlossen."
        logger.info(msg)
        send_telegram(msg)
        return order
    except Exception as e:
        logger.error(f"Fehler beim Schließen der Position: {e}")
        return None


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
