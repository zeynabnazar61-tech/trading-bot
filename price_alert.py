"""
Sofort-Preisalarm fuer ploetzliche Kursbewegungen.

Getrennt vom stuendlichen crypto_advisor.py (der Fear&Greed-Index, Trend-Signale
und Trending-Coins berechnet), damit dieser haeufige (alle 15 Min), absichtlich
leichtgewichtige Check nicht jedes Mal die schwere Analyse mit ausfuehren muss.

Meldet sich per Telegram, sobald ein Coin seit dem letzten Alarm-Basiswert um
mehr als ALERT_THRESHOLD_PCT gestiegen/gefallen ist.
"""
import json
import os

import requests

from logger_setup import get_logger
from notifier import send_telegram

logger = get_logger("price_alert")

COINS = {
    "bitcoin": "BTC",
    "ethereum": "ETH",
    "solana": "SOL",
    "binancecoin": "BNB",
    "ripple": "XRP",
    "dogecoin": "DOGE",
    "cardano": "ADA",
}
ALERT_THRESHOLD_PCT = 5.0
STATE_FILE = "logs/price_alert_state.json"


def get_prices() -> dict:
    """Holt aktuelle USD-Preise fuer die beobachteten Coins."""
    ids = ",".join(COINS.keys())
    url = f"https://api.coingecko.com/api/v3/simple/price?ids={ids}&vs_currencies=usd"
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    return {coin_id: data["usd"] for coin_id, data in response.json().items()}


def load_last_prices() -> dict:
    if not os.path.exists(STATE_FILE):
        return {}
    try:
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def save_last_prices(prices: dict) -> None:
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(prices, f)


def run_once():
    current_prices = get_prices()
    last_prices = load_last_prices()
    updated_baseline = dict(last_prices)

    for coin_id, symbol in COINS.items():
        current = current_prices.get(coin_id)
        previous = last_prices.get(coin_id)
        if current is None:
            continue

        if previous is None:
            # Erster Lauf fuer diesen Coin -> nur Basiswert speichern, kein Alarm.
            updated_baseline[coin_id] = current
            continue

        change_pct = (current - previous) / previous * 100
        if abs(change_pct) >= ALERT_THRESHOLD_PCT:
            direction = "gestiegen" if change_pct > 0 else "gefallen"
            message = (
                f"Preisalarm: {symbol} ist seit dem letzten Basiswert um "
                f"{change_pct:+.2f}% {direction} (${previous:,.2f} -> ${current:,.2f})"
            )
            logger.info(message)
            send_telegram(message)
            updated_baseline[coin_id] = current  # neuer Basiswert nach Alarm
        else:
            logger.info(f"{symbol}: {change_pct:+.2f}% seit letztem Basiswert -> kein Alarm.")

    save_last_prices(updated_baseline)


if __name__ == "__main__":
    run_once()
