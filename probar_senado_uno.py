#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Prueba aislada: baja el texto SOLO del expediente 97/26 (Poder Ejecutivo),
que sabemos que tiene PDF publicado en el navegador. Sirve para saber si el
obrero puede acceder al Senado desde Python, separado de "esta ley no tiene texto".

Uso: python probar_senado_uno.py
"""
import io
import re
import sys
import time
import urllib.request
import http.cookiejar

BASE = "https://www.senado.gob.ar"
PDF = BASE + "/parlamentario/parlamentaria/{aid}/downloadPdf"
CAB = {"User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
       "Accept": "text/html,application/xhtml+xml,*/*",
       "Accept-Language": "es-AR,es;q=0.9"}

try:
    from pypdf import PdfReader
except ImportError:
    print("Falta pypdf: pip install pypdf", file=sys.stderr)
    sys.exit(1)

# Sesión con cookies (como un navegador): primero visitamos la home para
# obtener cookies, después pedimos la ficha con esas cookies.
cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))


def get(url, referer=None):
    h = dict(CAB)
    if referer:
        h["Referer"] = referer
    try:
        req = urllib.request.Request(url, headers=h)
        with opener.open(req, timeout=60) as r:
            return r.read()
    except Exception as e:
        print("  ERROR al pedir %s -> %s" % (url, e))
        return None


print("0) Visitando la home para obtener cookies de sesión...")
get(BASE + "/parlamentario/parlamentaria/")
print("   Cookies obtenidas:", len(cj))
time.sleep(1)


# Probamos el 97/26 con origen PE (Poder Ejecutivo), que es el que funciona en el navegador.
NUM, ANIO, ORIGEN = "97", "26", "PE"
ficha = "%s/parlamentario/comisiones/verExp/%s.%s/%s/PL" % (BASE, NUM, ANIO, ORIGEN)
print("1) Pidiendo la ficha:", ficha)
html = get(ficha)
if not html:
    print("   No se pudo bajar la ficha.")
    sys.exit(1)
print("   Ficha bajada: %d bytes" % len(html))
if abs(len(html) - 31570) < 50:
    print("   ⚠ Parece la PÁGINA DE ERROR del Senado (31570 bytes).")

# Guardar el HTML para poder inspeccionarlo
with open("ficha_97_26.html", "wb") as f:
    f.write(html)
print("   HTML guardado en ficha_97_26.html (abrilo para revisar)")

# Buscar el link de varias formas
m = re.search(rb"parlamentaria/(\d+)/downloadPdf", html)
if not m:
    print("   ✗ NO se encontró 'parlamentaria/NNN/downloadPdf'.")
    # pistas alternativas
    for patron in [rb"downloadPdf", rb"textoOriginal", rb"\.pdf", rb"downloadpdf"]:
        n = len(re.findall(patron, html, re.IGNORECASE))
        print("     - apariciones de %s: %d" % (patron.decode(), n))
    # mostrar un pedazo alrededor de 'textoOriginal' si existe
    idx = html.lower().find(b"textooriginal")
    if idx > 0:
        print("     contexto de 'textoOriginal':")
        print("     " + html[idx-100:idx+300].decode("utf-8", "ignore"))
    sys.exit(1)

aid = m.group(1).decode()
print("2) Link del PDF encontrado, id =", aid)
pdf_url = PDF.format(aid=aid)
print("   Bajando PDF:", pdf_url)
time.sleep(1)
pdf = get(pdf_url, referer=ficha)
if not pdf:
    print("   ✗ No se pudo bajar el PDF.")
    sys.exit(1)
print("   PDF bajado: %d bytes" % len(pdf))

try:
    reader = PdfReader(io.BytesIO(pdf))
    texto = " ".join(" ".join((pg.extract_text() or "") for pg in reader.pages).split())
    print("3) Páginas:", len(reader.pages), "| caracteres de texto:", len(texto))
    if len(texto) < 60:
        print("   ⚠ El PDF casi no tiene texto extraíble -> probablemente ESCANEADO.")
    else:
        print("   ✓ TEXTO EXTRAÍDO OK. Primeros 300 caracteres:")
        print("   " + texto[:300])
except Exception as e:
    print("   ✗ Error al leer el PDF:", e)

print("\n=== CONCLUSIÓN ===")
print("Si llegaste hasta acá con texto -> el obrero PUEDE acceder al Senado; el problema")
print("de las otras es que no tienen texto publicado o el bloqueo por velocidad.")
