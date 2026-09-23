#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Pnyx - (c) 2026 Benjamin Kuchen. Obra protegida por la Ley 11.723 (Argentina).
# Distribuido bajo la Licencia Publica General Affero de GNU v3 (AGPL-3.0). Ver LICENSE.
"""
Pnyx · Chequeo — ultimas leyes del Senado
-----------------------------------------
Lista las leyes de camara = Senado mas recientes, para ver de un vistazo si
bajo algo nuevo. Muestra: fecha, bill_id, si tiene texto y si tiene resumen.

Si la tabla 'leyes' tiene columna 'created_at' (fecha de carga en la base),
tambien marca [NUEVO] las que se cargaron en las ultimas 48 horas.

Requisitos:  pip install supabase   +   $env:SUPABASE_SERVICE_KEY
Uso:
  python senado_ultimos.py           -> ultimas 25 del Senado
  python senado_ultimos.py 50        -> ultimas 50
  python senado_ultimos.py 25 3      -> ultimas 25 y marca NUEVO las de <=3 dias
"""

import os
import sys
from datetime import datetime, timedelta, timezone

try:
    from supabase import create_client
except ImportError:
    print("Falta supabase:  pip install supabase", file=sys.stderr)
    sys.exit(1)

SUPABASE_URL = "https://ihmbhbhwlntsjqdavxge.supabase.co"
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")

# argumentos: [cantidad] [dias_para_NUEVO]
CANT = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 25
DIAS_NUEVO = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2].isdigit() else 2


def parse_fecha(s):
    if not s:
        return None
    s = str(s).replace("Z", "+00:00")
    try:
        d = datetime.fromisoformat(s)
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return d
    except Exception:
        return None


def main():
    if not SUPABASE_KEY:
        print('Falta la clave:  $env:SUPABASE_SERVICE_KEY="..." (service_role)', file=sys.stderr)
        sys.exit(1)
    sb = create_client(SUPABASE_URL, SUPABASE_KEY)

    # Intento traer created_at (fecha de carga). Si la columna no existe, reintento sin ella.
    campos = "bill_id,titulo,oracion_ia,fecha,texto_oficial,created_at"
    tiene_created = True
    try:
        res = sb.table("leyes").select(campos).eq("camara", "Senado") \
            .order("created_at", desc=True).limit(CANT).execute()
        filas = res.data or []
    except Exception:
        tiene_created = False
        res = sb.table("leyes").select("bill_id,titulo,oracion_ia,fecha,texto_oficial") \
            .eq("camara", "Senado").order("fecha", desc=True).limit(CANT).execute()
        filas = res.data or []

    if not filas:
        print("No hay leyes del Senado en la base.", file=sys.stderr)
        return

    corte = datetime.now(timezone.utc) - timedelta(days=DIAS_NUEVO)
    nuevas = 0

    orden = "carga en la base (created_at)" if tiene_created else "fecha del proyecto"
    print("\nUltimas %d leyes del Senado — ordenadas por %s\n" % (len(filas), orden))
    print("  %-3s %-12s %-4s %-4s  %s" % ("", "fecha", "txt", "res", "titulo"))
    print("  " + "-" * 78)

    for f in filas:
        fref = parse_fecha(f.get("created_at")) if tiene_created else parse_fecha(f.get("fecha"))
        es_nuevo = bool(fref and fref >= corte)
        if es_nuevo:
            nuevas += 1
        marca = "NEW" if es_nuevo else ""
        fecha_txt = (f.get("created_at") or f.get("fecha") or "")[:10]
        txt = "si" if (f.get("texto_oficial") and len(str(f.get("texto_oficial"))) > 200) else "-"
        res = "si" if f.get("oracion_ia") else "-"
        titulo = (f.get("oracion_ia") or f.get("titulo") or f.get("bill_id") or "")[:60]
        print("  %-3s %-12s %-4s %-4s  %s" % (marca, fecha_txt, txt, res, titulo))

    print()
    if tiene_created:
        print("=> %d ley(es) del Senado cargadas en la base en los ultimos %d dias."
              % (nuevas, DIAS_NUEVO))
    else:
        print("(La tabla 'leyes' no tiene columna created_at: no puedo saber la fecha de CARGA.")
        print(" Arriba estan las de FECHA de proyecto mas reciente. Si no reconoces ninguna")
        print(" como nueva, probablemente no bajo nada del Senado.)")


if __name__ == "__main__":
    main()
