# PNYX — DOCUMENTO MAESTRO DE ESTADO (12/07/2026)
### Reemplaza al maestro del 07/07. Para pegar/subir al inicio del próximo chat, junto con el Pnyx_MVP.md original

---

## QUIÉN Y CÓMO
- Benjamín (bekuc). App cívica argentina de democracia participativa.
- Windows / VS Code / PowerShell. Carpeta: C:\Users\bekuc\Downloads\PNYX
- No programador: guiar pasito a paso, español rioplatense, directo, sin vueltas.
- Servidor local: `cd C:\Users\bekuc\Downloads\PNYX` → `python -m http.server 3000` → `http://localhost:3000/pnyx-app-v6.html`

## QUÉ ES PNYX (esencia)
- La ciudadanía vota (a favor / en contra / abstención) los proyectos de ley reales del Congreso argentino.
- Voto 100% anónimo por diseño; identidad y voto viven en bases separadas que NUNCA se cruzan.
- Resúmenes de leyes en lenguaje claro generados por IA (etiquetados como tales, neutralidad estricta).
- Fase 0: identidad liviana → Fase 2: identidad dura (RENAPER). Hoy: verificación biométrica vía Didit funcionando.

## ARQUITECTURA DE DATOS (Supabase = única fuente de verdad)
URL: https://ihmbhbhwlntsjqdavxge.supabase.co
Llave publishable (pública): sb_publishable_ih-dOjPauQayOpzn7uL6vw_vIt96ZHR

### Tablas del FEED (voto ciudadano) — sin cambios
- **leyes**: bill_id (UNIQUE), expediente, titulo, camara, origen, oracion_ia, resumen_ia, fecha, puntaje_pnyx, media_sancion, importante_prensa, texto_oficial. ~969 leyes (838 Diputados, 100 Senado, 31 sin cámara).
- **votos** (ANÓNIMA): ley_bill_id, voto, sello (HMAC). RLS: solo vía función emitir_voto.
- **ya_voto** (IDENTIDAD): user_id, ley_bill_id, votado_en. PK compuesta = anti-duplicación.
- **identidad_verificada**: user_id, verificado, metodo, dni_hash, didit_session_id.
- **config_secreta** (RLS cerrado): sello_secreto.
- Vista **estado_leyes** + función **emitir_voto** (SECURITY DEFINER).

### 🆕 Tablas de VOTADAS (votaciones reales del Congreso) — NUEVO 12/07
Información PÚBLICA. Universo SEPARADO de votos/ya_voto (que son anónimas). Sin cruce entre ambos mundos.
- **legisladores**: id, nombre, nombre_normalizado, camara, bloque, provincia, foto_url (vacío), partido (vacío), frente (vacío). UNIQUE(nombre_normalizado, camara) = dedup.
- **votaciones_congreso**: id, camara, acta_id, titulo, orden_del_dia, expediente_fuente, resultado, afirmativos, negativos, abstenciones, ausentes, presidente, votada_en, **ley_bill_id** (link opcional al feed), **match_score**, fuente. UNIQUE(camara, acta_id) = obrero re-ejecutable sin duplicar.
- **votos_nominales**: votacion_id, legislador_id, voto ('AFIRMATIVO'/'NEGATIVO'/'ABSTENCION'/'AUSENTE'/'PRESIDENTE'), bloque_en_voto, provincia_en_voto. PK(votacion_id, legislador_id). Guarda bloque/provincia AL MOMENTO del voto (histórico honesto: los legisladores cambian de bloque).
- **legisladores_autodeclarado**: legislador_id, eje_economico (-100..100), eje_social (-100..100), declarado_por (uuid), validado, validado_en. TABLA APARTE a propósito: el obrero NUNCA la toca, solo la escribe el legislador validado (RLS: auth.uid() = declarado_por). Es la brújula del MVP: autodeclarada, nunca asignada por Pnyx.
- RLS: lectura pública en las 3 primeras; escritura solo con service key (el obrero).
- Vistas: **votadas_feed**, **legisladores_ficha**.

### 🆕 Funciones de VOTADAS
- **votadas_lista(p_limite int default 15)** → las N votaciones más recientes.
- **votadas_buscar(p_texto, p_anio, p_limite)** → buscador de Históricas (título sin tildes + filtro por año).
- **votadas_anios()** → años disponibles con su cantidad (para el filtro).
- **votada_por_bloque(p_votacion_id)** → conteos agrupados por bloque (el servidor agrupa, no el navegador).
- **votada_nombres(p_votacion_id, p_bloque)** → nombres + provincia + voto de los legisladores de ese bloque.
- Todas SECURITY DEFINER, con grant execute a anon.

## 🆕 OBRERO 10_votadas.py — LA OTRA MITAD DE PNYX
Puebla las tablas de Votadas. Incremental y re-ejecutable (salta las actas ya guardadas).

**Fuentes por cámara (decisión clave):**
- **DIPUTADOS → JSON de como_voto** (`raw.githubusercontent.com/rquiroga7/como_voto/main/data/diputados.json`). NO se scrapea HCDN directo: **votaciones.hcdn.gob.ar tiene anti-bot y bloquea con 403** apenas detecta varias requests seguidas (probado: ni con backoff de 12s entra). como_voto ya lo resolvió, es open source, se actualiza lunes y jueves. Sus datos son de fuente oficial y dominio público.
- **SENADO → scraping propio directo** (anda sin bloqueo). El detalle del acta (`/votaciones/detalleActa/{id}`) trae TODO junto: título + expediente (formato `PE-159/25-PL`) + O.D. + tabla de votos con columnas fijas [Foto, Senador, Bloque, Provincia, ¿Cómo votó?].

**Reglas de filtrado (calibradas con datos reales):**
- Solo se guarda la votación **EN GENERAL** de cada ley. Una ley genera 20+ actas (general + cada título/capítulo); guardar todas ahogaría la pestaña.
- Diputados, 3 niveles: sin O.D. → interna (moción/apartamiento, descartar) · con O.D. + Capítulo/Título/Artículo → particular (descartar) · con O.D. sin eso → **general (guardar)**. OJO: los tratados NO dicen "EN GRAL" pero SÍ son leyes; por eso la regla es por O.D., no por la frase.
- Senado: descarta particulares y actos internos (sin expediente NI O.D. = designación/ratificación/moción).
- Normaliza bloques y provincias al insertar (ver lección abajo).

**Uso:**
```
$env:SUPABASE_SERVICE_KEY = "..."   (service_role, NO la publishable)
python 10_votadas.py               → baja 2026 y sube
python 10_votadas.py --dry-run     → baja y muestra, NO sube (lee con la llave pública)
python 10_votadas.py --anio 2026 --solo senado
```

**Estado actual de los datos:** 23 votaciones (17 Diputados + 6 Senado) de 2026, ~4.800 votos nominales, ~270 legisladores.

## 🆕 EL LINK CON EL FEED (método 2) — Y POR QUÉ ES PARCIAL
Descubrimiento importante del detective: **las leyes que se VOTAN son un universo distinto de las que están en el feed.**
- El acta de votación identifica el asunto por **Orden del Día**, no por expediente.
- El expediente que sale del puente O.D. (ej. `159/25`) **no matchea** el formato de la tabla `leyes` (`SENADO159-26`, `1234-D-2026`), y encima suele ser de un año anterior.
- Ejemplo: el Súper RIGI se votó en 2026 pero NO está en la tabla `leyes` (entró antes, con otra numeración).
- **Solución adoptada:** link oportunista por TÍTULO (fuzzy, umbral 0.65). Engancha poco: de 17 votaciones de Diputados, 3 linkearon (Zona Fría 0.67, Penal Juvenil 0.72, Presupuestos Mínimos 0.76). Se guarda en `ley_bill_id` + `match_score`.
- **Decisión de producto de Benjamín:** "Votadas" vive DESACOPLADA del feed. No interesa que la gente vote lo ya votado. El link es un plus para el futuro "¿te representan?", no la columna vertebral.

## LA APP (pnyx-app-v6.html)
- Onboarding: bienvenida → consentimiento → login → verificación de identidad (Didit).
- Feed: leyes de Supabase por puntaje_pnyx.desc, filtra las ya votadas.
- Voto: guardarVoto → /rpc/emitir_voto.
- Lenguaje ciudadano: título IA + oficial en letra chica, glosario tocable (GLOSA), micro-consejos, sección 📚 Aprender.
- Lectura progresiva 3 niveles: tarjeta (oración IA) → Ver el proyecto (resumen IA) → ley completa (texto oficial).

### 🆕 Pestaña VOTADAS — CONECTADA A DATOS REALES (12/07)
La interfaz ya existía mockeada; ahora lee de Supabase.
- **Dos vistas:** "Recientes" (las 15 más recientes, `VOTADAS_RECIENTES=15`) y "🔎 Históricas" (buscador por título + filtro por año).
- **Criterio "15 más recientes", NO por tiempo:** el Congreso vota poco (~40 leyes/año Diputados, ~15 Senado). Un corte por meses dejaría la pestaña casi vacía. Por cantidad, siempre está llena.
- Chips **apilados por cámara** (Diputados arriba, Senado abajo), NO en una sola fila con scroll horizontal (el Senado quedaba invisible).
- Al elegir una ley: resultado + desglose por bloque con **siglas** (diccionario `SIGLAS` + fallback automático) y el **número de ausentes** visible.
- Al tocar un bloque: **nombres reales** de los legisladores con provincia y voto (lazy load vía `votada_nombres`).
- Carga progresiva: lista liviana → detalle por bloque → nombres. Nunca baja los 4.800 votos de una.
- Si la ley tiene `ley_bill_id`, muestra un aviso 🔗 (el puente al futuro "¿te representan?").

## VERIFICACIÓN DE IDENTIDAD (Didit) — FUNCIONANDO END-TO-END
- Workflow "Free KYC": 96121d2c-7d50-45f7-941d-c26419573cbb. Documento + prueba de vida + coincidencia facial (500 gratis/mes).
- Módulo RENAPER ($0.20/consulta) DESTILDADO (Didit exige carga mínima USD 50).
- Edge Functions: **crear-sesion** y **webhook-didit** (--no-verify-jwt, valida firma HMAC + timestamp ±5 min, dni_hash SHA-256 con sal "|pnyx-sal").
- Secretos: DIDIT_API_KEY, DIDIT_WORKFLOW_ID, DIDIT_WEBHOOK_SECRET.
- PROBADO end-to-end. ✔

## TUBERÍA DE DATOS (obreros incrementales, PowerShell)
Claves: $env:SUPABASE_SERVICE_KEY, $env:ANTHROPIC_API_KEY (se pierden al cerrar terminal).
1. **1_consultar_supabase.py** → estado_nube.json
2. **2_bajar_diputados.py** → CSV datos abiertos HCDN; detecta "venidas en revisión"
3. **3_texto_diputados.py [N|--todos]** → PDF → texto_oficial
4. **4_resumir_diputados.py [N]** → Claude (JSON {oracion,resumen}, neutralidad estricta)
5. **5_bajar_senado.py** → Excel del Senado
6. **6_texto_senado.py [N|--todos]** → ídem 3
7. **7_resumir_senado.py [N]** → ídem 4
8. **8_prensa.py** → barrido RSS; ≥3 palabras clave → importante_prensa=true
9. **9_mezclar_ordenar.py** → puntaje: media sanción +150, prensa +100, novedad +40/+25/+10
10. **🆕 10_votadas.py** → votaciones reales del Congreso (ver arriba). NO está en pnyx_actualizar.py todavía.
- **pnyx_actualizar.py [--full]** → maestro: corre 1→8, re-corre 1, corre 9.

## PENDIENTES DE VOTADAS (descubiertos hoy, por prioridad)
1. **Sumar 10_votadas.py a pnyx_actualizar.py** para que corra en la tubería diaria.
2. **2 dudosas del Senado a limpiar:** "Reconocimiento a la labor del Equipo Argentino de..." (es declaración, no ley) y "Moción de preferencia para el tratamiento..." (trámite interno). Pasaron el filtro porque tienen O.D. Borrarlas a mano + afinar el criterio.
3. **El Senado se ve corto (6 leyes en 2026).** Verificar que el filtro `es_particular` no se esté comiendo leyes legítimas: hoy marca particular si el texto COMPLETO del acta contiene "EN PARTICULAR"/"TÍTULO", lo cual puede ser demasiado amplio.
4. **Provincia en Diputados sin normalizar** para agrupar prolijo (viene de como_voto; en el Senado sí sale limpia de la columna fija). Anotado por Benjamín.
5. **Partido y frente**: columnas creadas pero VACÍAS. Poblarlas requiere otra fuente (datos electorales) + su propio detective. Son datos objetivos (no ideología).
6. **Agrupar por provincia** en el detalle de una votación (hoy solo por bloque). Requiere el punto 4.
7. **Brújula autodeclarada**: tabla lista, falta el flujo en la app (el legislador valida banca → completa sus 2 ejes). Ligado a "Validar mi banca" (hoy mock).
8. **"¿Te representan?"**: comparar voto ciudadano (Pnyx) vs. voto real del Congreso, para las leyes con `ley_bill_id`. Es el gran tema pendiente y lo que le da sentido a la mitad de Votadas.

## OTROS PENDIENTES (del maestro anterior, siguen vigentes)
1. Git + hosting real (GitHub Pages): resuelve caché, versiones, Site URL de Supabase (hoy localhost:3000).
2. Autor + foto en tarjetas del feed (hoy "Propone: •" vacío).
3. Fuentes RSS de prensa (arreglar La Nación/P12/Diario de Cuyo) + ajustar umbral (hoy solo Clarín responde de 6).
4. Penalizar puntaje de media sanción sin texto.
5. Reactivar RENAPER cuando se decida + revisión legal Ley 25.326 antes de producción.
6. Videos de la sección Aprender (en producción por Benjamín).
7. **Bug menor preexistente:** error en consola `tramite is not defined` (algo del glosario GLOSA, línea ~802). No afecta Votadas.

## RASGOS DE LA APP YA IMPLEMENTADOS (no olvidar en rediseños)
- El termómetro/tendencia NO se muestra en el swipe (anti efecto manada); solo en Tendencias, vía resultados_por_ley.
- Voto atado a ley_bill_id (número oficial permanente), no al id de fila.
- Inicio con carrusel de frases + selector de país.
- T&C con dos casillas separadas.
- Lectura progresiva en 3 niveles. Siempre etiquetar qué es IA y qué es oficial.
- Lado representante (mock): "Validar mi banca", estados pendiente/validado, videos "explicá tu voto".

## DISEÑO CERRADO DEL MVP AÚN NO IMPLEMENTADO (deuda de producto)
- Regla del 60%: tendencia solo si un bucket ≥60%; si no, "dividido".
- Pisos de revelado: nacional 5.000 · provincial 1.000 · nivel 2 300 (piso duro 50).
- GEO-ETIQUETADO del voto desde el día 1 (provincia + unidad_n2). HOY LA COLUMNA zona VA NULL — deuda concreta.
- Frontera por distrito: ciudadano ve agregado nacional; representante validado ve SOLO su distrito.
- Representantes: revalidación automática contra nómina oficial, vencimiento por mandato, identidad persistente (la persona, no el cargo), legajo público DESCRIPTIVO (presentismo, votos, quiebres, coherencia con distrito) — nunca puntaje ni ranking. **NOTA: las tablas de Votadas son la base de datos de este legajo.**
- Voces por ley: expertos (≥2, afiliación declarada, ~2 min) → panel ciudadano (1 por ley) → primeros 5 legisladores que opinen ANTES de votar. Videos en YouTube, sin "me gusta", orden aleatorio.
- Brújula política 2 ejes autodeclarada: SOLO expertos y candidatos, nunca el ciudadano. **NOTA: tabla legisladores_autodeclarado ya creada.**
- Consola de administración: roles, módulos, gobernanza editorial (default: entran TODAS las leyes; despublicar es excepción; log de auditoría inviolable).
- Notificaciones — regla de oro: por la ley, NUNCA por la ausencia del usuario. Sin rachas ni gamificación.
- API pública de tendencias: solo datos que pasaron piso y regla 60%.
- Sello "URGENTE / se vota y es noticia" para media sanción + prensa.
- Comunidad (a futuro): anclada a cada ley, todo por video. Frontera visible (🔒 secreto vs 👁️ público).
- T&C: documento legal completo (Ley 25.326, AAIP) + resumen humano.
- Privacidad — regla de honestidad: NUNCA vender el voto como "inviolable"; prometer el diseño, no el milagro.
- Riesgos vigilados: adopción del representante (el verdadero riesgo), movilización organizada, oración IA nivel 1 = mayor superficie de sesgo.

## ADVERTENCIA PARA GIT
El Pnyx_MVP.md contiene la clave secreta del sello HMAC en texto plano. Antes de subir a un repo (aun privado), sacarla. La clave vive en config_secreta.

## LECCIONES OPERATIVAS (para no repetir)
- **El navegador cachea fuerte: Ctrl+Shift+R SIEMPRE.** (Volvió a morder hoy: la pestaña Votadas "no andaba" y era caché.)
- **HCDN (votaciones.hcdn.gob.ar) tiene anti-bot.** Bloquea con 403 tras varias requests, aun con backoff largo. Por eso Diputados va vía como_voto. El Senado, en cambio, se scrapea sin problema.
- **Diputados y Senado escriben los bloques distinto:** Diputados (vía como_voto) en Title Case sin tildes ("La Libertad Avanza"); Senado en MAYÚSCULAS con tildes ("LA LIBERTAD AVANZA"). Sin normalizar, el mismo bloque queda DUPLICADO en la base. El obrero ahora normaliza al insertar (`norm_bloque`); hubo que correr un UPDATE para arreglar lo ya cargado.
- **Una ley = muchas actas.** El Congreso vota en general + título por título. Hay que quedarse con la general o la pestaña se ahoga.
- **El detective antes que el código.** Casi todo el tiempo de Votadas se fue en descubrir (anti-bot, identificadores que no cruzan, una ley = N actas, capitalización) — no en escribir el obrero. Sin esa etapa, el obrero habría nacido roto.
- PowerShell rompe JSON en curl: usar Invoke-RestMethod con try/catch.
- findstr con espacios busca OR, no frase exacta.
- Los archivos generados deben descargarse y moverse a la carpeta correcta.
- No pegar claves secretas en el chat (una API key de Didit se expuso y se rotó).
- Preferir pegar texto de terminal/consola antes que capturas.
