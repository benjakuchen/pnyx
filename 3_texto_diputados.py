#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pnyx · Obrero 3 — Texto de Diputados (Supabase = fuente de verdad)
-------------------------------------------------------------------
Para cada ley de Diputados que AUN NO tenga texto en Supabase, baja el
PDF oficial, extrae el texto y lo SUBE directo a Supabase. No guarda en
archivos locales: la nube es la verdad.

Lee 'proyectos_diputados.json' (la lista de leyes) y 'estado_nube.json'
(que dice cuales ya tienen texto). Solo procesa las que faltan.

Dependencia: pip install pypdf supabase
Uso:  python 3_texto_diputados.py          (top 40 sin texto)
      python 3_texto_diputados.py 100       (top 100 sin texto)
      python 3_texto_diputados.py --todos    (todas las que falten)
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

ARCHIVO = "proyectos_diputados.json"
ESTADO = "estado_nube.json"
LIMITE_DEFAULT = 40
PAUSA = 1.2
MIN_CARACTERES = 60

SUPABASE_URL = "https://ihmbhbhwlntsjqdavxge.supabase.co"
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")

VISOR = "https://www.hcdn.gob.ar/proyectos/detalle_tp_adjunto/index.html?id={pid}"
PDF = "https://rest.hcdn.gob.ar/web/proyectos/{pid}/adjuntos/{aid}"
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


def extraer(pdf_bytes):
    if not pdf_bytes:
        return ""
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        return " ".join(" ".join((pg.extract_text() or "") for pg in reader.pages).split())
    except Exception:
        return ""


def texto_de(p):
    bid = p.get("bill_id", "")
    m = re.search(r"(\d+)", bid)
    if not m:
        return None
    pid = m.group(1)
    html = _get(VISOR.format(pid=pid))
    if not html:
        return None
    mm = re.search(rb"adjuntos/(\d+)", html)
    if not mm:
        return None
    aid = mm.group(1).decode()
    pdf = _get(PDF.format(pid=pid, aid=aid), referer=VISOR.format(pid=pid))
    return extraer(pdf)


def main():
    if not SUPABASE_KEY:
        print("Falta la clave:  $env:SUPABASE_SERVICE_KEY=\"...\"", file=sys.stderr)
        sys.exit(1)

    todos = "--todos" in sys.argv
    limite = LIMITE_DEFAULT
    for a in sys.argv[1:]:
        if a.isdigit():
            limite = int(a)

    with open(ARCHIVO, encoding="utf-8") as f:
        leyes = json.load(f)

    # Estado de la nube: que leyes ya tienen texto
    estado = {}
    if os.path.exists(ESTADO):
        with open(ESTADO, encoding="utf-8") as f:
            estado = json.load(f)
    else:
        print("Aviso: no encontre estado_nube.json. Corre el Obrero 1 primero.", file=sys.stderr)

    # Solo las que NO tienen texto en Supabase
    def tiene_texto_nube(p):
        e = estado.get(p.get("bill_id"))
        return e and e.get("tiene_texto")

    faltan = [p for p in leyes if not tiene_texto_nube(p)]
    objetivo = faltan if todos else faltan[:limite]

    if not objetivo:
        print("Todas las leyes de Diputados ya tienen texto en Supabase. Nada que bajar.",
              file=sys.stderr)
        return

    print("Sin texto en Supabase: %d | Bajando: %d%s\n"
          % (len(faltan), len(objetivo), " (TODAS)" if todos else ""), file=sys.stderr)

    sb = create_client(SUPABASE_URL, SUPABASE_KEY)
    ok = 0
    for i, p in enumerate(objetivo, 1):
        texto = texto_de(p)
        if texto and len(texto) >= MIN_CARACTERES:
            # Subir directo a Supabase
            try:
                sb.table("leyes").upsert(
                    {"bill_id": p["bill_id"], "texto_oficial": texto,
                     "autor": (p.get("autor") or None)},
                    on_conflict="bill_id"
                ).execute()
                ok += 1
                estado_txt = "OK (%d car.) -> subido" % len(texto)
            except Exception as e:
                estado_txt = "texto OK pero fallo subida: %s" % e
        else:
            estado_txt = "sin texto (queda pendiente)"
        print("  [%d/%d] %s  %s" % (i, len(objetivo), p.get("expediente"), estado_txt), file=sys.stderr)
        time.sleep(PAUSA)

    print("\nTexto bajado y subido a Supabase: %d de %d" % (ok, len(objetivo)), file=sys.stderr)
    print("(Para reflejar el cambio, volve a correr el Obrero 1.)", file=sys.stderr)


if __name__ == "__main__":
    main()
