#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Pnyx - (c) 2026 Benjamin Kuchen. Obra protegida por la Ley 11.723 (Argentina).
# Distribuido bajo la Licencia Publica General Affero de GNU v3 (AGPL-3.0). Ver LICENSE.
"""
Pnyx · Obrero 16 — Linkeo en cascada (título → IA)
---------------------------------------------------
Vincula las VOTACIONES del Congreso (votaciones_congreso, de comovoto) con las
LEYES PUBLICADAS del feed. Para cada votación sin linkear, prueba en orden:
  1) TÍTULO: similitud de texto (rápido, gratis). Si supera el umbral, linkea.
  2) IA: si el título no alcanza, le pide a la IA que elija cuál ley publicada
     corresponde (o ninguna), comparando título + resumen.

Alcance acotado: solo votadas SIN linkear × solo leyes PUBLICADAS. Así la IA
compara contra pocas candidatas y casi no gasta.

Guarda: ley_bill_id + match_metodo ('titulo' | 'ia') + match_score.

Claves: $env:SUPABASE_SERVICE_KEY  y (para el paso IA) $env:ANTHROPIC_API_KEY
Modos:
  python 16_linkeo.py --dry-run   muestra qué linkearía, sin escribir
  python 16_linkeo.py             aplica
  python 16_linkeo.py --sin-ia    solo por título (no usa IA)
"""

import json
import os
import re
import sys
import unicodedata
from difflib import SequenceMatcher

import requests

SUPABASE_URL = "https://ihmbhbhwlntsjqdavxge.supabase.co"
SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
UMBRAL_ALTO   = 0.72   # título >= esto: se acepta directo (muy confiable)
UMBRAL_TITULO = 0.62   # título entre esto y ALTO: zona gris -> la IA confirma
MODELO = "claude-sonnet-4-6"
DRY = "--dry-run" in sys.argv
SIN_IA = "--sin-ia" in sys.argv


def norm_titulo(t):
    t = unicodedata.normalize("NFKD", (t or "")).encode("ascii", "ignore").decode().lower()
    t = re.sub(r"[^a-z0-9 ]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def score_titulo(a, b):
    na, nb = norm_titulo(a), norm_titulo(b)
    return SequenceMatcher(None, na, nb).ratio() if (na and nb) else 0.0


def sb_get(path):
    r = requests.get(SUPABASE_URL + path,
                     headers={"apikey": SERVICE_KEY, "Authorization": "Bearer " + SERVICE_KEY},
                     timeout=30)
    r.raise_for_status()
    return r.json()


def sb_patch(votacion_id, datos):
    r = requests.patch(SUPABASE_URL + "/rest/v1/votaciones_congreso?id=eq." + str(votacion_id),
                       headers={"apikey": SERVICE_KEY, "Authorization": "Bearer " + SERVICE_KEY,
                                "Content-Type": "application/json"},
                       data=json.dumps(datos), timeout=30)
    if r.status_code >= 300:
        print("  ERROR al guardar:", r.status_code, r.text[:150], file=sys.stderr)


def linkear_ia(cliente, votacion_titulo, candidatas):
    """La IA elige entre POCAS candidatas (las más parecidas por título), o 'ninguna'.
    Nunca le pasamos toda la base: eso la marea y elige cualquiera."""
    if not candidatas:
        return None
    lista = ""
    for i, l in enumerate(candidatas):
        resumen = (l.get("oracion_ia") or l.get("titulo") or "")[:180]
        lista += "%d) %s\n" % (i, resumen)
    prompt = ("Una votación del Congreso argentino se titula:\n\"%s\"\n\n"
              "Estas son las únicas candidatas posibles (leyes en trámite):\n%s\n"
              "¿A cuál corresponde EXACTAMENTE la votación? Si ninguna es claramente la misma ley, "
              "respondé 'ninguna'. No fuerces un match. Respondé SOLO el número, o 'ninguna'. "
              "Sin explicaciones." % (votacion_titulo, lista))
    try:
        resp = cliente.messages.create(model=MODELO, max_tokens=10,
                                       messages=[{"role": "user", "content": prompt}])
    except Exception as e:
        print("    (aviso IA elegir: %s)" % e, file=sys.stderr)
        return None
    txt = "".join(b.text for b in resp.content if hasattr(b, "text")).strip().lower()
    if "ningun" in txt:
        return None
    m = re.search(r"\d+", txt)
    if m:
        idx = int(m.group())
        if 0 <= idx < len(candidatas):
            return candidatas[idx]
    return None


def top_candidatas(titulo, leyes, n=5, minimo=0.30):
    """Devuelve las n leyes más parecidas por título (con un piso mínimo de
    similitud, para no mandarle a la IA cosas totalmente inconexas)."""
    puntuadas = []
    for l in leyes:
        s = score_titulo(titulo, l.get("titulo", ""))
        if s >= minimo:
            puntuadas.append((s, l))
    puntuadas.sort(key=lambda x: x[0], reverse=True)
    return [l for _, l in puntuadas[:n]]


def confirmar_ia(cliente, votacion_titulo, ley):
    """La IA confirma (sí/no) si una votación corresponde a UNA ley concreta.
    Se usa para validar los matches de título en la zona gris."""
    ref = (ley.get("oracion_ia") or ley.get("titulo") or "")[:200]
    prompt = ("Una votación del Congreso argentino se titula:\n\"%s\"\n\n"
              "¿Corresponde a esta ley en trámite?\n\"%s\"\n\n"
              "Respondé SOLO 'si' o 'no'. Sin explicaciones." % (votacion_titulo, ref))
    try:
        resp = cliente.messages.create(model=MODELO, max_tokens=5,
                                       messages=[{"role": "user", "content": prompt}])
        txt = "".join(b.text for b in resp.content if hasattr(b, "text")).strip().lower()
        return txt.startswith("si") or txt.startswith("sí")
    except Exception as e:
        print("    (aviso IA confirmar: %s)" % e, file=sys.stderr)
        return True   # si la IA falla, no bloqueamos el match de título


def main():
    if not SERVICE_KEY:
        print('Falta $env:SUPABASE_SERVICE_KEY', file=sys.stderr)
        sys.exit(1)

    # Votaciones sin linkear
    votadas = sb_get("/rest/v1/votaciones_congreso?select=id,titulo,ley_bill_id&ley_bill_id=is.null&limit=1000")
    # Leyes candidatas: TODAS las que tengan texto (publicadas o no).
    # Traemos tambien 'publicada' para decidir si hay que despublicar al linkear.
    leyes = sb_get("/rest/v1/leyes?select=bill_id,titulo,oracion_ia,publicada&texto_oficial=not.is.null&limit=5000")
    print("Votaciones sin linkear: %d | Leyes con texto (candidatas): %d\n"
          % (len(votadas), len(leyes)), file=sys.stderr)
    if not votadas or not leyes:
        print("Nada para linkear.", file=sys.stderr)
        return

    cliente = None
    if not SIN_IA:
        clave = os.environ.get("ANTHROPIC_API_KEY")
        if clave:
            try:
                from anthropic import Anthropic
                cliente = Anthropic(api_key=clave)
            except ImportError:
                print("(anthropic no instalado: solo linkeo por título)", file=sys.stderr)
        else:
            print("(sin ANTHROPIC_API_KEY: solo linkeo por título)", file=sys.stderr)

    n_titulo = n_ia = 0
    for vt in votadas:
        titulo = vt.get("titulo") or ""
        # 1) TÍTULO
        best = (0.0, None)
        for l in leyes:
            s = score_titulo(titulo, l.get("titulo", ""))
            if s > best[0]:
                best = (s, l)
        if best[0] >= UMBRAL_ALTO and best[1]:
            # título muy confiable: se acepta directo
            metodo, ley, score = "titulo", best[1], round(best[0], 3)
        elif best[0] >= UMBRAL_TITULO and best[1]:
            # zona gris: la IA confirma antes de aceptar (si hay IA)
            if cliente:
                if confirmar_ia(cliente, titulo, best[1]):
                    metodo, ley, score = "titulo+ia", best[1], round(best[0], 3)
                else:
                    ley, metodo, score = None, None, None   # la IA lo descartó
            else:
                metodo, ley, score = "titulo", best[1], round(best[0], 3)  # sin IA: se acepta
        elif cliente:
            # título no alcanza: la IA elige entre las POCAS más parecidas (o ninguna)
            ley = linkear_ia(cliente, titulo, top_candidatas(titulo, leyes))
            metodo, score = ("ia", None) if ley else (None, None)
        else:
            ley, metodo, score = None, None, None

        if ley:
            if metodo == "titulo":
                n_titulo += 1
            else:
                n_ia += 1
            estaba_pub = bool(ley.get("publicada"))
            marca = "[%s%s]" % (metodo, (" %.2f" % score) if score else "")
            print("  %s %s -> %s  %s" % (marca, titulo[:46], ley["bill_id"],
                  "(sale de Votar)" if estaba_pub else "(no estaba en Votar)"), file=sys.stderr)
            if not DRY:
                # 1) Guardar el link en la votación (siempre)
                sb_patch(vt["id"], {"ley_bill_id": ley["bill_id"],
                                    "match_metodo": metodo,
                                    "match_score": score})
                # 2) Si la ley ESTABA publicada, ya fue votada -> sale de "Votar":
                #    se despublica y se marca. (No se borra: sigue en Votadas.)
                #    Si NO estaba publicada, no se toca su estado (solo queda linkeada).
                if estaba_pub:
                    r = requests.patch(
                        SUPABASE_URL + "/rest/v1/leyes?bill_id=eq." + ley["bill_id"],
                        headers={"apikey": SERVICE_KEY, "Authorization": "Bearer " + SERVICE_KEY,
                                 "Content-Type": "application/json"},
                        data=json.dumps({"publicada": False, "estado_tramite": "votada",
                                         "curaduria_estado": "votada"}),
                        timeout=30)
                    if r.status_code >= 300:
                        print("    (aviso: no se pudo despublicar la ley)", file=sys.stderr)

    print("\n=== RESULTADO ===", file=sys.stderr)
    print("Linkeadas por título: %d | por IA: %d | total: %d de %d"
          % (n_titulo, n_ia, n_titulo + n_ia, len(votadas)), file=sys.stderr)
    if DRY:
        print("(DRY-RUN: no se escribió nada.)", file=sys.stderr)


if __name__ == "__main__":
    main()
