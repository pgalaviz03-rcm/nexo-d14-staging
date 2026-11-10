# NEXO · Corte diario y actualización del superadministrador

Fecha: 10 de noviembre de 2026. Horario fijo: 08:00 America/Mexico_City (Aguascalientes, UTC−6). El disparo inicia la recopilación; el nuevo corte está disponible cuando termina. Un retraso del programador o de la fuente puede retrasar su disponibilidad.

## Comportamiento

El botón «Actualizar datos» aparece en la cabecera exclusivamente al superadministrador. El permiso también se comprueba en servidor. Cada proyecto tiene su propio corte compartido: todos sus lectores consultan lo guardado, sin iniciar extracciones al entrar, recargar o cambiar filtros. Los proyectos nuevos participan en el mismo horario sin copiar cuentas ni datos del D14.

La actualización manual tiene máximo dos solicitudes por proyecto y día, separación mínima de una hora y bloqueo mientras exista otra en curso. El corte automático tiene una clave única por fecha y proyecto. Una entrega repetida del programador no duplica trabajo. Los trabajos abandonados se marcan interrumpidos y no se repiten automáticamente; se preserva el archivo previo. El estado público muestra el último corte realmente completado.

## Ejecución y alcance de esta entrega

El ejecutor actual actualiza las fuentes RSS del proyecto mediante el adaptador existente, con validación de dominio, IP pública, TLS, límites de tamaño y tiempo, y deduplicación por enlace. Máximo cinco fuentes por corte. No genera análisis de IA ni resultados sociales ficticios.

Los conectores de Facebook seleccionados para la siguiente activación son:

| Función | Actor de referencia |
|---|---|
| Publicaciones, reacciones y comentarios agregados por publicación | apify/facebook-posts-scraper |
| Texto de comentarios y acciones observadas | apify/facebook-comments-scraper |
| Seguidores y datos públicos de cuenta | apify/facebook-pages-scraper |
| Quién reaccionó, si Facebook lo permite | scraper_one/facebook-reactions-scraper |

La selección de reacciones exige una prueba de cobertura: no sustituir el contador agregado por identidades inventadas, no interpretar registros ausentes como falta de participación y no inferir afinidad política. Las plataformas pueden ocultar parte de los participantes. Los conectores pagados permanecen cerrados; guardar un token no los activa. Para activarlos se requiere implementar/verificar la transformación de sus respuestas y aprobar el presupuesto y los límites del lote. El botón y el programador no eluden ese cierre.

## Programador externo

GitHub Actions usa 0 14 * * * (08:00 local), un ejecutor Ubuntu estándar y máximo tres minutos por disparo; no sube artefactos ni cachés. El workflow solo ejecuta el trabajo cuando NEXO_DAILY_REFRESH_ENABLED=true. Mantenerlo falso hasta verificar la cuota gratuita, presupuesto de sobreconsumo cero, código desplegado y migración aplicada. No se contrató Render Cron ni se modificó un medio de pago.

La identidad entre GitHub y NEXO es OIDC de corta duración: emisor, firma RS256, audiencia, ID inmutable de repositorio, rama main, workflow exacto y tipo de evento se verifican. El token solo admite solicitar el corte diario; no da acceso a documentos, sesiones de usuarios ni a otras API. No se guarda una clave de Supabase, de base de datos o de Apify en Actions. El operador configurado debe seguir activo y conservar su PlatformGrant; se comprueba en cada ejecución.

config/refresh_scheduler.json identifica esta instancia, su repositorio y el operador ya existente. Para otra instalación se configura el archivo antes del despliegue. El repositorio de esta instancia no implica que sus proyectos deban llamarse D14.

GitHub permite retrasos o pérdida de disparos programados, especialmente al inicio de la hora. Este mecanismo no es una garantía de ejecución al segundo. Para una exigencia contractual de disponibilidad exactamente a las 08:00 se necesita evaluar un programador con SLA y presupuesto separado.

## Esquema y publicación

La migración aditiva 012_project_refresh crea project_refresh_runs, con RLS habilitada y forzada. Los miembros solo leen los cortes de sus proyectos; únicamente el propietario solicita y actualiza trabajos. No se pueden reasignar proyecto ni operador desde el rol de ejecución. No altera documentos, informes, usuarios ni históricos.

Para actualización progresiva, el código admite 011 y 012. Mientras siga 011, la función nueva permanece cerrada. Desplegar primero el código; después aplicar 012 y comprobar RLS y la revisión. main.py y knowledge.py se mantienen intactos.

Se creó una instantánea cifrada de las 40 tablas de negocio antes del cambio y se comprobó el descifrado. No acredita una restauración completa de Auth/MFA o Storage. El respaldo anterior de nube continúa en el Drive privado; conservar su clave aparte.

## Pruebas

Las pruebas cubren horario anual UTC−6, corte compartido, bloqueo de lectores, duplicados, caducidad segura, separación de proyectos, revocación del operador, errores parciales, topes manuales y firmas OIDC. La interfaz se prueba con respuestas simuladas sin ejecutar proveedores. Las pruebas PostgreSQL WASM comprueban las políticas y privilegios, sin acreditar TCP o TLS. El resultado de nube y su captura se registran aparte al publicar.

## Aviso previo de seguridad del proveedor

El asesor de Supabase reporta que la protección de contraseñas filtradas está deshabilitada en Auth. Es una condición previa; esta entrega no cambia la autenticación. Revisar disponibilidad y costo antes de activarla: https://supabase.com/docs/guides/auth/password-security#password-strength-and-leaked-password-protection .
