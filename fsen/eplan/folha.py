"""Folha de esquema elétrico no estilo EPLAN (v1.15.0).

Cada folha é A3 paisagem (420 × 297 mm) com moldura, grade de colunas 1–10 (para referências cruzadas "página.coluna"),
linhas A–F, carimbo com cliente/projeto/função/local/página. As primitivas são guardadas em mm e renderizadas em
PDF (matplotlib, vetorial) e em DXF (ezdxf, camadas por tipo) – o mesmo desenho nos dois formatos.
Textos podem ser funções (avaliadas na renderização) – é assim que as referências cruzadas são resolvidas depois que
todas as folhas foram montadas.
"""
import math

X0, Y0, X1, Y1 = 15.0, 10.0, 410.0, 287.0       # área útil (moldura interna)
NCOL = 10
CAR_H = 22.0                                     # altura do carimbo (faixa inferior)
LIN = "ABCDEF"


def col_x(c):
    """Centro da coluna c (1..10)."""
    w = (X1 - X0) / NCOL
    return X0 + (c - 0.5) * w


def col_de_x(x):
    w = (X1 - X0) / NCOL
    return max(1, min(NCOL, int((x - X0) // w) + 1))


class Folha:
    def __init__(self, proj, titulo, funcao="", local="", tipo="esquema"):
        self.proj = proj
        self.titulo = titulo
        self.funcao = funcao                        # =ESTAGIOS, =COMANDO …
        self.local = local                          # +PAINEL
        self.tipo = tipo
        self.prim = []                              # (tipo, dados, camada)
        self.n = None                               # número da folha (definido ao adicionar ao projeto)

    # ---------------------------------------------------------------- primitivas (mm)
    def lin(self, x0, y0, x1, y1, lw=0.35, cam="FIOS", tracejado=False, cor="k"):
        self.prim.append(("lin", (x0, y0, x1, y1, lw, tracejado, cor), cam))

    def pol(self, pts, lw=0.35, cam="SIMBOLOS", fechado=False, preenchido=False, cor="k"):
        self.prim.append(("pol", (list(pts), lw, fechado, preenchido, cor), cam))

    def ret(self, x, y, w, h, lw=0.35, cam="SIMBOLOS", tracejado=False, preench=None):
        self.prim.append(("ret", (x, y, w, h, lw, tracejado, preench), cam))

    def circ(self, x, y, r, lw=0.35, cam="SIMBOLOS", preenchido=False):
        self.prim.append(("circ", (x, y, r, lw, preenchido), cam))

    def arco(self, x, y, r, a0, a1, lw=0.35, cam="SIMBOLOS"):
        self.prim.append(("arco", (x, y, r, a0, a1, lw), cam))

    def txt(self, x, y, t, fs=2.2, ha="left", va="bottom", rot=0, negrito=False, cam="TEXTOS", cor="k"):
        """fs em mm (altura da letra)."""
        self.prim.append(("txt", (x, y, t, fs, ha, va, rot, negrito, cor), cam))

    def ponto(self, x, y):
        self.circ(x, y, 0.55, lw=0.2, cam="FIOS", preenchido=True)

    # ---------------------------------------------------------------- moldura e carimbo
    def _moldura(self, total):
        p = self.proj
        out = []
        L = out.append
        L(("ret", (X0, Y0, X1 - X0, Y1 - Y0, 0.6, False, None), "MOLDURA"))
        L(("ret", (5, 5, 410, 287, 0.25, False, None), "MOLDURA"))
        w = (X1 - X0) / NCOL
        for c in range(NCOL):
            x = X0 + c * w
            L(("lin", (x, Y1, x, Y1 + 5, 0.25, False, "k"), "MOLDURA"))
            L(("txt", (x + w / 2, Y1 + 1.2, str(c + 1), 2.2, "center", "bottom", 0, False, "k"), "MOLDURA"))
        hy = (Y1 - Y0 - CAR_H) / len(LIN)
        for i, l in enumerate(LIN):
            y = Y1 - (i + 0.5) * hy
            L(("txt", (X0 - 5, y, l, 2.2, "center", "center", 0, False, "k"), "MOLDURA"))
        # carimbo
        yc = Y0
        L(("lin", (X0, yc + CAR_H, X1, yc + CAR_H, 0.5, False, "k"), "MOLDURA"))
        campos = [(X0, 70, "ELECTRIC SERVICE", "Engenharia – Porto Alegre/RS"),
                  (X0 + 70, 95, "Cliente", p.cliente or "–"),
                  (X0 + 165, 105, "Projeto", p.projeto),
                  (X0 + 270, 55, "Função / Local", f"{self.funcao} {self.local}".strip() or "–"),
                  (X0 + 325, 70, "Título da folha", self.titulo)]
        for x, wd, rot, val in campos:
            L(("lin", (x, yc, x, yc + CAR_H, 0.35, False, "k"), "MOLDURA"))
            L(("txt", (x + 1.5, yc + CAR_H - 3.4, rot, 1.8, "left", "bottom", 0, False, "0.35"), "MOLDURA"))
            fsv = 2.6 if x > X0 else 2.3
            fsv = min(fsv, (wd - 3) / max(len(str(val)), 1) * 1.65)
            L(("txt", (x + 1.5, yc + CAR_H - 8.5, val, fsv, "left", "bottom", 0, True, "k"), "MOLDURA"))
        L(("txt", (X0 + 1.5, yc + 7.5, f"Desenho {p.codigo}", 2.0, "left", "bottom", 0, False, "k"), "MOLDURA"))
        L(("txt", (X0 + 1.5, yc + 3.0, f"{p.data} | {p.versao}", 1.8, "left", "bottom", 0, False, "k"), "MOLDURA"))
        L(("txt", (X0 + 71.5, yc + 7.5, f"Rev. {p.rev} – {p.descr_rev}", 1.8, "left", "bottom", 0, False, "k"), "MOLDURA"))
        L(("txt", (X0 + 71.5, yc + 3.0, "Projetado: plataforma FSEN   Verificado: ______   Aprovado: ______", 1.8, "left",
                   "bottom", 0, False, "k"), "MOLDURA"))
        L(("txt", (X0 + 166.5, yc + 3.0, f"{p.norma}", 1.8, "left", "bottom", 0, False, "k"), "MOLDURA"))
        L(("txt", (X1 - 2, yc + 3.0, f"Folha {self.n} / {total}", 3.0, "right", "bottom", 0, True, "k"), "MOLDURA"))
        return out


class ProjetoEletrico:
    """Conjunto de folhas + dispositivos (para referências cruzadas, bornes, cabos e lista de material)."""

    def __init__(self, cliente, projeto, codigo, data, versao, rev="00", descr_rev="Emissão inicial",
                 norma="IEC 60617 / IEC 81346 / NBR IEC 61439"):
        self.cliente, self.projeto, self.codigo, self.data, self.versao = cliente, projeto, codigo, data, versao
        self.rev, self.descr_rev, self.norma = rev, descr_rev, norma
        self.folhas = []
        self.pos = {}           # (tag, papel) -> (folha, coluna)   papel: "bobina", "c13-14", "polo", ...
        self.disp = {}          # tag -> dict(descr, fab, cod, qtd, unid, grupo)
        self.bornes = []        # dict(regua, n, fio, de, para, funcao, folha)
        self.cabos = []         # dict(id, de, para, tipo, secao, n_cond, comp_m, funcao)
        self.fios = 0

    def nova(self, titulo, funcao="", local="+PAINEL", tipo="esquema"):
        f = Folha(self, titulo, funcao, local, tipo)
        self.folhas.append(f)
        f.n = len(self.folhas)
        return f

    def registra(self, tag, papel, folha, x):
        self.pos[(tag, papel)] = (folha.n, col_de_x(x))

    def ref(self, tag, papel):
        """Texto de referência cruzada '/folha.coluna' (resolvido na renderização)."""
        def _r():
            p = self.pos.get((tag, papel))
            return f"/{p[0]}.{p[1]}" if p else ""
        return _r

    def dispositivo(self, tag, descr, fab="", cod="", qtd=1, unid="pç", grupo="", dados=""):
        if tag in self.disp:
            self.disp[tag]["qtd"] += 0
            return tag
        self.disp[tag] = dict(tag=tag, descr=descr, fab=fab, cod=cod, qtd=qtd, unid=unid, grupo=grupo, dados=dados)
        return tag

    def fio(self):
        self.fios += 1
        return self.fios

    # ---------------------------------------------------------------- renderização
    def _prims(self, f):
        return f._moldura(len(self.folhas)) + f.prim

    def pdf(self, arq, png_dir=None):
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.backends.backend_pdf import PdfPages
        from matplotlib.patches import Rectangle, Circle, Arc, Polygon
        pt = 72 / 25.4
        with PdfPages(arq) as pdf:
            for f in self.folhas:
                fig = plt.figure(figsize=(420 / 25.4, 297 / 25.4))
                ax = fig.add_axes([0, 0, 1, 1])
                ax.set_xlim(0, 420)
                ax.set_ylim(0, 297)
                ax.set_aspect("equal")
                ax.axis("off")
                for tp, d, cam in self._prims(f):
                    if tp == "lin":
                        x0, y0, x1, y1, lw, tr, cor = d
                        ax.plot([x0, x1], [y0, y1], lw=lw * pt, color=cor, ls="--" if tr else "-", solid_capstyle="butt")
                    elif tp == "pol":
                        pts, lw, fech, pre, cor = d
                        ax.add_patch(Polygon(pts, closed=fech, fill=pre, fc=cor if pre else "none", ec=cor, lw=lw * pt))
                    elif tp == "ret":
                        x, y, w, h, lw, tr, pre = d
                        ax.add_patch(Rectangle((x, y), w, h, fill=pre is not None, fc=pre or "none", ec="k", lw=lw * pt,
                                               ls="--" if tr else "-"))
                    elif tp == "circ":
                        x, y, r, lw, pre = d
                        ax.add_patch(Circle((x, y), r, fill=pre, fc="k" if pre else "none", ec="k", lw=lw * pt))
                    elif tp == "arco":
                        x, y, r, a0, a1, lw = d
                        ax.add_patch(Arc((x, y), 2 * r, 2 * r, theta1=a0, theta2=a1, lw=lw * pt, color="k"))
                    elif tp == "txt":
                        x, y, t, fs, ha, va, rot, neg, cor = d
                        t = t() if callable(t) else t
                        if t:
                            ax.text(x, y, t, fontsize=fs * pt / 0.72, ha=ha, va=va, rotation=rot, color=cor,
                                    weight="bold" if neg else "normal", family="DejaVu Sans")
                if png_dir and f.n <= 3:
                    import os
                    fig.savefig(os.path.join(png_dir, f"esquema_folha_{f.n:02d}.png"), dpi=110)
                pdf.savefig(fig)
                plt.close(fig)
        return arq

    def dxf(self, arq):
        """Mesmas folhas em DXF (uma ao lado da outra, 450 mm de passo), camadas MOLDURA/FIOS/SIMBOLOS/TEXTOS."""
        import ezdxf
        doc = ezdxf.new("R2010", setup=True)
        msp = doc.modelspace()
        for nome, cor in (("MOLDURA", 8), ("FIOS", 7), ("SIMBOLOS", 5), ("TEXTOS", 3), ("POTENCIA", 1)):
            if nome not in doc.layers:
                doc.layers.add(nome, color=cor)
        for k, f in enumerate(self.folhas):
            ox = k * 450.0
            for tp, d, cam in self._prims(f):
                at = {"layer": cam if cam in doc.layers else "SIMBOLOS"}
                if tp == "lin":
                    x0, y0, x1, y1 = d[:4]
                    msp.add_line((ox + x0, y0), (ox + x1, y1), dxfattribs=at)
                elif tp == "pol":
                    pts = [(ox + x, y) for x, y in d[0]]
                    msp.add_lwpolyline(pts, close=d[2], dxfattribs=at)
                elif tp == "ret":
                    x, y, w, h = d[:4]
                    msp.add_lwpolyline([(ox + x, y), (ox + x + w, y), (ox + x + w, y + h), (ox + x, y + h)], close=True, dxfattribs=at)
                elif tp == "circ":
                    msp.add_circle((ox + d[0], d[1]), d[2], dxfattribs=at)
                elif tp == "arco":
                    msp.add_arc((ox + d[0], d[1]), d[2], d[3], d[4], dxfattribs=at)
                elif tp == "txt":
                    x, y, t, fs, ha, va, rot = d[:7]
                    t = t() if callable(t) else t
                    if t:
                        al = {("left", "bottom"): "BOTTOM_LEFT", ("center", "bottom"): "BOTTOM_CENTER", ("right", "bottom"): "BOTTOM_RIGHT",
                              ("left", "center"): "MIDDLE_LEFT", ("center", "center"): "MIDDLE_CENTER", ("right", "center"): "MIDDLE_RIGHT",
                              ("left", "top"): "TOP_LEFT", ("center", "top"): "TOP_CENTER", ("right", "top"): "TOP_RIGHT"}.get((ha, va), "BOTTOM_LEFT")
                        e = msp.add_text(str(t), height=fs, rotation=rot, dxfattribs=at)
                        e.set_placement((ox + x, y), align=getattr(ezdxf.enums.TextEntityAlignment, al))
        doc.saveas(arq)
        return arq
