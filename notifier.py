"""
Sendet optional eine Telegram-Nachricht bei jedem Trade/Ereignis.
Wenn keine Telegram-Daten in .env stehen, wird einfach nichts gesendet.
"""
import requests
import config
from logger_setup import get_logger

logger = get_logger("notifier")


def send_telegram(message: str) -> None:
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        return  # Telegram nicht konfiguriert -> überspringen

    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": config.TELEGRAM_CHAT_ID, "text": message}

    try:
        response = requests.post(url, data=payload, timeout=10)
        response.raise_for_status()
    except Exception as e:
        logger.warning(f"Telegram-Benachrichtigung fehlgeschlagen: {e}")
