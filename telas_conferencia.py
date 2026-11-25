"""Tela: Conferir proposta de fornecedor (indutor / capacitores) – v1.9.9."""
import os
import pandas as pd
import streamlit as st

from fsen import conferencia as C
from fsen.dimensionamento import carregar_catalogo


def _campo(chave_tela, k, rot, un, tipo):
    lab = f"{rot}" + (f" ({un})" if un else "")
    key = f"{chave_tela}_{k}"
    if tipo == "num":
        return st.number_input(lab, value=None, step=None, format="%g", key=key, placeholder="não declarado")
    if tipo == "txt":
        return st.text_input(lab, key=key)
    if tipo == "bool":
        v = st.selectbox(lab, ["não declarado", "sim", "não"], key=key)
        return None if v == "não declarado" else (v == "sim")
    v = st.selectbox(lab, tipo, key=key)
    return None if v.startswith("não declarad") else v


def tela_conferencia(pasta_saida):
    from telas_ajuste import listar_projetos
    import datetime as _dt
    st.title("Conferir proposta de fornecedor")
    st.caption("Digite o que o fornecedor DECLAROU na proposta. A plataforma compara com a especificação (com o porquê de cada "
               "critério), refaz o estudo térmico com as perdas declaradas e gera o parecer + o e-mail de resposta com as pendências.")
    lst = listar_projetos(pasta_saida)
    if not lst:
        st.warning("Nenhum projeto encontrado na pasta de saída.")
        return
    clientes = list(dict.fromkeys(c for c, _, _, _ in lst))
    c1, c2 = st.columns(2)
    cli = c1.selectbox("Cliente", clientes, key="conf_cli")
    projs = [(n, d, t) for c, n, d, t in lst if c == cli]
    idx = c2.selectbox("Projeto", range(len(projs)), key="conf_proj",
                       format_func=lambda i: f"{projs[i][0]}   ·   {_dt.datetime.fromtimestamp(projs[i][2]):%d/%m %H:%M}")
    pasta = projs[idx][1]
    st.caption(pasta)
    comp = st.radio("Componente", ["Indutor", "Capacitores"], horizontal=True, key="conf_comp")
    campos = C.CAMPOS_INDUTOR if comp == "Indutor" else C.CAMPOS_CAPACITOR
    # v1.28.0 (REQ-SEN-023): a planilha de resposta que vai no e-mail de cotação, preenchida pelo fabricante, preenche os campos abaixo
    _hf = "A planilha vai anexa ao e-mail de cotação. Carregue a que o fabricante devolveu preenchida: os campos abaixo são preenchidos sozinhos."
    upf = st.file_uploader("Planilha de resposta do fabricante (Formulario_Resposta_*.xlsx) – opcional", type=["xlsx"], key=f"conf_form_{comp}", help=_hf)
    if upf is not None and st.session_state.get(f"conf_form_lido_{comp}") != upf.name:
        try:
            lido = C.ler_formulario_xlsx(upf, "indutor" if comp == "Indutor" else "capacitor")
            for k, v in lido.items():
                tp = next((t for kk, _r, _u, t in campos if kk == k), None)
                st.session_state[f"conf_{comp}_{k}"] = ("sim" if v else "não") if tp == "bool" else v
            st.session_state[f"conf_form_lido_{comp}"] = upf.name
            st.success(f"{len(lido)} item(ns) lido(s) da planilha do fabricante.")
            st.rerun()
        except Exception as ex:
            st.error(f"Não consegui ler a planilha: {type(ex).__name__}: {ex}")
    decl = {}
    with st.form(f"form_conf_{comp}"):
        cols = st.columns(3)
        for i, (k, rot, un, tipo) in enumerate(campos):
            with cols[i % 3]:
                decl[k] = _campo(f"conf_{comp}", k, rot, un, tipo)
        ir = st.form_submit_button("🔎 Conferir proposta", type="primary")
    if ir:
        cat = carregar_catalogo()
        with st.spinner("Ressimulando o projeto e conferindo..."):
            chave = ("conf_proj_obj", pasta)
            if st.session_state.get("conf_cache_key") != chave:
                from fsen.mecanica import projetar_arranjo
                from fsen.termico import aplicar_termico
                pr = C.carregar_projeto(pasta, cat)
                arr = projetar_arranjo(pr, cat)
                arr, _ = aplicar_termico(pr, arr, cat)
                st.session_state["conf_cache_key"] = chave
                st.session_state["conf_cache"] = (pr, arr)
            pr, arr = st.session_state["conf_cache"]
            res = C.conferir_indutor(pr, arr, cat, decl) if comp == "Indutor" else C.conferir_capacitor(pr, cat, decl)
            docx, txt = C.gerar_parecer(pr, arr, cat, pasta, "indutor" if comp == "Indutor" else "capacitor", decl, res)
        st.session_state["conf_res"] = (res, docx, txt)
    if "conf_res" in st.session_state:
        res, docx, txt = st.session_state["conf_res"]
        par = res["parecer"]
        (st.success if par == "APROVADO" else st.warning if par.startswith(("APROVADO COM", "INCOMPLETO")) else st.error)(f"PARECER: {par}")
        df = pd.DataFrame(res["itens"])[["status", "item", "declarado", "exigido", "porque"]]
        cores = {"OK": "#C6EFCE", "ALERTA": "#FFEB9C", "REPROVA": "#FFC7CE", "PENDENTE": "#DDEBF7"}
        st.dataframe(df.style.apply(lambda r: [f"background-color: {cores.get(r['status'], '')}" if c == "status" else "" for c in r.index],
                                    axis=1), width="stretch", hide_index=True)
        c1, c2 = st.columns(2)
        if os.path.exists(docx):
            c1.download_button("📄 Parecer técnico (.docx)", open(docx, "rb"), file_name=os.path.basename(docx))
        if os.path.exists(txt):
            c2.download_button("✉️ E-mail de resposta (.txt)", open(txt, "rb"), file_name=os.path.basename(txt))
            with st.expander("E-mail de resposta ao fornecedor (pendências com o motivo)", expanded=True):
                st.code(open(txt, encoding="utf-8").read(), language=None)
        st.caption(f"Arquivos salvos em {os.path.dirname(docx)}")
    if comp == "Indutor":
        _secao_ensaios_indutor(pasta)


def _secao_ensaios_indutor(pasta):
    """v1.11.8: resultados medidos (calibração) e conferência no FEMM."""
    import glob
    import json
    st.divider()
    st.subheader("Ensaios medidos e verificação independente do indutor")
    eng = os.path.join(pasta, "01_Engenharia")
    js = glob.glob(os.path.join(eng, "**", "indutor_projeto.json"), recursive=True)
    if not js:
        st.info("Este projeto não tem o projeto do indutor por elementos finitos.")
        return
    ind = json.load(open(js[0], encoding="utf-8"))
    planilhas = glob.glob(os.path.join(eng, "**", "Resultados_Medidos_Indutor_*.xlsx"), recursive=True)
    luas = glob.glob(os.path.join(eng, "**", "Verificacao_FEMM_*.lua"), recursive=True)
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**1) Resultados medidos (protótipo ou indutor antigo)**")
        if planilhas:
            st.download_button("⬇️ Planilha em branco (previsto preenchido)", open(planilhas[0], "rb"),
                               file_name=os.path.basename(planilhas[0]))
        up = st.file_uploader("Carregar a planilha preenchida (.xlsx)", type=["xlsx"], key="cal_xlsx")
        if up is not None:
            from fsen import calibracao as CAL
            tmp = os.path.join(eng, "_medido_" + up.name)
            open(tmp, "wb").write(up.getbuffer())
            res = CAL.avaliar(tmp, cod=os.path.basename(pasta))
            df = pd.DataFrame(res["linhas"])
            st.dataframe(df, width="stretch", hide_index=True)
            fs = CAL.fatores_sugeridos()
            if fs:
                st.caption("Histórico de calibração (mediana medido/previsto) – não aplicado automaticamente: "
                           + "; ".join(f"{k} {v['fator']:.3f} (n={v['n']})" for k, v in fs.items()))
    with c2:
        st.markdown("**2) Conferência no FEMM (Windows)**")
        if luas:
            st.download_button("⬇️ Script FEMM (.lua)", open(luas[0], "rb"), file_name=os.path.basename(luas[0]))
        st.caption("Abra o script no FEMM 4.2 (File › Open Lua Script). Ele grava resultado_femm_FSEN.csv – carregue abaixo.")
        upc = st.file_uploader("Carregar resultado_femm_FSEN.csv", type=["csv"], key="femm_csv")
        if upc is not None:
            from fsen import ind_verificacao as V
            tmp = os.path.join(eng, "resultado_femm_FSEN.csv")
            open(tmp, "wb").write(upc.getbuffer())
            fem = V.ler_femm_csv(tmp, ind)
            vj = glob.glob(os.path.join(eng, "**", "verificacao_indutor.json"), recursive=True)
            if vj:
                cmp = V.carregar_cmp(vj[0])
                pdf = os.path.join(os.path.dirname(vj[0]), os.path.basename(vj[0]).replace(".json", "_com_FEMM.pdf"))
                V.relatorio(ind, cmp, pdf, femm=fem)
                st.success("Comparação com o FEMM incluída no relatório de verificação.")
                st.download_button("📄 Relatório de verificação (com FEMM)", open(pdf, "rb"), file_name=os.path.basename(pdf))
            P = {"L2d (µH)": [x * 1e6 for x in ind.get("L2d", [])]}
            st.write({"FEMM L 2D (µH)": [round(x * 1e6, 1) for x in fem.get("L2d", [])], "Plataforma L 2D (µH)":
                      [round(x, 1) for x in P["L2d (µH)"]], "FEMM R CA (mΩ)": {f"{k:g} Hz": round(v * 1e3, 2) for k, v in fem["Rac"].items()}})
