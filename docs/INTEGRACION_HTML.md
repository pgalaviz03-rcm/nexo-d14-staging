# NEXO · Integración local del nuevo diseño

19 de octubre de 2026 · Copia de desarrollo del puerto 8002

Se adaptaron `static/index.html`, `app/integration_ports.py` y `app/workspace_api.py` sobre la copia local actual. El tercero se recibió como texto en esta conversación. `app/main.py` y `app/knowledge.py` conservan exactamente sus bytes anteriores, comprobados por SHA-256. También se conserva `app/models.py`: el adjunto de modelos omite las tablas y referencias de temas, revisiones e historial que ya están en uso.

## Qué se aprovechó

- Diseño, navegación y organización de NEXO + Atalaya, con vista completa y simplificada. Cambiar la vista solo cambia la presentación; los permisos los sigue comprobando la API.
- Atalaya como entrada al archivo, radar y revisión documental.
- Ficha documental con citas: reúne extractos textuales del proyecto y permite descargar un JSON. No utiliza un modelo de lenguaje ni verifica automáticamente la veracidad de las fuentes.
- Biblioteca, RSS guardados, filtros, resumen periodístico, temas, notas, historial y mapa D14 existentes. Se preservan las etiquetas de demostración en los gráficos ficticios.

No se incorporaron perfiles electorales, simulación u optimización de mensajes políticos para segmentos, puntuaciones arbitrarias de sentimiento, supuestos ahorros de tokens ni conexiones a Ollama. No se creó la caché propuesta: las consultas no se persisten y cada ficha refleja la recuperación actual. La auditoría registra únicamente la acción y cantidad de citas.

## Cómo cargarlo

1. Detén con Ctrl+C la ventana del servidor que usa el puerto 8002.
2. Abre `ABRIR_NEXO_DESARROLLO_LOCAL.bat` en la carpeta outputs y conserva abierta su ventana.
3. Entra en `http://127.0.0.1:8002`, actualiza con Ctrl+F5 e inicia sesión con tu cuenta local habitual.
4. Abre **Ficha documental**, consulta un término presente en tus noticias y revisa los enlaces. Busca después una palabra inexistente: debe avisar que no hay coincidencias.
5. Comprueba que **Temas y revisión** conserve el catálogo y permita guardar una revisión y consultar su historial.

Esta actualización no cambia la cuenta ni la contraseña local. La aplicación del navegador necesita el reinicio para usar la nueva ruta y renovar su política de scripts. La revisión visual y el recorrido completo de esta nueva pantalla siguen pendientes; la herramienta de navegador tuvo un bloqueo de política de URL en la sesión anterior y no se intentó eludirlo.

## Acuerdo para trabajar en paralelo

Puedes continuar con textos, distribución visual y propuesta de pantallas. Envía el HTML completo como candidato y una lista corta de cambios. Conservaré las rutas y componentes funcionales al integrarlo; revisaremos cada dependencia antes de añadirla. No incluyas claves, contraseñas, datos personales ni información ficticia presentada como medición real.

La API local actual conserva:

| Ruta | Uso |
|---|---|
| `GET /api/projects/{pid}/workspace` | Conteos y conectores desactivados |
| `POST /api/projects/{pid}/knowledge/context` | Contexto textual con citas |
| `POST /api/projects/{pid}/knowledge/critical-audit` | Ficha de extractos; nombre de ruta compatible con el candidato recibido |
| `POST /api/projects/{pid}/knowledge/answer` | Devuelve 409; generación desactivada |
| `/api/projects/{pid}/topics` y `/reviews` | Temas, revisión e historial existentes |

Las dos consultas documentales aceptan `question` de 2 a 240 caracteres, `limit` de 1 a 8, `source_kind` igual a `all`, `news` o `documents`, y `days` igual a 0, 1, 7 o 30. Campos adicionales se rechazan. Siempre requieren sesión y membresía del proyecto.

La ficha devuelve `mode=local_documentary_digest`, `status=fragments_found` o `no_matches`, `answer=null`, `ai_used=false`, `external_calls=0`, `from_cache=false`, `citations`, `coverage` y una nota de alcance. Los textos de las fuentes se muestran como texto, sin ejecutar sus instrucciones ni su HTML. Las citas conservan fuente, extracto, hash y enlace cuando existe.

No existen rutas de perfiles o ingesta social en esta integración. Las siguientes tareas de arquitectura son guardar reportes versionados, evaluar la recuperación y preparar la extracción de PDF/XLSX. La generación con IA, embeddings, APIs autorizadas y publicación se mantienen para la fase final.

## Comprobaciones

64 pruebas Python aprobadas: 10 nuevas de integración y 54 de biblioteca, RSS, revisión y respaldo. Sintaxis de los dos scripts JavaScript aprobada. Los elementos y rutas de navegación del HTML tienen identificadores únicos y coinciden con sus controladores. Se comprobó que los archivos protegidos no cambian y que las 45 secciones, 41,984 votos territoriales y 65,378 registros de lista nominal permanecen en la base local.

Estas pruebas usan rutas y base de datos directamente; no sustituyen la aceptación del flujo HTTP en navegador. Las pruebas SQL anteriores de PostgreSQL WASM no se repitieron, pues esta actualización no cambia esquema ni políticas. Sigue pendiente probar la migración final en PostgreSQL nativo antes de publicar. No se desplegó ni se modificó la nube; no se activaron servicios de pago.
