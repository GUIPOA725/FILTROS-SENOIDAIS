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
    n_col = max(1, math.ceil(n / epc))
    perd = perdas(res)
    vent = ventilacao(perd["total"], ped.amb_c)
    colunas = []
    for i in range(n_col):
        lote = list(range(i * epc, min(n, (i + 1) * epc)))
        colunas.append(dict(funcao=f"coluna {i + 1}", largura=LARG_COLUNA, estagios=lote,
                            frente=(["COMANDO (porta)", "PROTEÇÃO GERAL / BARRAMENTO"] if i == 0 else ["BARRAMENTO"]) +
                                   [f"ESTÁGIO {k + 1}" for k in lote],
                            tras=[f"REATOR {k + 1}" for k in lote] + ["EXAUSTOR (teto)"],
                            zonas=["EXAUSTOR"]))
    larg = n_col * LARG_COLUNA
    prof = PROF_FRENTE + PROF_TRAS + 40
    prof = 800 if prof <= 800 else 1000
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
    return dict(dimensoes_mm=dict(altura=H, largura=larg, profundidade=prof), colunas=colunas, arranjo="frente/trás",
                perdas_w=perd, ventilacao=vent, avisos=avisos,
                folgas_mm=dict(entre_capacitores=30, capacitor_parede=30, entre_fases=30, exaustor_componentes=100,
                               parede_traseira_instalacao=600),
                base="Padrão Electric/AGCO Ibirubá (capacitores na frente, reatores atrás, separados) + IEC 60890 + "
                     "Schneider PB Guide (reator nunca abaixo do capacitor; entrada de ar embaixo, saída no topo)")
