import os
from sqlalchemy import create_engine, String, Float, ForeignKey
from sqlalchemy.orm import sessionmaker, DeclarativeBase, Mapped, mapped_column, relationship
from typing import List

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg2://flota_user:flotapassword@localhost:5433/flota_db")

engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Base(DeclarativeBase):
    pass

class Camion(Base):
    __tablename__="camiones"

    camion_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    capacidad_total_kg: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    capacidad_disponible_kg: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    rutas: Mapped[List["RutaCamion"]] = relationship(
        back_populates="camion",
        cascade="all, delete-orphan",
        lazy="joined"
    )

class RutaCamion(Base):
    __tablename__="rutas_camion"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    camion_id: Mapped[str] = mapped_column(ForeignKey("camiones.camion_id", ondelete="CASCADE"))
    nombre_ruta: Mapped[str] = mapped_column(String(100), nullable=False)

    camion: Mapped["Camion"] = relationship(back_populates="rutas")


CAMIONES_INICIALES = [
    ("CAM-01", 10000.0, ["Concepcion - Santiago"]),
    ("CAM-02", 8000.0, ["Concepcion - Temuco", "Temuco - Puerto Montt"]),
    ("CAM-03", 12000.0, ["Santiago - Valparaiso"]),
    ("CAM-04", 5000.0, ["Concepcion - Chillan"]),
    ("CAM-05", 3000.0, ["Los Angeles - Concepcion"]),
]

def init_db():
    Base.metadata.create_all(bind=engine)
    seed_db()

def seed_db():
    # Solo inserta la flota inicial si la tabla está vacía (idempotente entre reinicios)
    with SessionLocal() as db:
        if db.query(Camion).first() is not None:
            return
        for camion_id, capacidad, rutas in CAMIONES_INICIALES:
            db.add(Camion(
                camion_id=camion_id,
                capacidad_total_kg=capacidad,
                capacidad_disponible_kg=capacidad,
                rutas=[RutaCamion(nombre_ruta=r) for r in rutas]
            ))
        db.commit()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()