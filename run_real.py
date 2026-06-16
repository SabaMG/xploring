# -*- coding: utf-8 -*-
"""Exécute rendu/notebook.ipynb sur les VRAIES données (CA, OSM activé)."""
import os, json, time, sys
os.environ["MPLBACKEND"] = "Agg"
NB = os.path.abspath("rendu/notebook.ipynb")
nb = json.load(open(NB, encoding="utf-8"))
os.chdir("rendu")                       # sorties (csv/html) dans rendu/
g = {"__name__": "__main__"}
t0 = time.time()
for i, c in enumerate(nb["cells"]):
    if c["cell_type"] != "code":
        continue
    src = "".join(c["source"])
    if "%pip" in src:
        continue
    ts = time.time()
    try:
        exec(compile(src, f"<cell {i}>", "exec"), g)
    except Exception:
        import traceback
        print(f"\n*** ECHEC cellule {i} apres {time.time()-ts:.1f}s ***", flush=True)
        print(src[:500], flush=True)
        traceback.print_exc()
        sys.exit(1)
    print(f"[cell {i:>2}] OK  {time.time()-ts:6.1f}s  (total {time.time()-t0:6.1f}s)", flush=True)
    if i == 2:
        import matplotlib.pyplot as _p; _p.show = lambda *a, **k: None
print(f"\n=== RUN COMPLET OK en {time.time()-t0:.0f}s ===", flush=True)
print("Sorties:", [f for f in ["zones_prioritaires.csv","carte_zones_prioritaires.html"] if os.path.exists(f)], flush=True)
