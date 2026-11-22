"""Especificação de MONTAGEM do reator pelo campo magnético calculado (FEM) – REQ-REA-010 (v1.25.2).

Antes as distâncias entre reatores, até as partes metálicas e até os cabos eram no chute. Aqui o MESMO modelo de elementos
finitos do projeto do reator (ind_fem, corte 2D frontal, Az) é resolvido com uma caixa de ar grande e a corrente de PICO em
operação (fase lateral no pico: I, −I/2, −I/2). Mede-se |B| eficaz (60 Hz) ao longo de linhas saindo da superfície externa das
bobinas: para o LADO (vizinho na prateleira) e para CIMA (canaleta/cabos). A frente/trás das bobinas (porta/placa) não está no
corte 2D: usa-se o decaimento lateral como estimativa (as bobinas têm a mesma espessura nas quatro faces) – declarado no relatório.

Critérios (declarados – engenharia Electric/FSEN, auditáveis):
  • aço magnético (prateleira, estrutura, placa, quadro do vizinho): B_ef ≤ 2 mT (aquecimento por correntes induzidas desprezível);
  • cabos de força (Cu, isolados): B_ef ≤ 5 mT (força/aquecimento desprezíveis; laços fechados evitados);
  • cabos de comando/sinal: B_ef ≤ 1 mT (tensão induzida em laços de comando);
  • pessoas na porta aberta: B_ef ≤ 1 mT – nível de referência ocupacional ICNIRP 2010 (25 Hz–300 Hz).
"""
from __future__ import annotations

import math

import numpy as np

CRITERIOS_mT = {"aco": 2.0, "forca": 5.0, "comando": 1.0, "pessoas": 1.0}


def _modelo(d, margem):
    from . import ind_projeto as IP
    from .ind_fem import ModeloIndutor
    a = d["a"]
    xl = [i * (a + d["ww"]) for i in range(3)]
    ng = 2 if str(d.get("pos_gap", "")).startswith("culatra") else max(int(d.get("ng") or 1), 1)
    cond = IP._condutores(d, xl, a)
    return ModeloIndutor(dict(a=a, b=d["b"], hw=d["hw"], ww=d["ww"], ng=ng, gaps=list(d["gaps"]), condutores=cond,
                              pos_gap=d.get("pos_gap", "distribuido"), margem=margem))


def campo_externo(d, margem=0.45):
    """|B| eficaz (T) × distância (m) a partir da superfície externa das bobinas: lado e topo. Devolve dict."""
    M = _modelo(d, margem)
    r = d.get("requisitos") or {}
    Ipk = float(r.get("Ipk") or math.sqrt(2) * float(r.get("In", 100)))
    A = M.resolver([Ipk, -Ipk / 2, -Ipk / 2], mu_r=3000)
    Bx, By = M.B(A) if hasattr(M, "B") else M.m.campo(A)
    Bm = np.hypot(Bx, By) / math.sqrt(2)                       # eficaz (fundamental 60 Hz)
    cx, cy = M.m.cent[:, 0], M.m.cent[:, 1]
    x_ext = max([M.W] + [c["x1"] for c in M.g["condutores"]])  # face externa da bobina da fase lateral
    y_top = max([M.H] + [c["y1"] for c in M.g["condutores"]])
    dist = np.arange(0.0, margem * 0.8, 0.005)
    lado, topo = [], []
    for s in dist:
        sel = (np.abs(cx - (x_ext + s)) < 0.013) & (cy > 0) & (cy < M.H)
        lado.append(float(Bm[sel].max()) if sel.any() else float("nan"))
        sel = (np.abs(cy - (y_top + s)) < 0.013) & (cx > -0.01) & (cx < M.W + 0.01)
        topo.append(float(Bm[sel].max()) if sel.any() else float("nan"))
    return dict(dist_m=dist, lado_T=np.array(lado), topo_T=np.array(topo), Ipk=Ipk)


def _d_lim(dist, B, lim_T):
    ult = None
    for s, b in zip(dist, B):                                  # última distância ACIMA do limite (+ passo) – robusto a buracos da malha
        if not (b <= lim_T) and b == b:
            ult = s
    if ult is None:
        return 0.0
    if ult < dist[-1]:
        return float(ult + (dist[1] - dist[0]))
    return float(dist[-1])


def especificacao(d, layout=None):
    """Distâncias mínimas de montagem (mm) por critério + linhas de verificação contra o arranjo do painel.
    layout = dict(entre_reatores_mm, reator_placa_mm, reator_porta_mm, cabo_forca_mm, cabo_comando_mm) – opcional."""
    ce = campo_externo(d)
    dist, L, T = ce["dist_m"], ce["lado_T"], ce["topo_T"]
    dmin = {k: round(1000 * max(_d_lim(dist, L, v / 1000), _d_lim(dist, T, v / 1000))) for k, v in CRITERIOS_mT.items()}
    # entre reatores: o campo de um não pode passar do critério do aço no quadro/núcleo do vizinho
    dmin["entre_reatores"] = dmin["aco"]
    tab = [dict(dist_mm=round(1000 * s), lado_mT=round(1000 * float(b1), 2), topo_mT=round(1000 * float(b2), 2))
           for s, b1, b2 in zip(dist, L, T) if round(1000 * s) % 25 == 0]
    ver = []
    if layout:
        from . import checagem as CK
        for nome, chave, lim in (("Entre reatores vizinhos (prateleira)", "entre_reatores_mm", dmin["entre_reatores"]),
                                 ("Reator → placa de montagem (aço)", "reator_placa_mm", dmin["aco"]),
                                 ("Reator → porta / pessoas (ICNIRP 1 mT)", "reator_porta_mm", dmin["pessoas"]),
                                 ("Reator → cabos de força", "cabo_forca_mm", dmin["forca"]),
                                 ("Reator → cabos de comando", "cabo_comando_mm", dmin["comando"])):
            v = layout.get(chave)
            if v is None:
                continue
            ver.append(["Reator – campo magnético (FEM)", nome, f"{v:.0f} mm", f"≥ {lim} mm",
                        CK.texto(CK.check(v >= lim, CK.utilizacao(lim, max(v, 1))))])
    return dict(dmin_mm=dmin, tabela=tab, verificacoes=ver, Ipk=ce["Ipk"], criterios_mT=dict(CRITERIOS_mT),
                nota=("Campo eficaz a 60 Hz com a corrente de pico em operação, modelo FEM 2D do próprio reator (corte frontal). "
                      "Frente/trás das bobinas estimadas pelo decaimento lateral."))
