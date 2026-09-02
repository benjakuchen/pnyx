#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pnyx · Obrero 9 — Mezclar, puntuar y ordenar (sobre Supabase)
--------------------------------------------------------------
Recalcula el puntaje_pnyx de TODAS las leyes segun sus marcas, y detecta
media sancion. Trabaja 100% sobre Supabase: trae los campos necesarios,
calcula, y sube los puntajes que cambiaron.

Marcas y pesos:
  - Media sancion (origen != camara) ... +150
  - En prensa (importante_prensa) ...... +100
  - Novedad por fecha:
        <=30 dias ... +40
        <=90 dias ... +25
        mas viejo ... +10

No usa IA (gratis). Sube solo los puntajes/media_sancion que cambiaron.
Uso: python 9_mezclar_ordenar.py
"""

import os
import sys
import time
from datetime import datetime, date

try:
    from supabase import create_client
except ImportError:
    print("Falta supabase: pip install supabase", file=sys.stderr)
    sys.exit(1)

SUPABASE_URL = "https://ihmbhbhwlntsjqdavxge.supabase.co"
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")

PESO_MEDIA_SANCION = 150
PESO_PRENSA = 100
PESO_NOVEDAD = {"reciente": 40, "media": 25, "vieja": 10}
LOTE = 50


def dias_desde(fecha_str, hoy):
    try:
        f = datetime.strptime(str(fecha_str)[:10], "%Y-%m-%d").date()
        return (hoy - f).days
    except Exception:
        return 99999


def tiene_media_sancion(camara, origen):
    if camara == "Senado" and origen in ("Diputados", "CD"):
        return True
    if camara == "Diputados" and origen in ("Senado", "S"):
        return True
    return False


def calcular(ley, hoy):
    camara = ley.get("camara", "")
    origen = ley.get("origen", "")
    ms = tiene_media_sancion(camara, origen)
    puntaje = 0
    if ms:
        puntaje += PESO_MEDIA_SANCION
    if ley.get("importante_prensa"):
        puntaje += PESO_PRENSA
    d = dias_desde(ley.get("fecha", ""), hoy)
    if d <= 30:
        puntaje += PESO_NOVEDAD["reciente"]
    elif d <= 90:
        puntaje += PESO_NOVEDAD["media"]
    else:
        puntaje += PESO_NOVEDAD["vieja"]
    return puntaje, ms


def main():
    if not SUPABASE_KEY:
        print("Falta: $env:SUPABASE_SERVICE_KEY=\"...\"", file=sys.stderr)
        sys.exit(1)

    sb = create_client(SUPABASE_URL, SUPABASE_KEY)
    hoy = date.today()

    print("Trayendo leyes de Supabase...", file=sys.stderr)
    leyes = []
    offset = 0
    while True:
        res = sb.table("leyes") \
            .select("bill_id,camara,origen,fecha,importante_prensa,puntaje_pnyx,media_sancion") \
            .range(offset, offset + 999).execute()
        leyes.extend(res.data)
        if len(res.data) < 1000:
            break
        offset += 1000
    print("Leyes: %d" % len(leyes), file=sys.stderr)

    cambios = []
    ms_total = 0
    for ley in leyes:
        nuevo_puntaje, ms = calcular(ley, hoy)
        if ms:
            ms_total += 1
        if (nuevo_puntaje != ley.get("puntaje_pnyx")) or (ms != bool(ley.get("media_sancion"))):
            cambios.append({
                "bill_id": ley["bill_id"],
                "puntaje_pnyx": nuevo_puntaje,
                "media_sancion": ms,
            })

    if cambios:
        for i in range(0, len(cambios), LOTE):
            sb.table("leyes").upsert(cambios[i:i+LOTE], on_conflict="bill_id").execute()
            time.sleep(0.3)

    print("\n=== RESULTADO ===", file=sys.stderr)
    print("Total leyes: %d" % len(leyes), file=sys.stderr)
    print("Con media sancion: %d" % ms_total, file=sys.stderr)
    print("Puntajes actualizados en Supabase: %d" % len(cambios), file=sys.stderr)
    print("(El feed de la app ya queda ordenado por puntaje_pnyx.desc)", file=sys.stderr)


if __name__ == "__main__":
    main()
