#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Pnyx - (c) 2026 Benjamin Kuchen. Obra protegida por la Ley 11.723 (Argentina).
# Distribuido bajo la Licencia Publica General Affero de GNU v3 (AGPL-3.0). Ver LICENSE.
"""
Pnyx · Obrero 2b — Diputados DESDE LA WEB (complemento del CSV)
----------------------------------------------------------------
El dataset de Datos Abiertos (obrero 2) suele venir atrasado varias
semanas. Este obrero cubre ESE hueco: consulta el buscador web de
Diputados (POST a resultado.html), que esta al dia, y trae los
proyectos de LEY del rango de fechas pedido. Sube a Supabase los que
todavia no esten (no pisa texto ni resumen ya cargados).

NO reemplaza al obrero 2 (el CSV sigue siendo la fuente principal y
completa). Este solo agrega el ultimo tramo que el CSV aun no tiene.

Uso (PowerShell):
  $env:SUPABASE_SERVICE_KEY="..."
  python 2b_diputados_web.py                 -> ultimos 30 dias
  python 2b_diputados_web.py 60              -> ultimos 60 dias
  python 2b_diputados_web.py 06/10/2026 29/10/2026   -> rango exacto
  python 2b_diputados_web.py --dry-run       -> muestra lo que traeria, sin subir

Requisitos: pip install requests
"""

import os
import re
import sys
import time
import html as _html
from datetime import date, timedelta

import requests

SUPABASE_URL = "https://ihmbhbhwlntsjqdavxge.supabase.co"
SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")

BUSCADOR = "https://www.hcdn.gob.ar/proyectos/resultado.html"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
HEADERS = {
    "User-Agent": UA,
    "Content-Type": "application/x-www-form-urlencoded",
    "Referer": "https://www.hcdn.gob.ar/proyectos/",
    "Origin": "https://www.hcdn.gob.ar",
}
PAUSA = 1.0
MAX_PAGINAS = 40   # tope de seguridad (100 x 40 = 4000 proyectos)


# ---------- PARSER (validado contra el HTML real) ----------
def parse_wrappers(html_text):
    bloques = re.split(r'<div class="resultado_wrapper">', html_text)[1:]
    out = []
    for b in bloques:
        m = re.search(r'<h4>(.*?)</h4>', b, re.S)
        tipo = _html.unescape(m.group(1)).strip() if m else ""
        m = re.search(r'Expediente\s+\w+:\s*<strong>([^<]+)</strong>', b)
        exp = m.group(1).strip() if m else None
        m = re.search(r'Iniciado en:\s*<strong>([^<]+)</strong>', b)
        origen = m.group(1).strip() if m else ""
        m = re.search(r'Fecha:\s*<strong>([^<]+)</strong>', b)
        fecha = m.group(1).strip() if m else ""
        m = re.search(r'<div class="dp-texto">(.*?)</div>', b, re.S)
        titulo = _html.unescape(re.sub(r'\s+', ' ', m.group(1))).strip() if m else ""
        m = re.search(r'<tbody>\s*<tr>\s*<td>([^<]+)</td>', b)
        firmante = m.group(1).strip() if m else ""
        m = re.search(r'detalle_tp_adjunto/index\.html\?id=(\d+)', b)
        doc_id = m.group(1) if m else None
        out.append(dict(tipo=tipo, exp=exp, origen=origen, fecha=fecha,
                        titulo=titulo, firmante=firmante, doc_id=doc_id))
    return out


def ddmmyyyy_a_iso(f):
    m = re.match(r'(\d{2})/(\d{2})/(\d{4})', f or "")
    return "%s-%s-%s" % (m.group(3), m.group(2), m.group(1)) if m else None


def bill_id_de(p):
    """La base usa bill_id = 'HCDN<id>' donde <id> es el PROYECTO_ID de HCDN,
    que coincide con el id del documento ('...index.html?id=295672').
    El parser ya extrae ese id como doc_id. Verificado contra el CSV:
    0007-S-2025 -> HCDN282431, etc. Asi el bill_id calza con el del obrero 2
    y NO se duplica."""
    return ("HCDN" + p["doc_id"]) if p.get("doc_id") else None


# ---------- Descarga de una pagina del buscador ----------
def traer_pagina(desde, hasta, pagina):
    data = {
        "zezion": "true", "strTipo": "ley",
        "strNumExp": "", "strNumExpOrig": "", "strNumExpAnio": "",
        "strCamIni": "", "strFirmante": "", "strComision": "",
        "strFechaInicio": desde, "strFechaFin": hasta,
        "strPalabras": "", "strOrdenDelDiaNro": "", "strOrdenDelDiaAnio": "",
        "strLey": "",
        "strMostrarTramites": "on", "strMostrarDictamenes": "on",
        "strMostrarFirmantes": "on", "strMostrarComisiones": "on",
        "strCantPagina": "100",
    }
    url = BUSCADOR if pagina == 1 else (BUSCADOR + "?pagina=%d" % pagina)
    r = requests.post(url, headers=HEADERS, data=data, timeout=60)
    r.raise_for_status()
    r.encoding = r.apparent_encoding or "utf-8"
    return r.text


# ---------- Supabase ----------
def bill_ids_en_base():
    """Set de bill_id (HCDN...) ya en la base, para no duplicar."""
    headers = {"apikey": SERVICE_KEY, "Authorization": "Bearer " + SERVICE_KEY}
    ids = set()
    offset = 0
    while True:
        url = (SUPABASE_URL + "/rest/v1/leyes?select=bill_id"
               "&limit=1000&offset=" + str(offset))
        r = requests.get(url, headers=headers, timeout=30)
        r.raise_for_status()
        parte = r.json()
        for x in parte:
            if x.get("bill_id"):
                ids.add(x["bill_id"].strip())
        if len(parte) < 1000:
            break
        offset += 1000
    return ids


def subir(nuevos):
    headers = {"apikey": SERVICE_KEY, "Authorization": "Bearer " + SERVICE_KEY,
               "Content-Type": "application/json", "Prefer": "resolution=merge-duplicates"}
    filas = []
    for p in nuevos:
        filas.append({
            "bill_id": bill_id_de(p),          # HCDN<doc_id>, igual que el obrero 2
            "titulo": p["titulo"],
            "camara": "Diputados",
            "origen": p["origen"] or "Diputados",
            "expediente": p["exp"],
            "autor": p["firmante"] or None,
            "fecha": ddmmyyyy_a_iso(p["fecha"]),
            "publicada": False,
        })
    LOTE = 100
    for i in range(0, len(filas), LOTE):
        url = SUPABASE_URL + "/rest/v1/leyes?on_conflict=bill_id"
        r = requests.post(url, headers=headers, json=filas[i:i + LOTE], timeout=30)
        if r.status_code >= 300:
            print("  ERROR lote %d: %s %s" % (i // LOTE, r.status_code, r.text[:200]), file=sys.stderr)
            r.raise_for_status()
        time.sleep(0.3)


def main():
    dry = "--dry-run" in sys.argv
    args = [a for a in sys.argv[1:] if a != "--dry-run"]

    # Rango de fechas: dos args DD/MM/YYYY, o un numero de dias, o 30 por defecto.
    fechas = [a for a in args if re.match(r'\d{2}/\d{2}/\d{4}', a)]
    if len(fechas) == 2:
        desde, hasta = fechas[0], fechas[1]
    else:
        dias = 30
        for a in args:
            if a.isdigit():
                dias = int(a)
        hoy = date.today()
        desde = (hoy - timedelta(days=dias)).strftime("%d/%m/%Y")
        hasta = hoy.strftime("%d/%m/%Y")

    if not SERVICE_KEY and not dry:
        print('Falta la clave:  $env:SUPABASE_SERVICE_KEY="..."', file=sys.stderr)
        sys.exit(1)

    print("Buscando LEYES en Diputados (web) del %s al %s..." % (desde, hasta), file=sys.stderr)

    f_desde = ddmmyyyy_a_iso(desde)
    f_hasta = ddmmyyyy_a_iso(hasta)

    def en_rango(p):
        fi = ddmmyyyy_a_iso(p.get("fecha"))
        return bool(fi) and (f_desde <= fi <= f_hasta)

    # Recorrer paginas. OJO: el servidor a veces ignora el filtro de fecha al
    # paginar y devuelve de mas, asi que cortamos nosotros: los resultados
    # vienen de mas NUEVO a mas VIEJO; cuando una pagina entera ya quedo por
    # DEBAJO del rango (todas mas viejas que 'desde'), paramos.
    todos = []
    for pagina in range(1, MAX_PAGINAS + 1):
        try:
            html_text = traer_pagina(desde, hasta, pagina)
        except Exception as e:
            print("  ! Error en pagina %d: %s" % (pagina, e), file=sys.stderr)
            break
        filas = parse_wrappers(html_text)
        if not filas:
            break
        en = [p for p in filas if en_rango(p)]
        todos.extend(en)
        # fecha mas vieja de la pagina (ISO) para decidir el corte
        fechas_pag = [ddmmyyyy_a_iso(p.get("fecha")) for p in filas if ddmmyyyy_a_iso(p.get("fecha"))]
        mas_vieja = min(fechas_pag) if fechas_pag else None
        print("  pagina %d: %d en rango (de %d)" % (pagina, len(en), len(filas)), file=sys.stderr)
        # cortar si ya pasamos el limite inferior o si no se lleno la pagina
        if (mas_vieja and mas_vieja < f_desde) or len(filas) < 100:
            break
        time.sleep(PAUSA)

    # Filtrar SOLO leyes de verdad, con expediente Y con doc_id (para el bill_id).
    leyes = [p for p in todos if "LEY" in p["tipo"].upper() and p["exp"] and p.get("doc_id")]
    # dedup por bill_id dentro de lo bajado
    vistos = {}
    for p in leyes:
        vistos[bill_id_de(p)] = p
    leyes = list(vistos.values())
    sin_doc = sum(1 for p in todos if "LEY" in p["tipo"].upper() and p["exp"] and not p.get("doc_id"))
    print("\nTotal LEYES traidas de la web: %d%s" % (
        len(leyes), (" (%d sin documento, se saltean)" % sin_doc) if sin_doc else ""), file=sys.stderr)

    if dry:
        print("\n(DRY-RUN: no se consulto la base ni se subio nada.)", file=sys.stderr)
        for p in leyes[:15]:
            print("  %s  %s  (%s)  %s" % (p["fecha"], p["exp"], bill_id_de(p), p["titulo"][:45]), file=sys.stderr)
        if len(leyes) > 15:
            print("  ... y %d mas" % (len(leyes) - 15), file=sys.stderr)
        return

    # Cruzar con la base por bill_id: subir solo lo que no esta.
    print("Consultando bill_id ya en la base...", file=sys.stderr)
    en_base = bill_ids_en_base()
    nuevos = [p for p in leyes if bill_id_de(p) not in en_base]
    print("Ya en la base: %d | NUEVOS a subir: %d" % (len(leyes) - len(nuevos), len(nuevos)), file=sys.stderr)

    if not nuevos:
        print("No hay leyes nuevas de la web. (El CSV o una corrida previa ya las tiene.)", file=sys.stderr)
        return

    for p in nuevos[:20]:
        print("  + %s  %s  %s" % (p["fecha"], p["exp"], p["titulo"][:55]), file=sys.stderr)
    if len(nuevos) > 20:
        print("  ... y %d mas" % (len(nuevos) - 20), file=sys.stderr)
    print("  (bill_id = HCDN<id del documento>, mismo formato que el obrero 2)", file=sys.stderr)

    subir(nuevos)
    print("\nListo: %d leyes nuevas subidas a Supabase (sin texto aun)." % len(nuevos), file=sys.stderr)
    print("(Corre el Obrero 3 para bajarles el texto, y el 1 para refrescar estado.)", file=sys.stderr)


if __name__ == "__main__":
    main()
