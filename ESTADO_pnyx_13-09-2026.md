# PNYX — Actualización de estado (13/09/2026)
### Reemplaza a los ESTADO anteriores. Se suma a MAESTRO_pnyx_12-07-2026.md. Para retomar en un chat nuevo.

## CÓMO RETOMAR
Todo el código vive en GitHub: **https://github.com/benjakuchen/pnyx** (público).
En un chat nuevo, pedir leer el repo completo (.html, obreros .py, edge functions, este archivo y el MAESTRO). Ese es el punto de retomo permanente.

- App usuario ONLINE: https://benjakuchen.github.io/pnyx/pnyx-app-v6.html
- Admin ONLINE: https://benjakuchen.github.io/pnyx/pnyx-admin.html
- Benjamín: Windows/PowerShell, no programador, guiar paso a paso en rioplatense. San Juan.
- Flujo: editar archivo → `git add . / commit -m "..." / push` → 1-2 min online. **Ctrl+Shift+R (hard refresh) SIEMPRE**, el caché muerde fuerte (perdimos rato por no hacerlo).
- Las Edge Functions se editan y despliegan desde la WEB de Supabase (Edge Functions → función → pegar código → Deploy). Benjamín no usa CLI.

## HITOS DE ESTA SESIÓN (09/09/2026) — fue larga, muchos avances

### 0. FLUJO DE LEYES revisado + PLAN DE CURADURÍA (decisiones tomadas, falta implementar)
Cómo entra hoy una ley: obrero 2/5 baja del CSV de HCDN (proyectos tipo LEY del año en curso + revisiones del año anterior) → entra a tabla `leyes` con **publicada=true por DEFAULT** → la app muestra las publicada=true ordenadas por puntaje. O sea HOY se publica TODO automático, sin revisión. 969 leyes, 967 publicadas.
Problemas detectados: (a) entra ruido (declaraciones, homenajes, capitales de la trufa, pedidos de informe) mezclado con leyes reales; (b) nada saca del feed las leyes ya SANCIONADAS (el CSV de proyectos no trae estado de trámite).

DECISIONES DE BENJAMÍN para la curaduría (a implementar, es un mini-proyecto de varias piezas):
1. **Nada se publica solo.** Cambiar el default a publicada=FALSE. Todo entra despublicado, Benjamín revisa (corrige título, busca expertos, saca lo que no es ley real) y recién ahí publica. Régimen mixto: el sistema propone/prioriza, Benjamín decide.
2. **Filtrar "ley real"**: sacar declaraciones, resoluciones, homenajes, adhesiones, pedidos de informe, capitales/fiestas nacionales. Solo leyes (y acuerdos/tratados).
3. **Empezar de cero**: despublicar las 969 actuales y curar desde un panel de revisión en la admin (feed queda vacío hasta publicar). Benjamín aceptó el costo.
4. **Traer leyes VIEJAS (2024-2025) que sigan vivas**: definición alcanzable = las que tengan MEDIA SANCIÓN pendiente (en dataset de sanciones con PRIMERA_MEDIA_SANCION pero sin SANCION_DEFINITIVA) O que estén en prensa. NO traer las solo "formalmente vivas" sin movimiento (serían ruido dormido).
5. **Permanencia**: el estado manda. Si se sancionó, sale del feed (aunque haya estado poco); no hay permanencia mínima. Una ley que el usuario votó ya no le aparece a ÉL (individual, ya funciona vía ya_voto); una ley sancionada sale para TODOS (global, es la Capa 1).
ORDEN sugerido al retomar: (1) filtro de ley real → (2) panel de revisión en admin → (3) despublicar todo y curar → enganchar obrero 13 (salida) y traer viejas.
PENDIENTE que Benjamín debía traer: el SQL que agrupa el ruido (declaraciones/homenajes/etc.) para dimensionar cuántas de las 969 son "ley real" vs ruido.

### 0b. OBRERO 13 — Salida de leyes SANCIONADAS — LISTO, falta aplicar
- Nuevo obrero 13_sanciones.py: baja el dataset oficial HCDN "Leyes Sancionadas" (JSON, no CSV; https://datos.hcdn.gob.ar/dataset/leyes-sancionadas). Trae PROYECTO_ID (= bill_id, cruce DIRECTO), CAMARA_SANCIONADORA, SANCION_DEFINITIVA, LEY (número), EXPEDIENTE_INICIAL, PRIMERA/SEGUNDA_MEDIA_SANCION. 1337 proyectos sancionados en el dataset.
- Modos: --test (muestra columnas, no toca nada), --dry-run (cuenta sin escribir), normal (despublica + marca estado_tramite='sancionada').
- DRY-RUN dio: solo **2 leyes** del feed ya sancionadas (HCDN282431, HCDN286131). Pocas porque el feed es mayormente del año en curso (aún en trámite).
- El dataset de HCDN cubre TODAS las sancionadas del Congreso (toda ley pasa por Diputados). Fleco: leyes nacidas en Senado ya sancionadas podrían tener bill_id SENADO... y no cruzar por ID. Se descartó cruzar por expediente (formatos distintos: tabla '193/26' vs dataset '0020-S-2026'; mucho trabajo para ~0 casos). Para ese fleco → botón manual de despublicar en la admin (pendiente).
- FALTA: correr sql_estado_tramite.sql (columna estado_tramite), luego `python 13_sanciones.py` para aplicar, luego obrero 9.



### 1. LOGIN REPUESTO con modo invitado — HECHO
- Antes entraba directo al feed con un usuario fijo de desarrollo (eliminado).
- Ahora: pantalla de bienvenida con "Empezar" (crear cuenta) y "Mirar sin cuenta".
- Invitado ve TODO (feed, bancas, resultados) pero al intentar votar → lo manda a crear cuenta (interceptado en doVote y en el swipe up()).
- Flujo: o0 bienvenida → oC país → oTyc términos → oRen crear cuenta/login → oVer verificación → app.
- Config Supabase Auth YA estaba OK (Site URL = https://benjakuchen.github.io, Redirect URLs con github.io). 
- IMPORTANTE: se ACTIVÓ el provider Email y se DESACTIVÓ "Confirm email" en Supabase (registro instantáneo, sin confirmar por mail). Esto es para desarrollo; **reactivar Confirm email antes de producción pública**.
- Fix scroll de pantallas de onboarding (#onb tenía height indefinido; ahora height:100% + flex; los display='block' pasaron a 'flex'). Los mensajes de error/confirmación ahora se ven (antes quedaban cortados abajo).

### 2. VERIFICACIÓN DE IDENTIDAD (Didit/RENAPER) — FUNCIONANDO de punta a punta
- Didit está OPERATIVO. Webhook "PNYX" en Didit ACTIVO, escucha status.updated, secret ya coincide (User-Agent DiditWebhook/2.0; el x-signature viejo valida bien, NO hubo que tocar la firma).
- Edge functions desplegadas y corregidas:
  - **crear-sesion**: ahora manda `callback` (URL de la app) para que Didit devuelva al usuario a la app al terminar. La app pasa su URL como callback. (Antes no volvía solo; ahora sí.)
  - **webhook-didit**: BUG CLAVE resuelto → los datos vienen en `decision.id_verifications` (ARRAY, plural), no `id_verification` (singular). Por eso antes guardaba fila con NULL.
- Datos que Didit devuelve (confirmado con verificación real): document_number, date_of_birth, **age**, gender, parsed_address {city, region, postal_code}, full_name, etc. parsed_address YA viene clasificado → NO hace falta IA.
- Se guarda de forma ANÓNIMA en identidad_verificada (SQL sql_segmentacion.sql corrido): rango_edad ('36-50' etc., NO fecha exacta), genero (M/F/X), provincia (=region), ciudad, codigo_postal, dni_hash (hash, NO el DNI en claro). NO se guarda nombre/apellido/dirección de calle.
- Perfil: nuevo bloque "🪪 Verificá tu identidad" con botón que dispara Didit; cuando está verificado muestra "Identidad verificada ✅". La cabecera dice "Ciudadano verificado ✅" solo si de verdad lo está.
- Fix RLS: la app no reconocía la verificación porque consultaba sin token. Solución: (a) política RLS `iv_lee_lo_suyo` (SELECT USING auth.uid()=user_id) en identidad_verificada; (b) la app consulta con el access_token de la sesión (no solo apikey). Ahora sí reconoce.

### 3. ANTI-DUPLICADO "una persona, un voto" — HECHO Y PROBADO ✅
- Hallazgo clave: Didit NO bloquea el mismo DNI en dos cuentas (aprobó dos veces el mismo doc). El anti-duplicado es tarea de Pnyx.
- CONFIRMADO por SQL: la tabla `votos` NO tiene user_id (columnas: id, created_at, ley_id, voto, zona, ley_bill_id, sello). Los votos son ANÓNIMOS DE VERDAD, no seudónimos: aunque se reconstruya DNI→email→user_id, se corta ahí (user_id no lleva a ningún voto). Por eso guardar dni_hash es seguro.
- Solución (sin tabla nueva): el webhook, antes de aprobar, busca si el dni_hash ya está en OTRA cuenta verificada. Si sí → no aprueba, guarda motivo_rechazo='documento_ya_usado'. La app muestra "🚫 Documento ya registrado".
- PROBADO OK (09/09): se verificó con la cuenta Hotmail (bekuchen@hotmail.com) el mismo DNI que ya tenía la Gmail (benjaminkuchen@gmail.com) → el sistema lo detectó y mostró "Documento ya registrado". Funciona de punta a punta.
- (SQL sql_antiduplicado.sql corrido; webhook desplegado; app con el mensaje.)

### 4. PERFIL: historial de votos + afinidad — HECHO en sesión previa a esta, reconfirmado
- Historial de votos LOCAL (localStorage, solo en el dispositivo, nunca al servidor → no rompe anonimato). En el perfil, tarjeta "📜 Tu historial" que abre pantalla propia. Aviso al votar: "voto definitivo y anónimo".
- Afinidad "¿con quién coincidís?": motor en el dispositivo (cruza historial local con votos del Congreso vía RPC afinidad_votos_legisladores). Umbral 8 leyes coincidentes para mostrar; hoy solo 3 votaciones del Congreso están linkeadas a leyes del feed → muestra "en construcción" con contador. Se enciende solo cuando maduren los datos. (SQL sql_afinidad.sql.)

## PENDIENTES (prioridad)
0. **⚠️ AUTOMATIZAR LA TUBERÍA DE OBREROS (crítico para lanzar)**: hoy los obreros corren SOLO cuando Benjamín los ejecuta a mano en su PC (`python pnyx_actualizar.py` + 10/12/13/14). NO hay nada automático. Para 15.000 usuarios el feed TIENE que actualizarse solo, a diario. Plan: GitHub Actions (gratis, el repo ya está ahí) que corra la tubería en horario fijo. Requiere: claves como secrets en GitHub, que los obreros funcionen sin archivos locales (estado_nube.json), dimensionar costo de IA por corrida, orden correcto (1→9, luego 10,12,13,14). La curaduría convive bien: los obreros llenan la COLA automáticamente, Benjamín publica desde la admin. HACERLO AL FINAL, cuando la tubería esté estable y probada a mano.
1. **CURADURÍA DEL FEED** (el gran tema abierto, ver Hito 0): filtro de ley real → panel de revisión en admin (default despublicado) → despublicar las 969 y curar desde cero → aplicar obrero 13 (salida sancionadas) → traer viejas 2024-25 con media sanción/prensa. Es un mini-proyecto de varias sesiones.
2. **Prueba completa del flujo** como usuario nuevo (incógnito): bienvenida → mirar sin cuenta → intentar votar → crear cuenta → verificar → votar → historial → afinidad. (El anti-duplicado ya quedó probado OK.)
2. **App móvil / tiendas**: hoy es web app. Camino: PWA instalable (rápido) → luego Capacitor para App Store/Google Play (reusa el código, requiere cuenta dev Apple US$99/año, Google US$25). Va DESPUÉS de que la web funcione redonda con usuarios reales.
3. **Recuperación de cuenta**: por email (Supabase ya lo tiene) + liberación manual del dni_hash desde la admin si alguien pierde acceso al email. Falta armar el módulo admin.
4. **Estética "tipo oración"**: leyes/resúmenes/autores vienen TODO EN MAYÚSCULAS (del CSV de HCDN). Pasar a Tipo Oración. Logo "pnyx" en minúsculas. (Pedido pendiente, no hecho.)
5. **Reactivar "Confirm email"** en Supabase antes de producción pública.
6. **Rol admin real** (hoy cualquiera con la URL entra a la consola).
7. **Vínculo "tengo una banca"** (perfil ciudadano ↔ tabla bancas): que un legislador solicite validar su banca y el admin apruebe. Hoy el admin activa bancas a mano desde el panel.
8. Bajar texto de las 12 leyes sin texto (opcional, "detective").
9. Prolijar autor Diputados a Title Case (cosmético).

## HITOS DE SESIONES PREVIAS (05/09) — ya cerrados
- **Expertos**: opiniones reales con reproductor YouTube en la app; botón condicional. Admin carga opiniones.
- **Autor en tarjetas**: columna autor en leyes, obreros 3/6 la suben, obrero 11_autores.py backfill. App lo muestra.
- **Botón "Buscar en el Congreso"**: para leyes sin texto (12 con media sanción), abre Google acotado a hcdn/senado según cámara de origen.
- **Prensa RSS**: 8 fuentes (Clarín x3, Ámbito x2, Perfil x2, El Cronista). Obrero 8 con --test y --dry-run. Umbral 4 automáticas + umbral 3 sugerencias.
- **Panel de Prensa en admin**: automáticas (peso≥4) entran solas al feed con ⭐, sugerencias (peso 3) esperan revisión. Ascender/desmarcar/descartar. Acumula, respeta descartadas. RPCs admin_prensa_lista/admin_prensa_accion.
- **Bancas que escuchan REAL**: tabla bancas (330 legisladores: 258 dip + 72 sen), obrero 12_bancas.py (lista+cámara de tabla legisladores, presentismo cruzado de comovoto por nombre, 324/330 con presentismo). App: solapas Dip/Sen, buscador, agrupado por provincia, presentismo + sello escucha. Admin: panel Bancas con toggles validada/escucha. RPCs bancas_lista/admin_bancas_lista/admin_banca_toggle.
- **Navegación**: barra inferior FIJA (era min-height, ahora height:100dvh). Historial en pantalla propia.

## TABLAS EN SUPABASE (resumen)
leyes (+autor, +importante_prensa, +sugerida_prensa, +prensa_sugerida_en, +prensa_descartada, +prensa_confianza), 
votos (SIN user_id: id, created_at, ley_id, voto, zona, ley_bill_id, sello), ya_voto, 
identidad_verificada (user_id, verificado, metodo, dni_hash, rango_edad, genero, provincia, ciudad, codigo_postal, motivo_rechazo, verificado_en, didit_session_id), 
config_secreta, expertos, bancas, 
votaciones_congreso, votos_nominales (voto: AFIRMATIVO/NEGATIVO/AUSENTE/ABSTENCION/PRESIDENTE), legisladores (258 dip + 72 sen), votadas_feed.
Vista estado_leyes. RLS: identidad_verificada con política iv_lee_lo_suyo; bancas con lectura pública.
Funciones: emitir_voto, resultados_por_ley, cola_linkeo, linkear_manual, admin_*, bancas_lista, admin_bancas_lista, admin_banca_toggle, admin_prensa_lista, admin_prensa_accion, afinidad_votos_legisladores, afinidad_leyes_disponibles, votadas_*.
Edge Functions: crear-sesion (manda callback), webhook-didit (lee id_verifications array, anti-duplicado por dni_hash).

## DIDIT (verificación de identidad)
- Cuenta operativa. Workflow con features: ID_VERIFICATION, LIVENESS, FACE_MATCH, IP_ANALYSIS.
- Secrets en Supabase Edge Functions: DIDIT_API_KEY, DIDIT_WORKFLOW_ID, DIDIT_WEBHOOK_SECRET.
- Webhook PNYX → https://ihmbhbhwlntsjqdavxge.supabase.co/functions/v1/webhook-didit (activo, status.updated).
- vendor_data = user_id de la app (así el webhook sabe de quién es). OJO: verificar que crear-sesion mande el user_id de la cuenta LOGUEADA (una vez arrastró un id viejo).
- Cada verificación cuesta ~US$0.33. No re-verificar al pedo. Para probar sin gastar, se pueden cargar datos a mano (el JSON completo de la sesión queda en Didit → Sessions).

## OBREROS (tubería, PowerShell)
(nuevo: 13_sanciones.py — salida de sancionadas, con --test/--dry-run)
1-9 según maestro. 10_votadas.py (votaciones Congreso). 11_autores.py (backfill autores). **12_bancas.py** (carga tabla bancas + presentismo comovoto). 8_prensa.py con --test y --dry-run.
pnyx_actualizar.py corre 1→8, re-corre 1, corre 9. (10, 11, 12 se corren aparte a mano.)
Claves de entorno (se pierden al cerrar terminal): $env:SUPABASE_SERVICE_KEY (service_role), $env:ANTHROPIC_API_KEY.

## LECCIONES DE ESTA SESIÓN
- Ctrl+Shift+R SIEMPRE antes de decir "no anda" (perdimos rato por esto varias veces).
- Verificar con DATOS REALES antes de codear: el JSON real de Didit reveló id_verifications (plural) que rompía todo; el SQL de la tabla votos confirmó que no hay user_id (anonimato real).
- Anonimato: "sin user_id en el voto" = anónimo de verdad. "con user_id" = solo seudónimo (reconstruible con acceso a la base). Pnyx tiene lo primero.
- RLS: si la app consulta sin el access_token de la sesión, auth.uid() es null y las políticas por usuario bloquean la lectura. Hay que mandar el token.
- Didit no bloquea DNI duplicado: es responsabilidad de Pnyx (dni_hash).
- Nombre de columna (dni_hash) no es riesgo; lo que importa es guardar hash y no el número en claro.

## ANOTADO PARA DESPUÉS (linkeo votar↔votadas)
- Revisar la lógica del linkeo (hoy es por similitud de título, mete errores → cola manual en admin).
- Usar números de expediente como pista: Senado guarda '193/26', el dataset de sanciones trae EXPEDIENTE_INICIAL '0020-S-2026'. Normalizando (número+año) se pueden sugerir matches.
- EVALUAR LINKEO POR IA: comparar el TEXTO OFICIAL de una votación del Congreso con el de la ley del feed para sugerir el match. Por eso Benjamín quiere bajar TODOS los textos (no solo los publicados).
- Regla: NUNCA borrar de las tablas, solo filtrar la vista (los datos ocultos sirven de llave para cruces).
- Benjamín corre obreros 3 y 6 a escala para bajar texto de las ~800 que faltan (python 3_texto_diputados.py 2000 / python 6_texto_senado.py 2000). Gratis, tarda, algunas fallan (normal).

## RECORDATORIO
- Tendencias/resultados: mostrar recién en votaciones NACIONALES y con umbral de ~15.000 personas (anonimato). No mostrar con pocos votos.

## CURADURÍA — APLICADA Y FUNCIONANDO ✅ (13/09)
- Se corrió el obrero 14: ~16 automáticas + cola de ~816 + 132 ruido. Default de publicada = false.
- Benjamín usó el panel de la admin (pestaña 📋 Curaduría): publicó leyes. Quedaron 22 publicadas.
- PROBADO OK en incógnito: la app muestra el feed con las publicadas, títulos limpios y resúmenes. Circuito completo funciona (curar → publicar → feed). Si en la ventana normal el feed se ve vacío es porque Benjamín YA VOTÓ esas leyes (van a su historial); en incógnito aparecen.
- "Publicar" pone publicada=true (feed). "Despublicar"/"Descartar" la saca. Título editable a mano en la admin.

## TEXTOS Y RESÚMENES A ESCALA (13/09)
- Obrero 3 (Diputados) bajó 558 de 773, PERO se CORTÓ al final: HCDN BLOQUEA por volumen tras ~570 descargas rápidas. FALTA: ponerle pausa (1-2s) + backoff al obrero 3 (hoy NO tiene), y re-correr para las ~215 restantes.
- Obreros 4/7 (resumen) filtran por PUBLICADAS con texto sin oración. Funcionan bien (oraciones claras). Solo gastan IA en publicadas.
- Obrero 15 (OCR) funciona: lee escaneados y resume.
- Flujo: bajar texto (3/6) → resumir (4/7) → OCR escaneados (15). Todo filtra por publicadas.

## LEYES FANTASMA — limpiadas (13/09)
- 31 filas basura (bill_id SENADO6xx-26, TODO lo demás null). Despublicadas (no las veía el usuario) pero ensuciaban la cola. NO venían de votaciones.
- Borradas con: delete from leyes where (titulo is null or titulo='') and (expediente is null or expediente='').
- PENDIENTE: encontrar QUÉ las crea (¿obrero 5 parseando filas vacías del Excel del Senado?) y agregar filtro para no guardar leyes sin título/expediente.

## SENADO (obrero 6) — RESUELTO ✅ (cookies + backoff adaptativo)
- CAUSA RAÍZ encontrada: el Senado solo da el HTML completo (con el link del PDF) si tenés COOKIES DE SESIÓN. Sin cookies devuelve versión reducida sin link. Solución: el obrero 6 ahora visita la home primero (_iniciar_sesion) y usa un opener con http.cookiejar. Probado con probar_senado_uno.py → bajó el PDF del 97/26 OK.
- SEGUNDO problema: el Senado BLOQUEA por velocidad (páginas de 31570 bytes exactos tras pocos pedidos rápidos). Solución: BACKOFF ADAPTATIVO guardado en senado_backoff.json. Arranca en 30s entre expedientes; si hubo bloqueo en la corrida, la próxima usa +60s; si fue limpia, baja 5s (mín 15s, máx 600s). Se auto-calibra entre corridas.
- Mecanismo confirmado: ficha verExp/{num}.{anio}/{ORIGEN}/PL (prueba orígenes S/PE/CD) → link <a href="/parlamentario/parlamentaria/{id}/downloadPdf"> en el HTML → baja PDF → extrae texto.
- Estrategia de Benjamín: bajada inicial lenta (dejar corriendo `python 6_texto_senado.py 2000` de fondo, tarda horas a 30s c/u) + mantenimiento diario (el Senado genera pocas nuevas por día, el goteo lento alcanza). NO hay dataset de datos abiertos con los TEXTOS (solo listados de metadatos), así que el scraping es el único camino.
- Casos que quedan sin texto (normal): (a) "en proceso de carga" = el Senado no publicó el PDF aún; (b) escaneados (ej. tratado 97/26, 669 págs imagen) → van al pendiente "texto escaneado, leelo en el original".
- Obrero 3 (Diputados) baja perfecto, sin estos problemas.
- probar_senado_uno.py quedó como herramienta de diagnóstico (prueba un expediente aislado con cookies).

## PENDIENTE: manejo de textos ESCANEADOS (a armar tras bajar textos del Senado)
- Algunos PDFs del Congreso son escaneados (imagen, no texto): extraer() devuelve vacío (ej. tratado 97/26 del Senado, 669 págs escaneadas). Hoy quedan como "sin texto".
- Idea de Benjamín: la app debe mostrar en esos casos "📄 Texto escaneado (no legible automáticamente), leelo en el documento oficial ↗" + LINK DIRECTO al PDF (tenemos el link: parlamentaria/{id}/downloadPdf).
- Piezas a armar: (1) SQL columnas texto_escaneado (bool) + url_pdf_oficial (text); (2) obreros 3 y 6: si el PDF existe pero extraer() da vacío → marcar escaneado + guardar el link; (3) app: si escaneada, mostrar el mensaje con el link en vez del botón normal.
- PRIMERO: bajar los textos del Senado (obrero 6 ya arreglado: prueba orígenes S/PE/CD) para ver CUÁNTOS escaneados hay realmente y dimensionar. Si son pocos, es menor.

## PENDIENTE: OCR de PDFs escaneados (decidido, a implementar tras aplicar curaduría)
- Muchos PDFs del Senado (y algunos de Diputados) son ESCANEADOS: bajan pero extraer() da texto=0 (ej. 193/26 bajó PDF de 36MB sin texto). Bajarlos es lo que además dispara el bloqueo del Senado.
- DECISIÓN de Benjamín: para los que van al feed (automáticos + los que él aprueba en curaduría), hacer OCR con IA de las PRIMERAS ~15 PÁGINAS (donde está el articulado; el resto suele ser anexos). NO OCR completo (carísimo en un tratado de 669 págs).
- Implementación: detectar escaneado (PDF baja pero sin texto) → convertir primeras 15 págs a imagen (pdf2image + poppler, instalar en Windows) → mandar a Claude (lee imágenes) para transcribir/resumir → guardar como texto_oficial. Toca obreros 4/7 (resumen).
- Solo se OCR-ea lo que se publica (por eso va DESPUÉS de la curaduría). Costo asumido.
- Columnas ya pensadas: texto_escaneado (bool), url_pdf_oficial (link) — para app "texto escaneado, leelo en el original" en los que NO se OCR-ean todavía. (sql_escaneados.sql creado pero no aplicado.)

## OCR de escaneados — RESUELTO ✅ (obrero 15)
- Obrero nuevo 15_ocr.py: para leyes PUBLICADAS + escaneadas (texto_escaneado=true) sin oración, baja el PDF de Supabase Storage, convierte las primeras 15 págs a imagen con **pypdfium2** (NO poppler — poppler falló al instalar/descomprimir en Windows; pypdfium2 se instala solo con pip), y se las manda a Claude (lee imágenes) que devuelve oracion + resumen en una pasada.
- PROBADO OK: SENADO5-26 (PDF 26MB escaneado, un tratado) → la IA lo leyó y resumió correctamente.
- Ajuste clave: NO pedir el "texto" transcripto completo (inflaba la respuesta y cortaba el JSON). Solo oracion + resumen (que es lo que se muestra). max_tokens=800, DPI=110.
- Flujo Senado completo: obrero 6 baja PDF (cookies) → si escaneado lo sube a Storage (bucket pdfs-leyes) + marca texto_escaneado + url_pdf_oficial → obrero 15 lo lee con IA. Solo se procesan las PUBLICADAS (curaduría).
- Requiere: pip install pypdfium2. Claves SUPABASE_SERVICE_KEY + ANTHROPIC_API_KEY.
- Costo: leer 15 imágenes cuesta más que resumir texto; por eso solo las publicadas.
- PENDIENTE: la app debe mostrar bien estas leyes (tienen oracion/resumen pero texto_oficial vacío; el botón "leer completa" debería llevar al PDF en url_pdf_oficial). Revisar que la app maneje texto_escaneado con link al PDF.
