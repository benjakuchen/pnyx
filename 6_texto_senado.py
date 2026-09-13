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
import http.cookiejar

# Sesión con cookies: el Senado solo da el HTML completo (con el link del PDF)
# si tenés cookies de sesión. Sin cookies devuelve una versión reducida sin el link.
_cj = http.cookiejar.CookieJar()
_opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(_cj))
_sesion_iniciada = False


def _iniciar_sesion():
    """Visita la home una vez para obtener cookies antes de pedir fichas."""
    global _sesion_iniciada
    if _sesion_iniciada:
        return
    try:
        req = urllib.request.Request(BASE + "/parlamentario/parlamentaria/", headers=CAB)
        _opener.open(req, timeout=30).read()
    except Exception:
        pass
    _sesion_iniciada = True

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
MIN_CARACTERES = 60

SUPABASE_URL = "https://ihmbhbhwlntsjqdavxge.supabase.co"
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")

BASE = "https://www.senado.gob.ar"
PDF = BASE + "/parlamentario/parlamentaria/{aid}/downloadPdf"
DIAG = "--diag" in sys.argv
PAUSA_BLOQUEO = 120  # si el Senado corta, esperar 2 min (una vez por expediente)
BACKOFF_FILE = "senado_backoff.json"
PAUSA_BASE_INICIAL = 30.0   # arranca en 30 seg entre expedientes
PAUSA_MIN = 15.0            # no bajar de acá
PAUSA_MAX = 600.0           # tope: 10 min


def cargar_pausa():
    """Lee la pausa guardada de corridas anteriores (backoff adaptativo)."""
    try:
        with open(BACKOFF_FILE, encoding="utf-8") as f:
            import json as _j
            return float(_j.load(f).get("pausa", PAUSA_BASE_INICIAL))
    except Exception:
        return PAUSA_BASE_INICIAL


def guardar_pausa(pausa):
    try:
        with open(BACKOFF_FILE, "w", encoding="utf-8") as f:
            import json as _j
            _j.dump({"pausa": pausa}, f)
    except Exception:
        pass
TAM_BLOQUEO = 31570  # tamaño exacto de la página de error/rate-limit del Senado (bytes)
CAB = {"User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
       "Accept": "text/html,application/xhtml+xml,*/*",
       "Accept-Language": "es-AR,es;q=0.9"}


def _get(url, referer=None, timeout=60):
    _iniciar_sesion()
    h = dict(CAB)
    if referer:
        h["Referer"] = referer
    try:
        req = urllib.request.Request(url, headers=h)
        with _opener.open(req, timeout=timeout) as r:
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


def _ficha_a_pdf(ficha):
    """Baja la ficha del expediente y busca el link del PDF (downloadPdf)."""
    html = _get(ficha)
    if not html:
        return None
    m = re.search(rb"parlamentaria/(\d+)/downloadPdf", html)
    if not m:
        return None
    aid = m.group(1).decode()
    return extraer(_get(PDF.format(aid=aid), referer=ficha))


def _es_bloqueo(html):
    """El Senado devuelve una página de error de tamaño fijo cuando corta por rate-limit."""
    return html is not None and abs(len(html) - TAM_BLOQUEO) < 50


_hubo_bloqueo = False


def texto_de(p):
    global _hubo_bloqueo
    exp = p.get("expediente", "")
    if "/" not in exp:
        return None
    num, anio = exp.split("/")

    declarado = {"Senado": "S", "Poder Ejecutivo": "PE", "Diputados": "CD"}.get(p.get("origen") or "", None)
    orden = [o for o in [declarado, "S", "PE", "CD"] if o]
    vistos = set()
    ya_espere = False
    for origen in orden:
        if origen in vistos:
            continue
        vistos.add(origen)
        ficha = "%s/parlamentario/comisiones/verExp/%s.%s/%s/PL" % (BASE, num, anio, origen)
        html = _get(ficha)

        if _es_bloqueo(html) and not ya_espere:
            ya_espere = True
            _hubo_bloqueo = True
            if DIAG:
                print("      BLOQUEO, esperando %ds..." % PAUSA_BLOQUEO, file=sys.stderr)
            time.sleep(PAUSA_BLOQUEO)
            html = _get(ficha)

        tiene_link = bool(html and re.search(rb"parlamentaria/(\d+)/downloadPdf", html))
        if DIAG:
            diag = "no-html" if not html else ("%d bytes" % len(html))
            print("      probe %s/%s/%s -> %s, downloadPdf=%s" % (num, anio, origen, diag, tiene_link), file=sys.stderr)

        if html:
            m = re.search(rb"parlamentaria/(\d+)/downloadPdf", html)
            if m:
                aid = m.group(1).decode()
                url_pdf = PDF.format(aid=aid)
                time.sleep(1.0)
                pdf = _get(url_pdf, referer=ficha)
                txt = extraer(pdf)
                if txt and len(txt) >= MIN_CARACTERES:
                    return (txt, None, False, None)          # legible: (texto, -, no escaneado, -)
                else:
                    tam = len(pdf) if pdf else 0
                    if DIAG:
                        print("      PDF %d bytes sin texto -> ESCANEADO (a subir a Storage)" % tam, file=sys.stderr)
                    return (None, url_pdf, True, pdf)         # escaneado: (-, link_senado, True, bytes_pdf)
    return (None, None, False, None)


def subir_pdf_storage(bill_id, pdf_bytes):
    """Sube el PDF escaneado a Supabase Storage (bucket pdfs-leyes) y devuelve la URL pública."""
    if not pdf_bytes:
        return None
    nombre = "%s.pdf" % bill_id
    url = "%s/storage/v1/object/pdfs-leyes/%s" % (SUPABASE_URL, nombre)
    req = urllib.request.Request(url, data=pdf_bytes, method="POST")
    req.add_header("apikey", SUPABASE_KEY)
    req.add_header("Authorization", "Bearer " + SUPABASE_KEY)
    req.add_header("Content-Type", "application/pdf")
    req.add_header("x-upsert", "true")   # sobrescribe si ya existe
    try:
        urllib.request.urlopen(req, timeout=120).read()
        return "%s/storage/v1/object/public/pdfs-leyes/%s" % (SUPABASE_URL, nombre)
    except Exception as e:
        print("      error subiendo PDF a Storage: %s" % e, file=sys.stderr)
        return None


def main():
    if not SUPABASE_KEY:
        print("Falta:  $env:SUPABASE_SERVICE_KEY=\"...\"", file=sys.stderr)
        sys.exit(1)

    todos = "--todos" in sys.argv
    limite = 5   # por defecto 5 por corrida (para no gatillar el bloqueo del Senado)
    for a in sys.argv[1:]:
        if a.isdigit():
            limite = int(a)

    sb = create_client(SUPABASE_URL, SUPABASE_KEY)

    # Objetivo: leyes del Senado PUBLICADAS (en el feed), sin texto y no marcadas
    # como escaneadas. Solo bajamos texto de lo que se muestra.
    res = (sb.table("leyes")
           .select("bill_id,expediente,origen,autor,titulo")
           .eq("camara", "Senado")
           .eq("publicada", True)
           .is_("texto_oficial", "null")
           .or_("texto_escaneado.is.null,texto_escaneado.eq.false")
           .execute())
    faltan = res.data or []
    objetivo = faltan if todos else faltan[:limite]

    if not objetivo:
        print("No hay leyes del Senado PUBLICADAS sin texto. Nada que bajar.", file=sys.stderr)
        print("(Publicá leyes desde la curaduría para que aparezcan acá.)", file=sys.stderr)
        return

    pausa = cargar_pausa()
    print("Senado publicadas sin texto: %d | Bajando: %d%s | Pausa: %.0fs"
          % (len(faltan), len(objetivo), " (TODAS)" if todos else "", pausa), file=sys.stderr)
    ok = 0
    escaneadas = 0
    for i, p in enumerate(objetivo, 1):
        texto, url_senado, escaneado, pdf_bytes = texto_de(p)
        if texto and len(texto) >= MIN_CARACTERES:
            try:
                sb.table("leyes").upsert(
                    {"bill_id": p["bill_id"], "texto_oficial": texto,
                     "texto_escaneado": False, "autor": (p.get("autor") or None)},
                    on_conflict="bill_id"
                ).execute()
                ok += 1
                est = "OK (%d car.) -> texto subido" % len(texto)
            except Exception as e:
                est = "texto OK pero fallo subida: %s" % e
        elif escaneado and pdf_bytes:
            url_storage = subir_pdf_storage(p["bill_id"], pdf_bytes)
            try:
                sb.table("leyes").upsert(
                    {"bill_id": p["bill_id"], "texto_escaneado": True,
                     "url_pdf_oficial": url_storage},
                    on_conflict="bill_id"
                ).execute()
                escaneadas += 1
                est = "ESCANEADO (%.1f MB) -> PDF subido a Storage" % (len(pdf_bytes) / 1048576.0)
            except Exception as e:
                est = "escaneado pero fallo: %s" % e
        else:
            est = "sin texto (queda pendiente)"
        print("  [%d/%d] %s  %s" % (i, len(objetivo), p.get("expediente"), est), file=sys.stderr)
        time.sleep(pausa)

    if _hubo_bloqueo:
        nueva = min(pausa + 60, PAUSA_MAX)
        print("\n⚠ Hubo bloqueo(s) del Senado. Próxima corrida usará %.0fs de pausa." % nueva, file=sys.stderr)
    else:
        nueva = max(pausa - 5, PAUSA_MIN)
    guardar_pausa(nueva)

    print("\nTexto legible subido: %d | Escaneados marcados: %d | de %d"
          % (ok, escaneadas, len(objetivo)), file=sys.stderr)


if __name__ == "__main__":
    main()
