"""Fluxo completo de BANCO DESSINTONIZADO / FILTRO SINTONIZADO (v1.13.0):
pedido → cálculo elétrico dos estágios → varredura de ressonância → reator(es) por elementos finitos (mesmo motor do
filtro senoidal) → verificação independente + análise avançada → desenhos/CAD → memorial → ET reator/capacitores → e-mails.

Estrutura de pastas igual à do filtro senoidal:
  01_Engenharia/ (memorial, JSON, figuras; 3_Reator_<n>_Elementos_Finitos/)  03_Fornecedores/1_Reator_<n>/, 2_Capacitores/
  05_Desenhos/2_Reator_<n>/
"""
import datetime as _dt
import json
import os
import shutil

from . import banco as B
from . import doc_banco as DB
from .dimensionamento import carregar_catalogo, _json_default

FORN_REATOR = ["Cootrans", "IBT", "Wise"]


def processar_banco(ped: B.PedidoBanco, pasta_base, cat=None, log=print, verificar_ind=True, zipar=True, n_bancos=1):
    from .pipeline import pasta_cliente, _achar_pasta_cliente
    from . import ind_projeto as IP
    from .versao import info as _vi, carimbar_pasta
    t0 = _dt.datetime.now()
    cat = cat or carregar_catalogo()
    cod = DB.codigo(ped)
    versao = f"FSEN v{_vi().get('versao')}"
    pasta_cli = os.path.join(pasta_base, _achar_pasta_cliente(pasta_base, ped.cliente) if ped.cliente else pasta_cliente(""))
    pasta = os.path.join(pasta_cli, f"{cod}_{t0:%Y%m%d_%H%M}")
    sub = {k: os.path.join(pasta, k) for k in ("01_Engenharia", "02_Cliente", "03_Fornecedores", "05_Desenhos")}
    for p in sub.values():
        os.makedirs(p, exist_ok=True)
    arqs = {}
    log(f"1/5 {DB.titulo_tipo(ped)} – {sum(ped.estagios_kvar):g} kvar / {ped.tensao_v:g} V: cálculo dos estágios e ressonância...")
    res = B.dimensionar(ped, cat)
    for i, e in enumerate(res["estagios"]):
        log(f"   Estágio {i+1}: {e['Q_kvar']:g} kvar, p {e['p_pct']:.2f} % ({e['f_sintonia']:.0f} Hz), L {e['L_uH']:.0f} µH, I1 {e['I1']:.1f} A, "
            f"I_th reator {e['requisitos']['In']:.1f} A, U_C {e['Uc_rms']:.0f} V → capacitor {e['Q_cap_nom_kvar']:.1f} kvar / {e['U_cap_nom']:g} V")
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
            d = IP.projetar_requisitos(e["requisitos"], e["espectro"], cat, log=log)
            d["aplicacao"] = e["requisitos"]["aplicacao"]
            arqs.update(_docs_reator(d, e, ped, nome, cod, eng, forn, des, versao, verificar_ind, log))
        except Exception as ex:
            log(f"   ({nome}: projeto não concluído – {type(ex).__name__}: {ex})")
        inds.append(d)
    log("3/5 Memorial de cálculo...")
    figs = DB.figuras(ped, res, sub["01_Engenharia"], cod)
    arqs["memorial"] = DB.memorial(ped, res, grupos, inds, os.path.join(sub["01_Engenharia"], f"{cod}_Memorial_de_Calculo.pdf"), figs, versao)
    shutil.copy(arqs["memorial"], os.path.join(sub["02_Cliente"], os.path.basename(arqs["memorial"])))
    log("4/5 Especificações e e-mails aos fornecedores...")
    for gi, (grp, d) in enumerate(zip(grupos, inds)):
        e = res["estagios"][grp[0]]
        forn = os.path.join(sub["03_Fornecedores"], f"1_Reator_{gi+1}_{e['L_uH']:.0f}uH_{e['requisitos']['In']:.0f}A")
        et = DB.et_reator(ped, res, grp, d, forn, cod, cat, n_bancos)
        arqs[f"et_reator_{gi+1}"] = et
        anexos = [os.path.join(forn, f) for f in sorted(os.listdir(forn)) if not f.startswith("Email_")]
        for fn in FORN_REATOR:
            with open(os.path.join(forn, f"Email_Reator_{fn}.txt"), "w", encoding="utf-8") as fh:
                fh.write(DB.email_fornecedor(fn, ped, res, [grp], anexos, cod))
    capd = os.path.join(sub["03_Fornecedores"], "2_Capacitores")
    os.makedirs(capd, exist_ok=True)
    arqs["et_capacitores"] = DB.et_capacitores(ped, res, capd, cod, cat, n_bancos)
    with open(os.path.join(capd, "Email_Capacitores.txt"), "w", encoding="utf-8") as fh:
        fh.write(DB.email_fornecedor("fornecedor", ped, res, grupos, [arqs["et_capacitores"]], cod, tipo="capacitor"))
    log("5/5 Dados e carimbo de versão...")
    ped_d = ped.__dict__.copy()
    with open(os.path.join(pasta, "pedido_banco.json"), "w", encoding="utf-8") as fh:
        json.dump(dict(tipo_filtro=ped.tipo, **ped_d), fh, ensure_ascii=False, indent=1, default=_json_default)
    res_s = {k: v for k, v in res.items() if k != "varredura"}
    res_s["varredura"] = dict(picos=res["varredura"]["picos"])
    with open(os.path.join(sub["01_Engenharia"], "banco_resultado.json"), "w", encoding="utf-8") as fh:
        json.dump(res_s, fh, ensure_ascii=False, indent=1, default=_json_default)
    with open(os.path.join(pasta, "RESUMO.md"), "w", encoding="utf-8") as fh:
        fh.write(resumo(ped, res, grupos, inds, cod))
    carimbar_pasta(pasta, log)
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
            wf = B.wf_de_espectro(ped.freq_hz, r["I1"], e["Ih"])
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
         "| Estágio | kvar | p % | f sint. | L µH | I1 A | I_th A | Capacitor |", "|---|---|---|---|---|---|---|---|"]
    for i, e in enumerate(res["estagios"]):
        L.append(f"| {i+1} | {e['Q_kvar']:g} | {e['p_pct']:.2f} | {e['f_sintonia']:.0f} Hz | {e['L_uH']:.0f} | {e['I1']:.1f} | "
                 f"{e['requisitos']['In']:.1f} | {e['Q_cap_nom_kvar']:.1f} kvar/{e['U_cap_nom']:g} V |")
    L += ["", "Ressonância paralela: " + (", ".join(f"{x:.2f}ª" for x in res["varredura"]["picos"]) or "nenhuma"), ""]
    for gi, (grp, d) in enumerate(zip(grupos, inds)):
        if d:
            L.append(f"- Reator {gi+1} ({len(grp)} pç): {d['N']} esp., coluna {d['a']*1e3:.0f}×{d['b']*1e3:.0f} mm, {d['perdas']['total']:.0f} W, "
                     f"{d['massa_kg']['total']:.0f} kg, ΔT {d['termico']['elev_bobina_K']:.0f} K")
    if res["avisos"]:
        L += ["", "Avisos:"] + [f"- {a}" for a in res["avisos"]]
    return "\n".join(L) + "\n"
