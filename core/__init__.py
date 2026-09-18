"""
Módulo core de procesamiento matemático, caché y normalización para valuelytics-mx.
"""

from core.cache import OddsCache
from core.normalizer import clean_team_name, match_team_names, match_teams
from core.value_engine import (
    calculate_ev,
    is_value_bet,
    remove_vig_two_way,
)

__all__ = [
    "OddsCache",
    "clean_team_name",
    "match_team_names",
    "match_teams",
    "remove_vig_two_way",
    "calculate_ev",
    "is_value_bet",
]
