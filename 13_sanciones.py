#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pnyx · Obrero 13 — Estado de trámite: sacar del feed las leyes YA SANCIONADAS
------------------------------------------------------------------------------
Baja el dataset oficial de HCDN "Leyes Sancionadas" (proyectos convertidos en
ley) y marca en la tabla `leyes` cuáles del feed ya fueron sancionadas, para
despublicarlas (salen del feed de votación; su lugar es "Votadas").

Idea: si una ley del feed ya es ley, no tiene sentido pedir opinión previa.

MODOS:
  python 13_sanciones.py --test     baja el CSV y MUESTRA sus columnas + una
                                    prueba de cruce. NO toca Supabase. Empezá acá.
  python 13_sanciones.py --dry-run  hace el cruce completo y dice cuántas
                                    despublicaría, sin escribir.
  python 13_sanciones.py            aplica: despublica las sancionadas y les
                                    marca estado_tramite='sancionada'.

Requisitos: pip install requests supabase
"""

import csv
import io
import os
import re
import sys
import time

import requests

SUPABASE_URL = "https://ihmbhbhwlntsjqdavxge.supabase.co"
SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")

# Dataset "Leyes Sancionadas" de HCDN (trámite de proyectos convertidos en ley).
# Si la URL cambió, buscar en https://datos.hcdn.gob.ar/dataset/leyes-sancionadas
CSV_URL = ("https://datos.hcdn.gob.ar/dataset/leyes-sancionadas/"
           "resource/a449095f-1818-4918-8600-455724db34ac/download/")
UA = "Pnyx/1.0 (obrero-sanciones)"
LOTE = 50


def descargar(url):
    r = requests.get(url, headers={"User-Agent": UA}, timeout=90)
    r.raise_for_status()
    r.encoding = r.apparent_encoding or "utf-8"
    return r.text


def leer_filas(texto):
    """El dataset de HCDN es JSON (una lista de objetos). Fallback a CSV por las dudas."""
    import json
    txt = texto.strip()
    if txt[:1] in ("[", "{"):
        data = json.loads(txt)
        if isinstance(data, dict):
            # a veces viene {"data":[...]} o similar
            for v in data.values():
                if isinstance(v, list):
                    return v
            return [data]
        return data
    # fallback CSV
    return list(csv.DictReader(io.StringIO(texto)))


def buscar_col(headers, *candidatos):
    """Encuentra una columna por nombre aproximado (case-insensitive, sin tildes)."""
    def norm(s):
        return re.sub(r"[^a-z0-9]", "", (s or "").lower())
    hn = {norm(h): h for h in headers}
    for c in candidatos:
        if norm(c) in hn:
            return hn[norm(c)]
    # búsqueda parcial
    for c in candidatos:
        for k, orig in hn.items():
            if norm(c) in k:
                return orig
    return None


def modo_test():
    print("Bajando dataset de leyes sancionadas...", file=sys.stderr)
    try:
        txt = descargar(CSV_URL)
    except Exception as e:
        print("ERROR al bajar el CSV: %s" % e, file=sys.stderr)
        print("Verificá la URL en https://datos.hcdn.gob.ar/dataset/leyes-sancionadas", file=sys.stderr)
        return
    filas = leer_filas(txt)
    if not filas:
        print("El CSV vino vacío o no se pudo parsear.", file=sys.stderr)
        return
    headers = list(filas[0].keys())
    print("\n=== COLUMNAS del dataset (%d filas) ===" % len(filas), file=sys.stderr)
    for h in headers:
        print("  - %s" % h, file=sys.stderr)

    col_pid = buscar_col(headers, "PROYECTO_ID", "proyecto id", "id proyecto", "expediente")
    print("\nColumna que parece el identificador de proyecto: %s" % (col_pid or "NO ENCONTRADA"), file=sys.stderr)

    print("\n=== PRIMERAS 3 FILAS (muestra) ===", file=sys.stderr)
    for f in filas[:3]:
        print("  " + " | ".join("%s=%s" % (k, str(v)[:40]) for k, v in f.items()), file=sys.stderr)

    if col_pid:
        ids = set(str(f.get(col_pid, "")).strip() for f in filas if f.get(col_pid))
        print("\nIDs de proyecto sancionados en el dataset: %d" % len(ids), file=sys.stderr)
        print("Ejemplos:", list(ids)[:5], file=sys.stderr)
        print("\n>>> Si estos IDs se parecen a los bill_id del feed (HCDN..., SENADO...),", file=sys.stderr)
        print(">>> el cruce va a ser directo. Pegame esta salida y ajustamos.", file=sys.stderr)
    else:
        print("\n>>> No identifiqué la columna de ID. Pegame la lista de columnas y", file=sys.stderr)
        print(">>> las filas de muestra, y ajusto el cruce.", file=sys.stderr)


def traer_feed_bills():
    """bill_id de las leyes publicadas en el feed."""
    headers = {"apikey": SERVICE_KEY, "Authorization": "Bearer " + SERVICE_KEY}
    bills = {}
    offset = 0
    while True:
        url = (SUPABASE_URL + "/rest/v1/leyes?select=bill_id,titulo,publicada"
               "&limit=1000&offset=" + str(offset))
        r = requests.get(url, headers=headers, timeout=30)
        r.raise_for_status()
        parte = r.json()
        for x in parte:
            bills[x["bill_id"]] = x
        if len(parte) < 1000:
            break
        offset += 1000
    return bills


def aplicar(dry):
    if not SERVICE_KEY:
        print('Falta la clave:  $env:SUPABASE_SERVICE_KEY="..." (service_role)', file=sys.stderr)
        sys.exit(1)

    print("Bajando leyes sancionadas...", file=sys.stderr)
    txt = descargar(CSV_URL)
    filas = leer_filas(txt)
    headers = list(filas[0].keys()) if filas else []
    col_pid = buscar_col(headers, "PROYECTO_ID", "proyecto id", "id proyecto", "expediente")
    if not col_pid:
        print("No pude identificar la columna de ID. Corré primero --test.", file=sys.stderr)
        sys.exit(1)
    sancionados = set(str(f.get(col_pid, "")).strip() for f in filas if f.get(col_pid))
    print("Proyectos sancionados en el dataset: %d" % len(sancionados), file=sys.stderr)

    feed = traer_feed_bills()
    print("Leyes en la tabla: %d" % len(feed), file=sys.stderr)

    # Las del feed que ya están sancionadas Y todavía publicadas
    a_despublicar = [bid for bid, x in feed.items()
                     if bid in sancionados and x.get("publicada")]
    print("\n=== RESULTADO ===", file=sys.stderr)
    print("Leyes del feed ya sancionadas (a sacar): %d" % len(a_despublicar), file=sys.stderr)
    for bid in a_despublicar[:20]:
        t = (feed[bid].get("titulo") or "")[:60]
        print("  - %s  %s" % (bid, t), file=sys.stderr)
    if len(a_despublicar) > 20:
        print("  ... y %d más" % (len(a_despublicar) - 20), file=sys.stderr)

    if dry:
        print("\n(DRY-RUN: no se escribió nada.)", file=sys.stderr)
        return

    headers_w = {"apikey": SERVICE_KEY, "Authorization": "Bearer " + SERVICE_KEY,
                 "Content-Type": "application/json"}
    cambios = [{"bill_id": bid, "publicada": False, "estado_tramite": "sancionada"}
               for bid in a_despublicar]
    for i in range(0, len(cambios), LOTE):
        lote = cambios[i:i + LOTE]
        url = SUPABASE_URL + "/rest/v1/leyes?on_conflict=bill_id"
        headers_w["Prefer"] = "resolution=merge-duplicates"
        r = requests.post(url, headers=headers_w, data=__import__("json").dumps(lote), timeout=30)
        if r.status_code >= 300:
            print("ERROR lote %d: %s %s" % (i // LOTE, r.status_code, r.text[:200]), file=sys.stderr)
            r.raise_for_status()
        time.sleep(0.3)
    print("\nDespublicadas: %d leyes ya sancionadas salieron del feed." % len(cambios), file=sys.stderr)


def main():
    if "--test" in sys.argv:
        modo_test()
    elif "--dry-run" in sys.argv:
        aplicar(dry=True)
    else:
        aplicar(dry=False)


if __name__ == "__main__":
    main()
