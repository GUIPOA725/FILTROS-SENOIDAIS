"""Documentos de bancos dessintonizados / filtros sintonizados (v1.13.0): memorial (PDF), figuras, ET do reator e dos
capacitores (DOCX) e e-mails aos fornecedores (TXT)."""
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
    return f"Banco de capacitores dessintonizado p = {ped.p_pct:g} %"


def codigo(ped):
    Q = sum(ped.estagios_kvar)
    if ped.tipo == "sintonizado":
        return f"FSIN-H{'-'.join(f'{h:g}' for h in sorted(set(ped.ordens)))}-{Q:g}kvar-{ped.tensao_v:g}V"
    return f"BDES-P{ped.p_pct:g}-{Q:g}kvar-{ped.tensao_v:g}V".replace(".", ",")


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
    # espectro de corrente e tensão do capacitor por estágio distinto
    fig, axs = plt.subplots(1, 2, figsize=(10, 3.8))
    hs = sorted(e0["Ih"])
    w = 0.8 / max(len(res["estagios"]), 1)
    for k, e in enumerate(res["estagios"]):
        axs[0].bar([h + (k - len(res["estagios"]) / 2) * w for h in hs], [e["Ih"][h] / e["I1"] * 100 for h in hs], width=w,
                   label=f"Estágio {k+1} ({e['Q_kvar']:g} kvar)")
        axs[1].bar([h + (k - len(res["estagios"]) / 2) * w for h in hs], [e["Uch"][h] / e["Uc1"] * 100 for h in hs], width=w)
    axs[0].set_title("Corrente harmônica no estágio (% de I1)")
    axs[1].set_title("Tensão harmônica no capacitor (% de U_C1)")
    for a in axs:
        a.set_xlabel("h")
        a.set_xticks(hs)
        a.grid(True, axis="y", alpha=0.3)
    axs[0].legend(fontsize=7)
    fig.tight_layout()
    out["espectro"] = os.path.join(pasta, f"Banco_espectro_{cod}.png")
    fig.savefig(out["espectro"], dpi=150)
    plt.close(fig)
    return out


# ------------------------------------------------------------------------------------------------------------- memorial
def memorial(ped, res, grupos, inds, arq, figs, versao=""):
    from .auditoria import Rel, _Doc, _esc
    from reportlab.platypus import Paragraph
    R = Rel()
    tit = f"{titulo_tipo(ped)} – {sum(ped.estagios_kvar):g} kvar / {ped.tensao_v:g} V / {ped.freq_hz:g} Hz"
    R.f.append(Paragraph(_esc(tit), R.st["CAPA"]))
    R.p(f"Cliente: {ped.cliente or '–'} | Projeto: {ped.projeto or '–'} | Código {codigo(ped)} | Emissão {HOJE:%d/%m/%Y} | {versao}")
    R.p("Memorial de cálculo do banco/filtro e do(s) reator(es). O reator de cada estágio é projetado pelo mesmo motor de elementos "
        "finitos usado nos filtros senoidais (triagem de chapas e condutores, 2 entreferros por coluna, barra de cobre, térmico, "
        "verificação independente no NGSolve e análise avançada com as formas de onda do espectro harmônico).")
    R.h1("Dados de entrada")
    lin = [("Tensão nominal / frequência", f"{ped.tensao_v:g} V / {ped.freq_hz:g} Hz"),
           ("Estágios", " + ".join(f"{q:g}" for q in ped.estagios_kvar) + f" = {sum(ped.estagios_kvar):g} kvar (potência efetiva na tensão nominal)"),
           ("Tipo", titulo_tipo(ped)),
           ("Transformador", f"{ped.trafo_kva:g} kVA, Z = {ped.trafo_z_pct:g} %"),
           ("Potência de curto-circuito da rede (MT)", f"{ped.scc_rede_mva:g} MVA"),
           ("Reatância de curto-circuito na barra", f"{res['x_rede_ohm']*1e3:.2f} mΩ"),
           ("Distorção de fundo da rede a montante – Thévenin (% de Un)" if ped.tipo == "sintonizado" else "Distorção de tensão de projeto nos terminais (% de Un)", ", ".join(f"{h}ª {_f(u)} %" for h, u in sorted(ped.harm_tensao_pct.items()))),
           ("Corrente harmônica da carga (A)", ", ".join(f"{h}ª {i:g} A" for h, i in sorted(ped.harm_carga_a.items())) or "–"),
           ("Temperatura ambiente", f"{ped.amb_c:g} °C"),
           ("Sobretensão permanente admitida", f"{(ped.sobretensao-1)*100:.0f} %"),
           ("Tolerância da capacitância", f"±{ped.tol_c_pct:g} %")]
    R.tab(["Grandeza", "Valor"], lin, [2, 3])
    R.h1("Equações")
    R.eq("X_C (por fase, estrela equivalente) = Un² / (Q·(1 − p))      X_L = p·X_C      f_sint = f1/√p\n"
         "U_C1 = Un/(1 − p)      I1 = Q/(√3·Un)\n"
         "I_h = (u_h·Un/√3) / |R + j(h·X_L − X_C/h)|      U_C,h = √3·I_h·X_C/h\n"
         "Z_barra(h) = [1/(j·h·X_rede) + Σ 1/Z_estágio(h)]^-1   (ressonância paralela = pico de |Z|)\n"
         "Reator: I_th = 1,05·√(I1'² + Σ I_h²), I1' = I1·√(1,1·(1+tol_C)); linearidade L ≥ 95 % até "
         + ("1,8" if ped.tipo == "dessintonizado" else "1,5") + "·I1 (pico)")
    R.h1("Estágios")
    cab = ["Est.", "Q (kvar)", "p (%)", "f sint. (Hz)", "L (µH/fase)", "C Δ (µF/fase)", "I1 (A)", "I_th reator (A)", "U_C (V rms)",
           "Capacitor"]
    lin = []
    for i, e in enumerate(res["estagios"]):
        lin.append((i + 1, _f(e['Q_kvar'], 1), _f(e['p_pct'], 2), _f(e['f_sintonia']), _f(e['L_uH']), _f(e['C_delta_uF']),
                    _f(e['I1']), _f(e['requisitos']['In']), _f(e['Uc_rms'], 0),
                    f"{_f(e['Q_cap_nom_kvar'])} kvar / {e['U_cap_nom']:g} V"))
    R.tab(cab, lin, [0.6, 1, 0.8, 1, 1.2, 1.2, 0.9, 1.2, 1, 2.2])
    R.p("O capacitor é especificado na sua tensão nominal (≥ 1,1 × U_C rms e ≥ soma aritmética/1,1); a potência de placa na tensão "
        "nominal do capacitor é maior que a efetiva do estágio – é o que se compra (ex.: 525 V em rede de 440 V com p = 7 %).")
    R.h2("Correntes e tensões harmônicas por estágio")
    hs = sorted(res["estagios"][0]["Ih"])
    lin = []
    for i, e in enumerate(res["estagios"]):
        lin.append([f"{i+1} – I (A)"] + [_f(e['Ih'][h]) for h in hs])
        lin.append([f"{i+1} – U_C (V)"] + [_f(e['Uch'][h]) for h in hs])
    R.tab(["Estágio"] + [f"{h}ª" for h in hs], lin)
    R.img(figs.get("espectro"), legenda="Espectro de corrente no estágio e de tensão no capacitor.")
    R.h1("Ressonância com a rede")
    R.img(figs.get("varredura"), legenda="Impedância na barra com todos os estágios ligados.")
    pk = res["varredura"]["picos"]
    R.p("Ressonância(s) paralela(s) na barra: " + (", ".join(f"{x:.2f}ª ({x*ped.freq_hz:.0f} Hz)" for x in pk) or "nenhuma acima de 1,5× a rede")
        + ". Com reator, a ressonância paralela fica ABAIXO da sintonia e longe das harmônicas características (5ª, 7ª...).")
    if res.get("thd"):
        t = res["thd"]
        R.h2("Distorção de tensão na barra (corrente harmônica da carga)")
        R.tab(["h", "sem filtro (%)", "com filtro (%)"], [(h, f"{a:.2f}", f"{b:.2f}") for h, (a, b) in sorted(t["por_h"].items())]
              + [("THD", f"{t['sem']:.2f}", f"{t['com']:.2f}")])
    if res["avisos"]:
        R.h2("Avisos")
        R.bul(res["avisos"])
    R.h1("Reator(es)")
    for gi, (grp, d) in enumerate(zip(grupos, inds)):
        e = res["estagios"][grp[0]]
        R.h2(f"Reator {gi+1} – estágio(s) {', '.join(str(i+1) for i in grp)} – {e['L_uH']:.0f} µH / {e['requisitos']['In']:.0f} A")
        if not d:
            R.p("Projeto por elementos finitos não concluído – ver log.")
            continue
        from .ind_projeto import descr_condutor
        L3 = d.get("L3d")
        lin = [("Indutância (projeto / 3D por fase)", f"{d['requisitos']['L']*1e6:.0f} µH / " + (", ".join(f"{x*1e6:.0f}" for x in L3) if L3 is not None else "–") + " µH"),
               ("Núcleo", f"{d['chapa_dados']['nome']}; coluna {d['a']*1e3:.0f} × {d['b']*1e3:.0f} mm; {d['ng']} entreferros por coluna"),
               ("Enrolamento", f"{d['N']} espiras de {descr_condutor(d, curto=True)}; bobina a {d['c']*1e3:.0f} mm do núcleo"),
               ("Perdas (projeto)", f"{d['perdas']['total']:.0f} W (Cu 60 Hz {d['perdas']['enrolamento_60Hz']:.0f} W; Cu harm. "
                f"{d['perdas']['enrolamento_AF']:.0f} W; núcleo {d['perdas']['nucleo_60Hz'] + d['perdas']['nucleo_AF']:.0f} W) – "
                f"{d['perdas']['total']/e['Q_kvar']:.1f} W/kvar"),
               ("Elevação do enrolamento / ponto quente", f"{d['termico']['elev_bobina_K']:.0f} K / {d['termico']['ponto_quente_C']:.0f} °C"),
               ("Massa", f"{d['massa_kg']['total']:.0f} kg")]
        av = d.get("avancado")
        if av:
            lin.append(("Análise avançada (formas de onda do espectro, 3D)", f"{av['perdas']['total']:.0f} W; bobina média "
                        f"{av['termico']['T_cobre_med_C']:.0f} °C, ponto quente {av['termico']['T_cobre_max_C']:.0f} °C"))
        vf = d.get("verificacao_resumo")
        if vf:
            lin.append(("Verificação independente (NGSolve)", vf))
        sat = d.get("saturacao") or []
        for s in sat:
            lin.append((f"L em {s['caso']}", f"{min(s.get('L_lat_pct') or 999, s.get('L_cen_pct') or 999):.0f} % da nominal"))
        R.tab(["Grandeza", "Valor"], lin, [2, 4])
        if d.get("avisos_avancado"):
            R.bul(d["avisos_avancado"])
    R.p("Os desenhos, o CAD (STEP/DXF), o memorial de elementos finitos, a verificação independente e a análise avançada de cada "
        "reator estão em 01_Engenharia e 03_Fornecedores.")
    doc = _Doc(arq, tit, rotulo="MEMORIAL DE CÁLCULO – ELECTRIC SERVICE")
    doc.multiBuild(R.f)
    return arq


# ------------------------------------------------------------------------------------------------------------- DOCX
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


def et_reator(ped, res, grp, d, pasta, cod, cat, n_banco=1):
    from .documentos import _tabela, _bullets
    e = res["estagios"][grp[0]]
    r = e["requisitos"]
    qtd = len(grp) * n_banco
    dess = ped.tipo == "dessintonizado"
    tit = f"Especificação técnica – Reator {'dessintonizado' if dess else 'de filtro sintonizado'} {e['L_uH']:.0f} µH / {r['In']:.0f} A"
    doc = _novo(tit, f"{titulo_tipo(ped)} – estágio de {e['Q_kvar']:g} kvar em {ped.tensao_v:g} V / {ped.freq_hz:g} Hz", cod, cat)
    doc.add_heading("1. Objeto e quantidade", 1)
    doc.add_paragraph(f"{qtd} reator(es) trifásico(s) com núcleo de ferro, a seco, para ligação em série com capacitor trifásico de "
                      f"{e['Q_cap_nom_kvar']:.1f} kvar / {e['U_cap_nom']:g} V (estágio de {e['Q_kvar']:g} kvar efetivos). Normas: IEC 60076-6 "
                      "(reatores), IEC 60289 (complementar), NBR 5356 (ensaios), IEC 60831-1 (capacitor associado).")
    doc.add_heading("2. Características elétricas", 1)
    lin = [("Tensão do sistema / frequência", f"{ped.tensao_v:g} V / {ped.freq_hz:g} Hz (Um 1,1 kV)"),
           ("Fator de dessintonia p / sintonia", f"{e['p_pct']:.2f} % / {e['f_sintonia']:.1f} Hz ({e['h_sintonia']:.2f}ª)"),
           ("Indutância por fase", f"{e['L_uH']:.1f} µH  (tolerância ±{r['tol_L_pct']:g} %; desequilíbrio entre fases ≤ 2 %)"),
           ("Corrente fundamental (com sobretensão e tolerância)", f"{r['I1']:.1f} A"),
           ("Corrente térmica (fundamental + harmônicas, valor eficaz)", f"{r['In']:.1f} A – ensaio de aquecimento nesta corrente"),
           ("Linearidade", f"L ≥ 95 % do nominal até {r['linearidade']:g} × I1 eficaz ({r['Isat']:.0f} A pico)"),
           ("Corrente de pico de projeto", f"{r['Ipk']:.0f} A"),
           ("Perdas máximas a I_th e 75 °C/115 °C ref.", f"≤ {r['P_max']:.0f} W (todas as fases)"),
           ("Classe de isolação / ambiente", f"H (180 °C) ou F com elevação ≤ 100 K; ambiente {ped.amb_c:g} °C (painel)"),
           ("Tensão aplicada (60 s)", "3 kV entre enrolamento e massa"),
           ("Proteção térmica", "Termostato NF na bobina central (abre a 140 °C ± 5 °C), cabos até a régua de bornes"),
           ("Grau de proteção / instalação", "IP00, interna ao painel, ventilação natural (ou forçada conforme o painel)")]
    _tabela(doc, ["Grandeza", "Valor"], lin, [6.5, 10.5])
    doc.add_heading("3. Espectro de corrente de projeto", 1)
    hs = sorted(e["Ih"])
    _tabela(doc, ["Harmônica"] + [f"{h}ª" for h in hs], [["Corrente (A)"] + [f"{e['Ih'][h]:.1f}" for h in hs],
                                                         ["Tensão de rede (%)"] + [f"{ped.harm_tensao_pct.get(h, 0):g}" for h in hs]])
    doc.add_paragraph("Distorção de tensão de projeto conforme guias de aplicação de reatores dessintonizados (dentro da IEC 61000-2-4 "
                      "classe 2). O reator deve suportar este espectro em regime contínuo.")
    doc.add_heading("4. Construção", 1)
    itens = ["Núcleo trifásico de 3 colunas em chapa de aço silício NOVA, de grão orientado ou não orientado, com certificado do "
             "fabricante da chapa (Aperam ou equivalente) – não aceito material reaproveitado; espessura ≤ 0,35 mm.",
             "Entreferros distribuídos (2 por coluna, nas juntas coluna–culatra, ou mais), com espaçadores rígidos classe H "
             "(NOMEX/epóxi) colados; ajuste fino da indutância pela espessura dos espaçadores.",
             "Enrolamento em barra ou fio retangular de cobre esmaltado classe H, com isolação entre camadas e canal de ventilação.",
             "Impregnação a vácuo (VPI) ou imersão com resina classe H, cura em estufa.",
             "Quadros em U de chapa dobrada zincada e tirantes nos vãos entre fases, fora das bobinas; a alma do quadro termina 20 mm "
             "antes das juntas (não encostar aço magnético no entreferro).",
             "Saídas pela própria barra da bobina, horizontais para a frente, terminadas em barra de cobre estanhada com furação NEMA.",
             "Placa de identificação com L, I1, I_th, p %, frequência de sintonia, classe, massa, nº de série e data."]
    _bullets(doc, itens)
    if d:
        from .ind_projeto import descr_condutor
        doc.add_heading("5. Projeto de referência (Electric Service)", 1)
        doc.add_paragraph(f"Calculado por elementos finitos: {d['chapa_dados']['nome']}, coluna {d['a']*1e3:.0f} × {d['b']*1e3:.0f} mm, "
                          f"{d['N']} espiras de {descr_condutor(d, curto=True)}, {d['ng']} entreferros por coluna, perdas ≈ "
                          f"{d['perdas']['total']:.0f} W, elevação ≈ {d['termico']['elev_bobina_K']:.0f} K, massa ≈ {d['massa_kg']['total']:.0f} kg. "
                          "Seguem desenhos, CAD (STEP/DXF) e memorial. O fabricante pode adaptar ao seu padrão – declarar as diferenças.")
    doc.add_heading("6. Ensaios", 1)
    _bullets(doc, ["Rotina (todas as unidades): indutância de cada fase em 60 Hz na I1 (método tensão × corrente trifásico), resistência "
                   "CC das fases a 20 °C, tensão aplicada 3 kV/60 s, inspeção visual e dimensional.",
                   f"Tipo (1ª unidade): linearidade (L em {r['linearidade']:g}×I1), perdas, aquecimento na I_th = {r['In']:.0f} A até "
                   "estabilização (resistência a quente), atuação do termostato.",
                   "Relatório com os valores medidos, a temperatura e o instrumento (com calibração) – enviar antes do faturamento."])
    doc.add_heading("7. Dados a informar na proposta", 1)
    _bullets(doc, ["Preço unitário e prazo; massa e dimensões (C × P × A); perdas garantidas a I_th; elevação de temperatura;",
                   "origem e espessura da chapa (certificado); software/método de cálculo; desenho dimensional.",
                   "Validade da proposta, condições de pagamento e garantia."])
    arq = os.path.join(pasta, f"ET_Reator_{e['L_uH']:.0f}uH_{r['In']:.0f}A_{cod}.docx")
    doc.save(arq)
    return arq


def et_capacitores(ped, res, pasta, cod, cat, n_banco=1):
    from .documentos import _tabela, _bullets
    doc = _novo("Especificação técnica – Capacitores de potência", f"{titulo_tipo(ped)} – {ped.tensao_v:g} V / {ped.freq_hz:g} Hz", cod, cat)
    doc.add_paragraph("Capacitores trifásicos de baixa tensão, autorregenerativos (filme de polipropileno metalizado), com dispositivo de "
                      "interrupção por sobrepressão e resistores de descarga (≤ 50 V em 1 min). Norma IEC 60831-1/-2 (NBR IEC 60831). "
                      "Operação em série com reator: tensão nominal ACIMA da rede.")
    agg = {}
    for e in res["estagios"]:
        k = (e["U_cap_nom"], round(e["Q_cap_nom_kvar"], 1))
        a = agg.setdefault(k, dict(n=0, e=e))
        a["n"] += n_banco
    lin = []
    for (U, Q), a in agg.items():
        e = a["e"]
        lin.append((a["n"], f"{Q:.1f} kvar", f"{U:g} V", f"{e['C_delta_uF']:.1f} µF (Δ)", f"{e['Uc_rms']:.0f} V", f"{e['I_cap_rms']*1.3:.0f} A",
                    f"{e['Q_kvar']:g} kvar em {ped.tensao_v:g} V"))
    _tabela(doc, ["Qtd", "Potência nominal", "Tensão nominal", "Capacitância/fase", "Tensão de operação", "Corrente máx. (≥1,3 I)",
                  "Potência efetiva com reator"], lin)
    _bullets(doc, [f"Tolerância de capacitância ±{ped.tol_c_pct:g} % (preferência −5/+5 %; para filtro sintonizado pedir ±3 % ou casar as fases).",
                   f"Categoria de temperatura −25/D ou melhor (ambiente {ped.amb_c:g} °C).",
                   "Corrente de inrush ≥ 200 × In; vida útil ≥ 100 000 h; terminais com proteção IP20.",
                   "Informar marca, modelo, preço e prazo."])
    arq = os.path.join(pasta, f"ET_Capacitores_{cod}.docx")
    doc.save(arq)
    return arq


def email_fornecedor(nome, ped, res, grupos, arqs, cod, tipo="reator"):
    linhas = [f"Prezados, {nome},", ""]
    if tipo == "reator":
        linhas.append(f"Solicito cotação de reatores para {titulo_tipo(ped).lower()} ({ped.tensao_v:g} V / {ped.freq_hz:g} Hz, ref. {cod}):")
        for gi, grp in enumerate(grupos):
            e = res["estagios"][grp[0]]
            r = e["requisitos"]
            linhas.append(f"  {gi+1}) {len(grp)} pç – {e['L_uH']:.0f} µH/fase ±{_f(r['tol_L_pct'], 0)} %, I1 {r['I1']:.0f} A, I_th {r['In']:.0f} A, "
                          f"p = {_f(e['p_pct'], 2)} % ({e['f_sintonia']:.0f} Hz), linear até {_f(r['linearidade'])}×I1, perdas ≤ {r['P_max']:.0f} W, "
                          "classe H, termostato NF")
        linhas += ["", "Seguem a especificação técnica de cada reator e o projeto de referência (desenhos, CAD STEP/DXF e memorial de "
                   "cálculo por elementos finitos). Podem adaptar ao padrão de fabricação de vocês, declarando as diferenças.",
                   "Exigência: chapa de aço silício NOVA com certificado (não aceitamos chapa reaproveitada).",
                   "Peço preço, prazo, massa/dimensões, perdas garantidas e o relatório de ensaio de rotina de cada unidade."]
    else:
        linhas.append(f"Solicito cotação dos capacitores conforme a especificação anexa (ref. {cod}).")
    linhas += ["", "Anexos: " + ", ".join(os.path.basename(a) for a in arqs if a), "", "Atenciosamente,", "Electric Service – Engenharia"]
    return "\n".join(linhas)
