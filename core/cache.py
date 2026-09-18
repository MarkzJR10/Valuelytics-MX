import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from config.settings import CACHE_TTL_MINUTES

logger = logging.getLogger(__name__)


class OddsCache:
    """
    Sistema de caché persistente en disco JSON con TTL (30 minutos por defecto)
    para almacenar las cuotas sharp de Pinnacle de The Odds API y proteger la cuota de peticiones.
    """

    def __init__(self, default_ttl_minutes: int = CACHE_TTL_MINUTES) -> None:
        self.default_ttl = timedelta(minutes=default_ttl_minutes)
        self.cache_dir = Path(__file__).resolve().parent.parent / "data"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._memory_store: dict[str, tuple[Any, datetime]] = {}

    def _get_file_path(self, key: str) -> Path:
        safe_key = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in key)
        return self.cache_dir / f"cache_{safe_key}.json"

    def get(self, key: str) -> Any | None:
        """
        Obtiene datos del caché (en memoria o desde el disco JSON) si no han expirado (<30 min).

        Args:
            key (str): Clave del elemento.

        Returns:
            Any | None: Datos almacenados o None si expiró o no existe.
        """
        now = datetime.now()

        # 1. Verificar primero almacenamiento en memoria
        if key in self._memory_store:
            val, expiry = self._memory_store[key]
            if now < expiry:
                return val
            else:
                del self._memory_store[key]

        # 2. Verificar almacenamiento persistente en disco JSON
        file_path = self._get_file_path(key)
        if file_path.exists():
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    payload = json.load(f)

                timestamp_str = payload.get("timestamp")
                if timestamp_str:
                    saved_time = datetime.fromisoformat(timestamp_str)
                    if now - saved_time < self.default_ttl:
                        data = payload.get("data")
                        # Guardar en memoria para acceso ultrarrápido
                        self._memory_store[key] = (data, saved_time + self.default_ttl)
                        return data
                    else:
                        logger.debug(f"Caché en disco expirado para {key}")
            except Exception as e:
                logger.warning(f"Error al leer caché en disco ({file_path}): {e}")

        return None

    def set(self, key: str, value: Any, ttl_minutes: int | None = None) -> None:
        """
        Almacena datos en el caché en memoria y en disco JSON local.

        Args:
            key (str): Clave del elemento.
            value (Any): Datos a almacenar.
            ttl_minutes (int | None): TTL en minutos. Si es None, usa CACHE_TTL_MINUTES (30 min).
        """
        ttl = timedelta(minutes=ttl_minutes) if ttl_minutes is not None else self.default_ttl
        now = datetime.now()

        # Guardar en memoria
        self._memory_store[key] = (value, now + ttl)

        # Guardar en disco JSON
        file_path = self._get_file_path(key)
        payload = {
            "timestamp": now.isoformat(),
            "data": value,
        }
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Error al escribir caché en disco ({file_path}): {e}")

    def clear(self) -> None:
        """
        Limpia el almacenamiento en memoria y borra los archivos JSON de caché.
        """
        self._memory_store.clear()
        for f in self.cache_dir.glob("cache_*.json"):
            try:
                f.unlink()
            except Exception:
                pass
