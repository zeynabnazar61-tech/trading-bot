"""
Risikomanagement.

Das ist der wichtigste Teil des ganzen Bots. Eine perfekte Strategie
ohne Risikomanagement kann trotzdem dein ganzes Kapital verlieren.

Regeln hier:
- Bot stoppt sich SELBST, wenn Tagesverlust-Limit erreicht ist
- Bot begrenzt Anzahl der Trades pro Tag
- Jede Position bekommt automatisch Stop-Loss und Take-Profit
- NEU: Cooldown nach jedem Trade (kein sofortiges Nachtraden)
- NEU: Positionsgroesse wird anhand des Stop-Loss-Risikos berechnet,
       nicht mehr anhand eines festen Betrags
"""
import json
import os
from datetime import date, datetime, timedelta
import config
from logger_setup import get_logger

logger = get_logger("risk_manager")


class RiskManager:
    def __init__(self, state_file: str = None):
        self.state_file = state_file if state_file is not None else config.RISK_STATE_FILE
        self.daily_pnl = 0.0
        self.trades_today = 0
        self.current_day = date.today()
        self.trading_halted = False
        self.last_trade_time = None
        self._load_state()

    def _load_state(self):
        """Laedt den gespeicherten Zustand, falls die Datei existiert und vom heutigen Tag ist."""
        if not self.state_file or not os.path.exists(self.state_file):
            return

        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            saved_day = date.fromisoformat(data["current_day"])
        except (OSError, ValueError, KeyError, json.JSONDecodeError):
            logger.warning(f"Risk-State-Datei '{self.state_file}' ist unlesbar/korrupt -> ignoriere sie.")
            return

        if saved_day != date.today():
            logger.info("Gespeicherter Risk-State stammt von einem frueheren Tag -> starte neuen Tag.")
            return

        self.daily_pnl = data.get("daily_pnl", 0.0)
        self.trades_today = data.get("trades_today", 0)
        self.trading_halted = data.get("trading_halted", False)
        self.current_day = saved_day
        logger.info(
            f"Risk-State geladen: daily_pnl={self.daily_pnl:.2f}, trades_today={self.trades_today}, "
            f"trading_halted={self.trading_halted}"
        )

    def _save_state(self):
        """Speichert den aktuellen Zustand, damit er einen Neustart am selben Tag uebersteht."""
        if not self.state_file:
            return

        try:
            directory = os.path.dirname(self.state_file)
            if directory:
                os.makedirs(directory, exist_ok=True)
            data = {
                "daily_pnl": self.daily_pnl,
                "trades_today": self.trades_today,
                "trading_halted": self.trading_halted,
                "current_day": self.current_day.isoformat(),
            }
            with open(self.state_file, "w", encoding="utf-8") as f:
                json.dump(data, f)
        except OSError:
            logger.warning(f"Risk-State konnte nicht in '{self.state_file}' gespeichert werden.")

    def _reset_if_new_day(self):
        if date.today() != self.current_day:
            logger.info("Neuer Handelstag -> Zaehler zurueckgesetzt.")
            self.daily_pnl = 0.0
            self.trades_today = 0
            self.current_day = date.today()
            self.trading_halted = False
            self._save_state()

    def can_trade(self) -> bool:
        """Prueft, ob der Bot aktuell ueberhaupt handeln darf."""
        self._reset_if_new_day()

        if self.trading_halted:
            return False

        if self.daily_pnl <= -abs(config.MAX_DAILY_LOSS_USD):
            logger.warning(
                f"Tagesverlust-Limit erreicht ({self.daily_pnl:.2f} USD) -> Handel gestoppt fuer heute."
            )
            self.trading_halted = True
            self._save_state()
            return False

        if self.trades_today >= config.MAX_TRADES_PER_DAY:
            logger.warning("Maximale Anzahl Trades pro Tag erreicht -> kein weiterer Handel heute.")
            return False

        if self.last_trade_time is not None:
            elapsed = datetime.now() - self.last_trade_time
            cooldown = timedelta(minutes=config.COOLDOWN_MINUTES)
            if elapsed < cooldown:
                remaining = (cooldown - elapsed).total_seconds() / 60
                logger.info(f"Cooldown aktiv, noch {remaining:.1f} Min. -> kein Handel.")
                return False

        return True

    def calculate_position_size(self, current_price: float) -> int:
        """
        Berechnet die Positionsgroesse anhand des Stop-Loss-Risikos:
        Verlust pro Aktie (bei Stop-Loss-Treffer) * Anzahl <= MAX_RISK_PER_TRADE_USD.
        Zusaetzlich wird die Positionsgroesse durch MAX_POSITION_SIZE_USD gedeckelt.
        """
        if current_price <= 0:
            return 0

        risk_per_share = current_price * config.STOP_LOSS_PCT
        if risk_per_share <= 0:
            return 0

        qty_by_risk = int(config.MAX_RISK_PER_TRADE_USD // risk_per_share)
        qty_by_cap = int(config.MAX_POSITION_SIZE_USD // current_price)

        qty = min(qty_by_risk, qty_by_cap)
        return max(qty, 0)

    def get_stop_loss_price(self, entry_price: float) -> float:
        return round(entry_price * (1 - config.STOP_LOSS_PCT), 2)

    def get_take_profit_price(self, entry_price: float) -> float:
        return round(entry_price * (1 + config.TAKE_PROFIT_PCT), 2)

    def record_trade(self, pnl: float = 0.0):
        self._reset_if_new_day()
        self.trades_today += 1
        self.daily_pnl += pnl
        self.last_trade_time = datetime.now()
        self._save_state()
        logger.info(
            f"Trade #{self.trades_today} heute erfasst. Tages-PnL: {self.daily_pnl:.2f} USD"
        )