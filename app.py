"""Plataforma FSEN – interface web local.   Rodar:  streamlit run app.py"""
import os
import json
import sqlite3
import datetime as dt
import tempfile

import sys
import pandas as pd
import streamlit as st
import yaml

# Atualização com a plataforma aberta: o Streamlit recarrega o app.py mas mantém os módulos antigos na memória
# (erro "cannot import name ..."). Se a versão mudou, descarrega fsen.* e telas_ajuste para importar a versão nova.
try:
    _v_disco = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "versao_plataforma.json"), encoding="utf-8"))["versao"]
except Exception:
    _v_disco = "?"
if os.environ.get("FSEN_VER_CARREGADA") != _v_disco:
    for _m in list(sys.modules):
        if _m in ("telas_ajuste", "telas_conferencia", "fsen") or _m.startswith("fsen."):
            del sys.modules[_m]
    os.environ["FSEN_VER_CARREGADA"] = _v_disco

from fsen.modelos import Pedido
from fsen.leitor_ia import ler_pedido
from fsen.pipeline import processar
from fsen.dimensionamento import CAT_PADRAO, carregar_catalogo
from fsen import historico as H
from fsen.dimensionamento import config_de_projeto
from telas_ajuste import tela_ajuste_completa, tela_criterios, painel_abrir_projeto, painel_atp
from fsen.leitor_ia import status_provedores, config_ia, salvar_config_ia, salvar_chave, testar_ia, MODELOS_CLAUDE, ESFORCOS

RAIZ = os.path.dirname(os.path.abspath(__file__))
from fsen.versao import NOME, info as _vinfo
st.set_page_config(page_title=f"FSEN v{_vinfo().get('versao')} – Filtros Senoidais", page_icon="⚡", layout="wide")

st.sidebar.title(f"⚡ FSEN v{_vinfo().get('versao')}")
st.sidebar.caption(f"{NOME} – versão {_vinfo().get('versao')} de {_vinfo().get('data', '')}")
st.sidebar.caption("Dimensionamento, simulação e documentação de filtros senoidais LC/LCL")
pagina = st.sidebar.radio("Menu", ["Nova solicitação", "Ajuste manual e ressimulação", "Conferir proposta de fornecedor",
                                   "Critérios de projeto", "Histórico e clientes",
                                   "Catálogo e preços", "Melhorias / atualizações"])
from seletor import seletor_pasta
with st.sidebar.expander("📂 Pasta de saída (PROJETOS)", expanded=False):
    pasta_saida = seletor_pasta("Pasta onde ficam os projetos", "pasta_saida",
                                os.environ.get("FSEN_PASTA_SAIDA", os.path.join(RAIZ, "saidas")))
st.sidebar.caption(f"Saída: …{pasta_saida[-45:]}")
try:
    from fsen.atp import achar_tpbig as _tp
    _tpb = _tp(carregar_catalogo())
    (st.sidebar.success if _tpb else st.sidebar.warning)(
        f"ATP: encontrado – dupla checagem automática ({_tpb})" if _tpb else
        "ATP NÃO encontrado neste computador – a dupla checagem não roda (só gera os decks .atp)")
except Exception:
    pass
_st_ia = status_provedores()
_cfg_ia = config_ia()
_prov = st.sidebar.selectbox("IA para ler os pedidos", list(_st_ia), index=list(_st_ia).index(_cfg_ia.get("provedor_padrao", "claude")),
                             format_func=lambda k: ("✅ " if _st_ia[k]["pronto"] else "⚠️ ") + _st_ia[k]["nome"])
_pc = _cfg_ia["provedores"][_prov]
if _pc.get("tipo") in ("anthropic", "claude_code"):
    _mods = list(MODELOS_CLAUDE)
    if _pc["modelo"] not in _mods:
        _mods.append(_pc["modelo"])
    _mod = st.sidebar.selectbox("Modelo Claude", _mods, index=_mods.index(_pc["modelo"]),
                                format_func=lambda m: MODELOS_CLAUDE.get(m, m))
    _esf = st.sidebar.selectbox("Esforço", list(ESFORCOS), index=list(ESFORCOS).index(_pc.get("esforco") or "medium"),
                                format_func=lambda e: f"{ESFORCOS[e]} ({e})")
else:
    _mod = st.sidebar.text_input("Modelo", _pc["modelo"])
    _esf = _pc.get("esforco")
if (_prov != _cfg_ia.get("provedor_padrao") or _mod != _pc["modelo"] or _esf != _pc.get("esforco")):
    _cfg_ia["provedor_padrao"] = _prov
    _pc["modelo"] = _mod
    if _esf:
        _pc["esforco"] = _esf
    salvar_config_ia(_cfg_ia)
_cc = _pc.get("tipo") == "claude_code"
if _st_ia[_prov]["pronto"]:
    st.sidebar.success(("IA ativa pela sua assinatura Claude: " if _cc else "IA ativa: ") + _mod
                       + (f" · esforço {ESFORCOS.get(_esf, _esf)}" if _esf else ""))
elif _cc:
    st.sidebar.warning("IA DESLIGADA – Claude Code não encontrado neste computador. Instale o Claude Code e faça login com a sua "
                       "conta Claude (a mesma assinatura paga). Enquanto isso a leitura usa regras.")
else:
    st.sidebar.warning("IA DESLIGADA – sem chave de API. A leitura dos pedidos está usando regras (pior).")
if _cc:
    if st.sidebar.button("Testar IA", key="testar_ia_cc"):
        with st.spinner("Testando a IA pela assinatura..."):
            _ok, _msg = testar_ia(_prov)
        (st.sidebar.success if _ok else st.sidebar.error)(_msg)
if not _cc:
    with st.sidebar.expander("🔑 Chave da API" + (" (configurada)" if _st_ia[_prov]["pronto"] else " – configurar")):
        st.caption(f"Cole a chave do {_st_ia[_prov]['nome'].split(' –')[0]}. Fica salva só neste computador, em "
                   "%USERPROFILE%\\.fsen – não vai para o Drive nem para o GitHub.")
        _ch = st.text_input(_st_ia[_prov]["env"] or "Chave", type="password", key="chave_api")
        c1, c2 = st.columns(2)
        if c1.button("Salvar", key="salvar_chave") and _ch.strip() and _st_ia[_prov]["env"]:
            salvar_chave(_st_ia[_prov]["env"], _ch)
            st.rerun()
        if c2.button("Testar IA", key="testar_ia"):
            with st.spinner("Testando..."):
                _ok, _msg = testar_ia(_prov)
            (st.success if _ok else st.error)(_msg)


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
    p.corrente_a = c2.number_input("Corrente do filtro (A)", 0.0, 5000.0, float(p.corrente_a or 0))
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
    painel_abrir_projeto(pasta_saida, "abrir_ns")
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
        if not caminhos and not texto.strip():
            st.error("Cole o e-mail e/ou anexe os arquivos (Word, PDF, imagem) antes de ler.")
            st.stop()
        import time as _t
        _t0 = _t.time()
        with st.spinner(f"Lendo e-mail e {len(caminhos)} anexo(s) com {_st_ia[_prov]['nome']}..."):
            _pl = ler_pedido(texto, caminhos, provedor=_prov)
        st.session_state["pedido"] = _pl.to_dict()
        _ia = "[lido por IA" in (_pl.observacoes or "")
        st.session_state["leitura_info"] = dict(
            fonte=("IA – " + _mod + (f" · esforço {_esf}" if _esf else "")) if _ia else "REGRAS (sem IA)",
            ia=_ia, arquivos=[os.path.basename(c) for c in caminhos], tem_texto=bool(texto.strip()),
            hora=dt.datetime.now().strftime("%H:%M:%S"), seg=round(_t.time() - _t0, 1))
        for k in ("resultado", "cfg_auto", "cfg_manual", "manual_res", "auto_res"):
            st.session_state.pop(k, None)
    if "pedido" in st.session_state:
        p = Pedido.from_dict(st.session_state["pedido"])
        st.subheader("Dados extraídos – confira e ajuste")
        _li = st.session_state.get("leitura_info")
        if _li:
            (st.success if _li["ia"] else st.warning)(
                f"Leitura feita por **{_li['fonte']}** às {_li['hora']} ({_li['seg']} s) – arquivos lidos: "
                f"{', '.join(_li['arquivos']) or 'nenhum'}" + (" + texto do e-mail" if _li["tem_texto"] else ""))
        else:
            st.warning("Estes dados não vieram de uma leitura nesta sessão (projeto aberto ou dados antigos). "
                       "Para ler de novo, anexe os arquivos e clique em 🔎 Ler solicitação.")
        _vaz = [n for n, v in (("cliente", p.cliente), ("corrente do motor", p.motor_corrente_a), ("potência do motor", p.motor_cv or p.motor_kw),
                               ("comprimento do cabo", p.cabo_m), ("modelo do inversor", p.inversor not in ("", "GENERICO")),
                               ("faixa de operação", "f_saida_max_hz" in (p.informados or [])))
                if not v]
        if _vaz:
            st.warning("⚠️ Não foram encontrados no pedido: **" + ", ".join(_vaz) + "**. Se o cliente informou, a leitura falhou – "
                       "confira os anexos/IA ou preencha abaixo antes de dimensionar.")
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
        _falta = [n for n, v in (("corrente do filtro", p.corrente_a), ("tensão", p.tensao_v), ("cliente", p.cliente.strip())) if not v]
        if _falta:
            st.error("Falta " + " e ".join(_falta) + " – a leitura do pedido não encontrou. Preencha acima antes de dimensionar "
                     "(a plataforma não usa mais valor padrão escondido).")
        st.caption(f"Entra na simulação: filtro {p.corrente_a:g} A / {p.tensao_v:g} V · inversor {p.inversor} {p.inversor_corrente_a:g} A · "
                   f"motor {p.motor_cv:g} CV, {p.motor_corrente_a:g} A, FP {p.motor_fp:g}, FS {p.fator_servico:g} · "
                   f"cabo {p.cabo_m:g} m · {p.f_saida_min_hz:g}–{p.f_saida_max_hz:g} Hz · {p.quantidade} pç")
        if st.button("⚙️ Dimensionar, simular e gerar todos os documentos", type="primary", disabled=bool(_falta)):
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
        painel_atp(r["pasta"])
        st.markdown(r["resumo"])
        _ed = r["arquivos"].get("email_dados")
        if _ed and os.path.exists(_ed):
            with st.expander("✉️ E-mail ao cliente pedindo os dados que faltaram (gerado automaticamente – revise e envie)", expanded=True):
                st.text_area("E-mail", open(_ed, encoding="utf-8").read(), height=420, key="email_dados_txt")
                if r["arquivos"].get("questionario"):
                    st.download_button("📝 Questionário técnico (.docx) para anexar", open(r["arquivos"]["questionario"], "rb"),
                                       file_name=os.path.basename(r["arquivos"]["questionario"]))
        g = r["graficos"]
        t1, t2, t3, t4 = st.tabs(["Formas de onda / espectro", "Resposta em frequência", "Correntes e tensões RMS", "Desenhos"])
        def _img(*ks):
            for k in ks:
                if g.get(k) and os.path.exists(g[k]):
                    st.image(g[k])
        with t1:
            _img("formas_onda", "espectro")
        with t2:
            _img("bode", "baixa_ordem", "impedancia")
        with t3:
            _img("rms", "fluxo")
        with t4:
            pd_ = os.path.join(r["pasta"], "05_Desenhos")
            for f in (sorted(os.listdir(pd_)) if os.path.isdir(pd_) else []):
                if f.endswith(".png"):
                    st.image(os.path.join(pd_, f))
        st.subheader("Downloads")
        if r.get("zip") and os.path.exists(r["zip"]):
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

elif pagina == "Conferir proposta de fornecedor":
    from telas_conferencia import tela_conferencia
    tela_conferencia(pasta_saida)

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
    _pi = seletor_pasta("Pasta a importar", "pasta_importar", os.path.dirname(pasta_saida), lembrar_escolha=False)
    _lst = st.session_state.setdefault("pastas_importar", [])
    if st.button("➕ Adicionar esta pasta à lista") and _pi and _pi not in _lst:
        _lst.append(_pi)
    _lst[:] = st.multiselect("Pastas a importar", _lst, default=_lst)
    if st.button("Importar", disabled=not _lst):
        r = H.importar_pastas([x for x in _lst if os.path.isdir(x)])
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
