# Verificación de Pulso y plataforma

Desde la carpeta del código y un entorno local de prueba con NEXO_LOCAL_WORKSPACE=true, usa pytest para test_pulse.py junto con los módulos de informes, revisión y biblioteca. Emplea una base y directorio temporal separados; no credenciales reales.

`node tests/check_pulse_ui.mjs` comprueba controladores JavaScript en un DOM simulado con datos ficticios. No prueba el renderizado en un navegador.

Para las políticas: instala las dependencias de tests/package.json en el entorno de pruebas; genera SQL con `python scripts/export_policy_sql.py --output work/rls-schema.sql` y ejecuta `node tests/rls.pglite.mjs work/rls-schema.sql`. Ese SQL es solo para una base nueva desechable WASM: nunca se aplica sobre una base de datos existente. No sustituye Alembic ni la aceptación con PostgreSQL nativo, TLS o pooler.

El resultado entregado identifica comprobaciones realmente ejecutadas y limitaciones. Los respaldos sintéticos conservan datos y alcance; DPAPI se comprueba aparte en el respaldo privado del workspace.
