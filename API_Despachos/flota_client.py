import os
import logging
import grpc
import flota_pb2
import flota_pb2_grpc

GRPC_FLOTA_HOST = os.getenv("GRPC_FLOTA_HOST", "localhost:50051")
# Tiempo máximo de espera por llamada a Flota. Sin él, una Flota lenta bloquearía a la API indefinidamente.
GRPC_TIMEOUT_SEGUNDOS = float(os.getenv("GRPC_FLOTA_TIMEOUT", "2"))

# El canal se crea una sola vez y se reutiliza: HTTP/2 multiplexa todas las llamadas sobre él
_canal = grpc.insecure_channel(GRPC_FLOTA_HOST)
_stub = flota_pb2_grpc.ServicioFlotaStub(_canal)


class FlotaNoDisponible(Exception):
    """Flota no respondió a tiempo o está caída."""


class CamionNoEncontrado(Exception):
    """Flota no conoce el camión solicitado."""


logger = logging.getLogger("uvicorn.error")


def _traducir_error(e: grpc.RpcError):
    logger.warning("Llamada a Flota falló: %s %s", e.code().name, e.details())
    if e.code() == grpc.StatusCode.NOT_FOUND:
        return CamionNoEncontrado(e.details())
    return FlotaNoDisponible(f"{e.code().name}: {e.details()}")


def actualizar_capacidad(camion_id: str, variacion_kg: float):
    """Negativo ocupa capacidad, positivo la libera. Retorna ActualizarCapacidadResponse."""
    try:
        return _stub.ActualizarCapacidad(
            flota_pb2.ActualizarCapacidadRequest(camion_id=camion_id, variacion_kg=variacion_kg),
            timeout=GRPC_TIMEOUT_SEGUNDOS,
        )
    except grpc.RpcError as e:
        raise _traducir_error(e) from e
