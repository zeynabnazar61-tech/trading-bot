import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from risk_manager import RiskManager
import config


def test_position_size_respects_max_usd():
    rm = RiskManager()
    qty = rm.calculate_position_size(current_price=100.0)
    assert qty * 100.0 <= config.MAX_POSITION_SIZE_USD


def test_daily_loss_limit_halts_trading():
    rm = RiskManager()
    rm.record_trade(pnl=-config.MAX_DAILY_LOSS_USD - 1)
    assert rm.can_trade() is False


def test_max_trades_per_day_limit():
    rm = RiskManager()
    for _ in range(config.MAX_TRADES_PER_DAY):
        rm.record_trade(pnl=0)
    assert rm.can_trade() is False


def test_stop_loss_and_take_profit_prices():
    rm = RiskManager()
    entry = 100.0
    assert rm.get_stop_loss_price(entry) < entry
    assert rm.get_take_profit_price(entry) > entry
