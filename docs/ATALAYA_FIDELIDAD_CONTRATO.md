# Procedencia y límites del conector Atalaya

Fuente aportada por el usuario: atalaya-codigo-completo.zip, SHA256
148dc723f256e125bdbd277bb13216a47a8cb650c984cd16b36b650050c0c111.

Se revisaron estáticamente el servidor, proceso de lectura, cliente Apify, runtime y pantalla de esta versión. No se ejecutó código del ZIP. La adaptación emplea el formato público de publicaciones de proceso.py y la organización de la pantalla de Fidelidad, con los componentes de NEXO. No incorpora su servidor HTTP, acceso, perfiles personales, runtime Preact, plantillas dinámicas o tareas automáticas.

La entrada normalizada atalaya-publications-v1 declara actor_id y cuenta registrados en el proyecto, red, captured_at y publications. Cada publicación admite exclusivamente url, published_at, text, reactions, comments, shares y followers. Es una captura del exportado; no garantiza que sea el universo completo de la red ni identifica personas únicas. El historial de importaciones no convierte contadores acumulados en interacciones ocurridas dentro del periodo.

Interacciones: suma de reacciones, comentarios y compartidos disponibles, contados una sola vez por publicación de la captura más reciente por cuenta. Los campos desconocidos permanecen nulos. Engagement del corte: interacciones observadas en publicaciones del periodo / suma de seguidores declarados en las cuentas seleccionadas × 100, solo con denominadores disponibles para todas ellas. Puede superar 100%; no representa personas únicas. La fecha de exportación no certifica una fecha individual de actualización para cada contador de seguidores.

Los proveedores originales están identificados en el ZIP, pero no se ejecutan desde NEXO. La futura fase de conexión necesita contratos de salida verificados por Actor, límites de gasto/tiempo, control de reintentos, deduplicación, tareas por proyecto y secretos fuera del navegador. No se trasladarán lectores o clasificadores de postura política individual.

El registro fidelity_captures solo se crea en SQLite local al instalar el apartado. La activación en nube requiere migración versionada y RLS nativo probado; no se habilita un servidor nuevo ni se cambia la configuración de despliegue con esta entrega.
