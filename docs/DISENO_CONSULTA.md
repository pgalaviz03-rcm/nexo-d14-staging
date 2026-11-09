> **Pulso actualizado:** nueva composición de inicio; tono y emociones destacados; actores compactos; titulares por fecha y cuentas solo con seguidores/publicaciones/interacciones. Se retiraron las referencias de audiencia y el desplegable técnico al lector. Comparación histórica secundaria únicamente con datos y fechas. 131 pruebas del bloque y dos verificaciones finales con solapamiento; 262 comprobaciones JS. Revisión visual humana pendiente. Consulta NEXO_PULSO_REDISENO_GUIA.md o docs/PULSO_REDISENO.md. Las cifras de pruebas inferiores conservan el historial.

# NEXO: consulta, móvil y muestra visual

## Qué cambió

- Las cuentas de cliente solo consultan sus proyectos: navegan, filtran, buscan y descargan información autorizada. No cargan archivos, crean fichas, guardan informes, cambian reglas, revisan clasificaciones ni configuran envíos. La protección se aplica en el servidor, además de ocultar los controles.
- El superadministrador conserva la gestión. Los roles anteriores de proyecto no conceden edición si la cuenta no tiene un permiso activo de superadministración. La base de membresías se conserva; la política local determina el acceso efectivo.
- Los clientes ven únicamente las versiones de informes habilitadas para lectores. Un borrador del administrador no se vuelve visible por tener antiguamente el rol de analista o administrador de proyecto.
- La interfaz usa paneles más compactos, menos bordes y espacios vacíos, navegación lateral ordenada y filtros consistentes. En móvil hay menú desplegable, accesos inferiores y contenido en una columna; los indicadores usan dos columnas.
- Las listas desplegables tienen presentación propia, búsqueda en listas largas, control por teclado y selección coherente con los formularios existentes. Se conserva el selector original como base del formulario y alternativa sin JavaScript.
- Se retiraron «Vista simplificada», «Otro» del filtro de Pulso y el botón de demostración. En móvil, el detalle de emociones comienza plegado para dar prioridad al tono y los indicadores.

## 1. Tu NEXO habitual

1. Detén la ventana del puerto **8002** con **Ctrl+C**.
2. Abre **ABRIR_NEXO_DESARROLLO_LOCAL.bat** y actualiza el navegador con **Ctrl+F5**.
3. Entra como consultor: debe ver las pantallas y documentos autorizados, sin cargas ni configuraciones. Sus antiguos permisos de escritura ya no habilitan acciones.
4. Entra con tu cuenta de superadministrador en otra ventana para revisar que conserva la administración.

Los datos reales del D14 no se llenaron con cifras inventadas. Las referencias y el histórico originales se conservan. La cuenta de consultor sigue asignada a su proyecto.

## 2. Prueba visual con Pulso precargado

1. Abre **PROBAR_NEXO_DISENO.bat** desde esta carpeta y deja abierta su ventana.
2. Entra en **http://127.0.0.1:8003** con tu cuenta **local habitual**.
3. Esta copia te muestra la experiencia de **consulta**, incluso si en el piloto tu cuenta es superadministradora.
4. En Pulso aparecen cuatro actores ficticios, 360 menciones del corte, cinco emociones, titulares, dos tarjetas de cuentas y dos alertas. Cambia actor, canal y periodo para observar el comportamiento. El índice y las variaciones se calculan sobre registros ficticios guardados, sin IA ni servicios externos.

La muestra es una base privada independiente. No copia las noticias, documentos o métricas del D14. Reutiliza las credenciales locales únicamente dentro de la carpeta privada para evitar pedir otra contraseña; no las incorpora al código o al ZIP entregable. La muestra no tiene permisos de superadministración y marca todo su contenido como ficticio. El inicio de la prueba actualiza sus fechas para que los datos aparezcan en el corte de 24 horas.

En la aplicación, la etiqueta **Vista de prueba** distingue esta muestra; no hay un botón para alternar demostración en el proyecto real. Las demás pantallas de la copia de prueba no se presentan como llenas de información real.

## Revisar móvil y escritorio

- En escritorio comprueba el tamaño de los paneles, la lectura del tono y el acceso a titulares y cuentas. Los ajustes son comunes a las pantallas del producto.
- Estrecha la ventana o utiliza la vista de dispositivo del navegador, con anchos de **390 px** y **768 px**. Revisa el menú, los accesos inferiores, los filtros, el desplazamiento por actores y los desplegables.
- Las listas largas se pueden buscar. Con teclado se abren con Enter o flechas, se elige una opción y se cierran con Escape. El menú móvil devuelve el foco a su botón al cerrarlo.
- Revisa que el superadministrador pueda seguir configurando y que el cliente no vea opciones de gestión, incluso después de cambiar de pantalla o proyecto.

Estas direcciones se sirven solo en esta computadora. La comprobación física desde otro teléfono requiere un acceso de prueba independiente; no se expuso el servidor a la red local o a internet.

## Verificación y alcance

Las pruebas verifican la política del servidor, la ocultación de borradores, los controles, la navegación y los contratos de Pulso. Los controladores de interfaz se prueban con DOM simulado, sin acreditar renderizado real o ausencia de todo desbordamiento en cada dispositivo. La revisión visual en navegador de esta versión queda para tu comprobación con la muestra.

No se modificaron `app/main.py`, `app/knowledge.py`, las tablas, el histórico del D14, los servicios de nube o los proveedores. La nueva política se instala en el espacio de trabajo **local**; tendrá que trasladarse y validarse junto con PostgreSQL/RLS e identidad antes de activar la versión de nube.
