#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pnyx · Obrero 14 — Curaduría del feed
--------------------------------------
Clasifica cada ley en un nivel y decide qué se publica solo:
  - 'auto'  : media sancion O prensa alta        -> publicada=true (al feed)
  - 'cola'  : tema de peso / prensa media / resto -> despublicada, a revisar en admin
              curaduria_orden: 1=tema de peso, 2=prensa media, 3=resto
  - 'ruido' : declaraciones/homenajes/etc          -> despublicada, no se muestra

RESPETA las decisiones del admin: si curaduria_estado ya es 'publicada' o
'descartada', NO las toca (no pisa lo que Benjamín ya revisó).

Requiere sql_curaduria.sql corrido antes.
Modos:
  python 14_curaduria.py --dry-run   muestra el reparto por nivel, sin escribir
  python 14_curaduria.py             aplica la clasificación
"""

import os
import re
import sys
import time
import json

import requests

SUPABASE_URL = "https://ihmbhbhwlntsjqdavxge.supabase.co"
SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
LOTE = 50

# Palabras que marcan RUIDO (no es ley real para votar)
RUIDO = ["DECLAR", "BENEPLACITO", "BENEPLÁCITO", "HOMENAJE", "ADHESION", "ADHESIÓN",
         "PEDIDO DE INFORME", "INTERES", "INTERÉS", "CAPITAL NACIONAL", "FIESTA NACIONAL",
         "REPUDIO", "PESAR", "RECONOCIMIENTO A"]

# Palabras de TEMA DE PESO (prioridad 1 en la cola)
PESO = ["CODIGO", "CÓDIGO", "PRESUPUESTO", "TRIBUTAR", "IMPUESTO", "PENAL", "LABORAL",
        "JUBILA", "PREVISIONAL", "COPARTICIPACION", "REFORMA", "EMERGENCIA"]


def es_ruido(titulo):
    t = (titulo or "").upper()
    # ruido solo si EMPIEZA con declaración o contiene las marcas claras
    if t.startswith("DECLAR"):
        return True
    return any(p in t for p in RUIDO if p not in ("DECLAR",))


def es_peso(titulo):
    t = (titulo or "").upper()
    return any(p in t for p in PESO)


def traer_leyes():
    headers = {"apikey": SERVICE_KEY, "Authorization": "Bearer " + SERVICE_KEY}
    filas = []
    offset = 0
    while True:
        url = (SUPABASE_URL + "/rest/v1/leyes?select=bill_id,titulo,media_sancion,"
               "importante_prensa,sugerida_prensa,curaduria_estado,estado_tramite"
               "&limit=1000&offset=" + str(offset))
        r = requests.get(url, headers=headers, timeout=30)
        r.raise_for_status()
        parte = r.json()
        filas.extend(parte)
        if len(parte) < 1000:
            break
        offset += 1000
    return filas


def clasificar(ley):
    """Devuelve (nivel, orden, publicada) o None si no hay que tocarla."""
    # No tocar lo ya sancionado (lo maneja el obrero 13) ni lo ya decidido por el admin
    if ley.get("estado_tramite") == "sancionada":
        return None
    est = ley.get("curaduria_estado")
    if est in ("publicada", "descartada"):
        return None  # respeta la decisión humana

    titulo = ley.get("titulo")
    if es_ruido(titulo):
        return ("ruido", None, False)
    if ley.get("media_sancion") or ley.get("importante_prensa"):
        return ("auto", None, True)          # comprobadamente relevante -> al feed
    if es_peso(titulo):
        return ("cola", 1, False)            # tema de peso -> cola prioridad 1
    if ley.get("sugerida_prensa"):
        return ("cola", 2, False)            # prensa media -> cola prioridad 2
    return ("cola", 3, False)                # resto -> cola prioridad 3


def main():
    dry = "--dry-run" in sys.argv
    if not SERVICE_KEY:
        print('Falta la clave:  $env:SUPABASE_SERVICE_KEY="..."', file=sys.stderr)
        sys.exit(1)

    leyes = traer_leyes()
    print("Leyes traídas: %d" % len(leyes), file=sys.stderr)

    cambios = []
    cont = {"auto": 0, "cola1": 0, "cola2": 0, "cola3": 0, "ruido": 0, "intactas": 0}
    for ley in leyes:
        r = clasificar(ley)
        if r is None:
            cont["intactas"] += 1
            continue
        nivel, orden, publicada = r
        if nivel == "auto":
            cont["auto"] += 1
        elif nivel == "ruido":
            cont["ruido"] += 1
        else:
            cont["cola%d" % orden] += 1
        cambios.append({
            "bill_id": ley["bill_id"],
            "curaduria_nivel": nivel,
            "curaduria_orden": orden,
            "curaduria_estado": "pendiente",
            "publicada": publicada,
        })

    print("\n=== REPARTO ===", file=sys.stderr)
    print("Feed automático (auto):        %d" % cont["auto"], file=sys.stderr)
    print("Cola 1 (tema de peso):         %d" % cont["cola1"], file=sys.stderr)
    print("Cola 2 (prensa media):         %d" % cont["cola2"], file=sys.stderr)
    print("Cola 3 (resto):                %d" % cont["cola3"], file=sys.stderr)
    print("Ruido (descartado):            %d" % cont["ruido"], file=sys.stderr)
    print("Intactas (sancionadas/ya decididas): %d" % cont["intactas"], file=sys.stderr)

    if dry:
        print("\n(DRY-RUN: no se escribió nada. Cambios que se harían: %d)" % len(cambios), file=sys.stderr)
        return

    headers = {"apikey": SERVICE_KEY, "Authorization": "Bearer " + SERVICE_KEY,
               "Content-Type": "application/json", "Prefer": "resolution=merge-duplicates"}
    for i in range(0, len(cambios), LOTE):
        lote = cambios[i:i + LOTE]
        url = SUPABASE_URL + "/rest/v1/leyes?on_conflict=bill_id"
        r = requests.post(url, headers=headers, data=json.dumps(lote), timeout=30)
        if r.status_code >= 300:
            print("ERROR lote %d: %s %s" % (i // LOTE, r.status_code, r.text[:200]), file=sys.stderr)
            r.raise_for_status()
        time.sleep(0.3)
    print("\nClasificadas: %d leyes. El feed ahora muestra solo las 'auto'." % len(cambios), file=sys.stderr)
    print("Revisá la cola en la admin (pestaña Curaduría).", file=sys.stderr)


if __name__ == "__main__":
    main()
