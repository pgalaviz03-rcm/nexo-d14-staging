# Plantillas sin datos reales

`pulse-import.template.json` es ficticia. Sustituye identificador del actor, fechas, URL, título y contenido por información autorizada. El actor debe existir en el proyecto elegido. No mezcles esta plantilla con datos reales del cliente; para ver datos ficticios usa el botón de demostración aislada.

`apify-field-map.template.json` declara nombres de campos de ejemplo, no el esquema garantizado de un Actor. Ajusta el mapa a su exportación real. El script de normalización trabaja sin red y descarta campos no declarados, incluidos identificadores de autores. Revisa además el texto libre antes de importar.

Desde la carpeta del código:

```powershell
python scripts/normalize_apify_export.py --input RUTA_EXPORTACION.json --mapping examples/apify-field-map.template.json --network facebook --actor-id ID_ACTOR_PUBLICO --output LOTE_NUEVO.json
```

El destino debe ser nuevo. Esto no ejecuta un Actor ni activa una conexión.
