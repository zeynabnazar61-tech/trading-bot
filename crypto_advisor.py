"""
Krypto-Entscheidungshilfe (Fear & Greed Index).

Beobachtet BTC, ETH, SOL und gibt eine Empfehlung (BUY/SELL/HOLD) aus,
basierend auf dem Crypto Fear & Greed Index (alternative.me):
- Extreme Angst / Angst  -> BUY  (Markt uebertrieben aengstlich)
- Neutral                -> HOLD
- Gier / Extreme Gier    -> SELL (Markt uebertrieben euphorisch)

WICHTIG: Handelt NICHT automatisch. Zeigt nur eine Empfehlung an und
schickt per Telegram Bescheid, wenn sich die Empfehlung aendert.
Die eigentliche Kauf-/Verkaufsentscheidung triffst du selbst.
"""
import json
import os
import signal
import sys
import time

import pandas as pd
import requests

from logger_setup import get_logger
from notifier import send_telegram

logger = get_logger("crypto_advisor")

COINS = {"bitcoin": "BTC", "ethereum": "ETH", "solana": "SOL"}
CHECK_INTERVAL_SECONDS = 60 * 60  # Fear & Greed Index aktualisiert sich nur 1x/Tag
STATE_FILE = "logs/crypto_advisor_state.json"

# --- Pro-Coin-Signal (SMA-Crossover + Trendfilter, taegliche Kurse) ---
# Eigene, kleinere Fenster als beim Aktien-Bot (strategy.py), weil hier mit
# TAEGLICHEN statt 15-Minuten-Kerzen gerechnet wird.
COIN_SHORT_WINDOW = 10
COIN_LONG_WINDOW = 30
COIN_TREND_WINDOW = 50
COIN_MIN_CROSSOVER_MARGIN_PCT = 0.005  # 0.5%, groesser als bei Aktien (Krypto ist volatiler)
COIN_HISTORY_DAYS = 90  # taeglich, genug fuer TREND_WINDOW=50 + Puffer

_running = True


def _handle_shutdown(signum, frame):
    global _running
    logger.info("Beende Krypto-Advisor sauber... (Strg+C erkannt)")
    _running = False


signal.signal(signal.SIGINT, _handle_shutdown)
signal.signal(signal.SIGTERM, _handle_shutdown)


def get_fear_greed():
    """Holt den aktuellen Fear & Greed Index (0-100) + Klassifikation."""
    response = requests.get("https://api.alternative.me/fng/?limit=1", timeout=10)
    response.raise_for_status()
    data = response.json()["data"][0]
    return int(data["value"]), data["value_classification"]


def get_prices():
    """Holt aktuelle Preise + 24h-Aenderung fuer die beobachteten Coins."""
    ids = ",".join(COINS.keys())
    url = (
        f"https://api.coingecko.com/api/v3/simple/price"
        f"?ids={ids}&vs_currencies=usd&include_24hr_change=true"
    )
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    return response.json()


def get_recommendation(value: int) -> str:
    """Leitet aus dem Fear & Greed Wert eine einfache, marktweite Empfehlung ab."""
    if value <= 25:
        return "BUY"
    if value >= 75:
        return "SELL"
    return "HOLD"


def get_coin_history(coin_id: str) -> pd.DataFrame:
    """Holt taegliche Schlusskurse eines Coins (fuer SMA-Berechnung)."""
    url = (
        f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
        f"?vs_currency=usd&days={COIN_HISTORY_DAYS}&interval=daily"
    )
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    prices = response.json()["prices"]  # [[timestamp_ms, price], ...]
    return pd.DataFrame({"close": [p[1] for p in prices]})


def get_coin_signal(coin_id: str) -> str:
    """SMA-Crossover mit Trendfilter pro Coin - eigenstaendige, einfachere
    Variante von strategy.py, aber auf taegliche Krypto-Kurse zugeschnitten."""
    df = get_coin_history(coin_id)
    min_len = COIN_TREND_WINDOW + 1
    if len(df) < min_len:
        return "HOLD"

    df["sma_short"] = df["close"].rolling(window=COIN_SHORT_WINDOW).mean()
    df["sma_long"] = df["close"].rolling(window=COIN_LONG_WINDOW).mean()
    df["sma_trend"] = df["close"].rolling(window=COIN_TREND_WINDOW).mean()

    prev_short, prev_long = df["sma_short"].iloc[-2], df["sma_long"].iloc[-2]
    curr_short, curr_long = df["sma_short"].iloc[-1], df["sma_long"].iloc[-1]
    curr_price = df["close"].iloc[-1]
    curr_trend = df["sma_trend"].iloc[-1]

    if pd.isna(prev_short) or pd.isna(prev_long) or pd.isna(curr_trend):
        return "HOLD"

    crossed_up = prev_short <= prev_long and curr_short > curr_long
    crossed_down = prev_short >= prev_long and curr_short < curr_long

    gap_pct = abs(curr_short - curr_long) / curr_long if curr_long else 0
    if gap_pct < COIN_MIN_CROSSOVER_MARGIN_PCT:
        return "HOLD"

    uptrend = curr_price > curr_trend
    downtrend = curr_price < curr_trend

    if crossed_up and uptrend:
        return "BUY"
    if crossed_down and downtrend:
        return "SELL"
    return "HOLD"


def get_coin_signals() -> dict:
    """Pro-Coin-Signale, Fehler bei einem Coin duerfen die anderen nicht stoppen."""
    signals = {}
    for coin_id in COINS:
        try:
            signals[coin_id] = get_coin_signal(coin_id)
        except Exception as e:
            logger.warning(f"Konnte Signal fuer {coin_id} nicht berechnen: {e}")
            signals[coin_id] = "HOLD"
    return signals


def load_last_state():
    if not os.path.exists(STATE_FILE):
        return None, {}
    try:
        with open(STATE_FILE, "r") as f:
            data = json.load(f)
            return data.get("last_recommendation"), data.get("last_coin_signals", {})
    except (json.JSONDecodeError, OSError):
        return None, {}


def save_last_state(recommendation: str, coin_signals: dict) -> None:
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump({"last_recommendation": recommendation, "last_coin_signals": coin_signals}, f)


def format_message(value, classification, recommendation, prices, coin_signals) -> str:
    lines = [
        f"Markt-Stimmung: {recommendation}",
        f"Fear & Greed Index: {value} ({classification})",
        "",
    ]
    changes = {}
    for coin_id, symbol in COINS.items():
        info = prices.get(coin_id)
        if info:
            price = info["usd"]
            change = info.get("usd_24h_change", 0)
            changes[symbol] = change
            signal = coin_signals.get(coin_id, "HOLD")
            lines.append(f"{symbol}: ${price:,.2f} ({change:+.2f}% 24h) | Trend-Signal: {signal}")

    if changes:
        biggest_drop = min(changes, key=changes.get)
        biggest_rise = max(changes, key=changes.get)
        lines.append("")
        lines.append(f"Groesster 24h-Ruecksetzer: {biggest_drop} ({changes[biggest_drop]:+.2f}%)")
        lines.append(f"Groesster 24h-Anstieg: {biggest_rise} ({changes[biggest_rise]:+.2f}%)")

    return "\n".join(lines)


def run_once(force_notify: bool = False):
    """force_notify=True schickt immer eine Telegram-Nachricht, auch wenn sich
    nichts geaendert hat (z.B. bei manuell ausgeloesten Laeufen)."""
    value, classification = get_fear_greed()
    recommendation = get_recommendation(value)
    prices = get_prices()
    coin_signals = get_coin_signals()

    message = format_message(value, classification, recommendation, prices, coin_signals)
    logger.info(message.replace("\n", " | "))

    last_recommendation, last_coin_signals = load_last_state()
    changed = recommendation != last_recommendation or coin_signals != last_coin_signals

    if changed:
        send_telegram(f"Krypto-Update:\n{message}")
        save_last_state(recommendation, coin_signals)
    elif force_notify:
        send_telegram(f"Krypto-Update (manuell abgerufen):\n{message}")
    else:
        logger.info(f"Keine Aenderung ({recommendation}, {coin_signals}) -> keine Telegram-Nachricht.")


def main():
    logger.info(f"Krypto-Advisor gestartet. Beobachtet: {', '.join(COINS.values())}")
    while _running:
        try:
            run_once()
        except Exception as e:
            logger.error(f"Fehler im Krypto-Advisor-Zyklus: {e}", exc_info=True)

        for _ in range(CHECK_INTERVAL_SECONDS):
            if not _running:
                break
            time.sleep(1)

    logger.info("Krypto-Advisor beendet.")


if __name__ == "__main__":
    if "--once" in sys.argv:
        # Einmaliger Durchlauf statt Endlos-Schleife, z.B. fuer GitHub Actions
        # Cron-Jobs: dort startet jeder Lauf einen frischen, kurzlebigen Container.
        # GITHUB_EVENT_NAME wird von GitHub Actions automatisch gesetzt:
        # "workflow_dispatch" = manuell per "Run workflow" Button ausgeloest.
        manually_triggered = os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch"
        run_once(force_notify=manually_triggered)
    else:
        main()
