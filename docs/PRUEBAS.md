# NEXO v0.5 · Evidencia de validación

Fecha: 19 de octubre de 2026. Estado: staging desplegado en planes Free; sin contratación de pago ni aceptación de producción. Las pruebas locales se documentan como evidencia anterior.

| Comprobación | Resultado | Alcance |
| --- | --- | --- |
| Batería Python | 39 aprobadas; 1 omitida | API y SQLite, reglas de acceso, cargas, RSS simulado, JWT criptográfico y gateway MFA simulado. |
| SQL de políticas y migraciones | 16 comprobaciones aprobadas | Motor PostgreSQL 18.6 en WASM mediante PGlite 0.5.10; se ejecutaron los grants y políticas de las revisiones Alembic sobre DDL compilado del modelo. |
| Dependencias fijadas | 33 revisadas; ninguna vulnerabilidad conocida reportada | Consulta pip-audit a registro público; informe JSON adjunto. No equivale a una auditoría completa de seguridad. |
| Integridad de históricos | Coincidencia byte por byte con v0.4 | SHA-256 en PROCEDENCIA.json; 45 secciones, 41,984 votos territoriales, lista nominal 65,378. |
| Interfaz local | Acceso y consulta histórica comprobados en navegador | Diseño NEXO, 45 filas, mapa y detalle de sección. Captura adjunta sin datos de usuarios reales. |
| Sintaxis | Python y JavaScript aprobados | Compilación de módulos y comprobación del script del navegador. |
| Configuración | Sintaxis YAML/JSON aprobada; contrato del Blueprint revisado con documentación oficial | No se validó mediante la API de Render ni se creó un recurso. |

Las siete pruebas originales de v0.4 también forman parte de las 39 aprobadas. La advertencia de Starlette sobre una futura sustitución del transporte de pruebas httpx se conserva en el resultado; no fue un fallo de prueba.

Las pruebas SQL comprueban actor ausente, separación A/B, lectura de viewer, rechazo de escritura por viewer, bloqueo de cambios a membresías e históricos, aislamiento de blobs, limitación de columnas de actualización y limpieza del actor al confirmar la transacción. Esta prueba usa el motor PostgreSQL compilado a WASM; **no demuestra conexión psycopg, pool de red, TLS, Supavisor ni una migración sobre el PostgreSQL del proveedor**.

`test_postgres.py` quedó omitida porque esta máquina no tiene un PostgreSQL TCP de prueba configurado ni Docker disponible. El flujo `.github/workflows/security.yml` prepara una base PostgreSQL 16 desechable, aplica Alembic y verifica identidad tras commit/rollback y ausencia de fuga en el pool. Después se ejecutó en GitHub: la ejecución #3 terminó Success en 58 segundos, sobre el commit 73a22186d049844b798a140ebd3ad9cfb864b52b. Incluyó Alembic y la integración psycopg/RLS/pool en PostgreSQL 16 desechable. La primera ejecución falló al iniciar el contenedor por comillas del health check; se corrigió y las dos siguientes pasaron.

El flujo de contraseña y TOTP se validó con respuestas de proveedor simuladas y JWT firmados con claves de prueba. Falta comprobar creación/invitación de usuarios, enrolamiento, revocación, expiración y correos contra un proyecto Supabase real. No se utilizaron contraseñas, correos ni claves reales de usuarios.

## Pendiente antes de habilitar el piloto público

1. Cuenta administrativa inicial y verificación completa de acceso real al D14. Alembic y el pool ya pasaron en PostgreSQL TCP de CI; el esquema equivalente se aplicó mediante migración nativa de Supabase.
2. Revisión de vulnerabilidades de la imagen y fijación de digest aprobado si se requiere reproducibilidad completa. La imagen ya se construyó y arrancó en Render. El runtime Python está fijado por versión; las imágenes base son etiquetas y pueden actualizarse.
3. Login y TOTP reales del proveedor, expiración y revocación. TLS/CA, Data API desactivada, registro cerrado y rol mínimo ya se verificaron en el staging.
4. Prueba de carga, cuotas bajo concurrencia y disponibilidad frente a suspensión/arranque en frío.
5. RSS reales autorizados y pruebas de red con TLS, cambios de DNS y fallas de fuentes.
6. Backup cifrado, permisos del bucket, restauración completa con identidad Auth y medición de RPO/RTO.
7. Alertas, destinatario, costos y autorización explícita antes de activar planes o servicios de pago.

No hay escaneo de un servidor público, certificado emitido para NEXO, respaldo ejecutado en nube ni prueba de recuperación cumplida. Los checklist de la guía se mantienen pendientes hasta completar estas verificaciones.

## Reproducir las pruebas de SQL locales

Con dependencias Python instaladas y Node.js, desde la raíz del paquete:

```shell
python scripts/export_policy_sql.py --output work/rls-schema.sql
cd tests
npm install
node rls.pglite.mjs ../work/rls-schema.sql
```

`export_policy_sql.py` compila el esquema actual y ejecuta las operaciones de políticas de las revisiones para generar un SQL exclusivo de pruebas. No inspecciona una base v0.4 existente y no sustituye `alembic upgrade head`. No ejecutar ese SQL sobre una base en uso.


## Comprobación del staging real

- Render Free: `https://nexo-d14-staging.onrender.com`, servicio `srv-dbb87tu1egvs73dmckr0`, proyecto NEXO D14 Staging y entorno Staging.
- Despliegue `dep-dbb88b1jfumc73esj2rg` activo. El primer arranque se bloqueó por falta de NEXO_PUBLIC_ORIGIN; se guardó la URL asignada por Render y se desplegó de nuevo.
- `/api/ready` devolvió `{"status":"ready","version":"0.5"}` en navegador. `/api/projects` y `/api/projects/1/sections` devolvieron `{"detail":"Sesión requerida"}` sin sesión; `/docs` devolvió Not Found.
- Supabase mostró dos conexiones `nexo_app` con TLSv1.3 y TLS_AES_256_GCM_SHA384. La aplicación arrancó tras su verificación de rol y RLS; su URL exige `sslmode=verify-full` y la CA instalada como archivo privado de configuración.
- CA Supabase Root 2021: firma propia válida, vigencia hasta 2031-04-26, SHA-256 `807025ad50d4ed219d2c9c7d299c004f824eb00cf7f65afef607d07b72e6cafa`.
- JWKS del proyecto: ES256 / P-256 disponible. Data API desactivada. Registro público cerrado. TOTP habilitado y SMS desactivado. Site URL de Auth configurada al HTTPS exacto de NEXO.
- Los históricos mantienen 45 secciones; no se cargaron datos de identidad de ciudadanos.
- Esto no acredita todavía un login real con MFA, una prueba de carga ni una restauración completa de respaldo. La conexión local de prueba falló por DNS del entorno; la conexión real Render–Supabase sí se observó por TLS en el proveedor.

Ejecución CI: https://github.com/pgalaviz03-rcm/nexo-d14-staging/actions/runs/39317567177 .
