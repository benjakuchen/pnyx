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

## HECHO 2/10
- **Botón "Saltar por ahora"** en el feed de votar: la ley saltada se manda al final del mazo y sigue circulando hasta que la votes (o la vote el Congreso, en cuyo caso deja de aparecer). No se marca como votada. Funciona con botón y lo dejé con animación hacia arriba. (index.html)

## HECHO 4/10 (eficiencia del admin)
- **Curaduría: ver resumen y ley completa sin salir de la cola**: botón "📄 De qué trata" en cada proyecto. (pnyx-admin.html)
- **Curaduría: la cola muestra SOLO leyes**; homenajes/declaraciones/pedidos de informe van a un botón "🗂️ Todo lo demás" con buscador (por si hay un falso positivo que rescatar). Filtro por título en el navegador. (pnyx-admin.html)
- **Editar título y resumen inline + se guarda**, en Curaduría / Feed / Votadas. Título = oracion_ia (lo que ve el ciudadano); resumen = resumen_ia. (pnyx-admin.html + sql_admin_editar.sql) → CORRER sql_admin_editar.sql en Supabase.
- **Contadores arriba**: Feed "N publicadas de M"; Votadas "N destacadas de M". (pnyx-admin.html)
- **Caducidad arreglada**: la columna `fecha` es TEXT; las funciones fallaban (text < date). Corregido con cast por regex. Se archivaron 906 proyectos viejos (de 1716 → 809 en cola). (sql_caducidad.sql) → YA corrido en Supabase.
- **Caducado automático**: obrero 18 (18_caducar.py) sumado al maestro tras 14_curaduria → la cola se limpia sola a las 4am. (18_caducar.py + pnyx_actualizar.py)
- **Rescatar no se re-caduca**: al rescatar, se marca `rescatada=true`; el caducado automático la respeta. (sql_caducidad.sql nuevo) → CORRER sql_caducidad.sql actualizado en Supabase.
- **Orden manual del feed**: flechas ▲▼ en la pestaña Publicadas. Columna `orden_manual` que NINGÚN obrero toca; el feed del ciudadano la respeta (manual arriba, resto por puntaje). (pnyx-admin.html + index.html + sql_orden_manual.sql) → CORRER sql_orden_manual.sql en Supabase.

## SQL PENDIENTE DE CORRER EN SUPABASE (clave — sin esto la app da error)
1. `sql_admin_editar.sql` (versión con bigint) — editar título/resumen; sin esto Feed y Curaduría dan error 400.
2. `sql_caducidad.sql` (versión con `rescatada`) — rescatadas no re-caducan.
3. `sql_orden_manual.sql` — flechas de orden del feed; sin esto dan error.

## EN CURSO (5/10): Formulario metodológico + roles de autoría en la Plaza
Lo que hay hoy (básico): curadores con cupo 9 editan artículos sueltos directo; aportes de cualquiera; apoyar anónimo; cerrar texto. FALTA elevarlo a lo siguiente:

### A. Formulario guiado por secciones (estructura real de un proyecto de ley)
Verificado con fuentes oficiales (Senado + UBA/HCDN técnica legislativa). Un proyecto de ley argentino tiene:
1. Título / denominación (breve).
2. Fórmula de sanción (FIJA, la pone la app): "El Senado y Cámara de Diputados de la Nación Argentina, reunidos en Congreso,... sancionan con fuerza de Ley:".
3. Articulado (parte dispositiva), orden temático típico: Objeto (art.1) → Ámbito/Definiciones → Cuerpo (disposiciones de fondo) → Autoridad de aplicación → Disposiciones finales/Vigencia → Artículo de forma FIJO: "Comuníquese al Poder Ejecutivo.".
4. Fundamentos / exposición de motivos (obligatorio): problema, antecedentes, qué se busca lograr.
Diseño: secciones sugeridas pero EDITABLES (se pueden agregar/quitar artículos). La app arma el documento final con el formato oficial (fórmula + articulado + comuníquese), presentable para que un diputado lo tome casi tal cual.

### B. Roles de autoría (decidido 5/10)
- AUTOR/dueño (quien creó la iniciativa): es el EDITOR FINAL. Los curadores PROPONEN cambios; el autor los ACEPTA o RECHAZA antes de que entren al texto. El autor puede ECHAR a un curador.
- Curadores (hasta 9): proponen cambios, no editan directo.
- Aportes/enmiendas: cualquier verificado, desde afuera (ya existe).
- Autor ausente: tras inactividad, el rol lo HEREDA el curador más antiguo (la iniciativa no muere).

### C. Transparencia del legislador al presentar
- Cuando un diputado presenta el proyecto, debe SUBIR el documento realmente presentado. Se muestra junto al texto ciudadano para ver si introdujo cambios (no debería). Control público "esto construyó la gente / esto presentó el diputado".

Pendiente de construir: tablas de propuestas de cambio (pendientes de aprobación), campo de rol autor, secciones del formulario, generación del documento oficial, carga del doc presentado, lógica de herencia por inactividad. Es grande: hacerlo por partes.

## IDEA (anotada 5/10): Reputación / participación cívica
- Objetivo: cuantificar la actividad de cada ciudadano para premiar el COMPROMISO cívico (no la viralidad). Tabla de actividad por usuario + puntaje, y ranking de "ciudadanos más comprometidos".
- Actividades a contar (cada una con su valoración/peso, a definir): votar proyectos, apoyar iniciativas, ser curador, hacer aportes/enmiendas, editar artículos (editor de proyectos), proponer una iniciativa, etc.
- CUIDADO CON EL ANONIMATO (clave): votar proyectos y apoyar iniciativas son anónimos (no se sabe QUÉ votó). Pero el PUNTAJE se puede calcular sin romper eso: `ya_voto` (user_id, ley_bill_id) y `ya_apoyo` (user_id, iniciativa_id) registran QUE participó, NO el sentido. Entonces se cuenta la cantidad de participaciones sin tocar el contenido. Las de curaduría/aportes ya van por nick, sin problema.
- Diseño posible: tabla `actividad_civica` (user_id, tipo, puntos, ref, fecha) o calcular on-the-fly desde ya_voto/ya_apoyo/iniciativa_curadores/iniciativa_enmiendas. Definir pesos por actividad. Mostrar en el Perfil ("tu huella") y, si se quiere, un ranking.
- Pendiente: definir los pesos de cada actividad y si el ranking es público (ojo: exponer "quién participa más" puede tensionar con el anonimato/acoso; quizás el ranking es por nick y voluntario).

## VISIÓN: "Iniciativas / La plaza" — que la gente construya leyes (prototipo 4/10)
Prototipo visual navegable hecho (prototipo_iniciativas.html, artifact). Es VISIÓN, no construido aún.
Idea: la comunidad construye un proyecto, junta respaldo verificado y un diputado lo presenta.
Marco legal: la iniciativa popular formal (ley 24.747) pide ~1,5% del padrón (~500.000 firmas en papel, 6+ provincias, verificadas por la justicia electoral) y NO reconoce firma digital. Por eso Pnyx NO apunta a esa firma: apunta a construir el texto + demostrar respaldo real de ciudadanos verificados, para que un legislador lo presente. La firma en papel queda como etapa futura.
Decisiones de diseño tomadas:
- Flujo (10 pasos): La plaza → Proponer → Redactar → Las reglas → La sala → Apoyar o mejorar → Apoyar → Medir → ¡Lo logramos! → Presentar.
- Redacción: equipo CURADOR con CUPO (ej. 9). Quien propone es el primer curador. El resto no edita directo.
- Disenso: NO hay "en contra". Se propone enmienda/objeción; si junta apoyo, los curadores deben responder. El "en contra" real es el feed de votar.
- Anti-duplicados: al proponer, Pnyx detecta iniciativas parecidas (similitud de título) y sugiere unirse; puede insistir y crear igual.
- Punto de no retorno: al pasar a juntar respaldo, el texto se CONGELA en una versión. Se apoya esa versión. Un cambio de fondo pide RE-CONFIRMAR a los que ya apoyaron.
- Anonimato: apoyo con DNI verificado, se cuenta agregado + provincia, sin publicar nombre. Curadores trabajan por SEUDÓNIMO.
- Terreno de construcción: DENTRO de Pnyx (editor de artículos + chat del equipo por seudónimo), NO un Drive externo. Fuente de verdad única y trazable.
- Contacto entre curadores: por seudónimo dentro de la app. Compartir el mail es decisión INDIVIDUAL, de a uno, y solo DESPUÉS de presentado el proyecto. Cartel de advertencia al entrar ("conocer gente con tus ideales puede ser hermoso, pero expone tu figura a acoso por tu posición política").
- Homenaje al legislador que la presenta: sello "🏅 Escuchó a la ciudadanía" en su banca/ficha + agradecimiento de los que apoyaron. (Ojo: distinto de los "homenajes" del Congreso que se descartan como ruido; usar lenguaje "sello/reconocimiento".)
- Corazón de comunidad en "La plaza": pulso vivo (N personas construyendo hoy), caras + provincias, actividad reciente, tu huella (apoyaste N, M llegaron al Congreso), festejo de hitos compartido.
PENDIENTE para construir: es un proyecto grande. Necesita tablas nuevas (iniciativas, curadores, enmiendas, apoyos, versiones), editor colaborativo, chat, y el chequeo de admisibilidad de tema. Retomar desde el prototipo cuando se decida arrancar.

## PENDIENTES

### 0. Doble cámara — BASE LISTA 4/10, resto esperando datos
- HECHO: columna `ley_par` en leyes (enlaza las 2 versiones; ningún obrero la toca). Funciones admin_vincular_camaras / admin_desvincular_camaras / ley_par_info. Aviso en la app: al abrir el detalle para votar, si ya votaste la par en la otra cámara, cartel "ya votaste X" (usa el histórico local, respeta anonimato). (sql_doble_camara.sql + index.html) → CORRER sql_doble_camara.sql en Supabase.
- POR QUÉ NO SE HIZO MÁS: al 4/10 hay 14 leyes con media sanción pero NINGUNA tiene par cargado (son 14 leyes distintas, cada una a mitad de camino; falta la versión de la 1ª cámara), y NINGUNA tiene texto_oficial. Sin pares no hay qué vincular; sin textos no hay qué comparar.
- FALTA (cuando haya pares y textos reales):
  - Pantalla de vinculación en el admin (híbrido: sugerir el par más parecido por título + confirmar/rechazar). Guarda con admin_vincular_camaras.
  - Comparación de textos entre cámaras (resumen IA "respecto de Diputados, el Senado modificó…"). Requiere texto_oficial de ambas.
- A investigar aparte: por qué las de media sanción no tienen texto_oficial (¿problema de carga del texto?).

### 0-viejo. Doble cámara: misma ley en Diputados y Senado (notas originales)
- Problema: una ley pasa por las dos cámaras (media sanción). Hoy aparece 2 veces: se puede votar 2 veces y se resume 2 veces. Pero el texto puede haber CAMBIADO entre cámaras, así que no siempre es redundante.
- Decisión: opción 2 = AVISAR al usuario ("ya votaste esta ley en la otra cámara, votaste X; ahora está en la otra con posibles cambios") + COMPARAR qué cambió.
- Plan por pasos:
  - PASO A (lo más pesado): vincular las 2 versiones de la misma ley entre cámaras. Hoy NO hay vínculo (bill_id distintos: HCDN... vs SENADO...). Vía realista: por título/similitud (como el obrero 16 de linkeo).
  - PASO B (fácil, una vez hecho A): al cargar una ley para votar, si el usuario ya votó su par en la otra cámara, mostrar aviso. No bloquear.
  - PASO C: resumen comparativo IA ("respecto de Diputados, el Senado modificó..."). Requiere A + texto de ambas.
- PENDIENTE INMEDIATO para retomar: correr en Supabase y pegar el resultado →
  `select bill_id, camara, origen, expediente, titulo from leyes where media_sancion = true limit 15;`
  (para ver si se pueden vincular las cámaras con lo que ya hay).

### 1. Aplicar y verificar el linkeo (obrero 16) — INMEDIATO
- Correr `python 16_linkeo.py` (aplica). Solo 1 ley se despublica (Patentes → HCDN...); las demás solo suman resumen.
- Verificar en la app: abrir una votada linkeada (ej. Mercosur-UE) y ver la tarjeta "📄 De qué trata".
- Si hay algún match malo, desvincular desde admin → Linkeo.
- Obrero 16 NO va al maestro automático (gasta crédito de API): correr a mano.
- Sumar **17_labor** al maestro (ese sí, no gasta API).

### NUEVOS (pedido 21/09)

#### A. Admin — editar el título mostrado — HECHO 4/10
- Feed, Curaduría y Votadas: título editable inline y se guarda.

#### HECHO 23/09 — Admin: ver resumen y ley completa
- En Feed y en Votadas, botón "📄 Resumen y ley completa" en cada tarjeta: muestra resumen IA + texto completo desplegable + link al documento oficial (igual que la app del ciudadano). Carga bajo demanda por REST, sin tocar RPCs. En Votadas depende del linkeo. (pnyx-admin.html)

#### B. Votadas — cartel de posible ausentismo tendencioso
- En una votada: si la diferencia entre afirmativos y negativos es chica Y ese número es parecido al de ausentes, mostrar un cartel de "posible ausentismo tendencioso" (cuando la ausencia pudo definir el resultado).
- Definir el criterio exacto (umbrales de "diferencia chica" y "parecido a ausentes").

#### HECHO 24/09 — Votadas Históricas: buscador arreglado
- Causa: había DOS versiones de la función votadas_buscar en Supabase (una vieja con p_tipo). Postgres no sabía cuál usar (error PGRST203) → la app crasheaba (histResultados.filter is not a function). Se borró la vieja: drop function votadas_buscar(text, integer, text, integer). Además index.html ahora valida que la respuesta sea array (no crashea si vuelve a pasar).

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

### 7. Registro DNDA — CAMBIO DE RUMBO (2/10): ir por obra INÉDITA, no publicada
- Qué pasó: en el trámite de obra PUBLICADA (EX-2026-91494536) la DNDA liquidó un arancel enorme (del orden de $200.000.000) porque se declaró un valor de ejemplar/edición altísimo. No tiene sentido pagar eso para registrar software.
- Decisión: NO subsanar ni pagar ese expediente. Dejarlo caer / no continuarlo.
- Hacer en su lugar: registro de obra **INÉDITA** (arancel fijo bajo, del orden de $1.400). Retomar el expediente de inédita que ya existía: EX-2026-59025992.
- La protección de la obra (el código) es la misma; lo que cambia es que "inédita" no dispara el arancel por valor de edición.
- PENDIENTE: completar/retomar EX-2026-59025992 como obra inédita y pagar el arancel fijo. (Lo hacemos cuando toque, está anotado.)

### 8. Seguridad admin (URGENTE antes de público)
- El admin NO tiene login activo ("modo desarrollo"). Reactivar login/rol antes de abrir al público.

### 9. Otros
- Reactivar "Confirm email" en Supabase antes de público.
- Términos y condiciones: texto real (hoy el checkbox no lleva a nada).
- Limpiar código muerto en index.html (funciones viejas de votadas: votedOrder, chipLabel, cargarTipos, esVotadaMostrable).

### 10. Contador del feed cuenta "de 1000" (límite PostgREST)
- El feed del admin trae máximo 1000 filas (tope por defecto), así el contador dice "de 1000" en vez de las ~2000 reales. Subir el límite o contar por RPC aparte.
