> **Aceptación vigente:** el usuario confirmó la versión 2 del informe, el alcance limitado al documento y las fuentes correctas. Quedan validados el catálogo de PDF, la búsqueda por archivo, las citas por página, el lector textual y el informe guardado con filtro persistente. La versión 1 se conserva. Preparación automática de una nueva carga: probada de forma automatizada, pendiente de revisión humana al incorporar otro archivo. OCR, búsqueda semántica e IA siguen pendientes. Los apartados inferiores conservan el historial.

# Biblioteca: subir, elegir y buscar

La Biblioteca presenta los documentos originales del proyecto y su disponibilidad para buscar. Las copias internas de texto no aparecen como archivos adicionales. Los PDF con texto seleccionable se preparan al cargarlos desde Biblioteca o Fuentes y archivos; el original permanece intacto.

## Recorrido de uso

1. Abrir **Biblioteca documental**. En **Tus documentos** aparecen los archivos del proyecto.
2. Pulsar **Buscar en este documento** en el archivo que se desea consultar. El selector **Documento** y la descripción de alcance muestran cuál está elegido.
3. Escribir una palabra o tema y pulsar **Buscar evidencia**. Cada resultado de PDF identifica su archivo y página física, contando desde 1. **Ver origen y página** conserva la referencia y la huella, fuera del texto principal.
4. **Leer texto por página** permite revisar el texto extraído y avanzar o retroceder. No sustituye la visualización de imágenes, diagramas o tablas en el PDF original.
5. **Añadir documento** permite seleccionar un archivo en esta misma pantalla. La preparación de PDF se realiza como parte de esa carga. En archivos anteriores sin preparación aparece **Preparar para buscar**.

Al preparar un informe desde una búsqueda, se conserva el documento elegido. La pantalla de Reportes indica ese alcance y permite quitarlo explícitamente. Las versiones ya guardadas no se reescriben.

## Alcance y seguridad

- Operación local sin servicios de IA, APIs externas ni envíos. La búsqueda es por palabras; no interpreta preguntas como un modelo de lenguaje.
- La extracción conserva texto y número de página. No ejecuta instrucciones del documento, JavaScript, enlaces ni archivos incrustados. No hay OCR en esta versión. Un documento sin texto indica que necesita reconocimiento de texto; las páginas vacías se consignan en la cobertura.
- No se interpreta una página con poco texto como completa ni se reconstruyen gráficos o asociaciones de tablas. Es necesario contrastar el original cuando el orden visual de una tabla sea importante.
- 12 MB por original, de 1 a 160 páginas, 300 000 caracteres extraídos, 500 KiB de resultado. Exceder un límite rechaza la preparación sin modificar el original ni conservar una extracción parcial.
- Extracción con pypdf 6.10.0 en un proceso independiente: 25 segundos, memoria de 512 MiB, límites de descompresión de streams y entorno sin credenciales de proveedores. En Windows se exige el límite de memoria mediante Job Object; falla de forma segura si no se puede aplicar. En otros sistemas se limita memoria y CPU con `resource`.
- Las consultas, páginas, archivos y copias de texto se verifican contra el proyecto autorizado. Se comprueban las huellas del original y de la copia textual antes de consultar el caché. Las copias quedan en `Dataset`/`DatasetBlob`; no se agregan tablas ni migraciones.
- Lectores pueden consultar texto preparado; administradores, editores y analistas pueden preparar documentos. La carga conserva las validaciones, permisos y cuotas del cargador existente. La preparación manual tiene un máximo de 20 intentos por proyecto y día; la automática queda limitada por la cuota de carga de archivos y el espacio de 250 MB del proyecto.
- Las auditorías guardan identificadores y cantidades, sin preguntas, extractos, rutas privadas ni claves. Los mensajes del parser se suprimen; los errores de lectura no revelan el documento ni detalles internos.

## Integración y pruebas

`app/library_api.py` instala el catálogo, carga con preparación y lectura por páginas mediante el instalador local existente. `app/pdf_evidence.py` contiene el proceso de extracción. `app/evidence_search.py` ofrece citas que no mezclan páginas y filtra por `document_id`. Reportes recupera y congela esa misma selección en el servidor. `static/library.js` controla catálogo, selección, preparación y lector; descarta respuestas de otro proyecto o selección anterior.

`app/main.py` y `app/knowledge.py` permanecen intactos. La nueva carga delega en el cargador existente y el control de tamaño permite únicamente a la ruta de carga el presupuesto de archivos, conservando el límite de las consultas ordinarias.

Las pruebas cubren originales intactos, caché repetible, páginas y citas, aislamiento entre documentos y proyectos, roles, corrupción, archivos inválidos y cifrados, límites de páginas y tiempo, limpieza temporal, carga con preparación y alcance persistido en informes. Los controladores se prueban con DOM simulado. Las pruebas directas de rutas asíncronas usan un adaptador de planificación inmediato: no abren servidor ni sustituyen la revisión de navegador que debe realizar el usuario.

Los resultados vigentes están en `BIBLIOTECA_PDF_RESULTADO.json`. La aceptación visual de este recorrido queda pendiente de revisión del usuario después de reiniciar el servidor.

Ajuste posterior al lector aceptado: Reportes muestra desde su apertura que la consulta se limita al documento elegido, antes de escribir el título. 231 comprobaciones de controladores JS aprobadas; se conserva la ejecución de 127 pruebas Python sin cambios de backend. El guardado del informe permanece pendiente de confirmación humana.
