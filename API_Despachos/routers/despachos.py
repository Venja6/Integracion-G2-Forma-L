from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from database import get_db
from models import DespachoModel, ClienteModel
from schemas_generated import Despacho, DespachoInput, Error

router = APIRouter(prefix="/v1/despachos", tags=["Despachos"])

@router.get("", response_model=List[Despacho])
def listar_despachos(db: Session = Depends(get_db)):
    return db.query(DespachoModel).all()

@router.post(
    "",
    response_model=Despacho,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": Error},
        409: {"model": Error},
        503: {"model": Error}
    }
)
def registrar_despacho(despacho_in: DespachoInput, db: Session = Depends(get_db)):
    cliente = db.query(ClienteModel).filter(ClienteModel.id == despacho_in.cliente_id).first()
    if not cliente:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"codigo": "ERR_400", "mensaje": "El cliente especificado no existe."}
        )

    # MOCK de disponibilidad en Flota
    capacidad_disponible_mock = True

    if not capacidad_disponible_mock:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"codigo": "ERR_409", "mensaje": "Conflicto. No hay capacidad de carga disponible en el camión."}
        )

    nuevo_despacho = DespachoModel(
        cliente_id=despacho_in.cliente_id,
        camion_id=despacho_in.camion_id,
        carga_kg=despacho_in.carga_kg,
        estado="REGISTRADO"
    )
    db.add(nuevo_despacho)
    db.commit()
    db.refresh(nuevo_despacho)
    return nuevo_despacho

@router.get("/{id}", response_model=Despacho, responses={404: {"model": Error}})
def consultar_despacho(id: str, db: Session = Depends(get_db)):
    despacho = db.query(DespachoModel).filter(DespachoModel.id == id).first()
    if not despacho:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"codigo": "ERR_404", "mensaje": "Despacho no encontrado."}
        )
    return despacho

@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT, responses={404: {"model": Error}})
def revertir_despacho(id: str, db: Session = Depends(get_db)):
    despacho = db.query(DespachoModel).filter(DespachoModel.id == id).first()
    if not despacho:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"codigo": "ERR_404", "mensaje": "Orden de despacho no encontrada."}
        )
    
    db.delete(despacho)
    db.commit()
    return None