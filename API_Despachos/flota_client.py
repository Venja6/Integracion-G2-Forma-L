import os
import logging
import grpc
import flota_pb2
import flota_pb2_grpc

GRPC_FLOTA_HOST = os.getenv("GRPC_FLOTA_HOST", "localhost:50051")
# Tiempo maximo que esperamos a Flota, si no ponemos esto y Flota se pone lenta la API se queda pegada
GRPC_TIMEOUT_SEGUNDOS = float(os.getenv("GRPC_FLOTA_TIMEOUT", "2"))

# Creamos el canal una sola vez y lo reusamos, HTTP/2 permite mandar varias llamadas por el mismo canal
_canal = grpc.insecure_channel(GRPC_FLOTA_HOST)
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


def actualizar_capacidad(camion_id: str, variacion_kg: float):
    """Con un valor negativo se ocupa capacidad y con uno positivo se libera"""
    try:
        return _stub.ActualizarCapacidad(
            flota_pb2.ActualizarCapacidadRequest(camion_id=camion_id, variacion_kg=variacion_kg),
            timeout=GRPC_TIMEOUT_SEGUNDOS,
        )
    except grpc.RpcError as e:
        raise _traducir_error(e) from e
