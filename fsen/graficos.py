"""Gráficos de engenharia (PNG) para relatórios: formas de onda, espectro, Bode, fluxo de correntes."""
from __future__ import annotations
import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from .simulacao import resposta_frequencia, HARM_TEMPO_MORTO, ParamCircuito, z_cap

# Paleta categórica validada (ordem fixa): azul, laranja, verde-água, amarelo
C1, C2, C3, C4 = "#2a78d6", "#eb6834", "#1baf7a", "#eda100"
TINTA, TINTA2, GRADE = "#0b0b0b", "#52514e", "#e4e3df"

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 9, "axes.edgecolor": TINTA2, "axes.labelcolor": TINTA,
    "xtick.color": TINTA2, "ytick.color": TINTA2, "axes.grid": True, "grid.color": GRADE, "grid.linewidth": 0.6,
    "axes.spines.top": False, "axes.spines.right": False, "lines.linewidth": 1.4, "legend.frameon": False,
    "figure.dpi": 140, "savefig.bbox": "tight", "axes.titleweight": "bold", "axes.titlesize": 10,
})


def _salvar(fig, pasta, nome):
    caminho = os.path.join(pasta, nome)
    fig.savefig(caminho, facecolor="white")
    plt.close(fig)
    return caminho


def _caixa(ax, x, y, txt, cor, dy=4):
    ax.annotate(txt, (x, y), xytext=(4, dy), textcoords="offset points", fontsize=7, color=cor,
                bbox=dict(boxstyle="round,pad=0.25", fc="white", ec=cor, lw=0.8, alpha=0.95), zorder=6)


def _maxmin(ax, t, y, cor, un, rotulo, nivel=0):
    """Caixas com máximo e mínimo instantâneo + RMS da curva (nivel escalona as caixas para não sobrepor)."""
    i, j = int(np.argmax(y)), int(np.argmin(y))
    rms = float(np.sqrt(np.mean(np.asarray(y) ** 2)))
    ax.plot([t[i], t[j]], [y[i], y[j]], "o", ms=3.5, color=cor, zorder=5)
    _caixa(ax, t[i], y[i], f"{rotulo} máx {y[i]:.0f} {un} | RMS {rms:.1f} {un}", cor, dy=4 + 15 * nivel)
    _caixa(ax, t[j], y[j], f"{rotulo} mín {y[j]:.0f} {un}", cor, dy=-14 - 15 * nivel)


def formas_onda(sim, titulo, pasta, nome="formas_onda.png"):
    t = sim.t * 1000
    fig, ax = plt.subplots(2, 1, figsize=(9.2, 7.0), sharex=True, gridspec_kw={"hspace": 0.38})
    ax[0].plot(t, sim.u_ab, color="#b9b8b2", lw=0.5, label="Saída do inversor (PWM) U-V")
    ax[0].plot(t, sim.vc_ab, color=C1, lw=1.8, label="Saída do filtro U-V")
    vm = getattr(sim, "vm_ab", None)
    if vm is not None and len(vm) == len(t):
        ax[0].plot(t, vm, color=C3, lw=1.0, ls="--", label="Terminais do motor U-V")
    _maxmin(ax[0], t, sim.vc_ab, C1, "V", "Filtro")
    _maxmin(ax[0], t, sim.u_ab, TINTA2, "V", "Inversor", nivel=1)
    ax[0].set_ylabel("Tensão de linha (V)")
    ax[0].set_title(f"Tensões – {titulo}")
    ax[0].legend(loc="upper center", bbox_to_anchor=(0.5, -0.04), ncol=3, fontsize=8)
    ax[1].plot(t, sim.i1, color=C2, lw=1.0, label="Inversor / indutor (i1)")
    ax[1].plot(t, sim.i2, color=C1, lw=1.8, label="Motor (i2)")
    ax[1].plot(t, sim.icap_y, color=C3, lw=1.0, label="Ramo capacitivo (Y eq.)")
    _maxmin(ax[1], t, sim.i1, C2, "A", "i1")
    _maxmin(ax[1], t, sim.i2, C1, "A", "i2", nivel=1)
    _maxmin(ax[1], t, sim.icap_y, C3, "A", "iC")
    ax[1].set_ylabel("Corrente fase U (A)")
    ax[1].set_xlabel("Tempo (ms)")
    ax[1].set_title("Correntes")
    ax[1].legend(loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=3, fontsize=8)
    return _salvar(fig, pasta, nome)


def tabela_thd(pontos):
    """Linhas: ponto de operação; colunas: DHTv % no inversor, na saída do filtro e nos terminais do motor."""
    return [dict(ponto=p["nome"], f_hz=p["f1"], inversor=round(p["thd_v_inversor_pct"], 1),
                 saida_filtro=round(p["thd_v_saida_pct"], 2), motor=round(p.get("thd_v_motor_pct", p["thd_v_saida_pct"]), 2))
            for p in pontos]


def espectro(sim, f1, fs, pasta, nome="espectro.png", pontos=None):
    """Espectro em % da fundamental, escala LINEAR: em cima o inversor; embaixo saída do filtro e motor (escala própria).
    À direita, tabela de DHTv % (inversor, saída do filtro, motor) por ponto de operação."""
    e = sim.espectro
    f = e["f"]
    idx1 = np.argmin(np.abs(f - f1))
    fund_u = e["u"][idx1]
    msk = (f > 1.5 * f1) & (f <= 3.2 * fs)
    fx = f[msk]
    pu = 100 * e["u"][msk] / fund_u
    pv = 100 * e["vc"][msk] / fund_u
    pm = 100 * e["vm"][msk] / fund_u if "vm" in e else None
    fig = plt.figure(figsize=(11.5, 6.4))
    a1 = fig.add_axes([0.06, 0.56, 0.6, 0.36])
    a2 = fig.add_axes([0.06, 0.09, 0.6, 0.36], sharex=a1)
    a1.vlines(fx, 0, pu, color="#8f8e88", lw=0.9, label="Inversor (PWM)")
    a2.vlines(fx, 0, pv, color=C1, lw=1.6, label="Saída do filtro")
    if pm is not None:
        a2.vlines(fx + 0.004 * fs, 0, pm, color=C3, lw=1.1, label="Motor")
    for a, y, tit in ((a1, pu, f"Inversor – harmônicas em % da fundamental ({f1:g} Hz; fundamental = 100 %)"),
                      (a2, np.maximum(pv, pm if pm is not None else pv), "Saída do filtro e motor – % da fundamental (escala própria)")):
        ym = max(float(y.max()) if len(y) else 0.1, 0.05) * 1.25
        a.set_ylim(0, ym)
        a.set_ylabel("% da fundamental")
        a.set_title(tit, fontsize=9)
        for k in (1, 2, 3):
            a.axvline(k * fs, color=C4, lw=0.8, ls="--")
            a.text(k * fs, ym * 0.97, f"{k}·fs", color=TINTA2, ha="center", va="top", fontsize=8)
        a.legend(loc="upper right", fontsize=8, bbox_to_anchor=(1.0, 0.88))
    a2.set_xlabel("Frequência (Hz)")
    if len(pu):
        k = int(np.argmax(pu)); _caixa(a1, fx[k], pu[k], f"máx {pu[k]:.1f} % @ {fx[k]:.0f} Hz", TINTA2)
        k = int(np.argmax(pv)); _caixa(a2, fx[k], pv[k], f"máx saída filtro {pv[k]:.2f} % @ {fx[k]:.0f} Hz", C1)
        if pm is not None:
            k = int(np.argmax(pm)); _caixa(a2, fx[k], pm[k], f"máx motor {pm[k]:.2f} % @ {fx[k]:.0f} Hz", C3, dy=-16)
    axt = fig.add_axes([0.69, 0.09, 0.30, 0.83])
    axt.axis("off")
    linhas = tabela_thd(pontos) if pontos else []
    cel = [[l["ponto"].replace("Operação ", "").replace(" (", "\n("), f"{l['inversor']:.1f}", f"{l['saida_filtro']:.2f}", f"{l['motor']:.2f}"]
           for l in linhas]
    if cel:
        tb = axt.table(cellText=cel, colLabels=["Ponto", "Inversor\nDHTv %", "Saída\nfiltro\nDHTv %", "Motor\nDHTv %"],
                       loc="upper center", cellLoc="center", colWidths=[0.37, 0.21, 0.21, 0.21])
        tb.auto_set_font_size(False)
        tb.set_fontsize(8)
        tb.scale(1, 3.0)
        for (r, c), cell in tb.get_celld().items():
            cell.set_edgecolor(GRADE)
            if r == 0:
                cell.set_text_props(weight="bold")
                cell.set_facecolor("#f1f0ec")
                cell.set_height(cell.get_height() * 1.35)
        axt.set_title("Distorção harmônica total de tensão (DHTv)", fontsize=9)
        axt.text(0.5, 0.02, "DHTv até 4·fs. Inversor = tensão PWM de linha;\nsaída do filtro = bornes do filtro;\n"
                 "motor = terminais do motor (após o cabo).", ha="center", va="bottom", fontsize=7, color=TINTA2, transform=axt.transAxes)
    return _salvar(fig, pasta, nome)


def grandezas_rms(proj, pasta, nome="grandezas_rms.png"):
    """Correntes e tensões RMS em todos os ramos, por ponto de operação, com caixas de máximo e mínimo."""
    pts = proj.pontos
    b = proj.banco
    delta = b.ligacao == "Delta"
    n = max(1, b.n_por_ramo)
    w = lambda p: 2 * np.pi * p["f1"]
    L = proj.l1.l_uh * 1e-6
    nomes = [p["nome"].replace("Operação ", "").replace(" (", "\n(") for p in pts]
    cor = {"Inversor / indutor L1": C2, "Motor": C1, "Capacitor (por unidade)": C3, "Ramo capacitivo (Y eq.)": "#7fd1b3",
           "Ondulação no indutor": C4}
    I = {"Inversor / indutor L1": [p["i1_rms"] for p in pts],
         "Motor": [p["i2_rms"] for p in pts],
         "Ramo capacitivo (Y eq.)": [p.get("icap_main_y_rms", p["icap_y_rms"]) for p in pts],
         "Capacitor (por unidade)": [p.get("icap_main_y_rms", p["icap_y_rms"]) / (np.sqrt(3) if delta else 1) / n for p in pts],
         "Ondulação no indutor": [p["ripple_rms"] for p in pts]}
    V = {"Inversor (PWM, até 4·fs)": [p["v_inv_ll_fund"] * np.sqrt(1 + (p["thd_v_inversor_pct"] / 100) ** 2) for p in pts],
         "Inversor (fundamental)": [p["v_inv_ll_fund"] for p in pts],
         "Saída do filtro": [p["v_saida_ll_fund"] * np.sqrt(1 + (p["thd_v_saida_pct"] / 100) ** 2) for p in pts],
         "Motor (terminais)": [p.get("v_motor_ll_fund", p["v_saida_ll_fund"]) * np.sqrt(1 + (p.get("thd_v_motor_pct", 0) / 100) ** 2)
                               for p in pts],
         "Capacitor (por unidade)": [p["v_saida_ll_fund"] * np.sqrt(1 + (p["thd_v_saida_pct"] / 100) ** 2) / (1 if delta else np.sqrt(3))
                                     for p in pts],
         "Queda no indutor L1 (linha)": [np.sqrt(3) * w(p) * L * p.get("i1_fund", p["i1_rms"]) for p in pts]}
    corv = {"Inversor (PWM, até 4·fs)": "#b9b8b2", "Inversor (fundamental)": TINTA2, "Saída do filtro": C1, "Motor (terminais)": C3,
            "Capacitor (por unidade)": "#7fd1b3", "Queda no indutor L1 (linha)": C2}
    fig, ax = plt.subplots(2, 1, figsize=(10.5, 8.6), gridspec_kw={"hspace": 0.55})
    for a, dados, cores, un, tit in ((ax[0], I, cor, "A", "Correntes RMS por ramo"), (ax[1], V, corv, "V", "Tensões RMS por ramo (linha, salvo indicado)")):
        x = np.arange(len(pts))
        k = len(dados)
        larg = 0.8 / k
        for j, (lab, vals) in enumerate(dados.items()):
            xs = x + (j - (k - 1) / 2) * larg
            bars = a.bar(xs, vals, larg * 0.92, color=cores[lab], label=f"{lab}  [máx {max(vals):.1f} | mín {min(vals):.1f} {un}]")
            a.bar_label(bars, fmt="%.1f", fontsize=6.5, color=TINTA2, padding=1, rotation=90)
            jm, jn = int(np.argmax(vals)), int(np.argmin(vals))
            a.plot([xs[jm]], [vals[jm]], marker="v", color=cores[lab], ms=5, zorder=5)
        a.set_xticks(x, nomes, fontsize=8)
        a.set_ylabel(f"RMS ({un})")
        a.set_title(tit)
        a.set_ylim(0, max(max(v) for v in dados.values()) * 1.28)
        a.legend(fontsize=7, ncol=2, loc="upper center", bbox_to_anchor=(0.5, -0.16))
    if proj.banco.i_unit_max:
        ax[0].axhline(proj.banco.i_unit_max, color=C3, ls=":", lw=0.9)
        ax[0].text(len(pts) - 0.5, proj.banco.i_unit_max, f"Imax capacitor {proj.banco.i_unit_max:g} A", fontsize=7, color=C3,
                   ha="right", va="bottom")
    ax[0].axhline(proj.pedido["corrente_a"], color=TINTA2, ls=":", lw=0.9)
    ax[0].text(-0.45, proj.pedido["corrente_a"], f"In filtro {proj.pedido['corrente_a']:g} A", fontsize=7, color=TINTA2, va="bottom")
    ax[1].axhline(proj.banco.v_unit, color=C3, ls=":", lw=0.9)
    ax[1].text(len(pts) - 0.5, proj.banco.v_unit, f"V nominal capacitor {proj.banco.v_unit:g} V", fontsize=7, color=C3, ha="right", va="bottom")
    return _salvar(fig, pasta, nome)


def bode(p: ParamCircuito, fr, fs, fmin_op, fmax_op, pasta, nome="resposta_frequencia.png"):
    f, H, Hm, Zin = resposta_frequencia(p, fmax=max(4 * fs, 10000))
    p0 = ParamCircuito(**{**p.__dict__, "Rd": 0.0, "Cd": 0.0, "Rdp": 0.0})
    _, H0, _, _ = resposta_frequencia(p0, fmax=max(4 * fs, 10000))
    _, Hv, _, _ = resposta_frequencia(p, fmax=max(4 * fs, 10000), com_carga=False)
    fig, ax = plt.subplots(2, 1, figsize=(8.2, 5.8), sharex=True)
    ax[0].semilogx(f, 20 * np.log10(np.abs(Hm)), color=C1, lw=2, label="Projeto (com motor)")
    ax[0].semilogx(f, 20 * np.log10(np.abs(Hv)), color=C3, lw=1.2, label="Projeto (em vazio)")
    if p.Rd or p.Cd:
        ax[0].semilogx(f, 20 * np.log10(np.abs(H0)), color=C2, lw=1.0, ls="--", label="Sem amortecimento")
    ax[0].axvspan(5 * fmin_op, 25 * fmax_op, color=C4, alpha=0.12, lw=0)
    ax[0].text(np.sqrt(5 * fmin_op * 25 * fmax_op), -55, "harmônicas 5ª–25ª\nda faixa de operação", ha="center",
               fontsize=8, color=TINTA2)
    for x, lab in ((fr, f"fr = {fr:.0f} Hz"), (fs, f"fs = {fs:.0f} Hz")):
        ax[0].axvline(x, color=TINTA2, lw=0.8, ls=":")
        ax[0].text(x * 1.08, 24, lab, fontsize=8, color=TINTA)
    ax[0].set_ylim(-70, 30)
    ax[0].set_ylabel("Ganho Vmotor/Vinv (dB)")
    ax[0].set_title("Resposta em frequência do filtro")
    ax[0].legend(loc="lower left", fontsize=8)
    ax[1].semilogx(f, np.degrees(np.angle(Hm)), color=C1, lw=1.6)
    ax[1].set_ylabel("Fase (°)")
    ax[1].set_xlabel("Frequência (Hz)")
    ax[1].set_ylim(-200, 20)
    return _salvar(fig, pasta, nome)


def impedancia(p: ParamCircuito, fr, fs, pasta, nome="impedancia_entrada.png"):
    f, H, Hm, Zin = resposta_frequencia(p, fmax=max(4 * fs, 10000))
    fig, ax = plt.subplots(figsize=(8.2, 3.2))
    ax.loglog(f, np.abs(Zin), color=C1, lw=1.8)
    ax.axvline(fr, color=TINTA2, ls=":", lw=0.8)
    ax.axvline(fs, color=TINTA2, ls=":", lw=0.8)
    ax.set_xlabel("Frequência (Hz)")
    ax.set_ylabel("|Z| vista pelo inversor (Ω)")
    ax.set_title("Impedância de entrada do filtro (com motor)")
    return _salvar(fig, pasta, nome)


def baixa_ordem(p: ParamCircuito, fmin, fmax, pasta, nome="ressonancia_baixa_ordem.png"):
    fig, ax = plt.subplots(figsize=(8.2, 3.4))
    freqs = np.arange(fmin, fmax + 1e-9, 0.25)
    rp = p.Q_hf * 2 * np.pi * p.fs_ref * p.L1
    cores = [C1, C2, C3, C4]
    hs = [5, 7, 11, 13, 17, 19, 23, 25]
    tot = np.zeros_like(freqs)
    for h in hs:
        s = 2j * np.pi * h * freqs
        Zl1 = (p.R1 + s * p.L1) * rp / (p.R1 + s * p.L1 + rp)
        Zc = z_cap(p, s)
        Zm = (p.R2 + p.Rm) + s * (p.L2 + p.Lm)
        Zp = Zc * Zm / (Zc + Zm)
        tot += (HARM_TEMPO_MORTO[h] * np.abs(Zp / (Zl1 + Zp))) ** 2
    ax.plot(freqs, np.sqrt(tot), color=C1, lw=2, label="THD de baixa ordem na saída (tempo morto)")
    ax.axhline(3.0, color=C2, ls="--", lw=1, label="Limite de projeto 3 %")
    ax.set_ylim(0, max(5.0, 1.15 * np.sqrt(tot).max()))
    ax.set_xlabel("Frequência de saída do inversor (Hz)")
    ax.set_ylabel("THD baixa ordem (%)")
    ax.set_title("Robustez à ressonância na faixa de operação")
    ax.legend(loc="upper left", fontsize=8)
    return _salvar(fig, pasta, nome)


def fluxo_correntes(pontos, In, pasta, nome="fluxo_correntes.png"):
    nomes = [p["nome"].replace("Operação ", "") for p in pontos]
    x = np.arange(len(pontos))
    w = 0.2
    fig, ax = plt.subplots(figsize=(8.2, 3.6))
    series = [("Inversor i1 (RMS)", [p["i1_rms"] for p in pontos], C2),
              ("Motor i2 (RMS)", [p["i2_rms"] for p in pontos], C1),
              ("Capacitores (Y, RMS)", [p["icap_y_rms"] for p in pontos], C3),
              ("Ondulação no indutor (RMS)", [p["ripple_rms"] for p in pontos], C4)]
    for k, (lab, vals, cor) in enumerate(series):
        b = ax.bar(x + (k - 1.5) * w, vals, w * 0.92, color=cor, label=lab)
        ax.bar_label(b, fmt="%.0f", fontsize=7, color=TINTA2, padding=1)
    ax.axhline(In, color=TINTA2, ls=":", lw=1)
    ax.text(x[-1] + 0.45, In, f"In filtro {In:.0f} A", fontsize=8, color=TINTA2, va="bottom", ha="right")
    ax.set_xticks(x, nomes, fontsize=8)
    ax.set_ylabel("Corrente (A)")
    ax.set_title("Fluxo de correntes por ramo e ponto de operação")
    ax.legend(ncol=2, fontsize=8, loc="upper center", bbox_to_anchor=(0.5, -0.15))
    return _salvar(fig, pasta, nome)


def gerar_todos(proj, pasta):
    os.makedirs(pasta, exist_ok=True)
    ped = proj.pedido
    fmax = ped["f_saida_max_hz"] or ped["freq_rede_hz"]
    fmin = ped["f_saida_min_hz"] or max(0.5 * fmax, 20)
    p = proj.circuito()
    out = {}
    sims = getattr(proj, "_sims", None)
    if sims:
        out["formas_onda"] = formas_onda(sims[0], proj.pontos[0]["nome"], pasta)
        out["espectro"] = espectro(sims[0], proj.pontos[0]["f1"], proj.fs_hz, pasta, pontos=proj.pontos)
    out["bode"] = bode(p, proj.fr_hz, proj.fs_hz, fmin, fmax, pasta)
    out["impedancia"] = impedancia(p, proj.fr_hz, proj.fs_hz, pasta)
    out["baixa_ordem"] = baixa_ordem(p, fmin, fmax, pasta)
    out["fluxo"] = fluxo_correntes(proj.pontos, ped["corrente_a"], pasta)
    out["rms"] = grandezas_rms(proj, pasta)
    return out


def grafico_pareto(df, pasta, nome="otimizacao_pareto.png"):
    """Mapa de todas as configurações viáveis: custo × volume da caixa, cor = perdas; destaque Pareto e escolhida."""
    v = df[df.viavel]
    fig, ax = plt.subplots(1, 2, figsize=(10.5, 4.2), gridspec_kw={"wspace": 0.28})
    sem = v[v.Q_amort == 0]
    com = v[v.Q_amort != 0]
    ax[0].scatter(com.custo_total / 1000, com.perdas_W, s=10, color="#c9c8c2", label="com resistor de amortecimento")
    ax[0].scatter(sem.custo_total / 1000, sem.perdas_W, s=14, color=C3, label="sem resistor")
    par = v[v.pareto]
    ax[0].scatter(par.custo_total / 1000, par.perdas_W, s=26, facecolors="none", edgecolors=C1, lw=1.2, label="fronteira de Pareto")
    if v.nota.notna().any():
        b = v.loc[v.nota.idxmax()]
        ax[0].scatter([b.custo_total / 1000], [b.perdas_W], s=140, marker="*", color=C2, zorder=5, label="escolhida (melhor nota)")
    ax[0].set_xlabel("Custo do filtro montado (mil R$)")
    ax[0].set_ylabel("Perdas totais (W)")
    ax[0].set_title("Custo × aquecimento")
    ax[0].legend(fontsize=7, loc="upper right")
    ax[1].scatter(v.fr_Hz, v.thd_pct, s=10, c=v.uk_pct, cmap="Blues", vmin=v.uk_pct.min() - 2, vmax=v.uk_pct.max())
    if v.nota.notna().any():
        ax[1].scatter([b.fr_Hz], [b.thd_pct], s=140, marker="*", color=C2, zorder=5)
    ax[1].axvspan(780, 1330, color=C4, alpha=0.12, lw=0)
    ax[1].text(1055, 0.6, "faixa TDK/EPCOS 780–1330 Hz", ha="center", fontsize=7, color=TINTA2)
    ax[1].set_xlabel("Frequência de ressonância (Hz)")
    ax[1].set_ylabel("THD tensão no motor (%)")
    ax[1].set_title("Ressonância × THD (cor = uk %)")
    return _salvar(fig, pasta, nome)


def grafico_termico(proj, arr, pasta, nome="estudo_termico.png"):
    """Vista frontal com componentes coloridos pela temperatura + perfil vertical do ar."""
    from matplotlib.patches import Rectangle
    from matplotlib import cm, colors
    t = getattr(proj, "termico", None)
    if not t:
        return None
    perfil = t["perfil"]
    zs = [z for z, _ in perfil]
    ts = [v for _, v in perfil]
    tcomp = {}
    for c in t["componentes"]:
        if c["componente"].startswith("Indutor L1"):
            tcomp["L1"] = c["t_componente_C"]
        elif c["componente"].startswith("Indutor L2"):
            tcomp["L2"] = c["t_componente_C"]
        elif c["componente"].startswith("Capacitores"):
            tcomp["C"] = c["t_componente_C"]
        elif c["componente"].startswith("Resistores"):
            tcomp["RD"] = c["t_componente_C"]
    vmin, vmax = t["t_ambiente_C"], max(list(tcomp.values()) + ts + [t["t_ambiente_C"] + 20])
    norm = colors.Normalize(vmin=vmin, vmax=min(vmax, 160))
    cmap = matplotlib.colormaps["YlOrRd"]
    fig, ax = plt.subplots(1, 2, figsize=(9.5, 6.2), gridspec_kw={"width_ratios": [1.25, 1], "wspace": 0.35})
    a = ax[0]
    a.add_patch(Rectangle((0, 0), arr.caixa_l, arr.caixa_a, fill=False, lw=1.5, ec=TINTA))
    for c in arr.componentes:
        key = "C" if (c.tag.startswith("C") and "." in c.tag) else ("RD" if c.tag.startswith("RD") else c.tag)
        if key in tcomp:
            fc = cmap(norm(tcomp[key]))
        else:
            zc = c.z + c.h / 2
            fc = cmap(norm(np.interp(zc, zs, ts)))
        a.add_patch(Rectangle((c.x, c.z), c.w, c.h, fc=fc, ec=TINTA, lw=0.5))
        if key in ("L1", "L2"):
            a.text(c.x + c.w / 2, c.z + c.h / 2, f"{key}\n{tcomp[key]:.0f} °C", ha="center", va="center", fontsize=8, weight="bold")
    if "C" in tcomp:
        caps = [c for c in arr.componentes if c.tag.startswith("C") and "." in c.tag]
        zt = max(c.z + c.h for c in caps)
        a.text(arr.caixa_l - 30, zt + 20, f"capacitor mais quente {tcomp['C']:.0f} °C", ha="right", fontsize=7.5)
    a.annotate("", xy=(arr.caixa_l * 0.08, arr.caixa_a * 0.95), xytext=(arr.caixa_l * 0.08, arr.caixa_a * 0.05),
               arrowprops=dict(arrowstyle="->", color=C1, lw=1.5))
    a.text(arr.caixa_l * 0.1, arr.caixa_a * 0.5, "ar", color=C1, fontsize=8, rotation=90)
    a.set_xlim(-50, arr.caixa_l + 50)
    a.set_ylim(-50, arr.caixa_a + 50)
    a.set_aspect("equal")
    a.axis("off")
    a.set_title(f"Mapa térmico ({'capacitores embaixo' if t['arranjo_escolhido'] == 'capacitores_embaixo' else 'indutor embaixo'})")
    sm = cm.ScalarMappable(norm=norm, cmap=cmap)
    fig.colorbar(sm, ax=a, fraction=0.04, pad=0.02, label="°C")
    b = ax[1]
    b.plot(ts, [z / 1000 for z in zs], color=C2, lw=2, label="Ar interno")
    b.axvline(t["t_ambiente_C"], color=TINTA2, ls=":", lw=1)
    b.text(t["t_ambiente_C"] + 0.3, 0.05, "ambiente", fontsize=7, color=TINTA2, rotation=90)
    b.axvline(55, color=C4, ls="--", lw=1)
    b.text(55.3, arr.caixa_a / 1000 * 0.6, "55 °C (cat. D capacitores)", fontsize=7, color=TINTA2, rotation=90)
    b.set_xlabel("Temperatura do ar (°C)")
    b.set_ylabel("Altura na caixa (m)")
    b.set_title(f"Perfil vertical – {t['n_ventiladores']} vent., {t['vazao_efetiva_m3h']} m³/h efetivos")
    return _salvar(fig, pasta, nome)
