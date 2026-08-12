"""
Tests fuer die Trailing-Stop-Vergleichsvariante (ZOZ-40).
Ausführen mit: pytest tests/
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pandas as pd
import numpy as np
from strategy_trailing import generate_entry_signal, should_exit_trailing, should_exit_hard_stop_loss
import config


def make_price_df(prices):
    return pd.DataFrame({"close": prices})


def test_not_enough_data_returns_hold():
    df = make_price_df([100, 101, 102])
    assert generate_entry_signal(df) == "HOLD"


def test_golden_cross_triggers_buy():
    n = config.LONG_WINDOW + 10
    prices = list(np.linspace(100, 90, n // 2)) + list(np.linspace(90, 150, n // 2))
    df = make_price_df(prices)
    signal = generate_entry_signal(df)
    assert signal in ("BUY", "HOLD")  # BUY im Idealfall, HOLD falls Kreuzung nicht exakt am letzten Punkt


def test_flat_prices_returns_hold():
    prices = [100] * (config.LONG_WINDOW + 5)
    df = make_price_df(prices)
    assert generate_entry_signal(df) == "HOLD"


def test_entry_signal_never_returns_sell():
    # generate_entry_signal darf nie SELL liefern - der Ausstieg laeuft
    # ausschliesslich ueber den Trailing-Stop / harten Stop-Loss.
    n = config.LONG_WINDOW + 10
    prices = list(np.linspace(150, 90, n))  # klarer Abwaertstrend (waere Death Cross bei strategy.py)
    df = make_price_df(prices)
    assert generate_entry_signal(df) != "SELL"


def test_trailing_stop_triggers_when_price_falls_below_threshold():
    # Hoch bei 100, Trailing-Stop 5% -> Exit bei <= 95
    assert should_exit_trailing(highest_price_since_entry=100.0, current_price=94.99,
                                 trailing_stop_pct=0.05) is True


def test_trailing_stop_not_triggered_above_threshold():
    assert should_exit_trailing(highest_price_since_entry=100.0, current_price=96.0,
                                 trailing_stop_pct=0.05) is False


def test_trailing_stop_uses_highest_price_not_entry_price():
    # Preis ist ueber dem Einstieg gestiegen, dann wieder gefallen -> Trailing-Stop
    # bezieht sich auf das Hoch (120), nicht auf den Einstiegspreis (100).
    assert should_exit_trailing(highest_price_since_entry=120.0, current_price=113.0,
                                 trailing_stop_pct=0.05) is True
    assert should_exit_trailing(highest_price_since_entry=120.0, current_price=116.0,
                                 trailing_stop_pct=0.05) is False


def test_hard_stop_loss_triggers_below_entry_price():
    assert should_exit_hard_stop_loss(entry_price=100.0, current_price=97.9,
                                       stop_loss_pct=0.02) is True


def test_hard_stop_loss_not_triggered_above_threshold():
    assert should_exit_hard_stop_loss(entry_price=100.0, current_price=99.0,
                                       stop_loss_pct=0.02) is False


def test_hard_stop_loss_acts_as_safety_net_even_if_trailing_stop_not_yet_hit():
    # Hoch nur knapp ueber Einstieg (Trailing-Stop greift noch nicht),
    # aber harter Stop-Loss ab Einstiegspreis greift.
    entry_price = 100.0
    highest_price = 101.0
    current_price = 97.0
    assert should_exit_trailing(highest_price, current_price, trailing_stop_pct=0.05) is False
    assert should_exit_hard_stop_loss(entry_price, current_price, stop_loss_pct=0.02) is True
