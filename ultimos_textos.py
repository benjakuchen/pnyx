#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Pnyx - (c) 2026 Benjamin Kuchen. Obra protegida por la Ley 11.723 (Argentina).
# Distribuido bajo la Licencia Publica General Affero de GNU v3 (AGPL-3.0). Ver LICENSE.
"""
Pnyx · Chequeo — ultimos textos completos bajados
-------------------------------------------------
Muestra las leyes con texto_oficial cargado, ordenadas por fecha de carga
(created_at), separando por camara. Sirve para ver si la maquina de todos
los dias (Diputados) sigue trayendo textos y cuando fue el ultimo del Senado.

Ademas cuenta, por dia de carga, cuantos textos entraron (ambas camaras).

Requisitos:  pip install supabase  +  $env:SUPABASE_SERVICE_KEY
Uso:
  python ultimos_textos.py          -> ultimos 30 textos (ambas camaras)
  python ultimos_textos.py 60       -> ultimos 60
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
CANT = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 30


def main():
    if not SUPABASE_KEY:
        print('Falta la clave:  $env:SUPABASE_SERVICE_KEY="..."', file=sys.stderr)
        sys.exit(1)
    sb = create_client(SUPABASE_URL, SUPABASE_KEY)

    # Solo leyes con texto. Ordenadas por carga, mas nuevas primero.
    # PostgREST: filtro texto_oficial not null. Traemos un lote para contar por dia.
    try:
        res = sb.table("leyes") \
            .select("bill_id,camara,titulo,oracion_ia,created_at") \
            .not_.is_("texto_oficial", "null") \
            .order("created_at", desc=True).limit(2000).execute()
        filas = res.data or []
        tiene_created = True
    except Exception as e:
        print("No pude ordenar por created_at (%s). ¿Existe la columna?" % e, file=sys.stderr)
        return

    if not filas:
        print("No hay leyes con texto en la base.", file=sys.stderr)
        return

    # Conteo por dia de carga (ambas camaras)
    porDia = Counter((f.get("created_at") or "?")[:10] for f in filas)
    print("\n=== Textos por DIA de carga (ultimos dias, ambas camaras) ===")
    for dia, n in sorted(porDia.items(), reverse=True)[:15]:
        print("  %-12s %4d textos" % (dia, n))

    # Ultimo texto por camara
    print("\n=== Ultimo texto cargado por camara ===")
    for cam in ("Diputados", "Senado"):
        fc = next((f for f in filas if f.get("camara") == cam), None)
        if fc:
            print("  %-10s ultimo: %s  (%s)" % (cam, (fc.get("created_at") or "?")[:10],
                  (fc.get("oracion_ia") or fc.get("titulo") or fc.get("bill_id") or "")[:50]))
        else:
            print("  %-10s sin textos en el lote." % cam)

    # Listado de los ultimos N
    print("\n=== Ultimos %d textos cargados (ambas camaras) ===" % CANT)
    print("  %-12s %-10s %s" % ("carga", "camara", "titulo"))
    print("  " + "-" * 74)
    for f in filas[:CANT]:
        print("  %-12s %-10s %s" % ((f.get("created_at") or "?")[:10],
              f.get("camara") or "?",
              (f.get("oracion_ia") or f.get("titulo") or f.get("bill_id") or "")[:52]))


if __name__ == "__main__":
    main()
