#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pnyx · Obrero 2 — Bajar leyes de Diputados (incremental)
---------------------------------------------------------
Baja los proyectos de LEY desde el portal de Datos Abiertos de la HCDN.
Incluye leyes "venidas en revision" del Senado (media sancion en Diputados).

Incremental: lee 'existentes.json' (generado por el Obrero 1) y solo
agrega las leyes que no estan en Supabase. Las existentes se cargan
del archivo local 'proyectos_diputados.json' para no perder sus textos
y resumenes ya procesados.

Salida: proyectos_diputados.json (todas: existentes + nuevas)

Gratis (no usa IA). Uso: python 2_bajar_diputados.py
"""

import csv
import io
import json
import os
import sys
import urllib.request
from datetime import datetime

CSV_URL = (
    "https://datos.hcdn.gob.ar/dataset/"
    "839441fc-1b5c-45b8-82c9-8b0f18ac7c9b/resource/"
    "22b2d52c-7a0e-426b-ac0a-a3326c388ba6/download/"
    "proyectosparlamentarios1.10.csv"
)

ANIO_MIN = datetime.now().year
ANIO_MIN_REVISION = ANIO_MIN - 1
EXISTENTES = "existentes.json"
LOCAL = "proyectos_diputados.json"   # archivo local de Diputados
SALIDA = "proyectos_diputados.json"


def descargar_csv(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Pnyx-Fase0/0.1"})
    with urllib.request.urlopen(req, timeout=90) as r:
        return r.read().decode("utf-8", errors="replace")


def normalizar(texto):
    return " ".join((texto or "").split())


def parsear(csv_text):
    proyectos = []
    lector = csv.DictReader(io.StringIO(csv_text))
    for fila in lector:
        if (fila.get("TIPO") or "").strip().upper() != "LEY":
            continue

        camara_origen = (fila.get("CAMARA_ORIGEN") or "").strip()
        exp_dip = (fila.get("EXP_DIPUTADOS") or "").strip()
        exp_sen = (fila.get("EXP_SENADO") or "").strip()
        fecha = (fila.get("PUBLICACION_FECHA") or "").strip()
        es_revision = (camara_origen == "Senado" and exp_dip not in ("", "NA"))

        try:
            anio = int(fecha[:4])
        except ValueError:
            anio = None

        if es_revision:
            if anio and anio < ANIO_MIN_REVISION:
                continue
        else:
            if ANIO_MIN and anio and anio < ANIO_MIN:
                continue

        camara = "Diputados"
        origen = "Senado" if es_revision else camara_origen
        expediente = exp_dip if exp_dip not in ("", "NA") else (exp_sen if exp_sen not in ("", "NA") else None)

        proyectos.append({
            "bill_id": (fila.get("PROYECTO_ID") or "").strip(),
            "titulo": normalizar(fila.get("TITULO")),
            "camara": camara,
            "origen": origen,
            "expediente": expediente,
            "exp_senado": exp_sen if exp_sen not in ("", "NA") else None,
            "autor": (fila.get("AUTOR") or "").strip() or None,
            "tipo": "LEY",
            "fecha": fecha[:10] if fecha else None,
            "oracion_ia": None,
            "resumen_ia": None,
            "url_oficial": None,
            "publicado": False,
        })
    return proyectos


def main():
    # Cargar existentes en Supabase
    existentes = {}
    if os.path.exists(EXISTENTES):
        with open(EXISTENTES, encoding="utf-8") as f:
            existentes = json.load(f)
    else:
        print("Aviso: no encontre existentes.json. Corre primero el Obrero 1.", file=sys.stderr)

    # Cargar archivo local (para conservar textos y resumenes ya procesados)
    local = {}
    if os.path.exists(LOCAL):
        with open(LOCAL, encoding="utf-8") as f:
            for p in json.load(f):
                local[p["bill_id"]] = p

    # Bajar CSV de HCDN
    print("Descargando proyectos desde la HCDN...", file=sys.stderr)
    csv_text = descargar_csv(CSV_URL)
    del_csv = parsear(csv_text)
    print("En HCDN: %d leyes del periodo" % len(del_csv), file=sys.stderr)

    # Detectar nuevas (no estan en Supabase)
    nuevas = [p for p in del_csv if p["bill_id"] not in existentes]
    conocidas = [p for p in del_csv if p["bill_id"] in existentes]

    print("Ya en Supabase: %d | Nuevas: %d" % (len(conocidas), len(nuevas)), file=sys.stderr)

    # Armar lista final: conocidas con sus datos locales (texto, resumen) + nuevas
    resultado = []
    for p in del_csv:
        if p["bill_id"] in local:
            # Usar la version local que puede tener texto y resumen
            resultado.append(local[p["bill_id"]])
        else:
            resultado.append(p)

    resultado.sort(key=lambda p: p.get("fecha") or "", reverse=True)

    with open(SALIDA, "w", encoding="utf-8") as f:
        json.dump(resultado, f, ensure_ascii=False, indent=2)

    revision = [p for p in nuevas if p.get("origen") == "Senado"]
    print("Guardado en %s (%d leyes)" % (SALIDA, len(resultado)), file=sys.stderr)
    if nuevas:
        print("\nLeyes NUEVAS a procesar: %d" % len(nuevas), file=sys.stderr)
        if revision:
            print("  (incluye %d venidas en revision del Senado)" % len(revision), file=sys.stderr)
        for p in nuevas[:5]:
            t = (p["titulo"][:65] + "...") if len(p["titulo"]) > 65 else p["titulo"]
            print("  + [%s] %s" % (p["expediente"], t), file=sys.stderr)
        if len(nuevas) > 5:
            print("  ... y %d mas" % (len(nuevas) - 5), file=sys.stderr)
    else:
        print("No hay leyes nuevas de Diputados.", file=sys.stderr)


if __name__ == "__main__":
    main()
