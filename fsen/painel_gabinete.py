"""Dimensionamento do gabinete do banco (dessintonizado / sintonizado) – v1.17.0 (em construção).

Base: padrão Electric dos bancos TECHNIP (20/12/2016, dados/referencias_paineis.json)
  • até ~100 kVAr: 1 coluna 2200×600×600 – de cima p/ baixo: exaustor, comando, capacitores, rack de indutores;
  • acima: colunas de 800 mm (comando | capacitores | indutores), 2200 × N × 800 – exaustão no topo, admissão de ar
    na traseira junto aos indutores.
Térmica: balanço de calor IEC 60890 / IEC TR 60890 em ventilação forçada – vazão V = 3,1·P/ΔT [m³/h] (ar ao nível do mar),
com folga de filtro/grelha; exaustores escolhidos numa série comercial 230 V.
Determinístico: mesma entrada → mesmo gabinete.
"""
from __future__ import annotations

import json
import math
import os

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REF = os.path.join(RAIZ, "dados", "referencias_paineis.json")

ALTURA = 2000                             # AGCO Ibirubá (IFG): 2000 × 1600 × 800
PROF_1COL, PROF_NCOL = 600, 800
LARG_COL = (600, 800)                     # larguras comerciais de coluna
VAZOES_EXAUSTOR = (55, 105, 160, 230, 300, 550, 850)   # m³/h livres (série comercial 230 V com grelha/filtro)
K_FILTRO = 0.70                           # perda de vazão do filtro de saída/entrada
DT_MAX = 10.0                             # K – elevação interna máxima admitida (ar interno ≤ amb + 10 K)
W_CAP_POR_KVAR = 0.45                     # perdas típicas de capacitor de potência (W/kvar)
W_CONTATOR = 12.0                         # bobina + contatos por contatora de capacitor
W_FUSIVEL_POR_A = 0.08                    # NH: ≈ 0,08 W/A de corrente nominal de estágio (orientativo)
W_COMANDO = 60.0                          # controlador, trafo de comando, relés


def referencias():
    try:
        return json.load(open(REF, encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def perdas(res):
    """Perdas internas do painel (W) por origem, a partir do dimensionamento do banco."""
    est = res["estagios"]
    p_reat = sum(float(e["requisitos"].get("P_max") or 0) for e in est)
    p_cap = sum(float(e.get("Q_cap_nom_kvar") or e["Q_kvar"]) * W_CAP_POR_KVAR for e in est)
    p_ctt = W_CONTATOR * len(est)
    p_fus = sum(W_FUSIVEL_POR_A * float(e["I_cap_rms"]) for e in est) * 3
    return dict(reatores=round(p_reat), capacitores=round(p_cap), contatoras=round(p_ctt),
                fusiveis=round(p_fus), comando=W_COMANDO,
                total=round(p_reat + p_cap + p_ctt + p_fus + W_COMANDO))


def ventilacao(P_w, amb_c=40.0, dt_max=DT_MAX):
    """Vazão necessária (IEC 60890, ventilação forçada) e escolha de exaustores."""
    V = 3.1 * P_w / dt_max                                   # m³/h
    V_proj = V / K_FILTRO
    for q in VAZOES_EXAUSTOR:                                # menor exaustor que resolve com até 2 unidades
        n = max(1, math.ceil(V_proj / q))
        if n <= 2:
            break
    else:
        q = VAZOES_EXAUSTOR[-1]
        n = math.ceil(V_proj / q)
    return dict(vazao_necessaria_m3h=round(V), vazao_projeto_m3h=round(V_proj), exaustor_m3h=q, n_exaustores=n,
                vazao_instalada_m3h=round(n * q * K_FILTRO), dt_k=round(3.1 * P_w / (n * q * K_FILTRO), 1),
                t_interna_c=round(amb_c + 3.1 * P_w / (n * q * K_FILTRO), 1))


ESTAGIOS_POR_COLUNA = 4                   # AGCO Ibirubá: 7 estágios em 2 colunas de 800 (2000×1600×800)
LARG_COLUNA = 800
PROF_FRENTE = 360                         # compartimento frontal: placas de estágio (chave-fusível, contatora, capacitores)
PROF_TRAS = 400                           # compartimento traseiro: reatores (separado por chapa divisória)
AREA_ENTRADA_CM2_POR_KVAR = 1.0           # Schneider PB Guide: 100 cm² até 100 kvar, 200 cm² até 200 kvar


def gabinete(ped, res, altura=None, estagios_por_coluna=None):
    """Arranjo padrão Electric/AGCO (Ibirubá, filtros CVI): capacitores NA FRENTE, reatores ATRÁS, compartimentos
    separados por chapa divisória vertical; colunas de 800 mm, profundidade 800, altura 2000.
    Ar entra embaixo (venezianas da porta frontal e traseira), sobe e sai pelos exaustores no teto, sobre os reatores.
    Termostatos: T1 liga a ventilação a 35 °C, T2 desliga o banco a 55 °C (no topo, longe dos reatores)."""
    est = res["estagios"]
    n = len(est)
    Q = float(res.get("Q_total_kvar") or sum(e["Q_kvar"] for e in est))
    H = int(altura or ALTURA)
    epc = int(estagios_por_coluna or ESTAGIOS_POR_COLUNA)
    # v1.17.4: largura pela tabela de dimensionais da IFG (BCD 50 kvar/estágio, 380 V) e projetos reais (AGCO 2021, Panatlântica
    # 2024): acesso frontal/traseiro (prof. 800) ≈ 200 mm por estágio, mín. 800 (4→800, 6→1200, 8→1600, 10→2000);
    # acesso só frontal (prof. 400) ≈ 320 mm por estágio (2→800, 4→1200, 6→2000, 10→3200). Portas de até 800 mm.
    acesso = getattr(ped, "acesso_painel", "") or "frontal/traseiro"
    if estagios_por_coluna:
        larg = int(math.ceil(n / epc)) * LARG_COLUNA
    elif acesso == "frontal":
        larg = max(800, int(math.ceil(320 * n / 400.0)) * 400)
    else:
        larg = max(800, int(math.ceil(200 * n / 400.0)) * 400)   # módulos de 400 (AGCO 7 est. → 1600)
    n_col = max(1, int(math.ceil(larg / LARG_COLUNA)))
    bw = (larg // n_col) // 200 * 200
    w_col = [bw] * n_col
    for i in range((larg - bw * n_col) // 200):
        w_col[i] += 200
    nota_reator = ""
    rm = res.get("reator_mm")                     # v1.24.0: medidas REAIS do reator Electric (FEM) → cabe na coluna?
    if rm and rm.get("largura") and acesso != "frontal":
        rL, rA = float(rm["largura"]), float(rm["altura"])
        niveis = max(1, int((H - 100 - 300) // (rA + 80)))           # base 100, topo/exaustor 300, prateleira+ar 80
        def cap(wc):
            return max(1, int((wc - 2 * 30 + 30) // (rL + 30))) * niveis
        if sum(cap(w) for w in w_col) < n:                            # não cabe: escolhe colunas que caibam (menor largura total)
            melhor = None
            for wc in (800, 1000, 1200):
                nc = int(math.ceil(n / cap(wc)))
                if melhor is None or nc * wc < melhor[0] * melhor[1] or (nc * wc == melhor[0] * melhor[1] and nc < melhor[0]):
                    melhor = (nc, wc)
            n_col, w_col = melhor[0], [melhor[1]] * melhor[0]
            larg = sum(w_col)
            nota_reator = (f"Largura ajustada às medidas reais do reator ({rL:.0f} × {rm.get('profundidade', 0):.0f} × {rA:.0f} mm): "
                           f"{cap(w_col[0])} reator(es) por coluna de {w_col[0]} mm ({niveis} níveis) → {n_col} coluna(s).")
    perd = perdas(res)
    vent = ventilacao(perd["total"], ped.amb_c)
    colunas = []
    base = 0
    for i in range(n_col):
        q = n // n_col + (1 if i < n % n_col else 0)
        lote = list(range(base, base + q))
        base += q
        colunas.append(dict(funcao=f"coluna {i + 1}", largura=w_col[i], estagios=lote,
                            frente=(["COMANDO (porta)", "PROTEÇÃO GERAL / BARRAMENTO"] if i == 0 else ["BARRAMENTO"]) +
                                   [f"ESTÁGIO {k + 1}" for k in lote],
                            tras=[f"REATOR {k + 1}" for k in lote] + ["EXAUSTOR (teto)"],
                            zonas=["EXAUSTOR"]))
    prof = 400 if acesso == "frontal" else 800
    vent["n_exaustores"] = max(vent["n_exaustores"], n_col)        # pelo menos 1 exaustor por coluna, sobre os reatores
    vent["vazao_instalada_m3h"] = round(vent["n_exaustores"] * vent["exaustor_m3h"] * K_FILTRO)
    vent["dt_k"] = round(3.1 * perd["total"] / vent["vazao_instalada_m3h"], 1)
    vent["t_interna_c"] = round(ped.amb_c + vent["dt_k"], 1)
    vent["area_entrada_cm2"] = int(max(100, math.ceil(Q * AREA_ENTRADA_CM2_POR_KVAR / 50) * 50))
    vent["termostatos"] = [dict(tag="-B0", ajuste_c=35, funcao="liga exaustores"),
                           dict(tag="-BT2", ajuste_c=55, funcao="desliga o banco (sobretemperatura)")]
    avisos = []
    if vent["t_interna_c"] > ped.amb_c + DT_MAX + 0.05:
        avisos.append(f"Temperatura interna {vent['t_interna_c']} °C acima de amb+{DT_MAX:.0f} K – rever ventilação.")
    if ped.amb_c + vent["dt_k"] > 55:
        avisos.append("Ar interno > 55 °C (máximo dos capacitores IEC 60831 classe D) – aumentar ventilação.")
    if nota_reator:
        avisos.append(nota_reator)
    return dict(dimensoes_mm=dict(altura=H, largura=larg, profundidade=prof), colunas=colunas, arranjo="frente/trás",
                perdas_w=perd, ventilacao=vent, avisos=avisos,
                folgas_mm=dict(entre_capacitores=30, capacitor_parede=30, entre_fases=30, exaustor_componentes=100,
                               parede_traseira_instalacao=600),
                base="Padrão Electric/AGCO Ibirubá (capacitores na frente, reatores atrás, separados) + IEC 60890 + "
                     "Schneider PB Guide (reator nunca abaixo do capacitor; entrada de ar embaixo, saída no topo)")
