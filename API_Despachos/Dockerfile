FROM python:3.11-slim

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

# Generar el stub gRPC desde el contrato que publica Flota (fuente única de verdad del .proto)
COPY --from=flota_contrato flota.proto ./proto/flota.proto
RUN python -m grpc_tools.protoc -I proto --python_out=. --grpc_python_out=. proto/flota.proto

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]