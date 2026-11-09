> **27 de octubre: seguimiento del equipo registrado.** Se amplió Fidelidad con carga XLSX/CSV de colaboradores y sus cuentas, acciones observadas, orden por actividad, repetición sin duplicados y gestión exclusiva del superadministrador. Comunidad conserva únicamente totales agregados. Esta actualización amplía el alcance anterior, que todavía no incluía equipo nominal. Muestra aislada en 8004; aplicación habitual en 8002 después de reiniciar. Sin conexión nueva a Apify ni gastos. Guía actual: docs/FIDELIDAD_EQUIPO.md.

> **27 de octubre: Fidelidad adaptada desde Atalaya.** Bloque de cuentas, publicaciones y métricas agregadas dentro del apartado existente; importación local solo para superadministración y registro separado. Se mantienen sesiones y proyectos de NEXO. Sin perfiles nominales, postura política individual, tareas automáticas o conexión nueva a Apify. App principal, conocimiento, mapa y datos del D14 conservados. Prueba aislada con PROBAR_NEXO_FIDELIDAD.bat (8004); piloto habitual 8002 después de reiniciar. Revisión final: 166 pruebas Python y 277 comprobaciones de interfaz simulada. Falta la revisión visual humana. Guía: docs/ATALAYA_FIDELIDAD.md.

> **Pulso actualizado:** nueva composición de inicio; tono y emociones destacados; actores compactos; titulares por fecha y cuentas solo con seguidores/publicaciones/interacciones. Se retiraron las referencias de audiencia y el desplegable técnico al lector. Comparación histórica secundaria únicamente con datos y fechas. 131 pruebas del bloque y dos verificaciones finales con solapamiento; 262 comprobaciones JS. Revisión visual humana pendiente. Consulta NEXO_PULSO_REDISENO_GUIA.md o docs/PULSO_REDISENO.md. Las cifras de pruebas inferiores conservan el historial.

> **Política y diseño vigentes — 21 de octubre de 2026:** solo el superadministrador gestiona. Todas las demás cuentas consultan sus proyectos, buscan y descargan recursos autorizados; no cargan, guardan, publican ni configuran. La regla se aplica en el servidor local y oculta borradores. Interfaz compacta y adaptable, desplegables propios, sin «Vista simplificada», «Otro» de Pulso o botón de demostración. La muestra ficticia se abre con PROBAR_NEXO_DISENO.bat (8003); el piloto conserva 8002. 625 pruebas Python y 255 comprobaciones JS aprobadas. Falta revisión visual humana. Ver NEXO_DISENO_CONSULTA_GUIA.md o docs/DISENO_CONSULTA.md. Las referencias inferiores a roles editores/analistas pertenecen al historial y no conceden escritura actual. Nube y proveedores no se modificaron.

# Cierre del bloque local y prueba general

La Biblioteca local permite buscar noticias, TXT/MD/CSV, PDF con texto por página y selecciones de Excel por fila/celda. El usuario validó búsqueda, lector de páginas e informe limitado a un PDF en su versión 2. Los originales y la versión 1 se conservan.

Se agregó una evaluación declarativa de recuperación y un comprobador de solo lectura. La muestra del piloto tiene 23 casos aprobados, incluidos dos que antes retornaban fragmentos incorrectos al confundir una palabra con parte de otra. Las consultas ahora usan palabras completas y exigen los términos útiles del tema. La muestra es limitada y no certifica semántica o generación.

## Próximo paso de uso

Seguir `PRUEBA_GENERAL_LOCAL.md` con una cuenta de consultor y la de superadministrador. La guía reúne los recorridos de todas las pantallas para registrar errores y confusiones de forma conjunta. Los resultados automatizados vigentes están en `PRUEBA_GENERAL_RESULTADO.json`.

La plataforma está preparada para esa prueba local, no para declararla producción. Las métricas sin capturas externas conservan estados sin datos. Las preferencias de entrega tienen simulación; no hay envíos reales. IA, embeddings y adaptadores externos siguen desactivados.

## Secuencia de trabajo

1. Prueba general local y correcciones de acceso, datos, guardado y fuentes.
2. Ajustes de diseño y presentación por rol, preservando los recorridos aceptados.
3. Integración de adaptadores y trabajadores con muestras reales permitidas, modelos evaluados, límites, cuotas y costos autorizados.
4. Validación en PostgreSQL nativo/RLS, identidad y MFA, activación de los módulos en nube, HTTPS y monitoreo.
5. Prueba de recuperación independiente del equipo, reversión y aceptación antes de producción.

No se introduce hoy un proveedor ni se transfiere información. Conectar claves por sí solo no implementa los adaptadores, trabajadores, permisos o validaciones pendientes. El respaldo local DPAPI sirve para este perfil Windows; la copia externa recuperable sigue pendiente.

`MATRIZ_CONEXIONES_LOCAL.csv` distingue lo implementado de lo que falta. `EVALUACION_RECUPERACION.md` explica cómo ampliar la muestra y preparar la evaluación del RAG. No se modifican los archivos protegidos `app/main.py` y `app/knowledge.py`, las tablas o el histórico territorial.
