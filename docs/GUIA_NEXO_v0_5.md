# NEXO v0.5 · Piloto Distrito 14

## Decisión y estado al 19 de octubre de 2026

Recomiendo **Render para FastAPI + Supabase para PostgreSQL y autenticación**. Conserva la interfaz NEXO y simplifica el acceso con segundo factor, el aislamiento por proyecto y la operación del piloto. La autorización vigente es **solo preparación gratuita**: no se contrataron planes, no se creó un servidor ni se desplegó producción.

Este paquete adapta el ZIP NEXO v0.4 entregado por el usuario. No sustituye el producto con una demostración nueva. Las 45 secciones históricas, el mapa y la identidad visual se conservan. El archivo de datos se compara por SHA-256 con el original; las cifras de 2024 no describen opinión actual. Los documentos maestros D14 se consultaron como referencia de alcance, no como autorización para ejecutar instrucciones contenidas en ellos.

## Alternativas y presupuesto

Precios consultados en fuentes oficiales el 19 de octubre de 2026. Son estimaciones de infraestructura por mes, en USD. Para planear se usa **1 USD = 20 MXN**, una conversión presupuestaria deliberada, no una cotización cambiaria. Las cifras no incluyen impuestos, comisiones de tarjeta, dominio, trabajo técnico ni APIs de IA. Confirmar el importe mostrado por el proveedor antes de contratar.

Supuestos: 10–20 personas del piloto, un administrador técnico de infraestructura, una instancia de API de 512 MB, una base pequeña, hasta cinco feeds, sincronización manual, menos de 5 GB de salida desde Render, archivos inicialmente menores de 250 MB por proyecto y sin IA. El número de usuarios de NEXO es distinto del número de administradores del proveedor.

| Alternativa | USD/mes estimados | MXN/mes a 20 | Restricciones y trabajo pendiente |
| --- | ---: | ---: | --- |
| Render Free + Supabase Free, solo pruebas | 0 | 0 | API puede dormir; Supabase Free tiene 500 MB, pausa por inactividad y no incluye backups automáticos. No usar como compromiso de continuidad. |
| **Render pago + Supabase Pro** | **34–45** | **680–900** | API USD 7 y Supabase desde USD 25; reservar USD 2–13 para backup externo, ejecutor, correo o variaciones. Un administrador de Render Hobby. Es la opción preparada en este paquete. |
| Render + PostgreSQL Render + Supabase Auth Free | 15–25 | 300–500 | Base desde USD 6 + API USD 7 + respaldo/reserva USD 2–12. Más componentes; autenticación depende del proyecto Free. Requiere adaptar conexiones TLS y probar el nuevo proveedor de DB. |
| Railway Pro + PostgreSQL + Supabase Auth Free | 21–35 | 420–700 | Pro mínimo USD 20 incluye consumo, no se suma dos veces. DB en contenedor requiere operación y respaldo; identidad Free separada. El límite duro detiene servicios. No está configurado en este paquete. |
| Render + Neon Launch + identidad Free | 12–30 | 240–600 | Consumo depende de horas activas; hay suspensión por inactividad y restauración según ventana elegida. Integrar y probar identidad/conexión si se cambia de arquitectura. |

La alternativa económica con base Render usa Supabase solo para identidad; no incluye una base Supabase Pro. Las estimaciones de Railway y Neon tampoco suman un Supabase Pro. Si se exige que la identidad use un plan de pago, añadir su costo correspondiente o seleccionar la arquitectura recomendada.

**Desglose recomendado:** USD 7 API + USD 25 PostgreSQL/identidad + USD 1–3 de almacenamiento de respaldos + USD 1–3 de ejecutor de backup + USD 0–7 de margen operativo = USD 34–45. Es una provisión, no una factura ni un límite garantizado. Mantener RSS manual evita otro proceso permanente. Monitoreo inicial desde el panel del proveedor; un monitor externo debe autorizarse y configurarse después.

Si varias personas necesitan administrar Render, el plan Pro de workspace agrega **USD 25/mes** al cómputo: el escenario pasa a aproximadamente USD 59–70 / MXN 1,180–1,400. Si staging usa otro proyecto Micro en la misma organización Supabase Pro, prever aproximadamente **USD 10/mes adicionales**. Para ahorrar, staging queda en proyecto Free separado, con datos de prueba; no confundir esquemas distintos con entornos independientes.

**Cálculos de sensibilidad:** Railway publica memoria a USD 0.00000386/GB/s y CPU a USD 0.00000772/vCPU/s. Con 730 horas, 0.75 GB medios, 0.05 vCPU media, 1 GB de volumen y 5 GB de salida, el consumo orientativo es cercano a USD 9; en Pro se paga al menos USD 20. Un consumo real mayor aumenta la factura. Neon Launch publica USD 0.106/CU-h y USD 0.35/GB-mes: 0.25 CU × 4 h/día × 30 días ≈ USD 3.18 de cómputo; encendido continuo durante 730 h ≈ USD 19.35. Añadir API, almacenamiento, historial, respaldos y otras partidas. Los rangos no son límites de uso.

Fuentes oficiales: [Render precios](https://render.com/pricing), [referencia oficial de tamaños y costos](https://render.com/articles/production-rails-hosting-guide), [planes de workspace Render](https://render.com/docs/new-workspace-plans), [Supabase precios](https://supabase.com/pricing), [Supabase control de costos](https://supabase.com/docs/guides/platform/cost-control), [Railway precios](https://railway.com/pricing), [Railway límites](https://docs.railway.com/pricing/cost-control), [Neon precios](https://neon.com/pricing).

## Arquitectura inicial

```text
Navegador del usuario
  └── HTTPS Render · Interfaz NEXO + FastAPI · 1 proceso / 1 instancia
        ├── Supabase Auth del mismo entorno · contraseña + TOTP
        ├── PostgreSQL Supabase · TLS verificado · usuario nexo_app
        │     ├── identidad local vinculada a UUID del proveedor
        │     ├── membresías y roles por project_id
        │     ├── históricos, noticias, cuotas y bitácora con RLS
        │     └── archivos pequeños en dataset_blobs, dentro de PostgreSQL
        └── RSS · dominios exactos aprobados + DNS e IP fijados + HTTPS

Administrador → credencial de migración separada → Alembic y altas explícitas
Backup → pg_dump + age → bucket privado fuera de la base
IA → desactivada; sin proveedor, claves ni llamadas
```

La API y los archivos estáticos comparten origen para simplificar sesiones y controles de origen. No se necesitan Redis, Kubernetes ni un worker permanente en este piloto. Los archivos pequeños se guardan en PostgreSQL para evitar pérdida en disco efímero y mantener el control por proyecto. Al superar 250 MB, planear almacenamiento de objetos privado y descargas autorizadas por proyecto antes de elevar el límite.

**Entornos:** local con SQLite y usuarios de prueba; staging con API y proyecto Supabase propios; producción con otro proyecto Supabase, otras claves, usuarios y copia independiente. Ningún secreto ni copia de datos personales de producción entra en staging. La plantilla de producción arranca bloqueada con `NEXO_RELEASE_APPROVED=false`.

Usar regiones cercanas entre ambos proveedores; se propone Virginia/este de EE. UU. si está disponible. Confirmar residencia autorizada antes de cargar información privada. El alojamiento de aplicación, la identidad y la base no son una red privada entre proveedores: viajan por Internet con TLS. El navegador nunca recibe la contraseña de DB ni una clave de servicio.

## Cambios implementados

- Se conservan el diseño NEXO, el visor y `data/secciones_2024.json`. La suma del paquete sigue siendo 41,984 votos territoriales y lista nominal 65,378. Las ocho boletas anticipadas solo se suman al total si el conjunto completo coincide con la base original; no se asignan a una sección.
- `002_nexo_v05` protege también usuarios y membresías. El rol web no puede cambiar permisos, cuentas, proyectos ni históricos. Los roles de lectura no pueden insertar documentos o noticias aunque se intente fuera de la API. Los archivos y sus padres, y los artículos y sus feeds, deben pertenecer al mismo proyecto.
- La identidad se aplica en cada transacción. Un `commit` de sincronización no elimina la identidad de las operaciones siguientes; al regresar una conexión al pool no se conserva el actor anterior.
- Sesiones de nube en cookies `__Host-`, `Secure`, `HttpOnly`, `SameSite=Strict`. Se verifican firma asimétrica, emisor, audiencia, caducidad, rol y segundo factor del JWT. No se guardan refresh tokens ni tokens de nube en almacenamiento del navegador. El login local firmado permanece solo para desarrollo.
- La pantalla incluye inscripción/verificación TOTP y cierre de sesión. La vinculación entre usuario y UUID del proveedor se hace explícitamente con administración, sin dar acceso por coincidencia de correo.
- Cabeceras CSP con hash del script, bloqueo de marcos, no caché, no referrer y HSTS en nube. Host y Origin exactos, cuerpos acotados antes de procesar archivos, espera de carga limitada y límites de solicitudes.
- RSS conecta a una IP pública previamente resuelta y validada, conservando el hostname para SNI y certificado. No vuelve a resolver para conectar. Bloquea IP privadas/locales/metadatos, credenciales en URL, puertos alternos, redirecciones, compresión y entidades XML externas. Máximo 2 MB y 80 entradas por captura.
- Archivos de nube en `dataset_blobs`; no se publican directorios de carga. Cuotas y disparadores de PostgreSQL limitan tamaño de archivos y acumulación. La exportación histórica se autoriza en servidor y queda en bitácora.
- Las plantillas no contienen secretos reales. Auto deploy y previews permanecen desactivados. La imagen web usa usuario sin privilegios y una sola instancia con concurrencia limitada.

Referencias de diseño de seguridad: [RLS PostgreSQL](https://www.postgresql.org/docs/current/ddl-rowsecurity.html), [RLS Supabase](https://supabase.com/docs/guides/database/postgres/row-level-security), [prevención SSRF OWASP](https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html), [JWT Supabase](https://supabase.com/docs/guides/auth/jwts), [TOTP Supabase](https://supabase.com/docs/guides/auth/auth-mfa/totp).

## Límites de arranque

| Control | Valor inicial | Cómo se aplica |
| --- | --- | --- |
| API | 300 solicitudes/minuto globales | Memoria, una instancia. No sustituye protección de la plataforma frente a ataques. |
| Login y segundo factor | 20 solicitudes/minuto globales | Memoria y límites del proveedor de identidad. |
| Procesamiento simultáneo | 8 conexiones de aplicación | Servidor web; un proceso. |
| Consulta SQL | 8 segundos | Ajuste de conexión PostgreSQL. |
| Archivo | 12 MB; 250 MB acumulados por proyecto | API y disparadores SQL; rechazo de nuevos archivos sin borrar históricos. |
| Cargas y exportaciones | 20 diarias por proyecto y operación | Contador diario persistente; los intentos también cuentan. |
| Fuentes RSS | 5 por proyecto | API y disparador SQL. |
| Sincronización RSS | 96 intentos diarios/proyecto; al menos 60 s por fuente | Cuota persistente y bloqueo de fila para el intento. |
| Noticias | 50,000 por proyecto | Disparador SQL; conservación hasta archivo autorizado. |
| IA | 0 llamadas | Configuración rechaza habilitarla en nube. |

Al escalar a varias instancias, trasladar los límites en memoria a un gateway o almacén compartido. Las cuotas de PostgreSQL ya son atómicas entre instancias. Separar la ingestión en worker con identidad de servicio limitada al proyecto antes de automatizar RSS. No ejecutar un worker con la cuenta propietaria.

Supabase Spend Cap cubre determinadas partidas y **no es un techo monetario total**: cómputo, ramas y extras pueden quedar fuera. Mantenerlo activo, no activar autoscaling ni addons y revisar consumo al inicio diariamente. Render tiene cómputo fijo por instancia pero salida y otras partidas pueden aumentar. Los USD 45 son presupuesto propuesto, no un corte automático de factura.

Para IA futura, reservar un presupuesto separado solo después de aprobación. Antes de habilitar un adaptador debe existir una reserva atómica de costo máximo por usuario/proyecto/mes, tope de tokens y concurrencia, registro de uso real, cierre al agotar presupuesto, evaluación de evidencias y aislamiento de cachés y embeddings. Esa integración no está implementada ni cobrada aquí.

## Conectar cuentas sin gastar

1. Iniciar sesión personalmente en [Render](https://dashboard.render.com/) y [Supabase](https://supabase.com/dashboard), con MFA para los administradores. No compartir contraseñas, tokens, códigos ni medios de pago en el chat.
2. Mantener los planes Free mientras siga vigente la autorización gratuita. No activar Supabase Pro, Render pago, IPv4 adicional, branching, PITR ni el cron de backup.
3. Preparar un repositorio privado de la organización. Revisar `.gitignore` y el contenido del ZIP antes de subirlo. Conectar Render solo a ese repositorio; no conceder acceso a todos los repositorios.
4. Para una prueba alojada gratuita, crear únicamente el entorno staging después de confirmar cuentas y repositorio. Las plantillas están listas, pero esta sesión no creó cuentas ni recursos. Registrar la URL y referencia observadas de cada proyecto; no adivinarlas.
5. Una vez conectado, el único paso inmediato pendiente del usuario es avisar **“cuentas listas para staging gratuito”**. El operador puede introducir secretos directamente en los paneles. No hace falta decidir IA, dominio propio ni pagar ahora.

## Despliegue de staging paso a paso

Los comandos siguientes son para un operador técnico. Contienen marcadores; nunca pegar credenciales reales en un historial de chat.

1. Crear un proyecto Supabase dedicado de staging, sin datos personales. Desactivar registro público y la Data API para NEXO. Mantener Auth y TOTP activos. Usar claves de firma asimétricas y configurar duración del JWT en 900 segundos. No usar `anon`, `authenticated`, `postgres` o `service_role` como credencial de la API NEXO.
2. Obtener la CA y las cadenas de conexión desde Connect en ese proyecto. Para FastAPI usar el pooler **session**, puerto mostrado 5432. Para migraciones y backups, preferir conexión directa desde un ejecutor con IPv6; si solo hay IPv4, comprobar session pooler sin comprar el addon. No usar transaction pooler para esta entrega.
3. Crear el rol `nexo_app` con `deploy/provision_role.sql`. Fijar una contraseña aleatoria en el terminal interactivo con `\password nexo_app`; no editar el archivo SQL con la contraseña. El dueño de migración es otro rol.
4. Con la URL del dueño exclusivamente en `NEXO_MIGRATION_DATABASE_URL`, ejecutar desde la raíz del paquete:

```shell
python -m pip install -r requirements-dev.txt
python -m alembic upgrade head
```

5. Crear o invitar usuarios de prueba en Supabase Auth. Vincular el UUID observado y su proyecto explícitamente:

```shell
python scripts/bootstrap_cloud.py --subject UUID_REAL_DEL_USUARIO --email CORREO_AUTORIZADO --role admin
```

6. Crear un servicio Render Free mediante `deploy/render.staging.yaml`, seleccionado como ruta de Blueprint. Ajustar el contexto al directorio raíz del paquete. Introducir las variables `.env.example` en el panel de secretos; cargar la CA como Secret File. La única URL de DB en el servicio web debe usar `nexo_app`. No copiar allí `NEXO_MIGRATION_DATABASE_URL`, contraseñas del dueño, claves de servicio ni medios de pago.
7. Fijar `NEXO_PUBLIC_ORIGIN` a la URL real del servicio, sin ruta ni barra final. Conectar exclusivamente al Supabase de staging. La aplicación rechazará configuración incompleta o un usuario de DB con privilegios excesivos.
8. Ejecutar las pruebas de aceptación con dos usuarios/proyectos, segundo factor, carga y exportación. La primera inscripción TOTP muestra la clave solo al usuario autenticado; guardarla en su autenticador y no en capturas, logs o documentos de operación.
9. Solo después, elegir 2–3 RSS públicos autorizados y colocar sus dominios exactos en `NEXO_RSS_ALLOWED_HOSTS`. Confirmar cada URL y restricciones del editor. La lista comienza vacía y el paquete no hace capturas de red por su cuenta.

Conexión y certificados: [conexión Supabase](https://supabase.com/docs/guides/database/connecting-to-postgres), [SSL Supabase](https://supabase.com/docs/guides/platform/ssl-enforcement), [Data API](https://supabase.com/docs/guides/api/securing-your-api), [TLS Render](https://render.com/docs/tls).

## Migrar una instalación v0.4 existente

El ZIP recibido contiene código y datos históricos; no contiene una base de usuarios o carpeta de cargas de una instalación en uso. No se presume haber migrado datos privados que no fueron entregados.

Si existe una base PostgreSQL v0.4: detener escrituras, respaldar base y almacenamiento, verificar recuentos y duplicados por proyecto y SHA-256, y aplicar Alembic 002 primero en una copia aislada. Las restricciones nuevas fallan ante duplicados o referencias cruzadas; corregir con revisión humana, sin borrado automático. Las migraciones no sustituyen contraseñas ni sobrescriben métricas históricas. No reiniciar secuencias o recrear tablas sobre una instalación en uso.

Para las cargas de disco antiguas, tras aplicar 002 y con credencial de dueño, ejecutar `python scripts/migrate_uploads.py --legacy-root RUTA_AUTORIZADA`. El script comprueba ubicación, tamaño y SHA-256, conserva los originales y cambia los registros a almacenamiento de DB solo al confirmar la transacción. Probar restauración antes de retirar las copias originales.

Si la instalación real usa SQLite, se requiere una transferencia controlada de tablas, IDs, relaciones y secuencias a PostgreSQL; esta entrega no incluye un importador general de esa base no entregada. No copiar un archivo SQLite al servicio web como sustituto de PostgreSQL. Mantener v0.4 disponible en modo solo lectura hasta validar la copia y su aceptación.

## Secretos y sesiones

El repositorio y el ZIP solo contienen ejemplos. Guardar secretos en los paneles del entorno correspondiente; limitar la administración a las personas necesarias. Separar cuenta web, migración, backup y restauración. La clave `sb_publishable_` identifica el proyecto de Auth y no concede autoridad de servicio; las credenciales de DB sí son secretas.

Rotación: crear nueva contraseña para el rol web, actualizarla en Render y desplegar manualmente; confirmar readiness y pruebas de acceso; retirar la anterior. Rotar por separado claves de backup y de dueño. No imprimir URLs de conexión ni respuestas del proveedor de identidad. Un cambio de firma de IdP puede tardar hasta cinco minutos en reflejarse en la caché de JWKS; probar su procedimiento de revocación.

Las membresías y `users.active` se consultan en cada solicitud. Para retirar acceso inmediatamente, desactivar la cuenta local o quitar su membresía con el administrador y registrar el cambio en auditoría. El cierre de sesión borra cookies y solicita logout al IdP, pero un access token ya copiado puede seguir siendo válido hasta su expiración. Con JWT de 900 segundos, esa ventana debe contemplarse en la prueba de revocación. No se afirma invalidación instantánea de todos los tokens solo por cerrar sesión.

## Copias y recuperación

Objetivos iniciales propuestos: **RPO 24 horas y RTO 4 horas**, pendientes de ensayo; no son garantías obtenidas. Supabase Pro aporta copias diarias con retención indicada en su plan. Free no las incluye. No habilitar PITR de pago por defecto.

Además, preparar una copia externa cifrada del esquema `public` con datos y blobs: `scripts/backup.sh` usa `pg_dump`, `age` y un bucket privado. Solo la clave pública age va al ejecutor; custodiar la clave privada de recuperación fuera del servidor. La credencial de DB del ejecutor debe poder leer todo lo respaldado y se considera privilegiada: nunca usarla en la API web. El ejemplo IAM permite escribir en un prefijo; la cuenta de restauración necesita permisos de lectura distintos. Activar bloqueo de acceso público y retención/versionado en el bucket.

`deploy/render.backup.yaml` prepara un cron opcional diario a las 08:17 UTC. **No fue creado ni autorizado como gasto.** Proponer retención de siete diarios y cuatro semanales; configurarla y verificarla en el almacenamiento elegido antes de confiar en ella. El script de carga no elimina automáticamente copias. El nombre temporal y su checksum se transmiten sin incluir datos en los logs.

Restauración: crear una base aislada vacía y el rol `nexo_app` antes de restaurar. Verificar SHA-256, descifrar con la clave privada y usar `scripts/restore.sh` con `NEXO_RESTORE_CONFIRM=RESTORE_TO_EMPTY_ISOLATED_DB` y `NEXO_RESTORE_DATABASE` igual a `PGDATABASE`. Aplicar después `deploy/runtime_grants.sql`, ejecutar preflight y pruebas RLS, comprobar los 45 registros y hashes de archivos, y documentar tiempos y recuentos. No restaurar automáticamente encima de producción.

La copia externa del esquema `public` **no incluye** identidades internas de Supabase Auth, configuración del proveedor, secretos ni políticas del bucket. Recuperarlos con el respaldo administrado/procedimiento del proveedor y volver a vincular identidades si cambia el UUID. La recuperación completa exige ambas partes y su ensayo. [Respaldos Supabase](https://supabase.com/docs/guides/platform/backups).

## Monitoreo y operación

`/api/health` informa que el proceso responde; `/api/ready` comprueba la conexión a DB. El arranque de nube valida versión de migración, RLS forzado y privilegios del rol. `scripts/monitor.py` permite una sonda HTTPS de solo lectura. No hay monitor externo ni destinatario configurados en esta entrega.

Los registros de aplicación usan eventos con categoría de ruta, código HTTP y duración; no incluyen correos, contraseñas, tokens, consultas de usuario, nombres de archivos ni cuerpo de RSS. Los access logs del servidor se desactivan. Antes de publicar, comprobar también las opciones de registro de plataforma/DB y la retención disponible en el plan. La bitácora funcional puede contener IDs de usuario y proyecto; su acceso se rige por membresías y requiere retención definida.

Configurar alertas, con destinatario confirmado, para: tres fallos seguidos de readiness, 5xx sostenidos por encima del 2%, memoria superior al 80%, captura RSS degradada, respaldo de más de 26 horas o fallido, espacio DB al 70/85%, y presupuesto al 50/80/100%. En el entorno gratuito no mantener el servicio despierto artificialmente; documentar el arranque en frío. Una alerta de presupuesto no corta la factura por sí sola.

Antes de escalar, medir uso y latencia durante el piloto. Si la memoria supera 80% o la latencia crece, ajustar tamaño después de probar. Si crecen archivos, pasar a objetos privados; si crece RSS, aislar el worker; si crece el número de instancias, compartir el limitador y revisar conexiones. Cada cambio tiene presupuesto y prueba de aislamiento.

## Checklist de salida

- [ ] Cuentas conectadas, administrador con MFA y repositorio privado confirmado.
- [ ] Autorización explícita de gasto y responsable de facturación, si se activa pago.
- [ ] Staging y producción separados; solo datos autorizados en cada uno.
- [ ] Migraciones 001/002 ejecutadas sobre PostgreSQL real y privilegios mínimos verificados.
- [ ] Prueba de usuario A intentando leer/escribir archivos, noticias e históricos de B rechazada.
- [ ] Viewer rechazado al escribir; usuario web rechazado al cambiar permisos/históricos.
- [ ] Identidad reaplicada después de commit/rollback; sin fuga entre conexiones reutilizadas.
- [ ] Certificados HTTP/DB validados; CA correcta; HTTP redirige a HTTPS desde el borde.
- [ ] Login y TOTP reales probados; logout, expiración y retiro de membresía revisados.
- [ ] Cabeceras y CSP sin errores funcionales; formularios y exportación probados en navegador.
- [ ] URLs RSS autorizadas probadas; casos privados, redirecciones, DNS cambiante, XML y tamaño bloqueados.
- [ ] Cuotas, límites del proveedor, costos y comportamiento al agotarse revisados.
- [ ] Copia externa cifrada completa, restauración aislada y recovery de Auth ensayados.
- [ ] Alertas y destinatario confirmados; retención y recuperación de bitácora acordadas.
- [ ] Datos históricos y hashes comparados; ninguna información sensible empaquetada.
- [ ] Escaneo de dependencias e imagen repetido justo antes de publicar.
- [ ] Plan de rollback probado. No habilitar IA como parte de este despliegue.

Los puntos anteriores pendientes no se marcan como logrados por el mero hecho de existir archivos de configuración. `docs/PRUEBAS.md` registra qué se ejecutó localmente y qué sigue pendiente.

## Volver atrás

Detener nuevas escrituras y mantener el servicio anterior o la página de mantenimiento. Conservar la imagen y revisión previa; restaurar una copia en otra base si el cambio afecta datos. No ejecutar un downgrade destructivo de Alembic. Volver una imagen v0.4 a la base v0.5 no está validado: v0.4 desconoce las nuevas restricciones y el IdP. Para una reversión de versión, ensayar base y aplicación como conjunto y reconciliar escrituras antes de cambiar tráfico.
