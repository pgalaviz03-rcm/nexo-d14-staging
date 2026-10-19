# Respaldo y recuperación de la copia local

El script `scripts/backup_local.py` crea una copia coherente de SQLite mediante su API de respaldo, incluye la clave de sesión local y los archivos cargados que la base referencia, y cifra el conjunto en memoria con **DPAPI CurrentUser** de Windows. No incluye credenciales de Render o Supabase. La base activa se abre solo para lectura y nunca se reemplaza durante el ensayo.

En esta computadora se entrega además `RESPALDAR_NEXO_LOCAL.bat`, en la carpeta de resultados. Al abrirlo crea un respaldo cifrado y comprueba una recuperación en una carpeta nueva del área privada. Conserva tanto el respaldo como el resultado del ensayo; no hay programación automática ni eliminación de copias antiguas.

Uso general desde un entorno Python preparado, dentro del paquete:

```text
python scripts/backup_local.py --human
python scripts/backup_local.py --restore RUTA_ARCHIVO.nexobak --target CARPETA_NUEVA
```

El destino de restauración debe ser nuevo. El resultado contiene `storage/nexo.db`, `storage/.session_secret` y los archivos cargados; las rutas de esos archivos se ajustan al destino. Guarda el paquete fuente para reconstruir la aplicación alrededor de esos datos. Antes de activar una recuperación real, detén el servidor, conserva los datos existentes y ensaya en una carpeta distinta. La prueba incluida no inicia otro servidor ni modifica el que está en uso.

Se validan integridad y referencias de SQLite, conteos de tablas, hashes de archivos, rutas seguras, ausencia de duplicados y máximo de 128 MiB descomprimidos. Un archivo cargado ausente hace fallar la copia de forma explícita. El formato usa también la protección contra alteraciones de DPAPI. Los archivos recuperados de ensayo están descifrados y deben mantenerse en una carpeta privada.

**Alcance:** esta protección normalmente necesita el mismo perfil de Windows y la misma computadora. No sustituye una copia externa recuperable tras perder el equipo o el perfil; [Microsoft explica este alcance de DPAPI](https://learn.microsoft.com/en-us/windows/win32/api/dpapi/nf-dpapi-cryptprotectdata). No se ha configurado ni probado todavía una restauración completa de Supabase Auth, roles y PostgreSQL en otro proyecto. El procedimiento de nube preparado en `backup.sh`/`restore.sh` requiere credenciales administrativas, destinatario de cifrado y almacenamiento externo; sigue pendiente de conexión y ensayo, sin gasto autorizado.

Ensayo del 19 de octubre de 2026 en esta computadora: copia cifrada creada, recuperada en destino aislado y 45 secciones preservadas. Nueve pruebas locales aprobadas: recuperación con archivos, protección de rutas, integridad, ausencia de archivos, bloqueo de sobrescritura y cifrado real DPAPI con rechazo de alteraciones. La prueba DPAPI se omite en CI Linux; allí se ejecutan las pruebas de formato y aislamiento con datos artificiales.
