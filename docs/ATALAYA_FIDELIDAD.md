> **Actualización: Configuración unificada.** Los formularios del superadministrador están en Configuración, separados por proyecto: Actores y cuentas, Equipo, Medios y RSS, Alertas y temas, APIs, Programación y Datos. En Fidelidad, pulsa el nombre de un integrante registrado para abrir su ficha. Reinicia el servidor 8002 y actualiza con Ctrl+F5. Consulta la guía CONFIGURACION_UNIFICADA.md.

> **27 de octubre: seguimiento del equipo registrado.** Se amplió Fidelidad con carga XLSX/CSV de colaboradores y sus cuentas, acciones observadas, orden por actividad, repetición sin duplicados y gestión exclusiva del superadministrador. Comunidad conserva únicamente totales agregados. Esta actualización amplía el alcance anterior, que todavía no incluía equipo nominal. Muestra aislada en 8004; aplicación habitual en 8002 después de reiniciar. Sin conexión nueva a Apify ni gastos. Guía actual: docs/FIDELIDAD_EQUIPO.md.

# Fidelidad: adaptación de Atalaya a NEXO

## Probar la pantalla

1. Abre **PROBAR_NEXO_FIDELIDAD.bat** en esta carpeta. Deja su ventana abierta.
2. Entra en **http://127.0.0.1:8004** con tu cuenta **local habitual**.
3. Abre **Fidelidad**. Esta copia tiene un proyecto de muestra y permisos de consulta, incluso para tu cuenta habitual de superadministración.
4. Revisa 7 días, 24 horas y fechas. Cambia de red; en «Actividad de» puedes elegir todas las cuentas o una sola. Prueba las pestañas Publicaciones/Menciones y las páginas de la tabla.
5. Estrecha la ventana: en móvil la tabla se convierte en tarjetas. La comprobación física desde otro teléfono no está habilitada; esta dirección funciona solo en esta computadora.

La muestra utiliza dos cuentas y publicaciones ficticias. Con el corte de siete días aparecen aproximadamente 30 publicaciones, según el momento de apertura. Abajo hay un ejemplo de continuidad agregada, también ficticio. No copia noticias, documentos, métricas o perfiles del D14. Solo reutiliza las credenciales locales dentro de una carpeta privada; no las incluye en los entregables.

En la muestra, la pestaña Menciones puede estar vacía: no contiene menciones reales ni inventa sus cifras. En NEXO esa pestaña consulta el archivo de menciones del actor seleccionado; no atribuye esas menciones a una cuenta específica sin evidencia.

## Qué se integró

- La organización de Atalaya: cuentas monitoreadas, indicadores, publicaciones y menciones, filtros y paginación.
- Contadores por publicación: reacciones, comentarios y compartidos disponibles. Un valor negativo de reserva se conserva como dato ausente, no como cero.
- Interacciones observadas y engagement del corte, con denominador explícito. Los seguidores son contadores de cuentas, no personas distintas entre redes.
- Importación local de publicaciones exportadas por Atalaya, solo para superadministración. El servidor valida cuenta, proyecto, fechas, tamaño y campos.
- Capturas conservadas en un registro propio de Fidelidad. Repetir una captura no duplica los indicadores; una captura distinta con la misma fecha se rechaza. Una nueva captura queda en el historial.
- La continuidad agregada que ya tenía NEXO permanece debajo, con sus propias cuentas, periodos y fuentes. La tabla superior y la continuidad no fingen usar la misma fuente.

La adaptación cambia solo el apartado de Fidelidad y su registro local. No se reemplazó la aplicación completa con el HTML de Atalaya. NEXO conserva su autenticación, proyectos, roles y marca. No se modificaron app/main.py, app/knowledge.py ni el mapa. Las demás pantallas mantienen sus archivos funcionales.

## Alcance de la adaptación

La actualización FIDELIDAD_EQUIPO.md incorpora el equipo nominal que registra el superadministrador y el orden por acciones observadas. No incorpora perfiles de personas no registradas ni postura política individual. Las publicaciones y la continuidad agregada conservan sus fuentes.

El ZIP aporta código, pero excluye los resultados de tu servidor. Por eso los datos reales de la otra aplicación no aparecen automáticamente en NEXO. Tampoco se importan las credenciales ni los usuarios de Atalaya.

No se arrancó el servidor original de Atalaya, sus tareas cada seis horas o sus lectores de perfiles. Apify y el análisis externo permanecen desactivados. La ejecución real, presupuestos y trabajadores se revisarán en la fase de conexión.

## Incorporar publicaciones guardadas en el piloto

Para la aplicación habitual, reinicia **ABRIR_NEXO_DESARROLLO_LOCAL.bat**, abre **http://127.0.0.1:8002** y actualiza con **Ctrl+F5**. El reinicio agrega una tabla local exclusiva de Fidelidad; no modifica las tablas de datos existentes.

1. Entra como superadministrador y abre Fidelidad.
2. Selecciona el actor y la red. Sus cuentas deben estar registradas y activas en Actores.
3. Abre «Incorporar publicaciones de Atalaya», elige la cuenta y selecciona resultados.json exportado por la otra aplicación.
4. El navegador selecciona únicamente las publicaciones de esa cuenta y construye una petición con campos permitidos. Las listas de autores, seguidores, equipo y postura no se envían al servidor ni se guardan.
5. La cuenta de consulta podrá ver el resultado, sin opciones de carga o configuración.

Solo se usan actualizado y los campos públicos de publicaciones: red, cuenta, url, fecha, texto, reacciones, comentarios, compartidos y seguidores. Las fechas deben incluir zona horaria. El archivo de origen admite hasta 5 MB; la petición normalizada, 1 MB y 500 publicaciones de una cuenta.

La importación no alimenta automáticamente Pulso, Redes o la Biblioteca: sus fuentes se conservan separadas. Los datos de retorno y participantes únicos requieren cortes agregados comparables de la fuente, no se deducen de los seguidores o de los contadores por publicación.

## Comprobaciones y límites

Se probaron el contrato, aislamiento entre proyectos, importación exclusiva del superadministrador, ausencia de identificadores de participantes, fechas, datos faltantes, duplicados, cambios de proyecto y descarga.

Las comprobaciones de interfaz usan DOM simulado. La revisión visual real en navegador de esta versión queda pendiente. Esta entrega es local: no acredita PostgreSQL/RLS nativo, actualizaciones programadas, conexión activa a Apify, IA ni producción. El registro nuevo requiere su migración y políticas antes de activar estas rutas en nube.

El código anterior al cambio se conserva en una copia de recuperación de trabajo. Si hubiera que revertir la interfaz, se restauran los archivos previos; no se elimina la tabla de Fidelidad ni se sobrescriben los datos del piloto.
