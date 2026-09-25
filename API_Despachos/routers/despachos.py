import hashlib
import json
import logging
from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from typing import List, Optional
from database import get_db
from auth import usuario_actual, requiere_operador
from models import DespachoModel, ClienteModel
from schemas_generated import Despacho, DespachoInput, Error
import flota_client
from flota_client import FlotaNoDisponible, CamionNoEncontrado

router = APIRouter(prefix="/v1/despachos", tags=["Despachos"])
logger = logging.getLogger("uvicorn.error")

ERROR_FLOTA_NO_DISPONIBLE = {"codigo": "ERR_503", "mensaje": "El sistema de Flota no está disponible. Intente más tarde."}


def _representar(despacho: DespachoModel) -> dict:
    # HATEOAS, los enlaces le dicen al cliente que puede hacer con el despacho segun su estado
    enlaces = {
        "self": {"href": f"/v1/despachos/{despacho.id}", "method": "GET"},
        "cliente": {"href": f"/v1/clientes/{despacho.cliente_id}", "method": "GET"},
    }
    if despacho.estado == "REGISTRADO":
        enlaces["revertir"] = {"href": f"/v1/despachos/{despacho.id}", "method": "DELETE"}
    return {
        "id": despacho.id,
        "cliente_id": despacho.cliente_id,
        "camion_id": despacho.camion_id,
        "origen": despacho.origen,
        "destino": despacho.destino,
        "carga_kg": despacho.carga_kg,
        "estado": despacho.estado,
        "_links": enlaces,
    }


def _hash_solicitud(despacho_in: DespachoInput) -> str:
    # Sirve para detectar si reusan la misma Idempotency-Key pero con otros datos
    datos = json.dumps(despacho_in.model_dump(mode="json"), sort_keys=True)
    return hashlib.sha256(datos.encode()).hexdigest()


def _compensar(camion_id: str, origen: str, destino: str, variacion_kg: float):
    # Si la compensacion tambien falla no queremos tapar el error original, solo lo dejamos en el log
    try:
        flota_client.actualizar_capacidad(camion_id, origen, destino, variacion_kg)
    except Exception as e:
        logger.error(
            "No se pudo compensar en Flota (camion %s, %s - %s, %s kg), revisar a mano: %s",
            camion_id, origen, destino, variacion_kg, e
        )


def _repetir_respuesta(existente: DespachoModel, hash_solicitud: str, response: Response) -> dict:
    if existente.request_hash != hash_solicitud:
        raise HTTPException(
            status_code=422,
            detail={"codigo": "ERR_422", "mensaje": "La Idempotency-Key ya se usó con datos distintos."}
        )
    response.headers["Idempotent-Replayed"] = "true"
    return _representar(existente)


@router.get("", response_model=List[Despacho], responses={401: {"model": Error}})
def listar_despachos(db: Session = Depends(get_db), usuario: dict = Depends(usuario_actual)):
    return [_representar(d) for d in db.query(DespachoModel).all()]

@router.post(
    "",
    response_model=Despacho,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": Error},
        401: {"model": Error},
        403: {"model": Error},
        409: {"model": Error},
        422: {"model": Error},
        503: {"model": Error}
    }
)
def registrar_despacho(
    despacho_in: DespachoInput,
    response: Response,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key", max_length=255),
    db: Session = Depends(get_db),
    usuario: dict = Depends(requiere_operador)
):
    hash_solicitud = _hash_solicitud(despacho_in)

    # Si ya se proceso esta misma key devolvemos el despacho que se creo, sin volver a reservar en Flota
    if idempotency_key:
        existente = db.query(DespachoModel).filter(DespachoModel.idempotency_key == idempotency_key).first()
        if existente:
            return _repetir_respuesta(existente, hash_solicitud, response)

    cliente = db.query(ClienteModel).filter(ClienteModel.id == despacho_in.cliente_id).first()
    if not cliente:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"codigo": "ERR_400", "mensaje": "El cliente especificado no existe."}
        )

    # Reservamos la capacidad directo en Flota, asi se verifica y se ocupa en una sola operacion
    # (Flota usa SELECT ... FOR UPDATE) y no pasa que dos despachos ocupen la misma capacidad al mismo tiempo
    try:
        respuesta = flota_client.actualizar_capacidad(
            despacho_in.camion_id, despacho_in.origen, despacho_in.destino, -despacho_in.carga_kg
        )
    except CamionNoEncontrado:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"codigo": "ERR_400", "mensaje": "El camión no existe o no opera la ruta indicada."}
        )
    except FlotaNoDisponible:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=ERROR_FLOTA_NO_DISPONIBLE)

    if not respuesta.exito:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"codigo": "ERR_409", "mensaje": respuesta.mensaje_error}
        )

    nuevo_despacho = DespachoModel(
        cliente_id=despacho_in.cliente_id,
        camion_id=despacho_in.camion_id,
        origen=despacho_in.origen,
        destino=despacho_in.destino,
        carga_kg=despacho_in.carga_kg,
        estado="REGISTRADO",
        idempotency_key=idempotency_key,
        request_hash=hash_solicitud
    )
    try:
        db.add(nuevo_despacho)
        db.commit()
    except Exception as e:
        # Si falla al guardar el despacho devolvemos la capacidad que ya se habia reservado en Flota
        db.rollback()
        _compensar(despacho_in.camion_id, despacho_in.origen, despacho_in.destino, despacho_in.carga_kg)
        # Dos reintentos con la misma key al mismo tiempo, el segundo choca con el unique y devuelve el del primero
        if isinstance(e, IntegrityError) and idempotency_key:
            existente = db.query(DespachoModel).filter(DespachoModel.idempotency_key == idempotency_key).first()
            if existente:
                return _repetir_respuesta(existente, hash_solicitud, response)
        raise
    db.refresh(nuevo_despacho)
    return _representar(nuevo_despacho)

@router.get("/{id}", response_model=Despacho, responses={401: {"model": Error}, 404: {"model": Error}})
def consultar_despacho(id: str, db: Session = Depends(get_db), usuario: dict = Depends(usuario_actual)):
    despacho = db.query(DespachoModel).filter(DespachoModel.id == id).first()
    if not despacho:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"codigo": "ERR_404", "mensaje": "Despacho no encontrado."}
        )
    return _representar(despacho)

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
        respuesta = flota_client.actualizar_capacidad(
            despacho.camion_id, despacho.origen, despacho.destino, despacho.carga_kg
        )
    except (FlotaNoDisponible, CamionNoEncontrado):
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=ERROR_FLOTA_NO_DISPONIBLE)

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
        _compensar(despacho.camion_id, despacho.origen, despacho.destino, -despacho.carga_kg)
        raise
    return None
