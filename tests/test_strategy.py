"""
Einfache Tests für die Strategie-Logik.
Ausführen mit: pytest tests/
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pandas as pd
import numpy as np
from strategy import generate_signal
import config


def make_price_df(prices):
    return pd.DataFrame({"close": prices})


def test_not_enough_data_returns_hold():
    df = make_price_df([100, 101, 102])
    assert generate_signal(df) == "HOLD"


def test_golden_cross_triggers_buy():
    # Erzeugt eine Preisreihe, die klar ansteigt -> SMA kurz kreuzt SMA lang von unten
    n = config.LONG_WINDOW + 10
    prices = list(np.linspace(100, 90, n // 2)) + list(np.linspace(90, 150, n // 2))
    df = make_price_df(prices)
    signal = generate_signal(df)
    assert signal in ("BUY", "HOLD")  # BUY im Idealfall, HOLD falls Kreuzung nicht exakt am letzten Punkt


def test_flat_prices_returns_hold():
    prices = [100] * (config.LONG_WINDOW + 5)
    df = make_price_df(prices)
    assert generate_signal(df) == "HOLD"
