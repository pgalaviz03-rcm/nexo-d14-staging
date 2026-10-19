# NEXO v0.4 — PostgreSQL preparado + escucha digital RSS (piloto D14)

**Estado:** prototipo técnico local para pruebas. La aplicación **no se ha desplegado en un servidor público** y el entorno PostgreSQL/Docker **no pudo probarse contra un motor PostgreSQL real en esta sesión**. Las pruebas automatizadas se realizaron sobre SQLite de desarrollo.

## Qué se incorpora sobre v0.3

- Se conserva la identidad visual NEXO, el visor geográfico y las **45 secciones históricas** del Distrito 14.
- Nuevas tablas `feed_sources` y `news_articles` aisladas por `project_id`.
- Nuevo panel de noticias reales con fuentes RSS configurables por un administrador, búsqueda y fecha de ingestión.
- Fuentes RSS: registro HTTPS, dominios en lista de autorizados, control de tamaño y frecuencia, sin redirecciones, deduplicación por URL y bitácora.
- Contingencia manual: carga de CSV con `title,url,source` y campo opcional `description`.
- Script inicial Alembic, políticas PostgreSQL **RLS propuestas**, Dockerfile y `compose.yaml` para un servidor local.
- **7 pruebas automatizadas aprobadas**: acceso por proyecto, autenticación, datasets, RSS, CSV, fuente caída, sin pérdida de históricos.

## A. Prueba sencilla en Windows (SQLite, sin Docker)

1. Extrae el ZIP.
2. Instala Python 3.12 o más reciente.
3. Abre terminal dentro de `NEXO_v0_4_D14`.
4. Ejecuta:

   ```shell
   python -m pip install -r requirements.txt
   python iniciar.py
   ```

5. Copia la contraseña temporal que aparece en la terminal la primera vez; entra en `http://127.0.0.1:8000` con `admin@nexo.local`.
6. En el menú **Escucha digital** verás el Radar de información pública. Al inicio estará vacío, porque no se fingen publicaciones.
7. Para probar la contingencia sin Internet, importa un CSV con estas columnas:

   ```csv
   title,url,source,description
   Ejemplo ilustrativo,https://www.example.org/nota,Archivo de práctica,Registro ficticio solo para validar una importación
   ```

   Esta muestra es ficticia. La plataforma la registra como `origin=csv`; no es una noticia verificada.

## B. Prueba PostgreSQL (Docker, local)

**Requisitos:** Docker Desktop y Docker Compose. No exponer esta implementación a Internet sin endurecimiento previo.

1. Copia `.env.example` a `.env`.
2. Cambia **los tres secretos** por valores independientes, aleatorios y de alta entropía (idealmente `python -c "import secrets; print(secrets.token_hex(32))"`). Evita caracteres reservados de URL si no vas a codificarlos.
3. Opcional: en `NEXO_RSS_ALLOWED_HOSTS` incluye dominios exactos de fuentes RSS que hayas verificado y autorizado, separados por comas (sin `https://`). Por defecto está vacío: **la red está cerrada**.
4. Ejecuta `docker compose up --build`.
5. El contenedor `migrate` aplica el esquema inicial, instala las políticas RLS y carga el Distrito 14. Observa la terminal para la contraseña inicial generada; no compartas estos registros.
6. Abre `http://127.0.0.1:8000`.
7. Prueba que cada usuario consulta únicamente sus proyectos, que los conjuntos se pueden importar, y que las noticias tienen fuente y fecha.

**No se confirma PostgreSQL como funcional hasta ejecutar y superar en un servidor real** las migraciones, consultas con RLS y pruebas de acceso cruzado bajo el rol `nexo_app`. Se incluyen scripts, no un servicio hospedado.

## Limitaciones de seguridad deliberadamente visibles

- Inicio de sesión propio del prototipo; falta IdP/OIDC, MFA, sesiones revocables, protección de abuso, TLS, CSRF/CSP.
- Los permisos por API están probados en SQLite; **la defensa RLS del motor** está escrita, pero requiere pruebas PostgreSQL independientes.
- Debe validarse el bootstrap de Docker con usuarios separados de migración y aplicación.
- Las fuentes RSS tienen lista blanca de dominios exactos y bloqueos SSRF básicos. No se recomienda cargar dominios de terceros no confiables; aún falta defensa robusta ante cambios de DNS en ambientes expuestos.
- RSS es **monitoreo de publicaciones**, NO una encuesta de opinión, escucha de comentarios en redes ni una medición emocional.
- **Sin actualización automática programada:** la sincronización RSS de v0.4 es manual y limitada a una vez por minuto por fuente. Los datos ya importados quedan disponibles si falla un proveedor.
- La API jamás transfiere documentos de un proyecto a otro por decisión del frontend; las rutas verifican membresía.
- No se ha conectado IA, por tanto no hay ejecución ni costos de tokens, ni función de grounding check en uso todavía.
- El cierre/archivo/destrucción y demás controles del Documento Maestro v1.3 siguen pendientes de implementación y deben probarse antes de producción.

## Comprobaciones

```shell
python -m pytest -q tests
```

## Próxima etapa recomendada

1. Seleccionar proveedor de hosting y confirmar presupuesto mensual.
2. Probar `docker compose` y las políticas RLS sobre PostgreSQL verdadero, resolver cualquier ajuste del bootstrap.
3. Añadir OIDC/MFA, backups, alertas, limpieza de archivos y monitorización.
4. Autorizar 2–3 feeds RSS reales y medir cobertura, latencia y estabilidad.
5. Integrar fuentes complementarias (RSS, APIs habilitadas y carga manual) sin romper la pantalla.

---

**Datos electorales:** 45 secciones, 41,984 votos territoriales, 8 votos anticipados no localizados, lista nominal 65,378, todo referido a 2024. Ninguna cifra histórica se equipara a opinión actual.
