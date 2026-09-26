# ADR-03 - Contrato, versionado y evolución

**Estado:**  aceptada

**Contexto:**  Considerando nuestros múltiples sistemas independientes (El sistema que usa REST y el que usa gRPC), es muy posible llegar al escenario donde los datos que se envían evolucionan, en otras palabras, los paquetes de datos en la comunicación pueden tener más o menos campos (o campos que necesitan cambiar de tipo de dato) que la versión original, por esto se necesita definir una política de gobernanza de contratos (Reglamentos para la trata de datos) de tal forma que se puedan actualizar las APIs sin romper el funcionamiento normal del sistema completo.

**Alternativas consideradas:**

- **Versionado Semántico por Ruta con evolución retrocompatible:**  Permite cambios pequeños y es retrocompatible al permitir moverse entre versiones actuales y pasadas de la API, exige no eliminar campos ni alterar sus etiquetas numéricas (tags), además de exigir validación de retrocompatibilidad para que funcionen las versiones anteriores.

- **Versiones nuevas y obligatorias por cada cambio:** Cualquier campo nuevo genera una nueva versión de la API en el contrato, el problema es que causa una cantidad inmanejable de endpoints y código, por lo que los usuarios deben actualizar a la nueva API con cada cambio.

**Decisión:** Versionado semántico por ruta con evolución retrocompatible.

**Justificación:**  Considerando sus ventajas, nos permite añadir nuevos campos utilizando nuevas etiquetas o marcar valores como "deprecated" alertando al resto de sistema y desarrolladores que se dejará de usar el campo específico, pero también, gracias al versionado, las versiones anteriores ignoran los datos nuevos si la actualización es opcional.

Mantiene la cantidad de endpoints baja y tiene una organización por URLs simple (versionX/JSON).

**Costo aceptado:**  Asumimos mantener una alta tolerancia en nuestros endpoints durante las ventanas de transición, así como nunca eliminar etiquetas numéricas de los datos que se envían, aceptando la acumulación de campos obsoletos (deprecated) en los contratos internos.

**Consecuencias:**  Los cambios deben ser comunicados a través de:

Un documento Openapi que se actualiza dinámicamente con los cambios y deprecaciones

La compilación del .proto al momento de considerar los campos que se modificaron.
