#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Pnyx - (c) 2026 Benjamin Kuchen. Obra protegida por la Ley 11.723 (Argentina).
# Distribuido bajo la Licencia Publica General Affero de GNU v3 (AGPL-3.0). Ver LICENSE.
"""
Pnyx · Maestro — corre toda la tuberia en orden
------------------------------------------------
Ejecuta todos los obreros en secuencia. Cada uno actualiza Supabase (la
fuente de verdad). Si un obrero falla, avisa y sigue con el resto (salvo el
1, que es requisito de los demas).

Nota linkeo: el maestro corre el 16 en modo --sin-ia (solo titulo alto, no
gasta API). El linkeo con IA (zona gris) se corre a mano y revisando.

Uso:
  python pnyx_actualizar.py            (corrida normal, sin resumir de mas)
  python pnyx_actualizar.py --full     (resume todo lo que tenga texto)

Requiere las variables de entorno:
  SUPABASE_SERVICE_KEY  y  ANTHROPIC_API_KEY
"""

import os
import subprocess
import sys

FULL = "--full" in sys.argv

# (script, argumentos, es_critico)
PASOS = [
    ("1_consultar_supabase.py", [], True),                              # estado + existentes.json
    ("2_bajar_diputados.py", [], False),                               # lista Diputados
    ("3_texto_diputados.py", (["--todos"] if FULL else []), False),    # texto Diputados -> Supabase
    # SENADO: NO se puede automatizar. El sitio del Senado tiene un anti-bot
    # (F5 Shape / TSPD): devuelve un JavaScript-challenge en vez del Excel a
    # cualquier script (probado 23/09/2026, falla incluso desde la PC). Solo
    # un navegador real lo pasa. Por eso TODO el Senado es manual:
    #   1) bajar el Excel a mano del sitio  -> guardarlo como senado.xls
    #   2) python senado_desde_excel.py     (descubre leyes nuevas)
    #   3) python senado_reporte.py --todos (lista que falta)
    #   4) bajar PDFs a mano -> senado_pdfs\ -> python senado_subir.py
    ("15_ocr.py", [], False),                                          # OCR de escaneados sin texto (ambas camaras)
    ("4_resumir_diputados.py", (["50"] if FULL else []), False),       # resumen Diputados (incluye lo recien OCReado)
    ("7_resumir_senado.py", (["50"] if FULL else []), False),          # resumen Senado
    ("8_prensa.py", [], False),                                        # flags de prensa
    ("10_votadas.py", [], False),                                      # votaciones por bloque
    ("11_autores.py", [], False),                                      # autores / firmantes
    ("12_bancas.py", [], False),                                       # lista de legisladores
    ("13_sanciones.py", [], False),                                    # media sancion / sancion
    ("1_consultar_supabase.py", [], True),                             # refrescar estado
    ("14_curaduria.py", [], False),                                    # clasificar auto / cola / ruido
    ("9_mezclar_ordenar.py", [], False),                              # puntuar y ordenar
    ("17_labor.py", [], False),                                        # labor parlamentaria (no gasta API)
    # Linkeo AUTOMATICO solo por titulo alto (--sin-ia): no gasta credito de
    # API y casi no se equivoca (umbral 0.72). La zona gris que usa IA se corre
    # A MANO desde la PC:  python 16_linkeo.py   (revisando los matches).
    ("16_linkeo.py", ["--sin-ia"], False),
]


def falta_clave():
    faltan = []
    if not os.environ.get("SUPABASE_SERVICE_KEY"):
        faltan.append("SUPABASE_SERVICE_KEY")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        faltan.append("ANTHROPIC_API_KEY")
    return faltan


def main():
    faltan = falta_clave()
    if faltan:
        print("Faltan variables de entorno: %s" % ", ".join(faltan), file=sys.stderr)
        print("Configuralas asi (PowerShell):", file=sys.stderr)
        for v in faltan:
            print('  $env:%s="..."' % v, file=sys.stderr)
        sys.exit(1)

    print("=" * 60, file=sys.stderr)
    print("PNYX · Actualizacion completa%s" % (" (FULL)" if FULL else ""), file=sys.stderr)
    print("=" * 60, file=sys.stderr)

    for i, (script, args, critico) in enumerate(PASOS, 1):
        print("\n[%d/%d] %s %s" % (i, len(PASOS), script, " ".join(args)), file=sys.stderr)
        print("-" * 60, file=sys.stderr)
        if not os.path.exists(script):
            print("  (no existe %s, salteo)" % script, file=sys.stderr)
            continue
        r = subprocess.run([sys.executable, script] + args)
        if r.returncode != 0:
            print("  ! %s termino con error (codigo %d)" % (script, r.returncode), file=sys.stderr)
            if critico:
                print("  Es un paso critico. Corto aca.", file=sys.stderr)
                sys.exit(1)

    print("\n" + "=" * 60, file=sys.stderr)
    print("LISTO. Supabase actualizado. La app ya lee el feed nuevo.", file=sys.stderr)
    print("=" * 60, file=sys.stderr)


if __name__ == "__main__":
    main()
