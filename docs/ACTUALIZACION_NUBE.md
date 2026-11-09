# NEXO · Staging de nube del D14

Actualizado el 9 de noviembre de 2026. NEXO está publicado en el servicio gratuito existente:
[abrir NEXO](https://nexo-d14-staging.onrender.com/).

Se comprobó en el navegador una sesión autenticada con MFA, el rol Superadministrador, Configuración, las cuatro fichas de actores y los tres documentos listos para buscar. La copia local del puerto 8002 se conserva. Esta entrega sigue siendo staging: APIs de redes, IA y envíos no se activaron.

## Acceso y administración

Usa la cuenta y contraseña de NEXO de nube y su autenticador. La contraseña de base de datos y las cuentas locales cumplen funciones distintas. No se copiaron contraseñas ni usuarios de SQLite.

Configuración concentra proyecto y accesos, actores y cuentas, equipo, medios/RSS, alertas y temas, integraciones, programación y documentos. El superadministrador puede gestionar todos los proyectos. Los usuarios de proyecto conservan consulta, sin configuración ni escrituras. Para dar acceso a una nueva cuenta: crear su identidad en Supabase y después vincular su correo e ID y asignar membresía desde NEXO. La aplicación no recibe una clave service_role ni administra las contraseñas de Supabase.

## Contenido trasladado

- 3 originales de Biblioteca, sus 3 extracciones y los 6 contenidos durables en PostgreSQL. Se verificaron los bytes y SHA256 antes y después.
- 20 noticias, fusionadas por enlace con las 10 que ya estaban en nube; 2 fuentes RSS.
- 2 informes con 3 versiones y la habilitación previa de una versión para lectores.
- 4 actores con sus perfiles, 2 reglas, 1 tema y 2 integrantes registrados.
- Histórico conservado: 45 secciones, 41,984 votos territoriales y lista nominal de 65,378. No se sobrescribió.

Los identificadores de documentos, fuentes y citas se remapearon. La versión 2 del informe de rezago conserva el filtro de su PDF. Los hashes de los informes se recalcularon para sus nuevas referencias, conservando el hash anterior y los identificadores de autor local en la procedencia de importación. Los registros en nube identifican al operador que importó, sin inventar identidades de autores locales.

No se trasladaron muestras ficticias, capturas sociales de demostración, contraseñas, cuentas locales, colas de IA ni destinos de mensajería. Se mantuvo una instantánea local consistente del origen. La importación pasó un ensayo con reversión, se confirmó en una sola transacción y se verificó después. Repetir el mismo origen no duplica registros.

## Infraestructura y seguridad verificadas

Render Free y Supabase Free existentes; ningún nuevo recurso de pago. Auto-deploy y previews permanecen apagados. La corrección funcional del arranque está en f646dd2f9315fec5726d2f1d2f8c4535a0c1333e y se conserva en esta entrega.

La entrada app.cloud_main:app reutiliza las dependencias de autenticación y autorización de la API. main.py y knowledge.py conservan sus bytes validados. La revisión de esquema es 011_workspace_cloud: 40 tablas privadas con RLS habilitada y forzada. El rol de ejecución nexo_app no es propietario, superusuario ni BYPASSRLS, no reescribe históricos, no concede superadministradores y no cambia vínculos de identidad.

La conexión PostgreSQL valida el nombre y la CA mediante verify-full; se observó TLS 1.3. HTTPS, CSP, HSTS y cabeceras de seguridad están presentes. Los endpoints privados devuelven 401 sin sesión. Los archivos están en DatasetBlob, no en el disco efímero de Render. Las claves de integraciones y envíos son independientes y permanecen en secretos del proveedor.

El arranque del navegador usa un único recurso de módulos versionado. Las consultas de la interfaz se limitan a dos simultáneas, incluyendo la lectura de la respuesta, para respetar el límite del servidor gratuito. Se conserva el límite del servidor. Los fallos iniciales de carga y concurrencia se comprobaron y corrigieron en la web.

## Pruebas y evidencia

Pasaron 145 pruebas locales, 360 comprobaciones JS en 23 módulos, 39 comprobaciones SQL/RLS del trayecto 002→011, el ensayo nativo PostgreSQL del usuario, 26 pruebas finales de PDF y 9 comprobaciones de traslado. La regresión documental previa de 75 pruebas se solapa con PDF y no se suma. La auditoría de los 34 paquetes fijados no reportó vulnerabilidades conocidas en la comprobación realizada. pypdf del candidato de nube es 6.21.4; su proceso de extracción conserva límites de memoria, tiempo y descompresión.

/api/health y /api/ready respondieron 200; las rutas de proyectos y plataforma respondieron 401 sin sesión. El HTML y el recurso de módulos publicados coinciden con la fuente verificada. La CI de GitHub es manual y no se ejecutó como parte de esta publicación.

El JSON de resultado distingue pruebas de código, comprobaciones de nube e importación. El ZIP es un paquete editable de código, no un respaldo de datos o de credenciales.

## Respaldo y recuperación

El respaldo previo cifrado pasó la recuperación del esquema público y quedó en el Drive privado elegido, con tamaño y permisos comprobados. La clave de recuperación no se subió junto al archivo. Conserva esa clave y las claves de cifrado de Render en tu gestor privado, fuera de esta computadora. La custodia externa de esas claves aún requiere comprobación del propietario.

Auth/MFA y los objetos de Storage no se acreditaron como restaurados de extremo a extremo. Para revertir una revisión de esquema, restaurar primero en un entorno aislado compatible; cambiar solo a un contenedor antiguo puede fallar su preflight. No usar downgrade destructivo ni restaurar SQLite encima del proyecto existente.

## Siguiente prueba del usuario

Actualiza NEXO y revisa Configuración, Actores, Biblioteca y Reportes. Busca «sección 158» en documentos: debe identificar PRIMO VERDAD INEGI y 438. Abre el informe «Prueba PDF rezago», versión 2, y comprueba sus páginas del mismo PDF. En Fidelidad deben aparecer los integrantes; los indicadores de interacciones esperan capturas reales.

La prueba de una cuenta consultora real en nube sigue pendiente de crear o vincular esa identidad en Supabase. Las restricciones de consulta ya pasaron las pruebas de permisos. La aceptación final del usuario, el rendimiento con varios usuarios y la activación de proveedores se completan antes de declarar producción.
