#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Pnyx - (c) 2026 Benjamin Kuchen. Obra protegida por la Ley 11.723 (Argentina).
# Distribuido bajo la Licencia Publica General Affero de GNU v3 (AGPL-3.0). Ver LICENSE.
r"""
Pnyx · Senado Excel automatico — DESCUBRIR leyes nuevas (para el maestro)
------------------------------------------------------------------------
Intenta bajar SOLO el Excel de expedientes del Senado (la LISTA, no los PDF)
y meter en Supabase las leyes (PL) que todavia no estaban. Es la parte que
quizas SI se pueda automatizar (el bloqueo del Senado podria afectar solo a
los PDF del texto, no al Excel).

Pensado para correr en GitHub Actions:
  - Si consigue el Excel -> inserta las nuevas (solo titulo, sin texto).
  - Si el Senado bloquea la descarga -> avisa y SALE SIN ERROR (codigo 0),
    para no cortar el resto del maestro. Ese dia el Senado se hace a mano.

NO baja textos (eso sigue manual: senado_reporte.py + PDF + senado_subir.py).

Requiere:  $env:SUPABASE_SERVICE_KEY   +   pip install python-calamine
Uso:
  python senado_excel_auto.py            baja e inserta
  python senado_excel_auto.py --dry-run  baja y muestra, sin escribir
"""

import datetime
import http.cookiejar
import json
import os
import re
import sys
import urllib.parse
import urllib.request

try:
    from python_calamine import CalamineWorkbook
except ImportError:
    print("Falta python-calamine:  pip install python-calamine", file=sys.stderr)
    sys.exit(0)   # no rompemos el maestro
try:
    from supabase import create_client
except ImportError:
    print("Falta supabase:  pip install supabase", file=sys.stderr)
    sys.exit(0)

SUPABASE_URL = "https://ihmbhbhwlntsjqdavxge.supabase.co"
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
BASE = "https://www.senado.gob.ar"
URL_BUSQUEDA = BASE + "/parlamentario/parlamentaria/fechaMesa"
URL_EXCEL = BASE + "/micrositios/DatosAbiertosExpedientes/BusquedaMesaEntradas/XLS"
ARCHIVO_XLS = "senado_auto.xls"
ANIO = "26"
DESDE = (1, 1, 2026)
ORIGEN_TXT = {"S": "Senado", "PE": "Poder Ejecutivo", "CD": "Diputados"}
DRY = "--dry-run" in sys.argv

CABECERAS = {"User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                            "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")}


def bajar_excel():
    """Devuelve True si bajo un Excel valido (>20KB y firma OLE). False si no."""
    cj = http.cookiejar.CookieJar()
    nav = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    nav.addheaders = list(CABECERAS.items())
    hoy = datetime.date.today()
    try:
        nav.open(BASE + "/parlamentario/parlamentaria/", timeout=60).read()
    except Exception:
        pass
    form = {
        "busqueda_proyectos[fechaDesdeMesa][day]": DESDE[0],
        "busqueda_proyectos[fechaDesdeMesa][month]": DESDE[1],
        "busqueda_proyectos[fechaDesdeMesa][year]": DESDE[2],
        "busqueda_proyectos[fechaHastaMesa][day]": hoy.day,
        "busqueda_proyectos[fechaHastaMesa][month]": hoy.month,
        "busqueda_proyectos[fechaHastaMesa][year]": hoy.year,
    }
    datos = urllib.parse.urlencode(form).encode("utf-8")
    try:
        nav.open(urllib.request.Request(URL_BUSQUEDA, data=datos), timeout=90).read()
    except Exception as e:
        print("  (aviso busqueda: %s)" % e, file=sys.stderr)
    try:
        contenido = nav.open(URL_EXCEL, timeout=120).read()
    except Exception as e:
        print("  No se pudo bajar el Excel del Senado (%s)." % e, file=sys.stderr)
        return False
    # Validar que sea un XLS real (firma OLE), no una pagina HTML de error
    if len(contenido) < 20000 or not contenido[:4] == b"\xd0\xcf\x11\xe0":
        print("  El Senado no devolvio un Excel valido (%d bytes). Probablemente bloqueo."
              % len(contenido), file=sys.stderr)
        return False
    with open(ARCHIVO_XLS, "wb") as f:
        f.write(contenido)
    print("  Excel bajado: %d KB" % (len(contenido) // 1024), file=sys.stderr)
    return True


def separar_autor(extracto):
    extracto = " ".join(str(extracto).split())
    m = re.match(r"^([A-ZÁÉÍÓÚÑ ,\.YÜ]+?):\s*(.*)$", extracto)
    if m and len(m.group(1)) < 80:
        autor = m.group(1).strip().title()
        titulo = re.sub(r"^PROYECTO DE LEY\s+(QUE\s+)?", "", m.group(2).strip(), flags=re.IGNORECASE).strip()
        return autor, (titulo or extracto)
    return None, extracto


def fmt_fecha(v):
    s = str(v)
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", s) or re.search(r"(\d{2})/(\d{2})/(\d{4})", s)
    if not m:
        return ""
    g = m.groups()
    return "%s-%s-%s" % (g[0], g[1], g[2]) if len(g[0]) == 4 else "%s-%s-%s" % (g[2], g[1], g[0])


def bill_ids_existentes(sb):
    ids, desde = set(), 0
    while True:
        r = sb.table("leyes").select("bill_id").eq("camara", "Senado") \
            .range(desde, desde + 999).execute()
        filas = r.data or []
        for f in filas:
            ids.add(f["bill_id"])
        if len(filas) < 1000:
            break
        desde += 1000
    return ids


def main():
    if not SUPABASE_KEY:
        print("Falta $env:SUPABASE_SERVICE_KEY", file=sys.stderr)
        sys.exit(0)

    print("Senado (Excel automatico): intentando bajar la lista...", file=sys.stderr)
    if not bajar_excel():
        print("=> Hoy el Senado no se pudo bajar solo. Queda para hacer a mano.", file=sys.stderr)
        sys.exit(0)   # NO rompe el maestro

    wb = CalamineWorkbook.from_path(ARCHIVO_XLS)
    filas = wb.get_sheet_by_index(0).to_python()

    proyectos = []
    for r in filas[1:]:
        if not r or not r[0]:
            continue
        exp = str(r[0]).strip()
        tipo = str(r[1]).strip() if len(r) > 1 else ""
        origen = str(r[2]).strip() if len(r) > 2 else ""
        fecha = fmt_fecha(r[3]) if len(r) > 3 else ""
        extracto = r[4] if len(r) > 4 else ""
        if tipo != "PL" or not exp.endswith("/" + ANIO):
            continue
        autor, titulo = separar_autor(extracto)
        num = exp.split("/")[0]
        proyectos.append({
            "bill_id": "SENADO%s-%s" % (num, ANIO),
            "expediente": exp,
            "titulo": titulo,
            "camara": "Senado",
            "autor": autor,
            "origen": ORIGEN_TXT.get(origen, origen),
            "fecha": fecha,
            "publicada": False,
        })

    print("Proyectos de ley (PL) del Senado en el Excel: %d" % len(proyectos), file=sys.stderr)

    sb = create_client(SUPABASE_URL, SUPABASE_KEY)
    existentes = bill_ids_existentes(sb)
    nuevas = [p for p in proyectos if p["bill_id"] not in existentes]
    print("Ya en Supabase: %d | Nuevas: %d" % (len(proyectos) - len(nuevas), len(nuevas)), file=sys.stderr)

    if DRY:
        for p in nuevas[:10]:
            print("  + [%s] %s" % (p["expediente"], p["titulo"][:60]), file=sys.stderr)
        print("(DRY-RUN: no se escribio nada.)", file=sys.stderr)
        return
    if not nuevas:
        print("Nada nuevo.", file=sys.stderr)
        return

    # Insercion robusta: upsert ignorando duplicados; si un lote falla, fila por fila.
    LOTE = 100
    subidas = 0
    for i in range(0, len(nuevas), LOTE):
        lote = nuevas[i:i + LOTE]
        try:
            sb.table("leyes").upsert(lote, on_conflict="bill_id", ignore_duplicates=True).execute()
            subidas += len(lote)
        except Exception:
            for p in lote:
                try:
                    sb.table("leyes").upsert([p], on_conflict="bill_id", ignore_duplicates=True).execute()
                    subidas += 1
                except Exception as e2:
                    if not ("23505" in str(e2) or "duplicate" in str(e2).lower()):
                        print("  ! fallo %s: %s" % (p["bill_id"], e2), file=sys.stderr)
    print("Leyes nuevas del Senado insertadas: %d" % subidas, file=sys.stderr)


if __name__ == "__main__":
    main()
