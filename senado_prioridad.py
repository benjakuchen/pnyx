#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Pnyx - (c) 2026 Benjamin Kuchen. Obra protegida por la Ley 11.723 (Argentina).
# Distribuido bajo la Licencia Publica General Affero de GNU v3 (AGPL-3.0). Ver LICENSE.
r"""
Pnyx · Senado por prioridad de prensa — QUE PDF BAJAR PRIMERO
------------------------------------------------------------
Como el Senado se baja a mano, este obrero te dice CUALES conviene bajar
primero: las leyes del Senado SIN texto que mas estan sonando en los medios.

Reusa el radar de prensa del obrero 8: saca palabras clave del titulo de
cada ley y las cruza con los titulares del dia (RSS de varios diarios).
Ordena de mayor a menor coincidencia y escribe:
  senado_prioridad.txt  (para leer y copiar los links)
  senado_prioridad.csv  (para abrir con Excel)

Las que no aparecen en la prensa van al final (por numero de expediente).

Requiere:  $env:SUPABASE_SERVICE_KEY   +   pip install feedparser supabase
Uso:
  python senado_prioridad.py            todas las del Senado sin texto
  python senado_prioridad.py --solo-prensa   solo las que tienen alguna mencion
"""

import csv
import os
import sys

# Reusamos las fuentes RSS y las funciones del obrero 8 (un solo lugar para
# mantener los diarios y las palabras clave).
try:
    import importlib
    prensa = importlib.import_module("8_prensa")
except Exception as e:
    print("No pude importar 8_prensa.py (tiene que estar en la misma carpeta): %s" % e, file=sys.stderr)
    sys.exit(1)

try:
    from supabase import create_client
except ImportError:
    print("Falta supabase:  pip install supabase", file=sys.stderr)
    sys.exit(1)

SUPABASE_URL = "https://ihmbhbhwlntsjqdavxge.supabase.co"
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
BASE = "https://www.senado.gob.ar"
ORIGEN_COD = {"Senado": "S", "Poder Ejecutivo": "PE", "Diputados": "CD"}
SOLO_PRENSA = "--solo-prensa" in sys.argv
MIN_COINCIDENCIAS = 3   # palabras en comun con un titular para contar como "mencion"


def ficha_url(expediente, origen):
    if not expediente or "/" not in expediente:
        return ""
    num, anio = expediente.split("/", 1)
    cod = ORIGEN_COD.get(origen or "", "S")
    return "%s/parlamentario/comisiones/verExp/%s.%s/%s/PL" % (BASE, num, anio, cod)


def traer_senado_sin_texto(sb):
    filas, desde = [], 0
    while True:
        r = (sb.table("leyes")
             .select("bill_id,expediente,origen,titulo,oracion_ia,publicada")
             .eq("camara", "Senado")
             .is_("texto_oficial", "null")
             .or_("texto_escaneado.is.null,texto_escaneado.eq.false")
             .range(desde, desde + 999).execute())
        d = r.data or []
        filas += d
        if len(d) < 1000:
            break
        desde += 1000
    return filas


def puntuar(ley, titulares):
    """Cuenta en cuantos diarios distintos aparece la ley (>=MIN palabras)."""
    claves = prensa.palabras_clave(ley.get("titulo"), ley.get("oracion_ia"))
    if not claves:
        return 0, 0, set()
    diarios = set()
    total_hits = 0
    for diario, texto in titulares:
        comunes = sum(1 for c in claves if c in texto)
        if comunes >= MIN_COINCIDENCIAS:
            diarios.add(diario)
            total_hits += 1
    return len(diarios), total_hits, diarios


def main():
    if not SUPABASE_KEY:
        print('Falta la clave:  $env:SUPABASE_SERVICE_KEY="..."', file=sys.stderr)
        sys.exit(1)
    sb = create_client(SUPABASE_URL, SUPABASE_KEY)

    print("Leyes del Senado sin texto...", file=sys.stderr)
    leyes = traer_senado_sin_texto(sb)
    print("  %d sin texto." % len(leyes), file=sys.stderr)
    if not leyes:
        print("No hay leyes del Senado sin texto. Nada para priorizar.", file=sys.stderr)
        return

    print("Bajando titulares de los diarios...", file=sys.stderr)
    titulares = prensa.cargar_titulares()
    print("  %d titulares en total.\n" % len(titulares), file=sys.stderr)

    filas = []
    for l in leyes:
        n_diarios, hits, diarios = puntuar(l, titulares)
        filas.append({
            "bill_id": l.get("bill_id"),
            "expediente": l.get("expediente"),
            "origen": l.get("origen"),
            "titulo": l.get("titulo") or "",
            "publicada": l.get("publicada"),
            "n_diarios": n_diarios,
            "hits": hits,
            "diarios": ", ".join(sorted(diarios)),
            "link": ficha_url(l.get("expediente"), l.get("origen")),
        })

    # Orden: primero las que mas suenan (n_diarios, luego hits); despues por expediente.
    def clave_exp(f):
        try:
            n, a = (f.get("expediente") or "0/0").split("/")
            return (int(a), int(n))
        except Exception:
            return (0, 0)
    filas.sort(key=lambda f: (f["n_diarios"], f["hits"], clave_exp(f)), reverse=True)

    con_prensa = [f for f in filas if f["n_diarios"] > 0]
    if SOLO_PRENSA:
        filas = con_prensa

    # CSV
    with open("senado_prioridad.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["prioridad_diarios", "hits", "diarios", "bill_id", "expediente",
                    "publicada", "titulo", "link_ficha", "nombre_para_guardar"])
        for r in filas:
            w.writerow([r["n_diarios"], r["hits"], r["diarios"], r["bill_id"], r["expediente"],
                        "si" if r["publicada"] else "no", r["titulo"][:200], r["link"],
                        "%s.pdf" % r["bill_id"]])

    # TXT legible
    with open("senado_prioridad.txt", "w", encoding="utf-8") as f:
        f.write("SENADO — QUE BAJAR PRIMERO (por prensa) — %d sin texto, %d con mencion\n"
                % (len(filas), len(con_prensa)))
        f.write("Las de arriba son las que mas estan sonando en los medios hoy.\n")
        f.write("Baja el PDF y guardalo en senado_pdfs\\ con el nombre indicado.\n")
        f.write("=" * 72 + "\n\n")
        for r in filas:
            estrella = ("  ⭐ x%d diarios" % r["n_diarios"]) if r["n_diarios"] else "  (sin prensa)"
            f.write("Guardar como: %s.pdf%s\n" % (r["bill_id"], estrella))
            if r["diarios"]:
                f.write("  En: %s\n" % r["diarios"])
            f.write("  Exp: %s (%s)%s\n" % (r["expediente"], r["origen"] or "s/o",
                                            "  [PUBLICADA]" if r["publicada"] else ""))
            f.write("  Titulo: %s\n" % (r["titulo"][:150]))
            f.write("  Ficha:  %s\n\n" % r["link"])

    print("=== TOP por prensa ===", file=sys.stderr)
    for r in filas[:10]:
        if r["n_diarios"]:
            print("  x%d  %s  %s" % (r["n_diarios"], r["bill_id"], r["titulo"][:50]), file=sys.stderr)
    print("\nEscribí: senado_prioridad.txt y senado_prioridad.csv", file=sys.stderr)
    print("Con prensa: %d de %d. Baja esas primero." % (len(con_prensa), len(filas)), file=sys.stderr)


if __name__ == "__main__":
    main()
