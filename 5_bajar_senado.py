#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pnyx · Obrero 5 — Bajar leyes del Senado (incremental)
-------------------------------------------------------
Baja el Excel de proyectos del Senado (2 pasos: busqueda + descarga con
cookie de sesion), filtra los PROYECTOS DE LEY del año, y arma la lista.

Incremental: lee 'estado_nube.json' y marca cuales son nuevas (no estan
en Supabase). Conserva la lista completa en 'proyectos_senado.json' para
que los obreros siguientes sepan que existe.

Dependencia: pip install python-calamine
Uso:         python 5_bajar_senado.py
Salida:      proyectos_senado.json
"""

import json
import re
import sys
import os
import datetime
import urllib.request
import urllib.parse
import http.cookiejar

BASE = "https://www.senado.gob.ar"
URL_BUSQUEDA = BASE + "/parlamentario/parlamentaria/fechaMesa"
URL_EXCEL = BASE + "/micrositios/DatosAbiertosExpedientes/BusquedaMesaEntradas/XLS"
ARCHIVO_XLS = "senado.xls"
ESTADO = "estado_nube.json"
SALIDA = "proyectos_senado.json"
ANIO = "26"
DESDE = (1, 1, 2026)

CABECERAS = {"User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                            "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")}


def crear_navegador():
    cj = http.cookiejar.CookieJar()
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    op.addheaders = list(CABECERAS.items())
    return op


def bajar_excel_lleno():
    nav = crear_navegador()
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
    print("Paso 1: busqueda en el Senado...", file=sys.stderr)
    try:
        nav.open(urllib.request.Request(URL_BUSQUEDA, data=datos), timeout=90).read()
    except Exception as e:
        print("  (aviso: %s)" % e, file=sys.stderr)
    print("Paso 2: bajando Excel...", file=sys.stderr)
    try:
        contenido = nav.open(URL_EXCEL, timeout=120).read()
    except Exception as e:
        print("  No se pudo bajar (%s)." % e, file=sys.stderr)
        return False
    with open(ARCHIVO_XLS, "wb") as f:
        f.write(contenido)
    if len(contenido) < 20000:
        print("  Excel chico (%d bytes): la busqueda no quedo registrada." % len(contenido), file=sys.stderr)
        return False
    print("  Bajado: %d KB" % (len(contenido) // 1024), file=sys.stderr)
    return True


def abrir_excel(path):
    try:
        from python_calamine import CalamineWorkbook
        wb = CalamineWorkbook.from_path(path)
        return wb.get_sheet_by_index(0).to_python()
    except ImportError:
        print("Falta python-calamine. Instalalo con:  pip install python-calamine", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print("No pude abrir el Excel (%s)." % e, file=sys.stderr)
        sys.exit(1)


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


def main():
    ok = bajar_excel_lleno()
    if not ok and not (os.path.exists(ARCHIVO_XLS) and os.path.getsize(ARCHIVO_XLS) > 20000):
        print("\nNo consegui el Excel. Bajalo a mano, guardalo como 'senado.xls' y reintenta.", file=sys.stderr)
        sys.exit(1)

    filas = abrir_excel(ARCHIVO_XLS)
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
            "origen": {"S": "Senado", "PE": "Poder Ejecutivo", "CD": "Diputados"}.get(origen, origen),
            "tipo": "LEY",
            "fecha": fecha,
            "url_lectura": "%s/parlamentario/comisiones/verExp/%s.%s/%s/PL" % (BASE, num, ANIO, origen),
            "oracion_ia": None,
            "resumen_ia": None,
            "publicado": False,
        })

    proyectos.sort(key=lambda p: p.get("fecha", ""), reverse=True)

    # Estado de la nube: detectar nuevas
    estado = {}
    if os.path.exists(ESTADO):
        with open(ESTADO, encoding="utf-8") as f:
            estado = json.load(f)
    nuevas = [p for p in proyectos if p["bill_id"] not in estado]

    with open(SALIDA, "w", encoding="utf-8") as f:
        json.dump(proyectos, f, ensure_ascii=False, indent=2)

    print("\nProyectos de ley del Senado (%s): %d" % (ANIO, len(proyectos)), file=sys.stderr)
    print("Ya en Supabase: %d | Nuevas: %d" % (len(proyectos) - len(nuevas), len(nuevas)), file=sys.stderr)
    print("Guardado en %s" % SALIDA, file=sys.stderr)
    if nuevas:
        for p in nuevas[:5]:
            t = (p["titulo"][:60] + "...") if len(p["titulo"]) > 60 else p["titulo"]
            print("  + [%s] %s" % (p["expediente"], t), file=sys.stderr)


if __name__ == "__main__":
    main()
