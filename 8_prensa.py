#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pnyx · Obrero 8 — Radar de prensa (barrido completo diario)
------------------------------------------------------------
Confronta TODAS las leyes (vivan hace meses o sean de hoy) contra los
titulares frescos del dia. Una ley vieja puede volverse noticia hoy:
este obrero la detecta igual. No es incremental: barre todo cada vez.

Como: pide a Supabase id + titulo + oracion_ia de cada ley (liviano, sin
texto), saca palabras clave de "titulo + oracion", baja titulares por RSS
y marca importante_prensa=true si un titular comparte >=3 palabras clave.
Sube a Supabase solo los flags que cambiaron.

Reemplaza a los dos obreros viejos (Diputados + Senado) en uno solo.

Dependencia: pip install feedparser supabase
Uso:
  python 8_prensa.py           barrido normal (marca leyes, sube a Supabase)
  python 8_prensa.py --dry-run barre y muestra qué marcaría, SIN subir nada
  python 8_prensa.py --test    solo prueba las fuentes RSS y muestra cuales
                               responden (no toca Supabase, no necesita clave)
"""

import json
import os
import re
import sys
import time
import unicodedata

try:
    import feedparser
except ImportError:
    print("Falta feedparser. Instalalo con:  pip install feedparser", file=sys.stderr)
    sys.exit(1)

# supabase se importa solo cuando hace falta (el modo --test no lo necesita)

SUPABASE_URL = "https://ihmbhbhwlntsjqdavxge.supabase.co"
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")

MIN_AUTOMATICA = 4      # >=4 palabras en comun -> prioritaria automatica (al feed, +100)
MIN_SUGERENCIA = 3      # >=3 (y <4) -> se SUGIERE en la admin para que Benjamin decida
LOTE = 50

# User-Agent de navegador: sin esto, varios diarios rechazan al lector RSS (403).
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

# Fuentes confirmadas OK en la PC de Benjamín (05/09/2026): 8 feeds, ~355
# titulares por barrido. Para sumar/probar otra: agregarla acá y correr
# `python 8_prensa.py --test`; dejar solo las que traen titulares.
FUENTES = {
    "Clarin (politica)": "https://www.clarin.com/rss/politica/",
    "Clarin (economia)": "https://www.clarin.com/rss/economia/",
    "Clarin (portada)": "https://www.clarin.com/rss/lo-ultimo/",
    "Ambito (politica)": "https://www.ambito.com/rss/politica.xml",
    "Ambito (economia)": "https://www.ambito.com/rss/economia.xml",
    "Perfil (politica)": "https://www.perfil.com/feed/politica",
    "Perfil (economia)": "https://www.perfil.com/feed/economia",
    "El Cronista (economia)": "https://www.cronista.com/files/rss/news.xml",
}

STOP = set("""de la el los las del y o en para por con sobre que un una al se su sus
ley leyes proyecto nacional nacionales modificacion modificaciones regimen sistema
articulo art establecese establecer crease creacion del estado argentina argentino
publica publico sancion camara diputados senado proyecto presente sus esta este
ciudadanos personas derechos como mas para
declarase declarar declarese declara incorporacion incorporar incorporase modifica
modificase deroga derogase derogar creacion crease programa nacion nacionales
codigo penal civil procesal similar decreto federal provincia provincial ciudad
localidad partido interes historico cultural nacional bien monumento capital fiesta
transferencia autorizase disponese establecese emergencia primera instancia juzgado
articulos titulo capitulo materia proteccion integral promocion fomento fondo
funcion publica beneficio prestacion""".split())


def normaliza(s):
    s = unicodedata.normalize("NFD", (s or "").lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def palabras_clave(titulo, oracion):
    fuente = normaliza((titulo or "") + " " + (oracion or ""))
    palabras = re.findall(r"[a-zñ]{5,}", fuente)
    claves = []
    for p in palabras:
        if p not in STOP and p not in claves:
            claves.append(p)
    return set(claves[:15])


def cargar_titulares():
    titulares = []
    for nombre, url in FUENTES.items():
        try:
            feed = feedparser.parse(url, agent=UA)
            n = 0
            for e in feed.entries:
                texto = normaliza(getattr(e, "title", "") + " " + getattr(e, "summary", ""))
                if texto.strip():
                    titulares.append((nombre, texto))
                    n += 1
            print("  %s: %d titulares" % (nombre, n), file=sys.stderr)
        except Exception as ex:
            print("  %s: no se pudo leer (%s)" % (nombre, ex), file=sys.stderr)
    return titulares


def probar_fuentes():
    """Modo diagnostico: prueba cada feed y muestra si responde. No toca Supabase."""
    print("Probando fuentes RSS (con User-Agent de navegador)...\n", file=sys.stderr)
    ok, vacias, fallan = [], [], []
    for nombre, url in FUENTES.items():
        try:
            feed = feedparser.parse(url, agent=UA)
            status = getattr(feed, "status", "?")
            n = len(feed.entries)
            if n > 0:
                ok.append(nombre)
                marca = "OK"
            else:
                vacias.append(nombre)
                marca = "VACIA"
            ejemplo = ""
            if n > 0:
                ejemplo = " | ej: " + (getattr(feed.entries[0], "title", "")[:60])
            print("  [%-5s] status=%-3s entries=%-3d %s%s" % (marca, status, n, nombre, ejemplo), file=sys.stderr)
        except Exception as ex:
            fallan.append(nombre)
            print("  [FALLA] %s -> %s" % (nombre, ex), file=sys.stderr)
    print("\n=== RESUMEN ===", file=sys.stderr)
    print("Responden con titulares (%d): %s" % (len(ok), ", ".join(ok) or "-"), file=sys.stderr)
    print("Responden pero VACIAS (%d): %s" % (len(vacias), ", ".join(vacias) or "-"), file=sys.stderr)
    print("Fallan (%d): %s" % (len(fallan), ", ".join(fallan) or "-"), file=sys.stderr)
    print("\nDejá en FUENTES solo las que dicen OK. Borrá o comentá el resto.", file=sys.stderr)


def main():
    # Modo diagnostico: no necesita la clave de Supabase
    if "--test" in sys.argv:
        probar_fuentes()
        return

    if not SUPABASE_KEY:
        print("Falta:  $env:SUPABASE_SERVICE_KEY=\"...\"", file=sys.stderr)
        sys.exit(1)

    try:
        from supabase import create_client
    except ImportError:
        print("Falta supabase. Instalalo con:  pip install supabase", file=sys.stderr)
        sys.exit(1)

    sb = create_client(SUPABASE_URL, SUPABASE_KEY)

    # Traer TODAS las leyes (liviano: id, titulo, oracion, estado actual de prensa)
    print("Trayendo leyes de Supabase...", file=sys.stderr)
    leyes = []
    offset = 0
    while True:
        res = sb.table("leyes") \
            .select("bill_id,titulo,oracion_ia,importante_prensa,sugerida_prensa,prensa_descartada,prensa_confianza") \
            .range(offset, offset + 999).execute()
        leyes.extend(res.data)
        if len(res.data) < 1000:
            break
        offset += 1000
    print("Leyes totales: %d" % len(leyes), file=sys.stderr)

    print("\nBajando titulares del dia...", file=sys.stderr)
    titulares = cargar_titulares()
    print("\nTotal titulares: %d. Cruzando contra TODAS las leyes...\n" % len(titulares), file=sys.stderr)

    # Calcular estado de prensa para cada ley, en dos niveles:
    #  - >= MIN_AUTOMATICA diarios-palabras  -> prioritaria automatica (importante_prensa)
    #  - >= MIN_SUGERENCIA (y < automatica)   -> sugerencia para la admin (sugerida_prensa)
    # ACUMULA: una sugerencia queda prendida hasta que en la admin se ascienda o descarte.
    # RESPETA descartadas: si prensa_descartada=true, no se vuelve a sugerir.
    from datetime import datetime, timezone
    ahora = datetime.now(timezone.utc).isoformat()
    cambios = []
    autos_detalle = []       # (bill_id, titulo, n) automaticas de hoy
    sugeridas_detalle = []   # (bill_id, titulo, n) sugerencias nuevas de hoy
    n_auto = n_sug = 0
    for ley in leyes:
        claves = palabras_clave(ley.get("titulo"), ley.get("oracion_ia"))
        diarios_hit = set()
        for diario, titular in titulares:
            comunes = [c for c in claves if c in titular]
            if len(comunes) >= MIN_SUGERENCIA:
                diarios_hit.add(diario)
        # el "peso" es el maximo de coincidencias alcanzado en cualquier diario
        peso = 0
        for diario, titular in titulares:
            peso = max(peso, len([c for c in claves if c in titular]))

        es_auto = peso >= MIN_AUTOMATICA
        es_sug = (peso >= MIN_SUGERENCIA) and not es_auto
        descartada = bool(ley.get("prensa_descartada"))

        campos = {}
        # --- Nivel automatico: entra sola al feed (salvo que Benjamin la haya descartado) ---
        if es_auto:
            n_auto += 1
            autos_detalle.append((ley["bill_id"], ley.get("titulo", ""), len(diarios_hit)))
            if not descartada and not bool(ley.get("importante_prensa")):
                campos["importante_prensa"] = True
                campos["prensa_confianza"] = "alta"
        # --- Nivel sugerencia: no entra al feed; espera revision en la admin ---
        elif es_sug and not descartada and not bool(ley.get("importante_prensa")):
            if not bool(ley.get("sugerida_prensa")):
                campos["sugerida_prensa"] = True
                campos["prensa_confianza"] = "media"
                campos["prensa_sugerida_en"] = ahora
                n_sug += 1
                sugeridas_detalle.append((ley["bill_id"], ley.get("titulo", ""), len(diarios_hit)))

        if campos:
            campos["bill_id"] = ley["bill_id"]
            cambios.append(campos)

    # Subir los cambios a Supabase (salvo modo --dry-run)
    dry = "--dry-run" in sys.argv
    if cambios and not dry:
        for i in range(0, len(cambios), LOTE):
            sb.table("leyes").upsert(cambios[i:i+LOTE], on_conflict="bill_id").execute()
            time.sleep(0.3)

    print("\n--- PRIORITARIAS AUTOMATICAS (>=%d) : %d ---" % (MIN_AUTOMATICA, n_auto), file=sys.stderr)
    for bid, tit, nd in sorted(autos_detalle, key=lambda x: -x[2]):
        t = (tit[:58] + "...") if len(tit) > 58 else tit
        print("  ⭐ [%d diario%s] %s  %s" % (nd, "s" if nd != 1 else "", bid, t), file=sys.stderr)

    print("\n--- SUGERENCIAS NUEVAS (>=%d, para revisar en la admin) : %d ---" % (MIN_SUGERENCIA, n_sug), file=sys.stderr)
    for bid, tit, nd in sorted(sugeridas_detalle, key=lambda x: -x[2]):
        t = (tit[:58] + "...") if len(tit) > 58 else tit
        print("  ? %s  %s" % (bid, t), file=sys.stderr)

    print("\n=== RESULTADO ===", file=sys.stderr)
    print("Prioritarias automaticas detectadas hoy: %d" % n_auto, file=sys.stderr)
    print("Sugerencias nuevas para la admin: %d" % n_sug, file=sys.stderr)
    if dry:
        print("(DRY-RUN: NO se subio nada. Cambios que se harian: %d)" % len(cambios), file=sys.stderr)
    else:
        print("Cambios subidos a Supabase: %d" % len(cambios), file=sys.stderr)
    print("(Las sugerencias se revisan en la admin: ascender a prioritaria o descartar.)", file=sys.stderr)
    print("(Para reflejar los cambios en el feed, corre el Obrero 9.)", file=sys.stderr)


if __name__ == "__main__":
    main()
