# Fuentes RSS iniciales del piloto D14

El usuario eligió estos dos medios el 19 de octubre de 2026:

| Medio | RSS | Dominio permitido |
|---|---|---|
| El Heraldo de Aguascalientes | https://www.heraldo.mx/feed/ | `www.heraldo.mx` |
| Hidrocálido Digital | https://www.hidrocalidodigital.com/feed/ | `www.hidrocalidodigital.com` |

`NEXO_RSS_ALLOWED_HOSTS=www.heraldo.mx,www.hidrocalidodigital.com` se aplica solo al piloto aprobado. Las plantillas genéricas conservan la lista vacía por defecto. `ABRIR_NEXO_LOCAL.bat`, entregado para esta computadora, contiene la lista elegida; requiere reiniciar el servidor local para que se aplique. Las bases local y de nube guardan sus fuentes y noticias por separado.

En **Escucha digital → Radar de información pública**, registra el medio y su RSS; pulsa **Sincronizar** en cada fuente para recuperar publicaciones. **Actualizar** vuelve a consultar los registros ya guardados; no contacta con los periódicos. No se configuraron tareas recurrentes, avisos externos ni API de redes sociales. IA apagada.

Se conservan titular, URL, medio, fecha proporcionada por el RSS, fecha de ingreso y extracto de hasta 360 caracteres. Se normalizan las URL y se deduplican por proyecto y enlace. Una publicación no demuestra que un hecho ocurriera dentro del D14: corresponde revisar ubicación y contenido antes de usarla como evidencia. Los gráficos de tono y conversación del prototipo siguen siendo demostrativos y no se calculan con estas noticias.

Controles: HTTPS estándar, coincidencia exacta de dominio, resolución solo a direcciones públicas y conexión fijada a esa dirección, validación TLS, sin redirecciones ni proxies, máximo 2 MB y 80 elementos por lectura. El piloto admite cinco fuentes por proyecto, 96 intentos diarios de sincronización y al menos 60 segundos entre intentos por fuente. Los intentos fallidos también consumen cuota. Se requiere usuario con permisos admin/editor para registrar y admin/editor/analyst para sincronizar, además de MFA en nube.

Si un medio cambia su dominio, redirige, bloquea el acceso o deja de ofrecer RSS, se registra un error y se conservan las publicaciones anteriores. El administrador debe revisar el dominio nuevo antes de incorporarlo. Los resultados reales de conectividad y sincronización se documentan por separado, sin confundir un feed registrado con uno sincronizado.
