# Ejecución de Facebook en NEXO

## Estado de esta entrega

Se implementó el transporte HTTP real de Apify y la importación por proyecto para los cuatro procesos de Facebook. Las pruebas automatizadas usan respuestas simuladas. La comprobación con una cuenta real requiere autorización de consumo; el modo predeterminado sigue en **Pausado**. Instagram, TikTok, X y YouTube conservan sus configuraciones preparadas, pero sus ejecutores siguen pendientes. IA y RAG no se activan con esta entrega.

## Prueba acotada propuesta

- Proyecto: el seleccionado por el superadministrador.
- Cuenta: primera cuenta activa del actor principal (una cuenta como máximo).
- Proceso: `apify/facebook-posts-scraper`.
- Alcance: hasta tres publicaciones públicas de los últimos siete días.
- Límite por ejecución: **USD 0.05**.
- Presupuesto mensual de esta prueba: **USD 0.05**, para que no quede saldo autorizado para repetirla.
- Equivalencia ilustrativa: **MXN 1.00** con supuesto USD 1 = MXN 20; no es cotización bancaria ni incluye diferencias de conversión/impuestos.
- Sin contratación de plan, sin recarga ni activación diaria de Apify.

En **Configuración → APIs e integraciones → Apify**, el modo **Prueba única** utiliza estos límites y se guarda junto con las credenciales existentes. Luego **Actualizar datos** admite la captura. El modo de prueba nunca se ejecuta desde el programador diario. No hace falta volver a introducir el token si aparece guardado.

No actives un modo con consumo hasta autorizar el presupuesto. Si Apify exige un plan o saldo adicional, la integración informa el rechazo y no contrata ni recarga nada.

## Operación diaria posterior

El modo **Procesos seleccionados · diario a las 08:00** permite las selecciones de Facebook guardadas. Comparte la captura entre los usuarios del proyecto: abrir o cambiar filtros no inicia una nueva recolección. El superadministrador puede solicitar cortes manuales sujetos a cupos. El máximo de cuentas se limita a cinco; el D14 puede usar sus cuatro actores. Las cuentas se toman de Actores y Medios, sin repetirlas en cada proceso.

Una ejecución por proceso utiliza sus cuentas en un lote. Publicaciones y perfiles usan las URL registradas. Comentarios y reacciones usan una publicación reciente observada por cuenta, hasta cinco URL, compatible con el límite publicado del Actor de reacciones en Free. Por tanto, esta primera versión hace **muestreo acotado**, no una extracción exhaustiva de todas las interacciones de todos los posts.

Las referencias de tarea y dataset del catálogo no se usan para disparar estos procesos: el ejecutor emplea los Actors permitidos y genera sus entradas a partir del proyecto. Un dataset de una corrida vieja no se trata como fuente de actualizaciones nuevas.

## Datos incorporados

- Publicaciones y comentarios: documentos de Pulso con identificador y enlace de origen. Quedan **sin clasificación de tono o emociones** hasta incorporar una evaluación válida.
- Cuenta: seguidores observados. No se inventan vistas únicas, alcance ni impresiones.
- Fidelidad: publicaciones con sus contadores observados de reacciones, comentarios y compartidos.
- Equipo: presencia de reacción y comentarios individuales solo cuando el perfil observado coincide exactamente con una cuenta registrada del integrante. Los nombres parecidos no bastan. No se asigna afinidad política.
- Medios registrados: publicaciones en el archivo de noticias del proyecto. Las reacciones de personas ajenas al equipo no se convierten en perfiles internos.

## Control de consumo y fallos

Antes de cada POST a Apify, NEXO guarda una reserva del límite por ejecución y la compara con el presupuesto mensual del proyecto. Conserva esa reserva incluso si el inicio resulta incierto; nunca lo repite automáticamente. Se envían `maxTotalChargeUsd`, `maxItems`, `timeout=180` y `restartOnError=false`. La reserva es un control conservador, **no el costo facturado**, y no se libera automáticamente por cobrar menos.

Los identificadores de corrida y dataset quedan en el corte. Una marca temporal evita dos trabajadores simultáneos. La cuenta y el proyecto se comprueban antes de enviar y antes de importar. El token se descifra únicamente en el servidor y se transmite en Authorization al origen fijo `https://api.apify.com`; no se admite una URL de API arbitraria, redirecciones ni tokens en parámetros.

El navegador del superadministrador da seguimiento al corte admitido. El programador firmado de GitHub también observa el corte diario durante varios minutos, renovando sus credenciales temporales. Si la plataforma se interrumpe entre guardar una reserva y conocer el ID de Apify, se informa el inicio incierto y se conserva el presupuesto reservado.

Las capturas usan una identidad persistida antes de importarse; volver a leer un dataset no suma otra vez sus documentos o interacciones. Los errores de cada proceso se muestran sin respuestas crudas ni secretos. Un corte parcial se presenta como parcial y con números de piezas/cuentas/interacciones incorporadas.

## Fuentes del contrato

- [Iniciar Actor y limitar el cargo](https://docs.apify.com/api/v2/actors-runs-post).
- [Publicaciones de Facebook](https://apify.com/apify/facebook-posts-scraper).
- [Comentarios de Facebook](https://apify.com/apify/facebook-comments-scraper).
- [Estadísticas de páginas](https://apify.com/apify/facebook-pages-scraper).
- [Reacciones observables y sus límites](https://apify.com/scraper_one/facebook-reactions-scraper).

No se modifican `app/main.py`, `app/knowledge.py`, tablas, RLS ni históricos territoriales.
