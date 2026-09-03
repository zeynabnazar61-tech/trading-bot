"""
Zentrale Konfiguration.
Alle Parameter für Strategie und Risikomanagement werden HIER geändert,
nicht irgendwo tief im Code -> so bleibt alles übersichtlich.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# --- API Zugangsdaten ---
ALPACA_API_KEY = os.getenv("ALPACA_API_KEY")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")
ALPACA_PAPER = os.getenv("ALPACA_PAPER", "true").lower() == "true"

# --- Sentry: Fehlerüberwachung (optional) ---
SENTRY_DSN = os.getenv("SENTRY_DSN")
if SENTRY_DSN:
    import sentry_sdk
    sentry_sdk.init(dsn=SENTRY_DSN, traces_sample_rate=0.0, environment="paper" if ALPACA_PAPER else "live")

# --- Handelsparameter ---
SYMBOLS = ["AAPL", "XOM", "SPY", "JNJ"]  # Aktien, die der Bot gleichzeitig beobachtet/handelt
# Bewusst aus unterschiedlichen Sektoren gewaehlt (Tech, Energie, Breiter Markt, Gesundheit),
# damit nicht alle Positionen bei einem schlechten Markttag gleichzeitig fallen.
# (MSFT durch XOM ersetzt: AAPL+MSFT waren beide Tech und stark korreliert -> kaum echte Diversifikation.)
SYMBOL = SYMBOLS[0]          # Rueckwaertskompatibel: Standard-Symbol fuer Backtest/Tests (nur 1 Symbol)
TIMEFRAME_MINUTES = 15       # Kerzen-Zeitrahmen für die Strategie

# --- Strategie: Moving Average Crossover ---
SHORT_WINDOW = 20            # kurzer gleitender Durchschnitt
LONG_WINDOW = 50             # langer gleitender Durchschnitt

# --- Risikomanagement (WICHTIGSTER TEIL!) ---
MAX_POSITION_SIZE_USD = 5000.0    # max. Kapital pro Position
STOP_LOSS_PCT = 0.02              # 2% Stop-Loss pro Trade
TAKE_PROFIT_PCT = 0.08            # 8% Take-Profit pro Trade
# Maximaler erlaubter Tagesverlust: Der Bot stoppt sich selbst, sobald der
# kumulierte Verlust an einem Tag 100 USD erreicht. Ein konservativer Wert
# begrenzt das Risiko einzelner schlechter Handelstage und schützt Kapital.
MAX_DAILY_LOSS_USD = 100.0        # Bot stoppt sich selbst bei Erreichen
MAX_TRADES_PER_DAY = 5            # Überhandeln verhindern

# --- Sonstiges ---
LOOP_INTERVAL_SECONDS = 60        # wie oft der Bot den Markt prüft
LOG_FILE = "logs/trading_bot.log"
RISK_STATE_FILE = "logs/risk_state.json"  # Persistenz fuer RiskManager-Tageszaehler (ueberlebt Neustarts)

# --- Telegram (optional) ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


def validate_config():
    """Prüft beim Start, ob alles Nötige vorhanden ist."""
    if not ALPACA_API_KEY or not ALPACA_SECRET_KEY:
        raise ValueError(
            "ALPACA_API_KEY oder ALPACA_SECRET_KEY fehlt! "
            "Bitte .env Datei anlegen (siehe .env.example)."
        )
    if not ALPACA_PAPER:
        print("=" * 60)
        print("!! WARNUNG: LIVE-TRADING MODUS AKTIV - ECHTES GELD !!")
        print("=" * 60)
        confirm = input("Wirklich fortfahren? Tippe 'JA' zum Bestätigen: ")
        if confirm != "JA":
            raise SystemExit("Abgebrochen.")
 
# --- Erweiterte Strategie-Parameter (Trendfilter & Rauschfilter) ---
TREND_WINDOW = 100
MIN_CROSSOVER_MARGIN_PCT = 0.0002
COOLDOWN_MINUTES = 30
MAX_RISK_PER_TRADE_USD = 100.0

# --- Fill-Bestaetigung (ZOZ-33) ---
# Wie lange/oft nach einer Order auf den Fill-Status gepollt wird, bevor
# der Bot den Versuch als Timeout wertet (kein record_trade mehr).
ORDER_FILL_TIMEOUT_SECONDS = 30
ORDER_FILL_POLL_INTERVAL_SECONDS = 2

# --- Trailing-Stop-Vergleichsvariante (ZOZ-40, NUR Backtest, nicht live) ---
# Wird ausschliesslich von strategy_trailing.py / backtest_trailing.py genutzt.
# Bestehende Konstanten (STOP_LOSS_PCT, TAKE_PROFIT_PCT, MAX_DAILY_LOSS_USD, ...)
# bleiben unveraendert.
TRAILING_STOP_PCT = 0.05          # 5% unter dem Hoch seit Einstieg -> Exit
