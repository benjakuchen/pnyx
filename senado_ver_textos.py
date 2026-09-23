#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Pnyx - (c) 2026 Benjamin Kuchen. Obra protegida por la Ley 11.723 (Argentina).
"""
Muestra si bill_id concretos tienen texto/resumen. Pasar los numeros.
Uso:  python senado_ver_textos.py 637 638 639 640 641
"""
import os, sys
try:
    from supabase import create_client
except ImportError:
    print("Falta supabase:  pip install supabase", file=sys.stderr); sys.exit(1)

SUPABASE_URL = "https://ihmbhbhwlntsjqdavxge.supabase.co"
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")

def main():
    if not SUPABASE_KEY:
        print('Falta $env:SUPABASE_SERVICE_KEY', file=sys.stderr); sys.exit(1)
    nums = [a for a in sys.argv[1:] if a.isdigit()]
    if not nums:
        print("Pasá numeros de expediente, ej: python senado_ver_textos.py 637 638 641")
        return
    sb = create_client(SUPABASE_URL, SUPABASE_KEY)
    print("  %-16s %-5s %-5s %s" % ("bill_id","txt","res","titulo"))
    print("  " + "-"*70)
    for n in nums:
        bid = "SENADO%s-26" % n
        r = sb.table("leyes").select("bill_id,texto_oficial,oracion_ia,titulo") \
            .eq("bill_id", bid).limit(1).execute().data
        if not r:
            print("  %-16s NO EXISTE en la base" % bid); continue
        f = r[0]
        txt = "si" if (f.get("texto_oficial") and len(str(f.get("texto_oficial")))>200) else "-"
        res = "si" if f.get("oracion_ia") else "-"
        print("  %-16s %-5s %-5s %s" % (bid, txt, res, (f.get("titulo") or "")[:45]))

if __name__ == "__main__":
    main()
