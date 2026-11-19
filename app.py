"""Plataforma FSEN – interface web local.   Rodar:  streamlit run app.py"""
import os
import json
import sqlite3
import datetime as dt
import tempfile

import pandas as pd
import streamlit as st
import yaml

from fsen.modelos import Pedido
from fsen.leitor_ia import ler_pedido
from fsen.pipeline import processar
from fsen.dimensionamento import CAT_PADRAO, carregar_catalogo
from fsen import historico as H
from fsen.dimensionamento import config_de_projeto
from telas_ajuste import tela_ajuste_completa, tela_criterios
from fsen.leitor_ia import status_provedores, config_ia, salvar_config_ia

RAIZ = os.path.dirname(os.path.abspath(__file__))
st.set_page_config(page_title="FSEN – Filtros Senoidais", page_icon="⚡", layout="wide")

st.sidebar.title("⚡ FSEN")
st.sidebar.caption("Dimensionamento, simulação e documentação de filtros senoidais LC/LCL")
pagina = st.sidebar.radio("Menu", ["Nova solicitação", "Ajuste manual e ressimulação", "Critérios de projeto", "Histórico e clientes",
                                   "Catálogo e preços", "Melhorias / atualizações"])
pasta_saida = st.sidebar.text_input("Pasta de saída (Google Drive)", os.environ.get("FSEN_PASTA_SAIDA", os.path.join(RAIZ, "saidas")))
_st_ia = status_provedores()
_cfg_ia = config_ia()
_prov = st.sidebar.selectbox("IA para ler os pedidos", list(_st_ia), index=list(_st_ia).index(_cfg_ia.get("provedor_padrao", "claude")),
                             format_func=lambda k: ("✅ " if _st_ia[k]["pronto"] else "⚠️ ") + _st_ia[k]["nome"])
_mod = st.sidebar.text_input("Modelo", _cfg_ia["provedores"][_prov]["modelo"])
if _prov != _cfg_ia.get("provedor_padrao") or _mod != _cfg_ia["provedores"][_prov]["modelo"]:
    _cfg_ia["provedor_padrao"] = _prov
    _cfg_ia["provedores"][_prov]["modelo"] = _mod
    salvar_config_ia(_cfg_ia)
if not _st_ia[_prov]["pronto"]:
    st.sidebar.caption(f"Defina {_st_ia[_prov]['env']} no INICIAR.bat; sem chave a leitura usa regras.")


def form_pedido(p: Pedido) -> Pedido:
    c1, c2, c3, c4 = st.columns(4)
    p.cliente = c1.text_input("Cliente", p.cliente)
    p.cnpj = c2.text_input("CNPJ", p.cnpj)
    p.cidade_uf = c3.text_input("Cidade/UF", p.cidade_uf)
    p.quantidade = c4.number_input("Quantidade", 1, 1000, int(p.quantidade or 1))
    c1, c2, c3, c4 = st.columns(4)
    p.contato = c1.text_input("Contato", p.contato)
    p.email_contato = c2.text_input("E-mail", p.email_contato)
    p.topologia = c3.selectbox("Topologia", ["LC", "LCL"], index=0 if p.topologia == "LC" else 1)
    p.revenda = c4.checkbox("Revenda", p.revenda)
    c1, c2, c3, c4 = st.columns(4)
    p.tensao_v = c1.number_input("Tensão (V)", 100.0, 1000.0, float(p.tensao_v))
    p.corrente_a = c2.number_input("Corrente do filtro (A)", 1.0, 5000.0, float(p.corrente_a or 100))
    p.freq_rede_hz = c3.number_input("Freq. rede (Hz)", 50.0, 60.0, float(p.freq_rede_hz))
    fs = c4.number_input("fs chaveamento (kHz, 0 = padrão do inversor)", 0.0, 16.0, float(p.fs_khz or 0))
    p.fs_khz = fs or None
    c1, c2, c3, c4 = st.columns(4)
    p.inversor = c1.text_input("Inversor", p.inversor)
    p.inversor_corrente_a = c2.number_input("Corrente inversor (A)", 0.0, 5000.0, float(p.inversor_corrente_a or p.corrente_a))
    p.f_saida_min_hz = c3.number_input("f saída mín (Hz)", 0.0, 400.0, float(p.f_saida_min_hz))
    p.f_saida_max_hz = c4.number_input("f saída máx (Hz)", 1.0, 400.0, float(p.f_saida_max_hz or 60))
    c1, c2, c3, c4 = st.columns(4)
    p.motor_cv = c1.number_input("Motor (cv)", 0.0, 10000.0, float(p.motor_cv))
    p.motor_corrente_a = c2.number_input("Corrente motor (A)", 0.0, 5000.0, float(p.motor_corrente_a))
    p.motor_fp = c3.number_input("FP motor", 0.1, 1.0, float(p.motor_fp))
    p.fator_servico = c4.number_input("Fator de serviço", 1.0, 1.5, float(p.fator_servico))
    c1, c2, c3, c4 = st.columns(4)
    p.cabo_m = c1.number_input("Cabo (m)", 0.0, 5000.0, float(p.cabo_m))
    p.vpk_max_v = c2.number_input("Vpico máx (V)", 0.0, 3000.0, float(p.vpk_max_v or 0)) or None
    p.dvdt_max_v_us = c3.number_input("dv/dt máx (V/µs)", 0.0, 5000.0, float(p.dvdt_max_v_us or 0)) or None
    p.rise_time_min_us = c4.number_input("Rise time mín (µs)", 0.0, 100.0, float(p.rise_time_min_us or 0)) or None
    c1, c2, c3, c4 = st.columns(4)
    p.cabo_secao_mm2 = c1.number_input("Seção do cabo ao motor (mm², 0 = automática)", 0.0, 1000.0, float(p.cabo_secao_mm2 or 0))
    p.cabo_paralelos = int(c2.number_input("Cabos em paralelo por fase (0 = automático)", 0, 12, int(p.cabo_paralelos or 0)))
    p.cabo_blindado = c3.checkbox("Cabo blindado (VFD)", p.cabo_blindado)
    p.estrela_ao_cc = c4.checkbox("Centro-estrela ao barramento CC (all-pole)", p.estrela_ao_cc,
                                  help="Atenua o modo comum e as correntes de mancal; exige acesso ao CC do inversor.")
    p.aplicacao = st.text_input("Aplicação", p.aplicacao)
    return p


if pagina == "Nova solicitação":
    st.title("Nova solicitação")
    texto = st.text_area("Cole aqui o e-mail do cliente", height=180,
                         value=open(os.path.join(RAIZ, "exemplos", "email_AW_293A.txt"), encoding="utf-8").read()
                         if st.session_state.get("exemplo") else "")
    cA, cB, cC = st.columns([2, 1, 1])
    arquivos = cA.file_uploader("Anexos (PDF, imagem, DOCX)", accept_multiple_files=True)
    if cB.button("Carregar exemplo A&W 293 A"):
        st.session_state["exemplo"] = True
        st.rerun()
    if cC.button("🔎 Ler solicitação", type="primary"):
        caminhos = []
        tmp = tempfile.mkdtemp()
        for f in arquivos or []:
            c = os.path.join(tmp, f.name)
            open(c, "wb").write(f.getbuffer())
            caminhos.append(c)
        with st.spinner("Lendo e-mail e anexos..."):
            st.session_state["pedido"] = ler_pedido(texto, caminhos, provedor=_prov).to_dict()
    if "pedido" in st.session_state:
        p = Pedido.from_dict(st.session_state["pedido"])
        st.subheader("Dados extraídos – confira e ajuste")
        if p.lacunas:
            st.info("Premissas: " + " | ".join(p.lacunas))
        p = form_pedido(p)
        st.session_state["pedido"] = p.to_dict()
        sim = H.buscar_similares(p.tensao_v, p.corrente_a, p.topologia)
        if sim:
            with st.expander(f"Projetos anteriores semelhantes ({len(sim)})"):
                st.dataframe(pd.DataFrame(sim)[[c for c in ["cliente", "corrente_a", "tensao_v", "topologia", "l_uh", "c_y_uf",
                                                             "preco_unit", "fonte", "pasta"] if c in pd.DataFrame(sim).columns]])
        from fsen.otimizacao import TOPOLOGIAS
        modo_t = st.radio("Topologias", ["Automático: LC sem resistor primeiro (cascata)", "Escolher topologias"], horizontal=True)
        topos = None
        if modo_t.startswith("Escolher"):
            topos = st.multiselect("Avaliar somente", list(TOPOLOGIAS), default=["LC"], format_func=lambda k: TOPOLOGIAS[k]["nome"])
        _cat_ui = carregar_catalogo()
        _caps_ids = [c["id"] for c in _cat_ui["capacitores"]]
        _caps_sel = st.multiselect("Capacitores a considerar (ex.: só os do estoque; vazio = todos)", _caps_ids,
                                   default=_cat_ui.get("otimizacao", {}).get("capacitores_permitidos") or [],
                                   format_func=lambda i: next(f"{c['fabricante']} {c['uf']:g} µF {c['v_ac']} V – estoque {c.get('estoque', 0)}"
                                                              for c in _cat_ui["capacitores"] if c["id"] == i))
        _ligs = st.multiselect("Ligação do banco de capacitores", ["Estrela", "Delta"],
                               default=_cat_ui.get("otimizacao", {}).get("ligacoes_permitidas") or ["Estrela", "Delta"],
                               help="Delta usa 3× menos capacitores, mas cada um recebe tensão de linha e √3× mais corrente.")
        if st.button("⚙️ Dimensionar, simular e gerar todos os documentos", type="primary"):
            msgs = st.empty()
            with st.spinner("Processando..."):
                r = processar(p, pasta_saida, log=lambda m: msgs.write(m), topologias=topos or None,
                              capacitores=_caps_sel or None, ligacoes=_ligs or None)
            st.session_state["resultado"] = {"pasta": r["pasta"], "zip": r["zip"], "arquivos": r["arquivos"], "graficos": r["graficos"],
                                             "resumo": r["resumo"]}
            st.session_state["cfg_auto"] = config_de_projeto(r["projeto"])
            st.session_state["cfg_manual"] = dict(st.session_state["cfg_auto"])
            for k in ("manual_res", "auto_res"):
                st.session_state.pop(k, None)
    if "resultado" in st.session_state:
        r = st.session_state["resultado"]
        st.success(f"Projeto gerado em {r['pasta']}")
        st.info("Quer mudar algo (uk, fr, capacitores, fechamento, amortecimento, fs)? Abra **Ajuste manual e ressimulação** no menu.")
        st.markdown(r["resumo"])
        _ed = r["arquivos"].get("email_dados")
        if _ed and os.path.exists(_ed):
            with st.expander("✉️ E-mail ao cliente pedindo os dados que faltaram (gerado automaticamente – revise e envie)", expanded=True):
                st.text_area("E-mail", open(_ed, encoding="utf-8").read(), height=420, key="email_dados_txt")
                if r["arquivos"].get("questionario"):
                    st.download_button("📝 Questionário técnico (.docx) para anexar", open(r["arquivos"]["questionario"], "rb"),
                                       file_name=os.path.basename(r["arquivos"]["questionario"]))
        g = r["graficos"]
        t1, t2, t3, t4 = st.tabs(["Formas de onda / espectro", "Resposta em frequência", "Correntes", "Desenhos"])
        with t1:
            st.image(g.get("formas_onda")); st.image(g.get("espectro"))
        with t2:
            st.image(g.get("bode")); st.image(g.get("baixa_ordem")); st.image(g.get("impedancia"))
        with t3:
            st.image(g.get("fluxo"))
        with t4:
            pd_ = os.path.join(r["pasta"], "05_Desenhos")
            for f in sorted(os.listdir(pd_)):
                if f.endswith(".png"):
                    st.image(os.path.join(pd_, f))
        st.subheader("Downloads")
        if r["zip"]:
            st.download_button("📦 Pacote completo (.zip)", open(r["zip"], "rb"), file_name=os.path.basename(r["zip"]))
        cols = st.columns(3)
        for k, (nome, cam) in enumerate(sorted(r["arquivos"].items())):
            if os.path.exists(cam):
                cols[k % 3].download_button(os.path.basename(cam), open(cam, "rb"), file_name=os.path.basename(cam), key=nome)
        st.subheader("E-mails prontos")
        for nome, cam in r["arquivos"].items():
            if nome.startswith("email_"):
                with st.expander(nome.replace("email_", "E-mail – ")):
                    st.code(open(cam, encoding="utf-8").read(), language=None)

elif pagina == "Ajuste manual e ressimulação":
    tela_ajuste_completa(pasta_saida)

elif pagina == "Critérios de projeto":
    tela_criterios()

elif pagina == "Histórico e clientes":
    st.title("Histórico de projetos e clientes fornecidos")
    con = H.conectar()
    df = pd.read_sql("SELECT data, cliente, topologia, corrente_a, tensao_v, quantidade, l_uh, c_y_uf, n_capacitores, ligacao, fr_hz, "
                     "custo_unit, preco_unit, status, pasta FROM projetos ORDER BY data DESC", con)
    st.dataframe(df, width="stretch")
    leg = pd.read_sql("SELECT cliente, topologia, MAX(corrente_a) corrente_a, MAX(tensao_v) tensao_v, COUNT(*) arquivos, "
                      "MAX(modificado) ultimo FROM arquivos_legado GROUP BY pasta_cliente, topologia ORDER BY ultimo DESC", con)
    st.subheader(f"Pastas antigas importadas ({len(leg)})")
    st.dataframe(leg, width="stretch")
    st.subheader("Importar pastas antigas (Google Drive para desktop)")
    pastas = st.text_area("Uma pasta por linha", "G:/Meu Drive/5 - FILTROS-BANCOS-.../6 - FILTRO SENOIDAL LC\n"
                                                 "G:/Meu Drive/5 - FILTROS-BANCOS-.../7 - FILTRO SENOIDAL LCL")
    if st.button("Importar"):
        r = H.importar_pastas([x.strip() for x in pastas.splitlines() if x.strip() and os.path.isdir(x.strip())])
        st.success(f"{r['arquivos']} arquivos, {len(r['clientes'])} clientes")
    if st.button("Exportar planilha de clientes"):
        c = H.exportar_clientes_xlsx(os.path.join(pasta_saida, "Clientes_Fornecidos.xlsx"))
        st.download_button("Baixar", open(c, "rb"), file_name="Clientes_Fornecidos.xlsx")
    st.subheader("Registrar cotação real de fornecedor (recalibra custos)")
    c1, c2, c3, c4 = st.columns(4)
    fo = c1.text_input("Fornecedor", "Cootrans")
    en = c2.number_input("Energia do indutor (J) – ver memorial", 0.0, 10000.0, 0.0)
    pr = c3.number_input("Preço (R$)", 0.0, 1e6, 0.0)
    if c4.button("Salvar cotação") and en and pr:
        H.registrar_cotacao_fornecedor(fo, "INDUTOR", "indutor", en, pr)
        st.write("Calibração:", H.calibrar_custo_indutor() or "precisa de ≥ 2 cotações")

elif pagina == "Catálogo e preços":
    st.title("Catálogo, preços e critérios")
    st.caption("Capacitores, caixas, preços, impostos, margem, fornecedores e limites de projeto. Salvar grava dados/catalogo.yaml.")
    txt = st.text_area("catalogo.yaml", open(CAT_PADRAO, encoding="utf-8").read(), height=650)
    if st.button("Salvar catálogo"):
        yaml.safe_load(txt)
        open(CAT_PADRAO, "w", encoding="utf-8").write(txt)
        st.success("Catálogo salvo.")

else:
    st.title("Melhorias e atualizações")
    cam = os.path.join(RAIZ, "MELHORIAS.md")
    st.markdown(open(cam, encoding="utf-8").read())
    nova = st.text_input("Nova melhoria / pedido")
    if st.button("Adicionar") and nova:
        with open(cam, "a", encoding="utf-8") as f:
            f.write(f"\n- [ ] {dt.date.today():%d/%m/%Y} – {nova}")
        st.rerun()
