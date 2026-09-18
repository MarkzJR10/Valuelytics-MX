"""
Módulo de scrapers para casas de apuestas deportivas.
"""

from scrapers.base import BaseScraper
from scrapers.pinnacle_sharp import PinnacleSharpScraper
from scrapers.playdoit import PlaydoitScraper

__all__ = ["BaseScraper", "PlaydoitScraper", "PinnacleSharpScraper"]
