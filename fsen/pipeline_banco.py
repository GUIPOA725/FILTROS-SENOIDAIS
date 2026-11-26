"""Fluxo completo de BANCO DESSINTONIZADO / FILTRO SINTONIZADO (v1.13.0):
pedido → cálculo elétrico dos estágios → varredura de ressonância → reator(es) por elementos finitos (mesmo motor do
filtro senoidal) → verificação independente + análise avançada → desenhos/CAD → memorial → ET reator/capacitores → e-mails.

Estrutura de pastas igual à do filtro senoidal:
  01_Engenharia/ (memorial, JSON, figuras; 3_Reator_<n>_Elementos_Finitos/)  03_Fornecedores/1_Reator_<n>/, 2_Capacitores/
  05_Desenhos/2_Reator_<n>/
"""
import datetime as _dt
import json
import math
import os
import re
import shutil

from . import banco as B
from . import doc_banco as DB
from .dimensionamento import carregar_catalogo, _json_default

FORN_REATOR = [("COOTRANS", "Diadema – SP – Brasil"), ("IBT – Indústria Brasileira de Transformadores", "São Bernardo do Campo – SP – Brasil"),
               ("WISE Transformadores", "Jaraguá do Sul – SC – Brasil")]


def processar_banco(ped: B.PedidoBanco, pasta_base, cat=None, log=print, verificar_ind=True, zipar=True, n_bancos=1):
    from .pipeline import pasta_cliente, _achar_pasta_cliente
    from . import ind_projeto as IP
    from .versao import info as _vi, carimbar_pasta
    t0 = _dt.datetime.now()
    cat = cat or carregar_catalogo()
    cod = DB.codigo(ped)
    versao = f"FSEN v{_vi().get('versao')}"
    pasta_cli = os.path.join(pasta_base, _achar_pasta_cliente(pasta_base, ped.cliente) if ped.cliente else pasta_cliente(""))
    _mc = getattr(ped, "marca", "") or ""
    _suf = "" if _mc in ("", "Padrão Electric") else "_" + re.sub(r"[^A-Za-z0-9]+", "", _mc)
    pasta = os.path.join(pasta_cli, f"{cod}{_suf}_{t0:%Y%m%d_%H%M}")
    sub = {k: os.path.join(pasta, k) for k in ("01_Engenharia", "02_Cliente", "03_Fornecedores", "04_Montadora", "05_Desenhos")}
    for p in sub.values():
        os.makedirs(p, exist_ok=True)
    arqs = {}
    log(f"1/5 {DB.titulo_tipo(ped)} – {sum(ped.estagios_kvar):g} kvar / {ped.tensao_v:g} V: cálculo dos estágios e ressonância...")
    res = B.dimensionar(ped, cat)
    for i, e in enumerate(res["estagios"]):
        log(f"   Estágio {i+1} ({e['codigo']}): capacitor {e['cap'][0]}×{e['cap'][1]:g} kvar/{e['U_cap_nom']} V → {e['Q_kvar']:.1f} kvar efetivos, "
            f"Nr {e['nr']:.2f} (FD {e['p_pct']:.2f} %, {e['f_sintonia']:.0f} Hz), L {e['L_uH']:.0f} µH, I60 {e['I60']:.1f} A, "
            f"I projeto do reator {e['requisitos']['In']:.1f} A (k·I60 {e['requisitos']['I_electric']:.1f} / espectro {e['requisitos']['I_fisica']:.1f})")
    log("   Ressonância paralela na barra: " + (", ".join(f"{x:.2f}ª" for x in res["varredura"]["picos"]) or "nenhuma"))
    for a in res["avisos"]:
        log(f"   ⚠ {a}")
    grupos = B.reatores_distintos(res)
    inds = []
    log(f"2/5 Reator(es): {len(grupos)} projeto(s) distinto(s) por elementos finitos...")
    for gi, grp in enumerate(grupos):
        e = res["estagios"][grp[0]]
        nome = f"Reator_{gi+1}_{e['L_uH']:.0f}uH_{e['requisitos']['In']:.0f}A"
        eng = os.path.join(sub["01_Engenharia"], f"3_{nome}_Elementos_Finitos")
        forn = os.path.join(sub["03_Fornecedores"], f"1_{nome}")
        des = os.path.join(sub["05_Desenhos"], f"2_{nome}")
        for p in (eng, forn, des):
            os.makedirs(p, exist_ok=True)
        d = None
        _usar_bib = None
        try:                                            # v1.26.3 (REQ-REA-014): reator PADRÃO aprovado na biblioteca → não reprojeta
            from . import biblioteca_reatores as _BR
            _dl, _reg, _lin = _BR.buscar(ped, e)
            if _dl:
                _usar_bib = (_dl, _reg, _lin)
                log(f"   {nome}: usando o reator PADRÃO da biblioteca ({os.path.basename(_reg['_arquivo'])}, aprovado por "
                    f"{_reg.get('aprovado_por')}) – {_reg['massa_kg']:.0f} kg; cobre as {len(_lin)} grandezas deste caso")
            else:
                log(f"   {nome}: biblioteca de reatores – {_lin}; projetando")
        except Exception as _exb:
            log(f"   (biblioteca de reatores não consultada: {type(_exb).__name__}: {_exb})")
        try:
            log(f"   {nome}: estágio(s) {', '.join(str(i+1) for i in grp)}")
            if _usar_bib:
                d = _usar_bib[0]
                d["_biblioteca"] = dict(arquivo=os.path.basename(_usar_bib[1]["_arquivo"]), linhas=_usar_bib[2], reg={k: v for k, v in _usar_bib[1].items() if k != "projeto"})
                d["aplicacao"] = e["requisitos"]["aplicacao"]
                arqs.update(_docs_reator(d, e, ped, nome, cod, eng, forn, des, versao, verificar_ind, log))
                _teto_perdas(d, [res["estagios"][i] for i in grp], log)
                inds.append(d)
                continue
            # sintonizado: enrolamento em CHAPA (folha) – padrão Electric "chapa ou barra de alumínio"; a corrente harmônica alta
            # (1,1·I1 na 5ª) torna a barra única pesada (pelicular/proximidade) – a folha resolve
            if ped.tipo == "sintonizado":
                ordem = [("distribuido", ped.condutor), ("culatra_fio", "barra_al" if ped.condutor == "AL" else "barra_cu"),
                         ("culatra_fio", "livre")]
            else:
                ordem = [("culatra_fio", c) for c in (["barra_al", "livre", "barra_cu"] if ped.condutor == "AL" else ["barra_cu", "livre"])]
            nomes = {"barra_al": "barra de alumínio", "barra_cu": "barra de cobre", "livre": "fio/barra Al ou Cu, até 6 em paralelo",
                     "AL": "chapa (folha) de alumínio", "CU": "chapa (folha) de cobre"}
            for k_, (cons, cnd) in enumerate(ordem):
                try:
                    if cons == "distribuido":
                        d = IP.projetar_requisitos(e["requisitos"], e["espectro"], cat, log=log, construcao=cons, cond_id=cnd)
                    else:
                        d = IP.projetar_requisitos(e["requisitos"], e["espectro"], cat, log=log, construcao=cons, condutor=cnd)
                    log(f"   Reator: enrolamento em {nomes[cnd]}" + (" (opção anterior sem solução)" if k_ else ""))
                    break
                except RuntimeError as ex:
                    if k_ == len(ordem) - 1:
                        raise
                    log(f"   ({nomes[cnd]}: {ex} – tentando a próxima opção)")
            if verificar_ind:                           # v1.26.4 (REQ-GER-014): fecha a térmica com a análise avançada ANTES dos documentos
                def _refazer(alvo, _cons=cons, _cnd=cnd):
                    IP.ALVO_ELEV_EXT = alvo
                    try:
                        if _cons == "distribuido":
                            return IP.projetar_requisitos(e["requisitos"], e["espectro"], cat, log=lambda *_a: None, construcao=_cons, cond_id=_cnd)
                        return IP.projetar_requisitos(e["requisitos"], e["espectro"], cat, log=lambda *_a: None, construcao=_cons, condutor=_cnd)
                    finally:
                        IP.ALVO_ELEV_EXT = None
                d = _fechar_termica(d, lambda dd: B.wf_de_espectro(ped.freq_hz, dd["requisitos"]["I1"], dd["requisitos"]["Ih_termico"]),
                                    _refazer, log)
            d["aplicacao"] = e["requisitos"]["aplicacao"]
            arqs.update(_docs_reator(d, e, ped, nome, cod, eng, forn, des, versao, verificar_ind, log))
            _teto_perdas(d, [res["estagios"][i] for i in grp], log)
            try:                                        # todo reator projetado fica salvo como proposta (A_CONFERIR) – a biblioteca cresce
                _arq_b = _BR.propor(ped, e, d, projeto=cod, pasta=pasta)
                log(f"   Reator salvo na biblioteca de reatores como proposta (aguarda aprovação do engenheiro): {os.path.basename(_arq_b)}")
            except Exception as _exb:
                log(f"   (reator não salvo na biblioteca: {type(_exb).__name__}: {_exb})")
        except Exception as ex:
            log(f"   ({nome}: projeto não concluído – {type(ex).__name__}: {ex})")
        inds.append(d)
    log("3/5 Memorial de cálculo...")
    figs = DB.figuras(ped, res, sub["01_Engenharia"], cod)
    arqs["memorial"] = DB.memorial(ped, res, grupos, inds, os.path.join(sub["01_Engenharia"], f"{cod}_Memorial_de_Calculo.pdf"), figs, versao)
    shutil.copy(arqs["memorial"], os.path.join(sub["02_Cliente"], os.path.basename(arqs["memorial"])))
    trans = None
    try:                                            # v1.20.0: transitórios eletromagnéticos (energização, back-to-back, abertura…)
        from . import transitorios as TR
        log("3b/5 Transitórios eletromagnéticos (mesmo método do ATP) e dupla checagem no ATP...")
        trans = TR.gerar(ped, res, os.path.join(sub["01_Engenharia"], "4_Transitorios"), cod, log=log)
        arqs["transitorios_xlsx"] = trans["arquivos"][-1]
        e_ = trans["estudo"]
        log(f"   Estágios que podem ligar juntos: {e_['max_simultaneos']} | bloqueio de religamento ≥ "
            f"{math.ceil(e_['t_religar_s'] / 10) * 10:.0f} s | {e_['contatora']['texto'][:90]}…")
    except Exception as ex:
        log(f"   (transitórios não calculados: {type(ex).__name__}: {ex})")
    try:                                            # v1.24.0: gabinete com as medidas reais do reator (FEM)
        _dims = [d.get("dims_mm") for d in inds if d and d.get("dims_mm")]
        if _dims:
            res["reator_mm"] = max(_dims, key=lambda x: x.get("largura", 0) * x.get("altura", 0))
    except Exception:
        pass
    try:                                            # v1.25.2: distâncias de montagem do reator pelo campo FEM (REQ-REA-010)
        from . import reator_montagem as _RMt
        _d0 = next((d for d in inds if d), None)
        if _d0:
            res["reator_montagem"] = _RMt.especificacao(_d0)
            _dm = res["reator_montagem"]["dmin_mm"]
            log(f"   Montagem do reator (campo FEM): aço ≥ {_dm['aco']} mm, entre reatores ≥ {_dm['entre_reatores']} mm, cabos de força ≥ "
                f"{_dm['forca']} mm, comando ≥ {_dm['comando']} mm, porta/pessoas ≥ {_dm['pessoas']} mm")
    except Exception as _ex:
        log(f"   (campo externo do reator não calculado: {type(_ex).__name__}: {_ex})")
    try:                                            # v1.25.2: gabinete FINAL = o que cabe o arranjo real (fonte única p/ lista, normas, 3D)
        from . import painel3d as _P3f, painel_gabinete as _PGf
        _gf, _mf = _P3f.gabinete_final(ped, res, _PGf.gabinete(ped, res), B.protecao_pior(ped, res), inds)
        res["_gab_final"] = _gf
        log(f"   Gabinete final: {_gf['dimensoes_mm']['largura']} × {_gf['dimensoes_mm']['altura']} × {_gf['dimensoes_mm']['profundidade']} mm, "
            f"{len(_gf['colunas'])} coluna(s)")
    except Exception as _ex:
        log(f"   (gabinete final não calculado: {type(_ex).__name__}: {_ex})")
    log("4/5 Especificações e e-mails aos fornecedores...")
    for gi, (grp, d) in enumerate(zip(grupos, inds)):
        e = res["estagios"][grp[0]]
        nome = f"Reator_{gi+1}_{e['L_uH']:.0f}uH_{e['requisitos']['In']:.0f}A"
        forn = os.path.join(sub["03_Fornecedores"], f"1_{nome}")
        eng = os.path.join(sub["01_Engenharia"], f"3_{nome}_Elementos_Finitos")
        arqs[f"estagio_{gi+1}"] = DB.planilha_estagio(ped, e, os.path.join(sub["01_Engenharia"], f"ESTAGIO {e['Q_alvo']:g}KVAR {ped.tensao_v:g}V "
                                                      + (f"H{e['ordem']:g} Nr{e['nr']:.2f}" if ped.tipo == "sintonizado" else f"FD{e['p_pct']:.2f}%".replace(".", ","))
                                                      + f" - {e['codigo']}.xlsx"))
        for fn, loc in FORN_REATOR:
            arqs[f"esp_reator_{gi+1}_{fn}"] = DB.esp_reator(ped, res, grp, d, forn, cod, cat, fornecedor=fn, local=loc, n_banco=n_bancos,
                                                           mono=ped.monofasico)
        anexos = [os.path.join(forn, f) for f in sorted(os.listdir(forn)) if not f.startswith("Email_")]
        for fn, _ in FORN_REATOR:
            nm = fn.split()[0].title()
            ax = [a for a in anexos if not re.search(r"_(Cootrans|Ibt|Wise)\.docx$", a) or a.endswith(f"_{nm}.docx")]
            with open(os.path.join(forn, f"Email_Reator_{nm}.txt"), "w", encoding="utf-8") as fh:
                fh.write(DB.email_fornecedor(fn, ped, res, [grp], ax, cod))
    if ped.tipo == "sintonizado":                   # v1.31.0 (REQ-DOC-020): no sintonizado a Electric fornece reator + capacitor
        try:
            arqs["et_capacitores"], arqs["email_capacitores"] = DB.et_capacitor_sintonizado(
                ped, res, os.path.join(sub["03_Fornecedores"], "2_Capacitores"), cod, cat, n_bancos)
            log("   Capacitores do filtro sintonizado: ET (Word) + e-mail em 03_Fornecedores/2_Capacitores")
        except Exception as _exc:
            log(f"   (ET dos capacitores do sintonizado não gerada: {type(_exc).__name__}: {_exc})")
    # v1.31.0 (REQ-DOC-020): a montadora NÃO é fornecedor – pacote de cotação da montagem em 04_Montadora
    pnl = os.path.join(sub["04_Montadora"], "1_Cotacao_Montagem")
    os.makedirs(pnl, exist_ok=True)
    arqs["et_painel"], arqs["et_painel_xlsx"] = DB.et_painel(ped, res, pnl, cod, cat, n_bancos)
    # v1.15.0: esquema elétrico estilo EPLAN (força, comando, bornes, cabos, lista de material) em PDF + DXF + XLSX
    anexos_pnl = [arqs["et_painel"], arqs["et_painel_xlsx"]]
    try:
        from .eplan import banco_qet as BQ      # v1.16.0: padrão AGCO/EPLAN no modelo do QElectroTech
        desq = os.path.join(sub["05_Desenhos"], "1_Esquema_Eletrico")
        os.makedirs(desq, exist_ok=True)
        try:
            esq = BQ.gerar(ped, res, desq, cod, versao, n_bancos, log=log)
        except Exception as ex_q:
            log(f"   (esquema QET falhou: {type(ex_q).__name__}: {ex_q} – usando o esquema 1.15)")
            from .eplan import banco_eletrico as BE
            esq = BE.gerar(ped, res, desq, cod, versao, n_bancos, log=log)
        for k_ in ("pdf", "dxf", "xlsx", "qet", "etq_xlsx", "etq_pdf"):
            if not esq.get(k_):
                continue
            arqs[f"esquema_{k_}"] = esq[k_]
            shutil.copy(esq[k_], pnl)
            anexos_pnl.append(os.path.join(pnl, os.path.basename(esq[k_])))
    except Exception as ex:
        log(f"   (esquema elétrico não gerado: {type(ex).__name__}: {ex})")
    # v1.17.0: layout do gabinete (capacitores na frente, reatores atrás) + plaquetas + material do gabinete
    try:
        from . import painel_desenho as PDES
        dlay = os.path.join(sub["05_Desenhos"], "3_Layout_Painel")
        lay = PDES.gerar(ped, res, dlay, cod, versao, log=log)
        for k_ in ("pdf", "dxf"):
            arqs[f"layout_{k_}"] = lay[k_]
            shutil.copy(lay[k_], pnl)
            anexos_pnl.append(os.path.join(pnl, os.path.basename(lay[k_])))
    except Exception as ex:
        log(f"   (layout do painel não gerado: {type(ex).__name__}: {ex})")
    try:                                            # v1.25.0: lista de material COMPLETA (até parafuso/terminal/torque) por marca
        from . import lista_material as LMC
        from . import painel_gabinete as _PG
        _L = LMC.montar(ped, res, _PG.gabinete(ped, res), B.protecao_pior(ped, res))
        arqs["lista_completa"] = LMC.planilha(_L, os.path.join(pnl, f"Lista_Material_Completa_{cod}.xlsx"), ped, cod, versao)
        log(f"   Lista de material completa: {len(_L)} itens ({sum(1 for r in _L if 'CONFERIR' in str(r[7]))} a conferir no catálogo)")
    except Exception as ex:
        log(f"   (lista de material completa não gerada: {type(ex).__name__}: {ex})")
    try:                                            # v1.24.0: painel 3D com medidas reais (catálogo + reator FEM) e check
        from . import painel3d as P3
        from . import painel_gabinete as PG
        p3 = P3.gerar(ped, res, PG.gabinete(ped, res), B.protecao_pior(ped, res), inds,
                      os.path.join(sub["05_Desenhos"], "4_Painel_3D"), cod, versao, log=log)
        arqs["painel3d"] = p3["pdf"]
        shutil.copy(p3["pdf"], pnl)
        for _k in ("pdf", "dxf"):
            if (p3.get("d2") or {}).get(_k):
                arqs[f"painel2d_{_k}"] = p3["d2"][_k]
                shutil.copy(p3["d2"][_k], pnl)
        anexos_pnl.append(os.path.join(pnl, os.path.basename(p3["pdf"])))
    except Exception as ex:
        log(f"   (painel 3D não gerado: {type(ex).__name__}: {ex})")
        import traceback as _tb
        log("      " + _tb.format_exc().strip().splitlines()[-3])
    try:                                            # v1.25.1: conferência cruzada esquema × 2D/3D × lista (REQ-PNL-028)
        from . import conferencia_projeto as CPJ
        _dc = os.path.join(sub["01_Engenharia"], "6_Conferencia_Projeto")
        os.makedirs(_dc, exist_ok=True)
        _Lc = CPJ.conferir(pasta, res=res)
        arqs["conferencia"] = CPJ.planilha(_Lc, os.path.join(_dc, f"Conferencia_Esquema_x_Painel_x_Lista_{cod}.xlsx"))
        shutil.copy(arqs["conferencia"], pnl)
        res["conferencia"] = _Lc
        _nrep = sum(1 for r in _Lc if "REPROVADO" in str(r[3]))
        log(f"   Conferência esquema × 2D/3D × lista: {len(_Lc)} verificações, {_nrep} reprovada(s)")
    except Exception as ex:
        log(f"   (conferência cruzada não gerada: {type(ex).__name__}: {ex})")
    with open(os.path.join(pnl, "Email_Montadora.txt"), "w", encoding="utf-8") as fh:
        fh.write(DB.email_fornecedor("IFG", ped, res, grupos, anexos_pnl, cod, tipo="painel"))
    arqs["proposta"] = DB.proposta(ped, res, sub["02_Cliente"], cod, cat, inds, n_bancos)
    log("5/5 Dados e carimbo de versão...")
    try:                                            # v1.23.0: folha de dados + verificação IEC 61439/61921 com check
        from . import normas_banco as NB
        from . import painel_gabinete as PG
        _gab = PG.gabinete(ped, res)
        _prot = B.protecao_pior(ped, res)
        arqs["normas"], ver_iec = NB.gerar_pdf(ped, res, _gab, _prot, cod, os.path.join(sub["01_Engenharia"], "5_Normas_Folha_de_Dados"),
                                               trans=trans, inds=inds, versao=versao, log=log)
        shutil.copy(arqs["normas"], os.path.join(sub["02_Cliente"], os.path.basename(arqs["normas"])))
        try:                                        # v1.24.3: energia incidente IEEE 1584 + etiqueta (REQ-SEG-007/009, NR-10 10.4.12)
            from . import arco as AR
            _pn = os.path.join(sub["01_Engenharia"], "5_Normas_Folha_de_Dados")
            _ra = AR.cenarios(ped, NB._icc_barra_ka(ped), _gab)
            arqs["arco"] = AR.relatorio_pdf(os.path.join(_pn, f"Estudo_Energia_Incidente_{cod}.pdf"), ped, cod, _ra, versao)
            arqs["etiqueta_arco"] = AR.etiqueta_pdf(os.path.join(_pn, f"Etiqueta_Arco_Eletrico_{cod}.pdf"), ped, cod, _ra, versao)
            for _a in (arqs["arco"], arqs["etiqueta_arco"]):
                shutil.copy(_a, sub["02_Cliente"])
            shutil.copy(arqs["etiqueta_arco"], pnl)
            res["arco"] = _ra
            log(f"   Energia incidente: barramento {_ra['cenarios'][1]['E']:.1f} cal/cm² (sem disjuntor geral seria {_ra['sem_geral']['E']:.1f})")
        except Exception as _ex:
            log(f"   (energia incidente não calculada: {type(_ex).__name__}: {_ex})")
    except Exception as ex:
        ver_iec = None
        log(f"   (folha de dados / verificação IEC não gerada: {type(ex).__name__}: {ex})")
    ped_d = ped.__dict__.copy()
    with open(os.path.join(pasta, "pedido_banco.json"), "w", encoding="utf-8") as fh:
        json.dump(dict(tipo_filtro=ped.tipo, **ped_d), fh, ensure_ascii=False, indent=1, default=_json_default)
    res_s = {k: v for k, v in res.items() if k != "varredura"}
    res_s["varredura"] = dict(picos=res["varredura"]["picos"])
    with open(os.path.join(sub["01_Engenharia"], "banco_resultado.json"), "w", encoding="utf-8") as fh:
        json.dump(res_s, fh, ensure_ascii=False, indent=1, default=_json_default)
    with open(os.path.join(pasta, "RESUMO.md"), "w", encoding="utf-8") as fh:
        fh.write(resumo(ped, res, grupos, inds, cod))
        if trans:
            fh.write("\n" + trans["resumo"])
        if ver_iec:
            fh.write("\n".join(NB.verificacao_md(ver_iec)) + "\n")
        if res.get("reator_montagem"):
            _rm = res["reator_montagem"]
            fh.write("\n## Montagem do reator pelo campo magnético (FEM) – REQ-REA-010\n\n" + _rm["nota"] + "\n\n| Critério | B ef. máx. | Distância mínima |\n|---|---|---|\n")
            for k_, nm_ in (("aco", "Aço (prateleira, estrutura, placa, quadro do vizinho)"), ("entre_reatores", "Entre reatores"),
                            ("forca", "Cabos de força"), ("comando", "Cabos de comando/sinal"), ("pessoas", "Pessoas (porta) – ICNIRP 2010")):
                fh.write(f"| {nm_} | {_rm['criterios_mT'].get(k_, _rm['criterios_mT']['aco'])} mT | {_rm['dmin_mm'][k_]} mm |\n")
        if res.get("conferencia"):
            fh.write("\n## Conferência esquema elétrico × painel 2D/3D × lista de material (REQ-PNL-028)\n\n| Item | Esquema | Painel/Lista | Check | Obs. |\n|---|---|---|---|---|\n")
            for r in res["conferencia"]:
                fh.write("| " + " | ".join(str(x).replace("|", "/")[:160] for x in r) + " |\n")
    try:                                            # v1.26.4 (REQ-GER-014): status GERAL logo abaixo do título (todas as tabelas)
        from . import checagem as _CKg
        _arq_r = os.path.join(pasta, "RESUMO.md")
        _txt = open(_arq_r, encoding="utf-8").read()
        _lin = _txt.split("\n")
        _blk = _CKg.status_geral_md(_txt)
        open(_arq_r, "w", encoding="utf-8").write("\n".join(_lin[:1] + _blk + _lin[1:]))
        log("   " + _blk[3].replace("**", ""))
    except Exception as ex:
        log(f"   (status geral não gerado: {type(ex).__name__}: {ex})")
    try:                                            # v1.27.0 (REQ-GER-016): nível de maturidade + pasta de evidências
        from . import maturidade as _MAT
        _av = _MAT.iniciar(pasta, cod, DB.titulo_tipo(ped), ped.cliente or "", log)
        with open(os.path.join(pasta, "RESUMO.md"), "a", encoding="utf-8") as fh:
            fh.write("\n".join(_MAT.md(_av)) + "\n")
    except Exception as ex:
        log(f"   (maturidade do projeto não registrada: {type(ex).__name__}: {ex})")
    carimbar_pasta(pasta, log)
    try:                                            # v1.19.0: relatório consolidado (tudo num PDF só) na raiz do projeto
        from . import consolidado as CONS
        from . import painel_gabinete as PG
        try:
            gab = PG.gabinete(ped, res)
        except Exception:
            gab = None
        arqs["consolidado"] = CONS.gerar(pasta, cod, DB.titulo_tipo(ped) + f" – {sum(ped.estagios_kvar):g} kvar / {ped.tensao_v:g} V",
                                         versao, cliente=ped.cliente, projeto=ped.projeto, tipo=DB.titulo_tipo(ped),
                                         leitura=getattr(ped, "leitura", None) or {}, painel=gab, log=log)
    except Exception as ex:
        log(f"   (relatório consolidado não gerado: {type(ex).__name__}: {ex})")
    z = shutil.make_archive(pasta, "zip", pasta) if zipar else None
    log(f"Concluído em {(_dt.datetime.now() - t0).total_seconds():.0f} s → {pasta}")
    return dict(pasta=pasta, zip=z, arquivos=arqs, resultado=res, reatores=inds, grupos=grupos, figuras=figs, codigo=cod)


def _teto_perdas(d, estagios, log):
    """v1.26.4 (REQ-GER-014): o teto de perdas que vai na especificação do fabricante e na térmica do PAINEL nunca fica abaixo
    das perdas do pior método (+5 %); o teto de mercado original fica guardado para a comparação."""
    try:
        from .ind_avancado import final as _fin
        tf = _fin(d)
        for r in [d["requisitos"]] + [x["requisitos"] for x in estagios]:
            pm0 = float(r.get("P_max_mercado") or r.get("P_max") or 0)
            if not pm0:
                continue
            r["P_max_mercado"] = pm0
            r["P_max"] = max(pm0, math.ceil(1.05 * tf["perdas_W"] / 5.0) * 5.0)
        r = d["requisitos"]
        if r.get("P_max") and r["P_max"] > r["P_max_mercado"] + 0.5:
            log(f"   Reator: perdas do pior método {tf['perdas_W']:.0f} W acima do teto de mercado {r['P_max_mercado']:.0f} W → teto da "
                f"especificação e da térmica do painel passa a {r['P_max']:.0f} W")
    except Exception as ex:
        log(f"   (teto de perdas não atualizado: {type(ex).__name__}: {ex})")


def _fechar_termica(d, fazer_wf, refazer, log, max_it=3, proj=None, cat=None):
    """v1.26.4 (REQ-GER-014): roda a análise avançada (sem o 3D, ~1 min) sobre o projeto e, se o ponto quente do PIOR método
    não ficar MARGEM_TERMICA_K abaixo do limite, refaz o projeto com meta de elevação menor (até max_it vezes). Vale para o
    reator de banco/sintonizado (fazer_wf = espectro) e para o indutor do filtro senoidal (proj/cat = circuito)."""
    from . import ind_avancado as AV, ind_projeto as IP
    quieto = lambda *_a, **_k: None
    for it in range(max_it):
        try:
            av = AV.avaliar(d, proj, cat, log=quieto, fazer_3d=False, wf=(fazer_wf(d) if fazer_wf else None))
        except Exception as ex:
            log(f"   (fechamento térmico não concluído: {type(ex).__name__}: {ex})")
            return d
        tf = AV.adotar_pior(d, av)
        log(f"   Térmica (pior método): {tf['perdas_W']:.0f} W, ponto quente {tf['ponto_quente_C']:.0f} °C × limite {tf['limite_C']:.0f} °C "
            f"(folga {tf['margem_K']:.0f} K; mínimo {IP.MARGEM_TERMICA_K:.0f} K) – projeto {tf['projeto']['ponto_quente_C']:.0f} °C, "
            f"avançado {tf['avancado']['ponto_quente_C']:.0f} °C")
        if tf["margem_K"] >= IP.MARGEM_TERMICA_K or it == max_it - 1:
            break
        amb = tf["amb_C"]
        alvo = float(d["alvo"]) * (tf["limite_C"] - IP.MARGEM_TERMICA_K - 3.0 - amb) / max(tf["ponto_quente_C"] - amb, 1.0)
        alvo = min(alvo, float(d["termico"]["elev_bobina_K"]) * 0.92)          # tem que apertar de fato o projeto atual
        log(f"   → folga térmica insuficiente: refazendo o projeto com meta de elevação {alvo:.0f} K (era {d['alvo']:.0f} K)")
        try:
            d2 = refazer(alvo)
        except Exception as ex:
            log(f"   (sem solução com a meta {alvo:.0f} K: {type(ex).__name__}: {ex} – mantido o projeto anterior; status ficará pelo pior resultado)")
            break
        d2["fechamento_termico"] = list(d.get("fechamento_termico") or []) + [dict(meta_K=float(d["alvo"]), ponto_quente_C=tf["ponto_quente_C"],
                                                                                 perdas_W=tf["perdas_W"], massa_kg=float(d["massa_kg"]["total"]))]
        d = d2
    return d


def _docs_reator(d, e, ped, nome, cod, eng, forn, des, versao, verificar, log):
    """Desenhos, CAD, memorial FEM, planilha de calibração, script FEMM, verificação NGSolve e análise avançada do reator."""
    from . import ind_projeto as IP, ind_desenhos as IDS, auditoria as AUD
    arqs = {}
    r = d["requisitos"]
    ccod = f"{cod}_{nome.split('_')[0]}{nome.split('_')[1]}"
    # v1.26.2 (REQ-REL-009): banco/sintonizado – ao fabricante vai só a especificação de desempenho (03_Fornecedores); o projeto
    # detalhado (memorial, projeto de referência, CAD) fica INTERNO, para conferir a proposta
    forn = os.path.join(eng, "Projeto_interno_conferencia_NAO_ENVIAR")
    os.makedirs(forn, exist_ok=True)
    _inf = dict(titulo=f"Reator trifásico – {r['aplicacao']} – {r['L']*1e6:.0f} µH / {r['In']:.0f} A – {cod}",
                linha2=f"Classe {r['classe']} | {d['chapa_dados']['nome'][:48]} | {IP.descr_condutor(d, curto=True)}",
                cod=cod, data=f"{_dt.date.today():%d/%m/%Y}", versao=versao)
    try:
        IDS.imagens_campo(d, os.path.join(eng, "Indutor_campo_FEM.png"))
        arqs[f"{nome}_desenhos"] = IDS.gerar_pdf(d, os.path.join(forn, f"Projeto_Referencia_{nome}.pdf"), _inf, png_dir=eng)
        shutil.copy(arqs[f"{nome}_desenhos"], des)
    except Exception as ex:
        log(f"   (desenhos do reator não gerados: {type(ex).__name__}: {ex})")
    try:
        from . import ind_cad as ICAD
        arqs[f"{nome}_step"] = ICAD.gerar_step(d, os.path.join(forn, f"{nome}_3D.step"), nome.upper())
        arqs[f"{nome}_dxf"] = ICAD.gerar_dxf(d, os.path.join(forn, f"{nome}_2D.dxf"), _inf)
    except Exception as ex:
        log(f"   (CAD do reator não gerado: {type(ex).__name__}: {ex})")
    try:
        from . import calibracao as CAL, ind_verificacao as V
        arqs[f"{nome}_medidos"] = CAL.planilha(d, os.path.join(eng, f"Resultados_Medidos_{nome}.xlsx"), ccod)
        arqs[f"{nome}_femm"] = V.femm_lua(d, os.path.join(eng, f"Verificacao_FEMM_{nome}.lua"))
        if verificar and V.disponivel():
            log("   Reator: verificação independente no NGSolve (2D + 3D)...")
            cmp = V.comparar(d, log=log)
            V.salvar_cmp(cmp, os.path.join(eng, "verificacao_indutor.json"))
            arqs[f"{nome}_verif"] = V.relatorio(d, cmp, os.path.join(eng, f"Verificacao_Independente_{nome}.pdf"))
            lin = V.linhas_comparacao(cmp)
            nok = sum(1 for l in lin if l[-1] != "OK")
            d["verificacao_resumo"] = f"{len(lin) - nok} de {len(lin)} grandezas dentro do critério"
            log(f"   Reator: verificação independente – {d['verificacao_resumo']}")
        if verificar:
            from . import ind_avancado as AV
            log("   Reator: análise avançada – formas de onda do espectro harmônico, núcleo no tempo, 3D, mapa térmico...")
            # v1.26.4: MESMAS correntes do projeto – espectro do local × k_t, com √(I1² + ΣIh²) = In (antes: toda a folga em harmônicas)
            Ih = dict(r.get("Ih_termico") or e["Ih_projeto"])
            wf = B.wf_de_espectro(ped.freq_hz, r["I1"], Ih)
            av = AV.avaliar(d, None, None, log=log, fazer_3d=V.disponivel(), wf=wf)
            figs = AV.figuras(av, eng, nome)
            AV.salvar(av, os.path.join(eng, "avancado_indutor.json"))
            arqs[f"{nome}_avancado"] = AV.relatorio(d, av, os.path.join(eng, f"Analise_Avancada_{nome}.pdf"), figs)
            d["avancado"] = dict(perdas=av["perdas"], termico={k: v for k, v in av["termico"].items() if k != "iteracoes"})
            tf = AV.adotar_pior(d, av)                     # v1.26.4 (REQ-GER-014): resultado final = o mais severo
            avs = list(av.get("avisos") or [])
            T_proj = d["termico"]["amb_painel_C"] + d["termico"]["elev_bobina_K"]
            if av["termico"]["T_cobre_med_C"] > T_proj + 15:
                avs.append(f"Mapa térmico avançado: bobina média {av['termico']['T_cobre_med_C']:.0f} °C, acima dos {T_proj:.0f} °C do método de "
                           f"projeto – os dois métodos térmicos divergem; ADOTADO o mais severo (ponto quente {tf['ponto_quente_C']:.0f} °C, "
                           f"folga {tf['margem_K']:.0f} K até {tf['limite_C']:.0f} °C). Confirmar no ensaio de aquecimento do protótipo.")
            if tf["status"] != "APROVADO":
                avs.append(f"Térmica do reator {tf['status']}: ponto quente {tf['ponto_quente_C']:.0f} °C × limite {tf['limite_C']:.0f} °C "
                           f"(folga {tf['margem_K']:.0f} K; mínimo {tf['margem_min_K']:.0f} K).")
            try:                                           # caso EXTREMO informativo: toda a folga de corrente em harmônicas (limite IEC 60831)
                k_h, k_t = float(r.get("k_harm_extremo") or 0), float(r.get("k_termico") or 1)
                if k_h > 1.02 and r.get("I1_fisica"):
                    Ihx = {h: v * k_h for h, v in e["Ih_projeto"].items()}
                    avx = AV.avaliar(d, None, None, log=lambda *_a, **_k: None, fazer_3d=False, wf=B.wf_de_espectro(ped.freq_hz, r["I1_fisica"], Ihx))
                    d["avancado_extremo"] = dict(perdas_W=float(avx["perdas"]["total"]), ponto_quente_C=max(float(avx["termico"]["T_cobre_max_C"]), float(avx["termico"]["T_cobre_med_C"]) + 15.0),
                                                 I1_A=float(r["I1_fisica"]), Ih_A=float(r["I_harm_fisica"]) * k_h, k_h=k_h,
                                                 limite_C=tf["limite_C"])
                    x = d["avancado_extremo"]
                    log(f"   Reator – caso extremo (toda a folga em harmônicas: {x['Ih_A']:.0f} A = {k_h:.2f} × as do local): {x['perdas_W']:.0f} W, "
                        f"ponto quente {x['ponto_quente_C']:.0f} °C")
                    if x["ponto_quente_C"] > tf["limite_C"]:
                        avs.append(f"Caso extremo (harmônicas {k_h:.1f} × as do local, {x['Ih_A']:.0f} A – limite de corrente do capacitor IEC 60831): "
                                   f"ponto quente {x['ponto_quente_C']:.0f} °C, acima de {tf['limite_C']:.0f} °C – o termostato do reator e o relé de "
                                   f"sobrecarga harmônica do controlador são OBRIGATÓRIOS (desligam o estágio antes disso).")
            except Exception as _exx:
                log(f"   (caso extremo de harmônicas não calculado: {type(_exx).__name__}: {_exx})")
            d["avisos_avancado"] = avs
            for a_ in avs:
                log(f"   ⚠ Reator (análise avançada): {a_}")
    except Exception as ex:
        log(f"   (verificação/análise avançada do reator não concluída: {type(ex).__name__}: {ex})")
    try:
        arqs[f"{nome}_memorial"] = AUD.memorial_indutor(d, os.path.join(forn, f"Memorial_{nome}.pdf"), _inf["titulo"])
    except Exception as ex:
        log(f"   (memorial do reator não gerado: {type(ex).__name__}: {ex})")
    with open(os.path.join(eng, "indutor_projeto.json"), "w", encoding="utf-8") as fh:
        json.dump({k: v for k, v in d.items() if k not in ("campo_pico",)}, fh, ensure_ascii=False, indent=1, default=_json_default)
    log(f"   Reator: {d['N']} espiras, {d['ng']} entreferros/coluna, perdas ≈ {d['perdas']['total']:.0f} W, "
        f"elevação ≈ {d['termico']['elev_bobina_K']:.0f} K, massa ≈ {d['massa_kg']['total']:.0f} kg")
    return arqs


def resumo(ped, res, grupos, inds, cod):
    L = [f"# {DB.titulo_tipo(ped)} – {cod}", "", f"Cliente: {ped.cliente or '–'}  |  {ped.tensao_v:g} V / {ped.freq_hz:g} Hz", "",
         "| Estágio | Código | Capacitor | kvar efetivo | Nr / FD | L µH | I60 (ajuste) A | I projeto A |", "|---|---|---|---|---|---|---|---|"]
    for i, e in enumerate(res["estagios"]):
        L.append(f"| {i+1} | {e['codigo']} | {e['cap'][0]}×{e['cap'][1]:g} kvar/{e['U_cap_nom']} V | {e['Q_kvar']:.1f} | {e['nr']:.2f} / {e['p_pct']:.2f} % | "
                 f"{e['L_uH']:.0f} | {e['I60']:.1f} | {e['requisitos']['In']:.1f} |")
    L += ["", "Ressonância paralela: " + (", ".join(f"{x:.2f}ª" for x in res["varredura"]["picos"]) or "nenhuma"), ""]
    for gi, (grp, d) in enumerate(zip(grupos, inds)):
        if d:
            from .ind_avancado import final as _fin
            _tf = _fin(d)
            L.append(f"- Reator {gi+1} ({len(grp)} pç): {d['N']} esp., coluna {d['a']*1e3:.0f}×{d['b']*1e3:.0f} mm, {_tf['perdas_W']:.0f} W, "
                     f"{d['massa_kg']['total']:.0f} kg, ΔT {_tf['elev_K']:.0f} K, ponto quente {_tf['ponto_quente_C']:.0f} °C ({_tf['metodo']})")
    L += verificacoes_md(ped, res, grupos, inds)
    try:                                                # v1.26.3 (REQ-REA-014): tabela do reator padrão da biblioteca
        from . import biblioteca_reatores as _BRm
        for d in inds:
            if d and d.get("_biblioteca"):
                L += _BRm.tabela_md(dict(d["_biblioteca"]["reg"], _arquivo=d["_biblioteca"]["arquivo"]), d["_biblioteca"]["linhas"])
    except Exception as ex:
        L += ["", f"(tabela do reator padrão não gerada: {type(ex).__name__}: {ex})"]
    try:                                                # v1.26.1 (REQ-REA-015): reator projetado × reatores reais (Cootrans, fabricantes)
        from . import reator_benchmark as _RB
        for gi, (grp, d) in enumerate(zip(grupos, inds)):
            if d:
                e0 = res["estagios"][grp[0]] if isinstance(grp[0], int) else grp[0]
                dm = d.get("dims_mm") or {}
                med = (f"{dm.get('largura', 0):.0f} × {dm.get('profundidade', 0):.0f} × {dm.get('altura', 0):.0f} mm (L × P × A)" if dm else None)
                L += _RB.tabela_md(f"Reator {gi + 1}", e0["L_uH"], e0["requisitos"]["In"], d["massa_kg"]["total"], _fin(d)["perdas_W"], med,
                                   tipo=ped.tipo)
    except Exception as ex:
        L += ["", f"(comparação com reatores reais não calculada: {type(ex).__name__}: {ex})"]
    if res.get("arco"):                                 # v1.24.3: energia incidente IEEE 1584
        from . import arco as _AR
        L += ["", "## Energia incidente – IEEE 1584-2018 (NR-10 10.4.12)", "",
              "| Local | Eliminado por | I arco | Tempo | Energia | Fronteira | Categoria | Check |", "|---|---|---|---|---|---|---|---|"]
        L += ["| " + " | ".join(str(x) for x in r) + " |" for r in _AR.linhas_check(res["arco"])]
        L += ["", f"Sem disjuntor geral no painel o barramento ficaria com {res['arco']['sem_geral']['E']:.1f} cal/cm² "
              f"(proteção do cliente {res['arco']['t_montante_ms']:.0f} ms – confirmar no estudo de seletividade)."]
    if res["avisos"]:
        L += ["", "Avisos:"] + [f"- {a}" for a in res["avisos"]]
    return "\n".join(L) + "\n"


def verificacoes_md(ped, res, grupos, inds):
    """v1.22.0: tabela de verificações com coluna de CHECK (aprovado/atenção/reprovado) – capacitor (IEEE 18),
    sintonia × harmônicas presentes, reator (elevação de temperatura) e distorção de tensão na barra."""
    from . import checagem as CK
    L = ["", "## Verificações (check)", "", "| Item | Grandeza | Valor | Limite | Utilização | Check |", "|---|---|---|---|---|---|"]
    vistos = set()
    for i, e in enumerate(res["estagios"]):
        ch = (e["codigo"], round(e["Q_kvar"], 1))
        if ch in vistos:
            continue
        vistos.add(ch)
        iguais = [str(k + 1) for k, x in enumerate(res["estagios"]) if (x["codigo"], round(x["Q_kvar"], 1)) == ch]
        for nome, v, l in e["limites_cap"]:
            u = CK.utilizacao(v, l)
            L.append(f"| Capacitor est. {', '.join(iguais)} | {nome} (IEEE 18) | {v * 100:.0f} % | ≤ {l * 100:.0f} % | {u:.0f} % | "
                     f"{CK.texto(CK.check(v <= l, u))} |")
        # v1.26.1 (REQ-BCO-004): o capacitor escolhido tem que fechar o kvar pedido do estágio (±8 %) – senão REPROVADO
        if e.get("Q_alvo"):
            dq = abs(e["Q_kvar"] - e["Q_alvo"]) / e["Q_alvo"] * 100
            L.append(f"| Capacitor est. {', '.join(iguais)} | Potência efetiva × pedida ({e['cap'][0]}×{e['cap'][1]:g} kvar/{e['cap'][2]:g} V iguais) | "
                     f"{e['Q_kvar']:.1f} kvar (pedido {e['Q_alvo']:g}) | ± 8 % | {dq / 8 * 100:.0f} % | "
                     f"{CK.texto(CK.check(dq <= 8.0, dq / 8 * 100))} |")
    lim_dt = {"B": 80, "F": 105, "H": 125}.get(str(ped.classe).upper(), 105)   # elevação média (IEC 60076-6, amb. 40 °C)
    for gi, (grp, d) in enumerate(zip(grupos, inds)):
        if d:
            from .ind_avancado import final as _fin
            tf = _fin(d)                                  # v1.26.4 (REQ-GER-014): o PIOR entre projeto e análise avançada
            amb = tf["amb_C"]
            lim_e = tf["limite_C"] - amb - 15.0           # elevação média admissível no ambiente do painel (ponto quente = média + 15 K)
            dt = tf["elev_K"]
            u = CK.utilizacao(dt, lim_e)
            L.append(f"| Reator {gi + 1} | Elevação média da bobina – {tf['metodo']} (classe {ped.classe}, ambiente {amb:.0f} °C) | {dt:.0f} K | "
                     f"≤ {lim_e:.0f} K | {u:.0f} % | {CK.texto(CK.check(dt <= lim_e, u))} |")
            pq = tf["ponto_quente_C"]
            st = CK.REPROVADO if tf["status"] == "REPROVADO" else (CK.ATENCAO if tf["status"] != "APROVADO" else CK.APROVADO)
            L.append(f"| Reator {gi + 1} | Ponto quente da bobina (projeto {tf['projeto']['ponto_quente_C']:.0f} °C"
                     + (f" / avançado {tf['avancado']['ponto_quente_C']:.0f} °C" if tf.get("avancado") else " / avançado não rodado")
                     + f") | {pq:.0f} °C | ≤ {tf['limite_C']:.0f} °C com folga ≥ {tf['margem_min_K']:.0f} K | {pq / tf['limite_C'] * 100:.0f} % | {CK.texto(st)} |")
            pmx = float(d["requisitos"].get("P_max_mercado") or d["requisitos"].get("P_max") or 0)
            if pmx:
                u = CK.utilizacao(tf["perdas_W"], pmx)
                L.append(f"| Reator {gi + 1} | Perdas totais (projeto {tf['projeto']['perdas_W']:.0f} W"
                         + (f" / avançado {tf['avancado']['perdas_W']:.0f} W" if tf.get("avancado") else "")
                         + f") × teto de mercado na corrente de projeto; teto especificado ao fabricante e usado na térmica do painel: "
                         f"{float(d['requisitos'].get('P_max') or pmx):.0f} W | {tf['perdas_W']:.0f} W | ≤ {pmx:.0f} W | {u:.0f} % | "
                         f"{CK.texto(CK.check(tf['perdas_W'] <= pmx, u, nivel='aviso'))} |")
            x = d.get("avancado_extremo")
            if x:
                st = CK.APROVADO if x["ponto_quente_C"] <= x["limite_C"] else CK.ATENCAO
                L.append(f"| Reator {gi + 1} | Caso extremo: harmônicas {x['k_h']:.1f} × as do local ({x['Ih_A']:.0f} A; limite do capacitor IEC 60831) – "
                         f"ponto quente | {x['ponto_quente_C']:.0f} °C ({x['perdas_W']:.0f} W) | ≤ {x['limite_C']:.0f} °C (informativo; proteção: termostato + "
                         f"relé de sobrecarga harmônica) | {x['ponto_quente_C'] / x['limite_C'] * 100:.0f} % | {CK.texto(st)} |")
    try:                                                # v1.26.4 (auditoria BCD-04/05): cabo × fusível × borne da contatora, por tipo de estágio
        _vp = set()
        for i, e in enumerate(res["estagios"]):
            pr = B.protecao_estagio(ped, e)
            ch = (pr["fusivel_A"], pr["contator"], pr["cabo_calc"]["secao"], pr["cabo_cap_calc"]["secao"])
            if ch in _vp:
                continue
            _vp.add(ch)
            iguais = [str(k + 1) for k, x in enumerate(res["estagios"]) if round(x["Q_kvar"], 1) == round(e["Q_kvar"], 1)]
            for nome, val, lim, u, st, nota in B.conferencias_protecao(ped, e, pr):
                stc = {"ok": CK.APROVADO, "atencao": CK.ATENCAO, "reprovado": CK.REPROVADO}[st]
                L.append(f"| Estágio {', '.join(iguais)} | {nome}" + (f" – {nota}" if nota else "") + f" | {val} | {lim} | {u:.0f} % | {CK.texto(stc)} |")
    except Exception as _exc:
        L.append(f"| Estágios | Coordenação cabo × fusível × contatora | não calculada ({type(_exc).__name__}: {_exc}) | – | – | {CK.texto(CK.ATENCAO)} |")
    if res.get("arco"):                                  # v1.26.4 (auditoria BCD-06): o arco reprovado tem que aparecer nesta tabela
        try:
            from . import arco as _ARv
            for r_ in _ARv.linhas_check(res["arco"]):
                if "REPROVADO" in str(r_[-1]) or "ATEN" in str(r_[-1]):
                    L.append(f"| Arco elétrico | Energia incidente em {r_[0]} (IEEE 1584; eliminado por {r_[1]}, {r_[3]}) | {r_[4]} | "
                             f"ver tabela de energia incidente | – | {r_[-1]} |")
        except Exception:
            pass
    for x in res["varredura"]["picos"]:
        hs = [h for h in (ped.harm_tensao_pct or {}) if ped.harm_tensao_pct.get(h, 0) > 0.3] + list(ped.harm_carga_a or {})
        dist = min((abs(x - h) / h for h in hs), default=1.0)
        st = CK.APROVADO if dist >= 0.10 else CK.ATENCAO
        L.append(f"| Ressonância paralela | {x:.2f}ª × harmônicas presentes | {dist * 100:.0f} % da harmônica mais próxima | ≥ 10 % | – | "
                 f"{CK.texto(st)} |")
    if res.get("thd"):
        lim = 8.0 if ped.tensao_v <= 1000 else 5.0                            # IEEE 519-2022 (≤ 1 kV: 8 %)
        v = res["thd"]["com"]
        u = CK.utilizacao(v, lim)
        L.append(f"| Barra | DHTv com o banco (IEEE 519) | {v:.2f} % | ≤ {lim:g} % | {u:.0f} % | {CK.texto(CK.check(v <= lim, u))} |")
    L += ["", "Check: APROVADO (< 90 % do limite), ATENÇÃO (90–100 % ou aviso), REPROVADO (acima do limite obrigatório)."]
    return L
