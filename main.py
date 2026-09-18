import logging
import os
import sys
import time
from datetime import datetime, timedelta
import schedule

# Configurar encoding utf-8 para la salida estándar en Windows console
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

# Asegurar que exista el directorio logs/ en la raíz del proyecto
logs_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
os.makedirs(logs_dir, exist_ok=True)
log_file_path = os.path.join(logs_dir, "valuelytics.log")

# Configurar logging estándar con salidas simultáneas a archivo UTF-8 y consola
file_handler = logging.FileHandler(log_file_path, encoding="utf-8")
console_handler = logging.StreamHandler(sys.stdout)

formatter = logging.Formatter(
    fmt="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

logger = logging.getLogger("ValuelyticsMX")
logger.setLevel(logging.INFO)
logger.addHandler(file_handler)
logger.addHandler(console_handler)

from alerts.telegram_bot import send_ev_alert
from config.settings import (
    ALERT_ANTI_SPAM_TTL_MINUTES,
    CACHE_TTL_MINUTES,
    FORCE_SCAN_ON_START,
    MAX_EV_SANITY,
    MIN_EV_THRESHOLD,
    ODDS_API_KEY,
    SPORT_ID,
    TOP_LEAGUES,
)
from core.cache import OddsCache
from core.normalizer import match_teams
from core.value_engine import is_value_bet, remove_vig_three_way, remove_vig_two_way
from scrapers.pinnacle_sharp import PinnacleSharpScraper
from scrapers.playdoit import PlaydoitScraper


def is_operational_window() -> tuple[bool, list[str]]:
    """
    Evalúa el día de la semana y la hora local (México) para determinar la ventana operativa y ligas activas.

    Reglas:
    - Viernes (weekday 4): 14:00 a 23:00 hrs. Ligas: TOP_LEAGUES.
    - Sábado y Domingo (weekdays 5, 6): 07:00 a 22:00 hrs. Ligas: TOP_LEAGUES.
    - Lunes a Jueves (weekdays 0, 1, 2, 3): Barridos fijos a las 13:00 y 19:00 hrs.
    - Noche (23:00 a 07:00 hrs): Reposo total sin consumir peticiones.

    Returns:
        tuple[bool, list[str]]: (Esta_En_Ventana, Ligas_Activas)
    """
    now = datetime.now()
    weekday = now.weekday()
    hour = now.hour

    # Noche (23:00 a 07:00)
    if hour >= 23 or hour < 7:
        return False, []

    # Viernes
    if weekday == 4:
        if 14 <= hour < 23:
            return True, TOP_LEAGUES
        return False, []

    # Sábado y Domingo
    if weekday in (5, 6):
        if 7 <= hour < 22:
            return True, TOP_LEAGUES
        return False, []

    # Lunes, Martes, Miércoles, Jueves (Barridos a las 13h y 19h)
    if weekday in (0, 1, 2, 3):
        if hour in (13, 19):
            return True, TOP_LEAGUES
        return False, []

    return False, []


def clean_expired_alerts(alert_history: dict[str, datetime], window_minutes: int = ALERT_ANTI_SPAM_TTL_MINUTES) -> None:
    """
    Limpia del historial aquellas alertas enviadas hace más del TTL anti-spam (120 minutos por defecto).
    """
    now = datetime.now()
    expired_keys = [
        k for k, timestamp in alert_history.items()
        if now - timestamp > timedelta(minutes=window_minutes)
    ]
    for key in expired_keys:
        del alert_history[key]


def scan_pipeline(
    pinnacle_scraper: PinnacleSharpScraper,
    playdoit_scraper: PlaydoitScraper,
    cache: OddsCache,
    alert_history: dict[str, datetime],
) -> None:
    """
    Pipeline de escaneo en producción continua:
    1. Verifica ventana operativa.
    2. Trigger Inversion (Playdoit First): Consulta partidos recreativos de Playdoit.
    3. Si existen eventos, consulta / lee del caché en disco JSON de Pinnacle (30 min TTL).
    4. Emparejamiento por Fuzzy Matching (>= 75%).
    5. Desmargenado 3-Way (1X2) y 2-Way (Total 2.5 y BTTS).
    6. Filtro de Valor (+4.0% a +20.0% EV max sanity).
    7. Alertas a Telegram con Anti-Spam (2 horas TTL).
    """
    logger.info("=== Iniciando ciclo de escaneo automatizado (Valuelytics MX Producción) ===")

    clean_expired_alerts(alert_history, window_minutes=ALERT_ANTI_SPAM_TTL_MINUTES)

    in_window, active_leagues = is_operational_window()
    if not in_window and not FORCE_SCAN_ON_START:
        logger.info("Fuera de ventana operativa (o horario nocturno). Omitiendo escaneo.")
        return

    if not active_leagues:
        active_leagues = TOP_LEAGUES

    # 1. Playdoit First (Inversión de Trigger para proteger cuota API)
    logger.info("Consultando eventos recreativos en Playdoit (Altenar)...")
    playdoit_events = playdoit_scraper.get_top_events()

    if not playdoit_events:
        logger.info("Playdoit no tiene partidos disponibles en este momento. Omitiendo consulta a The Odds API.")
        return

    logger.info(f"Playdoit: {len(playdoit_events)} eventos activos encontrados.")

    # 2. Consultar / Leer Caché en Disco de Pinnacle (30 min TTL)
    pinnacle_events = pinnacle_scraper.get_match_odds(sports=active_leagues)

    if not pinnacle_events:
        logger.info("No se obtuvieron cuotas Sharp de Pinnacle en este ciclo.")

    logger.info(f"Pinnacle Sharp: {len(pinnacle_events)} eventos disponibles ({CACHE_TTL_MINUTES} min TTL en disco JSON).")

    # 3. Emparejamiento y Evaluación Quant de Valor
    opportunities_found = 0

    for pd_event in playdoit_events:
        pd_id = pd_event["event_id"]
        pd_name = pd_event["name"]

        parts = pd_name.replace(" vs. ", " vs ").replace(" - ", " vs ").split(" vs ")
        if len(parts) < 2:
            continue

        home_team = parts[0].strip()
        away_team = parts[1].strip()

        # Emparejar partido con Pinnacle
        pin_match = match_teams(home_team, away_team, pinnacle_events, threshold=75)
        if not pin_match:
            continue

        pd_odds = playdoit_scraper.get_event_odds(pd_id)
        if not pd_odds:
            continue

        pin_totals = pin_match.get("totals", {})
        pin_h2h = pin_match.get("h2h", {})
        pin_btts = pin_match.get("btts", {})

        # A. Mercado 1X2 (Moneyline - Desmargenado 3-Way)
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
                            alert_key = f"{pd_id}_1X2_{sel_name}_{pd_odd}"

                            if is_val and alert_key not in alert_history:
                                logger.info(
                                    f"🔥 ¡VALOR ENCONTRADO! {pd_name} | 1X2 ({sel_name}) | Playdoit: {pd_odd:.2f} | Pinnacle Fair: {fair_odd:.2f} | EV: +{ev_pct:.2f}%"
                                )
                                sent = send_ev_alert(
                                    match=pd_name,
                                    market="1X2 (Ganador del Partido)",
                                    selection=sel_name,
                                    rec_odd=pd_odd,
                                    fair_odd=fair_odd,
                                    ev_pct=ev_pct,
                                    bookmaker="Playdoit (Real)",
                                )
                                if sent:
                                    alert_history[alert_key] = datetime.now()
                                    opportunities_found += 1
                            elif ev_pct > MAX_EV_SANITY * 100.0:
                                logger.debug(
                                    f"Sanity Check descartó {pd_name} | 1X2 ({sel_name}) con EV de +{ev_pct:.2f}%"
                                )
            except ValueError:
                pass

        # B. Mercado Total Goals (Exclusivamente línea 2.5 - Desmargenado 2-Way)
        line_25_sharp = pin_totals.get(2.5)
        if line_25_sharp:
            over_sharp = line_25_sharp.get("over")
            under_sharp = line_25_sharp.get("under")

            if over_sharp and under_sharp and over_sharp > 1.0 and under_sharp > 1.0:
                try:
                    fair_over, fair_under = remove_vig_two_way(over_sharp, under_sharp)

                    for item in pd_odds:
                        if item["market"] == "Total Goals" and item.get("line") == 2.5:
                            sel_name = item["selection"]
                            pd_odd = item["odd"]

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
                                alert_key = f"{pd_id}_TotalGoals_2.5_{sel_name}_{pd_odd}"

                                if is_val and alert_key not in alert_history:
                                    logger.info(
                                        f"🔥 ¡VALOR ENCONTRADO! {pd_name} | Total Goals ({sel_name} 2.5) | Playdoit: {pd_odd:.2f} | Pinnacle Fair: {fair_odd:.2f} | EV: +{ev_pct:.2f}%"
                                    )
                                    sent = send_ev_alert(
                                        match=pd_name,
                                        market="Total Goals 2.5",
                                        selection=f"{sel_name} 2.5",
                                        rec_odd=pd_odd,
                                        fair_odd=fair_odd,
                                        ev_pct=ev_pct,
                                        bookmaker="Playdoit (Real)",
                                    )
                                    if sent:
                                        alert_history[alert_key] = datetime.now()
                                        opportunities_found += 1
                                elif ev_pct > MAX_EV_SANITY * 100.0:
                                    logger.debug(
                                        f"Sanity Check descartó {pd_name} | Total 2.5 ({sel_name}) con EV de +{ev_pct:.2f}%"
                                    )
                except ValueError:
                    pass

        # C. Mercado Both Teams to Score (Ambos Anotan - Desmargenado 2-Way)
        yes_sharp = pin_btts.get("Yes")
        no_sharp = pin_btts.get("No")

        if yes_sharp and no_sharp and yes_sharp > 1.0 and no_sharp > 1.0:
            try:
                fair_yes, fair_no = remove_vig_two_way(yes_sharp, no_sharp)

                for item in pd_odds:
                    if item["market"] == "Both Teams to Score":
                        sel_name = item["selection"]
                        pd_odd = item["odd"]

                        target_fair_prob = None
                        if sel_name.lower() in ["yes", "si"]:
                            target_fair_prob = fair_yes
                        elif sel_name.lower() == "no":
                            target_fair_prob = fair_no

                        if target_fair_prob:
                            is_val, ev_pct = is_value_bet(
                                pd_odd, target_fair_prob, min_ev=MIN_EV_THRESHOLD, max_ev_sanity=MAX_EV_SANITY
                            )
                            fair_odd = 1.0 / target_fair_prob
                            alert_key = f"{pd_id}_BTTS_{sel_name}_{pd_odd}"

                            if is_val and alert_key not in alert_history:
                                logger.info(
                                    f"🔥 ¡VALOR ENCONTRADO! {pd_name} | Both Teams to Score ({sel_name}) | Playdoit: {pd_odd:.2f} | Pinnacle Fair: {fair_odd:.2f} | EV: +{ev_pct:.2f}%"
                                )
                                sent = send_ev_alert(
                                    match=pd_name,
                                    market="Both Teams to Score",
                                    selection=sel_name,
                                    rec_odd=pd_odd,
                                    fair_odd=fair_odd,
                                    ev_pct=ev_pct,
                                    bookmaker="Playdoit (Real)",
                                )
                                if sent:
                                    alert_history[alert_key] = datetime.now()
                                    opportunities_found += 1
                            elif ev_pct > MAX_EV_SANITY * 100.0:
                                logger.debug(
                                    f"Sanity Check descartó {pd_name} | BTTS ({sel_name}) con EV de +{ev_pct:.2f}%"
                                )
            except ValueError:
                pass

    logger.info(
        f"=== Ciclo finalizado. Oportunidades REALES VÁLIDAS alertadas en este ciclo: {opportunities_found} ===\n"
    )


def main() -> None:
    """
    Función principal de inicio del scanner en producción continua 24/7.
    """
    logger.info("Starting Valuelytics MX +EV Scanner (Producción 24/7)...")
    logger.info(f"Ligas Activas (3 Top): {TOP_LEAGUES}")
    logger.info(f"Umbral EV: +{MIN_EV_THRESHOLD * 100:.1f}% | Sanity Check Máximo EV: +{MAX_EV_SANITY * 100:.1f}%")
    logger.info(f"Caché en Disco JSON: {CACHE_TTL_MINUTES} minutos TTL | Anti-Spam Alertas: {ALERT_ANTI_SPAM_TTL_MINUTES} minutos TTL")
    logger.info(f"Archivo de log configurado: {log_file_path}")

    if not ODDS_API_KEY or ODDS_API_KEY == "your_odds_api_key_here":
        logger.warning("⚠️ RECUERDA: Define 'ODDS_API_KEY' en tu archivo .env para consultar Pinnacle Real.")

    pinnacle_scraper = PinnacleSharpScraper()
    playdoit_scraper = PlaydoitScraper(sport_id=SPORT_ID)
    cache = OddsCache(default_ttl_minutes=CACHE_TTL_MINUTES)
    alert_history: dict[str, datetime] = {}

    # Escaneo inicial de arranque si FORCE_SCAN_ON_START es True
    if FORCE_SCAN_ON_START:
        logger.info("FORCE_SCAN_ON_START = True. Ejecutando primer escaneo de arranque...")
        try:
            scan_pipeline(pinnacle_scraper, playdoit_scraper, cache, alert_history)
        except Exception as e:
            logger.error(f"Error en el escaneo de arranque: {e}", exc_info=True)

    # Programar según el día/horario
    schedule.every(20).minutes.do(
        scan_pipeline, pinnacle_scraper, playdoit_scraper, cache, alert_history
    )

    logger.info("Scheduler activado en segundo plano. Monitoreando ejecuciones programadas...")

    while True:
        try:
            schedule.run_pending()
            time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Detención manual por teclado. Finalizando Valuelytics MX...")
            break
        except Exception as e:
            logger.critical(f"Excepción no controlada en el scheduler: {e}", exc_info=True)
            time.sleep(10)


if __name__ == "__main__":
    main()
