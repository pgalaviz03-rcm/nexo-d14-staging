# nexo. · Temas y revisión manual

Actualización local del piloto D14. IA y conectores externos desactivados.

El ZIP de Atalaya aporta una maqueta y definición de flujo. Se reutilizó su idea de catálogo editable, clasificación corregible y explorador; la persistencia, los permisos, las versiones y el historial son implementación de NEXO. No se copiaron sus cifras ficticias ni perfiles personales al proyecto.

## Cómo cargar la actualización

En la ventana del servidor que muestra el puerto 8002 pulsa Ctrl+C y vuelve a abrir `ABRIR_NEXO_DESARROLLO_LOCAL.bat`. Actualiza el navegador y entra con tu cuenta local habitual. El menú añade **Temas y revisión**. Se conserva la misma copia de trabajo, sin volver a importar o reemplazar noticias.

## Flujo disponible

1. Crea un tema descriptivo, por ejemplo Servicios públicos. El catálogo comienza vacío; no se incorporan etiquetas de ejemplo automáticamente.
2. Busca una noticia y pulsa **Abrir revisión**. El enlace permite consultar la fuente original.
3. Selecciona hasta diez temas, un estado y una nota. Los estados son Sin revisar, Por verificar y Revisado documentalmente. Este último registra trabajo documental, no certifica que el hecho sea verdadero.
4. Guarda la revisión. La versión aumenta y se registra usuario, fecha, nota y nombres de los temas en ese momento.
5. **Ver historial de cambios** muestra hasta las últimas cien versiones. Renombrar un tema no cambia el nombre guardado en una revisión antigua.

Los filtros por texto, estado y tema se aplican a los registros del proyecto. Se muestran hasta cien publicaciones y se declara si la consulta quedó acotada. No se asigna automáticamente una noticia al territorio D14 ni se infiere opinión pública por tener una etiqueta.

## Permisos y conservación

| Rol del proyecto | Catálogo | Etiquetar y revisar | Historial |
|---|---|---|---|
| Administrador / editor | Crear, renombrar, archivar y reactivar | Sí | Consultar |
| Analista | Consultar | Sí | Consultar |
| Lector | Consultar | No | Consultar |

Archivar un tema conserva sus asignaciones anteriores; puede conservarse al corregir la misma publicación, pero no asignarse de nuevo. Reactivarlo permite nuevas asignaciones. No existe un borrado del historial desde la API.

Si otra persona guardó antes una versión, el servidor rechaza el cambio atrasado. El formulario conserva lo escrito; recarga y compara antes de guardar nuevamente. En SQLite, una persona con acceso directo al archivo conserva control sobre él: el historial de la aplicación no es un registro criptográfico a prueba de alteraciones.

## Estructura y pruebas

Se añaden cuatro tablas: `topics`, `article_reviews`, `review_topics` y `review_changes`, con referencias que vinculan temas, revisiones y noticias dentro del mismo proyecto. El inicio local prepara las tablas faltantes y el índice necesario; se probó la actualización de un esquema anterior sin cambiar su noticia existente.

La migración Alembic `003_manual_reviews` prepara esa estructura para PostgreSQL, políticas RLS forzadas, permisos por operación y rechazo de cambios al historial por el rol de ejecución. **No se aplicó a la nube.** El arranque de la futura versión de nube exige esa revisión y catorce tablas con RLS forzada; no debe desplegarse sobre el esquema anterior sin migrarlo.

Pruebas ejecutadas: 54 casos locales específicos de biblioteca, noticias, revisión y respaldo, además de 32 comprobaciones SQL de permisos y aislamiento en PGlite 0.5.10 (PostgreSQL 18.6 en WASM). Esta última prueba utiliza datos ficticios en memoria y no valida red, TLS, pool ni el servidor nativo 17.11 de Supabase. La aceptación sobre esa versión real queda para la fase de conexión. Referencias de diseño: [RLS de Supabase](https://supabase.com/docs/guides/database/postgres/row-level-security) y [políticas PostgreSQL 17](https://www.postgresql.org/docs/17/ddl-rowsecurity.html).

Se creó y comprobó una copia cifrada antes de esta actualización. `RESPALDAR_NEXO_DESARROLLO_LOCAL.bat` incluye automáticamente las nuevas tablas al generar la siguiente copia y ensaya su recuperación en otra carpeta. Es DPAPI del perfil Windows; la copia externa y recuperación ante pérdida de computadora siguen pendientes.

## Cómo sigue la arquitectura

| Bloque | Estado después de esta entrega | Próxima pieza |
|---|---|---|
| Identidad y acceso por proyecto | Existente y probado; local separado de nube | Aceptación final de MFA/revocación al publicar |
| Datos y archivo histórico | 45 secciones y sus totales conservados | Mantener procedencia y separar nuevos indicadores |
| Ingesta | Noticias guardadas, CSV y archivos manuales | Contratos reales por API, al conectar |
| Biblioteca | TXT/MD/CSV y fragmentos con citas | Extracción segura de PDF/XLSX y cobertura |
| Organización | Catálogo y revisión manual persistentes, con historial | Datos revisados para reportes y evaluación |
| Reportes | Resumen documental y contexto exportable existentes | Guardar versiones de reportes con sus fuentes |
| Recuperación para IA | Búsqueda textual local acotada | Muestra evaluada, abstención y fuentes contradictorias |
| Generación y embeddings | Interfaces preparadas, implementación desactivada | Adaptadores, presupuesto y evaluación autorizados |
| Operación | Copia cifrada y restauración local | Copia externa, monitoreo y ensayos finales |

La meta es completar flujos que funcionen localmente, con datos y pruebas, antes de las conexiones. Crear únicamente pantallas y botones no completaría esa arquitectura. La jornada final se reservará para configurar secretos, integrar adaptadores, migrar y aceptar el despliegue cuando las piezas locales estén listas; sigue dependiendo de permisos, proveedores y calidad de datos.

Actualización de aceptación: el usuario confirmó la aparición de la sección. La comprobación visual del asistente quedó impedida por la política de URL del navegador tras una conexión rechazada; no se intentó eludirla. La persistencia y el historial se verificaron con pruebas de base de datos, no mediante esa pestaña.
