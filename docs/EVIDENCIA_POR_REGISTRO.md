> **Validación vigente:** el usuario confirmó que la consulta «sección 158» presenta una ficha clara y correcta, con PRIMO VERDAD INEGI y lista nominal 438, dejando el origen en el detalle desplegable. Se conserva la evidencia de 499 pruebas Python y 212 comprobaciones JS; esta confirmación corresponde a la revisión humana de esa consulta. Próximo bloque: extracción de PDF y citas por página con un documento representativo. Todo continúa local.

# Biblioteca: una ficha por registro

El usuario detectó que «SECCION 158» devolvía fragmentos que mezclaban varias filas y mostraban metadatos técnicos. La extracción se había conservado correctamente, pero el buscador trataba su copia textual como un documento narrativo y podía coincidir solo con parte de las palabras.

## Resultado esperado

Al buscar **sección 158**, **SECCION 158** o **lista nominal de la sección 158**, la Biblioteca devuelve la fila de esa sección en una tarjeta:

| Campo | Valor del Excel aportado |
|---|---|
| Sección | 158 |
| Distrito | 14 |
| Colonia de referencia | PRIMO VERDAD INEGI |
| Lista nominal | 438 |

Debajo queda el nombre del archivo y el año declarado. **Ver origen y celdas** conserva hoja, fila, celdas, anotación de procedencia, encabezado original y huella, sin ocupar la ficha principal. El original dice `SECCION 736` en A1: se normaliza únicamente la etiqueta visible a «Sección», y el valor se obtiene de la celda de la fila, no del número del encabezado.

Buscar una sección inexistente devuelve cero coincidencias; no se sustituye por una sección parecida. «158» no se confunde con «1580», ni con el mismo número presente en la lista nominal de otra fila. Dos filas o fuentes que contienen un mismo identificador siguen siendo registros separados, sin mezclar sus cifras.

Las búsquedas de palabras en Excel se aplican por fila y requieren todas las palabras útiles de la consulta. Una búsqueda general puede producir varias fichas y conserva los límites de resultados. Las consultas con un número de sección explícito usan igualdad del identificador. No se promete interpretar cualquier pregunta o calcular agregados: sigue siendo recuperación local de evidencia, sin generación conectada.

## Cambio interno

`app/evidence_search.py` conserva la lectura léxica de noticias y documentos ordinarios y consulta los libros como registros. Verifica el original, la copia textual y la reproducción de la selección antes de utilizar las filas. Un libro o selección que falla esa verificación no reaparece mediante los fragmentos técnicos de su copia Markdown.

Los resultados de Excel incluyen campos de presentación, fila y origen estructurado. El extracto destinado a contexto e informes contiene solamente los campos de la fila; los metadatos viajan separados. Las rutas de Biblioteca, ficha documental y los informes documentales nuevos usan esta misma capa. Las versiones anteriores de informes se conservan sin reescribir.

El Explorador sigue siendo un archivo de documentos y publicaciones; esta corrección de consulta por fila corresponde a Biblioteca y su preparación de informes. El texto almacenado conserva su procedencia para auditoría y recuperación.

`static/evidence_cards.js` dibuja tarjetas con textos literales, valores ausentes como «Sin dato» y el origen plegado. No inserta HTML de las celdas. Los contadores enteros se presentan con separadores, sin redondear ni convertir valores ausentes en cero.

No se modificaron `app/main.py`, `app/knowledge.py`, el libro, los datos extraídos ni el histórico territorial. No cambian las 34 tablas, la migración preparada 010 ni las políticas SQL. Cada consulta mantiene el ámbito del proyecto y los permisos existentes.

## Comprobación manual

1. Reiniciar `ABRIR_NEXO_DESARROLLO_LOCAL.bat` y actualizar con Ctrl+F5.
2. Entrar con la cuenta local de consultor. Abrir **Herramientas del proyecto → Biblioteca documental** y elegir **Documentos del proyecto**.
3. Buscar **sección 158**. Debe aparecer una sola ficha con los cuatro campos anteriores, sin filas de otras secciones ni bloque SHA256 en la ficha principal.
4. Abrir **Ver origen y celdas**. Deben verse `Hoja1`, fila 2 y las celdas `A2`, `B2`, `E2`, `F2`.
5. Opcionalmente buscar **sección 211** y después **sección 736**: la primera se consulta por separado y la segunda no tiene coincidencia en este libro.

Las pruebas de interfaz usan DOM simulado; la aceptación visual corresponde al usuario. La consulta real y la copia restaurada se comprueban en modo de solo lectura. Los resultados exactos se incorporan a `BIBLIOTECA_EXCEL_RESULTADO.json`.
