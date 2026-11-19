"""Desenhos de fabricação: vistas 2D cotadas, cortes, perspectiva 3D, vista externa e diagrama elétrico.
Gera folhas A3 com carimbo em PDF + PNG de cada folha."""
from __future__ import annotations
import os
import datetime as _dt
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle, FancyBboxPatch
from matplotlib.backends.backend_pdf import PdfPages
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

A3 = (16.54, 11.69)
TINTA = "#1a1a1a"
COTA = "#2a78d6"


def _carimbo(fig, titulo, folha, total, proj, cat, rev="00"):
    ax = fig.add_axes([0.0, 0.0, 1, 1], zorder=-1)
    ax.set_xlim(0, 420); ax.set_ylim(0, 297); ax.axis("off")
    ax.add_patch(Rectangle((10, 10), 400, 277, fill=False, lw=1.2, ec=TINTA))
    x0, y0, w, h = 250, 10, 160, 38
    ax.add_patch(Rectangle((x0, y0), w, h, fill=False, lw=1.0, ec=TINTA))
    for yy in (y0 + 10, y0 + 19, y0 + 28):
        ax.plot([x0, x0 + w], [yy, yy], color=TINTA, lw=0.6)
    ax.plot([x0 + 110, x0 + 110], [y0, y0 + 19], color=TINTA, lw=0.6)
    emp = cat["empresa"]
    ped = proj.pedido
    ax.text(x0 + 3, y0 + 31, emp["nome"].upper() + " – Engenharia", fontsize=10, weight="bold", va="bottom")
    ax.text(x0 + 3, y0 + 21, titulo, fontsize=9, va="bottom")
    ax.text(x0 + 3, y0 + 12, f"Filtro senoidal {proj.topologia} {ped['corrente_a']:g} A {ped['tensao_v']:g} V – {ped['cliente'][:40]}",
            fontsize=7, va="bottom")
    ax.text(x0 + 3, y0 + 3, f"Doc.: {proj_codigo(proj)}  |  Data: {_dt.date.today():%d/%m/%Y}  |  Resp.: {emp['responsavel']}",
            fontsize=6.5, va="bottom")
    ax.text(x0 + 113, y0 + 12, f"Folha {folha}/{total}", fontsize=8, va="bottom")
    ax.text(x0 + 113, y0 + 3, f"Rev. {rev}  Escala s/ esc.  mm", fontsize=7, va="bottom")
    from .versao import assinatura
    ax.text(14, 18, assinatura(), fontsize=6.5, color="#555")
    ax.text(14, 14, "Desenho gerado automaticamente pela plataforma FSEN – dimensões de componentes estimadas; "
            "confirmar com desenhos dos fornecedores antes da fabricação.", fontsize=6.5, color="#555")


def proj_codigo(proj):
    ped = proj.pedido
    return f"FSEN-{proj.topologia}-{int(ped['corrente_a'])}A-{int(ped['tensao_v'])}V"


def _cota_h(ax, x1, x2, y, txt, off=0):
    ax.annotate("", xy=(x1, y), xytext=(x2, y), arrowprops=dict(arrowstyle="<->", color=COTA, lw=0.8))
    ax.text((x1 + x2) / 2, y + 12 + off, txt, ha="center", va="bottom", fontsize=7, color=COTA)


def _cota_v(ax, x, y1, y2, txt):
    ax.annotate("", xy=(x, y1), xytext=(x, y2), arrowprops=dict(arrowstyle="<->", color=COTA, lw=0.8))
    ax.text(x - 12, (y1 + y2) / 2, txt, ha="right", va="center", fontsize=7, color=COTA, rotation=90)


def vista_frontal(ax, arr, proj):
    L, A = arr.caixa_l, arr.caixa_a
    ax.add_patch(Rectangle((0, 0), L, A, fill=False, lw=1.6, ec=TINTA))
    ax.add_patch(Rectangle((25, 25), L - 50, A - 50, fill=False, lw=0.6, ec="#888", ls="--"))
    if arr.soleira_mm:
        ax.add_patch(Rectangle((0, -arr.soleira_mm), L, arr.soleira_mm, fill=True, fc="#ddd", ec=TINTA, lw=0.8))
    for c in arr.componentes:
        ax.add_patch(Rectangle((c.x, c.z), c.w, c.h, fc=c.cor, ec=TINTA, lw=0.6, alpha=0.9))
        if c.tag.startswith("C") and "." in c.tag:
            ax.text(c.x + c.w / 2, c.z + c.h / 2, c.tag, ha="center", va="center", fontsize=4.5, rotation=90)
        else:
            ax.text(c.x + c.w / 2, c.z + c.h / 2, c.tag, ha="center", va="center", fontsize=7, weight="bold")
    ax.add_patch(Rectangle((0, 0), L, 200, fill=False, hatch="////", ec="#999", lw=0))
    ax.text(L / 2, 100, "chapa de passagem de cabos / prensa-cabos", ha="center", fontsize=6.5, color="#444")
    _cota_h(ax, 0, L, A + 40, f"{L}")
    _cota_v(ax, -50, 0, A, f"{A}")
    ind = next(c for c in arr.componentes if c.tag == "L1")
    _cota_h(ax, ind.x, ind.x + ind.w, ind.z + ind.h + 20, f"L1 ≈ {ind.w:.0f}")
    _cota_v(ax, ind.x - 25, ind.z, ind.z + ind.h, f"{ind.h:.0f}")
    ax.set_title("VISTA FRONTAL – PORTA REMOVIDA", fontsize=9, weight="bold")
    ax.set_xlim(-150, L + 80); ax.set_ylim(-arr.soleira_mm - 60, A + 120)
    ax.set_aspect("equal"); ax.axis("off")


def vista_lateral(ax, arr, proj):
    P, A = arr.caixa_p, arr.caixa_a
    ax.add_patch(Rectangle((0, 0), P, A, fill=False, lw=1.6, ec=TINTA))
    ax.add_patch(Rectangle((P - 25, 25), 4, A - 50, fc="#aaa", ec="none"))
    ax.text(P - 12, A / 2, "placa de montagem", rotation=90, fontsize=6, va="center", ha="center")
    for c in arr.componentes:
        ax.add_patch(Rectangle((P - 25 - c.y - c.d if c.tag.startswith("C") else c.y, c.z), c.d, c.h, fc=c.cor, ec=TINTA, lw=0.5, alpha=0.6))
    ind = next(c for c in arr.componentes if c.tag == "L1")
    ax.annotate("", xy=(ind.y, ind.z - 30), xytext=(ind.y + ind.d, ind.z - 30), arrowprops=dict(arrowstyle="<->", color=COTA, lw=0.8))
    ax.text(ind.y + ind.d / 2, ind.z - 60, f"{ind.d:.0f}", ha="center", fontsize=7, color=COTA)
    # fluxo de ar
    ax.annotate("", xy=(P / 2, A - 30), xytext=(P / 2, 120), arrowprops=dict(arrowstyle="->", color="#1baf7a", lw=1.5, ls="--"))
    ax.text(P / 2 + 10, A / 2, "fluxo de ar\n(entrada inferior\n→ exaustão superior)", fontsize=6.5, color="#1baf7a")
    _cota_h(ax, 0, P, A + 40, f"{P}")
    ax.set_title("CORTE A-A (LATERAL)", fontsize=9, weight="bold")
    ax.set_xlim(-60, P + 60); ax.set_ylim(-60, A + 120)
    ax.set_aspect("equal"); ax.axis("off")


def vista_superior(ax, arr, proj):
    L, P = arr.caixa_l, arr.caixa_p
    ax.add_patch(Rectangle((0, 0), L, P, fill=False, lw=1.6, ec=TINTA))
    ax.add_patch(Rectangle((25, P - 29), L - 50, 4, fc="#aaa", ec="none"))
    ind = [c for c in arr.componentes if c.tag in ("L1", "L2")]
    for c in ind:
        ax.add_patch(Rectangle((c.x, c.y), c.w, c.d, fc=c.cor, ec=TINTA, lw=0.6, alpha=0.8))
        ax.text(c.x + c.w / 2, c.y + c.d / 2, c.tag, ha="center", va="center", fontsize=8, weight="bold")
        # furação de fixação (4 furos estimados)
        for fx in (c.x + 30, c.x + c.w - 30):
            for fy in (c.y + 20, c.y + c.d - 20):
                ax.add_patch(Circle((fx, fy), 7, fill=False, ec=TINTA, lw=0.6))
    ax.add_patch(Rectangle((40, 40), L - 80, 60, fill=False, ec="#999", ls="--"))
    ax.text(L / 2, 70, "frente (porta)", ha="center", fontsize=7)
    _cota_h(ax, 0, L, P + 30, f"{L}")
    _cota_v(ax, -40, 0, P, f"{P}")
    ax.set_title("CORTE B-B (PLANTA NA ALTURA DO INDUTOR) – furos Ø14 indicativos", fontsize=9, weight="bold")
    ax.set_xlim(-120, L + 60); ax.set_ylim(-40, P + 100)
    ax.set_aspect("equal"); ax.axis("off")


def vista_externa(ax, arr, proj, cat):
    L, A = arr.caixa_l, arr.caixa_a
    ax.add_patch(Rectangle((0, 0), L, A, fc="#eeeeec", ec=TINTA, lw=1.6))
    ax.add_patch(Rectangle((15, 15), L - 30, A - 30, fill=False, ec="#777", lw=0.6))
    n = arr.n_ventiladores
    for k in range(n):
        x = L / (n + 1) * (k + 1) - 75
        ax.add_patch(Rectangle((x, A - 260), 150, 150, fc="#d0d0cc", ec=TINTA, lw=0.8))
        ax.add_patch(Circle((x + 75, A - 185), 55, fill=False, ec=TINTA, lw=0.6))
        ax.text(x + 75, A - 290, "exaustão", fontsize=6, ha="center")
        ax.add_patch(Rectangle((x, 120), 150, 150, fc="#d0d0cc", ec=TINTA, lw=0.8))
        for yy in range(135, 265, 15):
            ax.plot([x + 10, x + 140], [yy, yy], color="#666", lw=0.5)
        ax.text(x + 75, 100, "entrada de ar", fontsize=6, ha="center")
    ax.add_patch(Rectangle((L - 70, A / 2 - 60), 25, 120, fc="#888", ec=TINTA))
    ax.add_patch(Rectangle((L / 2 - 130, A / 2 + 60), 260, 120, fc="white", ec=TINTA))
    ped = proj.pedido
    ax.text(L / 2, A / 2 + 160, "PLACA DE DADOS", ha="center", fontsize=6.5, weight="bold")
    ax.text(L / 2, A / 2 + 120, f"Filtro senoidal {proj.topologia}\n{ped['corrente_a']:g} A  {ped['tensao_v']:g} V  {ped['freq_rede_hz']:g} Hz\n"
            f"fs ≥ {proj.fs_hz / 1000:g} kHz  IP{arr.caixa_ip}", ha="center", va="center", fontsize=6)
    ax.add_patch(Rectangle((L / 2 - 90, A / 2 - 80), 180, 90, fc="#f6d34a", ec=TINTA))
    ax.text(L / 2, A / 2 - 35, "⚠ PERIGO – CAPACITORES\naguardar 5 min após\ndesenergizar", ha="center", va="center", fontsize=5.5)
    ax.set_title("VISTA EXTERNA (PORTA FECHADA)", fontsize=9, weight="bold")
    ax.set_xlim(-60, L + 60); ax.set_ylim(-60, A + 80)
    ax.set_aspect("equal"); ax.axis("off")


def _caixa3d(ax, x, y, z, dx, dy, dz, cor, alpha=0.85, lw=0.3):
    v = np.array([[x, y, z], [x + dx, y, z], [x + dx, y + dy, z], [x, y + dy, z],
                  [x, y, z + dz], [x + dx, y, z + dz], [x + dx, y + dy, z + dz], [x, y + dy, z + dz]])
    f = [[v[0], v[1], v[2], v[3]], [v[4], v[5], v[6], v[7]], [v[0], v[1], v[5], v[4]],
         [v[2], v[3], v[7], v[6]], [v[1], v[2], v[6], v[5]], [v[4], v[7], v[3], v[0]]]
    ax.add_collection3d(Poly3DCollection(f, facecolors=cor, edgecolors="#222", linewidths=lw, alpha=alpha))


def vista_3d(ax, arr, proj):
    L, A, P = arr.caixa_l, arr.caixa_a, arr.caixa_p
    _caixa3d(ax, 0, 0, 0, L, P, A, "#cfd6de", alpha=0.08, lw=0.8)
    _caixa3d(ax, 25, P - 29, 25, L - 50, 4, A - 50, "#bbbbbb", alpha=0.25)
    for c in arr.componentes:
        y = (P - 29 - c.y - c.d) if c.tag.startswith(("C", "RD", "X3")) else c.y
        _caixa3d(ax, c.x, y, c.z, c.w, c.d, c.h, c.cor, alpha=0.9)
    ax.set_xlim(0, L); ax.set_ylim(0, P); ax.set_zlim(0, A)
    ax.set_box_aspect((L, P, A))
    ax.view_init(elev=18, azim=-58)
    ax.set_axis_off()
    ax.set_title("PERSPECTIVA 3D – ARRANJO INTERNO", fontsize=9, weight="bold")


def diagrama_eletrico(ax, proj, arr):
    ax.set_xlim(0, 400); ax.set_ylim(0, 230); ax.axis("off")
    fases = ["U", "V", "W"]
    ys = [190, 165, 140]
    lcl = proj.l2 is not None
    b = proj.banco
    am = proj.amortecimento
    ax.add_patch(FancyBboxPatch((8, 120), 52, 90, boxstyle="round,pad=2", fc="#eef3fa", ec=TINTA))
    ax.text(34, 165, f"INVERSOR\n{proj.pedido['inversor']}\nfs = {proj.fs_hz / 1000:g} kHz\n(fixa)", ha="center", va="center", fontsize=6.5)
    x_bornes1, x_l1a, x_l1b = 80, 110, 160
    x_no = 185
    x_l2a, x_l2b = 215, 265
    x_bornes2 = 300 if lcl else 250
    for f, y in zip(fases, ys):
        ax.plot([60, x_bornes1], [y, y], color=TINTA, lw=1)
        ax.add_patch(Circle((x_bornes1, y), 3, fc="white", ec=TINTA))
        ax.text(x_bornes1, y + 6, f"X1:{f}1", fontsize=6, ha="center")
        ax.plot([x_bornes1 + 3, x_l1a], [y, y], color=TINTA, lw=1)
        xs = np.linspace(x_l1a, x_l1b, 200)
        ax.plot(xs, y + 4 * np.abs(np.sin((xs - x_l1a) / (x_l1b - x_l1a) * 4 * np.pi)), color=TINTA, lw=1)
        ax.plot([x_l1b, x_no], [y, y], color=TINTA, lw=1)
        ax.add_patch(Circle((x_no, y), 1.6, fc=TINTA))
        if lcl:
            ax.plot([x_no, x_l2a], [y, y], color=TINTA, lw=1)
            xs = np.linspace(x_l2a, x_l2b, 200)
            ax.plot(xs, y + 4 * np.abs(np.sin((xs - x_l2a) / (x_l2b - x_l2a) * 4 * np.pi)), color=TINTA, lw=1)
            ax.plot([x_l2b, x_bornes2], [y, y], color=TINTA, lw=1)
        else:
            ax.plot([x_no, x_bornes2], [y, y], color=TINTA, lw=1)
        ax.add_patch(Circle((x_bornes2, y), 3, fc="white", ec=TINTA))
        ax.text(x_bornes2, y + 6, f"X2:{f}2", fontsize=6, ha="center")
        ax.plot([x_bornes2 + 3, x_bornes2 + 30], [y, y], color=TINTA, lw=1)
    ax.text((x_l1a + x_l1b) / 2, 205, f"L1  {proj.l1.l_uh:.0f} µH/fase\n{proj.l1.i_nom_a:.0f} A", ha="center", fontsize=7)
    if lcl:
        ax.text((x_l2a + x_l2b) / 2, 205, f"L2  {proj.l2.l_uh:.0f} µH/fase", ha="center", fontsize=7)
    ax.add_patch(Circle((x_bornes2 + 55, 165), 22, fc="white", ec=TINTA))
    ax.text(x_bornes2 + 55, 165, "M\n3~", ha="center", va="center", fontsize=9, weight="bold")
    ax.text(x_bornes2 + 55, 132, f"{proj.pedido.get('motor_cv') or ''} cv  {proj.pedido.get('motor_corrente_a') or ''} A\n"
            f"cabo {proj.pedido.get('cabo_m') or '?'} m", ha="center", fontsize=6.5, va="top")

    # banco de capacitores
    xb = [150, 200, 250]
    ytop, ybar = 120, 105
    lig = b.ligacao
    for k, (f, y) in enumerate(zip(fases, ys)):
        ax.plot([x_no, x_no], [y, 128 - k * 0], color=TINTA, lw=0.8) if False else None
    for k, y in enumerate(ys):
        ax.plot([x_no, x_no + 0], [y, y], color=TINTA)
    # barramentos do banco
    for k, y in enumerate([118, 112, 106]):
        ax.plot([x_no - 4 + k * 4, x_no - 4 + k * 4], [ys[k], y], color=TINTA, lw=0.8)
        ax.plot([x_no - 4 + k * 4, 345], [y, y], color=TINTA, lw=0.8)
        ax.text(347, y, fases[k], fontsize=6, va="center")
    ramos = [("U", "V"), ("V", "W"), ("W", "U")] if lig == "Delta" else [("U", "N"), ("V", "N"), ("W", "N")]
    ybus = {"U": 118, "V": 112, "W": 106}
    for k, (a, c) in enumerate(ramos):
        x = 205 + k * 55
        ax.plot([x, x], [ybus[a], 95], color=TINTA, lw=0.8)
        ax.add_patch(Circle((x, ybus[a]), 1.4, fc=TINTA))
        yy = 95
        if am:
            ax.add_patch(Rectangle((x - 4, 78), 8, 17, fc="white", ec=TINTA))
            txt = (f"RD{k + 1} {am.r_ramo_ohm:.2f} Ω {am.p_nominal_w:g} W\n+ Cd {am.n_cd_por_ramo}x{b.uf_unit:g} µF\n(ramo paralelo a C{k + 1})"
                   if am.tipo == "rc_paralelo" else f"RD{k + 1}\n{am.r_ramo_ohm:.2f} Ω\n{am.p_nominal_w:g} W")
            ax.text(x + 7, 86, txt, fontsize=5.5, va="center")
            yy = 78
        ax.plot([x, x], [yy, 72], color=TINTA, lw=0.8)
        ax.plot([x - 9, x + 9], [72, 72], color=TINTA, lw=1.6)
        ax.plot([x - 9, x + 9], [67, 67], color=TINTA, lw=1.6)
        ax.text(x + 11, 69, f"C{k + 1}: {b.n_por_ramo}x{b.uf_unit:g} µF\n{b.v_unit:g} V (={b.c_ramo_uf:g} µF)", fontsize=5.5, va="center")
        ax.plot([x, x], [67, 55], color=TINTA, lw=0.8)
        if lig == "Delta":
            ax.plot([x, x], [55, 50], color=TINTA, lw=0.8)
            dest = ybus[c]
            xr = x - 10 - 0 * k
            ax.plot([x, x - 12], [50, 50], color=TINTA, lw=0.8)
            ax.plot([x - 12, x - 12], [50, dest], color=TINTA, lw=0.8, ls=(0, (4, 2)))
            ax.add_patch(Circle((x - 12, dest), 1.4, fc=TINTA))
            ax.text(x - 10, 46, f"barra {c}", fontsize=5.5, va="center")
        else:
            ax.plot([x, 330], [55, 55], color=TINTA, lw=0.8)
    if lig != "Delta":
        ax.text(332, 55, "N (isolado)", fontsize=6, va="center")
    ax.text(120, 40, f"Banco de capacitores ligação {lig.upper()} – {b.n_total} capacitores {b.fabricante} {b.uf_unit:g} µF / {b.v_unit:g} V; "
            f"C equivalente estrela = {b.c_y_uf:g} µF/fase; resistor de descarga {b.r_descarga_mohm * 1000:.0f} kΩ em cada capacitor.",
            fontsize=6.5)
    ax.text(120, 32, f"fr = {proj.fr_hz:.0f} Hz.  Ajustar no inversor: frequência de chaveamento FIXA = {proj.fs_hz / 1000:g} kHz; "
            "controle escalar (V/f) recomendado; parâmetros de filtro senoidal quando disponíveis.", fontsize=6.5)
    # auxiliares
    ax.add_patch(Rectangle((10, 50), 95, 55, fill=False, ec=TINTA, lw=0.8, ls="--"))
    ax.text(57, 98, "CIRCUITO AUXILIAR 220 Vca (externo)", fontsize=6, ha="center", weight="bold")
    ax.text(14, 88, "X3:1 (L) ─ F1 2A ─ TH (NA, 40 °C) ─┬─ M1", fontsize=5.8, family="monospace")
    ax.text(14, 80, "                               └─ M2", fontsize=5.8, family="monospace")
    ax.text(14, 72, "X3:2 (N) ─────────────────────────┘", fontsize=5.8, family="monospace")
    ax.text(14, 62, "X3:3/4 – contato NF de alarme de\ntemperatura (opcional)", fontsize=5.8)
    ax.text(200, 225, "DIAGRAMA ELÉTRICO TRIFILAR – POTÊNCIA E AUXILIAR", ha="center", fontsize=10, weight="bold")
    ax.text(10, 18, "PE: carcaça do indutor, placa de montagem, porta e caixa ligados ao barramento PE (cabo verde/amarelo). "
            "Blindagem do cabo do motor aterrada em 360° na entrada da caixa.", fontsize=6.5)


def gerar_desenhos(proj, arr, cat, pasta):
    os.makedirs(pasta, exist_ok=True)
    pdf_path = os.path.join(pasta, f"{proj_codigo(proj)}_desenhos.pdf")
    pngs = []
    total = 4
    with PdfPages(pdf_path) as pdf:
        # folha 1: vistas
        fig = plt.figure(figsize=A3)
        _carimbo(fig, "Arranjo geral – vistas e cortes", 1, total, proj, cat)
        ax1 = fig.add_axes([0.04, 0.17, 0.34, 0.78]); vista_frontal(ax1, arr, proj)
        ax2 = fig.add_axes([0.40, 0.17, 0.20, 0.78]); vista_lateral(ax2, arr, proj)
        ax3 = fig.add_axes([0.62, 0.55, 0.36, 0.40]); vista_superior(ax3, arr, proj)
        axl = fig.add_axes([0.62, 0.18, 0.36, 0.34]); axl.axis("off")
        linhas = [f"{c.tag:6s} {c.nome}" for c in arr.componentes if not (c.tag.startswith("C") and "." in c.tag and not c.tag.endswith(".1"))]
        axl.text(0, 1, "LEGENDA\n" + "\n".join(linhas[:22]), va="top", fontsize=6.8, family="monospace")
        pdf.savefig(fig); p = os.path.join(pasta, "folha1_vistas.png"); fig.savefig(p, dpi=110); pngs.append(p); plt.close(fig)
        # folha 2: 3D + externa
        fig = plt.figure(figsize=A3)
        _carimbo(fig, "Perspectiva 3D e vista externa", 2, total, proj, cat)
        ax = fig.add_axes([0.02, 0.15, 0.55, 0.82], projection="3d"); vista_3d(ax, arr, proj)
        ax2 = fig.add_axes([0.60, 0.17, 0.36, 0.78]); vista_externa(ax2, arr, proj, cat)
        pdf.savefig(fig); p = os.path.join(pasta, "folha2_3d_externa.png"); fig.savefig(p, dpi=110); pngs.append(p); plt.close(fig)
        # folha 3: diagrama elétrico
        fig = plt.figure(figsize=A3)
        _carimbo(fig, "Diagrama elétrico trifilar", 3, total, proj, cat)
        ax = fig.add_axes([0.03, 0.16, 0.94, 0.80]); diagrama_eletrico(ax, proj, arr)
        pdf.savefig(fig); p = os.path.join(pasta, "folha3_diagrama.png"); fig.savefig(p, dpi=110); pngs.append(p); plt.close(fig)
        # folha 4: tabela de cabos e conexões
        fig = plt.figure(figsize=A3)
        _carimbo(fig, "Lista de cabos e conexões", 4, total, proj, cat)
        ax = fig.add_axes([0.04, 0.17, 0.92, 0.78]); ax.axis("off")
        lin = [["Origem", "Destino", "Cabo", "Terminal", "Torque / obs."]]
        s = arr.cabos[0]["secao"]; npar = arr.cabos[0]["n_par"]
        for f in "UVW":
            lin.append([f"X1:{f}1", f"L1:{f}1 (entrada)", f"{npar}x{s} mm² flex 1 kV", f"tubular {s} mm²", "conforme borne do indutor"])
        for f in "UVW":
            lin.append([f"L1:{f}2 (saída)", f"X2:{f}2", f"{npar}x{s} mm² flex 1 kV", f"tubular {s} mm²", "conforme borne"])
        sc = arr.cabos[2]["secao"]
        ramos = [("U", "V"), ("V", "W"), ("W", "U")] if proj.banco.ligacao == "Delta" else [("U", "N"), ("V", "N"), ("W", "N")]
        for k, (a, b2) in enumerate(ramos):
            if proj.amortecimento:
                lin.append([f"L1:{a}2", f"RD{k + 1}:1", f"{sc} mm²", "olhal", "afastar 50 mm de plásticos"])
                lin.append([f"RD{k + 1}:2", f"C{k + 1}.x (barra)", f"{sc} mm²", "olhal", ""])
            else:
                lin.append([f"L1:{a}2", f"C{k + 1}.x (barra)", f"{sc} mm²", "olhal", ""])
            lin.append([f"C{k + 1}.x (barra)", f"L1:{b2}2" if b2 != "N" else "estrela N", f"{sc} mm²", "olhal", ""])
        lin.append([f"C*.1..{proj.banco.n_por_ramo}", "jumpers paralelos", f"{arr.cabos[3]['secao']} mm²", "conforme capacitor", "torque do fabricante do capacitor"])
        lin.append(["Indutor / placa / porta", "PE", f"{arr.cabos[4]['secao']} mm² VD/AM", "olhal", "trança na porta"])
        lin.append(["X3:1/2", "TH, M1, M2", "1,5 mm²", "ilhós", "220 Vca externo"])
        tab = ax.table(cellText=lin[1:], colLabels=lin[0], loc="upper center", cellLoc="left", colWidths=[0.16, 0.2, 0.2, 0.16, 0.28])
        tab.auto_set_font_size(False); tab.set_fontsize(8); tab.scale(1, 1.5)
        pdf.savefig(fig); p = os.path.join(pasta, "folha4_cabos.png"); fig.savefig(p, dpi=110); pngs.append(p); plt.close(fig)
    return pdf_path, pngs
