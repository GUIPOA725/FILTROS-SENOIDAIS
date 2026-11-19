import sys, os, pickle, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fsen import atp
base = sys.argv[1]
todos = pickle.load(open(os.path.join(base, "casos.pkl"), "rb"))
out = {}
for cid, casos in todos.items():
    res = atp.comparar_casos(casos, os.path.join(base, cid))
    out[cid] = [dict(ponto=r["ponto"], tabela=r["tabela"]) for r in res]
    for r in res:
        div = [f"{l['grandeza']} Py {l['python']:g} ATP {l['atp']:g} ({l['dif_pct']:+.1f}%)" for l in r["tabela"] if not l["convergiu"]]
        thd = {l["grandeza"]: (l["python"], l["atp"]) for l in r["tabela"] if "THD" in l["grandeza"] or "DHT" in l["grandeza"]}
        print(cid, r["ponto"][:16], "OK" if not div else "DIV", thd, div[:3])
json.dump(out, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "atp_reais.json"), "w"), ensure_ascii=False, indent=1, default=float)
