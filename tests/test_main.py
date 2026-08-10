import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from unittest.mock import MagicMock, patch

import pandas as pd

import main


def _fake_df(price: float) -> pd.DataFrame:
    return pd.DataFrame({"close": [price]})


def _fake_position(qty: float, avg_entry_price: float):
    position = MagicMock()
    position.qty = qty
    position.avg_entry_price = avg_entry_price
    return position


def test_record_trade_pnl_multiplied_by_qty_on_stop_loss_exit():
    """Regression fuer ZOZ-14: PnL beim Stop-Loss-Exit muss (price - entry) * qty sein, nicht nur price - entry."""
    entry_price = 100.0
    qty = 10
    current_price = 90.0  # unter Stop-Loss (2%) -> loest Exit aus

    position = _fake_position(qty=qty, avg_entry_price=entry_price)

    with patch.object(main.data, "get_recent_bars", return_value=_fake_df(current_price)), \
         patch.object(main.strategy, "generate_signal", return_value="HOLD"), \
         patch.object(main.executor, "get_open_position", return_value=position), \
         patch.object(main.executor, "close_position"), \
         patch.object(main.risk_manager, "can_trade", return_value=True), \
         patch.object(main.risk_manager, "record_trade") as mock_record_trade:
        main.trading_cycle()

    expected_pnl = (current_price - entry_price) * qty
    mock_record_trade.assert_called_once_with(pnl=expected_pnl)
    # Regressions-Check: der urspruengliche Bug uebergab nur die Preisdifferenz ohne qty.
    assert mock_record_trade.call_args.kwargs["pnl"] != current_price - entry_price


def test_record_trade_pnl_multiplied_by_qty_on_take_profit_exit():
    entry_price = 100.0
    qty = 4
    current_price = 105.0  # ueber Take-Profit (4%) -> loest Exit aus

    position = _fake_position(qty=qty, avg_entry_price=entry_price)

    with patch.object(main.data, "get_recent_bars", return_value=_fake_df(current_price)), \
         patch.object(main.strategy, "generate_signal", return_value="HOLD"), \
         patch.object(main.executor, "get_open_position", return_value=position), \
         patch.object(main.executor, "close_position"), \
         patch.object(main.risk_manager, "can_trade", return_value=True), \
         patch.object(main.risk_manager, "record_trade") as mock_record_trade:
        main.trading_cycle()

    expected_pnl = (current_price - entry_price) * qty
    mock_record_trade.assert_called_once_with(pnl=expected_pnl)


def test_record_trade_pnl_multiplied_by_qty_on_sell_signal_exit():
    entry_price = 50.0
    qty = 7
    current_price = 51.0  # zwischen Stop-Loss (49.0) und Take-Profit (52.0) -> nur Signal-Exit greift

    position = _fake_position(qty=qty, avg_entry_price=entry_price)
    order = MagicMock()

    with patch.object(main.data, "get_recent_bars", return_value=_fake_df(current_price)), \
         patch.object(main.strategy, "generate_signal", return_value="SELL"), \
         patch.object(main.executor, "get_open_position", return_value=position), \
         patch.object(main.executor, "sell", return_value=order), \
         patch.object(main.risk_manager, "can_trade", return_value=True), \
         patch.object(main.risk_manager, "record_trade") as mock_record_trade:
        main.trading_cycle()

    expected_pnl = (current_price - entry_price) * qty
    mock_record_trade.assert_called_once_with(pnl=expected_pnl)
