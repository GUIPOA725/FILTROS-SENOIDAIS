"""Dupla checagem no ATP (ATP-EMTP): a plataforma gera o deck .atp da MESMA rede simulada no Python, roda o ATP
instalado no PC (tpbig.exe) em segundo plano, lê o .pl4 e compara as grandezas de projeto.

Rede no ATP (por fase, valores idênticos aos do Python):
  inversor 2 níveis (TACS: SVPWM, amostragem regular simétrica, mesma lei do Python) → fonte TACS tipo 60 ±Vcc/2
  → [medição] → L1 (R1 série) // Rp (perdas HF do núcleo) → nó do banco → C (Δ ou Y; Rd série; ramo RC opcional)
  → [L2 se LCL] → cabo (células π: R, L série; Cfase-terra e Cfase-fase) → motor: Rm + Lm (estrela isolada),
  f.c.e.m. por equivalente de Norton (fontes de corrente equilibradas, soma nula → não injeta modo comum),
  Cwf/3 de cada terminal à carcaça (terra).
A comparação usa o Python com R constante (sem efeito pelicular), pois o ATP com R-L concentrado não o representa.
"""
from __future__ import annotations
import os
import math
import struct
import shutil
import subprocess
import dataclasses
from typing import Dict, Any, List, Optional

import numpy as np

from .simulacao import ParamCircuito, PontoOperacao, simular, _fasores, _n_secoes

TPBIG_PADRAO = [r"C:\ATP\atpmingw\tpbig.exe", r"C:\ATP\tools\tpbig.exe", r"C:\ATPWin\tpbig.exe"]
PASTA_TRABALHO_PADRAO = r"C:\ATP\work\fsen"


# ----------------------------------------------------------------------------------------------- formatação
def _f(x, w):
    """Número em campo fixo de largura w (formato ATP) com o menor erro relativo possível (deixa 1 espaço livre)."""
    if x == 0:
        return "0.".rjust(w)
    wl = w - 1 if w > 8 else w
    cand = []
    for d in range(0, wl + 1):
        s = f"{x:.{d}f}"
        if "." not in s:
            s += "."
        cand.append(s)
        m, e = f"{x:.{d}E}".split("E")
        cand.append((m if "." in m else m + ".") + "E" + str(int(e)))
    ok = [c for c in cand if len(c) <= wl and float(c) != 0]
    best = min(ok, key=lambda c: (abs(float(c) - x) / abs(x), len(c)))
    return best.rjust(w)


def _no(s):
    s = s[:6]
    return s.ljust(6)


def _ramo(n1, n2, R=0.0, L=0.0, C=0.0, saida=0):
    """Ramo RLC série ($VINTAGE,1: R 27-42, L 43-58 [mH], C 59-74 [µF], saída col. 80)."""
    lin = "  " + _no(n1) + _no(n2) + " " * 12
    lin += (_f(R, 16) if R else " " * 16) + (_f(L * 1e3, 16) if L else " " * 16) + (_f(C * 1e6, 16) if C else " " * 16)
    return lin.ljust(79) + (str(saida) if saida else " ")


def _medidor(n1, n2, saida=1):
    return ("  " + _no(n1) + _no(n2)).ljust(54) + "MEASURING".ljust(25) + str(saida)


def _tacs98(nome, expr):
    lin = "98" + nome.ljust(6)[:6] + "  =" + expr
    if len(lin) > 80:
        raise ValueError(f"Expressão TACS longa demais: {lin}")
    return lin


def _fonte(tipo, no, amp, freq=0.0, fase_graus=0.0, corrente=False, t_ini=-1.0, t_fim=100.0):
    return (f"{tipo:2d}" + _no(no) + ("-1" if corrente else "  ") + _f(amp, 10) + _f(freq, 10) + _f(fase_graus, 10)
            + " " * 20 + _f(t_ini, 10) + _f(t_fim, 10))


# ----------------------------------------------------------------------------------------------- deck
def gerar_deck(p: ParamCircuito, op: PontoOperacao, ligacao: str, titulo: str = "FSEN", ciclos: int = 18,
               dt: Optional[float] = None, iplot: int = 32, n_dt: int = 2048) -> Dict[str, Any]:
    """Gera o texto do deck .atp. Retorna dict(texto, fs_ef, mf, tmax, dt, iplot, saidas)."""
    from .simulacao import op_efetivo
    m_nec = abs(_fasores(p, op)[0]) / (op.vdc / 2)
    op, _k = op_efetivo(p, op)                    # mesma correção de sobremodulação do Python
    vinv, i1f, vcf, imf, ef, vmf = _fasores(p, op)
    m = abs(vinv) / (op.vdc / 2)
    m_ef = min(m, 2 / math.sqrt(3))
    ang = float(np.angle(vinv))
    mf = max(3, int(round((op.fs / op.f1 - 3) / 6)) * 6 + 3)
    # n_dt = 2048 passos por período da portadora (validação 19/11/2026 nos 11 filtros reais): com 512 passos a
    # quantização das bordas do PWM no passo de tempo gerava harmônicas espúrias de baixa ordem que, perto da
    # ressonância do LC, davam THD falso no ATP (FN5040-24 a 30 Hz: 10,9 % com 512 → 2,41 % com 2048; Python 2,39 %).
    # passo de tempo = submúltiplo EXATO do período da portadora (evita jitter numérico das bordas, que gera
    # harmônicas espúrias e excita a ressonância natural pouco amortecida do LC). f1 e fs são ajustados ao dt
    # representável no cartão (diferença < 0,05 %).
    dt_f = float(_f(1 / (mf * op.f1 * n_dt), 8))
    fs_ef = 1 / (n_dt * dt_f)
    f1_t = fs_ef / mf
    Ts = 1 / fs_ef
    dt = dt_f
    tmax = ciclos / f1_t
    w1 = 2 * math.pi * f1_t
    rp = p.Q_hf * 2 * math.pi * p.fs_ref * p.L1
    L = []
    a = L.append
    a("BEGIN NEW DATA CASE")
    import unicodedata
    asc = lambda t: unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode()
    a(asc(f"C {titulo} - gerado pela Plataforma FSEN (dupla checagem Python x ATP)")[:80])
    from .versao import assinatura as _assin
    a(asc("C " + _assin(curta=True))[:80])
    a(asc(f"C f1 = {op.f1:g} Hz, fs = {fs_ef:.1f} Hz (mf = {mf}), m = {m:.4f}, Vcc = {op.vdc:.1f} V, ligacao {ligacao}")[:80])
    a("C  dT  >< Tmax >< Xopt >< Copt ><Epsiln>")
    a(_f(dt, 8) + _f(tmax, 8) + _f(0, 8) + _f(0, 8))
    a(f"{999999:8d}{iplot:8d}{0:8d}{0:8d}{1:8d}{0:8d}{0:8d}{1:8d}{0:8d}")
    # ---------------- TACS: SVPWM regular simétrica (idêntica ao Python)
    a("TACS HYBRID")
    fases = {"A": 0.0, "B": -2 * math.pi / 3, "C": 2 * math.pi / 3}
    num = lambda x, d=8: (f"{x:.{d}f}" if x >= 0 else f"({x:.{d}f})")
    a(_tacs98("FS", f"{fs_ef:.6f}"))
    a(_tacs98("TH", "TIMEX+" + f"{dt / 2:.4E}"))      # meio passo: evita empate numérico na borda da amostra
    a(_tacs98("TK", "TRUNC(TH*FS)"))
    a(_tacs98("TC", "(TK+0.5)/FS"))
    for k, d in fases.items():
        ph = ang + d
        a(_tacs98("R" + k, f"{m_ef:.6f}*SIN({w1:.6f}*TC{'+' if ph >= 0 else '-'}{abs(ph):.8f})"))
    a(_tacs98("MXAB", "(RA+RB+ABS(RA-RB))/2"))
    a(_tacs98("MX", "(MXAB+RC+ABS(MXAB-RC))/2"))
    a(_tacs98("MNAB", "(RA+RB-ABS(RA-RB))/2"))
    a(_tacs98("MN", "(MNAB+RC-ABS(MNAB-RC))/2"))
    a(_tacs98("ZS", "(MX+MN)/2"))
    a(_tacs98("FR", "TH*FS-TK"))
    a(_tacs98("TRI", "ABS(2*FR-1)*2-1"))
    vd2 = f"{op.vdc / 2:.4f}"
    for k in fases:
        a(_tacs98("Q" + k, f"R{k}-ZS"))
        a(_tacs98("G" + k, f"Q{k} .GT. TRI"))
        a(_tacs98("VL" + k, f"{vd2}*(2*G{k}-1)"))
    a("BLANK TACS")
    # ---------------- ramos
    a("$VINTAGE,1")
    sai = []
    for k in fases:
        a(_ramo(f"LI{k}", f"CP{k}", R=p.R1, L=p.L1))
        if rp:
            a(_ramo(f"LI{k}", f"CP{k}", R=rp))
    # banco de capacitores (Python: C_y, Rd, Cd, Rdp são equivalentes em estrela)
    pares = [("A", "B"), ("B", "C"), ("C", "A")]
    if ligacao == "Delta":
        for x, y in pares:
            a(_ramo(f"CP{x}", f"KM{x}{y}", R=3 * p.Rd if p.Rd else 1e-6, C=p.C_y / 3))
            if p.Cd > 0:
                a(_ramo(f"CP{x}", f"CP{y}", R=3 * p.Rdp, C=p.Cd / 3))
    else:
        for x in fases:
            a(_ramo(f"CP{x}", f"KM{x}", R=p.Rd if p.Rd else 1e-6, C=p.C_y))
            if p.Cd > 0:
                a(_ramo(f"CP{x}", "NCAP", R=p.Rdp, C=p.Cd))
        a(_ramo("NCAP", "", R=1e6))
    # L2 (LCL)
    ini = "CP"
    if p.L2 > 0:
        for k in fases:
            a(_ramo(f"CP{k}", f"L2{k}", R=p.R2 or 1e-6, L=p.L2))
        ini = "L2"
    # cabo: células π
    n = _n_secoes(p)
    prev = ini
    if n:
        lsec = p.cabo_m / 1000 / n
        for j in range(n):
            nxt = f"C{j + 1:02d}" if j < n - 1 else "MT"
            for k in fases:
                if p.cabo_Cpg_km:
                    a(_ramo(f"{prev}{k}", "", C=p.cabo_Cpg_km * lsec / 2))
                    a(_ramo(f"{nxt}{k}", "", C=p.cabo_Cpg_km * lsec / 2))
                a(_ramo(f"{prev}{k}", f"{nxt}{k}", R=max(p.cabo_R_km * lsec, 1e-7), L=p.cabo_L_km * lsec))
            if p.cabo_Cpp_km:
                for x, y in pares:
                    a(_ramo(f"{prev}{x}", f"{prev}{y}", C=p.cabo_Cpp_km * lsec / 2))
                    a(_ramo(f"{nxt}{x}", f"{nxt}{y}", C=p.cabo_Cpp_km * lsec / 2))
            prev = nxt
    else:
        for k in fases:
            a(_ramo(f"{ini}{k}", f"MT{k}", R=1e-6))
    # motor: Rm + Lm em estrela isolada (medição de corrente) + Cwf/3 à carcaça
    for k in fases:
        a(_ramo(f"MI{k}", "NMOT", R=max(p.Rm, 1e-6), L=p.Lm))
        if p.Cwf:
            a(_ramo(f"MT{k}", "", C=p.Cwf / 3))
    a(_ramo("NMOT", "", R=1e6))
    a("$VINTAGE,0")
    a("BLANK BRANCH")
    # ---------------- chaves de medição (correntes)
    for k in fases:
        a(_medidor(f"VL{k}", f"LI{k}"))                    # corrente do inversor
        a(_medidor(f"MT{k}", f"MI{k}"))                    # corrente do motor
    if ligacao == "Delta":
        for x, y in pares:
            a(_medidor(f"KM{x}{y}", f"CP{y}"))             # corrente do ramo do banco (Δ)
    else:
        for x in fases:
            a(_medidor(f"KM{x}", "NCAP"))                  # corrente do ramo do banco (Y)
    a("BLANK SWITCH")
    # ---------------- fontes
    for k in fases:
        a(f"60VL{k}".ljust(60) + _f(-1.0, 10) + _f(100.0, 10))
    # f.c.e.m. por Norton: i_N = E/(Rm + jωLm), injetada nos terminais (soma nula nas 3 fases)
    iN = ef / complex(p.Rm, w1 * p.Lm)
    norton = {}
    for k, d in fases.items():
        # Python usa referência seno: x(t) = |X| sen(ωt + ∠X); ATP tipo 14 = cosseno → fase −90°
        fase = math.degrees(np.angle(iN) + d) - 90.0
        norton[k] = (abs(iN), fase)
        a(_fonte(14, f"MI{k}", abs(iN), f1_t, fase, corrente=True))   # injetada após a medição → mede a corrente terminal
    a("BLANK SOURCE")
    # ---------------- saídas (tensões de nó)
    nos = [f"CP{k}" for k in fases] + [f"MT{k}" for k in fases] + [f"VL{k}" for k in fases]   # VL = saída do inversor (PWM)
    a("  " + "".join(_no(x) for x in nos))
    a("BLANK OUTPUT")
    a("BLANK PLOT")
    a("BEGIN NEW DATA CASE")
    a("BLANK")
    texto = "\n".join(L) + "\n"
    return dict(texto=texto, fs_ef=fs_ef, mf=mf, tmax=tmax, dt=dt, iplot=iplot, m=m, ligacao=ligacao, f1=f1_t,
                norton=norton, norton_no="MI")


# ----------------------------------------------------------------------------------------------- leitura PL4
def ler_pl4(caminho: str) -> Dict[str, Any]:
    """Lê arquivo .pl4 binário do ATP (Windows, 4 bytes, formato 'C-like'). Retorna dict(t, nomes, dados[nome])."""
    with open(caminho, "rb") as f:
        b = f.read()
    dt = struct.unpack("<f", b[40:44])[0]
    nvar = struct.unpack("<L", b[48:52])[0] // 2
    pl4size = struct.unpack("<L", b[56:60])[0] - 1
    # o tpbig NÃO trunca um .pl4 já existente: se a rodada anterior foi mais longa, o fim do arquivo fica com dados
    # VELHOS de outro caso (bug achado 19/11/2026 na A&W v1.8.8 a 41 Hz: lia o fim de um caso de 30 Hz). O cabeçalho
    # traz o tamanho real gravado nesta rodada: corta o arquivo nele.
    if 1000 < pl4size < len(b):
        b = b[:pl4size]
    nomes = []
    for i in range(nvar):
        pos = 5 * 16 + i * 16
        h = b[pos:pos + 16]
        tipo = h[3:4].decode("latin-1")
        n1 = h[4:10].decode("latin-1").strip()
        n2 = h[10:16].decode("latin-1").strip()
        nomes.append((int(tipo) if tipo.strip().isdigit() else tipo, n1, n2))
    ini = (5 + nvar) * 16
    nbytes = len(b) - ini
    passos = nbytes // ((nvar + 1) * 4)
    # há variantes com bytes nulos entre o cabeçalho e os dados: procura o início pelo tempo crescente
    melhor = None
    for extra in range(0, 64, 4):
        n_ = (len(b) - ini - extra) // ((nvar + 1) * 4)
        arr = np.frombuffer(b, dtype="<f4", count=n_ * (nvar + 1), offset=ini + extra).reshape(n_, nvar + 1)
        t = arr[:, 0]
        if n_ > 10 and np.all(np.diff(t[:1000]) > 0) and abs(t[0]) < 1e-3:
            # proteção extra: para no primeiro salto/retorno do tempo (resto de arquivo antigo)
            d = np.diff(t)
            med = float(np.median(d))
            ruim = np.nonzero((d <= 0) | (d > 1.5 * med))[0]
            melhor = arr[:ruim[0] + 1] if len(ruim) else arr
            break
    if melhor is None:
        raise ValueError("Formato .pl4 não reconhecido – verifique NEWPL4/L4BYTE no STARTUP do ATP")
    dados = {}
    for i, (tp, n1, n2) in enumerate(nomes):
        chave = {4: f"V:{n1}", 8: f"I:{n1}-{n2}", 9: f"I:{n1}-{n2}", 1: f"T:{n1}", 2: f"T:{n1}"}.get(tp, f"{tp}:{n1}-{n2}")
        if tp in (4,) and n2:
            chave = f"V:{n1}-{n2}"
        while chave in dados:
            chave += "'"
        dados[chave] = melhor[:, i + 1].astype(float)
    return dict(t=melhor[:, 0].astype(float), nomes=nomes, dados=dados, dt=dt, nvar=nvar)


# ----------------------------------------------------------------------------------------------- comparação
def _janela(t, y, f1, n_ciclos=2):
    T = n_ciclos / f1
    t_fim = t[-1]
    sel = t >= t_fim - T + 1e-12
    tt, yy = t[sel], y[sel]
    # reamostra em grade uniforme exata de N pontos por período (FFT exata das harmônicas de f1)
    N = int(round(T / np.median(np.diff(tt))))
    tg = t_fim - T + np.arange(N) * (T / N)
    return np.interp(tg, tt, yy), T / N


def _harm(y, n_ciclos):
    F = np.fft.rfft(y) / len(y)
    return F[::n_ciclos]          # componentes nas harmônicas inteiras de f1 (k = 0, 1, 2, …)


def metricas_atp(pl4: Dict[str, Any], f1: float, ligacao: str, n_por_ramo: int, kmax: int, n_ciclos: int = 2,
                 norton_descontar: Optional[Dict[str, Any]] = None) -> Dict[str, float]:
    """norton_descontar: {fase: (amp, fase_graus)} quando a fonte de Norton foi injetada ANTES da medição (decks v1)."""
    t, D = pl4["t"], pl4["dados"]

    def ser(chave_parcial):
        for k, v in D.items():
            if k.replace("'", "") == chave_parcial:
                return v
        raise KeyError(f"{chave_parcial} não encontrado no .pl4 (tem: {list(D)[:20]})")

    def w(x):
        return _janela(t, x, f1, n_ciclos)[0]

    def rms_bl(H):                # RMS com banda até kmax (igual ao Python)
        return float(np.sqrt(np.sum(2 * np.abs(H[1:kmax + 1]) ** 2)))

    def thd(H):
        a = np.sqrt(2) * np.abs(H[:kmax + 1])
        return float(100 * np.sqrt(np.sum(a[2:] ** 2)) / a[1]), float(a[1])

    vab = w(ser("V:CPA") - ser("V:CPB"))
    vmab = w(ser("V:MTA") - ser("V:MTB"))
    ia_raw = [w(ser(f"I:VL{k}-LI{k}")) for k in "ABC"]
    ia = ia_raw[0] - sum(ia_raw) / 3                  # componente diferencial (remove modo comum)
    im = []
    for k in "ABC":
        x = ser(f"I:MT{k}-MI{k}")
        if norton_descontar:
            A, ph = norton_descontar[k]
            x = x - A * np.cos(2 * np.pi * f1 * t + np.radians(ph))
        im.append(w(x))
    if ligacao == "Delta":
        ic = w(ser("I:KMAB-CPB"))
        ic_unit_fator = 1 / n_por_ramo
    else:
        ic = w(ser("I:KMA-NCAP"))
        ic_unit_fator = 1 / n_por_ramo
    Hv, Hvm, Hi1, Hi2, Hic = (_harm(x, n_ciclos) for x in (vab, vmab, ia, im[0], ic))
    thd_v, v1 = thd(Hv)
    thd_vm, vm1 = thd(Hvm)
    # pico de banda limitada (igual à reconstrução do Python) e pico bruto
    def pico_bl(H, N):
        F = np.zeros(N // 2 + 1, complex)
        F[:kmax + 1] = H[:kmax + 1] * N
        return float(np.max(np.abs(np.fft.irfft(F, n=N))))
    N = 2 * kmax * 8
    fund = np.zeros_like(Hi1); fund[1] = Hi1[1]
    Fi = np.zeros(N // 2 + 1, complex); Fi[:kmax + 1] = (Hi1 - fund)[:kmax + 1] * N
    rip = np.fft.irfft(Fi, n=N)
    return dict(
        thd_v_saida_pct=thd_v, v_saida_ll_fund=v1, vpk_saida=pico_bl(Hv, N), vpk_saida_bruto=float(np.max(np.abs(vab))),
        thd_v_motor_pct=thd_vm, v_motor_ll_fund=vm1, vpk_motor=pico_bl(Hvm, N),
        i1_rms=rms_bl(Hi1), i1_fund=float(np.sqrt(2) * abs(Hi1[1])), ripple_pp=float(rip.max() - rip.min()),
        i2_rms=rms_bl(Hi2), i2_fund=float(np.sqrt(2) * abs(Hi2[1])),
        icap_ramo_rms=rms_bl(Hic), icap_unit_rms=rms_bl(Hic) * ic_unit_fator,
        icap_ramo_bruto=float(np.sqrt(np.mean(ic ** 2))),
    )


def metricas_python(p: ParamCircuito, op: PontoOperacao, ligacao: str, n_por_ramo: int) -> Dict[str, float]:
    pc = dataclasses.replace(p, pelicular=False)
    r = simular(pc, op)
    m = r.metricas
    k_i = (1 / math.sqrt(3) if ligacao == "Delta" else 1.0)
    return dict(thd_v_saida_pct=m["thd_v_saida_pct"], v_saida_ll_fund=m["v_saida_ll_fund"], vpk_saida=m["vpk_saida"],
                thd_v_motor_pct=m["thd_v_motor_pct"], v_motor_ll_fund=m["v_motor_ll_fund"], vpk_motor=m["vpk_motor"],
                i1_rms=m["i1_rms"], i1_fund=m["i1_fund"], ripple_pp=m["ripple_pp"], i2_rms=m["i2_rms"], i2_fund=m["i2_fund"],
                icap_ramo_rms=m["icap_main_y_rms"] * k_i, icap_unit_rms=m["icap_main_y_rms"] * k_i / n_por_ramo)


ROTULOS = [
    ("v_saida_ll_fund", "Tensão de saída L-L fundamental", "V", 1.0),
    ("thd_v_saida_pct", "THD tensão de saída (até 4,6·fs)", "%", 10.0),
    ("vpk_saida", "Pico tensão L-L no banco", "V", 2.0),
    ("v_motor_ll_fund", "Tensão no motor L-L fundamental", "V", 1.0),
    ("thd_v_motor_pct", "THD tensão no motor", "%", 10.0),
    ("vpk_motor", "Pico tensão L-L no motor", "V", 2.0),
    ("i1_fund", "Corrente inversor fundamental", "A", 1.0),
    ("i1_rms", "Corrente inversor RMS", "A", 1.0),
    ("ripple_pp", "Ondulação p-p no indutor", "A", 8.0),
    ("i2_fund", "Corrente motor fundamental", "A", 1.0),
    ("icap_ramo_rms", "Corrente RMS ramo do banco", "A", 3.0),
    ("icap_unit_rms", "Corrente RMS por capacitor", "A", 3.0),
]


# tolerância ABSOLUTA mínima (validação 19/11/2026): THD abaixo de ~1 % difere em décimos entre os programas sem
# importância prática (ex.: SENAI 30 Hz: Python 0,62 % × ATP 0,92 %) – converge se |ATP − Python| ≤ 0,5 ponto percentual.
TOL_ABS = {"thd_v_saida_pct": 0.5, "thd_v_motor_pct": 0.5}


def comparar(py: Dict[str, float], atp: Dict[str, float]) -> List[Dict[str, Any]]:
    out = []
    for k, nome, un, tol in ROTULOS:
        a, b = py.get(k), atp.get(k)
        if a is None or b is None:
            continue
        dif = 100 * (b - a) / a if a else float("nan")
        out.append(dict(grandeza=nome, unidade=un, python=round(a, 3), atp=round(b, 3), dif_pct=round(dif, 2),
                        tolerancia_pct=tol, convergiu=bool(abs(dif) <= tol or abs(b - a) <= TOL_ABS.get(k, 0))))
    return out


# ----------------------------------------------------------------------------------------------- execução
def achar_tpbig(cat=None) -> Optional[str]:
    cfg = (cat or {}).get("atp", {})
    for c in [cfg.get("tpbig")] + TPBIG_PADRAO:
        if c and os.path.exists(c):
            return c
    return None


def rodar_atp(arquivo_atp: str, tpbig: Optional[str] = None, timeout: int = 1800) -> Dict[str, Any]:
    """Roda o ATP em segundo plano (sem janela). Retorna dict(ok, pl4, lis, msg). Só funciona no PC com ATP instalado."""
    tpbig = tpbig or achar_tpbig()
    if not tpbig:
        return dict(ok=False, msg="ATP não encontrado (configure 'atp: tpbig:' no catálogo)")
    pasta, nome = os.path.split(os.path.abspath(arquivo_atp))
    base = os.path.splitext(nome)[0]
    env = dict(os.environ)
    dir_tp = os.path.dirname(tpbig)
    # o tpbig procura o STARTUP na pasta de trabalho: copia o do ATP se não existir
    for st in ("startup", "STARTUP"):
        if os.path.exists(os.path.join(dir_tp, st)) and not os.path.exists(os.path.join(pasta, "startup")):
            shutil.copy(os.path.join(dir_tp, st), os.path.join(pasta, "startup"))
    # apaga resultados antigos ANTES de rodar: o tpbig não trunca o .pl4 e, se falhar, o arquivo velho pareceria válido
    for ext in (".pl4", ".lis", ".dbg"):
        try:
            os.remove(os.path.join(pasta, base + ext))
        except OSError:
            pass
    flags = 0x08000000 if os.name == "nt" else 0          # CREATE_NO_WINDOW
    pr = subprocess.run([tpbig, "disk", nome, "s", "-r"], cwd=pasta, capture_output=True, text=True, timeout=timeout,
                        env=env, creationflags=flags)
    pl4 = os.path.join(pasta, base + ".pl4")
    lis = os.path.join(pasta, base + ".lis")
    ok = os.path.exists(pl4) and os.path.getsize(pl4) > 1000
    return dict(ok=ok, pl4=pl4, lis=lis, msg=(pr.stdout or "")[-2000:] + (pr.stderr or "")[-1000:])


def preparar_casos(proj, cat, pasta: str) -> List[Dict[str, Any]]:
    """Gera um .atp por ponto de operação do projeto + o script de execução. Retorna a lista de casos."""
    from .dimensionamento import avaliar, pontos_operacao
    from .modelos import Pedido
    ped = Pedido.from_dict(proj.pedido) if isinstance(proj.pedido, dict) else proj.pedido
    b = proj.banco
    cap = next((c for c in cat["capacitores"] if c["id"] == b.cap_id), None) or dict(id=b.cap_id, uf=b.uf_unit, v_ac=b.v_unit, preco=0)
    am = proj.amortecimento
    rd = (am.rd_y_ohm if am and am.tipo != "rc_paralelo" else 0.0)
    cd = (am.cd_y_uf * 1e-6 if am and am.tipo == "rc_paralelo" else 0.0)
    rdp = (am.rdp_y_ohm if am and am.tipo == "rc_paralelo" else 0.0)
    vdc = 1.35 * ped.tensao_v
    L2 = proj.l2.l_uh * 1e-6 if proj.l2 else 0.0
    p, _, _ = avaliar(ped, cat, proj.l1.l_uh * 1e-6, cap, (b.ligacao, b.n_por_ramo, b.c_y_uf * 1e-6), proj.fs_hz, vdc,
                      L2=L2, rd=rd, cd=cd, rdp=rdp, pts_por_portadora=24)
    os.makedirs(pasta, exist_ok=True)
    casos = []
    for i, pt in enumerate(pontos_operacao(ped, vdc, proj.fs_hz)):
        d = gerar_deck(p, pt["op"], b.ligacao, titulo=f"{pt['nome']}")
        nome = f"fsen_caso{i + 1}"
        with open(os.path.join(pasta, nome + ".atp"), "w", encoding="latin-1", newline="\r\n") as f:
            f.write(d["texto"].encode("latin-1", "replace").decode("latin-1"))
        caso = dict(nome=nome, ponto=pt["nome"], op=pt["op"], deck=d, p=p, ligacao=b.ligacao, n_por_ramo=b.n_por_ramo)
        try:                                       # desenho da MESMA rede no ATPDraw (abre junto com o .pl4)
            from .atpdraw import gerar_atpdraw_xml
            try:
                mp = metricas_python(p, pt["op"], b.ligacao, b.n_por_ramo)
                rp = {k: (f"{v:.4g}" if isinstance(v, float) else v) for k, v in mp.items()}
            except Exception:
                rp = {}
            caso["atpdraw"] = gerar_atpdraw_xml(p, d, b.ligacao, os.path.join(pasta, nome + "_desenho.xml"),
                                                titulo=pt["nome"], resumo_python=rp)
        except Exception as e:
            caso["atpdraw_erro"] = str(e)
        casos.append(caso)
    with open(os.path.join(pasta, "rodar_atp.bat"), "w", newline="\r\n") as f:
        f.write("@echo off\r\ncd /d \"%~dp0\"\r\nif not exist startup copy /y C:\\ATP\\atpmingw\\startup startup >nul\r\n")
        for c in casos:
            f.write(f"C:\\ATP\\atpmingw\\tpbig.exe disk {c['nome']}.atp s -r > {c['nome']}_console.txt 2>&1\r\n")
        f.write("echo FIM > atp_concluido.txt\r\n")
    return casos


def comparar_casos(casos, pasta: str) -> List[Dict[str, Any]]:
    out = []
    for c in casos:
        pl4 = os.path.join(pasta, c["nome"] + ".pl4")
        py = metricas_python(c["p"], c["op"], c["ligacao"], c["n_por_ramo"])
        kmax = int(4.6 * c["deck"]["mf"])
        no = c["deck"].get("norton_no", "MT")
        lis = os.path.join(pasta, c["nome"] + ".lis")
        if os.path.exists(lis):          # confere no .lis onde a fonte de Norton foi realmente injetada
            txt = open(lis, encoding="latin-1", errors="ignore").read()
            no = "MT" if "|14MTA" in txt else ("MI" if "|14MIA" in txt else no)
        nd = c["deck"]["norton"] if no == "MT" else None
        at = metricas_atp(ler_pl4(pl4), c["deck"].get("f1", c["op"].f1), c["ligacao"], c["n_por_ramo"], kmax, norton_descontar=nd)
        out.append(dict(ponto=c["ponto"], tabela=comparar(py, at), python=py, atp=at))
    return out


def dupla_checagem(proj, cat, pasta: str = PASTA_TRABALHO_PADRAO, log=print) -> Dict[str, Any]:
    """Fluxo completo no PC: gera decks, roda o ATP em segundo plano, compara e devolve as tabelas."""
    casos = preparar_casos(proj, cat, pasta)
    tp = achar_tpbig(cat)
    if not tp:
        return dict(ok=False, msg="ATP não instalado neste computador", casos=[c["nome"] for c in casos])
    for c in casos:
        log(f"ATP: {c['ponto']} …")
        r = rodar_atp(os.path.join(pasta, c["nome"] + ".atp"), tp)
        if not r["ok"]:
            return dict(ok=False, msg=f"ATP falhou em {c['nome']}: {r['msg']}")
    res = comparar_casos(casos, pasta)
    ok = all(l["convergiu"] for x in res for l in x["tabela"])
    return dict(ok=True, convergiu=ok, resultados=res)


# ----------------------------------------------------------------------------------------------- relatório
def grafico_comparacao(caso, pasta_pl4: str, arquivo_png: str, n_ciclos: int = 2):
    """Sobrepõe Python × ATP: tensão L-L no banco, corrente no ramo do capacitor e corrente do inversor."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    p, op, lig, n = caso["p"], caso["op"], caso["ligacao"], caso["n_por_ramo"]
    pc = dataclasses.replace(p, pelicular=False)
    r = simular(pc, op, pts_por_portadora=120, ciclos_analise=n_ciclos)
    d = ler_pl4(os.path.join(pasta_pl4, caso["nome"] + ".pl4"))
    t, D = d["t"], d["dados"]
    T = n_ciclos / op.f1
    sel = t >= t[-1] - T
    ta = (t[sel] - (t[-1] - T)) * 1e3
    g = lambda k: D[k][sel]
    # alinhamento de fase: o Python começa em t=0 do período; o ATP termina em k·T → mesmo instante de fase
    t0 = (t[-1] - T) % (1 / op.f1)
    tp = (r.t - 0) * 1e3
    k_i = 1 / math.sqrt(3) if lig == "Delta" else 1.0
    # corrente do ramo do capacitor no Python (forma de onda Y equivalente → ramo)
    vab_atp = g("V:CPA") - g("V:CPB")
    ic_atp = g("I:KMAB-CPB") if lig == "Delta" else g("I:KMA-NCAP")
    ia = [g(f"I:VL{k}-LI{k}") for k in "ABC"]
    i1_atp = ia[0] - sum(ia) / 3
    shift = lambda y: np.interp((tp / 1e3 + t0) % T, r.t, y)
    # ATP levado ao mesmo eixo do Python e alinhado pelo padrão PWM (correlação da parcela de alta frequência)
    from .spec_indutor import alinhar_fundamental as _al
    _no_tp = lambda y_atp, y_py: _al(np.interp(tp, ta, y_atp), y_py, n_ciclos)
    vab_atp = _no_tp(vab_atp, shift(r.vc_ab))
    i1_atp = _no_tp(i1_atp, shift(r.i1))
    ta = tp
    fig, ax = plt.subplots(3, 1, figsize=(11, 8.5), sharex=True)
    ax[0].plot(ta, vab_atp, color="#d95f02", lw=0.8, label="ATP")
    ax[0].plot(tp, shift(r.vc_ab), color="#1b4f9c", lw=0.8, ls="--", label="Python")
    ax[0].set_ylabel("V banco L-L (V)")
    ax[1].plot(ta, i1_atp, color="#d95f02", lw=0.8, label="ATP")
    ax[1].plot(tp, shift(r.i1), color="#1b4f9c", lw=0.8, ls="--", label="Python")
    ax[1].set_ylabel("I inversor fase A (A)")
    ic_py = None
    try:
        if lig == "Delta":
            # ramo AB do triângulo: i = C_Δ·dv_ab/dt, com C_Δ = C_Y/3 (derivada periódica da tensão do banco)
            dtp = float(r.t[1] - r.t[0])
            v = np.asarray(r.vc_ab, float)
            ic_py = shift((p.C_y / 3.0) * (np.roll(v, -1) - np.roll(v, 1)) / (2 * dtp))
        else:
            ic_py = shift(r.icap_y) * k_i
    except Exception:
        pass
    try:
        ic_atp = np.interp(tp, (t[sel] - (t[-1] - T)) * 1e3, ic_atp)
        if ic_py is not None:
            ic_atp = _al(ic_atp, ic_py, n_ciclos)
    except Exception:
        pass
    ax[2].plot(ta, ic_atp, color="#d95f02", lw=0.6, label="ATP – ramo AB" if lig == "Delta" else "ATP – ramo A")
    if ic_py is not None:
        ax[2].plot(tp, ic_py, color="#1b4f9c", lw=0.6, ls="--", label="Python")
    ax[2].set_ylabel(f"I ramo do banco (A)\n{n} cap. em paralelo")
    ax[2].set_xlabel("t (ms) – últimos 2 ciclos em regime")
    for a_ in ax:
        a_.grid(alpha=0.3)
        a_.legend(loc="upper right", fontsize=8)
    fig.suptitle(f"Dupla checagem Python × ATP – {caso['ponto']}", fontsize=11)
    fig.tight_layout()
    fig.savefig(arquivo_png, dpi=130)
    plt.close(fig)
    return arquivo_png


def salvar_relatorio(resultados, arquivo_xlsx: str):
    import pandas as pd
    linhas = []
    for r in resultados:
        for l in r["tabela"]:
            linhas.append(dict(ponto=r["ponto"], **l))
    df = pd.DataFrame(linhas)
    df.to_excel(arquivo_xlsx, index=False)
    return df


# ----------------------------------------------------------------------------------------------- abrir no ATPDraw / PlotXY
PLOTXY_PADRAO = [r"C:\ATP\PlotXY\PlotXY.exe", r"C:\ATP\tools\PlotXY.exe", r"C:\ATP\PlotXY.exe", r"C:\Program Files\PlotXY\PlotXY.exe",
                 r"C:\Program Files (x86)\PlotXY\PlotXY.exe"]
ATPDRAW_PADRAO = [r"C:\ATP\ATPDraw77\Atpdraw.exe", r"C:\ATP\ATPDraw72\Atpdraw.exe", r"C:\ATP\ATPDraw\ATPDraw.exe", r"C:\ATP\ATPDraw7\ATPDraw.exe", r"C:\ATPDraw\ATPDraw.exe",
                  r"C:\Program Files\ATPDraw\ATPDraw.exe", r"C:\Program Files (x86)\ATPDraw\ATPDraw.exe"]


def _achar(cfg_chave, padroes, cat=None):
    cfg = (cat or {}).get("atp", {})
    for c in [cfg.get(cfg_chave)] + padroes:
        if c and os.path.exists(c):
            return c
    return None


def exportar_python_mat(casos, pasta: str, n_ciclos: int = 2) -> List[str]:
    """Grava as formas de onda do PYTHON em MATLAB v4 (.mat), formato que o PlotXY abre junto com o .pl4 do ATP,
    com os MESMOS nomes de grandeza (sufixo _PY) – para sobrepor Python × ATP no próprio PlotXY."""
    from scipy.io import savemat
    out = []
    for c in casos:
        pc = dataclasses.replace(c["p"], pelicular=False)
        r = simular(pc, c["op"], pts_por_portadora=120, ciclos_analise=n_ciclos)
        k_i = 1 / math.sqrt(3) if c["ligacao"] == "Delta" else 1.0
        d = {"t": r.t, "V_INV_AB_PY": r.u_ab, "V_CP_AB_PY": r.vc_ab, "V_MT_AB_PY": getattr(r, "vm_ab", r.vc_ab),
             "I_L1_A_PY": r.i1, "I_MT_A_PY": r.i2, "I_CAP_RAMO_PY": r.icap_y * k_i}
        arq = os.path.join(pasta, f"{c['nome']}_python.mat")
        savemat(arq, {k: np.asarray(v, float).reshape(-1, 1) for k, v in d.items()}, format="4")
        out.append(arq)
    return out


def abrir_no_windows(pasta_atp: str, caso: str = "fsen_caso1", cat=None) -> Dict[str, Any]:
    """Abre o resultado do ATP no PlotXY (.pl4 + .mat do Python) e o desenho no ATPDraw (.acp), se existirem neste PC."""
    import subprocess
    res = dict(plotxy=None, atpdraw=None, msg=[])
    pl4 = os.path.join(pasta_atp, caso + ".pl4")
    mat = os.path.join(pasta_atp, caso + "_python.mat")
    acp = os.path.join(pasta_atp, caso + ".acp")
    if not os.path.exists(acp):                    # desenho gerado pela plataforma (XML do ATPDraw 7)
        acp = os.path.join(pasta_atp, caso + "_desenho.xml")
    px = _achar("plotxy", PLOTXY_PADRAO, cat)
    if os.path.exists(pl4):
        try:
            if px:
                subprocess.Popen([px, pl4] + ([mat] if os.path.exists(mat) else []), cwd=pasta_atp)
            else:
                os.startfile(pl4)                      # programa associado ao .pl4
            res["plotxy"] = px or "associação do Windows"
        except Exception as e:
            res["msg"].append(f"PlotXY não abriu: {e}")
    else:
        res["msg"].append("Sem .pl4 (o ATP não rodou neste projeto).")
    ad = _achar("atpdraw", ATPDRAW_PADRAO, cat)
    if os.path.exists(acp):
        try:
            if ad:
                subprocess.Popen([ad, acp], cwd=pasta_atp)
            else:
                os.startfile(acp)
            res["atpdraw"] = ad or "associação do Windows"
        except Exception as e:
            res["msg"].append(f"ATPDraw não abriu: {e}")
    else:
        res["msg"].append("Desenho ATPDraw ainda não gerado para este projeto (rode o projeto de novo na v1.9.2+).")
    return res
