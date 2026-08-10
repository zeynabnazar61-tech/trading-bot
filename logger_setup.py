"""
Logging-Konfiguration für den Trading-Bot.
"""

import logging
import os
import sys

os.makedirs("logs", exist_ok=True)

# Windows-Konsole nutzt sonst cp1252, das kann z.B. Emojis nicht darstellen
# und wuerde beim Loggen mit UnicodeEncodeError abstuerzen.
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

logger = logging.getLogger("trading_bot")
logger.setLevel(logging.INFO)

if not logger.handlers:
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

    file_handler = logging.FileHandler("logs/trading_bot.log", encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)


def get_logger(name: str = "trading_bot"):
    return logger