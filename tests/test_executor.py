import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from unittest.mock import MagicMock, patch

from alpaca.trading.enums import OrderSide

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
