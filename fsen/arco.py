"""Energia incidente (arco elétrico) do painel – IEEE 1584-2018 (REQ-SEG-007/009, NR-10 10.4.12).

Usa o módulo arcflash (IEEE 1584-2018, licença MIT, Li-aung Yip) já usado na Plataforma de Estudos – cópia em
fsen/terceiros/arcflash (não roda na pasta da Plataforma de Estudos). Calcula cenários lado a lado para mostrar ao cliente
quanto cada medida de projeto reduz a energia incidente:
  • terminais de entrada (lado de linha do disjuntor geral) – eliminado pela proteção A MONTANTE do cliente;
  • barramento geral (lado de carga do -Q0) – eliminado pelo disparo instantâneo do disjuntor geral do painel;
  • compartimento de estágio (após a chave-fusível NH gG) – eliminado pelo fusível limitador.
Distância de trabalho 455 mm (NR-10 Anexo IV); limite de 1,2 cal/cm² (5 J/cm²) = distância segura (glossário NR-10).
"""
from __future__ import annotations

import math
import os
import sys

from . import checagem as CK

_T = os.path.join(os.path.dirname(os.path.abspath(__file__)), "terceiros")
if _T not in sys.path:
    sys.path.insert(0, _T)

CATEGORIAS = [(1.2, "abaixo de 1,2 cal/cm² – distância segura (sem risco de queimadura de 2º grau)"), (4.0, "categoria 1 (≤ 4 cal/cm²)"),
              (8.0, "categoria 2 (≤ 8 cal/cm²)"), (25.0, "categoria 3 (≤ 25 cal/cm²)"), (40.0, "categoria 4 (≤ 40 cal/cm²)"),
              (1e9, "acima de 40 cal/cm² – PROIBIDO trabalho energizado")]


def categoria(E):
    return next(t for lim, t in CATEGORIAS if E <= lim)


def calcular(V_kV, Ibf_kA, T_ms, altura_mm=2200, largura_mm=1000, profundidade_mm=800, gap_mm=25.0, dist_mm=455.0, EC="VCB"):
    """Energia incidente (cal/cm²) e fronteira de arco (mm) – maior entre corrente de arco cheia e reduzida (IEEE 1584 §4.10)."""
    from arcflash.ieee_1584.calculation import Calculation
    from arcflash.ieee_1584.cubicle import Cubicle
    from arcflash.ieee_1584.units import kA, kV, ms, mm
    h, w, d = min(altura_mm, 1244.6), min(largura_mm, 1244.6), min(profundidade_mm, 1244.6)   # limites do modelo (§4.8)
    cub = Cubicle(V_oc=V_kV * kV, EC=EC, G=gap_mm * mm, D=dist_mm * mm, height=h * mm, width=w * mm, depth=d * mm)
    out = []
    for modo in ("full", "reduced"):
        c = Calculation(cub, Ibf_kA * kA, modo)
        c.calculate_I_arc()
        c.calculate_E_AFB(T_ms * ms)
        out.append(dict(modo=modo, I_arc_kA=float(c.I_arc.to("kA").magnitude), E=float(c.E.to("cal/cm**2").magnitude),
                        AFB_mm=float(c.AFB.to("mm").magnitude)))
    pior = max(out, key=lambda x: x["E"])
    return dict(E=pior["E"], AFB_mm=pior["AFB_mm"], I_arc_kA=pior["I_arc_kA"], casos=out, T_ms=T_ms, Ibf_kA=Ibf_kA)


def cenarios(ped, Icc_kA, gab=None, t_montante_ms=500.0, t_geral_ms=50.0, t_fusivel_ms=10.0):
    """Cenários do painel. t_montante_ms: tempo da proteção do cliente (não informado → 500 ms, conservador);
    t_geral_ms: disparo instantâneo do disjuntor geral (abertura + arco ≈ 50 ms); t_fusivel_ms: NH gG limitador (≤ ½ ciclo)."""
    V = ped.tensao_v / 1000
    dim = (gab or {}).get("dimensoes_mm") or {"altura": 2200, "largura": 1000, "profundidade": 800}
    larg_col = max((c["largura"] for c in (gab or {}).get("colunas", [])), default=1000)
    geo = dict(altura_mm=dim["altura"], largura_mm=larg_col, profundidade_mm=dim["profundidade"])
    Ibf = min(max(Icc_kA, 0.5), 106.0)
    L = []
    for nome, t, onde in (("Terminais de entrada (lado de linha do -Q0)", t_montante_ms, "proteção a montante do cliente"),
                          ("Barramento geral (lado de carga do -Q0)", t_geral_ms, "instantâneo do disjuntor geral do painel"),
                          ("Compartimento de estágio (após chave-fusível NH gG)", t_fusivel_ms, "fusível NH gG limitador")):
        r = calcular(V, Ibf, t, **geo)
        L.append(dict(local=nome, eliminacao=onde, **r, categoria=categoria(r["E"])))
    sem_geral = calcular(V, Ibf, t_montante_ms, **geo)                  # referência: painel SEM disjuntor geral (como antes)
    return dict(cenarios=L, sem_geral=sem_geral, t_montante_ms=t_montante_ms, Ibf_kA=Ibf, dist_mm=455.0)


def linhas_check(res_arco):
    """Linhas [local, eliminação, I arco, tempo, E, fronteira, categoria, check] para tabelas (Check: ≤1,2 APROVADO; ≤8 ATENÇÃO;
    >8 REPROVADO para trabalho energizado – o painel é para operar FECHADO; NR-10 exige desenergizar para intervir)."""
    out = []
    for c in res_arco["cenarios"]:
        st = CK.APROVADO if c["E"] <= 1.2 else (CK.ATENCAO if c["E"] <= 8 else CK.REPROVADO)
        out.append([c["local"], c["eliminacao"], f"{c['I_arc_kA']:.1f} kA", f"{c['T_ms']:.0f} ms", f"{c['E']:.2f} cal/cm²",
                    f"{c['AFB_mm']:.0f} mm", c["categoria"], CK.texto(st, c["E"] / 1.2 * 100)])
    return out


def etiqueta_pdf(arq, ped, cod, res_arco, versao=""):
    """Etiqueta de advertência de arco (porta do painel) – valores do pior cenário ACESSÍVEL com a porta aberta."""
    from reportlab.lib.pagesizes import landscape
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas
    c = canvas.Canvas(arq, pagesize=landscape((105 * mm, 148 * mm)))
    W, H = 148 * mm, 105 * mm
    pior = max(res_arco["cenarios"][:2], key=lambda x: x["E"])
    c.setFillColor("#f39c12"); c.rect(0, H - 22 * mm, W, 22 * mm, fill=1, stroke=0)
    c.setFillColor("black"); c.setFont("Helvetica-Bold", 20); c.drawCentredString(W / 2, H - 14 * mm, "ADVERTÊNCIA")
    c.setFont("Helvetica-Bold", 11); c.drawCentredString(W / 2, H - 20 * mm, "RISCO DE ARCO ELÉTRICO E CHOQUE – NR-10")
    y = H - 32 * mm
    for t, v in (("Tensão nominal", f"{ped.tensao_v:g} V CA"), ("Energia incidente (455 mm)", f"{pior['E']:.1f} cal/cm²"),
                 ("Fronteira de arco", f"{pior['AFB_mm'] / 1000:.2f} m"), ("Vestimenta mínima", pior["categoria"][:40]),
                 ("Icc presumida", f"{res_arco['Ibf_kA']:.1f} kA"), ("Base", "IEEE 1584-2018 – estudo do projeto " + cod)):
        c.setFont("Helvetica", 10); c.drawString(8 * mm, y, t); c.setFont("Helvetica-Bold", 10); c.drawRightString(W - 8 * mm, y, v)
        y -= 7 * mm
    c.setFont("Helvetica-Bold", 9)
    c.drawCentredString(W / 2, 8 * mm, "DESLIGAR O DISJUNTOR GERAL E BLOQUEAR ANTES DE ABRIR – ACESSO SOMENTE A AUTORIZADOS")
    c.setFont("Helvetica", 6); c.drawCentredString(W / 2, 3 * mm, f"Electric Service – Plataforma FSEN {versao}")
    c.save()
    return arq


MEDIDAS = [
    ("Disjuntor geral -Q0 no painel com manopla externa, intertravamento e cadeado", "barramento eliminado em ~50 ms em vez do tempo da proteção do cliente", "NR-10 10.4.1 / 10.6.5"),
    ("Fusíveis NH gG limitadores por estágio", "arco no estágio eliminado em ≤ ½ ciclo", "NR-10 10.6.5 (limitadores de corrente)"),
    ("Compartimento do barramento com policarbonato (forma 2b) e protetores de borne (IPXXB)", "arco não se propaga; nada vivo exposto com a porta aberta", "NR-10 10.6.1/10.6.2; NBR IEC 61439-2"),
    ("Operação e inspeção com a porta fechada (controlador, sinaleiros, comando na porta; janela de termografia opcional)", "elimina exposição na operação de rotina", "NR-10 10.7.7.1"),
    ("Torque especificado e marcado nas conexões (conferido no TAF)", "remove a causa nº 1 de arco: conexão frouxa", "boa prática / NBR IEC 61439-1 §11"),
    ("Pinos de aterramento temporário e indicador de presença de tensão", "desenergização segura", "NR-10 10.4.6 / 10.13"),
    ("Opcional: relé de detecção de arco óptico atuando no disjuntor a montante", "reduz também o arco nos terminais de entrada", "IEC TS 63107"),
]


def relatorio_pdf(arq, ped, cod, res_arco, versao=""):
    """Estudo de energia incidente do painel (cenários + medidas de redução), com Check."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    st = getSampleStyleSheet()
    doc = SimpleDocTemplate(arq, pagesize=landscape(A4), leftMargin=14 * mm, rightMargin=14 * mm, topMargin=12 * mm, bottomMargin=12 * mm,
                            title=f"Energia incidente {cod}")
    P = lambda t, s="BodyText": Paragraph(t, st[s])
    el = [P(f"Estudo de energia incidente do painel – {cod} – {getattr(ped, 'cliente', '')}", "Title"),
          P(f"IEEE 1584-2018 (módulo arcflash da Plataforma de Estudos) · {ped.tensao_v:g} V · Icc presumida {res_arco['Ibf_kA']:.1f} kA · "
            f"distância de trabalho 455 mm (NR-10 Anexo IV) · gap 25 mm · eletrodos verticais em caixa (VCB) · "
            f"tempo da proteção a montante adotado {res_arco['t_montante_ms']:.0f} ms (confirmar com o estudo de seletividade do cliente)."),
          Spacer(1, 4 * mm)]
    cab = ["Local", "Eliminado por", "I arco", "Tempo", "Energia", "Fronteira", "Categoria", "Check"]
    rows = [cab] + linhas_check(res_arco)
    t = Table([[P(str(x)) for x in r] for r in rows], colWidths=[52 * mm, 45 * mm, 18 * mm, 16 * mm, 24 * mm, 20 * mm, 58 * mm, 30 * mm])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#c8641e")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                           ("GRID", (0, 0), (-1, -1), 0.3, colors.grey), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    el += [t, Spacer(1, 3 * mm),
           P(f"<b>Ganho do disjuntor geral no painel:</b> sem ele, o barramento interno dependeria da proteção do cliente "
             f"({res_arco['sem_geral']['E']:.1f} cal/cm²); com ele, {res_arco['cenarios'][1]['E']:.1f} cal/cm²."),
           P("Check: APROVADO ≤ 1,2 cal/cm² (distância segura); ATENÇÃO ≤ 8 cal/cm²; REPROVADO acima – trabalho energizado não "
             "permitido nesse ponto (NR-10: desenergizar e bloquear antes de abrir)."), Spacer(1, 4 * mm), P("<b>Medidas de projeto aplicadas</b>")]
    t2 = Table([[P("Medida"), P("Efeito"), P("Norma")]] + [[P(a), P(b), P(c)] for a, b, c in MEDIDAS], colWidths=[110 * mm, 100 * mm, 52 * mm])
    t2.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.3, colors.grey), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eeeeee"))]))
    el += [t2, Spacer(1, 3 * mm), P(f"Electric Service – Plataforma FSEN {versao}")]
    doc.build(el)
    return arq
