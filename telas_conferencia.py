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
