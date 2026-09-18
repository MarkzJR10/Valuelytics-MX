import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Configurar encoding utf-8 para la salida estándar en Windows console
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

# Agregar directorio raíz al PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from alerts.telegram_bot import send_ev_alert
from core.value_engine import calculate_ev, remove_vig_two_way

load_dotenv()


def test_dry_run() -> None:
    print("=== INICIANDO PRUEBA EN SECO (0 TOKENS CONSUMIDOS) ===")

    # 1. Simular datos Sharp de Pinnacle (como si vinieran de The Odds API)
    mock_pinnacle_over = 1.85
    mock_pinnacle_under = 2.05

    # 2. Simular cuota colgada/desfasada en Playdoit
    mock_playdoit_over = 2.10

    # 3. Calcular Fair Odds sin Vig
    prob_over, prob_under = remove_vig_two_way(mock_pinnacle_over, mock_pinnacle_under)
    fair_odd_over = 1 / prob_over

    # 4. Calcular +EV
    ev = calculate_ev(mock_playdoit_over, prob_over)
    ev_pct = ev * 100

    print(f"Línea Pinnacle: Over {mock_pinnacle_over} | Under {mock_pinnacle_under}")
    print(
        f"Probabilidad Justa Over: {prob_over * 100:.2f}% (Cuota Fair: {fair_odd_over:.2f})"
    )
    print(f"Cuota Playdoit: {mock_playdoit_over}")
    print(f"Valor Esperado Calculado: +{ev_pct:.2f}%")

    # 5. Probar envío de alerta real a Telegram si supera el +4%
    if ev_pct >= 4.0:
        print("\n🚀 Disparando alerta de prueba a Telegram...")
        sent = send_ev_alert(
            match="Arsenal vs. Chelsea (SIMULACIÓN)",
            market="Total Goles 2.5",
            selection="Más de 2.5",
            rec_odd=mock_playdoit_over,
            fair_odd=fair_odd_over,
            ev_pct=ev_pct,
            bookmaker="Playdoit",
        )
        if sent:
            print("✅ Alerta enviada. Revisa tu canal de Telegram.")
        else:
            print("❌ No se pudo enviar la alerta a Telegram. Revisa el log de errores.")
    else:
        print("❌ No superó el umbral.")


if __name__ == "__main__":
    test_dry_run()
