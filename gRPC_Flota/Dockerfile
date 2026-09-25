FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Los stubs se generan en el build a partir del .proto, asi nunca quedan desactualizados
RUN python -m grpc_tools.protoc -I . --python_out=. --grpc_python_out=. flota.proto

EXPOSE 50051

CMD ["python", "servidor.py"]