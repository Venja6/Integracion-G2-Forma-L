FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Generar los modelos Pydantic directamente desde el contrato openapi.yaml
RUN datamodel-codegen --input openapi.yaml --output schemas_generated.py --input-file-type openapi

# Se genera el stub gRPC a partir del flota.proto de Flota, asi usamos un solo contrato y no una copia
COPY --from=flota_contrato flota.proto ./proto/flota.proto
RUN python -m grpc_tools.protoc -I proto --python_out=. --grpc_python_out=. proto/flota.proto

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]