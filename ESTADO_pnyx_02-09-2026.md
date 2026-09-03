# PNYX — Actualización de estado (02/09/2026)
### Se suma a MAESTRO_pnyx_12-07-2026.md. Para retomar en un chat nuevo.

## CÓMO RETOMAR
Todo el código vive en GitHub: **https://github.com/benjakuchen/pnyx** (público).
En un chat nuevo, pedir que se lea el repo completo (.html, obreros .py, edge functions, este archivo y el MAESTRO). Ese es el punto de retomo permanente.
- App usuario ONLINE: https://benjakuchen.github.io/pnyx/pnyx-app-v6.html
- Admin ONLINE: https://benjakuchen.github.io/pnyx/pnyx-admin.html
- Benjamín: Windows/PowerShell, no programador, guiar paso a paso en rioplatense.

## HITOS DE ESTAS SESIONES (jul–sep 2026)

### 1. Git + GitHub Pages (hosting real) — HECHO
- Repo `benjakuchen/pnyx` público. GitHub Pages sirviendo desde main / root.
- `.gitignore` excluye JSON/CSV/XLS pesados (viven en Supabase), temporales, HTML de debug, y secretos.
- Verificado: ningún .py/.html/.sql tiene la clave secreta hardcodeada (vive en tabla config_secreta de Supabase).
- **Flujo de trabajo nuevo:** editar archivo → `git add . / commit -m "..." / push` → en 1-2 min está online. Se acabó el descargar-mover-refrescar. Tip: Ctrl+Shift+R en el navegador para ver cambios (caché).
- PENDIENTE al publicar de verdad: actualizar en Supabase Auth la Site URL y Redirect URLs a la de github.io (hoy apuntan a localhost); Didit ya usa callback_url dinámico.

### 2. Consola de administración (pnyx-admin.html) — CONECTADA A DATOS REALES
Reemplaza la maqueta vieja (que tenía datos inventados). Tres pestañas:
- **🔗 Leyes: feed ↔ Congreso** — tabla comparativa. Izquierda: ley del feed (título IA editable). Derecha: cómo la votó el Congreso (título editable). Filtros: Pendientes / Linkeadas / Descartadas / Todas. Acciones: linkear manual (buscador por título/expediente), desvincular, descartar ("no está en el feed"), rescatar (deshacer descarte). Todo con deshacer.
- **🗳️ Feed de votación** — todas las leyes del feed. Editar título IA, publicar/despublicar (default publicada=true; despublicar saca la ley del feed del usuario). Filtros pub/desp/todas + buscador. Dentro de cada ley: módulo de EXPERTOS.
- **🎬 Expertos·Bancas·Usuarios** — placeholder (bancas/usuarios/sensibles pendientes).

### 3. Cruce ciudadanía vs Congreso (app usuario) — HECHO, madura con el tiempo
En la pestaña Votadas, para una ley que está en el feed Y fue votada: muestra "TU COMUNIDAD vs EL CONGRESO" (tendencia ciudadana por resultados_por_ley + resultado del Congreso + veredicto coincidieron/distinto). Solo aparece si la ley tiene ≥1 voto ciudadano. Limitación natural: requiere que una ley complete el ciclo trámite→gente vota→recinto; se activa solo con el uso.

### 4. Votadas: solo LEY por ahora — HECHO
La pestaña Votadas abre filtrada en tipo LEY (votedTipo='LEY'). El obrero 10_votadas.py sigue guardando TODO (acuerdos, designaciones, etc.); solo se filtra lo que se muestra. Los chips permiten ver otros tipos.

### 5. Módulo de Expertos — EN CURSO (falta la mitad de la app usuario)
- Tabla `expertos`: id, ley_bill_id, nombre, afiliacion (obligatoria, "nadie apolítico"), postura (a_favor/en_contra/abstencion), youtube_url, orden. RLS: lectura pública.
- Funciones: admin_expertos_ley(p_bill), admin_expertos_add(...), admin_expertos_del(p_id).
- ADMIN: en cada ley del Feed de votación, botón "🎬 Opiniones de expertos" → lista + alta (nombre, afiliación, link YouTube, postura) + borrar. FUNCIONA.
- **FALTA (próximo paso inmediato):** en la APP DE USUARIO, mostrar el botón "ver opiniones" SOLO si la ley tiene expertos cargados, y reproducir los videos de YouTube embebidos. Decisión tomada: cada experto declara postura definida (favor/contra/abstención), sin neutrales; el botón aparece con ≥1 opinión.

## ESTADO DE LAS TABLAS DE VOTACIONES (Congreso) — YA EXISTÍAN, POBLADAS
- votaciones_congreso: 47 (cabeceras) · votos_nominales: 6529 · legisladores: 330 · votadas_feed: 47.
- Fuente: repo comovoto de rquiroga7 (resuelve el anti-bot de HCDN/Senado). El obrero es 10_votadas.py; usa clasificar_tipo.py.
- Linkeo votación↔ley del feed: por SIMILITUD DE TÍTULO (comovoto NO trae expediente para Diputados; para Senado sí viene embebido en el título). El auto-linkeo mete errores (ej. Danza↔Zona Fría) → por eso la cola de linkeo manual en la admin.
- Columnas útiles: expediente_fuente, match_score, orden_del_dia, link_descartado (bool, para descartes).
- Estado actual del linkeo tras regeneración: pocas auto-linkeadas; se revisan a mano en la admin.

## LOGIN DESACTIVADO (temporal, reponer antes de producción)
- App usuario: entra directo al feed. initAuth usa usuario fijo de desarrollo (id 75c330d1-...-2d12294aaad8, que es un auth.users real) para que el voto funcione vía emitir_voto.
- cargarVotadas: sin sesión no lee ya_voto (RLS por auth.uid), así que en dev pueden reaparecer leyes ya votadas — no crítico.
- Admin: entra directo, sin credenciales.
- Reponer: restaurar el flujo continuarTrasLogin/mostrarVerificacion (Didit) en la app y el login por contraseña en la admin.

## PENDIENTES (prioridad)
1. Terminar Expertos: botón + reproductor YouTube en la app usuario (aparece si hay opiniones).
2. Autor + foto en las tarjetas (autor ya está en los JSON; falta columna en leyes + conectar; hoy "Propone: •" vacío).
3. Afinidad con legisladores (Camino A, cálculo en el dispositivo, anonimato intacto): choca con el desfase temporal, madura con el uso.
4. Fuentes RSS de prensa (solo Clarín responde de 6).
5. Penalizar puntaje de media sanción sin texto.
6. Reponer logins (app + admin) antes de producción; actualizar Site URL de Supabase.
7. Más módulos admin: bancas (validar representantes contra padrón legisladores), usuarios/curadores con roles, controles sensibles (pisos, regla 60%).
8. Rol admin real (hoy cualquiera con contraseña entra a la consola).

## TABLAS EN SUPABASE (resumen)
leyes, votos, ya_voto, identidad_verificada, config_secreta, expertos,
votaciones_congreso, votos_nominales, legisladores, legisladores_autodeclarado, legisladores_fic..., votadas_feed.
Vista estado_leyes. Funciones clave: emitir_voto, resultados_por_ley, cola_linkeo, linkear_manual, descartar_link, admin_rescatar, admin_desvincular, admin_comparativa, admin_editar_titulo_feed, admin_editar_titulo_votada, admin_feed_leyes, admin_publicar, admin_expertos_*, votadas_lista/buscar/anios/tipos, votada_por_bloque, votada_nombres.
Edge Functions: crear-sesion, webhook-didit (Didit/RENAPER, desplegadas).
