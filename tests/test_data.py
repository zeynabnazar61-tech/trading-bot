import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from unittest.mock import MagicMock, patch

import pandas as pd

import data


def _bars_response(df: pd.DataFrame):
    bars = MagicMock()
    bars.df = df
    return bars


def test_get_recent_bars_returns_dataframe_on_normal_response():
    expected_df = pd.DataFrame({
        "open": [100.0, 101.0],
        "high": [101.0, 102.0],
        "low": [99.0, 100.0],
        "close": [100.5, 101.5],
        "volume": [1000, 1100],
    })

    with patch.object(data, "_client") as mock_client:
        mock_client.get_stock_bars.return_value = _bars_response(expected_df)
        result = data.get_recent_bars("NVDA")

    assert not result.empty
    assert list(result["close"]) == [100.5, 101.5]


def test_get_recent_bars_returns_empty_dataframe_on_empty_response():
    empty_df = pd.DataFrame()

    with patch.object(data, "_client") as mock_client:
        mock_client.get_stock_bars.return_value = _bars_response(empty_df)
        result = data.get_recent_bars("NVDA")

    assert result.empty


def test_get_recent_bars_returns_empty_dataframe_on_api_exception():
    with patch.object(data, "_client") as mock_client:
        mock_client.get_stock_bars.side_effect = Exception("API error")
        result = data.get_recent_bars("NVDA")

    assert isinstance(result, pd.DataFrame)
    assert result.empty


def test_get_recent_bars_unwraps_multiindex_for_symbol():
    symbol = "NVDA"
    index = pd.MultiIndex.from_tuples(
        [(symbol, pd.Timestamp("2024-01-01")), (symbol, pd.Timestamp("2024-01-02"))],
        names=["symbol", "timestamp"],
    )
    multi_df = pd.DataFrame({
        "open": [100.0, 101.0],
        "high": [101.0, 102.0],
        "low": [99.0, 100.0],
        "close": [100.5, 101.5],
        "volume": [1000, 1100],
    }, index=index)

    with patch.object(data, "_client") as mock_client:
        mock_client.get_stock_bars.return_value = _bars_response(multi_df)
        result = data.get_recent_bars(symbol)

    assert not isinstance(result.index, pd.MultiIndex)
    assert list(result["close"]) == [100.5, 101.5]


def test_get_recent_bars_uses_default_symbol_from_config():
    import config
    expected_df = pd.DataFrame({"close": [100.0]})

    with patch.object(data, "_client") as mock_client:
        mock_client.get_stock_bars.return_value = _bars_response(expected_df)
        data.get_recent_bars()

    request = mock_client.get_stock_bars.call_args[0][0]
    assert request.symbol_or_symbols == config.SYMBOL
