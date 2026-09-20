#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Pnyx - (c) 2026 Benjamin Kuchen. Obra protegida por la Ley 11.723 (Argentina).
# Distribuido bajo la Licencia Publica General Affero de GNU v3 (AGPL-3.0). Ver LICENSE.
"""
Pnyx · Obrero 17 — Labor parlamentaria (leyes presentadas por legislador)
-------------------------------------------------------------------------
Cuenta cuantas leyes presento cada legislador, cruzando el campo 'autor' de
la tabla 'leyes' (apellido, ej. "Fama") con el apellido de la tabla 'bancas'
(nombre "APELLIDO, Nombre"). Guarda el conteo en bancas.leyes_presentadas.

OJO: el cruce es POR APELLIDO. Es una aproximacion:
 - "Autor Y Otros" cuenta para el primer apellido.
 - Si dos legisladores comparten apellido y camara, es ambiguo (se avisa).
Por eso el dato se muestra como labor APROXIMADA en la app.

Requisitos:  pip install supabase   +   $env:SUPABASE_SERVICE_KEY
Antes, correr una vez en Supabase:
  ALTER TABLE bancas ADD COLUMN IF NOT EXISTS leyes_presentadas int default 0;

Uso:
  python 17_labor.py --dry-run   -> muestra el cruce y el top, sin escribir
  python 17_labor.py             -> calcula y sube a Supabase
"""

import os
import re
import sys
import unicodedata

try:
    from supabase import create_client
except ImportError:
    print("Falta supabase:  pip install supabase", file=sys.stderr)
    sys.exit(1)

SUPABASE_URL = "https://ihmbhbhwlntsjqdavxge.supabase.co"
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
DRY = "--dry-run" in sys.argv

# leyes.camara -> bancas.camara
CAM = {"Diputados": "diputados", "Senado": "senadores"}


def camara_de(ley):
    """Cámara de la ley en formato bancas ('diputados'/'senadores').
    Si camara viene null, la deduce del bill_id:
      - Senado: empieza con 'SENADO'
      - Diputados: tiene '-D-' (ej 1234-D-2026) o empieza con 'HCDN'"""
    c = CAM.get(ley.get("camara"))
    if c:
        return c
    bid = (ley.get("bill_id") or "").upper()
    if bid.startswith("SENADO"):
        return "senadores"
    if "-D-" in bid or bid.startswith("HCDN"):
        return "diputados"
    return ""


def norm(t):
    t = unicodedata.normalize("NFKD", t or "").encode("ascii", "ignore").decode().upper()
    return re.sub(r"\s+", " ", t).strip()


def apellido_autor(autor):
    """Del campo autor ('Fama', 'Valenzuela Y Otros', 'Lopez C.') saca el apellido."""
    a = norm(autor)
    if not a:
        return ""
    # cortar en " Y OTROS", " Y OTRO", " Y OTRA"
    a = re.split(r"\bY OTRO", a)[0].strip()
    # si viene "APELLIDO, NOMBRE" tomar antes de la coma
    a = a.split(",")[0].strip()
    # tomar solo el primer token (apellido); descarta iniciales sueltas
    toks = [x for x in a.split(" ") if len(x) > 1]
    return toks[0] if toks else a


def apellido_banca(nombre):
    """De 'ABAD, Maximiliano' saca 'ABAD'."""
    return norm((nombre or "").split(",")[0])


def traer(sb, tabla, campos):
    filas, desde = [], 0
    while True:
        r = sb.table(tabla).select(campos).range(desde, desde + 999).execute()
        d = r.data or []
        filas += d
        if len(d) < 1000:
            break
        desde += 1000
    return filas


def main():
    if not SUPABASE_KEY:
        print('Falta la clave:  $env:SUPABASE_SERVICE_KEY="..." (service_role)', file=sys.stderr)
        sys.exit(1)
    sb = create_client(SUPABASE_URL, SUPABASE_KEY)

    leyes = traer(sb, "leyes", "bill_id,autor,camara")  # bill_id para deducir camara si falta
    bancas = traer(sb, "bancas", "nombre,nombre_norm,camara")
    print("Leyes: %d | Bancas: %d" % (len(leyes), len(bancas)), file=sys.stderr)

    # indice: (apellido, camara) -> [nombre_norm, ...]
    idx = {}
    for b in bancas:
        key = (apellido_banca(b.get("nombre")), (b.get("camara") or "").lower())
        idx.setdefault(key, []).append(b.get("nombre_norm"))

    conteo = {}          # nombre_norm -> cantidad
    sin_match = 0
    ambiguos = set()
    for l in leyes:
        ap = apellido_autor(l.get("autor"))
        cam = camara_de(l)
        if not ap or not cam:
            sin_match += 1
            continue
        matches = idx.get((ap, cam), [])
        if not matches:
            sin_match += 1
            continue
        if len(matches) > 1:
            ambiguos.add((ap, cam))
        for nn in matches:
            conteo[nn] = conteo.get(nn, 0) + 1

    con_labor = len(conteo)
    print("Legisladores con labor contada: %d | leyes sin match de autor: %d | apellidos ambiguos: %d"
          % (con_labor, sin_match, len(ambiguos)), file=sys.stderr)

    # top 10 para ver calidad
    top = sorted(conteo.items(), key=lambda x: x[1], reverse=True)[:10]
    print("\n=== TOP 10 (labor parlamentaria) ===", file=sys.stderr)
    nombre_de = {b.get("nombre_norm"): b.get("nombre") for b in bancas}
    for nn, c in top:
        print("  %3d  %s" % (c, nombre_de.get(nn, nn)), file=sys.stderr)
    if ambiguos:
        print("\nApellidos ambiguos (comparten apellido+camara, el conteo puede repetirse):", file=sys.stderr)
        for ap, cam in sorted(ambiguos):
            print("  %s (%s)" % (ap, cam), file=sys.stderr)

    if DRY:
        print("\n(DRY-RUN: no se escribio nada.)", file=sys.stderr)
        return

    # Escribir con UPDATE (no upsert): solo modifica filas existentes, nunca
    # crea nuevas. Actualiza cada banca por su id.
    subidas = 0
    fallos = 0
    for b in bancas:
        nn = b.get("nombre_norm")
        val = conteo.get(nn, 0)
        try:
            sb.table("bancas").update({"leyes_presentadas": val}) \
              .eq("nombre_norm", nn).eq("camara", b.get("camara")).execute()
            subidas += 1
        except Exception as e:
            fallos += 1
            if fallos <= 3:
                print("  ! fallo al actualizar %s: %s" % (b.get("nombre"), e), file=sys.stderr)
    print("\nLabor parlamentaria actualizada en bancas: %d filas (fallos: %d)." % (subidas, fallos), file=sys.stderr)


if __name__ == "__main__":
    main()
