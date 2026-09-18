import re
from typing import Any
from thefuzz import fuzz


def clean_team_name(name: str) -> str:
    """
    Limpia y estandariza el nombre de un equipo eliminando sufijos y prefijos comunes
    (FC, CF, Club, CD, UANL, Deportivo, Atletico, Real, etc.), puntuación y acentos.

    Args:
        name (str): Nombre original del equipo.

    Returns:
        str: Nombre limpio y estandarizado.
    """
    if not name:
        return ""

    cleaned = name.lower().strip()

    # Reemplazo de caracteres con acentos
    replacements = {
        "á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u", "ü": "u", "ñ": "n"
    }
    for orig, rep in replacements.items():
        cleaned = cleaned.replace(orig, rep)

    # Eliminar prefijos/sufijos comunes
    patterns = [
        r"\b(fc|cf|cd|sc|ac|sv|rb|club|deportivo|atletico|real|sporting|uanl)\b",
        r"[^\w\s]",
    ]
    for pattern in patterns:
        cleaned = re.sub(pattern, " ", cleaned)

    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def match_team_names(name_a: str, name_b: str, threshold: int = 75) -> bool:
    """
    Compara dos nombres de equipos utilizando token_set_ratio para manejar variaciones en orden
    y sufijos (ej. 'FC Juarez' vs 'Juarez', 'Tigres UANL' vs 'Tigres').

    Args:
        name_a (str): Nombre del primer equipo.
        name_b (str): Nombre del segundo equipo.
        threshold (int): Umbral de similitud (0-100). Por defecto 75.

    Returns:
        bool: True si la similitud >= threshold, False en caso contrario.
    """
    clean_a = clean_team_name(name_a)
    clean_b = clean_team_name(name_b)

    if not clean_a or not clean_b:
        return False

    ratio = fuzz.token_set_ratio(clean_a, clean_b)
    return ratio >= threshold


def match_teams(
    team_a_playdoit: str, team_b_playdoit: str, events_sharp: list[dict[str, Any]], threshold: int = 75
) -> dict[str, Any] | None:
    """
    Busca y empareja un partido de Playdoit (local y visitante) contra una lista de eventos sharp.
    Utiliza token_set_ratio con umbral >= 75%.

    Args:
        team_a_playdoit (str): Nombre del equipo local en Playdoit.
        team_b_playdoit (str): Nombre del equipo visitante en Playdoit.
        events_sharp (list[dict[str, Any]]): Lista de eventos sharp.
        threshold (int): Umbral mínimo de coincidencia (por defecto 75).

    Returns:
        dict[str, Any] | None: El evento coincidente o None si no se encuentra match.
    """
    clean_home_playdoit = clean_team_name(team_a_playdoit)
    clean_away_playdoit = clean_team_name(team_b_playdoit)

    if not clean_home_playdoit or not clean_away_playdoit:
        return None

    best_match = None
    best_score = 0

    for sharp_event in events_sharp:
        sharp_home_raw = sharp_event.get("home") or sharp_event.get("home_team") or ""
        sharp_away_raw = sharp_event.get("away") or sharp_event.get("away_team") or ""

        sharp_home = clean_team_name(str(sharp_home_raw))
        sharp_away = clean_team_name(str(sharp_away_raw))

        if not sharp_home or not sharp_away:
            continue

        score_home = fuzz.token_set_ratio(clean_home_playdoit, sharp_home)
        score_away = fuzz.token_set_ratio(clean_away_playdoit, sharp_away)

        if score_home >= threshold and score_away >= threshold:
            avg_score = (score_home + score_away) / 2.0
            if avg_score > best_score:
                best_score = avg_score
                best_match = sharp_event

    return best_match
