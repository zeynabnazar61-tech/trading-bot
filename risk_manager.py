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
from datetime import date, datetime, timedelta
import config
from logger_setup import get_logger

logger = get_logger("risk_manager")


class RiskManager:
    def __init__(self):
        self.daily_pnl = 0.0
        self.trades_today = 0
        self.current_day = date.today()
        self.trading_halted = False
        self.last_trade_time = None

    def _reset_if_new_day(self):
        if date.today() != self.current_day:
            logger.info("Neuer Handelstag -> Zaehler zurueckgesetzt.")
            self.daily_pnl = 0.0
            self.trades_today = 0
            self.current_day = date.today()
            self.trading_halted = False

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
        logger.info(
            f"Trade #{self.trades_today} heute erfasst. Tages-PnL: {self.daily_pnl:.2f} USD"
        )