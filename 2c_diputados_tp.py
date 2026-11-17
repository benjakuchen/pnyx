#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Pnyx - (c) 2026 Benjamin Kuchen. Obra protegida por la Ley 11.723 (Argentina).
# Distribuido bajo la Licencia Publica General Affero de GNU v3 (AGPL-3.0). Ver LICENSE.
"""
Pnyx · Obrero 2c — Diputados desde TRAMITES PARLAMENTARIOS
----------------------------------------------------------
En noviembre de 2026 la HCDN rehizo el sitio y cerro el buscador de
proyectos ("Acceso solo desde Intranet"). Pero la seccion de TRAMITES
PARLAMENTARIOS sigue publica y al dia. Este obrero la lee:

  1. Baja la tabla indice de Tramites Parlamentarios (lista de TPs con
     fecha y link).
  2. Por cada TP reciente, baja su pagina y extrae los proyectos.
  3. Filtra SOLO los "DE LEY" (descarta resolucion/declaracion).
  4. Cruza por EXPEDIENTE con la base y sube los que falten.

Ojo con el bill_id: esta fuente NO da el numero HCDN<id> (lo daba el
buscador viejo). Usamos el EXPEDIENTE como clave e id: bill_id = el
expediente (ej. "6187-D-2026"). El cruce para no duplicar es por
'expediente'. Si el buscador vuelve algun dia, convivira por expediente.

El PDF de cada proyecto queda guardado como 'pdf_url' para que el
Obrero 3 le baje el texto.

Uso (PowerShell):
  $env:SUPABASE_SERVICE_KEY="..."
  python 2c_diputados_tp.py            -> TPs de los ultimos 45 dias
  python 2c_diputados_tp.py 90         -> ultimos 90 dias
  python 2c_diputados_tp.py --dry-run  -> muestra lo que traeria, sin subir

Requisitos: pip install requests
"""

import os
import re
import sys
import time
import html as _html
from datetime import date, datetime, timedelta

import requests

SUPABASE_URL = "https://ihmbhbhwlntsjqdavxge.supabase.co"
SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")

BASE = "https://www.hcdn.gob.ar"
INDICE = BASE + "/secparl/dsecretaria/s_t_parlamentario/tramites-parlamentarios.html"
TP_URL = BASE + "/_q/%s.html"
PDF_URL = BASE + "/_ext/rest.hcdn.gob.ar/web/tramites-parlamentarios/render/adjunto/%s.pdf"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
HEADERS = {"User-Agent": UA}
PAUSA = 0.8


def _get(url):
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    r.encoding = r.apparent_encoding or "utf-8"
    return r.text


# ---------- Indice: lista de TPs (hash, numero, fecha, rango de expedientes) ----------
def _rango_dip(fila_tr):
    """Del <tr> de un TP, saca (exp_bajo, exp_alto) de la columna Diputados."""
    m = re.search(r'(\d+)\s+al\s+(\d+)-D-\d{4}', fila_tr)
    if m:
        return int(m.group(1)), int(m.group(2))
    m = re.search(r'(\d+)-D-\d{4}', fila_tr)
    if m:
        return int(m.group(1)), int(m.group(1))
    return None, None


def traer_indice():
    """Lee la tabla indice (1 request liviano). Devuelve, por cada TP: hash,
    numero, fecha y el rango de expedientes de Diputados que contiene. Con eso
    el obrero decide QUE TPs abrir, sin bajar nada mas si no hace falta."""
    txt = _get(INDICE)
    filas = re.findall(r'<tr align="center">(.*?)</tr>', txt, re.S)
    out = []
    for fila in filas:
        mnum = re.search(r'/_q/([0-9a-f]+)\.html" target="_self">(\d+)</a>', fila)
        if not mnum:
            continue
        mfec = re.search(r'(\d{2}/\d{2}/\d{4})', fila)
        f = mfec.group(1) if mfec else None
        try:
            fdt = datetime.strptime(f, "%d/%m/%Y").date() if f else None
        except Exception:
            fdt = None
        bajo, alto = _rango_dip(fila)
        out.append({"hash": mnum.group(1), "num": int(mnum.group(2)),
                    "fecha": f, "fecha_dt": fdt, "exp_bajo": bajo, "exp_alto": alto})
    return out


def _num_exp(exp):
    """'6187-D-2026' -> 6187 (para comparar). None si no matchea."""
    m = re.match(r'(\d+)-D-\d{4}', exp or "")
    return int(m.group(1)) if m else None


def max_exp_en_base():
    """El numero de expediente D mas alto que ya esta en la base (de 2026)."""
    headers = {"apikey": SERVICE_KEY, "Authorization": "Bearer " + SERVICE_KEY}
    url = (SUPABASE_URL + "/rest/v1/leyes?select=expediente&camara=eq.Diputados"
           "&expediente=like.*-D-2026&order=expediente.desc&limit=1000")
    try:
        r = requests.get(url, headers=headers, timeout=30)
        r.raise_for_status()
        nums = [_num_exp(x.get("expediente")) for x in r.json()]
        nums = [n for n in nums if n]
        return max(nums) if nums else 0
    except Exception:
        return 0


# ---------- Detalle de un TP: proyectos DE LEY ----------
def parse_tp(txt):
    """Devuelve la lista de proyectos del TP (todos los tipos)."""
    out = []
    parras = re.findall(r'<p style="text-transform: uppercase[^>]*>(.*?)</p>', txt, re.S)
    for p in parras:
        mtipo = re.search(r'</strong>\s*(DE LEY|DE RESOLUCIÓN|DE DECLARACIÓN)\.', p)
        tipo = mtipo.group(1) if mtipo else None
        # expediente + hash del pdf
        mexp = re.search(r'adjunto/([0-9a-f]+)\.pdf"[^>]*>([0-9]+-[A-Z]+-[0-9]+)</a>', p)
        if mexp:
            pdfhash, exp = mexp.group(1), mexp.group(2)
        else:
            m2 = re.search(r'\(([0-9]+-[A-Z]+-[0-9]+)\)', p)
            exp = m2.group(1) if m2 else None
            pdfhash = None
        # firmantes: los <strong> antes del tipo (quitando el que lleva "DE LEY:")
        firmantes = ""
        mfir = re.match(r'(.*?):\s*</strong>\s*(?:DE LEY|DE RESOLUCIÓN|DE DECLARACIÓN)', p, re.S)
        if mfir:
            crudo = re.sub(r'</?strong>', '', mfir.group(1))
            firmantes = _html.unescape(re.sub(r'\s+', ' ', crudo)).strip(' ;')
        # titulo: entre el tipo y el "(expediente)"
        mtit = re.search(r'(?:DE LEY|DE RESOLUCIÓN|DE DECLARACIÓN)\.\s*(.*?)\s*\(', p, re.S)
        titulo = _html.unescape(re.sub(r'<[^>]+>', '', re.sub(r'\s+', ' ', mtit.group(1)))).strip() if mtit else ""
        retirado = "PROYECTO RETIRADO" in p.upper()
        if exp:
            out.append({"tipo": tipo, "exp": exp, "pdfhash": pdfhash,
                        "firmantes": firmantes, "titulo": titulo, "retirado": retirado})
    return out


def _cap(s):
    # "DEL CAÑO, NICOLAS; BREGMAN, MYRIAM" -> dejar tal cual (ya viene de la fuente)
    return s


# ---------- Supabase ----------
def expedientes_en_base():
    headers = {"apikey": SERVICE_KEY, "Authorization": "Bearer " + SERVICE_KEY}
    exps = set()
    offset = 0
    while True:
        url = (SUPABASE_URL + "/rest/v1/leyes?select=expediente&camara=eq.Diputados"
               "&limit=1000&offset=" + str(offset))
        r = requests.get(url, headers=headers, timeout=30)
        r.raise_for_status()
        parte = r.json()
        for x in parte:
            if x.get("expediente"):
                exps.add(x["expediente"].strip())
        if len(parte) < 1000:
            break
        offset += 1000
    return exps


def subir(nuevos):
    headers = {"apikey": SERVICE_KEY, "Authorization": "Bearer " + SERVICE_KEY,
               "Content-Type": "application/json", "Prefer": "resolution=merge-duplicates"}
    filas = []
    for p in nuevos:
        filas.append({
            "bill_id": p["exp"],          # el expediente ES el id (no hay HCDN<id> en esta fuente)
            "titulo": p["titulo"],
            "camara": "Diputados",
            "origen": "Diputados",
            "expediente": p["exp"],
            "autor": p["firmantes"] or None,
            "fecha": p["fecha_iso"],
            "pdf_url": p["pdf_url"],       # para que el Obrero 3 baje el texto
            "publicada": False,
        })
    LOTE = 100
    for i in range(0, len(filas), LOTE):
        url = SUPABASE_URL + "/rest/v1/leyes?on_conflict=bill_id"
        r = requests.post(url, headers=headers, json=filas[i:i + LOTE], timeout=30)
        if r.status_code >= 300:
            print("  ERROR lote %d: %s %s" % (i // LOTE, r.status_code, r.text[:300]), file=sys.stderr)
            r.raise_for_status()
        time.sleep(0.3)


def main():
    dry = "--dry-run" in sys.argv
    dias = 45
    for a in sys.argv[1:]:
        if a.isdigit():
            dias = int(a)

    if not SERVICE_KEY and not dry:
        print('Falta la clave:  $env:SUPABASE_SERVICE_KEY="..."', file=sys.stderr)
        sys.exit(1)

    limite = date.today() - timedelta(days=dias)

    # PASO 1 (liviano): leer SOLO el indice. 1 request.
    try:
        tps = traer_indice()
    except Exception as e:
        print("  ! No pude leer el indice de Tramites Parlamentarios: %s" % e, file=sys.stderr)
        sys.exit(1)

    tope_tabla = max([t["exp_alto"] for t in tps if t["exp_alto"]] or [0])
    print("Expediente D mas alto en la tabla: %s" % (tope_tabla or "?"), file=sys.stderr)

    # PASO 2: comparar con la base. Si ya tenemos todo, NO abrimos ningun TP.
    if not dry:
        tope_base = max_exp_en_base()
        print("Expediente D mas alto en la base: %s" % tope_base, file=sys.stderr)
        if tope_tabla and tope_base and tope_tabla <= tope_base:
            print("No hay expedientes nuevos (la base ya esta al dia). No se abre ningun TP.", file=sys.stderr)
            return
    else:
        tope_base = 0  # en dry-run, revisamos todos los del rango de fechas

    # PASO 3: abrir SOLO los TPs que contienen expedientes por encima del tope
    # de la base (y dentro del rango de fechas). El resto no se toca.
    recientes = [t for t in tps
                 if t["fecha_dt"] and t["fecha_dt"] >= limite
                 and (dry or not tope_base or (t["exp_alto"] and t["exp_alto"] > tope_base))]
    print("TPs a abrir: %d (de %d en la tabla)" % (len(recientes), len(tps)), file=sys.stderr)
    if not recientes:
        print("Nada que abrir en el rango.", file=sys.stderr)
        return

    leyes = []
    for t in recientes:
        try:
            html_tp = _get(TP_URL % t["hash"])
        except Exception as e:
            print("  ! TP %d: no se pudo bajar (%s)" % (t["num"], e), file=sys.stderr)
            continue
        proyectos = parse_tp(html_tp)
        deley = [p for p in proyectos if p["tipo"] == "DE LEY" and not p["retirado"] and p["pdfhash"]]
        for p in deley:
            p["fecha_iso"] = t["fecha_dt"].isoformat()
            p["pdf_url"] = PDF_URL % p["pdfhash"]
            leyes.append(p)
        print("  TP %d (%s): %d leyes de %d proyectos" % (t["num"], t["fecha"], len(deley), len(proyectos)), file=sys.stderr)
        time.sleep(PAUSA)

    # dedup por expediente
    vistos = {}
    for p in leyes:
        vistos[p["exp"]] = p
    leyes = list(vistos.values())
    print("\nTotal LEYES (de ley, con PDF) en el rango: %d" % len(leyes), file=sys.stderr)

    if dry:
        print("\n(DRY-RUN: no se consulto la base ni se subio nada.)", file=sys.stderr)
        for p in leyes[:20]:
            print("  %s  %s  %s" % (p["fecha_iso"], p["exp"], p["titulo"][:50]), file=sys.stderr)
        if len(leyes) > 20:
            print("  ... y %d mas" % (len(leyes) - 20), file=sys.stderr)
        return

    print("Consultando expedientes ya en la base...", file=sys.stderr)
    en_base = expedientes_en_base()
    nuevos = [p for p in leyes if p["exp"] not in en_base]
    print("Ya en la base: %d | NUEVOS a subir: %d" % (len(leyes) - len(nuevos), len(nuevos)), file=sys.stderr)

    if not nuevos:
        print("No hay leyes nuevas.", file=sys.stderr)
        return

    for p in nuevos[:20]:
        print("  + %s  %s  %s" % (p["fecha_iso"], p["exp"], p["titulo"][:55]), file=sys.stderr)
    if len(nuevos) > 20:
        print("  ... y %d mas" % (len(nuevos) - 20), file=sys.stderr)

    subir(nuevos)
    print("\nListo: %d leyes nuevas subidas a Supabase (sin texto aun)." % len(nuevos), file=sys.stderr)
    print("(Corre el Obrero 3 para bajarles el texto, y el 1 para refrescar estado.)", file=sys.stderr)


if __name__ == "__main__":
    main()
