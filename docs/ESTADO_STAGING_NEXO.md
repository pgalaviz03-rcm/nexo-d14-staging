# NEXO D14 · Estado del piloto gratuito

Actualizado el 19 de octubre de 2026. **USD 0 / MXN 0 autorizados. Producción no habilitada.**

## Acceso y despliegue

- [NEXO D14 Staging](https://nexo-d14-staging.onrender.com): acceso de administrador del D14 con contraseña y autenticador comprobado; la recarga recupera la sesión vigente.
- [Render](https://dashboard.render.com/web/srv-dbb87tu1egvs73dmckr0): Docker Free, Virginia, 0.1 CPU/512 MB; despliegue manual. Estado observado: Live, `dep-dbba8gdg1s2s73862phg`, código `9f67ec8585e7c88ec260e702e61a1ea66d22e164`.
- [Repositorio privado](https://github.com/pgalaviz03-rcm/nexo-d14-staging): Render autorizado exclusivamente para este repositorio.
- Supabase Free, región us-east-1. API de datos y registro público desactivados; TOTP habilitado y SMS desactivado. No se contrataron funciones de pago.

## Escucha digital real

El usuario autorizó los dos medios. Se guardó la lista exacta de dominios en Render y se comprobó desde la aplicación con sesión y MFA.

| Medio | Resultado real | Publicaciones guardadas |
|---|---|---:|
| Hidrocálido Digital | Activo; sincronización manual comprobada | 10 |
| El Heraldo de Aguascalientes | Error HTTP 202; no entregó una respuesta RSS válida al servidor | 0 |

Dos fuentes registradas y una activa. No se conoce la causa interna de la respuesta de El Heraldo. No se eludieron sus controles. Los errores conservan los registros anteriores. No hubo grupos de enlaces duplicados; el extracto más largo mide 353 caracteres, dentro del límite de 360.

Las noticias son información pública general: no se verificó que cada hecho ocurriera dentro del D14. Los gráficos de tono y conversación siguen siendo demostrativos. **IA apagada y actualización manual**, sin cron ni avisos recurrentes.

La copia local conserva su propia base. El usuario confirmó el reinicio y se registraron y sincronizaron ambos medios: **20 publicaciones, diez por fuente, ambas activas**. Se verificaron en el navegador y se creó/restauró otro respaldo cifrado local después de la lectura. Las credenciales de nube y local son independientes. Ver `NEXO_RSS_LOCAL_RESULTADO.json`.

## Datos y seguridad verificados

- Históricos conservados: **45 secciones, 41,984 votos territoriales, lista nominal 65,378**. Incluyendo ocho votos anticipados: 41,992 votos. Proceden del paquete v0.4; no se revalidó externamente su fuente electoral.
- Conexión real de aplicación a PostgreSQL con TLS 1.3 y CA verificada. Rol restringido `nexo_app`, máximo seis conexiones, sin superusuario ni bypass RLS.
- Diez tablas con RLS habilitada y forzada. Pruebas de aislamiento y permisos realizadas con rollback; el rol de ejecución no modifica identidades ni históricos.
- Sin sesión, las consultas privadas requieren autenticación; `/docs` cerrado. Ingreso real con MFA y consulta histórica comprobados.
- RSS: HTTPS, lista exacta de dominios, direcciones públicas y conexión fijada, validación de certificado, sin redirecciones ni proxies; límite 2 MB/80 elementos por lectura, cinco fuentes por proyecto, 96 intentos diarios y 60 segundos entre intentos por fuente. Los fallos consumen cuota.
- [CI final aprobada](https://github.com/pgalaviz03-rcm/nexo-d14-staging/actions/runs/39340220621): pruebas Python, migraciones, PostgreSQL desechable, RLS/pool y auditoría de dependencias. Pruebas locales específicas: nueve de respaldo, 26 de seguridad/RSS y ocho de diagnóstico seguro aprobadas. La batería ASGI local se interrumpió al quedar detenida; se verificó en CI.

## Integración Atalaya en nube

[PR #1 fusionada](https://github.com/pgalaviz03-rcm/nexo-d14-staging/pull/1). Filtros por 24 horas, siete días, treinta días, fuente y origen; resumen documental manual con enlaces y máximo 100 registros. En sesión real de nube se comprobaron siete días + Hidrocálido + RSS: ocho resultados y ocho registros en el resumen. Origen CSV: cero resultados y resumen vacío, sin relato inventado. No hubo migraciones ni nuevos permisos. La copia local habitual del puerto 8000 conserva su versión anterior; la copia de prueba 8001 es independiente.

## Respaldo local comprobado

Se creó una copia cifrada con Windows DPAPI del SQLite local, la clave de sesión y los archivos cargados referenciados. Se restauró en una carpeta nueva y se verificaron integridad, relaciones y totales sin sobrescribir la base activa. También se probó la restauración por la herramienta de línea de comandos.

La protección está asociada al perfil de Windows y normalmente a esta computadora. No es una copia externa ni incluye la base de Supabase. Usa `RESPALDAR_NEXO_LOCAL.bat` para generar otra copia y su ensayo aislado; el resultado se guarda en el área privada del espacio de trabajo. No se configuró una programación automática.

## Preparación de copia externa

Se creó [NEXO_D14_Respaldos_Cifrados](https://drive.google.com/drive/folders/1sajcw1VvbDLlSsNY2rmYqBkmg7ZCNjgt) en el Drive privado elegido por el usuario. Metadatos verificados: sin compartir, solo propietario. Está vacía: todavía no se exportó Supabase ni se subió un respaldo. `RESPALDAR_NEXO_NUBE.bat` solicita la contraseña de base de datos en la consola local, cifra la exportación y ensaya el esquema público en una base desechable. La recuperación completa de Auth/MFA queda pendiente. Ver `NEXO_Respaldo_Nube/GUIA.md`.

## Pendiente

1. Respaldo cifrado externo de nube y ensayo aislado con medición de RPO/RTO; el ensayo local no cubre Supabase ni la recuperación ante pérdida de esta computadora.
2. La activación local ya se comprobó. Revisar El Heraldo en nube cuando vuelva a ofrecer una respuesta RSS utilizable; conservar Hidrocálido como fuente comprobada.
3. Aceptación de carga/cuotas concurrentes, expiración/revocación de sesión y monitoreo externo. No se cerró la sesión humana para forzar pruebas.
4. Producción futura con recursos, credenciales, presupuesto y aceptación separados. Render Free puede suspenderse por inactividad; no se activó un plan de pago.

Supabase informa un aviso: detección de contraseñas filtradas desactivada, función [reservada a Pro o superior](https://supabase.com/docs/guides/auth/password-security#password-strength-and-leaked-password-protection). El TOTP y el registro cerrado siguen activos. La contraseña y los códigos de nube fueron ingresados por el usuario; no se leyeron ni exportaron.

## Entregables

- `NEXO_v0_5_Paquete_Despliegue_D14.zip`: fuente editable, migraciones, pruebas y guías, sin secretos reales.
- `NEXO_RSS_PRUEBAS_RESULTADO.json`: resultado de cada fuente y límites.
- `NEXO_RESPALDO_LOCAL_RESULTADO.json`: comprobación de la copia local y restauración.
- `NEXO_DESPLIEGUE_RESULTADO.json`: estado técnico actualizado.
- `NEXO_RSS_resultado_verificado.png`: evidencia visual de las fuentes y diez publicaciones.

Los secretos están en el área privada y en los controles del proveedor. El ZIP excluye base activa, contraseñas, claves de sesión y respaldos privados. No repetir la instalación inicial SQL sobre esta base existente.
