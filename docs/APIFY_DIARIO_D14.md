# NEXO · Corte diario de Facebook D14

Estado verificado el 10 de noviembre de 2026. El proyecto D14 quedó en modo **programado**, con presupuesto de **USD 10 al mes**. La actualización se solicita a las **08:00, America/Mexico_City**. GitHub puede retrasar el inicio y Render Free necesita despertar; no es una garantía de entrega al minuto exacto. La primera ejecución futura de este horario todavía no se ha observado.

## Límites guardados

| Proceso | Muestreo máximo por cuenta | Consultas por día | Reserva por consulta | Reserva en 31 días |
|---|---|---:|---:|---:|
| Publicaciones | 2 publicaciones, ventana de 7 días | 1 | USD 0.07 | USD 2.17 / MXN 43.40 |
| Seguidores | 1 captura de cuenta | 1 | USD 0.07 | USD 2.17 / MXN 43.40 |
| Comentarios | 5 comentarios de una publicación reciente | 1 | USD 0.07 | USD 2.17 / MXN 43.40 |
| Reacciones | 4 reacciones de una publicación reciente | 1 | USD 0.07 | USD 2.17 / MXN 43.40 |
| **Total** | Hasta 4 cuentas registradas | **4 procesos** | **USD 0.28 diarios** | **USD 8.68 / MXN 173.60** |

Tipo de cambio ilustrativo: USD 1 = MXN 20. No es una cotización bancaria; impuestos y conversión dependen del proveedor. Es una proyección de **reservas máximas**, no una factura ni una promesa de precio constante. Abrir pantallas, cambiar filtros o entrar como consultor no llama a Apify. Las capturas se comparten entre los usuarios autorizados del proyecto. Los cortes manuales también consumen los cupos diario y mensual.

Antes de iniciar cada corrida, NEXO reserva USD 0.07 en el presupuesto del proyecto y envía ese límite a Apify. Conserva la reserva aunque el costo real sea menor o la respuesta sea parcial. Si no cabe otra reserva dentro de USD 10, detiene nuevas corridas hasta el siguiente mes o una decisión del superadministrador. Esta protección no es un límite global de la cuenta Apify: las ejecuciones iniciadas directamente fuera de NEXO no pasan por este control. No se contrató ningún plan ni se recargó saldo.

## Resultado real

Los seis procesos ejecutados para esta activación y comprobación costaron **USD 0.09790**. Sumando la prueba previa de USD 0.016, el total verificado es **USD 0.11390**, aproximadamente **MXN 2.28**. NEXO mantiene **USD 0.47 reservados**, por ser un control conservador distinto del gasto real.

- Rodrigo: publicaciones disponibles y 4,047 seguidores observados. El Actor de reacciones devolvió cuatro filas válidas en la publicación muestreada.
- Quique: publicaciones disponibles y 10,410 seguidores observados. El reel muestreado sigue rechazado por el Actor de reacciones, incluso usando el enlace numérico alternativo entregado por Facebook.
- Alma Hilda: el proveedor indicó contenido no disponible. José Juan: no devolvió publicaciones ni una cifra de seguidores. Hace falta revisar sus enlaces públicos; no equivalen a cero seguidores.
- Comentarios: el proveedor devolvió `no_items` para ambas publicaciones, también con enlaces alternativos. No se incorporaron comentarios.
- Equipo: ninguna de las reacciones observadas coincidió exactamente con las cuentas registradas. No se fabricaron interacciones ni conclusiones de fidelidad.
- Pulso conserva cinco documentos reales de Facebook tras eliminar duplicados. Las emociones y el tono permanecen sin clasificar hasta conectar la IA. No es una medición completa de la conversación pública.

Las otras redes conservan sus formularios, pero sus ejecutores todavía están pendientes. Este presupuesto cubre únicamente los cuatro procesos de Facebook; no habilita IA ni otras redes.

## Operación

En **Configuración → APIs e integraciones → Apify** se controla el modo, presupuesto, cuentas y procesos. El token existente permanece cifrado; dejar vacío el campo conserva la credencial. Selecciona **Pausado** y guarda si quieres detener nuevas capturas. Solo el superadministrador puede modificarlo o solicitar un corte manual con **Actualizar datos**. Los lectores consultan el último corte compartido.

Para revisar el resultado, abre Pulso y Redes, selecciona **7 días** y el actor. Fidelidad utiliza los contadores de publicaciones observadas y las coincidencias exactas del equipo. Un corte **parcial** significa que alguna fuente o proceso no entregó todo; nunca debe interpretarse como una captura exhaustiva.

## Verificaciones y archivos

La revisión `97c09d8` está Live en el Render existente. La prueba firmada del programador pasó; el corte diario ya admitido no se duplicó. Pasaron 30 pruebas del transporte, contratos, importación y enlaces públicos, sin consumo real de Apify durante esas pruebas unitarias. Los controles previos de configuración e interfaz permanecen en sus informes. Salud y disponibilidad respondieron 200; la configuración sin sesión y el programador sin firma rechazaron el acceso. No se modificaron tablas, RLS, `app/main.py`, `app/knowledge.py` ni el mapa histórico.

El resultado JSON y la tabla CSV adjuntos son editables. El ZIP contiene código y documentación de la lista de integridad; excluye credenciales, bases locales y documentos privados. La copia local habitual del usuario no fue reemplazada por esta publicación.
