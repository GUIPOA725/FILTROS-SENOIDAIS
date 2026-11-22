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

ALTURA = 2200
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


def gabinete(ped, res):
    """Escolhe o gabinete, as colunas e a ventilação. Retorna dict pronto para desenho/lista de peças."""
    n = len(res["estagios"])
    Q = float(res.get("Q_total_kvar") or sum(e["Q_kvar"] for e in res["estagios"]))
    perd = perdas(res)
    vent = ventilacao(perd["total"], ped.amb_c)
    if Q <= 105 and n <= 4:                                  # padrão TECHNIP 100 kVAr (220 e 460 V)
        colunas = [dict(funcao="única", largura=600,
                        zonas=["EXAUSTOR", "PAINEL DE COMANDO", "BANCO DE CAPACITORES", "RACK DE INDUTORES"])]
        prof = PROF_1COL
    else:
        # padrão TECHNIP 400 kVAr 460 V = 1600 mm: comando 400 | capacitores 600 | indutores 600.
        # Capacidade por coluna (kVAr efetivos, referência 440 V; em 220/380 V a corrente maior reduz na proporção V/440).
        cap_col = 400.0 * min(1.0, ped.tensao_v / 440.0) ** 0.5
        n_col = max(1, math.ceil(Q / (1.05 * cap_col)))      # 5 % de folga (400 kVAr nominais ≈ 410 efetivos)
        w = 600 if Q / n_col <= 1.05 * 400 else 800
        colunas = [dict(funcao="operação/comando", largura=400 if n <= 6 else 600,
                        zonas=["EXAUSTOR", "CONTROLADOR E COMANDO", "PROTEÇÃO GERAL E BARRAMENTO"])]
        colunas += [dict(funcao=f"capacitores {i + 1}", largura=w,
                         zonas=["EXAUSTOR", "FUSÍVEIS E CONTATORAS", "BANCO DE CAPACITORES"]) for i in range(n_col)]
        colunas += [dict(funcao=f"indutores {i + 1}", largura=w,
                         zonas=["EXAUSTOR", "RACK DE INDUTORES", "ADMISSÃO DE AR (traseira)"]) for i in range(n_col)]
        prof = PROF_NCOL
    larg = sum(c["largura"] for c in colunas)
    # exaustores distribuídos: pelo menos 1 por coluna que tem indutores ou capacitores
    quentes = [c for c in colunas if c["funcao"] == "única" or c["funcao"].startswith(("indutores", "capacitores"))]
    vent["n_exaustores"] = max(vent["n_exaustores"], len(quentes))
    vent["vazao_instalada_m3h"] = round(vent["n_exaustores"] * vent["exaustor_m3h"] * K_FILTRO)
    vent["dt_k"] = round(3.1 * perd["total"] / vent["vazao_instalada_m3h"], 1)
    vent["t_interna_c"] = round(ped.amb_c + vent["dt_k"], 1)
    avisos = []
    if vent["t_interna_c"] > ped.amb_c + DT_MAX + 0.05:
        avisos.append(f"Temperatura interna {vent['t_interna_c']} °C acima de amb+{DT_MAX:.0f} K – rever ventilação.")
    return dict(dimensoes_mm=dict(altura=ALTURA, largura=larg, profundidade=prof), colunas=colunas,
                perdas_w=perd, ventilacao=vent, avisos=avisos,
                base="Padrão Electric BCD 2016 (TECHNIP) + IEC 60890 ventilação forçada")
