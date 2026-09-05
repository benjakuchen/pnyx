#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pnyx · Obrero 12 — Bancas que escuchan
--------------------------------------
Llena la tabla `bancas` (una fila por legislador nacional actual) combinando:
  - LISTA y CAMARA: tu tabla `legisladores` (los actuales, de las votaciones).
  - PRESENTISMO: el JSON publico de comovoto (campo `pres`), cruzado por nombre.

- No pisa las decisiones del admin: si una banca ya existe, actualiza solo
  nombre/provincia/bloque/presentismo/foto, y DEJA INTACTOS `validada` y `escucha`.
- Re-ejecutable. Requiere la tabla `bancas` (correr antes sql_bancas.sql).

Requisitos:  pip install supabase requests
Uso:
  python 12_bancas.py            carga/actualiza las bancas
  python 12_bancas.py --dry-run  muestra que haria, sin escribir
"""

import json
import os
import re
import sys
import time
import unicodedata

import requests

SUPABASE_URL = "https://ihmbhbhwlntsjqdavxge.supabase.co"
SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
COMOVOTO_URL = "https://raw.githubusercontent.com/rquiroga7/Como_voto/main/docs/data/legislators.json"
LOTE = 50


def norm_nombre(n):
    n = unicodedata.normalize("NFKD", n or "").encode("ascii", "ignore").decode().upper()
    return re.sub(r"\s+", " ", n).strip()


def cargar_presentismo():
    """Baja el JSON de comovoto y arma: nombre_norm -> (pres, foto).
    Toma solo legisladores con actividad hasta 2026 (actuales)."""
    print("Bajando presentismo de comovoto...", file=sys.stderr)
    r = requests.get(COMOVOTO_URL, timeout=60)
    r.raise_for_status()
    data = r.json()
    idx = {}
    for x in data:
        by_co = x.get("by_co") or {}
        activo = any((v.get("yt") == 2026) for v in by_co.values())
        if not activo:
            continue
        clave = norm_nombre(x.get("k") or x.get("n"))
        idx[clave] = {"pres": x.get("pres"), "foto": x.get("ph") or None}
    print("  Legisladores actuales en comovoto: %d" % len(idx), file=sys.stderr)
    return idx


def traer_legisladores():
    """Trae tu tabla legisladores (lista + camara actual correcta)."""
    print("Trayendo tu tabla legisladores...", file=sys.stderr)
    filas = []
    offset = 0
    headers = {"apikey": SERVICE_KEY, "Authorization": "Bearer " + SERVICE_KEY}
    while True:
        url = (SUPABASE_URL + "/rest/v1/legisladores"
               "?select=nombre,nombre_normalizado,camara,bloque,provincia"
               "&limit=1000&offset=" + str(offset))
        r = requests.get(url, headers=headers, timeout=30)
        r.raise_for_status()
        parte = r.json()
        filas.extend(parte)
        if len(parte) < 1000:
            break
        offset += 1000
    print("  Legisladores en tu tabla: %d" % len(filas), file=sys.stderr)
    return filas


def camara_norm(c):
    c = (c or "").lower()
    if "dipu" in c:
        return "diputados"
    if "sena" in c:
        return "senadores"
    return c


def main():
    dry = "--dry-run" in sys.argv
    if not SERVICE_KEY:
        print('Falta la clave:  $env:SUPABASE_SERVICE_KEY="..." (service_role)', file=sys.stderr)
        sys.exit(1)

    pres_idx = cargar_presentismo()
    legis = traer_legisladores()

    # Armar las filas de bancas
    filas = []
    con_pres = 0
    sin_pres = []
    for lg in legis:
        nn = lg.get("nombre_normalizado") or norm_nombre(lg.get("nombre"))
        cam = camara_norm(lg.get("camara"))
        match = pres_idx.get(nn)
        if match and match.get("pres") is not None:
            con_pres += 1
        else:
            sin_pres.append(lg.get("nombre"))
        filas.append({
            "nombre": lg.get("nombre"),
            "nombre_norm": nn,
            "camara": cam,
            "provincia": lg.get("provincia"),
            "bloque": lg.get("bloque"),
            "presentismo": (match.get("pres") if match else None),
            "foto": (match.get("foto") if match else None),
        })

    dip = sum(1 for f in filas if f["camara"] == "diputados")
    sen = sum(1 for f in filas if f["camara"] == "senadores")
    print("\n=== A CARGAR ===", file=sys.stderr)
    print("Total bancas: %d  (diputados %d, senadores %d)" % (len(filas), dip, sen), file=sys.stderr)
    print("Con presentismo cruzado: %d  |  sin cruzar: %d" % (con_pres, len(sin_pres)), file=sys.stderr)
    if sin_pres:
        print("  Sin presentismo (primeros 10): %s" % ", ".join(sin_pres[:10]), file=sys.stderr)

    if dry:
        print("\n(DRY-RUN: no se escribio nada.)", file=sys.stderr)
        return

    # Subir en lotes. upsert por (nombre_norm,camara): actualiza datos, respeta validada/escucha.
    headers = {"apikey": SERVICE_KEY, "Authorization": "Bearer " + SERVICE_KEY,
               "Content-Type": "application/json",
               "Prefer": "resolution=merge-duplicates"}
    subidas = 0
    for i in range(0, len(filas), LOTE):
        lote = filas[i:i + LOTE]
        url = SUPABASE_URL + "/rest/v1/bancas?on_conflict=nombre_norm,camara"
        r = requests.post(url, headers=headers, data=json.dumps(lote), timeout=30)
        if r.status_code >= 300:
            print("ERROR al subir lote %d: %s %s" % (i // LOTE, r.status_code, r.text[:300]), file=sys.stderr)
            r.raise_for_status()
        subidas += len(lote)
        time.sleep(0.3)

    print("\n=== LISTO ===", file=sys.stderr)
    print("Bancas cargadas/actualizadas: %d" % subidas, file=sys.stderr)
    print("(validada y escucha NO se tocan: son decisiones del admin.)", file=sys.stderr)


if __name__ == "__main__":
    main()
