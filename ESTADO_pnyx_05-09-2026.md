# PNYX — Actualización de estado (05/09/2026)
### Reemplaza a ESTADO_pnyx_02-09-2026.md. Se suma a MAESTRO_pnyx_12-07-2026.md. Para retomar en un chat nuevo.

## CÓMO RETOMAR
Todo el código vive en GitHub: **https://github.com/benjakuchen/pnyx** (público).
En un chat nuevo, pedir que se lea el repo completo (.html, obreros .py, edge functions, este archivo y el MAESTRO). Ese es el punto de retomo permanente.

- App usuario ONLINE: https://benjakuchen.github.io/pnyx/pnyx-app-v6.html
- Admin ONLINE: https://benjakuchen.github.io/pnyx/pnyx-admin.html
- Benjamín: Windows/PowerShell, no programador, guiar paso a paso en rioplatense.
- Flujo de trabajo: editar archivo → `git add . / commit -m "..." / push` → en 1-2 min online. Ctrl+Shift+R en el navegador para ver cambios (caché muerde siempre).

## HITOS DE ESTA SESIÓN (05/09/2026)

### 1. Módulo de Expertos — TERMINADO en la app de usuario
- Ya estaba la admin (cargar opiniones por ley) y la tabla `expertos`. Faltaba la mitad de la app usuario: HECHA.
- Al cargar el feed, una sola consulta cuenta cuántas opiniones tiene cada ley visible (`cargarConteoExpertos`, lee la tabla `expertos` por RLS de lectura pública, sin función nueva).
- En el detalle de la ley, el botón "🎬 Ver opiniones de expertos (N)" **aparece SOLO si la ley tiene ≥1 opinión**. Si no hay, no aparece nada.
- La pantalla de opiniones baja los expertos de esa ley (orden `orden.asc`), los agrupa en A FAVOR / EN CONTRA / CON MATICES, y **reproduce cada video de YouTube embebido** (iframe youtube-nocookie, 16:9). Helper `ytId` parsea watch/youtu.be/shorts/embed/live; si no parsea, cae a link externo. Cache por ley (`expCache`) para no re-pedir.
- Se eliminó el mock viejo (Dra. Ana Field, etc.) y el panel ciudadano ilustrativo (queda para cuando exista su tabla).

### 2. Autor en las tarjetas — TERMINADO
- Antes: "Propone: •" vacío (la app ponía `autor:''` fijo).
- SQL corrido en Supabase: `ALTER TABLE leyes ADD COLUMN IF NOT EXISTS autor text;`
- La app ahora lee `f.autor` y lo muestra en tarjeta y detalle vía helper `proponeLinea` (autor + bloque solo si existen; si no hay autor, "Sin autor cargado" en gris, sin separador colgando). Avatar con iniciales (`iniAutor`).
- Obreros 3 y 6 (texto Diputados/Senado) ahora **también suben el autor** en su upsert, así las leyes futuras lo traen solas.
- Obrero nuevo `11_autores.py`: backfill re-ejecutable que toma el autor de los JSON locales y completa las leyes ya existentes. Al correrlo dio "A actualizar: 0 / Ya al día: 965" → la columna ya estaba poblada (los obreros 3/6 la habían llenado). 965 de 969 leyes con autor.
- LIMITACIÓN CONOCIDA (no bloqueante): el autor de Diputados viene del CSV de HCDN en MAYÚSCULAS y formato "APELLIDO, NOMBRE", a veces truncado ("MAYANS, JOSE MIGUEL ANGE"). Senado viene en Title Case. Decisión de Benjamín: dejarlo así por ahora; se puede prolijar a Title Case con un obrero chico más adelante.

### 3. Botón "Buscar el texto en el Congreso" — TERMINADO
- Problema detectado: 12 leyes tienen media sanción pero NO tienen texto oficial cargado. Son las "venidas en revisión" (camara ≠ origen): el texto vive en el portal de la cámara de ORIGEN, pero cada obrero de texto (3 y 6) busca solo en su propia cámara por bill_id. Por eso quedan sin texto para siempre.
- Se descartó la teoría de "el texto ya está en Pnyx en la fila de origen": se verificó por SQL que la fila de origen NO está guardada (cae fuera del filtro de años del obrero 2, o nunca entró). Confirmado con la ley 25.565: las coincidencias por título son temáticas, no la misma ley.
- Se descartó embeber el buscador oficial (HCDN/Senado mandan X-Frame-Options; no se puede iframe) y el link directo (los buscadores oficiales no aceptan búsqueda por URL).
- SOLUCIÓN adoptada (honesta y sin trabajo de detective): en el detalle, si la ley NO tiene texto, en vez de "Leer la ley completa" aparece "🔎 Buscar el texto en el Congreso ↗", que abre Google acotado al sitio oficial de la cámara de origen (`site:hcdn.gob.ar` o `site:senado.gob.ar`) con el título ya cargado. Primer resultado suele ser la ficha real. Abre en pestaña nueva.
- Helpers en la app: `buscadorCongreso(b)` y `textoBtn(b)`. El mapeo ahora trae `origen` y un flag `tieneTexto` (calculado del largo de texto_oficial que ya venía en el select). Bonus: el texto que ya bajaba el feed se guarda en `completa`, así "Leer la ley completa" abre sin segunda consulta.
- PENDIENTE ASOCIADO (opcional, camino "detective", largo): bajar automáticamente el texto de esas 12 desde el portal de la cámara de origen. No urgente: el usuario ya nunca ve pantalla vacía.

## PENDIENTES (prioridad) — actualizado
1. **Prensa RSS**: de 6 diarios solo responde Clarín (obrero 8). Arreglar o reemplazar las otras 5 fuentes + ajustar umbral. Acotado, no toca la base.
2. **Afinidad con legisladores** (Camino A, cálculo en el dispositivo, anonimato intacto): choca con el desfase temporal, madura con el uso. Es el "¿te representan?" — el gran tema de la mitad Votadas.
3. **Reponer logins** (app + admin) antes de producción; actualizar en Supabase Auth la Site URL y Redirect URLs de localhost a la de github.io (Didit ya usa callback_url dinámico). Restaurar flujo continuarTrasLogin/mostrarVerificacion (Didit) en la app y login por contraseña en la admin.
4. **Rol admin real** (hoy cualquiera con contraseña entra a la consola).
5. **Más módulos admin**: bancas (validar representantes contra padrón legisladores), usuarios/curadores con roles, controles sensibles (pisos, regla 60%).
6. **Prolijar autor de Diputados** a Title Case (opcional, cosmético).
7. **Bajar texto de las 12 leyes sin texto** desde la cámara de origen (opcional, "detective").
8. Penalizar puntaje de media sanción sin texto — REVISADO Y DESCARTADO como enfoque: mejor el botón al Congreso (ya hecho) que castigar en el ranking. Si igual se quiere, sería en el obrero 9 usando la vista estado_leyes (tiene_texto).

## ESTADO DE LAS TABLAS DE VOTACIONES (Congreso) — sin cambios esta sesión
- votaciones_congreso: 47 · votos_nominales: 6529 · legisladores: 330 · votadas_feed: 47.
- Fuente: repo comovoto de rquiroga7. Obrero 10_votadas.py, usa clasificar_tipo.py.
- Linkeo votación↔ley por SIMILITUD DE TÍTULO. Auto-linkeo mete errores → cola de linkeo manual en la admin.

## LOGIN DESACTIVADO (temporal, reponer antes de producción)
- App usuario: entra directo al feed. initAuth usa usuario fijo de desarrollo (id 75c330d1-...-2d12294aaad8, auth.users real) para que el voto funcione vía emitir_voto.
- cargarVotadas: sin sesión no lee ya_voto (RLS por auth.uid), así que en dev pueden reaparecer leyes ya votadas — no crítico.
- Admin: entra directo, sin credenciales.

## TABLAS EN SUPABASE (resumen)
leyes (+ columna **autor** nueva), votos, ya_voto, identidad_verificada, config_secreta, expertos,
votaciones_congreso, votos_nominales, legisladores, legisladores_autodeclarado, legisladores_fic..., votadas_feed.
Vista estado_leyes. Funciones clave: emitir_voto, resultados_por_ley, cola_linkeo, linkear_manual, descartar_link, admin_rescatar, admin_desvincular, admin_comparativa, admin_editar_titulo_feed, admin_editar_titulo_votada, admin_feed_leyes, admin_publicar, admin_expertos_*, votadas_lista/buscar/anios/tipos, votada_por_bloque, votada_nombres.
Edge Functions: crear-sesion, webhook-didit (Didit/RENAPER, desplegadas).

## OBREROS (tubería, PowerShell)
1-9 igual que el maestro. **10_votadas.py** (votaciones Congreso, NO está en pnyx_actualizar.py todavía). **11_autores.py** (backfill de autores, se corre a mano cuando haga falta; requiere la columna autor).
pnyx_actualizar.py corre 1→8, re-corre 1, corre 9.
Claves de entorno (se pierden al cerrar terminal): $env:SUPABASE_SERVICE_KEY (service_role, NO la publishable), $env:ANTHROPIC_API_KEY.

## LECCIONES DE ESTA SESIÓN
- El navegador cachea fuerte: Ctrl+Shift+R SIEMPRE.
- Las leyes con media sanción son un universo distinto de sus proyectos de origen: el texto de origen NO siempre está en Pnyx (filtro de años + identificadores que no cruzan entre cámaras). Ya avisado en el maestro para Votadas, ahora confirmado también para el feed.
- No se pueden embeber sitios oficiales grandes (X-Frame-Options). YouTube sí porque ofrece /embed/ pensado para eso.
- Verificar la teoría con SQL ANTES de escribir el obrero (se evitó armar un emparejador que no habría matcheado nada).
