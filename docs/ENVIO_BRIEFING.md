> Actualización: el circuito de IA y la corrección opcional están documentados en `ANALISIS_IA.md`. La clasificación manual descrita abajo queda como corrección; el proveedor de IA sigue sin conectar.

# NEXO · Briefing: contenido y programación

20 de octubre de 2026 · Preparación local. La lectura, el guardado y la habilitación del Briefing base fueron aceptados por el usuario. Esta ampliación requiere revisar sus nuevos controles en pantalla.

## Lo que se puede preparar ahora

En **Briefing → Mi briefing: horario y canal**, cada cuenta decide, dentro del proyecto activo:

- Canal: correo o Telegram.
- Frecuencia: diaria, lunes a viernes o semanal; día de la semana cuando corresponda.
- Hora local y zona horaria; por defecto 07:00, America/Mexico_City.
- Periodo que resume: últimas 24 h, siete días o treinta días.
- Destino autorizado; puede quedar vacío durante la preparación.

Es una programación por cuenta y proyecto, con un canal a la vez. No se comparten los destinos entre usuarios ni proyectos. El destino se guarda cifrado, se devuelve parcialmente oculto y puede borrarse. Cambiar de canal no reutiliza el destino anterior. Al cambiar o pausar la configuración se cancelan sus simulaciones anteriores.

El checkbox **Dejar preparada esta programación** guarda la intención. **No activa un envío ni inicia un proceso en segundo plano.** La pantalla calcula el siguiente horario; actualmente solo hay una bandeja de simulación, sin entregas reales ni tareas del sistema operativo instaladas. Al cerrar el programa no corre un servicio de preparación.

## WhatsApp y los proveedores

WhatsApp Business Platform no está disponible para este uso: su política prohíbe candidatos y campañas, y también empresas que ofrecen servicios relacionados con política y consultoría de campañas. Por ello se retiró de la interfaz; su restricción se comunica al propietario fuera de la aplicación. No se implementan alternativas para eludir esa restricción. [Política oficial, apartado Government and Political Use](https://whatsappbusiness.com/policy/).

Correo y Telegram tienen puertos de integración separados del horario y del contenido. No se eligió ni contrató un proveedor de correo. Como referencia técnica de la fase final: [API de envío de correo de SendGrid](https://www.twilio.com/docs/sendgrid/api-reference/mail-send/mail-send), [sendMessage de Telegram](https://core.telegram.org/bots/api#sendmessage). No se conectó ninguna cuenta ni se proporcionaron credenciales a esos servicios.

La representación actual usa texto plano y un límite conservador de 3500 unidades UTF-16. Esto queda por debajo del límite documentado de Telegram de 4096 caracteres; no habilita broadcasts pagados ni interpreta HTML o Markdown de las fuentes.

## Qué contiene el mensaje

**Ver mensaje del corte actual** muestra una vista previa local de:

1. Proyecto y fechas del periodo.
2. Piezas únicas observadas y cantidad con clasificación de tono.
3. Ánimo del contenido: índice y balance favorable, desfavorable o mixto, cuando hay muestra suficiente.
4. Porcentajes positivo, negativo y neutral.
5. Alegría, ira, sorpresa, miedo y tristeza, con base de clasificación.
6. Burla y su base de piezas codificadas.
7. Temas más frecuentes entre las etiquetas manuales del periodo.
8. Alertas activadas, señales que requieren revisión, notas pendientes y fuentes seleccionadas.

La nota editorial privada no se incorpora automáticamente al mensaje. La vista previa no guarda, habilita ni envía un informe. El mensaje puede quedar acotado; la revisión completa se hace dentro de NEXO.

## Cómo se calculan las nuevas métricas

El corpus reúne noticias guardadas del proyecto y publicaciones reales de Pulso asociadas a actores monitoreados activos, dentro de la misma ventana. Las demostraciones no entran. Las coincidencias de **URL exacta guardada** cuentan una vez. URL diferentes pueden corresponder al mismo contenido: no se promete deduplicación semántica completa.

Las clasificaciones son por pieza, no perfiles de lectores, autores o votantes. Se pueden registrar manualmente en **Revisar tono, emociones y burla de las piezas**. Cada revisión conserva proyecto, fuente, huella, autor de la revisión y versión. Si el texto, título o URL cambia, esa revisión deja de usarse hasta revisarla nuevamente. Una edición simultánea o fuente modificada se rechaza sin sobrescribir otra revisión.

El tono admite positivo, negativo o neutral; se puede dejar sin clasificar. Se registra una emoción principal de las cinco solicitadas, o ninguna. Burla tiene tres estados: sí, no y sin revisar. No se deduce burla mediante una lista de palabras.

Cada porcentaje usa su propio denominador de piezas clasificadas: tono, emoción o burla. La burla puede coexistir con un tono y una emoción. Si hay etiquetas contradictorias para una misma URL, esa dimensión queda sin clasificar. Cuando no hay evaluación por pieza para una publicación de Pulso, el tono y emoción pueden usar etiquetas concordantes de sus menciones a actores; si no concuerdan, quedan desconocidos.

El mínimo de muestra sigue siendo el configurado en Pulso: por defecto veinte clasificaciones por dimensión. Con una muestra menor se muestra guion o «Sin dato», incluso si algunas piezas ya tienen etiquetas. El índice usa `(positivas + 0.5 × neutrales) / clasificadas × 100`. No describe el estado psicológico de una población ni equivale a una encuesta.

Las reglas de alertas siguen siendo las de Pulso por actor. La revisión por pieza no sustituye sus etiquetas por mención a un actor. Los riesgos del mensaje son **señales para revisar**, no probabilidades ni predicciones automáticas. Los temas superiores proceden de etiquetas manuales en noticias del periodo; todavía no hay extracción temática automática de todas las redes.

Los informes habilitados antes de esta ampliación conservan su versión original. No se les agregan emociones o porcentajes retrospectivamente. Para incluir el nuevo desglose hay que preparar, revisar y habilitar otro corte.

## Simular el horario

**Simular preparación del horario** crea un registro local para el siguiente horario previsto. Repetirlo con la misma versión de configuración y horario recupera el mismo registro.

- **Falta un briefing habilitado y vigente:** no se usa un borrador ni se inventa un corte diario. La selección busca hasta cincuenta habilitaciones recientes e indica si acotó la búsqueda; el periodo y la vigencia deben corresponder con la preferencia.
- **Falta destino:** existe un corte habilitado, pero falta configurar un destino.
- **Proveedor desconectado:** existe un corte y destino preparados; faltan proveedor y verificación del destino.
- **Cancelada:** la programación cambió o se pausó.

La simulación no convierte un corte de siete días en uno diario. La frecuencia de entrega y el periodo que se resume son ajustes distintos. Se admiten hasta veinte simulaciones por cuenta y proyecto en veinticuatro horas.

Las zonas horarias se almacenan por nombre IANA. En una zona con cambio estacional se omite un horario que no exista; si una hora ocurre dos veces se elige la primera. Nunca se asume que todos los proyectos tengan la zona del D14.

## Arquitectura y controles

Tres tablas nuevas, migración futura **006_delivery**:

| Tabla | Función |
|---|---|
| content_assessments | Clasificación por pieza con referencia compuesta al proyecto y fuente real |
| briefing_schedules | Preferencia privada por cuenta y proyecto; destino cifrado y versión |
| delivery_jobs | Bandeja inmutable de simulaciones, ligada a versión de informe cuando corresponde |

Las preferencias y la bandeja solo se consultan por su propietario dentro de un proyecto autorizado. Un administrador de proyecto no obtiene acceso a destinos privados de otros usuarios. La revisión de contenido requiere administrador, editor o analista; el lector puede preparar su propia preferencia.

La política SQL impide que el rol web inserte trabajos reales, vincule un borrador no habilitado, cambie el mensaje preparado o lo marque como enviado. Solo permite cancelar su propia simulación. La base conserva una restricción adicional que admite exclusivamente simulaciones. La fase de activación debe aprovisionar un trabajador y un estado de entrega reales con permisos separados; no basta con escribir una clave o cambiar una variable.

`app/delivery.py` contiene el cálculo de horarios, el formato y `DisabledSender`. El puerto rechaza todos los envíos incluso con credenciales presentes. `delivery_api.py` expone configuración, vista previa y simulación autenticadas. Las fuentes recuperadas no ejecutan herramientas ni deciden destinos. La vista previa no contiene tokens ni enlaces de acceso sin autenticación.

En local, el cifrado de destinos deriva de la clave privada de sesión ya respaldada. Para nube se reserva una clave Fernet independiente `NEXO_DELIVERY_ENCRYPTION_KEY` en un gestor de secretos. Si se usa una clave independiente, su custodia y recuperación deben resolverse aparte. No se entrega ninguna clave en el ZIP ni en el navegador.

## Antes de conectar de verdad

1. Elegir proveedor de correo o bot de Telegram, verificar remitente/destino y confirmar que el canal esté autorizado para ese proyecto y destinatario.
2. Custodiar credenciales y clave de cifrado; revisar permisos y presupuesto explícito, límites y revocación.
3. Activar un trabajador que prepare los cortes a la hora indicada y gestione revisión, idempotencia, reintentos acotados, fallos y confirmaciones del proveedor. La generación y revisión automáticas no se implementaron en esta ampliación.
4. Extender de forma controlada la bandeja para entregas reales. Comprobar publicación, pertenencia activa del destinatario y autorización inmediatamente antes de enviar. No confiar únicamente en el contenido de una cola antigua.
5. Completar pruebas nativas de PostgreSQL, TLS, RLS, restauración externa, monitoreo y retirada del consentimiento; enviar una prueba explícitamente autorizada.

## Comprobación local

180 pruebas Python aprobadas, incluidas 24 nuevas; 92 comprobaciones SQL en PostgreSQL WASM; nueve comprobaciones del controlador de programación y las anteriores de Briefing, Pulso y Reportes. Se probaron destinos cifrados, roles, fechas, cambio estacional, porcentajes, etiquetas obsoletas, duplicados y recuperación. Se conserva la limitación previa del navegador local: la aceptación visual de los nuevos controles debe hacerla el usuario.

La actualización local conserva las filas anteriores y el histórico del D14. Se verificó respaldo cifrado y restauración de las 29 tablas. En una copia aislada del informe real habilitado se comprobó que un lector del proyecto lo lee y un lector ajeno no puede abrirlo; no se crearon cuentas de prueba en la base activa.

## Revisión que sigue

Reinicia el servidor 8002, abre Briefing y revisa el desglose y **Mi briefing: horario y canal**. Prueba primero la vista previa del mensaje; después guarda la preferencia y simula un horario. Al aceptar esta ampliación seguimos con Actores. No se envió ningún mensaje, se desplegó código ni se contrató un servicio.
