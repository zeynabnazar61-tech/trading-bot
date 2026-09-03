# Trading Bot (Paper-Trading, Alpaca API)

Ein modularer, automatisierter Trading-Bot mit Moving-Average-Crossover-Strategie.
**Standardmäßig im Paper-Trading-Modus (Fake-Geld) - so sollte es auch erstmal bleiben.**

## ⚠️ Wichtiger Hinweis

Dieser Bot ist ein Lern- und Test-Framework. Automatisiertes Trading ist riskant,
auch mit sauberem Code. Teste über Wochen im Paper-Trading, bevor du auch nur
in Erwägung ziehst, echtes Geld zu riskieren - und dann nur mit Geld, dessen
Verlust du dir leisten kannst.

## Projektstruktur

```
trading-bot/
├── config.py          # ALLE Parameter (Strategie, Risiko) werden hier geändert
├── data.py             # Marktdaten von Alpaca holen
├── strategy.py         # Handelslogik (Moving Average Crossover)
├── risk_manager.py      # Stop-Loss, Positionsgröße, Tagesverlust-Limit
├── executor.py          # Platziert die eigentlichen Orders
├── logger_setup.py       # Protokollierung
├── notifier.py           # Optionale Telegram-Benachrichtigungen
├── main.py               # Hauptschleife - startet den Bot
├── backtest.py            # Testet Strategie an historischen Daten
├── tests/                 # Unit-Tests
├── logs/                   # Log-Dateien (wird automatisch erstellt)
├── .env.example             # Vorlage für API-Keys
└── requirements.txt
```

## Einrichtung

### 1. Alpaca-Konto erstellen

- Gehe zu https://alpaca.markets und erstelle ein kostenloses Konto
- Im Dashboard unter "Paper Trading" deine **Paper-API-Keys** generieren
  (NICHT die Live-Keys - erstmal nur Paper!)

### 2. Python-Umgebung einrichten

```bash
cd trading-bot
python3 -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. API-Keys eintragen

```bash
cp .env.example .env
```

Dann `.env` öffnen und deine Paper-Trading-Keys eintragen:

```
ALPACA_API_KEY=dein_key
ALPACA_SECRET_KEY=dein_secret
ALPACA_PAPER=true
```

### 4. Strategie-Parameter anpassen (optional)

Alle Einstellungen in `config.py`:
- `SYMBOLS` - Liste der Aktien, die gleichzeitig beobachtet/gehandelt werden (z.B. `["AAPL", "MSFT", "SPY", "JNJ"]`).
  Risikolimits (Tagesverlust, max. Trades/Tag, Cooldown) gelten global für den
  gesamten Bot, nicht pro Aktie einzeln.
- `SHORT_WINDOW` / `LONG_WINDOW` - Moving-Average-Perioden
- `MAX_POSITION_SIZE_USD` - maximales Kapital pro Position
- `STOP_LOSS_PCT` / `TAKE_PROFIT_PCT` - Risikogrenzen pro Trade
- `MAX_DAILY_LOSS_USD` - Bot stoppt sich selbst bei Erreichen

## Nutzung

### Schritt A: Backtest (IMMER ZUERST)

Teste die Strategie an historischen Daten, bevor überhaupt live getestet wird:

```bash
python backtest.py --symbol AAPL --days 365
```

Das zeigt dir Sharpe Ratio, Max Drawdown, Win-Rate und Gesamtrendite.
Wenn das Ergebnis schlecht aussieht, Strategie in `strategy.py` anpassen und erneut testen.

### Schritt B: Tests ausführen

```bash
pytest tests/
```

### Schritt C: Paper-Trading starten

```bash
python main.py
```

Der Bot läuft jetzt dauerhaft, prüft alle `LOOP_INTERVAL_SECONDS` den Markt
und protokolliert alles in `logs/trading_bot.log`.

Zum Stoppen: `Strg+C` (der Bot beendet sich dann sauber).

### Schritt D: Dauerhaft laufen lassen (Deployment)

Für einen kleinen Server (z.B. Hetzner, DigitalOcean) mit systemd:

```ini
# /etc/systemd/system/trading-bot.service
[Unit]
Description=Trading Bot
After=network.target

[Service]
WorkingDirectory=/pfad/zu/trading-bot
ExecStart=/pfad/zu/trading-bot/venv/bin/python main.py
Restart=always
RestartSec=10
User=deinbenutzer

[Install]
WantedBy=multi-user.target
```

Aktivieren:
```bash
sudo systemctl enable trading-bot
sudo systemctl start trading-bot
sudo systemctl status trading-bot   # Status prüfen
journalctl -u trading-bot -f         # Live-Logs ansehen
```

`Restart=always` sorgt dafür, dass der Bot bei einem Absturz automatisch neu startet.

## Sicherheits-Check der Abhängigkeiten

Vor jedem Deployment (besonders vor einem Wechsel zu Live-Trading) auf bekannte
Sicherheitslücken in den genutzten Bibliotheken prüfen:

```bash
pip install -r requirements-dev.txt
pip-audit
```

Meldet `pip-audit` eine Lücke, die betroffene Bibliothek in `requirements.txt`
auf eine gepatchte Version aktualisieren und den Bot danach erneut testen,
bevor weitergemacht wird.

## Telegram-Benachrichtigungen (optional)

1. Bot bei [@BotFather](https://t.me/BotFather) auf Telegram erstellen -> Token erhalten
2. Chat-ID herausfinden (z.B. über [@userinfobot](https://t.me/userinfobot))
3. Beides in `.env` eintragen -> ab sofort Nachricht bei jedem Trade/Fehler

## Von Paper- zu Live-Trading wechseln

**Erst NACH mehreren Wochen erfolgreichem Paper-Trading in Erwägung ziehen.**

1. Live-API-Keys von Alpaca generieren (nicht die Paper-Keys!)
2. In `.env`: `ALPACA_PAPER=false` setzen und Live-Keys eintragen
3. Bot fragt beim Start eine Sicherheitsbestätigung ab

## Nächste Schritte / Ideen zur Erweiterung

- Weitere Strategie-Indikatoren (RSI, Bollinger Bands) in `strategy.py` ergänzen
- Mehrere Symbole gleichzeitig handeln
- Trailing-Stop-Loss statt fixem Stop-Loss
- Dashboard zur Live-Überwachung (z.B. mit Streamlit)
