"""Filtro senoidal ABERTO em base de montagem (IP00) para instalação no painel do cliente – v1.35.0 (REQ-SEN-030).

Engenheiro (26/11/2026 21:08): "os filtros senoidais quando vendidos acredito que são abertos, tem sobre uma base metálica para
fixação dos equipamentos ... depois o cliente instala em painel ... consegue projetar essa base metálica com base nos outros
fabricantes? consegue fazer o projeto dela para o montador fazer".

O que os fabricantes fazem nessa faixa (fontes no relatório de instalação):
  • TDK B84143V*R227: IP00 de 132 A a 320 A; caixa IP21 vendida à parte (B84143Q…R229); convecção natural, respeitar a
    posição de montagem; fiação inversor → filtro < 10 m.
  • Block SFB 400/250: IP00, "Bauart offen", fixação por cantoneira (pé) M10, "nur für stehende Montage", 40 °C.
  • Danfoss (VLT sine-wave): IP00 e IP20 em toda a faixa; acima de 75 A montagem no piso; convecção natural; 45 °C.
  • MTE SineWave Guardian: "open panel/modular" para montagem dentro do invólucro do cliente (folga 4" lateral e 6" vertical)
    ou armário NEMA 1/3R; perdas do filtro entram no cálculo térmico do painel do cliente.
→ O padrão do mercado é o filtro ABERTO; o armário próprio é opção. A plataforma passa a gerar as DUAS formas: (A) aberto em
  base de montagem, com o projeto da base para o montador e o guia de instalação para o cliente; (B) em caixa (o projeto atual).

Base (padrão Electric): chapa de aço SAE 1020 de 6,35 mm (1/4"), plana – só corte laser e furação –, indutor em pé
sobre a base pelos 4 oblongos do quadro inferior (M12), capacitores verticais pelo pino M12 do próprio capacitor, bornes X1/X2 em
trilho DIN na faixa da frente, barra PE com parafuso M12 de aterramento, 6 furos Ø13 de fixação no painel do cliente.
"""
from __future__ import annotations

import math
import os

ESP = 6.35          # chapa da base (mm) – 1/4", plana (só corte laser e furação, sem dobra)
ABA = 0.0           # sem abas (base plana apoiada na placa/trilhos do painel do cliente)
MARG = 40.0         # margem às bordas
FAIXA = 130.0       # faixa da frente (bornes e capacitores)
FOLGA_CABO = 70.0   # entre a faixa da frente e a frente do indutor (curvatura dos cabos)
FAIXA_FUNDO = 50.0  # atrás do indutor: barra PE e bornes X3 (PTC)
RS_KG = 32.0        # custo estimado da base fabricada (corte laser + furação + galvanização) por kg – ESTIMATIVA
RS_SETUP = 150.0

FONTES = [
    ("TDK B84143V*R227 – Sine output filters (datasheet, versão 2020-06), p.2/p.15",
     "https://www.tdk-electronics.tdk.com/inf/30/db/emc_2014_d/B84143V_R227.pdf",
     "IP00 de 132 A a 320 A; sem refrigeração adicional; montar sem prejudicar a convecção natural; respeitar a posição de montagem; "
     "fiação inversor → filtro < 10 m"),
    ("TDK B84143Q…R229 – IP21 housings (versão 2020-06), p.14/p.19",
     "https://www.tdk-electronics.tdk.com/inf/30/db/emc_2014_d/B84143Q_R229_IP21_Housings.pdf",
     "Caixa IP21 vendida como ACESSÓRIO do filtro aberto; acima de 130 A só montagem horizontal"),
    ("Block SFB 400/250 – Datenblatt", "https://www.block.eu/en_EN/productversion/sfb-400250",
     "IP00, construção aberta, fixação por cantoneira M10, só montagem em pé, 40 °C"),
    ("Danfoss VLT Sine-wave filters – Design Guide MG.90.N1.02, p.11/p.22/p.25",
     "https://files.danfoss.com/test/Drives/doc_MG90N102.pdf",
     "IP00 e IP20 em toda a faixa; piso acima de 75 A; convecção natural; 45 °C; montagem vertical; longe de fontes de calor"),
    ("MTE SineWave Guardian – Technical Reference Manual SWG-TRM-E rev. 007 (12/2024), p.4/p.5/p.23",
     "https://mtecorp.com/wp-content/uploads/SWG-TRM-E_Web.pdf",
     "Open panel/modular para montar DENTRO do invólucro do cliente (folga 4\" lateral e 6\" vertical) ou NEMA 1/3R; incluir as perdas "
     "do filtro no cálculo térmico do painel; capacitores na região mais fria; filtro o mais perto possível do inversor"),
]


def forma(ped):
    """v1.36.0 (REQ-SEN-031, engenheiro: "Sugestão A"): padrão = ABERTO em base; caixa só se o cliente pedir.
    Pedido explícito (forma_fornecimento) vale; senão, IP informado ≥ IP20 ou instalação em gabinete próprio → caixa."""
    g = (lambda k, d=None: ped.get(k, d) if isinstance(ped, dict) else getattr(ped, k, d))
    f = str(g("forma_fornecimento", "") or "").lower()
    if f in ("aberto", "caixa"):
        return f
    inf = g("informados", None) or []
    ip = str(g("ip", "") or "").upper().replace(" ", "")
    inst = str(g("instalacao", "") or "").lower()
    if ("ip" in inf and ip not in ("", "IP00", "IP10")) or any(k in inst for k in ("ao tempo", "gabinete", "armário", "armario", "caixa")):
        return "caixa"
    return "aberto"


def _dict(c):
    """Componente do arranjo como dict (no pipeline é Caixa2D; no JSON salvo é dict)."""
    if isinstance(c, dict):
        return c
    from dataclasses import asdict, is_dataclass
    return asdict(c) if is_dataclass(c) else dict(vars(c))


def _comps(arr):
    return [_dict(c) for c in (getattr(arr, "componentes", None) or [])]


def _comp(arr, tag):
    return next((c for c in _comps(arr) if c.get("tag") == tag), None)


def _ind_geo(ind):
    """Envelope e oblongos dos pés do indutor a partir do MESMO modelo do STEP/DXF enviado ao fabricante."""
    try:
        from . import ind_cad as IC
        g = IC.geo_mm(ind)
        pc = IC.pecas_3d(ind)
        pts = [q for _, fs, _ in pc for f, _h in fs for q in f]
        mn = [min(q[k] for q in pts) for k in range(3)]
        mx = [max(q[k] for q in pts) for k in range(3)]
        pes = [f[0] for f in g["est"]["furos"] if str(f[3]).startswith("oblongo")]
        return dict(x0=mn[0], x1=mx[0], y0=mn[1], y1=mx[1], h=mx[2] - mn[2], pes=[(p[0], p[1]) for p in pes])
    except Exception:
        return None


def layout(proj, arr, ind=None):
    L1 = _comp(arr, "L1") or {"w": 550, "d": 350, "h": 370}
    caps = [c for c in _comps(arr) if str(c.get("tag", "")).startswith("C")]
    x1 = _comp(arr, "X1") or {"w": 210, "h": 90, "d": 120}
    gi = _ind_geo(ind) if ind else None
    wL = (gi["x1"] - gi["x0"]) if gi else float(L1["w"])
    dL = (gi["y1"] - gi["y0"]) if gi else float(L1["d"])
    hL = gi["h"] if gi else float(L1["h"])
    dcap = float(caps[0]["w"]) if caps else 63.5
    hcap = float(caps[0]["h"]) if caps else 112.0
    passo_cap = dcap + 40
    larg_faixa = 2 * float(x1["w"]) + len(caps) * passo_cap + 4 * MARG
    L = math.ceil(max(wL + 2 * MARG, larg_faixa) / 50) * 50        # múltiplo de 50 mm (chapa padrão e cotas redondas)
    P = math.ceil((MARG + FAIXA + FOLGA_CABO + dL + FAIXA_FUNDO + MARG) / 50) * 50
    # indutor: frente (saídas, y mínimo do modelo) virada para a faixa dos bornes
    xi = (L - wL) / 2
    yi = MARG + FAIXA + FOLGA_CABO
    furos = []          # (x, y, diam, descr)
    if gi:
        for (px, py) in gi["pes"]:
            furos.append((xi + (px - gi["x0"]), yi + (py - gi["y0"]), 13.0, "M12 – pé do indutor (oblongo 14×25 no quadro)"))
    else:
        for fx in (xi + 30, xi + wL - 30):
            for fy in (yi + dL * 0.23, yi + dL * 0.77):
                furos.append((fx, fy, 13.0, "M12 – pé do indutor"))
    # capacitores: pino M12 do próprio capacitor, centrados na faixa da frente
    yc = MARG + FAIXA / 2
    xc0 = L / 2 - (len(caps) - 1) * passo_cap / 2
    pos_caps = []
    for k, c in enumerate(caps):
        x = xc0 + k * passo_cap
        pos_caps.append((x, yc, c.get("tag", f"C{k + 1}")))
        furos.append((x, yc, 12.5, f"M12 – pino do capacitor {c.get('tag', '')}"))
    # trilhos DIN dos bornes X1 (esquerda) e X2 (direita): 2 furos Ø6,5 (M6) por trilho
    wX = float(x1["w"])
    trilhos = [("X1", MARG, yc, wX), ("X2", L - MARG - wX, yc, wX)]
    for tag, x, y, w in trilhos:
        for fx in (x + 15, x + w - 15):
            furos.append((fx, y, 6.5, f"M6 – trilho DIN 35 dos bornes {tag}"))
    # X3 (PTC/auxiliar) atrás à direita, barra PE atrás à esquerda
    y_fundo = yi + dL + FAIXA_FUNDO / 2 + 5
    x3 = (L - MARG - 160, y_fundo, 160)
    for fx in (x3[0] + 15, x3[0] + x3[2] - 15):
        furos.append((fx, x3[1], 6.5, "M6 – trilho DIN dos bornes X3 (PTC TH1/TH2)"))
    pe = (MARG, y_fundo, 140)
    for fx in (pe[0] + 20, pe[0] + pe[2] - 20):
        furos.append((fx, pe[1], 10.5, "M10 – barra PE (cobre) direto na base"))
    furos.append((pe[0] + pe[2] / 2, pe[1], 13.0, "M12 – parafuso de aterramento do conjunto (cliente)"))
    # fixação no painel do cliente: 6 × Ø13 (cantos + meio)
    fix = [(25, 25), (L - 25, 25), (L / 2, 25), (25, P - 25), (L - 25, P - 25), (L / 2, P - 25)]
    for fx, fy in fix:
        furos.append((fx, fy, 13.0, "Ø13 – fixação da base no painel do cliente (M12)"))
    massa_base = L * P * ESP * 7.85e-6
    m_ind = float(getattr(proj.l1, "massa_kg", 0) or 0) + (float(proj.l2.massa_kg) if getattr(proj, "l2", None) else 0)
    m_caps = len(caps) * 0.8
    massa_conj = massa_base + m_ind + m_caps + 6.0
    return dict(L=L, P=P, esp=ESP, aba=ABA, xi=xi, yi=yi, wL=wL, dL=dL, hL=hL, caps=pos_caps, dcap=dcap, hcap=hcap,
                trilhos=trilhos, x3=x3, pe=pe, furos=furos, fix=fix, massa_base=round(massa_base, 1),
                massa_conj=round(massa_conj, 0), altura_conj=round(ESP + max(hL, hcap + 20), 0), geo_ind=bool(gi),
                custo_base=round(massa_base * RS_KG + RS_SETUP, -1))


# ------------------------------------------------------------------------------------------------------------- desenho
def desenho_pdf(b, cod, arq, cliente=""):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Circle, Rectangle
    fig = plt.figure(figsize=(16.54, 11.69))         # A3 paisagem
    ax = fig.add_axes([0.03, 0.18, 0.62, 0.78])
    L, P = b["L"], b["P"]
    ax.add_patch(Rectangle((0, 0), L, P, fill=False, lw=1.6))
    ax.add_patch(Rectangle((b["xi"], b["yi"]), b["wL"], b["dL"], fill=True, fc="#dfe6f0", ec="#7a8ca8", lw=0.8))
    ax.text(b["xi"] + b["wL"] / 2, b["yi"] + b["dL"] / 2, "INDUTOR L1\n(projeção)\nsaídas para a frente", ha="center", va="center", fontsize=8,
            color="#44546a")
    for (x, y, tag) in b["caps"]:
        ax.add_patch(Circle((x, y), b["dcap"] / 2, fill=True, fc="#f6e3b5", ec="#b8862b", lw=0.7))
        ax.text(x, y + b["dcap"] / 2 + 8, tag, ha="center", fontsize=7)
    for tag, x, y, w in b["trilhos"]:
        ax.add_patch(Rectangle((x, y - 17.5), w, 35, fill=True, fc="#eeeeee", ec="#888", lw=0.6))
        ax.text(x + w / 2, y - 30, f"{tag} – trilho DIN 35 (bornes)", ha="center", fontsize=7)
    x3 = b["x3"]
    ax.add_patch(Rectangle((x3[0], x3[1] - 17.5), x3[2], 35, fill=True, fc="#eeeeee", ec="#888", lw=0.6))
    ax.text(x3[0] + x3[2] / 2, x3[1] - 30, "X3 – PTC TH1/TH2", ha="center", fontsize=7)
    pe = b["pe"]
    ax.add_patch(Rectangle((pe[0], pe[1] - 12), pe[2], 24, fill=True, fc="#cfe3c0", ec="#5b8a3c", lw=0.6))
    ax.text(pe[0] + pe[2] / 2, pe[1] - 26, "Barra PE Cu", ha="center", fontsize=7)
    for (x, y, d, _) in b["furos"]:
        ax.add_patch(Circle((x, y), d / 2, fill=False, lw=0.8, color="k"))
    # cotas gerais
    ax.annotate("", (0, -45), (L, -45), arrowprops=dict(arrowstyle="<->", lw=0.8))
    ax.text(L / 2, -60, f"{L:.0f}", ha="center", va="top", fontsize=10)
    ax.annotate("", (-45, 0), (-45, P), arrowprops=dict(arrowstyle="<->", lw=0.8))
    ax.text(-60, P / 2, f"{P:.0f}", ha="right", va="center", rotation=90, fontsize=10)
    ax.text(L / 2, P + 30, "VISTA SUPERIOR – FRENTE PARA BAIXO (bornes X1 entrada do inversor à esquerda, X2 saída ao motor à direita)",
            ha="center", fontsize=9, weight="bold")
    ax.set_xlim(-140, L + 60)
    ax.set_ylim(-140, P + 70)
    ax.set_aspect("equal")
    ax.axis("off")
    # vista frontal (perfil da chapa e alturas)
    af = fig.add_axes([0.03, 0.03, 0.62, 0.14])
    af.add_patch(Rectangle((0, 0), L, ESP, fc="#999", ec="k", lw=0.6))
    for xx in (0, L - ESP):
        pass
    af.add_patch(Rectangle((b["xi"], ESP), b["wL"], b["hL"], fill=False, ec="#7a8ca8", lw=0.8, ls="--"))
    for (x, y, tag) in b["caps"]:
        af.add_patch(Rectangle((x - b["dcap"] / 2, ESP), b["dcap"], b["hcap"], fill=False, ec="#b8862b", lw=0.7))
    af.text(L + 20, ESP + b["hL"] / 2, f"altura do conjunto ≈ {b['altura_conj']:.0f} mm", fontsize=8, va="center")
    af.text(L / 2, -40, f"VISTA FRONTAL – chapa plana {ESP} mm (1/4\"), sem dobras",
            ha="center", fontsize=8)
    af.set_xlim(-140, L + 400)
    af.set_ylim(-70, b["hL"] + 40)
    af.set_aspect("equal")
    af.axis("off")
    # tabela de furos e notas
    at = fig.add_axes([0.67, 0.03, 0.31, 0.94])
    at.axis("off")
    tipos = {}
    for (x, y, d, desc) in b["furos"]:
        tipos.setdefault((d, desc), []).append((x, y))
    linhas = [f"BASE DE MONTAGEM – FILTRO SENOIDAL {cod}", f"Cliente: {cliente}", "",
              "TABELA DE FUROS (origem: canto frente-esquerda, mm)"]
    for (d, desc), pts in tipos.items():
        linhas.append(f"• {len(pts)}× Ø{d:g} – {desc}")
        for (x, y) in pts:
            linhas.append(f"    X {x:7.1f}   Y {y:7.1f}")
    linhas += ["", "NOTAS PARA O MONTADOR",
               f"1. Chapa aço SAE 1020 #{ESP} mm (1/4\"), plana, corte laser + furação (sem dobra, sem solda).",
               "2. Tolerâncias ISO 2768-m; furos ±0,2 mm; planicidade ≤ 1 mm/m; rebarbas removidas.",
               "3. Galvanização a fogo (NBR 6323) ou zincado + epóxi-pó RAL 7035;",
               "   área da barra PE e do parafuso de terra SEM pintura.",
               "4. Indutor: 4× parafuso M12 classe 8.8 + arruelas lisa e de pressão, 70 N·m.",
               "5. Capacitores: pelo pino M12 do capacitor, porca dentada, 10 N·m (datasheet TDK).",
               "6. Trilhos DIN 35×15 com parafuso M6 + porca, bornes X1/X2 dimensionados no esquema.",
               "7. Barra PE Cu estanhado na chapa (M10, 40 N·m);",
               "   parafuso M12 de aterramento para o PE do cliente.",
               f"8. Massa da base ≈ {b['massa_base']:.0f} kg; conjunto montado ≈ {b['massa_conj']:.0f} kg.",
               "9. Içar o conjunto com cintas sob a base (nunca pelos bornes ou capacitores).",
               "10. Furos Ø13 de fixação: 6 pontos no painel do cliente (M12).",
               "11. Indutor SEMPRE em pé (base horizontal) –",
               "    convecção natural (TDK, Block, Danfoss).",
               "", "Electric Service – desenho gerado pela Plataforma FSEN (REQ-SEN-030)"]
    at.text(0, 1, "\n".join(linhas), va="top", fontsize=7.2, family="monospace")
    fig.savefig(arq)
    plt.close(fig)
    return arq


def desenho_dxf(b, arq):
    try:
        import ezdxf
    except Exception:
        return None
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()
    L, P = b["L"], b["P"]
    msp.add_lwpolyline([(0, 0), (L, 0), (L, P), (0, P), (0, 0)], dxfattribs={"layer": "CORTE"})
    for (x, y, d, desc) in b["furos"]:
        msp.add_circle((x, y), d / 2, dxfattribs={"layer": "FUROS"})
    msp.add_lwpolyline([(b["xi"], b["yi"]), (b["xi"] + b["wL"], b["yi"]), (b["xi"] + b["wL"], b["yi"] + b["dL"]),
                        (b["xi"], b["yi"] + b["dL"]), (b["xi"], b["yi"])], dxfattribs={"layer": "REFERENCIA_INDUTOR"})
    msp.add_text(f"BASE {L:.0f}x{P:.0f} chapa plana {ESP} mm", dxfattribs={"height": 12, "layer": "TEXTO"}).set_placement((0, P + 30))
    doc.saveas(arq)
    return arq


# ------------------------------------------------------------------------------------------------------------- documentos
def preco_opcao_aberta(proj, orc, cat, b):
    """Preço da forma (A): troca caixa, ventiladores, grelhas e termostato de ventilação pela base de montagem."""
    from .custos import ItemBOM, formar_preco
    itens = [i for i in orc.itens if i.grupo != "CAIXA" and i.tag not in ("TH",)]
    itens.append(ItemBOM(len(itens) + 1, "CAIXA", "Montadora", "Base de montagem aberta (IP00) – projeto Electric",
                         f"Chapa SAE 1020 {ESP} mm {b['L']:.0f}×{b['P']:.0f} mm plana, galvanizada – ESTIMATIVA "
                         f"({b['massa_base']:.0f} kg)", 1, "pç", b["custo_base"], "Montadora", "BASE"))
    return formar_preco(proj, itens, cat)


def guia_instalacao(proj, arr, b, pasta, cod, novo, tabela, bullets, cat):
    os.makedirs(pasta, exist_ok=True)
    d = novo("Guia de Instalação – Filtro Senoidal Aberto (IP00)", f"{cod} – montagem no painel do cliente", proj, cat)
    perdas = float(getattr(arr, "perda_total_w", 0) or 0)
    vaz = 3.1 * perdas / 10.0
    d.add_heading("1. Forma de fornecimento", 1)
    d.add_paragraph("Filtro senoidal ABERTO (IP00): indutor, capacitores, bornes e barra de terra montados e interligados sobre uma base "
                    "metálica, para instalação DENTRO do painel do cliente – é a forma padrão dos fabricantes internacionais nesta faixa de "
                    "corrente (TDK, Block, Danfoss, MTE). O armário próprio é opcional.")
    tabela(d, ["Item", "Valor"], [
        ("Base (L × P)", f"{b['L']:.0f} × {b['P']:.0f} mm, chapa {ESP} mm, 6 furos Ø13 (M12) de fixação"),
        ("Altura do conjunto", f"≈ {b['altura_conj']:.0f} mm"),
        ("Massa do conjunto", f"≈ {b['massa_conj']:.0f} kg"),
        ("Perdas a dissipar no painel do cliente", f"≈ {perdas:.0f} W (carga nominal, fs de projeto)"),
        ("Ar de ventilação necessário no painel", f"≈ {vaz:.0f} m³/h para elevação de 10 K (Q = 3,1·P/ΔT)"),
        ("Temperatura do ar no local do filtro", "≤ 50 °C (projeto térmico do indutor e dos capacitores)"),
    ], [6, 11])
    d.add_heading("2. Onde e como instalar", 1)
    bullets(d, [
        "Somente em local abrigado, dentro de painel/invólucro que dê a proteção contra contato direto (IP00 → o painel do cliente "
        "deve garantir no mínimo IPXXB com a porta aberta ou barreiras) – não instalar ao tempo.",
        "Base na HORIZONTAL e indutor em pé (convecção natural). Não montar deitado nem de cabeça para baixo (Block: 'só montagem em pé'; "
        "TDK: respeitar a posição de montagem).",
        "Folgas livres em volta do conjunto: ≥ 100 mm nas laterais e ≥ 150 mm acima e abaixo (guia MTE para filtros abertos); não "
        "bloquear a passagem de ar entre as bobinas.",
        "Não instalar acima de resistores de frenagem, inversores ou outras fontes de calor; capacitores na região mais fria do painel.",
        f"Incluir os {perdas:.0f} W do filtro no cálculo térmico do painel (ventilação forçada ou trocador de calor).",
        "Filtro o mais perto possível do inversor (TDK: fiação inversor → filtro < 10 m).",
        "Aterramento: ligar o parafuso M12 de terra da base ao PE do painel antes de energizar (corrente de fuga dos capacitores).",
        "Capacitores guardam carga: esperar a descarga (resistores) e medir antes de tocar. A superfície do indutor fica quente.",
        "Proteção térmica: ligar os bornes TH1/TH2 (PTC 160 °C) à entrada de termistor do inversor ou a um relé de PTC.",
    ])
    d.add_heading("3. Fontes consultadas (fabricantes)", 1)
    tabela(d, ["Documento", "O que diz", "Link"], [(t, o, l) for t, l, o in FONTES], [5, 7, 5], tam=7)
    arq = os.path.join(pasta, f"Guia_Instalacao_Filtro_Aberto_{cod}.docx")
    d.save(arq)
    return arq


def et_base(proj, b, pasta, cod, novo, tabela, bullets, cat, anexos=()):
    os.makedirs(pasta, exist_ok=True)
    d = novo("ET – Base de Montagem do Filtro Senoidal", f"{cod} – fabricação e montagem (montadora)", proj, cat)
    d.add_heading("1. Objeto", 1)
    d.add_paragraph("Fabricar a base metálica e montar sobre ela o indutor L1, os capacitores, os bornes X1/X2/X3 e a barra PE, "
                    "conforme o desenho anexo. O conjunto é entregue aberto (IP00) para instalação no painel do cliente.")
    tabela(d, ["Item", "Especificação"], [
        ("Material", f"Chapa aço SAE 1020, {ESP} mm (1/4\"), plana"),
        ("Dimensões", f"{b['L']:.0f} × {b['P']:.0f} mm – só corte laser e furação (sem dobra, sem solda)"),
        ("Furação", f"{len(b['furos'])} furos conforme tabela do desenho (origem no canto frente-esquerda)"),
        ("Tolerâncias", "ISO 2768-m; furos ±0,2 mm; planicidade ≤ 1 mm/m"),
        ("Acabamento", "Galvanização a fogo (NBR 6323) ou zincado + epóxi-pó RAL 7035; área do PE sem pintura"),
        ("Fixações", "Indutor 4× M12 8.8 (70 N·m); capacitores pino M12 (10 N·m); PE M10 (40 N·m); trilhos M6"),
        ("Massa", f"Base ≈ {b['massa_base']:.0f} kg; conjunto ≈ {b['massa_conj']:.0f} kg"),
        ("Cabos internos", "Conforme lista de cabos (força fora de canaleta, espaçados – NBR IEC 61439-1 Anexo H)"),
        ("Inspeção", "Conferência dimensional, torque marcado, continuidade do PE ≤ 0,1 Ω, fotos do conjunto"),
        ("Preço de referência", f"≈ R$ {b['custo_base']:,.0f} a base (ESTIMATIVA – cotar)".replace(",", ".")),
    ], [4, 13])
    if anexos:
        d.add_heading("2. Anexos", 1)
        bullets(d, [os.path.basename(a) for a in anexos if a])
    arq = os.path.join(pasta, f"ET_Base_Montagem_{cod}.docx")
    d.save(arq)
    return arq


def gerar(proj, arr, orc, cat, ind, sub, cod, novo, tabela, bullets, log=print):
    """Gera o pacote da forma (A) – aberto em base: desenho PDF/DXF + ET para a montadora + guia de instalação para o cliente."""
    b = layout(proj, arr, ind)
    p_mont = os.path.join(sub["04_Montadora"], "4_Base_Montagem")
    os.makedirs(p_mont, exist_ok=True)
    pdf = desenho_pdf(b, cod, os.path.join(p_mont, f"Base_Montagem_{cod}.pdf"), proj.pedido.get("cliente", ""))
    dxf = desenho_dxf(b, os.path.join(p_mont, f"Base_Montagem_{cod}.dxf"))
    et = et_base(proj, b, p_mont, cod, novo, tabela, bullets, cat, anexos=[pdf, dxf])
    guia = guia_instalacao(proj, arr, b, os.path.join(sub["02_Cliente"], "5_Instalacao"), cod, novo, tabela, bullets, cat)
    try:
        orc_a = preco_opcao_aberta(proj, orc, cat, b)
    except Exception as e:
        log(f"   Base: preço da forma aberta não calculado ({e})")
        orc_a = None
    log(f"   Forma (A) aberta em base: base {b['L']:.0f}×{b['P']:.0f} mm, conjunto ≈ {b['massa_conj']:.0f} kg"
        + (f", preço unit. R$ {orc_a.preco_unit:,.0f}" if orc_a else ""))
    return dict(base=b, pdf=pdf, dxf=dxf, et=et, guia=guia, orc=orc_a)
