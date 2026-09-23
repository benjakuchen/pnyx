# -*- coding: utf-8 -*-
# Pnyx - (c) 2026 Benjamin Kuchen. Obra protegida por la Ley 11.723 (Argentina).
# Distribuido bajo la Licencia Publica General Affero de GNU v3 (AGPL-3.0). Ver LICENSE.
"""
Pnyx · Reporte Senado — QUE FALTA BAJAR A MANO
----------------------------------------------
Lee Supabase y arma la lista de leyes del Senado que NO tienen texto todavia.
Para cada una te da el link a la ficha oficial del Senado, donde vas a poder
descargar el PDF con un clic.

Que hace:
  - Consulta la tabla 'leyes' (camara = Senado, sin texto_oficial).
  - Arma el link a la ficha de cada expediente.
  - Escribe dos archivos: senado_faltantes.csv (para Excel) y
    senado_faltantes.txt (para leer rapido).

Uso (PowerShell, desde la carpeta PNYX):
  $env:SUPABASE_SERVICE_KEY="...."   (la clave service_role)
  python senado_reporte.py           -> solo las PUBLICADAS sin texto
  python senado_reporte.py --todos   -> TODAS las del Senado sin texto

Como seguir despues:
  1. Abri cada link de la ficha, descarga el PDF.
  2. Guardalo con el nombre del bill_id + .pdf   (ej: SENADO871-26.pdf)
     dentro de una carpeta llamada  senado_pdfs\
  3. Corre:  python senado_subir.py   (sube todos los PDF de esa carpeta)
"""

import csv
import os
import sys

try:
    from supabase import create_client
except ImportError:
    print("Falta supabase:  pip install supabase", file=sys.stderr)
    sys.exit(1)

SUPABASE_URL = "https://ihmbhbhwlntsjqdavxge.supabase.co"
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")

BASE = "https://www.senado.gob.ar"
# La ficha del expediente. El sufijo de origen (S / PE / CD) puede variar; ponemos
# el declarado y, si ese no abre, se prueban los otros a mano.
ORIGEN_COD = {"Senado": "S", "Poder Ejecutivo": "PE", "Diputados": "CD"}


def ficha_url(expediente, origen):
    if not expediente or "/" not in expediente:
        return ""
    num, anio = expediente.split("/", 1)
    cod = ORIGEN_COD.get(origen or "", "S")
    return "%s/parlamentario/comisiones/verExp/%s.%s/%s/PL" % (BASE, num, anio, cod)


def main():
    if not SUPABASE_KEY:
        print('Falta la clave:  $env:SUPABASE_SERVICE_KEY="..." (service_role)', file=sys.stderr)
        sys.exit(1)

    todos = "--todos" in sys.argv
    sb = create_client(SUPABASE_URL, SUPABASE_KEY)

    q = (sb.table("leyes")
         .select("bill_id,expediente,origen,titulo,publicada")
         .eq("camara", "Senado")
         .is_("texto_oficial", "null")
         .or_("texto_escaneado.is.null,texto_escaneado.eq.false"))
    if not todos:
        q = q.eq("publicada", True)
    filas = q.execute().data or []

    # ordenar por expediente (mas nuevas primero, por numero)
    def clave(f):
        exp = f.get("expediente") or ""
        try:
            n, a = exp.split("/")
            return (int(a), int(n))
        except Exception:
            return (0, 0)
    filas.sort(key=clave, reverse=True)

    if not filas:
        print("No hay leyes del Senado sin texto. Nada para bajar.", file=sys.stderr)
        return

    # CSV para Excel
    with open("senado_faltantes.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["bill_id", "expediente", "origen", "publicada", "titulo", "link_ficha", "nombre_para_guardar"])
        for r in filas:
            w.writerow([r.get("bill_id"), r.get("expediente"), r.get("origen"),
                        "si" if r.get("publicada") else "no",
                        (r.get("titulo") or "")[:200],
                        ficha_url(r.get("expediente"), r.get("origen")),
                        "%s.pdf" % r.get("bill_id")])

    # TXT legible
    with open("senado_faltantes.txt", "w", encoding="utf-8") as f:
        f.write("LEYES DEL SENADO SIN TEXTO — %d en total%s\n" % (len(filas), " (TODAS)" if todos else " (solo publicadas)"))
        f.write("Baja el PDF de cada ficha y guardalo en  senado_pdfs\\  con el nombre indicado.\n")
        f.write("=" * 70 + "\n\n")
        for r in filas:
            f.write("Guardar como: %s.pdf\n" % r.get("bill_id"))
            f.write("  Expediente: %s  (%s)%s\n" % (r.get("expediente"), r.get("origen") or "s/origen",
                                                    "  [PUBLICADA]" if r.get("publicada") else ""))
            f.write("  Titulo: %s\n" % ((r.get("titulo") or "")[:160]))
            f.write("  Ficha:  %s\n\n" % ficha_url(r.get("expediente"), r.get("origen")))

    print("Listo. %d leyes del Senado sin texto%s." % (len(filas), " (TODAS)" if todos else " (solo publicadas)"))
    print("Se escribieron:")
    print("  senado_faltantes.csv  (abrilo con Excel)")
    print("  senado_faltantes.txt  (para leer y copiar los links)")
    print("")
    print("Siguiente paso: baja los PDF, guardalos en la carpeta  senado_pdfs\\")
    print("con el nombre que dice cada fila (ej: SENADO871-26.pdf), y corre:")
    print("  python senado_subir.py")


if __name__ == "__main__":
    main()
