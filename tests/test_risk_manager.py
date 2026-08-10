import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from datetime import date, datetime, timedelta

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


# --- Grenzwerte Tagesverlust-Limit ---

def test_daily_loss_exactly_at_limit_halts_trading():
    """daily_pnl == -MAX_DAILY_LOSS_USD ist bereits der Abbruch-Fall (<=)."""
    rm = RiskManager()
    rm.daily_pnl = -abs(config.MAX_DAILY_LOSS_USD)
    assert rm.can_trade() is False
    assert rm.trading_halted is True


def test_daily_loss_just_under_limit_does_not_halt():
    """Ein Cent unter dem Limit darf noch gehandelt werden."""
    rm = RiskManager()
    rm.daily_pnl = -abs(config.MAX_DAILY_LOSS_USD) + 0.01
    assert rm.can_trade() is True
    assert rm.trading_halted is False


def test_trading_halted_persists_even_if_pnl_recovers():
    """Einmal gestoppt bleibt gestoppt, auch wenn daily_pnl sich wieder erholt."""
    rm = RiskManager()
    rm.daily_pnl = -abs(config.MAX_DAILY_LOSS_USD)
    assert rm.can_trade() is False
    rm.daily_pnl = 50.0
    assert rm.can_trade() is False


def test_new_day_resets_counters_and_halt():
    rm = RiskManager()
    rm.daily_pnl = -abs(config.MAX_DAILY_LOSS_USD)
    rm.trades_today = config.MAX_TRADES_PER_DAY
    rm.trading_halted = True
    rm.current_day = date.today() - timedelta(days=1)

    assert rm.can_trade() is True
    assert rm.daily_pnl == 0.0
    assert rm.trades_today == 0
    assert rm.trading_halted is False


# --- Grenzwerte max. Trades pro Tag (isoliert vom Cooldown) ---

def test_max_trades_per_day_boundary_isolated_from_cooldown():
    rm = RiskManager()
    rm.trades_today = config.MAX_TRADES_PER_DAY - 1
    rm.last_trade_time = datetime.now() - timedelta(minutes=config.COOLDOWN_MINUTES + 1)
    assert rm.can_trade() is True

    rm.trades_today = config.MAX_TRADES_PER_DAY
    assert rm.can_trade() is False


# --- Cooldown ---

def test_cooldown_blocks_immediately_after_trade():
    rm = RiskManager()
    rm.record_trade(pnl=0)
    assert rm.can_trade() is False


def test_cooldown_expires_after_enough_time():
    rm = RiskManager()
    rm.record_trade(pnl=0)
    rm.last_trade_time = datetime.now() - timedelta(minutes=config.COOLDOWN_MINUTES + 1)
    assert rm.can_trade() is True


# --- Positionsgroessen-Berechnung bei ungewoehnlichen Preisen ---

def test_position_size_zero_for_zero_price():
    rm = RiskManager()
    assert rm.calculate_position_size(current_price=0.0) == 0


def test_position_size_zero_for_negative_price():
    rm = RiskManager()
    assert rm.calculate_position_size(current_price=-50.0) == 0


def test_position_size_zero_when_price_exceeds_position_cap():
    rm = RiskManager()
    qty = rm.calculate_position_size(current_price=config.MAX_POSITION_SIZE_USD * 10)
    assert qty == 0


def test_position_size_very_small_price():
    rm = RiskManager()
    qty = rm.calculate_position_size(current_price=0.01)
    assert qty >= 0
    assert qty * 0.01 <= config.MAX_POSITION_SIZE_USD


def test_position_size_risk_cap_binds_when_lower_than_position_cap(monkeypatch):
    """Wenn MAX_RISK_PER_TRADE_USD der engere Deckel ist, muss er greifen (nicht nur MAX_POSITION_SIZE_USD)."""
    monkeypatch.setattr(config, "MAX_RISK_PER_TRADE_USD", 4.0)
    rm = RiskManager()
    # price=100, STOP_LOSS_PCT=0.02 -> risk_per_share=2.0 -> qty_by_risk=2, qty_by_cap=5
    qty = rm.calculate_position_size(current_price=100.0)
    assert qty == 2


def test_position_size_never_negative():
    rm = RiskManager()
    qty = rm.calculate_position_size(current_price=1_000_000.0)
    assert qty >= 0


# --- Stop-Loss / Take-Profit Grenzwerte ---

def test_stop_loss_take_profit_zero_entry_price():
    rm = RiskManager()
    assert rm.get_stop_loss_price(0.0) == 0.0
    assert rm.get_take_profit_price(0.0) == 0.0


def test_stop_loss_take_profit_rounded_to_two_decimals():
    rm = RiskManager()
    sl = rm.get_stop_loss_price(33.333)
    tp = rm.get_take_profit_price(33.333)
    assert sl == round(sl, 2)
    assert tp == round(tp, 2)


# --- record_trade ---

def test_record_trade_accumulates_pnl_and_count():
    rm = RiskManager()
    rm.record_trade(pnl=10.0)
    rm.record_trade(pnl=-3.0)
    assert rm.trades_today == 2
    assert rm.daily_pnl == 7.0
    assert rm.last_trade_time is not None
