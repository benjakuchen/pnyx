# PENDIENTES Pnyx — al 20/09/2026

Registro de todo lo acordado que falta hacer, para no perderlo entre sesiones.

## HECHO en esta tanda (20/09)
- **Votadas — elegir cámara primero**: al entrar, dos botones grandes Senado/Diputados arriba de las pestañas Destacadas/Últimas/Históricas; cada sección filtra por la cámara elegida. (index.html)
- **Votadas — resumen IA + documento**: en el detalle de una votada linkeada aparece la tarjeta "📄 De qué trata" (resumen IA) y el botón "Ver el documento oficial". Solo cuando la votación está linkeada a una ley del feed (comovoto no trae ni resumen ni PDF). (index.html)
- **Bancas rediseñadas**: foto real (desde comovoto), labor parlamentaria (leyes presentadas) y presentismo; lista rankeada sin agrupar por provincia. Diputados ordenados por labor, Senadores por presentismo. Botones Senado/Diputados. (index.html + sql_bancas_labor.sql + 17_labor.py)
- **Obrero 17 (labor parlamentaria)** creado: cuenta leyes por legislador cruzando autor↔apellido y guarda en bancas.leyes_presentadas. TOP validado (PAGANO 105, PROPATO 39...). 174 con labor, 89 sin match. (17_labor.py + sql_bancas_labor.sql)
- **Admin reorganizado**: navegación de 2 niveles (grupos + subtabs) con las mismas separaciones que la app: Feed de votar / Votadas / Linkeo votar↔votadas / Bancas (Validaciones, Videos, Legisladores) / Sistema. Sin tocar la lógica. (pnyx-admin.html)
- **Obrero 16 (linkeo)** afinado: linkea contra TODAS las leyes con texto; título ≥0.72 acepta directo, 0.62–0.72 la IA confirma (sí/no), <0.62 la IA elige entre las 5 mejores por título (o ninguna). Dry-run limpio: 7 matches. (16_linkeo.py + sql_linkeo.sql)
- **Tendencias — umbral y anonimato**: constante `UMBRAL_TENDENCIA=100`. Con menos de 100 votos por ley → cartel "Todavía no hay suficientes votos", sin barra ni tag. Desde 100 → solo porcentajes, SIN mostrar cantidad de votos. Aplicado en Tendencias, en el termómetro (post-voto) y en el cruce comunidad-vs-Congreso. El admin sigue viendo números reales. (index.html)

## PENDIENTES

### 1. Aplicar y verificar el linkeo (obrero 16) — INMEDIATO
- Correr `python 16_linkeo.py` (aplica). Solo 1 ley se despublica (Patentes → HCDN...); las demás solo suman resumen.
- Verificar en la app: abrir una votada linkeada (ej. Mercosur-UE) y ver la tarjeta "📄 De qué trata".
- Si hay algún match malo, desvincular desde admin → Linkeo.
- Obrero 16 NO va al maestro automático (gasta crédito de API): correr a mano.
- Sumar **17_labor** al maestro (ese sí, no gasta API).

### 2. Panel de deslizadores en el admin (grupo Sistema)
- Sliders continuos para calibrar lo automático: umbral de prensa, sensibilidades, ventanas de fechas.
- Requiere: tabla de config en Supabase + RPC leer/escribir + que los obreros lean de ahí (hoy hardcodeado) + UI en admin. Mini-proyecto.

### 4. Sugerencia de destacadas por prensa (mejora)
- El 📰 en curaduría solo aparece si la votación está linkeada a una ley con prensa. Para sugerir sobre CUALQUIER votación, adaptar el obrero 8 para escanear también títulos de votaciones_congreso.

### 5. Boletín Oficial del Ejecutivo (idea a futuro)
- Sección con lo que hace el Ejecutivo (decretos, DNU, resoluciones), no solo el Congreso.

### 6. Dominio propio (en curso)
- pnyx.ar / pnyx.com.ar registrados; esperar activación (nslookup pnyx.ar).
- Cuando activen: DNS en nic.ar → GitHub Pages, Custom domain en Settings→Pages, y actualizar Site URL + Redirect en Supabase al dominio nuevo.

### 7. Registro DNDA (en curso)
- Obra publicada iniciada (EX-2026-91494536). Falta: pagar aranceles y subir el ZIP cuando llegue el mail con link+contraseña (60 días hábiles).
- Dejar el de obra inédita (EX-2026-59025992) como antecedente, no cancelar.

### 8. Seguridad admin (URGENTE antes de público)
- El admin NO tiene login activo ("modo desarrollo"). Reactivar login/rol antes de abrir al público.

### 9. Otros
- Reactivar "Confirm email" en Supabase antes de público.
- Términos y condiciones: texto real (hoy el checkbox no lleva a nada).
- Limpiar código muerto en index.html (funciones viejas de votadas: votedOrder, chipLabel, cargarTipos, esVotadaMostrable).

## Para subir hoy
- Push de los commits pendientes (index.html, pnyx-admin.html, 16_linkeo.py, 17_labor.py y los .sql).
- Correr en Supabase: `sql_bancas_labor.sql`, `sql_linkeo.sql` (y `sql_votadas_v4.sql` si no se corrió).
- Correr en la PC: `python 17_labor.py` (labor) y `python 16_linkeo.py` (linkeo).
