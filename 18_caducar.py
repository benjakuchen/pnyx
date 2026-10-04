#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Pnyx - (c) 2026 Benjamin Kuchen. Obra protegida por la Ley 11.723 (Argentina).
# Distribuido bajo la Licencia Publica General Affero de GNU v3 (AGPL-3.0). Ver LICENSE.
"""
Pnyx · Obrero 18 — Caducar proyectos viejos de la cola de curaduria
-------------------------------------------------------------------
Llama a la RPC archivar_caducadas(dias): marca como 'caducada' todo
proyecto que lleva mas de N dias en la cola sin publicarse, sin media
sancion y sin prensa. No borra nada: quedan en "Revisar caducadas" del
admin y se pueden rescatar.

Corre despues de 14_curaduria.py (que llena la cola), asi cada dia la
cola se limpia sola y nunca vuelve a amontonarse.

MODOS:
  python 18_caducar.py            archiva con el default (60 dias)
  python 18_caducar.py 90         archiva las de mas de 90 dias

Requisitos: pip install requests
"""

import os
import sys
import requests

SUPABASE_URL = "https://ihmbhbhwlntsjqdavxge.supabase.co"
SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")

DIAS = 60
if len(sys.argv) > 1:
    try:
        DIAS = int(sys.argv[1])
    except ValueError:
        print("El argumento debe ser un numero de dias. Uso: python 18_caducar.py [dias]", file=sys.stderr)
        sys.exit(1)


def main():
    if not SERVICE_KEY:
        print("Falta SUPABASE_SERVICE_KEY en el entorno.", file=sys.stderr)
        sys.exit(1)

    url = SUPABASE_URL + "/rest/v1/rpc/archivar_caducadas"
    headers = {
        "apikey": SERVICE_KEY,
        "Authorization": "Bearer " + SERVICE_KEY,
        "Content-Type": "application/json",
    }
    try:
        r = requests.post(url, headers=headers, json={"p_dias": DIAS}, timeout=60)
        r.raise_for_status()
    except Exception as e:
        print("  ! No se pudo caducar: %s" % e, file=sys.stderr)
        sys.exit(1)

    n = r.json()
    print("  Caducadas (archivadas): %s  (mas de %d dias en la cola)" % (n, DIAS), file=sys.stderr)


if __name__ == "__main__":
    main()
