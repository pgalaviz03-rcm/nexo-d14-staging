# NEXO + Atalaya · Aceptación y despliegue

19 de octubre de 2026. USD 0 / MXN 0. Staging gratuito; producción deshabilitada.

El usuario confirmó ingreso y filtros de siete días/fuente y resumen documental en la copia local del puerto 8001. La herramienta no observó esa pestaña por la política de URL del navegador; esa aceptación corresponde al usuario.

[PR #1](https://github.com/pgalaviz03-rcm/nexo-d14-staging/pull/1) fusionada en main, commit `9f67ec8585e7c88ec260e702e61a1ea66d22e164`. [CI de main](https://github.com/pgalaviz03-rcm/nexo-d14-staging/actions/runs/39340220621) aprobada. La batería del candidato registró 69 pruebas de aplicación y una de PostgreSQL/RLS/pool, con una prueba nativa Windows omitida en Linux; migraciones y auditoría de dependencias aprobadas. Los 22 casos locales previos se solapan con esa batería y no deben sumarse.

Render Free: despliegue `dep-dbba8gdg1s2s73862phg`, Live. `/api/ready` respondió ready, versión 0.5. En la sesión autenticada real de nube se verificaron filtros siete días + Hidrocálido + RSS, ocho resultados y ocho registros con titulares/enlaces en el resumen documental. Origen CSV produjo cero registros y resumen vacío. Evidencia: `NEXO_Atalaya_Staging_verificado.png`.

Antes y después: 45 secciones, 41,984 votos territoriales, lista nominal 65,378, dos fuentes, diez noticias, una membresía y diez tablas con RLS forzada. Conexiones de aplicación observadas con TLS 1.3. No hubo cambio de esquema, permisos, proveedor ni presupuesto.

El Heraldo sigue con HTTP 202 en nube; Hidrocálido está activo. La copia local previa permanece independiente y conserva veinte noticias. El ZIP integrado excluye bases y secretos.

Pendiente: exportación cifrada real de Supabase, verificación de recuperación y copia externa en Drive; recuperación de Auth/MFA en otro proyecto. Tener una carpeta de Drive creada no acredita un respaldo. Ver `NEXO_Respaldo_Nube/GUIA.md`.
