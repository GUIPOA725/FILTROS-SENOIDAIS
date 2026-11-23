"""Desenhos do PROJETO DE REFERÊNCIA do indutor – padrão de fábrica (v1.10.3).

Folhas A3 paisagem (ABNT NBR 10068 / 10582), 1º diedro, escalas normalizadas, carimbo com tabela de revisões, cotas em cadeia,
balões numerados ligados à lista de materiais. Tudo desenhado em milímetros reais sobre a folha (escala aplicada por vista).
Folhas: 1 Conjunto (vistas) · 2 Núcleo (chapas, step-lap, pacotes, calços) · 3 Bobina (cortes, tabela de bobinagem,
terminal) · 4 Vista 3D · 5 Lista de materiais, ficha de fabricação e notas.
O fabricante emite o desenho de fabricação próprio a partir deste e declara as diferenças.
"""
import math
from .ind_projeto import descr_condutor
from .ind_estrutura import texto_padrao
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



def _banco(d):
    return bool((d.get("requisitos") or {}).get("aplicacao"))


def _tol(d):
    """v1.13.0: tolerância de L (±5 % filtro senoidal; ±3 % dessintonizado; ±2 % sintonizado)."""
    return f"{float((d.get('requisitos') or {}).get('tol_L_pct', 5)):g}".replace(".", ",")

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
    f = d.get("fio")
    g["fio"] = ({k: (v * 1e3 if k in ("t", "h", "iso", "t_cam") else v) for k, v in f.items()} if f else None)
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
    from .ind_estrutura import estrutura                   # v1.11.6: estrutura padrão nacional (quadros U, saídas horizontais)
    e = estrutura(g, d)
    g["est"] = e
    g["Lb"] = e["env"][1] - e["env"][0]
    g["Bb"] = e["env"][3] - e["env"][2]
    g["Ht"] = e["env"][5] - e["env"][4]
    return g


def fabricacao(d):
    """Dados de fabricação derivados do projeto (tabelas usadas nos desenhos e no memorial)."""
    from .ind_estrutura import texto_padrao
    g = geo_mm(d)
    ch, cond = d["chapa_dados"], d["cond_dados"]
    t = ch["esp_mm"]
    n_lam = int(round(g["b"] * ch["kf"] / t))
    ng = g["ng"]
    gl, gc = g["gaps"][0] / ng, g["gaps"][1] / ng
    # pacotes da coluna: entreferros centrados em hw(k+0,5)/ng
    def pacotes(gcada):
        if d.get("pos_gap") == "culatra":           # v1.11.1: 2 calços nas juntas coluna–culatra (coluna inteira entre eles)
            return [0.0, g["hw"] - 2 * gcada, 0.0]
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
    fw = g.get("fio")
    if fw:                                                  # v1.11.2: fio retangular em camadas
        canais = sorted(set(round((k + 1) * fw["n_cam"] / (g["nd"] + 1)) for k in range(g["nd"])))
        esp_cam = fw["np"] * (fw["t"] + fw["iso"])
        for j in range(fw["n_cam"]):
            if j in canais:
                camadas.append((f"Canal axial (réguas EP GC 203 {g['wd']:.0f} mm)", f"{g['wd']:.1f}", r, r + g["wd"]))
                r += g["wd"]
            camadas.append((f"Camada {j + 1}: {fw['n_ax']} espiras × {fw['np']} fio(s) {fw['t']:.2f}×{fw['h']:.1f} (isolado)",
                            f"{esp_cam:.2f}", r, r + esp_cam))
            r += esp_cam
            camadas.append((f"Aramida entre camadas {fw['t_cam']:.2f}" if j < fw["n_cam"] - 1 else f"Aramida final {fw['t_cam']:.2f}",
                            f"{fw['t_cam']:.2f}", r, r + fw["t_cam"]))
            r += fw["t_cam"]
    else:
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
    comp_folha = g["N"] * MLT / 1000 * (fw["np"] if fw else 1)          # fio: comprimento total de fio (todos os paralelos)
    A_mm2 = (fw["np"] * fw["t"] * fw["h"]) if fw else g["tf"] * g["hf"]
    massa_folha = g["N"] * MLT / 1000 * A_mm2 * 1e-6 * cond["dens"]
    forca = d.get("forca_gap_N", 0)
    return dict(
        n_lam=n_lam, t=t, pac_l=pac_l, pac_c=pac_c, gl=gl, gc=gc, camadas=camadas, build_real=r - g["c"], comp_folha=comp_folha,
        massa_folha=massa_folha, MLT=MLT, forca=forca, aperto_N=max(2.5 * forca, 2000),
        corte=[("Coluna (pacotes)", f"{g['a']:.0f}", "ver pacotes", (f"3 × 1 coluna inteira × {n_lam} lâminas" if d.get("pos_gap") == "culatra" else f"3 × {ng + 1} pacotes × {n_lam} lâminas")),
               ("Culatra superior", f"{g['a']:.0f}", f"{g['W']:.0f} (45°)", f"{n_lam} lâminas"),
               ("Culatra inferior", f"{g['a']:.0f}", f"{g['W']:.0f} (45°)", f"{n_lam} lâminas")],
        sequencia=[
            "Cortar chapas (guilhotina/estampo) e rebarbar: rebarba ≤ 0,02 mm; recozer se o fornecedor da chapa exigir.",
            *([f"Montar a culatra inferior; colunas inteiras de {g['b']:.0f} mm (≈ {n_lam} lâminas) com faces de topo retificadas – junta de TOPO "
               f"(não step-lap) com as culatras, onde ficam os entreferros.",
               f"Colar os calços EP GC 203 nas DUAS juntas coluna–culatra (lat. {gl:.2f} mm / cen. {gc:.2f} mm cada) com epóxi classe H."]
              if d.get("pos_gap") == "culatra" else
              [f"Montar a culatra inferior e as colunas em pacotes de {g['b']:.0f} mm (≈ {n_lam} lâminas), junta step-lap 3 degraus × 5 mm nas culatras.",
               f"Colar os calços EP GC 203 entre pacotes (lat. {gl:.2f} mm / cen. {gc:.2f} mm) com epóxi classe H; retificar faces dos pacotes."]),
            *([f"Bobinar as 3 bobinas sobre mandril com o tubo EP GC 203: {fw['n_cam']} camada(s) × {fw['n_ax']} espiras de "
               f"{fw['np']} fio(s) retangular(es) {fw['t']:.2f} × {fw['h']:.1f} mm em paralelo, aramida {fw['t_cam']:.2f} mm entre camadas, "
               "espiras encostadas (sem folga axial), calço de cunha nas extremidades de cada camada.",
               (f"TRANSPOR os {fw['np']} fios em paralelo: permutar a posição radial dos fios a cada 1/{fw['np']} do comprimento da bobina "
                "(ou usar cabo transposto); sem transposição, aparecem correntes de circulação e as perdas sobem."
                if fw["np"] > 1 else "Fio único por espira: sem necessidade de transposição."),
               ("Saídas: " + texto_padrao(g, d)["saida"] + "; todas as saídas para o MESMO lado (frente), fora da região das juntas "
                "coluna–culatra (≥ 25 mm); " + ("unir os fios em paralelo na barra de saída; " if fw["np"] > 1 else "")
                + "instalar PTC entre as 2 últimas camadas.")] if fw else
              [f"Bobinar as 3 bobinas sobre mandril com o tubo EP GC 203 (folha {g['tf']:.1f} × {g['hf']:.0f} mm, {g['N']} espiras, aramida entre espiras, reforço nas 2 primeiras/últimas).",
               "Soldar as barras de saída (TIG, largura total da folha) antes de bobinar a espira inicial e depois da final; instalar PTC entre as últimas camadas."]),
            "Encaixar as bobinas nas colunas com calços de extremidade; fechar a culatra superior "
            + ("(junta de topo sobre os calços)." if d.get("pos_gap") == "culatra" else "(step-lap)."),
            f"Prensar o conjunto: força de aperto ≥ {max(2.5 * forca, 2000):.0f} N por coluna nos entreferros (quadros em U + tirantes "
            f"{g['est']['perfil']['rosca']} 8.8 nas buchas, torque {80 if g['est']['perfil']['d_tir'] <= 12 else 160} N·m), quadros isolados do núcleo por EP GC 203 2 mm.",
            f"Medir L por fase na corrente nominal (ou fonte CA + ponte LCR em 60 Hz com correção) e ajustar o calço: L ±{_tol(d)} %, desequilíbrio ≤ 3 %.",
            "Impregnar por VPI com resina classe H; curar na estufa conforme fabricante da resina; retocar pintura da estrutura.",
            "Ensaios de rotina (resistência, L, tensão aplicada 3 kV/1 min, isolamento) e de tipo no protótipo (perdas, aquecimento "
            + ("com a corrente térmica (fundamental + harmônicas), linearidade L × I)." if d["requisitos"].get("aplicacao") else "com inversor, L × I)."),
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
COR_EST = dict(estrutura="#c3c7cb", zinco="#d6d6d6", estanho="#e4e4dc", cobre_bar="#c8763c", placa="#f6f6f6", ptc="#e9e9e9")


def _elems_est(g, vista):
    """Projeção das peças da estrutura (v1.11.6). vista: 'frente' (x,z), 'lado' (u=-y, z – vista lateral esquerda), 'topo' (x,y).
    Devolve lista (prof, tipo, args, cor) ordenada do mais distante para o mais próximo do observador."""
    e = g["est"]
    out = []
    for nome, mat, (x0, x1, y0, y1, z0, z1) in e["caixas"]:
        if vista == "frente":
            out.append((-(y0 + y1) / 2, "ret", (x0, z0, x1 - x0, z1 - z0), COR_EST.get(mat, "#ddd")))
        elif vista == "lado":
            out.append(((x0 + x1) / 2, "ret", (-y1, z0, y1 - y0, z1 - z0), COR_EST.get(mat, "#ddd")))
        else:
            out.append(((z0 + z1) / 2, "ret", (x0, y0, x1 - x0, y1 - y0), COR_EST.get(mat, "#ddd")))
    for nome, mat, (xc, yc, z0, z1), r, _ in e["cilindros"]:
        if vista == "frente":
            out.append((-yc, "ret", (xc - r, z0, 2 * r, z1 - z0), COR_EST.get(mat, "#ddd")))
        elif vista == "lado":
            out.append((xc, "ret", (-yc - r, z0, 2 * r, z1 - z0), COR_EST.get(mat, "#ddd")))
        else:
            out.append((z1, "circ", (xc, yc, r), COR_EST.get(mat, "#ddd")))
    for (hx, hy, hz), eixo, r, _ in e["furos"]:
        if vista == "frente" and eixo == "y":
            out.append((-hy + 0.1, "circ", (hx, hz, r), "white"))
        elif vista == "topo" and eixo == "z":
            out.append((hz + 0.1, "circ", (hx, hy, r), "white"))
    out.sort(key=lambda q: q[0])
    return out


def _desenha_est(V, elems, filtro):
    for prof, tipo, args, cor in elems:
        if not filtro(prof):
            continue
        if tipo == "ret":
            V.ret(*args, fc=cor, lw=LW_F)
        else:
            V.circ(*args, fc=cor, lw=LW_F)


def folha_conjunto(F, g, d):
    a, W, H, hw, ww, b = g["a"], g["W"], g["H"], g["hw"], g["ww"], g["b"]
    est = g["est"]
    ex0, ex1, ey0, ey1, ez0, ez1 = est["env"]
    yb, ytop = ez0, ez1
    Htot = ytop - yb
    x_min, x_max = ex0, ex1
    D = ey1 - ey0
    e = _esc(max((x_max - x_min + D + 90) / 270, (Htot + D + 60) / 215), 1)
    # ---- posições na folha (1º diedro: lateral esquerda à DIREITA da frontal; superior ABAIXO da frontal) ----
    ox = 32 - x_min / e
    oy = 262 - ytop / e
    V = F.vista(ox, oy, e, "VISTA FRONTAL", 32, 278)
    el = _elems_est(g, "frente")
    _desenha_est(V, el, lambda p: p < 0)                         # peças de trás (atrás do núcleo)
    V.ret(0, 0, W, H, fc=C["ferro"], lw=LW_G)
    for i in range(2):
        V.ret(a + i * g["pitch"], a, ww, hw, fc="white", lw=LW_M)
    for i, xc in enumerate(g["xc"]):
        V.rret(xc - g["Dc"] / 2, g["yc0"], g["Dc"], g["hc"], 6, fc=C["bob"], lw=LW_G)
        V.txt(xc, g["yc0"] + g["hc"] * 0.42, "UVW"[i], ha="center", va="center", fontsize=10, weight="bold", color="white")
        V.eixo(xc, yb - 4, xc, ytop + 4)
    _desenha_est(V, el, lambda p: p >= 0)                        # peças da frente
    for tr in est["terminais"]:
        ch = tr["chapa"]
        V.txt(tr["x"], (ch[5] + 4) if tr["pos"] == "sup" else (ch[4] - 12), tr["nome"], ha="center", fontsize=6.0, weight="bold")
    # cotas
    V.cota_h(x_min, x_max, yb, -6, f"{x_max - x_min:.0f} (quadros)")
    V.cota_h(0, W, yb, -12, f"{W:.0f} (núcleo)")
    xs = [0, a, a + ww, 2 * a + ww, 2 * a + 2 * ww, W]
    for p_, q in zip(xs[:-1], xs[1:]):
        V.cota_h(p_, q, yb, -18, f"{q - p_:.0f}")
    V.cota_h(g["xc"][0], g["xc"][1], ytop, 8, f"passo {g['pitch']:.0f}")
    V.cota_h(g["xc"][1], g["xc"][2], ytop, 8, f"{g['pitch']:.0f}")
    V.cota_v(yb, ytop, x_max, 14, f"{Htot:.0f} (total)")
    V.cota_v(0, H, x_max, 7, f"{H:.0f}")
    V.cota_v(g["yc0"], g["yc0"] + g["hc"], x_min, -6, f"bobina {g['hc']:.0f}")
    # balões (itens da lista de materiais)
    tr0 = est["terminais"][-1]
    xr, _ = est["tirantes"][0]
    zq0, zq1 = est["quadros"]["sup"]
    V.balao(a * 0.5, H - a * 0.5, 1, -8, 10)
    V.balao(g["xc"][0] - g["Dc"] * 0.3, g["yc0"] + g["hc"] * 0.3, 2, -10, -8)
    V.balao(W * 0.45, (zq0 + zq1) / 2, 14, 4, 13)
    V.balao(xr, (a + H - a) / 2, 15, -9, 6)
    V.balao(x_max - est["ext"] / 2, yb + 2, 16, 8, -7)
    V.balao(tr0["x"], tr0["chapa"][5], 17, 14, 6)
    V.balao(x_min + est["ext"] / 2, (zq0 + zq1) / 2, 19, -6, 11)
    V.balao(x_max - 47, ytop - 6, 20, 9, 6)
    # ---- vista lateral esquerda (u = -y: frente/terminais à direita) ----
    oxl = ox + (x_max + 25) / e - (-ey1) / e
    VL = F.vista(oxl, oy, e, "VISTA LATERAL ESQUERDA", oxl + (-ey1) / e, 278)
    ell = _elems_est(g, "lado")
    _desenha_est(VL, ell, lambda p: p > W / 2)
    VL.ret(-b / 2, 0, b, H, fc=C["ferro"], lw=LW_G)
    VL.rret(-g["Ec"] / 2, g["yc0"], g["Ec"], g["hc"], 6, fc=C["bob"], lw=LW_G)
    _desenha_est(VL, ell, lambda p: p <= W / 2)
    VL.eixo(0, yb - 4, 0, ytop + 4)
    VL.cota_h(-ey1, -ey0, yb, -6, f"{D:.0f}")
    VL.cota_h(-g["Ec"] / 2, g["Ec"] / 2, yb, -12, f"bobina {g['Ec']:.0f}")
    VL.cota_h(-b / 2, b / 2, ytop, 8, f"empilh. {b:.0f}")
    VL.txt(-ey0 - 2, yb - 22, "frente\n(saídas)", ha="right", fontsize=5.4)
    # ---- vista superior / furação ----
    oys = oy + (yb / e) - 26 - ey1 / e
    VS = F.vista(ox, oys, e, "VISTA SUPERIOR / FURAÇÃO DOS PÉS", 32, oys + ey1 / e + 4)
    els = _elems_est(g, "topo")
    for xc in g["xc"]:
        VS.rret(xc - g["Dc"] / 2, -g["Ec"] / 2, g["Dc"], g["Ec"], g["rc"], fc=C["bob"], lw=LW_G)
    VS.ret(0, -b / 2, W, b, fc=C["ferro"], lw=LW_G)                 # culatra superior cobre as bobinas
    for xc in g["xc"]:
        VS.eixo(xc, ey0 - 3, xc, ey1 + 3)
    _desenha_est(VS, els, lambda p: True)
    VS.txt(W / 2, 0, "placa", ha="center", va="center", fontsize=5.2)
    pes = [f[0] for f in est["furos"] if f[3].startswith("oblongo")]
    for (hx, hy, hz) in pes:
        VS.rret(hx - 12.5, hy - 7, 25, 14, 7, fc="white", lw=LW_M, ls="--")
    xf0, xf1 = min(p[0] for p in pes), max(p[0] for p in pes)
    yf0, yf1 = min(p[1] for p in pes), max(p[1] for p in pes)
    VS.cota_h(xf0, xf1, ey0, -6, f"{xf1 - xf0:.0f} (furos dos pés)")
    VS.cota_v(yf0, yf1, x_max, 7, f"{yf1 - yf0:.0f}")
    VS.txt(x_max + 34, 0, "4× furo oblongo\n14 × 25 na aba\ninferior do quadro", fontsize=5.4, va="center")
    F.info["escala_folha"] = f"1:{e:g}"
    # quadro de dados à direita
    r = d["requisitos"]
    dados = [("L por fase", f"{r['L']*1e6:.0f} µH ±{_tol(d)} %"), ("In" if not r.get("aplicacao") else "I térmica", f"{r['In']:.0f} A  (pico {r['Ipk']:.0f} A)"),
             ("Isat", f"≥ {r['Isat']:.0f} A com L ≥ 90 %") if not r.get("aplicacao") else
             ("Linearidade", f"L ≥ 95 % até {r.get('linearidade', 1.8):g}×I1 ({r['Isat']:.0f} A pico)".replace(".", ",")),
             ("Sobrecarga", f"{r['Iovl']:.0f} A com L ≥ 70 %"),
             ("fs", f"{r['fs']/1e3:.0f} kHz – tensão PWM") if not r.get("aplicacao") else
             ("Aplicação", f"{r['aplicacao'][:34]}"), ("Isolação", f"sistema classe {r['classe']}, 1,1 kV"),
             ("Elevação", f"≤ {d['termico']['meta_elev_K']:.0f} K (calc. {d['termico']['elev_bobina_K']:.0f} K)"),
             ("Perdas", f"{d['perdas']['total']:.0f} W (calc.)"), ("Massa", f"{d['massa_kg']['total']:.0f} kg (calc.)"),
             ("Montagem", "padrão reator nacional: quadros U,"), ("", "tirantes nas buchas, saídas horizontais")]
    F.tabela(300, 140, ["Característica", "Valor"], dados, [30, 72], fs=5.8, h=4.8)


def folha_nucleo(F, g, d, fab):
    a, W, H, hw, ww, b = g["a"], g["W"], g["H"], g["hw"], g["ww"], g["b"]
    e = _esc(max(W / 200, H / 150), 1)
    V = F.vista(35, 120, e, "NÚCLEO – PLANTA DAS CHAPAS (vista frontal, sem bobinas)", 35, 272)
    V.ret(0, 0, W, H, fc=C["ferro"], lw=LW_G)
    for i in range(2):
        V.ret(a + i * g["pitch"], a, ww, hw, fc="white", lw=LW_M)
    # v1.26.4 (auditoria BCD-09): com os entreferros nas culatras a junta é de TOPO (colunas inteiras sobre os calços) – o
    # desenho não pode mostrar step-lap; juntas a 45° (step-lap) só na construção com entreferros distribuídos
    _topo = d.get("pos_gap") == "culatra"
    if _topo:
        for yy in (a, a + hw):
            V.lin([0, W], [yy, yy], lw=LW_F, color="k")
    else:
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
        if ph > 0.05:
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
    # detalhe da junta
    if _topo:
        F.texto(275, 265, "DETALHE E – JUNTA DE TOPO sobre o calço de entreferro (sem escala)", fontsize=7.4, weight="bold")
        ax = F.ax
        ax.add_patch(Polygon([(272, 252), (360, 252), (360, 258), (272, 258)], closed=True, fc=C["ferro_esc"], ec="k", lw=0.3))
        ax.add_patch(Polygon([(296, 250.4), (336, 250.4), (336, 252), (296, 252)], closed=True, fc="#e8c36a", ec="k", lw=0.3))
        ax.add_patch(Polygon([(296, 238), (336, 238), (336, 250.4), (296, 250.4)], closed=True, fc=C["ferro"], ec="k", lw=0.3))
        F.texto(338, 254.2, "culatra", fontsize=5.6)
        F.texto(338, 250.4, "calço EP GC 203", fontsize=5.6)
        F.texto(338, 243, "coluna inteira (topo retificado)", fontsize=5.6)
        F.texto(272, 234, "Colunas inteiras com as faces de topo retificadas; a junta com a culatra é de TOPO, sobre o calço (NÃO step-lap)", fontsize=5.8)
    else:
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
        F.texto(272, yt2 - 8, f"para L = {d['requisitos']['L']*1e6:.0f} µH ±{_tol(d)} % e desequilíbrio ≤ 3 %.", fontsize=5.6)
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
    fw = g.get("fio")
    if fw:
        canais = sorted(set(round((k + 1) * fw["n_cam"] / (g["nd"] + 1)) for k in range(g["nd"])))
        r += 0.26
        for j in range(fw["n_cam"]):
            if j in canais:
                r += g["wd"]
            for p in range(fw["np"]):
                r += fw["t"] + fw["iso"]
                V.rret(-a / 2 - r, -b / 2 - r, a + 2 * r, b + 2 * r, r, fill=False, ec=C["bob_esc"], lw=0.5)
            r += fw["t_cam"]
    else:
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
        if fw:                                              # cada fio desenhado (camadas × espiras × paralelos)
            yb0 = y0 + (g["hc"] - g["hf"]) / 2
            rr = abs(xa) - abs(xi) + 0.26
            for j in range(fw["n_cam"]):
                for p in range(fw["np"]):
                    xx = s * (abs(xi) + rr + p * (fw["t"] + fw["iso"]) + fw["iso"] / 2)
                    for k in range(fw["n_ax"]):
                        VB.ret(min(xx, xx + s * fw["t"]), yb0 + k * (fw["h"] + fw["iso"]) + fw["iso"] / 2, fw["t"], fw["h"],
                               fc=C["bob"], lw=0.15)
                rr += fw["np"] * (fw["t"] + fw["iso"]) + fw["t_cam"]
        else:
            VB.ret(min(xa, xb) + 0.5, y0 + (g["hc"] - g["hf"]) / 2, abs(xb - xa) - 1, g["hf"], fc=C["bob"], lw=0, alpha=0.95)
        for yy in (0, g["hw"] - y0):
            VB.ret(min(xa, xb), yy, abs(xb - xa), y0, fc="#cfe8c4", lw=0.3, hatch="xxx")
    xr = a / 2 + g["c"] + g["build"]
    VB.cota_v(0, y0, xr, 6, f"{y0:.0f}")
    VB.cota_v(y0, y0 + (g["hc"] - g["hf"]) / 2, xr, 6, f"{(g['hc'] - g['hf']) / 2:.0f}")
    VB.cota_v(y0 + (g["hc"] - g["hf"]) / 2, y0 + (g["hc"] + g["hf"]) / 2, xr, 6, (f"bobina {g['hf']:.0f}" if fw else f"folha {g['hf']:.0f}"))
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
    if fw:
        F.texto(212, yt - 4.5, f"{'Barra' if (fw['t'] >= 5 or fw['h'] >= 16) else 'Fio'} retangular {('Al 1350-O' if d['cond'] == 'AL' else 'Cu ETP')} {fw['t']:.2f} × {fw['h']:.1f} mm, cantos "
                               f"arredondados, papel aramida enrolado (classe H); {fw['np']} em paralelo" + (" TRANSPOSTOS." if fw["np"] > 1 else "."),
                fontsize=5.6)
        F.texto(212, yt - 8.5, f"Espiras: {g['N']} por bobina ({fw['n_cam']} camada(s) × {fw['n_ax']}) – sentido IGUAL nas 3 bobinas. "
                               f"Fio ≈ {fab['comp_folha']:.0f} m/bobina (todos os paralelos, {fab['massa_folha']:.1f} kg).", fontsize=5.6)
    else:
        F.texto(212, yt - 4.5, f"Folha {d['cond_dados']['nome']}: {g['tf']:.1f} × {g['hf']:.0f} mm, bordas sem rebarba e arredondadas;"
                               f" margem de aramida {12:.0f} mm além da borda.", fontsize=5.6)
        F.texto(212, yt - 8.5, f"Espiras: {g['N']} por bobina – sentido de bobinagem IGUAL nas 3 bobinas (horário visto de cima). "
                               f"Comprimento de folha ≈ {fab['comp_folha']:.1f} m/bobina ({fab['massa_folha']:.1f} kg).", fontsize=5.6)
    F.texto(212, yt - 12.5, f"Espira média (MLT) ≈ {fab['MLT']:.0f} mm.  Espessura radial calculada {fab['build_real']:.1f} mm.  "
                            + ("PTC (item 21) sobre a camada externa, no meio da altura, sob o enfaixamento." if (fw and fw["n_cam"] == 1)
                             else "PTC (item 21) entre as 2 últimas camadas, no meio da altura."), fontsize=5.6)
    # Detalhe terminal
    F.texto(212, 150, (("DETALHE D – SAÍDA DOS FIOS E TERMINAL (sem escala)" if fw["np"] > 1 else "DETALHE D – SAÍDA DA BARRA E TERMINAL (sem escala)") if fw else "DETALHE D – SAÍDA DA FOLHA E TERMINAL (sem escala)"),
            fontsize=7.4, weight="bold")
    ax = F.ax
    ax.add_patch(Rectangle((215, 102), 3, 38, fc=C["bob"], ec="k", lw=0.4))
    ax.add_patch(Rectangle((218, 114), 38, 7, fc="#c8c8c8" if d["cond"] == "AL" else C["cu"], ec="k", lw=0.4))
    ax.add_patch(Rectangle((256, 111), 34, 13, fc=C["cu"], ec="k", lw=0.4))
    for xx in (264, 282):
        ax.add_patch(Circle((xx, 117.5), 3.2, fc="white", ec="k", lw=0.4))
    ax.annotate("", (264, 128), (282, 128), arrowprops=dict(arrowstyle="<|-|>", lw=0.35, color=C["cota"], mutation_scale=4.5))
    ax.text(273, 129, "44,5", fontsize=5.6, ha="center", color=C["cota"])
    ax.text(256, 106.5, "furos Ø13 (NEMA 2 furos) – terminal horizontal p/ frente", fontsize=5.6)
    import textwrap as _tw
    for _k, _l in enumerate(_tw.wrap(texto_padrao(g, d)["saida"] + ".", 120)[:3]):
        ax.text(215, 97.5 - 3.5 * _k, _l, fontsize=5.0)
    ax.text(215, 143, (("fios em paralelo unidos" if fw["np"] > 1 else "barra única da bobina") if fw else "folha (largura total)"), fontsize=5.6)
    ax.text(219, 123, (("barra da bobina (Al) – solda TIG" if d["cond"] == "AL" else "barra da bobina brasada") if fw else
                       ("barra Al 40×6 soldada TIG em toda a largura" if d["cond"] == "AL" else "barra Cu 40×6 brasada em toda a largura")),
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
    est = g["est"]
    ex0, ex1, ey0, ey1, ez0, ez1 = est["env"]
    caixa(0, -b / 2, 0, W, b, a, C["ferro"])
    caixa(0, -b / 2, H - a, W, b, a, C["ferro"])
    for i in range(3):
        caixa(i * g["pitch"], -b / 2, a, a, b, hw, C["ferro_esc"])
    for i, xc in enumerate(g["xc"]):
        prisma_arred(xc, 0, g["Dc"], g["Ec"], g["rc"], g["yc0"], g["yc0"] + g["hc"], "#d9c48f")
    for nome, mat, (x0, x1, y0, y1, z0, z1) in est["caixas"]:
        caixa(x0, y0, z0, x1 - x0, y1 - y0, z1 - z0, COR_EST.get(mat, "#ccc"))
    for nome, mat, (xc_, yc_, z0, z1), r, _ in est["cilindros"]:
        caixa(xc_ - r * 0.8, yc_ - r * 0.8, z0, 1.6 * r, 1.6 * r, z1 - z0, COR_EST.get(mat, "#ccc"))
    pc = Poly3DCollection(TODAS_F, facecolors=TODAS_C, edgecolors=TODAS_C, linewidths=0.4)   # sem costuras visíveis
    pc.set_sort_zpos(None)
    ax.set_autoscale_on(False)
    ax.add_collection3d(pc, autolim=False)
    ax.set_box_aspect((ex1 - ex0, ey1 - ey0 + 40, ez1 - ez0))
    ax.set_xlim(ex0, ex1)
    ax.set_ylim(ey0 - 20, ey1 + 20)
    ax.set_zlim(ez0, ez1)
    ax.view_init(20, -58)
    ax.axis("off")
    F.texto(275, 262, "VISTA ISOMÉTRICA 3D (sombreada)", fontsize=8, weight="bold")
    m = d["massa_kg"]
    r = d["requisitos"]
    resumo = [
        ("L por fase", f"{r['L']*1e6:.0f} µH ±{_tol(d)} %"), ("Corrente nominal" if not r.get("aplicacao") else "Corrente térmica", f"{r['In']:.0f} A (pico {r['Ipk']:.0f} A)"),
        ("Isat / sobrecarga", f"≥ {r['Isat']:.0f} A (L ≥ 90 %) / {r['Iovl']:.0f} A (L ≥ 70 %)"),
        ("Chaveamento", f"{r['fs']/1e3:.0f} kHz (tensão PWM, barramento ≈ {r['Vdc']:.0f} V)") if not r.get("aplicacao") else
        ("Aplicação", f"{r['aplicacao']} – I1 {r['I1']:.0f} A + harmônicas"),
        ("Isolação", f"Sistema classe {r['classe']} – elevação média ≤ {d['termico']['meta_elev_K']:.0f} K"),
        ("Perdas (calc.)", f"{d['perdas']['total']:.0f} W"), ("Elevação (calc.)", f"{d['termico']['elev_bobina_K']:.0f} K"),
        ("Massa (calc.)", f"{m['total']:.0f} kg (núcleo {m['nucleo']:.0f} / condutor {m['condutor']:.0f})"),
        ("Dimensões", f"{g['Lb']:.0f} × {g['Bb']:.0f} × {g['Ht']:.0f} mm (C × P × A, com saídas)"),
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
             "3) Calços colados + VPI: evitam ruído/vibração " + ("(harmônicas 100–1000 Hz)" if _banco(d) else "a 4–8 kHz") + ".   4) Separação ≥ 10 mm e escoamento ≥ 16 mm entre partes vivas e massa "
             "(IEC 60664-1, cat. III, PD3, 1000 V).   5) Protótipo obrigatório com ensaio de aquecimento " + ("na corrente térmica." if _banco(d) else "em inversor."))
    import textwrap
    for k, l in enumerate(textwrap.wrap(notas, 190)):
        F.texto(25, y - 3 - 4 * k, l, fontsize=5.6)


VPI_PASSOS = [
    "Pré-secagem da parte ativa (bobinas montadas no núcleo) em estufa a 130–150 °C até massa constante (≥ 4 h).",
    "Resfriar a 60–70 °C, levar ao autoclave e fazer vácuo ≤ 1 mbar (100 Pa) por ≥ 1 h, até estabilizar.",
    "Admitir a resina classe H (poliéster-imida ou silicone, índice térmico ≥ 180 °C, IEC 60464-3) sob vácuo, cobrindo a peça.",
    "Pressurizar com ar seco ou N₂ a 4–6 bar por ≥ 2 h: a resina penetra entre fios, camadas, calços e lâminas.",
    "Escorrer 30 min e curar em estufa conforme a ficha da resina (típico 150–160 °C por 8–12 h).",
    "2ª impregnação por imersão + cura: superfície vitrificada (pó, umidade, ruído/vibração).",
    "Controle: isolamento ≥ 100 MΩ após a cura, sem bolhas/regiões secas, lote da resina registrado.",
]


def folha_realista(F, d, png_dir=None):
    """Folha 6 – vista realista (render 3D com materiais) + detalhe da bobina em corte + sistema de isolação + VPI (v1.11.4)."""
    import tempfile
    import matplotlib.image as mpimg
    from . import ind_render as R
    tmp = png_dir or tempfile.mkdtemp()
    f1, f2 = os.path.join(tmp, "Indutor_render_geral.png"), os.path.join(tmp, "Indutor_render_corte.png")
    W1, H1, W2, H2 = 1800, 1300, 1400, 1200
    px1 = R.render(d, f1, W1, H1, "geral")
    px2 = R.render(d, f2, W2, H2, "corte")
    ax = F.ax
    # vista geral
    x0, x1 = 22, 230
    hgt = (x1 - x0) * H1 / W1
    y1 = 284
    y0 = y1 - hgt
    ax.imshow(mpimg.imread(f1), extent=(x0, x1, y0, y1), zorder=1)
    F.texto(x0 + 2, y1 - 4, "VISTA REALISTA – reator trifásico a seco, bobina U em corte (sem escala)", fontsize=7.4, weight="bold")
    itens = {n: (t, e) for n, t, e in R.ITENS_VISTA}

    usados = {}

    def chamar(px, Wp, Hp, xa, xb, ya, yb, n, lado):
        X = xa + px[0] / Wp * (xb - xa)
        Y = yb - px[1] / Hp * (yb - ya)
        if not (xa + 1 < X < xb - 1 and ya + 1 < Y < yb - 1):
            return
        Xb = xa + 6 if lado < 0 else xb - 6
        Yb = Y
        lst = usados.setdefault((xa, lado), [])
        while any(abs(Yb - u) < 7.0 for u in lst):      # não sobrepor balões do mesmo lado
            Yb -= 7.0
        lst.append(Yb)
        Xm = Xb + (8 if lado < 0 else -8)
        ax.plot([X, Xm, Xb], [Y, Yb, Yb], lw=0.35, color="k", zorder=6)
        ax.add_patch(Circle((X, Y), 0.7, color="k", zorder=7))
        ax.add_patch(Circle((Xb, Yb), 3.0, fc="white", ec="k", lw=0.6, zorder=8))
        ax.text(Xb, Yb, str(n), fontsize=6.5, ha="center", va="center", zorder=9, weight="bold")
    xm = (x0 + x1) / 2
    for n, pp in px1.items():
        X = x0 + pp[0] / W1 * (x1 - x0)
        chamar(pp, W1, H1, x0, x1, y0, y1, n, -1 if X < xm else 1)
    # detalhe aproximado
    u0, u1 = 236, 408
    h2 = (u1 - u0) * H2 / W2
    v1 = 284
    v0 = v1 - h2
    ax.imshow(mpimg.imread(f2), extent=(u0, u1, v0, v1), zorder=1)
    ax.add_patch(Rectangle((u0, v0), u1 - u0, h2, fill=False, lw=0.6, zorder=2))
    F.texto(u0 + 2, v1 - 4, "DETALHE – bobina em corte: coluna, calços do entreferro, tubo, fios isolados, resina", fontsize=6.6,
            weight="bold", zorder=10, bbox=dict(fc="white", ec="none", alpha=0.8, pad=0.6))
    um = (u0 + u1) / 2
    for n in (2, 3, 4, 6, 10):
        if n in px2:
            X = u0 + px2[n][0] / W2 * (u1 - u0)
            chamar(px2[n], W2, H2, u0, u1, v0, v1, n, -1 if X < um else 1)
    # legenda dos itens (materiais) – sistema de isolação classe H
    F.texto(22, y0 - 6, f"CONSTRUÇÃO E SISTEMA DE ISOLAÇÃO CLASSE {d['requisitos'].get('classe', 'H')} (a classe é do SISTEMA – IEC 60085 / IEC 61857)",
            fontsize=7.2, weight="bold")
    from .ind_projeto import descr_condutor
    esp = {1: (f"{d['chapa_dados']['nome']}, revestimento C-5; colunas inteiras com junta de TOPO nas culatras (onde ficam os calços)"
               if d.get("pos_gap") == "culatra" else f"{d['chapa_dados']['nome']}, revestimento C-5; empilhamento em pacotes; cantos a 45° step-lap 3 degraus"),
           2: ((lambda f: f"{descr_condutor(d, curto=True)} {('cobre' if d.get('cond') == 'CU' else 'alumínio')}, papel aramida "
                f"enrolado; {d['N']} espiras ({f['n_cam']} camada(s))" + ("; paralelos TRANSPOSTOS" if f["np"] > 1 else "; condutor único"))(d["fio"]) if d.get("fio")
               else descr_condutor(d))[:150],
           3: (f"vidro-epóxi EP GC 203 retificado ±0,05 mm, colado com epóxi classe H – "
               + ("2 por coluna, nas juntas com as culatras" if d.get("pos_gap") == "culatra" else f"{d['ng']} por coluna, distribuídos"))}
    linhas = []
    for n, t, e in R.ITENS_VISTA:
        linhas.append((str(n), t, esp.get(n, e)))
    yt = F.tabela(22, y0 - 9, ["Nº", "Item", "Material / construção"], linhas, [8, 34, 166], fs=5.2, h=4.3)
    # VPI
    F.texto(236, v0 - 6, "IMPREGNAÇÃO VPI (vácuo e pressão) – CLASSE H", fontsize=7.2, weight="bold")
    import textwrap
    yy = v0 - 10.5
    for k, passo in enumerate(VPI_PASSOS, start=1):
        for j, lin in enumerate(textwrap.wrap(passo, 92)):
            F.texto(236 if j == 0 else 240, yy, (f"{k}. " if j == 0 else "") + lin, fontsize=5.4)
            yy -= 3.4
        yy -= 0.4
    F.texto(236, yy - 1, "Valores típicos – seguir a ficha técnica da resina escolhida (declarar fabricante, tipo e índice térmico).",
            fontsize=5.2, style="italic")
    F.info["escala_folha"] = "sem escala"


def folha_entreferro(F, d):
    """Folha 7 – DETALHE G: entreferro (desenho ampliado, material, cotas, fluxo espraiado) + memorial do cálculo (v1.11.4)."""
    from .ind_fem import MU0
    ax = F.ax
    g = geo_mm(d)
    fab = fabricacao(d)
    culatra = d.get("pos_gap") == "culatra"
    ng = g["ng"]
    gl, gc = fab["gl"], fab["gc"]
    dbc = (g["hw"] - g["hc"]) / 2
    import numpy as _np
    k = 2.6                                               # ampliação do esquema
    xa, yb = 30, 100
    F.texto(25, 280, ("DETALHE G – ENTREFERRO NA JUNTA COLUNA–CULATRA (esquema ampliado, sem escala)" if culatra else
                      "DETALHE G – ENTREFERRO ENTRE PACOTES DA COLUNA (esquema ampliado, sem escala)"), fontsize=8.2, weight="bold")

    def R_(x, y, w, h, **kw):
        ax.add_patch(Rectangle((xa + x * k, yb + y * k), w * k, h * k, **kw))
    # culatra
    R_(0, 0, 66, 14, fc="#9aa0a8", ec="k", lw=0.7, hatch="----")
    ax.text(xa + 2 * k, yb + 7 * k, "CULATRA – lâminas de aço-silício GO empilhadas (corte transversal)", fontsize=6.2, va="center",
            bbox=dict(fc="white", ec="none", alpha=0.85, pad=0.8))
    yg = 14
    tg = 5.0
    R_(15, yg, 22, 0.6, fc="#e0c060", ec="none")
    R_(15, yg + 0.6, 22, tg - 1.2, fc="#b23a2a", ec="k", lw=0.7)
    R_(15, yg + tg - 0.6, 22, 0.6, fc="#e0c060", ec="none")
    R_(15, yg + tg, 22, 36, fc="#9aa0a8", ec="k", lw=0.7, hatch="||||")
    ax.text(xa + 26 * k, yb + (yg + tg + 22) * k, "COLUNA\n(lâminas GO)", fontsize=6.4, ha="center", va="center",
            bbox=dict(fc="white", ec="none", alpha=0.85, pad=0.8))
    # bobinas dos dois lados
    for sx in (-1, 1):
        xb_ = 26 + sx * 18.5
        R_(xb_ - 3.5, yg + tg + 2 + dbc / 25 * 2, 7, 30, fc="#c56a2f", ec="k", lw=0.5)
        for j in range(6):
            ax.plot([xa + (xb_ - 3.5) * k, xa + (xb_ + 3.5) * k], [yb + (yg + tg + 6 + j * 4.6) * k] * 2, lw=0.4, color="#f0d9a0")
    ax.text(xa + 50 * k, yb + (yg + tg + 24) * k, "BOBINA\nfio retangular + papel aramida\n+ resina VPI" if d.get("fio") else
            "BOBINA\nfolha + aramida + resina VPI", fontsize=6.0, va="center")
    # fluxo espraiado
    t = _np.linspace(0, _np.pi, 40)
    for r_ in (2.5, 4.5, 6.5, 8.5):
        for sx in (-1, 1):
            cx = 15 if sx < 0 else 37
            ax.plot(xa + (cx + sx * r_ * _np.sin(t) * 0.8) * k, yb + (yg + tg / 2 + r_ * _np.cos(t)) * k, lw=0.5, color="#2c7fb8", ls="--")
    ax.text(xa - 4, yb + (yg + tg + 3) * k, "fluxo espraiado\n(fringing)", fontsize=5.8, color="#2c7fb8", ha="right")
    # cotas
    ax.annotate("", (xa + 40 * k, yb + (yg + 0.6) * k), (xa + 40 * k, yb + (yg + tg - 0.6) * k),
                arrowprops=dict(arrowstyle="<|-|>", lw=0.6, mutation_scale=6))
    ax.text(xa + 41 * k, yb + (yg + tg / 2) * k, f"g por peça = {gl:.2f} mm (colunas U, W)\n                 {gc:.2f} mm (coluna V)",
            fontsize=6.4, va="center", weight="bold")
    ax.annotate("", (xa + 9 * k, yb + yg * k), (xa + 9 * k, yb + (yg + tg + 2 + dbc / 25 * 2) * k),
                arrowprops=dict(arrowstyle="<|-|>", lw=0.5, mutation_scale=5))
    ax.text(xa + 4 * k, yb + (yg + 3.5) * k, f"{dbc:.0f} mm", fontsize=6.0, va="center", rotation=90)
    # chamadas de material
    ax.annotate("calço: laminado vidro-epóxi EP GC 203 (IEC 60893-3-2,\nclasse 180 °C), retificado ±0,05 mm, peça inteira na seção\n"
                f"{g['a']:.0f} × {g['b']:.0f} mm", (xa + 30 * k, yb + (yg + tg / 2) * k), (xa + 46 * k, yb - 12),
                fontsize=6.0, arrowprops=dict(arrowstyle="-", lw=0.4))
    ax.annotate("cola epóxi classe H (camada fina dos dois lados)", (xa + 20 * k, yb + (yg + 0.3) * k), (xa, yb - 12),
                fontsize=6.0, arrowprops=dict(arrowstyle="-", lw=0.4))
    F.texto(25, 44, f"Construção: {'2 entreferros por coluna – um em cada junta coluna–culatra (em cima e embaixo); coluna inteira com faces de topo retificadas' if culatra else f'{ng} entreferros distribuídos por coluna (coluna em {ng + 1} pacotes)'}.",
            fontsize=6.2)
    F.texto(25, 39, "Montagem: medir a espessura de cada calço (micrômetro), colar, fechar a culatra e apertar os tirantes no torque indicado;"
                    " medir L e corrigir o calço se preciso.", fontsize=6.2)
    F.texto(25, 34, "Força magnética no entreferro (pico) " + f"≈ {d.get('forca_gap_N', 0):.0f} N por junta – aperto mínimo "
                    f"{max(2.5 * d.get('forca_gap_N', 0), 2000):.0f} N por coluna; calço colado + VPI evitam vibração/ruído.", fontsize=6.2)
    # memorial
    r = d["requisitos"]
    L = r["L"]
    N = d["N"]
    Ag = d["a"] * d["b"]
    g_id = MU0 * N * N * Ag / L * 1e3
    gcol = [x * 1e3 for x in d["gaps"]]
    L3 = [x * 1e6 for x in d.get("L3d", [L] * 3)]
    k_esp = gcol[1] / g_id if g_id else 0
    xm = 238
    linhas = [
        ("COMO A DISTÂNCIA DO ENTREFERRO É CALCULADA", True),
        ("1) Entreferro IDEAL (sem espraiamento, ferro ideal):", True),
        (f"    g = μ0 · N² · A / L = 4π·10⁻⁷ × {N}² × ({d['a']*1e3:.0f} × {d['b']*1e3:.0f} mm²) / {L*1e6:.0f} µH = {g_id:.1f} mm por coluna", False),
        ("2) Entreferro REAL – espraiamento:", True),
        ("    Em volta do entreferro o fluxo 'abre' (linhas azuis); a área efetiva fica maior e a indutância sobe.", False),
        ("    Para manter L, o entreferro precisa ser MAIOR que o ideal. Isso é calculado por elementos finitos:", False),
        ("    • modelo 2D do núcleo com ferro não linear (curva B-H do aço GO) + correção 3D das faces da frente/trás;", False),
        ("    • a plataforma ajusta o entreferro de cada coluna até L = valor exigido (laterais e central têm", False),
        ("      acoplamentos magnéticos diferentes, por isso a central leva calço um pouco maior).", False),
        ("3) Resultado deste projeto:", True),
        (f"    g total por coluna = {gcol[0]:.1f} mm (U, W)  /  {gcol[1]:.1f} mm (V)   → fator de espraiamento ≈ {k_esp:.2f}", False),
        (f"    {'2 calços' if culatra else f'{ng} calços'} por coluna → {gl:.2f} mm (U, W)  /  {gc:.2f} mm (V) cada", False),
        (f"    L calculada: U {L3[0]:.1f} µH  ·  V {L3[1]:.1f} µH  ·  W {L3[2]:.1f} µH   (exigido {L*1e6:.0f} µH ± 5 %)", False),
        ("4) Limites de projeto (verificados):", True),
        (f"    peça ≤ {10 if culatra else 3} mm; total ≤ 20 % da largura da coluna ({0.2 * d['a'] * 1e3:.0f} mm); bobina a {dbc:.0f} mm da junta.", False),
        ("    Acima disso o espraiamento atinge as espiras (perdas) e aumentam força e ruído.", False),
        ("    Linearidade (FEM): L ≥ 90 % na corrente de saturação e ≥ 70 % na sobrecarga do inversor.", False),
        ("5) Ajuste na fábrica:", True),
        (f"    Sensibilidade ≈ {100 / max(gcol[1], 1e-6):.0f} % de L por mm de entreferro total (L ∝ 1/g): calço mais grosso → L menor.", False),
        (f"    Medir L por fase (ponte LCR 60 Hz ou corrente nominal) e corrigir o calço até L ±{_tol(d)} % e desequilíbrio ≤ 3 %.", False),
        ("    Registrar a espessura final de cada calço no relatório do protótipo.", False),
    ]
    yy = 280
    for t, neg in linhas:
        F.texto(xm, yy, t, fontsize=7.6 if t.startswith("COMO") else 6.2, weight="bold" if neg else "normal")
        yy -= 6.2 if t.startswith("COMO") else (5.0 if neg else 4.4)
    F.info["escala_folha"] = "sem escala"


def lista_materiais(d):
    g = geo_mm(d)
    ch, cond = d["chapa_dados"], d["cond_dados"]
    m = d["massa_kg"]
    ng = g["ng"]
    linhas = [
        ("1", "Núcleo – chapas", f"{ch['nome']}; " + ("colunas inteiras em junta de TOPO com as culatras, calços nas juntas" if d.get("pos_gap") == "culatra" else f"culatras a 45° step-lap 3 degraus; colunas em {ng + 1} pacotes"), f"{m['nucleo']:.0f} kg", ch["norma"]),
        ("2", "Enrolamento", (descr_condutor(d) + ", 3 bobinas") if d.get("fio") else f"{cond['nome']} {g['tf']:.1f} × {g['hf']:.0f} mm, {g['N']} espiras/bobina, 3 bobinas",
         f"{m['condutor']:.0f} kg", ("IEC 60317-0-2 / ABNT NBR (fio retangular); " + cond["norma"].split("/")[0]) if d.get("fio") else cond["norma"]),
        ("3", "Calços do entreferro", f"EP GC 203 retificado: laterais {g['gaps'][0]/ng:.2f} mm, central {g['gaps'][1]/ng:.2f} mm, {ng} por coluna",
         f"{3 * ng} pç", "IEC 60893-3-2"),
    ]
    for k, it in enumerate(d["isolacao"], start=4):
        linhas.append((str(k), it["item"], it["mat"], "cj.", it["norma"]))
    k = len(linhas) + 1
    from .ind_estrutura import texto_padrao
    _tp = texto_padrao(g, d)
    linhas += [
        (str(k), "Quadros de aperto em U", _tp["quadro"], "4 pç", "ABNT NBR 7008 (zincado)"),
        (str(k + 1), "Tirantes", _tp["tirante"], "4 pç", "ISO 898-1"),
        (str(k + 2), "Pés de fixação", "Aba inferior dos quadros de baixo com 4 furos oblongos 14 × 25 (parafuso M12 no trilho/base do painel)", "4 furos", "–"),
        (str(k + 3), "Saídas / terminais", _tp["saida"] + " (Al: placa bimetálica Cu-Al)", "6 pç", "NEMA CC1 / IEC 60445"),
        (str(k + 4), "Aterramento", "Cordoalha Cu 25 mm² núcleo → quadro (1 ponto) + terminal PE M8 no quadro inferior", "1 cj.", "IEC 60364-5-54"),
        (str(k + 5), "Içamento", "Furo Ø22 nas pontas dos quadros superiores (içar pelos 4 furos, cabo a ≤ 30° da vertical)", "4 furos", "–"),
        (str(k + 6), "Caixa de bornes do sensor", "Caixa com bornes 2,5 mm², cabo silicone 180 °C até o PTC", "1 cj.", "IEC 60947-7-1"),
        (str(k + 7), "Placa de identificação", "Colada na face de cima da culatra superior (como nos reatores nacionais) – inox/alumínio gravado: L, In, fs, classe, elevação, perdas, massa, nº de série, data", "1 pç", "IEC 60076-6"),
    ]
    return linhas


def gerar_pdf(d, pdf_path, info, png_dir=None):
    g = geo_mm(d)
    fab = fabricacao(d)
    folhas = [("Conjunto – vistas", lambda F: folha_conjunto(F, g, d)),
              ("Núcleo – chapas, step-lap, pacotes e calços", lambda F: folha_nucleo(F, g, d, fab)),
              ("Bobina – cortes, bobinagem e terminal", lambda F: folha_bobina(F, g, d, fab)),
              ("Vista 3D e características", lambda F: folha_3d(F, g, d)),
              ("Lista de materiais, ficha de fabricação e notas", lambda F: folha_bom(F, d, fab))]
    try:
        from . import ind_render as _R
        if _R.disponivel():
            folhas.append(("Vista realista em corte, isolação e impregnação VPI", lambda F: folha_realista(F, d, png_dir)))
    except Exception:
        pass
    folhas.append(("Entreferro – detalhe, material e cálculo", lambda F: folha_entreferro(F, d)))
    total = len(folhas)
    with PdfPages(pdf_path) as pdf:
        for n, (nome, fun) in enumerate(folhas, start=1):
            inf = dict(info)
            for tent in range(2):                      # 1 nova tentativa se a folha falhar (ex.: limites 3D do matplotlib)
                F = Folha(inf, n, total, nome)
                try:
                    fun(F)
                    break
                except Exception as e:
                    plt.close(F.fig)
                    if tent == 1:
                        F = Folha(inf, n, total, nome)
                        F.texto(30, 200, f"(folha não gerada: {type(e).__name__}: {e})", fontsize=8)
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
