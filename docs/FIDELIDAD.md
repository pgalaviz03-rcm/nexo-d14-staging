# Fidelidad: continuidad de audiencia agregada

## Revisar la pantalla

Detén la ventana del servidor local 8002 con Ctrl+C y vuelve a abrir `ABRIR_NEXO_DESARROLLO_LOCAL.bat`. Actualiza el navegador en http://127.0.0.1:8002 y abre **Fidelidad**. Utiliza tu cuenta local habitual.

1. Selecciona actor, red, cuenta y periodo. D14 reutiliza su actor principal y sus cuatro referencias registradas; otros proyectos usan sus propios directorios.
2. Revisa audiencia participante, audiencia que regresa, nuevas en el corte, retorno y retención de la audiencia anterior.
3. Consulta la evolución de hasta doce cortes observados y el cuadro del periodo anterior. Cada corte tiene igual duración y la misma medición.
4. **Descargar corte** exporta los datos visibles con sus periodos y definición. Los valores reservados siguen siendo `null` en la respuesta y en el archivo.
5. **Ver cuentas en Actores** abre el directorio común. Quienes tengan rol administrador, editor o consultor pueden desplegar **Incorporar un corte agregado** y descargar una plantilla con su cuenta y fechas. Los conteos de la plantilla son `null`: debe completarlos una fuente, no inventarse para llenar la pantalla.

La estructura está disponible localmente. No se cargaron cifras artificiales en D14: inicialmente verás guiones y un estado de primer corte pendiente. No hace falta capturar datos para aceptar la navegación y la legibilidad de esta pantalla.

## Qué significa cada indicador

La unidad es una **cuenta participante única en una cuenta pública monitoreada**, según la medición declarada por la fuente. No representa personas únicas, ciudadanos, votantes ni preferencias políticas.

| Indicador | Definición |
|---|---|
| Audiencia participante, N | Cuentas distintas que interactuaron al menos una vez en el periodo |
| Audiencia que regresa, R | Intersección agregada entre participantes del periodo y de la referencia |
| Nuevas en este corte | N − R; nuevas respecto al periodo anterior, no necesariamente nuevas en toda la historia |
| Retorno | 100 × R / N |
| Retención de audiencia anterior | 100 × R / B, donde B es la audiencia participante del periodo anterior entregada por la fuente |
| Cambio de retorno | Diferencia en puntos porcentuales entre dos cortes equivalentes |

La referencia es siempre el periodo inmediatamente anterior, contiguo y de igual duración. Si B no está disponible, la retención queda sin dato; no se reemplaza por seguidores. Si B contradice el N observado en la captura anterior, se conservan las observaciones y se suspende la variación hasta conciliar las bases.

Una medición identifica una metodología estable de la fuente, por ejemplo el mismo conjunto de tipos de interacción, cobertura y tratamiento de cuentas. Cambiar esas condiciones requiere otro `measurement_id`. Tampoco se comparan proveedores diferentes. NEXO valida forma y coherencia; no certifica que una carga manual provenga de una plataforma ni que su cobertura sea exhaustiva.

Los periodos predefinidos usan días completos según la zona del navegador. Las fechas se convierten a UTC. El cierre es exclusivo. Solo un intervalo exactamente igual al solicitado ocupa los indicadores: no se suman ventanas solapadas ni cuentas de diferentes redes. La evolución usa las últimas doce ventanas con la duración elegida, dentro de un horizonte de doce periodos. Muestra cada corte observado por separado, sin interpolar.

## Protección y acceso

- Membresía comprobada en cada consulta y carga. Los lectores pueden consultar y exportar su proyecto, no importar. El administrador de un proyecto conserva el ámbito de ese proyecto; no adquiere permisos de plataforma.
- Solo referencias activas de actores reales del proyecto. Se excluyen demostraciones y actores archivados.
- Contratos estrictos: no aceptan nombres, listas de usuarios, identificadores de participantes, credenciales ni campos adicionales. La normalización externa copia exclusivamente los campos agregados expresamente mapeados y fija actor y cuenta desde un contexto confiable.
- Se reservan todos los conteos y tasas del corte si N < 20, si B disponible < 20, o si alguna celda positiva R, N−R o B−R es menor de 5. El cero de retorno con bases suficientes se conserva. Esta reserva reduce exposición de muestras pequeñas; no constituye una garantía matemática de anonimato frente a cruces entre consultas. No hay desglose individual.
- Historial de capturas inmutable mediante la API. Una repetición idéntica se deduplica; un cambio con idéntica identidad produce conflicto 409. Una revisión de fuente se conserva como nueva captura con fecha posterior; se utiliza la última observación del mismo corte y medición.
- Una carga fallida revierte todas sus capturas. Auditoría solo de cantidades de cortes nuevos y duplicados. Límites: 100 cortes y 1 MB por lote; 20 intentos de importación por proyecto/día UTC; consulta de hasta 1.000 capturas, 50 actores y 20 referencias del actor seleccionado.
- En PostgreSQL se preparó RLS forzada y permisos SELECT/INSERT; el rol de aplicación no puede actualizar ni borrar capturas. Esta política protege proyectos. La reserva de muestras pequeñas es una capa de la API, no una restricción sobre el acceso directo del operador a su propia base.

## Estructura interna editable

- `app/continuity_port.py`: esquema `AudienceCapture`, lote, normalizador con mapa explícito, protocolo `AudienceReader` y lector deshabilitado.
- `app/continuity_models.py`: tabla `audience_snapshots`, referencias compuestas de proyecto/actor y restricciones de coherencia.
- `app/continuity_service.py`: cálculo, reserva de muestras, corte exacto, comparación y serie.
- `app/continuity_api.py`: GET `/api/projects/{pid}/continuity` y POST `/api/projects/{pid}/continuity/captures`; permisos, cuota, deduplicación y transacción.
- `static/continuity.js` y sección Fidelidad de `static/index.html`: presentación, filtros, plantilla, importación y exportación. Descarta respuestas y lecturas de archivo pertenecientes a otro proyecto.
- `migrations/versions/009_audience.py`: actualización aditiva local y preparación PostgreSQL. `preflight.py`, permisos y exportador SQL de pruebas actualizados a 009. No se modificaron `app/main.py` ni `app/knowledge.py`.

Ejemplo de contrato **exclusivamente ficticio**, no corresponde al D14:

```json
{
  "provider": "manual",
  "items": [{
    "actor_id": 1,
    "network": "facebook",
    "url": "https://www.facebook.com/public_fixture",
    "measurement_id": "source-participation-v1",
    "contract_version": "participating-accounts-v1",
    "period_from": "2026-10-08T00:00:00Z",
    "period_to": "2026-10-15T00:00:00Z",
    "reference_from": "2026-10-01T00:00:00Z",
    "reference_to": "2026-10-08T00:00:00Z",
    "captured_at": "2026-10-16T00:00:00Z",
    "participants": 100,
    "returning": 60,
    "reference_participants": 120
  }]
}
```

Los campos de intervalo y conteos son obligatorios salvo `reference_participants`. `provider` admite `manual` o `apify_export`, que indican procedencia declarada, no una conexión activa. Las fechas deben incluir zona horaria; duración de 1 minuto a 90 días; captura posterior al cierre y nunca futura. Los conteos son enteros no negativos de hasta 9.007.199.254.740.991; R no supera N ni B.

## Conectar al final

No se activó ninguna conexión, tarea periódica, clave ni gasto. `DisabledAudienceReader` falla de forma cerrada aunque exista un token en el entorno. La IA no inventa ni estima estos conteos.

Antes de implementar el lector real, revisar un ejemplo autorizado del proveedor: debe entregar participantes únicos y su intersección agregada entre ventanas con la misma cobertura. Seguidores, reacciones y comentarios totales por sí solos no permiten calcular retorno o retención. Si la plataforma no entrega esos agregados, habrá que acordar una fuente autorizada de analítica que los proporcione o dejar esas métricas pendientes. NEXO no reconstruye historiales de personas a partir de sus identificadores.

Después: aprobar permisos de cuenta, alcance, conservación y presupuesto; implementar adaptador acotado con secretos fuera del cliente, límites/reintentos e idempotencia; comparar resultados con la analítica de origen; validar PostgreSQL nativo y migración 009 en un entorno separado; completar monitoreo y aceptación antes de activar un worker. Una API key por sí sola no completa esa validación.

## Verificación y respaldo

Consultar `FIDELIDAD_RESULTADO.json` para las cifras finales de pruebas. Incluye lógica de indicadores, aislamiento, permisos SQL en PGlite PostgreSQL WASM y controladores JS con DOM simulado. No representa aceptación visual en un navegador ni prueba de PostgreSQL nativo, HTTPS, correo o proveedores reales.

La tabla se ensayó dos veces sobre una copia antes de aplicarla a la base local. Se verificaron las huellas de todas las filas previas y el mapa. Se hicieron respaldos cifrados DPAPI antes y después, con recuperación aislada verificada. Están vinculados al usuario Windows actual; no sustituyen un respaldo externo ni son portables a otra máquina. El ZIP editable excluye bases, claves y respaldos privados.

Tras aceptar esta pantalla, sigue **Alertas**.

Aceptación visual del usuario: «Sí, aparece todo y se entiende». Continúa Alertas; fuentes externas pendientes.
