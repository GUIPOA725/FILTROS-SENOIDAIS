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
    sub = {k: os.path.join(pasta, k) for k in ("01_Engenharia", "02_Cliente", "03_Fornecedores", "05_Desenhos")}
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
        try:
            log(f"   {nome}: estágio(s) {', '.join(str(i+1) for i in grp)}")
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
            d["aplicacao"] = e["requisitos"]["aplicacao"]
            arqs.update(_docs_reator(d, e, ped, nome, cod, eng, forn, des, versao, verificar_ind, log))
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
    pnl = os.path.join(sub["03_Fornecedores"], "2_Painel_Montadora")
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
    with open(os.path.join(pnl, "Email_Montadora.txt"), "w", encoding="utf-8") as fh:
        fh.write(DB.email_fornecedor("IFG", ped, res, grupos, anexos_pnl, cod, tipo="painel"))
    arqs["proposta"] = DB.proposta(ped, res, sub["02_Cliente"], cod, cat, inds, n_bancos)
    log("5/5 Dados e carimbo de versão...")
    try:                                            # v1.23.0: folha de dados + verificação IEC 61439/61921 com check
        from . import normas_banco as NB
        from . import painel_gabinete as PG
        _gab = PG.gabinete(ped, res)
        _prot = B.protecao_estagio(ped, res["estagios"][0])
        arqs["normas"], ver_iec = NB.gerar_pdf(ped, res, _gab, _prot, cod, os.path.join(sub["01_Engenharia"], "5_Normas_Folha_de_Dados"),
                                               trans=trans, inds=inds, versao=versao, log=log)
        shutil.copy(arqs["normas"], os.path.join(sub["02_Cliente"], os.path.basename(arqs["normas"])))
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


def _docs_reator(d, e, ped, nome, cod, eng, forn, des, versao, verificar, log):
    """Desenhos, CAD, memorial FEM, planilha de calibração, script FEMM, verificação NGSolve e análise avançada do reator."""
    from . import ind_projeto as IP, ind_desenhos as IDS, auditoria as AUD
    arqs = {}
    r = d["requisitos"]
    ccod = f"{cod}_{nome.split('_')[0]}{nome.split('_')[1]}"
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
            Ih = dict(e["Ih_projeto"])                     # espectro escalado para a corrente de projeto adotada (k·I60 ou física)
            s_h = math.sqrt(sum(v ** 2 for v in Ih.values()))
            alvo = math.sqrt(max(r["In"] ** 2 - r["I1"] ** 2, 0.0))
            if s_h > 0 and alvo > s_h:
                Ih = {h: v * alvo / s_h for h, v in Ih.items()}
            wf = B.wf_de_espectro(ped.freq_hz, r["I1"], Ih)
            av = AV.avaliar(d, None, None, log=log, fazer_3d=V.disponivel(), wf=wf)
            figs = AV.figuras(av, eng, nome)
            AV.salvar(av, os.path.join(eng, "avancado_indutor.json"))
            arqs[f"{nome}_avancado"] = AV.relatorio(d, av, os.path.join(eng, f"Analise_Avancada_{nome}.pdf"), figs)
            d["avancado"] = dict(perdas=av["perdas"], termico={k: v for k, v in av["termico"].items() if k != "iteracoes"})
            avs = list(av.get("avisos") or [])
            T_proj = d["termico"]["amb_painel_C"] + d["termico"]["elev_bobina_K"]
            if av["termico"]["T_cobre_med_C"] > T_proj + 15:
                avs.append(f"Mapa térmico avançado: bobina média {av['termico']['T_cobre_med_C']:.0f} °C, acima dos {T_proj:.0f} °C do método de "
                           f"projeto – ainda dentro da classe {r['classe']}, mas pedir ao fabricante canal de ventilação ou confirmar no ensaio de aquecimento.")
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
            L.append(f"- Reator {gi+1} ({len(grp)} pç): {d['N']} esp., coluna {d['a']*1e3:.0f}×{d['b']*1e3:.0f} mm, {d['perdas']['total']:.0f} W, "
                     f"{d['massa_kg']['total']:.0f} kg, ΔT {d['termico']['elev_bobina_K']:.0f} K")
    L += verificacoes_md(ped, res, grupos, inds)
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
    lim_dt = {"B": 80, "F": 105, "H": 125}.get(str(ped.classe).upper(), 105)   # elevação média (IEC 60076-6, amb. 40 °C)
    for gi, (grp, d) in enumerate(zip(grupos, inds)):
        if d:
            dt = d["termico"]["elev_bobina_K"]
            u = CK.utilizacao(dt, lim_dt)
            L.append(f"| Reator {gi + 1} | Elevação de temperatura da bobina (classe {ped.classe}) | {dt:.0f} K | ≤ {lim_dt} K | {u:.0f} % | "
                     f"{CK.texto(CK.check(dt <= lim_dt, u))} |")
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
