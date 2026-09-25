from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from database import get_db
from auth import usuario_actual, requiere_operador
from models import DespachoModel, ClienteModel
from schemas_generated import Despacho, DespachoInput, Error
import flota_client
from flota_client import FlotaNoDisponible, CamionNoEncontrado

router = APIRouter(prefix="/v1/despachos", tags=["Despachos"])

@router.get("", response_model=List[Despacho], responses={401: {"model": Error}})
def listar_despachos(db: Session = Depends(get_db), usuario: dict = Depends(usuario_actual)):
    return db.query(DespachoModel).all()

@router.post(
    "",
    response_model=Despacho,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": Error},
        401: {"model": Error},
        403: {"model": Error},
        409: {"model": Error},
        503: {"model": Error}
    }
)
def registrar_despacho(despacho_in: DespachoInput, db: Session = Depends(get_db), usuario: dict = Depends(requiere_operador)):
    cliente = db.query(ClienteModel).filter(ClienteModel.id == despacho_in.cliente_id).first()
    if not cliente:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"codigo": "ERR_400", "mensaje": "El cliente especificado no existe."}
        )

    # Reservamos la capacidad directo en Flota, asi se verifica y se ocupa en una sola operacion
    # (Flota usa SELECT ... FOR UPDATE) y no pasa que dos despachos ocupen la misma capacidad al mismo tiempo
    try:
        respuesta = flota_client.actualizar_capacidad(despacho_in.camion_id, -despacho_in.carga_kg)
    except CamionNoEncontrado:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"codigo": "ERR_400", "mensaje": "El camión especificado no existe."}
        )
    except FlotaNoDisponible:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"codigo": "ERR_503", "mensaje": "El sistema de Flota no está disponible. Intente más tarde."}
        )

    if not respuesta.exito:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"codigo": "ERR_409", "mensaje": respuesta.mensaje_error}
        )

    nuevo_despacho = DespachoModel(
        cliente_id=despacho_in.cliente_id,
        camion_id=despacho_in.camion_id,
        carga_kg=despacho_in.carga_kg,
        estado="REGISTRADO"
    )
    try:
        db.add(nuevo_despacho)
        db.commit()
    except Exception:
        # Si falla al guardar el despacho devolvemos la capacidad que ya se habia reservado en Flota
        db.rollback()
        flota_client.actualizar_capacidad(despacho_in.camion_id, despacho_in.carga_kg)
        raise
    db.refresh(nuevo_despacho)
    return nuevo_despacho

@router.get("/{id}", response_model=Despacho, responses={401: {"model": Error}, 404: {"model": Error}})
def consultar_despacho(id: str, db: Session = Depends(get_db), usuario: dict = Depends(usuario_actual)):
    despacho = db.query(DespachoModel).filter(DespachoModel.id == id).first()
    if not despacho:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"codigo": "ERR_404", "mensaje": "Despacho no encontrado."}
        )
    return despacho

@router.delete(
    "/{id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        401: {"model": Error},
        403: {"model": Error},
        404: {"model": Error},
        409: {"model": Error},
        503: {"model": Error}
    }
)
def revertir_despacho(id: str, db: Session = Depends(get_db), usuario: dict = Depends(requiere_operador)):
    despacho = db.query(DespachoModel).filter(DespachoModel.id == id).first()
    if not despacho:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"codigo": "ERR_404", "mensaje": "Orden de despacho no encontrada."}
        )

    # Si el despacho ya estaba cancelado no hacemos nada, para no liberar la capacidad dos veces
    if despacho.estado == "CANCELADO":
        return None

    try:
        respuesta = flota_client.actualizar_capacidad(despacho.camion_id, despacho.carga_kg)
    except (FlotaNoDisponible, CamionNoEncontrado):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"codigo": "ERR_503", "mensaje": "El sistema de Flota no está disponible. Intente más tarde."}
        )

    if not respuesta.exito:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"codigo": "ERR_409", "mensaje": respuesta.mensaje_error}
        )

    # No borramos el despacho, solo lo marcamos como CANCELADO para que quede el historial
    despacho.estado = "CANCELADO"
    try:
        db.commit()
    except Exception:
        # Si falla al marcarlo como cancelado volvemos a ocupar la capacidad que se libero
        db.rollback()
        flota_client.actualizar_capacidad(despacho.camion_id, -despacho.carga_kg)
        raise
    return None
