# ADR-01 - Estilo de integración y descomposición (Se deciden dos servicios para el proyecto)

**Estado:**  aceptada

**Contexto:**  El entorno está definido por dos partes del negocio, la parte que se encarga de manejar los despachos y la que manipula la flota de camiones y decide si puede llevar los encargos.

Considerando esto, la flota no necesita saber todos los detalles con los que trata el área de despacho, pero si necesita un punto de integración con el otro sistema.

Observando el sistema general que esperamos, aparecen restricciones de mantener un alto rendimiento en la lectura y garantizar consistencia entre cada transacción.

**Alternativas consideradas:**

- **Servicios y bases de datos independientes:** Opción que más se apega a los principios de DDD, escalable independientemente y puede aislar los fallos, a cambio puede haber una duplicación de datos y estos mismos deberán ser mejor resguardados para coordinar los eventos de transacción.

- **Monolito modular:**  Mantiene separación estilo DDD y evita latencia de red, pero los módulos comparten una sola base de datos lo que puede degradar el rendimiento de esta.

**Decisión:** Servicios y bases de datos independientes

**Justificación:**  Aparte de ser un sistema que demuestra un flujo de trabajo donde primero se realizan los servicios independientes para luego integrarlos entre ellos (Objetivo de la tarea de esta primera unidad), según : "Ayuda a asegurar que los servicios no estén muy acoplados y evita que los cambios en una base de datos no afecten a los datos de otra (...) Cada servicio usa el tipo de base de datos que se acerque más a sus necesidades."

Esto justifica la separación de bases de datos, pero para la separación de servicios, según : "La separación de servicios ayuda en la facilidad para realizar cambios en el sistema sin coordinación entre equipos de desarrollo/servicio (...) la mayoría o todos los cambios se mantienen dentro de un solo servicio."

**Costo aceptado:**  El mayor problema que nace de usar esta arquitectura son las posibles inconsistencias en las bases de datos, ya que hay que gestionar las pequeñas ventanas donde los datos pueden ser inconsistentes entre bases (Fenómeno llamada consistencia eventual).

Otro punto que viene implícito al usar una arquitectura con contextos tan independientes es la aparición de latencia para que una transacción se termine y la complejidad que implica mantener varios servicios separados.

**Consecuencias:**  Exige el uso de APIs para interactuar con la base de datos, exige implementar métodos de consistencia de datos e idealmente implica el uso de sistemas distintos para cada contexto que lo necesite.
