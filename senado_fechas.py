#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Pnyx - (c) 2026 Benjamin Kuchen. Obra protegida por la Ley 11.723 (Argentina).
# Distribuido bajo la Licencia Publica General Affero de GNU v3 (AGPL-3.0). Ver LICENSE.
"""
Pnyx · Chequeo — fechas de las leyes del Senado
-----------------------------------------------
Trae TODAS las leyes del Senado y cuenta cuantas hay por 'fecha' (fecha del
proyecto) y, si existe, por dia de 'created_at' (carga en la base). Sirve
para ver si realmente esta todo pegado en una sola fecha o hay variedad.

Requisitos:  pip install supabase  +  $env:SUPABASE_SERVICE_KEY
Uso:  python senado_fechas.py
"""

import os
import sys
from collections import Counter

try:
    from supabase import create_client
except ImportError:
    print("Falta supabase:  pip install supabase", file=sys.stderr)
    sys.exit(1)

SUPABASE_URL = "https://ihmbhbhwlntsjqdavxge.supabase.co"
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")


def traer_todo(sb, campos):
    filas, desde = [], 0
    while True:
        r = sb.table("leyes").select(campos).eq("camara", "Senado") \
            .range(desde, desde + 999).execute()
        d = r.data or []
        filas += d
        if len(d) < 1000:
            break
        desde += 1000
    return filas


def main():
    if not SUPABASE_KEY:
        print('Falta la clave:  $env:SUPABASE_SERVICE_KEY="..."', file=sys.stderr)
        sys.exit(1)
    sb = create_client(SUPABASE_URL, SUPABASE_KEY)

    tiene_created = True
    try:
        filas = traer_todo(sb, "bill_id,fecha,created_at")
    except Exception:
        tiene_created = False
        filas = traer_todo(sb, "bill_id,fecha")

    print("\nTotal leyes del Senado en la base: %d\n" % len(filas))

    # Por fecha de PROYECTO
    cf = Counter((f.get("fecha") or "sin fecha")[:10] for f in filas)
    print("=== Por FECHA de proyecto (columna 'fecha') ===")
    for fch, n in sorted(cf.items(), reverse=True):
        print("  %-12s %4d" % (fch, n))

    # Por dia de CARGA
    if tiene_created:
        cc = Counter((f.get("created_at") or "sin created_at")[:10] for f in filas)
        print("\n=== Por DIA de carga en la base (created_at) ===")
        for fch, n in sorted(cc.items(), reverse=True):
            print("  %-12s %4d" % (fch, n))
    else:
        print("\n(La tabla no tiene columna created_at: no puedo ver dias de carga.)")


if __name__ == "__main__":
    main()
