#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pnyx · Obrero 1 — Consultar Supabase (fuente de verdad)
--------------------------------------------------------
Baja de Supabase el estado de cada ley SIN traer el texto completo
(usa la vista 'estado_leyes' que calcula tiene_texto en el servidor).
Guarda 'estado_nube.json' que los obreros siguientes usan para saber
que saltear.

Por cada bill_id:
  - huella: detecta cambios para el obrero de subida
  - tiene_texto: el obrero de texto saltea si ya tiene
  - tiene_resumen: el obrero de resumen saltea si ya tiene

Requiere la vista 'estado_leyes' creada en Supabase (ver SQL adjunto).
Gratis. Uso: python 1_consultar_supabase.py
"""

import json
import os
import sys

try:
    from supabase import create_client
except ImportError:
    print("Falta supabase. Instalalo con:  pip install supabase", file=sys.stderr)
    sys.exit(1)

SUPABASE_URL = "https://ihmbhbhwlntsjqdavxge.supabase.co"
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
SALIDA = "estado_nube.json"


def main():
    if not SUPABASE_KEY:
        print("Falta la clave:  $env:SUPABASE_SERVICE_KEY=\"tu-service-role-key\"", file=sys.stderr)
        sys.exit(1)

    sb = create_client(SUPABASE_URL, SUPABASE_KEY)
    print("Consultando Supabase (vista liviana, sin bajar textos)...", file=sys.stderr)

    estado = {}
    offset = 0
    while True:
        # La vista estado_leyes devuelve tiene_texto como booleano,
        # calculado en el servidor: NO baja el texto completo.
        res = sb.table("estado_leyes") \
            .select("bill_id,puntaje_pnyx,oracion_ia,media_sancion,tiene_texto") \
            .range(offset, offset + 999) \
            .execute()
        for r in res.data:
            bid = r["bill_id"]
            estado[bid] = {
                "huella": "%s|%s|%s" % (r.get("puntaje_pnyx"), r.get("oracion_ia"), r.get("media_sancion")),
                "tiene_texto": bool(r.get("tiene_texto")),
                "tiene_resumen": bool(r.get("oracion_ia")),
            }
        if len(res.data) < 1000:
            break
        offset += 1000

    with open(SALIDA, "w", encoding="utf-8") as f:
        json.dump(estado, f, ensure_ascii=False, indent=2)

    con_texto = sum(1 for e in estado.values() if e["tiene_texto"])
    con_resumen = sum(1 for e in estado.values() if e["tiene_resumen"])
    print("En Supabase: %d leyes (%d con texto, %d con resumen)"
          % (len(estado), con_texto, con_resumen), file=sys.stderr)
    print("Guardado en %s" % SALIDA, file=sys.stderr)


if __name__ == "__main__":
    main()
