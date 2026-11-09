# NEXO · Candidato de actualización de nube

Código del espacio local validado, adaptado al staging existente de Render y Supabase. **Candidato; no desplegado ni acreditado para producción.**

Lee [ACTUALIZACION_NUBE.md](docs/ACTUALIZACION_NUBE.md) antes de migrar. Punto de entrada: `app.cloud_main:app`. Revisión de base requerida: `011_workspace_cloud`. Se conserva la copia local y los archivos protegidos `app/main.py` y `app/knowledge.py`.

La publicación de código no incluye datos privados ni contraseñas locales. APIs, IA y envíos permanecen apagados. No aplicar migraciones a Supabase hasta verificar respaldo y pruebas nativas. La CI es manual para controlar el consumo de minutos; no se activa por cada subida.
