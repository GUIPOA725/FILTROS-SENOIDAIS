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


def formas_onda(sim, titulo, pasta, nome="formas_onda.png"):
    t = sim.t * 1000
    fig, ax = plt.subplots(2, 1, figsize=(8.2, 6.4), sharex=True, gridspec_kw={"hspace": 0.35})
    ax[0].plot(t, sim.u_ab, color=GRADE if False else "#b9b8b2", lw=0.5, label="Saída do inversor (PWM) U-V")
    ax[0].plot(t, sim.vc_ab, color=C1, lw=1.8, label="Saída do filtro / motor U-V")
    ax[0].set_ylabel("Tensão de linha (V)")
    ax[0].set_title(f"Tensões – {titulo}")
    ax[0].legend(loc="upper center", bbox_to_anchor=(0.5, -0.04), ncol=2, fontsize=8)
    ax[1].plot(t, sim.i1, color=C2, lw=1.0, label="Inversor / indutor (i1)")
    ax[1].plot(t, sim.i2, color=C1, lw=1.8, label="Motor (i2)")
    ax[1].plot(t, sim.icap_y, color=C3, lw=1.0, label="Ramo capacitivo (Y eq.)")
    ax[1].set_ylabel("Corrente fase U (A)")
    ax[1].set_xlabel("Tempo (ms)")
    ax[1].set_title("Correntes")
    ax[1].legend(loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=3, fontsize=8)
    return _salvar(fig, pasta, nome)


def espectro(sim, f1, fs, pasta, nome="espectro.png"):
    e = sim.espectro
    f = e["f"]
    idx1 = np.argmin(np.abs(f - f1))
    fund_u = e["u"][idx1]
    fig, ax = plt.subplots(figsize=(8.2, 3.6))
    msk = (f > 0) & (f <= 3.2 * fs)
    ax.vlines(f[msk], 1e-3, 100 * e["u"][msk] / fund_u, color="#b9b8b2", lw=0.8, label="Inversor (PWM)")
    ax.vlines(f[msk], 1e-3, 100 * e["vc"][msk] / fund_u, color=C1, lw=1.2, label="Saída do filtro")
    ax.set_yscale("log")
    ax.set_ylim(1e-2, 150)
    ax.set_xlabel("Frequência (Hz)")
    ax.set_ylabel("% da fundamental (log)")
    ax.set_title("Espectro harmônico da tensão de linha")
    for k in (1, 2, 3):
        ax.axvline(k * fs, color=C4, lw=0.8, ls="--")
        ax.text(k * fs, 110, f"{k}·fs", color=TINTA2, ha="center", fontsize=8)
    ax.legend(loc="upper right")
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
        out["espectro"] = espectro(sims[0], proj.pontos[0]["f1"], proj.fs_hz, pasta)
    out["bode"] = bode(p, proj.fr_hz, proj.fs_hz, fmin, fmax, pasta)
    out["impedancia"] = impedancia(p, proj.fr_hz, proj.fs_hz, pasta)
    out["baixa_ordem"] = baixa_ordem(p, fmin, fmax, pasta)
    out["fluxo"] = fluxo_correntes(proj.pontos, ped["corrente_a"], pasta)
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
