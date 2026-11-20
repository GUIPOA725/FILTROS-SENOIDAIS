"""Fluxo completo: pedido -> dimensionamento -> simulação -> desenhos -> documentos -> custos -> histórico."""
from __future__ import annotations
import os
import re
import json
import shutil
import datetime as _dt

from .modelos import Pedido
from .dimensionamento import dimensionar, carregar_catalogo, _json_default
from .mecanica import projetar_arranjo
from .custos import montar_bom, formar_preco
from .graficos import gerar_todos
from .desenhos import gerar_desenhos, proj_codigo
from . import documentos as D
from . import historico as H

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def pasta_cliente(nome: str) -> str:
    """Nome legível da pasta do cliente: sem sufixos societários e caracteres inválidos no Windows."""
    n = re.sub(r"\(.*?\)", " ", nome or "")
    n = re.sub(r"\b(LTDA|LTDA\.|S/?A|S\.A\.|EIRELI|ME|EPP|REVENDA)\b\.?", " ", n, flags=re.I)
    n = re.sub(r'[<>:"/\\|?*]', " ", n)
    n = re.sub(r"\s+", " ", n).strip(" .-_–—")
    return n[:60] or "Cliente sem nome"


def _norm(t):
    import unicodedata
    t = unicodedata.normalize("NFKD", t or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]", "", t)


def _achar_pasta_cliente(pasta_base, cliente):
    """Reaproveita a pasta do cliente que já existe (ignora acentos, maiúsculas e pontuação)."""
    alvo = pasta_cliente(cliente)
    try:
        n = _norm(alvo)
        for d in os.listdir(pasta_base):
            if os.path.isdir(os.path.join(pasta_base, d)) and (_norm(d) == n or (len(n) > 5 and (_norm(d).startswith(n) or n.startswith(_norm(d))) and len(_norm(d)) > 5)):
                return d
    except FileNotFoundError:
        pass
    return alvo


def _slug(s):
    s = re.sub(r"[^\w\s-]", "", s or "", flags=re.U).strip()
    return re.sub(r"\s+", "_", s)[:40] or "cliente"


def processar(ped: Pedido, pasta_base: str = None, cat=None, registrar=True, zipar=True, log=print, projeto=None, topologias=None, capacitores=None,
              ligacoes=None, prioridade="custo", queda_max=None):
    """projeto: um Projeto já pronto (ex.: ajuste manual). Se None, roda a otimização global."""
    cat = cat or carregar_catalogo()
    pasta_base = pasta_base or os.path.join(RAIZ, "saidas")
    t0 = _dt.datetime.now()
    log("1/7 Dimensionando e otimizando (L, C, amortecimento)...")
    if projeto is not None:
        proj = projeto
        cat = getattr(projeto, "_cat", cat)
        if not getattr(proj, "_sims", None):
            from .dimensionamento import projeto_manual, config_de_projeto
            cfg = config_de_projeto(proj)
            proj2 = projeto_manual(ped, cat, **cfg)
            proj2._otimizacao = getattr(proj, "_otimizacao", None)
            proj = proj2
    else:
        proj = dimensionar(ped, cat, log=log, topologias=topologias, capacitores=capacitores, ligacoes=ligacoes)
        if prioridade == "mercado" and proj.topologia == "LC" and not proj.l2:
            # v1.9.11: indutor na faixa de mercado (MTE 8–10 %) e MENOS capacitores, aprovado e robusto (L ±10 %, C ±5 %)
            try:
                from . import ponto_otimo as PO
                from .dimensionamento import projeto_manual
                log("   Prioridade 'indutor de mercado / menos capacitores': varrendo opções...")
                _caps = capacitores or None
                _ops = PO.otimizar_mercado(ped, cat, proj.fs_hz / 1000, caps=_caps, ligacoes=tuple(ligacoes or ("Delta", "Estrela")))
                if _ops:
                    o = _ops[0]
                    _otim = getattr(proj, "_otimizacao", None)
                    proj = projeto_manual(ped, cat, proj.fs_hz / 1000, o["L_uh"], o["cap_id"], o["ligacao"], o["n_por_ramo"])
                    proj._otimizacao = _otim
                    proj.avisos = list(getattr(proj, "avisos", []) or []) + [
                        f"Configuração escolhida pela prioridade 'indutor de mercado / menos capacitores' (uk {o['uk_pct']} %, "
                        f"{o['n_caps']} capacitores, robusta a L ±10 % e C ±5 %)."]
                    log(f"   → {o['L_uh']:.0f} µH + {o['n_caps']} × {o['cap_id']} ({o['ligacao']})")
                else:
                    log("   Nenhuma opção de mercado robusta – mantida a otimização por custo")
            except Exception as e:
                log(f"   (prioridade de mercado não aplicada: {e})")
        elif prioridade == "min_caps" and proj.topologia == "LC" and not proj.l2:
            # v1.9.13: capacitor FORÇADO (estoque) e o MÍNIMO de capacitores, compensando no indutor, com queda máxima
            try:
                from . import opcoes_caps as OC
                from .dimensionamento import projeto_manual
                _caps = list(capacitores or [proj.banco.cap_id])
                _ligs = tuple(ligacoes or ("Delta", "Estrela"))
                _qm = float(queda_max or OC.QUEDA_MAX_PADRAO)
                log(f"   Prioridade 'mínimo de capacitores': {', '.join(_caps)} ({', '.join(_ligs)}), queda ≤ {_qm:g} % – varrendo casos...")
                _est = OC.varrer(ped, cat, proj.fs_hz / 1000, _caps, _ligs, queda_max=_qm, log=log)
                o = _est["recomendada"]
                if o:
                    _otim = getattr(proj, "_otimizacao", None)
                    proj = projeto_manual(ped, cat, proj.fs_hz / 1000, o["L_uh"], o["cap_id"], o["ligacao"], o["n_por_ramo"])
                    proj._otimizacao = _otim
                    proj.avisos = list(getattr(proj, "avisos", []) or []) + [
                        f"Configuração escolhida pela prioridade 'mínimo de capacitores' com capacitor forçado ({o['cap_id']}): "
                        f"{o['n_caps']} capacitores, queda {o['queda']} % (≤ {_qm:g} %), robusta a L ±10 % e C ±5 %."]
                    log(f"   → {o['L_uh']:.0f} µH + {o['n_caps']} × {o['cap_id']} ({o['ligacao']})")
                else:
                    log("   Nenhum caso válido com o capacitor forçado – mantida a otimização por custo")
                proj.estudo_opcoes = _est
            except Exception as e:
                log(f"   (prioridade 'mínimo de capacitores' não aplicada: {type(e).__name__}: {e})")
    cod = proj_codigo(proj)
    sufixo = f"_AJUSTE-MANUAL-{t0:%H%M}" if projeto is not None else ""
    # uma pasta por cliente; dentro, um projeto por solicitação: PROJETOS\<Cliente>\<data>_<código>
    pasta = os.path.join(pasta_base, _achar_pasta_cliente(pasta_base, ped.cliente), f"{t0:%Y-%m-%d}_{cod}{sufixo}")
    if os.path.exists(pasta) and not sufixo:          # mesma solicitação reprocessada no mesmo dia: não sobrescreve
        pasta += f"_{t0:%H%M}"
    sub = {k: os.path.join(pasta, k) for k in ("01_Engenharia", "02_Cliente", "03_Fornecedores", "04_Montadora", "05_Desenhos", "graficos")}
    for p in sub.values():
        os.makedirs(p, exist_ok=True)
    similares = H.buscar_similares(ped.tensao_v, ped.corrente_a, proj.topologia)
    log("2/7 Arranjo mecânico, térmica e cabos...")
    arr = projetar_arranjo(proj, cat)
    from .termico import aplicar_termico
    arr, _term = aplicar_termico(proj, arr, cat)
    log("   Dados faltantes: análise de sensibilidade das premissas...")
    try:
        from . import dados_faltantes as DF
        _ped_obj = Pedido.from_dict(proj.pedido) if isinstance(proj.pedido, dict) else proj.pedido
        _ped_obj.informados = ped.informados
        proj.dados_faltantes = DF.analisar(proj, cat, _ped_obj, log=log)
        log(f"   {len(proj.dados_faltantes['itens'])} itens a confirmar com o cliente "
            f"({proj.dados_faltantes['n_criticos']} críticos)")
    except Exception as e:
        proj.dados_faltantes = None
        log(f"   Dados faltantes: análise não concluída ({e})")
    log("3/7 Lista de material e preço...")
    itens = montar_bom(proj, arr, cat)
    orc = formar_preco(proj, itens, cat)
    log("4/7 Gráficos de simulação e da otimização...")
    graf = gerar_todos(proj, sub["graficos"])
    from .graficos import grafico_termico
    graf["termico"] = grafico_termico(proj, arr, sub["graficos"])
    df_opt = getattr(proj, "_otimizacao", None)
    if df_opt is not None and len(df_opt):
        from .graficos import grafico_pareto
        graf["pareto"] = grafico_pareto(df_opt, sub["graficos"])
        df_opt.to_excel(os.path.join(sub["01_Engenharia"], f"{cod}_Otimizacao_todas_configuracoes.xlsx"), index=False)
    _atp_dupla_checagem(proj, cat, sub["01_Engenharia"], cod, log)
    log("5/7 Desenhos 2D/3D e diagrama elétrico...")
    pdf_des, pngs = gerar_desenhos(proj, arr, cat, sub["05_Desenhos"])
    log("6/7 Documentos (memorial, proposta, ETs, montagem, planilha)...")
    arqs = {
        "memorial": D.memorial(proj, arr, orc, graf, pngs, cat, sub["01_Engenharia"]),
        "planilha": D.planilha_custos(proj, arr, orc, cat, sub["01_Engenharia"]),
        "proposta": D.proposta(proj, arr, orc, cat, sub["02_Cliente"]),
        "folha_dados": D.folha_dados(proj, arr, cat, sub["02_Cliente"], pngs),
        "desenhos_pdf": pdf_des,
    }
    try:                                            # v1.9.11: estudo de ponto ótimo de mercado + robustez + referências
        from . import ponto_otimo as PO
        proj.estudo_mercado = PO.estudo(proj, cat, log=log)
        arqs["estudo_ponto_otimo"] = PO.gerar_docx(proj, cat, proj.estudo_mercado, sub["01_Engenharia"], D._novo, D._tabela, D._bullets)
        log("   Estudo de ponto ótimo e robustez gerado (01_Engenharia)")
    except Exception as e:
        log(f"   (estudo de ponto ótimo não gerado: {type(e).__name__}: {e})")
    if getattr(proj, "estudo_opcoes", None):
        try:
            from . import opcoes_caps as OC
            arqs["estudo_opcoes"] = OC.gerar_docx(proj, cat, proj.estudo_opcoes, sub["01_Engenharia"], D._novo, D._tabela, D._bullets)
            log("   Estudo de opções – mínimo de capacitores gerado (01_Engenharia)")
        except Exception as e:
            log(f"   (estudo de opções não gerado: {type(e).__name__}: {e})")
    ets = D.et_fornecedores(proj, arr, orc, cat, sub["03_Fornecedores"], pdf_des)
    for k, (doc, mail) in ets.items():
        arqs[f"et_{k}"] = doc
        arqs[f"email_{k}"] = mail
    arqs["rfq_montagem"], arqs["email_montagem"] = D.rfq_montagem(proj, arr, orc, cat, sub["04_Montadora"])
    arqs["caderno_montagem"] = D.caderno_montagem(proj, arr, orc, cat, sub["04_Montadora"], pngs)
    shutil.copy(pdf_des, sub["04_Montadora"])
    # relatório técnico final (padrão RTM da Electric) – resultados Python + ATP + limites dos componentes
    try:
        from . import relatorio_final as RF
        _da = getattr(proj, "dupla_checagem_atp", None) or {}
        _atp = [dict(ponto=x["ponto"], tabela=x["tabela"]) for x in (_da.get("resultados") or [])] or None
        arqs["relatorio_final"] = RF.gerar(proj, {"arranjo": arr.to_dict()}, pasta, cat, atp=_atp,
                                           vistas_dir=os.path.join(sub["01_Engenharia"], "ATP"), log=log)
        log("   Relatório técnico final (RTM) gerado em 02_Cliente")
    except Exception as e:
        log(f"   (relatório técnico final não gerado: {type(e).__name__}: {e})")
    # resposta ao cliente
    email_cli = _email_cliente(proj, orc, cat)
    with open(os.path.join(sub["02_Cliente"], "Email_Resposta_Cliente.txt"), "w", encoding="utf-8") as f:
        f.write(email_cli)
    arqs["email_cliente"] = os.path.join(sub["02_Cliente"], "Email_Resposta_Cliente.txt")
    if getattr(proj, "dados_faltantes", None) and proj.dados_faltantes["itens"]:
        from . import dados_faltantes as DF
        txt = DF.email_cliente(proj.dados_faltantes, proj, cat)
        arqs["email_dados"] = os.path.join(sub["02_Cliente"], "Email_Solicitacao_Dados_Tecnicos.txt")
        with open(arqs["email_dados"], "w", encoding="utf-8") as f:
            f.write(txt)
        arqs["questionario"] = DF.questionario_docx(proj.dados_faltantes, proj, cat,
                                                    os.path.join(sub["02_Cliente"], f"{cod}_Questionario_Tecnico.docx"))
        arqs["sensibilidade"] = DF.salvar_sensibilidade(proj.dados_faltantes,
                                                        os.path.join(sub["01_Engenharia"], f"{cod}_Sensibilidade_Dados_Faltantes.xlsx"))
    # dados brutos
    ped.salvar(os.path.join(pasta, "pedido.json"))
    proj.salvar(os.path.join(sub["01_Engenharia"], "projeto.json"))
    with open(os.path.join(sub["01_Engenharia"], "arranjo_orcamento.json"), "w", encoding="utf-8") as f:
        json.dump({"arranjo": arr.to_dict(), "orcamento": orc.to_dict(), "similares": similares}, f, ensure_ascii=False, indent=2,
                  default=_json_default)
    resumo = resumo_texto(proj, arr, orc, similares, pasta)
    with open(os.path.join(pasta, "RESUMO.md"), "w", encoding="utf-8") as f:
        f.write(resumo)
    from .versao import carimbar_pasta
    carimbar_pasta(pasta, log)
    log("7/7 Registrando no histórico...")
    if registrar:
        H.registrar_projeto(proj, arr, orc, pasta)
    z = None
    if zipar:
        z = shutil.make_archive(pasta, "zip", pasta)
    log(f"Concluído em {(_dt.datetime.now() - t0).total_seconds():.1f} s → {pasta}")
    _op = None
    if getattr(proj, "estudo_opcoes", None):
        from . import opcoes_caps as OC
        _op = OC.tabela_ui(proj.estudo_opcoes)
    return dict(projeto=proj, arranjo=arr, orcamento=orc, pasta=pasta, zip=z, arquivos=arqs, graficos=graf, resumo=resumo,
                similares=similares, opcoes=_op)


def _atp_dupla_checagem(proj, cat, pasta_eng, cod, log):
    """Gera os decks .atp; se o ATP estiver instalado neste PC, roda em segundo plano e compara com o Python.
    SEMPRE registra o que aconteceu (rodou/convergiu, não instalado, falhou) em proj.dupla_checagem_atp e ATP/status_atp.json."""
    import time as _time
    from . import atp as A
    cfg = cat.get("atp", {})
    pasta_atp = os.path.join(pasta_eng, "ATP")
    st = dict(status="desabilitado", msg="Dupla checagem ATP desabilitada no catálogo (atp: habilitado: false).",
              hora=_dt.datetime.now().strftime("%d/%m/%Y %H:%M:%S"))
    proj.dupla_checagem_atp = st
    if not cfg.get("habilitado", True):
        return _salvar_status_atp(pasta_atp, st)
    t0 = _time.time()
    try:
        tp = A.achar_tpbig(cat)
        trab = os.path.join(cfg.get("pasta_trabalho", A.PASTA_TRABALHO_PADRAO), cod) if tp else pasta_atp
        casos = A.preparar_casos(proj, cat, trab)
        st.update(casos=[dict(nome=c["nome"], ponto=c["ponto"]) for c in casos], tpbig=tp,
                  atpdraw=[os.path.basename(c["atpdraw"]) for c in casos if c.get("atpdraw")])
        if not tp:
            if trab != pasta_atp:
                shutil.copytree(trab, pasta_atp, dirs_exist_ok=True)
            st.update(status="nao_instalado", msg="ATP (tpbig.exe) não encontrado neste computador – só os decks .atp foram gerados.")
            log("   ATP não encontrado neste computador – decks .atp gerados para rodar depois")
            st["vistas"] = _vistas(proj, casos, None, None, pasta_atp, log)
            return _salvar_status_atp(pasta_atp, st)
        log("   ATP: rodando a dupla checagem em segundo plano...")
        for c in casos:
            r = A.rodar_atp(os.path.join(trab, c["nome"] + ".atp"), tp)
            if not r["ok"]:
                st.update(status="falhou", msg=f"ATP falhou em {c['ponto']}: {r['msg'][-300:]}")
                log("   " + st["msg"])
                return _salvar_status_atp(pasta_atp, st)
        res = A.comparar_casos(casos, trab)
        os.makedirs(pasta_atp, exist_ok=True)
        A.salvar_relatorio(res, os.path.join(pasta_atp, f"{cod}_Comparacao_Python_x_ATP.xlsx"))
        pngs = [A.grafico_comparacao(c, trab, os.path.join(pasta_atp, f"comparacao_{c['nome']}.png")) for c in casos]
        for f in os.listdir(trab):
            if f.endswith((".atp", ".lis", ".bat", ".pl4", ".xml")):
                shutil.copy(os.path.join(trab, f), pasta_atp)
        conv = all(l["convergiu"] for x in res for l in x["tabela"])
        div = [f"{x['ponto'].replace('Operação ', '')}: {l['grandeza']} (Py {l['python']:g} × ATP {l['atp']:g} {l['unidade']}, {l['dif_pct']:+.0f} %)"
               for x in res for l in x["tabela"] if not l["convergiu"]]
        st.update(status="rodou", convergiu=conv, segundos=round(_time.time() - t0, 1), divergencias=div,
                  msg=("ATP rodou e CONVERGIU com o Python em todos os pontos" if conv else
                       "ATP rodou e há DIVERGÊNCIA com o Python em " + "; ".join(div[:3])),
                  resultados=[dict(ponto=x["ponto"], tabela=x["tabela"]) for x in res], graficos=pngs,
                  vistas=_vistas(proj, casos, res, trab, pasta_atp, log))
        proj.dupla_checagem_atp = dict(st, resultados=res)
        log(f"   ATP × Python: {'CONVERGIU' if conv else 'DIVERGÊNCIA – revisar'}")
        try:
            st["mat_python"] = [os.path.basename(x) for x in A.exportar_python_mat(casos, pasta_atp)]
        except Exception as e:
            log(f"   (.mat do Python para o PlotXY não gerado: {e})")
        if cfg.get("abrir_ao_terminar", False) and os.name == "nt":
            ab = A.abrir_no_windows(pasta_atp, casos[0]["nome"], cat)
            st["aberto"] = ab
            log(f"   Abrindo no PlotXY: {ab['plotxy'] or '-'} | ATPDraw: {ab['atpdraw'] or '-'}")
    except Exception as e:  # a dupla checagem nunca bloqueia a emissão
        st.update(status="falhou", msg=f"Dupla checagem não concluída: {type(e).__name__}: {e}")
        log(f"   ATP: dupla checagem não concluída ({e})")
    return _salvar_status_atp(pasta_atp, st)


def _vistas(proj, casos, res, pasta_pl4, pasta_atp, log):
    """Rede elétrica com os valores dos dois programas, ondas lado a lado e espectro Python × ATP (um conjunto por ponto)."""
    try:
        from .vista_simulacao import gerar_vistas
        v = gerar_vistas(proj, casos, res, pasta_pl4, pasta_atp)
        return [{k: (os.path.basename(x) if k != "ponto" else x) for k, x in d.items()} for d in v]
    except Exception as e:
        log(f"   (vistas Python × ATP não geradas: {e})")
        return []


def _salvar_status_atp(pasta_atp, st):
    try:
        os.makedirs(pasta_atp, exist_ok=True)
        with open(os.path.join(pasta_atp, "status_atp.json"), "w", encoding="utf-8") as f:
            json.dump({k: v for k, v in st.items() if k != "resultados" or isinstance(v, list)}, f, ensure_ascii=False, indent=1,
                      default=str)
    except Exception:
        pass


def texto_atp(st):
    """Bloco do RESUMO com o resultado do ATP (sempre aparece, mesmo quando o ATP não rodou)."""
    if not st:
        return ["## Dupla checagem no ATP", "- ⚠️ sem registro (projeto gerado por versão antiga)", ""]
    ic = {"rodou": "✅" if st.get("convergiu") else "❌", "nao_instalado": "⚠️", "falhou": "❌", "desabilitado": "⚠️"}.get(st["status"], "⚠️")
    L = ["## Dupla checagem no ATP", f"- {ic} {st['msg']} ({st.get('hora', '')}"
         + (f", {st['segundos']} s" if st.get("segundos") else "") + ")"]
    if st.get("tpbig"):
        L.append(f"- Programa: `{st['tpbig']}`")
    for x in st.get("resultados") or []:
        L.append(f"- **{x['ponto']}** – Python × ATP:")
        for l in x["tabela"]:
            L.append(f"  - {'✅' if l['convergiu'] else '❌'} {l['grandeza']}: Python {l['python']:g} | ATP {l['atp']:g} {l['unidade']} "
                     f"(dif. {l['dif_pct']:+.1f} %, tolerância ±{l['tolerancia_pct']:g} %)")
    L.append("")
    return L


def _email_cliente(proj, orc, cat):
    ped = proj.pedido
    emp = cat["empresa"]
    com = cat["comercial"]
    rs = lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return (f"Para: {ped.get('email_contato') or ''}\nAssunto: RE: {ped.get('referencia') or 'Cotação filtro senoidal'} – Proposta {proj_codigo(proj)}\n\n"
            f"Olá {(ped.get('contato') or '').split(' ')[0]},\n\n"
            f"Segue nossa proposta para {orc.quantidade} filtro(s) senoidal(is) {proj.topologia} {ped['corrente_a']:g} A / {ped['tensao_v']:g} V, "
            f"dimensionado(s) e simulado(s) para a aplicação informada ({ped.get('inversor')}, motor {ped.get('motor_cv') or ''} cv):\n\n"
            f"- Preço unitário: {rs(orc.preco_unit)} (impostos inclusos)\n- Total: {rs(orc.preco_total)}\n"
            f"- NCM: {com['ncm_sugerido']} | Frete: FOB Porto Alegre/RS | Prazo: {com['prazo_entrega']}\n"
            f"- Validade: {com['validade_dias']} dias | Pagamento: {com['pagamento']} | Garantia: {com['garantia']}\n\n"
            f"Atendimento técnico: Vpico {max(p['vpk_saida'] for p in proj.pontos):.0f} V (≤ {ped.get('vpk_max_v') or '-'} V), "
            f"dv/dt {max(p['dvdt_saida_v_us'] for p in proj.pontos):.1f} V/µs (≤ {ped.get('dvdt_max_v_us') or '-'} V/µs), "
            f"THD de tensão {max(p['thd_v_saida_pct'] for p in proj.pontos):.1f} %, isolação 1,1 kV, classe F.\n"
            f"Importante: o inversor deve operar com frequência de chaveamento fixa de {proj.fs_hz / 1000:g} kHz.\n\n"
            "Anexos: proposta, folha de dados, memorial de cálculo e desenho dimensional.\n\n"
            f"Atenciosamente,\n{emp['responsavel']}\n{emp['nome']}\n{emp['email']} | {emp['telefone']}\n")


def resumo_texto(proj, arr, orc, similares, pasta):
    ped = proj.pedido
    b = proj.banco
    am = proj.amortecimento
    rs = lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    from .versao import assinatura
    lin = [f"# {proj_codigo(proj)} – {ped['cliente']}", "", f"*{assinatura()}*", "",
           f"**Status:** {'✅ APROVADO' if proj.aprovado else '❌ REPROVADO'}  |  {ped['quantidade']} pç  |  fs fixa {proj.fs_hz / 1000:g} kHz", "",
           "## Solução", f"- L1 = **{proj.l1.l_uh:.0f} µH/fase** (uk {proj.l1.uk_pct:.1f} %), {proj.l1.i_nom_a:.0f} A, Isat ≥ {proj.l1.i_sat_a:.0f} A",
           f"- Capacitores: **{b.n_total} × {b.uf_unit:g} µF {b.v_unit:g} V** ({b.fabricante}) em **{b.ligacao}**, {b.n_por_ramo}/ramo → {b.c_y_uf:g} µF Y",
           f"- fr = **{proj.fr_hz:.0f} Hz**" + (f"; amortecimento {am.r_ramo_ohm:.3f} Ω / {am.p_nominal_w:g} W por ramo" if am else "; sem resistor de amortecimento"),
           f"- Caixa {arr.caixa_id}, perdas {arr.perda_total_w:.0f} W, {arr.n_ventiladores} ventiladores, massa ≈ {arr.massa_total_kg:.0f} kg", "",
           "## Verificações"] + [f"- {'✅' if v.ok else ('❌' if v.critico else '⚠️')} {v.item}: {v.valor} (limite {v.limite})" for v in proj.verificacoes] + [
           ""] + texto_atp(getattr(proj, "dupla_checagem_atp", None)) + ["## Comercial", f"- Custo por filtro: {rs(orc.custo_unit_total)}  (material {rs(orc.custo_material)} + montagem {rs(orc.custo_montagem)})",
           f"- Preço unitário: **{rs(orc.preco_unit)}** | total {rs(orc.preco_total)} (impostos {orc.impostos_pct:g} %, margem {orc.margem_pct:g} %)", ""]
    if proj.avisos:
        lin += ["## Avisos"] + [f"- {a}" for a in proj.avisos] + [""]
    if ped.get("lacunas"):
        lin += ["## Premissas (dados que faltaram no pedido)"] + [f"- {a}" for a in ped["lacunas"]] + [""]
    df_ = getattr(proj, "dados_faltantes", None)
    if df_ and df_["itens"]:
        lin += [f"## Dados a confirmar com o cliente ({df_['n_criticos']} críticos) – ver 02_Cliente/Email_Solicitacao_Dados_Tecnicos.txt"]
        for it in df_["itens"]:
            rep = [c["cenario"] for c in it.get("cenarios", []) if not c["aprovado"]]
            lin.append(f"- **{it['prioridade']}** {it['pergunta']}" + (f" – reprova com: {', '.join(rep)}" if rep else ""))
        lin.append("")
    if similares:
        lin += ["## Projetos anteriores semelhantes"] + [
            f"- {s.get('cliente')} – {s.get('corrente_a')} A {s.get('tensao_v') or ''} V {s.get('topologia') or ''} ({s.get('fonte')})" for s in similares] + [""]
    lin += ["## Pastas", "- 01_Engenharia: memorial de cálculo, planilha BOM/custos/preço, projeto.json",
            "- 02_Cliente: proposta, folha de dados, e-mail de resposta",
            "- 03_Fornecedores: ET + e-mail por fornecedor (indutor, capacitores, resistores, caixa, cabos/misc.)",
            "- 04_Montadora: RFQ de montagem, caderno de montagem, desenhos, e-mail",
            "- 05_Desenhos: PDF A3 (vistas, cortes, 3D, diagrama, cabos)"]
    return "\n".join(lin)
