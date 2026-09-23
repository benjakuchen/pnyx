#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Diagnostico: baja lo que devuelva el Senado y lo guarda SIEMPRE para inspeccionar.
import datetime, http.cookiejar, urllib.parse, urllib.request, sys

BASE = "https://www.senado.gob.ar"
URL_BUSQUEDA = BASE + "/parlamentario/parlamentaria/fechaMesa"
URL_EXCEL = BASE + "/micrositios/DatosAbiertosExpedientes/BusquedaMesaEntradas/XLS"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

cj = http.cookiejar.CookieJar()
nav = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
nav.addheaders = [("User-Agent", UA)]
hoy = datetime.date.today()

print("1) home...", file=sys.stderr)
try:
    nav.open(BASE + "/parlamentario/parlamentaria/", timeout=60).read()
except Exception as e:
    print("   home aviso:", e, file=sys.stderr)

form = {
    "busqueda_proyectos[fechaDesdeMesa][day]": 1,
    "busqueda_proyectos[fechaDesdeMesa][month]": 1,
    "busqueda_proyectos[fechaDesdeMesa][year]": 2026,
    "busqueda_proyectos[fechaHastaMesa][day]": hoy.day,
    "busqueda_proyectos[fechaHastaMesa][month]": hoy.month,
    "busqueda_proyectos[fechaHastaMesa][year]": hoy.year,
}
print("2) busqueda POST...", file=sys.stderr)
try:
    r = nav.open(urllib.request.Request(URL_BUSQUEDA, data=urllib.parse.urlencode(form).encode()), timeout=90)
    print("   busqueda HTTP", r.status, "url final:", r.geturl(), file=sys.stderr)
except Exception as e:
    print("   busqueda aviso:", e, file=sys.stderr)

print("3) descarga XLS...", file=sys.stderr)
try:
    r = nav.open(URL_EXCEL, timeout=120)
    data = r.read()
    print("   XLS HTTP", r.status, "content-type:", r.headers.get("Content-Type"), file=sys.stderr)
    print("   tamaño:", len(data), file=sys.stderr)
    print("   primeros bytes:", data[:120], file=sys.stderr)
    open("senado_debug.bin", "wb").write(data)
    print("   guardado en senado_debug.bin", file=sys.stderr)
except Exception as e:
    print("   descarga error:", e, file=sys.stderr)
