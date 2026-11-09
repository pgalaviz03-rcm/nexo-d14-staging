# NEXO · Revisión de Briefing

20 de octubre de 2026 · Entrega local. **Pulso aceptado visualmente por el usuario. Lectura de Briefing aceptada; guardado y habilitación pendientes de comprobación humana.**

## Para qué sirve

Briefing permite leer el corte de un proyecto sin recorrer todas las pestañas: publicaciones recientes, señales del contenido observado en Pulso, temas asignados y pendientes de revisión. Todo procede del archivo local. No genera opiniones, recomendaciones o textos con IA.

Cada cuenta conserva el mismo alcance por proyecto que en Pulso. La cuenta D14 no puede abrir el Briefing de otro cliente. La cuenta de plataforma accede mediante sus membresías administrativas. No se necesita añadir claves ni conectar proveedores para esta revisión.

## Comprobar la pantalla

1. Detén la ventana del servidor 8002 con Ctrl+C y vuelve a abrir **ABRIR_NEXO_DESARROLLO_LOCAL.bat** en outputs. Entra con tu cuenta LOCAL habitual.
2. Abre **Briefing**. El periodo inicial es **Últimos 7 días**. Deben aparecer una primera lectura, cuatro indicadores, notas con enlaces y fechas, señales de Pulso y pendientes de revisión. Cambia a 24 h y vuelve a 7 días: es correcto que los conteos varíen o que un corte esté vacío.
3. Comprueba que el proyecto sigue siendo D14. La biblioteca y los informes completos están en el desplegable inferior, separados de los conteos del periodo.

En la comprobación de esta entrega, el D14 tenía **16 notas dentro de los últimos siete días**, de las cuales se muestran las ocho más recientes. El total guardado sigue siendo 20 noticias. El corte se mueve con el tiempo; esos números no son constantes ni valores que deban escribirse en la interfaz. No había menciones reales importadas en Pulso, por lo que el tono y la evaluación insuficientes se muestran con guion; las cifras de demostración de Pulso no entran en Briefing.

## Comprobar el guardado, después de revisar la lectura

Con administrador, editor o analista:

1. Escribe un título y, si hace falta, una nota editorial breve. Usa **Guardar borrador en Reportes**.
2. En Reportes debe aparecer el corte, su periodo, cifras, nota y fuentes seleccionadas. El corte guardado es de consulta; para incorporar cambios se prepara otro desde Briefing.
3. Administrador o editor puede **habilitarlo para lectores** desde Reportes. Guardar no lo habilita por sí solo. Un lector no verá el borrador.

Si las fuentes o datos cambiaron desde la consulta, el servidor rechaza el guardado y pide actualizar el corte. La nota escrita se conserva. Si cambias de proyecto con una nota sin guardar, se pide decidir si se descarta. Al confirmar el cambio se limpian los datos y formularios anteriores.

**Descargar JSON** exporta el corte visible y la nota actual. Descargar no guarda una versión en la base ni habilita lectores. No hay envíos por correo o mensajería.

## Qué significan las cifras

| Elemento | Universo y límites |
|---|---|
| Notas | Noticias del proyecto con fecha dentro del periodo. Sin fecha de publicación se usa ingreso y se indica. Inicio incluido, fin excluido |
| Revisión registrada | Notas con estado «revisada». Una revisión editorial no certifica veracidad |
| Menciones | Pares publicación–actor de Pulso real, mismo periodo, todos los canales y actores activos. No se suman a las notas para afirmar un total único |
| Tono | Fórmula y muestra mínima de Pulso. Describe contenido clasificado; no opinión de una población |
| Alertas | Reglas activadas en el corte. Sin evaluación suficiente se muestra guion, no «cero riesgo» |
| Temas | Etiquetas manuales en noticias del periodo; una noticia puede tener varias. Hasta ocho temas visibles |
| Fuentes | Conteos periodísticos por medio, hasta veinte medios visibles. No equivalen a audiencia o alcance |
| Biblioteca | Número total de archivos del proyecto; no recibe el filtro de fechas ni aporta texto automáticamente a este corte |

Las notas se ordenan por fecha. Se muestran hasta ocho notas y hasta seis fuentes de publicaciones de Pulso. Los conteos se calculan sobre el universo del corte; los fragmentos son una selección, no una copia completa del corpus. Se conservan hasta cinco alertas en la lista y se indica si hubo límites. No se interpreta una etiqueta emocional como estado psicológico de una persona.

## Estructura preparada para después

`app/briefing.py` construye un paquete de evidencia versionado por contrato (`local_documentary_briefing_v1`). Reúne proyecto, ventana UTC, indicadores, cobertura, citas con hashes y pendientes. El texto de una fuente se trata como dato literal, nunca como instrucciones de un agente.

`app/briefing_api.py` añade:

- `GET /api/projects/{pid}/briefing?start=ISO_UTC&end=ISO_UTC`: corte vivo autenticado; devuelve filtros y huella de la evidencia.
- `POST /api/projects/{pid}/briefing/reports`: acepta solo `start`, `end`, `preview_sha256`, `title` y `note`. Recalcula las fuentes en el servidor, rechaza un corte desactualizado y guarda un borrador.

No se aceptan citas ni cifras enviadas por el navegador para construir el informe. El servidor guarda las cifras y fuentes seleccionadas junto con la nota manual en las tablas existentes de Reportes. La huella protege la integridad del archivo, no la veracidad de las fuentes. El tamaño máximo de cada versión es 64 KiB y la nota admite 2000 caracteres.

En SQLite las consultas de un corte usan una transacción de lectura. El guardado obtiene el bloqueo de escritura antes de recalcular; una base ocupada pide reintentar. No se añadió esquema ni se tocaron `app/main.py` o `app/knowledge.py`.

Para conectar APIs después, las nuevas observaciones deberán entrar por los adaptadores del proyecto y su normalización; Briefing consumirá esas mismas tablas. Para una síntesis RAG futura, el contrato entrega evidencia acotada con citas y cobertura. Falta evaluar recuperación, extracción documental, referencias, contradicciones, vigencia, abstención, límites y permisos antes de activar un modelo. Esta entrega no incluye generación automática, lectura programada ni entrega matutina.

## Verificación de esta entrega

- **156 pruebas Python aprobadas**, incluidas 22 específicas de Briefing: permisos, proyectos ajenos, fechas, conteos, corte vacío, límites, hash, cambio de fuentes, guardado, habilitación para lectores, transacciones y recuperación.
- **11 comprobaciones del controlador de Briefing** en DOM simulado, además de las de Pulso y Reportes: texto literal, roles, notas sin guardar, exportación, errores y respuestas tardías.
- JavaScript y hash de seguridad del script integrado comprobados.
- Lectura real del corte D14 comprobada sin modificar ninguna fila privada; respaldo cifrado y recuperación aislada verificados.
- Se conservan 26 tablas y la migración futura 005. Las 73 comprobaciones SQL anteriores siguen como antecedente; esta entrega no cambia políticas ni ejecuta una migración en nube.
- Lectura visual aceptada por el usuario; recorrido humano de guardado y habilitación pendiente. La herramienta mantiene la limitación previa de acceso al navegador local y no la ha evadido. No se ejecutó de nuevo la suite HTTP completa ni aceptación nativa de PostgreSQL.

## Siguiente pantalla

Tras aceptar la lectura y el guardado de Briefing, seguimos con **Actores**: identificar la persona principal, sus comparativos públicos y las cuentas o fuentes autorizadas de cada uno, siempre dentro del proyecto correspondiente. Las integraciones externas siguen para la fase final.
