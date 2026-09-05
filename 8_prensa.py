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

MIN_COINCIDENCIAS = 3   # cuantas palabras clave en comun para marcar (estricto)
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
ciudadanos personas derechos como mas para""".split())


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
            .select("bill_id,titulo,oracion_ia,importante_prensa") \
            .range(offset, offset + 999).execute()
        leyes.extend(res.data)
        if len(res.data) < 1000:
            break
        offset += 1000
    print("Leyes totales: %d" % len(leyes), file=sys.stderr)

    print("\nBajando titulares del dia...", file=sys.stderr)
    titulares = cargar_titulares()
    print("\nTotal titulares: %d. Cruzando contra TODAS las leyes...\n" % len(titulares), file=sys.stderr)

    # Calcular el nuevo estado de prensa para cada ley
    cambios = []
    marcadas = 0
    for ley in leyes:
        claves = palabras_clave(ley.get("titulo"), ley.get("oracion_ia"))
        diarios_hit = set()
        for diario, titular in titulares:
            comunes = [c for c in claves if c in titular]
            if len(comunes) >= MIN_COINCIDENCIAS:
                diarios_hit.add(diario)
        nuevo_flag = len(diarios_hit) > 0
        if nuevo_flag:
            marcadas += 1
        # Subir solo si cambio respecto a lo que esta en Supabase
        if nuevo_flag != bool(ley.get("importante_prensa")):
            cambios.append({"bill_id": ley["bill_id"], "importante_prensa": nuevo_flag})
            if nuevo_flag:
                t = (ley.get("titulo", "")[:55] + "...") if len(ley.get("titulo", "")) > 55 else ley.get("titulo", "")
                print("  ⭐ NUEVA en prensa: %s (%s)" % (ley["bill_id"], t), file=sys.stderr)
            else:
                print("  ○ Salio de prensa: %s" % ley["bill_id"], file=sys.stderr)

    # Subir los cambios a Supabase
    if cambios:
        for i in range(0, len(cambios), LOTE):
            sb.table("leyes").upsert(cambios[i:i+LOTE], on_conflict="bill_id").execute()
            time.sleep(0.3)

    print("\n=== RESULTADO ===", file=sys.stderr)
    print("Leyes marcadas en prensa (total): %d de %d" % (marcadas, len(leyes)), file=sys.stderr)
    print("Cambios subidos a Supabase: %d" % len(cambios), file=sys.stderr)
    print("(El admin revisa estas marcas; no deciden solas.)", file=sys.stderr)
    print("(Para reflejar el cambio en el feed, corre los Obreros 10 y 11.)", file=sys.stderr)


if __name__ == "__main__":
    main()
