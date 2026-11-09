# Configuración única y fichas del equipo

## Abrir la actualización

1. Detén con Ctrl+C la ventana del servidor 8002.
2. Vuelve a abrir ABRIR_NEXO_DESARROLLO_LOCAL.bat.
3. Abre http://127.0.0.1:8002 y actualiza con Ctrl+F5.
4. Entra como superadministrador. En el menú lateral aparece Configuración.

El proyecto se elige en el selector habitual. Al cambiarlo, Configuración permanece abierta y carga únicamente sus datos. Se limpian las credenciales escritas y las fichas del proyecto anterior. Un proyecto vacío también se puede configurar; no recibe datos del D14.

## Dónde está cada cosa

| Apartado | Qué se configura |
|---|---|
| Proyecto y accesos | Contexto y mínimo de clasificación del proyecto activo; creación de proyectos, cuentas y membresías de la plataforma |
| Actores y cuentas | Ficha única del actor principal y comparativos, perfiles públicos, estado y selección del principal |
| Equipo | Registro individual, Excel/CSV, activación de integrantes e incorporación de sus acciones observadas |
| Medios y RSS | Medios de comunicación, sitios y cuentas oficiales en redes, junto con el registro de RSS |
| Alertas y temas | Reglas del proyecto y catálogo de temas |
| APIs e integraciones | Proveedor, URL, modelo o recurso, dataset, cuenta, límites y credenciales cifradas |
| Programación | Horario, frecuencia, destino y canal del briefing; simulaciones locales |
| Datos e importaciones | Archivos, selección de Excel y lotes de publicaciones, cuentas, continuidad y medios |

En Equipo y Datos e importaciones aparece un selector del actor observado. Se alimenta del mismo directorio de Actores y cuentas y prepara las capturas y el seguimiento para ese actor. Las cuentas no se vuelven a registrar en cada pantalla.

Pulso y Actores ya no ofrecen dos formularios para crear o editar al mismo actor. Las reglas de alerta también se administran en un solo lugar. Los botones de configuración de cuentas llevan al directorio central.

Los filtros de lectura, las búsquedas, la revisión de un incidente y la creación o habilitación de informes siguen siendo acciones de trabajo en sus pantallas. Las cuentas de consultor no reciben acceso a Configuración ni permisos para modificar el proyecto.

La marca y el lema se retiraron del formulario de administración. La identidad actual permanece visible; la sustitución definitiva del nombre, lema y logo se hará como un cambio de diseño de la plataforma.

## Ficha de un integrante

En Fidelidad → Mi equipo pulsa el nombre de una persona registrada. La ficha muestra:

- Las cuentas que aportó el superadministrador y enlaces para abrirlas.
- Reacciones registradas, publicaciones comentadas y comentarios individuales cuando tienen identificador de origen.
- Las publicaciones del actor y periodo elegidos, con enlaces, texto de origen y fecha de observación.
- Páginas de hasta 20 publicaciones; el cierre o cambio de proyecto limpia la ficha.

La fecha de observación corresponde a la captura, no necesariamente al momento de la reacción. Publicaciones comentadas es un conteo de publicaciones distintas, no de todos los comentarios hechos. El exportado de Atalaya no siempre permite reconstruir comentarios individuales; en ese caso no se inventan cifras ni textos.

Las fichas corresponden exclusivamente al equipo que tú registras. La comunidad no registrada conserva estadísticas agregadas. No se asignan opiniones, postura política o puntuaciones personales de apoyo a partir de reacciones.

## Registrar medios y sus redes

En Configuración → Medios y RSS pulsa Añadir medio para abrir el formulario. Escribe su nombre, sitio y los enlaces oficiales disponibles de Facebook, Instagram, X, TikTok o YouTube. No necesitas tener todas las redes. Pulsa Guardar medio. El formulario se cierra, aparece una confirmación con su nombre y el registro queda resaltado en la lista de medios guardados, con enlaces al sitio y a cada red. El contador muestra cuántos medios tiene ese proyecto.

Para corregirlo, pulsa Editar en su registro; el botón del formulario cambia a Guardar cambios. Cancelar vuelve a la lista sin enviar datos. Si el servidor rechaza un guardado, se conserva lo escrito y se muestra el error. Puedes pausar el medio sin borrar publicaciones ya conservadas. El registro de RSS sigue separado y su botón dice Registrar RSS.

Una misma cuenta social activa no se puede registrar dos veces en medios distintos del mismo proyecto. Otro proyecto conserva su registro independiente.

El registro de medios no ejecuta una búsqueda remota. Prepara las cuentas que la futura conexión deberá consultar. El RSS conserva sus controles de dominios autorizados y protección frente a destinos privados.

### Probar la entrada local de publicaciones sin RSS

En Datos e importaciones → Incorporar publicaciones de un medio:

1. Elige un medio y una de sus cuentas registradas.
2. Descarga la plantilla JSON y completa cada publicación con sus datos reales de origen.
3. Los campos de cada pieza son external_id, url, title, text y published_at. captured_at y las fechas de publicación deben incluir zona horaria. El lote admite hasta 500 publicaciones y 1 MB.
4. Reemplaza los identificadores y enlaces de ejemplo; la plantilla sin completar se rechaza.
5. Incorpora el archivo. Sus piezas entran al archivo de noticias y se pueden encontrar en Explorador, en la búsqueda de noticias de Biblioteca y en Briefing.

El registro conserva también el medio, red, cuenta e identificador de origen. Repetir el mismo lote no duplica las noticias. Si una URL ya existía por otra fuente, se conserva su registro editorial anterior. Un identificador de origen que cambie de publicación se rechaza y revierte el lote completo.

No se inventan alcance, vistas ni emociones. Este contrato local es la entrada que tendrá que usar el adaptador de la API después de validar el esquema real de sus resultados.

## Preparar las APIs

Hay apartados para Apify, IA/análisis/RAG, embeddings, correo, Telegram, WhatsApp, base de datos de nube y archivos/respaldos.

1. Selecciona el servicio del proyecto.
2. Escribe proveedor y los datos que correspondan: URL HTTPS, modelo, proceso/recurso, dataset o cuenta.
3. Define elementos por consulta y límite diario. El presupuesto autorizado permanece en USD 0.
4. Si ya tienes una credencial, escríbela únicamente en el campo seguro de esta pantalla. Nunca hace falta enviarla al chat.
5. Guarda. La pantalla indica Guardado localmente; eso no acredita una conexión verificada.

Las credenciales se cifran en la base privada y no se devuelven en las respuestas del catálogo. Los campos vacíos conservan las claves existentes; reemplazar una clave de almacenamiento no elimina la otra. Borrar credenciales guardadas requiere marcarlo expresamente. Los cambios usan versión para impedir sobrescribir una edición concurrente.

El servidor registra en auditoría el servicio y la versión, sin tokens ni contraseñas. Los errores de validación de esta ruta tampoco devuelven el contenido recibido de las credenciales. Los límites y el guardado no activan trabajos, SDKs ni llamadas externas.

### Qué falta al conectar

Hay que implementar y probar cada adaptador real, confirmar los procesos y campos de Apify, traducir sus resultados al contrato local, definir cursores y reintentos y comprobar límites, fuentes y permisos con una ejecución controlada. No es suficiente pegar una clave para declarar funcionando la integración.

La programación actual admite correo y Telegram. WhatsApp tiene preparado el registro cifrado de su API; su programación y envío requieren ampliar las restricciones de la base y añadir el conector. Ningún canal envía mensajes en esta entrega.

Las credenciales de arranque del servidor y del despliegue no se sustituyen automáticamente desde esta página. Antes de nube se prepararán migraciones y políticas de acceso para los registros nuevos y se probarán en PostgreSQL. No se acredita RLS nativo ni producción con estas pruebas locales.

## Comprobación manual pendiente

- Como superadministrador, cambia a un proyecto vacío y revisa los ocho apartados de Configuración; crea un actor o un medio de prueba solo si quieres conservarlo en ese proyecto.
- En Fidelidad abre una ficha del equipo y comprueba sus cuentas y publicaciones. Para una muestra ficticia aislada puedes seguir usando PROBAR_NEXO_FIDELIDAD.bat en 8004; esa muestra tiene permisos de lectura y no muestra Configuración.
- En una cuenta de consultor comprueba que Configuración no aparece y que sí puedes consultar las fichas del equipo de tu proyecto.
- Estrecha la ventana para revisar las pestañas y formularios en tamaño móvil. Las verificaciones automáticas de interfaz usan DOM simulado; no sustituyen esta revisión visual real.

No se escribieron datos ficticios en el D14 ni se ejecutaron servicios externos. Se conservaron app/main.py, app/knowledge.py y el mapa territorial.

## Nota técnica para recuperación y conexión

Se añaden tres tablas locales: integration_settings, media_outlets y media_article_links. Las claves de integraciones usan Fernet con una clave de propósito separado derivada de la clave privada local, o NEXO_INTEGRATIONS_ENCRYPTION_KEY si se configura expresamente. La base cifrada necesita conservar su clave privada de recuperación fuera del paquete de código. Si cambia esa clave, habrá que borrar y volver a ingresar las credenciales que no puedan descifrarse.

Las rutas de Configuración son exclusivas del superadministrador y están limitadas al desarrollo local. Las noticias de medios y las fichas del equipo conservan el aislamiento por proyecto. Las URL de proveedor son referencias almacenadas: el futuro adaptador debe resolver y revalidar IPs públicas y redirecciones antes de conectarse, además de aplicar tiempos, tamaños, cuotas e idempotencia.
