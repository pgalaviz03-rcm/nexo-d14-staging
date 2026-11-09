# NEXO · Actualización del desarrollo local al staging existente

Estado: candidato separado. Esta preparación no equivale a despliegue, migración remota ni aceptación de producción. La copia local del puerto 8002 queda intacta.

## Destinos existentes

- Render: nexo-d14-staging, servicio srv-dbb87tu1egvs73dmckr0, plan Free.
- Supabase: wxucnydbquvzurythrfs, organización NEXO D14 Staging, plan Free.
- GitHub: pgalaviz03-rcm/nexo-d14-staging, privado.
- Versión remota observada antes de actualizar: 9f67ec8585e7c88ec260e702e61a1ea66d22e164. No contiene los avances locales posteriores.

## Cambios del candidato

El nuevo punto de entrada app.cloud_main:app instala los módulos de trabajo sobre las mismas dependencias de autenticación y sesión de la API existente. main.py y knowledge.py conservan sus bytes locales validados. No se finge entorno local para saltar controles.

La migración Alembic 011_workspace_cloud completa seis tablas: capturas de publicaciones, integrantes y acciones del equipo, configuración cifrada de integraciones, medios y referencias de sus publicaciones. Son 40 tablas privadas con RLS habilitada y forzada. No expone tablas a anon, authenticated o service_role ni usa funciones SECURITY DEFINER. Solo modifica políticas y permisos de las tablas conocidas de NEXO.

El superadministrador puede crear proyectos, vincular identidades existentes de Supabase y asignar membresías. La contraseña y el autenticador permanecen en Supabase. El servidor no recibe la clave service_role, no administra contraseñas del proveedor, no puede conceder PlatformGrant y no puede cambiar auth_subject, hashes o históricos. Las membresías del propietario se sincronizan en nuevas sesiones; un consultor sigue en lectura aunque tenga una etiqueta histórica admin/editor/analyst.

Los archivos cargados permanecen en PostgreSQL mediante DatasetBlob. El disco efímero de Render se usa solo para procesos temporales. No copiar SQLite al contenedor ni iniciar init_demo.py en nube.

## Comprobaciones antes del cambio

1. Abrir PREPARAR_NEXO_NUBE.bat en outputs. Usa el entorno y PostgreSQL portátil ya existentes; no instala servicios ni ejecuta llamadas de IA.
2. El primer paso crea un PostgreSQL nuevo en 127.0.0.1, con contraseña aleatoria, aplica Alembic y prueba el rol real nexo_app, los permisos y las rutas nuevas. Solo datos ficticios; detiene esa base al terminar.
3. Si pasa, pide la contraseña de BASE DE DATOS de Supabase en la consola local, exporta por TLS, cifra y ensaya la recuperación del esquema NEXO. No modifica la base de nube.
4. Confirmar en NEXO_RESPALDO_NUBE_RESULTADO.json public_restore_verified=true y la fecha de esta ejecución. El archivo cifrado debe guardarse fuera de esta computadora, separado de su clave de recuperación. Auth/MFA y los objetos Storage requieren comprobación adicional.

La herramienta de este chat no pudo completar PostgreSQL TCP: hubo bloqueo de socket y tiempos de espera. No se cuentan esos intentos como pruebas aprobadas. Las comprobaciones PostgreSQL WASM validan SQL/RLS, pero no prueban sockets, libpq, TLS, pool ni el ciclo real de Alembic. Debe pasar la ejecución nativa o la CI antes de modificar Supabase.

## Aplicación controlada

- Revisar el borrador de código y completar pruebas nativas. La CI del candidato es manual, con límite de 20 minutos por job: confirmar minutos incluidos y límite de gasto cero antes de ejecutarla.
- Tener respaldo externo vigente y un procedimiento de restauración ensayado.
- Revisar y autorizar la ampliación concreta de permisos de administración: crear proyectos, vincular identidades y gestionar membresías, exclusivamente para el PlatformGrant del propietario.
- Con credenciales de migración temporales, aplicar Alembic hasta 011_workspace_cloud. El contenedor usa solo nexo_app; no recibe la contraseña postgres ni una clave service_role.
- Provisionar el PlatformGrant para la cuenta ya vinculada del propietario, verificando correo y auth_subject en Supabase. No promover consultores ni copiar las claves locales.
- Añadir NEXO_INTEGRATIONS_ENCRYPTION_KEY y NEXO_DELIVERY_ENCRYPTION_KEY independientes en secretos de Render y conservar recuperación privada. No pegarlas en GitHub ni en el chat. Preservar DATABASE_URL restringida, sslmode=verify-full y la CA existente.
- NEXO_ENV=staging, NEXO_STORAGE_MODE=database, NEXO_AI_ENABLED=false. No marcar producción ni activar trabajos de proveedores.
- Despliegue manual del commit exacto aprobado. Comprobar ready, login con MFA, Configuración de propietario, consulta de otra cuenta, aislamiento entre proyectos y carga durable de un archivo de prueba.

## Datos de la copia local

Este paquete es código: no contiene bases, documentos privados, integrantes, destinos o credenciales. El traslado de datos locales requiere comparar el contenido de nube, remapear los identificadores y conservar las referencias de informes, documentos y fuentes. No restaurar SQLite encima de Supabase ni sobrescribir históricos. La subida de código por sí sola no traslada los datos del piloto local.

## Reversión

Las migraciones son aditivas pero cambian la revisión requerida por el preflight. Volver al contenedor antiguo sin restaurar una base compatible no basta: el arranque antiguo exige su propia revisión Alembic. No usar un downgrade destructivo ni borrar tablas en el proyecto original. La reversión se prepara con el respaldo verificado y una restauración aislada; después se cambia la conexión a la copia compatible. Mantener el staging anterior sin cambios hasta que estén listas las comprobaciones.

## Límites de esta entrega

No conecta Apify, IA, correo, Telegram ni WhatsApp, no programa envíos y no contrata recursos. El almacenamiento de claves solo prepara adaptadores futuros. WhatsApp sigue sin programador ni conector de envío. La revisión visual y el acceso real con MFA posteriores al despliegue siguen pendientes.
