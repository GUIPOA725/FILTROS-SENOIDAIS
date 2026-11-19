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
    n = re.sub(r"\s+", " ", n).strip(" .-_")
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
              ligacoes=None):
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
    ets = D.et_fornecedores(proj, arr, orc, cat, sub["03_Fornecedores"], pdf_des)
    for k, (doc, mail) in ets.items():
        arqs[f"et_{k}"] = doc
        arqs[f"email_{k}"] = mail
    arqs["rfq_montagem"], arqs["email_montagem"] = D.rfq_montagem(proj, arr, orc, cat, sub["04_Montadora"])
    arqs["caderno_montagem"] = D.caderno_montagem(proj, arr, orc, cat, sub["04_Montadora"], pngs)
    shutil.copy(pdf_des, sub["04_Montadora"])
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
    return dict(projeto=proj, arranjo=arr, orcamento=orc, pasta=pasta, zip=z, arquivos=arqs, graficos=graf, resumo=resumo,
                similares=similares)


def _atp_dupla_checagem(proj, cat, pasta_eng, cod, log):
    """Gera os decks .atp; se o ATP estiver instalado neste PC, roda em segundo plano e compara com o Python."""
    from . import atp as A
    cfg = cat.get("atp", {})
    if not cfg.get("habilitado", True):
        return
    pasta_atp = os.path.join(pasta_eng, "ATP")
    try:
        tp = A.achar_tpbig(cat)
        # o tpbig não lida bem com espaços no caminho: roda em pasta de trabalho local e copia os resultados
        trab = os.path.join(cfg.get("pasta_trabalho", A.PASTA_TRABALHO_PADRAO), cod) if tp else pasta_atp
        casos = A.preparar_casos(proj, cat, trab)
        if not tp:
            if trab != pasta_atp:
                shutil.copytree(trab, pasta_atp, dirs_exist_ok=True)
            log("   ATP não encontrado neste computador – decks .atp gerados para rodar depois")
            return
        log("   ATP: rodando a dupla checagem em segundo plano...")
        for c in casos:
            r = A.rodar_atp(os.path.join(trab, c["nome"] + ".atp"), tp)
            if not r["ok"]:
                log(f"   ATP falhou em {c['ponto']}: {r['msg'][-300:]}")
                return
        res = A.comparar_casos(casos, trab)
        os.makedirs(pasta_atp, exist_ok=True)
        A.salvar_relatorio(res, os.path.join(pasta_atp, f"{cod}_Comparacao_Python_x_ATP.xlsx"))
        pngs = [A.grafico_comparacao(c, trab, os.path.join(pasta_atp, f"comparacao_{c['nome']}.png")) for c in casos]
        for f in os.listdir(trab):
            if f.endswith((".atp", ".lis", ".bat")):
                shutil.copy(os.path.join(trab, f), pasta_atp)
        conv = all(l["convergiu"] for x in res for l in x["tabela"])
        proj.dupla_checagem_atp = dict(convergiu=conv, resultados=res, graficos=pngs)
        log(f"   ATP × Python: {'CONVERGIU' if conv else 'DIVERGÊNCIA – revisar'}")
    except Exception as e:  # a dupla checagem nunca bloqueia a emissão
        log(f"   ATP: dupla checagem não concluída ({e})")


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
           "", "## Comercial", f"- Custo por filtro: {rs(orc.custo_unit_total)}  (material {rs(orc.custo_material)} + montagem {rs(orc.custo_montagem)})",
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
