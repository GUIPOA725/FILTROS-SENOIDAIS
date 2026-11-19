"""Gera decks ATP + desenhos ATPDraw (XML) de cada filtro REAL (projeto_manual) em todos os pontos de operação."""
import sys, os, json, pickle
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fsen.dimensionamento import carregar_catalogo, projeto_manual
from fsen import atp
from casos_reais import CASOS, pedido
cat = carregar_catalogo()
saida = sys.argv[1]
todos = {}
for c in CASOS:
    r = c["real"]
    pr = projeto_manual(pedido(c), cat, c["fs_khz"], r["L1_uH"], r["cap_id"], r["ligacao"], r["n_por_ramo"])
    casos = atp.preparar_casos(pr, cat, os.path.join(saida, c["id"]))
    todos[c["id"]] = casos
    print(c["id"], [(x["nome"], x["ponto"], x.get("atpdraw_erro")) for x in casos], flush=True)
pickle.dump(todos, open(os.path.join(saida, "casos.pkl"), "wb"))
