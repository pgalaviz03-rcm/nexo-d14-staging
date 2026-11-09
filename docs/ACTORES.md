# Actores: fichas públicas del proyecto

La sección permite consultar y preparar los actores públicos que se observarán en cada proyecto. Reutiliza las identidades de Pulso: no crea un segundo directorio ni asigna los mismos datos a todos los clientes.

## Recorrido de revisión

1. Reinicia la copia local con `ABRIR_NEXO_DESARROLLO_LOCAL.bat` y abre **Actores**.
2. Comprueba los indicadores de actores activos, referencias de cuentas en seguimiento, enlaces por revisar y actores archivados. Son registros de configuración, no estadísticas obtenidas de una red.
3. Busca por nombre, nombres alternativos, cargo, organización o territorio; alterna entre activos, archivados y todos.
4. Abre una ficha. Debe mostrar sus referencias públicas, contexto, menciones existentes en archivo y capturas de cuentas. «Ver en Pulso» usa el mismo actor e inicia la consulta con datos reales del proyecto.
5. Como administrador o editor, añade o edita una ficha. Nombre y función principal/comparativa son suficientes; los demás campos pueden estar vacíos. Cada referencia permite elegir red, URL, identificador público del proveedor, seguimiento y revisión humana del enlace. «Referencia revisada» no es una verificación otorgada por la red social.
6. Para sustituir al principal, usa **Hacer principal** en otro actor activo. El cambio es atómico: el anterior pasa a comparativo. Para detener su observación, archívalo. El historial y la ficha se conservan. Si reactivas un antiguo principal mientras existe otro principal activo, vuelve como comparativo.
7. Con una cuenta de consultor o lector, comprueba la consulta sin botones para modificar la configuración. Cambiar de proyecto limpia las fichas, referencias y formularios; una edición sin guardar pide decidir si se descarta.

No es obligatorio rellenar todos los campos. Las fichas guardan información pública necesaria para el proyecto; no son perfiles de votantes ni contienen instrucciones de persuasión individual.

## Estructura y permisos

- `pulse_actors` conserva identidad, nombre, función, estado y versión.
- La tabla nueva `actor_profiles` añade cargo, organización, territorio, descripción pública, nombres alternativos y referencias de cuentas. Clave compuesta de referencia al actor/proyecto/modo real. Una ficha no puede referirse a un actor de otro proyecto ni de demostración.
- Perfiles preexistentes de Pulso aparecen con ficha vacía y versión 0; al completarlos se crea solo el perfil. No se duplican actores ni se cargan nombres ficticios en el D14.
- Lectura: miembros del proyecto. Edición, alta, archivado y cambio del principal: administrador y editor. El superadministrador opera mediante sus membresías explícitas; ser administrador de un proyecto no concede control de plataforma.
- Edición con dos versiones: identidad de actor y perfil. Un conflicto revierte ambos cambios. La bitácora registra identificadores y versiones, no descripciones ni URLs.
- RLS de PostgreSQL habilitada y forzada; `nexo_app` no puede mover el vínculo a otro proyecto/actor, falsificar al autor de una actualización ni borrar perfiles. Consultores y lectores no modifican perfiles.
- Migración aditiva `008_actor_profiles`: total 31 tablas. Ensayo de actualización y repetición sobre copia aislada antes de modificar SQLite local. Las filas anteriores y el histórico D14 se comprueban por huellas.
- Se conservan `app/main.py` y `app/knowledge.py` sin modificaciones.

## Contrato para la conexión final

`GET /api/projects/{pid}/actors` devuelve las fichas propias y capacidades del usuario. `POST /actors` crea actor y perfil en la misma transacción; `PUT /actors/{id}` edita ambos con versiones esperadas; `PATCH /actors/{id}/state` archiva/reactiva, y `POST /actors/{id}/primary` sustituye al principal con la identidad y versión esperadas del anterior.

Hasta 50 actores reales por proyecto, incluidos archivados; 12 nombres alternativos y 12 referencias por ficha. Nombre normalizado, comprobación de duplicados sin distinguir mayúsculas en las rutas del directorio y de Pulso. Los enlaces requieren HTTPS público sin credenciales, IP literal ni claves de API. Los dominios de Facebook, Instagram, X, TikTok y YouTube deben corresponder a la red seleccionada. Guardar o revisar una referencia **no abre una conexión**, no confirma su existencia y no recupera estadísticas.

Las referencias contienen `network`, `url`, `external_id`, `enabled` y `review`. Quedan listas como configuración para el adaptador futuro de escucha y capturas. El importador actual de Apify continúa recibiendo `actor_ids` explícitos del proyecto; no hay asociación automática por alias ni sincronización de estos enlaces todavía. Al activar un adaptador habrá que resolver identificadores, comprobar propiedad/relevancia de las cuentas, alcance de permisos, cuotas y validar URLs/DNS/redirecciones antes de cualquier solicitud de red. Ninguna credencial se guarda en estas fichas ni en el navegador.

La pantalla separa referencias configuradas de capturas existentes. Registrar un perfil no inventa seguidores, vistas, alcance ni emociones. El detalle permite abrir el enlace público con protección de la ventana de origen. No usa cargas remotas de avatares; las iniciales se dibujan localmente.

## Verificación

Los resultados precisos están en `ACTORES_RESULTADO.json`. Las pruebas usan bases y actores ficticios: alta y persistencia, compatibilidad con Pulso, permisos y separación de proyectos, conflictos, cambios de principal, archivo con historial, enlaces seguros y ausencia de llamadas externas. Los controladores JS se prueban con DOM simulado: esta entrega requiere aún la comprobación visual del usuario en su servidor habitual. PostgreSQL WASM verifica las políticas SQL; no equivale a aceptación en PostgreSQL nativo ni a un despliegue.
