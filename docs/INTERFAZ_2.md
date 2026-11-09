# NEXO · Segunda entrega de interfaz

19 de octubre de 2026 · Desarrollo local D14 · Puerto 8002

Se integró el archivo `html2code-1792460355931.html` como versión adaptada de `static/index.html`. Se aprovecharon la distribución, el inventario, la biblioteca, los estados vacíos y el espacio de reportes. Todo el código Python de `app/` y el módulo `static/reviews.js` conservaron exactamente sus hashes anteriores. La actualización no modifica cuentas, modelos, esquema ni datos.

## Estados visibles

| Estado | Pantallas y alcance |
|---|---|
| Operativo en local | Biblioteca, fuentes, noticias guardadas, ficha documental, revisión manual y archivo histórico. Cada consulta utiliza los permisos actuales. |
| Datos de demostración | Inicio ejecutivo: cantidades, pulso, emociones, titulares ficticios y porcentajes de ejemplo. No representan mediciones reales. |
| Pendiente de integración | Reportes guardados y versiones: pantalla preparada; aún no guarda ni consulta reportes persistentes. |

Cada pantalla muestra su estado y la cabecera lo actualiza al navegar. Los estados incluyen texto, además de color. La vista simplificada cambia la presentación; no cambia el rol de la cuenta.

## Adaptaciones necesarias

El archivo recibido todavía etiquetaba como operativas las métricas ficticias del inicio, la caché y funciones de perfiles que no forman parte del servidor actual. Se corrigieron esas afirmaciones y se conservaron los accesos documentales existentes. No se incorporaron simulaciones políticas por perfiles ni llamadas a rutas de personas o redes sociales.

El mapa recibido contenía cuatro figuras de sección. Se mantuvo el mapa completo de 45 secciones y las geometrías existentes. También se conservó «Temas y revisión», ausente del adjunto, y la ficha documental compatible con la respuesta real de la API. El radar ahora muestra solo el archivo consultable; sus antiguos ejemplos visuales se retiraron de esa pantalla.

La biblioteca declara los límites de extracción: TXT/MD y CSV consultables; PDF/XLSX almacenables, con extracción pendiente. El registro de archivos conserva hash y estado; no se anuncia un sistema de versiones de archivos que todavía no existe. Reportes muestra «—» en versiones y un acceso funcional a la ficha documental, sin inventar reportes guardados.

## Cargar la actualización

1. En la ventana del servidor del puerto 8002, pulsa Ctrl+C.
2. Abre `ABRIR_NEXO_DESARROLLO_LOCAL.bat` en outputs y deja su ventana abierta.
3. Actualiza `http://127.0.0.1:8002` con Ctrl+F5 e inicia sesión con tu cuenta local habitual.
4. Comprueba las etiquetas al cambiar entre Inicio ejecutivo, Biblioteca y Reportes. Revisa también el mapa y «Temas y revisión».

No se cambió tu contraseña ni hace falta introducir claves externas. La comprobación visual en navegador sigue pendiente. La herramienta de navegador encontró previamente un bloqueo de política de URL; no se intentó eludirlo ni se usa una captura antigua como prueba de esta interfaz.

## Validación y trabajo siguiente

65 pruebas Python aprobadas: los 64 casos existentes y una comprobación de regresión del mapa completo y los estados de demostración/reportes. Los dos scripts JavaScript pasaron revisión de sintaxis; los identificadores del HTML coinciden con sus controladores. Las pruebas usan las rutas y base directamente; no se repitió la suite HTTP completa ni la aceptación visual. No hay cambios SQL que requieran repetir las pruebas PostgreSQL en esta entrega.

Los datos locales se comprobaron en lectura: 45 secciones de 2024, 41,984 votos territoriales y lista nominal de 65,378. Los conteos de noticias, archivos, temas, revisiones e historial coinciden antes y después. No se desplegó código ni se activaron conexiones o pagos.

Puedes continuar con diseño, textos y presentación sobre el HTML adaptado que acompaña esta guía. Para evitar regresiones, conserva `static/reviews.js`, los identificadores de formularios y el mapa completo. Envía cada propuesta como candidato: se revisa antes de sustituir la copia funcional. No añadas rutas o funciones como operativas hasta confirmar su contrato con el servidor.

El próximo bloque del servidor es persistir reportes con versiones y fuentes, comprobar permisos y permitir su consulta desde la pantalla preparada. Esta entrega deja visible el espacio y su estado; todavía no implementa ese guardado.
