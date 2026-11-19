"""Telas editáveis da plataforma: ajuste manual + ressimulação e critérios de projeto."""
import os
import re
import math
import tempfile

import pandas as pd
import streamlit as st

from fsen.modelos import Pedido
from fsen.dimensionamento import (carregar_catalogo, CAT_PADRAO, projeto_manual, config_de_projeto, n_para_fr, _inv_chave)
from fsen.mecanica import projetar_arranjo
from fsen.custos import montar_bom, formar_preco
from fsen.otimizacao import confiabilidade
from fsen.graficos import gerar_todos
from fsen.pipeline import processar


def _rs(x):
    return "R$ " + f"{x:,.0f}".replace(",", ".")


def _avaliar(ped, cat, cfg, cap_custom=None):
    proj = projeto_manual(ped, cat, cfg["fs_khz"], cfg["L1_uH"], cfg["cap_id"], cfg["ligacao"], cfg["n_por_ramo"],
                          cfg.get("rd_ramo_ohm", 0.0), cfg["L2_uH"], cap_custom=cap_custom,
                          amort_tipo=cfg.get("amort_tipo", "nenhum"), nd_por_ramo=cfg.get("nd_por_ramo", 0),
                          rdp_ramo_ohm=cfg.get("rdp_ramo_ohm", 0.0))
    cat2 = getattr(proj, "_cat", cat)
    arr = projetar_arranjo(proj, cat2)
    from fsen.termico import aplicar_termico
    arr, _t = aplicar_termico(proj, arr, cat2)
    orc = formar_preco(proj, montar_bom(proj, arr, cat2), cat2)
    conf = confiabilidade(proj, arr, cat2)
    return proj, arr, orc, conf


def _resumo(proj, arr, orc, conf):
    pts = proj.pontos
    return {
        "Ressonância (Hz)": round(proj.fr_hz), "uk (%)": proj.l1.uk_pct, "Queda @ f máx (%)": proj.l1.queda_v_pct,
        "THD tensão motor (%)": round(max(p["thd_v_saida_pct"] for p in pts), 2),
        "THD baixa ordem (%)": next((v.valor.split(" ")[0] for v in proj.verificacoes if v.item.startswith("Amplificação")), "-"),
        "Vpico motor (V)": round(max(p["vpk_saida"] for p in pts)), "dv/dt (V/µs)": round(max(p["dvdt_saida_v_us"] for p in pts), 2),
        "Ondulação p-p (A)": proj.l1.ripple_pp_a, "Tensão no capacitor (V)": proj.banco.v_cap_rms,
        "I capacitor / Imax": round(proj.banco.i_unit_rms / proj.banco.i_unit_max, 2),
        "Resistor amortecimento": f"{proj.amortecimento.r_ramo_ohm:.3f} Ω / {proj.amortecimento.p_ramo_w:.0f} W" if proj.amortecimento else "não",
        "Perdas totais (W)": arr.perda_total_w, "Caixa": arr.caixa_id.replace("CX-", ""), "Custo montado": _rs(orc.custo_unit_total),
        "Preço unitário": _rs(orc.preco_unit), "Confiabilidade (0–100)": conf["indice"],
        "Aprovado": "✅ sim" if proj.aprovado else "❌ não",
    }


def tela_ajuste(pasta_saida):
    st.title("Ajuste manual e ressimulação")
    cat = carregar_catalogo()
    painel_abrir_projeto(pasta_saida, "abrir_aj")
    if "pedido" not in st.session_state:
        st.info("Abra um projeto já feito acima, ou um pedido novo em **Nova solicitação**.")
        return
    ped = Pedido.from_dict(st.session_state["pedido"])
    st.caption(f"{ped.cliente} – {ped.quantidade} × {ped.corrente_a:g} A / {ped.tensao_v:g} V – {ped.inversor} – "
               f"{ped.f_saida_min_hz:g}–{ped.f_saida_max_hz:g} Hz")
    auto = st.session_state.get("cfg_auto")
    if not auto:
        st.warning("Ainda não há solução automática para este pedido; a tela começa com valores típicos (uk 8,5 %, fr ~1 kHz).")
        w = 2 * math.pi * ped.freq_rede_hz
        L = 0.085 * ped.tensao_v / math.sqrt(3) / ped.corrente_a / w * 1e6
        n, _ = n_para_fr(L, 1000, 30, "Estrela")
        auto = dict(fs_khz=4.0, L1_uH=round(L, 1), L2_uH=0.0, cap_id="TDK_PEC_30u_480", ligacao="Estrela", n_por_ramo=n, rd_ramo_ohm=0.0)
    cfg = st.session_state.setdefault("cfg_manual", dict(auto))
    if st.button("↺ Voltar para a solução automática"):
        st.session_state["cfg_manual"] = dict(auto)
        st.rerun()

    w = 2 * math.pi * ped.freq_rede_hz
    Zb = ped.tensao_v / math.sqrt(3) / ped.corrente_a
    inv = cat["inversores"].get(_inv_chave(ped.inversor, cat), cat["inversores"]["GENERICO"])

    st.subheader("1 · Inversor e indutor")
    c1, c2, c3, c4 = st.columns(4)
    ops = sorted(set(inv["fs_opcoes_khz"] + [cfg["fs_khz"]]))
    cfg["fs_khz"] = c1.selectbox("Frequência de chaveamento (kHz)", ops, index=ops.index(cfg["fs_khz"]), key="aj_fs")
    modo_L = c2.radio("Definir indutância por", ["uk %", "µH"], horizontal=True, key="aj_modoL")
    if modo_L == "uk %":
        uk = c3.number_input("uk (%) @ rede, In", 1.0, 25.0, round(100 * cfg["L1_uH"] * 1e-6 * w / Zb, 2), 0.25, key="aj_uk")
        cfg["L1_uH"] = round(uk / 100 * Zb / w * 1e6, 1)
        c4.metric("L1 (µH/fase)", f"{cfg['L1_uH']:.1f}")
    else:
        cfg["L1_uH"] = c3.number_input("L1 (µH/fase)", 1.0, 100000.0, float(cfg["L1_uH"]), 1.0, key="aj_L1")
        c4.metric("uk equivalente", f"{100 * cfg['L1_uH'] * 1e-6 * w / Zb:.2f} %")
    lcl = st.checkbox("Topologia LCL (indutor L2 no lado do motor)", value=cfg["L2_uH"] > 0, key="aj_lcl")
    if lcl:
        cfg["L2_uH"] = st.number_input("L2 (µH/fase)", 0.0, 100000.0, float(cfg["L2_uH"] or round(0.3 * cfg["L1_uH"], 1)), 1.0, key="aj_L2")
    else:
        cfg["L2_uH"] = 0.0

    st.subheader("2 · Banco de capacitores")
    ids = [c["id"] for c in cat["capacitores"]] + ["Personalizado…"]
    c1, c2, c3 = st.columns(3)
    sel = c1.selectbox("Capacitor", ids, index=ids.index(cfg["cap_id"]) if cfg["cap_id"] in ids else len(ids) - 1, key="aj_cap",
                       format_func=lambda i: i if i == "Personalizado…" else
                       next(f"{c['fabricante']} {c['uf']:g} µF {c['v_ac']} V – {c['linha']}" for c in cat["capacitores"] if c["id"] == i))
    cap_custom = None
    if sel == "Personalizado…":
        k1, k2, k3, k4, k5 = st.columns(5)
        cap_custom = dict(id="CUSTOM", fabricante=k1.text_input("Fabricante", "TDK EPCOS", key="cc_f"),
                          linha=k1.text_input("Linha", "MKP filtro AC (IEC 61071)", key="cc_l"), pn="a definir",
                          uf=k2.number_input("µF", 0.5, 2000.0, 30.0, key="cc_uf"), v_ac=k3.number_input("Tensão nominal (Vca)", 100, 2000, 480, key="cc_v"),
                          imax_a=k4.number_input("Imax RMS (A, 0 = 1,3·In)", 0.0, 500.0, 0.0, key="cc_i") or None,
                          preco=k5.number_input("Preço (R$)", 0.0, 100000.0, 150.0, key="cc_p"))
        cfg["cap_id"] = "CUSTOM"
        cap_uf = cap_custom["uf"]
    else:
        cfg["cap_id"] = sel
        cap_uf = next(c["uf"] for c in cat["capacitores"] if c["id"] == sel)
    cfg["ligacao"] = c2.radio("Fechamento", ["Delta", "Estrela"], index=0 if cfg["ligacao"] == "Delta" else 1, horizontal=True, key="aj_lig")
    modo_c = c3.radio("Definir por", ["nº por ramo", "fr desejada"], horizontal=True, key="aj_modoC")
    c1, c2, c3 = st.columns(3)
    if modo_c == "fr desejada":
        fr_alvo = c1.number_input("Ressonância desejada (Hz)", 100.0, 5000.0, 1000.0, 10.0, key="aj_fr")
        n, cy = n_para_fr(cfg["L1_uH"], fr_alvo, cap_uf, cfg["ligacao"])
        cfg["n_por_ramo"] = int(n)
        c2.metric("Capacitores por ramo", n, help=f"C estrela necessário {cy:.0f} µF")
    else:
        cfg["n_por_ramo"] = int(c1.number_input("Capacitores por ramo", 1, 200, int(cfg["n_por_ramo"]), key="aj_n"))
    fator = 3 if cfg["ligacao"] == "Delta" else 1
    cy = fator * cfg["n_por_ramo"] * cap_uf
    fr = 1 / (2 * math.pi * math.sqrt(cfg["L1_uH"] * 1e-6 * cy * 1e-6))
    c3.metric("fr resultante", f"{fr:.0f} Hz", f"C estrela {cy:.0f} µF – total {3 * cfg['n_por_ramo']} pç", delta_color="off")

    st.subheader("3 · Topologia de amortecimento")
    st.caption("Padrão da casa e dos fabricantes (Schaffner, TDK, ABB, Danfoss, TCI): LC sem resistor. "
               "Ramo RC paralelo amortece sem dissipar a fundamental; resistor série é o mais simples, mas dissipa a ondulação.")
    opcoes = {"nenhum": "Sem resistor (LC/LCL puro)", "rc": "Ramo RC paralelo (Rd + Cd)", "serie": "Resistor em série com o banco"}
    atual = cfg.get("amort_tipo", "serie" if cfg.get("rd_ramo_ohm") else "nenhum")
    cfg["amort_tipo"] = st.radio("Amortecimento", list(opcoes), index=list(opcoes).index(atual), format_func=opcoes.get,
                                 horizontal=True, key="aj_tipo_am")
    z0 = math.sqrt(cfg["L1_uH"] * 1e-6 / (cy * 1e-6))
    para_ramo = 3 if cfg["ligacao"] == "Delta" else 1
    c1, c2, c3 = st.columns(3)
    cfg["rd_ramo_ohm"], cfg["nd_por_ramo"], cfg["rdp_ramo_ohm"] = 0.0, 0, 0.0
    if cfg["amort_tipo"] == "serie":
        modo = c1.radio("Definir", ["por Q", "em Ω"], horizontal=True, key="aj_am")
        if modo == "por Q":
            q = c2.number_input("Q desejado (2 = muito amortecido, 10 = leve)", 1.0, 30.0, 4.0, 0.5, key="aj_q")
            cfg["rd_ramo_ohm"] = round((z0 / q) * para_ramo, 4)
            c3.metric("R por ramo", f"{cfg['rd_ramo_ohm']:.3f} Ω")
        else:
            cfg["rd_ramo_ohm"] = c2.number_input("R por ramo (Ω)", 0.0, 100.0, float(st.session_state.get("cfg_manual", {}).get("rd_ramo_ohm") or 0.3),
                                                 0.01, key="aj_rd")
    elif cfg["amort_tipo"] == "rc":
        nd = int(c1.number_input("Capacitores Cd por ramo (mesmo tipo)", 1, 100, max(1, int(st.session_state.get("cfg_manual", {}).get("nd_por_ramo") or
                                                                                      max(1, cfg["n_por_ramo"] // 2))), key="aj_nd"))
        from fsen.otimizacao import _r_otimo_rc
        r_ot = _r_otimo_rc(z0, nd / cfg["n_por_ramo"]) * para_ramo
        modo = c2.radio("Rd", ["ótimo (Erickson)", "em Ω"], horizontal=True, key="aj_rcm")
        cfg["nd_por_ramo"] = nd
        if modo.startswith("ótimo"):
            cfg["rdp_ramo_ohm"] = round(r_ot, 4)
            c3.metric("Rd por ramo", f"{r_ot:.3f} Ω")
        else:
            cfg["rdp_ramo_ohm"] = c3.number_input("Rd por ramo (Ω)", 0.0, 100.0, round(r_ot, 3), 0.01, key="aj_rdp")

    st.divider()
    b1, b2 = st.columns(2)
    if b1.button("▶ Ressimular", type="primary", width="stretch"):
        with st.spinner("Simulando PWM e verificando critérios..."):
            try:
                proj, arr, orc, conf = _avaliar(ped, cat, cfg, cap_custom)
            except Exception as e:
                st.error(f"Não foi possível simular esta configuração: {e}")
                return
            tmp = tempfile.mkdtemp()
            graf = gerar_todos(proj, tmp)
            from fsen.graficos import grafico_termico
            graf["termico"] = grafico_termico(proj, arr, tmp)
            st.session_state["manual_res"] = dict(proj=proj, arr=arr, orc=orc, conf=conf, graf=graf, cap_custom=cap_custom)
            if "auto_res" not in st.session_state and st.session_state.get("cfg_auto"):
                st.session_state["auto_res"] = _avaliar(ped, cat, st.session_state["cfg_auto"])
    res = st.session_state.get("manual_res")
    if not res:
        st.caption("Ajuste os parâmetros e clique em **Ressimular** (cerca de 1–3 s).")
        return
    proj, arr, orc, conf = res["proj"], res["arr"], res["orc"], res["conf"]
    st.subheader("Resultado da ressimulação")
    resumo_m = _resumo(proj, arr, orc, conf)
    tabela = pd.DataFrame({"Manual": resumo_m})
    if st.session_state.get("auto_res"):
        tabela["Automático (otimizador)"] = pd.Series(_resumo(*st.session_state["auto_res"]))
    st.dataframe(tabela.astype(str), width="stretch")
    ver = pd.DataFrame([dict(Status=("✅" if v.ok else ("❌" if v.critico else "⚠️")), Verificação=v.item, Valor=v.valor,
                             Limite=v.limite, Referência=v.referencia) for v in proj.verificacoes])
    st.dataframe(ver, width="stretch", hide_index=True)
    g = res["graf"]
    t1, t2, t3, t4 = st.tabs(["Formas de onda", "Espectro", "Resposta em frequência", "Correntes / ressonância"])
    t1.image(g["formas_onda"])
    t2.image(g["espectro"])
    t3.image(g["bode"])
    t3.image(g["impedancia"])
    t4.image(g["fluxo"])
    t4.image(g["baixa_ordem"])
    st.subheader("Estudo térmico do painel")
    if g.get("termico"):
        st.image(g["termico"])
    tm = getattr(proj, "termico", None)
    if tm:
        st.dataframe(pd.DataFrame(tm["componentes"]), width="stretch", hide_index=True)
        st.caption(f"Arranjo escolhido: {tm['arranjo_escolhido']} – comparação: {tm['comparacao_arranjos']}")
    st.subheader("Condições extremas (tolerâncias, rede ±10 %, cabo)")
    if getattr(proj, "condicoes_extremas", None):
        st.dataframe(pd.DataFrame(proj.condicoes_extremas), width="stretch", hide_index=True)
    if b2.button("📦 Gerar pacote completo com esta configuração", width="stretch"):
        with st.spinner("Gerando desenhos, documentos, ETs e preço..."):
            r = processar(ped, pasta_saida, log=lambda m: None, projeto=proj)
        st.session_state["resultado"] = {"pasta": r["pasta"], "zip": r["zip"], "arquivos": r["arquivos"], "graficos": r["graficos"],
                                         "resumo": r["resumo"]}
        st.success(f"Pacote gerado em {r['pasta']} – veja downloads em Nova solicitação.")


def tela_ajuste_completa(pasta_saida):
    tela_ajuste(pasta_saida)
    if "pedido" in st.session_state:
        st.divider()
        painel_comparar_topologias(Pedido.from_dict(st.session_state["pedido"]), carregar_catalogo())


def painel_comparar_topologias(ped, cat):
    st.subheader("Comparar todas as topologias")
    st.caption("Otimiza separadamente LC, LC+RC, LC+R série, LCL e LCL+RC e mostra a melhor de cada uma (alguns minutos).")
    if st.button("Comparar topologias", key="cmp_topo"):
        from fsen.otimizacao import comparar_topologias
        prog = st.empty()
        with st.spinner("Otimizando as cinco topologias..."):
            d = comparar_topologias(ped, cat, log=lambda m: prog.write(m))
        st.session_state["cmp_topo_df"] = d
    d = st.session_state.get("cmp_topo_df")
    if d is None:
        return
    cols = ["topologia", "aprovadas", "avaliadas", "viavel", "uk_pct", "L2_uH", "n_caps_total", "ligacao", "fr_Hz", "Rd_ramo_ohm",
            "p_amort_W", "thd_pct", "thd_baixa_ordem_pct", "perdas_W", "caixa", "custo_total", "confiabilidade"]
    st.dataframe(d[[c for c in cols if c in d.columns]], width="stretch", hide_index=True)
    escolha = st.selectbox("Carregar no ajuste manual", d.topologia.tolist(), key="cmp_sel")
    if st.button("Carregar esta topologia", key="cmp_load"):
        row = d[d.topologia == escolha].iloc[0]
        c = row["_c"]
        lig = c["arr"][0]
        mult = 3 if lig == "Delta" else 1
        st.session_state["cfg_manual"] = dict(
            fs_khz=float(row.fs_khz), L1_uH=round(c["L1"] * 1e6, 1), L2_uH=round(c["L2"] * 1e6, 1), cap_id=c["cap"]["id"],
            ligacao=lig, n_por_ramo=int(c["arr"][1]),
            amort_tipo=("rc" if c.get("cd") else ("serie" if c.get("rd") else "nenhum")),
            rd_ramo_ohm=round(c.get("rd", 0) * mult, 4), nd_por_ramo=int(c.get("nd", 0)), rdp_ramo_ohm=round(c.get("rdp", 0) * mult, 4))
        st.session_state.pop("manual_res", None)
        st.rerun()


# ------------------------------------------------------------------ critérios
CRITERIOS = [
    ("thd_v_max_pct", "THD máx. de tensão no motor (%)", 0.5, 20.0),
    ("thd_baixa_ordem_max_pct", "Distorção máx. por harmônicas de tempo morto (%)", 0.5, 20.0),
    ("fr_min_mult_fout", "Ressonância mínima (× f saída máx)", 3.0, 40.0),
    ("fr_max_frac_fs", "Ressonância máxima (fração de fs)", 0.1, 0.6),
    ("uk_min_pct", "uk mínimo da busca (%)", 1.0, 20.0),
    ("uk_busca_max_pct", "uk máximo da busca (%)", 2.0, 25.0),
    ("uk_max_pct", "Queda máx. no indutor na f máx (%)", 2.0, 25.0),
    ("ripple_pp_max_pct", "Ondulação p-p máx. no indutor (% do pico)", 5.0, 100.0),
    ("ic_fund_max_pct", "Corrente capacitiva máx. (% In)", 1.0, 60.0),
    ("vcap_max_pu", "Tensão máx. no capacitor (× Un)", 0.8, 1.3),
    ("icap_max_fator_iec60831", "Imax capacitor sem datasheet (× In)", 1.0, 3.0),
    ("tensao_motor_min_pu", "Tensão mín. disponível no motor (pu)", 0.7, 1.0),
    ("delta_t_painel_k", "Elevação interna da caixa (K)", 5.0, 30.0),
    ("penalidade_cap_nao_preferido", "Penalidade p/ capacitor fora do estoque", 0.0, 2.0),
]
PESOS = [("custo", "Custo"), ("confiabilidade", "Confiabilidade"), ("tamanho", "Tamanho da caixa"), ("perdas", "Perdas / aquecimento"),
         ("thd", "THD"), ("queda", "Queda de tensão")]


def _set_yaml(texto, chave, valor):
    pad = re.compile(rf"^(\s*{re.escape(chave)}:\s*)([^#\n]*?)(\s*(#.*)?)$", re.M)
    if not pad.search(texto):
        return texto
    return pad.sub(lambda m: f"{m.group(1)}{valor}{m.group(3)}", texto, count=1)


def tela_criterios():
    st.title("Critérios de projeto e pesos da otimização")
    st.caption("Valores usados pelo otimizador automático e pelas verificações da tela de ajuste. Salvar grava em dados/catalogo.yaml.")
    cat = carregar_catalogo()
    cp = cat["projeto_padrao"]
    novos = {}
    cols = st.columns(2)
    for k, (chave, rot, lo, hi) in enumerate(CRITERIOS):
        v = float(cp.get(chave, lo))
        novos[chave] = cols[k % 2].number_input(rot, float(lo), float(hi), v, key=f"cr_{chave}")
    st.subheader("Pesos da nota (somam 1)")
    pes = cat.get("otimizacao", {}).get("pesos", {})
    cols = st.columns(6)
    npes = {k: cols[i].number_input(r, 0.0, 1.0, float(pes.get(k, 0)), 0.05, key=f"pw_{k}") for i, (k, r) in enumerate(PESOS)}
    soma = sum(npes.values())
    st.caption(f"Soma atual: {soma:.2f}" + ("" if abs(soma - 1) < 0.01 else " – os pesos são normalizados automaticamente."))
    fx = cat.get("otimizacao", {}).get("fs_khz_faixa", [2, 8])
    c1, c2 = st.columns(2)
    f1 = c1.number_input("fs mínima avaliada (kHz)", 1.0, 16.0, float(fx[0]))
    f2 = c2.number_input("fs máxima avaliada (kHz)", 1.0, 16.0, float(fx[1]))
    if st.button("Salvar critérios", type="primary"):
        txt = open(CAT_PADRAO, encoding="utf-8").read()
        for k, v in novos.items():
            txt = _set_yaml(txt, k, f"{v:g}")
        for k, v in npes.items():
            txt = _set_yaml(txt, k, f"{v:g}")
        txt = _set_yaml(txt, "fs_khz_faixa", f"[{f1:g}, {f2:g}]")
        import yaml
        yaml.safe_load(txt)
        open(CAT_PADRAO, "w", encoding="utf-8").write(txt)
        st.success("Critérios salvos. A próxima otimização já usa os novos valores.")


# ------------------------------------------------------------------ abrir projeto já feito
_GRAF = {"formas_onda": "formas_onda.png", "espectro": "espectro.png", "bode": "resposta_frequencia.png",
         "baixa_ordem": "ressonancia_baixa_ordem.png", "impedancia": "impedancia_entrada.png", "fluxo": "fluxo_correntes.png"}


def listar_projetos(pasta_saida):
    """Projetos já gerados: PROJETOS\\<Cliente>\\<data>_<código> (pastas com pedido.json)."""
    out = []
    if not pasta_saida or not os.path.isdir(pasta_saida):
        return out
    for cli in sorted(os.listdir(pasta_saida)):
        pc = os.path.join(pasta_saida, cli)
        if not os.path.isdir(pc):
            continue
        cands = [pc] + [os.path.join(pc, d) for d in os.listdir(pc) if os.path.isdir(os.path.join(pc, d))]
        for d in cands:
            if os.path.exists(os.path.join(d, "pedido.json")):
                out.append((cli, os.path.basename(d) if d != pc else "(raiz)", d))
    out.sort(key=lambda x: (x[0].lower(), x[1]), reverse=False)
    return out


def carregar_projeto_pasta(pasta):
    """Lê pedido.json + 01_Engenharia/projeto.json e deixa tudo pronto na sessão (Nova solicitação e Ajuste manual)."""
    import json
    ped = json.load(open(os.path.join(pasta, "pedido.json"), encoding="utf-8"))
    st.session_state["pedido"] = Pedido.from_dict(ped).to_dict()
    cfg = None
    cam = os.path.join(pasta, "01_Engenharia", "projeto.json")
    if os.path.exists(cam):
        pj = json.load(open(cam, encoding="utf-8"))
        b, am = pj.get("banco") or {}, pj.get("amortecimento") or {}
        tipo = am.get("tipo") if am else None
        cfg = dict(fs_khz=float(pj.get("fs_hz", 4000)) / 1000, L1_uH=float(pj["l1"]["l_uh"]),
                   L2_uH=float((pj.get("l2") or {}).get("l_uh") or 0.0), cap_id=b.get("cap_id"), ligacao=b.get("ligacao", "Estrela"),
                   n_por_ramo=int(b.get("n_por_ramo", 1)),
                   amort_tipo=("nenhum" if not tipo else ("rc" if tipo == "rc_paralelo" else "serie")),
                   rd_ramo_ohm=float(am.get("r_ramo_ohm", 0.0)) if tipo == "serie" else 0.0,
                   nd_por_ramo=int(am.get("n_cd_por_ramo", 0)) if tipo == "rc_paralelo" else 0,
                   rdp_ramo_ohm=float(am.get("r_ramo_ohm", 0.0)) if tipo == "rc_paralelo" else 0.0)
    for k in ("manual_res", "auto_res", "cmp_topo_df"):
        st.session_state.pop(k, None)
    if cfg:
        st.session_state["cfg_auto"] = cfg
        st.session_state["cfg_manual"] = dict(cfg)
    arquivos = {}
    for raiz, _, fs in os.walk(pasta):
        for f in fs:
            c = os.path.join(raiz, f)
            if f.startswith("Email_Solicitacao_Dados"):
                arquivos["email_dados"] = c
            elif f.startswith("Email_"):
                arquivos["email_" + f[6:-4]] = c
            elif "Questionario" in f:
                arquivos["questionario"] = c
            elif f.lower().endswith((".docx", ".xlsx", ".pdf")):
                arquivos[f] = c
    gdir = os.path.join(pasta, "graficos")
    graf = {k: os.path.join(gdir, v) for k, v in _GRAF.items() if os.path.exists(os.path.join(gdir, v))}
    zips = [os.path.join(os.path.dirname(pasta), z) for z in os.listdir(os.path.dirname(pasta))
            if z == os.path.basename(pasta) + ".zip"]
    res = os.path.join(pasta, "RESUMO.md")
    st.session_state["resultado"] = {"pasta": pasta, "zip": zips[0] if zips else None, "arquivos": arquivos, "graficos": graf,
                                     "resumo": open(res, encoding="utf-8").read() if os.path.exists(res) else ""}
    return cfg is not None


def painel_abrir_projeto(pasta_saida, chave="abrir"):
    """Seletor de projetos já feitos (cliente → projeto) + campo para colar o caminho da pasta."""
    with st.expander("📂 Abrir um projeto já feito", expanded="pedido" not in st.session_state):
        lst = listar_projetos(pasta_saida)
        if lst:
            clientes = sorted({c for c, _, _ in lst}, key=str.lower)
            c1, c2 = st.columns(2)
            cli = c1.selectbox("Cliente", clientes, key=f"{chave}_cli")
            projs = [(n, d) for c, n, d in lst if c == cli]
            nome = c2.selectbox("Projeto", [n for n, _ in projs][::-1], key=f"{chave}_proj")
            pasta = dict(projs)[nome]
        else:
            st.caption(f"Nenhum projeto encontrado em {pasta_saida}.")
            pasta = None
        colado = st.text_input("…ou cole o caminho da pasta (cliente ou projeto)", key=f"{chave}_cam",
                               placeholder=r"G:\Drives compartilhados\...\PROJETOS\A & W Suprimentos Industriais")
        if colado.strip():
            p = colado.strip().strip('"')
            if os.path.isdir(p) and not os.path.exists(os.path.join(p, "pedido.json")):
                subs = sorted([os.path.join(p, d) for d in os.listdir(p) if os.path.exists(os.path.join(p, d, "pedido.json"))])
                if subs:
                    p = st.selectbox("Projetos nesta pasta", subs, index=len(subs) - 1, format_func=os.path.basename, key=f"{chave}_sub")
            pasta = p
        if st.button("Abrir projeto", key=f"{chave}_btn", type="primary", disabled=not pasta):
            if not os.path.exists(os.path.join(pasta, "pedido.json")):
                st.error("Essa pasta não tem pedido.json (projetos antigos, de antes da plataforma, não podem ser abertos aqui).")
            else:
                carregar_projeto_pasta(pasta)
                st.success(f"Aberto: {pasta}")
                st.rerun()
