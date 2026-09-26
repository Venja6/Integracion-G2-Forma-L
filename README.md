# Sistema de Gestión y Despacho Logístico (CargaSur)

Solución de integración entre el sistema de **Despachos** (API REST en FastAPI) y el sistema de **Flota** (microservicio gRPC en Python), respaldada por bases de datos PostgreSQL independientes por servicio y una capa de almacenamiento en memoria con Redis.

Este proyecto corresponde a la evaluación de la **Unidad 1 - Integración de Sistemas (Forma L)**, Facultad de Ingeniería, Universidad de Concepción.

---

## 1. Arquitectura General y Servicios

El sistema implementa el patrón de referencia **"REST hacia afuera, gRPC hacia adentro"**:

* **API Despachos (REST - FastAPI):** Punto de entrada público expuesto en el puerto `8000`. Maneja clientes, órdenes de despacho y consulta de disponibilidad de camiones.
* **Servicio Flota (gRPC - Python):** Servicio interno de alto rendimiento en el puerto `50051`. Administra el catálogo de camiones, rutas y la capacidad disponible.
* **Bases de Datos (PostgreSQL):** Una base de datos por servicio (*Database-per-Service*):
  * `despachos_db`: Puerto host `5432` (interno `5432`).
  * `flota_db`: Puerto host `5433` (interno `5432`).
* **Caché (Redis):** Almacenamiento en memoria para optimizar lecturas frecuentes de disponibilidad de camiones e invalidación activa ante reservas/cancelaciones.
* **Cliente Node.js:** Segundo cliente gRPC implementado para demostrar interoperabilidad sobre el contrato binario.

---

## 2. Requisitos Previos

* [Docker Desktop](https://www.docker.com/products/docker-desktop/) (con Docker Compose v2+) en ejecución.
* [Node.js](https://nodejs.org/) v18+ y npm.
* Python 3.11+.

---

## 3. Instrucciones de Ejecución con Docker

Toda la plataforma está containerizada y se despliega con un único comando:

### Paso 1: Clonar el repositorio
```bash
git clone <URL_DEL_REPOSITORIO>
cd Integracion-G2-Forma-L
```

### Paso 2: Construir e iniciar los contenedores
```bash
docker compose up -d --build
```

### Paso 3: Verificar el estado de los servicios
Verifica que los contenedores estén activos:
```bash
docker compose ps
```

---

## 4. Acceso e Interacción con el Sistema

### A. Documentación Interactiva (Swagger UI)
Una vez levantado el sistema, ingresa desde tu navegador a:
* **Swagger UI:** [http://localhost:8000/docs](http://localhost:8000/docs)
* **ReDoc:** [http://localhost:8000/redoc](http://localhost:8000/redoc)
* **Especificación OpenAPI:** `API_Despachos/openapi.yaml`

### B. Flujo Básico de Uso

1. **Autenticación:**
   * Obtén tu token JWT o credencial en `/v1/auth/login`.
   * En Swagger UI, pulsa el botón **Authorize** e introduce el token (`Bearer <token>`).
2. **Gestión de Clientes:**
   * Registra un cliente con `POST /v1/clientes`.
   * Lista los clientes existentes con `GET /v1/clientes`.
3. **Consulta de Disponibilidad de Camiones:**
   * Realiza una consulta con `GET /v1/camiones`.
4. **Registro de Despacho:**
   * Registra un despacho con `POST /v1/despachos`. La API verificará la capacidad en Flota por gRPC.
5. **Reversión / Cancelación:**
   * Cancela una orden con `DELETE /v1/despachos/{id}` para liberar la capacidad del camión en Flota.

---

## 5. Ejecución del Segundo Cliente gRPC (Node.js)

Para interactuar directamente con el servicio gRPC desde Node.js:

```bash
docker compose run --rm cliente_node
```

---

## 6. Ejecución de Tests Automatizados

Para ejecutar la suite de pruebas unitarias y de integración:

```bash
# Crear entorno virtual e instalar dependencias de tests
pip install -r tests/requirements.txt

# Ejecutar pytest
pytest
```

---

## 7. Demostración de Resiliencia y Modos de Falla (T7)

Para evidenciar el comportamiento de la API REST ante la caída del servicio gRPC de Flota:

1. Detén el contenedor de Flota:
   ```bash
   docker stop flota_grpc
   ```
2. Realiza un intento de despacho desde Swagger UI o cURL (`POST /v1/despachos`).
3. Comprueba que la API devuelve un código de estado controlado (`503 Service Unavailable` o `504 Gateway Timeout`) con un mensaje estructurado en JSON y no colapsa.
4. Vuelve a iniciar el servicio:
   ```bash
   docker start flota_grpc
   ```

---

## 8. Detener y Limpiar el Entorno

Para detener todos los servicios y liberar los puertos:
```bash
docker compose down
```

Para eliminar los contenedores y los volúmenes de datos asociados:
```bash
docker compose down -v
```

---

## 9. Declaración de Integridad Académica y Asistentes de IA

En cumplimiento con los requerimientos del encargo de Unidad 1:
* **Herramientas utilizadas:** Asistentes de Inteligencia Artificial (Gemini / Claude) fueron utilizados como soporte para:
  1. Consulta de sintaxis para construcción de la base de datos en SQLAlchemy 2.0.
  2. Apoyo en la configuración inicial de Dockerfiles y scripts de benchmarking.
  3. Verificación y mejora del código fuente
  4. Redacción y estructura de plantillas técnicas.
* **Verificación:** Todo el código fuente, modelos relacionales, contratos (.proto y openapi.yaml) e implementación de lógica de negocio fueron revisados, probados y validados por los integrantes del equipo.