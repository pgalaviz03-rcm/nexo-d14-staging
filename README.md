# NEXO + Atalaya · Candidato de integración

Basado en NEXO v0.5, con explorador y resumen documental sin IA. Candidato separado: no reemplaza el servidor activo ni se desplegó en nube. No incluye bases de datos ni credenciales. Consulta `docs/INTEGRACION_ATALAYA.md` y `docs/RESULTADO_CANDIDATO.json`.

La carpeta `docs/` conserva referencias técnicas de la base v0.5; sus resultados históricos de CI no validan automáticamente los cambios de este candidato. La interfaz conserva los gráficos demostrativos identificados y las 45 secciones originales.

## Cambios

- `app/news_review.py`: consultas de noticias por proyecto/periodo/fuente/origen y resumen de hasta 100 registros.
- `app/rss_api.py`: filtros de lectura y `GET /api/projects/{pid}/articles/brief`, con las mismas dependencias de autenticación y membresía.
- `static/index.html`: filtros y resumen con enlaces; identifica fuentes registradas/activas y alcance de resultados.
- `tests/test_news_review.py`: fechas, búsquedas literales, separación entre proyectos, gate de membresía y truncamiento.
- `scripts/preview_local.py`: vista de prueba en 127.0.0.1:8001 con copia privada de SQLite y lectura externa deshabilitada.

## Verificación

Python 3.12 y dependencias de `requirements-dev.txt`. Ejecutar pytest usando una carpeta temporal nueva autorizada. Hay 22 casos específicos aprobados (14 de esta integración y ocho de diagnóstico RSS) y sintaxis JavaScript aprobada. El usuario confirmó ingreso, filtros y resumen en navegador. La herramienta no pudo observar esa pestaña por su política de URL. Falta CI completa/PostgreSQL. No hay cambios de esquema ni permisos nuevos.

Para probar en otra computadora, preparar un entorno Python, dependencias y una copia privada SQLite v0.5 con sus cuentas locales. `scripts/preview_local.py --source RUTA_DB --directory CARPETA_PRIVADA_NUEVA` inicia una copia en el puerto 8001. El directorio privado debe estar fuera del código; no se sobrescribe un snapshot ya existente. Nunca incluirlo en GitHub. El iniciador general heredado usa el puerto 8000: no usarlo mientras esté ocupado por NEXO habitual.

## Antes de integrar en staging

Completar la aceptación en navegador y pruebas HTTP; ejecutar CI completa y aislamiento PostgreSQL. Respaldar la base, publicar solo código revisado y hacer despliegue manual gratuito. No habilitar IA, redes, mensajería o producción durante esta integración.
