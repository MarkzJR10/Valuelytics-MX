from abc import ABC, abstractmethod
from typing import Any


class BaseScraper(ABC):
    """
    Clase base abstracta para la implementación de scrapers de casas de apuestas.
    Garantiza el tipado estricto y la consistencia en la recolección de eventos y cuotas.
    """

    @abstractmethod
    def get_top_events(self) -> list[dict[str, Any]]:
        """
        Obtiene los principales eventos deportivos disponibles.

        Returns:
            list[dict[str, Any]]: Lista de eventos estandarizados con estructura:
                [{'event_id': int, 'name': str, 'start_date': str}]
        """
        pass

    @abstractmethod
    def get_event_odds(self, event_id: int) -> list[dict[str, Any]]:
        """
        Obtiene las cuotas para un evento específico.

        Args:
            event_id (int): Identificador del evento en la casa de apuestas.

        Returns:
            list[dict[str, Any]]: Lista de selecciones de mercado estandarizadas con estructura:
                [{'market': str, 'selection': str, 'odd': float, 'line': float | None}]
        """
        pass
