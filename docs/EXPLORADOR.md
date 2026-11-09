# Explorador: archivo y selección de evidencias

## Recorrido local

Reinicia con `ABRIR_NEXO_DESARROLLO_LOCAL.bat`, actualiza http://127.0.0.1:8002 y abre **Explorador**.

1. La pantalla reúne noticias guardadas, publicaciones normalizadas de redes y documentos del proyecto. En D14 conserva las veinte noticias existentes; no se añadieron publicaciones ni documentos de demostración.
2. Busca palabras, filtra contenido, canal, actor, fuente y periodo. Los indicadores describen coincidencias dentro del archivo revisado. Se presentan veinte resultados por página.
3. Pulsa un título para consultar extracto, fuente, fecha y referencia. Las noticias sin fecha de publicación muestran su fecha de ingreso; los documentos usan su fecha de carga. **Abrir fuente original** abre un enlace HTTPS con protección de la ventana de origen; el servidor no visita ese enlace.
4. Añade hasta ocho evidencias a **Mi selección**. Se conservan al recorrer páginas y filtros dentro del mismo proyecto. **Preparar selección** vuelve a leer las fuentes y prepara sus extractos y huellas. Puedes descargar el contexto como JSON.
5. Administradores, editores y consultores pueden escribir título y nota y pulsar **Guardar en Reportes**. El servidor comprueba otra vez las fuentes y rechaza una selección desactualizada, conservando la nota en pantalla. Se abre el informe guardado como borrador.
6. El informe conserva exactamente la selección revisada. Usa el proceso existente de **Habilitar para lectores del proyecto** para permitir su consulta a lectores. Para cambiar las fuentes prepara otra selección desde Explorador: el buscador de informes anterior no reemplaza esta selección.

Los lectores pueden buscar, leer y preparar/descargar evidencias autorizadas; no guardar informes. La selección y la nota tienen protección al cambiar de proyecto. Los campos de edición se deshabilitan mientras se prepara o guarda una selección.

**Abrir biblioteca** conserva la búsqueda documental existente. **Radar RSS y administración de fuentes**, al final de Explorador, reúne los controles anteriores de noticias, filtros RSS, resumen documental y fuentes. No se reemplazaron sus identificadores ni sus datos.

## Alcance de la búsqueda

Es búsqueda textual local, sin modelo, embeddings ni consultas externas. Coinciden todas las palabras introducidas, sin distinguir mayúsculas ni acentos. Los caracteres `%` y `_` son texto literal, no instrucciones SQL. La búsqueda no aplica relevancia semántica ni ofrece una respuesta generada.

Cada consulta revisa como máximo las últimas 500 noticias, 500 piezas de redes y 100 fichas documentales que cumplen filtros básicos de tipo, canal, actor y fecha. El texto, la fuente y la paginación se aplican dentro de ese conjunto; un resultado vacío no demuestra que no exista material anterior fuera de los límites. La respuesta conserva los límites, filas revisadas, coincidencias y cobertura. Las páginas son consultas actuales: si se importa material entre páginas, su posición puede cambiar. Solo la selección guardada constituye un corte congelado.

Las fuentes del selector proceden únicamente de ese archivo revisado del proyecto y de los filtros básicos; los homónimos de distintos tipos se mantienen separados mediante su clave. No se presentan cifras como alcance, personas, votantes o ánimo de toda la población.

El filtro por actor requiere un vínculo explícito `PulseMention` entre una publicación de redes y el actor del proyecto. No atribuye automáticamente noticias o documentos por una coincidencia de nombre; con actor elegido solo aparecen esas piezas de redes vinculadas. La futura atribución desde medios requiere su contrato de datos y validación antes de ampliar este filtro.

Los rangos predefinidos son ventanas móviles; el personalizado usa días del navegador y limita el cierre al momento actual. Se normalizan a UTC, con cierre exclusivo. Sin periodo se consulta todo el archivo dentro de los límites de revisión. No se admiten fechas sin zona, rangos invertidos ni fin futuro.

## Documentos e integridad

TXT, MD y CSV de hasta 512 KB utilizan la lectura privada existente, con ruta contenida en el directorio del proyecto o blob del mismo proyecto y SHA-256 verificado. Se intentan como máximo veinte textos documentales por consulta y se revisan hasta 40.000 caracteres por documento. El detalle muestra hasta 4.000 caracteres; la selección conserva hasta 1.500 por fuente.

PDF, XLSX y otros formatos se consultan por su ficha. No se añadió extracción de esos formatos ni OCR; no se incorporan como evidencia textual a la selección hasta disponer de texto verificable. Lo mismo ocurre con archivos ausentes, fuera del almacenamiento privado, demasiado grandes, con codificación inválida o huella diferente. Los códigos de estado de la API son acotados y no incluyen rutas ni errores internos. La ficha de un archivo no certifica su contenido.

El texto de documentos es dato no confiable: se muestra como texto literal y no escoge herramientas, URLs de conexión, instrucciones ni permisos. CSV se lee como texto, no se ejecutan fórmulas y no se genera un CSV de resultados. No se devuelven rutas de disco, contraseñas ni credenciales de conectores.

## Selecciones e informes

Una referencia tiene formato `news:123`, `social:123` o `document:123`. El navegador envía únicamente una lista de referencias y, al guardar, la huella de la selección previamente revisada, título y nota. No puede enviar extractos, autor, proyecto ni etiquetas arbitrarias.

El servidor vuelve a resolver cada referencia dentro del proyecto autorizado; excluye demostraciones. Calcula huellas a partir de campos de origen y texto verificado, ordena el JSON canónico y conserva el orden elegido para las citas. La selección tiene modo `explorer_selection_v1` y la huella cambia si cambia su evidencia. El guardado utiliza el bloqueo del proyecto antes de volver a leer y crear el informe.

Se reutilizan `reports`, `report_versions` y `report_releases`, con sus políticas de acceso y publicación. No se añadieron tablas ni migraciones. El informe nuevo usa `mode=explorer_selection_v1`, fuentes congeladas y la nota del equipo; sigue protegido por el control de integridad y la habilitación existentes. La huella detecta cambios, no certifica que una afirmación sea verdadera.

Guardar intencionalmente varias veces puede crear varios borradores; no se implementó una clave de idempotencia para esa acción manual. La interfaz evita doble envío simultáneo y limita el guardado a veinte intentos por proyecto/día UTC. No publica ni envía el informe a nadie.

## Archivos editables

- `app/explorer_port.py`: filtros, referencias, selección e informe estrictos; protocolo de búsqueda semántica futura y lector deshabilitado.
- `app/explorer_service.py`: búsqueda acotada, lectura privada verificada, resolución y huellas.
- `app/explorer_api.py`: GET `/api/projects/{pid}/explorer`, GET `/explorer/items/{reference}`, POST `/explorer/selection` y POST `/explorer/reports`.
- `static/explorer.js` y la sección `listening` del HTML: interfaz, filtros, página, detalle, selección y guardado.
- `app/report_api.py` y `static/reports.js`: preservan las selecciones congeladas y evitan sustituirlas desde la edición de búsqueda anterior.
- `tests/test_explorer.py`, `tests/check_explorer_ui.mjs` y `tests/check_reports_ui.mjs`: límites, filtros, integridad documental, proyectos, roles, fuentes cambiadas, recuperación e integración con informes.

Los módulos `app/main.py` y `app/knowledge.py` conservan sus huellas originales. El mapa y todas las filas de la base privada se comprobaron sin modificación. Se mantiene la migración preparada 010 y las 34 tablas.

## Conexiones posteriores

No se conectaron proveedores, IA ni RAG ni se generaron gastos. `DisabledSemanticEvidenceSearch` falla de forma cerrada aunque haya claves en el entorno. El protocolo prepara una frontera para devolver referencias; antes de incorporar un adaptador real deberán validarse sus permisos por proyecto y volver a resolver sus referencias en el servidor.

Falta preparar el índice con texto extraído, versionado y hashes, extracción de nuevos formatos, separación y borrado por proyecto, evaluación de recuperación y citas, reglas frente a instrucciones incrustadas, límites de tokens/coste y monitoreo. También falta validar conectores de medios/redes y la atribución de actores. Un proveedor semántico no reemplaza la autorización ni la lectura verificable de fuentes.

La nube y el motor PostgreSQL nativo no se modificaron. Las pruebas SQL de regresión usan PGlite PostgreSQL WASM; las pruebas de interfaz usan DOM simulado. La revisión visual pertenece al usuario en el navegador local. Las cifras finales se registran en `EXPLORADOR_RESULTADO.json`.

Se renovó el respaldo cifrado DPAPI y se comprobó su restauración aislada. Está ligado al usuario Windows actual y no es un respaldo externo ni portable a otra computadora. El paquete editable excluye bases, claves y copias privadas.

Tras aceptar Explorador, sigue **Reportes**.

Aceptación visual del usuario: «Sí, aparece todo y la selección funciona». Continúa Reportes; fuentes externas pendientes.
