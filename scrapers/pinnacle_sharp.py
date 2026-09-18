import logging
from typing import Any
import requests

from config.settings import CACHE_TTL_MINUTES, ODDS_API_KEY, TOP_LEAGUES
from core.cache import OddsCache

logger = logging.getLogger(__name__)


class PinnacleSharpScraper:
    """
    Scraper oficial para la fuente Sharp de Pinnacle utilizando The Odds API.
    Utiliza caché en disco JSON (30 min TTL) y registra el consumo exacto de la cuota mensual.
    """

    BASE_URL = "https://api.the-odds-api.com/v4/sports/{sport}/odds/"

    def __init__(self, api_key: str = ODDS_API_KEY) -> None:
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "ValuelyticsMX/1.0 (+https://valuelytics.mx)",
                "Accept": "application/json",
            }
        )
        self.cache = OddsCache(default_ttl_minutes=CACHE_TTL_MINUTES)

    def get_match_odds(self, sports: list[str] | None = None) -> list[dict[str, Any]]:
        """
        Consulta The Odds API con caché en disco (30 min TTL) para las ligas top especificadas.

        Args:
            sports (list[str] | None): Lista de ligas (ej. ["soccer_epl", "soccer_spain_la_liga", "soccer_mexico_ligamx"]).

        Returns:
            list[dict[str, Any]]: Lista de eventos sharp reales con formato estandarizado.
        """
        parsed_events: list[dict[str, Any]] = []

        if not self.api_key or self.api_key == "your_odds_api_key_here":
            logger.warning(
                "PinnacleSharpScraper: ODDS_API_KEY no está configurada en .env. Ingresa tu API Key de https://the-odds-api.com"
            )
            return parsed_events

        target_sports = sports if sports else TOP_LEAGUES

        for sport in target_sports:
            cache_key = f"pinnacle_odds_{sport}"
            cached_data = self.cache.get(cache_key)

            if cached_data is not None:
                logger.info(f"[CACHE HIT] Usando cuotas de Pinnacle en memoria/disco para '{sport}'. 0 créditos consumidos.")
                parsed_events.extend(cached_data)
                continue

            url = self.BASE_URL.format(sport=sport)
            params = {
                "apiKey": self.api_key,
                "regions": "eu",
                "markets": "totals,h2h",
                "bookmakers": "pinnacle",
                "oddsFormat": "decimal",
            }

            try:
                logger.info(f"PinnacleSharpScraper: Consultando The Odds API para '{sport}'...")
                response = self.session.get(url, params=params, timeout=10)

                # Reportar consumo de cuota mensual
                remaining = response.headers.get("x-requests-remaining")
                used = response.headers.get("x-requests-used")
                if remaining is not None:
                    logger.info(
                        f"[QUOTA] Peticiones usadas este mes: {used} | Restantes: {remaining}"
                    )

                if response.status_code != 200:
                    logger.warning(
                        f"The Odds API devolvió HTTP {response.status_code} para {sport}: {response.text[:150]}"
                    )
                    continue

                events_data = response.json()
                if not isinstance(events_data, list):
                    continue

                sport_events: list[dict[str, Any]] = []

                for event in events_data:
                    home_team = str(event.get("home_team", "")).strip()
                    away_team = str(event.get("away_team", "")).strip()

                    if not home_team or not away_team:
                        continue

                    bookmakers = event.get("bookmakers", [])
                    pinnacle_bm = None
                    for bm in bookmakers:
                        if bm.get("key") == "pinnacle":
                            pinnacle_bm = bm
                            break

                    if not pinnacle_bm:
                        continue

                    markets = pinnacle_bm.get("markets", [])

                    totals_by_line: dict[float, dict[str, float]] = {}
                    h2h_dict: dict[str, float] = {}

                    for mkt in markets:
                        mkt_key = mkt.get("key")
                        outcomes = mkt.get("outcomes", [])

                        if mkt_key == "totals":
                            for out in outcomes:
                                name = str(out.get("name", "")).lower()
                                price = out.get("price")
                                point = out.get("point")

                                if point is not None and price is not None:
                                    line_float = float(point)
                                    price_float = float(price)

                                    if line_float not in totals_by_line:
                                        totals_by_line[line_float] = {}

                                    if name == "over":
                                        totals_by_line[line_float]["over"] = price_float
                                    elif name == "under":
                                        totals_by_line[line_float]["under"] = price_float

                        elif mkt_key == "h2h":
                            for out in outcomes:
                                name = str(out.get("name", "")).strip()
                                price = out.get("price")
                                if price is not None:
                                    if name == home_team:
                                        h2h_dict["Home"] = float(price)
                                    elif name == away_team:
                                        h2h_dict["Away"] = float(price)
                                    elif name.lower() in ["draw", "empate"]:
                                        h2h_dict["Draw"] = float(price)

                    default_over = totals_by_line.get(2.5, {}).get("over")
                    default_under = totals_by_line.get(2.5, {}).get("under")

                    event_entry = {
                        "home": home_team,
                        "away": away_team,
                        "match": f"{home_team} vs. {away_team}",
                        "totals": totals_by_line,
                        "h2h": h2h_dict,
                        "btts": {},
                        # Compatibilidad hacia atrás:
                        "home_team": home_team,
                        "away_team": away_team,
                        "market": "Total 2.5",
                        "line": 2.5,
                        "over": default_over,
                        "under": default_under,
                        "over_odd": default_over,
                        "under_odd": default_under,
                    }
                    sport_events.append(event_entry)

                # Guardar en caché de disco JSON por liga
                self.cache.set(cache_key, sport_events, ttl_minutes=CACHE_TTL_MINUTES)
                parsed_events.extend(sport_events)

            except requests.exceptions.Timeout:
                logger.warning(f"Timeout al consultar The Odds API ({sport}).")
            except Exception as e:
                logger.error(f"Excepción al consultar The Odds API ({sport}): {e}")

        logger.info(
            f"PinnacleSharpScraper: Se obtuvieron {len(parsed_events)} eventos con cuotas sharp de Pinnacle."
        )
        return parsed_events
