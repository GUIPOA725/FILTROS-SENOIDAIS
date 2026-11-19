"""Simulação no domínio do tempo (PWM real) e da frequência do filtro LC/LCL.

Modelo por fase (modo diferencial, neutros isolados):
  inversor PWM (SVPWM, portadora triangular fs) -> L1 (com R série e Rp de perdas HF)
  -> C (estrela equivalente) -> [L2 se LCL] -> motor (R + L dispersão + f.c.e.m.)
Discretização exata (ZOH) por exponencial de matriz.
"""
from __future__ import annotations
import numpy as np
from dataclasses import dataclass, field


@dataclass
class ParamCircuito:
    L1: float            # H
    R1: float            # ohm (série, cobre)
    C_y: float           # F por fase (estrela equivalente)
    L2: float = 0.0      # H (LCL, lado motor)
    R2: float = 0.0
    Q_hf: float = 40.0   # fator de qualidade do indutor na freq. de chaveamento (perdas núcleo HF)
    fs_ref: float = 4000.0  # Hz onde Q_hf é definido
    Lm: float = 0.0      # H dispersão do motor
    Rm: float = 0.0      # ohm resistência do motor
    Rd: float = 0.0      # ohm resistor de amortecimento em série com cada capacitor (Y equiv.)
    Cd: float = 0.0      # F ramo de amortecimento RC paralelo (Y equiv.): Cd em série com Rdp, em paralelo com C
    Rdp: float = 0.0     # ohm resistor do ramo RC paralelo (Y equiv.)
    # --- cabo filtro→motor (modelo π distribuído) ---
    cabo_m: float = 0.0          # comprimento (m)
    cabo_R_km: float = 0.0       # ohm/km por fase (90 °C, já dividido pelos paralelos)
    cabo_L_km: float = 0.0       # H/km por fase
    cabo_Cpg_km: float = 0.0     # F/km fase–blindagem/terra
    cabo_Cpp_km: float = 0.0     # F/km fase–fase
    cabo_secoes: int = 0         # nº de células π (0 = automático)
    # --- motor: alta frequência e modo comum ---
    Cwf: float = 0.0             # F capacitância enrolamento–carcaça total (3 fases)
    bvr: float = 0.04            # relação tensão no mancal / tensão de modo comum (BVR)
    # --- modo comum ---
    L0_fator: float = 0.10       # indutância de sequência zero do indutor (fração de L1) – núcleo trifásico 3 colunas ≈ 0,05–0,15
    estrela_ao_cc: bool = False  # centro-estrela do banco ligado ao barramento CC (filtro "all-pole")
    C_emc: float = 0.5e-6        # F capacitores Y do filtro EMC do inversor (CC → PE)
    L_terra_km: float = 0.4e-3   # H/km indutância do laço condutores–PE/blindagem (modo comum)
    R_pe_km: float = 0.3         # ohm/km condutor PE/blindagem
    pelicular: bool = True       # efeito pelicular em R do cabo e do motor (False = R constante, p/ comparar com o ATP)


def z_cap(p, s):
    """Impedância do ramo capacitivo por fase (Y): C (+Rd série) // (Rdp + Cd)."""
    z = 1 / (s * p.C_y) + p.Rd
    if p.Cd > 0:
        z = 1 / (1 / z + 1 / (p.Rdp + 1 / (s * p.Cd)))
    return z


@dataclass
class PontoOperacao:
    v_ll: float          # tensão de linha de saída desejada (fundamental, V rms)
    f1: float            # Hz
    i_carga: float       # A rms
    fp: float            # fator de potência da carga
    vdc: float           # V barramento CC
    fs: float            # Hz chaveamento


@dataclass
class ResultadoSim:
    t: np.ndarray
    u_ab: np.ndarray
    vc_ab: np.ndarray
    i1: np.ndarray       # corrente do inversor (fase a)
    i2: np.ndarray       # corrente do motor (fase a)
    icap_y: np.ndarray   # corrente ramo capacitivo equivalente Y (fase a)
    m_index: float
    sobremodulacao: bool
    metricas: dict = field(default_factory=dict)
    espectro: dict = field(default_factory=dict)


def _mul(T1, T2):
    A1, B1, C1, D1 = T1
    A2, B2, C2, D2 = T2
    return (A1 * A2 + B1 * C2, A1 * B2 + B1 * D2, C1 * A2 + D1 * C2, C1 * B2 + D1 * D2)


def _n_secoes(p):
    if p.cabo_m <= 0:
        return 0
    return p.cabo_secoes or int(min(20, max(2, np.ceil(p.cabo_m / 25))))


def _abcd_dm(p, s):
    """Duas-portas do nó dos capacitores até os terminais do motor: L2 (LCL) + cabo (células π), por fase (Y)."""
    one, zero = np.ones_like(s), np.zeros_like(s)
    T = (one, p.R2 + s * p.L2, zero, one)
    n = _n_secoes(p)
    if n:
        lsec = p.cabo_m / 1000 / n
        kp = np.sqrt(np.maximum(np.abs(s) / (2 * np.pi * 60), 1)) ** 0.5 if p.pelicular else 1.0
        Z = (p.cabo_R_km * lsec) * kp + s * p.cabo_L_km * lsec
        Y = s * (p.cabo_Cpg_km + 3 * p.cabo_Cpp_km) * lsec
        cel = _mul(_mul((one, zero, Y / 2, one), (one, Z, zero, one)), (one, zero, Y / 2, one))
        for _ in range(n):
            T = _mul(T, cel)
    return T


def _z_motor(p, s, f1=None):
    """Impedância do motor por fase: fundamental = dispersão (+f.c.e.m. à parte); harmônicas = R·√h (efeito pelicular) + L de dispersão."""
    w1 = 2 * np.pi * (f1 or 60.0)
    h = np.maximum(np.abs(s) / w1, 1.0)
    return p.Rm * (np.sqrt(h) if p.pelicular else 1.0) + s * p.Lm


def _fasores(p: ParamCircuito, op: PontoOperacao):
    """Fundamental: impõe tensão e corrente nos TERMINAIS DO MOTOR e calcula a tensão necessária no inversor.
    Retorna V_inv, I1, Vc, Im (motor), E (f.c.e.m.), Vm (fasores de pico, fase a)."""
    w = 2 * np.pi * op.f1
    s1 = np.array([1j * w])
    vm = op.v_ll / np.sqrt(3) * np.sqrt(2) + 0j
    phi = np.arccos(np.clip(op.fp, 0.05, 1.0))
    im = op.i_carga * np.sqrt(2) * np.exp(-1j * phi)
    e = vm - (p.Rm + 1j * w * p.Lm) * im
    A, B, C, D = (x[0] for x in _abcd_dm(p, s1))
    vc = A * vm + B * im
    iout = C * vm + D * im
    i1 = iout + vc / z_cap(p, 1j * w)
    zl1 = p.R1 + 1j * w * p.L1
    rp = _rp(p)
    zl1p = zl1 * rp / (zl1 + rp) if rp else zl1
    vinv = vc + zl1p * i1
    return vinv, i1, vc, im, e, vm


def op_efetivo(p: ParamCircuito, op: PontoOperacao):
    """Sobremodulação: o inversor não entrega a tensão pedida. A CORRENTE de carga é mantida (o motor escorrega mais
    para manter o torque) e a tensão nos terminais cai até o inversor atingir m = 2/√3. Retorna (op_ajustado, k_tensao)."""
    import dataclasses
    m_lim = 2 / np.sqrt(3)
    vinv1 = _fasores(p, op)[0]
    if abs(vinv1) / (op.vdc / 2) <= m_lim:
        return op, 1.0
    a = vinv1 - _fasores(p, dataclasses.replace(op, v_ll=1e-9))[0]     # parcela proporcional à tensão do motor
    b = vinv1 - a                                                      # parcela devida à corrente (quedas em série)
    alvo = m_lim * op.vdc / 2
    # |a·k + b| = alvo  →  |a|²k² + 2Re(a·b*)k + |b|² − alvo² = 0
    A, B, C = abs(a) ** 2, 2 * (a * np.conj(b)).real, abs(b) ** 2 - alvo ** 2
    k = (-B + np.sqrt(max(B * B - 4 * A * C, 0))) / (2 * A)
    k = float(min(1.0, max(0.3, k)))
    return dataclasses.replace(op, v_ll=op.v_ll * k), k


def _rp(p: ParamCircuito):
    """Resistência paralela equivalente das perdas HF do núcleo (Q definido em fs)."""
    return p.Q_hf * 2 * np.pi * p.fs_ref * p.L1


def _bordas_pwm(m_ef, ang, f1, mf, desloc):
    """PWM vetorial (SVPWM = senoide + injeção min/max) com amostragem regular simétrica, como no DSP do inversor.
    Retorna, por fase, os instantes exatos de subida/descida do braço em um período fundamental."""
    T = 1 / f1
    Ts = T / mf
    t0 = np.arange(mf) * Ts
    # referência avaliada no centro do pulso (o controle do inversor compensa o atraso de amostragem)
    ref = m_ef * np.sin(2 * np.pi * f1 * (t0[:, None] + Ts / 2) + ang + desloc[None, :])
    ref = ref - (ref.max(axis=1, keepdims=True) + ref.min(axis=1, keepdims=True)) / 2
    d = np.clip((1 + ref) / 2, 0.0, 1.0)                      # razão cíclica do braço
    t_on = t0[:, None] + Ts * (1 - d) / 2
    t_off = t0[:, None] + Ts * (1 + d) / 2
    return t_on, t_off, T


def _espectro_pwm(t_on, t_off, T, vdc, kmax):
    """Coeficientes complexos exatos X_k (k = 0..kmax) da tensão de braço (±Vdc/2) – sem quantização."""
    k = np.arange(1, kmax + 1)
    w = 2 * np.pi / T
    X = np.zeros((kmax + 1, t_on.shape[1]), complex)
    for f in range(t_on.shape[1]):
        a = np.exp(-1j * np.outer(k, w * t_on[:, f]))
        b = np.exp(-1j * np.outer(k, w * t_off[:, f]))
        X[1:, f] = vdc * (a - b).sum(axis=1) / (1j * k * w) / T
        X[0, f] = vdc * np.sum(t_off[:, f] - t_on[:, f]) / T - vdc / 2
    return X


def simular(p: ParamCircuito, op: PontoOperacao, ciclos: int = 2, pts_por_portadora: int = 60,
            ciclos_analise: int = 2) -> ResultadoSim:
    """Regime permanente exato: espectro analítico do PWM (bordas exatas) aplicado harmônica a harmônica ao circuito.
    `pts_por_portadora` só define a resolução das curvas no tempo (não afeta as métricas espectrais)."""
    m = abs(_fasores(p, op)[0]) / (op.vdc / 2)                     # índice de modulação NECESSÁRIO
    sobremod = m > 2 / np.sqrt(3)
    op, k_tensao = op_efetivo(p, op)                               # mantém a corrente; tensão cai se faltar barramento
    vinv, i1f, vcf, i2f, ef, vmf = _fasores(p, op)
    m_ef = min(m, 2 / np.sqrt(3))
    ang = np.angle(vinv)
    mf = max(3, int(round((op.fs / op.f1 - 3) / 6)) * 6 + 3)     # múltiplo ímpar de 3
    fs_ef = mf * op.f1
    desloc = np.array([0, -2 * np.pi / 3, 2 * np.pi / 3])
    t_on, t_off, T = _bordas_pwm(m_ef, ang, op.f1, mf, desloc)
    kmax = int(4.6 * mf)                                            # até ~4,6·fs
    X = _espectro_pwm(t_on, t_off, T, op.vdc, kmax)
    U = X - X.mean(axis=1, keepdims=True)                           # modo diferencial (remove seq. zero)
    U[0, :] = 0
    k = np.arange(kmax + 1)
    f = k * op.f1
    s = 2j * np.pi * f
    s[0] = 1e-9j
    rp = _rp(p)
    Zl1 = (p.R1 + s * p.L1) * rp / (p.R1 + s * p.L1 + rp)
    Zc = z_cap(p, s)
    Zm = _z_motor(p, s, op.f1)
    A, B, C, D = (x[:, None] for x in _abcd_dm(p, s))
    E = np.zeros_like(U)
    for q in range(3):
        E[1, q] = ef * np.exp(1j * desloc[q]) / 2j                  # sen(ωt+φ) -> coef. complexo e^{jωt}
    Y1 = (1 / Zl1 + 1 / Zc)[:, None]
    Zm_ = Zm[:, None]
    I2 = (U / Zl1[:, None] - (A * Y1 + C) * E) / ((A * Zm_ + B) * Y1 + C * Zm_ + D)   # corrente no motor
    VM = E + Zm_ * I2                                               # tensão nos terminais do motor
    VC = A * VM + B * I2
    IOUT = C * VM + D * I2
    I1 = (U - VC) / Zl1[:, None]
    IC = (VC / Zc[:, None])
    IM = VC / (1 / (s * p.C_y) + p.Rd)[:, None]                    # corrente só nos capacitores principais
    ID = (VC / (p.Rdp + 1 / (s * p.Cd))[:, None]) if p.Cd > 0 else np.zeros_like(VC)
    for X_ in (VC, I1, I2, IC, IM, ID, VM):
        X_[0, :] = 0

    # formas de onda (banda até kmax) para gráficos
    n = mf * pts_por_portadora
    def onda(A):
        F = np.zeros(n // 2 + 1, complex)
        kk = min(kmax, n // 2)
        F[:kk + 1] = A[:kk + 1] * n
        return np.fft.irfft(F, n=n)
    dt = T / n
    t = np.arange(n) * dt
    Ts = T / mf
    idx = np.minimum((t // Ts).astype(int), mf - 1)
    leg = np.where((t[:, None] >= t_on[idx]) & (t[:, None] < t_off[idx]), op.vdc / 2, -op.vdc / 2)
    rep = max(1, ciclos_analise)
    til = lambda x: np.tile(x, rep)
    r = ResultadoSim(t=np.arange(n * rep) * dt, u_ab=til(leg[:, 0] - leg[:, 1]), vc_ab=til(onda(VC[:, 0] - VC[:, 1])),
                     i1=til(onda(I1[:, 0])), i2=til(onda(I2[:, 0])), icap_y=til(onda(IC[:, 0])), m_index=m,
                     sobremodulacao=bool(sobremod))
    r.metricas, r.espectro = _metricas_espectrais(r, op, f, U, VC, I1, I2, IC, rp, dt, Zl1)
    rmsA = lambda A: float(np.sqrt(np.sum(2 * np.abs(A[1:]) ** 2)))
    r.metricas["icap_main_y_rms"] = rmsA(IM[:, 0])
    r.metricas["icap_main_y_fund"] = float(np.sqrt(2) * abs(IM[1, 0]))
    r.metricas["icap_d_y_rms"] = rmsA(ID[:, 0])
    r.metricas["p_amort_w"] = 3 * (rmsA(IM[:, 0]) ** 2 * p.Rd + rmsA(ID[:, 0]) ** 2 * p.Rdp)
    r.metricas["fs_efetiva"] = fs_ef
    r.metricas["k_tensao_sobremod"] = k_tensao
    # --- tensão nos terminais do motor (após cabo) ---
    vmab = VM[:, 0] - VM[:, 1]
    a_m = np.sqrt(2) * np.abs(vmab)
    r.metricas["thd_v_motor_pct"] = float(100 * np.sqrt(np.sum(a_m[2:] ** 2)) / a_m[1])
    r.metricas["v_motor_ll_fund"] = float(a_m[1])
    wm = onda(vmab)
    r.metricas["vpk_motor"] = float(np.max(np.abs(wm)))
    r.metricas["dvdt_motor_v_us"] = float(np.max(np.abs(np.diff(wm))) / dt / 1e6)
    r.vm_ab = til(wm)
    # --- capacitores: pico de tensão de fase/linha e somas para perdas (ESR e dielétrico) ---
    r.metricas["vpk_cap_ll"] = float(np.max(np.abs(onda(VC[:, 0] - VC[:, 1]))))
    r.metricas["vpk_cap_ph"] = float(np.max(np.abs(onda(VC[:, 0]))))
    i2h = 2 * np.abs(IM[1:, 0]) ** 2                               # I_rms² por harmônica (Y equiv.)
    r.metricas["icap_sum_i2"] = float(np.sum(i2h))
    r.metricas["icap_sum_i2_sobre_f"] = float(np.sum(i2h / f[1:]))
    # --- modo comum e corrente de terra ---
    r.metricas.update(_modo_comum(p, op, X, f, s, n, dt, onda, mf))
    return r


def _modo_comum(p, op, X, f, s, n, dt, onda, mf):
    """Circuito de modo comum (sequência zero) inversor → filtro → cabo → carcaça do motor → PE → filtro EMC do inversor.
    O filtro senoidal diferencial (C em Δ ou Y isolado) NÃO atenua o modo comum."""
    Vcm = X.mean(axis=1).copy()
    Vcm[0] = 0
    one, zero = np.ones_like(s), np.zeros_like(s)
    s_ = s.copy()
    Zf = p.R1 / 3 + s_ * p.L0_fator * p.L1 / 3
    Zsh = (1 / (s_ * 3 * p.C_y) + p.Rd / 3) if p.estrela_ao_cc else np.full_like(s_, 1e12)
    Zret = 1 / (s_ * p.C_emc) + 0.05
    T = (one, zero, zero, one)
    nsec = _n_secoes(p)
    L_m = max(p.cabo_m, 1.0)
    if nsec:
        lsec = p.cabo_m / 1000 / nsec
        Zs = (p.cabo_R_km / 3 + p.R_pe_km) * lsec + s_ * p.L_terra_km * lsec
        Ysh = s_ * 3 * p.cabo_Cpg_km * lsec
        cel = _mul(_mul((one, zero, Ysh / 2, one), (one, Zs, zero, one)), (one, zero, Ysh / 2, one))
        for _ in range(nsec):
            T = _mul(T, cel)
    A, B, C, D = T
    Zl = 1 / (s_ * max(p.Cwf, 1e-12)) + 0.5
    Zin = (A * Zl + B) / (C * Zl + D)
    Ig = Vcm / (Zf * ((Zret + Zin) / Zsh + 1) + Zret + Zin)
    Il = Ig * Zin / (A * Zl + B)
    Vmot = Zl * Il                                                   # tensão de modo comum enrolamento–carcaça
    Ig[0] = Vmot[0] = 0
    rms = lambda Z: float(np.sqrt(np.sum(2 * np.abs(Z[1:]) ** 2)))
    w_v = onda(Vmot)
    w_i = onda(Ig)
    # pico nas comutações (borda de ns, fora da banda simulada): degrau Vcc/3 sobre a impedância de surto do cabo em MC
    if nsec and p.cabo_Cpg_km > 0:
        z0 = np.sqrt(p.L_terra_km / (3 * p.cabo_Cpg_km))
        i_borda = (op.vdc / 3) / z0
        if p.estrela_ao_cc:
            i_borda *= 0.15
    else:
        i_borda = 0.0
    vcm_pk_borda = (op.vdc / 2) * (0.15 if p.estrela_ao_cc else 1.0)
    return dict(vcm_motor_rms=rms(Vmot), vcm_motor_pk=float(max(np.max(np.abs(w_v)), vcm_pk_borda * 0.0 + np.max(np.abs(w_v)))),
                vcm_motor_pk_borda=float(vcm_pk_borda), i_terra_rms=rms(Ig), i_terra_pk_banda=float(np.max(np.abs(w_i))),
                i_terra_pk_borda=float(i_borda), v_mancal_pk=float(p.bvr * vcm_pk_borda))


def _metricas_espectrais(r, op, f, U, VC, I1, I2, IC, rp, dt, Zl1):
    rms = lambda A: np.sqrt(2) * np.abs(A)                      # valor eficaz de cada harmônica
    uab, vab = U[:, 0] - U[:, 1], VC[:, 0] - VC[:, 1]
    def thd(A, hmax=None):
        a = rms(A)
        sel = slice(2, (hmax + 1) if hmax else None)
        return 100 * np.sqrt(np.sum(a[sel] ** 2)) / a[1], a[1]
    thd_vc, vc1 = thd(vab)
    thd_vc50, _ = thd(vab, 50)
    thd_u, u1 = thd(uab)
    thd_i2, i21 = thd(I2[:, 0])
    thd_i1, i11 = thd(I1[:, 0])
    tot = lambda A: float(np.sqrt(np.sum(rms(A[1:]) ** 2)))
    rip = I1[:, 0].copy()
    rip[1] = 0
    rip_rms = tot(rip)
    # ondulação p-p a partir da forma de onda reconstruída
    X1 = I1[1, 0]
    fund = np.real(2 * X1 * np.exp(1j * 2 * np.pi * op.f1 * r.t))
    rw = r.i1 - fund
    # perdas HF no Rp: tensão no indutor (U - VC) nas harmônicas
    p_hf = 3 * np.sum((rms(U[2:, 0] - VC[2:, 0])) ** 2) / rp
    met = dict(
        thd_v_saida_pct=float(thd_vc), thd_v_saida_h50_pct=float(thd_vc50), thd_v_inversor_pct=float(thd_u),
        v_saida_ll_fund=float(vc1), v_inv_ll_fund=float(u1),
        vpk_saida=float(np.max(np.abs(r.vc_ab))), vpk_inversor=float(op.vdc),
        dvdt_saida_v_us=float(np.max(np.abs(np.diff(r.vc_ab))) / dt / 1e6), dvdt_inversor_v_us=float("nan"),
        i1_rms=tot(I1[:, 0]), i1_pico=float(np.max(np.abs(r.i1))), i1_fund=float(i11), i1_thd_pct=float(thd_i1),
        i2_rms=tot(I2[:, 0]), i2_thd_pct=float(thd_i2), i2_fund=float(i21),
        icap_y_rms=tot(IC[:, 0]), icap_y_fund=float(rms(IC[1, 0])),
        ripple_pp=float(rw.max() - rw.min()), ripple_rms=rip_rms, p_hf_w=float(p_hf), m_index=r.m_index,
        sobremodulacao=r.sobremodulacao,
    )
    esp = dict(f=f, vc=rms(vab), u=rms(uab), i1=rms(I1[:, 0]), i2=rms(I2[:, 0]), ic=rms(IC[:, 0]))
    return met, esp


def _h_motor(p, s, f1=60.0, com_carga=True):
    """Ganho Vmotor/Vinv e Vcap/Vinv e impedância vista pelo inversor (cabo + motor incluídos)."""
    rp = _rp(p)
    Zl1 = (p.R1 + s * p.L1) * rp / (p.R1 + s * p.L1 + rp)
    Zc = z_cap(p, s)
    A, B, C, D = _abcd_dm(p, s)
    Zm = _z_motor(p, s, f1) if com_carga else np.full_like(s, 1e9)
    Zin = (A * Zm + B) / (C * Zm + D)
    Zp = Zc * Zin / (Zc + Zin)
    Hc = Zp / (Zl1 + Zp)
    Hm = Hc * Zm / (A * Zm + B)
    return Hc, Hm, Zl1 + Zp


def resposta_frequencia(p: ParamCircuito, fmax=20000, n=2000, com_carga=True, Zcarga_R=None):
    """H(f) = Vc/U, Hm = Vmotor/U e Zin(f) vista pelo inversor (inclui cabo e motor)."""
    f = np.logspace(0, np.log10(fmax), n)
    s = 2j * np.pi * f
    H, Hm, Zin = _h_motor(p, s, com_carga=com_carga)
    return f, H, Hm, Zin


# Amplitudes típicas de harmônicas de baixa ordem na tensão do inversor causadas por tempo morto,
# queda nos semicondutores e ondulação do barramento (% da fundamental). Conservador.
# harmônicas 6k±1 do tempo morto / pulso mínimo (% da fundamental, decaimento ~1/h) – até h49 para cobrir a
# ressonância natural do LC com o motor em paralelo (achado na dupla checagem ATP: h35 a 41 Hz na A&W)
HARM_TEMPO_MORTO = {5: 1.5, 7: 1.0, 11: 0.6, 13: 0.5, 17: 0.3, 19: 0.25, 23: 0.2, 25: 0.15}
HARM_ALTAS = {29: 0.13, 31: 0.12, 35: 0.10, 37: 0.10, 41: 0.08, 43: 0.08, 47: 0.07, 49: 0.07}


def risco_ressonancia_baixa_ordem(p: ParamCircuito, fmin: float, fmax: float, passo: float = 0.25, harmonicas=None):
    """Varre a faixa de operação e calcula a distorção de saída causada pelas harmônicas de
    baixa ordem do inversor amplificadas pelo filtro. Retorna (thd_pior_%, f_pior, h_pior, ganho_pior)."""
    rp = _rp(p)
    pior = (0.0, fmin, 0, 0.0)
    for f1 in np.arange(fmin, fmax + 1e-9, passo):
        tot = 0.0
        hmax, gmax = 0, 0.0
        tab = harmonicas or HARM_TEMPO_MORTO
        hs = np.array(list(tab))
        _, Hm, _ = _h_motor(p, 2j * np.pi * hs * f1, f1)
        for h, a, g in zip(hs, tab.values(), np.abs(Hm)):
            tot += (a * g) ** 2
            if g > gmax:
                hmax, gmax = h, g
        thd = np.sqrt(tot)
        if thd > pior[0]:
            pior = (float(thd), float(f1), hmax, float(gmax))
    return pior
