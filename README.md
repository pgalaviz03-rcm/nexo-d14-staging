# NEXO v0.5 · Distrito 14 Aguascalientes

Adaptación del paquete NEXO v0.4 entregado por el usuario. **Solo preparación gratuita autorizada. No desplegado.**

Empieza por [la guía completa](docs/GUIA_NEXO_v0_5.md), [los resultados de pruebas](docs/PRUEBAS.md) y [las decisiones editables](DECISIONES.json).

La recomendación es Render + Supabase, con staging gratuito aislado y una propuesta futura de USD 34–45/mes (MXN 680–900 a un tipo presupuestario de 20, antes de impuestos y extras). No hay credenciales reales en este paquete.

## Uso local

Con Python 3.12 y terminal dentro de esta carpeta:

```shell
python -m pip install -r requirements.txt
python iniciar.py
```

El inicio local conserva la creación de una cuenta de prueba en la máquina. No usar sus credenciales en nube. Para una base SQLite v0.4 existente, respaldarla y aplicar `python -m alembic upgrade head` antes de iniciar; no se aplica automáticamente sobre datos en uso.

## Verificación

```shell
python -m pip install -r requirements-dev.txt
python -m pytest -q tests
```

La prueba `test_postgres.py` requiere una base PostgreSQL TCP vacía y dedicada con las variables indicadas en su encabezado; no apuntarla a producción. El flujo de CI prepara PostgreSQL 16 y ejecuta migraciones y comprobaciones del pool. Que exista el flujo no significa que GitHub Actions ya lo haya ejecutado.

## Archivos principales

- `deploy/render.staging.yaml`: plantilla gratuita, auto deploy desactivado.
- `deploy/render.production.yaml`: plantilla de pago bloqueada; no autorizada.
- `.env.example`: variables y separación de credenciales, sin secretos.
- `migrations/versions/002_cloud_security.py`: RLS, grants mínimos, cuotas y blobs durables.
- `scripts/bootstrap_cloud.py`: vinculación explícita de identidades, membresía y históricos.
- `scripts/backup.sh`, `restore.sh`: copia cifrada y restauración aislada, pendientes de ensayo real.
- `scripts/migrate_uploads.py`: traslado verificable de archivos antiguos, conserva originales.
- `docs/PROCEDENCIA.json`: hashes y alcance de los datos conservados.

La guía contiene el checklist, conexiones, TLS, secretos, límites, monitoreo, escenarios de costo y rollback. La interfaz conserva NEXO y las 45 secciones; las pantallas de simulación conservan sus etiquetas. IA desactivada. RSS manual y dominios vacíos por defecto. El README v0.4 original se conserva solo como referencia histórica en docs.
