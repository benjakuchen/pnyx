#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Pnyx - (c) 2026 Benjamin Kuchen. Obra protegida por la Ley 11.723 (Argentina).
"""
Muestra bill_id del Senado que NO tienen el formato normal 'SENADO<num>-<anio>'.
Sirve para encontrar filas creadas por error (nombres de PDF mal puestos).
Uso:  python senado_ver_raros.py
"""
import os, re, sys
try:
    from supabase import create_client
except ImportError:
    print("Falta supabase:  pip install supabase", file=sys.stderr); sys.exit(1)

SUPABASE_URL = "https://ihmbhbhwlntsjqdavxge.supabase.co"
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
OK = re.compile(r"^SENADO\d+-\d{2}$")

def main():
    if not SUPABASE_KEY:
        print('Falta $env:SUPABASE_SERVICE_KEY', file=sys.stderr); sys.exit(1)
    sb = create_client(SUPABASE_URL, SUPABASE_KEY)
    filas, desde = [], 0
    while True:
        r = sb.table("leyes").select("bill_id,camara,titulo").eq("camara","Senado") \
            .range(desde, desde+999).execute()
        d = r.data or []; filas += d
        if len(d) < 1000: break
        desde += 1000
    raros = [f for f in filas if not OK.match(f.get("bill_id") or "")]
    print("Total Senado: %d | con formato raro: %d\n" % (len(filas), len(raros)))
    for f in raros:
        print("  %-16s %s" % (f.get("bill_id"), (f.get("titulo") or "")[:55]))
    if not raros:
        print("(No hay bill_id raros. Puede que las 5 filas no se hayan creado,")
        print(" o que el texto haya ido a las leyes correctas. Verificá con senado_ultimos.py)")

if __name__ == "__main__":
    main()
