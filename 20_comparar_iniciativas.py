#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Pnyx - (c) 2026 Benjamin Kuchen. Obra protegida por la Ley 11.723 (Argentina).
# Distribuido bajo la Licencia Publica General Affero de GNU v3 (AGPL-3.0). Ver LICENSE.
"""
Pnyx · Obrero 20 — Detectar iniciativas EQUIVALENTES (version barata, sin IA)
---------------------------------------------------------------------------
Dos pasos, los dos en Supabase (no gasta API de IA):
  1) fichas_recalcular_todas()  -> arma una ficha de texto por cada iniciativa viva.
  2) equivalencias_detectar(u)  -> compara por area + similitud de texto (pg_trgm)
     y guarda los pares parecidos en iniciativa_equivalencias.

Despues, en la app de administracion, se ven los pares detectados y se decide
si avisar a los autores (equivalencia_marcar).

MODOS:
  python 20_comparar_iniciativas.py           umbral por defecto (0.25)
  python 20_comparar_iniciativas.py 0.35      umbral mas exigente (menos pares)

Umbral: 0..1. Mas alto = solo pares muy parecidos. 0.25 es un buen arranque.

Requisitos: pip install requests
"""

import os
import sys
import requests

SUPABASE_URL = "https://ihmbhbhwlntsjqdavxge.supabase.co"
SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")

UMBRAL = 0.25
if len(sys.argv) > 1:
    try:
        UMBRAL = float(sys.argv[1])
    except ValueError:
        print("El argumento debe ser un numero 0..1. Uso: python 20_comparar_iniciativas.py [umbral]", file=sys.stderr)
        sys.exit(1)


def rpc(nombre, payload):
    url = SUPABASE_URL + "/rest/v1/rpc/" + nombre
    headers = {
        "apikey": SERVICE_KEY,
        "Authorization": "Bearer " + SERVICE_KEY,
        "Content-Type": "application/json",
    }
    r = requests.post(url, json=payload, headers=headers, timeout=120)
    r.raise_for_status()
    try:
        return r.json()
    except Exception:
        return None


def main():
    if not SERVICE_KEY:
        print("Falta SUPABASE_SERVICE_KEY en el entorno.", file=sys.stderr)
        sys.exit(1)

    print("1) Recalculando fichas de iniciativas vivas...", file=sys.stderr)
    try:
        n_fichas = rpc("fichas_recalcular_todas", {})
        print("   fichas actualizadas: %s" % n_fichas, file=sys.stderr)
    except Exception as e:
        print("   ERROR armando fichas: %s" % e, file=sys.stderr)
        sys.exit(1)

    print("2) Detectando equivalencias (umbral %.2f)..." % UMBRAL, file=sys.stderr)
    try:
        n_pares = rpc("equivalencias_detectar", {"p_umbral": UMBRAL})
        print("   pares detectados/actualizados: %s" % n_pares, file=sys.stderr)
    except Exception as e:
        print("   ERROR detectando equivalencias: %s" % e, file=sys.stderr)
        sys.exit(1)

    print("Listo. Revisalos en la app de administracion (seccion Equivalencias).", file=sys.stderr)


if __name__ == "__main__":
    main()
