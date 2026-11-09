> **Actualización: Configuración unificada.** Los formularios del superadministrador están en Configuración, separados por proyecto: Actores y cuentas, Equipo, Medios y RSS, Alertas y temas, APIs, Programación y Datos. En Fidelidad, pulsa el nombre de un integrante registrado para abrir su ficha. Reinicia el servidor 8002 y actualiza con Ctrl+F5. Consulta la guía CONFIGURACION_UNIFICADA.md.

# Equipo y comunidad en Fidelidad

El equipo es una lista de colaboradores que tú aportas. Se registran acciones observadas en las publicaciones de las cuentas del proyecto: reacciones, publicaciones comentadas y comentarios individuales cuando la fuente proporciona un identificador. No se asignan opiniones ni puntuaciones de lealtad.

## Ver la muestra sin modificar el D14

1. Cierra con Ctrl+C la ventana anterior de PROBAR_NEXO_FIDELIDAD.bat, si sigue abierta.
2. Abre de nuevo PROBAR_NEXO_FIDELIDAD.bat y entra en http://127.0.0.1:8004 con tu cuenta local habitual. Actualiza con Ctrl+F5.
3. Abre Fidelidad → Equipo y comunidad → Mi equipo. Hay tres colaboradores ficticios con diferentes cantidades de actividad. Prueba el periodo, la red, el orden y las pestañas.
4. Comunidad muestra los contadores agregados de las publicaciones, sin fichas de personas no registradas.

Esta muestra es de consulta, incluso al entrar con la cuenta que administras. Solo la carpeta privada de la muestra contiene sus datos ficticios. El piloto conserva sus datos. No se conecta Apify ni se generan cobros.

## Incorporar tu equipo real en NEXO local

Reinicia ABRIR_NEXO_DESARROLLO_LOCAL.bat, abre http://127.0.0.1:8002 y actualiza con Ctrl+F5. Entra como superadministrador y selecciona el proyecto y actor correctos.

Para registrar una persona sin Excel, abre Gestionar equipo y registros → Registrar un integrante sin Excel. Escribe su nombre, al menos una cuenta y pulsa Guardar integrante. El código es opcional, pero se recomienda para mantener una referencia estable. Estas fichas son integrantes del equipo, no cuentas nuevas de acceso a NEXO. Si reutilizas un código, se actualiza la ficha completa; incluye todas sus redes. La carga individual admite hasta 100 operaciones diarias por proyecto y comparte con Excel el límite de 500 integrantes activos.

Para cargar varios integrantes de una vez:

1. En Fidelidad, abre Gestionar equipo y registros y descarga la plantilla. También puedes usar tu Excel XLSX con estas columnas: Código, Nombre, Facebook, Instagram, TikTok y X. Solo Nombre y una cuenta son indispensables. El código es recomendable: debe ser estable y distinto para cada integrante. Los teléfonos, correos y columnas ajenas se ignoran.
2. En cada red escribe el enlace público o el usuario exacto. Un nombre de pantalla no basta para identificar una cuenta. Para un perfil numérico de Facebook usa su enlace profile.php?id=... o id:... . No se buscan coincidencias aproximadas entre personas con el mismo nombre.
3. Carga el Excel o CSV UTF-8. Si hay varias hojas válidas, escribe el nombre de la hoja. Hasta 500 integrantes activos y 2 MB por archivo. El archivo original no se guarda; se conservan los campos seleccionados y su huella.
4. En el bloque anterior, Incorporar publicaciones de Atalaya, incorpora resultados.json de la cuenta observada. El ZIP de código no contiene estos resultados: se exportan de tu instalación de Atalaya. Selecciona una cuenta registrada y activa del actor.
5. En Gestionar equipo y registros selecciona la misma cuenta y el mismo resultados.json, y pulsa Incorporar actividad del equipo. El navegador toma únicamente observaciones de las cuentas activas que registraste; las personas no registradas, sus nombres y sus historiales no se envían a NEXO.
6. Revisa Mi equipo. Repetir la carga no suma dos veces una reacción ni una presencia en la misma publicación. Una nueva observación puede actualizar su fecha. Puedes desactivar y reactivar integrantes sin borrar sus registros anteriores.

Las cuentas de consultor o lector pueden consultar la tabla; no ven la gestión ni pueden cargar archivos o cambiar integrantes. Cada proyecto tiene su propio equipo y sus propios registros. El reinicio crea dos tablas nuevas de equipo en SQLite, sin reemplazar las tablas anteriores.

## Qué significa cada columna

- Reacciones registradas: publicaciones donde la fuente identificó una reacción de esa cuenta registrada. Cero registros no demuestra ausencia de actividad: algunas fuentes no entregan todos los autores.
- Publicaciones comentadas: publicaciones distintas donde se observó al menos un comentario o respuesta del integrante.
- Comentarios con ID: conteo de comentarios/respuestas distintos que cuentan con identificador de origen. Si solo hay presencia, aparece un guion. El exportado de Atalaya usa un conjunto de autores por publicación y tipo, por lo que no permite reconstruir cuántos comentarios distintos hizo cada persona.
- Presencia registrada: publicaciones con al menos una acción divididas entre publicaciones del corte en las redes registradas de ese integrante. No es una medida de apoyo personal. Si no hay publicaciones elegibles, no se calcula el porcentaje.
- Última observación: fecha de la captura que registró la acción; no necesariamente el momento en que la persona reaccionó o comentó.

Los filtros seleccionan las publicaciones por su fecha, actor, red y cuenta; no reconstruyen el día de cada acción si la fuente no informa ese dato. La tabla se ordena por publicaciones con actividad, reacciones o publicaciones comentadas. Los totales de Comunidad incluyen al equipo y no se presentan como personas únicas ni como actividad orgánica separada.

## Preparado para la conexión posterior

El contrato local de eventos acepta reaction, comment_presence, comment y reply; estos dos últimos requieren event_id. La futura conexión debe proporcionar datos verificables de la fuente y resolver las cuentas exactamente contra el equipo registrado. No se copió la autenticación, el planificador ni el análisis de postura personal de la otra aplicación.

La conexión automática a Apify continúa pendiente, de acuerdo con el trabajo local acordado. Antes de nube hay que incorporar las migraciones y las políticas de acceso de estas tablas y comprobarlas en PostgreSQL. Las pruebas actuales no acreditan una integración activa ni un servicio de producción.

El código de las demás pantallas, app/main.py, app/knowledge.py y el mapa territorial se conservan. El límite de carga HTTP se amplió solo para las rutas de importación de Fidelidad; las demás rutas mantienen sus límites.

## Estado exacto de la conexión automática

La carga manual, el registro por proyecto, los permisos y la importación de exportados están implementados localmente. La automatización de Apify no está implementada ni validada en esta adaptación. El código de Atalaya se revisó como referencia; no se ejecutó su planificador ni se sustituyó la seguridad de NEXO.

Para automatizar faltan: confirmar las versiones de los actores de Apify que usas y sus esquemas; desarrollar el adaptador de lectura al contrato de NEXO; validar cuentas y acciones identificables realmente disponibles; guardar cursores y deduplicar por identificadores; aplicar las cuotas antes de ejecutar trabajos; incorporar credenciales al almacén de secretos; y probar errores, reintentos y aislamiento con una ejecución controlada. Si un actor solo entrega un conjunto de autores por publicación, se conserva presencia y no se inventa el número de comentarios.

La conexión no consiste únicamente en pegar una clave. Las credenciales se ingresarán directamente en la configuración segura al preparar esa fase, nunca en el chat. Esta entrega no requiere conectarlas ni ejecutar servicios externos.
