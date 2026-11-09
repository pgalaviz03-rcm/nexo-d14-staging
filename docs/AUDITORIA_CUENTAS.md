# Auditoría de cuentas: referencias y calidad de capturas

La pantalla reúne las cuentas de todos los actores del proyecto, incluidas las referencias que aún no tienen capturas, las pausadas y las cuentas antiguas con capturas que todavía no están en una ficha. Se reutilizan Actores, Redes y sus registros inmutables. No se crea otro directorio.

## Recorrido de revisión

1. Reiniciar el servidor con `ABRIR_NEXO_DESARROLLO_LOCAL.bat` y actualizar http://127.0.0.1:8002.
2. Abrir **Auditoría de cuentas**. En D14 deben aparecer las cuatro referencias públicas configuradas, con primera captura pendiente. No se añadieron cifras ficticias ni se verificó externamente la identidad de sus titulares.
3. Cambiar actor, red o periodo y revisar los indicadores. Los periodos de 7, 30 y 90 días utilizan días completos anteriores a hoy según la zona horaria del navegador; los intervalos se envían como instantes UTC.
4. Pulsar **Ver diagnóstico en pantalla**, junto al filtro Mostrar. Abre los diagnósticos y desplaza la pantalla a las tarjetas. Cada tarjeta tiene también un botón **Ver diagnóstico** para abrir o cerrar solo su información. El estado **Primera captura pendiente** aparece fuera del diagnóstico, sin pulsar nada.
5. **Mostrar** filtra únicamente las tarjetas; los indicadores conservan el alcance del actor y red seleccionados. **Descargar datos (JSON)** guarda ese corte como JSON con el filtro de estado y las tarjetas visibles. Los conteos del archivo mantienen el mismo alcance de los indicadores.
6. Los botones de Actores, Redes y Fidelidad abren las pantallas existentes. Se puede cambiar de proyecto y cada espacio comienza limpio.

## Qué comprueba

- Referencias HTTPS con dominio correspondiente a la red, sin credenciales ni parámetros de secreto reconocidos. No se realiza DNS, HTTP ni recolección.
- Registros con JSON de objeto y tamaño acotado; solo salen los campos permitidos. Un error devuelve un código diagnóstico, nunca el JSON original ni una excepción con su contenido.
- Contadores enteros no negativos hasta 9,007,199,254,740,991. Booleanos, cadenas y decimales no se convierten en cifras. Cero es un dato; ausente es desconocido.
- Fechas de captura no futuras. Una captura futura se señala y se excluye de la última observación y de los cortes.
- Para actividad, inicio anterior a fin y fin no posterior a captura. El periodo elegido y el anterior deben coincidir exactamente con los intervalos declarados; no se suman capturas ni se interpolan cifras.
- Los campos alineados necesitan valores válidos en ambos periodos de la misma cuenta, red y origen conocido (`manual` o `apify_export`). Un origen desconocido o distinto impide esa alineación. Los campos que no aparecen en ambas capturas no se consideran alineados.

«Cortes alineados» describe comprobaciones de forma, intervalo y procedencia declarada. No certifica las cifras, la autenticidad de una cuenta ni que el proveedor haya mantenido su definición. El adaptador futuro debe documentar versión de contrato y significado de las métricas antes de interpretar variaciones. No se calcula un porcentaje universal de completitud: las redes ofrecen campos distintos.

Las incidencias se acumulan sobre el historial consultado; un registro anterior inválido sigue visible aunque exista una captura posterior válida. La tabla de campos corresponde exclusivamente a la última captura no futura, sin rellenarla con cifras de otras fechas. El indicador «Con capturas» significa que existe un registro no futuro, aunque su contenido necesite revisión.

La revisión de una referencia es interna al equipo. Esta pantalla no certifica identidad, cuentas falsas, bots ni seguidores auténticos; no examina personas ni infiere preferencias políticas o fidelidad individual.

## Estructura y permisos

`GET /api/projects/{pid}/account-audit` acepta `actor_id`, `network`, `start`, `end`. Requiere membresía del proyecto, incluye únicamente datos reales de ese proyecto y aplica la selección de actor dentro del conjunto autorizado. Lectores, consultores y administradores pueden consultar y descargar. Se utiliza el mismo mecanismo de acceso del resto del proyecto; un administrador de proyecto no obtiene acceso global.

Consulta de solo lectura: no modifica fichas, capturas, informes ni bitácoras. No hay tabla, migración, credencial o proveedor nuevo. Continúan las 34 tablas y la migración preparada `010_alerts`. `main.py` y `knowledge.py` permanecen intactos.

Límites explícitos: 50 actores reales (activos primero), 1,000 capturas por actor y 32 cuentas por actor (referencias registradas primero). Las capturas se acotan antes de filtrar la red. Si se alcanza un límite se indica cobertura acotada; los conteos corresponden al conjunto consultado. Los actores sin referencia y sin capturas están en el selector, pero no generan una cuenta ficticia. Una referencia completamente inválida puede generar una tarjeta de diagnóstico sin enlace en la vista de todas las redes.

La interfaz escribe textos literales y solo abre enlaces HTTPS. Al cambiar de proyecto o reiniciar el módulo se invalidan respuestas anteriores, incluso si se vuelve al mismo proyecto; no se permite exportar el corte anterior. No se inserta HTML de las fuentes.

## Integración posterior

Los futuros adaptadores alimentarán los contratos existentes de Redes y Fidelidad; esta pantalla leerá esos mismos registros. Para obtener datos reales faltan la selección del producto/actor de Apify o API de cada red, permisos de cuenta, mapeo y definición de campos, credenciales solo de servidor, fechas y periodos reales, cuotas y presupuesto, programación, reintentos y observabilidad. Registrar un perfil público no concede acceso a métricas privadas. Nada de ello se activa en esta entrega.

La clasificación de textos mediante IA continúa separada: no produce los contadores de las cuentas. No se han enviado mensajes, conectado fuentes ni realizado cambios en nube.

Los resultados exactos se conservan en `AUDITORIA_CUENTAS_RESULTADO.json`. Las pruebas de controladores utilizan DOM simulado; la inspección visual corresponde al usuario en su navegador. Las comprobaciones SQL previas usan PostgreSQL WASM; falta aceptación con PostgreSQL nativo antes de desplegar.

Ajuste tras la revisión del usuario: se sustituyó el texto desplegable por botones explícitos, se añadió un acceso superior al diagnóstico y un resumen visible de capturas pendientes. La descarga JSON conserva los datos y no abre el diagnóstico. Al actualizar esta versión, reiniciar el servidor y pulsar Ctrl+F5 en el navegador. El usuario confirmó después del ajuste: «Sí, ahora aparecen».
