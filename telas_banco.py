"""Tela de BANCO DESSINTONIZADO e FILTRO SINTONIZADO (v1.13.0) – aparece quando o tipo de filtro escolhido na barra lateral
não é o filtro senoidal. O filtro senoidal continua no fluxo original, sem mudanças."""
import os

import pandas as pd
import streamlit as st

from fsen import banco as B
from fsen.doc_banco import titulo_tipo, codigo


def _harm_editor(chave, padrao, rotulo, unidade):
    df = pd.DataFrame([dict(h=int(h), valor=float(v)) for h, v in sorted(padrao.items())])
    ed = st.data_editor(df, key=chave, num_rows="dynamic", width="stretch",
                        column_config={"h": st.column_config.NumberColumn("Harmônica", min_value=2, max_value=50, step=1),
                                       "valor": st.column_config.NumberColumn(f"{rotulo} ({unidade})", min_value=0.0, format="%.2f")})
    return {int(r["h"]): float(r["valor"]) for _, r in ed.dropna().iterrows() if r["valor"] > 0}


def tela_banco(tipo, pasta_saida):
    sint = tipo == "sintonizado"
    st.title("Filtro harmônico sintonizado" if sint else "Banco de capacitores dessintonizado")
    st.caption("O reator de cada estágio é projetado pelo mesmo motor do filtro senoidal: triagem de chapas Aperam e condutores, "
               "elementos finitos (2 entreferros/coluna, barra de cobre), térmico, verificação independente (NGSolve), análise "
               "avançada 3D, desenhos, CAD e documentos aos fornecedores.")
    p = B.PedidoBanco(tipo=tipo)
    c1, c2, c3, c4 = st.columns(4)
    p.cliente = c1.text_input("Cliente", "", key="bc_cli")
    p.projeto = c2.text_input("Projeto / referência", "", key="bc_proj")
    p.tensao_v = c3.number_input("Tensão da rede (V)", 200.0, 1000.0, 440.0, key="bc_v")
    p.freq_hz = c4.selectbox("Frequência (Hz)", [60.0, 50.0], key="bc_f")
    c1, c2, c3 = st.columns([2, 1, 1])
    est = c1.text_input("Estágios (kvar efetivos na tensão da rede, separados por +)", "25 + 50 + 50" if not sint else "100",
                        key="bc_est")
    try:
        p.estagios_kvar = [float(x.replace(",", ".")) for x in est.replace(";", "+").split("+") if x.strip()]
    except ValueError:
        st.error("Estágios: use números separados por + (ex.: 25 + 50 + 50)")
        return
    n_bancos = c2.number_input("Quantidade de bancos", 1, 100, 1, key="bc_n")
    p.amb_c = c3.number_input("Ambiente (°C)", 20.0, 55.0, 40.0, key="bc_amb")
    if sint:
        c1, c2, c3 = st.columns(3)
        ords = c1.text_input("Harmônica de cada ramo (na ordem dos estágios)", "5", key="bc_ord")
        try:
            p.ordens = [float(x.replace(",", ".")) for x in ords.replace(";", "+").replace(",", "+").split("+") if x.strip()]
        except ValueError:
            st.error("Harmônicas: ex. 5 + 7 + 11")
            return
        p.fator_sintonia = c2.number_input("Sintonia (fração da harmônica)", 0.85, 1.0, 0.95, 0.01, key="bc_fs",
                                           help="Abaixo da harmônica para não virar ressonância com a tolerância e o envelhecimento do capacitor (típico 0,93–0,97).")
        p.q_reator = c3.number_input("Fator de qualidade Q do reator", 10.0, 200.0, 40.0, key="bc_q")
    else:
        p.p_pct = st.radio("Fator de dessintonia p", [5.67, 7.0, 14.0], index=1, horizontal=True, key="bc_p",
                           format_func=lambda x: {5.67: "5,67 % (210 Hz/60 Hz – 4,2ª)", 7.0: "7 % (227 Hz – 3,78ª)",
                                                  14.0: "14 % (160 Hz – 2,67ª; rede com 3ª harmônica)"}[x])
    st.subheader("Rede")
    c1, c2, c3 = st.columns(3)
    p.trafo_kva = c1.number_input("Transformador (kVA)", 50.0, 10000.0, 1000.0, key="bc_tr")
    p.trafo_z_pct = c2.number_input("Impedância do transformador (%)", 2.0, 12.0, 6.0, key="bc_z")
    p.scc_rede_mva = c3.number_input("Scc da rede em MT (MVA)", 10.0, 5000.0, 250.0, key="bc_scc")
    c1, c2 = st.columns(2)
    with c1:
        if sint:
            st.markdown("**Distorção de FUNDO da rede a montante (% de Un, sem o filtro)** – o filtro sintonizado absorve o fundo da "
                        "rede; use a medição sempre que houver")
        else:
            st.markdown("**Distorção de tensão de projeto (% de Un)** – padrão de guias de fabricantes; substitua pela medição")
        p.harm_tensao_pct = _harm_editor("bc_hv" + ("s" if sint else ""), B.HARM_PADRAO_SINT if sint else B.HARM_PADRAO, "Tensão", "%")
    with c2:
        st.markdown("**Corrente harmônica da carga (A)**" + (" – define a absorção do filtro e o THD" if sint else " – opcional"))
        p.harm_carga_a = _harm_editor("bc_hi", {5: 0.0} if not sint else {5: 50.0, 7: 30.0}, "Corrente", "A")
    st.divider()
    try:
        res = B.dimensionar(p)
    except Exception as e:
        st.error(f"Cálculo não concluído: {e}")
        return
    st.subheader(f"Prévia – {titulo_tipo(p)} – {codigo(p)}")
    df = pd.DataFrame([{"Estágio": i + 1, "kvar": e["Q_kvar"], "p %": round(e["p_pct"], 2), "Sintonia Hz": round(e["f_sintonia"], 1),
                        "L µH/fase": round(e["L_uH"], 1), "I1 A": round(e["I1"], 1), "I térmica reator A": round(e["requisitos"]["In"], 1),
                        "U capacitor V": round(e["Uc_rms"]), "Capacitor": f"{e['Q_cap_nom_kvar']:.1f} kvar / {e['U_cap_nom']:g} V"}
                       for i, e in enumerate(res["estagios"])])
    st.dataframe(df, hide_index=True, width="stretch")
    vr = res["varredura"]
    st.line_chart(pd.DataFrame({"h": vr["h"], "|Z| com banco (Ω)": vr["Z"], "|Z| rede (Ω)": vr["Zs"]}).set_index("h"))
    st.caption("Ressonância paralela: " + (", ".join(f"{x:.2f}ª ({x*p.freq_hz:.0f} Hz)" for x in vr["picos"]) or "nenhuma"))
    if res.get("thd"):
        st.info(f"THD de tensão na barra pela carga: sem filtro {res['thd']['sem']:.2f} % → com filtro {res['thd']['com']:.2f} %")
    for a in res["avisos"]:
        st.warning(a)
    verif = st.checkbox("Verificação independente + análise avançada dos reatores (NGSolve, ~2–3 min por reator)", True, key="bc_verif")
    if st.button("Gerar projeto completo (reatores, desenhos, CAD, memorial, especificações)", type="primary"):
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
