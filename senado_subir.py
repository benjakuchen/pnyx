# -*- coding: utf-8 -*-
# Pnyx - (c) 2026 Benjamin Kuchen. Obra protegida por la Ley 11.723 (Argentina).
# Distribuido bajo la Licencia Publica General Affero de GNU v3 (AGPL-3.0). Ver LICENSE.
r"""
Pnyx · Subir Senado — DE LOS PDF QUE BAJASTE A MANO -> SUPABASE
--------------------------------------------------------------
Lee todos los PDF de la carpeta  senado_pdfs\  (que bajaste a mano siguiendo
senado_reporte.py), extrae el texto de cada uno y lo sube a Supabase.
  - Si el PDF tiene texto legible -> lo guarda en texto_oficial.
  - Si es escaneado (imagen, sin texto) -> sube el PDF a Storage y lo marca
    como escaneado (despues el obrero 15 de OCR lo procesa en la nube).

Cada archivo tiene que llamarse como el bill_id + .pdf   (ej: SENADO871-26.pdf).
Ese nombre es el que te dio el reporte.

Uso (PowerShell, desde la carpeta PNYX):
  $env:SUPABASE_SERVICE_KEY="...."
  python senado_subir.py                 -> usa la carpeta senado_pdfs\
  python senado_subir.py otra_carpeta    -> usa esa carpeta
"""

import os
import re
import sys
import urllib.request

try:
    from pypdf import PdfReader
except ImportError:
    print("Falta pypdf:  pip install pypdf", file=sys.stderr)
    sys.exit(1)
try:
    from supabase import create_client
except ImportError:
    print("Falta supabase:  pip install supabase", file=sys.stderr)
    sys.exit(1)

SUPABASE_URL = "https://ihmbhbhwlntsjqdavxge.supabase.co"
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
CARPETA = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("-") else "senado_pdfs"
MIN_CARACTERES = 60
BUCKET = "pdfs-leyes"


def normalizar_billid(nombre_archivo):
    """Convierte el nombre del PDF al bill_id Pnyx 'SENADO<num>-<anio>'.
    Acepta varios formatos que puede traer el sitio del Senado:
      SENADO637-26   -> SENADO637-26   (ya correcto)
      S637_26PL      -> SENADO637-26
      637-26 / 637_26 / 637.26 -> SENADO637-26
      637            -> SENADO637-26   (asume anio 26)
    """
    base = os.path.splitext(nombre_archivo)[0].strip().upper()
    if base.startswith("SENADO"):
        return base
    # S637_26PL  o  S637-26  etc.
    m = re.match(r"^S?(\d+)[\-_\.]?(\d{2})?(?:PL)?$", base)
    if m:
        num = m.group(1)
        anio = m.group(2) or "26"
        return "SENADO%s-%s" % (num, anio)
    return base  # no reconocido: se deja tal cual (y probablemente falle, avisando)


def extraer_texto(path):
    try:
        reader = PdfReader(path)
        return " ".join(" ".join((pg.extract_text() or "") for pg in reader.pages).split())
    except Exception as e:
        print("    (no pude leer el PDF: %s)" % e, file=sys.stderr)
        return ""


def subir_pdf_storage(bill_id, path):
    with open(path, "rb") as f:
        pdf_bytes = f.read()
    nombre = "%s.pdf" % bill_id
    url = "%s/storage/v1/object/%s/%s" % (SUPABASE_URL, BUCKET, nombre)
    req = urllib.request.Request(url, data=pdf_bytes, method="POST")
    req.add_header("apikey", SUPABASE_KEY)
    req.add_header("Authorization", "Bearer " + SUPABASE_KEY)
    req.add_header("Content-Type", "application/pdf")
    req.add_header("x-upsert", "true")
    try:
        urllib.request.urlopen(req, timeout=120).read()
        return "%s/storage/v1/object/public/%s/%s" % (SUPABASE_URL, BUCKET, nombre)
    except Exception as e:
        print("    error subiendo PDF a Storage: %s" % e, file=sys.stderr)
        return None


def main():
    if not SUPABASE_KEY:
        print('Falta la clave:  $env:SUPABASE_SERVICE_KEY="..." (service_role)', file=sys.stderr)
        sys.exit(1)
    if not os.path.isdir(CARPETA):
        print("No existe la carpeta '%s'. Crearla y poner ahi los PDF." % CARPETA, file=sys.stderr)
        sys.exit(1)

    pdfs = [f for f in os.listdir(CARPETA) if f.lower().endswith(".pdf")]
    if not pdfs:
        print("No hay PDF en la carpeta '%s'." % CARPETA, file=sys.stderr)
        return

    sb = create_client(SUPABASE_URL, SUPABASE_KEY)
    print("Subiendo %d PDF desde '%s'..." % (len(pdfs), CARPETA), file=sys.stderr)
    ok = 0
    escaneadas = 0
    fallos = 0
    sin_match = 0
    for i, fname in enumerate(sorted(pdfs), 1):
        bill_id = normalizar_billid(fname)
        path = os.path.join(CARPETA, fname)

        # La ley TIENE que existir ya en la base (la creo senado_desde_excel).
        # Si no existe, NO creamos fila fantasma: avisamos para renombrar el PDF.
        try:
            existe = sb.table("leyes").select("bill_id").eq("bill_id", bill_id).limit(1).execute().data
        except Exception as e:
            existe = None
            print("  [%d/%d] %s  (no pude verificar: %s)" % (i, len(pdfs), bill_id, e), file=sys.stderr)
            fallos += 1
            continue
        if not existe:
            sin_match += 1
            print("  [%d/%d] %s  NO EXISTE en la base -> revisá el nombre del PDF (archivo: %s)"
                  % (i, len(pdfs), bill_id, fname), file=sys.stderr)
            continue

        texto = extraer_texto(path)
        if texto and len(texto) >= MIN_CARACTERES:
            try:
                sb.table("leyes").update(
                    {"texto_oficial": texto, "texto_escaneado": False}
                ).eq("bill_id", bill_id).execute()
                ok += 1
                est = "OK (%d car.) -> texto subido" % len(texto)
            except Exception as e:
                fallos += 1
                est = "texto OK pero fallo subida: %s" % e
        else:
            url_storage = subir_pdf_storage(bill_id, path)
            try:
                sb.table("leyes").update(
                    {"texto_escaneado": True, "url_pdf_oficial": url_storage}
                ).eq("bill_id", bill_id).execute()
                escaneadas += 1
                est = "ESCANEADO -> PDF subido a Storage (lo OCRea el obrero 15)"
            except Exception as e:
                fallos += 1
                est = "escaneado pero fallo: %s" % e
        print("  [%d/%d] %s  %s" % (i, len(pdfs), bill_id, est), file=sys.stderr)

    print("\nTexto legible subido: %d | Escaneados: %d | Sin match: %d | Fallos: %d | de %d"
          % (ok, escaneadas, sin_match, fallos, len(pdfs)), file=sys.stderr)
    if sin_match:
        print("(Los 'NO EXISTE' son PDF cuyo nombre no coincide con ningun bill_id.", file=sys.stderr)
        print(" Renombralos como dice senado_faltantes.txt, ej: SENADO637-26.pdf)", file=sys.stderr)
    print("(Para reflejar los cambios en el feed, corre:  python 9_mezclar_ordenar.py)", file=sys.stderr)


if __name__ == "__main__":
    main()
