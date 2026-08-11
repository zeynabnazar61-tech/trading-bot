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


def _fake_filled_order(filled_qty: float, filled_avg_price: float):
    """Simuliert eine von executor.wait_for_order_fill() bestaetigte, gefuellte Order."""
    order = MagicMock()
    order.filled_qty = filled_qty
    order.filled_avg_price = filled_avg_price
    return order


def test_record_trade_pnl_multiplied_by_qty_on_stop_loss_exit():
    """Regression fuer ZOZ-14: PnL beim Stop-Loss-Exit muss (price - entry) * qty sein, nicht nur price - entry.
    ZOZ-33: PnL basiert jetzt auf der bestaetigten Fill-Qty/Preis, nicht mehr auf current_price/position_qty."""
    entry_price = 100.0
    qty = 10
    current_price = 90.0  # unter Stop-Loss (2%) -> loest Exit aus
    filled_order = _fake_filled_order(filled_qty=qty, filled_avg_price=current_price)

    position = _fake_position(qty=qty, avg_entry_price=entry_price)

    with patch.object(main.data, "get_recent_bars", return_value=_fake_df(current_price)), \
         patch.object(main.strategy, "generate_signal", return_value="HOLD"), \
         patch.object(main.executor, "get_open_position", return_value=position), \
         patch.object(main.executor, "close_position", return_value=MagicMock()), \
         patch.object(main.executor, "wait_for_order_fill", return_value=filled_order), \
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
    filled_order = _fake_filled_order(filled_qty=qty, filled_avg_price=current_price)

    position = _fake_position(qty=qty, avg_entry_price=entry_price)

    with patch.object(main.data, "get_recent_bars", return_value=_fake_df(current_price)), \
         patch.object(main.strategy, "generate_signal", return_value="HOLD"), \
         patch.object(main.executor, "get_open_position", return_value=position), \
         patch.object(main.executor, "close_position", return_value=MagicMock()), \
         patch.object(main.executor, "wait_for_order_fill", return_value=filled_order), \
         patch.object(main.risk_manager, "can_trade", return_value=True), \
         patch.object(main.risk_manager, "record_trade") as mock_record_trade:
        main.trading_cycle()

    expected_pnl = (current_price - entry_price) * qty
    mock_record_trade.assert_called_once_with(pnl=expected_pnl)


def test_stop_loss_exit_unfilled_order_does_not_record_trade():
    """ZOZ-33: Wenn die Stop-Loss-Close-Order nicht bestaetigt wird (Timeout/Ablehnung),
    darf KEIN record_trade erfolgen - der interne Zustand darf nicht vom Konto abweichen."""
    entry_price = 100.0
    qty = 10
    current_price = 90.0

    position = _fake_position(qty=qty, avg_entry_price=entry_price)

    with patch.object(main.data, "get_recent_bars", return_value=_fake_df(current_price)), \
         patch.object(main.strategy, "generate_signal", return_value="HOLD"), \
         patch.object(main.executor, "get_open_position", return_value=position), \
         patch.object(main.executor, "close_position", return_value=MagicMock()), \
         patch.object(main.executor, "wait_for_order_fill", return_value=None), \
         patch.object(main.risk_manager, "can_trade", return_value=True), \
         patch.object(main.risk_manager, "record_trade") as mock_record_trade:
        main.trading_cycle()

    mock_record_trade.assert_not_called()


def test_buy_signal_without_open_position_places_buy_order():
    current_price = 100.0
    filled_order = _fake_filled_order(filled_qty=3, filled_avg_price=current_price)

    with patch.object(main.data, "get_recent_bars", return_value=_fake_df(current_price)), \
         patch.object(main.strategy, "generate_signal", return_value="BUY"), \
         patch.object(main.executor, "get_open_position", return_value=None), \
         patch.object(main.executor, "get_account_info", return_value={"cash": 100000.0, "portfolio_value": 100000.0, "buying_power": 100000.0}), \
         patch.object(main.executor, "buy", return_value=MagicMock()) as mock_buy, \
         patch.object(main.executor, "wait_for_order_fill", return_value=filled_order), \
         patch.object(main.risk_manager, "can_trade", return_value=True), \
         patch.object(main.risk_manager, "calculate_position_size", return_value=3), \
         patch.object(main.risk_manager, "record_trade") as mock_record_trade:
        main.trading_cycle()

    mock_buy.assert_called_once_with(main.config.SYMBOL, 3)
    mock_record_trade.assert_called_once_with()


def test_buy_signal_with_zero_qty_skips_order():
    """calculate_position_size liefert 0 (z.B. Risiko-Cap) -> keine Order platzieren."""
    current_price = 100.0

    with patch.object(main.data, "get_recent_bars", return_value=_fake_df(current_price)), \
         patch.object(main.strategy, "generate_signal", return_value="BUY"), \
         patch.object(main.executor, "get_open_position", return_value=None), \
         patch.object(main.executor, "get_account_info", return_value={"cash": 100000.0, "portfolio_value": 100000.0, "buying_power": 100000.0}), \
         patch.object(main.executor, "buy") as mock_buy, \
         patch.object(main.risk_manager, "can_trade", return_value=True), \
         patch.object(main.risk_manager, "calculate_position_size", return_value=0), \
         patch.object(main.risk_manager, "record_trade") as mock_record_trade:
        main.trading_cycle()

    mock_buy.assert_not_called()
    mock_record_trade.assert_not_called()


def test_buy_signal_when_order_fails_does_not_record_trade():
    current_price = 100.0

    with patch.object(main.data, "get_recent_bars", return_value=_fake_df(current_price)), \
         patch.object(main.strategy, "generate_signal", return_value="BUY"), \
         patch.object(main.executor, "get_open_position", return_value=None), \
         patch.object(main.executor, "get_account_info", return_value={"cash": 100000.0, "portfolio_value": 100000.0, "buying_power": 100000.0}), \
         patch.object(main.executor, "buy", return_value=None), \
         patch.object(main.executor, "wait_for_order_fill") as mock_wait_for_fill, \
         patch.object(main.risk_manager, "can_trade", return_value=True), \
         patch.object(main.risk_manager, "calculate_position_size", return_value=3), \
         patch.object(main.risk_manager, "record_trade") as mock_record_trade:
        main.trading_cycle()

    mock_wait_for_fill.assert_not_called()  # order ist None -> kein Sinn zu pollen
    mock_record_trade.assert_not_called()


def test_buy_signal_when_order_not_confirmed_does_not_record_trade():
    """ZOZ-33: Order wurde angenommen, aber nicht (rechtzeitig) gefuellt -> kein record_trade."""
    current_price = 100.0

    with patch.object(main.data, "get_recent_bars", return_value=_fake_df(current_price)), \
         patch.object(main.strategy, "generate_signal", return_value="BUY"), \
         patch.object(main.executor, "get_open_position", return_value=None), \
         patch.object(main.executor, "get_account_info", return_value={"cash": 100000.0, "portfolio_value": 100000.0, "buying_power": 100000.0}), \
         patch.object(main.executor, "buy", return_value=MagicMock()), \
         patch.object(main.executor, "wait_for_order_fill", return_value=None), \
         patch.object(main.risk_manager, "can_trade", return_value=True), \
         patch.object(main.risk_manager, "calculate_position_size", return_value=3), \
         patch.object(main.risk_manager, "record_trade") as mock_record_trade:
        main.trading_cycle()

    mock_record_trade.assert_not_called()


def test_buy_signal_when_account_info_unavailable_skips_buy_fail_safe():
    """Fail-Safe: get_account_info() liefert None (z.B. API-Fehler) -> Kauf wird sicherheitshalber uebersprungen."""
    current_price = 100.0

    with patch.object(main.data, "get_recent_bars", return_value=_fake_df(current_price)), \
         patch.object(main.strategy, "generate_signal", return_value="BUY"), \
         patch.object(main.executor, "get_open_position", return_value=None), \
         patch.object(main.executor, "get_account_info", return_value=None), \
         patch.object(main.executor, "buy") as mock_buy, \
         patch.object(main.risk_manager, "can_trade", return_value=True), \
         patch.object(main.risk_manager, "calculate_position_size") as mock_calculate_position_size, \
         patch.object(main.risk_manager, "record_trade") as mock_record_trade:
        main.trading_cycle()

    mock_buy.assert_not_called()
    mock_calculate_position_size.assert_not_called()
    mock_record_trade.assert_not_called()


def test_buy_signal_with_existing_position_does_not_buy_again():
    current_price = 91.0  # zwischen Stop-Loss (88.2) und Take-Profit (93.6) bei Einstieg 90 -> kein Exit ausgeloest
    position = _fake_position(qty=5, avg_entry_price=90.0)

    with patch.object(main.data, "get_recent_bars", return_value=_fake_df(current_price)), \
         patch.object(main.strategy, "generate_signal", return_value="BUY"), \
         patch.object(main.executor, "get_open_position", return_value=position), \
         patch.object(main.executor, "buy") as mock_buy, \
         patch.object(main.executor, "close_position") as mock_close, \
         patch.object(main.risk_manager, "can_trade", return_value=True):
        main.trading_cycle()

    mock_buy.assert_not_called()
    mock_close.assert_not_called()


def test_hold_signal_without_position_takes_no_action():
    """'Kein Handlungsbedarf'-Pfad: HOLD-Signal und keine offene Position."""
    current_price = 100.0

    with patch.object(main.data, "get_recent_bars", return_value=_fake_df(current_price)), \
         patch.object(main.strategy, "generate_signal", return_value="HOLD"), \
         patch.object(main.executor, "get_open_position", return_value=None), \
         patch.object(main.executor, "buy") as mock_buy, \
         patch.object(main.executor, "sell") as mock_sell, \
         patch.object(main.executor, "close_position") as mock_close, \
         patch.object(main.risk_manager, "can_trade", return_value=True), \
         patch.object(main.risk_manager, "record_trade") as mock_record_trade:
        main.trading_cycle()

    mock_buy.assert_not_called()
    mock_sell.assert_not_called()
    mock_close.assert_not_called()
    mock_record_trade.assert_not_called()


def test_sell_signal_without_open_position_takes_no_action():
    """SELL-Signal aber keine offene Position -> nichts zu tun."""
    current_price = 100.0

    with patch.object(main.data, "get_recent_bars", return_value=_fake_df(current_price)), \
         patch.object(main.strategy, "generate_signal", return_value="SELL"), \
         patch.object(main.executor, "get_open_position", return_value=None), \
         patch.object(main.executor, "sell") as mock_sell, \
         patch.object(main.risk_manager, "can_trade", return_value=True), \
         patch.object(main.risk_manager, "record_trade") as mock_record_trade:
        main.trading_cycle()

    mock_sell.assert_not_called()
    mock_record_trade.assert_not_called()


def test_can_trade_false_skips_cycle_entirely():
    """Wenn risk_manager.can_trade() False liefert, darf kein Marktdaten-Abruf erfolgen."""
    with patch.object(main.risk_manager, "can_trade", return_value=False), \
         patch.object(main.data, "get_recent_bars") as mock_get_bars:
        main.trading_cycle()

    mock_get_bars.assert_not_called()


def test_empty_dataframe_skips_cycle():
    """Leeres DataFrame (keine Marktdaten) -> Zyklus wird sauber uebersprungen."""
    with patch.object(main.data, "get_recent_bars", return_value=pd.DataFrame()), \
         patch.object(main.strategy, "generate_signal") as mock_signal, \
         patch.object(main.risk_manager, "can_trade", return_value=True):
        main.trading_cycle()

    mock_signal.assert_not_called()


def test_record_trade_pnl_multiplied_by_qty_on_sell_signal_exit():
    entry_price = 50.0
    qty = 7
    current_price = 51.0  # zwischen Stop-Loss (49.0) und Take-Profit (52.0) -> nur Signal-Exit greift

    position = _fake_position(qty=qty, avg_entry_price=entry_price)
    order = MagicMock()
    filled_order = _fake_filled_order(filled_qty=qty, filled_avg_price=current_price)

    with patch.object(main.data, "get_recent_bars", return_value=_fake_df(current_price)), \
         patch.object(main.strategy, "generate_signal", return_value="SELL"), \
         patch.object(main.executor, "get_open_position", return_value=position), \
         patch.object(main.executor, "sell", return_value=order), \
         patch.object(main.executor, "wait_for_order_fill", return_value=filled_order) as mock_wait_for_fill, \
         patch.object(main.risk_manager, "can_trade", return_value=True), \
         patch.object(main.risk_manager, "record_trade") as mock_record_trade:
        main.trading_cycle()

    mock_wait_for_fill.assert_called_once_with(order)
    expected_pnl = (current_price - entry_price) * qty
    mock_record_trade.assert_called_once_with(pnl=expected_pnl)


def test_sell_signal_exit_unfilled_order_does_not_record_trade():
    """ZOZ-33: Sell-Order angenommen, aber nicht bestaetigt gefuellt -> kein record_trade,
    interner Zustand darf nicht vom tatsaechlichen Konto abweichen."""
    entry_price = 50.0
    qty = 7
    current_price = 51.0

    position = _fake_position(qty=qty, avg_entry_price=entry_price)
    order = MagicMock()

    with patch.object(main.data, "get_recent_bars", return_value=_fake_df(current_price)), \
         patch.object(main.strategy, "generate_signal", return_value="SELL"), \
         patch.object(main.executor, "get_open_position", return_value=position), \
         patch.object(main.executor, "sell", return_value=order), \
         patch.object(main.executor, "wait_for_order_fill", return_value=None), \
         patch.object(main.risk_manager, "can_trade", return_value=True), \
         patch.object(main.risk_manager, "record_trade") as mock_record_trade:
        main.trading_cycle()

    mock_record_trade.assert_not_called()
