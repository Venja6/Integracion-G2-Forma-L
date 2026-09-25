from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import List
from auth import usuario_actual
from schemas_generated import CamionDisponible, Error
import flota_client
from flota_client import FlotaNoDisponible

router = APIRouter(prefix="/v1/camiones", tags=["Camiones"])


@router.get(
    "/disponibles",
    response_model=List[CamionDisponible],
    responses={401: {"model": Error}, 422: {"model": Error}, 503: {"model": Error}}
)
def buscar_camiones_disponibles(
    origen: str = Query(..., min_length=1),
    destino: str = Query(..., min_length=1),
    carga_kg: float = Query(0, ge=0),
    usuario: dict = Depends(usuario_actual)
):
    # Despachos no guarda camiones, le pregunta a Flota que es el dueno de esos datos
    try:
        camiones = flota_client.buscar_disponibles(origen, destino, carga_kg)
    except FlotaNoDisponible:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"codigo": "ERR_503", "mensaje": "El sistema de Flota no está disponible. Intente más tarde."}
        )
    return [
        CamionDisponible(camion_id=camion_id, origen=origen, destino=destino, capacidad_disponible_kg=capacidad)
        for camion_id, capacidad in camiones
    ]
