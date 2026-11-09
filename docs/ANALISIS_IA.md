# Briefing: análisis automático y corrección opcional

## Experiencia acordada

La IA clasificará el **tono del contenido**, su emoción predominante —alegría, ira, sorpresa, miedo o tristeza— y si contiene burla. El usuario recibirá un Briefing agregado con fuentes y cobertura. No tendrá que etiquetar cada publicación. «Revisar resultados y corregir una pieza» es un recurso opcional.

En esta entrega local, al abrir un corte como administrador, editor o analista, se descubren las piezas y se preparan tareas persistentes sin conexión externa. Los lectores solo consultan el estado. La pantalla muestra pendientes de análisis con discreción y mantiene los valores desconocidos como guiones. El canal no admitido y su explicación se retiraron de la interfaz.

**Estado real:** existe el circuito de preparación, validación y consumo de resultados, probado con fuentes y respuestas ficticias. El único adaptador instalado está desconectado. No se ha ejecutado IA real, no hay credenciales de modelo ni programador de análisis funcionando. Correo y Telegram conservan preferencias y simulación local; tampoco envían mensajes todavía. Estas dependencias se resuelven con el propietario antes de activar el servicio.

## Circuito interno

1. Corte por proyecto y fechas → descubrimiento de notas y publicaciones reales de actores activos; excluye demostraciones.
2. Tarea `content_analyses` por fuente, huella de título/texto/URL y contrato `content-v1`. Preparar el mismo corte no duplica trabajo. Hasta 100 tareas nuevas por pasada y 500 pendientes por proyecto; futuras pasadas avanzan sobre piezas sin tarea. Las piezas demasiado grandes permanecen pendientes.
3. Un trabajador de confianza llama `process_one(session, project_id, task_id, adapter)`. El adaptador deberá implementar `AnalysisPort.analyze`: texto acotado, instrucciones fijas, esquema JSON estricto, solicitud de máximo 600 tokens de salida y tiempo máximo de 20 segundos. No existe ruta HTTP para introducir respuestas de IA ni claves.
4. Se acepta solo el esquema exacto: `sentiment`, `emotion`, `mockery`, `confidence`, `evidence`. Los valores pueden abstenerse con `null`; burla es booleana, no una etiqueta equivalente a negatividad. Debe haber un fragmento literal del texto que respalde las etiquetas. Se rechazan claves adicionales, valores fuera de catálogo, NaN, coacciones de texto a booleano y citas inventadas.
5. Confianza declarada de al menos 0.8 y alguna etiqueta conocida → `completed`; ambigüedad → `needs_review`; respuesta inválida/fallo → `failed`. Esta confianza es una señal del modelo, **no una probabilidad calibrada ni prueba de exactitud**. La validación comprueba formato y coincidencia de la cita; la corrección semántica requiere evaluación humana del modelo antes de activarlo.
6. Un cambio de fuente invalida la elegibilidad del resultado; se comprueba otra vez antes y después de la llamada. Las correcciones vigentes del usuario tienen prioridad sin borrar el resultado original.
7. Briefing agrega resultados aceptados y congela modelo/proveedor/versión de contrato en el reporte. Los informes anteriores conservan sus cifras, fuentes y huellas. Una pieza con emociones puede tener burla y cualquier tono. Los porcentajes mantienen denominadores separados y el mínimo de cobertura configurado en Pulso.

La clasificación es de piezas públicas. No identifica ideología, fidelidad o estado psicológico de personas. No permite inferir lo que piensa todo un territorio. El tono por pieza no equivale a sentimiento hacia cada actor: el análisis específico de menciones de Pulso mantiene su contrato separado y requerirá evaluación al conectarlo.

## Seguridad y consumo

- Texto de fuente tratado como datos no confiables; las instrucciones niegan obedecer órdenes incrustadas, seguir enlaces, usar herramientas o inferir creencias políticas. El contrato no permite instrucciones, destinatarios, secretos ni llamadas arbitrarias en la respuesta.
- Máximo 32 KiB de título y texto por tarea. Un intento por versión de fuente, 100 intentos por proyecto en 24 horas y reclamación atómica. El bloqueo por proyecto serializa la comprobación de cuota; SQLite usa bloqueo de escritura y PostgreSQL un bloqueo transaccional. Sin reintentos automáticos.
- No se guarda el texto de errores del proveedor. No se incorporan contraseñas, identificadores de usuarios o destinatarios al prompt. Se mantiene el texto público necesario en la instantánea local de la tarea; su acceso exige membresía del proyecto.
- La aplicación PostgreSQL puede insertar únicamente tareas vacías en estado pendiente. RLS impide insertar resultados, cambiar etiquetas/estado o borrar historial, incluso siendo administrador de un proyecto. No se ha creado ni conectado un rol de trabajador remoto con permiso para completarlas.
- Migración **007_analysis**, aditiva: una tabla nueva; total 30. No se ha aplicado en nube. `main.py` y `knowledge.py` siguen intactos.

## Conexión final: decisiones y trabajo pendiente

Elegir un proveedor/modelo con evaluación en español sobre un corpus anotado por humanos: tono, emoción, burla, abstención y posibles diferencias por fuente. Implementar su adaptador con credencial exclusivamente de servidor y timeout real, validar retención y tratamiento de datos y acordar límites monetarios y de tokens. Esta entrega impone límites de tareas/intentos; **no calcula una factura ni sustituye un presupuesto global del proveedor**.

Habilitar el trabajador con identidad y permisos propios, descubrimiento periódico independiente de las páginas abiertas, aislamiento de proyectos, recuperación controlada de tareas interrumpidas, monitorización y apagado de emergencia. Hoy una interrupción puede dejar la tarea en `processing`; no se reintenta sola. Validar el flujo completo en PostgreSQL nativo antes de desplegar. Después se activan proveedores de entrega permitidos, verificación de destinatarios y el trabajador de envíos. No basta colocar una clave en `.env`.

## Revisión visual local

Reiniciar la copia habitual con `ABRIR_NEXO_DESARROLLO_LOCAL.bat`, entrar en Briefing y actualizar el corte. Debe aparecer «pendientes de análisis», sin nuevos porcentajes inventados. La corrección opcional queda plegada y «Mi briefing: horario y canal» ofrece los canales preparados. Las pruebas de interfaz de esta entrega simulan el DOM; no sustituyen esta revisión visual.
