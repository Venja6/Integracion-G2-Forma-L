# ADR-02: Adopción de gRPC y Protocol Buffers para comunicación interna (Despachos-Flota)

**Estado:**  Aceptada

**Contexto:**  El sistema de Despachos (orientado al cliente) necesita comunicarse a nivel interno con el sistema de Flota para validar y reservar capacidades. Esta comunicación interna ocurrirá con una alta frecuencia y para manejar los tiempos se requiere una baja latencia. Tradicionalmente se usaría REST sobre HTTP/1.1 con JSON, pero el volumen de tráfico proyectado exige evaluar alternativas de mayor rendimiento computacional.

**Alternativas consideradas:**

- **Opción A (REST + JSON puro):**  Es el formato estándar, fácil de debugear por humanos. Utiliza HTTP/1.1 tradicional.

- **Opción B (REST + JSON con compresión gzip):**  Reduce el tráfico de red, pero añade un costo de CPU en cada extremo para comprimir y descomprimir los strings.

- **Opción C (gRPC + Protocol Buffers):**  RPC binario sobre HTTP/2, requiere un esquema predefinido (.proto) y librerías generadas automáticamente.

**Decisión:**  Se eligió la Opción C. La comunicación interna entre los microservicios de Despachos y Flota se realizará exclusivamente mediante gRPC utilizando Protocol Buffers.

**Justificación:**  Se ejecutó un experimento de carga (hasta 10.000 entidades) comparando directamente JSON y Protobuf. Los datos derribaron el mito del tamaño: bajo compresión estándar, JSON y Protobuf consumen un ancho de banda similar. Sin embargo, Protobuf demostró ser de 6 a 8 veces más veloz para armar los mensajes (serialización) y 3 veces más veloz para leerlos (deserialización) en Python. Al usar gRPC, los servidores gastarán significativamente menos CPU procesando mensajes, permitiendo atender más peticiones concurrentes con el mismo hardware. Además, el archivo .proto fuerza un contrato estricto entre equipos, eliminando los errores de tipeo y estructuras mal formadas comunes en JSON.

**Costo aceptado:**  Protobuf es un formato binario, por lo que no es legible por humanos. Además, introduce una fricción inicial en el desarrollo y el flujo de trabajo CI/CD: cada vez que cambia el contrato de la API, es obligatorio actualizar el archivo .proto y desde el cual se generan los stubs durante la etapa de compilacion para ambos servicios.

**Consecuencias:**

- Se requerirán herramientas especializadas (como Postman gRPC, BloomRPC o grpcurl) para probar manualmente los endpoints de Flota.

- El pipeline de integración continua (CI/CD) deberá incluir un paso para compilar los stubs de protobuf y validar que no se rompan contratos hacia atrás.
