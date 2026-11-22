"""Transitórios eletromagnéticos de bancos DESSINTONIZADOS e filtros SINTONIZADOS – v1.20.0.

Mesma filosofia da dupla checagem do filtro senoidal: a plataforma simula no tempo com o MESMO método do ATP-EMTP
(regra trapezoidal, passo fixo, inicialização fasorial em regime permanente, chaves ideais que abrem no zero de
corrente) e gera o deck .atp da mesma rede para rodar no ATP instalado e comparar.

Rede (por fase, no lado de baixa tensão):
  fonte ideal (tipo 14, cosseno) → Zrede MT referida (Scc, X/R 10) + Ztrafo (Z %, X/R pelo porte) → BARRA
  → por estágio: contatora (chave 3 polos) → reator (R = ωL/FQ, L) → capacitor em Δ (C por fase do Δ) ∥ resistores
     de descarga; nós internos com 100 MΩ à terra (referência – igual nos dois programas)
  → harmônicas da carga como fontes de corrente na barra (caso de regime).

Casos (IEEE 1036 / IEEE C37.012 / IEC 60831-1 / IEC 60871 / estudos de manobra de filtros):
  E1 energização do 1º estágio no pior instante (varredura do ângulo de fechamento em 0–360°)
  E2 back-to-back: último estágio com os demais ligados (pior para contatora e fusível)
  E3 k estágios ao mesmo tempo → quantos podem entrar juntos
  E4 dispersão dos polos da contatora (0 / 1,5 / 3 ms)
  D1 desenergização: tensão de restabelecimento (TRV) na contatora e carga residual no capacitor
  D2 reacendimento (restrike) meio ciclo após a abertura
  R1 religamento com o capacitor carregado (antes do tempo de descarga) – mostra por que o controlador precisa de bloqueio
  S1 regime permanente com todas as harmônicas da carga (confere o cálculo em frequência da plataforma)
Avaliação de cada componente: contatora (pico de fechamento × capacidade AC-6b), fusível (I²t × I²t de fusão),
disjuntor (pico × disparo magnético), capacitor (2√2·Un e 100·In – IEC 60831-1), reator (pico × Isat),
barra (sobretensão × suportabilidade de inversores/cargas sensíveis), resistor de descarga (tempo até 75 V).
"""
from __future__ import annotations

import math

from . import checagem as CK
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np

R_TERRA = 1e8            # Ω – referência dos nós flutuantes (estágios desligados), igual no ATP
R_CHAVE = 1e-6           # Ω – chave fechada no Python (ATP: chave ideal)
FASES = "ABC"

# I²t de fusão (pré-arco, A²s) típico de fusíveis NH gG – conferir no catálogo do fabricante escolhido
I2T_FUSAO_GG = {16: 300, 20: 500, 25: 900, 32: 1600, 35: 2000, 40: 2700, 50: 4500, 63: 7500, 80: 12500, 100: 21000,
                125: 36000, 160: 60000, 200: 105000, 224: 135000, 250: 170000, 315: 290000, 355: 400000, 400: 520000,
                500: 900000, 630: 1500000}
K_CONT_COMUM = 30         # pico de fechamento ≤ 30·Ie – contatora comum AC-6b com reator em série
K_CONT_ESPECIAL = 200     # contatora para capacitor com resistores de pré-carga (Epcos B44066, Schneider LC1-D…K, WEG CWMC)
K_DISJ_MAG = 10           # disjuntor curva C: disparo magnético em 10·In (pior caso; curva D = 20·In)
V_BARRA_INV = 1.30        # pu – sobretensão na barra que pode desarmar inversores (sobretensão no barramento CC)
V_BARRA_MAX = 2.00        # pu – suportabilidade geral de equipamentos BT a surtos de manobra
V_DESCARGA = 75.0         # V – IEC 60831-1: capacitor deve descarregar a ≤ 75 V em 3 min


# ------------------------------------------------------------------------------------------------- rede
@dataclass
class Rede:
    f: float
    dt: float
    tmax: float
    ramos: List[dict] = field(default_factory=list)       # n1, n2, R, L, C, nome, saida(bool)
    chaves: List[dict] = field(default_factory=list)      # n1, n2, tf (fechamento), ta (abertura), nome
    fontes_v: List[dict] = field(default_factory=list)    # no, amp, fase_graus (cosseno), f
    fontes_i: List[dict] = field(default_factory=list)    # no (injeção da terra para o nó), amp, fase_graus, f
    saida_nos: List[str] = field(default_factory=list)

    def ramo(self, n1, n2, R=0.0, L=0.0, C=0.0, nome="", saida=False):
        self.ramos.append(dict(n1=n1, n2=n2, R=R, L=L, C=C, nome=nome or f"{n1}-{n2}", saida=saida))

    def chave(self, n1, n2, tf, ta=1e3, nome=""):
        self.chaves.append(dict(n1=n1, n2=n2, tf=tf, ta=ta, nome=nome or f"{n1}-{n2}"))


# ------------------------------------------------------------------------------------------------- solver (EMTP)
class _Elem:
    __slots__ = ("a", "b", "tipo", "G", "x", "ih", "i", "v", "nome", "chave")

    def __init__(self, a, b, tipo, x, nome="", chave=None):
        self.a, self.b, self.tipo, self.x, self.nome, self.chave = a, b, tipo, x, nome, chave
        self.ih = self.i = self.v = 0.0


def simular(rede: Rede, gravar: Optional[List[str]] = None):
    """Simulação EMTP (trapezoidal, passo fixo) – devolve dict(t, V[no], I[nome da chave/ramo]).
    Inicialização: regime permanente fasorial com a topologia em t = 0 (chaves com tf ≤ 0 fechadas), como o ATP faz com
    fontes de Tstart < 0."""
    dt, w = rede.dt, 2 * math.pi * rede.f
    nos = {"": -1}
    fonte_no = {fv["no"]: fv for fv in rede.fontes_v}

    def idx(n):
        if n not in nos:
            nos[n] = len(nos) - 1
        return nos[n]

    elems: List[_Elem] = []
    for k, r in enumerate(rede.ramos):                    # RLC série → elementos com nós internos
        seq = [(t, v) for t, v in (("R", r["R"]), ("L", r["L"]), ("C", r["C"])) if v]
        if not seq:
            seq = [("R", 1e-9)]
        a = r["n1"]
        for j, (t, v) in enumerate(seq):
            b = r["n2"] if j == len(seq) - 1 else f"__{k}_{j}"
            elems.append(_Elem(idx(a), idx(b), t, v, nome=r["nome"] if j == 0 else ""))
            a = b
    for c in rede.chaves:
        elems.append(_Elem(idx(c["n1"]), idx(c["n2"]), "S", 0.0, nome=c["nome"], chave=c))
    N = len(nos) - 1
    conhecidos = sorted(nos[n] for n in fonte_no)
    desconh = [i for i in range(N) if i not in conhecidos]
    pos_u = {n: j for j, n in enumerate(desconh)}
    pos_k = {n: j for j, n in enumerate(conhecidos)}
    fonte_por_idx = {nos[n]: fv for n, fv in fonte_no.items()}

    # ---------- regime permanente inicial (fasores, referência cosseno: x(t) = Re{X e^{jωt}})
    def estado_chave(c, t):
        return c["tf"] <= t < c["ta"]

    Y = np.zeros((N, N), complex)
    Iinj = np.zeros(N, complex)
    for e in elems:
        if e.tipo == "R":
            y = 1 / e.x
        elif e.tipo == "L":
            y = 1 / (1j * w * e.x)
        elif e.tipo == "C":
            y = 1j * w * e.x
        else:
            y = 1 / R_CHAVE if estado_chave(e.chave, 0.0) else 0.0
        for p, q, s in ((e.a, e.a, 1), (e.b, e.b, 1), (e.a, e.b, -1), (e.b, e.a, -1)):
            if p >= 0 and q >= 0:
                Y[p, q] += s * y
    for fi in rede.fontes_i:
        if abs(fi.get("f", rede.f) - rede.f) < 1e-9:
            Iinj[idx(fi["no"])] += fi["amp"] * np.exp(1j * math.radians(fi["fase_graus"]))
    Vk = np.array([fonte_por_idx[n]["amp"] * np.exp(1j * math.radians(fonte_por_idx[n]["fase_graus"])) for n in conhecidos], complex)
    Yuu = Y[np.ix_(desconh, desconh)] + np.eye(len(desconh)) * 1e-12
    Yuk = Y[np.ix_(desconh, conhecidos)]
    Vu = np.linalg.solve(Yuu, Iinj[desconh] - Yuk @ Vk)
    Vph = np.zeros(N, complex)
    Vph[desconh] = Vu
    Vph[conhecidos] = Vk

    def vph(i):
        return Vph[i] if i >= 0 else 0.0

    for e in elems:
        V = vph(e.a) - vph(e.b)
        if e.tipo == "R":
            I = V / e.x
        elif e.tipo == "L":
            I = V / (1j * w * e.x)
        elif e.tipo == "C":
            I = V * 1j * w * e.x
        else:
            I = V / R_CHAVE if estado_chave(e.chave, 0.0) else 0.0
        e.v, e.i = float(np.real(V)), float(np.real(I))

    # ---------- marcha no tempo
    def G_de(e, t):
        if e.tipo == "R":
            return 1 / e.x
        if e.tipo == "L":
            return dt / (2 * e.x)
        if e.tipo == "C":
            return 2 * e.x / dt
        return (1 / R_CHAVE) if e.chave["_fechada"] else 0.0

    for e in elems:
        if e.tipo == "S":
            e.chave["_fechada"] = estado_chave(e.chave, 0.0)
            e.chave["_abriu"] = False

    def montar():
        G = np.zeros((N, N))
        for e in elems:
            e.G = G_de(e, 0)
            for p, q, s in ((e.a, e.a, 1), (e.b, e.b, 1), (e.a, e.b, -1), (e.b, e.a, -1)):
                if p >= 0 and q >= 0:
                    G[p, q] += s * e.G
        Guu = G[np.ix_(desconh, desconh)] + np.eye(len(desconh)) * 1e-12
        import scipy.linalg as sl
        return sl.lu_factor(Guu), G[np.ix_(desconh, conhecidos)]

    lu, Guk = montar()
    import scipy.linalg as sl
    n_passos = int(round(rede.tmax / dt))
    gravar = gravar or rede.saida_nos
    gidx = [nos[n] for n in gravar if n in nos]
    nomes_i = [e.nome for e in elems if e.nome and (e.tipo == "S" or any(r["saida"] and r["nome"] == e.nome for r in rede.ramos))]
    T = np.arange(n_passos + 1) * dt
    VV = np.zeros((n_passos + 1, len(gidx)))
    II = {nm: np.zeros(n_passos + 1) for nm in nomes_i}
    ei = {e.nome: e for e in elems if e.nome in II}
    v_all = np.zeros(N)
    v_all[desconh] = np.real(Vu)
    v_all[conhecidos] = np.real(Vk)
    VV[0] = [v_all[i] for i in gidx]
    for nm, e in ei.items():
        II[nm][0] = e.i
    for e in elems:                                       # histórico em t = 0
        if e.tipo == "L":
            e.ih = e.i + (dt / (2 * e.x)) * e.v
        elif e.tipo == "C":
            e.ih = -e.i - (2 * e.x / dt) * e.v
    for n in range(1, n_passos + 1):
        t = n * dt
        mudou = False
        for e in elems:
            if e.tipo != "S":
                continue
            c = e.chave
            if not c["_fechada"] and not c["_abriu"] and t >= c["tf"] - 1e-12 and t < c["ta"]:
                c["_fechada"], mudou = True, True
            elif c["_fechada"] and t >= c["ta"] - 1e-12 and c.get("_ipassado") is not None and (e.i == 0 or e.i * c["_ipassado"] <= 0):
                c["_fechada"], c["_abriu"], mudou = False, True, True
        if mudou:
            lu, Guk = montar()
        rhs = np.zeros(N)
        for e in elems:
            if e.tipo in ("L", "C"):
                if e.a >= 0:
                    rhs[e.a] -= e.ih
                if e.b >= 0:
                    rhs[e.b] += e.ih
        for fi in rede.fontes_i:
            rhs[idx(fi["no"])] += fi["amp"] * math.cos(2 * math.pi * fi.get("f", rede.f) * t + math.radians(fi["fase_graus"]))
        vk = np.array([fonte_por_idx[i]["amp"] * math.cos(w * t + math.radians(fonte_por_idx[i]["fase_graus"])) for i in conhecidos])
        vu = sl.lu_solve(lu, rhs[desconh] - Guk @ vk)
        v_all[desconh] = vu
        v_all[conhecidos] = vk
        for e in elems:
            va = v_all[e.a] if e.a >= 0 else 0.0
            vb = v_all[e.b] if e.b >= 0 else 0.0
            v = va - vb
            if e.tipo == "S":
                e.chave["_ipassado"] = e.i
            if e.tipo in ("L", "C"):
                e.i = e.G * v + e.ih
                e.ih = (e.i + e.G * v) if e.tipo == "L" else (-e.i - e.G * v)
            else:
                e.i = e.G * v
            e.v = v
        VV[n] = [v_all[i] for i in gidx]
        for nm, e in ei.items():
            II[nm][n] = e.i
    return dict(t=T, V={gravar[j]: VV[:, j] for j in range(len(gidx))}, I=II)


# ------------------------------------------------------------------------------------------------- montagem da rede
def _xr_trafo(kva):
    return 4.0 if kva <= 300 else 5.0 if kva <= 750 else 6.0 if kva <= 1500 else 8.0


def parametros(ped, res):
    """Parâmetros elétricos da rede e dos estágios (valores por fase, Ω/H/F) a partir do dimensionamento do banco."""
    from . import banco as B
    V, f = ped.tensao_v, ped.freq_hz
    w = 2 * math.pi * f
    Zb = V ** 2 / (ped.trafo_kva * 1e3)
    Xt = ped.trafo_z_pct / 100 * Zb
    Xs = V ** 2 / (ped.scc_rede_mva * 1e6)
    Rt = Xt / _xr_trafo(ped.trafo_kva)
    Rs = Xs / 10
    est = []
    for i, e in enumerate(res["estagios"]):
        pr = B.protecao_estagio(ped, e)
        L = e["L_uH"] * 1e-6
        R = e.get("R_ohm") or w * L / (e.get("fq") or ped.fq_())
        Cd = e["C_delta_uF"] * 1e-6
        Ucap = e["U_cap_nom"]
        In_cap = e["Q_cap_nom_kvar"] * 1e3 / (math.sqrt(3) * Ucap)
        # resistor de descarga dimensionado para 75 V em 180 s (IEC 60831-1) a partir de √2·Ucap: R = t / (C ln(√2U/75))
        Rdesc = 180.0 / (Cd * math.log(math.sqrt(2) * Ucap / V_DESCARGA)) * 0.8
        espec = pr["contator"]
        especial = "capacitor" in (pr.get("contator_tipo") or "") and not pr.get("contator_pico")
        est.append(dict(i=i + 1, L=L, R=R, Cd=Cd, Rdesc=Rdesc, Ucap=Ucap, In_cap=In_cap, Isat=e["requisitos"].get("Isat") or 0,
                        In=e["requisitos"]["In"], I60=e["I60"], Q=e["Q_kvar"], fus=pr["fusivel_A"], cont=pr["contator"],
                        cont_In=pr["contator_In"], cont_k=K_CONT_ESPECIAL if especial else K_CONT_COMUM,
                        cont_pico=pr.get("contator_pico"), cont_tipo=pr.get("contator_tipo"),
                        I_cap_rms=e.get("I_cap_rms"), codigo=e.get("codigo")))
    return dict(V=V, f=f, Vfase_pk=V * math.sqrt(2 / 3), Rs=Rs + Rt, Ls=(Xs + Xt) / w, estagios=est,
                harm=dict(ped.harm_carga_a or {}))


def montar_rede(par, fechados, manobras, dt=2e-6, tmax=0.1, harmonicas=False):
    """fechados: estágios ligados desde t<0; manobras: {estágio: dict(tf=…, ta=…, polos=(tA,tB,tC) opcional, restrike=t)}."""
    rd = Rede(f=par["f"], dt=dt, tmax=tmax)
    fase = {"A": 0.0, "B": -120.0, "C": 120.0}
    for k in FASES:
        rd.fontes_v.append(dict(no=f"SRC{k}", amp=par["Vfase_pk"], fase_graus=fase[k], f=par["f"]))
        rd.ramo(f"SRC{k}", f"BUS{k}", R=par["Rs"], L=par["Ls"], nome=f"REDE{k}", saida=True)
    if harmonicas:
        I1 = sum(s["I60"] for s in par["estagios"])
        for h, a in sorted(par["harm"].items()):
            for k in FASES:
                rd.fontes_i.append(dict(no=f"BUS{k}", amp=a * math.sqrt(2), fase_graus=h * fase[k], f=h * par["f"]))
    for s in par["estagios"]:
        n = s["i"]
        K, Ln = f"K{n:02d}", f"L{n:02d}"
        man = manobras.get(n)
        for j, k in enumerate(FASES):
            if man:
                tf = man["polos"][j] if man.get("polos") else man["tf"]
                ta = man.get("ta", 1e3)
            elif n in fechados:
                tf, ta = -1.0, 1e3
            else:
                tf, ta = 1e3, 1e3 + 1
            rd.chave(f"BUS{k}", f"{K}{k}", tf, ta, nome=f"S{n:02d}{k}")
            if man and man.get("restrike"):
                rd.chave(f"BUS{k}", f"{K}{k}", man["restrike"], 1e3, nome=f"RS{n:02d}{k}")
            rd.ramo(f"{K}{k}", f"{Ln}{k}", R=s["R"], L=s["L"], nome=f"X{n:02d}{k}")
            rd.ramo(f"{K}{k}", "", R=R_TERRA)
            rd.ramo(f"{Ln}{k}", "", R=R_TERRA)
        for x, y in (("A", "B"), ("B", "C"), ("C", "A")):
            rd.ramo(f"{Ln}{x}", f"{Ln}{y}", C=s["Cd"], nome=f"C{n:02d}{x}{y}")
            rd.ramo(f"{Ln}{x}", f"{Ln}{y}", R=s["Rdesc"])
    rd.saida_nos = [f"BUS{k}" for k in FASES] + [f"{p}{s['i']:02d}{k}" for s in par["estagios"] for p in ("K", "L") for k in FASES]
    return rd


# ------------------------------------------------------------------------------------------------- métricas
def metricas(sim, par, estagio, t0, janela=0.04):
    """Grandezas do estágio manobrado a partir de t0 (instante da manobra)."""
    t = sim["t"]
    sel = t >= t0 - 1e-12
    n = estagio["i"]
    i_ph = [sim["I"][f"S{n:02d}{k}"][sel] for k in FASES]
    if f"RS{n:02d}A" in sim["I"]:
        i_ph = [a + sim["I"][f"RS{n:02d}{k}"][sel] for a, k in zip(i_ph, FASES)]
    ipk = max(float(np.max(np.abs(x))) for x in i_ph)
    dtt = t[1] - t[0]
    m10 = (t[sel] - t0) <= 0.010 + 1e-12
    i2t = max(float(np.sum(x[m10] ** 2) * dtt) for x in i_ph)
    L = f"L{n:02d}"
    vcap = [sim["V"][f"{L}{x}"][sel] - sim["V"][f"{L}{y}"][sel] for x, y in (("A", "B"), ("B", "C"), ("C", "A"))]
    vcap_pk = max(float(np.max(np.abs(v))) for v in vcap)
    vbus_pk = max(float(np.max(np.abs(sim["V"][f"BUS{k}"][sel]))) for k in FASES) / par["Vfase_pk"]
    K = f"K{n:02d}"
    # v1.20.1: capacitor BT trifásico em Δ, sem referência de terra – a tensão entre contatos é medida ENTRE FASES:
    # (tensão da barra no par x-y) − (tensão do lado do capacitor no mesmo par) = soma das tensões nos 2 polos do par
    # (no pior caso: rede em oposição à carga presa no capacitor, até 2·√2·V_LL). Fase-terra do lado do Δ aberto não é
    # definida pelo circuito (dava 850 × 1278 V entre plataforma e ATP) e não é grandeza de projeto a 60 Hz.
    sel_a = t >= t0 + 0.5e-3
    trv = max(float(np.max(np.abs((sim["V"][f"BUS{x}"][sel_a] - sim["V"][f"BUS{y}"][sel_a])
                                  - (sim["V"][f"{K}{x}"][sel_a] - sim["V"][f"{K}{y}"][sel_a]))))
              for x, y in (("A", "B"), ("B", "C"), ("C", "A")))
    # frequência do inrush pelo intervalo entre os 2 primeiros picos da fase com maior pico
    x = i_ph[int(np.argmax([np.max(np.abs(y)) for y in i_ph]))]
    zc = np.nonzero(np.diff(np.sign(x - np.mean(x[-int(1 / par['f'] / dtt):]))))[0]
    f_ir = float(1 / (2 * np.median(np.diff(zc[:6])) * dtt)) if len(zc) > 3 else float("nan")
    vres = max(float(abs(v[-1])) for v in vcap)
    return dict(ipk=ipk, i2t=i2t, vcap_pk=vcap_pk, vbus_pu=vbus_pk, trv=trv, f_inrush=f_ir, vcap_final=vres)


def avaliar(m, s, par, caso):
    """Critérios por componente → lista de (componente, grandeza, valor, limite, ok, nível).
    nível: "crit" (reprova o projeto), "aviso" (atenção/conferir), "info" (caso proibido mostrado de propósito)."""
    out = []
    info = caso == "R1"                                   # religamento sem descarga: caso proibido – mostra a necessidade do bloqueio
    if caso == "D2":                                      # reacendimento: raro em contatora BT; mostra o risco (contatora sem reacendimento)
        def add(comp, gr, val, lim, ok, nivel="crit", u=None):
            out.append((comp, gr, val, lim, bool(ok), "aviso", u))

    if caso != "D2":
        def add(comp, gr, val, lim, ok, nivel="crit", u=None):
            out.append((comp, gr, val, lim, bool(ok), "info" if info else nivel, u))

    if s.get("cont_pico"):                                # pico máximo do catálogo (ex.: ABB A/AF – tabela de manobra de capacitor)
        add("Contatora", f"Pico de fechamento ({s['cont'].split('(')[0].strip()} – {s.get('cont_tipo')})", f"{m['ipk']:.0f} A",
            f"≤ {s['cont_pico']:.0f} A (catálogo)", m["ipk"] <= s["cont_pico"], u=CK.utilizacao(m["ipk"], s["cont_pico"]))
    else:
        add("Contatora", f"Pico de fechamento ({s['cont'].split('(')[0].strip()})", f"{m['ipk']:.0f} A ({m['ipk'] / s['cont_In']:.1f}·Ie)",
            f"≤ {s['cont_k']}·Ie = {s['cont_k'] * s['cont_In']:.0f} A", m["ipk"] <= s["cont_k"] * s["cont_In"],
            u=CK.utilizacao(m["ipk"], s["cont_k"] * s["cont_In"]))
    i2f = I2T_FUSAO_GG.get(s["fus"]) or min((v for k, v in I2T_FUSAO_GG.items() if k >= s["fus"]), default=1e9)
    add("Fusível", f"I²t nos 10 ms (gG {s['fus']} A)", f"{m['i2t']:.0f} A²s", f"≤ 50 % do I²t de fusão ({0.5 * i2f:.0f} A²s)",
        m["i2t"] <= 0.5 * i2f, u=CK.utilizacao(m["i2t"], 0.5 * i2f))
    lim_mag = K_DISJ_MAG * s["fus"] * math.sqrt(2)
    add("Disjuntor (se usado no lugar do fusível)", f"Pico × disparo magnético curva C {s['fus']} A", f"{m['ipk']:.0f} A",
        f"< {lim_mag:.0f} A (10·In·√2)", m["ipk"] < lim_mag, "aviso", u=CK.utilizacao(m["ipk"], lim_mag))
    add("Capacitor", "Tensão de pico (IEC 60831-1: 2√2·Un)", f"{m['vcap_pk']:.0f} V", f"≤ {2 * math.sqrt(2) * s['Ucap']:.0f} V",
        m["vcap_pk"] <= 2 * math.sqrt(2) * s["Ucap"], u=CK.utilizacao(m["vcap_pk"], 2 * math.sqrt(2) * s["Ucap"]))
    add("Capacitor", "Corrente de pico (IEC 60831-1: 100·In)", f"{m['ipk']:.0f} A", f"≤ {100 * s['In_cap']:.0f} A",
        m["ipk"] <= 100 * s["In_cap"], u=CK.utilizacao(m["ipk"], 100 * s["In_cap"]))
    if s["Isat"]:
        # o reator é especificado linear até Isat para as harmônicas em regime (IEC 60076-6); no inrush o fluxo tem componente
        # contínua que decai em poucos ciclos – passar de Isat aqui é ATENÇÃO (pede reator com Isat maior ou entreferro maior)
        add("Reator", "Pico de corrente × linearidade (Isat)", f"{m['ipk']:.0f} A", f"≤ Isat {s['Isat']:.0f} A", m["ipk"] <= s["Isat"], "aviso",
            u=CK.utilizacao(m["ipk"], s["Isat"]))
    add("Barra", "Sobretensão de manobra (inversores podem desarmar)", f"{m['vbus_pu']:.2f} pu", f"≤ {V_BARRA_INV:.2f} pu",
        m["vbus_pu"] <= V_BARRA_INV, "aviso", u=CK.utilizacao(m["vbus_pu"], V_BARRA_INV))
    add("Barra", "Sobretensão de manobra (equipamentos BT)", f"{m['vbus_pu']:.2f} pu", f"≤ {V_BARRA_MAX:.2f} pu",
        m["vbus_pu"] <= V_BARRA_MAX, u=CK.utilizacao(m["vbus_pu"], V_BARRA_MAX))
    if caso.startswith("D"):
        # par de polos em série: rede em oposição à carga presa no Δ (a abertura polo a polo pode deixar a carga presa acima do
        # pico da tensão de linha). Limite conservador: metade da tensão suportável de impulso dos contatos abertos
        # (Uimp 6 kV – IEC 60947-4-1, contatoras BT usuais) para o par de polos.
        add("Contatora", "Tensão entre contatos após abrir (par de polos, entre fases)", f"{m['trv']:.0f} V "
            f"(carga presa no capacitor {m['vcap_final']:.0f} V)", "≤ 3000 V (Uimp 6 kV ÷ 2 – IEC 60947-4-1)", m["trv"] <= 3000,
            u=CK.utilizacao(m["trv"], 3000))
    return out


def check_criterio(x):
    """(componente, grandeza, valor, limite, ok, nível, utilização) → APROVADO/ATENÇÃO/REPROVADO/INFO."""
    u = x[6] if len(x) > 6 else None
    return CK.check(x[4], u, x[5])


def check_caso(c):
    return CK.pior([check_criterio(x) for x in c["criterios"]])


def recomendar_contatora(casos, par):
    """Contatora comum (AC-3/AC-1) × especial AC-6b: Schneider (FAQ FA408331) – com reator de dessintonia não precisa de
    contatora para capacitor; ABB (1SBC101140C0203) – contatores comuns com indutância antirressonância (~7 %),
    dimensionados pela corrente AC-1 × 1,15, pico < 30·In do capacitor."""
    s = par["estagios"][0]
    pior = max((c["metricas"].get("ipk", 0) for c in casos if c["codigo"] in ("E1", "E2", "E3", "E4", "D2")), default=0)
    s1 = next((c for c in casos if c["codigo"] == "S1"), None)
    irms = s1["metricas"]["i_rms"] if s1 else (s.get("I_cap_rms") or s["I60"])
    ie_ac1 = 1.15 * max(irms, s["I60"])
    lim = min(s["cont_pico"], 30 * s["In_cap"]) if s.get("cont_pico") else 30 * s["In_cap"]
    ok_pico = pior <= lim
    nome = s["cont"].split("(")[0].strip()
    return dict(comum_serve=bool(ok_pico), pico_pior_A=round(pior, 1), lim_pico_A=round(lim, 1),
                ie_ac1_min_A=round(ie_ac1, 1),
                texto=(f"Contatora COMUM (AC-3/AC-1) serve: pior pico de manobra {pior:.0f} A ≤ {lim:.0f} A "
                       f"({'catálogo ' + nome + ' e ' if s.get('cont_pico') else ''}30·In do capacitor) – "
                       f"escolher pela corrente AC-1 ≥ {ie_ac1:.0f} A (1,15 × {max(irms, s['I60']):.0f} A RMS com harmônicas). "
                       "Base: Schneider FAQ FA408331 e ABB 1SBC101140C0203 (reator em série limita o inrush)."
                       if ok_pico else
                       f"Usar contatora ESPECIAL para capacitor (AC-6b com resistores de pré-carga): pior pico {pior:.0f} A > 30·In "
                       f"({30 * s['In_cap']:.0f} A)."))


# ------------------------------------------------------------------------------------------------- casos
def _t_pico(par, ang_graus, ciclo=1):
    """Instante (s) em que a fase A da FONTE está no ângulo dado (cosseno: 0° = pico positivo)."""
    T = 1 / par["f"]
    return ciclo * T + (ang_graus % 360) / 360 * T


def estudo(ped, res, dt=2e-6, log=print, varredura=24):
    """Roda todos os casos no Python. Devolve dict(casos=[…], max_simultaneos, parametros)."""
    par = parametros(ped, res)
    n = len(par["estagios"])
    T = 1 / par["f"]
    casos = []

    def roda(cod, nome, fechados, manobras, s_alvo, t0, tmax=None, harm=False):
        rd = montar_rede(par, fechados, manobras, dt=dt, tmax=tmax or (t0 + 4 * T), harmonicas=harm)
        sim = simular(rd)
        m = metricas(sim, par, s_alvo, t0)
        return dict(codigo=cod, nome=nome, fechados=sorted(fechados), manobras=manobras, estagio=s_alvo["i"], t0=t0,
                    tmax=rd.tmax, metricas=m, criterios=avaliar(m, s_alvo, par, cod), sim=sim, rede=rd)

    s1, sn = par["estagios"][0], par["estagios"][-1]
    # E1 – varredura do ângulo de fechamento (rápida: dt maior), depois o pior ângulo no passo fino
    log("   Transitórios E1: varredura do ângulo de fechamento...")
    piores = []
    for a in np.linspace(0, 360, varredura, endpoint=False):
        t0 = _t_pico(par, a)
        rd = montar_rede(par, set(), {1: dict(tf=t0)}, dt=dt * 5, tmax=t0 + 0.6 * T)
        m = metricas(simular(rd), par, s1, t0)
        piores.append((m["ipk"], a))
    a_pior = max(piores)[1]
    t0 = _t_pico(par, a_pior)
    casos.append(roda("E1", f"Energização do 1º estágio no pior ângulo ({a_pior:.0f}° da fase A)", set(), {1: dict(tf=t0)}, s1, t0))
    if n > 1:
        log("   Transitórios E2: back-to-back (último estágio com os demais ligados)...")
        fe = set(range(1, n))
        piores = []
        for a in np.linspace(0, 360, varredura, endpoint=False):
            t0 = _t_pico(par, a)
            rd = montar_rede(par, fe, {n: dict(tf=t0)}, dt=dt * 5, tmax=t0 + 0.6 * T)
            piores.append((metricas(simular(rd), par, sn, t0)["ipk"], a))
        a2 = max(piores)[1]
        t0 = _t_pico(par, a2)
        casos.append(roda("E2", f"Back-to-back: estágio {n} com {n - 1} ligado(s) ({a2:.0f}°)", fe, {n: dict(tf=t0)}, sn, t0))
    # E3 – quantos estágios juntos (no pior ângulo de E1)
    log("   Transitórios E3: estágios ligando juntos...")
    t0 = _t_pico(par, a_pior)
    max_ok, e3 = 0, None
    for k in range(1, n + 1):
        c = roda("E3", f"{k} estágio(s) ligando ao mesmo tempo", set(), {j: dict(tf=t0) for j in range(1, k + 1)}, s1, t0)
        if all(x[4] for x in c["criterios"] if x[5] == "crit"):
            max_ok, e3 = k, c
        else:
            if e3 is None:
                e3 = c
            break
    if e3:
        e3["nome"] = f"{max_ok} estágio(s) ligando ao mesmo tempo (máximo que passa em todos os critérios)" if max_ok else e3["nome"]
        casos.append(e3)
    # E4 – dispersão dos polos
    t0 = _t_pico(par, a_pior)
    casos.append(roda("E4", "Dispersão dos polos da contatora (0 / 1,5 / 3 ms)", set(),
                      {1: dict(tf=t0, polos=(t0, t0 + 1.5e-3, t0 + 3e-3))}, s1, t0))
    # D1 – desenergização (abre no zero de corrente após ta)
    ta = 1.25 * T
    log("   Transitórios D1/D2/R1: desenergização, reacendimento e religamento...")
    casos.append(roda("D1", "Desenergização do estágio 1 (TRV na contatora, carga residual)", {1}, {1: dict(tf=-1.0, ta=ta)}, s1, ta,
                      tmax=ta + 4 * T))
    # D2 – reacendimento meio ciclo depois
    casos.append(roda("D2", "Reacendimento (restrike) meio ciclo após a abertura", {1}, {1: dict(tf=-1.0, ta=ta, restrike=ta + 0.5 * T + 0.2e-3)},
                      s1, ta, tmax=ta + 4 * T))
    # R1 – religamento com capacitor carregado (abre e religa 1,5 ciclo depois, em oposição)
    casos.append(roda("R1", "Religamento rápido com o capacitor carregado (sem esperar a descarga)", set(),
                      {1: dict(tf=-1.0, ta=ta, restrike=ta + 1.5 * T + 0.2e-3)}, s1, ta, tmax=ta + 5 * T))
    casos[-1]["fechados"] = [1]
    # S1 – regime com harmônicas (todos ligados)
    if par["harm"]:
        log("   Transitórios S1: regime permanente com as harmônicas da carga...")
        rd = montar_rede(par, set(range(1, n + 1)), {}, dt=dt, tmax=10 * T, harmonicas=True)
        sim = simular(rd)
        t = sim["t"]
        sel = t >= t[-1] - 2 * T
        x = sim["I"]["S01A"][sel]
        Lx = "L01"
        vab = sim["V"][f"{Lx}A"][sel] - sim["V"][f"{Lx}B"][sel]
        icap = float(np.sqrt(np.mean(x ** 2)))
        casos.append(dict(codigo="S1", nome="Regime permanente com as harmônicas da carga (todos os estágios ligados)", estagio=1,
                          fechados=list(range(1, n + 1)), manobras={}, t0=0.0, tmax=rd.tmax, sim=sim, rede=rd,
                          metricas=dict(i_rms=icap, vcap_rms=float(np.sqrt(np.mean(vab ** 2))), vcap_pk=float(np.max(np.abs(vab)))),
                          criterios=[("Reator", "Corrente RMS do estágio 1 (tempo) × corrente de projeto do reator", f"{icap:.1f} A",
                                      f"≤ {s1['In']:.1f} A (In do reator)", icap <= s1["In"] * 1.02, "crit"),
                                     ("Capacitor", "Corrente RMS (tempo) × cálculo em frequência da plataforma", f"{icap:.1f} A",
                                      f"plataforma {s1['I_cap_rms']:.1f} A (±5 %)" if s1.get("I_cap_rms") else "–",
                                      (abs(icap - s1["I_cap_rms"]) <= 0.05 * s1["I_cap_rms"]) if s1.get("I_cap_rms") else True, "aviso"),
                                     ("Capacitor", "Tensão de pico no capacitor em regime", f"{float(np.max(np.abs(vab))):.0f} V",
                                      f"≤ {math.sqrt(2) * 1.1 * s1['Ucap']:.0f} V (1,1·Un pico)",
                                      float(np.max(np.abs(vab))) <= math.sqrt(2) * 1.1 * s1["Ucap"], "crit")]))
    # tempo de descarga
    s = s1
    tau = s["Rdesc"] * s["Cd"]                            # cada lado do Δ tem o seu resistor: τ = R·C
    t75 = tau * math.log(math.sqrt(2) * s["Ucap"] / V_DESCARGA)
    t10 = tau * math.log(math.sqrt(2) / 0.1)              # até 10 % de Un (critério usual de religamento seguro)
    return dict(casos=casos, max_simultaneos=max_ok, parametros=par, t_descarga_s=t75, t_religar_s=t10,
                contatora=recomendar_contatora(casos, par))


# ------------------------------------------------------------------------------------------------- ATP
def deck_atp(rede: Rede, titulo):
    """Deck .atp da MESMA rede (ramos RLC série, chaves de tempo, fontes tipo 14 com Tstart = −1 → regime inicial)."""
    from .atp import _f, _no, _ramo, _fonte
    import unicodedata
    asc = lambda t: unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode()
    L = []
    a = L.append
    a("BEGIN NEW DATA CASE")
    a(asc(f"C {titulo} - Plataforma FSEN (transitorios, dupla checagem Python x ATP)")[:80])
    a("C  dT  >< Tmax >< Xopt >< Copt ><Epsiln>")
    a(_f(rede.dt, 8) + _f(rede.tmax, 8) + _f(0, 8) + _f(0, 8))
    a(f"{999999:8d}{1:8d}{0:8d}{0:8d}{1:8d}{0:8d}{0:8d}{1:8d}{0:8d}")
    a("$VINTAGE,1")
    for r in rede.ramos:
        a(_ramo(r["n1"], r["n2"], R=r["R"], L=r["L"], C=r["C"], saida=1 if r["saida"] else 0))
    a("$VINTAGE,0")
    a("BLANK BRANCH")
    for c in rede.chaves:
        a(("  " + _no(c["n1"]) + _no(c["n2"]) + _f(c["tf"], 10) + _f(c["ta"], 10) + _f(0.0, 10)).ljust(79) + "1")
    a("BLANK SWITCH")
    for fv in rede.fontes_v:
        a(_fonte(14, fv["no"], fv["amp"], fv["f"], fv["fase_graus"], t_ini=-1.0, t_fim=100.0))
    for fi in rede.fontes_i:
        a(_fonte(14, fi["no"], fi["amp"], fi["f"], fi["fase_graus"], corrente=True, t_ini=-1.0, t_fim=100.0))
    a("BLANK SOURCE")
    nos = rede.saida_nos
    for j in range(0, len(nos), 13):
        a("  " + "".join(_no(x) for x in nos[j:j + 13]))
    a("BLANK OUTPUT")
    a("BLANK PLOT")
    a("BEGIN NEW DATA CASE")
    a("BLANK")
    return "\n".join(L) + "\n"


def sim_de_pl4(pl4, rede):
    """Converte o .pl4 do ATP no mesmo formato do simular() (V[nó], I[nome da chave])."""
    D = pl4["dados"]
    V = {n: D[f"V:{n}"] for n in rede.saida_nos if f"V:{n}" in D}
    I = {}
    for c in rede.chaves:
        k = f"I:{c['n1']}-{c['n2']}"
        cand = [x for x in D if x.replace("'", "") == k]
        j = sum(1 for cc in rede.chaves[:rede.chaves.index(c)] if cc["n1"] == c["n1"] and cc["n2"] == c["n2"])
        if len(cand) > j:
            I[c["nome"]] = D[cand[j]]
    return dict(t=pl4["t"], V=V, I=I)


# Regra Electric (22/11/2026): o ATP é a referência de transitórios dos 3 filtros – a plataforma e o ATP, com os MESMOS dados,
# têm que bater; só então o estudo está APROVADO. Mesmo método numérico e mesmo passo → tolerância de 1 %.
TOL_ATP = 1.0
GRANDEZAS = [("ipk", "Pico de corrente no estágio", "A", TOL_ATP), ("i2t", "I²t nos 10 ms", "A²s", TOL_ATP),
             ("vcap_pk", "Pico de tensão no capacitor", "V", TOL_ATP), ("vbus_pu", "Pico de tensão na barra", "pu", TOL_ATP),
             ("trv", "Tensão entre contatos (entre fases)", "V", TOL_ATP)]


def dupla_checagem(est, pasta, log=print):
    """Gera um .atp por caso; se o ATP estiver instalado, roda e compara com o Python (±5 % nos picos)."""
    from . import atp as A
    os.makedirs(pasta, exist_ok=True)
    tp = A.achar_tpbig()
    out = []
    for c in est["casos"]:
        arq = os.path.join(pasta, f"trans_{c['codigo'].lower()}.atp")
        with open(arq, "w", encoding="ascii", errors="ignore") as fh:
            fh.write(deck_atp(c["rede"], f"{c['codigo']} {c['nome']}"))
        linha = dict(caso=c["codigo"], deck=arq, rodou=False, comparacao=[])
        if tp and c["codigo"] != "S1":
            r = A.rodar_atp(arq, tp, timeout=900)
            if r["ok"]:
                try:
                    s_atp = sim_de_pl4(A.ler_pl4(r["pl4"]), c["rede"])
                    s_alvo = next(s for s in est["parametros"]["estagios"] if s["i"] == c["estagio"])
                    ma = metricas(s_atp, est["parametros"], s_alvo, c["t0"])
                    for k, nome, un, tol in GRANDEZAS:
                        if k == "trv" and not c["codigo"].startswith(("D", "R")):
                            continue                      # tensão entre contatos só nas aberturas
                        a_, b_ = c["metricas"].get(k), ma.get(k)
                        if a_ is None or b_ is None or not a_:
                            continue
                        dif = 100 * (b_ - a_) / a_
                        linha["comparacao"].append(dict(grandeza=nome, unidade=un, python=round(a_, 3), atp=round(b_, 3),
                                                        dif_pct=round(dif, 2), tolerancia_pct=tol, convergiu=abs(dif) <= tol))
                    linha["rodou"] = True
                except Exception as ex:
                    linha["erro"] = f"{type(ex).__name__}: {ex}"
            else:
                linha["erro"] = r["msg"][-300:]
        out.append(linha)
    if not tp:
        log("   Transitórios: ATP não encontrado neste computador – decks .atp gerados para rodar depois.")
    return dict(atp=bool(tp), casos=out)


# ------------------------------------------------------------------------------------------------- saídas do projeto
def figuras(est, pasta, cod):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    os.makedirs(pasta, exist_ok=True)
    arqs = []
    par = est["parametros"]
    for c in est["casos"]:
        sim, n = c["sim"], c["estagio"]
        t = sim["t"]
        t0 = c["t0"]
        sel = (t >= max(0, t0 - 1 / par["f"])) & (t <= t0 + 3 / par["f"])
        fig, ax = plt.subplots(3, 1, figsize=(10, 8), sharex=True)
        for k in FASES:
            i = sim["I"][f"S{n:02d}{k}"] + (sim["I"].get(f"RS{n:02d}{k}", 0))
            ax[0].plot((t[sel] - t0) * 1e3, i[sel], lw=0.9, label=f"fase {k}")
        ax[0].set_ylabel(f"Corrente estágio {n} (A)")
        for x, y in (("A", "B"), ("B", "C"), ("C", "A")):
            v = sim["V"][f"L{n:02d}{x}"] - sim["V"][f"L{n:02d}{y}"]
            ax[1].plot((t[sel] - t0) * 1e3, v[sel], lw=0.9, label=f"{x}{y}")
        ax[1].set_ylabel("Tensão no capacitor (V)")
        for k in FASES:
            ax[2].plot((t[sel] - t0) * 1e3, sim["V"][f"BUS{k}"][sel] / par["Vfase_pk"], lw=0.9, label=k)
        ax[2].set_ylabel("Tensão na barra (pu)")
        ax[2].set_xlabel("tempo após a manobra (ms)")
        for a in ax:
            a.grid(alpha=0.3)
            a.legend(fontsize=7, loc="upper right")
        fig.suptitle(f"{cod} – {c['codigo']}: {c['nome']}", fontsize=10)
        _st = check_caso(c)
        _ruins = [x for x in c["criterios"] if check_criterio(x) in (CK.REPROVADO, CK.ATENCAO)]
        CK.selo(ax[0], _st, "; ".join(f"{x[0]} {x[6]:.0f} %" if x[6] is not None else x[0] for x in _ruins)[:70])
        fig.tight_layout()
        arq = os.path.join(pasta, f"Transitorio_{c['codigo']}_{cod}.png")
        fig.savefig(arq, dpi=110)
        plt.close(fig)
        c["figura"] = arq
        arqs.append(arq)
    return arqs


def resumo_md(est, chk=None):
    L = ["## Transitórios eletromagnéticos e regime (simulação no tempo – mesmo método do ATP)", ""]
    L.append(f"- Estágios que podem ligar **ao mesmo tempo**: **{est['max_simultaneos']}**")
    L.append(f"- Descarga do capacitor: {est['t_descarga_s']:.0f} s até 75 V (IEC 60831-1: ≤ 180 s); "
             f"**bloqueio de religamento no controlador ≥ {math.ceil(est['t_religar_s'] / 10) * 10:.0f} s** (até 10 % de Un)")
    L.append(f"- {est['contatora']['texto']}")
    L += ["", "| Caso | Descrição | Pico I (A) | I²t 10 ms (A²s) | Pico V cap (V) | Barra (pu) | Check | Observação |",
          "|---|---|---|---|---|---|---|---|"]
    for c in est["casos"]:
        m = c["metricas"]
        st = check_caso(c)
        ruins = [x for x in c["criterios"] if check_criterio(x) in (CK.REPROVADO, CK.ATENCAO)]
        if st == CK.INFO:
            obs = "caso proibido mostrado de propósito – exige bloqueio de religamento no controlador"
        else:
            obs = "; ".join(f"{x[0]}: {x[2]} ({x[3]}){'' if x[6] is None else f' – {x[6]:.0f} %'}" for x in ruins) or "dentro de todos os critérios"
        L.append(f"| {c['codigo']} | {c['nome']} | {m.get('ipk', m.get('i_rms', 0)):.0f} | {m.get('i2t', 0):.0f} | "
                 f"{m.get('vcap_pk', 0):.0f} | {m.get('vbus_pu', 0):.2f} | {CK.texto(st)} | {obs} |")
    L += ["", "Check: APROVADO (utilização < 90 % do limite), ATENÇÃO (90–100 % ou critério de aviso violado), "
          "REPROVADO (passa do limite obrigatório), INFO (caso mostrado de propósito)."]
    L.append("")
    L.append("**Status do estudo de transitórios: " + status(est, chk) + "**")
    return "\n".join(L) + "\n"


def status(est, chk):
    """APROVADO só quando o ATP (referência) rodou todos os casos de manobra e bateu com a plataforma (±1 %) e nenhum
    critério crítico falhou."""
    crit = [(c["codigo"], x) for c in est["casos"] for x in c["criterios"] if not x[4] and x[5] == "crit"]
    if not chk or not chk.get("atp"):
        base = "PENDENTE – falta a confirmação no ATP (referência): rodar neste projeto num computador com o ATP"
    else:
        casos = [x for x in chk["casos"] if x["caso"] != "S1"]
        nao_rodou = [x["caso"] for x in casos if not x["rodou"]]
        div = [f"{x['caso']}: {y['grandeza']} {y['dif_pct']:+.2f} %" for x in casos for y in x["comparacao"] if not y["convergiu"]]
        if nao_rodou:
            base = "PENDENTE – ATP não rodou o(s) caso(s) " + ", ".join(nao_rodou)
        elif div:
            base = "REPROVADO na dupla checagem – plataforma e ATP não bateram: " + "; ".join(div)
        else:
            tot = sum(len(x["comparacao"]) for x in casos)
            base = f"Plataforma = ATP em {tot}/{tot} grandezas (±{TOL_ATP:g} %)"
    if crit:
        return "REPROVADO – " + "; ".join(f"{c}: {x[0]} – {x[1]} {x[2]} ({x[3]})" for c, x in crit) + " | " + base
    return ("APROVADO – " + base) if base.startswith("Plataforma = ATP") else base


def planilha(est, chk, arq):
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Casos"
    ws.append(["Caso", "Descrição", "Componente", "Grandeza", "Valor", "Limite", "Utilização (%)", "Check", "Nível do critério"])
    for c in est["casos"]:
        for x in c["criterios"]:
            u = x[6] if len(x) > 6 else None
            ws.append([c["codigo"], c["nome"], x[0], x[1], x[2], x[3], None if u is None else round(u, 1), check_criterio(x),
                       {"crit": "obrigatório", "aviso": "aviso", "info": "informativo"}.get(x[5], x[5])])
    ws2 = wb.create_sheet("Python x ATP")
    ws2.append(["Caso", "Grandeza", "Unidade", "Python", "ATP", "Dif (%)", "Tolerância (%)", "Check"])
    for x in (chk or {}).get("casos", []):
        for y in x["comparacao"]:
            ws2.append([x["caso"], y["grandeza"], y["unidade"], y["python"], y["atp"], y["dif_pct"], y["tolerancia_pct"],
                        CK.APROVADO if y["convergiu"] else CK.REPROVADO])
        if not x["comparacao"]:
            ws2.append([x["caso"], x.get("erro") or ("ATP não rodado" if not x["rodou"] else ""), "", "", "", "", "", ""])
    ws3 = wb.create_sheet("Parâmetros")
    par = est["parametros"]
    ws3.append(["Rede: R (Ω)", par["Rs"]]); ws3.append(["Rede: L (H)", par["Ls"]])
    for s_ in par["estagios"]:
        ws3.append([f"Estágio {s_['i']}", f"L {s_['L'] * 1e6:.1f} µH", f"R {s_['R'] * 1e3:.2f} mΩ", f"C Δ {s_['Cd'] * 1e6:.1f} µF",
                    f"Rdesc {s_['Rdesc'] / 1e3:.0f} kΩ", f"fusível {s_['fus']} A", s_["cont"]])
    for w_ in (ws, ws2):
        CK.colorir_planilha(w_)
    wb.save(arq)
    return arq


def gerar(ped, res, pasta, cod, log=print, pasta_atp_trabalho=None):
    """Estudo completo + figuras + planilha + decks/dupla checagem ATP. Devolve dict(estudo, checagem, arquivos, resumo)."""
    os.makedirs(pasta, exist_ok=True)
    est = estudo(ped, res, dt=5e-6, varredura=12, log=log)
    figs = figuras(est, pasta, cod)
    trab = pasta_atp_trabalho
    from . import atp as A
    if A.achar_tpbig() and not trab:
        trab = os.path.join(A.PASTA_TRABALHO_PADRAO + "_transitorios", cod.replace(",", "_"))
    chk = dupla_checagem(est, trab or os.path.join(pasta, "ATP"), log=log)
    if trab:                                              # cópia dos decks (e .pl4) para a pasta do projeto
        import shutil
        dst = os.path.join(pasta, "ATP")
        os.makedirs(dst, exist_ok=True)
        for f_ in os.listdir(trab):
            if f_.endswith((".atp", ".pl4", ".lis")):
                shutil.copy(os.path.join(trab, f_), dst)
    xl = planilha(est, chk, os.path.join(pasta, f"Transitorios_{cod}.xlsx"))
    md = resumo_md(est, chk)
    est["status"] = status(est, chk)
    for c in est["casos"]:                                # libera memória (séries grandes) depois das figuras
        c.pop("sim", None)
    return dict(estudo=est, checagem=chk, arquivos=figs + [xl], resumo=md)
