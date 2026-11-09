# Evaluación local de recuperación documental

Esta evaluación comprueba la selección de evidencia y sus permisos. No evalúa respuestas de un modelo, razonamiento, tono, emociones, búsqueda semántica o calidad de una futura IA.

## Contrato editable

`app/retrieval_evaluation.py` define `retrieval-evaluation-v1`. Un caso declara su identificador, proyecto, pregunta, archivo opcional, tipo de fuente, periodo y límite. Espera coincidencias concretas, ausencia de coincidencias o acceso denegado. La evidencia esperada puede fijar documento original, página de PDF, fila de Excel, tipo de fuente y texto literal. Los casos no contienen funciones ni instrucciones ejecutables.

El evaluador verifica proyecto, archivo elegido, ausencia de fuentes prohibidas, citas únicas, huellas, límites y ausencia de generación o llamadas externas. Se exige que aparezca toda la evidencia esperada; en ausencia de datos no se acepta una coincidencia arbitraria. Una fuente contradictoria se mantiene como una cita distinta: recuperar ambas versiones no significa que el sistema haya decidido cuál es verdadera.

Los resultados solo guardan identificadores de caso, cantidades y códigos de comprobaciones fallidas. No guardan preguntas, extractos, rutas privadas ni detalles de excepciones. El archivo de casos y sus expectativas se conserva separado y requiere revisión humana antes de aprobar un proveedor de IA.

## Muestra del piloto

La muestra del D14 tiene 23 casos: búsquedas exactas y preguntas sobre sección 158, otra fila, colonia, encabezado que no es un registro, números que no deben coincidir por subcadena, búsquedas por PDF/página, consultas ausentes, archivo equivocado, proyecto ajeno y un titular del archivo de prensa. Es una muestra pequeña y específica; aprobarla no mide toda la precisión del buscador ni certifica un RAG.

`NEXO_EVALUACION_DOCUMENTAL_CASOS.csv`, fuera del paquete genérico de código, permite revisar preguntas y expectativas del piloto. Los casos de ejecución se guardan junto al espacio privado de trabajo y no se incorporan a otros proyectos.

La evaluación detectó que «fue» coincidía dentro de «fuente» y retornaba fragmentos ajenos a una pregunta sobre temperatura de Groenlandia. La búsqueda actual utiliza palabras completas, omite expresiones habituales de pregunta y exige todos los términos útiles del tema. Sigue siendo léxica: no interpreta sinónimos ni resuelve cálculos o relaciones entre fuentes. El identificador explícito de sección conserva su búsqueda exacta por fila.

La selección de un archivo se aplica antes del límite del archivo general: cargar después otros documentos no debe desplazar al documento elegido. Las selecciones internas de Excel y PDF se consultan a través de sus originales, sin ofrecerlas como archivos independientes.

## Ejecución local

`scripts/evaluate_retrieval.py` recibe `--database`, `--uploads`, `--cases` y `--output`. Abre SQLite con `mode=ro` y `query_only`, sin acceso a claves ni creación de un servidor. Rechaza resultados dentro de la carpeta de originales o sobre la base y el archivo de casos. El resultado es JSON; el proceso devuelve error si un caso falla.

`scripts/check_local_readiness.py` añade revisión de dependencias, sintaxis, integridad SQLite, referencias, roles y configuración del iniciador local. La aprobación significa que se puede pasar a la prueba humana local. No comprueba por sí sola el navegador ni la configuración efectiva del proceso de servidor ya abierto. No acredita producción o conectividad con proveedores.

El acceso directo `COMPROBAR_NEXO_LOCAL.bat`, en la carpeta de entregables de esta instalación, ejecuta la comprobación con los casos privados del piloto. No necesita detener el servidor ni introducir una contraseña. Es específico de esta instalación; en otro equipo se deben configurar rutas y muestra propias.

## Antes de activar RAG

1. Revisar una muestra mayor de preguntas reales y las páginas/celdas que realmente las sustentan. Separar conjuntos de ajuste y de aceptación para no evaluar solo con ejemplos usados al desarrollar.
2. Versionar fuentes, extracción, modelo de embeddings, fragmentación, filtros y modelo de generación. Repetir las pruebas cuando alguno cambie.
3. Probar recuperación semántica, citas fieles, respuestas sin sustento, fuentes incompatibles e instrucciones maliciosas en los documentos. Exigir abstención cuando no exista sustento; ausencia de resultados léxicos no prueba ausencia de información en toda la colección.
4. Ensayar permisos y límites con PostgreSQL nativo y la identidad de nube. Los documentos nunca deciden herramientas, destinos, permisos o presupuesto.
5. Conectar adaptadores y trabajadores con muestras permitidas, cuotas, reintentos, recuperación y costos autorizados. Las métricas deben proceder de datos reales; un modelo no crea estadísticas de redes ni convierte contenido observado en una encuesta de población.
