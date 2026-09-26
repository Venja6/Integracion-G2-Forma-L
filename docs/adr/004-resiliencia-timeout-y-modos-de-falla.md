# ADR-04: Resiliencia, timeout y modos de falla en la integración gRPC


**Estado:** Aceptada

**Contexto:**  El sistema de Despachos depende síncronamente del servicio de Flota para validar y reservar la capacidad de carga. Si Flota experimenta latencias excesivas o caídas, la API de Despachos podría agotar sus hilos de conexión esperando respuestas, generando una falla en cascada que degradaría todo el sistema.

**Alternativas consideradas:**

- **Opción A:**  Esperar indefinidamente la respuesta de Flota. Ofrece alta consistencia si el sistema vuelve, pero permite la caída total de la API pública ante fallas prolongadas.

- **Opción B:** Despachos interrumpe la conexión tras 2 segundos devolviendo un HTTP 503. Protege a la API, pero genera alto riesgo de "reservas huérfanas" si Flota termina la operación internamente.

- **Opción C:**  Despachos configura un timeout de 2s, y Flota valida la vigencia del plazo justo antes de confirmar los cambios en su base de datos.

**Decisión:**  Se eligió la Opción C. La API responderá con HTTP 503 cuando Flota no procese a tiempo, abortando la transacción en ambos extremos.

**Justificación:**  Según nuestra experimentación empírica, la falta de timeout permite que las peticiones se encolen superando los 3 segundos de bloqueo cuando Flota colapsa. Implementar un timeout unilateral acotó el tiempo de respuesta en ~2009 ms, pero generó un 100% de inconsistencia (124 reservas huérfanas medidas) porque Flota ignoraba el abandono del cliente. La Opción C mantiene el límite de latencia (protegiendo a la API) y con eso se logró reducir las reservas huérfanas a 0.

**Costo aceptado:**  Cerca del umbral de tiempo límite, Flota abortará peticiones que quizás habrían completado su escritura con unos milisegundos extra. Se sacrifica esa tasa de éxito inmediata a favor de garantizar que un error 503 efectivamente signifique que no se descontó capacidad por error.

**Consecuencias:**  Si en el futuro se observan inconsistencias derivadas de retrasos post-commit (ej. respuesta perdida tras guardar en BD), será necesario evolucionar este diseño hacia un modelo de consistencia eventual. Utilizar mecanismos que puedan manejar eventos y resolución de dichos problemas.
