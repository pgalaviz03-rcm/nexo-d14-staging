# NEXO v0.5 · Evidencia de validación

Fecha: 19 de octubre de 2026. Estado: preparación local, sin despliegue ni contratación.

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

`test_postgres.py` quedó omitida porque esta máquina no tiene un PostgreSQL TCP de prueba configurado ni Docker disponible. El flujo `.github/workflows/security.yml` prepara una base PostgreSQL 16 desechable, aplica Alembic y verifica identidad tras commit/rollback y ausencia de fuga en el pool. Ese flujo fue preparado, no ejecutado en GitHub en esta sesión.

El flujo de contraseña y TOTP se validó con respuestas de proveedor simuladas y JWT firmados con claves de prueba. Falta comprobar creación/invitación de usuarios, enrolamiento, revocación, expiración y correos contra un proyecto Supabase real. No se utilizaron contraseñas, correos ni claves reales de usuarios.

## Pendiente antes de habilitar el piloto público

1. Migraciones Alembic completas en PostgreSQL TCP y Supabase, con roles reales y el test del pool.
2. Construcción/arranque de imágenes y revisión de vulnerabilidades de la imagen; fijación de digest aprobado si se requiere reproducibilidad completa. El runtime Python está fijado por versión; las imágenes base son etiquetas y pueden actualizarse.
3. Autenticación y TOTP del proveedor, TLS/CA reales, configuración de Data API, registro cerrado y roles mínimos.
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
