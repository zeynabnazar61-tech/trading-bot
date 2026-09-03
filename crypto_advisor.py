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

import requests

from logger_setup import get_logger
from notifier import send_telegram

logger = get_logger("crypto_advisor")

COINS = {"bitcoin": "BTC", "ethereum": "ETH", "solana": "SOL"}
CHECK_INTERVAL_SECONDS = 60 * 60  # Fear & Greed Index aktualisiert sich nur 1x/Tag
STATE_FILE = "logs/crypto_advisor_state.json"

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
    """Leitet aus dem Fear & Greed Wert eine einfache Empfehlung ab."""
    if value <= 25:
        return "BUY"
    if value >= 75:
        return "SELL"
    return "HOLD"


def load_last_recommendation():
    if not os.path.exists(STATE_FILE):
        return None
    try:
        with open(STATE_FILE, "r") as f:
            return json.load(f).get("last_recommendation")
    except (json.JSONDecodeError, OSError):
        return None


def save_last_recommendation(recommendation: str) -> None:
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump({"last_recommendation": recommendation}, f)


def format_message(value, classification, recommendation, prices) -> str:
    lines = [
        f"Empfehlung: {recommendation}",
        f"Fear & Greed Index: {value} ({classification})",
        "",
    ]
    for coin_id, symbol in COINS.items():
        info = prices.get(coin_id)
        if info:
            price = info["usd"]
            change = info.get("usd_24h_change", 0)
            lines.append(f"{symbol}: ${price:,.2f} ({change:+.2f}% 24h)")
    return "\n".join(lines)


def run_once():
    value, classification = get_fear_greed()
    recommendation = get_recommendation(value)
    prices = get_prices()

    message = format_message(value, classification, recommendation, prices)
    logger.info(message.replace("\n", " | "))

    last = load_last_recommendation()
    if recommendation != last:
        send_telegram(f"Krypto-Update:\n{message}")
        save_last_recommendation(recommendation)
    else:
        logger.info(f"Empfehlung unveraendert ({recommendation}) -> keine Telegram-Nachricht.")


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
        run_once()
    else:
        main()
