#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Pnyx - (c) 2026 Benjamin Kuchen. Obra protegida por la Ley 11.723 (Argentina).
# Distribuido bajo la Licencia Publica General Affero de GNU v3 (AGPL-3.0). Ver LICENSE.
"""
Pnyx · Obrero 21 — Clasificar leyes por AREA TEMATICA (por palabras clave)
-------------------------------------------------------------------------
Recorre las leyes y les asigna un area segun palabras clave del titulo y
el resumen. Gratis, sin IA. Lo que no matchea con nada -> "Otros".

Por defecto SOLO clasifica las que no tienen area (las nuevas). Con --todas
reclasifica todo (util si se cambian las reglas).

Uso (PowerShell):
  $env:SUPABASE_SERVICE_KEY="..."
  python 21_areas.py            -> solo las que aun no tienen area
  python 21_areas.py --todas    -> reclasifica TODAS
  python 21_areas.py --dry-run  -> muestra el reparto sin escribir

Requisitos: pip install requests
"""

import os
import re
import sys
import json
import requests

SUPABASE_URL = "https://ihmbhbhwlntsjqdavxge.supabase.co"
SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
TODAS = "--todas" in sys.argv
DRY = "--dry-run" in sys.argv
LOTE = 200

# Areas y sus palabras clave (en orden: la primera que matchea gana).
# Las mas especificas van primero; "Otros" es el fallback.
AREAS = [
    ("Salud", [
        "salud", "hospital", "medic", "enfermedad", "sanitari", "vacun", "farmac",
        "paciente", "psicolog", "psiquiatr", "oncolog", "discapacidad mental",
        "adicc", "droga", "obra social", "emergencia sanitaria", "pandemia", "epidem",
        "aliment", "etiquetado", "nutric", "obesidad", "tabaco", "alcohol",
    ]),
    ("Educación", [
        "educ", "escuela", "escolar", "universi", "docente", "aluvmn", "alumn",
        "alumn", "beca", "estudiant", "colegio", "jardin de infantes", "alfabet", "pedagog",
    ]),
    ("Ambiente", [
        "ambient", "glaciar", "bosque", "fauna", "flora", "contamin", "residu",
        "clima", "clímat", "ecolog", "biodivers", "humedal", "agua", "forestal",
        "mineria", "minería", "energia renovable", "energía renovable", "reciclaje",
    ]),
    ("Economía y trabajo", [
        "trabaj", "empleo", "laboral", "salario", "jubilac", "pension", "aporte",
        "sindical", "pyme", "industri", "produc", "comercio", "exporta", "importa",
        "impuesto", "tribut", "iva", "ganancias", "monotributo", "arancel", "inversi",
        "banco", "credito", "crédito", "moneda", "inflaci", "presupuesto", "economia", "economía",
        "tarifa", "subsidi", "combustible",
    ]),
    ("Seguridad y justicia", [
        "seguridad", "delito", "penal", "crimen", "narcotrafico", "narcotráfico",
        "policia", "policía", "carcel", "cárcel", "prision", "prisión", "justicia",
        "codigo procesal", "código procesal", "juez", "tribunal", "fiscal",
        "violencia", "arma", "terroris", "camara de apelaciones", "cámara de apelaciones",
        "camara federal", "cámara federal", "juzgado", "poder judicial", "magistrad",
    ]),
    ("Derechos y géneros", [
        "genero", "género", "mujer", "igualdad", "paridad", "diversidad", "lgbt",
        "femici", "aborto", "derechos human", "discrimin", "identidad de genero",
        "identidad de género", "violencia de genero", "violencia de género", "paternidad",
        "maternidad", "licencia por",
    ]),
    ("Transporte e infraestructura", [
        "transport", "vial", "ruta", "autopista", "ferrocarril", "tren", "colectivo",
        "subte", "aero", "puerto", "navegab", "obra publica", "obra pública",
        "infraestructura", "vivienda", "habitat", "hábitat", "urban", "peaje",
    ]),
    ("Ciencia y tecnología", [
        "ciencia", "tecnolog", "innovaci", "conicet", "investigac", "software",
        "internet", "digital", "datos personales", "inteligencia artificial",
        "telecomunicaci", "satelit", "satélit", "nuclear", "espaci",
    ]),
    ("Niñez, familia y adultos mayores", [
        "niñez", "niño", "niña", "infancia", "adolescen", "familia", "adopci",
        "adulto mayor", "tercera edad", "jubilad", "anciano", "menor", "patria potestad",
    ]),
    ("Cultura y deporte", [
        "cultura", "cultural", "patrimonio", "arte", "musica", "música", "cine",
        "teatro", "libro", "deporte", "deportiv", "futbol", "fútbol", "turismo",
        "fiesta nacional", "capital nacional", "homenaje", "monumento",
    ]),
    ("Estado y transparencia", [
        "transparencia", "acceso a la informacion", "acceso a la información",
        "electoral", "boleta", "voto", "partido politico", "partido político",
        "administracion publica", "administración pública", "ministerio", "organismo",
        "etica publica", "ética pública", "corrupcion", "corrupción", "funcionario",
        "presupuesto nacional", "coparticipacion", "coparticipación", "federal",
        "provincia", "municipio", "constituc", "tratado", "acuerdo internacional",
    ]),
]


def _norm(s):
    return (s or "").lower()


def clasificar(titulo, resumen):
    txt = _norm(titulo) + " " + _norm(resumen)
    for area, claves in AREAS:
        for c in claves:
            if c in txt:
                return area
    return "Otros"


def traer_leyes():
    headers = {"apikey": SERVICE_KEY, "Authorization": "Bearer " + SERVICE_KEY}
    filas = []
    offset = 0
    sel = "bill_id,titulo,oracion_ia,area,area_manual"
    # Nunca tocar las editadas a mano (area_manual=true). not.is.true cubre false y null.
    # Sin --todas: solo las que aun no tienen area. Con --todas: todas menos las manuales.
    filtro = "&area_manual=not.is.true" if TODAS else "&area=is.null&area_manual=not.is.true"
    while True:
        url = (SUPABASE_URL + "/rest/v1/leyes?select=" + sel +
               filtro + "&limit=1000&offset=" + str(offset))
        r = requests.get(url, headers=headers, timeout=30)
        r.raise_for_status()
        parte = r.json()
        filas.extend(parte)
        if len(parte) < 1000:
            break
        offset += 1000
    return filas


def main():
    if not SERVICE_KEY:
        print('Falta la clave:  $env:SUPABASE_SERVICE_KEY="..."', file=sys.stderr)
        sys.exit(1)

    leyes = traer_leyes()
    print("Leyes a clasificar: %d%s" % (len(leyes), " (TODAS)" if TODAS else " (sin area)"),
          file=sys.stderr)

    cont = {}
    cambios = []
    for l in leyes:
        area = clasificar(l.get("titulo"), l.get("oracion_ia"))
        cont[area] = cont.get(area, 0) + 1
        cambios.append({"bill_id": l["bill_id"], "area": area})

    print("\n=== REPARTO POR AREA ===", file=sys.stderr)
    for area, n in sorted(cont.items(), key=lambda x: -x[1]):
        print("  %-34s %d" % (area, n), file=sys.stderr)

    if DRY:
        print("\n(DRY-RUN: no se escribio nada.)", file=sys.stderr)
        return

    headers = {"apikey": SERVICE_KEY, "Authorization": "Bearer " + SERVICE_KEY,
               "Content-Type": "application/json", "Prefer": "resolution=merge-duplicates"}
    for i in range(0, len(cambios), LOTE):
        lote = cambios[i:i + LOTE]
        url = SUPABASE_URL + "/rest/v1/leyes?on_conflict=bill_id"
        r = requests.post(url, headers=headers, data=json.dumps(lote), timeout=30)
        if r.status_code >= 300:
            print("  error lote %d: %s %s" % (i, r.status_code, r.text[:200]), file=sys.stderr)
    print("\nListo: %d leyes clasificadas." % len(cambios), file=sys.stderr)


if __name__ == "__main__":
    main()
