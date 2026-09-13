#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pnyx · Obrero 15 — OCR de PDFs escaneados (IA lee la imagen y resume)
----------------------------------------------------------------------
Para las leyes PUBLICADAS marcadas como escaneadas (texto_escaneado=true) que
todavia no tienen oracion, baja el PDF desde Supabase Storage, convierte las
primeras 15 paginas a imagen, y le pide a la IA que las LEA y devuelva la
oracion + resumen (una sola pasada). Guarda el resultado como si fuera texto.

Requisitos: pip install pypdfium2 pillow anthropic supabase requests
            (pypdfium2 NO necesita poppler ni nada externo)
Claves:  $env:SUPABASE_SERVICE_KEY  y  $env:ANTHROPIC_API_KEY

Uso:
  python 15_ocr.py            procesa hasta 3 leyes escaneadas publicadas
  python 15_ocr.py 5          procesa hasta 5
  python 15_ocr.py --diag     muestra detalle
"""

import base64
import io
import os
import sys

import requests

try:
    import pypdfium2 as pdfium
except ImportError:
    print("Falta pypdfium2: pip install pypdfium2", file=sys.stderr)
    sys.exit(1)
try:
    from anthropic import Anthropic
except ImportError:
    print("Falta anthropic: pip install anthropic", file=sys.stderr)
    sys.exit(1)
try:
    from supabase import create_client
except ImportError:
    print("Falta supabase: pip install supabase", file=sys.stderr)
    sys.exit(1)

MODELO = "claude-sonnet-4-6"
PAGINAS = 15         # cuantas paginas del PDF leer (donde suele estar el articulado)
DPI = 110            # resolución de la imagen (suficiente para leer, liviano para PDFs pesados)
SUPABASE_URL = "https://ihmbhbhwlntsjqdavxge.supabase.co"
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
DIAG = "--diag" in sys.argv

SISTEMA = """Sos un asistente que lee proyectos de ley argentinos ESCANEADOS (imágenes) para una app ciudadana.
Te paso las primeras páginas de un proyecto como imágenes. Leelas y devolvés SOLO un objeto JSON, sin nada más:
{"oracion": "...", "resumen": "..."}

Reglas estrictas:
- "oracion": UNA sola frase clara y simple que cualquiera entienda en 5 segundos. Qué hace el proyecto. Sin jerga ni números de ley. Máximo 25 palabras.
- "resumen": 2 a 4 frases. Qué dice el proyecto, después una línea con "A favor:" y "En discusión:" planteando los dos lados SIN tomar partido.
- NEUTRALIDAD ABSOLUTA. Español rioplatense, claro y sobrio.
- Basate en lo que puedas leer de las imágenes. Si son ilegibles o no son un proyecto de ley, devolvé oracion y resumen vacíos ("").
- Respondés SOLO el JSON, sin explicaciones."""


def bajar_pdf(url):
    r = requests.get(url, timeout=120)
    r.raise_for_status()
    return r.content


def paginas_a_imagenes(pdf_bytes):
    doc = pdfium.PdfDocument(pdf_bytes)
    total = len(doc)
    n = min(PAGINAS, total)
    escala = DPI / 72.0   # pypdfium usa escala; 72 dpi es la base del PDF
    bloques = []
    for i in range(n):
        page = doc[i]
        pil = page.render(scale=escala).to_pil()
        buf = io.BytesIO()
        pil.save(buf, format="JPEG", quality=70)
        b64 = base64.standard_b64encode(buf.getvalue()).decode()
        bloques.append({"type": "image",
                        "source": {"type": "base64", "media_type": "image/jpeg", "data": b64}})
    doc.close()
    return bloques


def ocr_y_resumir(cliente, titulo, pdf_bytes):
    import json
    imgs = paginas_a_imagenes(pdf_bytes)
    contenido = [{"type": "text", "text": "TÍTULO (referencia): %s\n\nLeé estas páginas del proyecto:" % titulo}]
    contenido += imgs
    resp = cliente.messages.create(
        model=MODELO, max_tokens=800, system=SISTEMA,
        messages=[{"role": "user", "content": contenido}],
    )
    salida = "".join(b.text for b in resp.content if hasattr(b, "text")).strip()
    salida = salida.replace("```json", "").replace("```", "").strip()
    datos = json.loads(salida)
    return datos.get("oracion"), datos.get("resumen")


def main():
    if not SUPABASE_KEY:
        print('Falta $env:SUPABASE_SERVICE_KEY', file=sys.stderr); sys.exit(1)
    clave = os.environ.get("ANTHROPIC_API_KEY")
    if not clave:
        print('Falta $env:ANTHROPIC_API_KEY', file=sys.stderr); sys.exit(1)

    limite = 3
    for a in sys.argv[1:]:
        if a.isdigit():
            limite = int(a)

    sb = create_client(SUPABASE_URL, SUPABASE_KEY)
    res = (sb.table("leyes")
           .select("bill_id,titulo,url_pdf_oficial")
           .eq("publicada", True)
           .eq("texto_escaneado", True)
           .is_("oracion_ia", "null")
           .not_.is_("url_pdf_oficial", "null")
           .limit(limite).execute())
    objetivo = res.data or []
    if not objetivo:
        print("No hay leyes escaneadas publicadas pendientes de OCR.", file=sys.stderr)
        return

    print("Leyes escaneadas a procesar con OCR: %d\n" % len(objetivo), file=sys.stderr)
    cliente = Anthropic(api_key=clave)
    ok = 0
    for i, p in enumerate(objetivo, 1):
        bid = p["bill_id"]
        try:
            pdf = bajar_pdf(p["url_pdf_oficial"])
            if DIAG:
                print("  [%d/%d] %s  PDF %.1f MB, leyendo con IA..." % (i, len(objetivo), bid, len(pdf)/1048576.0), file=sys.stderr)
            oracion, resumen = ocr_y_resumir(cliente, p.get("titulo", ""), pdf)
            if oracion:
                sb.table("leyes").upsert({
                    "bill_id": bid,
                    "oracion_ia": oracion,
                    "resumen_ia": resumen,
                }, on_conflict="bill_id").execute()
                ok += 1
                print("  [%d/%d] %s  OK -> %s" % (i, len(objetivo), bid, (oracion or "")[:60]), file=sys.stderr)
            else:
                print("  [%d/%d] %s  la IA no pudo leerlo (ilegible)" % (i, len(objetivo), bid), file=sys.stderr)
        except Exception as e:
            print("  [%d/%d] %s  ERROR: %s" % (i, len(objetivo), bid, e), file=sys.stderr)

    print("\nProcesadas con OCR: %d de %d" % (ok, len(objetivo)), file=sys.stderr)


if __name__ == "__main__":
    main()
