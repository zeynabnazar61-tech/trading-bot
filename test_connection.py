# Kurzes Testskript, das der Nutzer lokal ausführen kann,
# um zu prüfen ob seine Keys funktionieren
import os
import sys
sys.stdout.reconfigure(encoding="utf-8")
from dotenv import load_dotenv
load_dotenv()

api_key = os.getenv("ALPACA_API_KEY")
secret_key = os.getenv("ALPACA_SECRET_KEY")

if not api_key or api_key == "dein_paper_api_key_hier":
    print("❌ API_KEY nicht gesetzt - bitte .env Datei ausfüllen")
elif not secret_key or secret_key == "dein_paper_secret_key_hier":
    print("❌ SECRET_KEY nicht gesetzt - bitte .env Datei ausfüllen")
else:
    print("✅ Keys gefunden in .env - bereit für den nächsten Schritt")
