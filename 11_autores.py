#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pnyx · Obrero 11 — Subir autores a Supabase (backfill re-ejecutable)
---------------------------------------------------------------------
Lee los JSON locales (proyectos_diputados.json y proyectos_senado.json),
que ya traen el autor, y completa la columna 'autor' de la tabla leyes.

- Solo actualiza leyes que YA EXISTEN en Supabase (no crea filas nuevas).
- Solo sube donde el autor cambio o falta (idempotente: correrlo dos
  veces no hace nada la segunda).

Requiere haber corrido antes:
  ALTER TABLE leyes ADD COLUMN IF NOT EXISTS autor text;

Gratis (no usa IA). Uso: python 11_autores.py
"""

import json
import os
import sys
import time

try:
    from supabase import create_client
except ImportError:
    print("Falta supabase: pip install supabase", file=sys.stderr)
    sys.exit(1)

SUPABASE_URL = "https://ihmbhbhwlntsjqdavxge.supabase.co"
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")

ARCHIVOS = ["proyectos_diputados.json", "proyectos_senado.json"]
LOTE = 50


def main():
    if not SUPABASE_KEY:
        print('Falta la clave:  $env:SUPABASE_SERVICE_KEY="..."', file=sys.stderr)
        sys.exit(1)

    # 1) Autores segun los JSON locales
    autores = {}
    for archivo in ARCHIVOS:
        if not os.path.exists(archivo):
            print("Aviso: no encontre %s (salteo)" % archivo, file=sys.stderr)
            continue
        with open(archivo, encoding="utf-8") as f:
            for p in json.load(f):
                a = (p.get("autor") or "").strip()
                if p.get("bill_id") and a:
                    autores[p["bill_id"]] = a
    print("Autores en los JSON locales: %d" % len(autores), file=sys.stderr)
    if not autores:
        print("Nada para subir.", file=sys.stderr)
        return

    # 2) Que hay hoy en Supabase (solo bill_id + autor, liviano)
    sb = create_client(SUPABASE_URL, SUPABASE_KEY)
    nube = {}
    offset = 0
    while True:
        res = sb.table("leyes").select("bill_id,autor").range(offset, offset + 999).execute()
        for r in res.data:
            nube[r["bill_id"]] = r.get("autor")
        if len(res.data) < 1000:
            break
        offset += 1000
    print("Leyes en Supabase: %d" % len(nube), file=sys.stderr)

    # 3) Cambios: existe en la nube Y el autor difiere
    cambios = [{"bill_id": bid, "autor": a}
               for bid, a in autores.items()
               if bid in nube and nube[bid] != a]

    sin_nube = sum(1 for bid in autores if bid not in nube)
    print("A actualizar: %d | Ya al dia: %d | En JSON pero no en Supabase: %d"
          % (len(cambios), len(autores) - len(cambios) - sin_nube, sin_nube), file=sys.stderr)

    # 4) Subir en lotes (upsert seguro: todos los bill_id existen)
    for i in range(0, len(cambios), LOTE):
        sb.table("leyes").upsert(cambios[i:i + LOTE], on_conflict="bill_id").execute()
        time.sleep(0.3)

    print("\n=== LISTO ===", file=sys.stderr)
    print("Autores subidos a Supabase: %d" % len(cambios), file=sys.stderr)


if __name__ == "__main__":
    main()
