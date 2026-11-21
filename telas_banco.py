"""Tela de BANCO DESSINTONIZADO e FILTRO SINTONIZADO (v1.14.0) – mesmo caminho do filtro senoidal:
cola o e-mail, solta os anexos (pedido, unifilar, placa do trafo, relatório de QEE, exportações de medição Dranview/Fluke/CSV),
a IA lê, a plataforma decide pelo critério Electric e o engenheiro confere e gera o projeto completo."""
import datetime as dt
import os
import tempfile

import pandas as pd
import streamlit as st

from fsen import banco as B
from fsen.doc_banco import titulo_tipo, codigo


def _harm_editor(chave, padrao, rotulo, unidade):
    df = pd.DataFrame([dict(h=int(h), valor=float(v)) for h, v in sorted(padrao.items())] or [dict(h=5, valor=0.0)])
    ed = st.data_editor(df, key=chave, num_rows="dynamic", width="stretch",
                        column_config={"h": st.column_config.NumberColumn("Harmônica", min_value=2, max_value=50, step=1),
                                       "valor": st.column_config.NumberColumn(f"{rotulo} ({unidade})", min_value=0.0, format="%.2f")})
    return {int(r["h"]): float(r["valor"]) for _, r in ed.dropna().iterrows() if r["valor"] > 0}


def _leitura(tipo, provedor, nome_ia):
    st.markdown("#### 1. Solicitação – cole o e-mail e solte os arquivos (igual ao filtro senoidal)")
    texto = st.text_area("E-mail / pedido do cliente", height=150, key="bc_email")
    arquivos = st.file_uploader("Anexos: pedido, unifilar, placa do trafo, fotos, relatório de QEE, medições (xlsx, csv, txt, pdf, docx, imagens)",
                                accept_multiple_files=True, key="bc_anexos")
    if st.button("🔎 Ler solicitação e medições", type="primary", key="bc_ler"):
        caminhos, tmp = [], tempfile.mkdtemp()
        for f in arquivos or []:
            c = os.path.join(tmp, f.name)
            open(c, "wb").write(f.getbuffer())
            caminhos.append(c)
        if not caminhos and not texto.strip():
            st.error("Cole o e-mail e/ou anexe os arquivos antes de ler.")
            return
        from fsen import leitor_banco as LB
        import time
        t0 = time.time()
        with st.spinner(f"Lendo e-mail e {len(caminhos)} anexo(s) com {nome_ia}..."):
            dados = LB.ler(texto, caminhos, provedor)
        ped, just, lac = LB.decidir(dados)
        st.session_state["bc_dados"] = dados
        st.session_state["bc_ped"] = ped.__dict__.copy()
        st.session_state["bc_just"] = just
        st.session_state["bc_lac"] = lac
        st.session_state["bc_info"] = dict(fonte=dados.get("_fonte"), arquivos=[os.path.basename(c) for c in caminhos],
                                           hora=dt.datetime.now().strftime("%H:%M:%S"), seg=round(time.time() - t0, 1))
        st.session_state.pop("resultado_banco", None)
        for k in list(st.session_state):
            if k.startswith("bcf_"):
                del st.session_state[k]
        st.rerun()


def tela_banco(tipo, pasta_saida, provedor=None, nome_ia="IA"):
    sint_menu = tipo == "sintonizado"
    st.title("Filtro harmônico sintonizado" if sint_menu else "Banco de capacitores dessintonizado")
    st.caption("Padrão de engenharia da Electric (planilhas ESTAGIO, cartas à Cootrans, ET para a montadora, propostas FHSBT/BCD) + "
               "física (espectro, ressonância, limites do capacitor) + reator por elementos finitos (mesmo motor do filtro senoidal).")
    _leitura(tipo, provedor, nome_ia)
    info = st.session_state.get("bc_info")
    base = B.PedidoBanco.from_dict(st.session_state["bc_ped"]) if st.session_state.get("bc_ped") else B.PedidoBanco(tipo=tipo)
    if info:
        (st.success if str(info["fonte"]).startswith("IA") else st.warning)(
            f"Leitura por **{info['fonte']}** às {info['hora']} ({info['seg']} s) – arquivos: {', '.join(info['arquivos']) or 'nenhum'}")
        if base.tipo != tipo:
            st.warning(f"Pela solicitação/medição o indicado é **{base.tipo}** – troque o 'Tipo de filtro' na barra lateral, "
                       "ou continue aqui para estudar como " + tipo + ".")
        with st.expander("Critério aplicado (por que este banco/filtro)", expanded=True):
            for x in st.session_state.get("bc_just", []):
                st.markdown(f"- {x}")
            obs = (st.session_state.get("bc_dados") or {}).get("observacoes")
            if obs:
                st.markdown("**Observações da leitura:** " + obs)
            ev = (st.session_state.get("bc_dados") or {}).get("evidencias") or []
            if ev:
                st.caption("De onde saíram os números: " + " | ".join(ev))
        for x in st.session_state.get("bc_lac", []):
            st.info(x)
    base.tipo = tipo
    sint = sint_menu
    st.markdown("#### 2. Dados – confira e ajuste")
    p = B.PedidoBanco(**{k: getattr(base, k) for k in B.PedidoBanco.__dataclass_fields__})
    c1, c2, c3, c4 = st.columns(4)
    p.cliente = c1.text_input("Cliente", base.cliente, key="bcf_cli")
    p.projeto = c2.text_input("Projeto / local", base.projeto, key="bcf_proj")
    p.tensao_v = c3.number_input("Tensão da rede (V)", 200.0, 1000.0, float(base.tensao_v), key="bcf_v")
    p.freq_hz = c4.selectbox("Frequência (Hz)", [60.0, 50.0], index=0 if base.freq_hz == 60 else 1, key="bcf_f")
    c1, c2, c3 = st.columns([2, 1, 1])
    est = c1.text_input("Estágios (kvar efetivos na rede, separados por +)", " + ".join(f"{x:g}" for x in base.estagios_kvar), key="bcf_est")
    try:
        p.estagios_kvar = [float(x.replace(",", ".")) for x in est.replace(";", "+").split("+") if x.strip()]
    except ValueError:
        st.error("Estágios: números separados por + (ex.: 25 + 50 + 50)")
        return
    n_bancos = c2.number_input("Quantidade de bancos/filtros", 1, 100, 1, key="bcf_n")
    p.amb_c = c3.number_input("Ambiente (°C)", 20.0, 55.0, float(base.amb_c), key="bcf_amb")
    if sint:
        c1, c2, c3, c4 = st.columns(4)
        ords = c1.text_input("Harmônica de cada ramo (na ordem dos estágios)", " + ".join(f"{h:g}" for h in base.ordens), key="bcf_ord")
        try:
            p.ordens = [float(x.replace(",", ".")) for x in ords.replace(";", "+").split("+") if x.strip()]
        except ValueError:
            st.error("Harmônicas: ex. 5 + 5 + 7")
            return
        p.fator_sintonia = c2.number_input("Nr = fator × h", 0.85, 0.99, float(base.fator_sintonia), 0.01, key="bcf_fs",
                                           help="Electric: Nr 4,4–4,8 na 5ª (fator 0,88–0,96).")
        p.dhti_carga_pct = c3.number_input("DHTi drenada da rede (%)", 0.0, 400.0, float(base.dhti_carga_pct), key="bcf_dhti")
        p.monofasico = c4.checkbox("3 reatores monofásicos de 2 colunas por ramo", base.monofasico, key="bcf_mono")
    else:
        nrs = list(B.NR_DESSINT)
        p.nr = st.radio("Fator de dessintonia", nrs, index=nrs.index(base.nr) if base.nr in nrs else 0, horizontal=True, key="bcf_nr",
                        format_func=lambda x: B.NR_DESSINT[x])
    with st.expander("Reator e capacitores (padrão Electric – altere só se precisar)"):
        c1, c2, c3, c4, c5 = st.columns(5)
        p.k_corrente = c1.number_input("k = I_projeto / I60", 1.0, 3.0, float(base.k_()), 0.01, key="bcf_k",
                                       help="Planilha ESTAGIO: 1,3 dessintonizado. Sintonizado: " + B.K_HIST_SINT)
        p.fq = c2.number_input("Fator de qualidade FQ", 20.0, 200.0, float(base.fq_()), key="bcf_fq")
        p.tol_l_pct = c3.number_input("Tolerância de L (±%)", 1.0, 5.0, float(base.tol_l_pct), key="bcf_tl")
        p.classe = c4.selectbox("Classe térmica", ["F", "H"], index=0 if base.classe == "F" else 1, key="bcf_cl")
        p.condutor = c5.selectbox("Enrolamento", ["AL", "CU"], index=0 if base.condutor == "AL" else 1, key="bcf_cd",
                                  format_func=lambda x: "Alumínio (padrão Electric)" if x == "AL" else "Cobre")
        st.caption("Capacitores: deixe em branco para a escolha automática (unidades usuais: 4×18 kvar/480 V, 4×20 kvar/600 V, "
                   "4×40 kvar/690 V…). Para fixar: 'n×kvar/V' por estágio, separados por ';' – ex.: 4x18/480; 2x18/480")
        capt = st.text_input("Capacitores por estágio (opcional)", "", key="bcf_caps")
        caps = []
        for tok in [t.strip() for t in capt.split(";")]:
            try:
                n_, rest = tok.lower().replace("×", "x").split("x")
                u_, v_ = rest.split("/")
                caps.append([int(n_), float(u_.replace(",", ".")), int(float(v_))])
            except Exception:
                caps.append(None)
        p.caps = caps if any(caps) else []
    st.markdown("**Rede**")
    c1, c2, c3 = st.columns(3)
    p.trafo_kva = c1.number_input("Transformador (kVA)", 50.0, 20000.0, float(base.trafo_kva), key="bcf_tr")
    p.trafo_z_pct = c2.number_input("Impedância do transformador (%)", 2.0, 15.0, float(base.trafo_z_pct), key="bcf_z")
    p.scc_rede_mva = c3.number_input("Scc da rede em MT (MVA)", 10.0, 5000.0, float(base.scc_rede_mva), key="bcf_scc")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Distorção de tensão (% de Un)** – " + ("fundo da rede (Thévenin)" if sint else "de projeto nos terminais"))
        p.harm_tensao_pct = _harm_editor("bcf_hv" + ("s" if sint else ""), base.harm_tensao_pct or
                                         (B.HARM_PADRAO_SINT if sint else B.HARM_PADRAO), "Tensão", "%")
    with c2:
        st.markdown("**Corrente harmônica da carga (A)**" + (" – define a absorção e o DHTv" if sint else " – opcional"))
        p.harm_carga_a = _harm_editor("bcf_hi", base.harm_carga_a or ({5: 50.0, 7: 30.0} if sint else {}), "Corrente", "A")
    st.divider()
    try:
        res = B.dimensionar(p)
    except Exception as e:
        st.error(f"Cálculo não concluído: {type(e).__name__}: {e}")
        return
    st.markdown(f"#### 3. Prévia – {titulo_tipo(p)} – {codigo(p)}")
    df = pd.DataFrame([{"Est.": i + 1, "Código": e["codigo"], "Capacitor": f"{e['cap'][0]}×{e['cap'][1]:g} kvar/{e['U_cap_nom']} V",
                        "kvar efetivo": round(e["Q_kvar"], 1), "Nr / FD %": f"{e['nr']:.2f} / {e['p_pct']:.2f}",
                        "L µH": round(e["L_uH"], 1), "I60 (ajuste) A": round(e["I60"], 1), "V ajuste/fase": round(e["V_ajuste_fase"], 1),
                        "I projeto A": round(e["requisitos"]["In"], 1), "V cap op. V": round(e["Uc1"])}
                       for i, e in enumerate(res["estagios"])])
    st.dataframe(df, hide_index=True, width="stretch")
    vr = res["varredura"]
    st.line_chart(pd.DataFrame({"h": vr["h"], "|Z| com banco (Ω)": vr["Z"], "|Z| rede (Ω)": vr["Zs"]}).set_index("h"))
    st.caption("Ressonância paralela: " + (", ".join(f"{x:.2f}ª ({x*p.freq_hz:.0f} Hz)" for x in vr["picos"]) or "nenhuma"))
    if res.get("thd"):
        st.info(f"DHTv na barra pela carga: sem filtro {res['thd']['sem']:.2f} % → com filtro {res['thd']['com']:.2f} %")
    for a in res["avisos"]:
        st.warning(a)
    verif = st.checkbox("Verificação independente + análise avançada dos reatores (NGSolve, ~2–3 min por reator)", True, key="bcf_verif")
    if st.button("Gerar projeto completo (reatores, desenhos, CAD, memorial, planilhas ESTAGIO, especificações, ET painel, proposta)",
                 type="primary"):
        from fsen.pipeline_banco import processar_banco
        msgs = st.status("Processando...", expanded=True)
        r = processar_banco(p, pasta_saida, log=lambda m: msgs.write(m), verificar_ind=verif, n_bancos=int(n_bancos))
        msgs.update(label="Concluído", state="complete")
        st.session_state["resultado_banco"] = dict(pasta=r["pasta"], zip=r["zip"], figuras=r["figuras"])
    rb = st.session_state.get("resultado_banco")
    if rb and os.path.isdir(rb["pasta"]):
        st.success(f"Projeto gerado em {rb['pasta']}")
        for k, f in rb["figuras"].items():
            if os.path.exists(f):
                st.image(f)
        if rb.get("zip") and os.path.exists(rb["zip"]):
            with open(rb["zip"], "rb") as fh:
                st.download_button("Baixar tudo (.zip)", fh.read(), file_name=os.path.basename(rb["zip"]))
        resumo = os.path.join(rb["pasta"], "RESUMO.md")
        if os.path.exists(resumo):
            st.markdown(open(resumo, encoding="utf-8").read())
