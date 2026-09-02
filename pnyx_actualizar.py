#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pnyx · Maestro — corre toda la tuberia en orden
------------------------------------------------
Ejecuta los 9 obreros en secuencia. Cada uno actualiza Supabase (la fuente
de verdad). Si un obrero falla, avisa y sigue con el resto (salvo el 1,
que es requisito de los demas).

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
    ("1_consultar_supabase.py", [], True),
    ("2_bajar_diputados.py", [], False),
    ("3_texto_diputados.py", (["--todos"] if FULL else []), False),
    ("4_resumir_diputados.py", (["50"] if FULL else []), False),
    ("5_bajar_senado.py", [], False),
    ("6_texto_senado.py", (["--todos"] if FULL else []), False),
    ("7_resumir_senado.py", (["50"] if FULL else []), False),
    ("8_prensa.py", [], False),
    ("1_consultar_supabase.py", [], True),   # refrescar estado antes de puntuar
    ("9_mezclar_ordenar.py", [], False),
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
