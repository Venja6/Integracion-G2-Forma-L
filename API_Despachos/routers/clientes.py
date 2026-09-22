from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from database import get_db
from models import ClienteModel
from schemas_generated import Cliente, ClienteInput, Error

router = APIRouter(prefix="/v1/clientes", tags=["Clientes"])

@router.get("", response_model=List[Cliente])
def listar_clientes(db: Session = Depends(get_db)):
    return db.query(ClienteModel).all()

@router.post("", response_model=Cliente, status_code=status.HTTP_201_CREATED, responses={400: {"model": Error}})
def crear_cliente(cliente_in: ClienteInput, db: Session = Depends(get_db)):
    cliente_existente = db.query(ClienteModel).filter(ClienteModel.email == cliente_in.email).first()
    if cliente_existente:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"codigo": "ERR_400", "mensaje": "El email ya se encuentra registrado."}
        )
    
    nuevo_cliente = ClienteModel(nombre=cliente_in.nombre, email=cliente_in.email)
    db.add(nuevo_cliente)
    db.commit()
    db.refresh(nuevo_cliente)
    return nuevo_cliente

@router.get("/{id}", response_model=Cliente, responses={404: {"model": Error}})
def consultar_cliente(id: str, db: Session = Depends(get_db)):
    cliente = db.query(ClienteModel).filter(ClienteModel.id == id).first()
    if not cliente:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"codigo": "ERR_404", "mensaje": "Cliente no encontrado."}
        )
    return cliente