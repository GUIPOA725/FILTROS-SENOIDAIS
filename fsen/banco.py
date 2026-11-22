"""Bancos de capacitores DESSINTONIZADOS e filtros SINTONIZADOS – método padrão Electric (v1.14.0).

O PADRÃO vem das planilhas de engenharia da Electric ("ESTAGIO xxkVAr yyyV FD8,16%.xlsx", "Ajuste Indutor Trifásico para
Banco de capacitor Dessintonizado…", "mem calculo…", "Ajuste Indutor Monofásico para Filtro de Harmônica…") e das
especificações enviadas à Cootrans/IFG (2013–2023):

  Entradas por estágio: tensão da rede V, CAPACITOR associado (n × kvar unitário na tensão nominal V_cap), ordem de sintonia Nr
  (dessintonizado 3,5 = FD 8,16 % [padrão]; 3,78 = 7 %; 2,67 = 14 %; 2,5 = 16 % · sintonizado ≈ 0,94·h, ex. 4,7 na 5ª),
  fator de qualidade FQ (60 dessintonizado, 100 sintonizado) e fator de corrente de projeto k (1,3 dessintonizado; ≈1,8 sintonizado).
  X_C = V_cap²/Q_cap ;  X_L = X_C/Nr² ;  FD = 1/Nr² ;  L = X_L/ω
  I60 (rede, por fase) = (V/(X_C − X_L))/√3 ;  Q efetivo = √3·V·I60 ;  I_cap(V_cap) = Q_cap/(√3·V_cap)
  V_cap em operação = Nr²/(Nr²−1)·V  (+10 % de sobretensão) ;  R = X_L/FQ ;  perda fundamental = 3·I60²·R
  I de PROJETO do reator = k·I60  (dessintonizado k = 1,3 – DHTi ≈ 83 % no indutor)
  Ensaio/ajuste do reator: trifásico 60 Hz – corrente de AJUSTE = I60 com V por fase = I60·X_L (e a corrente de projeto)
  Sintonizado (planilha do indutor monofásico): I1 com V+10 %; I5 = 1,1·I1; I7 = 0,55·I1; I11 = 0,44·I1 → I_RMS ≈ 1,65·I1;
  V_h = h·X_L·I_h.

A plataforma acrescenta (física, conferência): espectro pela distorção de tensão da rede e pela corrente da carga, varredura de
impedância com a rede (transformador + Scc), THD antes/depois, limites do capacitor (IEEE 18: V pico 120 %, V rms 110 %,
I rms 135 %, kvar 135 %), faixa de sintonia com as tolerâncias. A corrente de projeto do reator é a MAIOR entre o padrão
Electric (k·I60) e a calculada pela física. O REATOR é projetado pelo mesmo motor do filtro senoidal (FEM, 3D, térmico,
desenhos, CAD).
"""
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np

# distorção de tensão de PROJETO (dessintonizado, nos terminais) – guias de fabricantes; IEC 61000-2-4 classe 2
HARM_PADRAO = {3: 0.5, 5: 6.0, 7: 5.0, 11: 3.5, 13: 3.0}
# sintonizado: fundo da rede a montante (Thévenin atrás da reatância de curto-circuito, SEM o filtro)
HARM_PADRAO_SINT = {5: 2.0, 7: 1.5, 11: 1.0, 13: 0.8}
NR_DESSINT = {3.5: "FD 8,16 % (Nr 3,5 – 210 Hz) – padrão Electric", 3.78: "FD 7 % (Nr 3,78 – 227 Hz)",
              2.67: "FD 14 % (Nr 2,67 – 160 Hz) – rede com 3ª harmônica", 2.5: "FD 16 % (Nr 2,5 – 150 Hz)"}
V_CAP_PADRAO = (380, 440, 480, 525, 600, 690, 800)   # 550 V (série F) só por escolha manual
# kvar unitários usuais por tensão do capacitor (Phicap/série F usados pela Electric/IFG)
UNID_KVAR = {380: (25, 27.5, 12.5, 15, 20, 30, 10), 440: (10, 12.5, 15, 20, 25), 480: (18, 20, 25, 12.5, 15, 10),
             525: (20, 25, 15, 12.5), 550: (50, 25), 600: (20, 25, 12.5), 690: (40, 20, 30), 800: (50, 25, 40)}
K_CORRENTE_DESSINT = 1.30          # planilha ESTAGIO: "Corrente Indutor = I60 × 1,3"
K_CORRENTE_SINT = 1.80             # planilha do indutor monofásico: 1,1·I60·√(1+1,1²+0,55²+0,44²) = 1,81·I60 (140 A / 77,5 A)
K_HIST_SINT = "histórico Electric: 1,615 (DHTi 50 %), 2,0 (DHTi 150 %), 2,5 (52 kvar/400 V)"
FQ_DESSINT, FQ_SINT = 60.0, 100.0
P_W_POR_KVAR = 6.0                 # teto de perdas do reator (W/kvar efetivo) – catálogos de reatores dessintonizados
P_W_POR_KVAR_SINT = 10.0           # sintonizado: corrente ≈ 1,8–2,5 × I60 com a harmônica sintonizada a 300 Hz (FQ ≥ 60 na fundamental)
R_POR_KVAR_CAP = 45.0              # R$/kvar (ESTIMATIVA – confirmar com fornecedor)
LIM_CAP = dict(V_pico=1.20, V_rms=1.10, I_rms=1.35, kvar=1.35)   # IEEE 18 / planilha PTW "LIMITES BANCO CAPACITORES"


@dataclass
class PedidoBanco:
    cliente: str = ""
    projeto: str = ""
    tipo: str = "dessintonizado"          # "dessintonizado" | "sintonizado"
    tensao_v: float = 380.0
    freq_hz: float = 60.0
    estagios_kvar: List[float] = field(default_factory=lambda: [25.0, 50.0, 50.0])   # kvar EFETIVOS desejados na rede
    caps: List[Optional[list]] = field(default_factory=list)   # por estágio: [n, kvar_unit, V_cap] (None = escolha automática)
    nr: float = 3.5                       # dessintonizado: ordem de sintonia (3,5 = FD 8,16 %)
    ordens: List[float] = field(default_factory=lambda: [5.0])   # sintonizado: harmônica de cada ramo
    fator_sintonia: float = 0.94          # sintonizado: Nr = fator × h (Electric: 4,4–4,8 na 5ª)
    fq: Optional[float] = None            # fator de qualidade do reator (None → 60 / 100)
    k_corrente: Optional[float] = None    # I_projeto / I60 (None → 1,3 / 1,8)
    dhti_carga_pct: float = 50.0          # sintonizado: DHTi drenada da rede (informativo / proposta)
    harm_tensao_pct: Dict[int, float] = field(default_factory=lambda: dict(HARM_PADRAO))
    harm_carga_a: Dict[int, float] = field(default_factory=dict)
    trafo_kva: float = 1000.0
    trafo_z_pct: float = 6.0
    scc_rede_mva: float = 250.0
    amb_c: float = 40.0
    tol_c_pct: float = 5.0
    tol_l_pct: float = 2.0                # especificação Electric: −2 %/+2 %
    sobretensao: float = 1.10
    classe: str = "F"                     # especificação Electric: classe F (155 °C), isolação 1 kV, IP00
    condutor: str = "AL"                  # "AL" (padrão Electric: chapa/barra de alumínio) | "CU"
    monofasico: bool = False              # sintonizado: 3 reatores monofásicos de 2 colunas em vez de 1 trifásico
    # v1.16.0 – Plataforma de Estudos: cenários de curto da barra (estudo de proteção) e origem de cada dado
    cenarios_rede: List[dict] = field(default_factory=list)
    origem_dados: Dict[str, str] = field(default_factory=dict)
    barra_ligacao: str = ""
    acesso_painel: str = "frontal/traseiro"   # v1.17.4: "frontal/traseiro" (prof. 800, padrão) | "frontal" (prof. 400, mais largo)

    @property
    def p_pct(self):
        return 100.0 / self.nr ** 2

    @staticmethod
    def from_dict(d):
        d = dict(d)
        if "p_pct" in d and "nr" not in d:
            d["nr"] = 1 / math.sqrt(float(d["p_pct"]) / 100)
        for k in ("harm_tensao_pct", "harm_carga_a"):
            if k in d and d[k]:
                d[k] = {int(a): float(b) for a, b in d[k].items()}
        return PedidoBanco(**{k: v for k, v in d.items() if k in PedidoBanco.__dataclass_fields__})

    def fq_(self):
        return self.fq or (FQ_SINT if self.tipo == "sintonizado" else FQ_DESSINT)

    def k_(self):
        return self.k_corrente or (K_CORRENTE_SINT if self.tipo == "sintonizado" else K_CORRENTE_DESSINT)


def _x_rede(ped):
    """Reatância de curto-circuito na barra (Ω, por fase) = rede + transformador."""
    Un = ped.tensao_v
    return Un ** 2 / (ped.scc_rede_mva * 1e6) + ped.trafo_z_pct / 100 * Un ** 2 / (ped.trafo_kva * 1e3)


def fator_q(V, Vcap, nr):
    """Q efetivo na rede / Q de placa do capacitor."""
    return (V / Vcap) ** 2 * nr ** 2 / (nr ** 2 - 1)


def v_cap_padrao(ped, nr):
    """Tensão nominal do capacitor no padrão Electric: a menor da série ≥ 1,1 × V_cap em operação (dessintonizado);
    sintonizado ≥ 1,1 × (V_op + 15 % de harmônicas) – a Electric usa 690/800 V em 380–440 V."""
    vop = nr ** 2 / (nr ** 2 - 1) * ped.tensao_v
    if ped.tipo == "sintonizado":            # prática Electric: capacitores "especiais para filtro" 690 V (380–440 V) / 800 V
        tab = [(230, 440), (415, 690), (460, 690), (520, 800)]
        return next((vc for vmax, vc in tab if ped.tensao_v <= vmax), 800)
    alvo = vop * ped.sobretensao
    return next((v for v in V_CAP_PADRAO if v >= alvo - 0.5), V_CAP_PADRAO[-1])


def escolher_capacitor(ped, Q_alvo, nr, Vcap=None):
    """Combinação n × kvar unitário (na V_cap padrão) com Q efetivo mais próximo do alvo (preferindo menos unidades)."""
    Vcap = Vcap or v_cap_padrao(ped, nr)
    fq = fator_q(ped.tensao_v, Vcap, nr)
    melhor = None
    for rk, u in enumerate(UNID_KVAR.get(Vcap, (10, 12.5, 15, 20, 25, 30, 40, 50))):
        for n in range(1, 13):
            Qe = n * u * fq
            err = abs(Qe - Q_alvo) / Q_alvo
            key = (round(err, 3) > 0.08, n > 6, rk if err <= 0.08 else 0, round(err, 2), n)   # ±8 %, ≤ 6 unidades, unidade usual da Electric
            if melhor is None or key < melhor[0]:
                melhor = (key, [n, u, Vcap])
    return melhor[1]


def estagio(ped, Q_alvo, cap=None, nr=None, ordem=None):
    """Estágio pelo método da planilha ESTAGIO da Electric + espectro físico."""
    V, f1 = ped.tensao_v, ped.freq_hz
    w1 = 2 * math.pi * f1
    if nr is None:
        nr = ped.fator_sintonia * ordem if ped.tipo == "sintonizado" else ped.nr
    if not cap:
        cap = escolher_capacitor(ped, Q_alvo, nr)
    n, u, Vcap = cap
    Qcap = n * u * 1e3
    Xc = Vcap ** 2 / Qcap                       # Ω (estrela equivalente)
    Xl = Xc / nr ** 2
    p = 1 / nr ** 2
    I60 = (V / (Xc - Xl)) / math.sqrt(3)
    Qe = math.sqrt(3) * V * I60
    fq = ped.fq_()
    R = Xl / fq                                 # planilha: R = X_L / FQ
    I_cap_nom = Qcap / (math.sqrt(3) * Vcap)
    Uc1 = nr ** 2 / (nr ** 2 - 1) * V
    hs = sorted(set(list(ped.harm_tensao_pct) + list(ped.harm_carga_a)))
    Xs = _x_rede(ped)
    Ih, Uch = {}, {}
    for h in hs:
        Zf = complex(R * math.sqrt(h), h * Xl - Xc / h)          # R cresce ~√h (pelicular) – conservador para o fator de mérito
        Vh = ped.harm_tensao_pct.get(h, 0) / 100 * V / math.sqrt(3)
        Ih[h] = abs(Vh / (complex(0, h * Xs) + Zf)) if ped.tipo == "sintonizado" else abs(Vh / Zf)
        Uch[h] = Ih[h] * (Xc / h) * math.sqrt(3)
    ft = f1 * nr
    return dict(Q_alvo=Q_alvo, Q_kvar=Qe / 1e3, cap=[n, u, Vcap], Q_cap_nom_kvar=Qcap / 1e3, U_cap_nom=Vcap, nr=nr, p=p, p_pct=p * 100,
                ordem=ordem, f_sintonia=ft, h_sintonia=nr, Xc=Xc, Xl=Xl, C_uF_estrela=1e6 / (w1 * Xc), C_delta_uF=1e6 / (w1 * Xc) / 3,
                L_uH=Xl / w1 * 1e6, R_ohm=R, fq=fq, I1=I60, I60=I60, I_cap_nom=I_cap_nom, Ih=Ih, Uc1=Uc1, Uc1_110=Uc1 * 1.1,
                Uch=Uch, P_fund_W=3 * I60 ** 2 * R, V_ajuste_fase=I60 * Xl)


def sintonizado_correntes_carga(ped, est_list):
    """Corrente harmônica da carga dividida entre a rede e os ramos (divisor de impedâncias na barra)."""
    Xs = _x_rede(ped)
    for h, Ilh in ped.harm_carga_a.items():
        Zs = complex(0, h * Xs)
        Yf = [1 / complex(e["R_ohm"] * math.sqrt(h), h * e["Xl"] - e["Xc"] / h) for e in est_list]
        Vbus = Ilh / (1 / Zs + sum(Yf))
        for e, y in zip(est_list, Yf):
            e["Ih"][h] = e["Ih"].get(h, 0) + abs(Vbus * y)          # soma (fase desconhecida → conservador)
            e["Uch"][h] = e["Ih"][h] * (e["Xc"] / h) * math.sqrt(3)
    return est_list


def varredura(ped, est_list, hmax=25, n=2400):
    """|Z| na barra (Ω) com e sem o banco; picos (ressonâncias paralelas)."""
    Xs = _x_rede(ped)
    h = np.linspace(1.0, hmax, n)
    Zs = 1j * h * Xs
    Yb = sum(1 / (e["R_ohm"] * np.sqrt(h) + 1j * (h * e["Xl"] - e["Xc"] / h)) for e in est_list)
    Z = 1 / (1 / Zs + Yb)
    picos = [float(h[i]) for i in range(1, n - 1) if abs(Z[i]) > abs(Z[i - 1]) and abs(Z[i]) > abs(Z[i + 1]) and abs(Z[i]) > 1.5 * abs(Zs[i])]
    return dict(h=h, Z=np.abs(Z), Zs=np.abs(Zs), picos=picos)


def thd_tensao(ped, est_list):
    if not ped.harm_carga_a:
        return None
    Xs = _x_rede(ped)
    Un_f = ped.tensao_v / math.sqrt(3)
    s0 = s1 = 0.0
    det = {}
    for h, Ilh in ped.harm_carga_a.items():
        Zs = complex(0, h * Xs)
        Yf = sum(1 / complex(e["R_ohm"] * math.sqrt(h), h * e["Xl"] - e["Xc"] / h) for e in est_list)
        v0 = abs(Ilh * Zs) / Un_f * 100
        v1 = abs(Ilh / (1 / Zs + Yf)) / Un_f * 100
        det[h] = (v0, v1)
        s0 += v0 ** 2
        s1 += v1 ** 2
    return dict(sem=math.sqrt(s0), com=math.sqrt(s1), por_h=det)


def espectro_electric_sint(I1):
    """Planilha 'Ajuste Indutor Monofásico para Filtro de Harmônica': I1 (V+10 %), I5 = 1,1·I1, I7 = 0,55·I1, I11 = 0,44·I1."""
    return {5: 1.1 * I1, 7: 0.55 * I1, 11: 0.44 * I1}


def limites_capacitor(e, Ih):
    """IEEE 18 (planilha PTW): V pico ≤ 120 %, V rms ≤ 110 %, I rms ≤ 135 %, kvar ≤ 135 % da placa."""
    Vn = e["U_cap_nom"]
    In = e["I_cap_nom"]
    Uch = {h: Ih[h] * (e["Xc"] / h) * math.sqrt(3) for h in Ih}
    vpk = (e["Uc1"] + sum(Uch.values())) / Vn
    vrms = math.sqrt(e["Uc1"] ** 2 + sum(v ** 2 for v in Uch.values())) / Vn
    irms = math.sqrt(e["I60"] ** 2 + sum(v ** 2 for v in Ih.values())) / In
    kvar = vrms * irms
    return [("Tensão de pico", vpk, LIM_CAP["V_pico"]), ("Tensão rms", vrms, LIM_CAP["V_rms"]),
            ("Corrente rms", irms, LIM_CAP["I_rms"]), ("Potência reativa", kvar, LIM_CAP["kvar"])]


def faixa_sintonia(e, tol_c, tol_l):
    """Frequência de sintonia com as tolerâncias de C e L (envelhecimento do capacitor reduz C → sintonia sobe)."""
    f = e["f_sintonia"]
    return dict(f_nom=f, f_min=f / math.sqrt((1 + tol_c / 100) * (1 + tol_l / 100)),
                f_max=f / math.sqrt((1 - tol_c / 100) * (1 - tol_l / 100)))


def requisitos_reator(ped, e):
    """Requisitos do reator: corrente de projeto = max(padrão Electric k·I60, física) + espectro de tensão sobre ele."""
    f1 = ped.freq_hz
    k = ped.k_()
    I_el = k * e["I60"]
    I1 = e["I60"] * ped.sobretensao                                # V + 10 % (planilha)
    Ih = dict(e["Ih"])
    if ped.tipo == "sintonizado":                                  # espectro mínimo do padrão Electric (planilha do monofásico)
        carac = [5, 7, 11, 13, 17, 19]
        h0 = int(round(e["ordem"] or 5))
        i0 = carac.index(h0) if h0 in carac else 0
        for h, rel in zip(carac[i0:], (1.1, 0.55, 0.44)):
            Ih[h] = max(Ih.get(h, 0.0), rel * I1)
    Ih2 = sum(v ** 2 for v in Ih.values())
    I_fis = math.sqrt(I1 ** 2 + Ih2) * (1 + ped.tol_c_pct / 200)
    Ith = max(I_el, I_fis)
    Ihs = math.sqrt(Ih2)
    hdom = max(Ih, key=lambda h: Ih[h] * h) if Ih else 5
    L = e["L_uH"] * 1e-6
    hs = sorted(Ih)
    fh = np.array([h * f1 for h in hs])
    Vh = np.array([math.sqrt(2) * Ih[h] * 2 * math.pi * h * f1 * L for h in hs])
    ipk = math.sqrt(2) * (I1 + sum(Ih.values()))
    lin = 1.5                                                      # "Sobrecarga 50 %" (ET Electric) – L mantida até 1,5×I_proj
    req = dict(L=L, In=Ith, I1=I1, Ipk=ipk, Isat=max(math.sqrt(2) * lin * Ith * 0.97, ipk), Iovl=math.sqrt(2) * 2.0 * Ith,
               Iinv=e["I60"], rpp=2 * math.sqrt(2) * Ihs, rrms=Ihs, fs=hdom * f1, f1=f1, V=ped.tensao_v,
               Vdc=math.sqrt(2) * ped.tensao_v * 1.1, classe=ped.classe,
               P_max=(P_W_POR_KVAR_SINT if ped.tipo == "sintonizado" else P_W_POR_KVAR) * e["Q_kvar"], k_Pmax=0.88,
               aplicacao=("reator de banco dessintonizado" if ped.tipo == "dessintonizado" else f"reator de filtro sintonizado ({e['ordem']:g}ª)"),
               linearidade=lin, tol_L_pct=ped.tol_l_pct, I_electric=I_el, I_fisica=I_fis, k_corrente=k, I_ajuste=e["I60"],
               V_ajuste_fase=e["V_ajuste_fase"], fq=e["fq"])
    return req, (fh, Vh), Ih


def dimensionar(ped, cat=None):
    """Cálculo de todos os estágios (padrão Electric) + física (espectro, ressonância, THD, limites, sintonia)."""
    est = []
    for i, Q in enumerate(ped.estagios_kvar):
        cap = ped.caps[i] if i < len(ped.caps) and ped.caps[i] else None
        if ped.tipo == "sintonizado":
            ordem = ped.ordens[i] if i < len(ped.ordens) else ped.ordens[-1]
            est.append(estagio(ped, Q, cap=cap, ordem=ordem))
        else:
            est.append(estagio(ped, Q, cap=cap))
    if ped.tipo == "sintonizado" and len(est) > 1:   # fundo da rede com TODOS os ramos ligados
        Xs = _x_rede(ped)
        for h in list(est[0]["Ih"]):
            Vh = ped.harm_tensao_pct.get(h, 0) / 100 * ped.tensao_v / math.sqrt(3)
            Yf = [1 / complex(e["R_ohm"] * math.sqrt(h), h * e["Xl"] - e["Xc"] / h) for e in est]
            Vbus = Vh / (1 + complex(0, h * Xs) * sum(Yf))
            for e, y in zip(est, Yf):
                e["Ih"][h] = abs(Vbus * y)
                e["Uch"][h] = e["Ih"][h] * (e["Xc"] / h) * math.sqrt(3)
    if ped.harm_carga_a:
        sintonizado_correntes_carga(ped, est)
    avisos = []
    for i, e in enumerate(est):
        e["Uc_arit"] = e["Uc1"] + sum(e["Uch"].values())
        e["Uc_rms"] = math.sqrt(e["Uc1"] ** 2 + sum(v ** 2 for v in e["Uch"].values()))
        e["requisitos"], e["espectro"], e["Ih_projeto"] = requisitos_reator(ped, e)
        e["I_cap_rms"] = math.sqrt(e["I60"] ** 2 + sum(v ** 2 for v in e["Ih_projeto"].values()))
        e["limites_cap"] = limites_capacitor(e, e["Ih_projeto"])
        e["faixa_sintonia"] = faixa_sintonia(e, ped.tol_c_pct, ped.tol_l_pct)
        e["custo_cap_R"] = e["Q_cap_nom_kvar"] * R_POR_KVAR_CAP
        e["codigo"] = codigo_modulo(ped, e)
        for nome, v, lim in e["limites_cap"]:
            if v > lim:
                avisos.append(f"Estágio {i+1}: capacitor {e['cap'][0]}×{e['cap'][1]:g} kvar/{e['U_cap_nom']} V – {nome.lower()} "
                              f"{v*100:.0f} % > {lim*100:.0f} % (IEEE 18). Subir a tensão do capacitor.")
        if abs(e["Q_kvar"] - e["Q_alvo"]) / e["Q_alvo"] > 0.08:
            avisos.append(f"Estágio {i+1}: potência efetiva {e['Q_kvar']:.1f} kvar difere {abs(e['Q_kvar']/e['Q_alvo']-1)*100:.0f} % do pedido "
                          f"({e['Q_alvo']:g} kvar) com os capacitores padrão.")
        r = e["requisitos"]
        if r["I_fisica"] > r["I_electric"] * 1.05:
            avisos.append(f"Estágio {i+1}: a corrente calculada pelo espectro ({r['I_fisica']:.0f} A) é maior que o padrão Electric "
                          f"k·I60 = {r['I_electric']:.0f} A – o reator foi especificado pela maior.")
    vr = varredura(ped, est)
    hs_rel = [h for h, u in ped.harm_tensao_pct.items() if u >= 0.5] + list(ped.harm_carga_a)
    tol_r = 0.03 if ped.tipo == "sintonizado" else 0.10   # no sintonizado a paralela fica logo abaixo da sintonia (inerente)
    for pk in vr["picos"]:
        for h in hs_rel:
            if abs(pk - h) / h < tol_r:
                avisos.append(f"Ressonância paralela em {pk:.2f}ª harmônica, a menos de 10 % da {h}ª presente na rede/carga.")
    if ped.tipo == "dessintonizado" and ped.harm_tensao_pct.get(3, 0) >= 1.0 and ped.nr > 3:
        avisos.append(f"3ª harmônica de {ped.harm_tensao_pct[3]:g} % com Nr {ped.nr:g}: usar FD 14 % (Nr 2,67, sintonia abaixo da 3ª).")
    if ped.tipo == "sintonizado":
        for i, e in enumerate(est):
            fs = e["faixa_sintonia"]
            if fs["f_max"] >= (e["ordem"] or 5) * ped.freq_hz * 0.99:
                avisos.append(f"Estágio {i+1}: com as tolerâncias a sintonia pode chegar a {fs['f_max']:.0f} Hz (≥ {e['ordem']:g}ª) – "
                              "baixar o fator de sintonia.")
    hr_simples = math.sqrt(ped.trafo_kva / (ped.trafo_z_pct / 100) / max(sum(e["Q_cap_nom_kvar"] for e in est), 1e-6))
    return dict(estagios=est, varredura=vr, thd=thd_tensao(ped, est), avisos=avisos, x_rede_ohm=_x_rede(ped),
                Q_total_kvar=sum(e["Q_kvar"] for e in est), hr_sem_reator=hr_simples)


def codigo_modulo(ped, e):
    """Código de produto Electric: '380FD8-50' (dessintonizado), '380FS5-75' (sintonizado)."""
    if ped.tipo == "sintonizado":
        return f"{ped.tensao_v:.0f}FS{e['ordem']:g}-{round(e['Q_alvo']):d}"
    fd = {3.5: "8", 3.78: "7", 2.67: "14", 2.5: "16"}.get(round(e["nr"], 2), f"{e['p_pct']:.0f}")
    return f"{ped.tensao_v:.0f}FD{fd}-{round(e['Q_alvo']):d}"


def reatores_distintos(res):
    """Agrupa estágios com o mesmo reator (mesma L e corrente) – um projeto de indutor por grupo."""
    grupos = {}
    for i, e in enumerate(res["estagios"]):
        k = (round(e["L_uH"], 0), round(e["requisitos"]["In"], 0), e.get("ordem"))
        grupos.setdefault(k, []).append(i)
    return list(grupos.values())


def wf_de_espectro(f1, I1_rms, Ih_rms, n_por_h=64):
    """Formas de onda das 3 fases a partir do espectro (harmônicas de sequência natural, em fase com a fundamental –
    conservador para o pico). Mesmo formato de ind_avancado.formas_onda."""
    hmax = max([1] + list(Ih_rms))
    n = int(n_por_h * hmax)
    n += (-n) % 6
    t = np.arange(n) / (n * f1)
    nh = n // 2 + 1
    F = np.zeros(nh, complex)
    F[1] = I1_rms * math.sqrt(2) * n / 2
    for h, v in Ih_rms.items():
        if int(h) % 3 == 0:            # sequência zero: não circula em banco trifásico a 3 fios
            continue
        if h < nh:
            F[int(h)] = v * math.sqrt(2) * n / 2
    from .ind_avancado import _normalizar
    ia = np.fft.irfft(F, n)
    return _normalizar(t, ia, f1, I1_rms)


# ------------------------------------------------------------------ painel (padrão das ET Electric → IFG)
NH = (32, 40, 50, 63, 80, 100, 125, 160, 200, 250, 315, 355, 400, 500, 630)
CONTATORES = [("Epcos B44066-S2011 (≤ 22 kvar 440 V)", 28.9), ("Epcos B44066-S3312 (≤ 36 kvar 440 V)", 48.0),
              ("Epcos B44066-S6012 (≤ 66 kvar 440 V)", 92.0), ("Epcos B44066-S7410 (≤ 80 kvar 440 V)", 108.0),
              ("Epcos B44066-S9910 (≤ 100 kvar 400 V)", 144.0), ("Schneider LC1D150 AC6b", 150.0), ("Schneider LC1F185 AC6b", 185.0),
              ("Schneider LC1F265 AC6b", 265.0), ("Schneider LC1F330 AC6b", 330.0)]
CABO_90C = [(10, 60), (16, 80), (25, 105), (35, 130), (50, 160), (70, 205), (95, 245), (120, 285), (150, 325), (185, 370), (240, 435)]


def protecao_estagio(ped, e):
    """Chave-fusível, fusível, contator e cabos por estágio (regras tiradas das ET Electric 2017–2023)."""
    sint = ped.tipo == "sintonizado"
    I_ref = e["requisitos"]["In"] if sint else e["I60"]
    fus = next(x for x in NH if x >= 1.6 * I_ref)
    chave = 100 if fus <= 63 else 160 if fus <= 125 else 250 if fus <= 250 else 400 if fus <= 400 else 630
    base = "NH00" if fus <= 160 else "NH01" if fus <= 250 else "NH2"
    I_ct = e["requisitos"]["In"] * 0.96 if sint else e["I60"] * 1.1
    cont = next((c for c in CONTATORES if c[1] >= I_ct), CONTATORES[-1])
    fr = 0.62                                 # agrupamento + painel a 45–50 °C (ET Electric: 50 mm² p/ 50 kvar 380 V; 70–95 mm² sintonizado)
    cabo = next((s for s, a in CABO_90C if a * fr >= e["requisitos"]["In"]), 240)
    return dict(fusivel_A=fus, chave_A=chave, base=base, contator=cont[0], contator_In=cont[1], cabo_mm2=cabo,
                cabo_ind_cap_mm2=next((s for s, a in CABO_90C if a * fr >= e["I_cap_rms"] * 0.7), 240))


def painel(ped, res):
    """Itens gerais do painel (padrão ET Electric) e dimensões orientativas."""
    n = len(res["estagios"])
    It = sum(e["I_cap_rms"] for e in res["estagios"])
    geral = next(x for x in NH + (800, 1000, 1250, 1600) if x >= 1.35 * It)
    from .painel_gabinete import gabinete          # v1.17.0: gabinete padrão Electric/AGCO (frente/trás)
    gab = gabinete(ped, res)
    Dg = gab["dimensoes_mm"]
    larg = Dg["largura"]
    itens = [(f"Painel metálico {Dg['altura']}(A) × {larg}(L) × {Dg['profundidade']}(P) mm – capacitores na frente, reatores "
              f"atrás com chapa divisória ({len(gab['colunas'])} coluna(s) de 800 mm; ver Layout_Painel)", 1, "pç"),
             (f"Controlador de fator de potência Epcos BR6000 {6 if n <= 6 else 12} estágios", 1, "pç"),
             (f"Relé falta de fase trifásico {ped.tensao_v:.0f} V", 1, "pç"),
             ("Disjuntor bipolar 10 A DIN (comando)", 2, "pç"), ("Disjuntor tripolar 10 A DIN (relé falta de fase)", 1, "pç"),
             (f"Transformador de comando {ped.tensao_v:.0f}/220 V – {500 if n <= 6 else 1000} VA", 1, "pç"),
             (f"Exaustor 220 V {gab['ventilacao']['exaustor_m3h']} m³/h com grelha e filtro (teto, sobre os reatores)",
              gab["ventilacao"]["n_exaustores"], "pç"),
             ("Termostato do painel -B0 35 °C (liga exaustores) e -BT2 55 °C (desliga o banco)", 2, "pç"),
             ("Botoeira de emergência c/ trava Ø22 mm 1NF+1NA", 1, "pç"), ("Sinaleiro LED vermelho Ø22 mm 220 V (estágio ligado)", n, "pç"),
             ("Chave seletora 2 posições Ø22 mm (desligado – automático)", 1, "pç"),
             (f"Proteção geral: chave seccionadora-fusível {geral} A (ou disjuntor caixa moldada)", 1, "pç")]
    if ped.tipo == "sintonizado":
        Imx = max(e["requisitos"]["In"] for e in res["estagios"])
        itens += [(f"TCs de proteção por estágio {next(x for x in NH if x >= Imx)}/5 A", 3 * n, "pç"),
                  ("Chave de aferição de TC", 1, "pç")]
    eletric = ["Reatores (indutores) – fornecimento Electric"]
    if ped.tipo == "sintonizado":
        eletric += ["Multimedidores Embrasul MD4040 – proteção por estágio (1 por estágio)", "CLP de controle e proteção",
                    "Projeto elétrico (diagrama de força e comando)"]
    return dict(itens=itens, eletric=eletric, geral_A=geral, dim=(Dg['altura'], larg, Dg['profundidade']), I_total=It, gabinete=gab)
