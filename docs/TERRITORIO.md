# Territorio: reutilización de la vista validada

Se conserva la vista histórica que ya funcionaba. El SVG de `realMap` es idéntico al de `NEXO_Integrado_D14`, `NEXO_Atalaya_Candidato_D14` y `NEXO_v0_5_D14`: 45 secciones y 721 polígonos de manzanas. Se mantienen su distribución visual, colores, leyenda, selección por mapa o teclado, búsqueda, detalle y descarga CSV.

## Datos conservados

- Año: 2024.
- Lista nominal territorial: 65,378.
- Votos territoriales: 41,984.
- Votos oficiales: 41,992, incluidos 8 anticipados sin asignación geográfica.
- La participación territorial se calcula con votos territoriales y lista nominal; no incluye esos ocho votos en las secciones.

Las fuentes son el libro histórico electoral y los KML de secciones, manzanas y delimitación ya incorporados. No se recalculó la cartografía ni se sustituyeron sus datos. Los indicadores corresponden a historia electoral, no a opinión actual.

## Ajustes acotados

Al cambiar de proyecto se limpian búsqueda, selección, resaltado y capa de manzanas. El mapa D14 se muestra únicamente en ese proyecto con su histórico conciliado. En otro proyecto la tabla queda vacía y la descarga de esta vista permanece desactivada. La descarga verifica de nuevo el proyecto y la versión de la vista antes de usar una respuesta tardía, incluso cuando se sale y regresa al mismo proyecto.

El mensaje técnico sobre ausencia de servidor de producción se retiró de la nota de fuentes. No se añadieron controles de proveedor ni avisos sobre funciones desconectadas.

Las rutas autenticadas existentes de resumen, secciones y exportación siguen comprobando membresía del proyecto. No se modificaron `app/main.py`, `app/knowledge.py`, las tablas ni las políticas SQL. No hay migración nueva: la versión preparada sigue siendo `008_actor_profiles`.

## Alcance para otros proyectos

Los demás clientes conservarán sus propios datos territoriales. Cargar un archivo en Fuentes no crea automáticamente otro mapa: su futura integración necesita validar cartografía, tabla, año y correspondencia de secciones. Esta entrega reutiliza el D14 y evita replicar su información en el resto de los proyectos.

## Verificación de esta entrega

17 pruebas Python dirigidas aprobadas —6 de Territorio y 11 de regresión documental—, junto con 75 comprobaciones de controladores JavaScript, incluidas 14 de Territorio. Se verificaron también la sintaxis y la coincidencia del hash CSP. Los controladores se ejecutaron con DOM simulado; no hubo una sesión de navegador controlada por el agente. La regresión completa anterior de 231 pruebas y las 119 comprobaciones SQL no se repitieron, dado que no cambiaron el backend ni las políticas.

Las huellas del SVG y de las filas territoriales permanecen iguales. Las fichas de actores configuradas por el usuario también se conservan. El resultado detallado está en `TERRITORIO_RESULTADO.json`.

Para cargar el ajuste, reiniciar con `ABRIR_NEXO_DESARROLLO_LOCAL.bat` y abrir **Territorio**. La pantalla conserva el recorrido ya conocido. Siguiente módulo de revisión: **Redes**.
