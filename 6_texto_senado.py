#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pnyx · Obrero 6 — Texto del Senado (Supabase = fuente de verdad)
-----------------------------------------------------------------
Para cada ley del Senado que AUN no tenga texto en Supabase, baja el PDF
oficial (ficha -> downloadPdf), extrae el texto y lo SUBE a Supabase.

Lee 'proyectos_senado.json' y 'estado_nube.json'. Solo procesa las que
faltan. No guarda texto en archivos locales: la nube es la verdad.

Dependencia: pip install pypdf supabase
Uso:  python 6_texto_senado.py          (top 40 sin texto)
      python 6_texto_senado.py 100       (top 100)
      python 6_texto_senado.py --todos    (todas las que falten)
"""

import io
import json
import os
import re
import sys
import time
import urllib.request

try:
    from pypdf import PdfReader
except ImportError:
    print("Falta pypdf. Instalalo con:  pip install pypdf", file=sys.stderr)
    sys.exit(1)
try:
    from supabase import create_client
except ImportError:
    print("Falta supabase. Instalalo con:  pip install supabase", file=sys.stderr)
    sys.exit(1)

ARCHIVO = "proyectos_senado.json"
ESTADO = "estado_nube.json"
LIMITE_DEFAULT = 40
PAUSA = 1.2
MIN_CARACTERES = 60

SUPABASE_URL = "https://ihmbhbhwlntsjqdavxge.supabase.co"
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")

BASE = "https://www.senado.gob.ar"
PDF = BASE + "/parlamentario/parlamentaria/{aid}/downloadPdf"
CAB = {"User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
       "Accept": "text/html,application/pdf,*/*"}


def _get(url, referer=None, timeout=60):
    h = dict(CAB)
    if referer:
        h["Referer"] = referer
    try:
        req = urllib.request.Request(url, headers=h)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read()
    except Exception:
        return None


def extraer(b):
    if not b:
        return ""
    try:
        reader = PdfReader(io.BytesIO(b))
        return " ".join(" ".join((pg.extract_text() or "") for pg in reader.pages).split())
    except Exception:
        return ""


def texto_de(p):
    exp = p.get("expediente", "")
    if "/" not in exp:
        return None
    num, anio = exp.split("/")
    origen = {"Senado": "S", "Poder Ejecutivo": "PE", "Diputados": "CD"}.get(p.get("origen", ""), "S")
    ficha = "%s/parlamentario/comisiones/verExp/%s.%s/%s/PL" % (BASE, num, anio, origen)
    html = _get(ficha)
    if not html:
        return None
    m = re.search(rb"parlamentaria/(\d+)/downloadPdf", html)
    if not m:
        return None
    aid = m.group(1).decode()
    return extraer(_get(PDF.format(aid=aid), referer=ficha))


def main():
    if not SUPABASE_KEY:
        print("Falta:  $env:SUPABASE_SERVICE_KEY=\"...\"", file=sys.stderr)
        sys.exit(1)

    todos = "--todos" in sys.argv
    limite = LIMITE_DEFAULT
    for a in sys.argv[1:]:
        if a.isdigit():
            limite = int(a)

    with open(ARCHIVO, encoding="utf-8") as f:
        leyes = json.load(f)
    estado = {}
    if os.path.exists(ESTADO):
        with open(ESTADO, encoding="utf-8") as f:
            estado = json.load(f)

    def tiene_texto_nube(p):
        e = estado.get(p.get("bill_id"))
        return e and e.get("tiene_texto")

    faltan = [p for p in leyes if not tiene_texto_nube(p)]
    objetivo = faltan if todos else faltan[:limite]

    if not objetivo:
        print("Todas las leyes del Senado ya tienen texto en Supabase. Nada que bajar.", file=sys.stderr)
        return

    print("Sin texto en Supabase: %d | Bajando: %d%s\n"
          % (len(faltan), len(objetivo), " (TODAS)" if todos else ""), file=sys.stderr)

    sb = create_client(SUPABASE_URL, SUPABASE_KEY)
    ok = 0
    for i, p in enumerate(objetivo, 1):
        texto = texto_de(p)
        if texto and len(texto) >= MIN_CARACTERES:
            try:
                sb.table("leyes").upsert(
                    {"bill_id": p["bill_id"], "texto_oficial": texto,
                     "autor": (p.get("autor") or None)},
                    on_conflict="bill_id"
                ).execute()
                ok += 1
                est = "OK (%d car.) -> subido" % len(texto)
            except Exception as e:
                est = "texto OK pero fallo subida: %s" % e
        else:
            est = "sin texto (queda pendiente)"
        print("  [%d/%d] %s  %s" % (i, len(objetivo), p.get("expediente"), est), file=sys.stderr)
        time.sleep(PAUSA)

    print("\nTexto bajado y subido a Supabase: %d de %d" % (ok, len(objetivo)), file=sys.stderr)
    print("(Para reflejar el cambio, volve a correr el Obrero 1.)", file=sys.stderr)


if __name__ == "__main__":
    main()
