import logging
from typing import Any
from curl_cffi import requests

from config.settings import SPORT_ID
from scrapers.base import BaseScraper

logger = logging.getLogger(__name__)


class PlaydoitScraper(BaseScraper):
    """
    Scraper oficial para Playdoit a través de la API backend de Altenar (sb2frontend).
    Extrae exclusivamente mercados de tiempo regular (90 min) para 1X2, Total Goals (línea 2.5) y Both Teams to Score.
    """

    BASE_URL = "https://sb2frontend-altenar2.biahosted.com/api/Sportsbook"

    def __init__(self, sport_id: int = SPORT_ID) -> None:
        self.sport_id = sport_id
        self.session = requests.Session(impersonate="chrome120")
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                "Origin": "https://www.playdoit.mx",
                "Referer": "https://www.playdoit.mx/",
            }
        )

    def get_top_events(self) -> list[dict[str, Any]]:
        """
        Obtiene los eventos principales de fútbol en Playdoit/Altenar.

        Returns:
            list[dict[str, Any]]: Lista de eventos [{'event_id': int, 'name': str, 'start_date': str}]
        """
        url = f"{self.BASE_URL}/GetTopEvents"
        params = {
            "culture": "es-MX",
            "integration": "playdoit2",
            "deviceType": 1,
            "sportId": self.sport_id,
            "numItems": 50,
        }

        try:
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            events: list[dict[str, Any]] = []
            result = data.get("Result", {}) if isinstance(data, dict) else {}
            raw_events = result.get("Events", []) if isinstance(result, dict) else []

            for item in raw_events:
                if not isinstance(item, dict):
                    continue

                event_id = item.get("Id") or item.get("id")
                name = item.get("Name") or item.get("name")
                start_date = item.get("EventDate") or item.get("StartDate") or ""

                if event_id and name:
                    events.append(
                        {
                            "event_id": int(event_id),
                            "name": str(name).strip(),
                            "start_date": str(start_date),
                        }
                    )

            logger.info(f"PlaydoitScraper: Se obtuvieron {len(events)} eventos principales.")
            return events

        except Exception as e:
            logger.error(f"Error al obtener eventos principales de Playdoit: {e}")
            return []

    def get_event_odds(self, event_id: int) -> list[dict[str, Any]]:
        """
        Obtiene cuotas de 1X2, Total Goals (exclusivamente línea 2.5) y Both Teams to Score.

        Args:
            event_id (int): ID del evento en Altenar.

        Returns:
            list[dict[str, Any]]: Lista estandarizada de selecciones:
                [{'market': '1X2'|'Total Goals'|'Both Teams to Score',
                  'selection': 'Home'|'Draw'|'Away'|'Over'|'Under'|'Yes'|'No',
                  'line': 2.5 | None,
                  'odd': float}]
        """
        url = f"{self.BASE_URL}/GetEventDetails"
        params = {
            "culture": "es-MX",
            "integration": "playdoit2",
            "eventId": event_id,
            "deviceType": 1,
        }

        odds_list: list[dict[str, Any]] = []

        try:
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            result = data.get("Result", {}) if isinstance(data, dict) else {}
            if not isinstance(result, dict):
                return odds_list

            market_groups = result.get("MarketGroups", [])
            seen_combos = set()

            for group in market_groups:
                if not isinstance(group, dict):
                    continue

                items = group.get("Items", [])
                for item in items:
                    if not isinstance(item, dict):
                        continue

                    mkt_name = str(item.get("Name") or item.get("name") or "").strip()
                    mkt_name_lower = mkt_name.lower()
                    org_type = item.get("OrgMarketTypeId") or item.get("MarketTypeId")

                    # Excluir tiempo parcial (1st half, 2nd half, tiros de esquina, tarjetas)
                    if any(bad in mkt_name_lower for bad in ["1st half", "2nd half", "1er tiempo", "2do tiempo", "corner", "card", "booking", "tarjeta", "tiro de esquina"]):
                        continue

                    target_market = None
                    if mkt_name_lower in ["1x2", "match result", "ganador del partido", "resultado del partido"] or org_type in [1, "1_"]:
                        target_market = "1X2"
                    elif mkt_name_lower in ["total", "total goals", "goles totales"] or org_type in [18, "18_"]:
                        target_market = "Total Goals"
                    elif mkt_name_lower in ["both teams to score", "ambos anotan", "ambos equipos anotarán", "ambos equipos anotaran"] or org_type in [29, "29_"]:
                        target_market = "Both Teams to Score"

                    if not target_market:
                        continue

                    selections = item.get("Items", [])
                    for sel in selections:
                        if not isinstance(sel, dict):
                            continue

                        raw_sel_name = str(sel.get("Name") or sel.get("name") or "").strip()
                        price_val = sel.get("Price") or sel.get("price") or sel.get("PriceDecimal")

                        if price_val is None:
                            continue

                        try:
                            float_odd = float(price_val)
                            if float_odd <= 1.0:
                                continue
                        except (ValueError, TypeError):
                            continue

                        norm_selection = None
                        line_val = None

                        if target_market == "1X2":
                            sel_type = sel.get("SelectionTypeId")
                            if sel_type == 1 or "1" in raw_sel_name or "home" in raw_sel_name.lower():
                                norm_selection = "Home"
                            elif sel_type == 2 or "draw" in raw_sel_name.lower() or "empate" in raw_sel_name.lower() or "x" in raw_sel_name.lower():
                                norm_selection = "Draw"
                            elif sel_type == 3 or "2" in raw_sel_name or "away" in raw_sel_name.lower():
                                norm_selection = "Away"
                            else:
                                col = sel.get("ColumnNum") or sel.get("MobileColumnNum")
                                if col == 1:
                                    norm_selection = "Home"
                                elif col == 2:
                                    norm_selection = "Draw"
                                elif col == 3:
                                    norm_selection = "Away"

                        elif target_market == "Total Goals":
                            parts = raw_sel_name.split()
                            extracted_line = None
                            if parts:
                                try:
                                    extracted_line = float(parts[-1])
                                except ValueError:
                                    extracted_line = None

                            # EXCLUSIVAMENTE línea 2.5
                            if extracted_line != 2.5:
                                continue

                            line_val = 2.5
                            if raw_sel_name.lower().startswith("over") or "mas de" in raw_sel_name.lower() or "más de" in raw_sel_name.lower():
                                norm_selection = "Over"
                            elif raw_sel_name.lower().startswith("under") or "menos de" in raw_sel_name.lower():
                                norm_selection = "Under"

                        elif target_market == "Both Teams to Score":
                            if raw_sel_name.lower() in ["yes", "si", "sí"]:
                                norm_selection = "Yes"
                            elif raw_sel_name.lower() in ["no"]:
                                norm_selection = "No"

                        if not norm_selection:
                            continue

                        combo_key = (target_market, norm_selection, line_val, float_odd)
                        if combo_key not in seen_combos:
                            seen_combos.add(combo_key)
                            odds_list.append(
                                {
                                    "market": target_market,
                                    "selection": norm_selection,
                                    "line": line_val,
                                    "odd": float_odd,
                                }
                            )

            return odds_list

        except Exception as e:
            logger.error(f"Error al obtener cuotas del evento {event_id} en Playdoit: {e}")
            return []
