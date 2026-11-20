"""Desenhos do PROJETO DE REFERÊNCIA do indutor (folhas A3): vistas, cortes, detalhes, 3D, lista de materiais (v1.10.0).
O fabricante emite o desenho de fabricação próprio a partir deste, declarando as diferenças."""
import math
import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.patches import Rectangle, FancyBboxPatch, Polygon

A3 = (16.54, 11.69)
COR = dict(ferro="#9aa5b1", gap="#d62728", bob="#d58b3a", isol="#f1e3a0", aco="#555555", cu="#b87333", txt="#111111")


def _mm(d):
    """Dimensões principais em mm a partir do dicionário de projeto (SI)."""
    g = {k: d[k] * 1e3 for k in ("a", "b", "hw", "ww", "c", "build", "hc", "hf", "tf", "tube", "wrap", "wd")}
    g["N"], g["nd"], g["ng"] = d["N"], d["nd"], d["ng"]
    g["gaps"] = [x * 1e3 for x in d["gaps"]]
    g["W"] = 3 * g["a"] + 2 * g["ww"]
    g["H"] = 2 * g["a"] + g["hw"]
    g["Dc"] = g["a"] + 2 * (g["c"] + g["build"])          # largura externa da bobina (plano x)
    g["Ec"] = g["b"] + 2 * (g["c"] + g["build"])          # profundidade externa da bobina (plano z)
    g["fr_h"] = 50.0                                      # altura da cantoneira de aperto
    g["base_h"] = 60.0
    return g


def _carimbo(fig, titulo, folha, info):
    ax = fig.add_axes([0.0, 0.0, 1, 1], zorder=-1)
    ax.set_xlim(0, 420)
    ax.set_ylim(0, 297)
    ax.axis("off")
    ax.add_patch(Rectangle((10, 10), 400, 277, fill=False, lw=1.2))
    x0, y0 = 250, 10
    ax.add_patch(Rectangle((x0, y0), 160, 38, fill=False, lw=1.0))
    for yy in (y0 + 10, y0 + 20, y0 + 29):
        ax.plot([x0, x0 + 160], [yy, yy], lw=0.5, color="k")
    ax.text(x0 + 2, y0 + 31.5, "ELECTRIC SERVICE – Engenharia", fontsize=8.5, weight="bold")
    ax.text(x0 + 2, y0 + 22.5, titulo, fontsize=7.5)
    ax.text(x0 + 2, y0 + 13, info.get("linha2", ""), fontsize=6.5)
    ax.text(x0 + 2, y0 + 3, f"Folha {folha}  |  {info.get('cod', '')}  |  Rev. 00  |  {info.get('data', '')}  |  {info.get('versao', '')}",
            fontsize=6.3)
    ax.text(14, 14, "PROJETO DE REFERÊNCIA – o fabricante emite o desenho de fabricação próprio e declara as diferenças. "
                    "Medidas em mm. Não medir no desenho.", fontsize=6.5, style="italic")
    return ax


def _cota(ax, p1, p2, txt, off=8, vertical=False, fs=6.5):
    (x1, y1), (x2, y2) = p1, p2
    if vertical:
        x = max(x1, x2) + off
        ax.annotate("", (x, y1), (x, y2), arrowprops=dict(arrowstyle="<->", lw=0.6))
        ax.plot([x1, x], [y1, y1], lw=0.3, color="k")
        ax.plot([x2, x], [y2, y2], lw=0.3, color="k")
        ax.text(x + 2, (y1 + y2) / 2, txt, fontsize=fs, rotation=90, va="center")
    else:
        y = min(y1, y2) - off
        ax.annotate("", (x1, y), (x2, y), arrowprops=dict(arrowstyle="<->", lw=0.6))
        ax.plot([x1, x1], [y1, y], lw=0.3, color="k")
        ax.plot([x2, x2], [y2, y], lw=0.3, color="k")
        ax.text((x1 + x2) / 2, y - 3.5, txt, fontsize=fs, ha="center")


def vista_frontal(ax, g):
    a, ww, hw, H, W = g["a"], g["ww"], g["hw"], g["H"], g["W"]
    # base e cantoneiras
    ax.add_patch(Rectangle((-30, -g["fr_h"] - g["base_h"]), W + 60, g["base_h"], fc="#cfcfcf", ec="k", lw=0.6))
    ax.add_patch(Rectangle((-15, -g["fr_h"]), W + 30, g["fr_h"], fc="#bdbdbd", ec="k", lw=0.6))
    ax.add_patch(Rectangle((-15, H), W + 30, g["fr_h"], fc="#bdbdbd", ec="k", lw=0.6))
    # núcleo
    ax.add_patch(Rectangle((0, 0), W, H, fc=COR["ferro"], ec="k", lw=0.8))
    for i in range(2):
        x0 = a + i * (a + ww)
        ax.add_patch(Rectangle((x0, a), ww, hw, fc="white", ec="k", lw=0.6))
    # bobinas (na frente das colunas)
    for i in range(3):
        xc = a / 2 + i * (a + ww)
        y0 = a + (hw - g["hc"]) / 2
        ax.add_patch(FancyBboxPatch((xc - g["Dc"] / 2, y0), g["Dc"], g["hc"], boxstyle="round,pad=0,rounding_size=12",
                                    fc=COR["bob"], ec="k", lw=0.7, alpha=0.9))
        ax.text(xc, y0 + g["hc"] / 2, "UVW"[i], ha="center", va="center", fontsize=11, weight="bold", color="white")
        # terminais em cima
        for s, lab in ((-1, "1"), (1, "2")):
            xt = xc + s * g["Dc"] / 4
            ax.add_patch(Rectangle((xt - 20, y0 + g["hc"]), 40, H + g["fr_h"] + 35 - (y0 + g["hc"]), fc=COR["cu"], ec="k", lw=0.5))
            ax.add_patch(plt.Circle((xt, H + g["fr_h"] + 22), 6.5, fc="white", ec="k", lw=0.5))
            ax.text(xt, H + g["fr_h"] + 42, "UVW"[i] + lab, ha="center", fontsize=6.5)
    # tirantes verticais (fora do núcleo)
    for x in (-8, W + 8):
        ax.plot([x, x], [-g["fr_h"], H + g["fr_h"]], color=COR["aco"], lw=2.2)
    _cota(ax, (0, -g["fr_h"] - g["base_h"]), (W, -g["fr_h"] - g["base_h"]), f"{W:.0f} (núcleo)", off=10)
    _cota(ax, (W + 30, 0), (W + 30, H), f"{H:.0f} (núcleo)", off=12, vertical=True)
    _cota(ax, (a, a + hw), (a + ww, a + hw), f"janela {ww:.0f}", off=-hw - 6)
    _cota(ax, (W, a), (W, a + hw), f"{hw:.0f}", off=50, vertical=True)
    ax.set_title("VISTA FRONTAL", fontsize=8.5, weight="bold")


def vista_superior(ax, g):
    a, ww, b, W = g["a"], g["ww"], g["b"], g["W"]
    ax.add_patch(Rectangle((-30, -b / 2 - 70), W + 60, b + 140, fc="#e6e6e6", ec="k", lw=0.5))   # base (pés)
    for x in (-20, W + 20):
        for y in (-b / 2 - 55, b / 2 + 55):
            ax.add_patch(FancyBboxPatch((x - 12, y - 7), 24, 14, boxstyle="round,pad=0,rounding_size=7", fc="white", ec="k", lw=0.5))
    ax.add_patch(Rectangle((0, -b / 2), W, b, fc=COR["ferro"], ec="k", lw=0.8))
    for i in range(3):
        xc = a / 2 + i * (a + ww)
        ax.add_patch(FancyBboxPatch((xc - g["Dc"] / 2, -g["Ec"] / 2), g["Dc"], g["Ec"], boxstyle="round,pad=0,rounding_size=14",
                                    fc=COR["bob"], ec="k", lw=0.7, alpha=0.9))
        ax.add_patch(Rectangle((xc - a / 2, -b / 2), a, b, fc=COR["ferro"], ec="k", lw=0.5))
    _cota(ax, (0, -b / 2 - 70), (W, -b / 2 - 70), f"{W:.0f}", off=8)
    _cota(ax, (W + 40, -g["Ec"] / 2), (W + 40, g["Ec"] / 2), f"bobina {g['Ec']:.0f}", off=6, vertical=True)
    _cota(ax, (W + 40, -b / 2), (W + 40, b / 2), f"empilh. {b:.0f}", off=30, vertical=True)
    ax.text(W / 2, b / 2 + 85, "Furos de fixação Ø14 × 25 (oblongo) – 4×", ha="center", fontsize=6.5)
    ax.set_title("VISTA SUPERIOR", fontsize=8.5, weight="bold")


def vista_lateral(ax, g):
    a, b, H, hw = g["a"], g["b"], g["H"], g["hw"]
    ax.add_patch(Rectangle((-b / 2 - 70, -g["fr_h"] - g["base_h"]), b + 140, g["base_h"], fc="#cfcfcf", ec="k", lw=0.6))
    for s in (-1, 1):
        ax.add_patch(Rectangle((s * (b / 2) - (0 if s > 0 else 50), -g["fr_h"]), 50, g["fr_h"], fc="#bdbdbd", ec="k", lw=0.5))
        ax.add_patch(Rectangle((s * (b / 2) - (0 if s > 0 else 50), H), 50, g["fr_h"], fc="#bdbdbd", ec="k", lw=0.5))
    ax.add_patch(Rectangle((-b / 2, 0), b, H, fc=COR["ferro"], ec="k", lw=0.8))
    y0 = a + (hw - g["hc"]) / 2
    ax.add_patch(FancyBboxPatch((-g["Ec"] / 2, y0), g["Ec"], g["hc"], boxstyle="round,pad=0,rounding_size=12", fc=COR["bob"],
                                ec="k", lw=0.7, alpha=0.9))
    ax.plot([-b / 2 - 55, -b / 2 - 55], [-g["fr_h"], H + g["fr_h"]], color=COR["aco"], lw=2.2)
    ax.plot([b / 2 + 55, b / 2 + 55], [-g["fr_h"], H + g["fr_h"]], color=COR["aco"], lw=2.2)
    Htot = H + g["fr_h"] * 2 + g["base_h"] + 45
    _cota(ax, (b / 2 + 80, -g["fr_h"] - g["base_h"]), (b / 2 + 80, H + g["fr_h"] + 45), f"altura total ≈ {Htot:.0f}", off=6, vertical=True)
    ax.set_title("VISTA LATERAL", fontsize=8.5, weight="bold")


def corte_AA(ax, g):
    """Corte horizontal no meio da bobina: coluna + tubo + camadas de folha + canais."""
    a, b = g["a"], g["b"]
    ax.add_patch(Rectangle((-a / 2, -b / 2), a, b, fc=COR["ferro"], ec="k", lw=0.8, hatch="////"))
    r = g["c"]
    ax.add_patch(FancyBboxPatch((-a / 2 - r, -b / 2 - r), a + 2 * r, b + 2 * r, boxstyle=f"round,pad=0,rounding_size={r}",
                                fill=False, ec="#2c7fb8", lw=1.0, ls="--"))
    r += g["tube"]
    ax.add_patch(FancyBboxPatch((-a / 2 - r, -b / 2 - r), a + 2 * r, b + 2 * r, boxstyle=f"round,pad=0,rounding_size={r}",
                                fill=False, ec="#2ca25f", lw=1.6))
    canais = set(round((k + 1) * g["N"] / (g["nd"] + 1)) for k in range(g["nd"]))
    for k in range(g["N"]):
        if k in canais:
            r += g["wd"]
            ax.add_patch(FancyBboxPatch((-a / 2 - r + 1, -b / 2 - r + 1), a + 2 * r - 2, b + 2 * r - 2,
                                        boxstyle=f"round,pad=0,rounding_size={r}", fill=False, ec="#6baed6", lw=0.5, ls=":"))
        r += g["tf"] + 0.26
        ax.add_patch(FancyBboxPatch((-a / 2 - r, -b / 2 - r), a + 2 * r, b + 2 * r, boxstyle=f"round,pad=0,rounding_size={r}",
                                    fill=False, ec=COR["cu"], lw=0.45))
    r += g["wrap"]
    ax.add_patch(FancyBboxPatch((-a / 2 - r, -b / 2 - r), a + 2 * r, b + 2 * r, boxstyle=f"round,pad=0,rounding_size={r}",
                                fill=False, ec="k", lw=1.0))
    lim = a / 2 + r + 25
    ax.set_xlim(-lim, lim + 60)
    ax.set_ylim(-b / 2 - r - 25, b / 2 + r + 25)
    _cota(ax, (a / 2, 0), (a / 2 + g["c"], 0), f"c={g['c']:.0f}", off=-b / 2 - 4)
    ax.text(a / 2 + r + 5, b / 4, f"{g['N']} espiras de folha {g['tf']:.1f} mm\n+ 2×0,13 aramida/camada\n"
                                  f"{g['nd']} canal(is) de {g['wd']:.0f} mm\ntubo vidro-epóxi {g['tube']:.0f} mm\n"
                                  f"espessura radial {g['build']:.1f} mm", fontsize=6.5, va="center")
    ax.text(0, 0, f"coluna\n{a:.0f} × {b:.0f}", ha="center", va="center", fontsize=7, weight="bold")
    ax.set_title("CORTE A-A (horizontal, meio da bobina)", fontsize=8.5, weight="bold")


def corte_BB(ax, g):
    """Corte vertical pela coluna: pacotes de chapa, calços de entreferro, bobina, distâncias à culatra."""
    a, hw = g["a"], g["hw"]
    ng = g["ng"]
    gcada = g["gaps"][1] / ng
    ax.add_patch(Rectangle((-a / 2 - 120, hw), a + 240, a * 0.6, fc=COR["ferro"], ec="k", lw=0.6))
    ax.add_patch(Rectangle((-a / 2 - 120, -a * 0.6), a + 240, a * 0.6, fc=COR["ferro"], ec="k", lw=0.6))
    ys = [hw * (k + 0.5) / ng for k in range(ng)]
    prev = 0.0
    for yc in ys:
        ax.add_patch(Rectangle((-a / 2, prev), a, yc - gcada / 2 - prev, fc=COR["ferro"], ec="k", lw=0.5, hatch="----"))
        ax.add_patch(Rectangle((-a / 2, yc - gcada / 2), a, gcada, fc=COR["gap"], ec="k", lw=0.4))
        ax.text(a / 2 + 3, yc, f"calço EP GC 203  {gcada:.2f} mm", fontsize=5.8, va="center", color=COR["gap"])
        prev = yc + gcada / 2
    ax.add_patch(Rectangle((-a / 2, prev), a, hw - prev, fc=COR["ferro"], ec="k", lw=0.5, hatch="----"))
    y0 = (hw - g["hc"]) / 2
    for s in (-1, 1):
        x_in = s * (a / 2 + g["c"] + g["tube"])
        x_out = s * (a / 2 + g["c"] + g["build"])
        ax.add_patch(Rectangle((min(x_in, x_out), y0), abs(x_out - x_in), g["hc"], fc=COR["isol"], ec="k", lw=0.6))
        ax.add_patch(Rectangle((min(x_in, x_out) + 1, y0 + (g["hc"] - g["hf"]) / 2), abs(x_out - x_in) - 2, g["hf"], fc=COR["bob"],
                               ec="none", alpha=0.85))
        xt0 = s * (a / 2 + g["c"])
        ax.add_patch(Rectangle((min(xt0, x_in), y0 - 10), g["tube"], g["hc"] + 20, fc="#2ca25f", ec="k", lw=0.4))
        for yy in (0, hw - y0):
            ax.add_patch(Rectangle((min(x_in, x_out), yy if yy == 0 else hw - y0), abs(x_out - x_in), y0, fc="#c7e9c0", ec="k", lw=0.4,
                                   hatch="xx"))
    _cota(ax, (a / 2 + g["c"] + g["build"] + 15, 0), (a / 2 + g["c"] + g["build"] + 15, y0), f"{y0:.0f} bobina–culatra", off=4,
          vertical=True)
    _cota(ax, (a / 2 + g["c"] + g["build"] + 15, y0 + (g["hc"] - g["hf"]) / 2), (a / 2 + g["c"] + g["build"] + 15,
          y0 + (g["hc"] + g["hf"]) / 2), f"folha {g['hf']:.0f}", off=30, vertical=True)
    ax.set_xlim(-a / 2 - 130, a / 2 + 200)
    ax.set_ylim(-a * 0.6 - 10, hw + a * 0.6 + 10)
    ax.set_title(f"CORTE B-B (vertical pela coluna) – {ng} entreferro(s) por coluna", fontsize=8.5, weight="bold")


def detalhe_gap(ax, g):
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 60)
    ax.axis("off")
    ax.add_patch(Rectangle((10, 32), 50, 18, fc=COR["ferro"], ec="k", hatch="----"))
    ax.add_patch(Rectangle((10, 26), 50, 6, fc=COR["gap"], ec="k"))
    ax.add_patch(Rectangle((10, 8), 50, 18, fc=COR["ferro"], ec="k", hatch="----"))
    ax.text(62, 42, "pacote de chapas GO\n(empilhamento alternado,\nrebarba ≤ 0,02 mm)", fontsize=6.3, va="center")
    ax.text(62, 29, "calço vidro-epóxi EP GC 203\nretificado ±0,05 mm,\ncolado com epóxi classe H", fontsize=6.3, va="center",
            color=COR["gap"])
    ax.text(62, 14, "faces do pacote retificadas/\nplanas – sem chapa solta\n(ruído a 4–8 kHz)", fontsize=6.3, va="center")
    ax.set_title("DETALHE C – entreferro (sem escala)", fontsize=8.5, weight="bold")


def detalhe_terminal(ax, g, cond):
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 60)
    ax.axis("off")
    ax.add_patch(Rectangle((10, 10), 4, 40, fc=COR["bob"], ec="k"))
    ax.add_patch(Rectangle((14, 20), 40, 8, fc="#bbbbbb" if cond == "AL" else COR["cu"], ec="k"))
    ax.add_patch(Rectangle((54, 18), 30, 12, fc=COR["cu"], ec="k"))
    ax.add_patch(plt.Circle((69, 24), 3.5, fc="white", ec="k"))
    ax.text(12, 53, "folha", fontsize=6.3)
    ax.text(16, 31, ("barra Al soldada TIG\nna largura total da folha" if cond == "AL" else "barra Cu soldada/brasada\nna largura total"),
            fontsize=6.0)
    ax.text(55, 6, ("placa bimetálica Cu-Al (ou Al estanhado),\nfuro Ø13 – NEMA 2 furos 44,5 mm" if cond == "AL" else
                    "barra Cu estanhada, furo Ø13\nNEMA 2 furos 44,5 mm"), fontsize=6.0)
    ax.set_title("DETALHE D – terminal de saída", fontsize=8.5, weight="bold")


def vista_3d(ax, g):
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection

    def caixa(x0, y0, z0, dx, dy, dz, cor, alpha=1.0):
        X = [x0, x0 + dx]
        Y = [y0, y0 + dy]
        Z = [z0, z0 + dz]
        v = np.array([[X[i], Y[j], Z[k]] for i in (0, 1) for j in (0, 1) for k in (0, 1)])
        f = [[0, 1, 3, 2], [4, 5, 7, 6], [0, 1, 5, 4], [2, 3, 7, 6], [0, 2, 6, 4], [1, 3, 7, 5]]
        ax.add_collection3d(Poly3DCollection([v[ff] for ff in f], facecolors=cor, edgecolors="k", linewidths=0.3, alpha=alpha))

    a, b, ww, hw, W, H = g["a"], g["b"], g["ww"], g["hw"], g["W"], g["H"]
    caixa(-30, -b / 2 - 70, -g["fr_h"] - g["base_h"], W + 60, b + 140, 12, "#bbbbbb")
    caixa(0, -b / 2, 0, W, b, a, COR["ferro"])
    caixa(0, -b / 2, H - a, W, b, a, COR["ferro"])
    for i in range(3):
        x0 = i * (a + ww)
        caixa(x0, -b / 2, a, a, b, hw, COR["ferro"])
        xc = x0 + a / 2
        y0 = a + (hw - g["hc"]) / 2
        caixa(xc - g["Dc"] / 2, -g["Ec"] / 2, y0, g["Dc"], g["Ec"], g["hc"], COR["bob"], 0.92)
        for s in (-1, 1):
            caixa(xc + s * g["Dc"] / 4 - 20, -3, y0 + g["hc"], 40, 6, H + g["fr_h"] + 35 - (y0 + g["hc"]), COR["cu"])
    for z in (-g["fr_h"], H):
        caixa(-15, -b / 2 - 50, z, W + 30, 50, g["fr_h"], "#9e9e9e")
        caixa(-15, b / 2, z, W + 30, 50, g["fr_h"], "#9e9e9e")
    ax.set_box_aspect((W + 60, b + 140, H + 200))
    ax.set_xlim(-30, W + 30)
    ax.set_ylim(-b / 2 - 70, b / 2 + 70)
    ax.set_zlim(-g["fr_h"] - g["base_h"], H + g["fr_h"] + 50)
    ax.view_init(22, -55)
    ax.axis("off")
    ax.set_title("VISTA ISOMÉTRICA 3D (esquemática – bobinas cobrem as colunas)", fontsize=9, weight="bold", y=0.98)


def lista_materiais(d):
    g = _mm(d)
    ch, cond = d["chapa_dados"], d["cond_dados"]
    m = d["massa_kg"]
    gcada = g["gaps"][1] / g["ng"]
    linhas = [
        ("1", "Núcleo – chapas", f"{ch['nome']}; corte a 45° nas culatras (step-lap 2–4 degraus); colunas em pacotes", f"{m['nucleo']:.0f} kg", ch["norma"]),
        ("2", "Enrolamento", f"{cond['nome']} {g['tf']:.1f} × {g['hf']:.0f} mm, {g['N']} espiras/fase, 3 bobinas", f"{m['condutor']:.0f} kg", cond["norma"]),
        ("3", "Calços do entreferro", f"EP GC 203 retificado {gcada:.2f} mm, {g['ng']} por coluna (lat. {g['gaps'][0]/g['ng']:.2f} / cen. {g['gaps'][1]/g['ng']:.2f} mm)",
         f"{3*g['ng']} pç", "IEC 60893-3-2"),
    ]
    for k, it in enumerate(d["isolacao"], start=4):
        linhas.append((str(k), it["item"], it["mat"], "cj.", it["norma"]))
    k = len(linhas) + 1
    linhas += [
        (str(k), "Cantoneiras de aperto", "Aço carbono L 2½\" × ¼\", pintura epóxi/ zincado; isoladas do núcleo por EP GC 203 2 mm", "4 pç", "ABNT NBR 6648"),
        (str(k + 1), "Tirantes", "Barra roscada M12 classe 8.8 zincada, FORA do núcleo (não atravessar a chapa)", "4 pç", "ISO 898-1"),
        (str(k + 2), "Base / pés", "Perfil U 4\" com furos oblongos Ø14 × 25", "2 pç", "—"),
        (str(k + 3), "Terminais", "Barra Cu estanhada 40 × 6 mm (Al: placa bimetálica Cu-Al), furação NEMA 2 furos Ø13 / 44,5 mm", "6 pç", "NEMA CC1 / IEC 60445"),
        (str(k + 4), "Aterramento", "Cordoalha Cu 25 mm² núcleo → estrutura em UM ponto + terminal PE M8 na base", "1 cj.", "IEC 60364-5-54"),
        (str(k + 5), "Olhais de içamento", "M12 forjado, nas cantoneiras superiores", "2 pç", "DIN 580"),
        (str(k + 6), "Bornes do sensor", "Borne 2,5 mm² 2 vias com tampa, cabo silicone 180 °C", "1 cj.", "IEC 60947-7-1"),
        (str(k + 7), "Placa de identificação", "Aço inox gravada: L, In, fs, classe, elevação, perdas, massa, nº série, data", "1 pç", "IEC 60076-6 (dados de placa)"),
    ]
    return linhas


def gerar_pdf(d, pdf_path, info, png_dir=None):
    g = _mm(d)
    with PdfPages(pdf_path) as pdf:
        # Folha 1 – vistas
        fig = plt.figure(figsize=A3)
        _carimbo(fig, info["titulo"], "1/4 – Vistas", info)
        ax1 = fig.add_axes([0.04, 0.42, 0.50, 0.53])
        vista_frontal(ax1, g)
        ax2 = fig.add_axes([0.04, 0.08, 0.50, 0.30])
        vista_superior(ax2, g)
        ax3 = fig.add_axes([0.58, 0.42, 0.30, 0.53])
        vista_lateral(ax3, g)
        for ax in (ax1, ax2, ax3):
            ax.set_aspect("equal")
            ax.axis("off")
            ax.autoscale_view()
        ax1.set_xlim(-60, g["W"] + 110)
        ax1.set_ylim(-g["fr_h"] - g["base_h"] - 30, g["H"] + g["fr_h"] + 60)
        ax2.set_xlim(-60, g["W"] + 110)
        ax2.set_ylim(-g["b"] / 2 - 100, g["b"] / 2 + 100)
        ax3.set_xlim(-g["b"] / 2 - 90, g["b"] / 2 + 130)
        ax3.set_ylim(-g["fr_h"] - g["base_h"] - 20, g["H"] + g["fr_h"] + 60)
        ax = fig.add_axes([0.60, 0.08, 0.34, 0.30])
        ax.axis("off")
        r = d["requisitos"]
        txt = (f"DADOS PRINCIPAIS\nL = {r['L']*1e6:.0f} µH/fase ±5 %  |  In = {r['In']:.0f} A  |  fs = {r['fs']/1e3:.0f} kHz\n"
               f"Isat ≥ {r['Isat']:.0f} A (L ≥ 90 %)  |  sobrecarga {r['Iovl']:.0f} A (L ≥ 70 %)\n"
               f"Isolação classe {r['classe']} (sistema) – elevação média ≤ {d['termico']['meta_elev_K']:.0f} K\n"
               f"Tensão de isolação 1,1 kV – ensaio aplicado 3 kV/1 min\n"
               f"Massa ≈ {d['massa_kg']['total']:.0f} kg   |   Perdas ≈ {d['perdas']['total']:.0f} W\n"
               f"Dimensões ≈ {d['dims_mm']['largura']:.0f} × {d['dims_mm']['altura']:.0f} × {d['dims_mm']['profundidade']:.0f} mm\n"
               f"Entreferro por coluna: lat. {g['gaps'][0]:.2f} / central {g['gaps'][1]:.2f} mm em {g['ng']} peças\n"
               f"→ ajuste final do calço no ensaio para L ±5 % e desequilíbrio ≤ 3 %")
        ax.text(0, 1, txt, fontsize=8, va="top", family="DejaVu Sans")
        if png_dir:
            fig.savefig(os.path.join(png_dir, "Indutor_folha1.png"), dpi=110)
        pdf.savefig(fig)
        plt.close(fig)
        # Folha 2 – cortes e detalhes
        fig = plt.figure(figsize=A3)
        _carimbo(fig, info["titulo"], "2/4 – Cortes e detalhes", info)
        axA = fig.add_axes([0.04, 0.45, 0.42, 0.50])
        corte_AA(axA, g)
        axB = fig.add_axes([0.50, 0.30, 0.46, 0.65])
        corte_BB(axB, g)
        for ax in (axA, axB):
            ax.set_aspect("equal")
            ax.axis("off")
        detalhe_gap(fig.add_axes([0.04, 0.17, 0.25, 0.25]), g)
        detalhe_terminal(fig.add_axes([0.29, 0.17, 0.22, 0.25]), g, d["cond"])
        if png_dir:
            fig.savefig(os.path.join(png_dir, "Indutor_folha2.png"), dpi=110)
        pdf.savefig(fig)
        plt.close(fig)
        # Folha 3 – 3D
        fig = plt.figure(figsize=A3)
        _carimbo(fig, info["titulo"], "3/4 – Vista 3D", info)
        ax = fig.add_axes([0.05, 0.20, 0.62, 0.72], projection="3d")
        ax.patch.set_alpha(0)
        vista_3d(ax, g)
        if png_dir:
            fig.savefig(os.path.join(png_dir, "Indutor_folha3.png"), dpi=110)
        pdf.savefig(fig)
        plt.close(fig)
        # Folha 4 – lista de materiais e notas
        fig = plt.figure(figsize=A3)
        _carimbo(fig, info["titulo"], "4/4 – Lista de materiais e notas", info)
        ax = fig.add_axes([0.04, 0.30, 0.92, 0.65])
        ax.axis("off")
        lm = lista_materiais(d)
        tb = ax.table(cellText=[list(x) for x in lm], colLabels=["Item", "Descrição", "Especificação", "Qtd.", "Norma"],
                      colWidths=[0.04, 0.17, 0.55, 0.06, 0.18], loc="upper left", cellLoc="left")
        tb.auto_set_font_size(False)
        tb.set_fontsize(6.6)
        tb.scale(1, 1.32)
        ax2 = fig.add_axes([0.04, 0.17, 0.92, 0.12])
        ax2.axis("off")
        notas = ("NOTAS: 1) Classe de isolação é do SISTEMA (IEC 60085/IEC 61857): todos os materiais acima com índice térmico ≥ classe; "
                 "proibido DMD, GPO-3 e cabo PVC em classe H.  2) Núcleo aterrado em UM ponto; nenhum parafuso atravessa as chapas sem isolação.  "
                 "3) Calços do entreferro colados e o conjunto impregnado por VPI – evita ruído/vibração a 4–8 kHz.  4) Distâncias: separação ≥ 10 mm, "
                 "escoamento ≥ 16 mm entre partes vivas e massa (IEC 60664-1, cat. III, PD3, 1000 V).  5) Ensaios de rotina e de tipo conforme "
                 "a ET; protótipo obrigatório.  6) Ajustar o calço do entreferro no ensaio para L ±5 % e desequilíbrio ≤ 3 %.")
        ax2.text(0, 1, notas, fontsize=7, va="top", wrap=True)
        if png_dir:
            fig.savefig(os.path.join(png_dir, "Indutor_folha4.png"), dpi=110)
        pdf.savefig(fig)
        plt.close(fig)
    return pdf_path


def imagens_campo(d, png):
    """Mapa de |B| no pico (FEM não-linear) com linhas de fluxo."""
    from matplotlib.tri import Triangulation
    M, A = d["campo_pico"]
    Bx, By = M.B(A)
    Bm = np.hypot(Bx, By)
    m = M.m
    tri = Triangulation(m.p[:, 0] * 1e3, m.p[:, 1] * 1e3, m.t)
    fig, ax = plt.subplots(figsize=(12, 7))
    tc = ax.tripcolor(tri, facecolors=Bm, cmap="viridis", vmin=0, vmax=max(1.6, float(np.percentile(Bm[M.ferro], 99.5))))
    ax.tricontour(tri, A, levels=40, colors="white", linewidths=0.35)
    W, H = M.W * 1e3, M.H * 1e3
    ax.set_xlim(-0.25 * W, 1.25 * W)
    ax.set_ylim(-0.15 * H, 1.15 * H)
    ax.set_aspect("equal")
    fig.colorbar(tc, ax=ax, label="|B| (T)")
    ax.set_title("Elementos finitos – indução no pico de operação (fase U no máximo) e linhas de fluxo")
    ax.set_xlabel("mm")
    fig.tight_layout()
    fig.savefig(png, dpi=140)
    plt.close(fig)
    return png
