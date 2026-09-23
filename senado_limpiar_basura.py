#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Pnyx - (c) 2026 Benjamin Kuchen. Obra protegida por la Ley 11.723 (Argentina).
# Distribuido bajo la Licencia Publica General Affero de GNU v3 (AGPL-3.0). Ver LICENSE.
"""
Pnyx · Limpiar filas basura del Senado
--------------------------------------
Borra de la tabla 'leyes' las filas que se crearon por error con bill_id en
formato viejo del sitio (ej 'S637_26PL') en vez del formato Pnyx
('SENADO637-26'). Detecta el patron  S<numero>_<anio>PL.

SEGURO: solo toca filas con ese patron exacto. Corre primero --dry-run.

Requisitos:  pip install supabase  +  $env:SUPABASE_SERVICE_KEY
Uso:
  python senado_limpiar_basura.py --dry-run   -> muestra que borraria
  python senado_limpiar_basura.py             -> borra
"""

import os
import re
import sys

try:
    from supabase import create_client
except ImportError:
    print("Falta supabase:  pip install supabase", file=sys.stderr)
    sys.exit(1)

SUPABASE_URL = "https://ihmbhbhwlntsjqdavxge.supabase.co"
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
DRY = "--dry-run" in sys.argv

# patron del bill_id basura: S + numero + _ + 2 digitos + PL  (ej S637_26PL)
PATRON = re.compile(r"^S\d+_\d{2}PL$")


def main():
    if not SUPABASE_KEY:
        print('Falta la clave:  $env:SUPABASE_SERVICE_KEY="..."', file=sys.stderr)
        sys.exit(1)
    sb = create_client(SUPABASE_URL, SUPABASE_KEY)

    # Traigo todo el Senado y filtro por patron (mas seguro que un like en el server)
    filas, desde = [], 0
    while True:
        r = sb.table("leyes").select("bill_id,camara").eq("camara", "Senado") \
            .range(desde, desde + 999).execute()
        d = r.data or []
        filas += d
        if len(d) < 1000:
            break
        desde += 1000

    basura = [f["bill_id"] for f in filas if PATRON.match(f.get("bill_id") or "")]
    print("Filas basura detectadas (formato viejo S..._..PL): %d" % len(basura), file=sys.stderr)
    for b in basura:
        print("  - %s" % b, file=sys.stderr)

    if not basura:
        print("Nada para borrar.", file=sys.stderr)
        return
    if DRY:
        print("\n(DRY-RUN: no se borro nada.)", file=sys.stderr)
        return

    borradas = 0
    for b in basura:
        try:
            sb.table("leyes").delete().eq("bill_id", b).execute()
            borradas += 1
        except Exception as e:
            print("  ! fallo al borrar %s: %s" % (b, e), file=sys.stderr)
    print("\nBorradas: %d" % borradas, file=sys.stderr)


if __name__ == "__main__":
    main()
