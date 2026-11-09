# Reportes: archivo, versiones y lectura

## Revisar en local

Reinicia con `ABRIR_NEXO_DESARROLLO_LOCAL.bat`, actualiza http://127.0.0.1:8002 y abre **Reportes**.

El archivo distingue tres orígenes: Briefing, selección de evidencias de Explorador y búsqueda documental. Los filtros de título, origen y estado trabajan sobre los últimos cien informes autorizados recuperados; no buscan todo un archivo de tamaño ilimitado. Las cifras superiores describen ese archivo consultado, antes de aplicar los filtros de pantalla.

| Estado | Qué ve el equipo |
|---|---|
| Borrador | El informe todavía no tiene ninguna versión habilitada para lectores |
| Habilitado | La última versión visible para el equipo está habilitada |
| Actualización sin habilitar | Existe una versión nueva; los lectores siguen consultando la versión anterior habilitada |

Un lector recibe exclusivamente las versiones habilitadas. Sus filtros y contadores no revelan el título, las cifras ni el estado de borradores posteriores. Las cuentas del proyecto y la superadministración conservan sus permisos establecidos; el rol de administrador de proyecto no adquiere control global.

## Trabajar con un informe

1. Abre un informe desde el archivo. Consulta origen, versión, fecha de guardado, nota del equipo y fuentes. Cada fuente puede expandirse para leer su extracto y abrir el enlace original. Las fechas de carga o ingreso se distinguen cuando la cita las declara.
2. **Ver versiones** permite revisar una copia anterior sin editarla. Una versión previamente habilitada conserva su condición de lectura aunque ya exista otra más reciente.
3. Los informes procedentes de una búsqueda documental permiten guardar una **nueva versión** con título, tema y nota. La búsqueda de fuentes se repite y la versión anterior se conserva. Si otra persona guarda antes, se rechaza el intento desactualizado y tu nota permanece en pantalla.
4. Briefing y Explorador conservan sus fuentes congeladas. **Abrir origen** lleva a la pantalla correspondiente para preparar otro corte o selección. La edición de búsqueda anterior no reemplaza estos informes.
5. Administradores y editores pueden **Habilitar para lectores del proyecto**, únicamente sobre la versión actual revisada. Los consultores pueden escribir pero no habilitar. No se habilita una actualización automáticamente al guardarla.

En Briefing se muestran los indicadores que ya existan en su corte guardado: notas, menciones, señales, piezas y cobertura de clasificación, índice de tono, desglose de tono, emociones, burla y temas. No se realiza análisis al abrir un informe; los valores desconocidos conservan el guion. Un informe antiguo que no incluya esas dimensiones no las adquiere por abrirse con esta versión.

Guardar, habilitar o descargar no envía mensajes ni modifica preferencias de entrega. La programación y los canales siguen en el circuito de Briefing, pendiente de sus conexiones externas.

## Descargas

**Descargar datos JSON** conserva la respuesta del informe guardado, su versión, citas, metadatos y huella. **Documento imprimible** descarga un archivo `.html` autónomo, con la marca y el proyecto configurados, título, estado de esa versión, fechas, nota y fuentes.

Abre el archivo descargado en tu navegador. Para obtener un PDF, usa Imprimir y elige Guardar como PDF o la impresora PDF disponible en tu equipo. NEXO no genera un PDF binario en esta versión. La hoja preparada utiliza tamaño A4 y estilos de impresión, sin fuentes, imágenes ni recursos externos.

El documento se compone exclusivamente a partir de la versión guardada, sin volver a buscar noticias ni consultar IA. Los datos de Briefing existentes en el corte también se conservan en la impresión. Las fuentes se presentan con sus extractos y enlaces HTTPS admisibles. Todo título, nota, extracto, marca y nombre de proyecto se escapa como texto; no se incorporan scripts, formularios, imágenes ni estilos provenientes de esas fuentes. Se incluye una política de contenido restrictiva y se desactiva el envío del referente al abrir enlaces.

La autorización y habilitación se comprueban en el servidor antes de entregar ambos formatos. El documento imprimible se recibe como JSON autenticado y la interfaz construye la descarga local, sin crear una URL pública del informe. Las respuestas de exportación usan `Cache-Control: no-store`.

La huella mostrada corresponde al JSON de la versión almacenada, no al archivo HTML o al PDF que se imprima. No es una firma digital ni prueba de veracidad. Una copia descargada queda fuera de los controles de acceso de NEXO y no se revoca al cambiar permisos: debe conservarse y distribuirse únicamente entre personas autorizadas. La aplicación no hace esa distribución.

## Protección de la interfaz

Las solicitudes de lista, detalle, versiones, guardado, habilitación y descarga comprueban el proyecto y la generación de la vista antes de mostrar resultados. También se descartan respuestas tardías si se cambia de proyecto y después se regresa al mismo. Una descarga pendiente no se activa en el nuevo proyecto.

Una versión histórica no puede provocar el guardado de una revisión ni habilitar una cabecera más reciente mediante sus controles. La habilitación envía la versión efectivamente revisada, y el servidor rechaza una versión desactualizada. Durante un guardado se bloquean edición y cambio de proyecto. Actualizar el archivo conserva la nota sin guardar; un conflicto no la borra.

Las consultas no publican ni escriben auditoría. El seguimiento de creación, revisión y habilitación mantiene la auditoría existente, con identificadores de informe y versión, sin copiar notas o extractos a los registros de auditoría.

## Estructura editable

- `app/report_api.py`: metadatos de origen/estado del archivo, condición de habilitación de la versión exacta, rechazo temprano de revisiones desactualizadas y nueva descarga imprimible autenticada. Se conservan los controles de membresía, roles, versiones inmutables e integridad.
- `app/report_document.py`: composición HTML autónoma, texto escapado, enlaces admitidos y estilos de impresión.
- `static/reports.js`: filtros, estados, lectura, versiones, edición, habilitación, retorno al origen y descargas, con protección de solicitudes tardías.
- Sección Reportes de `static/index.html`: archivo con indicadores y controles nuevos. Las secciones y los datos de otros módulos se conservaron.
- `tests/test_report_workbench.py`: estados visibles, permisos de impresión, versión exacta, integridad, marca dinámica, contenido hostil y estadísticas guardadas.
- `tests/check_report_safety_ui.mjs`: filtros, versiones históricas, conflictos, notas, cambio de proyecto y descargas tardías. Se mantienen las pruebas anteriores de informes.

El endpoint nuevo es `GET /api/projects/{pid}/reports/{report_id}/versions/{version}/document`. Devuelve un objeto JSON con `format`, `filename`, `html`, `report_id`, `version` y `sha256`; comparte la autorización de la exportación JSON existente. La interfaz descarga ese HTML como archivo, sin insertarlo en el DOM de NEXO.

Se conservan las 34 tablas y la migración 010. No se modificaron `app/main.py` ni `app/knowledge.py`, ni el mapa territorial ni las filas de la base privada. No se creó otro informe real durante las pruebas del agente; los informes ficticios se limitaron a bases aisladas.

## Verificación y pendientes

Las cifras finales se registran en `REPORTES_RESULTADO.json`. Las comprobaciones de interfaz emplean DOM simulado y las de permisos SQL usan PGlite PostgreSQL WASM; no equivalen a revisión visual del navegador, impresión en una impresora real ni aceptación de PostgreSQL nativo. Se verificó la composición del informe existente del D14, con sus ocho fuentes, sin guardar un archivo privado ni alterar la base.

Se renovó el respaldo cifrado DPAPI con restauración aislada verificada. Permanece ligado al usuario Windows actual y no es una copia externa ni portable a otro equipo. El ZIP editable excluye bases, claves y respaldos privados.

No se conectaron IA, RAG, proveedores de mensajes ni servicios de PDF, ni se generaron gastos o cambios en la nube. Para el cierre siguen pendientes las conexiones autorizadas, evaluación de fuentes y modelos, reglas de envío, permisos y presupuesto de proveedores, monitoreo y pruebas en el entorno de nube separado. La descarga HTML usa únicamente funciones locales y no necesita un proveedor nuevo.

Tras aceptar Reportes, sigue **Auditoría de cuentas**.

Aceptación del usuario: «Sí, descarga y se ve bien». Pantalla y documento HTML descargado legible; impresión física y PDF aún no probados.
