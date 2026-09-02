#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pnyx · Obrero 4 — Resumir Diputados con IA (Supabase = fuente de verdad)
-------------------------------------------------------------------------
Para cada ley de Diputados que tenga texto en Supabase pero AUN no tenga
resumen, baja el texto de Supabase, le pide a la IA la oracion y el
resumen neutral, y los sube directo a Supabase.

Lee 'estado_nube.json' para saber cuales tienen texto sin resumen.
Procesa de las mas relevantes hacia abajo (segun el orden del feed local
'proyectos_diputados.json'), hasta TOP_N.

Todo queda revisado_admin=false (el admin revisa antes de publicar).

Requisitos: pip install anthropic supabase  +  ANTHROPIC_API_KEY
Uso:  python 4_resumir_diputados.py          (top 30 sin resumen)
      python 4_resumir_diputados.py 50         (top 50)
"""

import json
import os
import sys
import time

try:
    from anthropic import Anthropic
except ImportError:
    print("Falta anthropic. Instalalo con:  pip install anthropic", file=sys.stderr)
    sys.exit(1)
try:
    from supabase import create_client
except ImportError:
    print("Falta supabase. Instalalo con:  pip install supabase", file=sys.stderr)
    sys.exit(1)

ARCHIVO = "proyectos_diputados.json"
ESTADO = "estado_nube.json"
TOP_N = 30
MODELO = "claude-sonnet-4-6"
MAX_CHARS_TEXTO = 18000

SUPABASE_URL = "https://ihmbhbhwlntsjqdavxge.supabase.co"
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")

SISTEMA = """Sos un asistente que resume proyectos de ley argentinos para una app ciudadana.
Te paso el TEXTO OFICIAL de un proyecto. Devolves SOLO un objeto JSON, sin nada mas, con esta forma exacta:
{"oracion": "...", "resumen": "..."}

Reglas estrictas:
- "oracion": UNA sola frase, clara y simple, que cualquier persona entienda en 5 segundos. Que diga QUE hace el proyecto. Sin jerga, sin numeros de ley, sin tecnicismos. Maximo 25 palabras.
- "resumen": 2 a 4 frases. Primero que dice el proyecto (sacado del texto). Despues una linea de tension del debate, empezando con "A favor:" y "En discusion:", planteando los dos lados SIN tomar partido.
- NEUTRALIDAD ABSOLUTA: describis lo que dice la ley, no opinas si es buena o mala. No uses adjetivos cargados.
- Basate UNICAMENTE en el texto que te paso. Si algo no esta en el texto, no lo agregues.
- Escribi en español rioplatense, claro y sobrio.
- Respondes SOLO el JSON, sin explicaciones ni texto adicional."""


def resumir(cliente, titulo, texto):
    texto = texto[:MAX_CHARS_TEXTO]
    mensaje = "TITULO (referencia): %s\n\nTEXTO OFICIAL DEL PROYECTO:\n%s" % (titulo, texto)
    try:
        resp = cliente.messages.create(
            model=MODELO, max_tokens=600, system=SISTEMA,
            messages=[{"role": "user", "content": mensaje}],
        )
        salida = "".join(b.text for b in resp.content if hasattr(b, "text")).strip()
        salida = salida.replace("```json", "").replace("```", "").strip()
        datos = json.loads(salida)
        return datos.get("oracion"), datos.get("resumen")
    except Exception as e:
        print("    (error con la IA: %s)" % e, file=sys.stderr)
        return None, None


def main():
    if not SUPABASE_KEY:
        print("Falta:  $env:SUPABASE_SERVICE_KEY=\"...\"", file=sys.stderr)
        sys.exit(1)
    clave = os.environ.get("ANTHROPIC_API_KEY")
    if not clave:
        print("Falta:  $env:ANTHROPIC_API_KEY=\"...\"", file=sys.stderr)
        sys.exit(1)

    top_n = TOP_N
    for a in sys.argv[1:]:
        if a.isdigit():
            top_n = int(a)

    with open(ARCHIVO, encoding="utf-8") as f:
        leyes = json.load(f)
    with open(ESTADO, encoding="utf-8") as f:
        estado = json.load(f)

    # Leyes que tienen texto en Supabase pero NO resumen
    def listo_para_resumir(p):
        e = estado.get(p.get("bill_id"))
        return e and e.get("tiene_texto") and not e.get("tiene_resumen")

    objetivo = [p for p in leyes if listo_para_resumir(p)][:top_n]

    if not objetivo:
        print("No hay leyes de Diputados con texto pendientes de resumir.", file=sys.stderr)
        print("(Quizas ya estan resumidas, o falta bajar texto con el Obrero 3.)", file=sys.stderr)
        return

    print("Leyes con texto sin resumen: resumiendo %d...\n" % len(objetivo), file=sys.stderr)

    sb = create_client(SUPABASE_URL, SUPABASE_KEY)
    cliente = Anthropic(api_key=clave)
    hechos = 0

    for i, p in enumerate(objetivo, 1):
        bid = p["bill_id"]
        # Bajar el texto de Supabase (vive en la nube, no en el archivo local)
        try:
            res = sb.table("leyes").select("texto_oficial").eq("bill_id", bid).single().execute()
            texto = res.data.get("texto_oficial") if res.data else None
        except Exception as e:
            print("  [%d/%d] %s  (no pude traer el texto: %s)" % (i, len(objetivo), p.get("expediente"), e),
                  file=sys.stderr)
            continue

        if not texto:
            print("  [%d/%d] %s  (sin texto en Supabase, salteo)" % (i, len(objetivo), p.get("expediente")),
                  file=sys.stderr)
            continue

        oracion, resumen = resumir(cliente, p.get("titulo", ""), texto)
        if oracion:
            sb.table("leyes").upsert({
                "bill_id": bid,
                "oracion_ia": oracion,
                "resumen_ia": resumen,
            }, on_conflict="bill_id").execute()
            hechos += 1
            print("  [%d/%d] %s -> subido" % (i, len(objetivo), p.get("expediente")), file=sys.stderr)
            print("        %s" % oracion, file=sys.stderr)
        else:
            print("  [%d/%d] %s  (no se pudo, queda sin resumen)" % (i, len(objetivo), p.get("expediente")),
                  file=sys.stderr)
        time.sleep(0.5)

    print("\n=== LISTO ===", file=sys.stderr)
    print("Resumidos y subidos a Supabase: %d de %d" % (hechos, len(objetivo)), file=sys.stderr)
    print("(Para reflejar el cambio, volve a correr el Obrero 1.)", file=sys.stderr)


if __name__ == "__main__":
    main()
