# NEXO · Estimación de actualización diaria

Precios consultados el 10 de noviembre de 2026. Supuestos: un proyecto, cuatro cuentas de Facebook, 30 días, un lote diario agrupado por Actor, sin consultas manuales adicionales. USD 1 = MXN 20 es un tipo de cambio de planificación, no una cotización bancaria. Importes antes de impuestos/comisiones y sin una primera carga de históricos. Los límites se refieren a registros devueltos por Apify, incluidos los repetidos; deduplicarlos después en NEXO no evita el cobro de la extracción.

## Escenarios de volumen

| Escenario | Publicaciones/día | Comentarios/día | Reacciones identificables/día | Consumo Apify USD/mes | Pago estimado con Starter USD/mes | MXN/mes |
|---|---:|---:|---:|---:|---:|---:|
| Austero | 20 | 100 | 0 | 10.04 | 19.00 | 380.00 |
| Piloto con equipo | 40 | 300 | 100 | 34.05 | 34.05 | 680.91 |
| Amplio | 80 | 1000 | 500 | 118.05 | 118.05 | 2360.91 |

El plan Starter consultado cuesta USD 19/mes e incluye USD 19 de consumo: no se suma otra vez ese crédito al consumo. La fórmula de pago es max(19, consumo), suponiendo tarifas Bronze y sobreconsumo habilitado. Esta es una estimación, no una autorización de cobro ni un plan contratado. El plan Free incluye USD 5/mes de uso; si se agota, el piloto debe detenerse, no prometer operar el mes completo gratis.

## Desglose del escenario «Piloto con equipo»

| Componente | Supuesto | USD/mes | MXN/mes |
|---|---|---:|---:|
| Publicaciones | 40/día, tarifa Bronze USD .004 + .001 de filtro por fecha, un inicio .001/día | 6.03 | 120.60 |
| Comentarios | 300/día, USD .002/comentario + un inicio .001/día; sin complemento de filtro de pago | 18.03 | 360.60 |
| Estadísticas de páginas | 4/día, USD .0082/página | .984 | 19.68 |
| Personas que reaccionan | 100/día, USD .003/registro + inicio .00005/día | 9.0015 | 180.03 |
| Total de extracción | Crédito mensual Starter ya considerado | 34.0455 | 680.91 |
| Render Free + Supabase Free | Dentro de los límites de los servicios existentes | 0 | 0 |
| Programador GitHub | Dentro de cuota incluida y con sobreconsumo bloqueado | 0 | 0 |
| IA/RAG y mensajería | Sin modelo, volumen o envío contratado | Por definir | Por definir |

En nivel Free las tarifas verificadas son USD .005/post, .002/post de filtro, .0025/comentario y .012/página; por ello el mismo escenario no cabe en el crédito gratuito. El Actor de reacciones usa USD .004/registro en Free. El anuncio «desde» puede mostrar otro nivel y no debe usarse para calcular Free.

Una ejecución manual adicional de todo el lote del escenario Piloto consumiría aproximadamente USD 1.13 (MXN 22.70), antes de IA y fuera del crédito disponible. Los lotes sin resultados, cargos mínimos y complementos de cada Actor pueden alterar ese importe. Antes de activar, realizar una prueba pequeña y revisar usageTotalUsd y el conteo real en Apify.

El scraping no determina emociones ni sarcasmo por sí mismo. La IA requiere su propio modelo, presupuesto y procesamiento solo de textos nuevos o modificados. No se ha incluido un precio ficticio de IA en el total. Tampoco se garantizan datos privados de alcance, personas únicas ni identificación exhaustiva de reacciones.

## Fuentes primarias

- Planes y crédito: https://apify.com/pricing
- Publicaciones: https://apify.com/apify/facebook-posts-scraper/pricing
- Tarifas por nivel de publicaciones: https://api.apify.com/v2/acts/apify~facebook-posts-scraper
- Comentarios y tarifas por nivel: https://api.apify.com/v2/acts/apify~facebook-comments-scraper
- Páginas y tarifas por nivel: https://api.apify.com/v2/acts/apify~facebook-pages-scraper
- Reacciones: https://apify.com/scraper_one/facebook-reactions-scraper y https://api.apify.com/v2/acts/scraper_one~facebook-reactions-scraper
- Cuotas de Actions: https://docs.github.com/en/billing/concepts/product-billing/github-actions

Estado actual: no se han activado ni cobrado ejecuciones de Apify o IA durante esta preparación. Mantener presupuesto externo cero hasta la aprobación del propietario.
