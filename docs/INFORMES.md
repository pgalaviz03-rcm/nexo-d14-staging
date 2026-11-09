# NEXO · Informes locales con versiones y fuentes

19 de octubre de 2026 · Piloto D14 · Puerto 8002

NEXO incorpora informes persistentes y una entrada más sencilla: **Resumen, Explorar, Territorio, Informes y Fuentes**. La biblioteca y la revisión siguen disponibles dentro del recorrido. El resumen utiliza conteos del archivo; las métricas ficticias anteriores quedan fuera del menú principal.

## Abrir esta actualización

Detén con Ctrl+C la ventana del servidor del puerto 8002. Abre `ABRIR_NEXO_DESARROLLO_LOCAL.bat` desde outputs, deja su ventana abierta y actualiza `http://127.0.0.1:8002` con Ctrl+F5. Usa tu cuenta local habitual. No se cambió la contraseña ni hace falta una cuenta de nube.

La actualización local añadió únicamente tres tablas: informes, versiones y habilitaciones de lectura. Se conservan usuarios, noticias, archivos, temas, revisiones e históricos. Hay respaldo cifrado antes y después, con recuperación comprobada en otra carpeta.

## Primer informe

1. Entra en **Informes** y elige **Nuevo informe** o **Preparar informe** desde el resumen.
2. Escribe título, tema y una nota del autor. Puedes probar `FONACOT`, que tiene una noticia guardada en el archivo local; no depende de leer internet.
3. Pulsa **Guardar borrador**. El servidor busca los fragmentos y conserva sus citas; el navegador no puede inventar las fuentes que se guardan.
4. Abre el informe, revisa la nota, los extractos y sus enlaces. Una cita no certifica la veracidad del contenido.
5. Para corregirlo, cambia la nota o la consulta y pulsa **Guardar nueva versión**. Las versiones anteriores permanecen consultables.
6. Un editor o administrador puede pulsar **Habilitar para lectores del proyecto**. Esto habilita esa versión dentro de este entorno; no publica en internet ni envía mensajes.
7. **Ver versiones** permite consultar el historial. Una versión histórica se abre como solo lectura. **Descargar informe** conserva la versión elegida en JSON con las citas y su huella.

También puedes buscar en Biblioteca y elegir **Preparar un informe de este tema**. Guardar vuelve a consultar el archivo actual; la evidencia definitiva es la que muestra la versión guardada. Si no hay coincidencias, no se guarda un informe sin fuentes.

## Permisos actuales

| Membresía del proyecto | Preparar versiones | Habilitar lectura | Consultar informes |
|---|---|---|---|
| admin / editor | Sí | Sí | Borradores e historial |
| analyst | Sí | No | Borradores e historial |
| viewer | No | No | Solo versiones habilitadas |

Los permisos se verifican en la API. Una nueva versión no cambia automáticamente la versión habilitada: los lectores siguen viendo la anterior hasta que se revise y habilite la nueva. Las lecturas de versiones, historial y exportaciones aplican el mismo filtro.

Esta separación corresponde al **módulo de informes**. Todavía no implementa un perfil completo de candidato ni un superadministrador global: los permisos existentes de noticias y biblioteca se conservan. La asignación de esos perfiles de producto queda en la hoja de ruta.

## Evidencia y límites

Cada versión conserva título, nota del autor, consulta, filtros, fragmentos, fuentes, cobertura, fecha de preparación y SHA-256 del contenido serializado. Los textos se muestran literalmente; no se ejecuta HTML ni instrucciones incluidas en documentos. No hay red, IA generativa, caché de consultas ni opiniones sintéticas de electores en este flujo.

La recuperación mantiene los límites de la biblioteca: hasta 200 noticias, 20 documentos, 400 candidatos, ocho citas y 10,000 caracteres de contexto. El formulario usa cinco citas y todo el periodo por defecto. Los informes admiten 50 versiones y un contenido serializado máximo de 64 KiB. La lista muestra hasta 100 informes e indica truncamiento. PDF/XLSX siguen pendientes de extracción.

La huella permite detectar cambios accidentales. El propietario del archivo SQLite puede modificarlo, por lo que no equivale a firma digital ni a historial criptográficamente inalterable. La API no ofrece actualización o borrado de versiones guardadas ni de habilitaciones. Las políticas futuras de PostgreSQL niegan esas operaciones al rol de aplicación.

## Validación

90 pruebas Python aprobadas: 25 del nuevo módulo y 65 de regresión. Siete recorridos del controlador de informes pasaron en un DOM simulado, incluyendo guardado, habilitación, nueva versión, histórico de solo lectura, exportación y controles de lector. Los tres scripts JavaScript pasaron sintaxis y se comprobó la política de scripts del servidor.

48 comprobaciones SQL aprobadas sobre PostgreSQL 18.6 en PGlite WASM, incluidas las tres tablas nuevas y sus permisos de lectura/habilitación. Esto no sustituye la aceptación con PostgreSQL nativo, TLS, pool y autenticación final. La migración `004_reports` y los permisos están preparados; no se ejecutaron en Supabase.

La comprobación visual de esta nueva pantalla sigue pendiente. La herramienta de navegador tuvo antes un bloqueo de política de URL y no se intentó eludirlo. No se repitió la suite HTTP completa en este entorno. Las pruebas y el respaldo no incluyen una publicación web nueva.

DPAPI protege el respaldo con este perfil Windows y normalmente esta computadora. La custodia externa y recuperación fuera del equipo siguen pendientes. Los documentos históricos de staging en la carpeta describen una versión anterior y no prueban el despliegue del código local actual.

## Recursos técnicos

- Servidor: `app/report_api.py`; instalado solo con el espacio de trabajo local explícitamente activado.
- Datos: `Report`, `ReportVersion`, `ReportRelease`, con referencias compuestas por proyecto.
- Migración futura: `migrations/versions/004_reports.py`; preflight exige 17 tablas con RLS forzado.
- Interfaz: `static/reports.js`; mantiene formularios y fuentes como texto seguro.
- Pruebas: `tests/test_reports.py` y ampliación de `tests/rls.pglite.mjs`.
- `app/main.py` y `app/knowledge.py` permanecen idénticos a la versión anterior.
