import sys
from pathlib import Path

# Configurar encoding utf-8 para la salida estándar en Windows console
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

# Agregar directorio raíz al PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scrapers.playdoit import PlaydoitScraper


def main() -> None:
    print("=== PRUEBA DE EXTRACCIÓN REFINADA: PLAYDOIT (ALTENAR) ===")
    scraper = PlaydoitScraper()

    print("Obteniendo eventos principales de fútbol...")
    events = scraper.get_top_events()

    if not events:
        print("❌ No se pudieron obtener eventos de Playdoit.")
        return

    print(f"✅ Se encontraron {len(events)} eventos. Analizando los primeros 3 partidos:\n")

    for i, event in enumerate(events[:3], start=1):
        event_id = event["event_id"]
        name = event["name"]
        start_date = event["start_date"]

        print("-" * 65)
        print(f"[{i}] Partido: {name:<45} | ID: {event_id}")

        odds = scraper.get_event_odds(event_id)
        if not odds:
            print("   ⚠️ No se encontraron cuotas para los mercados filtrados.")
            continue

        # 1. Mercado 1X2 / Ganador
        h2h_odds = [o for o in odds if o["market"] == "1X2"]
        if h2h_odds:
            print("   ⚽ Mercado 1X2 (Ganador del Partido):")
            for item in h2h_odds:
                print(f"      - Selección: {item['selection']:<8} | Cuota: {item['odd']:.2f}")

        # 2. Mercado Total Goals (Filtrado .5)
        totals_odds = [o for o in odds if o["market"] == "Total Goals"]
        if totals_odds:
            print("   📊 Mercado Total Goals (Líneas Estándar .5):")
            for item in totals_odds:
                line_str = f" (Línea: {item['line']})" if item["line"] is not None else ""
                print(f"      - Selección: {item['selection']:<8}{line_str:<14} | Cuota: {item['odd']:.2f}")

        # 3. Mercado Both Teams to Score (Ambos Anotan)
        btts_odds = [o for o in odds if o["market"] == "Both Teams to Score"]
        if btts_odds:
            print("   🎯 Mercado Both Teams to Score (Ambos Anotan):")
            for item in btts_odds:
                print(f"      - Selección: {item['selection']:<8} | Cuota: {item['odd']:.2f}")

    print("\n-----------------------------------------------------------------")
    print("Prueba finalizada exitosamente.")


if __name__ == "__main__":
    main()
