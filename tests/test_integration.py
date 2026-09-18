import sys
from pathlib import Path

# Configurar encoding utf-8 para la salida estándar en Windows console
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

# Agregar directorio raíz al PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from alerts.telegram_bot import send_ev_alert
from config.settings import CACHE_TTL_MINUTES, MAX_EV_SANITY, MIN_EV_THRESHOLD, ODDS_API_KEY
from core.cache import OddsCache
from core.normalizer import match_teams
from core.value_engine import is_value_bet, remove_vig_three_way, remove_vig_two_way
from scrapers.pinnacle_sharp import PinnacleSharpScraper
from scrapers.playdoit import PlaydoitScraper


def main() -> None:
    print("=== PRUEBA DE INTEGRACIÓN CON COINCIDENCIA ESTRICTA DE LÍNEAS & SANITY CHECK ===")

    if not ODDS_API_KEY or ODDS_API_KEY == "your_odds_api_key_here":
        print("\n❌ Error: 'ODDS_API_KEY' no está configurada en el archivo .env.\n")
        return

    pinnacle_scraper = PinnacleSharpScraper(api_key=ODDS_API_KEY)
    playdoit_scraper = PlaydoitScraper()
    cache = OddsCache(default_ttl_minutes=CACHE_TTL_MINUTES)

    # 1. Verificar Caché en Disco JSON antes de consultar The Odds API
    print("\n1. Verificando cuotas Sharp de Pinnacle en Caché...")
    pinnacle_events = cache.get("pinnacle_odds_soccer_epl")

    if pinnacle_events is not None:
        print("[CACHE HIT] Usando cuotas de Pinnacle en memoria/disco. 0 créditos consumidos.")
    else:
        print("Consultando 1 llamada a The Odds API (Premier League / Pinnacle)...")
        pinnacle_events = pinnacle_scraper.get_match_odds(sports=["soccer_epl"])

    print(f"   [Pinnacle Real] Eventos obtenidos: {len(pinnacle_events)}")

    # 2. Consultar eventos de Playdoit
    print("\n2. Consultando eventos Recreativos de Playdoit (Altenar Real)...")
    playdoit_events = playdoit_scraper.get_top_events()
    print(f"   [Playdoit Real] Eventos obtenidos: {len(playdoit_events)}")

    if not playdoit_events:
        print("❌ No se obtuvieron eventos de Playdoit.")
        return

    matched_count = 0
    value_found = 0

    print("\n3. Comparativa Lado a Lado (Línea Exacta 2.5 & Sanity Check EV +4% a +20%):\n")

    for i, pd_event in enumerate(playdoit_events, start=1):
        pd_id = pd_event["event_id"]
        pd_name = pd_event["name"]

        parts = pd_name.replace(" vs. ", " vs ").replace(" - ", " vs ").split(" vs ")
        if len(parts) < 2:
            continue

        home_team = parts[0].strip()
        away_team = parts[1].strip()

        # Emparejar con Pinnacle
        pin_match = match_teams(home_team, away_team, pinnacle_events, threshold=75)

        if not pin_match:
            print(f"[{i}] {pd_name:<45} | ⚠️ Sin match en Pinnacle (soccer_epl)")
            continue

        matched_count += 1
        matched_home = pin_match.get("home") or pin_match.get("home_team")
        matched_away = pin_match.get("away") or pin_match.get("away_team")
        print("-" * 75)
        print(f"[{i}] {pd_name:<45} | ✅ Match Pinnacle: {matched_home} vs {matched_away}")

        pd_odds = playdoit_scraper.get_event_odds(pd_id)
        if not pd_odds:
            continue

        pin_totals = pin_match.get("totals", {})
        pin_h2h = pin_match.get("h2h", {})

        # A. Mercado Totales (Exclusivamente Línea 2.5)
        for item in pd_odds:
            if item["market"] == "Total Goals" and item.get("line") == 2.5:
                sel_name = item["selection"]
                pd_odd = item["odd"]

                line_25_sharp = pin_totals.get(2.5)
                if not line_25_sharp:
                    continue

                over_sharp = line_25_sharp.get("over")
                under_sharp = line_25_sharp.get("under")

                if not over_sharp or not under_sharp or over_sharp <= 1.0 or under_sharp <= 1.0:
                    continue

                try:
                    fair_over, fair_under = remove_vig_two_way(over_sharp, under_sharp)

                    target_fair_prob = None
                    if sel_name.lower() == "over":
                        target_fair_prob = fair_over
                    elif sel_name.lower() == "under":
                        target_fair_prob = fair_under

                    if target_fair_prob:
                        is_val, ev_pct = is_value_bet(
                            pd_odd, target_fair_prob, min_ev=MIN_EV_THRESHOLD, max_ev_sanity=MAX_EV_SANITY
                        )
                        fair_odd = 1.0 / target_fair_prob
                        ev_flag = "🔥 [+EV ALERTA DISPARADA]" if is_val else ""

                        print(
                            f"   📊 Total Goals ({sel_name} 2.5): Playdoit: {pd_odd:.2f} | Pinnacle Fair: {fair_odd:.2f} (Sharp: {over_sharp:.2f}/{under_sharp:.2f}) | EV: +{ev_pct:.2f}% {ev_flag}"
                        )

                        if is_val:
                            value_found += 1
                            send_ev_alert(
                                match=pd_name,
                                market="Total Goals 2.5",
                                selection=f"{sel_name} 2.5",
                                rec_odd=pd_odd,
                                fair_odd=fair_odd,
                                ev_pct=ev_pct,
                                bookmaker="Playdoit (Real)",
                            )
                except ValueError:
                    pass

        # B. Mercado 1X2 (Moneyline 3-Way)
        h2h_home = pin_h2h.get("Home")
        h2h_draw = pin_h2h.get("Draw")
        h2h_away = pin_h2h.get("Away")

        if h2h_home and h2h_draw and h2h_away and h2h_home > 1.0 and h2h_draw > 1.0 and h2h_away > 1.0:
            try:
                fair_home, fair_draw, fair_away = remove_vig_three_way(h2h_home, h2h_draw, h2h_away)
                fair_map = {"Home": fair_home, "Draw": fair_draw, "Away": fair_away}

                for item in pd_odds:
                    if item["market"] == "1X2":
                        sel_name = item["selection"]
                        pd_odd = item["odd"]

                        target_fair_prob = fair_map.get(sel_name)
                        if target_fair_prob:
                            is_val, ev_pct = is_value_bet(
                                pd_odd, target_fair_prob, min_ev=MIN_EV_THRESHOLD, max_ev_sanity=MAX_EV_SANITY
                            )
                            fair_odd = 1.0 / target_fair_prob
                            ev_flag = "🔥 [+EV ALERTA DISPARADA]" if is_val else ""

                            print(
                                f"   ⚽ 1X2 ({sel_name}): Playdoit: {pd_odd:.2f} | Pinnacle Fair: {fair_odd:.2f} (Sharp: {h2h_home:.2f}/{h2h_draw:.2f}/{h2h_away:.2f}) | EV: +{ev_pct:.2f}% {ev_flag}"
                            )

                            if is_val:
                                value_found += 1
                                send_ev_alert(
                                    match=pd_name,
                                    market="1X2 (Ganador)",
                                    selection=sel_name,
                                    rec_odd=pd_odd,
                                    fair_odd=fair_odd,
                                    ev_pct=ev_pct,
                                    bookmaker="Playdoit (Real)",
                                )
            except ValueError:
                pass

    print("\n----------------------------------------------------------------------")
    if value_found > 0:
        print(f"✅ Se encontraron {value_found} oportunidad(es) +EV real(es) válidas y se enviaron a Telegram.")
    else:
        print("ℹ️ No superó el umbral de +4% EV o las alertas fueron filtradas por el Sanity Check (+20%). No se envió alerta.")

    print(f"Resumen de prueba: Partidos analizados: {len(playdoit_events)} | Emparejados: {matched_count} | Oportunidades +EV: {value_found}")


if __name__ == "__main__":
    main()
