import os
from pathlib import Path
from dotenv import load_dotenv

# Cargar variables de entorno desde el archivo .env
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

# Telegram Settings
TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")

# The Odds API Key
ODDS_API_KEY: str = os.getenv("ODDS_API_KEY", "")

# Ligas Top Exclusivas (3 Ligas de Producción)
TOP_LEAGUES: list[str] = [
    "soccer_epl",
    "soccer_spain_la_liga",
    "soccer_mexico_ligamx",
]
ACTIVE_SPORTS: list[str] = TOP_LEAGUES

# Control de Caché en Disco JSON (30 minutos TTL)
CACHE_TTL_MINUTES: int = int(os.getenv("CACHE_TTL_MINUTES", "30"))

# Control del Scheduler
FORCE_SCAN_ON_START: bool = os.getenv("FORCE_SCAN_ON_START", "True").lower() in ("true", "1", "yes")

# Umbrales Quant y Filtros de Seguridad
MIN_EV_THRESHOLD: float = float(os.getenv("MIN_EV_THRESHOLD", "0.04"))  # +4.0%
MAX_EV_SANITY: float = float(os.getenv("MAX_EV_SANITY", "0.20"))        # +20.0%
ALERT_ANTI_SPAM_TTL_MINUTES: int = int(os.getenv("ALERT_ANTI_SPAM_TTL_MINUTES", "120"))  # 2 Horas

# Altenar Sport ID (Fútbol)
SPORT_ID: int = int(os.getenv("SPORT_ID", "66"))
