# Apify: cinco redes en NEXO

Revisión de referencias públicas: 10 de noviembre de 2026.

## Cómo llenar la configuración

1. Como superadministrador, selecciona el proyecto correcto. Abre **Configuración → APIs e integraciones → Apify**.
2. **Proveedor:** `Apify`. **Dirección de la API:** `https://api.apify.com/v2`.
3. Escribe tu token exclusivamente en **Token de Apify** dentro de NEXO. Si ya aparece «Credenciales guardadas y cifradas», déjalo vacío para conservarlo. No lo compartas por chat ni lo pongas en una URL.
4. En **Redes y procesos de este proyecto**, elige Facebook, Instagram, TikTok, X o YouTube. Los Actors ya están indicados: no reemplaces el de Facebook con el de otra red.
5. Marca los procesos que deseas preparar. Para empezar, plantea **20 resultados por consulta** y **1 consulta máxima por día por proceso**. Son cantidades de preparación, no una estimación cerrada de consumo ni un límite monetario.
6. **ID de tarea:** opcional; déjalo vacío si no creaste una tarea guardada en Apify. Es su ID, no el enlace del Actor. Cada tarea debe corresponder a la función y red de su tarjeta.
7. **ID de dataset:** opcional; déjalo vacío si no tienes una ejecución previa. Un dataset es una captura concreta, no una suscripción a resultados nuevos.
8. Cambia entre las redes que necesitas y pulsa **Guardar configuración** una sola vez al terminar. Se guardan todas las redes editadas, conservando el token cifrado. El mensaje confirma el guardado, no una conexión verificada.
9. Registra las URL públicas de cada cuenta en **Actores** y las de los medios en **Medios**. No hay que repetirlas en cada proceso de Apify. Hoy no se conocen las cuentas de Instagram/TikTok/X/YouTube de los cuatro actores D14: no se deducen a partir de sus URL de Facebook.

## Procesos seleccionados

| Red | Publicaciones | Comentarios / respuestas | Estadísticas de cuenta |
|---|---|---|---|
| Facebook | [apify/facebook-posts-scraper](https://apify.com/apify/facebook-posts-scraper) | [apify/facebook-comments-scraper](https://apify.com/apify/facebook-comments-scraper) | [apify/facebook-pages-scraper](https://apify.com/apify/facebook-pages-scraper) |
| Instagram | [apify/instagram-scraper](https://apify.com/apify/instagram-scraper), modo `posts` | El mismo Actor, modo `comments` | El mismo Actor, modo `details` |
| TikTok | [clockworks/tiktok-scraper](https://apify.com/clockworks/tiktok-scraper) | [clockworks/tiktok-comments-scraper](https://apify.com/clockworks/tiktok-comments-scraper) | [clockworks/tiktok-profile-scraper](https://apify.com/clockworks/tiktok-profile-scraper) |
| X | [apidojo/tweet-scraper](https://apify.com/apidojo/tweet-scraper) | [apidojo/x-api](https://apify.com/apidojo/x-api), respuestas | El mismo servicio API, perfil |
| YouTube | [streamers/youtube-scraper](https://apify.com/streamers/youtube-scraper) | [streamers/youtube-comments-scraper](https://apify.com/streamers/youtube-comments-scraper) | [streamers/youtube-channel-scraper](https://apify.com/streamers/youtube-channel-scraper) |

Facebook tiene además un proceso independiente de [reacciones identificables](https://apify.com/scraper_one/facebook-reactions-scraper). La visibilidad puede ser parcial. Un contador agregado de likes no identifica a sus autores. Los comentarios públicos sí pueden aportar autor y texto según la fuente; las cuentas deben poder vincularse con certeza para atribuir una interacción a un integrante. No se infiere afinidad política a partir de estas acciones.

Instagram distingue perfil, publicaciones y comentarios por el modo del Actor y el tipo de URL. No representa una búsqueda exhaustiva de todo Instagram. Los procesos de X en modo Standby responden directamente a peticiones HTTP: **no tienen tarea ni dataset de ejecución por lotes**.

## Estado real y próximo paso

Esta entrega habilita **configuración y persistencia separadas por red/proceso/proyecto**. Mantiene token cifrado, control de versiones y permisos exclusivos del superadministrador. No cambia tablas ni requiere migración de la base de datos.

**El ejecutor de Apify todavía no está implementado ni activado.** Guardar un token o marcar procesos no inicia consultas. El programador diario existente de las 08:00 America/Mexico_City ejecuta RSS; no ejecuta estos 16 procesos. No se hicieron llamadas pagadas durante esta preparación. IA y envíos permanecen apagados.

Antes de activar consumo faltan los adaptadores de entrada/salida de cada Actor, validación con exportaciones reales, deduplicación por identificador de origen, periodos incrementales, cupos monetarios y una prueba acotada autorizada. La IA de emociones y RAG requiere su integración aparte. No basta con proporcionar un token para afirmar que estas funciones están conectadas.

El presupuesto previo es **solo de Facebook**: no incluye estas otras cuatro redes ni IA. Los resultados por consulta no son unidades de facturación equivalentes entre Actors. Debe recalcularse el presupuesto según redes, cuentas, publicaciones, comentarios y funciones activadas antes de autorizar ejecuciones.

## Conservación y comprobación

- El formulario anterior de token no borra los planes por red guardados.
- Una edición con versión antigua se rechaza; evita sobrescribir cambios de otra sesión.
- El token no regresa al navegador, ni a auditoría, ni a ejemplos exportables.
- Los consultores no pueden leer ni guardar configuración de integraciones.
- Cada proyecto mantiene su propia configuración, sin heredar las cuentas del D14.
