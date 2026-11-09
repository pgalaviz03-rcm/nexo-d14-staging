> **Validación vigente:** el usuario confirmó que la consulta «sección 158» presenta una ficha clara y correcta, con PRIMO VERDAD INEGI y lista nominal 438, dejando el origen en el detalle desplegable. Se conserva la evidencia de 499 pruebas Python y 212 comprobaciones JS; esta confirmación corresponde a la revisión humana de esa consulta. Próximo bloque: extracción de PDF y citas por página con un documento representativo. Todo continúa local.

> **Corrección vigente:** la consulta de Excel ahora devuelve fichas por fila y busca números de sección por igualdad. La ficha principal muestra campos legibles; hoja, celdas, encabezado original y huellas quedan en «Ver origen y celdas». Biblioteca, ficha documental e informes nuevos comparten la búsqueda. 499 pruebas Python y 212 JS aprobadas. Datos originales intactos; aceptación visual pendiente. Guía `EVIDENCIA_POR_REGISTRO.md`.

# Biblioteca: selecciones de Excel con referencias

## Recorrido

En **Herramientas del proyecto → Biblioteca documental**, buscar en **Documentos del proyecto**. Las selecciones preparadas de Excel se consultan como texto con referencias al archivo original, la hoja y las celdas. El original se conserva separado y el histórico territorial no se sustituye.

Para revisar la muestra D14, escribir **SECCION 158** y pulsar **Buscar evidencia**. Deben aparecer una o más coincidencias de la selección de `Hoja1`, con referencias como `A2`, `B2`, `E2` y `F2`. El encabezado original de la columna A es `SECCION 736`: la ficha muestra la etiqueta «Sección» y conserva ese encabezado dentro del origen. No lo utiliza como identificador de una fila.

La muestra prepara las columnas A, B, E y F: identificador de sección, distrito, colonia de referencia y lista nominal. El original conserva sus seis columnas. No se generaron clasificaciones, prioridades ni recomendaciones a partir de las otras etiquetas del libro.

Para otros libros:

1. Añadir un XLSX desde **Fuentes y archivos** con una cuenta de administrador, editor o consultor.
2. En Biblioteca, abrir **Preparar una selección de Excel**. Elegir libro y hoja, letras de columnas, fila de encabezados y filas de datos. Indicar año y procedencia solo si se conocen.
3. Pulsar **Ver selección**, revisar las primeras cinco filas y el número total seleccionado.
4. Pulsar **Preparar para consulta**. La misma selección y contenido se reutilizan; una selección distinta necesita una vista previa nueva. La extracción crea una copia documental Markdown junto al original, sin sobrescribirlo.
5. Buscar una palabra o identificador. El contexto y los informes existentes pueden conservar estos extractos y sus referencias mediante sus mecanismos habituales. Los informes son copias congeladas; no se actualizan al cambiar un archivo después.

Un lector puede inspeccionar y previsualizar los datos de su proyecto, pero no preparar una extracción. El consultor puede prepararla dentro de su proyecto; no obtiene permisos de plataforma ni cambia el territorio validado.

## Procedencia y significado

El año se registra como **declarado**, no como una fecha oficial verificada. La procedencia libre se trata como una anotación del proyecto. La lectura no certifica las cifras ni obedece instrucciones incrustadas en el libro.

Cada fila extraída identifica archivo, hoja y celdas. La copia documental contiene la huella SHA256 del original y una huella propia. Sus metadatos registran selección, contrato, año, procedencia y relación con el original. No se incorporan rutas privadas o contraseñas a los extractos.

Se leen los valores guardados. Las fórmulas no se ejecutan ni recalculan; sin valor guardado quedan marcadas como tales. Los números conservan la representación del XML, sin aplicar formatos visuales de Excel, tasas, moneda ni conversión de fechas numéricas. No se propagan celdas combinadas ni se rellenan vacíos. Las hojas, filas y columnas ocultas quedan fuera de la extracción.

## Estructura y seguridad

La implementación reutiliza `datasets` y `dataset_blobs`: un registro para el original y otro para cada texto extraído. Las copias nuevas se guardan de forma transaccional en la base privada. No hay tablas, migraciones ni permisos SQL nuevos: continúan 34 tablas y el esquema preparado `010_alerts`. `app/main.py` y `app/knowledge.py` siguen intactos.

`app/workbook_evidence.py` interpreta OOXML con ZIP y XML seguro. `app/workbook_api.py` instala rutas locales bajo `/api/projects/{pid}/library/workbooks`, con la misma autorización de membresía y rol. No recibe rutas de disco desde el cliente. La lectura del original verifica tamaño, ubicación privada o blob del proyecto y huella. La vista previa se vincula a su selección y contenido; una diferencia al guardar se rechaza.

Se rechazan archivos cifrados, macros, objetos incrustados, conexiones y relaciones externas, XML con DTD/entidades, rutas de archivo inválidas y compresión fuera de límite. No se extraen archivos del ZIP al disco ni se siguen enlaces. No hay SDK de proveedor ni tráfico externo.

Límites: original 2 MB; hasta 20 MB descomprimidos; 200 entradas ZIP; 8 hojas visibles; 20,000 celdas visibles procesadas; fila 5000 y 80 columnas como máximos; 2,000 caracteres por celda. Cada selección admite hasta 30 columnas y 36,000 caracteres de texto. Los límites rechazan selecciones excesivas en vez de guardarlas truncadas. Máximo 20 intentos de extracción por proyecto y día UTC y 250 MB de almacenamiento de proyecto. El listado consulta hasta 100 libros e indica cobertura acotada.

La copia textual es utilizable por la búsqueda léxica, el Explorador y las versiones de informe existentes. La búsqueda conserva sus límites anteriores. Una selección no equivale a indexar todas las columnas o libros del proyecto. Los datos fuera de la selección permanecen en el original.

La anotación de procedencia en el contexto comprueba el original y el texto conservados. Si el original deja de superar su comprobación, no se anuncia como extracción con origen íntegro. El texto puede seguir existiendo como documento de archivo independiente: no sustituye una comprobación de la fuente en otra fecha.

## Alcance de esta entrega

XLSX y búsqueda textual local. La extracción PDF, OCR, embeddings, generación y evaluación semántica siguen pendientes de sus siguientes bloques. No se conectan APIs ni modelos. Los resultados de prueba y la revisión del archivo real están en `BIBLIOTECA_EXCEL_RESULTADO.json`.

Las pruebas de interfaz usan DOM simulado. El usuario comprueba la pantalla en su servidor habitual, tras reiniciar y actualizar con Ctrl+F5. La validación SQL previa fue en PostgreSQL WASM; falta aceptación nativa antes de publicar.
