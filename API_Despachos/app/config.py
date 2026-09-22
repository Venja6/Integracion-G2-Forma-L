import os

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@db:5432/despachos_db")
GRPC_FLOTA_HOST = os.getenv("GRPC_FLOTA_HOST", "localhost:50051")
SECRET_KEY = os.getenv("SECRET_KEY", "super-secret-key-cargasur")
ALGORITHM = "HS256"