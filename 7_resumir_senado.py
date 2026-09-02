#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pnyx · Obrero 7 — Resumir Senado con IA (Supabase = fuente de verdad)
----------------------------------------------------------------------
Para cada ley del Senado con texto en Supabase pero sin resumen, baja el
texto de Supabase, le pide a la IA la oracion y el resumen neutral, y los
sube a Supabase.

Lee 'proyectos_senado.json' y 'estado_nube.json'.

Requisitos: pip install anthropic supabase  +  ANTHROPIC_API_KEY
Uso:  python 7_resumir_senado.py          (top 30 sin resumen)
      python 7_resumir_senado.py 50
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

ARCHIVO = "proyectos_senado.json"
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

    def listo_para_resumir(p):
        e = estado.get(p.get("bill_id"))
        return e and e.get("tiene_texto") and not e.get("tiene_resumen")

    objetivo = [p for p in leyes if listo_para_resumir(p)][:top_n]

    if not objetivo:
        print("No hay leyes del Senado con texto pendientes de resumir.", file=sys.stderr)
        return

    print("Resumiendo %d leyes del Senado...\n" % len(objetivo), file=sys.stderr)

    sb = create_client(SUPABASE_URL, SUPABASE_KEY)
    cliente = Anthropic(api_key=clave)
    hechos = 0

    for i, p in enumerate(objetivo, 1):
        bid = p["bill_id"]
        try:
            res = sb.table("leyes").select("texto_oficial").eq("bill_id", bid).single().execute()
            texto = res.data.get("texto_oficial") if res.data else None
        except Exception as e:
            print("  [%d/%d] %s  (no pude traer texto: %s)" % (i, len(objetivo), p.get("expediente"), e),
                  file=sys.stderr)
            continue
        if not texto:
            print("  [%d/%d] %s  (sin texto, salteo)" % (i, len(objetivo), p.get("expediente")), file=sys.stderr)
            continue

        oracion, resumen = resumir(cliente, p.get("titulo", ""), texto)
        if oracion:
            sb.table("leyes").upsert({
                "bill_id": bid, "oracion_ia": oracion, "resumen_ia": resumen,
            }, on_conflict="bill_id").execute()
            hechos += 1
            print("  [%d/%d] %s -> subido" % (i, len(objetivo), p.get("expediente")), file=sys.stderr)
            print("        %s" % oracion, file=sys.stderr)
        else:
            print("  [%d/%d] %s  (no se pudo)" % (i, len(objetivo), p.get("expediente")), file=sys.stderr)
        time.sleep(0.5)

    print("\n=== LISTO ===", file=sys.stderr)
    print("Resumidos y subidos: %d de %d" % (hechos, len(objetivo)), file=sys.stderr)
    print("(Para reflejar el cambio, volve a correr el Obrero 1.)", file=sys.stderr)


if __name__ == "__main__":
    main()
