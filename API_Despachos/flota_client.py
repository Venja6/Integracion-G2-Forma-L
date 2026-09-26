import os
import logging
import grpc
import flota_pb2
import flota_pb2_grpc
import cache

GRPC_FLOTA_HOST = os.getenv("GRPC_FLOTA_HOST", "localhost:50051")
# Tiempo maximo que esperamos a Flota, si no ponemos esto y Flota se pone lenta la API se queda pegada
GRPC_TIMEOUT_SEGUNDOS = float(os.getenv("GRPC_FLOTA_TIMEOUT", "2"))

# Creamos el canal una sola vez y lo reusamos, HTTP/2 permite mandar varias llamadas por el mismo canal.
# Por defecto gRPC espera cada vez mas entre intentos de reconexion (hasta 120 s), entonces despues de una caida
# larga la API seguiria dando 503 aunque Flota ya haya vuelto. Con esto reintenta como maximo cada 2 s
_canal = grpc.insecure_channel(
    GRPC_FLOTA_HOST,
    options=[
        ("grpc.initial_reconnect_backoff_ms", 500),
        ("grpc.max_reconnect_backoff_ms", 2000),
    ],
)
_stub = flota_pb2_grpc.ServicioFlotaStub(_canal)


class FlotaNoDisponible(Exception):
    """Flota no respondio a tiempo o esta caida"""


class CamionNoEncontrado(Exception):
    """Flota no tiene el camion que se pidio"""


logger = logging.getLogger("uvicorn.error")


def _traducir_error(e: grpc.RpcError):
    logger.warning("Llamada a Flota falló: %s %s", e.code().name, e.details())
    if e.code() == grpc.StatusCode.NOT_FOUND:
        return CamionNoEncontrado(e.details())
    return FlotaNoDisponible(f"{e.code().name}: {e.details()}")


def actualizar_capacidad(camion_id: str, origen: str, destino: str, variacion_kg: float):
    """Con un valor negativo se ocupa capacidad y con uno positivo se libera"""
    try:
        return _stub.ActualizarCapacidad(
            flota_pb2.ActualizarCapacidadRequest(
                camion_id=camion_id, origen=origen, destino=destino, variacion_kg=variacion_kg
            ),
            timeout=GRPC_TIMEOUT_SEGUNDOS,
        )
    except grpc.RpcError as e:
        raise _traducir_error(e) from e
    finally:
        # Se invalida siempre, incluso si hubo error, porque con un timeout no sabemos si Flota alcanzo a aplicar el cambio
        cache.invalidar_ruta(origen, destino)


def buscar_disponibles(origen: str, destino: str, carga_minima_kg: float = 0.0):
    """Devuelve una lista de (camion_id, capacidad_disponible_kg) para la ruta"""
    try:
        respuesta = _stub.BuscarDisponibles(
            flota_pb2.BuscarDisponiblesRequest(origen=origen, destino=destino, carga_minima_kg=carga_minima_kg),
            timeout=GRPC_TIMEOUT_SEGUNDOS,
        )
    except grpc.RpcError as e:
        raise _traducir_error(e) from e
    return [(c.camion_id, c.capacidad_disponible_kg) for c in respuesta.camiones]


def listar_flota():
    """ListarFlota es server streaming, se recorre el stream y se arma la lista camion por camion"""
    try:
        return [
            {
                "camion_id": c.camion_id,
                "rutas": [
                    {"origen": r.origen, "destino": r.destino,
                     "capacidad_total_kg": r.capacidad_total_kg, "capacidad_disponible_kg": r.capacidad_disponible_kg}
                    for r in c.rutas
                ],
            }
            for c in _stub.ListarFlota(flota_pb2.ListarFlotaRequest(), timeout=GRPC_TIMEOUT_SEGUNDOS)
        ]
    except grpc.RpcError as e:
        raise _traducir_error(e) from e
