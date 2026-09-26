from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from typing import List
from auth import usuario_actual
from schemas_generated import CamionDisponible, CamionFlota, Error
import cache
import flota_client
from flota_client import FlotaNoDisponible

router = APIRouter(prefix="/v1/camiones", tags=["Camiones"])


@router.get("", response_model=List[CamionFlota], responses={401: {"model": Error}, 503: {"model": Error}})
def listar_camiones(usuario: dict = Depends(usuario_actual)):
    # Usa ListarFlota de Flota, que envia los camiones en streaming
    try:
        return flota_client.listar_flota()
    except FlotaNoDisponible:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"codigo": "ERR_503", "mensaje": "El sistema de Flota no está disponible. Intente más tarde."}
        )


@router.get(
    "/disponibles",
    response_model=List[CamionDisponible],
    responses={401: {"model": Error}, 422: {"model": Error}, 503: {"model": Error}}
)
def buscar_camiones_disponibles(
    response: Response,
    origen: str = Query(..., min_length=1),
    destino: str = Query(..., min_length=1),
    carga_kg: float = Query(0, ge=0),
    usuario: dict = Depends(usuario_actual)
):
    # En cache se guardan todos los camiones de la ruta y aca se filtra por carga,
    # asi una sola entrada sirve para cualquier carga que se pida
    try:
        camiones = cache.obtener_disponibles(origen, destino)
        response.headers["X-Cache"] = "HIT" if camiones is not None else "MISS"
    except ConnectionError:
        camiones = None
        response.headers["X-Cache"] = "BYPASS"

    if camiones is None:
        # Despachos no guarda camiones, le pregunta a Flota que es el dueno de esos datos
        try:
            camiones = flota_client.buscar_disponibles(origen, destino)
        except FlotaNoDisponible:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={"codigo": "ERR_503", "mensaje": "El sistema de Flota no está disponible. Intente más tarde."}
            )
        if response.headers["X-Cache"] == "MISS":
            cache.guardar_disponibles(origen, destino, camiones)

    return [
        CamionDisponible(camion_id=camion_id, origen=origen, destino=destino, capacidad_disponible_kg=capacidad)
        for camion_id, capacidad in camiones
        if capacidad >= carga_kg
    ]
