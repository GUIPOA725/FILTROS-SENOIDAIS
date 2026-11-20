"""Desenhos do PROJETO DE REFERÊNCIA do indutor – padrão de fábrica (v1.10.3).

Folhas A3 paisagem (ABNT NBR 10068 / 10582), 1º diedro, escalas normalizadas, carimbo com tabela de revisões, cotas em cadeia,
balões numerados ligados à lista de materiais. Tudo desenhado em milímetros reais sobre a folha (escala aplicada por vista).
Folhas: 1 Conjunto (vistas) · 2 Núcleo (chapas, step-lap, pacotes, calços) · 3 Bobina (cortes, tabela de bobinagem,
terminal) · 4 Vista 3D · 5 Lista de materiais, ficha de fabricação e notas.
O fabricante emite o desenho de fabricação próprio a partir deste e declara as diferenças.
"""
import math
import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.patches import Rectangle, FancyBboxPatch, Polygon, Circle, PathPatch
from matplotlib.path import Path

A3_IN = (420 / 25.4, 297 / 25.4)
C = dict(ferro="#aab4be", ferro_esc="#7d8994", gap="#d62728", bob="#d9902f", bob_esc="#a8661a", isol="#f3e6a6", tubo="#3a9a5b",
         aco="#6e6e6e", aco_cl="#b9b9b9", cu="#c47a3c", txt="#111111", cota="#1f3b73", bal="#ffffff")
ESCALAS = [1, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10]
LW_G, LW_M, LW_F = 0.7, 0.45, 0.25          # linhas grossa / média / fina (mm na folha → pontos aproximados)


def _esc(dim_mm, area_mm):
    for e in ESCALAS:
        if dim_mm / e <= area_mm:
            return e
    return ESCALAS[-1]


# ---------------------------------------------------------------------------------------------------------------------
class Folha:
    """Folha A3 em mm; vistas são desenhadas em mm reais com (origem na folha, escala)."""

    def __init__(self, info, n, total, titulo_folha):
        self.fig = plt.figure(figsize=A3_IN)
        self.ax = self.fig.add_axes([0, 0, 1, 1])
        self.ax.set_xlim(0, 420)
        self.ax.set_ylim(0, 297)
        self.ax.set_aspect("equal")
        self.ax.axis("off")
        self.info, self.n, self.total, self.tf = info, n, total, titulo_folha
        self._moldura()

    def _moldura(self):
        a = self.ax
        a.add_patch(Rectangle((20, 10), 390, 277, fill=False, lw=1.1))          # margem de arquivamento 20 mm (NBR 10068)
        for x in np.arange(20, 410, 48.75):
            a.plot([x, x], [10, 13], lw=0.4, color="k")
        # carimbo 180 × 50 mm no canto inferior direito
        x0, y0, w = 230, 10, 180
        a.add_patch(Rectangle((x0, y0), w, 52, fill=False, lw=1.0))
        for yy in (y0 + 12, y0 + 22, y0 + 32, y0 + 42):
            a.plot([x0, x0 + w], [yy, yy], lw=0.5, color="k")
        for xx in (x0 + 60, x0 + 105, x0 + 140):
            a.plot([xx, xx], [y0, y0 + 22], lw=0.5, color="k")
        i = self.info
        a.text(x0 + 3, y0 + 45, "ELECTRIC SERVICE  –  Engenharia de Filtros", fontsize=9, weight="bold")
        a.text(x0 + 3, y0 + 35, i["titulo"], fontsize=7.4)
        a.text(x0 + 3, y0 + 25, f"Folha {self.n}/{self.total} – {self.tf}", fontsize=7.4, weight="bold")
        a.text(x0 + 3, y0 + 16.5, "Desenho nº", fontsize=5.5, color="0.35")
        a.text(x0 + 3, y0 + 13, f"IND-{i['cod']}-{self.n:02d}", fontsize=7.2)
        a.text(x0 + 63, y0 + 16.5, "Escala", fontsize=5.5, color="0.35")
        self._t_esc = a.text(x0 + 63, y0 + 13, i.get("escala_folha", "indicada"), fontsize=7.2)
        a.text(x0 + 108, y0 + 16.5, "Unid. / Projeção", fontsize=5.5, color="0.35")
        a.text(x0 + 108, y0 + 13, "mm  1º diedro", fontsize=7.2)
        self._simbolo_diedro(x0 + 128, y0 + 4)
        a.text(x0 + 143, y0 + 16.5, "Rev.", fontsize=5.5, color="0.35")
        a.text(x0 + 143, y0 + 13, "00", fontsize=7.2)
        a.text(x0 + 3, y0 + 6.5, f"Data {i['data']}   |   Projeto: {i['versao']} (cálculo automático)", fontsize=5.8)
        a.text(x0 + 3, y0 + 2.5, "Verificado: ________   Aprovado: ________", fontsize=5.8)
        # tabela de revisões acima do carimbo
        a.add_patch(Rectangle((x0, y0 + 52), w, 10, fill=False, lw=0.6))
        a.text(x0 + 2, y0 + 58.5, "Rev.  Data        Descrição", fontsize=5.5, color="0.35")
        a.text(x0 + 2, y0 + 54.2, f"00    {i['data']}  Emissão inicial – projeto de referência", fontsize=5.8)
        a.text(22, 13.5, "PROJETO DE REFERÊNCIA – o fabricante emite o desenho de fabricação próprio e declara as diferenças.  "
                         "Cotas em mm.  Não medir no desenho.  Tolerâncias gerais ISO 2768-m.", fontsize=6.2, style="italic")

    def _simbolo_diedro(self, x, y):
        a = self.ax
        a.add_patch(Polygon([(x, y + 1.5), (x + 6, y), (x + 6, y + 6), (x, y + 4.5)], closed=True, fill=False, lw=0.5))
        a.add_patch(Circle((x + 11, y + 3), 3, fill=False, lw=0.5))
        a.add_patch(Circle((x + 11, y + 3), 1.4, fill=False, lw=0.5))

    # ---- primitivas em coordenadas da vista (mm reais) ----
    def vista(self, ox, oy, esc, titulo=None, tx=None, ty=None):
        return Vista(self, ox, oy, esc, titulo, tx, ty)

    def texto(self, x, y, t, **kw):
        kw.setdefault("fontsize", 6.5)
        self.ax.text(x, y, t, **kw)

    def tabela(self, x, y, cab, linhas, larg, fs=5.8, h=4.2):
        a = self.ax
        W = sum(larg)
        n = len(linhas) + 1
        a.add_patch(Rectangle((x, y - n * h), W, n * h, fill=False, lw=0.6))
        a.add_patch(Rectangle((x, y - h), W, h, fc="#dde6f3", ec="k", lw=0.5))
        for i in range(1, n):
            a.plot([x, x + W], [y - i * h, y - i * h], lw=0.25, color="0.4")
        cx = x
        for j, l in enumerate(larg):
            a.text(cx + 0.8, y - h + 1.2, cab[j], fontsize=fs, weight="bold")
            for i, lin in enumerate(linhas):
                a.text(cx + 0.8, y - (i + 2) * h + 1.2, str(lin[j]), fontsize=fs)
            cx += l
            if j < len(larg) - 1:
                a.plot([cx, cx], [y, y - n * h], lw=0.25, color="0.4")
        return y - n * h

    def salvar(self, pdf, png=None):
        self._t_esc.set_text(self.info.get("escala_folha", "indicada"))
        if png:
            self.fig.savefig(png, dpi=130)
        pdf.savefig(self.fig)
        plt.close(self.fig)


class Vista:
    def __init__(self, f, ox, oy, esc, titulo, tx, ty):
        self.f, self.ax, self.ox, self.oy, self.e = f, f.ax, ox, oy, esc
        if titulo:
            esc_txt = f"1:{esc:g}" if esc >= 1 else f"{1/esc:g}:1"
            f.ax.text(tx if tx is not None else ox, ty if ty is not None else oy, f"{titulo}   (ESC. {esc_txt})", fontsize=7.4,
                      weight="bold", ha="left")

    def P(self, x, y):
        return self.ox + x / self.e, self.oy + y / self.e

    def ret(self, x, y, w, h, **kw):
        x1, y1 = self.P(x, y)
        kw.setdefault("lw", LW_M)
        kw.setdefault("ec", "k")
        self.ax.add_patch(Rectangle((x1, y1), w / self.e, h / self.e, **kw))

    def rret(self, x, y, w, h, r, **kw):
        x1, y1 = self.P(x, y)
        kw.setdefault("lw", LW_M)
        kw.setdefault("ec", "k")
        rr = min(r, w / 2 - 0.01, h / 2 - 0.01) / self.e
        self.ax.add_patch(FancyBboxPatch((x1 + rr, y1 + rr), w / self.e - 2 * rr, h / self.e - 2 * rr,
                                         boxstyle=f"round,pad={rr},rounding_size={rr}", **kw))

    def lin(self, xs, ys, **kw):
        kw.setdefault("lw", LW_M)
        kw.setdefault("color", "k")
        p = [self.P(x, y) for x, y in zip(xs, ys)]
        self.ax.plot([q[0] for q in p], [q[1] for q in p], **kw)

    def eixo(self, x0, y0, x1, y1):
        self.lin([x0, x1], [y0, y1], lw=0.3, color="#c03030", ls=(0, (8, 2, 1, 2)))

    def circ(self, x, y, r, **kw):
        kw.setdefault("lw", LW_M)
        kw.setdefault("ec", "k")
        kw.setdefault("fc", "white")
        cx, cy = self.P(x, y)
        self.ax.add_patch(Circle((cx, cy), r / self.e, **kw))

    def txt(self, x, y, t, **kw):
        kw.setdefault("fontsize", 6.2)
        cx, cy = self.P(x, y)
        self.ax.text(cx, cy, t, **kw)

    def cota_h(self, x1, x2, y, off, t=None, fs=5.8):
        """Cota horizontal entre x1 e x2 na altura y, deslocada 'off' mm DA FOLHA (negativo = abaixo)."""
        a = self.ax
        X1, Y = self.P(x1, y)
        X2, _ = self.P(x2, y)
        Yc = Y + off
        a.plot([X1, X1], [Y, Yc + (0.8 if off < 0 else -0.8) * -1], lw=0.25, color=C["cota"])
        a.plot([X2, X2], [Y, Yc + (0.8 if off < 0 else -0.8) * -1], lw=0.25, color=C["cota"])
        a.annotate("", (X1, Yc), (X2, Yc), arrowprops=dict(arrowstyle="<|-|>", lw=0.35, color=C["cota"], mutation_scale=4.5,
                                                          shrinkA=0, shrinkB=0))
        a.text((X1 + X2) / 2, Yc + 0.6, t if t is not None else f"{abs(x2 - x1):.0f}", fontsize=fs, ha="center", va="bottom",
               color=C["cota"])

    def cota_v(self, y1, y2, x, off, t=None, fs=5.8):
        a = self.ax
        X, Y1 = self.P(x, y1)
        _, Y2 = self.P(x, y2)
        Xc = X + off
        a.plot([X, Xc + (0.8 if off > 0 else -0.8)], [Y1, Y1], lw=0.25, color=C["cota"])
        a.plot([X, Xc + (0.8 if off > 0 else -0.8)], [Y2, Y2], lw=0.25, color=C["cota"])
        a.annotate("", (Xc, Y1), (Xc, Y2), arrowprops=dict(arrowstyle="<|-|>", lw=0.35, color=C["cota"], mutation_scale=4.5,
                                                          shrinkA=0, shrinkB=0))
        a.text(Xc - 0.6, (Y1 + Y2) / 2, t if t is not None else f"{abs(y2 - y1):.0f}", fontsize=fs, rotation=90, ha="right",
               va="center", color=C["cota"])

    def balao(self, x, y, n, dx, dy):
        """Balão numerado (item da lista de materiais) com linha de chamada; dx, dy em mm da folha."""
        X, Y = self.P(x, y)
        a = self.ax
        a.plot([X, X + dx], [Y, Y + dy], lw=0.3, color="k")
        a.add_patch(Circle((X, Y), 0.6, color="k"))
        a.add_patch(Circle((X + dx, Y + dy), 2.8, fc="white", ec="k", lw=0.5, zorder=5))
        a.text(X + dx, Y + dy, str(n), fontsize=6, ha="center", va="center", zorder=6, weight="bold")


# ---------------------------------------------------------------------------------------------------------------------
def geo_mm(d):
    g = {k: d[k] * 1e3 for k in ("a", "b", "hw", "ww", "c", "build", "hc", "hf", "tf", "tube", "wrap", "wd")}
    g["N"], g["nd"], g["ng"] = d["N"], d["nd"], d["ng"]
    g["gaps"] = [x * 1e3 for x in d["gaps"]]
    g["W"] = 3 * g["a"] + 2 * g["ww"]
    g["H"] = 2 * g["a"] + g["hw"]
    g["Dc"] = g["a"] + 2 * (g["c"] + g["build"])
    g["Ec"] = g["b"] + 2 * (g["c"] + g["build"])
    g["rc"] = g["c"] + g["build"] * 0.6                    # raio de canto externo da bobina
    g["yc0"] = g["a"] + (g["hw"] - g["hc"]) / 2
    g["fr"] = 63.5                                         # cantoneira 2½" × ¼"
    g["fe"] = 6.35
    g["base_h"] = 50.0
    g["term_h"] = 60.0                                     # terminais acima da cantoneira superior
    g["pitch"] = g["a"] + g["ww"]
    g["xc"] = [g["a"] / 2 + i * g["pitch"] for i in range(3)]
    g["xr"] = (g["xc"][0] - g["Dc"] / 2 - 22, g["xc"][2] + g["Dc"] / 2 + 22)   # tirantes fora das bobinas
    g["Lb"] = g["xr"][1] - g["xr"][0] + 80                  # comprimento da base
    g["Bb"] = g["Ec"] + 2 * 40                             # largura da base (profundidade)
    return g


def fabricacao(d):
    """Dados de fabricação derivados do projeto (tabelas usadas nos desenhos e no memorial)."""
    g = geo_mm(d)
    ch, cond = d["chapa_dados"], d["cond_dados"]
    t = ch["esp_mm"]
    n_lam = int(round(g["b"] * ch["kf"] / t))
    ng = g["ng"]
    gl, gc = g["gaps"][0] / ng, g["gaps"][1] / ng
    # pacotes da coluna: entreferros centrados em hw(k+0,5)/ng
    def pacotes(gcada):
        ys = [g["hw"] * (k + 0.5) / ng for k in range(ng)]
        out, prev = [], 0.0
        for y in ys:
            out.append(y - gcada / 2 - prev)
            prev = y + gcada / 2
        out.append(g["hw"] - prev)
        return out
    pac_l, pac_c = pacotes(gl), pacotes(gc)
    # tabela de bobinagem
    camadas = []
    r = g["c"]
    camadas.append(("Tubo vidro-epóxi EP GC 203", f"{g['tube']:.1f}", r, r + g["tube"]))
    r += g["tube"]
    camadas.append(("Aramida 2×0,13 (início)", "0.26", r, r + 0.26))
    r += 0.26
    canais = sorted(set(round((k + 1) * g["N"] / (g["nd"] + 1)) for k in range(g["nd"])))
    for k in range(g["N"]):
        if k in canais:
            camadas.append((f"Canal axial (réguas EP GC 203 {g['wd']:.0f} mm)", f"{g['wd']:.1f}", r, r + g["wd"]))
            r += g["wd"]
        reforco = k in (0, 1, g["N"] - 2, g["N"] - 1)
        ti = 0.26 + (0.13 if reforco else 0)
        camadas.append((f"Espira {k + 1}: folha {g['tf']:.1f} + aramida {ti:.2f}" + (" (reforço)" if reforco else ""),
                        f"{g['tf'] + ti:.2f}", r, r + g["tf"] + ti))
        r += g["tf"] + ti
    camadas.append(("Enfaixamento externo (fita de vidro + aramida)", f"{g['wrap']:.1f}", r, r + g["wrap"]))
    r += g["wrap"]
    MLT = d["MLT"] * 1e3
    comp_folha = g["N"] * MLT / 1000
    massa_folha = comp_folha * g["tf"] * g["hf"] * 1e-6 * cond["dens"]
    forca = d.get("forca_gap_N", 0)
    return dict(
        n_lam=n_lam, t=t, pac_l=pac_l, pac_c=pac_c, gl=gl, gc=gc, camadas=camadas, build_real=r - g["c"], comp_folha=comp_folha,
        massa_folha=massa_folha, MLT=MLT, forca=forca, aperto_N=max(2.5 * forca, 2000),
        corte=[("Coluna (pacotes)", f"{g['a']:.0f}", "ver pacotes", f"3 × {ng + 1} pacotes × {n_lam} lâminas"),
               ("Culatra superior", f"{g['a']:.0f}", f"{g['W']:.0f} (45°)", f"{n_lam} lâminas"),
               ("Culatra inferior", f"{g['a']:.0f}", f"{g['W']:.0f} (45°)", f"{n_lam} lâminas")],
        sequencia=[
            "Cortar chapas (guilhotina/estampo) e rebarbar: rebarba ≤ 0,02 mm; recozer se o fornecedor da chapa exigir.",
            f"Montar a culatra inferior e as colunas em pacotes de {g['b']:.0f} mm (≈ {n_lam} lâminas), junta step-lap 3 degraus × 5 mm nas culatras.",
            f"Colar os calços EP GC 203 entre pacotes (lat. {gl:.2f} mm / cen. {gc:.2f} mm) com epóxi classe H; retificar faces dos pacotes.",
            f"Bobinar as 3 bobinas sobre mandril com o tubo EP GC 203 (folha {g['tf']:.1f} × {g['hf']:.0f} mm, {g['N']} espiras, aramida entre espiras, reforço nas 2 primeiras/últimas).",
            "Soldar as barras de saída (TIG, largura total da folha) antes de bobinar a espira inicial e depois da final; instalar PTC entre as últimas camadas.",
            "Encaixar as bobinas nas colunas com calços de extremidade; fechar a culatra superior (step-lap).",
            f"Prensar o conjunto: força de aperto ≥ {max(2.5 * forca, 2000):.0f} N por coluna nos entreferros (cantoneiras + tirantes M12 8.8, torque 80 N·m).",
            "Medir L por fase na corrente nominal (ou fonte CA + ponte LCR em 60 Hz com correção) e ajustar o calço: L ±5 %, desequilíbrio ≤ 3 %.",
            "Impregnar por VPI com resina classe H; curar na estufa conforme fabricante da resina; retocar pintura da estrutura.",
            "Ensaios de rotina (resistência, L, tensão aplicada 3 kV/1 min, isolamento) e de tipo no protótipo (perdas, aquecimento com inversor, L × I).",
        ])


def _rret_pts(cx, cy, w, h, r, n=8):
    """Pontos de um retângulo arredondado (para 3D)."""
    r = min(r, w / 2 - 0.1, h / 2 - 0.1)
    pts = []
    for (qx, qy, a0) in ((cx + w / 2 - r, cy + h / 2 - r, 0), (cx - w / 2 + r, cy + h / 2 - r, 90),
                         (cx - w / 2 + r, cy - h / 2 + r, 180), (cx + w / 2 - r, cy - h / 2 + r, 270)):
        for k in range(n + 1):
            t = math.radians(a0 + 90 * k / n)
            pts.append((qx + r * math.cos(t), qy + r * math.sin(t)))
    return pts


# ---------------------------------------------------------------------------------------------------------------------
def folha_conjunto(F, g, d):
    a, W, H, hw, ww, b = g["a"], g["W"], g["H"], g["hw"], g["ww"], g["b"]
    xr0, xr1 = g["xr"]
    yb = -g["fr"] - g["base_h"]
    ytop = H + g["fr"] + g["term_h"]
    Htot = ytop - yb
    x_min, x_max = xr0 - 40, xr1 + 40
    e = _esc(max((x_max - x_min) / 190, (Htot + g["Bb"]) / 200), 1)
    # ---- posições na folha (1º diedro: lateral esquerda à DIREITA da frontal; superior ABAIXO da frontal) ----
    ox = 32 - x_min / e
    oy = 262 - ytop / e
    V = F.vista(ox, oy, e, "VISTA FRONTAL", 32, 278)
    # base, cantoneiras, núcleo
    V.ret(x_min, yb, x_max - x_min, g["base_h"], fc=C["aco_cl"], lw=LW_M)
    V.lin([x_min, x_max], [yb + 8, yb + 8], lw=LW_F)
    V.ret(xr0 - 18, -g["fr"], xr1 - xr0 + 36, g["fr"], fc=C["aco"], alpha=0.9)
    V.ret(xr0 - 18, H, xr1 - xr0 + 36, g["fr"], fc=C["aco"], alpha=0.9)
    V.ret(0, 0, W, H, fc=C["ferro"], lw=LW_G)
    for i in range(2):
        V.ret(a + i * g["pitch"], a, ww, hw, fc="white", lw=LW_M)
    for i, xc in enumerate(g["xc"]):
        V.rret(xc - g["Dc"] / 2, g["yc0"], g["Dc"], g["hc"], 6, fc=C["bob"], lw=LW_G)
        V.txt(xc, g["yc0"] + g["hc"] / 2, "UVW"[i], ha="center", va="center", fontsize=10, weight="bold", color="white")
        V.eixo(xc, yb - 4, xc, ytop + 4)
        for s, lab in ((-1, "1"), (1, "2")):
            xt = xc + s * g["Dc"] * 0.28
            y0 = g["yc0"] + g["hc"]
            V.ret(xt - 20, y0, 40, ytop - y0, fc=C["cu"], lw=LW_M, alpha=0.9)
            V.circ(xt, ytop - 14, 6.5)
            V.txt(xt, ytop + 5, "UVW"[i] + lab, ha="center", fontsize=6.3, weight="bold")
    for x in (xr0, xr1):                                                     # tirantes M12 FORA das bobinas
        V.ret(x - 6, -g["fr"] - 12, 12, H + 2 * g["fr"] + 24, fc=C["aco_cl"], lw=LW_F)
        for y in (-g["fr"] - 12, H + g["fr"] + 4):
            V.ret(x - 10, y, 20, 8, fc=C["aco"], lw=LW_F)
    for x in (W * 0.3, W * 0.7):                                             # olhais DIN 580
        V.circ(x, H + g["fr"] + 20, 12, fc="white", lw=LW_M)
    V.ret(xr1 - 70, H + g["fr"] + 2, 50, 28, fc="#e9e9e9", lw=LW_M)          # caixa de bornes PTC
    V.txt(xr1 - 45, H + g["fr"] + 14, "PTC", ha="center", fontsize=5.8)
    V.ret(W * 0.5 - 45, yb + 13, 90, 26, fc="#f7f7f7", lw=LW_F)              # placa
    V.txt(W * 0.5, yb + 26, "PLACA", ha="center", va="center", fontsize=5.5)
    V.circ(x_min + 18, yb + g["base_h"] / 2, 6, fc="#7cb342")                # PE
    # cotas
    V.cota_h(x_min, x_max, yb, -6, f"{x_max - x_min:.0f} (base)")
    V.cota_h(0, W, yb, -12, f"{W:.0f} (núcleo)")
    xs = [0, a, a + ww, 2 * a + ww, 2 * a + 2 * ww, W]
    for p, q in zip(xs[:-1], xs[1:]):
        V.cota_h(p, q, yb, -18, f"{q - p:.0f}")
    V.cota_h(g["xc"][0], g["xc"][1], ytop, 8, f"passo {g['pitch']:.0f}")
    V.cota_h(g["xc"][1], g["xc"][2], ytop, 8, f"{g['pitch']:.0f}")
    gap_bob = ww - 2 * (g["c"] + g["build"])
    V.cota_h(g["xc"][0] + g["Dc"] / 2, g["xc"][1] - g["Dc"] / 2, g["yc0"] + 18, 0, f"{gap_bob:.0f}")
    V.cota_v(yb, ytop, x_max, 14, f"{Htot:.0f} (total)")
    V.cota_v(0, H, x_max, 7, f"{H:.0f}")
    V.cota_v(g["yc0"], g["yc0"] + g["hc"], x_min, -6, f"bobina {g['hc']:.0f}")
    # balões (itens da lista de materiais)
    V.balao(a * 0.5, H - a * 0.5, 1, -8, 10)
    V.balao(g["xc"][0] - g["Dc"] * 0.3, g["yc0"] + g["hc"] * 0.3, 2, -10, -8)
    V.balao(W * 0.45, H + g["fr"] * 0.5, 14, 4, 13)
    V.balao(xr0, H * 0.5, 15, -9, 6)
    V.balao(x_max - 20, yb + 4, 16, 8, -7)
    V.balao(g["xc"][2] + g["Dc"] * 0.28, ytop - 40, 17, 14, -4)
    V.balao(x_min + 18, yb + g["base_h"] / 2, 18, -7, 9)
    V.balao(W * 0.3, H + g["fr"] + 20, 19, -6, 11)
    V.balao(xr1 - 45, H + g["fr"] + 28, 20, 9, 9)
    V.balao(W * 0.5 + 30, yb + 20, 21, 10, -10)
    # ---- vista lateral esquerda ----
    oxl = ox + (x_max + 70) / e + (g["Bb"] / 2) / e
    VL = F.vista(oxl, oy, e, "VISTA LATERAL ESQUERDA", oxl - g["Bb"] / 2 / e, 278)
    VL.ret(-g["Bb"] / 2, yb, g["Bb"], g["base_h"], fc=C["aco_cl"])
    for s in (-1, 1):
        x0 = b / 2 if s > 0 else -b / 2 - g["fe"]
        VL.ret(x0, -g["fr"], g["fe"], g["fr"], fc=C["aco"])
        VL.ret(x0, H, g["fe"], g["fr"], fc=C["aco"])
        VL.ret(s * (b / 2 + 22) - 6, -g["fr"] - 12, 12, H + 2 * g["fr"] + 24, fc=C["aco_cl"], lw=LW_F)
        VL.lin([s * (b / 2 + g["fe"]), s * (b / 2 + 50)], [-g["fr"] + 6, -g["fr"] + 6], lw=LW_M)
        VL.lin([s * (b / 2 + g["fe"]), s * (b / 2 + 50)], [H + g["fr"] - 6, H + g["fr"] - 6], lw=LW_M)
    VL.ret(-b / 2, 0, b, H, fc=C["ferro"], lw=LW_G)
    VL.rret(-g["Ec"] / 2, g["yc0"], g["Ec"], g["hc"], 6, fc=C["bob"], lw=LW_G)
    VL.ret(-b / 2 - g["c"] - 6, g["yc0"] + g["hc"], 6, ytop - g["yc0"] - g["hc"], fc=C["cu"])
    VL.eixo(0, yb - 4, 0, ytop + 4)
    VL.cota_h(-g["Bb"] / 2, g["Bb"] / 2, yb, -6, f"{g['Bb']:.0f}")
    VL.cota_h(-g["Ec"] / 2, g["Ec"] / 2, yb, -12, f"bobina {g['Ec']:.0f}")
    VL.cota_h(-b / 2, b / 2, ytop, 8, f"empilh. {b:.0f}")
    # ---- vista superior / furação da base ----
    oys = oy + (yb / e) - 30 - (g["Bb"] / 2) / e
    VS = F.vista(ox, oys, e, "VISTA SUPERIOR / FURAÇÃO DA BASE", 32, oys + (g["Bb"] / 2) / e + 4)
    VS.ret(x_min, -g["Bb"] / 2, x_max - x_min, g["Bb"], fc="#ececec")
    VS.ret(0, -b / 2, W, b, fc=C["ferro"], lw=LW_G)
    for xc in g["xc"]:
        VS.rret(xc - g["Dc"] / 2, -g["Ec"] / 2, g["Dc"], g["Ec"], g["rc"], fc=C["bob"], lw=LW_G)
        VS.ret(xc - a / 2, -b / 2, a, b, fc=C["ferro_esc"], lw=LW_M)
        VS.eixo(xc, -g["Bb"] / 2 - 3, xc, g["Bb"] / 2 + 3)
    xf0, xf1 = x_min + 25, x_max - 25
    for x in (xf0, xf1):
        for y in (-g["Bb"] / 2 + 20, g["Bb"] / 2 - 20):
            VS.rret(x - 12.5, y - 7, 25, 14, 7, fc="white", lw=LW_M)
    VS.cota_h(xf0, xf1, -g["Bb"] / 2, -6, f"{xf1 - xf0:.0f} (furos)")
    VS.cota_v(-g["Bb"] / 2 + 20, g["Bb"] / 2 - 20, x_max, 7, f"{g['Bb'] - 40:.0f}")
    VS.txt(x_max + 40, 0, "4× furo oblongo\nØ14 × 25", fontsize=5.6, va="center")
    F.info["escala_folha"] = f"1:{e:g}"
    # quadro de dados à direita
    r = d["requisitos"]
    dados = [("L por fase", f"{r['L']*1e6:.0f} µH ±5 %"), ("In", f"{r['In']:.0f} A  (pico {r['Ipk']:.0f} A)"),
             ("Isat", f"≥ {r['Isat']:.0f} A com L ≥ 90 %"), ("Sobrecarga", f"{r['Iovl']:.0f} A com L ≥ 70 %"),
             ("fs", f"{r['fs']/1e3:.0f} kHz – tensão PWM"), ("Isolação", f"sistema classe {r['classe']}, 1,1 kV"),
             ("Elevação", f"≤ {d['termico']['meta_elev_K']:.0f} K (calc. {d['termico']['elev_bobina_K']:.0f} K)"),
             ("Perdas", f"{d['perdas']['total']:.0f} W (calc.)"), ("Massa", f"{d['massa_kg']['total']:.0f} kg (calc.)")]
    F.tabela(300, 140, ["Característica", "Valor"], dados, [30, 72], fs=5.8, h=4.8)
def folha_nucleo(F, g, d, fab):
    a, W, H, hw, ww, b = g["a"], g["W"], g["H"], g["hw"], g["ww"], g["b"]
    e = _esc(max(W / 200, H / 150), 1)
    V = F.vista(35, 120, e, "NÚCLEO – PLANTA DAS CHAPAS (vista frontal, sem bobinas)", 35, 272)
    V.ret(0, 0, W, H, fc=C["ferro"], lw=LW_G)
    for i in range(2):
        V.ret(a + i * g["pitch"], a, ww, hw, fc="white", lw=LW_M)
    # juntas a 45° nas culatras (step-lap)
    for xx in (0, W):
        s = 1 if xx == 0 else -1
        V.lin([xx, xx + s * a], [0, a], lw=LW_F, color="k")
        V.lin([xx, xx + s * a], [H, H - a], lw=LW_F, color="k")
    xm = g["xc"][1]
    V.lin([xm - a / 2, xm, xm + a / 2], [a, 0, a], lw=LW_F)
    V.lin([xm - a / 2, xm, xm + a / 2], [H - a, H, H - a], lw=LW_F)
    # entreferros (calços) em cada coluna, com cotas dos pacotes na coluna lateral e na central
    for i in range(3):
        x0 = i * g["pitch"]
        gcada = fab["gl"] if i != 1 else fab["gc"]
        y = a
        pac = fab["pac_l"] if i != 1 else fab["pac_c"]
        for k, ph in enumerate(pac):
            y += ph
            if k < len(pac) - 1:
                V.ret(x0, y, a, gcada, fc=C["gap"], lw=0.2)
                y += gcada
        V.eixo(x0 + a / 2, -8, x0 + a / 2, H + 8)
    y = a
    for k, ph in enumerate(fab["pac_l"]):
        V.cota_v(y, y + ph, 0, -6, f"{ph:.1f}", fs=5.2)
        y += ph + (fab["gl"] if k < len(fab["pac_l"]) - 1 else 0)
    y = a
    xr = 2 * g["pitch"] + a
    for k, ph in enumerate(fab["pac_c"]):
        if k < len(fab["pac_c"]) - 1:
            V.txt(g["xc"][1] + a / 2 + 2, y + ph + fab["gc"] / 2, f"calço {fab['gc']:.2f}", fontsize=5.2, color=C["gap"], va="center")
        y += ph + (fab["gc"] if k < len(fab["pac_c"]) - 1 else 0)
    V.cota_h(0, W, 0, -8, f"{W:.0f}")
    V.cota_h(0, a, H, 6, f"{a:.0f}")
    V.cota_h(a, a + ww, H, 6, f"{ww:.0f}")
    V.cota_v(0, a, W, 8, f"{a:.0f}")
    V.cota_v(a, a + hw, W, 8, f"{hw:.0f}")
    V.cota_v(a + hw, H, W, 8, f"{a:.0f}")
    V.cota_v(0, H, W, 16, f"{H:.0f}")
    V.balao(a / 2, a / 2, 1, -10, -10)
    V.balao(g["xc"][2], a + fab["pac_l"][0] + fab["gl"] / 2, 3, 14, 6)
    # detalhe step-lap
    F.texto(275, 265, "DETALHE E – JUNTA STEP-LAP (sem escala)", fontsize=7.4, weight="bold")
    ax = F.ax
    for k in range(3):
        y0 = 248 - k * 3.2
        ax.add_patch(Polygon([(272 + k * 5, y0), (310 + k * 5, y0), (318 + k * 5, y0 + 2.6), (280 + k * 5, y0 + 2.6)], closed=True,
                             fc=C["ferro"], ec="k", lw=0.3))
        ax.add_patch(Polygon([(318 + k * 5, y0), (360, y0), (360, y0 + 2.6), (326 + k * 5, y0 + 2.6)], closed=True, fc=C["ferro_esc"],
                             ec="k", lw=0.3))
    F.texto(272, 234, "3 degraus × 5 mm, corte a 45°, 2 lâminas por degrau – reduz perdas e ruído na junta", fontsize=5.8)
    # tabelas: corte, pacotes / calços
    yt = F.tabela(272, 228, ["Peça", "Largura", "Comprimento", "Quantidade"], fab["corte"], [36, 14, 26, 46], fs=5.4)
    F.texto(272, yt - 4, f"Chapa: {d['chapa_dados']['nome']}  ({d['chapa_dados']['norma']})", fontsize=5.6)
    F.texto(272, yt - 8, f"Empilhamento {b:.0f} mm ≈ {fab['n_lam']} lâminas de {fab['t']} mm (fator {d['chapa_dados']['kf']})",
            fontsize=5.6)
    lin = [(f"Lateral (U, W)", d["ng"], f"{fab['gl']:.2f}", f"{fab['gl'] * d['ng']:.2f}", " / ".join(f"{p:.1f}" for p in fab["pac_l"])),
           ("Central (V)", d["ng"], f"{fab['gc']:.2f}", f"{fab['gc'] * d['ng']:.2f}", " / ".join(f"{p:.1f}" for p in fab["pac_c"]))]
    yt2 = F.tabela(272, yt - 14, ["Coluna", "nº calços", "calço (mm)", "total (mm)", "pacotes (mm, de baixo p/ cima)"], lin,
                   [22, 13, 14, 14, 59], fs=5.2)
    F.texto(272, yt2 - 4, "Calço: EP GC 203 retificado ±0,05 mm, colado com epóxi classe H. Valor final AJUSTADO no ensaio", fontsize=5.6)
    F.texto(272, yt2 - 8, "para L = 180 µH ±5 % e desequilíbrio ≤ 3 % (o central é ligeiramente maior para equalizar as fases).",
            fontsize=5.6) if abs(d["requisitos"]["L"] * 1e6 - 180) < 1 else \
        F.texto(272, yt2 - 8, f"para L = {d['requisitos']['L']*1e6:.0f} µH ±5 % e desequilíbrio ≤ 3 %.", fontsize=5.6)
    F.texto(272, yt2 - 13, f"Força magnética por entreferro ≈ {fab['forca']:.0f} N (pico) → aperto ≥ {fab['aperto_N']:.0f} N por coluna.",
            fontsize=5.6)
    F.info["escala_folha"] = f"1:{e:g}"


def folha_bobina(F, g, d, fab):
    a, b = g["a"], g["b"]
    # Corte A-A horizontal
    ext = g["a"] + 2 * (g["c"] + g["build"]) + 20
    e = _esc(max(ext / 110, (g["b"] + 2 * (g["c"] + g["build"]) + 30) / 78), 1)
    V = F.vista(100, 224, e, "CORTE A-A – horizontal no meio da bobina", 28, 274)
    V.ret(-a / 2, -b / 2, a, b, fc=C["ferro"], lw=LW_G, hatch="////")
    r = g["c"]
    V.rret(-a / 2 - r, -b / 2 - r, a + 2 * r, b + 2 * r, r, fill=False, ec="#2c7fb8", lw=LW_F, ls="--")
    V.rret(-a / 2 - r, -b / 2 - r, a + 2 * r, b + 2 * r, r + 0.01, fill=False, ec=C["tubo"], lw=1.2)
    r += g["tube"]
    V.rret(-a / 2 - r, -b / 2 - r, a + 2 * r, b + 2 * r, r, fill=False, ec=C["tubo"], lw=1.2)
    canais = sorted(set(round((k + 1) * g["N"] / (g["nd"] + 1)) for k in range(g["nd"])))
    r += 0.26
    for k in range(g["N"]):
        if k in canais:
            r += g["wd"]
        r += g["tf"]
        V.rret(-a / 2 - r, -b / 2 - r, a + 2 * r, b + 2 * r, r, fill=False, ec=C["bob_esc"], lw=0.5)
        r += 0.26 + (0.13 if k in (0, 1, g["N"] - 2, g["N"] - 1) else 0)
    r += g["wrap"]
    V.rret(-a / 2 - r, -b / 2 - r, a + 2 * r, b + 2 * r, r, fill=False, ec="k", lw=LW_G)
    V.eixo(-a / 2 - r - 6, 0, a / 2 + r + 6, 0)
    V.eixo(0, -b / 2 - r - 6, 0, b / 2 + r + 6)
    V.cota_h(-a / 2, a / 2, -b / 2, -4 - (g["c"] + g["build"]) / e, f"{a:.0f}")
    V.cota_h(a / 2, a / 2 + g["c"], 0, 4, f"c={g['c']:.0f}")
    V.cota_h(a / 2 + g["c"], a / 2 + g["c"] + g["build"], 0, -4, f"{g['build']:.1f}")
    V.cota_h(-a / 2 - g["c"] - g["build"], a / 2 + g["c"] + g["build"], b / 2 + g["c"] + g["build"], 6, f"{g['Dc']:.0f}")
    V.cota_v(-b / 2, b / 2, -a / 2, -4 - (g["c"] + g["build"]) / e, f"{b:.0f}")
    V.cota_v(-b / 2 - g["c"] - g["build"], b / 2 + g["c"] + g["build"], a / 2 + g["c"] + g["build"], 6, f"{g['Ec']:.0f}")
    V.balao(-a / 4, b / 4, 1, -14, 14)
    V.balao(0, -b / 2 - g["c"] - g["tube"] / 2, 6, -10, -12)
    V.balao(a / 2 + g["c"] + g["build"] * 0.5, -b / 2 - g["c"] - g["build"] * 0.5, 2, 14, -12)
    V.balao(-a / 2 - g["c"] - g["build"], 0, 11, -14, 4)
    # Corte B-B vertical pela coluna
    hy = a * 0.4
    eb = _esc(max((g["hw"] + 2 * hy) / 128, (a + 2 * (g["c"] + g["build"]) + 80) / 120), 1)
    VB = F.vista(100, 30 + hy / eb, eb, "CORTE B-B – vertical pela coluna central", 28, 30 + (g["hw"] + 2 * hy) / eb + 4)
    VB.ret(-a / 2 - g["c"] - g["build"] - 25, g["hw"], a + 2 * (g["c"] + g["build"]) + 50, hy, fc=C["ferro"], lw=LW_M, hatch="////")
    VB.ret(-a / 2 - g["c"] - g["build"] - 25, -hy, a + 2 * (g["c"] + g["build"]) + 50, hy, fc=C["ferro"], lw=LW_M, hatch="////")
    y = 0
    for k, ph in enumerate(fab["pac_c"]):
        VB.ret(-a / 2, y, a, ph, fc=C["ferro"], lw=LW_F, hatch="----")
        y += ph
        if k < len(fab["pac_c"]) - 1:
            VB.ret(-a / 2, y, a, fab["gc"], fc=C["gap"], lw=0.2)
            y += fab["gc"]
    y0 = (g["hw"] - g["hc"]) / 2
    for s in (-1, 1):
        xi = s * (a / 2 + g["c"])
        xo = s * (a / 2 + g["c"] + g["build"])
        VB.ret(min(xi, xi + s * g["tube"]), y0 - 6, g["tube"], g["hc"] + 12, fc=C["tubo"], lw=0.3)
        xa, xb = xi + s * g["tube"], xo
        VB.ret(min(xa, xb), y0, abs(xb - xa), g["hc"], fc=C["isol"], lw=LW_M)
        VB.ret(min(xa, xb) + 0.5, y0 + (g["hc"] - g["hf"]) / 2, abs(xb - xa) - 1, g["hf"], fc=C["bob"], lw=0, alpha=0.95)
        for yy in (0, g["hw"] - y0):
            VB.ret(min(xa, xb), yy, abs(xb - xa), y0, fc="#cfe8c4", lw=0.3, hatch="xxx")
    xr = a / 2 + g["c"] + g["build"]
    VB.cota_v(0, y0, xr, 6, f"{y0:.0f}")
    VB.cota_v(y0, y0 + (g["hc"] - g["hf"]) / 2, xr, 6, f"{(g['hc'] - g['hf']) / 2:.0f}")
    VB.cota_v(y0 + (g["hc"] - g["hf"]) / 2, y0 + (g["hc"] + g["hf"]) / 2, xr, 6, f"folha {g['hf']:.0f}")
    VB.cota_v(0, g["hw"], xr, 16, f"{g['hw']:.0f}")
    VB.balao(0, fab["pac_c"][0] + fab["gc"] / 2, 3, -16, 4)
    VB.balao(-(a / 2 + g["c"] + g["build"] / 2), y0 / 2, 9, -14, -4)
    VB.balao(-(a / 2 + g["c"] + g["build"] / 2), g["hw"] / 2, 2, -16, 6)
    VB.balao(a / 2 + g["c"] + g["tube"] / 2, y0 + g["hc"] * 0.8, 6, 14, 8)
    # Tabela de bobinagem (resumida: agrupa espiras normais)
    linhas = []
    for nome, esp, r0, r1 in fab["camadas"]:
        linhas.append((nome, esp, f"{r0:.1f}", f"{r1:.1f}"))
    if len(linhas) > 16:
        cab, cauda = linhas[:5], linhas[-4:]
        meio = ("… espiras intermediárias (folha + aramida 2×0,13) …", "", "", "")
        linhas = cab + [meio] + cauda
    F.texto(212, 272, "TABELA DE BOBINAGEM (por bobina, de dentro para fora; raio a partir da face da coluna)", fontsize=7.4,
            weight="bold")
    yt = F.tabela(212, 268, ["Camada", "Espessura", "r inicial", "r final"], linhas, [100, 18, 18, 18], fs=5.3)
    F.texto(212, yt - 4.5, f"Folha {d['cond_dados']['nome']}: {g['tf']:.1f} × {g['hf']:.0f} mm, bordas sem rebarba e arredondadas;"
                           f" margem de aramida {12:.0f} mm além da borda.", fontsize=5.6)
    F.texto(212, yt - 8.5, f"Espiras: {g['N']} por bobina – sentido de bobinagem IGUAL nas 3 bobinas (horário visto de cima). "
                           f"Comprimento de folha ≈ {fab['comp_folha']:.1f} m/bobina ({fab['massa_folha']:.1f} kg).", fontsize=5.6)
    F.texto(212, yt - 12.5, f"Espira média (MLT) ≈ {fab['MLT']:.0f} mm.  Espessura radial calculada {fab['build_real']:.1f} mm.  "
                            "PTC (item 21) entre as 2 últimas camadas, no meio da altura.", fontsize=5.6)
    # Detalhe terminal
    F.texto(212, 150, "DETALHE D – SAÍDA DA FOLHA E TERMINAL (sem escala)", fontsize=7.4, weight="bold")
    ax = F.ax
    ax.add_patch(Rectangle((215, 102), 3, 38, fc=C["bob"], ec="k", lw=0.4))
    ax.add_patch(Rectangle((218, 114), 38, 7, fc="#c8c8c8" if d["cond"] == "AL" else C["cu"], ec="k", lw=0.4))
    ax.add_patch(Rectangle((256, 111), 34, 13, fc=C["cu"], ec="k", lw=0.4))
    for xx in (264, 282):
        ax.add_patch(Circle((xx, 117.5), 3.2, fc="white", ec="k", lw=0.4))
    ax.annotate("", (264, 128), (282, 128), arrowprops=dict(arrowstyle="<|-|>", lw=0.35, color=C["cota"], mutation_scale=4.5))
    ax.text(273, 129, "44,5", fontsize=5.6, ha="center", color=C["cota"])
    ax.text(256, 106.5, "furos Ø13 (NEMA 2 furos)", fontsize=5.6)
    ax.text(215, 143, "folha (largura total)", fontsize=5.6)
    ax.text(219, 123, ("barra Al 40×6 soldada TIG em toda a largura" if d["cond"] == "AL" else "barra Cu 40×6 brasada em toda a largura"),
            fontsize=5.4)
    ax.text(256, 102.5, ("placa bimetálica Cu-Al ou Al estanhado" if d["cond"] == "AL" else "Cu estanhado"), fontsize=5.4)
    F.info["escala_folha"] = f"A-A 1:{e:g} / B-B 1:{eb:g}"


def folha_3d(F, g, d):
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    ax = F.fig.add_axes([0.04, 0.2, 0.62, 0.74], projection="3d")
    ax.patch.set_alpha(0)
    TODAS_F, TODAS_C = [], []
    luz = np.array([0.35, -0.6, 0.72])
    luz = luz / np.linalg.norm(luz)

    def sombra(cor, n):
        import matplotlib.colors as mc
        rgb = np.array(mc.to_rgb(cor))
        k = 0.55 + 0.45 * max(float(np.dot(n, luz)), 0)
        return tuple(np.clip(rgb * k, 0, 1))

    def poli(faces, cor, alpha=1.0, lw=0.15):
        cols = []
        for f in faces:
            f = np.array(f)
            n = np.cross(f[1] - f[0], f[2] - f[0])
            nn = np.linalg.norm(n)
            n = n / nn if nn > 0 else np.array([0, 0, 1])
            if n[1] > 0.0001 and False:
                pass
            cols.append(sombra(cor, n if np.dot(n, [0.3, -1, 0.3]) > 0 else -n))
        TODAS_F.extend(faces)
        TODAS_C.extend(cols)

    def caixa(x0, y0, z0, dx, dy, dz, cor, alpha=1.0):
        if dx > 120:                                   # subdivide peças longas: melhora a ordem de pintura do 3D
            n = int(math.ceil(dx / 50))
            for k in range(n):
                caixa(x0 + k * dx / n, y0, z0, dx / n, dy, dz, cor, alpha)
            return
        if dz > 160:
            n = int(math.ceil(dz / 60))
            for k in range(n):
                caixa(x0, y0, z0 + k * dz / n, dx, dy, dz / n, cor, alpha)
            return
        X, Y, Z = [x0, x0 + dx], [y0, y0 + dy], [z0, z0 + dz]
        v = np.array([[X[i], Y[j], Z[k]] for i in (0, 1) for j in (0, 1) for k in (0, 1)])
        fs = [[0, 1, 3, 2], [4, 5, 7, 6], [0, 1, 5, 4], [2, 3, 7, 6], [0, 2, 6, 4], [1, 3, 7, 5]]
        poli([v[f] for f in fs], cor, alpha)

    def prisma_arred(cx, cy, w, h, r, z0, z1, cor):
        pts = _rret_pts(cx, cy, w, h, r)
        lados = [[(pts[i][0], pts[i][1], z0), (pts[i + 1][0], pts[i + 1][1], z0), (pts[i + 1][0], pts[i + 1][1], z1),
                  (pts[i][0], pts[i][1], z1)] for i in range(len(pts) - 1)]
        topo = [[(x, y, z1) for x, y in pts]]
        base = [[(x, y, z0) for x, y in pts]]
        poli(lados + topo + base, cor, 1.0, 0.05)

    a, b, W, H, hw = g["a"], g["b"], g["W"], g["H"], g["hw"]
    yb = -g["fr"] - g["base_h"]
    xb0 = g["xr"][0] - 40
    caixa(xb0, -g["Bb"] / 2, yb, g["Lb"], g["Bb"], 10, "#9a9a9a")
    for s in (-1, 1):
        caixa(xb0, s * (g["Bb"] / 2) - (0 if s < 0 else 50), yb + 10, g["Lb"], 50, g["base_h"] - 10, "#8d8d8d")
    caixa(0, -b / 2, 0, W, b, a, C["ferro"])
    caixa(0, -b / 2, H - a, W, b, a, C["ferro"])
    for i in range(3):
        caixa(i * g["pitch"], -b / 2, a, a, b, hw, C["ferro_esc"])
    for i, xc in enumerate(g["xc"]):
        prisma_arred(xc, 0, g["Dc"], g["Ec"], g["rc"], g["yc0"], g["yc0"] + g["hc"], C["bob"])
        for s in (-1, 1):
            xt = xc + s * g["Dc"] * 0.28
            caixa(xt - 20, -b / 2 - g["c"] - 3, g["yc0"] + g["hc"], 40, 6, H + g["fr"] + g["term_h"] - g["yc0"] - g["hc"], C["cu"])
    for z in (-g["fr"], H):
        caixa(g["xr"][0] - 18, -b / 2 - g["fe"], z, g["xr"][1] - g["xr"][0] + 36, g["fe"], g["fr"], C["aco"])
        caixa(g["xr"][0] - 18, b / 2, z, g["xr"][1] - g["xr"][0] + 36, g["fe"], g["fr"], C["aco"])
    for x in g["xr"]:
        for yy in (-b / 2 - 25, b / 2 + 25):
            caixa(x - 6, yy - 6, -g["fr"] - 12, 12, 12, H + 2 * g["fr"] + 24, "#cfcfcf")
    caixa(W - 75, -b / 2 - g["fe"] - 30, H + g["fr"], 55, 30, 30, "#e6e6e6")
    pc = Poly3DCollection(TODAS_F, facecolors=TODAS_C, edgecolors=TODAS_C, linewidths=0.4)   # sem costuras visíveis
    pc.set_sort_zpos(None)
    ax.add_collection3d(pc)
    ax.set_box_aspect((g["Lb"], g["Bb"] + 40, H + 2 * g["fr"] + g["base_h"] + g["term_h"]))
    ax.set_xlim(xb0, xb0 + g["Lb"])
    ax.set_ylim(-g["Bb"] / 2 - 20, g["Bb"] / 2 + 20)
    ax.set_zlim(yb, H + g["fr"] + g["term_h"])
    ax.view_init(20, -58)
    ax.axis("off")
    F.texto(275, 262, "VISTA ISOMÉTRICA 3D (sombreada)", fontsize=8, weight="bold")
    m = d["massa_kg"]
    r = d["requisitos"]
    resumo = [
        ("L por fase", f"{r['L']*1e6:.0f} µH ±5 %"), ("Corrente nominal", f"{r['In']:.0f} A (pico {r['Ipk']:.0f} A)"),
        ("Isat / sobrecarga", f"≥ {r['Isat']:.0f} A (L ≥ 90 %) / {r['Iovl']:.0f} A (L ≥ 70 %)"),
        ("Chaveamento", f"{r['fs']/1e3:.0f} kHz (tensão PWM, barramento ≈ {r['Vdc']:.0f} V)"),
        ("Isolação", f"Sistema classe {r['classe']} – elevação média ≤ {d['termico']['meta_elev_K']:.0f} K"),
        ("Perdas (calc.)", f"{d['perdas']['total']:.0f} W"), ("Elevação (calc.)", f"{d['termico']['elev_bobina_K']:.0f} K"),
        ("Massa (calc.)", f"{m['total']:.0f} kg (núcleo {m['nucleo']:.0f} / folha {m['condutor']:.0f})"),
        ("Dimensões", f"{g['Lb']:.0f} × {g['Bb']:.0f} × {g['base_h'] + 2 * g['fr'] + H + g['term_h']:.0f} mm (C × L × A)"),
    ]
    F.tabela(272, 255, ["Característica", "Valor"], resumo, [34, 100], fs=5.8, h=5)


def folha_bom(F, d, fab):
    lm = lista_materiais(d)
    F.texto(25, 272, "LISTA DE MATERIAIS (itens = balões dos desenhos)", fontsize=8, weight="bold")
    yt = F.tabela(25, 268, ["Item", "Descrição", "Especificação", "Qtd.", "Norma"], lm, [10, 42, 150, 18, 40], fs=5.2, h=4.6)
    F.texto(25, yt - 6, "FICHA DE FABRICAÇÃO – SEQUÊNCIA", fontsize=7.6, weight="bold")
    y = yt - 10
    for i, s in enumerate(fab["sequencia"], start=1):
        F.texto(25, y, f"{i:>2}. {s}", fontsize=5.6)
        y -= 4.1
    notas = ("NOTAS:  1) A classe térmica é do SISTEMA de isolação (IEC 60085 / IEC 61857): todos os materiais com índice térmico ≥ classe; "
             "proibido DMD, GPO-3 e cabo PVC em classe H.   2) Núcleo aterrado em UM ponto; nenhum parafuso atravessa as chapas.   "
             "3) Calços colados + VPI: evitam ruído/vibração a 4–8 kHz.   4) Separação ≥ 10 mm e escoamento ≥ 16 mm entre partes vivas e massa "
             "(IEC 60664-1, cat. III, PD3, 1000 V).   5) Protótipo obrigatório com ensaio de aquecimento em inversor.")
    import textwrap
    for k, l in enumerate(textwrap.wrap(notas, 190)):
        F.texto(25, y - 3 - 4 * k, l, fontsize=5.6)


def lista_materiais(d):
    g = geo_mm(d)
    ch, cond = d["chapa_dados"], d["cond_dados"]
    m = d["massa_kg"]
    ng = g["ng"]
    linhas = [
        ("1", "Núcleo – chapas", f"{ch['nome']}; culatras a 45° step-lap 3 degraus; colunas em {ng + 1} pacotes", f"{m['nucleo']:.0f} kg", ch["norma"]),
        ("2", "Enrolamento", f"{cond['nome']} {g['tf']:.1f} × {g['hf']:.0f} mm, {g['N']} espiras/bobina, 3 bobinas", f"{m['condutor']:.0f} kg", cond["norma"]),
        ("3", "Calços do entreferro", f"EP GC 203 retificado: laterais {g['gaps'][0]/ng:.2f} mm, central {g['gaps'][1]/ng:.2f} mm, {ng} por coluna",
         f"{3 * ng} pç", "IEC 60893-3-2"),
    ]
    for k, it in enumerate(d["isolacao"], start=4):
        linhas.append((str(k), it["item"], it["mat"], "cj.", it["norma"]))
    k = len(linhas) + 1
    linhas += [
        (str(k), "Cantoneiras de aperto", "Aço carbono L 2½\" × ¼\", pintura epóxi; isoladas do núcleo por EP GC 203 2 mm", "4 pç", "ABNT NBR 6648"),
        (str(k + 1), "Tirantes", "Barra roscada M12 classe 8.8 zincada, porca + arruela de pressão, FORA do núcleo", "4 pç", "ISO 898-1"),
        (str(k + 2), "Base", "Perfil U 4\" (2 pç) com furos oblongos Ø14 × 25", "2 pç", "ABNT NBR 6355"),
        (str(k + 3), "Terminais", "Barra Cu estanhada 40 × 6 mm, 2 furos Ø13 a 44,5 mm (Al: placa bimetálica Cu-Al)", "6 pç", "NEMA CC1 / IEC 60445"),
        (str(k + 4), "Aterramento", "Cordoalha Cu 25 mm² núcleo → estrutura (1 ponto) + terminal PE M8 na base", "1 cj.", "IEC 60364-5-54"),
        (str(k + 5), "Olhais de içamento", "Olhal M12 forjado nas cantoneiras superiores", "2 pç", "DIN 580"),
        (str(k + 6), "Caixa de bornes do sensor", "Caixa com bornes 2,5 mm², cabo silicone 180 °C até o PTC", "1 cj.", "IEC 60947-7-1"),
        (str(k + 7), "Placa de identificação", "Inox gravado: L, In, fs, classe, elevação, perdas, massa, nº de série, data", "1 pç", "IEC 60076-6"),
    ]
    return linhas


def gerar_pdf(d, pdf_path, info, png_dir=None):
    g = geo_mm(d)
    fab = fabricacao(d)
    total = 5
    with PdfPages(pdf_path) as pdf:
        for n, (nome, fun) in enumerate([("Conjunto – vistas", lambda F: folha_conjunto(F, g, d)),
                                         ("Núcleo – chapas, step-lap, pacotes e calços", lambda F: folha_nucleo(F, g, d, fab)),
                                         ("Bobina – cortes, bobinagem e terminal", lambda F: folha_bobina(F, g, d, fab)),
                                         ("Vista 3D e características", lambda F: folha_3d(F, g, d)),
                                         ("Lista de materiais, ficha de fabricação e notas", lambda F: folha_bom(F, d, fab))], start=1):
            inf = dict(info)
            F = Folha(inf, n, total, nome)
            fun(F)
            F.salvar(pdf, os.path.join(png_dir, f"Indutor_folha{n}.png") if png_dir else None)
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
