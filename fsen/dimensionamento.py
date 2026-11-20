"""Dimensionamento e otimização de filtros senoidais LC / LCL para saída de inversores.

Critérios (consolidados de normas e prática de fabricantes):
- IEC 61800-2 / IEC 61800-5-1: sistema de acionamento e segurança do filtro de saída
- IEC TS 60034-25 e NEMA MG1 Part 30/31: tensão de pico e dv/dt no motor
- IEC 60076-6 / IEC 61558-2-20: reatores (indutância, elevação de temperatura, isolação)
- IEC 60831-1/2 (capacitores de potência) / IEC 61071 (capacitores p/ eletrônica de potência)
- IEC 61000-2-4 / IEEE 519: THD de referência (5 %) para tensão "senoidal"
- Prática Schaffner FN5040/5045, ABB, Danfoss MCC101, WEG/TDK:
    10·f_out,max <= f_res <= f_s/2 ; queda no indutor ~4–10 %; THDv saída <= 5 %;
    inversor com fs fixa e controle escalar (ou DTC com parâmetros do filtro).
"""
from __future__ import annotations
import math
import os
import json
import itertools
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any

import numpy as np
import yaml

from .modelos import Pedido
from .simulacao import ParamCircuito, PontoOperacao, simular, risco_ressonancia_baixa_ordem

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAT_PADRAO = os.path.join(RAIZ, "dados", "catalogo.yaml")
_NORMAS_CACHE: Dict[str, Any] = {}


def carregar_catalogo(caminho: str = CAT_PADRAO) -> Dict[str, Any]:
    with open(caminho, encoding="utf-8") as f:
        cat = yaml.safe_load(f)
    _NORMAS_CACHE.clear()
    _NORMAS_CACHE.update(cat.get("normas_capacitor") or {})
    return cat


# --------------------------------------------------------------------------------------
@dataclass
class BancoCapacitores:
    cap_id: str
    fabricante: str
    linha: str
    pn: str
    uf_unit: float
    v_unit: float
    ligacao: str          # "Delta" ou "Estrela"
    n_por_ramo: int       # capacitores em paralelo por ramo
    n_total: int
    c_y_uf: float         # capacitância equivalente estrela por fase
    c_ramo_uf: float      # capacitância por ramo físico
    v_cap_rms: float = 0.0
    i_unit_rms: float = 0.0
    i_unit_fund: float = 0.0
    i_unit_max: float = 0.0
    kvar_60: float = 0.0
    preco_unit: float = 0.0
    r_descarga_mohm: float = 0.0
    r_descarga_w: float = 0.0


@dataclass
class Indutor:
    nome: str
    l_uh: float
    uk_pct: float
    i_nom_a: float        # corrente térmica (rms total)
    i_fund_a: float
    i_pico_a: float
    i_sat_a: float
    ripple_pp_a: float
    ripple_rms_a: float
    f_chav_hz: float
    r_dc_mohm: float
    energia_j: float      # 3 fases
    perdas_w: float
    massa_kg: float
    dim_mm: List[int]     # L x A x P (estimado)
    custo: float
    queda_v_pct: float


@dataclass
class Amortecimento:
    rd_y_ohm: float          # resistência equivalente estrela (por fase)
    r_ramo_ohm: float        # resistor físico em série com cada ramo do banco (Δ: 3x Rd_y)
    q_alvo: float
    i_ramo_rms: float
    p_ramo_w: float          # dissipação por resistor
    p_total_w: float
    p_nominal_w: float       # potência nominal especificada (2x margem)
    custo: float
    tipo: str = "serie"      # "serie" (R em série com o banco) ou "rc_paralelo" (ramo Rd + Cd em paralelo com o banco)
    cd_y_uf: float = 0.0     # capacitância do ramo de amortecimento (Y equiv.)
    n_cd_por_ramo: int = 0   # capacitores de amortecimento por ramo (mesmo tipo do banco)
    rdp_y_ohm: float = 0.0


@dataclass
class Verificacao:
    item: str
    valor: str
    limite: str
    ok: bool
    referencia: str
    critico: bool = True


@dataclass
class Projeto:
    pedido: Dict[str, Any]
    topologia: str
    fs_hz: float
    vdc: float
    fr_hz: float
    l1: Indutor
    l2: Optional[Indutor]
    banco: BancoCapacitores
    pontos: List[Dict[str, Any]]           # métricas por ponto de operação
    verificacoes: List[Verificacao]
    aprovado: bool
    custo_componentes: float
    alternativas: List[Dict[str, Any]] = field(default_factory=list)
    avisos: List[str] = field(default_factory=list)
    notas_inversor: str = ""
    q_hf: float = 40.0
    lm_h: float = 0.0
    rm_ohm: float = 0.0
    amortecimento: Optional["Amortecimento"] = None
    condicoes_extremas: List[Dict[str, Any]] = field(default_factory=list)
    estresse_capacitor: Dict[str, Any] = field(default_factory=dict)
    sistema: Dict[str, Any] = field(default_factory=dict)

    def circuito(self) -> ParamCircuito:
        return ParamCircuito(L1=self.l1.l_uh * 1e-6, R1=self.l1.r_dc_mohm * 1e-3, C_y=self.banco.c_y_uf * 1e-6,
                             L2=(self.l2.l_uh * 1e-6 if self.l2 else 0.0),
                             R2=(self.l2.r_dc_mohm * 1e-3 if self.l2 else 0.0),
                             Q_hf=self.q_hf, fs_ref=self.fs_hz, Lm=self.lm_h, Rm=self.rm_ohm,
                             Rd=(self.amortecimento.rd_y_ohm if self.amortecimento and self.amortecimento.tipo == "serie" else 0.0),
                             Cd=(self.amortecimento.cd_y_uf * 1e-6 if self.amortecimento else 0.0),
                             Rdp=(self.amortecimento.rdp_y_ohm if self.amortecimento else 0.0))

    def to_dict(self):
        d = asdict(self)
        return d

    def salvar(self, caminho):
        with open(caminho, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2, default=_json_default)


def _json_default(o):
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    return str(o)


# --------------------------------------------------------------------------------------
def derating_fs(cat, ped, fs_hz):
    inv = cat["inversores"].get(_inv_chave(ped.inversor, cat), cat["inversores"]["GENERICO"])
    tab = inv.get("derating_fs", {2: 1.0, 4: 1.0, 8: 0.65, 12: 0.5})
    k = min(tab, key=lambda x: abs(float(x) - fs_hz / 1000))
    return float(tab[k]) if abs(float(k) - fs_hz / 1000) < 0.6 else 1.0


def perdas_indutor(cat, L, In, ripple_pp, fs):
    """Perdas (W, 3 fases) calibradas na linha Schaffner FN5040 (P = 170·E^0,85, E = ½·L·(√2·In)² por fase, fs = 3 kHz,
    ondulação ~45 %): 60 % cobre (escala com o tamanho) + 40 % núcleo (Steinmetz: ∝ ΔB²·f^1,5, ΔB ∝ ondulação relativa)."""
    ic = cat["indutor_custo"]
    e = 0.5 * L * (math.sqrt(2) * In) ** 2
    pref = ic.get("perda_k", 170.0) * e ** ic.get("perda_exp", 0.85)
    rr = ripple_pp / (math.sqrt(2) * In) if In else 0.45
    return pref * (0.6 + 0.4 * (rr / 0.45) ** 2 * (fs / 3000.0) ** 1.5)


def _fs_projeto(ped: Pedido, cat) -> (float, str):
    inv = cat["inversores"].get(_inv_chave(ped.inversor, cat), cat["inversores"]["GENERICO"])
    fs = ped.fs_khz or inv["fs_padrao_khz"]
    return fs * 1000.0, inv["notas"]


def _inv_chave(nome: str, cat) -> str:
    n = (nome or "").upper()
    for k in cat["inversores"]:
        tok = k.upper().split()[-1]
        if tok in n.replace("-", "").replace(" ", "") or k.upper() in n:
            return k
    return "GENERICO"


def pontos_operacao(ped: Pedido, vdc: float, fs: float) -> List[Dict[str, Any]]:
    """Pontos de verificação: f máx (V/f), f mín e nominal da placa do filtro (60 Hz, In)."""
    In = ped.corrente_a
    i_motor = ped.motor_corrente_a * max(ped.fator_servico, 1.0) if ped.motor_corrente_a else In
    i_op = min(In, i_motor)
    vf = ped.tensao_v / ped.freq_rede_hz
    pts = []
    fmax = ped.f_saida_max_hz or ped.freq_rede_hz
    fmin = ped.f_saida_min_hz or max(0.5 * fmax, 20)
    fp = ped.motor_fp or 0.85
    pts.append(dict(nome=f"Operação f máx ({fmax:g} Hz)", op=PontoOperacao(v_ll=min(vf * fmax, ped.tensao_v), f1=fmax,
                                                                           i_carga=i_op, fp=fp, vdc=vdc, fs=fs), critico_tensao=True))
    if abs(fmin - fmax) > 1:
        # bomba centrífuga: corrente cai ~ (f/fmax)^2 ; usa conservador (f/fmax)^1
        pts.append(dict(nome=f"Operação f mín ({fmin:g} Hz)", op=PontoOperacao(v_ll=vf * fmin, f1=fmin,
                                                                               i_carga=i_op * fmin / fmax, fp=fp, vdc=vdc, fs=fs), critico_tensao=True))
    if abs(fmax - ped.freq_rede_hz) > 1 or i_op < In:
        pts.append(dict(nome=f"Placa do filtro ({ped.freq_rede_hz:g} Hz, {In:g} A)", op=PontoOperacao(
            v_ll=ped.tensao_v, f1=ped.freq_rede_hz, i_carga=In, fp=fp, vdc=vdc, fs=fs), critico_tensao=False))
    return pts


def _arranjos_capacitor(cap, cat_proj, C_alvo_y, v_ll):
    """Gera arranjos Delta/Estrela com n capacitores por ramo próximos do alvo."""
    out = []
    for lig in ("Delta", "Estrela"):
        v_ramo = v_ll if lig == "Delta" else v_ll / math.sqrt(3)
        if v_ramo > cap["v_ac"] * cat_proj["vcap_max_pu"] / 1.0 * 0.98:
            continue
        fator = 3.0 if lig == "Delta" else 1.0
        n_ideal = C_alvo_y / (fator * cap["uf"] * 1e-6)
        for n in sorted({max(1, math.floor(n_ideal)), max(1, math.ceil(n_ideal))}):
            out.append((lig, n, fator * n * cap["uf"] * 1e-6))
    return out


def _custo_indutor(cat, energia_j):
    ic = cat["indutor_custo"]
    return ic["base"] + ic["k_energia"] * energia_j


def _dim_indutor(cat, massa):
    vol = massa / cat["indutor_custo"]["densidade_kg_m3"]
    a = (vol / (1.6 * 1.2 * 0.8)) ** (1 / 3)
    return [int(round(1.6 * a * 1000, -1)), int(round(1.2 * a * 1000, -1)), int(round(0.8 * a * 1000, -1))]


def parametros_sistema(ped: Pedido, cat) -> Dict[str, Any]:
    """Modelo do motor (placa) e do cabo (seção, paralelos, comprimento) usados na simulação."""
    from .mecanica import secao_cabo
    w = 2 * math.pi * ped.freq_rede_hz
    In = ped.corrente_a
    mm = cat.get("motor_modelo", {})
    i_m = (ped.motor_corrente_a or In) * max(ped.fator_servico, 1.0)
    Zbm = ped.tensao_v / math.sqrt(3) / i_m
    kw = ped.motor_kw or (ped.motor_cv * 0.7355 if ped.motor_cv else math.sqrt(3) * ped.tensao_v * i_m * 0.85 * 0.93 / 1000)
    sec, par = (ped.cabo_secao_mm2, ped.cabo_paralelos or 1) if ped.cabo_secao_mm2 else secao_cabo(cat, i_m)
    tab = {int(k): v for k, v in cat.get("cabos_parametros", {}).items()}
    if tab:
        k = min(tab, key=lambda x: abs(x - sec))
        R, L, Cpg, Cpp = tab[k]
    else:
        R, L, Cpg, Cpp = 0.16, 0.25, 370, 185
    if not ped.cabo_blindado:
        Cpg, Cpp = Cpg * 0.45, Cpp * 0.6
    comp = ped.cabo_m or cat.get("cabo_comprimento_padrao_m", 30)
    mc = cat.get("modo_comum", {})
    return dict(Lm=mm.get("l_disp_pu", 0.15) * Zbm / w, Rm=mm.get("r_pu", 0.012) * Zbm,
                Cwf=mm.get("cwf_nf_por_raiz_kw", 0.35) * 1e-9 * math.sqrt(max(kw, 0.5)), bvr=mm.get("bvr", 0.04),
                cabo_m=comp, cabo_R_km=R / par, cabo_L_km=L * 1e-3 / par, cabo_Cpg_km=Cpg * 1e-9 * par, cabo_Cpp_km=Cpp * 1e-9 * par,
                L0_fator=mc.get("L0_fator", 0.10), C_emc=mc.get("C_emc_uF", 0.5) * 1e-6, L_terra_km=mc.get("L_terra_mH_km", 0.4) * 1e-3,
                R_pe_km=mc.get("R_pe_ohm_km", 0.3), estrela_ao_cc=bool(ped.estrela_ao_cc),
                _info=dict(cabo_secao_mm2=k if tab else sec, cabo_paralelos=par, cabo_m=comp, motor_kw=round(kw, 1),
                           Cwf_nF=round(mm.get("cwf_nf_por_raiz_kw", 0.35) * math.sqrt(max(kw, 0.5)), 2)))


def avaliar(ped: Pedido, cat, L1, cap, arranjo, fs, vdc, L2=0.0, rd=0.0, pts_por_portadora=120, detalhado=False, cd=0.0, rdp=0.0,
            sistema=None, extra=None):
    lig, n, Cy = arranjo
    In = ped.corrente_a
    Zb = ped.tensao_v / math.sqrt(3) / In
    sistema = sistema or parametros_sistema(ped, cat)
    sp = {k: v for k, v in sistema.items() if not k.startswith("_")}
    if lig != "Estrela":
        sp["estrela_ao_cc"] = False
    sp.update(extra or {})
    Lm, Rm = sp["Lm"], sp["Rm"]
    R1 = 0.003 * Zb       # ~0,3 % (cobre)
    q = 40.0
    p = ParamCircuito(L1=L1, R1=R1, C_y=Cy, L2=L2, R2=(0.003 * Zb if L2 else 0.0), Q_hf=q, fs_ref=fs, Rd=rd, Cd=cd, Rdp=rdp, **sp)
    resultados = []
    for pt in pontos_operacao(ped, vdc, fs):
        r = simular(p, pt["op"], pts_por_portadora=pts_por_portadora)
        m = dict(r.metricas)
        m["nome"] = pt["nome"]
        m["f1"] = pt["op"].f1
        m["v_alvo"] = pt["op"].v_ll
        m["i_carga"] = pt["op"].i_carga
        m["critico_tensao"] = pt["critico_tensao"]
        if detalhado:
            m["_sim"] = r
        resultados.append(m)
    return p, resultados, (Lm, Rm, q)


def verificar(ped: Pedido, cat, p: ParamCircuito, res, cap, arranjo, fs, fr) -> List[Verificacao]:
    cp = cat["projeto_padrao"]
    lig, n, Cy = arranjo
    In = ped.corrente_a
    v = []
    fmax = ped.f_saida_max_hz or ped.freq_rede_hz
    thd = max(r["thd_v_saida_pct"] for r in res)
    v.append(Verificacao("THD tensão de saída (até 4·fs)", f"{thd:.2f} %", f"≤ {cp['thd_v_max_pct']:.1f} %", thd <= cp["thd_v_max_pct"],
                         "IEC 61000-2-4 cl.2 / prática fabricantes (onda 'senoidal')"))
    v.append(Verificacao("Ressonância ≥ 10·f saída máx", f"{fr:.0f} Hz", f"≥ {cp['fr_min_mult_fout'] * fmax:.0f} Hz",
                         fr >= cp["fr_min_mult_fout"] * fmax, "Prática Schaffner/ABB/Danfoss"))
    v.append(Verificacao("Ressonância ≤ fs/2", f"{fr:.0f} Hz", f"≤ {cp['fr_max_frac_fs'] * fs:.0f} Hz",
                         fr <= cp["fr_max_frac_fs"] * fs, "Estabilidade do controle do inversor"))
    fmin = ped.f_saida_min_hz or max(0.5 * fmax, 20)
    # robustez: avalia também os cantos de tolerância (L ±5 %, C −5/+10 %) – o pior caso decide
    import dataclasses
    thd_lo, f_lo, h_lo, g_lo = 0.0, fmin, 0, 0.0
    for kL, kC in cp.get("tolerancias_lc", [[1, 1], [0.95, 0.95], [1.05, 1.10], [0.95, 1.10], [1.05, 0.95]]):
        pt = dataclasses.replace(p, L1=p.L1 * kL, C_y=p.C_y * kC, Cd=p.Cd * kC)
        r_ = risco_ressonancia_baixa_ordem(pt, fmin, fmax, passo=0.5)
        if r_[0] > thd_lo:
            thd_lo, f_lo, h_lo, g_lo = r_
    lim_lo = cp.get("thd_baixa_ordem_max_pct", 4.0)
    # v1.8: validação com filtros fabricados (IHR, SENAI, Gelluns) e de catálogo (Schaffner FN5040): o pior caso teórico
    # (velocidade exata em que uma harmônica cai na ressonância + tolerâncias) aparece em TODO LC sem amortecimento e não
    # corresponde a falhas em campo → vira ALERTA. O que é crítico é a CONSEQUÊNCIA física (capacitor) e o THD nominal.
    v.append(Verificacao("Amplificação de harmônicas de baixa ordem (tempo morto) – pior caso teórico (velocidade exata + tolerâncias de L e C)",
                         f"{thd_lo:.2f} % (pior em {f_lo:.1f} Hz, h{h_lo}, ganho {g_lo:.2f})", f"≤ {lim_lo:.1f} % (alerta)",
                         thd_lo <= lim_lo, "Robustez à ressonância: h = 6k±1 com amplitudes típicas de tempo morto. Validação v1.8: "
                         "filtros LC fabricados (SENAI/IHR medidos com Dranetz) e Schaffner FN5040 também têm este ponto; "
                         "consequência no capacitor verificada abaixo", critico=False))
    # v1.9.5: as medições de calibração (SENAI 40/20 µF, IHR) foram SEM motor (confirmado pelo usuário). Elas validam o filtro,
    # o inversor (tabela de baixa ordem) e o amortecimento (Q 4). Em operação o motor está ligado → critério crítico COM motor;
    # sem motor (teste/comissionamento a vazio) vira alerta, e o capacitor é verificado nos dois casos.
    thd_nom = risco_ressonancia_baixa_ordem(p, fmax, fmax, passo=1.0, com_motor_desligado=False)[0]
    thd_sem_motor = risco_ressonancia_baixa_ordem(p, fmax, fmax, passo=1.0)[0]
    thd_pwm_fmax = max((r["thd_v_saida_pct"] for r in res if abs(r["f1"] - fmax) < 0.6), default=thd)
    thd_tot = math.hypot(thd_pwm_fmax, thd_nom)
    thd_tot_sm = math.hypot(thd_pwm_fmax, thd_sem_motor)
    v.append(Verificacao(f"THD total no motor @ {fmax:g} Hz (PWM + baixa ordem, valores nominais)", f"{thd_tot:.2f} %",
                         f"≤ {cp['thd_v_max_pct'] + 1:.1f} %", thd_tot <= cp["thd_v_max_pct"] + 1,
                         "Calibrado com medições Dranetz (formas de onda) a 60 Hz: SENAI 958 µH/40 µF Y 7,2 %; SENAI 958 µH/20 µF Y 4,9 %; "
                         "IHR 1586 µH/20 µF Y 4,0 % – medições SEM motor; com motor o valor é calculado (modelo do motor)"))
    v.append(Verificacao(f"THD na saída do filtro SEM motor @ {fmax:g} Hz (teste/comissionamento a vazio)", f"{thd_tot_sm:.2f} %",
                         f"≤ {cp['thd_v_max_pct'] + 1:.1f} % (alerta)", thd_tot_sm <= cp["thd_v_max_pct"] + 1,
                         "Modelo calibrado nas medições Dranetz sem motor (SENAI 40 µF: previsto 7,2 % × medido 7,2 %). "
                         "Só afeta a operação sem carga; o capacitor é verificado abaixo também neste caso", critico=False))
    _lo = dict(thd=thd_lo, f=f_lo, h=h_lo)
    from .simulacao import HARM_ALTAS
    thd_hi, f_hi, h_hi, g_hi = risco_ressonancia_baixa_ordem(p, fmin, fmax, passo=0.5, harmonicas=HARM_ALTAS)
    v.append(Verificacao("Ressonância natural (LC ∥ motor) × harmônicas altas h29–h49 do tempo morto",
                         f"{thd_hi:.2f} % (pior em {f_hi:.1f} Hz, h{h_hi}, ganho {g_hi:.1f})", "≤ 3,0 % (alerta)", thd_hi <= 3.0,
                         "Achado na dupla checagem ATP: LC sem amortecimento tem ganho alto na ressonância natural; "
                         "se o alerta persistir, medir em campo ou usar amortecimento RC", critico=False))
    vpk = max(r.get("vpk_motor", r["vpk_saida"]) for r in res)
    lim_vpk = ped.vpk_max_v or 1000.0
    v.append(Verificacao("Tensão de pico no motor (L-L)", f"{vpk:.0f} V", f"≤ {lim_vpk:.0f} V", vpk <= lim_vpk,
                         "Especificação do cliente / NEMA MG1 Pt.30 (1000 V) / IEC TS 60034-25"))
    dvdt = max(r.get("dvdt_motor_v_us", r["dvdt_saida_v_us"]) for r in res)
    lim_dvdt = ped.dvdt_max_v_us or 500.0
    v.append(Verificacao("dv/dt no motor", f"{dvdt:.1f} V/µs", f"≤ {lim_dvdt:.0f} V/µs", dvdt <= lim_dvdt,
                         "Especificação do cliente / IEC TS 60034-25"))
    if ped.rise_time_min_us:
        tr = 0.8 * vpk / max(dvdt, 1e-6)   # tempo 10-90 % equivalente
        v.append(Verificacao("Rise time (10–90 %)", f"{tr:.1f} µs", f"> {ped.rise_time_min_us:g} µs", tr > ped.rise_time_min_us,
                             "Especificação do cliente"))
    m_max = cp.get("m_max_sobremodulacao", 1.21)
    v_min = cp.get("tensao_motor_min_pu", 0.90)
    for r in res:
        v_disp = min(1.0, m_max / r["m_index"])
        txt = f"{100 * v_disp:.1f} % do V/f (m = {r['m_index']:.3f}{' – sobremodulação' if r['m_index'] > 1.155 else ''})"
        if r["critico_tensao"]:
            v.append(Verificacao(f"Tensão disponível no motor – {r['nome']}", txt, f"≥ {100 * v_min:.0f} %", v_disp >= v_min,
                                 "Queda no filtro x reserva de tensão do inversor (Vcc = 1,35·Vrede)"))
        elif v_disp < 1.0:
            v.append(Verificacao(f"Tensão disponível no motor – {r['nome']}", txt, "100 %", False,
                                 "Na placa (60 Hz/In) o motor opera com tensão reduzida (enfraquecimento de campo leve)", critico=False))
    queda = 100 * In * 2 * math.pi * fmax * (p.L1 + p.L2) / (ped.tensao_v / math.sqrt(3))
    v.append(Verificacao("Queda de tensão no(s) indutor(es) @ f máx, In", f"{queda:.1f} %", f"≤ {cp['uk_max_pct']:.0f} %",
                         queda <= cp["uk_max_pct"], "IEC 61800-2 / prática (4–10 %)"))
    i1max = max(r["i1_rms"] for r in res)
    lim_inv = (ped.inversor_corrente_a or In) * derating_fs(cat, ped, fs)
    v.append(Verificacao("Corrente do inversor (com filtro)", f"{i1max:.1f} A", f"≤ {lim_inv:.0f} A", i1max <= lim_inv * 1.0001,
                         "Corrente nominal do inversor"))
    icf = max(r["icap_y_fund"] for r in res)
    v.append(Verificacao("Corrente capacitiva fundamental", f"{100 * icf / In:.1f} % In", f"≤ {cp['ic_fund_max_pct']:.0f} %",
                         100 * icf / In <= cp["ic_fund_max_pct"], "Carga reativa no inversor"))
    rpp = max(r["ripple_pp"] for r in res)
    lim_r = cp["ripple_pp_max_pct"] / 100 * In * math.sqrt(2)
    v.append(Verificacao("Ondulação de corrente no indutor (p-p)", f"{rpp:.0f} A", f"≤ {lim_r:.0f} A", rpp <= lim_r,
                         "Prática Schaffner/ABB (uk ~7–9 %): perdas HF, ruído, corrente nos capacitores"))
    # capacitores
    v_ramo_rms = max(r["v_saida_ll_fund"] * math.sqrt(1 + (r["thd_v_saida_pct"] / 100) ** 2) for r in res)
    i_y = max(r.get("icap_main_y_rms", r["icap_y_rms"]) for r in res)
    if lig == "Estrela":
        v_ramo_rms /= math.sqrt(3)
        i_unit = i_y / n
    else:
        i_unit = i_y / math.sqrt(3) / n
    lc = limites_capacitor(cap, cat, extremo=bool(cat.get("_extremo")))
    v.append(Verificacao(f"Tensão RMS no capacitor ({lig}) – {lc['norma_txt']}", f"{v_ramo_rms:.0f} V", f"≤ {lc['v_rms']:.0f} V",
                         v_ramo_rms <= lc["v_rms"] * 1.0001,
                         "IEC 61071: URMS do datasheet" if lc["norma"] == "IEC61071" else "IEC 60831-1 cl.20 (1,10·UN 8 h/24 h)"))
    imax = lc["imax"]
    v.append(Verificacao(f"Corrente RMS por capacitor (fund.+HF) – {lc['norma_txt']}", f"{i_unit:.2f} A ({100 * i_unit / imax:.0f} % Imax)",
                         f"≤ {imax:.2f} A", i_unit <= imax, f"Imax: {lc['imax_fonte']}"))
    v.extend(verificar_capacitor_termico(cat, cap, lig, n, res))
    # consequência do pior caso de ressonância de baixa ordem no capacitor (crítico)
    if _lo["thd"] > 0 and _lo["h"]:
        f0 = ped.freq_rede_hz or 60.0
        v_fase = ped.tensao_v / math.sqrt(3) * min(1.0, _lo["f"] / f0)
        vh_unit = _lo["thd"] / 100 * v_fase * (math.sqrt(3) if lig == "Delta" else 1.0)
        ih_unit = vh_unit * 2 * math.pi * _lo["h"] * _lo["f"] * cap["uf"] * 1e-6
        i_tot = math.hypot(i_unit, ih_unit)
        vpk_tot = estresse_capacitor(cat, cap, lig, n, res)["vpk"] + math.sqrt(2) * vh_unit
        ok_r = i_tot <= imax and vpk_tot <= lc["vpk"]
        v.append(Verificacao("Capacitor no pior caso de ressonância de baixa ordem (I e Û com a harmônica amplificada)",
                             f"{i_tot:.2f} A ({100 * i_tot / imax:.0f} % Imax) | Û {vpk_tot:.0f} V",
                             f"≤ {imax:.2f} A | ≤ {lc['vpk']:.0f} V", ok_r,
                             f"h{_lo['h']} a {_lo['f']:.1f} Hz com {_lo['thd']:.1f} % sobre o capacitor; {lc['norma_txt']}/datasheet"))
    if cat.get("verificar_tambem_ieee18", True) and lc["norma"] == "IEC60831":
        e_ = estresse_capacitor(cat, cap, lig, n, res)
        v.append(verificar_ieee18(cap, lig, n, res, v_ramo_rms, i_unit, e_["vpk"]))
    v.extend(verificar_modo_comum(ped, cat, res))
    if p.Cd > 0:
        nd = max(1, round(p.Cd / (p.C_y / n)))
        i_d = max(r.get("icap_d_y_rms", 0) for r in res)
        i_du = (i_d / math.sqrt(3) if lig == "Delta" else i_d) / nd
        v.append(Verificacao("Corrente RMS por capacitor do ramo de amortecimento", f"{i_du:.2f} A", f"≤ {imax:.2f} A", i_du <= imax,
                             f"Imax: {lc['imax_fonte']}"))
    pam = max(r.get("p_amort_w", 0) for r in res)
    if pam > 0:
        lim_pam = cp.get("p_amort_max_pct_s", 0.25) / 100 * math.sqrt(3) * ped.tensao_v * In
        v.append(Verificacao("Perdas no amortecimento", f"{pam:.0f} W", f"≤ {lim_pam:.0f} W", pam <= lim_pam,
                             "Eficiência / aquecimento da caixa", critico=False))
    return v


NOMES_NORMA = {"IEC60831": "IEC 60831-1/2", "IEC61071": "IEC 61071", "IEEE18": "IEEE Std 18"}


def limites_capacitor(cap, cat=None, extremo=False):
    """Limites de suportabilidade do capacitor unitário conforme a NORMA DO TIPO do capacitor + datasheet.
    IEC 61071 (eletrônica de potência / filtro AC, ex. B32361 'PEC'): Irms, Û, Î/C, ponto quente do datasheet.
    IEC 60831 (correção de FP, ex. PhiCap): 1,10·UN, Imax = fator do datasheet (≥ 1,3·IN), Û ≤ 1,2·√2·UN.
    IEEE 18: 1,10 V, 1,20 Vpico, 1,35 I, 1,35 kvar (informativo p/ capacitores de potência)."""
    cat = cat or {}
    normas = cat.get("normas_capacitor", {})
    ct = cat.get("capacitor_termico", {})
    norma = (cap.get("norma") or "IEC60831").replace(" ", "").replace("-1/2", "")
    nb = normas.get(norma, {})
    w = 2 * math.pi * 60
    i_n = cap.get("v_ac", 480) * w * cap.get("uf", 20) * 1e-6
    fat = cap.get("imax_fator") or nb.get("i_rms_fator_padrao") or (cat.get("projeto_padrao", {}).get("icap_max_fator_iec60831", 1.3))
    imax = cap.get("imax_a") or fat * i_n
    v_rms = cap.get("v_ac", 480) * (cap.get("vmax_cont_pu") or nb.get("v_rms_pu") or 1.10)
    if cap.get("vn_pico_v"):
        vpk = cap["vn_pico_v"]
    else:
        vpk = (nb.get("v_pico_pu") or ct.get("vpk_max_pu", 1.2)) * (1 if norma == "IEC61071" else math.sqrt(2)) * cap.get("v_ac", 480)
    if extremo and nb.get("v_pico_extremo_pu"):
        vpk *= nb["v_pico_extremo_pu"]
        v_rms *= nb["v_pico_extremo_pu"]
    dvdt = (cap.get("ipk_a") / (cap.get("uf", 20) * 1e-6) / 1e6) if cap.get("ipk_a") else (nb.get("dvdt_v_us") or ct.get("dvdt_max_v_us", 20))
    thot = cap.get("t_hotspot_max_c") or nb.get("t_hotspot_max_c") or ct.get("t_hotspot_max_c", 70)
    fonte = "datasheet" if cap.get("imax_a") else (f"datasheet ({fat:g}·IN)" if cap.get("imax_fator") else f"{NOMES_NORMA.get(norma, norma)} ({fat:g}·IN)")
    return dict(norma=norma, norma_txt=NOMES_NORMA.get(norma, norma), i_n=i_n, imax=imax, imax_fonte=fonte, v_rms=v_rms, vpk=vpk,
                dvdt=dvdt, t_hot=thot, vida_h=cap.get("vida_h") or ct.get("vida_ref_h", 100000),
                t_vida=cap.get("t_vida_ref_c") or ct.get("t_ref_c", 70), q_pu=nb.get("q_pu"), extremo=extremo)


def verificar_ieee18(cap, lig, n, res, v_ramo_rms, i_unit, vpk):
    """IEEE Std 18 cl. 5 – limites contínuos (informativo; IEEE 18 é para capacitores de potência shunt)."""
    C = cap["uf"] * 1e-6
    k_i = (1 / math.sqrt(3) if lig == "Delta" else 1.0) / n
    sf = max(r.get("icap_sum_i2_sobre_f", r["icap_y_rms"] ** 2 / 60) for r in res) * k_i ** 2
    q = sf / (2 * math.pi * C)
    qn = cap["v_ac"] ** 2 * 2 * math.pi * 60 * C
    i_n = cap["v_ac"] * 2 * math.pi * 60 * C
    ok = v_ramo_rms <= 1.10 * cap["v_ac"] and vpk <= 1.2 * math.sqrt(2) * cap["v_ac"] and i_unit <= 1.35 * i_n and q <= 1.35 * qn
    return Verificacao("IEEE 18 (informativo): V ≤ 110 %, Vpico ≤ 120 %, I ≤ 135 %, kvar ≤ 135 %",
                       f"V {100 * v_ramo_rms / cap['v_ac']:.0f} % | Vpk {100 * vpk / (math.sqrt(2) * cap['v_ac']):.0f} % | "
                       f"I {100 * i_unit / i_n:.0f} % | Q {100 * q / qn:.0f} %", "110/120/135/135 %", ok,
                       "IEEE Std 18-2012 cl. 5 (limites de contingência; não é a norma do capacitor de filtro)", critico=False)


def estresse_capacitor(cat, cap, lig, n, res):
    """Suportabilidade do capacitor unitário no pior ponto: pico de tensão, perdas (ESR + dielétrico), ponto quente, vida."""
    ct = cat.get("capacitor_termico", {})
    cp = cat["projeto_padrao"]
    k_i = (1 / math.sqrt(3) if lig == "Delta" else 1.0) / n          # corrente do Y equiv. → corrente por capacitor
    C_u = cap["uf"] * 1e-6
    esr = cap.get("esr_mohm", 3.0) * 1e-3
    tand = cap.get("tan_delta", 0.0002)
    rth = cap.get("rth_k_w", 12.0)
    pior = None
    for r in res:
        s0 = r.get("icap_sum_i2", r["icap_y_rms"] ** 2) * k_i ** 2
        sf = r.get("icap_sum_i2_sobre_f", s0 / 60) * k_i ** 2
        perdas = esr * s0 + tand / (2 * math.pi * C_u) * sf
        vpk = r.get("vpk_cap_ll" if lig == "Delta" else "vpk_cap_ph", 0.0)
        d = dict(ponto=r["nome"], perdas_w=perdas, vpk=vpk, irms=math.sqrt(s0))
        if pior is None or perdas > pior["perdas_w"]:
            pior = {**d, "vpk": max(vpk, (pior or {}).get("vpk", 0))}
        else:
            pior["vpk"] = max(pior["vpk"], vpk)
    t_int = cp.get("amb_max_c", 40) + cp.get("delta_t_painel_k", 15)
    t_hot = t_int + pior["perdas_w"] * rth
    lc = limites_capacitor(cap, cat)
    vida = lc["vida_h"] * 2 ** ((lc["t_vida"] - t_hot) / ct.get("k_dobra_c", 7))
    return dict(**pior, t_interno_c=t_int, t_hotspot_c=t_hot, vida_h=vida)


def verificar_capacitor_termico(cat, cap, lig, n, res):
    """Suportabilidade harmônica/térmica conforme a norma do tipo do capacitor (IEC 61071 ou IEC 60831) + datasheet."""
    e = estresse_capacitor(cat, cap, lig, n, res)
    lc = limites_capacitor(cap, cat, extremo=bool(cat.get("_extremo")))
    dv = max(r.get("dvdt_saida_v_us", 0) for r in res)
    if lc["norma"] == "IEC61071":
        ref_v = f"IEC 61071: Û recorrente ≤ UN {cap.get('vn_pico_v') or '√2·URMS'} V pico (datasheet)" + (" × 1,10 (curta duração)" if lc["extremo"] else "")
        ref_dv = f"IEC 61071: dv/dt ≤ Î/C = {cap.get('ipk_a', 0):g} A / {cap['uf']:g} µF (datasheet)"
    else:
        ref_v = "IEC 60831-1: Û ≤ 1,2·√2·UN (harmônicas incluídas) / datasheet"
        ref_dv = "Datasheet do capacitor de potência (não é capacitor de snubber)"
    return [
        Verificacao(f"Pico de tensão no capacitor ({lig}, harmônicas incluídas)", f"{e['vpk']:.0f} V", f"≤ {lc['vpk']:.0f} V",
                    e["vpk"] <= lc["vpk"], ref_v),
        Verificacao(f"Ponto quente do capacitor ({e['perdas_w']:.2f} W/unid., ar interno {e['t_interno_c']:.0f} °C)",
                    f"{e['t_hotspot_c']:.1f} °C", f"≤ {lc['t_hot']:.0f} °C", e["t_hotspot_c"] <= lc["t_hot"],
                    f"Perdas Rs·ΣI² + tanδ0 dielétrico; Rth {cap.get('rth_k_w', 12):g} K/W; limite {lc['norma_txt']}/datasheet"),
        Verificacao("Vida estimada do capacitor", f"{e['vida_h'] / 1000:.0f} mil h", "≥ 100 mil h", e["vida_h"] >= 100000,
                    f"Datasheet: {lc['vida_h'] / 1000:.0f} mil h a {lc['t_vida']:.0f} °C ponto quente; dobra a cada 7 K a menos", critico=False),
        Verificacao("dv/dt nos capacitores", f"{dv:.1f} V/µs", f"≤ {lc['dvdt']:.0f} V/µs", dv <= lc["dvdt"], ref_dv),
    ]


def verificar_modo_comum(ped, cat, res):
    mm = cat.get("motor_modelo", {})
    mc = cat.get("modo_comum", {})
    r = max(res, key=lambda x: x.get("i_terra_rms", 0))
    if "i_terra_rms" not in r:
        return []
    ig_lim = mc.get("i_terra_rms_max_pct", 2.0) / 100 * ped.corrente_a
    vb_lim = mm.get("v_mancal_max_v", 10)
    return [
        Verificacao("Tensão de modo comum no motor (enrolamento–carcaça)", f"{r['vcm_motor_rms']:.0f} V RMS / {r['vcm_motor_pk_borda']:.0f} V pico",
                    "informativo", True, "O filtro senoidal LC NÃO atenua o modo comum (IEC TS 60034-25)", critico=False),
        Verificacao("Corrente de terra (PE/blindagem) – RMS até 4·fs", f"{r['i_terra_rms']:.2f} A", f"≤ {ig_lim:.1f} A",
                    r["i_terra_rms"] <= ig_lim, "Capacitância do cabo + motor; filtro EMC do inversor", critico=False),
        Verificacao("Corrente de terra – pico nas comutações (estimativa)", f"{r['i_terra_pk_borda']:.1f} A", "informativo", True,
                    "Degrau Vcc/3 sobre a impedância de surto de modo comum do cabo", critico=False),
        Verificacao("Tensão estimada no mancal", f"{r['v_mancal_pk']:.1f} V pico", f"≤ {vb_lim:g} V", r["v_mancal_pk"] <= vb_lim,
                    "BVR típico; acima do limite: mancal isolado (lado oposto), escova de aterramento do eixo ou filtro de modo comum",
                    critico=False),
    ]


def condicoes_extremas(ped: Pedido, cat, c, fs) -> List[Dict[str, Any]]:
    """Teste de robustez da configuração escolhida: tolerâncias e condições de rede/instalação."""
    base = parametros_sistema(ped, cat)
    casos = [
        ("Nominal", dict(), 1.0, 1.0, 1.0),
        ("Rede +10 %", dict(), 1.0, 1.0, 1.10),
        ("Rede −10 %", dict(), 1.0, 1.0, 0.90),
        ("L −5 %, C −5 % (envelhecido)", dict(), 0.95, 0.95, 1.0),
        ("L +5 %, C +10 %", dict(), 1.05, 1.10, 1.0),
        ("Cabo 2× mais longo", dict(cabo_m=base["cabo_m"] * 2), 1.0, 1.0, 1.0),
        ("Sem cabo (filtro junto ao motor)", dict(cabo_m=0.0), 1.0, 1.0, 1.0),
    ]
    out = []
    lig, nn, Cy = c["arr"]
    import copy
    cat_n = copy.deepcopy(cat)
    cat_n["projeto_padrao"]["tolerancias_lc"] = [[1, 1]]       # o canto já aplica a tolerância: não duplicar
    cat_n["_extremo"] = True    # condição de curta duração: sobretensões admissíveis da norma do capacitor (IEC 61071: 1,10·UN)
    for nome, extra, kL, kC, kV in casos:
        ped2 = Pedido.from_dict({**ped.to_dict(), "tensao_v": ped.tensao_v})
        arr2 = (lig, nn, Cy * kC)
        vdc = 1.35 * ped.tensao_v * kV
        p, res, _ = avaliar(ped2, cat, c["L1"] * kL, c["cap"], arr2, fs, vdc, L2=c["L2"], rd=c["rd"], cd=c.get("cd", 0) * kC,
                            rdp=c.get("rdp", 0), pts_por_portadora=24, sistema=base, extra=extra)
        fr = 1 / (2 * math.pi * math.sqrt(c["L1"] * kL * Cy * kC))
        ver = verificar(ped2, cat_n, p, res, c["cap"], arr2, fs, fr)
        e = estresse_capacitor(cat, c["cap"], lig, nn, res)
        out.append(dict(condicao=nome, fr_Hz=round(fr), thd_motor=round(max(r.get("thd_v_motor_pct", r["thd_v_saida_pct"]) for r in res), 2),
                        vpk_motor=round(max(r.get("vpk_motor", 0) for r in res)),
                        m_max=round(max(r["m_index"] for r in res if r["critico_tensao"]), 3),
                        i_cap=round(e["irms"], 2), t_cap=round(e["t_hotspot_c"], 1),
                        baixa_ordem=next((v.valor.split(" ")[0] for v in ver if v.item.startswith("Amplificação")), "-"),
                        i_terra=round(max(r.get("i_terra_rms", 0) for r in res), 2),
                        aprovado=all(v.ok for v in ver if v.critico),
                        falhas="; ".join(v.item for v in ver if v.critico and not v.ok)))
    return out


def dimensionar(ped: Pedido, cat=None, rapido=False, verbose=False, modo="global", log=None, topologias=None, capacitores=None,
                ligacoes=None) -> Projeto:
    """modo="global": otimização multiobjetivo completa (padrão); modo="rapido": busca por menor custo de componentes."""
    cat = cat or carregar_catalogo()
    cp = cat["projeto_padrao"]
    if modo == "global":
        from .otimizacao import otimizar_global
        r = otimizar_global(ped, cat, log=log or (print if verbose else (lambda m: None)), topologias=topologias,
                            capacitores=capacitores, ligacoes=ligacoes)
        best = r["melhor"]
        c = best["_c"]
        fs = float(best["fs_khz"]) * 1000
        lcl = c.get("L2", 0) > 0
        w = 2 * math.pi * ped.freq_rede_hz
        Zb = ped.tensao_v / math.sqrt(3) / ped.corrente_a
        notas_inv = cat["inversores"].get(_inv_chave(ped.inversor, cat), cat["inversores"]["GENERICO"])["notas"]
        df = r["df"]
        top = df[df.viavel].sort_values("nota", ascending=False).head(12)
        alts = [dict(uk=x.uk_pct, L1_uH=x.L1_uH, L2_uH=x.L2_uH, capacitor=x.capacitor, ligacao=x.ligacao, n_por_ramo=x.n_por_ramo,
                     Rd_y_ohm=x.Rd_ramo_ohm, Q_amort=x.Q_amort, C_y_uF=x.C_y_uF, fr_Hz=x.fr_Hz, custo_est=x.custo_total,
                     thd_pct=x.thd_pct, aprovado=True, falhas=0, nota=x.nota, fs_khz=x.fs_khz) for x in top.itertuples()]
        avisos = [] if bool(best["viavel"]) else ["Nenhuma configuração do espaço de busca atendeu a todos os critérios críticos: "
                                                   f"apresentada a de menor nº de falhas ({best['falhas']})."]
        proj = _construir_projeto(ped, cat, cp, c, fs, 1.35 * ped.tensao_v, lcl, Zb, w, notas_inv, alts, avisos)
        proj.alternativas = alts
        proj._otimizacao = df.drop(columns=["_c"])
        from .otimizacao import TOPOLOGIAS
        proj._topologias_avaliadas = r.get("topologias", [])
        proj.topologia = c.get("topo", "LC")
        if len(proj._topologias_avaliadas) > 1:
            proj.avisos.append("A topologia padrão (LC sem resistor) não atendeu a todos os critérios; a cascata avaliou: "
                               + ", ".join(TOPOLOGIAS[t]["nome"] for t in proj._topologias_avaliadas) + ".")
        return proj
    fs, notas_inv = _fs_projeto(ped, cat)
    vdc = 1.35 * ped.tensao_v
    In = ped.corrente_a * cp["margem_corrente"]
    w = 2 * math.pi * ped.freq_rede_hz
    Zb = ped.tensao_v / math.sqrt(3) / In
    fmax = ped.f_saida_max_hz or ped.freq_rede_hz
    fr_min = cp["fr_min_mult_fout"] * fmax
    fr_max = cp["fr_max_frac_fs"] * fs

    caps = [c for c in cat["capacitores"]]
    pref = cat.get("capacitor_preferido")
    caps.sort(key=lambda c: (c["id"] != pref,))
    lcl = ped.topologia.upper() == "LCL"
    razao_l2 = 0.3

    candidatos = []
    for relax in (1.0, 1.6, 3.0, 1e9):
        candidatos = _gerar_candidatos(ped, cat, cp, caps, pref, lcl, razao_l2, In, Zb, w, fs, vdc, fr_min, fr_max, relax)
        if candidatos:
            break
    if not candidatos:
        raise ValueError("Nenhum arranjo de capacitores do catálogo é compatível com esta tensão/corrente. "
                         "Cadastre capacitores com tensão adequada (ex.: 690 V em estrela) no catálogo.")
    candidatos.sort(key=lambda c: c["custo_est"])
    if verbose:
        print(f"{len(candidatos)} candidatos; fs={fs:.0f} Hz, fr in [{fr_min:.0f}, {fr_max:.0f}]")
    return _escolher(ped, cat, cp, candidatos, fs, vdc, lcl, Zb, w, notas_inv, rapido)


def _gerar_candidatos(ped, cat, cp, caps, pref, lcl, razao_l2, In, Zb, w, fs, vdc, fr_min, fr_max, relax):
    candidatos = []
    uks = np.arange(cp["uk_min_pct"], cp["uk_max_pct"] + 0.01, 0.5)
    frs = np.linspace(fr_min, fr_max, 9)
    vistos = set()
    for uk in uks:
        Lt = uk / 100 * Zb / w
        L1 = Lt / (1 + razao_l2) if lcl else Lt
        L2 = Lt - L1 if lcl else 0.0
        for fr_alvo in frs:
            # filtro de SAÍDA: o lado motor (L2 + dispersão do motor) é alto em relação a L1, logo a ressonância
            # vista pelo inversor é ~ L1-C também no LCL (diferente do LCL de rede, onde L1||L2 governa)
            C_alvo = 1 / (L1 * (2 * math.pi * fr_alvo) ** 2)
            for cap in caps:
                for arr in _arranjos_capacitor(cap, cp, C_alvo, ped.tensao_v):
                    chave = (round(uk, 2), cap["id"], arr[0], arr[1])
                    if chave in vistos:
                        continue
                    vistos.add(chave)
                    Cy = arr[2]
                    fr = 1 / (2 * math.pi * math.sqrt(L1 * Cy))
                    if not (fr_min * 0.97 <= fr <= fr_max * 1.03):
                        continue
                    # estimativa analítica de THD (calibrada com a simulação PWM): pré-filtro
                    x = (fr / fs) ** 2
                    thd_est = 0.6 * 100 * x / max(1 - x, 1e-3)   # recalibrado c/ simulação de regime exato
                    if thd_est > cp["thd_v_max_pct"] * 1.15 * relax:
                        continue
                    ripple_est = 0.19 * vdc / ((L1) * fs)
                    if ripple_est > 1.1 * relax * cp["ripple_pp_max_pct"] / 100 * In * math.sqrt(2):
                        continue
                    ipk_est = In * math.sqrt(2) * 1.25
                    energia = 1.5 * (L1 + L2) * ipk_est ** 2
                    custo = _custo_indutor(cat, energia) + (1 if lcl else 0) * cat["indutor_custo"]["base"] \
                        + 3 * arr[1] * cap["preco"] * (1.0 if cap["id"] == pref else 1.0 + cp.get("penalidade_cap_nao_preferido", 0.15))
                    z0 = math.sqrt(L1 / Cy)
                    for qd in cp.get("amortecimento_q_opcoes", [0, 8, 5, 3]):
                        rd = z0 / qd if qd else 0.0
                        custo_rd = 0.0 if not rd else cat["miscelanea"].get("preco_resistor_amort_base", 450) * 3
                        candidatos.append(dict(uk=uk, L1=L1, L2=L2, cap=cap, arr=arr, fr=fr, rd=rd, qd=qd,
                                               custo_est=custo + custo_rd))
    return candidatos


def _escolher(ped, cat, cp, candidatos, fs, vdc, lcl, Zb, w, notas_inv, rapido):
    melhor = None
    avaliados = []
    limite_aval = 25 if rapido else 60
    for c in candidatos[:limite_aval * 4]:
        p, res, extra = avaliar(ped, cat, c["L1"], c["cap"], c["arr"], fs, vdc, L2=c["L2"], rd=c["rd"], pts_por_portadora=24)
        ver = verificar(ped, cat, p, res, c["cap"], c["arr"], fs, c["fr"])
        ok = all(x.ok for x in ver if x.critico)
        n_falhas = sum((not x.ok) for x in ver if x.critico)
        avaliados.append(dict(uk=round(c["uk"], 2), L1_uH=round(c["L1"] * 1e6, 1), L2_uH=round(c["L2"] * 1e6, 1),
                              capacitor=c["cap"]["id"], ligacao=c["arr"][0], n_por_ramo=c["arr"][1],
                              Rd_y_ohm=round(c["rd"], 4), Q_amort=c["qd"],
                              C_y_uF=round(c["arr"][2] * 1e6, 1), fr_Hz=round(c["fr"]), custo_est=round(c["custo_est"]),
                              thd_pct=round(max(r["thd_v_saida_pct"] for r in res), 2), aprovado=ok, falhas=n_falhas))
        if ok and melhor is None:
            melhor = c
        n_ok = len([a for a in avaliados if a["aprovado"]])
        if melhor is not None and (n_ok >= (1 if rapido else 4) or len(avaliados) >= limite_aval):
            break
        if len(avaliados) >= limite_aval * 2:
            break
    avisos = []
    fallback = False
    if melhor is None:
        avaliados.sort(key=lambda a: (a["falhas"], a["thd_pct"]))
        a0 = avaliados[0]
        melhor = next(c for c in candidatos if round(c["uk"], 2) == a0["uk"] and c["cap"]["id"] == a0["capacitor"]
                      and c["arr"][0] == a0["ligacao"] and c["arr"][1] == a0["n_por_ramo"] and c["qd"] == a0["Q_amort"])
        fallback = True
        avisos.append("Nenhuma combinação atendeu a todos os critérios críticos: apresentada a de menor nº de falhas. "
                      "Revise fs do inversor, limites do catálogo ou use capacitores para eletrônica de potência (IEC 61071).")

    return _construir_projeto(ped, cat, cp, melhor, fs, vdc, lcl, Zb, w, notas_inv, avaliados, avisos, fallback)


def _construir_projeto(ped, cat, cp, c, fs, vdc, lcl, Zb, w, notas_inv, avaliados=None, avisos=None, fallback=False,
                       pts_por_portadora=160, detalhado=True):
    avisos = list(avisos or [])
    avaliados = avaliados or []
    p, res, (Lm, Rm, q) = avaliar(ped, cat, c["L1"], c["cap"], c["arr"], fs, vdc, L2=c["L2"], rd=c["rd"],
                                  cd=c.get("cd", 0.0), rdp=c.get("rdp", 0.0),
                                  pts_por_portadora=pts_por_portadora, detalhado=detalhado)
    ver = verificar(ped, cat, p, res, c["cap"], c["arr"], fs, c["fr"])
    aprovado = all(x.ok for x in ver if x.critico)
    if fallback and aprovado:
        avisos = ["Aprovado somente na simulação fina (alta resolução) – conferir margens."]

    l1 = _spec_indutor("L1 – indutor de saída do inversor", cat, ped, c["L1"], res, fs, Zb, w, ripple_fonte="i1")
    l2 = _spec_indutor("L2 – indutor lado motor", cat, ped, c["L2"], res, fs, Zb, w, ripple_fonte="i2") if lcl else None
    banco = _spec_banco(c["cap"], c["arr"], res, cp)
    amort = _spec_amortecimento(c, res, cat)
    custo = l1.custo + (l2.custo if l2 else 0) + banco.n_total * banco.preco_unit + (amort.custo if amort else 0)

    pontos_limpos = []
    for r in res:
        pontos_limpos.append({k: (float(v) if isinstance(v, (np.floating, float)) else v) for k, v in r.items() if k != "_sim"})

    proj = Projeto(pedido=ped.to_dict(), topologia="LCL" if lcl else "LC", fs_hz=fs, vdc=vdc, fr_hz=c["fr"], l1=l1, l2=l2,
                   banco=banco, pontos=pontos_limpos, verificacoes=ver, aprovado=aprovado, custo_componentes=custo,
                   alternativas=sorted(avaliados, key=lambda a: (not a.get("aprovado"), a.get("custo_est", 0)))[:12],
                   avisos=avisos, notas_inversor=notas_inv, q_hf=q, lm_h=Lm, rm_ohm=Rm, amortecimento=amort)
    if detalhado:
        proj._sims = [r["_sim"] for r in res]          # para gráficos (não serializado)
        try:
            proj.condicoes_extremas = condicoes_extremas(ped, cat, c, fs)
        except Exception as e:  # nunca impede o projeto
            proj.condicoes_extremas = [dict(condicao=f"erro: {e}")]
        proj.estresse_capacitor = estresse_capacitor(cat, c["cap"], c["arr"][0], c["arr"][1], res)
        proj.sistema = parametros_sistema(ped, cat)["_info"]
    return proj


def _spec_indutor(nome, cat, ped, L, res, fs, Zb, w, ripple_fonte="i1"):
    In = ped.corrente_a
    if ripple_fonte == "i1":
        i_rms = max(max(r["i1_rms"] for r in res), In)
        ipk = max(r["i1_pico"] for r in res)
        rpp = max(r["ripple_pp"] for r in res)
        rrms = max(r["ripple_rms"] for r in res)
        i_f = max(r["i1_fund"] for r in res)
    else:
        i_rms = max(max(r["i2_rms"] for r in res), In)
        ipk = max(r["i2_rms"] for r in res) * math.sqrt(2) * 1.05
        rpp = 0.0
        rrms = 0.0
        i_f = max(r["i2_fund"] for r in res)
    ipk = max(ipk, In * math.sqrt(2))
    cp = cat["projeto_padrao"]
    isat = cp["isat_margem"] * ipk
    energia = 1.5 * L * ipk ** 2
    massa = cat["indutor_custo"]["kg_por_j"] * energia
    s_kva = math.sqrt(3) * ped.tensao_v * In / 1000
    perdas = perdas_indutor(cat, L, In, rpp if ripple_fonte == "i1" else 0.1 * In, fs)
    uk = 100 * L * w / Zb
    fmax = ped.f_saida_max_hz or ped.freq_rede_hz
    queda = 100 * In * 2 * math.pi * fmax * L / (ped.tensao_v / math.sqrt(3))
    return Indutor(nome=nome, l_uh=round(L * 1e6, 1), uk_pct=round(uk, 2), i_nom_a=round(i_rms, 1), i_fund_a=round(float(i_f), 1),
                   i_pico_a=round(ipk, 1), i_sat_a=round(isat, 0), ripple_pp_a=round(rpp, 1), ripple_rms_a=round(rrms, 1),
                   f_chav_hz=fs, r_dc_mohm=round(0.003 * Zb * 1000, 2), energia_j=round(energia, 1), perdas_w=round(perdas, 0),
                   massa_kg=round(massa, 0), dim_mm=_dim_indutor(cat, massa), custo=round(_custo_indutor(cat, energia), 2),
                   queda_v_pct=round(queda, 2))


def _spec_amortecimento(c, res, cat):
    rd, cd, rdp = c.get("rd", 0.0), c.get("cd", 0.0), c.get("rdp", 0.0)
    if not rd and not cd:
        return None
    lig, n, Cy = c["arr"]
    pam = max(r.get("p_amort_w", 0) for r in res)
    if cd:
        i_y = max(r.get("icap_d_y_rms", 0) for r in res)
        r_y, tipo = rdp, "rc_paralelo"
    else:
        i_y = max(r.get("icap_main_y_rms", r["icap_y_rms"]) for r in res)
        r_y, tipo = rd, "serie"
    if lig == "Delta":
        r_ramo, i_ramo = 3 * r_y, i_y / math.sqrt(3)
    else:
        r_ramo, i_ramo = r_y, i_y
    p_ramo = pam / 3 if pam else i_ramo ** 2 * r_ramo
    p_nom = max(50.0, math.ceil(2 * p_ramo / 50) * 50)
    nd = c.get("nd", 0)
    custo = 3 * (150 + 0.9 * p_nom) + (3 * nd * c["cap"]["preco"] if cd else 0)
    return Amortecimento(rd_y_ohm=round(rd, 4), r_ramo_ohm=round(r_ramo, 4), q_alvo=c.get("qd", 0), i_ramo_rms=round(i_ramo, 1),
                         p_ramo_w=round(p_ramo, 1), p_total_w=round(3 * p_ramo, 1), p_nominal_w=p_nom, custo=round(custo, 2),
                         tipo=tipo, cd_y_uf=round(cd * 1e6, 2), n_cd_por_ramo=nd, rdp_y_ohm=round(rdp, 4))


def _spec_banco(cap, arr, res, cp):
    lig, n, Cy = arr
    i_y = max(r.get("icap_main_y_rms", r["icap_y_rms"]) for r in res)
    i_yf = max(r.get("icap_main_y_fund", r["icap_y_fund"]) for r in res)
    v_ll = max(r["v_saida_ll_fund"] for r in res)
    if lig == "Delta":
        v_ramo, i_u, i_uf, c_ramo = v_ll, i_y / math.sqrt(3) / n, i_yf / math.sqrt(3) / n, n * cap["uf"]
    else:
        v_ramo, i_u, i_uf, c_ramo = v_ll / math.sqrt(3), i_y / n, i_yf / n, n * cap["uf"]
    imax = limites_capacitor(cap, {"normas_capacitor": _NORMAS_CACHE, "projeto_padrao": cp})["imax"]
    kvar = 3 * n * (cap["v_ac"] ** 2) * 2 * math.pi * 60 * cap["uf"] * 1e-6 / 1000
    # resistor de descarga por unidade: <= 50 V em 60 s (NR-10 / IEC 60831 exige 75 V em 3 min)
    vpk = math.sqrt(2) * cap["v_ac"]
    r = 60 / (cap["uf"] * 1e-6 * math.log(vpk / 50))
    serie_e12 = [1.0, 1.2, 1.5, 1.8, 2.2, 2.7, 3.3, 3.9, 4.7, 5.6, 6.8, 8.2]
    dec = 10 ** math.floor(math.log10(r))
    r_sel = max(x * dec for x in serie_e12 if x * dec <= r)
    p_r = (v_ramo ** 2) / r_sel
    return BancoCapacitores(cap_id=cap["id"], fabricante=cap["fabricante"], linha=cap["linha"], pn=cap["pn"], uf_unit=cap["uf"],
                            v_unit=cap["v_ac"], ligacao=lig, n_por_ramo=n, n_total=3 * n, c_y_uf=round(Cy * 1e6, 2),
                            c_ramo_uf=c_ramo, v_cap_rms=round(v_ramo, 1), i_unit_rms=round(i_u, 2), i_unit_fund=round(i_uf, 2),
                            i_unit_max=round(imax, 2), kvar_60=round(kvar, 2), preco_unit=cap["preco"],
                            r_descarga_mohm=round(r_sel / 1e6, 3), r_descarga_w=round(max(1.0, 4 * p_r), 1))


# --------------------------------------------------------------------------------------
def projeto_manual(ped: Pedido, cat, fs_khz: float, L1_uH: float, cap_id: str, ligacao: str, n_por_ramo: int,
                   rd_ramo_ohm: float = 0.0, L2_uH: float = 0.0, cap_custom: Optional[Dict[str, Any]] = None,
                   detalhado: bool = True, amort_tipo: str = None, nd_por_ramo: int = 0, rdp_ramo_ohm: float = 0.0) -> Projeto:
    """Monta e simula uma configuração definida manualmente (tela de ajuste). Mesmos critérios do automático.
    amort_tipo: "nenhum", "serie" (rd_ramo_ohm em série com cada ramo) ou "rc" (ramo de nd_por_ramo capacitores + rdp_ramo_ohm
    em paralelo com cada ramo). Valores em Ω são do resistor físico por ramo."""
    cp = cat["projeto_padrao"]
    if amort_tipo is None:
        amort_tipo = "serie" if rd_ramo_ohm else "nenhum"
    if cap_custom:
        cap = dict(cap_custom)
        cap.setdefault("id", "CUSTOM")
        cap.setdefault("dim_mm", [75, 75, 165])
        cap.setdefault("peso_kg", 0.8)
        cat = dict(cat)
        cat["capacitores"] = [c for c in cat["capacitores"] if c["id"] != cap["id"]] + [cap]
    else:
        cap = next(c for c in cat["capacitores"] if c["id"] == cap_id)
    fator = 3 if ligacao == "Delta" else 1
    para_y = (lambda r: r / 3) if ligacao == "Delta" else (lambda r: r)
    Cy = fator * n_por_ramo * cap["uf"] * 1e-6
    L1 = L1_uH * 1e-6
    L2 = (L2_uH or 0) * 1e-6
    fs = fs_khz * 1000
    w = 2 * math.pi * ped.freq_rede_hz
    Zb = ped.tensao_v / math.sqrt(3) / ped.corrente_a
    fr = 1 / (2 * math.pi * math.sqrt(L1 * Cy))
    z0 = math.sqrt(L1 / Cy)
    rd = para_y(rd_ramo_ohm) if amort_tipo == "serie" and rd_ramo_ohm else 0.0
    cd = fator * nd_por_ramo * cap["uf"] * 1e-6 if amort_tipo == "rc" and nd_por_ramo else 0.0
    rdp = para_y(rdp_ramo_ohm) if cd else 0.0
    topo = ("LCL" if L2 > 0 else "LC") + ({"serie": "_R", "rc": "_RC"}.get(amort_tipo, "") if (rd or cd) else "")
    c = dict(uk=100 * (L1 + L2) * w / Zb, L1=L1, L2=L2, cap=cap, arr=(ligacao, int(n_por_ramo), Cy), fr=fr, rd=rd,
             qd=round(z0 / (rd or rdp), 2) if (rd or rdp) else 0, cd=cd, rdp=rdp, nd=int(nd_por_ramo) if cd else 0, topo=topo)
    notas = cat["inversores"].get(_inv_chave(ped.inversor, cat), cat["inversores"]["GENERICO"])["notas"]
    proj = _construir_projeto(ped, cat, cp, c, fs, 1.35 * ped.tensao_v, L2 > 0, Zb, w, notas,
                              avisos=["Configuração definida manualmente (ajuste do engenheiro)."], detalhado=detalhado)
    proj.topologia = topo
    proj._cat = cat
    return proj


def config_de_projeto(proj) -> Dict[str, Any]:
    """Extrai os parâmetros editáveis de um projeto (para pré-preencher a tela de ajuste)."""
    b = proj.banco
    am = proj.amortecimento
    return dict(fs_khz=proj.fs_hz / 1000, L1_uH=float(proj.l1.l_uh), L2_uH=float(proj.l2.l_uh) if proj.l2 else 0.0,
                cap_id=b.cap_id, ligacao=b.ligacao, n_por_ramo=int(b.n_por_ramo),
                amort_tipo=("nenhum" if not am else ("rc" if am.tipo == "rc_paralelo" else "serie")),
                rd_ramo_ohm=float(am.r_ramo_ohm) if am and am.tipo == "serie" else 0.0,
                nd_por_ramo=int(am.n_cd_por_ramo) if am and am.tipo == "rc_paralelo" else 0,
                rdp_ramo_ohm=float(am.r_ramo_ohm) if am and am.tipo == "rc_paralelo" else 0.0)


def n_para_fr(L1_uH, fr_alvo, cap_uf, ligacao):
    """Nº de capacitores por ramo que mais aproxima a frequência de ressonância desejada."""
    C_y = 1 / (L1_uH * 1e-6 * (2 * math.pi * fr_alvo) ** 2)
    fator = 3 if ligacao == "Delta" else 1
    return max(1, round(C_y / (fator * cap_uf * 1e-6))), C_y * 1e6
