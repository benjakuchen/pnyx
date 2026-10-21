#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Pnyx - (c) 2026 Benjamin Kuchen. Obra protegida por la Ley 11.723 (Argentina).
# Distribuido bajo la Licencia Publica General Affero de GNU v3 (AGPL-3.0). Ver LICENSE.
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


def _bill_ids_con_texto():
    """Set de bill_ids que YA tienen texto cargado. Consulta liviana:
    pide solo bill_id filtrando server-side por texto_oficial no nulo."""
    headers = {"apikey": SERVICE_KEY, "Authorization": "Bearer " + SERVICE_KEY}
    ids = set()
    offset = 0
    while True:
        url = (SUPABASE_URL + "/rest/v1/leyes?select=bill_id"
               "&texto_oficial=not.is.null&limit=1000&offset=" + str(offset))
        r = requests.get(url, headers=headers, timeout=30)
        r.raise_for_status()
        parte = r.json()
        ids.update(p["bill_id"] for p in parte)
        if len(parte) < 1000:
            break
        offset += 1000
    return ids


def traer_leyes():
    headers = {"apikey": SERVICE_KEY, "Authorization": "Bearer " + SERVICE_KEY}
    con_texto = _bill_ids_con_texto()
    filas = []
    offset = 0
    while True:
        url = (SUPABASE_URL + "/rest/v1/leyes?select=bill_id,titulo,media_sancion,"
               "importante_prensa,sugerida_prensa,curaduria_estado,estado_tramite,decidido_manual"
               "&limit=1000&offset=" + str(offset))
        r = requests.get(url, headers=headers, timeout=30)
        r.raise_for_status()
        parte = r.json()
        for p in parte:
            p["tiene_texto"] = p["bill_id"] in con_texto
        filas.extend(parte)
        if len(parte) < 1000:
            break
        offset += 1000
    return filas


def clasificar(ley):
    """Devuelve (nivel, orden, publicada) o None si no hay que tocarla.
    MODELO B (control total manual): el obrero NUNCA publica solo. Todo lo
    que sugiere va a la COLA (publicada=False) para que el admin lo publique
    a mano. La media sanción va a la cola pero en prioridad 0 (arriba de todo).
    """
    # CANDADO MANUAL: si el admin ya decidió algo sobre esta ley, no se toca NUNCA.
    if ley.get("decidido_manual"):
        return None
    # No tocar lo ya sancionado (lo maneja el obrero 13) ni lo ya decidido por estado.
    if ley.get("estado_tramite") == "sancionada":
        return None
    est = ley.get("curaduria_estado")
    if est in ("publicada", "descartada", "votada"):
        return None  # respeta la decisión humana / el linkeo

    titulo = ley.get("titulo")
    if es_ruido(titulo):
        return ("ruido", None, False)

    # MEDIA SANCIÓN: a la cola PRIORIDAD 0 (arriba de todo), para publicar primero.
    # Ya NO se publica sola: el admin la publica a mano.
    if ley.get("media_sancion"):
        return ("cola", 0, False)

    # El resto, a la cola priorizada (nada se publica solo).
    if es_peso(titulo):
        return ("cola", 1, False)            # tema de peso -> cola prioridad 1
    if ley.get("importante_prensa"):
        return ("cola", 1, False)            # prensa alta -> también prioridad 1
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
    cont = {"cola0": 0, "cola1": 0, "cola2": 0, "cola3": 0, "ruido": 0, "intactas": 0}
    for ley in leyes:
        r = clasificar(ley)
        if r is None:
            cont["intactas"] += 1
            continue
        nivel, orden, publicada = r
        if nivel == "ruido":
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

    print("\n=== REPARTO (modelo B: nada se publica solo) ===", file=sys.stderr)
    print("Cola 0 (MEDIA SANCIÓN, arriba):%d" % cont["cola0"], file=sys.stderr)
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
