# -*- coding: utf-8 -*-
# Pnyx - (c) 2026 Benjamin Kuchen. Obra protegida por la Ley 11.723 (Argentina).
# Distribuido bajo la Licencia Publica General Affero de GNU v3 (AGPL-3.0). Ver LICENSE.
"""
Pnyx · Senado desde Excel — DESCUBRIR LEYES NUEVAS DEL SENADO (manual)
---------------------------------------------------------------------
Reemplaza al obrero 5 (que ya no puede bajar el Excel solo). Vos bajas el
Excel a mano desde el sitio del Senado y este script lo lee y mete en
Supabase las leyes (tipo PL) que todavia no estaban.

Como bajar el Excel (una vez):
  1. Entra a  https://www.senado.gob.ar/parlamentario/parlamentaria/
  2. Abri "INGRESADOS POR MESA DE ENTRADAS", elegi el rango de fechas
     (desde 01/01/2026 hasta hoy) y busca.
  3. Descarga el Excel (ListadoDeExpedientes....xls) y guardalo en la carpeta
     PNYX con el nombre  senado.xls

Uso (PowerShell, desde PNYX):
  $env:SUPABASE_SERVICE_KEY="...."
  python senado_desde_excel.py                 -> usa senado.xls, solo inserta nuevas
  python senado_desde_excel.py otro.xls        -> usa ese archivo
  python senado_desde_excel.py --dry-run       -> muestra que haria, sin escribir

Solo INSERTA leyes nuevas (publicada=false, las decide la curaduria). A las
que ya existen NO las toca (no las despublica ni las pisa).

Despues corre:
  python senado_reporte.py     (para ver cuales bajar el texto)
"""

import os
import re
import sys

try:
    from python_calamine import CalamineWorkbook
except ImportError:
    print("Falta python-calamine:  pip install python-calamine", file=sys.stderr)
    sys.exit(1)
try:
    from supabase import create_client
except ImportError:
    print("Falta supabase:  pip install supabase", file=sys.stderr)
    sys.exit(1)

SUPABASE_URL = "https://ihmbhbhwlntsjqdavxge.supabase.co"
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
BASE = "https://www.senado.gob.ar"
ANIO = "26"
ORIGEN_TXT = {"S": "Senado", "PE": "Poder Ejecutivo", "CD": "Diputados"}

DRY = "--dry-run" in sys.argv
ARCHIVO = "senado.xls"
for a in sys.argv[1:]:
    if not a.startswith("-"):
        ARCHIVO = a
        break


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


def leer_excel(path):
    wb = CalamineWorkbook.from_path(path)
    return wb.get_sheet_by_index(0).to_python()


def bill_ids_existentes(sb):
    ids = set()
    desde = 0
    while True:
        r = (sb.table("leyes").select("bill_id")
             .eq("camara", "Senado")
             .range(desde, desde + 999).execute())
        filas = r.data or []
        for f in filas:
            ids.add(f["bill_id"])
        if len(filas) < 1000:
            break
        desde += 1000
    return ids


def main():
    if not SUPABASE_KEY:
        print('Falta la clave:  $env:SUPABASE_SERVICE_KEY="..." (service_role)', file=sys.stderr)
        sys.exit(1)
    if not os.path.exists(ARCHIVO):
        print("No encuentro '%s'. Baja el Excel del Senado y guardalo con ese nombre." % ARCHIVO, file=sys.stderr)
        sys.exit(1)

    try:
        filas = leer_excel(ARCHIVO)
    except Exception as e:
        print("No pude abrir el Excel (%s)." % e, file=sys.stderr)
        print("Asegurate de que sea el .xls bajado a mano del Senado (no una pagina HTML).", file=sys.stderr)
        sys.exit(1)

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

    print("Ya en Supabase: %d | Nuevas a insertar: %d" % (len(proyectos) - len(nuevas), len(nuevas)), file=sys.stderr)
    for p in nuevas[:8]:
        t = (p["titulo"][:60] + "...") if len(p["titulo"]) > 60 else p["titulo"]
        print("  + [%s] %s" % (p["expediente"], t), file=sys.stderr)
    if len(nuevas) > 8:
        print("  ... y %d mas" % (len(nuevas) - 8), file=sys.stderr)

    if DRY:
        print("\n(DRY-RUN: no se escribio nada en Supabase.)", file=sys.stderr)
        return
    if not nuevas:
        print("Nada nuevo para insertar.", file=sys.stderr)
        return

    # Insertamos con upsert ignorando duplicados: si alguna ya existe (por
    # desajustes de formato de bill_id), NO tira abajo el resto del lote.
    # Si aun asi un lote falla, reintentamos fila por fila.
    LOTE = 100
    subidas = 0
    dup = 0
    for i in range(0, len(nuevas), LOTE):
        lote = nuevas[i:i + LOTE]
        try:
            sb.table("leyes").upsert(lote, on_conflict="bill_id",
                                     ignore_duplicates=True).execute()
            subidas += len(lote)
        except Exception:
            # el lote fallo: probamos una por una para no perder las buenas
            for p in lote:
                try:
                    sb.table("leyes").upsert([p], on_conflict="bill_id",
                                             ignore_duplicates=True).execute()
                    subidas += 1
                except Exception as e2:
                    if "23505" in str(e2) or "duplicate" in str(e2).lower():
                        dup += 1
                    else:
                        print("  ! fallo con %s: %s" % (p["bill_id"], e2), file=sys.stderr)
    print("\nLeyes nuevas del Senado procesadas: %d (duplicadas ya existentes: %d)"
          % (subidas, dup), file=sys.stderr)
    print("Siguiente: python senado_reporte.py  (para bajar sus textos)", file=sys.stderr)


if __name__ == "__main__":
    main()
