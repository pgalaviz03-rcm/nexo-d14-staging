# Pulso: panorama del proyecto

## Abrir la nueva presentación

1. En la ventana de la prueba del puerto **8003**, pulsa **Ctrl+C**.
2. Abre de nuevo **PROBAR_NEXO_DISENO.bat**.
3. Entra en **http://127.0.0.1:8003**, actualiza con **Ctrl+F5** y usa tu cuenta local habitual.

La muestra conserva cuatro actores inventados, 360 menciones del corte de 24 horas, emociones, titulares, cuentas y alertas. Esta copia muestra la experiencia de consulta y no modifica el D14. Si el puerto 8003 no estaba abierto, comienza directamente en el paso 2.

Para ver el mismo diseño con los datos del piloto, reinicia **ABRIR_NEXO_DESARROLLO_LOCAL.bat** y actualiza **http://127.0.0.1:8002**. Ahí no se rellenan métricas pendientes con datos inventados.

## Qué cambió

- Encabezado «La conversación, de un vistazo», periodo y canal en una barra ordenada, y filtros de actor separados.
- Cuatro indicadores: menciones, presencia en la conversación, contenido favorable y alertas. Cuando se observan todos los actores, «Mayor presencia» identifica al de mayor participación; al elegir uno se muestra su parte de la conversación.
- Panel principal con índice de tono, reparto favorable/neutral/desfavorable y emociones. El índice va de 0 a 100 y describe contenido clasificado, no una encuesta de la población. Los porcentajes se calculan sobre las menciones clasificadas suficientes.
- Actores en filas compactas, con iniciales, índice expresamente etiquetado, menciones y participación. Se eliminó el mensaje repetido de «línea base».
- Titulares recientes con enlace, fuente y fecha. El orden usa fecha de publicación, también para RSS; no se presenta como un ranking de alcance o lectores.
- Cuentas en tarjetas con **seguidores, publicaciones e interacciones**. Sin vistas, alcance único ni impresiones. Se muestra la fecha del registro; si existe una comparación de seguidores válida, se indica desde qué fecha.
- «Cómo se calculan estos indicadores» queda solo para el superadministrador. El cliente conserva la consulta sin controles de gestión.
- En móvil, el contenido pasa a una columna, los indicadores a dos columnas, los actores se pueden recorrer y las emociones comienzan plegadas. Se conservaron controles de al menos 44 px y las listas con presentación propia.

## Las dos expresiones anteriores

«Cambio en el tono» era la diferencia entre el índice actual y el de las menciones guardadas en los 90 días anteriores al inicio del corte. No era el porcentaje de personas que cambió de opinión. Ese indicador principal se sustituyó por **Contenido favorable**, un porcentaje del contenido clasificado.

«Sin línea base suficiente» significaba que no había clasificación anterior suficiente para comparar. Se retiró esa frase. La comparación histórica aparece como una línea secundaria únicamente cuando es calculable, con sus fechas; si no existe, no ocupa espacio ni muestra una diferencia inventada.

«Audiencia única» aludía a personas distintas alcanzadas. No se obtiene contando menciones o sumando seguidores. Se retiró de Pulso junto con los indicadores de audiencia no previstos para las fuentes del proyecto.

## Prueba de uso

Revisa primero 24 horas y todos los actores; después elige uno, cambia canal y amplía a 30 días. Los porcentajes, titulares y cuentas deben respetar el filtro. Un filtro sin datos puede quedar vacío. Revisa también la ventana estrecha de 390 y 768 px y confirma que no aparece el desplegable técnico al consultor.

131 pruebas de Pulso, Briefing, entrega y permisos aprobadas; dos verificaciones finales de fecha/fuente aprobadas (una se solapa con ese bloque). 262 comprobaciones JS en DOM simulado. No se suman las ejecuciones como pruebas distintas. Esto no acredita renderizado en navegador: queda pendiente la revisión visual de esta versión.

El D14, su mapa, documentos, histórico y cuentas se conservan. No se modificaron `app/main.py` o `app/knowledge.py`. No se conectaron APIs, IA o servicios de nube; las clasificaciones de la muestra son ficticias.
