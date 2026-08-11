import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from unittest.mock import MagicMock, patch

from alpaca.trading.enums import OrderSide, OrderStatus

import executor


def test_buy_places_order_with_correct_side_and_qty():
    order = MagicMock()
    with patch.object(executor, "_client") as mock_client:
        mock_client.submit_order.return_value = order
        with patch.object(executor, "send_telegram"):
            result = executor.buy("NVDA", 5)

    assert result is order
    submitted_request = mock_client.submit_order.call_args[0][0]
    assert submitted_request.symbol == "NVDA"
    assert submitted_request.qty == 5
    assert submitted_request.side == OrderSide.BUY


def test_sell_places_order_with_correct_side_and_qty():
    order = MagicMock()
    with patch.object(executor, "_client") as mock_client:
        mock_client.submit_order.return_value = order
        with patch.object(executor, "send_telegram"):
            result = executor.sell("NVDA", 3)

    assert result is order
    submitted_request = mock_client.submit_order.call_args[0][0]
    assert submitted_request.symbol == "NVDA"
    assert submitted_request.qty == 3
    assert submitted_request.side == OrderSide.SELL


def test_place_market_order_skips_when_qty_zero():
    with patch.object(executor, "_client") as mock_client:
        result = executor.buy("NVDA", 0)

    assert result is None
    mock_client.submit_order.assert_not_called()


def test_place_market_order_skips_when_qty_negative():
    with patch.object(executor, "_client") as mock_client:
        result = executor.sell("NVDA", -1)

    assert result is None
    mock_client.submit_order.assert_not_called()


def test_place_market_order_returns_none_and_logs_on_api_exception():
    with patch.object(executor, "_client") as mock_client:
        mock_client.submit_order.side_effect = Exception("API down")
        with patch.object(executor, "send_telegram") as mock_notify:
            result = executor.buy("NVDA", 5)

    assert result is None
    mock_notify.assert_called_once()
    assert "FEHLER" in mock_notify.call_args[0][0]


def test_place_market_order_returns_none_when_order_rejected():
    """Simuliert eine von Alpaca abgelehnte Order (Exception beim submit_order-Call)."""
    with patch.object(executor, "_client") as mock_client:
        mock_client.submit_order.side_effect = Exception("order rejected: insufficient buying power")
        result = executor.sell("NVDA", 2)

    assert result is None


def test_close_position_calls_client_and_notifies():
    with patch.object(executor, "_client") as mock_client:
        with patch.object(executor, "send_telegram") as mock_notify:
            executor.close_position("NVDA")

    mock_client.close_position.assert_called_once_with("NVDA")
    mock_notify.assert_called_once()


def test_close_position_handles_api_exception_without_raising():
    with patch.object(executor, "_client") as mock_client:
        mock_client.close_position.side_effect = Exception("network error")
        # Darf keine Exception nach aussen werfen.
        executor.close_position("NVDA")


def test_get_open_position_returns_position_when_present():
    fake_position = MagicMock()
    with patch.object(executor, "_client") as mock_client:
        mock_client.get_open_position.return_value = fake_position
        result = executor.get_open_position("NVDA")

    assert result is fake_position


def test_get_open_position_returns_none_when_no_position():
    with patch.object(executor, "_client") as mock_client:
        mock_client.get_open_position.side_effect = Exception("position does not exist")
        result = executor.get_open_position("NVDA")

    assert result is None


def test_get_account_info_returns_dict_on_success():
    account = MagicMock()
    account.cash = "1000.50"
    account.portfolio_value = "2000.75"
    account.buying_power = "4000.00"

    with patch.object(executor, "_client") as mock_client:
        mock_client.get_account.return_value = account
        result = executor.get_account_info()

    assert result == {
        "cash": 1000.50,
        "portfolio_value": 2000.75,
        "buying_power": 4000.00,
    }


def test_get_account_info_returns_none_on_api_exception():
    with patch.object(executor, "_client") as mock_client:
        mock_client.get_account.side_effect = Exception("API error")
        result = executor.get_account_info()

    assert result is None


def _fake_order(order_id="order-1", status=OrderStatus.NEW):
    order = MagicMock()
    order.id = order_id
    order.status = status
    return order


def _fake_filled_order(order_id="order-1", filled_qty="5", filled_avg_price="123.45"):
    order = _fake_order(order_id=order_id, status=OrderStatus.FILLED)
    order.filled_qty = filled_qty
    order.filled_avg_price = filled_avg_price
    return order


# --- wait_for_order_fill ---


def test_wait_for_order_fill_returns_immediately_when_already_filled():
    submitted_order = _fake_order()
    filled_order = _fake_filled_order()

    with patch.object(executor, "_client") as mock_client:
        mock_client.get_order_by_id.return_value = filled_order
        with patch.object(executor, "send_telegram"):
            result = executor.wait_for_order_fill(submitted_order, timeout_seconds=30, poll_interval_seconds=2)

    assert result is filled_order
    mock_client.get_order_by_id.assert_called_once_with(submitted_order.id)


def test_wait_for_order_fill_polls_multiple_times_until_filled():
    submitted_order = _fake_order()
    filled_order = _fake_filled_order()
    pending_order = _fake_order(status=OrderStatus.NEW)
    partially_filled_order = _fake_order(status=OrderStatus.PARTIALLY_FILLED)

    with patch.object(executor, "_client") as mock_client:
        mock_client.get_order_by_id.side_effect = [pending_order, partially_filled_order, filled_order]
        with patch.object(executor, "time") as mock_time, patch.object(executor, "send_telegram"):
            result = executor.wait_for_order_fill(submitted_order, timeout_seconds=30, poll_interval_seconds=2)

    assert result is filled_order
    assert mock_client.get_order_by_id.call_count == 3
    assert mock_time.sleep.call_count == 2  # nur zwischen den Versuchen, nicht danach


def test_wait_for_order_fill_times_out_and_does_not_return_order():
    submitted_order = _fake_order()
    pending_order = _fake_order(status=OrderStatus.NEW)

    with patch.object(executor, "_client") as mock_client:
        mock_client.get_order_by_id.return_value = pending_order
        with patch.object(executor, "time") as mock_time, patch.object(executor, "send_telegram") as mock_notify:
            result = executor.wait_for_order_fill(submitted_order, timeout_seconds=0.05, poll_interval_seconds=0.02)

    assert result is None
    assert mock_client.get_order_by_id.call_count == 2  # 0.05 // 0.02 = 2 Versuche
    mock_notify.assert_called_once()


def test_wait_for_order_fill_returns_none_when_order_rejected():
    submitted_order = _fake_order()
    rejected_order = _fake_order(status=OrderStatus.REJECTED)

    with patch.object(executor, "_client") as mock_client:
        mock_client.get_order_by_id.return_value = rejected_order
        with patch.object(executor, "time") as mock_time, patch.object(executor, "send_telegram") as mock_notify:
            result = executor.wait_for_order_fill(submitted_order, timeout_seconds=30, poll_interval_seconds=2)

    assert result is None
    mock_client.get_order_by_id.assert_called_once()
    mock_notify.assert_called_once()


def test_wait_for_order_fill_returns_none_when_order_canceled():
    submitted_order = _fake_order()
    canceled_order = _fake_order(status=OrderStatus.CANCELED)

    with patch.object(executor, "_client") as mock_client:
        mock_client.get_order_by_id.return_value = canceled_order
        with patch.object(executor, "time") as mock_time, patch.object(executor, "send_telegram") as mock_notify:
            result = executor.wait_for_order_fill(submitted_order, timeout_seconds=30, poll_interval_seconds=2)

    assert result is None
    mock_notify.assert_called_once()


def test_wait_for_order_fill_times_out_but_returns_partial_fill_when_partially_filled():
    """ZOZ-35: Erreicht das Timeout, waehrend die Order PARTIALLY_FILLED ist, wurde am Broker
    bereits real Kapital bewegt. In diesem Fall muss die letzte bekannte Order (mit ihrer
    tatsaechlichen filled_qty/filled_avg_price) zurueckgegeben werden, statt sie zu verwerfen -
    sonst weichen trades_today/daily_pnl im RiskManager vom echten Broker-Kontostand ab."""
    submitted_order = _fake_order()
    partially_filled_order = _fake_order(status=OrderStatus.PARTIALLY_FILLED)
    partially_filled_order.filled_qty = "3"
    partially_filled_order.filled_avg_price = "123.45"

    with patch.object(executor, "_client") as mock_client:
        mock_client.get_order_by_id.return_value = partially_filled_order
        with patch.object(executor, "time") as mock_time, patch.object(executor, "send_telegram") as mock_notify:
            result = executor.wait_for_order_fill(submitted_order, timeout_seconds=0.05, poll_interval_seconds=0.02)

    assert result is partially_filled_order
    assert result.filled_qty == "3"
    assert result.filled_avg_price == "123.45"
    mock_notify.assert_called_once()


def test_wait_for_order_fill_cancels_rest_order_when_partially_filled_timeout():
    """ZOZ-38: Bei PARTIALLY_FILLED-Timeout muss die Restmenge aktiv storniert werden,
    BEVOR der Teil-Fill an den Aufrufer zurueckgegeben wird - sonst bleibt die Rest-Order
    unbeobachtet offen am Broker liegen (Race-Bedingung/Genauigkeitsluecke)."""
    submitted_order = _fake_order()
    partially_filled_order = _fake_order(status=OrderStatus.PARTIALLY_FILLED)
    partially_filled_order.filled_qty = "3"
    partially_filled_order.filled_avg_price = "123.45"

    with patch.object(executor, "_client") as mock_client:
        mock_client.get_order_by_id.return_value = partially_filled_order
        with patch.object(executor, "time") as mock_time, patch.object(executor, "send_telegram") as mock_notify:
            result = executor.wait_for_order_fill(submitted_order, timeout_seconds=0.05, poll_interval_seconds=0.02)

    assert result is partially_filled_order
    mock_client.cancel_order_by_id.assert_called_once_with(submitted_order.id)
    # Kein zusaetzlicher Telegram-Alarm, wenn die Stornierung erfolgreich war.
    mock_notify.assert_called_once()


def test_wait_for_order_fill_logs_and_notifies_when_cancel_of_rest_order_fails():
    """Stornierung der Rest-Order kann fehlschlagen (z.B. weil sie zwischenzeitlich
    doch noch vollstaendig gefuellt hat) - das muss sauber geloggt/benachrichtigt
    werden, ohne den Teil-Fill-Rueckgabewert zu veraendern."""
    submitted_order = _fake_order()
    partially_filled_order = _fake_order(status=OrderStatus.PARTIALLY_FILLED)
    partially_filled_order.filled_qty = "3"
    partially_filled_order.filled_avg_price = "123.45"

    with patch.object(executor, "_client") as mock_client:
        mock_client.get_order_by_id.return_value = partially_filled_order
        mock_client.cancel_order_by_id.side_effect = Exception("order already filled")
        with patch.object(executor, "time") as mock_time, patch.object(executor, "send_telegram") as mock_notify:
            result = executor.wait_for_order_fill(submitted_order, timeout_seconds=0.05, poll_interval_seconds=0.02)

    assert result is partially_filled_order
    mock_client.cancel_order_by_id.assert_called_once_with(submitted_order.id)
    # Ein Alarm fuer den Teil-Fill selbst, plus ein zweiter fuer den fehlgeschlagenen Storno-Versuch.
    assert mock_notify.call_count == 2
    assert "Stornieren" in mock_notify.call_args[0][0]


def test_wait_for_order_fill_times_out_without_any_fill_returns_none():
    """Timeout mit PARTIALLY_FILLED aber filled_qty=0 (z.B. Order gerade erst akzeptiert,
    Feld noch nicht gesetzt) darf keinen Trade vortaeuschen -> weiterhin None."""
    submitted_order = _fake_order()
    partially_filled_order = _fake_order(status=OrderStatus.PARTIALLY_FILLED)
    partially_filled_order.filled_qty = "0"
    partially_filled_order.filled_avg_price = "0"

    with patch.object(executor, "_client") as mock_client:
        mock_client.get_order_by_id.return_value = partially_filled_order
        with patch.object(executor, "time") as mock_time, patch.object(executor, "send_telegram") as mock_notify:
            result = executor.wait_for_order_fill(submitted_order, timeout_seconds=0.05, poll_interval_seconds=0.02)

    assert result is None
    mock_notify.assert_called_once()


def test_wait_for_order_fill_returns_none_when_order_is_none():
    with patch.object(executor, "_client") as mock_client:
        result = executor.wait_for_order_fill(None)

    assert result is None
    mock_client.get_order_by_id.assert_not_called()


def test_wait_for_order_fill_recovers_from_transient_api_errors():
    """Ein voruebergehender Fehler beim Status-Abruf darf nicht sofort abbrechen,
    solange noch Versuche/Zeit uebrig sind."""
    submitted_order = _fake_order()
    filled_order = _fake_filled_order()

    with patch.object(executor, "_client") as mock_client:
        mock_client.get_order_by_id.side_effect = [Exception("network hiccup"), filled_order]
        with patch.object(executor, "time") as mock_time, patch.object(executor, "send_telegram"):
            result = executor.wait_for_order_fill(submitted_order, timeout_seconds=30, poll_interval_seconds=2)

    assert result is filled_order
    assert mock_client.get_order_by_id.call_count == 2


def test_close_position_returns_order_on_success():
    order = MagicMock()
    with patch.object(executor, "_client") as mock_client:
        mock_client.close_position.return_value = order
        with patch.object(executor, "send_telegram"):
            result = executor.close_position("NVDA")

    assert result is order
