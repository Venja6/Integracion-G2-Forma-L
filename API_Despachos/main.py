import os
import time
import yaml
from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from database import engine, Base
from routers import clientes, despachos
from dotenv import load_dotenv

load_dotenv()

# Intentar conectar a la base de datos
max_retries = 5
for attempt in range(max_retries):
    try:
        Base.metadata.create_all(bind=engine)
        print("Conexión exitosa a la base de datos.")
        break
    except Exception as e:
        if attempt < max_retries - 1:
            print(f"Base de datos no lista, reintentando... ({attempt + 1}/{max_retries})")
            time.sleep(3)
        else:
            raise e

app = FastAPI(
    title="API de Sistema de Despachos - CargaSur",
    version="1.0.0"
)

app.include_router(clientes.router)
app.include_router(despachos.router)

# Forzar a FastAPI a entregar exactamente el OpenAPI definido en el YAML
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_path = os.path.join(os.path.dirname(__file__), "openapi.yaml")
    if os.path.exists(openapi_path):
        with open(openapi_path, "r", encoding="utf-8") as f:
            app.openapi_schema = yaml.safe_load(f)
            return app.openapi_schema
    return get_openapi(title=app.title, version=app.version, routes=app.routes)

app.openapi = custom_openapi

@app.get("/")
def read_root():
    return {"mensaje": "API REST de Despachos activa (Contract-First)."}