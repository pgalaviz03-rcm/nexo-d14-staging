# NEXO + Atalaya · Comparación y primera integración

19 de octubre de 2026. Piloto D14. Presupuesto autorizado: **USD 0 / MXN 0**. Producción deshabilitada.

La recomendación es conservar NEXO como base y tomar de Atalaya su organización funcional. Ya quedó preparado un candidato con explorador y resumen documental; no se reemplazó la aplicación activa ni se desplegó esta integración en la nube.

## Qué se revisó realmente

Se revisaron visualmente las 23 páginas de `Atalaya_Referencia.pdf`, copia sin cambios del PDF entregado. La capa de texto tiene fuentes sin correspondencia Unicode utilizable; por eso se leyó el documento renderizado, no solo su extracción automática. SHA-256: `7292b154cade135610d6be38d8b7cd61ec479499d2ab884755ad60d57cc60996`.

El documento describe una especificación, una maqueta y una prueba previa de unos 240 comentarios. **No se entregaron aquí la maqueta, el CSV original ni el código de ese clasificador.** Sus cifras de 61% de comentarios negativos, tono 38/100 y 33% de sarcasmo son resultados declarados en el PDF, no revalidados en este trabajo ni incorporados como datos actuales de NEXO.

Las etiquetas «DECIDIDO», «PROPUESTA» e «INFERIDO» dentro del PDF son antecedentes documentales. No sustituyen las instrucciones del usuario en este chat ni autorizan gastos, extracción nueva, envío de mensajes o cambios de acceso.

## Comparación

| Área | NEXO comprobado | Aporte de Atalaya | Decisión |
|---|---|---|---|
| Base técnica | FastAPI, acceso por proyecto, MFA en nube, permisos/RLS y pruebas | Modelo de producto; el PDF reconoce que no hay backend construido | Conservar NEXO y Render + Supabase |
| Noticias | RSS seguro y carga manual; fuente/enlace/fecha | Un explorador común de piezas | Añadir filtros de servidor por periodo, fuente y origen |
| Briefing | Aún sin briefing real | Resumen diario narrativo y automatizado | Empezar por resumen documental manual con enlaces, sin IA |
| Temas y hechos | Búsqueda textual; los gráficos siguen siendo demo | Catálogos, revisión humana y agrupación | Diseñar etiquetas y trazabilidad antes de automatizar |
| Indicadores | No hay medición real de tono o emociones | Fórmulas de ánimo, percepción y alertas | Validar método; no presentar porcentajes inventados |
| Territorio | 45 secciones históricas preservadas | Ubicación de noticias y futuro cruce de bases | Mantener histórico separado; ubicación desconocida si falta evidencia |
| Redes sociales | Sin conectores activos | CSV, extractores y webhooks | Requiere muestra autorizada y adaptación específica; no implementado ahora |
| Recuperación | Respaldo SQLite cifrado y restauración probados | Atalaya propone reutilizar la base de NEXO | Completar la copia externa de nube, todavía pendiente |

El CSV editable `NEXO_Atalaya_Backlog.csv` contiene 16 componentes, su estado, prioridad y criterios de aceptación.

## Primera integración preparada

Carpeta: `NEXO_Atalaya_Candidato_D14`. Es una copia de código separada, sin base privada ni credenciales en el ZIP.

- Periodos de **24 horas, 7 días y 30 días**, o todo el archivo. Se filtra en el servidor por fecha de publicación; si falta, por fecha de ingreso. Los periodos móviles excluyen fechas futuras. «Todo el archivo» muestra también los registros con fecha futura para permitir su revisión.
- Selección de fuente RSS y origen RSS/CSV, combinables con búsqueda textual. Los filtros conservan el proyecto autorizado y no permiten consultar noticias de otro proyecto mediante un ID de fuente ajeno.
- Máximo 100 publicaciones por consulta. El contador describe los resultados mostrados; no es un total de conversación pública ni garantiza recuperar todo el archivo.
- **Resumen documental sin IA**: corte UTC, filtros en la respuesta, conteo de la selección, medios y titulares con enlaces originales. Si hay más de 100 coincidencias, declara el truncamiento. Si no hay evidencia, devuelve cero registros sin redactar una explicación ficticia.
- La interfaz distingue fuentes registradas de fuentes activas. Los gráficos demostrativos permanecen identificados.

La pantalla normal sigue en http://127.0.0.1:8000. El candidato usa http://127.0.0.1:8001 y una copia privada de SQLite creada con la operación de respaldo de SQLite; no modifica la base activa. La copia conserva las noticias disponibles al crearla, no se actualiza automáticamente. La lectura RSS externa y la IA están apagadas en esta vista de prueba.

Para verlo en esta computadora, abre `PROBAR_NEXO_ATALAYA.bat`, conserva la nueva ventana y entra al puerto 8001 con la cuenta local. No cierres la ventana habitual del puerto 8000. El iniciador depende del entorno Python preparado en este espacio de trabajo. No publiques la base privada ni la carpeta `work/private`.

## Pruebas y límites de la entrega

- **22 pruebas aprobadas:** 14 de consultas y límites, búsquedas literales, fechas faltantes/futuras, separación entre proyectos y comprobación de membresía en las funciones de ruta; ocho de diagnóstico seguro de RSS.
- Sintaxis JavaScript aprobada con Node. Hash de los datos históricos igual al del código NEXO actual. No se agregaron tablas, permisos, credenciales ni proveedores.
- La primera ejecución de pytest no pudo crear su carpeta temporal fuera del espacio permitido. Se corrigió la ubicación del directorio de prueba y las 22 pruebas finalizaron correctamente.
- La vista iniciada desde la herramienta no fue accesible en el navegador: conexión rechazada. Se detuvo ese proceso y se entregó el iniciador para Windows. **El usuario confirmó después el ingreso y el funcionamiento de filtros de últimos siete días/fuente y del resumen con titulares y enlaces, sin errores. La herramienta no pudo observar esa pestaña por su política de URL; esta aceptación se atribuye al usuario.**
- La CI ya aprobada del repositorio corresponde al NEXO v0.5 activo, no a este candidato. Se creó la rama `nexo-atalaya-explorador` para ejecutar las comprobaciones completas del candidato; no se despliega automáticamente. No se afirma que el candidato haya pasado todavía la CI completa, PostgreSQL/RLS o MFA de nube. Antes de reemplazar staging: abrir la vista, probar filtros/resumen en navegador, ejecutar la CI completa y comprobar el aislamiento en PostgreSQL.
- No hay migraciones nuevas: solo consultas acotadas sobre las tablas existentes. La autenticación y la membresía siguen siendo dependencias de cada ruta; no se añadieron vistas ni funciones privilegiadas. Referencia técnica: [RLS y permisos en Supabase](https://supabase.com/docs/guides/database/postgres/row-level-security).

## Qué debe corregirse antes de adoptar el resto del PDF

1. **Ánimo no equivale a opinión representativa.** El promedio de tonos de contenidos seleccionados describe esa muestra, no la población del estado o del distrito. Se necesitan cobertura, tamaño de muestra, faltantes, revisión humana y fórmula versionada.
2. **Interacciones no son alcance observado.** La ponderación logarítmica propuesta es un proxy elegido por diseño; no demuestra audiencia real. Una reacción de Facebook tampoco demuestra por sí sola la emoción de una persona.
3. **Confianza del modelo no es precisión medida.** Se necesita una muestra etiquetada por personas, evaluación por campo y posibilidad de «desconocido». Los ejemplos previos no sustituyen esa evaluación.
4. **Ubicación requiere evidencia.** No asignar una noticia al D14 porque mencione Aguascalientes ni inferir domicilio de autores. Los datos electorales de 2024 se conservan como archivo histórico independiente.
5. **Fuera de esta integración:** perfiles individuales de afinidad o lealtad política, listas de activación de personas y persuasión política por colonia o segmento personal. La alternativa utilizable es el análisis agregado de contenidos y fuentes públicas, con revisión humana.

## Costos y siguiente secuencia

El PDF cita USD 130–190/mes para un escenario reducido y USD 290–430/mes para uno completo; son estimaciones del documento, **no cotizaciones actuales verificadas ni gasto autorizado**. También cita USD 34–45 para un NEXO futuro de pago. El entorno actual permanece gratuito. No se contrataron Apify, IA, Vercel, mensajería, dominio ni cron.

1. **Hecho:** registrar y sincronizar los medios en local; ambos activos, diez publicaciones cada uno, veinte en total. Se creó otro respaldo cifrado y se restauró después de incorporarlas.
2. **Preparado:** candidato de explorador y resumen documental; aceptación funcional confirmada por el usuario; completar CI antes de integrarlo en staging.
3. **Prioridad operativa paralela:** copia externa de la base de nube y prueba aislada de recuperación, incluyendo alcance de Auth y medición de RPO/RTO. El respaldo local no cubre Supabase.
4. **Después:** catálogo manual de temas y revisión de evidencia. Para aprovechar el trabajo anterior de Atalaya hacen falta su maqueta editable y una muestra minimizada del CSV, sin nombres ni enlaces de perfiles personales. No se infiere el formato ni se inventan filas.
5. **Etapa posterior, con decisión separada:** conectores autorizados y clasificación de contenido con presupuesto y evaluación. No se activa IA por el mero hecho de estar descrita en el PDF.

## Estado de fuentes por entorno

| Entorno | El Heraldo | Hidrocálido | Noticias |
|---|---|---|---:|
| Local activo | Activo, 10 publicaciones | Activo, 10 publicaciones | 20 |
| Nube, última comprobación | HTTP 202, 0 publicaciones | Activo, 10 publicaciones | 10 |

Las bases son independientes. La causa interna de la respuesta HTTP 202 en nube no quedó establecida; no se eludieron controles del medio. Los resultados locales constan en `NEXO_RSS_LOCAL_RESULTADO.json` y la evidencia visual adjunta. Los históricos siguen en **45 secciones, 41,984 votos territoriales y lista nominal 65,378**.

Actualización de aceptación: el usuario confirmó ingreso, filtros de periodo/fuente y resumen documental con titulares y enlaces sin errores. No se efectuó observación directa de esa pestaña por la herramienta. El nuevo intento de batería completa local se detuvo al quedar sin resultados; no cuenta como aprobado. Rama de revisión: `nexo-atalaya-explorador`; CI completa pendiente.
