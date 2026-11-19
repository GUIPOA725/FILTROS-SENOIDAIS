"""Otimização global multiobjetivo do filtro senoidal.

Varre todo o espaço de projeto viável – frequência de chaveamento, indutância (uk), arranjo REAL de capacitores
(tipo, Δ/Y, nº por ramo) e amortecimento – simula cada candidato (PWM em regime exato), aplica todas as
verificações normativas e calcula, para cada um:

  custo global montado (indutor + capacitores + resistores + caixa + ventilação + cabos + montagem),
  volume da caixa, perdas/aquecimento, THD, queda de tensão e um índice de confiabilidade.

Depois extrai a fronteira de Pareto (soluções não dominadas) e uma nota ponderada (pesos no catálogo).
"""
from __future__ import annotations
import math
import time
from types import SimpleNamespace
from typing import Dict, Any, List, Optional

import numpy as np
import pandas as pd

from .modelos import Pedido
from .dimensionamento import (carregar_catalogo, estresse_capacitor, avaliar, verificar, _construir_projeto, _arranjos_capacitor, _inv_chave,
                              derating_fs, risco_ressonancia_baixa_ordem)
from .mecanica import projetar_arranjo
from .custos import montar_bom, formar_preco


def _opcoes_fs(ped, cat):
    if ped.fs_khz:
        return [ped.fs_khz * 1000]
    inv = cat["inversores"].get(_inv_chave(ped.inversor, cat), cat["inversores"]["GENERICO"])
    fmin_k, fmax_k = cat.get("otimizacao", {}).get("fs_khz_faixa", [2, 8])
    ops = [f for f in inv["fs_opcoes_khz"] if fmin_k <= f <= fmax_k] or [inv["fs_padrao_khz"]]
    # descarta fs em que o derating do inversor já impede a corrente do motor
    i_need = min(ped.corrente_a, (ped.motor_corrente_a or ped.corrente_a) * max(ped.fator_servico, 1.0))
    lim = ped.inversor_corrente_a or ped.corrente_a
    ops = [f for f in ops if lim * derating_fs(cat, ped, f * 1000) >= i_need] or ops[:1]
    return [f * 1000 for f in ops]


def confiabilidade(proj, arr, cat) -> Dict[str, float]:
    """Índice 0–100 (maior = mais confiável). Penalidades transparentes:"""
    cp = cat["projeto_padrao"]
    b = proj.banco
    pen = {}
    ri = b.i_unit_rms / max(b.i_unit_max, 1e-6)
    pen["corrente nos capacitores"] = 40 * max(0.0, ri - 0.6) / 0.4          # vida útil cai com a corrente (aquecimento)
    rv = b.v_cap_rms / b.v_unit
    pen["tensão nos capacitores"] = 20 * max(0.0, rv - 0.85) / 0.25
    if proj.amortecimento:
        pen["resistor de amortecimento (componente quente extra)"] = 8 + (5 if proj.amortecimento.p_ramo_w > 300 else 0)
    lo = next((v for v in proj.verificacoes if v.item.startswith("Amplificação")), None)
    if lo:
        val = float(lo.valor.split("%")[0])
        pen["margem de ressonância (baixa ordem)"] = 15 * min(1.5, val / cp["thd_baixa_ordem_max_pct"]) ** 2
    fmax = proj.pedido["f_saida_max_hz"] or proj.pedido["freq_rede_hz"]
    pen["ressonância < 20·f máx (prática TDK/Schaffner)"] = 8 * max(0.0, (20 - proj.fr_hz / fmax) / 10)
    thd = max(p["thd_v_saida_pct"] for p in proj.pontos)
    pen["THD (margem)"] = 10 * min(1.5, thd / cp["thd_v_max_pct"])
    dens = arr.perda_total_w / max(arr.caixa_l * arr.caixa_a * arr.caixa_p / 1e9, 0.05)   # W/m³
    pen["densidade de perdas na caixa"] = 10 * min(1.5, dens / 3000)
    pen["nº de capacitores"] = min(8, 0.15 * b.n_total)
    vd = min((float(v.valor.split("%")[0]) for v in proj.verificacoes if v.item.startswith("Tensão disponível") and v.critico), default=100)
    pen["tensão disponível no motor"] = 10 * max(0, 100 - vd) / 10
    nota = max(0.0, 100 - sum(pen.values()))
    return {"indice": round(nota, 1), **{k: round(v, 1) for k, v in pen.items()}}


def _avaliar_completo(ped, cat, c, fs, vdc, lcl, Zb, w, notas, pts=64):
    proj = _construir_projeto(ped, cat, cat["projeto_padrao"], c, fs, vdc, lcl, Zb, w, notas, pts_por_portadora=pts, detalhado=False)
    proj.estresse_capacitor = estresse_capacitor(cat, c["cap"], c["arr"][0], c["arr"][1], proj.pontos)
    arr = projetar_arranjo(proj, cat)
    from .termico import aplicar_termico
    arr, term = aplicar_termico(proj, arr, cat)
    itens = montar_bom(proj, arr, cat)
    orc = formar_preco(proj, itens, cat)
    conf = confiabilidade(proj, arr, cat)
    falhas = [v.item for v in proj.verificacoes if v.critico and not v.ok]
    queda = max(proj.l1.queda_v_pct + (proj.l2.queda_v_pct if proj.l2 else 0), 0)
    return dict(
        fs_khz=fs / 1000, uk_pct=round(c["uk"], 2), L1_uH=round(c["L1"] * 1e6, 1), L2_uH=round(c["L2"] * 1e6, 1),
        capacitor=c["cap"]["id"], ligacao=c["arr"][0], n_por_ramo=c["arr"][1], n_caps=3 * c["arr"][1],
        n_caps_total=3 * c["arr"][1] + 3 * c.get("nd", 0),
        C_y_uF=round(c["arr"][2] * 1e6, 1), fr_Hz=round(c["fr"]), fr_sobre_fs=round(c["fr"] / fs, 3),
        fr_sobre_fmax=round(c["fr"] / (ped.f_saida_max_hz or ped.freq_rede_hz), 1),
        topologia_filtro=c.get("topo", "LC"), Q_amort=c["qd"],
        Rd_ramo_ohm=proj.amortecimento.r_ramo_ohm if proj.amortecimento else 0.0,
        n_cd_por_ramo=c.get("nd", 0), p_amort_W=proj.amortecimento.p_total_w if proj.amortecimento else 0.0,
        thd_pct=round(max(p["thd_v_saida_pct"] for p in proj.pontos), 2),
        thd_baixa_ordem_pct=next((float(v.valor.split("%")[0]) for v in proj.verificacoes if v.item.startswith("Amplificação")), 0.0),
        queda_pct=round(queda, 2), ripple_pct=round(100 * proj.l1.ripple_pp_a / (math.sqrt(2) * ped.corrente_a), 1),
        i_cap_ratio=round(proj.banco.i_unit_rms / proj.banco.i_unit_max, 2),
        perdas_indutor_W=round(proj.l1.perdas_w + (proj.l2.perdas_w if proj.l2 else 0)),
        perdas_W=round(arr.perda_total_w), massa_indutor_kg=proj.l1.massa_kg + (proj.l2.massa_kg if proj.l2 else 0),
        caixa=arr.caixa_id, volume_m3=round(arr.caixa_l * arr.caixa_a * arr.caixa_p / 1e9, 3),
        n_vent=arr.n_ventiladores, custo_indutor=round(proj.l1.custo + (proj.l2.custo if proj.l2 else 0)),
        custo_total=round(orc.custo_unit_total), preco=orc.preco_unit, confiabilidade=conf["indice"],
        custo_ip00=round(orc.custo_unit_total - sum(i.total for i in itens if i.grupo == "CAIXA")),
        derating_inversor=derating_fs(cat, ped, fs), viavel=not falhas, falhas="; ".join(falhas),
        t_cap_hotspot_C=round(estresse_capacitor(cat, c["cap"], c["arr"][0], c["arr"][1], proj.pontos)["t_hotspot_c"], 1),
        i_terra_A=round(max(p_.get("i_terra_rms", 0) for p_ in proj.pontos), 2),
        t_ar_saida_C=term["t_saida_C"], arranjo_termico=term["arranjo_escolhido"],
        t_indutor_C=next((x["t_componente_C"] for x in term["componentes"] if x["componente"].startswith("Indutor L1")), None),
        _c=c,
    )


# Topologias (prática dos fabricantes):
#   LC      – L + C, sem resistor (Schaffner FN5040, TDK B84143V, ABB NSIN, Danfoss MCC101, TCI KMG). PADRÃO.
#   LC_RC   – LC + ramo de amortecimento Rd–Cd em paralelo com C (sem perda na fundamental; literatura/Erickson).
#   LC_R    – LC + resistor em série com os capacitores (simples; dissipa a ondulação de alta frequência).
#   LCL     – L1 + C + L2 no lado do motor (cabos longos, menor ondulação no motor).
#   LCL_RC  – LCL + ramo RC paralelo.
# Resistor em paralelo com o indutor (usado em filtros dv/dt) não serve para filtro senoidal: dissiparia a tensão de chaveamento.
TOPOLOGIAS = {
    "LC": dict(nome="LC sem resistor (padrão)", l2=[0.0], amort="nenhum"),
    "LC_RC": dict(nome="LC + ramo RC paralelo", l2=[0.0], amort="rc"),
    "LC_R": dict(nome="LC + resistor série com capacitores", l2=[0.0], amort="serie"),
    "LCL": dict(nome="LCL sem resistor", l2=[0.2, 0.35, 0.5], amort="nenhum"),
    "LCL_RC": dict(nome="LCL + ramo RC paralelo", l2=[0.3], amort="rc"),
}


def _r_otimo_rc(z0, n):
    """Rd ótimo do ramo RC paralelo (Erickson & Maksimović, cap. 'Input filter design'), n = Cd/C."""
    return z0 * math.sqrt((2 + n) * (4 + 3 * n) / (2 * n * n * (4 + n)))


def _candidatos(ped, cat, fs, uks, topo, vdc, fino=False, capacitores=None, ligacoes=None):
    cp = cat["projeto_padrao"]
    tp = TOPOLOGIAS[topo]
    In = ped.corrente_a
    w = 2 * math.pi * ped.freq_rede_hz
    Zb = ped.tensao_v / math.sqrt(3) / In
    fmax = ped.f_saida_max_hz or ped.freq_rede_hz
    fr_min, fr_max = cp["fr_min_mult_fout"] * fmax, cp["fr_max_frac_fs"] * fs
    out = []
    for uk in uks:
        for k2 in tp["l2"]:
            Lt = uk / 100 * Zb / w
            L1 = Lt / (1 + k2)
            L2 = Lt - L1
            ripple_est = 0.19 * vdc / (L1 * fs)
            if ripple_est > 1.35 * cp["ripple_pp_max_pct"] / 100 * In * math.sqrt(2):
                continue
            for cap in [c for c in cat["capacitores"] if not capacitores or c["id"] in capacitores]:
                vistos = set()
                for fr_alvo in np.geomspace(fr_min, fr_max, 24):
                    C_alvo = 1 / (L1 * (2 * math.pi * fr_alvo) ** 2)
                    for arr in _arranjos_capacitor(cap, cp, C_alvo, ped.tensao_v):
                        if ligacoes and arr[0] not in ligacoes:
                            continue
                        if (arr[0], arr[1]) in vistos:
                            continue
                        vistos.add((arr[0], arr[1]))
                        fr = 1 / (2 * math.pi * math.sqrt(L1 * arr[2]))
                        if not (fr_min * 0.97 <= fr <= fr_max * 1.03):
                            continue
                        x = (fr / fs) ** 2
                        if 0.6 * 100 * x / (1 - x) > 1.6 * cp["thd_v_max_pct"] * (1.6 if tp["amort"] != "nenhum" else 1):
                            continue
                        z0 = math.sqrt(L1 / arr[2])
                        base = dict(uk=uk, L1=L1, L2=L2, cap=cap, arr=arr, fr=fr, rd=0.0, qd=0, cd=0.0, rdp=0.0, nd=0, topo=topo)
                        if tp["amort"] == "nenhum":
                            out.append(base)
                        elif tp["amort"] == "serie":
                            for qd in (cp.get("amortecimento_q_opcoes", [10, 6, 4, 3, 2]) if fino else [6, 3]):
                                if qd:
                                    out.append({**base, "rd": z0 / qd, "qd": qd})
                        else:
                            fator = 3 if arr[0] == "Delta" else 1
                            for nd in sorted({max(1, arr[1] // 2), arr[1]}):
                                cd = fator * nd * cap["uf"] * 1e-6
                                ratio = cd / arr[2]
                                for kr in ((0.6, 1.0, 1.6) if fino else (1.0,)):
                                    out.append({**base, "cd": cd, "nd": nd, "rdp": kr * _r_otimo_rc(z0, ratio),
                                                "qd": round(1 / kr, 2)})
    return out, Zb, w


def pareto(df: pd.DataFrame, objetivos=("custo_total", "volume_m3", "perdas_W", "thd_pct", "-confiabilidade")) -> pd.Series:
    cols = []
    for o in objetivos:
        cols.append(-df[o[1:]].values if o.startswith("-") else df[o].values)
    M = np.vstack(cols).T
    n = len(M)
    nd = np.ones(n, bool)
    for i in range(n):
        if not nd[i]:
            continue
        dom = np.all(M <= M[i], axis=1) & np.any(M < M[i], axis=1)
        if dom.any():
            nd[i] = False
    return pd.Series(nd, index=df.index)


def nota(df: pd.DataFrame, pesos: Dict[str, float]) -> pd.Series:
    def norm(s, maior_melhor=False):
        r = (s - s.min()) / (s.max() - s.min() + 1e-12)
        return r if maior_melhor else 1 - r
    sc = (pesos.get("custo", 0) * norm(df["custo_total"]) + pesos.get("tamanho", 0) * norm(df["volume_m3"])
          + pesos.get("perdas", 0) * norm(df["perdas_W"]) + pesos.get("confiabilidade", 0) * norm(df["confiabilidade"], True)
          + pesos.get("thd", 0) * norm(df["thd_pct"]) + pesos.get("queda", 0) * norm(df["queda_pct"]))
    return (100 * sc / max(sum(pesos.values()), 1e-9)).round(1)


def _otimizar_topologia(ped, cat, topo, log, refinar=True, capacitores=None, ligacoes=None):
    cp = cat["projeto_padrao"]
    oc = cat.get("otimizacao", {})
    vdc = 1.35 * ped.tensao_v
    notas = cat["inversores"].get(_inv_chave(ped.inversor, cat), cat["inversores"]["GENERICO"])["notas"]
    passo = oc.get("passo_uk_pct", 1.0)
    uks = np.arange(cp["uk_min_pct"], cp.get("uk_busca_max_pct", 15) + 1e-9, passo)
    lcl = topo.startswith("LCL")
    linhas = []
    for fs in _opcoes_fs(ped, cat):
        cands, Zb, w = _candidatos(ped, cat, fs, uks, topo, vdc, capacitores=capacitores, ligacoes=ligacoes)
        log(f"[{TOPOLOGIAS[topo]['nome']}] fs = {fs / 1000:g} kHz: {len(cands)} candidatos")
        for c in cands:
            linhas.append(_avaliar_completo(ped, cat, c, fs, vdc, lcl, Zb, w, notas))
    df = pd.DataFrame(linhas)
    if refinar and len(df):
        viaveis = df[df.viavel]
        base = viaveis if len(viaveis) else df
        base = base.assign(_n=nota(base, oc.get("pesos", {}))).sort_values("_n", ascending=False).head(8)
        extra = []
        for _, r in base.iterrows():
            fs = r.fs_khz * 1000
            uk_fino = [r.uk_pct - passo / 2, r.uk_pct, r.uk_pct + passo / 2]
            cands, Zb, w = _candidatos(ped, cat, fs, uk_fino, topo, vdc, fino=True, capacitores=capacitores, ligacoes=ligacoes)
            cands = [c for c in cands if c["cap"]["id"] == r.capacitor and abs(c["arr"][1] - r.n_por_ramo) <= 1 and c["arr"][0] == r.ligacao]
            for c in cands:
                extra.append(_avaliar_completo(ped, cat, c, fs, vdc, lcl, Zb, w, notas))
        if extra:
            df = pd.concat([df, pd.DataFrame(extra)], ignore_index=True)
    if len(df):
        df = df.drop_duplicates(subset=["fs_khz", "uk_pct", "L2_uH", "capacitor", "ligacao", "n_por_ramo", "Q_amort", "n_cd_por_ramo"])
    return df.reset_index(drop=True)


def ordem_topologias(ped: Pedido, cat) -> List[str]:
    """Cascata: começa pela topologia padrão (LC sem resistor) e só avança se nenhuma configuração passar.
    Se o pedido exigir LCL, começa pelo LCL."""
    ordem = list(cat.get("otimizacao", {}).get("cascata_topologias", ["LC"]))
    if (ped.topologia or "").upper() == "LCL":
        ordem = [t for t in ordem if t.startswith("LCL")] + [t for t in ordem if not t.startswith("LCL")]
    return ordem


def otimizar_global(ped: Pedido, cat=None, log=print, refinar=True, topologias=None, cascata=True, capacitores=None,
                    ligacoes=None) -> Dict[str, Any]:
    """topologias: lista a avaliar (None = cascata do catálogo). cascata=True para na primeira com solução aprovada."""
    cat = cat or carregar_catalogo()
    oc = cat.get("otimizacao", {})
    t0 = time.time()
    ordem = topologias or ordem_topologias(ped, cat)
    capacitores = capacitores or oc.get("capacitores_permitidos") or None
    ligacoes = ligacoes or oc.get("ligacoes_permitidas") or None
    dfs = []
    usadas = []
    for topo in ordem:
        d = _otimizar_topologia(ped, cat, topo, log, refinar, capacitores=capacitores, ligacoes=ligacoes)
        usadas.append(topo)
        if len(d):
            dfs.append(d)
            n_ok = int(d.viavel.sum())
            log(f"[{TOPOLOGIAS[topo]['nome']}] {len(d)} configurações, {n_ok} aprovadas")
            if cascata and n_ok:
                break
    df = pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()
    via = df[df.viavel].copy()
    if len(via):
        via["pareto"] = pareto(via)
        via["nota"] = nota(via, oc.get("pesos", {}))
        df = df.merge(via[["pareto", "nota"]], left_index=True, right_index=True, how="left")
    else:
        df["pareto"], df["nota"] = False, np.nan
    df["pareto"] = df["pareto"].fillna(False).astype(bool)
    log(f"{len(df)} configurações avaliadas, {int(df.viavel.sum())} viáveis, {int(df.pareto.sum())} na fronteira de Pareto "
        f"({time.time() - t0:.0f} s); topologias: {', '.join(usadas)}")
    if df.viavel.any():
        # robustez: a escolhida precisa passar também nas condições extremas (tolerâncias L/C, rede ±10 %, cabo)
        from .dimensionamento import condicoes_extremas
        df["robusto"] = pd.Series([None] * len(df), index=df.index, dtype=object)
        rank = df[df.viavel].sort_values("nota", ascending=False)
        melhor = rank.iloc[0]
        for idx, row in rank.head(oc.get("n_teste_robustez", 10)).iterrows():
            try:
                ce = condicoes_extremas(ped, cat, row["_c"], float(row["fs_khz"]) * 1000)
                ok = all(x.get("aprovado") for x in ce)
            except Exception:
                ok = False
            df.loc[idx, "robusto"] = ok
            if ok:
                melhor = df.loc[idx]
                break
        log(f"Robustez (condições extremas): {'aprovada' if melhor.get('robusto') else 'nenhuma das 10 melhores passou em todas – usando a de maior nota'}")
    else:
        melhor = df.assign(_f=df.falhas.str.count(";")).sort_values(["_f", "thd_pct"]).iloc[0]
    return dict(df=df, melhor=melhor, tempo_s=time.time() - t0, topologias=usadas)


def comparar_topologias(ped: Pedido, cat=None, log=print, topologias=None, capacitores=None, ligacoes=None) -> pd.DataFrame:
    """Melhor configuração aprovada de CADA topologia (sem cascata), para comparação lado a lado."""
    cat = cat or carregar_catalogo()
    r = otimizar_global(ped, cat, log, topologias=topologias or list(TOPOLOGIAS), cascata=False, capacitores=capacitores,
                        ligacoes=ligacoes)
    df = r["df"]
    linhas = []
    for topo in TOPOLOGIAS:
        d = df[(df.topologia_filtro == topo)]
        if not len(d):
            continue
        ok = d[d.viavel]
        b = (ok.sort_values("nota", ascending=False).iloc[0] if len(ok) else
             d.assign(_f=d.falhas.str.count(";")).sort_values(["_f", "thd_pct"]).iloc[0])
        linhas.append({"topologia": TOPOLOGIAS[topo]["nome"], **{k: v for k, v in b.items() if k != "_c"}, "_c": b["_c"],
                       "aprovadas": int(d.viavel.sum()), "avaliadas": len(d)})
    return pd.DataFrame(linhas)


def avaliar_configuracao(ped: Pedido, cat, L1_uH, cap_id, ligacao, n_por_ramo, fs_khz, rd_q=0, nome="") -> Dict[str, Any]:
    """Avalia uma configuração específica (ex.: seu Excel, um concorrente) com os mesmos critérios."""
    cap = next(c for c in cat["capacitores"] if c["id"] == cap_id)
    fator = 3 if ligacao == "Delta" else 1
    Cy = fator * n_por_ramo * cap["uf"] * 1e-6
    L1 = L1_uH * 1e-6
    fs = fs_khz * 1000
    w = 2 * math.pi * ped.freq_rede_hz
    Zb = ped.tensao_v / math.sqrt(3) / ped.corrente_a
    fr = 1 / (2 * math.pi * math.sqrt(L1 * Cy))
    z0 = math.sqrt(L1 / Cy)
    c = dict(uk=100 * L1 * w / Zb, L1=L1, L2=0.0, cap=cap, arr=(ligacao, n_por_ramo, Cy), fr=fr, rd=(z0 / rd_q if rd_q else 0.0), qd=rd_q)
    r = _avaliar_completo(ped, cat, c, fs, 1.35 * ped.tensao_v, False, Zb, w,
                          cat["inversores"]["GENERICO"]["notas"], pts=120)
    r["nome"] = nome
    return r
