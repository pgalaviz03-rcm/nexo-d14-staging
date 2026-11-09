# Recorrido por proyecto y rol · validación local

## Estado

El usuario aceptó Auditoría de cuentas después del ajuste de visibilidad: «Sí, ahora aparecen». La revisión siguiente comprueba la experiencia de cuentas y proyectos. El código funcional de las pantallas no cambia en esta etapa.

La comprobación inicial de la copia real fue de solo lectura: había dos proyectos activos y una cuenta activa, con concesión explícita de superadministrador y membresías de administrador en ambos. Posteriormente el usuario creó y asignó la cuenta local de prueba: se verificó activa, con una sola membresía D14 de consultor y sin concesión de plataforma. El usuario confirmó su inicio de sesión, selector limitado al D14 y ausencia de Superadministración. El agente no creó ni reactivó cuentas, no cambió permisos y no leyó ni restableció contraseñas.


El usuario confirmó la presencia de las cuatro secciones de la consola: «Sí, aparecen las cuatro secciones». La creación y asignación al D14 fueron confirmadas después por el usuario y verificadas en modo de solo lectura; el inicio de sesión como consultor ya fue confirmado por el usuario.

## Permisos vigentes

| Acción | Superadministrador | Admin del proyecto | Editor | Consultor / analista | Lector |
|---|---|---|---|---|---|
| Consultar las pantallas del proyecto | Todos los proyectos activos vinculados | Solo asignados | Solo asignados | Solo asignados | Solo asignados |
| Administrar marca, usuarios, proyectos y membresías | Sí, en consola global local | No | No | No | No |
| Gestionar fichas de Actores y reglas | Sí | Sí | Sí | No | No |
| Incorporar capturas y revisar hallazgos | Sí | Sí | Sí | Sí | No |
| Guardar borradores de informes | Sí | Sí | Sí | Sí | No |
| Habilitar informes para lectores | Sí | Sí | Sí | No | No |
| Leer informes | Incluye borradores | Incluye borradores | Incluye borradores | Incluye borradores | Versiones habilitadas |
| Descargar diagnóstico de cuentas | Sí | Sí | Sí | Sí | Sí |

Superadministración es un permiso separado, no otro nombre del rol administrador de proyecto. La concesión global crea membresías administrativas auditadas en los proyectos activos; los proyectos nuevos también vinculan a los propietarios de plataforma. Cambiar el identificador de proyecto en la dirección de una petición no concede acceso. Una cuenta de consultor puede tener más de un proyecto solamente si recibe membresías adicionales explícitas.

Las pantallas comparten diseño y módulos; la membresía decide datos y acciones. No son copias separadas del sitio. La autorización se comprueba en cada petición del servidor, aunque alguien manipule la interfaz. El cambio de proyecto limpia las vistas de los módulos; las pruebas de sus controladores cubren el descarte de respuestas tardías. El acceso al proyecto siguiente requiere membresía.

## Prueba manual con la cuenta principal

1. En el lateral, abrir **Superadministración**. Deben verse Marca de la plataforma, Nuevo proyecto, Cuenta local, Membresía de un proyecto, Proyectos y Cuentas registradas.
2. Consultar las membresías sin cambiar permisos. El selector del espacio de trabajo debe ofrecer los proyectos autorizados a esta cuenta.
3. Abrir el D14 y comprobar que conserva sus noticias, actores y territorio. Cambiar a otro proyecto no debe mostrar sus datos como si fueran propios.

No hace falta crear otro proyecto para validar la consola ni cambiar el nombre de la marca.

## Preparar una cuenta local de consultor

Esta operación se hará directamente en la interfaz por el usuario, con una contraseña nueva que nunca se comparte en el chat.

1. En **Cuenta local**, usar como identificador de prueba `consultor.prueba@nexo.local`. Es un identificador local; no envía correo. Escribir una contraseña exclusiva de al menos 12 caracteres y pulsar **Crear cuenta local**.
2. En **Membresía de un proyecto**, seleccionar únicamente **Distrito 14**, la cuenta recién creada y **Consultor / analista**; pulsar **Guardar membresía**. Crear una cuenta por sí solo no le asigna un proyecto.
3. Conservar abierta la sesión de superadministrador. Abrir una ventana privada del navegador, entrar en http://127.0.0.1:8002 e iniciar sesión con esa cuenta de prueba.
4. Debe aparecer solo D14 en el selector, sin Superadministración. Sus pestañas deben mostrar los datos D14. El consultor puede preparar borradores y consultar el diagnóstico; no puede gestionar fichas/reglas ni habilitar informes para lectores.

No usar el correo o contraseña de Supabase para esta prueba. No reactivar otras cuentas ni modificar tu membresía principal. La cuenta puede desactivarse después desde la consola de superadministración. Para probar también al lector, se puede cambiar el rol de esta cuenta y actualizar su sesión, conservando la cuenta principal.

## Verificación automatizada y límites

`tests/test_project_journeys.py` recorre las rutas de Pulso, Briefing, Actores, Territorio (resumen y secciones), Redes, Fidelidad, Alertas, Explorador, Reportes y Auditoría. Comprueba roles, acceso ajeno, revocación, proyectos inactivos y un proyecto nuevo sin información heredada.

Los escenarios usan bases SQLite aisladas y cuentas sintéticas. Prueban los manejadores reales y la autorización del servidor; no sustituyen una prueba completa de HTTP, autenticación en navegador, MFA o PostgreSQL nativo. Los resultados exactos y el alcance de las comprobaciones anteriores se guardan en `VALIDACION_ROLES_RESULTADO.json`.

La consola global actual está habilitada únicamente para desarrollo local. La administración en nube requiere su servicio y controles correspondientes. Las APIs externas, modelos y envíos permanecen desconectados. Esta etapa no conecta proveedores ni prepara una publicación automática.

Después del alta del usuario se actualizó el respaldo local cifrado y se verificó su restauración aislada. Sigue limitado a este perfil Windows; no es una copia externa.

Aceptación manual de inicio de sesión: «Sí, solo D14 y sin Superadministración». El usuario también confirmó los cuatro actores sin gestión y la lectura del informe existente con sus fuentes: «Sí, actores e informe correctos». No implica aceptación nativa de PostgreSQL ni publicación en nube.
