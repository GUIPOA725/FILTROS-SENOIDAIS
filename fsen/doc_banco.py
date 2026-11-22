"""Documentos de bancos dessintonizados / filtros sintonizados no PADRÃO ELECTRIC (v1.14.0): memorial (PDF), planilha ESTAGIO
(XLSX com fórmulas, mesmo leiaute da engenharia), especificação do indutor (carta ao fabricante, formato Cootrans), ET do painel
para o montador (DOCX + XLSX), proposta técnica e comercial (DOCX) e e-mails."""
import datetime as _dt
import math
import os

import numpy as np

HOJE = _dt.date.today()


def _f(x, n=1):
    try:
        return f"{float(x):,.{n}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return str(x)


def titulo_tipo(ped):
    if ped.tipo == "sintonizado":
        hs = "/".join(f"{h:g}ª" for h in sorted(set(ped.ordens)))
        return f"Filtro harmônico sintonizado {hs}"
    return f"Banco de capacitores dessintonizado FD {_f(ped.p_pct, 2)} %"


def codigo(ped):
    Q = sum(ped.estagios_kvar)
    if ped.tipo == "sintonizado":
        return f"FHSBT-H{'-'.join(f'{h:g}' for h in sorted(set(ped.ordens)))}-{Q:g}kvar-{ped.tensao_v:g}V"
    fd = {3.5: "8,16", 3.78: "7", 2.67: "14", 2.5: "16"}.get(round(ped.nr, 2), f"{ped.p_pct:.1f}".replace(".", ","))
    return f"BCD-FD{fd}-{Q:g}kvar-{ped.tensao_v:g}V"


# ------------------------------------------------------------------------------------------------------------- figuras
def figuras(ped, res, pasta, cod):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    out = {}
    vr = res["varredura"]
    fig, ax = plt.subplots(figsize=(9, 4.2))
    ax.semilogy(vr["h"], vr["Zs"], color="#8a8f98", lw=1.2, ls="--", label="Rede sem o banco")
    ax.semilogy(vr["h"], vr["Z"], color="#1f4e8c", lw=2, label="Rede com todos os estágios ligados")
    for h, u in ped.harm_tensao_pct.items():
        if u > 0:
            ax.axvline(h, color="#c0392b", lw=0.8, alpha=0.5)
            ax.text(h + 0.15, min(vr["Z"]) * 1.05, f"{h}ª", color="#c0392b", fontsize=7, ha="left")
    for pk in vr["picos"]:
        ax.annotate(f"ressonância {pk:.2f}ª", (pk, np.interp(pk, vr["h"], vr["Z"])), textcoords="offset points", xytext=(8, 8),
                    fontsize=8, color="#1f4e8c")
    e0 = res["estagios"][0]
    ax.axvline(e0["h_sintonia"], color="#2e8b57", lw=1.2, ls=":")
    ax.text(e0["h_sintonia"], min(vr["Z"]) * 1.4, f"sintonia {e0['h_sintonia']:.2f}ª ({e0['f_sintonia']:.0f} Hz)", color="#2e8b57",
            fontsize=8, rotation=90, va="bottom", ha="right")
    ax.set_xlabel("Ordem harmônica h")
    ax.set_ylabel("|Z| na barra (Ω)")
    ax.set_title("Varredura de impedância na barra de instalação")
    ax.grid(True, which="both", alpha=0.3)
    ax.legend(fontsize=8, loc="lower right")
    fig.tight_layout()
    out["varredura"] = os.path.join(pasta, f"Banco_varredura_{cod}.png")
    fig.savefig(out["varredura"], dpi=150)
    plt.close(fig)
    # espectro de corrente e tensão do capacitor por estágio distinto – SEMPRE com a coluna THD (padrão Electric)
    fig, axs = plt.subplots(1, 2, figsize=(10, 3.8))
    hs = [h for h in sorted(e0["Ih"]) if h != 1]
    pos = list(range(len(hs) + 1))                    # 0 = THD, depois as ordens
    rot = ["THD"] + [str(h) for h in hs]
    grupos_e = {}                                     # estágios iguais (mesmo módulo) aparecem uma vez só
    for i_, e in enumerate(res["estagios"]):
        grupos_e.setdefault((e.get("codigo"), round(e["Q_kvar"], 1)), []).append((i_ + 1, e))
    lista_e = [(g[0][1], ", ".join(str(n) for n, _ in g)) for g in grupos_e.values()]
    n_e = max(len(lista_e), 1)
    w = 0.8 / n_e
    for k, (e, nums) in enumerate(lista_e):
        ih = [e["Ih"].get(h, 0) / e["I1"] * 100 for h in hs]
        uh = [e["Uch"].get(h, 0) / e["Uc1"] * 100 for h in hs]
        thd_i = float(np.sqrt(sum(x * x for x in ih)))
        thd_u = float(np.sqrt(sum(x * x for x in uh)))
        xs = [x + (k - (n_e - 1) / 2) * w for x in pos]
        b0 = axs[0].bar(xs, [thd_i] + ih, width=w, label=f"Estágio(s) {nums} ({e['Q_kvar']:.0f} kvar) – THDi {thd_i:.1f} %")
        b1 = axs[1].bar(xs, [thd_u] + uh, width=w, label=f"Estágio(s) {nums} – THDu {thd_u:.1f} %")
        if k == 0:
            axs[0].bar_label(b0, labels=[f"{thd_i:.1f}"] + [""] * len(hs), fontsize=7, padding=1)
            axs[1].bar_label(b1, labels=[f"{thd_u:.1f}"] + [""] * len(hs), fontsize=7, padding=1)
    axs[0].set_title("Corrente harmônica no estágio (% de I1)")
    axs[1].set_title("Tensão harmônica no capacitor (% de U_C1)")
    for a in axs:
        a.set_xlabel("THD e ordem harmônica h")
        a.set_xticks(pos, rot)
        a.axvline(0.5, color="#999999", lw=0.8, ls=":")
        a.grid(True, axis="y", alpha=0.3)
    axs[0].legend(fontsize=7)
    axs[1].legend(fontsize=7)
    fig.tight_layout()
    out["espectro"] = os.path.join(pasta, f"Banco_espectro_{cod}.png")
    fig.savefig(out["espectro"], dpi=150)
    plt.close(fig)
    return out


def _novo(titulo, subtitulo, cod, cat):
    from docx import Document
    from docx.shared import Pt, Cm, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml.ns import qn
    AZUL = RGBColor(0x1F, 0x3A, 0x5F)
    d = Document()
    sec = d.sections[0]
    sec.page_height, sec.page_width = Cm(29.7), Cm(21.0)
    sec.left_margin = sec.right_margin = Cm(2.0)
    st = d.styles["Normal"]
    st.font.name = "Calibri"
    st.font.size = Pt(11)
    st.element.rPr.rFonts.set(qn("w:eastAsia"), "Calibri")
    for nome, tam in (("Heading 1", 14), ("Heading 2", 12)):
        h = d.styles[nome]
        h.font.name, h.font.size, h.font.color.rgb, h.font.bold = "Calibri", Pt(tam), AZUL, True
    emp = (cat or {}).get("empresa") or dict(nome="Electric Service", email="", telefone="", cidade="")
    hp = sec.header.paragraphs[0]
    hp.text = f"{emp['nome']} – Engenharia  |  {cod}"
    fp = sec.footer.paragraphs[0]
    fp.text = f"{emp['nome']} • {emp.get('email','')} • {emp.get('telefone','')} • {emp.get('cidade','')}"
    fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p = d.add_paragraph()
    r = p.add_run(titulo)
    r.bold, r.font.size, r.font.color.rgb = True, Pt(17), AZUL
    if subtitulo:
        d.add_paragraph(subtitulo)
    from .versao import info
    d.add_paragraph(f"Documento {cod} • Emissão {HOJE:%d/%m/%Y} • Rev. 00 • FSEN v{info().get('versao')}")
    return d



MESES = ("janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro")


def _data_ext(d=None):
    d = d or HOJE
    return f"{d.day:02d} de {MESES[d.month - 1]} de {d.year}"


def _fd_txt(e):
    return f"FD {_f(e['p_pct'], 2)} % (Nr {_f(e['nr'], 2)})"


def _cap_txt(e):
    n, u, V = e["cap"]
    return f"{_f(n * u, 1)} kVAr/{V:g} V ({n} × {_f(u, 1)} kVAr/{V:g} V)"


# ------------------------------------------------------------------------------------------------------------- memorial
def memorial(ped, res, grupos, inds, arq, figs, versao=""):
    from .auditoria import Rel, _Doc, _esc
    from reportlab.platypus import Paragraph
    from . import banco as B
    R = Rel()
    sint = ped.tipo == "sintonizado"
    tit = f"{titulo_tipo(ped)} – {_f(res['Q_total_kvar'], 0)} kvar / {ped.tensao_v:g} V / {ped.freq_hz:g} Hz"
    R.f.append(Paragraph(_esc(tit), R.st["CAPA"]))
    R.p(f"Cliente: {ped.cliente or '–'} | Projeto: {ped.projeto or '–'} | Código {codigo(ped)} | Emissão {HOJE:%d/%m/%Y} | {versao}")
    R.p("Memorial de cálculo no padrão de engenharia da Electric (mesmas equações das planilhas 'ESTAGIO …kVAr …V FD8,16 %' e "
        "'Ajuste Indutor Trifásico/Monofásico'), com a conferência física da plataforma: espectro harmônico, ressonância com a rede, "
        "limites do capacitor (IEEE 18) e faixa de sintonia. Cada reator é projetado pelo motor de elementos finitos da plataforma "
        "(o mesmo do filtro senoidal), com verificação independente e análise avançada.")
    R.h1("Dados de entrada")
    lin = [("Tensão da rede / frequência", f"{ped.tensao_v:g} V / {ped.freq_hz:g} Hz"),
           ("Tipo", titulo_tipo(ped)),
           ("Estágios pedidos (kvar efetivos)", " + ".join(f"{q:g}" for q in ped.estagios_kvar) + f" = {sum(ped.estagios_kvar):g} kvar"),
           ("Fator de qualidade do reator FQ", f"{ped.fq_():g} (por fase, 60 Hz)"),
           ("Fator de corrente de projeto k = I_projeto/I60", f"{_f(ped.k_(), 2)}" + (f" ({B.K_HIST_SINT})" if sint else " (planilha ESTAGIO: ×1,3)")),
           ("Transformador / Scc da rede", f"{ped.trafo_kva:g} kVA, Z = {_f(ped.trafo_z_pct)} % / {ped.scc_rede_mva:g} MVA"),
           ("Reatância de curto-circuito na barra", f"{_f(res['x_rede_ohm']*1e3, 2)} mΩ"),
           ("Distorção de tensão " + ("de fundo (Thévenin)" if sint else "de projeto nos terminais") + " (% de Un)",
            ", ".join(f"{h}ª {_f(u)} %" for h, u in sorted(ped.harm_tensao_pct.items()))),
           ("Corrente harmônica da carga (A)", ", ".join(f"{h}ª {_f(i, 0)} A" for h, i in sorted(ped.harm_carga_a.items())) or "–"),
           ("Tolerâncias C / L", f"±{_f(ped.tol_c_pct, 0)} % / ±{_f(ped.tol_l_pct, 0)} %"),
           ("Reator", f"classe {ped.classe}, isolação 1 kV, IP00, enrolamento de {'alumínio' if ped.condutor == 'AL' else 'cobre'}"
                      + (", 3 monofásicos de 2 colunas por ramo" if ped.monofasico else ", trifásico 3 colunas"))]
    R.tab(["Grandeza", "Valor"], lin, [2.2, 3])
    R.h1("Método (padrão Electric)")
    R.eq("X_C = V_cap²/Q_cap      X_L = X_C/Nr²      FD = 1/Nr²      L = X_L/(2π·60)\n"
         "I60 = (V/(X_C − X_L))/√3      Q_efetivo = √3·V·I60      I_cap = Q_cap/(√3·V_cap)\n"
         "V_cap(operação) = Nr²/(Nr² − 1)·V   (+10 %)      R = X_L/FQ      P_fund = 3·I60²·R\n"
         "I_projeto = max( k·I60 ; √(I1² + Σ I_h²) )   I1 = 1,1·I60      ajuste: I60 com V_fase = I60·X_L (ensaio trifásico 60 Hz)"
         + ("\nEspectro mínimo do sintonizado (planilha do monofásico): I_h0 = 1,1·I1; seguintes 0,55·I1 e 0,44·I1" if sint else ""))
    R.h1("Estágios – parâmetros de ajuste e dados calculados")
    cab = ["Grandeza"] + [f"Est. {i+1}" for i in range(len(res["estagios"]))]
    E = res["estagios"]
    linhas = [
        ("Código do módulo", [e["codigo"] for e in E]),
        ("Capacitor associado", [_cap_txt(e) for e in E]),
        ("Nr / FD", [f"{_f(e['nr'], 2)} / {_f(e['p_pct'], 2)} %" for e in E]),
        ("Sintonia (Hz)", [_f(e["f_sintonia"], 0) for e in E]),
        ("X_C / X_L (Ω)", [f"{_f(e['Xc'], 3)} / {_f(e['Xl'], 4)}" for e in E]),
        ("L por fase (µH)", [_f(e["L_uH"], 1) for e in E]),
        ("Q efetivo na rede (kvar)", [_f(e["Q_kvar"], 1) for e in E]),
        ("I60 rede = corrente de AJUSTE (A)", [_f(e["I60"], 1) for e in E]),
        ("V por fase no ajuste (V)", [_f(e["V_ajuste_fase"], 1) for e in E]),
        ("I_cap nominal na V_cap (A)", [_f(e["I_cap_nom"], 1) for e in E]),
        ("V_cap operação / +10 % (V)", [f"{_f(e['Uc1'], 0)} / {_f(e['Uc1_110'], 0)}" for e in E]),
        ("R = X_L/FQ (mΩ) / perda fund. 3F (W)", [f"{_f(e['R_ohm']*1e3, 2)} / {_f(e['P_fund_W'], 0)}" for e in E]),
        ("I projeto padrão k·I60 (A)", [_f(e["requisitos"]["I_electric"], 1) for e in E]),
        ("I pelo espectro (A)", [_f(e["requisitos"]["I_fisica"], 1) for e in E]),
        ("I de PROJETO do reator (A)", [_f(e["requisitos"]["In"], 1) for e in E]),
        ("I rms no capacitor (A)", [_f(e["I_cap_rms"], 1) for e in E]),
    ]
    R.tab(cab, [[a] + b for a, b in linhas], [2.6] + [1.6] * len(E), 6.6)
    R.h2("Espectro de corrente de projeto por estágio (A)")
    hs = sorted(set(h for e in E for h in e["Ih_projeto"]))
    R.tab(["Estágio"] + [f"{h}ª" for h in hs], [[i + 1] + [_f(e["Ih_projeto"].get(h, 0), 1) for h in hs] for i, e in enumerate(E)])
    R.img(figs.get("espectro"), legenda="Espectro de corrente no estágio e de tensão no capacitor (física).")
    R.h2("Limites do capacitor (IEEE 18) e faixa de sintonia")
    lin = []
    for i, e in enumerate(E):
        fs = e["faixa_sintonia"]
        from . import checagem as CK
        _ck = CK.pior([CK.check(v <= l, CK.utilizacao(v, l)) for _, v, l in e["limites_cap"]])
        lin.append([i + 1] + [f"{v*100:.0f} % (≤ {l*100:.0f})" for _, v, l in e["limites_cap"]]
                   + [f"{_f(fs['f_min'], 0)}–{_f(fs['f_max'], 0)} Hz", CK.texto(_ck)])
    R.tab(["Est.", "V pico", "V rms", "I rms", "kvar", "Sintonia c/ tolerâncias", "Check"], lin, [0.5, 1.2, 1.2, 1.2, 1.2, 1.6, 1.3])
    R.h1("Ressonância com a rede")
    R.p(f"Sem reator, o banco ressonaria com o transformador em h ≈ √(Scc/Q) = {_f(res['hr_sem_reator'], 2)} (usando a potência de "
        "placa dos capacitores) – é o motivo do reator.")
    R.img(figs.get("varredura"), legenda="Impedância na barra com todos os estágios ligados.")
    pk = res["varredura"]["picos"]
    R.p("Ressonância(s) paralela(s) na barra com o banco: " + (", ".join(f"{x:.2f}ª ({x*ped.freq_hz:.0f} Hz)" for x in pk) or "nenhuma")
        + ". Com o reator ela fica ABAIXO da sintonia, longe das harmônicas características.")
    if res.get("thd"):
        t = res["thd"]
        R.h2("Distorção de tensão na barra (corrente harmônica da carga)")
        R.tab(["h", "sem filtro (%)", "com filtro (%)"], [(h, _f(a, 2), _f(b, 2)) for h, (a, b) in sorted(t["por_h"].items())]
              + [("DHTv", _f(t["sem"], 2), _f(t["com"], 2))])
    if res["avisos"]:
        R.h2("Avisos")
        R.bul(res["avisos"])
    R.h1("Proteção e manobra por estágio (padrão ET Electric)")
    lin = []
    for i, e in enumerate(E):
        pr = B.protecao_estagio(ped, e)
        lin.append((i + 1, f"{pr['chave_A']} A {pr['base']}", f"{pr['fusivel_A']} A", pr["contator"], f"{pr['cabo_mm2']} mm²",
                    f"{pr['cabo_ind_cap_mm2']} mm²"))
    R.tab(["Est.", "Chave-fusível", "Fusível", "Contator", "Cabo barra→reator", "Cabo reator→cap."], lin, [0.5, 1.4, 0.9, 3, 1.3, 1.3])
    R.h1("Reator(es) – projeto de referência por elementos finitos")
    for gi, (grp, d) in enumerate(zip(grupos, inds)):
        e = E[grp[0]]
        R.h2(f"Reator {gi+1} – estágio(s) {', '.join(str(i+1) for i in grp)} – {_f(e['L_uH'], 0)} µH / {_f(e['requisitos']['In'], 0)} A")
        if not d:
            R.p("Projeto por elementos finitos não concluído – ver log.")
            continue
        from .ind_projeto import descr_condutor
        L3 = d.get("L3d")
        lin = [("Indutância (projeto / 3D por fase)", f"{d['requisitos']['L']*1e6:.0f} µH / "
                + (", ".join(f"{x*1e6:.0f}" for x in L3) if L3 is not None else "–") + " µH"),
               ("Núcleo", f"{d['chapa_dados']['nome']}; coluna {d['a']*1e3:.0f} × {d['b']*1e3:.0f} mm; {d['ng']} entreferros por coluna"),
               ("Enrolamento", f"{d['N']} espiras de {descr_condutor(d, curto=True)}; bobina a {d['c']*1e3:.0f} mm do núcleo"),
               ("Perdas (projeto)", f"{d['perdas']['total']:.0f} W ({d['perdas']['total']/e['Q_kvar']:.1f} W/kvar)"),
               ("Elevação do enrolamento / ponto quente", f"{d['termico']['elev_bobina_K']:.0f} K / {d['termico']['ponto_quente_C']:.0f} °C (classe {ped.classe})"),
               ("Massa", f"{d['massa_kg']['total']:.0f} kg")]
        av = d.get("avancado")
        if av:
            lin.append(("Análise avançada (espectro, 3D)", f"{av['perdas']['total']:.0f} W; bobina média {av['termico']['T_cobre_med_C']:.0f} °C, "
                        f"ponto quente {av['termico']['T_cobre_max_C']:.0f} °C"))
        if d.get("verificacao_resumo"):
            lin.append(("Verificação independente (NGSolve)", d["verificacao_resumo"]))
        R.tab(["Grandeza", "Valor"], lin, [2, 4])
        if d.get("avisos_avancado"):
            R.bul(d["avisos_avancado"])
    if getattr(ped, "cenarios_rede", None) or getattr(ped, "origem_dados", None):
        R.h1("Dados da Plataforma de Estudos (medição e estudo de proteção)")
        if ped.origem_dados:
            R.p("Origem dos dados usados no projeto (digitado > medição QEE / estudo de proteção > IA > premissa):")
            R.tab(["Dado", "Origem"], [(k, v) for k, v in sorted(ped.origem_dados.items()) if not k.startswith("_")], [3, 3])
        if ped.cenarios_rede:
            from . import integracao as _IN
            R.p(f"Potência de curto da barra de ligação{(' ' + ped.barra_ligacao) if ped.barra_ligacao else ''} em cada cenário do "
                "estudo de proteção e verificação de ressonância do banco projetado (Scc da barra aplicada ao modelo de rede):")
            lin = []
            for c in _IN.verificar_cenarios(ped, ped.cenarios_rede):
                lin.append((c["nome"], f"{c.get('scc_mva', 0):.1f}", f"{c.get('hr_sem_reator', 0):.2f}",
                            "; ".join(c.get("avisos") or []) or "sem ressonância próxima de harmônica presente"))
            R.tab(["Cenário", "Scc (MVA)", "h ress. (sem reator)", "Verificação com o reator"], lin, [2.6, 0.9, 1.1, 2.4])
    R.h1("Conferência com as planilhas da Electric")
    R.p("O mesmo código recalcula casos reais das planilhas de engenharia (valores da planilha entre parênteses):")
    R.tab(["Caso (planilha)", "L (µH)", "I60 (A)", "I projeto (A)"], conferencia_planilhas(), [3.5, 1.6, 1.4, 1.6])
    doc = _Doc(arq, tit, rotulo="MEMORIAL DE CÁLCULO – ELECTRIC SERVICE")
    doc.multiBuild(R.f)
    return arq


CASOS_PLANILHA = [
    ("ESTAGIO 10KVAR 380V FD8,16 % – cap 15/480", dict(tensao_v=380, estagios_kvar=[10], caps=[[1, 15, 480]], nr=3.5), 3326.0, 15.55, 20.2),
    ("Ajuste FD14 % 10kVAr 220V – cap 27,5/380", dict(tensao_v=220, estagios_kvar=[10], caps=[[1, 27.5, 380]], nr=2.67), 1953.8, 28.14, 36.6),
    ("20kVAr 380V FD7 % – cap 25/440", dict(tensao_v=380, estagios_kvar=[20], caps=[[1, 25, 440]], nr=3.78), 1437.6, 30.46, 39.6),
    ("mem calculo 50kvar 440V – cap 80/600", dict(tensao_v=440, estagios_kvar=[50], caps=[[4, 20, 600]], nr=3.5, k_corrente=1.34), 974.4, 61.47, 82.4),
    ("Ajuste 1mH 45kVAr 440V – cap 60/525", dict(tensao_v=440, estagios_kvar=[45], caps=[[3, 20, 525]], nr=3.5), 994.7, 60.22, 78.3),
    ("Monofásico sintonizado 0,365 mH 51kVAr 380V – cap 160/690", dict(tipo="sintonizado", tensao_v=380, estagios_kvar=[50],
     caps=[[4, 40, 690]], ordens=[5], fator_sintonia=0.93, harm_tensao_pct={}), 365.2, 77.5, 140.3),
]


def conferencia_planilhas():
    from . import banco as B
    out = []
    for nome, kw, L, I, Ip in CASOS_PLANILHA:
        e = B.dimensionar(B.PedidoBanco(**kw))["estagios"][0]
        out.append((nome, f"{_f(e['L_uH'], 1)} ({_f(L, 1)})", f"{_f(e['I60'], 2)} ({_f(I, 2)})", f"{_f(e['requisitos']['In'], 1)} ({_f(Ip, 1)})"))
    return out


# ------------------------------------------------------------------------------------------------------------- planilha ESTAGIO
def planilha_estagio(ped, e, arq):
    """Planilha no MESMO leiaute da 'ESTAGIO xxKVAR yyyV FD…' da Electric, com fórmulas vivas (o engenheiro continua usando)."""
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    wb = Workbook()
    ws = wb.active
    ws.title = "Plan1"
    b = Font(bold=True)
    amarelo = PatternFill("solid", fgColor="FFF2CC")
    n, u, V = e["cap"]
    cel = {"C1": "PARAMETROS DE AJUSTE", "G1": "DADOS CALCULADOS", "D2": "Amps", "F2": "Volts", "H2": "Ohms", "J2": "Indutância uH",
           "B3": "Ajuste por Tensões e Correntes Trifásicas"}
    for k, v in cel.items():
        ws[k] = v
        ws[k].font = b
    for r, (fase, ang) in zip((3, 4, 5), (("A", "0°"), ("B", "120°"), ("C", "240°"))):
        ws[f"C{r}"] = f"Corrente I{fase} [60Hz] - {ang}"
        ws[f"D{r}"] = "=(M9/(M16-M15))/SQRT(3)"
        ws[f"E{r}"] = f"Tensão V{fase}1 - V{fase}2 [60Hz]"
        ws[f"F{r}"] = f"=D{r}*M15"
        ws[f"G{r}"] = f"XL {fase} [Ω]"
        ws[f"H{r}"] = f"=F{r}/D{r}"
        ws[f"I{r}"] = f"mH {fase}"
        ws[f"J{r}"] = f"=(H{r}/(2*PI()*M13))*1000000"
        ws[f"K{r}"] = f"FASE {fase}"
    ws["C6"] = "Corrente Indutor (projeto)"
    ws["D6"] = f"=D5*{ped.k_():g}"
    ws["F6"] = "=D6*M15"
    ws["C9"] = "DHTi% (IRMS INDUTOR)"
    ws["D9"] = "=(SQRT(D6^2-D5^2)/D5)"
    ws["B16"] = "IRMS DHTI 50% +10%"
    ws["C16"] = "=SQRT((D5*1.1)^2+(D5*1.1*0.5)^2)"
    inp = [("L9", "V_Rede", "M9", ped.tensao_v), ("L10", "Cap Kvar", "M10", n * u), ("L11", "Cap V", "M11", V),
           ("L12", "Nr", "M12", round(e["nr"], 4)), ("L13", "FQ (freq.)", "M13", ped.freq_hz)]
    for lc, lt, vc, vv in inp:
        ws[lc] = lt
        ws[vc] = vv
        ws[vc].fill = amarelo
    ws["N9"] = "INSERIR"
    form = [("L14", "FD[%]", "M14", "=1/M12^2"), ("L15", "XL", "M15", "=(((M11^2/M10)/1000)/M12^2)"), ("L16", "XC", "M16", "=(M11^2/M10)/1000"),
            ("L17", "R[Ω] (XL/FQ)", "M17", f"=M15/{e['fq']:g}"), ("L18", "kVAr_Rede", "M18", "=(D3*M9*SQRT(3))/1000"),
            ("L19", "I60HZ CAPACITOR", "M19", "=(M10/(M11*SQRT(3)))*1000"), ("L20", "I60HZ REDE", "M20", "=(M18/(M9*SQRT(3)))*1000"),
            ("L21", "IHARM CAP", "M21", "=SQRT(M19^2-M20^2)"), ("L22", "DHTI% IN CAP", "M22", "=(SQRT(M19^2-M20^2))/M20"),
            ("L23", "DHTI% IN IND", "M23", "=D9"), ("L25", "IRMS 100% DHTI", "M25", "=SQRT((M20^2)*2)"),
            ("L26", "Perda W Bobina 3F (fund.)", "M26", "=D3^2*M17*3"), ("L27", "VCAP", "M27", "=(M12^2/(M12^2-1))*M9"),
            ("L28", "VCAP + 10% VN", "M28", "=M27*1.1")]
    for lc, lt, vc, f in form:
        ws[lc] = lt
        ws[vc] = f
    ws["N14"] = "RESULTADO"
    ws["B30"] = (f"Gerado pela plataforma FSEN – {e['codigo']} – corrente de projeto do reator adotada {e['requisitos']['In']:.1f} A "
                 f"(maior entre k·I60 = {e['requisitos']['I_electric']:.1f} A e o espectro = {e['requisitos']['I_fisica']:.1f} A).")
    for col, w in zip("BCDEFGHIJKLMN", (10, 26, 10, 22, 10, 9, 9, 9, 12, 8, 24, 10, 10)):
        ws.column_dimensions[col].width = w
    wb.save(arq)
    return arq


# ------------------------------------------------------------------------------------------------------------- DOCX
def esp_reator(ped, res, grp, d, pasta, cod, cat, fornecedor="COOTRANS", local="Diadema – SP – Brasil", n_banco=1, mono=False):
    """Especificação do reator no formato das cartas da Electric à Cootrans (2015–2022) + o que a plataforma acrescenta."""
    from docx import Document
    from docx.shared import Pt, Cm
    from .documentos import _tabela, _bullets
    e = res["estagios"][grp[0]]
    r = e["requisitos"]
    sint = ped.tipo == "sintonizado"
    qtd = len(grp) * n_banco * (3 if mono else 1)
    doc = Document()
    sec = doc.sections[0]
    sec.page_height, sec.page_width = Cm(29.7), Cm(21.0)
    sec.left_margin = sec.right_margin = Cm(2.2)
    st = doc.styles["Normal"]
    st.font.name = "Calibri"
    st.font.size = Pt(11)
    doc.add_paragraph(f"Porto Alegre, {_data_ext()}.").alignment = 2
    doc.add_paragraph(f"À\n{fornecedor}\n{local}")
    if mono:
        titulo = "INDUTOR MONOFÁSICO, NÚCLEO DE FERRO ENVOLVIDO, PARA FILTRO DE HARMÔNICA SINTONIZADO"
    elif sint:
        titulo = "INDUTOR TRIFÁSICO PARA FILTRO DE HARMÔNICA SINTONIZADO"
    else:
        titulo = "INDUTOR TRIFÁSICO PARA BANCO DE CAPACITORES DESSINTONIZADO"
    p = doc.add_paragraph()
    p.add_run(titulo).bold = True
    p = doc.add_paragraph()
    p.add_run(f"{_f(e['Q_alvo'], 0)}kVAr/{ped.tensao_v:g}V/" + (f"{e['ordem']:g}ª harmônica (Nr {_f(e['nr'], 2)})" if sint else
                                                              f"FD{_f(e['p_pct'], 2)}%") + f" – {cod}").bold = True
    p = doc.add_paragraph()
    p.add_run("EQUIPAMENTO:").bold = True
    vsai = e["Uc1"]
    itens = [f"Corrente RMS de Projeto [A]: {r['In']:.0f}A.",
             f"Frequência Rede [Hz]: {ped.freq_hz:g}Hz.",
             "Regime de Funcionamento: Contínuo.",
             f"Núcleo: {'Monofásico – “Duas Colunas”' if mono else 'Trifásico'}.",
             f"Tensão Nominal Entrada F-F: {ped.tensao_v:g}V + 10%.",
             f"Tensão Nominal Saída F-F (lado capacitor): {vsai:.0f}V + 10%.",
             "Nível Isolamento: 1kV",
             f"Classe de Temperatura: {'F(155°C)' if ped.classe == 'F' else 'H(180°C)'}",
             "Grau de proteção: IP00",
             f"Fator de Qualidade: O FQ deverá ser >{e['fq']:g} por fase em 60Hz.",
             f"Quantidade: {qtd} unidades",
             f"Capacitor Associado: {_cap_txt(e)}.",
             f"Indutância [uH]: {e['L_uH']:.0f}uH com variação -{_f(ped.tol_l_pct, 0)}%/+{_f(ped.tol_l_pct, 0)}%"
             + (" (desequilíbrio entre fases ≤ 2 %)." if not mono else "."),
             "Ajuste da Indutância: A indutância deverá ser ajustada pelo gap (entreferro) por tensão e corrente trifásicas.",
             "Gap (entreferro): o gap (entreferro) deverá ser separado por material isolante, mantendo as condições de variação de "
             "indutância, para circulação de corrente do projeto e elevação de temperatura.",
             f"Linearidade (sobrecarga 50 %): o indutor não deverá saturar e deverá manter a indutância dentro da variação até "
             f"1,5 × a corrente de projeto ({1.5*r['In']:.0f} A rms; pico de operação {r['Ipk']:.0f} A).",
             f"Enrolamento: chapa ou barra de {'alumínio' if ped.condutor == 'AL' else 'cobre'}.",
             "Núcleo: chapa de aço silício NOVA, com certificado do fabricante da chapa (não aceito material reaproveitado).",
             "Proteção térmica: termostato NF na bobina central (abre a 130 °C ± 5 °C para classe F), cabos até a régua de bornes."]
    for t in itens:
        doc.add_paragraph(t, style="List Bullet")
    doc.add_paragraph("Correntes harmônicas previstas pelo indutor (regime contínuo):")
    hs = sorted(e["Ih_projeto"])
    _tabela(doc, ["Harmônica", "60 Hz"] + [f"{h}ª ({h*ped.freq_hz:g} Hz)" for h in hs],
            [["Corrente [A]", _f(r['I1'])] + [_f(e['Ih_projeto'][h]) for h in hs],
             ["Tensão no indutor [V]", _f(r['I1'] * e['Xl'])] + [_f(e['Ih_projeto'][h] * h * e['Xl']) for h in hs]])
    doc.add_paragraph(f"Valor eficaz do espectro: {_f(r['I_fisica'], 0)} A. Corrente RMS de projeto adotada: {_f(r['In'], 0)} A "
                      f"(maior entre o padrão Electric {_f(r['k_corrente'], 2)} × I60 = {_f(r['I_electric'], 0)} A e o espectro).")
    if sint or mono:
        doc.add_paragraph("Para a condição de corrente máxima da tabela acima, a temperatura no núcleo do indutor não deverá passar de "
                          "100 graus, bem como nos enrolamentos se possível. A Electric garante que esses limites de corrente não serão "
                          "ultrapassados por meio de proteção de sobrecorrente externa.")
    p = doc.add_paragraph()
    p.add_run("Ensaios Elétricos Indutores: ").bold = True
    p.add_run("Deverá ser enviado um relatório, contendo no mínimo os ensaios elétricos trifásicos com os resultados médios para as "
              "correntes de:")
    for nome, I in ((f"Corrente de Projeto: {r['In']:.0f}A", r["In"]), (f"Corrente de Ajuste: {e['I60']:.0f}A", e["I60"])):
        doc.add_paragraph().add_run(nome).bold = True
        for t in ("Resistência dos enrolamentos a 28°C:", "Resistência corrigida a 115 °C:", "Reatância por fase a 28°C:",
                  f"Tensão esperada por fase (I × X_L): {_f(I * e['Xl'])} V  (X_L = {_f(e['Xl'] * 1e3)} mΩ)",
                  "Resistência do Isolamento Megômetro escala 1000Vcc:", "Tensão Aplicada [60Hz – 1 minuto ENR/M]: 2,5 kV"):
            doc.add_paragraph(t, style="List Bullet")
    if d:
        from .ind_projeto import descr_condutor
        p = doc.add_paragraph()
        p.add_run("Projeto de referência Electric (anexo): ").bold = True
        p.add_run(f"calculado por elementos finitos – {d['chapa_dados']['nome']}, coluna {d['a']*1e3:.0f} × {d['b']*1e3:.0f} mm, {d['N']} "
                  f"espiras de {descr_condutor(d, curto=True)}, {d['ng']} entreferros por coluna, perdas ≈ {d['perdas']['total']:.0f} W, "
                  f"elevação ≈ {d['termico']['elev_bobina_K']:.0f} K, massa ≈ {d['massa_kg']['total']:.0f} kg. Seguem desenhos, CAD "
                  "(STEP/DXF) e memorial. O fabricante pode adaptar ao seu padrão – favor declarar as diferenças.")
    doc.add_paragraph("Favor informar: preço unitário, prazo, massa e dimensões (C × P × A), perdas garantidas na corrente de projeto, "
                      "origem e espessura da chapa e desenho dimensional.")
    doc.add_paragraph("\nAtenciosamente,\n\nEngº Guilherme Schallenberger\nElectric Service")
    tipo = "Monofasico" if mono else "Trifasico"
    arq = os.path.join(pasta, f"Indutor_{tipo}_{e['L_uH']:.0f}uH-{r['In']:.0f}A_{e['codigo']}_{fornecedor.split()[0].title()}.docx")
    doc.save(arq)
    return arq


def et_painel(ped, res, pasta, cod, cat, n_banco=1):
    """ET para o montador do painel (IFG) – mesmo formato das ET Electric (por estágio + componentes gerais + layout)."""
    from . import banco as B
    from .documentos import _tabela, _bullets
    sint = ped.tipo == "sintonizado"
    E = res["estagios"]
    tit = ("ESPECIFICAÇÃO PARA FORNECIMENTO – FILTRO HARMÔNICA SINTONIZADO" if sint else
           "ESPECIFICAÇÃO PARA FORNECIMENTO – BANCO DE CAP DESSINTONIZADO")
    comp = " + ".join(f"{len(g)}X{_f(E[g[0]]['Q_alvo'], 0)}KVAR" for g in B.reatores_distintos(res))
    doc = _novo(tit, f"{_f(sum(ped.estagios_kvar), 0)}KVAR ({comp}) {ped.tensao_v:g}V – {len(E)} estágios", cod, cat)
    pn = B.painel(ped, res)
    for g in B.reatores_distintos(res):
        e = E[g[0]]
        pr = B.protecao_estagio(ped, e)
        doc.add_heading(f"FORNECIMENTO MONTADORA: ESTÁGIO {_f(e['Q_alvo'], 0)}KVAR/{ped.tensao_v:g}V", 2)
        lin = [("Estágios", f"{len(g) * n_banco} X {_f(e['Q_alvo'], 0)}KVAR/{ped.tensao_v:g}V"),
               ("Tensão Rede", f"{ped.tensao_v:g}V"),
               ("Potência Nominal dos Capacitores “por Estágio”", _cap_txt(e) + (" – especial para filtro" if sint else "")),
               ("Potência efetiva de rede 60 Hz “por Estágio”", f"{_f(e['Q_kvar'], 1)}kVAr/{ped.tensao_v:g}V"),
               ("Corrente Nominal de Rede 60 Hz “por Estágio”", f"{e['I60']:.0f}A/{ped.tensao_v:g}V"),
               ("Corrente RMS com harmônicas “por Estágio”", f"{e['requisitos']['In']:.0f}A"),
               ("Seccionador-fusível “por estágio”", f"Chave {pr['chave_A']}A {pr['base']} – Fusíveis {pr['fusivel_A']}A"),
               ("Contatora “por estágio”", f"{pr['contator']} – IN {pr['contator_In']:.0f} A (manobra de capacitor)"),
               ("Cabo de força barramento → reator", f"{pr['cabo_mm2']} mm² 90 °C"),
               ("Cabo reator → capacitores", f"{pr['cabo_ind_cap_mm2']} mm² 90 °C"),
               ("Reator", f"{e['L_uH']:.0f} µH / {e['requisitos']['In']:.0f} A – FORNECIMENTO ELECTRIC")]
        _tabela(doc, ["Item", "Especificação"], lin, [6.5, 10.5])
    doc.add_heading("FORNECIMENTO MONTADORA: COMPONENTES GERAIS", 2)
    _tabela(doc, ["Item", "Descrição", "Quant.", "Unid."], [(i + 1, a, q * (n_banco if "Painel" in a else 1), u)
                                                            for i, (a, q, u) in enumerate(pn["itens"])], [1, 11, 2, 2])
    _bullets(doc, ["Demais materiais: barramento de cobre, isoladores, cabos de comando 1,5 mm², secundários de TC 2,5 mm², bornes, "
                   "canaletas, trilhos, base dos capacitores e base dos reatores, etiquetas.",
                   "Reatores sobre base própria na parte inferior do painel, capacitores acima, ventilação de baixo para cima."])
    doc.add_heading("FORNECIMENTO ELECTRIC", 2)
    _bullets(doc, pn["eletric"])
    doc.add_heading("FUNCIONAMENTO", 2)
    doc.add_paragraph("Modo automático: o controlador de fator de potência comanda os estágios. "
                      + ("Cada estágio tem multimedidor de proteção: se a corrente passar do ajuste, o CLP desarma o estágio; o retorno "
                         "é pelo botão de reset. " if sint else "")
                      + "A correção por banco com reatores de dessintonia evita a ressonância com o sistema, aumenta a vida útil dos "
                        "capacitores e reduz a amplificação das harmônicas.")
    arq = os.path.join(pasta, f"ET_Painel_{cod}.docx")
    doc.save(arq)
    # lista de materiais em planilha (mesmo modelo das ET .xlsx)
    from openpyxl import Workbook
    from openpyxl.styles import Font
    wb = Workbook()
    ws = wb.active
    ws.title = "Planilha1"
    ws["A1"] = f"{tit} – {_f(sum(ped.estagios_kvar), 0)} kVAr ({comp}) em {ped.tensao_v:g} V"
    ws["A1"].font = Font(bold=True, size=12)
    ws.append([])
    ws.append(["Item", "Descritivo", "Quant.", "Unid.", "Obs."])
    k = 1
    for a, q, u in pn["itens"]:
        ws.append([k, a, q, u, ""])
        k += 1
    for g in B.reatores_distintos(res):
        e = E[g[0]]
        pr = B.protecao_estagio(ped, e)
        nst = len(g) * n_banco
        ws.append([k, f"Chave Fusível Seccionadora Tripolar {pr['chave_A']}A {pr['base']}", nst, "pç", f"estágio {_f(e['Q_alvo'], 0)} kvar"]); k += 1
        ws.append([k, f"Fusível {pr['base']} {pr['fusivel_A']}A", 3 * nst, "pç", ""]); k += 1
        ws.append([k, f"Contatora {pr['contator']} – IN {pr['contator_In']:.0f}A", nst, "pç", ""]); k += 1
        ws.append([k, f"Capacitor trifásico {_f(e['cap'][1], 1)}kVAr/{e['cap'][2]}V" + (" especial filtro" if sint else ""), e["cap"][0] * nst,
                   "pç", f"{e['cap'][0]} caps por estágio"]); k += 1
        ws.append([k, f"Indutor Trif. {_fd_txt(e)} - {ped.tensao_v:g}V-{_f(e['Q_alvo'], 0)}kVAr-60Hz - "
                      f"{'Alumínio' if ped.condutor == 'AL' else 'Cobre'} - {'155' if ped.classe == 'F' else '180'}ºC - 1000V - Q>{e['fq']:g} - "
                      f"{e['L_uH']:.0f}uH {e['requisitos']['In']:.0f}A", nst, "pç", "Fornecimento Electric"]); k += 1
    for col, w in zip("ABCDE", (6, 90, 8, 6, 22)):
        ws.column_dimensions[col].width = w
    arq2 = os.path.join(pasta, f"ET_Painel_{cod}.xlsx")
    wb.save(arq2)
    return arq, arq2


def proposta(ped, res, pasta, cod, cat, inds=None, n_banco=1):
    """Proposta técnica e comercial no formato Electric (módulos com código, ou filtro FHSBT em painel). Preços em branco."""
    from .documentos import _tabela, _bullets
    from . import banco as B
    sint = ped.tipo == "sintonizado"
    E = res["estagios"]
    tit = ("PROPOSTA TÉCNICA E COMERCIAL – FILTRO DE HARMÔNICAS SINTONIZADO" if sint else
           "PROPOSTA TÉCNICA E COMERCIAL – FILTRO DE HARMÔNICA DESSINTONIZADO")
    doc = _novo(tit, f"{ped.cliente or 'Cliente'} – {_f(res['Q_total_kvar'], 0)} kVAr / {ped.tensao_v:g} V", cod, cat)
    doc.add_paragraph(f"Porto Alegre, {_data_ext()}.")
    doc.add_paragraph(f"À\n{ped.cliente or '________'}")
    doc.add_heading("APRESENTAÇÃO", 1)
    doc.add_paragraph("Presente no mercado desde 1985, a Electric presta consultoria para diferentes áreas do setor elétrico: medições e "
                      "diagnóstico de qualidade de energia, estudos para geração, transmissão, distribuição e indústria, e fornece "
                      "soluções de correção de fator de potência e de harmônicas.")
    if sint:
        doc.add_heading("1. DESCRIÇÃO DO FUNCIONAMENTO DE FILTROS SINTONIZADOS", 1)
        doc.add_paragraph("Filtros de harmônicas passivos sintonizados têm a frequência de ressonância próxima da harmônica perturbadora, "
                          "absorvendo um percentual muito grande da harmônica à qual estão sintonizados. Cada filtro também faz a "
                          "correção do fator de potência, simultaneamente à correção de harmônicos.")
        doc.add_heading("2. DESCRIÇÃO DA SOLUÇÃO", 1)
        hs = "/".join(f"{h:g}ª" for h in sorted(set(ped.ordens)))
        _tabela(doc, ["Item", "Valor"], [
            ("Empreendimento", ped.cliente or "–"), ("Local de instalação", ped.projeto or "Secundário do transformador"),
            ("TAG", "FHSBT#1"), ("Potência efetiva fornecida [kVAr]", f"{_f(res['Q_total_kvar'], 0)} kVAr"),
            ("Tensão de operação [V]", f"{ped.tensao_v:g} V"), ("Harmônica(s) sintonizada(s)", hs),
            ("Distorção harmônica de corrente drenada da rede [DHTi]", f"{_f(ped.dhti_carga_pct, 0)} %"),
            ("Equipamento", "Filtro sintonizado com indutores de núcleo de ferro"),
            ("Número total de estágios", " + ".join(f"{len(g)} x {_f(E[g[0]]['Q_alvo'], 0)} kVAr" for g in B.reatores_distintos(res))),
            ("Proteção geral do painel", "Chave seccionadora-fusível geral"),
            ("Dimensional A x L x P [mm] orientativo", "A={} x L={} x P={}".format(*B.painel(ped, res)["dim"]))], [7, 10])
        if res.get("thd"):
            doc.add_paragraph(f"Estudo: DHTv na barra de {_f(res['thd']['sem'], 2)} % sem filtro para {_f(res['thd']['com'], 2)} % com filtro "
                              "(corrente harmônica da carga informada).")
        doc.add_heading("Componentes básicos do filtro", 2)
        _bullets(doc, [("Reatores monofásicos" if ped.monofasico else "Reatores trifásicos") + ", com núcleo de ferro;",
                       f"Capacitores trifásicos conectados em delta, especiais para filtros, tensão de {E[0]['U_cap_nom']} V;",
                       "Contatoras de manobra dimensionadas para a corrente efetiva e a distorção harmônica prevista;",
                       "Chave desconectora tripolar com base NH e fusíveis para proteção individual de cada estágio;",
                       "Chave seccionadora-fusível geral; botoeira 3 posições; controlador automático;",
                       "Multimedidores por estágio para medição e proteção; CLP; comando; ventilação."])
        doc.add_heading("Serviços", 2)
        _bullets(doc, ["Medições comprobatórias de qualidade de energia após a entrada em operação, com relatório;",
                       "Termografia do filtro;", "Garantia de 12 meses (equipamentos e funcionamento)."])
    else:
        doc.add_heading("MÓDULO DE FILTRO DE HARMÔNICA DESSINTONIZADO", 1)
        doc.add_paragraph("A correção de fator de potência por filtros de harmônicas dessintonizados é feita para evitar a ressonância do "
                          "banco com o sistema, evitando a queima, aumentando a vida útil e reduzindo a amplificação dos níveis de "
                          "harmônicos. Dependendo do FD (fator de dessintonia) e da impedância do sistema, mais harmônicas serão "
                          "absorvidas pelo conjunto.")
        _bullets(doc, ["Evita ressonância com o sistema;", "Reduz a DHT do sistema;", "Aumenta a vida útil do capacitor;",
                       "Diminui o desgaste de componentes de manobra;", "Suporta o sistema de controle automático existente."])
    doc.add_heading("MÓDULOS E CONDIÇÕES COMERCIAIS", 1)
    for k, g in enumerate(B.reatores_distintos(res)):
        e = E[g[0]]
        _tabela(doc, ["Item", "Descritivo técnico", "Valor", "Qtd", "Unitário", "Total"], [
            (k + 1, "Código produto", e["codigo"], f"{len(g) * n_banco} pç", "R$ ______", "R$ ______"),
            ("", "Potência efetiva fornecida ao sistema", f"{_f(e['Q_alvo'], 0)} kVAr/{ped.tensao_v:g} V ({_f(e['Q_kvar'], 1)} kVAr calc.)", "", "", ""),
            ("", "Tensão nominal e frequência da rede", f"{ped.tensao_v:g} V/{ped.freq_hz:g} Hz", "", "", ""),
            ("", "Potência e tensão do capacitor", _cap_txt(e), "", "", ""),
            ("", "Fator de dessintonia / ordem" if not sint else "Sintonia", f"{_f(e['p_pct'], 2)} % / Nr {_f(e['nr'], 2)} ({e['f_sintonia']:.0f} Hz)", "", "", ""),
            ("", "Reator", f"{e['L_uH']:.0f} µH / {e['requisitos']['In']:.0f} A, classe {ped.classe}", "", "", "")], [1, 5, 6, 1.5, 2, 2])
    doc.add_heading("CONDIÇÕES", 1)
    _bullets(doc, ["Prazo de entrega: a definir (referência: 45–60 dias para módulos; 120–150 dias para painéis);",
                   "Pagamento, frete e instalação: a definir;", "Garantia: 12 meses;", "Validade da proposta: 15 dias."])
    doc.add_paragraph("\nEngº Guilherme Schallenberger – Engenheiro de Aplicação\nEngº Jeremias Wolff – Diretor de Engenharia")
    arq = os.path.join(pasta, f"Proposta_Tecnica_Comercial_{cod}.docx")
    doc.save(arq)
    return arq


def email_fornecedor(nome, ped, res, grupos, arqs, cod, tipo="reator"):
    linhas = [f"Prezados, {nome},", ""]
    if tipo == "reator":
        linhas.append(f"Solicito cotação de indutores para {titulo_tipo(ped).lower()} ({ped.tensao_v:g} V / {ped.freq_hz:g} Hz, ref. {cod}):")
        for gi, grp in enumerate(grupos):
            e = res["estagios"][grp[0]]
            r = e["requisitos"]
            linhas.append(f"  {gi+1}) {len(grp) * (3 if ped.monofasico else 1)} pç – {e['L_uH']:.0f} µH ±{_f(ped.tol_l_pct, 0)} %, corrente de "
                          f"projeto {r['In']:.0f} A (ajuste {e['I60']:.0f} A), {_fd_txt(e)}, capacitor associado {_cap_txt(e)}, "
                          f"classe {ped.classe}, FQ > {e['fq']:g}, isolação 1 kV")
        linhas += ["", "Segue a especificação de cada indutor (mesmo formato das anteriores) e o projeto de referência da Electric "
                   "(desenhos, CAD STEP/DXF e memorial de cálculo por elementos finitos). Podem adaptar ao padrão de fabricação de vocês, "
                   "declarando as diferenças.",
                   "Exigência: chapa de aço silício NOVA com certificado (não aceitamos chapa reaproveitada).",
                   "Peço preço, prazo, massa/dimensões, perdas garantidas e o relatório de ensaio (corrente de projeto e de ajuste) de cada unidade."]
    elif tipo == "painel":
        linhas.append(f"Solicito cotação da montagem do painel conforme a especificação anexa (ref. {cod}). Os reatores são fornecimento Electric.")
    else:
        linhas.append(f"Solicito cotação dos capacitores conforme a especificação anexa (ref. {cod}).")
    linhas += ["", "Anexos: " + ", ".join(os.path.basename(a) for a in arqs if a), "", "Atenciosamente,", "Electric Service – Engenharia"]
    return "\n".join(linhas)
