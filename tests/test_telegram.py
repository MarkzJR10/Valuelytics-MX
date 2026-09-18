import sys
from pathlib import Path

# Configurar encoding utf-8 para la salida estándar en Windows console
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

# Agregar directorio raíz al PYTHONPATH para permitir ejecuciones directas
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from alerts.telegram_bot import send_ev_alert
from config.settings import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID


def main() -> None:
    print("--- PRUEBA DE CONEXIÓN TELEGRAM BOT ---")
    print(
        f"Token configurado: {TELEGRAM_BOT_TOKEN[:8]}..."
        if TELEGRAM_BOT_TOKEN
        else "Token NO configurado"
    )
    print(
        f"Chat ID configurado: {TELEGRAM_CHAT_ID}"
        if TELEGRAM_CHAT_ID
        else "Chat ID NO configurado"
    )

    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print(
            "\n❌ Error: Debes definir TELEGRAM_BOT_TOKEN y TELEGRAM_CHAT_ID en tu archivo .env"
        )
        return

    print("\nEnviando mensaje de prueba...")
    success = send_ev_alert(
        match="Prueba FC vs Valuelytics United",
        market="Both Teams to Score",
        selection="Yes",
        rec_odd=2.10,
        fair_odd=1.90,
        ev_pct=10.53,
        bookmaker="Playdoit (Test)",
    )

    if success:
        print("✅ Alerta enviada con éxito. Revisa tu canal de Telegram.")
    else:
        print("❌ Falló el envío de la alerta. Revisa los logs de error.")


if __name__ == "__main__":
    main()
