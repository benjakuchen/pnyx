# -*- coding: utf-8 -*-
"""
10_votadas.py — OBRERO DE VOTACIONES DEL CONGRESO (la otra mitad de Pnyx)
==========================================================================
v2 (12/07/2026): AMBAS camaras desde como_voto.
  - Diputados: HCDN tiene anti-bot -> via como_voto.
  - Senado:    tambien activo anti-bot (F5/TSPD) -> via como_voto.
  como_voto (rquiroga7) resuelve el anti-bot de las dos, es open source,
  fuente oficial, se actualiza lunes y jueves. Una sola fuente = mas estable.

Guarda SOLO la votacion "en general" de cada ley. Linkea con el feed por titulo (metodo 2).

Filtros por camara:
  - Diputados (titulos sin campo tp): 3 niveles por O.D.
      sin O.D. -> interna (descarta) | con O.D. + Cap/Titulo/Art -> particular (descarta) | resto -> GUARDA
  - Senado (tiene campo tp): guarda solo tp que empiece con "EN GENERAL".
      "EN GENERAL" y "EN GENERAL Y EN PARTICULAR" -> GUARDA
      "EN PARTICULAR" -> particular (descarta) | "" -> interna (descarta)

Requisitos:
  $env:SUPABASE_SERVICE_KEY = "..."   (service_role, NO la publishable)
Uso:
  python 10_votadas.py            -> baja 2026 y sube
  python 10_votadas.py --dry-run  -> baja y muestra, NO sube
  python 10_votadas.py --anio 2026 --solo senado
"""

import os
import re
import sys
import json
import time
import argparse
import unicodedata
from datetime import datetime
from difflib import SequenceMatcher

import requests

# modulo compartido de clasificacion (mismo archivo en la carpeta PNYX)
from clasificar_tipo import clasificar_tipo

SUPA_URL = "https://ihmbhbhwlntsjqdavxge.supabase.co"
SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
PUBLISHABLE_KEY = "sb_publishable_ih-dOjPauQayOpzn7uL6vw_vIt96ZHR"

COMO_VOTO_DIP = "https://raw.githubusercontent.com/rquiroga7/como_voto/main/data/diputados.json"
COMO_VOTO_SEN = "https://raw.githubusercontent.com/rquiroga7/como_voto/main/data/senadores.json"

UMBRAL_MATCH = 0.65
VOTE_DECODE = {1: "AFIRMATIVO", 2: "NEGATIVO", 3: "ABSTENCION", 4: "AUSENTE", 5: "PRESIDENTE"}

HEADERS_WEB = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) pnyx-obrero"}

# --- expediente embebido en titulos del Senado: "PE-159/25-PL" ---
RE_EXP_SEN = re.compile(r"([A-Z]{1,3}-\d{1,5}/\d{2,4}-[A-Z]{1,3})")

STOP = set("de la el los las y del en a al para por con su sus un una o e sobre respecto "
           "que se dict may od vot gral proyecto ley modificacion modificaciones".split())

def norm_titulo(t):
    t = unicodedata.normalize("NFKD", t or "").encode("ascii", "ignore").decode().lower()
    t = re.sub(r"[^a-z0-9 ]", " ", t)
    return " ".join(p for p in t.split() if p not in STOP and len(p) > 2)

def norm_nombre(n):
    n = unicodedata.normalize("NFKD", n or "").encode("ascii", "ignore").decode().upper()
    return re.sub(r"\s+", " ", n).strip()

def norm_bloque(b):
    if not b: return None
    b = unicodedata.normalize("NFKD", b).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", b).strip().title()

def score_titulo(a, b):
    na, nb = norm_titulo(a), norm_titulo(b)
    return SequenceMatcher(None, na, nb).ratio() if (na and nb) else 0.0

def limpiar_titulo(t):
    t = re.sub(r"^O\.?\s*D\.?\s*\d+\s*-\s*", "", t, flags=re.I)
    t = re.sub(r"\.?\s*DICT\.?\s*DE\s*MAY\.?.*$", "", t, flags=re.I)
    t = re.sub(r"\.?\s*VOT\.?\s*EN\s*GRAL.*$", "", t, flags=re.I)
    # senado: sacar el expediente y O.D. embebidos del titulo
    t = RE_EXP_SEN.sub("", t)
    t = re.split(r",?\s*O\.?\s*D\.?\s*\d", t)[0]
    return t.strip(" .,;")

def extraer_exp_sen(t):
    m = RE_EXP_SEN.search(t or "")
    return m.group(1) if m else None

def extraer_od(t):
    m = re.search(r"O\.?\s*D\.?\s*N?\.?\s*(\d+(?:/\d{4})?)", t or "", re.I)
    return m.group(1) if m else None

def clasificar_dip(titulo):
    tu = titulo.upper()
    if not re.search(r"O\.?\s*D\.?\s*\d+", tu): return "interna"
    if re.search(r"CAP[IÍ]TULO|T[IÍ]TULO\s+[IVXLCDM]|ART[ÍI]?CULO|ART\.\s|INC\.", tu): return "particular"
    return "general"

def clasificar_sen(tp):
    """El Senado trae campo tp. Guarda solo 'EN GENERAL' / 'EN GENERAL Y EN PARTICULAR'."""
    tp = (tp or "").strip().upper()
    if tp.startswith("EN GENERAL"): return "general"
    if tp == "EN PARTICULAR": return "particular"
    return "interna"  # vacio = ratificacion/mocion/habilitacion


class Supa:
    def __init__(self, url, key, dry, read_key=None):
        self.url = url.rstrip("/"); self.dry = dry
        self.h = {"apikey": key, "Authorization": f"Bearer {key}",
                  "Content-Type": "application/json", "Prefer": "return=representation"}
        rk = read_key or key
        self.rh = {"apikey": rk, "Authorization": f"Bearer {rk}"}
        self._cache_leyes = {}; self._cache_legis = {}

    def _get(self, path):
        r = requests.get(self.url + path, headers=self.rh, timeout=30); r.raise_for_status()
        return r.json()

    def leyes(self, camara):
        if camara not in self._cache_leyes:
            self._cache_leyes[camara] = self._get(
                f"/rest/v1/leyes?camara=eq.{camara}&select=bill_id,titulo&limit=3000")
        return self._cache_leyes[camara]

    def actas_existentes(self, camara):
        data = self._get(f"/rest/v1/votaciones_congreso?camara=eq.{camara}&select=acta_id&limit=10000")
        return {row["acta_id"] for row in data}

    def upsert_legislador(self, nombre, camara, bloque, provincia):
        nn = norm_nombre(nombre); clave = (nn, camara)
        if clave in self._cache_legis: return self._cache_legis[clave]
        if self.dry:
            fake = f"DRY-{len(self._cache_legis)+1}"; self._cache_legis[clave] = fake; return fake
        body = [{"nombre": nombre, "nombre_normalizado": nn, "camara": camara,
                 "bloque": bloque, "provincia": provincia,
                 "actualizado_en": datetime.now().isoformat()}]
        r = requests.post(self.url + "/rest/v1/legisladores?on_conflict=nombre_normalizado,camara",
            headers={**self.h, "Prefer": "resolution=merge-duplicates,return=representation"},
            data=json.dumps(body), timeout=30)
        r.raise_for_status()
        lid = r.json()[0]["id"]; self._cache_legis[clave] = lid; return lid

    def insert_votacion(self, v):
        if self.dry: return "DRY-VOT"
        r = requests.post(self.url + "/rest/v1/votaciones_congreso?on_conflict=camara,acta_id",
            headers={**self.h, "Prefer": "resolution=merge-duplicates,return=representation"},
            data=json.dumps([v]), timeout=30)
        r.raise_for_status(); return r.json()[0]["id"]

    def insert_votos(self, filas):
        if self.dry or not filas: return
        for i in range(0, len(filas), 500):
            r = requests.post(self.url + "/rest/v1/votos_nominales?on_conflict=votacion_id,legislador_id",
                headers={**self.h, "Prefer": "resolution=merge-duplicates,return=minimal"},
                data=json.dumps(filas[i:i+500]), timeout=30)
            r.raise_for_status()

    def borrar_camara(self, camara):
        """Borra todas las votaciones (y sus votos por cascade) de una camara."""
        if self.dry: return
        r = requests.delete(self.url + f"/rest/v1/votaciones_congreso?camara=eq.{camara}",
            headers={**self.h, "Prefer": "return=minimal"}, timeout=30)
        r.raise_for_status()


def linkear(titulo, leyes):
    best = (0.0, None)
    for ley in leyes:
        s = score_titulo(titulo, ley.get("titulo", ""))
        if s > best[0]: best = (s, ley)
    s, ley = best
    return (ley["bill_id"], round(s, 3)) if (s >= UMBRAL_MATCH and ley) else (None, None)


def bajar_json(url):
    r = requests.get(url, headers=HEADERS_WEB, timeout=60); r.raise_for_status()
    return r.json()


def mirror_a_storage(url, nombre_base, dry):
    """Sube una copia cruda del JSON de como_voto a Supabase Storage.
    Guarda dos versiones: una con fecha (historial) y una 'latest' (ultima).
    Bucket: mirror-comovoto (crearlo antes en el panel de Supabase)."""
    if dry:
        print(f"    [mirror] (dry-run) omito subir {nombre_base}")
        return
    if not SERVICE_KEY:
        print(f"    [mirror] sin service key, omito {nombre_base}")
        return
    try:
        r = requests.get(url, headers=HEADERS_WEB, timeout=60); r.raise_for_status()
        contenido = r.content  # bytes crudos
        hoy = datetime.now().strftime("%Y-%m-%d")
        bucket = "mirror-comovoto"
        for ruta in [f"{nombre_base}_latest.json", f"historial/{nombre_base}_{hoy}.json"]:
            up = requests.post(
                f"{SUPA_URL}/storage/v1/object/{bucket}/{ruta}",
                headers={"apikey": SERVICE_KEY, "Authorization": f"Bearer {SERVICE_KEY}",
                         "Content-Type": "application/json", "x-upsert": "true"},
                data=contenido, timeout=60)
            if up.status_code not in (200, 201):
                print(f"    [mirror] {ruta}: HTTP {up.status_code} {up.text[:120]}")
            else:
                print(f"    [mirror] subido {ruta} ({len(contenido)//1024} KB)")
    except Exception as e:
        print(f"    [mirror] ERROR con {nombre_base}: {e}")


def procesar_camara(supa, camara, url, anio, stats):
    """Procesa una camara desde como_voto. Diputados y Senado comparten estructura."""
    print(f"\n=== {camara.upper()} (fuente: como_voto) ===")
    print("  bajando JSON fresco...")
    d = bajar_json(url)
    # respaldo automatico del JSON crudo a Supabase Storage (independencia de como_voto)
    mirror_a_storage(url, camara.lower(), supa.dry)
    names, blocs, provs = d["names"], d["blocs"], d["provinces"]
    votaciones = d["votaciones"]

    ya = supa.actas_existentes(camara)
    leyes = supa.leyes(camara)
    del_anio = [v for v in votaciones if str(anio) in str(v.get("d", ""))]
    print(f"  actas ya en base: {len(ya)} | leyes en feed: {len(leyes)} | votaciones {anio}: {len(del_anio)}")

    es_senado = (camara == "Senado")
    nuevas = 0
    for v in sorted(del_anio, key=lambda x: x.get("d", "")):
        acta_id = str(v["id"])
        if acta_id in ya: continue

        # --- filtro por camara ---
        if es_senado:
            cat = clasificar_sen(v.get("tp", ""))
        else:
            cat = clasificar_dip(v["t"])
        if cat != "general":
            stats[f"{camara.lower()[:3]}_descarta_{cat}"] += 1
            continue

        titulo = limpiar_titulo(v["t"])
        expediente = extraer_exp_sen(v["t"]) if es_senado else None

        # clasificar tipo (LEY/ACUERDO/DECLARACION/RESOLUCION/HOMENAJE/INTERNO)
        tipo = clasificar_tipo(titulo, expediente)
        if tipo == "INTERNO":
            stats[f"{camara.lower()[:3]}_descarta_interno_tipo"] += 1
            continue

        try:
            votada_en = datetime.strptime(v["d"].strip(), "%d/%m/%Y - %H:%M").isoformat()
        except Exception:
            votada_en = None

        bill_id, msc = linkear(titulo, leyes)
        registro = {
            "camara": camara, "acta_id": acta_id,
            "titulo": titulo, "orden_del_dia": extraer_od(v["t"]),
            "expediente_fuente": expediente,
            "tipo": tipo,
            "resultado": v.get("r"),
            "afirmativos": v.get("a", 0), "negativos": v.get("n", 0),
            "abstenciones": v.get("b", 0), "ausentes": v.get("u", 0),
            "presidente": sum(1 for x in v["v"] if x[3] == 5),
            "votada_en": votada_en,
            "ley_bill_id": bill_id, "match_score": msc,
            "fuente": "como_voto",
        }
        vid = supa.insert_votacion(registro)

        filas = []
        for ni, bi, pi, code in v["v"]:
            nombre = names[ni]
            bloque = norm_bloque(blocs[bi]); prov = norm_bloque(provs[pi])
            lid = supa.upsert_legislador(nombre, camara, bloque, prov)
            filas.append({"votacion_id": vid, "legislador_id": lid,
                          "voto": VOTE_DECODE.get(code, "AUSENTE"),
                          "bloque_en_voto": bloque, "provincia_en_voto": prov})
        supa.insert_votos(filas)
        nuevas += 1
        link = f" -> link {bill_id} ({msc})" if bill_id else ""
        exp = f" [{expediente}]" if expediente else ""
        print(f"    + [{acta_id}] {tipo:11s}{exp} {titulo[:44]}{link}")

    stats[f"{camara.lower()[:3]}_guardadas"] = nuevas
    print(f"  {camara}: {nuevas} votaciones nuevas guardadas.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--anio", type=int, default=2026)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--solo", choices=["diputados", "senado"])
    ap.add_argument("--recargar-senado", action="store_true",
                    help="borra los del Senado (scraping viejo) y recarga desde como_voto")
    ap.add_argument("--recargar-todo", action="store_true",
                    help="borra Diputados Y Senado y recarga limpio (para aplicar tipos nuevos)")
    args = ap.parse_args()

    if not args.dry_run and not SERVICE_KEY:
        print("ERROR: falta $env:SUPABASE_SERVICE_KEY (service_role).")
        print("       Prueba sin subir:  python 10_votadas.py --dry-run")
        sys.exit(1)

    print(f"OBRERO 10_votadas v2 — anio {args.anio}" + ("  [DRY-RUN]" if args.dry_run else ""))
    supa = Supa(SUPA_URL, SERVICE_KEY or "dry", args.dry_run, read_key=PUBLISHABLE_KEY)

    if args.recargar_todo and not args.dry_run:
        print("  Borrando TODAS las votaciones (Diputados + Senado) para recargar con tipos...")
        supa.borrar_camara("Diputados")
        supa.borrar_camara("Senado")
        print("  Listo. Se recargan limpias desde como_voto.")
    elif args.recargar_senado and not args.dry_run:
        print("  Borrando votaciones viejas del Senado (scraping)...")
        supa.borrar_camara("Senado")
        print("  Listo. Se recargan desde como_voto.")

    from collections import defaultdict
    stats = defaultdict(int); t0 = time.time()
    try:
        if args.solo != "senado":
            procesar_camara(supa, "Diputados", COMO_VOTO_DIP, args.anio, stats)
        if args.solo != "diputados":
            procesar_camara(supa, "Senado", COMO_VOTO_SEN, args.anio, stats)
    except requests.HTTPError as e:
        print(f"\nERROR HTTP: {e}\n(¿service key correcta? ¿corriste los SQL del esquema?)")
        sys.exit(1)

    print("\n" + "="*50 + "\nRESUMEN")
    for k in sorted(stats): print(f"  {k}: {stats[k]}")
    print(f"  tiempo: {time.time()-t0:.1f}s")
    if args.dry_run:
        print("\n(DRY-RUN: no se escribio nada. Sacá --dry-run para subir.)")

if __name__ == "__main__":
    main()
