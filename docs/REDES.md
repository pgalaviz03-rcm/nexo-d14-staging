# Redes: rendimiento de cuentas por proyecto

## Recorrido

La pantalla abre por defecto al actor principal del proyecto. En D14 utiliza las referencias públicas ya registradas para Rodrigo Cervantes, Quique Galo, Jose Juan y Alma Hilda; no se añadieron estadísticas ficticias. Cada cliente recibe únicamente sus actores, referencias y capturas.

- Elegir **actor**, **red** y **periodo**. Los periodos de 7, 30 y 90 días utilizan días completos anteriores al día actual, según la zona horaria del navegador. También hay fechas personalizadas.
- Elegir una cuenta cuando el actor tenga varias: los indicadores corresponden siempre a **una cuenta**. No se suman seguidores, vistas o alcances entre redes.
- Consultar seguidores con fecha de observación, actividad del corte, evolución de seguidores y comparativo de una cuenta por actor en la misma red. El comparativo muestra las fechas de los seguidores: no supone que todos fueron observados simultáneamente.
- **Gestionar cuentas** abre Actores, conservando un único directorio. **Descargar corte** exporta el JSON de los datos visibles y su metodología.
- Administradores, editores y consultores pueden usar **Incorporar capturas locales**. Los lectores consultan y descargan; no pueden cargar capturas. La plantilla contiene las referencias del proyecto y valores `null` para completar con datos observados, nunca valores de ejemplo inventados.

La evolución muestra hasta 30 observaciones del periodo. Una sola observación se representa como un punto. Sin capturas, aparecen guiones y un estado de primera captura pendiente. Cero es distinto de desconocido.

## Significado de las cifras

**Seguidores** es la última observación conocida a la fecha de consulta; puede ser posterior al cierre del periodo de actividad. Su fecha aparece en pantalla. El cambio se calcula entre esa observación y la última disponible al inicio o antes del corte, mostrando las fechas reales: no se presenta como crecimiento continuo inferido de todo el periodo. La gráfica incluye únicamente observaciones dentro del corte.

**Publicaciones, interacciones, vistas, impresiones y alcance** se usan como actividad del corte solamente si la fuente declara un intervalo exactamente igual al solicitado. El periodo anterior tiene la misma duración y termina cuando empieza el actual. No se suman capturas solapadas ni se convierte un contador sin periodo en una cifra de siete días. Una captura de actividad puede recibirse después del cierre del intervalo que informa.

**Interacciones por 100 seguidores** utiliza las interacciones del periodo y la última observación conocida de seguidores dentro del corte. El denominador y su fecha quedan identificados. Si solo hay seguidores antiguos o posteriores al corte, el cociente queda sin dato. No es porcentaje de personas únicas y puede superar 100.

Las redes no garantizan los mismos campos ni definiciones; el adaptador deberá respetar la semántica del proveedor. El software valida forma, fechas, referencias y coherencia; no certifica la autenticidad de cifras introducidas manualmente. La procedencia declarada de cada captura se conserva.

## Contrato de captura

Se reutiliza `pulse_accounts`, con capturas inmutables. No hay tabla ni migración nuevas; se conserva la migración preparada `008_actor_profiles` y las 31 tablas existentes.

`GET /api/projects/{pid}/networks` acepta `actor_id`, `network`, `account_url`, `start` y `end`; comprueba membresía, devuelve capacidades y mantiene el ámbito del proyecto. No mezcla demostraciones, actores archivados, referencias pausadas ni menciones de Pulso con publicaciones propias de una cuenta.

`POST /api/projects/{pid}/networks/captures` recibe un lote:

```json
{
  "provider": "manual",
  "items": [
    {
      "actor_id": 1,
      "network": "facebook",
      "url": "https://www.facebook.com/public_fixture",
      "captured_at": "2026-10-19T18:00:00Z",
      "followers": 100,
      "metrics_from": null,
      "metrics_to": null,
      "posts": null,
      "views": null,
      "impressions": null,
      "reach": null,
      "interactions": null
    }
  ]
}
```

El ejemplo es ficticio; el identificador y la URL deben sustituirse por una referencia activa del proyecto. Para datos de actividad se necesitan `metrics_from` y `metrics_to`, con inicio anterior a fin y fin no posterior a la observación. Fechas con zona horaria; normalización UTC antes de almacenar. `captured_at` identifica la observación, no debe inventarse una fecha de cierre si el proveedor entregó un valor actual.

Contadores enteros no negativos hasta 9,007,199,254,740,991. Se rechazan booleanos, cadenas numéricas, valores negativos, fechas futuras y capturas sin ninguna métrica. Solo cuentas públicas ya registradas y activas en Actores. Hasta 100 capturas y 1 MB por lote; 20 intentos de importación por proyecto y día UTC. La cuota persiste aunque falle el lote; las capturas sí se incorporan todas o ninguna.

La misma cuenta, actor, red, fecha y contenido vuelve como duplicado. Si el contenido cambia bajo esa identidad, se rechaza sin sobrescribir el historial. Una corrección del proveedor necesita otra observación/versionado coherente, no modificar la cifra anterior en silencio.

## Fuentes futuras y seguridad

`network_port.py` define el lector de cuentas y la normalización de exportaciones. El mapa de campos es explícito y simple; los identificadores de actor y cuenta se fijan desde el contexto del proyecto, no desde un campo arbitrario de un archivo externo. Se admiten procedencias declaradas `manual` y `apify_export`.

El único lector instalado es `DisabledAccountReader`: no utiliza tokens aunque existan variables de entorno. Para activar una fuente faltan el adaptador real, permisos/OAuth correspondientes, secretos de servidor, presupuesto, cuotas globales, programación, reintentos limitados, monitorización y pruebas de campos/periodos reales. Registrar cuatro enlaces no obtiene por sí solo estadísticas ni acceso privado. Los contadores de cuenta los entrega la fuente; no se inventan mediante IA. El análisis de texto de Pulso y Briefing mantiene su circuito aparte.

La futura solicitud de red deberá validar de nuevo URL, DNS, IP pública y redirecciones. Esta entrega solo valida y almacena identificadores; no abre los enlaces para recolectar datos. HTTPS, ausencia de credenciales y correspondencia entre dominio y red se comprueban al importar. Las claves y tokens no son campos admitidos.

Las políticas PostgreSQL existentes de `pulse_accounts` limitan lectura e inserción al proyecto y al usuario autorizados; el rol de aplicación no puede actualizar ni borrar las capturas. La bitácora de carga conserva conteos, sin URLs, textos ni claves. Las respuestas tardías y la lectura tardía de un archivo se descartan al cambiar de proyecto. Los formularios y permisos visibles se limpian al salir.

Cada consulta está acotada a las últimas 1,000 capturas y 20 cuentas por actor, máximo 50 actores activos. La cobertura informa cuándo se aplican límites. No se finge completitud del archivo más allá de ellos.

No se clasifican personas, ideología, autenticidad ni bots. No se construyen perfiles políticos individuales. Las cifras describen cuentas y actividad pública observada.

## Verificación y siguiente paso

Resultados exactos en `REDES_RESULTADO.json`. Las pruebas de interfaz usan DOM simulado; la validación visual queda a cargo del usuario en su servidor habitual. La comprobación de D14 se hizo en modo de solo lectura: las cuatro referencias se muestran, Rodrigo es el principal y no se agregaron capturas ficticias.

Reiniciar con `ABRIR_NEXO_DESARROLLO_LOCAL.bat`, actualizar el navegador y entrar en **Redes**. Deben verse el selector, la referencia Facebook del principal y las cuatro filas comparativas con cifras pendientes. Se pueden cambiar actor y red sin mostrar información de otro proyecto. Después de aceptar el recorrido se revisa el siguiente módulo.

**Aceptación del usuario, 20/10/2026:** confirmó referencias, filtros y comparativo y que el recorrido se entiende. Se acepta la interfaz local; la conexión y validación de estadísticas reales siguen pendientes.
