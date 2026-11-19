"""Simulação lado a lado: plataforma Python × ATP.
- rede_eletrica_png: diagrama da rede simulada (inversor → L1 → banco → cabo → motor) com os valores de CADA ramo
  calculados pelos dois programas (Python | ATP | diferença).
- ondas_lado_a_lado_png: as mesmas grandezas em duas colunas (Python à esquerda, ATP à direita) + sobreposição.
- espectro_comparado_png: espectro da tensão no banco e no motor, Python × ATP, em % da fundamental (escala linear).
"""
from __future__ import annotations
import dataclasses
import math
import os

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle, FancyBboxPatch

from .simulacao import simular
from .atp import ler_pl4, _janela, _harm

PY, AT = "#2a78d6", "#eb6834"
TINTA, TINTA2, GRADE = "#0b0b0b", "#52514e", "#e4e3df"


def _ser(D, chave):
    for k, v in D.items():
        if k.replace("'", "") == chave:
            return v
    return None


def ondas_atp(pl4_path, caso, n_ciclos=2):
    """Formas de onda do ATP nos últimos n ciclos (grade uniforme) – o que existir no .pl4."""
    d = ler_pl4(pl4_path)
    t, D = d["t"], d["dados"]
    f1 = caso["deck"].get("f1", caso["op"].f1)
    w = lambda x: _janela(t, x, f1, n_ciclos)[0]
    out = {}
    if _ser(D, "V:CPA") is not None:
        out["v_banco"] = w(_ser(D, "V:CPA") - _ser(D, "V:CPB"))
    if _ser(D, "V:MTA") is not None:
        out["v_motor"] = w(_ser(D, "V:MTA") - _ser(D, "V:MTB"))
    if _ser(D, "V:VLA") is not None:
        out["v_inv"] = w(_ser(D, "V:VLA") - _ser(D, "V:VLB"))
    ia = [_ser(D, f"I:VL{k}-LI{k}") for k in "ABC"]
    if all(x is not None for x in ia):
        out["i1"] = w(ia[0] - sum(ia) / 3)
    im = _ser(D, "I:MTA-MIA")
    if im is not None:
        out["i2"] = w(im)
    ic = _ser(D, "I:KMAB-CPB") if caso["ligacao"] == "Delta" else _ser(D, "I:KMA-NCAP")
    if ic is not None:
        out["icap"] = w(ic)
    n = len(next(iter(out.values())))
    out["t"] = np.arange(n) * (n_ciclos / f1 / n) * 1e3
    out["f1"] = f1
    return out


def ondas_python(caso, n_ciclos=2):
    p = dataclasses.replace(caso["p"], pelicular=False)
    r = simular(p, caso["op"], pts_por_portadora=120, ciclos_analise=n_ciclos)
    k_i = 1 / math.sqrt(3) if caso["ligacao"] == "Delta" else 1.0
    return dict(t=r.t * 1e3, v_inv=r.u_ab, v_banco=r.vc_ab, v_motor=getattr(r, "vm_ab", r.vc_ab), i1=r.i1, i2=r.i2,
                icap=r.icap_y * k_i, espectro=r.espectro, f1=caso["op"].f1)


def _alinhar(py, at, chave="v_banco"):
    """Desloca o Python no tempo para ficar em fase com o ATP (máxima correlação da tensão no banco)."""
    if chave not in at or chave not in py:
        return 0.0
    tt = at["t"]
    T = tt[-1] + (tt[1] - tt[0])
    y_at = at[chave] - np.mean(at[chave])
    best, s_best = -1e99, 0.0
    for s in np.linspace(0, T, 721)[:-1]:
        y = np.interp((tt + s) % T, py["t"] % T, py[chave])
        c = float(np.dot(y - y.mean(), y_at))
        if c > best:
            best, s_best = c, s
    return s_best


ROTULOS_CURTOS = {
    "v_saida_ll_fund": "V saída (fund.)", "thd_v_saida_pct": "DHTv saída", "vpk_saida": "Vpico banco",
    "v_motor_ll_fund": "V motor (fund.)", "thd_v_motor_pct": "DHTv motor", "vpk_motor": "Vpico motor",
    "i1_fund": "I1 fund.", "i1_rms": "I1 RMS", "ripple_pp": "ondulação p-p", "i2_fund": "I2 motor (fund.)",
    "icap_ramo_rms": "I ramo banco", "icap_unit_rms": "I por capacitor"}


def _caixa_valores(ax, x, y, titulo, chaves, py, at, un, largura=62):
    linhas = [titulo]
    for k in chaves:
        a, b = py.get(k), (at or {}).get(k)
        if a is None:
            continue
        u = un.get(k, "")
        if b is None:
            linhas.append(f"{ROTULOS_CURTOS[k]}: Py {a:.1f}{u} | ATP —")
        else:
            d = 100 * (b - a) / a if a else 0
            linhas.append(f"{ROTULOS_CURTOS[k]}: Py {a:.1f} | ATP {b:.1f}{u} ({d:+.1f} %)")
    ax.text(x, y, "\n".join(linhas), fontsize=7.2, family="DejaVu Sans Mono", va="top", ha="left",
            bbox=dict(boxstyle="round,pad=0.4", fc="white", ec=TINTA2, lw=0.8), zorder=5)


def rede_eletrica_png(proj, caso, py, at, arquivo):
    """Diagrama unifilar da rede simulada com os resultados dos dois programas em cada ramo."""
    ped = proj.pedido
    b = proj.banco
    p = caso["p"]
    op = caso["op"]
    un = {"v_saida_ll_fund": " V", "vpk_saida": " V", "v_motor_ll_fund": " V", "vpk_motor": " V", "thd_v_saida_pct": " %",
          "thd_v_motor_pct": " %", "i1_fund": " A", "i1_rms": " A", "ripple_pp": " A", "i2_fund": " A", "icap_ramo_rms": " A",
          "icap_unit_rms": " A"}
    fig, ax = plt.subplots(figsize=(13.5, 7.2))
    ax.set_xlim(0, 135); ax.set_ylim(0, 72); ax.axis("off")
    y0 = 46
    # barramento CC + inversor
    ax.add_patch(Rectangle((3, y0 - 7), 16, 14, fc="#f1f0ec", ec=TINTA))
    ax.text(11, y0 + 3, "INVERSOR", ha="center", fontsize=9, weight="bold")
    ax.text(11, y0 - 1, f"Vcc {op.vdc:.0f} V\nSVPWM fs {caso['deck'].get('fs_ef', op.fs) / 1000:.2f} kHz\nf1 {caso['deck'].get('f1', op.f1):.1f} Hz",
            ha="center", va="top", fontsize=7)
    # linha
    ax.plot([19, 30], [y0, y0], color=TINTA, lw=2)
    # indutor L1 (arcos)
    xs = np.linspace(30, 46, 200)
    ax.plot(xs, y0 + 2.2 * np.abs(np.sin((xs - 30) / 16 * 4 * np.pi)), color=TINTA, lw=2)
    ax.text(38, y0 + 5, f"L1 = {proj.l1.l_uh:.0f} µH/fase\n(uk {proj.l1.uk_pct:.1f} %, R {p.R1 * 1e3:.1f} mΩ)", ha="center", fontsize=7.5)
    ax.plot([46, 64], [y0, y0], color=TINTA, lw=2)
    # banco
    ax.plot([64, 64], [y0, y0 - 10], color=TINTA, lw=2)
    ax.plot([60, 68], [y0 - 10, y0 - 10], color=TINTA, lw=2.5)
    ax.plot([60, 68], [y0 - 12, y0 - 12], color=TINTA, lw=2.5)
    ax.plot([64, 64], [y0 - 12, y0 - 16], color=TINTA, lw=2)
    ax.text(70, y0 - 9, f"Banco {b.ligacao}\n{b.n_total} × {b.uf_unit:g} µF {b.v_unit:g} V\n({b.n_por_ramo}/ramo → {b.c_y_uf:g} µF Y)",
            fontsize=7.5, va="top")
    ax.text(64, y0 + 1.5, "nó do filtro", ha="center", fontsize=7, color=TINTA2)
    # cabo
    ax.plot([64, 82], [y0, y0], color=TINTA, lw=2)
    ax.add_patch(Rectangle((82, y0 - 2), 16, 4, fc="#e8f1fb", ec=TINTA))
    ax.text(90, y0 + 3.5, f"Cabo {p.cabo_m:.0f} m (π)", ha="center", fontsize=7.5)
    ax.plot([98, 110], [y0, y0], color=TINTA, lw=2)
    # motor
    ax.add_patch(Circle((116, y0), 6, fc="#f1f0ec", ec=TINTA))
    ax.text(116, y0, "M", ha="center", va="center", fontsize=14, weight="bold")
    ax.text(116, y0 - 8.5, f"{ped.get('motor_cv') or 0:g} CV · {op.i_carga:.0f} A · FP {op.fp:g}\nLσ {p.Lm * 1e3:.2f} mH · R {p.Rm * 1e3:.0f} mΩ",
            ha="center", va="top", fontsize=7)
    # valores por ramo
    _caixa_valores(ax, 1, 30, "SAÍDA DO INVERSOR / L1", ["i1_fund", "i1_rms", "ripple_pp"], py, at, un)
    _caixa_valores(ax, 44, 22, "BANCO DE CAPACITORES", ["icap_ramo_rms", "icap_unit_rms", "vpk_saida"], py, at, un)
    _caixa_valores(ax, 44, 70, "NÓ DO FILTRO (saída)", ["v_saida_ll_fund", "thd_v_saida_pct"], py, at, un)
    _caixa_valores(ax, 92, 30, "TERMINAIS DO MOTOR", ["v_motor_ll_fund", "thd_v_motor_pct", "vpk_motor", "i2_fund"], py, at, un)
    ax.text(1, 3, f"Rede simulada nos dois programas – {caso['ponto']}.  Py = plataforma Python (domínio da frequência, "
            "R constante);  ATP = ATP-EMTP (domínio do tempo, chaves ideais).  Diferença = (ATP − Py)/Py." +
            ("" if at else "   ATP: não executado neste computador."), fontsize=7.5, color=TINTA2)
    ax.set_title(f"Rede elétrica simulada – Python × ATP – {caso['ponto']}", fontsize=11, weight="bold")
    fig.savefig(arquivo, dpi=130, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return arquivo


def ondas_lado_a_lado_png(caso, pl4_path, arquivo, n_ciclos=2):
    py = ondas_python(caso, n_ciclos)
    at = ondas_atp(pl4_path, caso, n_ciclos) if pl4_path and os.path.exists(pl4_path) else {}
    s = _alinhar(py, at) if at else 0.0
    T = n_ciclos / py["f1"] * 1e3
    tt = at.get("t", np.linspace(0, T, 2000, endpoint=False))
    pyi = {k: np.interp((tt + s) % T, py["t"] % T, py[k]) for k in ("v_inv", "v_banco", "v_motor", "i1", "i2", "icap")}
    linhas = [("v_inv", "Tensão de saída do inversor L-L (V)"), ("v_banco", "Tensão no banco / saída do filtro L-L (V)"),
              ("v_motor", "Tensão nos terminais do motor L-L (V)"), ("i1", "Corrente do inversor / L1 – fase A (A)"),
              ("i2", "Corrente do motor – fase A (A)"), ("icap", "Corrente no ramo do banco (A)")]
    fig, ax = plt.subplots(len(linhas), 3, figsize=(15, 15), sharex=True, gridspec_kw={"hspace": 0.45, "wspace": 0.18})
    for i, (k, tit) in enumerate(linhas):
        ypy = pyi[k]
        yat = at.get(k)
        lim = max(np.max(np.abs(ypy)), np.max(np.abs(yat)) if yat is not None else 0) * 1.12
        for j, (y, cor, nome) in enumerate(((ypy, PY, "Python"), (yat, AT, "ATP"))):
            a = ax[i, j]
            if y is None:
                a.text(0.5, 0.5, "não medido neste deck\n(gere de novo com a v1.9)", ha="center", va="center", transform=a.transAxes,
                       color=TINTA2, fontsize=8)
            else:
                a.plot(tt, y, color=cor, lw=0.6 if k == "v_inv" else 0.9)
                rms = float(np.sqrt(np.mean(y ** 2)))
                a.text(0.01, 0.97, f"{nome}: máx {np.max(y):.0f} | mín {np.min(y):.0f} | RMS {rms:.1f}", transform=a.transAxes,
                       fontsize=7, va="top", color=cor, bbox=dict(fc="white", ec=cor, lw=0.6, boxstyle="round,pad=0.2"))
            a.set_ylim(-lim, lim)
            a.grid(color=GRADE, lw=0.5)
            a.set_title(f"{nome} – {tit}", fontsize=8.5, color=cor if y is not None else TINTA2)
        a = ax[i, 2]
        if yat is not None:
            a.plot(tt, yat, color=AT, lw=0.9, label="ATP")
        a.plot(tt, ypy, color=PY, lw=0.9, ls="--", label="Python")
        a.set_ylim(-lim, lim)
        a.grid(color=GRADE, lw=0.5)
        a.set_title("Sobreposição", fontsize=8.5)
        a.legend(fontsize=7, loc="upper right")
    for j in range(3):
        ax[-1, j].set_xlabel("t (ms) – últimos 2 ciclos em regime")
    fig.suptitle(f"Simulação Python × ATP – {caso['ponto']}", fontsize=12, weight="bold", y=0.995)
    fig.savefig(arquivo, dpi=120, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return arquivo


def espectro_comparado_png(caso, pl4_path, arquivo, n_ciclos=2):
    """Espectro (% da fundamental, linear) da tensão no banco e no motor – Python × ATP, mesmas harmônicas de f1."""
    py = ondas_python(caso, n_ciclos)
    at = ondas_atp(pl4_path, caso, n_ciclos) if pl4_path and os.path.exists(pl4_path) else {}
    fs = caso["deck"].get("fs_ef", caso["op"].fs)
    f1 = py["f1"]
    kmax = int(3.2 * fs / f1)
    fig, ax = plt.subplots(2, 1, figsize=(13, 7.4), gridspec_kw={"hspace": 0.4})
    for a, k, tit in ((ax[0], "v_banco", "Tensão no banco / saída do filtro"), (ax[1], "v_motor", "Tensão nos terminais do motor")):
        Hp = np.sqrt(2) * np.abs(_harm(np.interp(np.linspace(0, py["t"][-1], len(py["t"])), py["t"], py[k]), n_ciclos))
        pp = 100 * Hp[2:kmax] / Hp[1]
        hs = np.arange(2, kmax)
        a.vlines(hs * f1 - 0.15 * f1, 0, pp[:len(hs)], color=PY, lw=1.4, label=f"Python – DHTv {np.sqrt(np.sum(pp ** 2)):.2f} %")
        if k in at:
            Ha = np.sqrt(2) * np.abs(_harm(at[k], n_ciclos))
            pa = 100 * Ha[2:kmax] / Ha[1]
            a.vlines(hs * f1 + 0.15 * f1, 0, pa[:len(hs)], color=AT, lw=1.4, label=f"ATP – DHTv {np.sqrt(np.sum(pa ** 2)):.2f} %")
        for m in (1, 2, 3):
            a.axvline(m * fs, color="#eda100", ls="--", lw=0.8)
        a.set_ylabel("% da fundamental")
        a.set_title(f"{tit} – harmônicas de {f1:.1f} Hz até 3,2·fs (fundamental = 100 %)", fontsize=9)
        a.grid(color=GRADE, lw=0.5)
        a.legend(fontsize=8, loc="upper right")
    ax[1].set_xlabel("Frequência (Hz)")
    fig.suptitle(f"Espectro Python × ATP – {caso['ponto']}", fontsize=12, weight="bold")
    fig.savefig(arquivo, dpi=130, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return arquivo


def gerar_vistas(proj, casos, resultados, pasta_pl4, pasta_saida):
    """Para cada ponto: rede elétrica, ondas lado a lado e espectro. resultados = saída de comparar_casos (ou None)."""
    os.makedirs(pasta_saida, exist_ok=True)
    out = []
    for i, c in enumerate(casos):
        pl4 = os.path.join(pasta_pl4, c["nome"] + ".pl4") if pasta_pl4 else None
        r = (resultados or [None] * len(casos))[i] if resultados else None
        from .atp import metricas_python
        py = r["python"] if r else metricas_python(c["p"], c["op"], c["ligacao"], c["n_por_ramo"])
        at = r["atp"] if r else None
        f = dict(ponto=c["ponto"],
                 rede=rede_eletrica_png(proj, c, py, at, os.path.join(pasta_saida, f"rede_{c['nome']}.png")),
                 ondas=ondas_lado_a_lado_png(c, pl4 if pl4 and os.path.exists(pl4) else None,
                                             os.path.join(pasta_saida, f"ondas_python_atp_{c['nome']}.png")),
                 espectro=espectro_comparado_png(c, pl4 if pl4 and os.path.exists(pl4) else None,
                                                 os.path.join(pasta_saida, f"espectro_python_atp_{c['nome']}.png")))
        out.append(f)
    return out
