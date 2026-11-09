> **Actualización: Configuración unificada.** Los formularios del superadministrador están en Configuración, separados por proyecto: Actores y cuentas, Equipo, Medios y RSS, Alertas y temas, APIs, Programación y Datos. En Fidelidad, pulsa el nombre de un integrante registrado para abrir su ficha. Reinicia el servidor 8002 y actualiza con Ctrl+F5. Consulta la guía CONFIGURACION_UNIFICADA.md.

# Gestión de todos los proyectos desde Superadministración

## Corrección

Un proyecto nuevo conserva los permisos del superadministrador aunque todavía no tenga actores, cuentas, capturas o equipo. Fidelidad debe cargar su gestión en ese estado. Antes se detenían dos controladores al no encontrar actor seleccionado, y también se omitía la consulta de permisos del equipo. Eso hacía que la pantalla pareciera de consulta.

Se eliminaron esas dos dependencias de la carga de la pantalla. Las consultas utilizan actor_id=0 cuando aún no existe un actor; no envían null o undefined. No se modificaron roles, membresías ni datos del D14 para resolverlo.

## Uso

1. Detén con Ctrl+C la ventana del servidor 8002 y vuelve a abrir ABRIR_NEXO_DESARROLLO_LOCAL.bat.
2. Actualiza http://127.0.0.1:8002 con Ctrl+F5 e ingresa con tu cuenta local de superadministrador.
3. Selecciona otro proyecto. En Fidelidad → Gestionar equipo y registros puedes cargar el Excel o registrar integrantes uno a uno, aunque el proyecto todavía no tenga actor principal.
4. En Actores puedes añadir el actor principal y sus cuentas. Una vez que haya cuentas registradas, Fidelidad habilita la incorporación de actividad de esas cuentas. El equipo cargado previamente se conserva.
5. Regresa al D14: deben aparecer sus propios actores, documentos y equipo. Los datos no se copian de un proyecto a otro.

La falta de una cuenta observada impide importar actividad de esa cuenta; no elimina el permiso de administrar el equipo. Los indicadores siguen sin cifras cuando no hay datos. No se precargaron datos ficticios en los proyectos reales.

## Alcance de la comprobación

Se revisaron los permisos del servidor en Pulso y su configuración, Briefing, Actores, Territorio, Redes, Fidelidad y equipo, Alertas, Explorador, Reportes, Auditoría de cuentas, Biblioteca, revisión documental y fuentes. Se comprobaron proyectos existentes y un proyecto sintético nuevo asignado a otra cuenta, con acceso administrativo del superadministrador.

La API de creación de proyectos ya agrega las membresías administrativas de los superadministradores activos. Se comprobó este comportamiento y se mantuvo. Los consultores continúan en modo de consulta, incluso si su membresía histórica se llama admin, editor o analyst: no reciben permisos de plataforma y el control de solicitudes impide sus modificaciones.

La regresión de interfaz ejecuta juntos los controladores reales de Continuidad, Fidelidad, Equipo y Actores: cambio a un proyecto vacío, gestión antes del primer actor, alta de un integrante, primer actor, regreso al proyecto anterior, cuenta lectora y descarte de una respuesta tardía. Usa DOM simulado; la comprobación visual real sigue pendiente.

Esta corrección es local. No ejecuta Apify, IA, envíos ni servicios de nube. Se conservan app/main.py, app/knowledge.py y el mapa territorial.
