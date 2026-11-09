> **Pulso actualizado:** nueva composición de inicio; tono y emociones destacados; actores compactos; titulares por fecha y cuentas solo con seguidores/publicaciones/interacciones. Se retiraron las referencias de audiencia y el desplegable técnico al lector. Comparación histórica secundaria únicamente con datos y fechas. 131 pruebas del bloque y dos verificaciones finales con solapamiento; 262 comprobaciones JS. Revisión visual humana pendiente. Consulta NEXO_PULSO_REDISENO_GUIA.md o docs/PULSO_REDISENO.md. Las cifras de pruebas inferiores conservan el historial.

# Prueba de NEXO local: consulta y administración

Versión del 21 de octubre de 2026. Cambió la política: **solo el superadministrador administra; el cliente observa**. No hay que conceder permisos de edición a un consultor para completar esta prueba.

## Preparación

Detén el servidor 8002 con Ctrl+C, abre ABRIR_NEXO_DESARROLLO_LOCAL.bat y actualiza http://127.0.0.1:8002 con Ctrl+F5. Conserva las dos sesiones en ventanas distintas. Las contraseñas se escriben solo en NEXO.

## Cuenta de consulta

1. Entrada: aparecen únicamente sus proyectos, el rol «Consulta del proyecto» y las pantallas del producto. No aparece Administración ni Superadministración, ni «Vista simplificada».
2. Pulso y Actores: cambia actor, canal y periodo. No aparecen «Otro», demostración ni gestión de actores. Las cifras reales pendientes permanecen sin inventar. Las cuatro referencias del D14 se conservan.
3. Biblioteca: elige un PDF y busca su texto; abre una página. Busca «sección 158» en el Excel: PRIMO VERDAD INEGI y 438, sin otras filas. No aparecen cargas ni botones para guardar un informe.
4. Briefing: consulta periodos, fuentes, fechas y resultados disponibles. No aparecen guardado, clasificación manual o configuración de horario/canal.
5. Reportes: aparecen solo versiones habilitadas para lectores. Abre «Prueba funcional D14» y descarga su documento imprimible. El borrador «Prueba PDF rezago» queda reservado al superadministrador hasta que este lo habilite.
6. Territorio: selecciona una sección y revisa ficha y mapa. El histórico y el Excel mantienen años y bases separados.
7. Redes, Fidelidad y Auditoría: filtros y diagnóstico en pantalla funcionan; no aparecen importaciones o configuración. Las métricas sin captura no se convierten en cero. La continuidad es agregada, sin perfiles individuales de afinidad política.
8. Alertas y Explorador: consulta bandeja y detalle, busca y prepara una selección de evidencia. No crea reglas, cambia estados ni guarda informes.

## Superadministrador

9. Administración: conserva Marca, Proyectos, Cuentas y Membresías, además de cargas, fichas y reglas. Solo esta cuenta cambia datos.
10. Informes: crea un borrador desde Biblioteca/Briefing/Explorador, comprueba fuentes y ámbito, y habilítalo para lectores cuando corresponda. «Prueba PDF rezago» versión 2 mantiene únicamente el PDF seleccionado. Confirma en la otra sesión que el cliente ve solo lo habilitado.
11. Horario/canal de Briefing: esta configuración queda reservada al superadministrador. Las simulaciones no envían mensajes reales; los trabajadores y proveedores siguen pendientes de integración.
12. Separación: al cambiar de proyecto se limpian resultados y filtros ajenos. Un nuevo proyecto comienza sin heredar datos del D14. No alteres el piloto para simular otro cliente.

## Diseño con datos precargados

Abre PROBAR_NEXO_DISENO.bat y http://127.0.0.1:8003. Entra con tu cuenta local habitual. Esta copia te muestra siempre como lector, con cuatro actores inventados, 360 menciones del corte, emociones, titulares, cuentas y alertas ficticias. No modifica el D14. Ver NEXO_DISENO_CONSULTA_GUIA.md.

Revisa escritorio y ventana estrecha (390 y 768 px): menú, navegación inferior, filtros, listas y comparativos. El detalle de emociones comienza plegado en móvil. Las listas largas permiten buscar y usar teclado. La prueba sigue limitada a esta computadora; no se abrió acceso desde teléfonos de la red.

## Registro

| Recorrido | Resultado | Observaciones |
|---|---|---|
| Consulta: acceso y ausencia de gestión | Pendiente | |
| Pulso: filtros y datos ficticios | Pendiente | |
| Biblioteca y fuentes | Pendiente | |
| Briefing y reportes habilitados | Pendiente | |
| Territorio, Redes y Fidelidad | Pendiente | |
| Alertas, Explorador y Auditoría | Pendiente | |
| Superadministración y separación | Pendiente | |
| Diseño escritorio y móvil | Pendiente | |

**Verificación técnica:** 625 pruebas Python y 255 comprobaciones JS aprobadas. Los controladores usan DOM simulado: esto no acredita renderizado visual en navegador ni todos los dispositivos. El mapa, archivos protegidos y datos del piloto se conservaron. No se conectaron APIs o IA, no se cambió la nube ni se habilitaron envíos. PostgreSQL/RLS nativo, identidad de nube, integraciones y operación requieren validación posterior.
