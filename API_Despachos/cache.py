import json
import logging
import os
import time

import redis

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
TTL_SEGUNDOS = int(os.getenv("CACHE_TTL_SEGUNDOS", "30"))
# Despues de una falla no se vuelve a intentar Redis por este tiempo. Si esta caido, cada intento
# puede tardar segundos (por ejemplo resolviendo el DNS) y eso haria mas lenta a toda la API
PAUSA_TRAS_FALLA_SEGUNDOS = 10

logger = logging.getLogger("uvicorn.error")

# Timeouts cortos a proposito, si Redis falla preferimos ir directo a Flota antes que dejar esperando al cliente
_cliente = redis.Redis.from_url(REDIS_URL, socket_connect_timeout=0.2, socket_timeout=0.2)


_pausado_hasta = 0.0


def _disponible() -> bool:
    return time.monotonic() >= _pausado_hasta


def _marcar_falla(operacion: str, error: Exception):
    global _pausado_hasta
    _pausado_hasta = time.monotonic() + PAUSA_TRAS_FALLA_SEGUNDOS
    logger.warning("Redis no disponible al %s, se omite la cache por %s s: %s", operacion, PAUSA_TRAS_FALLA_SEGUNDOS, error)


def _clave(origen: str, destino: str) -> str:
    return f"disponibles:{origen.strip().lower()}|{destino.strip().lower()}"


def obtener_disponibles(origen: str, destino: str):
    """Devuelve la lista guardada para la ruta, None si no esta, o lanza ConnectionError si Redis no responde"""
    if not _disponible():
        raise ConnectionError("cache en pausa")
    try:
        valor = _cliente.get(_clave(origen, destino))
    except redis.RedisError as e:
        _marcar_falla("leer", e)
        raise ConnectionError from e
    return json.loads(valor) if valor else None


def guardar_disponibles(origen: str, destino: str, camiones):
    if not _disponible():
        return
    try:
        _cliente.set(_clave(origen, destino), json.dumps(camiones), ex=TTL_SEGUNDOS)
    except redis.RedisError as e:
        _marcar_falla("guardar", e)


def invalidar_ruta(origen: str, destino: str):
    # Se llama cada vez que cambia la capacidad de la ruta, asi la cache no muestra datos viejos.
    # Si Redis esta caido no se puede borrar, pero el TTL igual hace que el dato expire solo
    if not _disponible():
        return
    try:
        _cliente.delete(_clave(origen, destino))
    except redis.RedisError as e:
        _marcar_falla("invalidar", e)
