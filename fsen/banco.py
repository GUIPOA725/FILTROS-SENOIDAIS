"""Bancos de capacitores DESSINTONIZADOS e filtros SINTONIZADOS (5ª, 7ª, 11ª…) – v1.13.0.

Cálculo elétrico (por estágio/ramo, sistema trifásico equilibrado, capacitores trifásicos IEC 60831 em triângulo interno):
  X_C (estrela eq.) = Un² / (Q·(1 − p)) ;  X_L = p·X_C ;  f_sintonia = f1/√p
  U_C1 = Un/(1 − p)  (tensão elevada no capacitor) ;  U_C,h = u_h·Un·(X_C/h)/|h·X_L − X_C/h|
  I1 = Q/(√3·Un) ;  I_h = (u_h·Un/√3)/|h·X_L − X_C/h|  (+ parcela da corrente harmônica da carga no filtro sintonizado)
  Varredura de impedância na barra (rede ‖ todos os estágios) → ressonâncias paralelas; THD de tensão antes/depois.
O REATOR de cada estágio distinto é projetado pelo MESMO motor do filtro senoidal (triagem IEC, elementos finitos, 2
entreferros por coluna, barra de cobre, térmico, verificação independente, análise avançada, desenhos, CAD, documentos).
"""
import math
import os
import datetime as _dt
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional

import numpy as np

# distorção de tensão típica de PROJETO para reatores dessintonizados (guias de aplicação de fabricantes; dentro dos níveis
# de compatibilidade da IEC 61000-2-4 classe 2) – o usuário pode substituir pela medição
HARM_PADRAO = {3: 0.5, 5: 6.0, 7: 5.0, 11: 3.5, 13: 3.0}
# sintonizado: distorção de FUNDO da rede a montante (fonte de Thévenin atrás da reatância de curto-circuito, SEM o filtro) –
# o filtro sintonizado absorve o fundo da rede; usar a medição sempre que houver
HARM_PADRAO_SINT = {5: 2.0, 7: 1.5, 11: 1.0, 13: 0.8}
P_W_POR_KVAR = 6.0          # teto de perdas do reator (W/kvar do estágio) – referência de catálogos de reatores dessintonizados
V_CAP_PADRAO = (440, 480, 525, 600, 690)
KVAR_CAP_PADRAO = (5, 7.5, 10, 12.5, 15, 20, 25, 30, 40, 50)
R_POR_KVAR_CAP = 45.0       # R$/kvar (ESTIMATIVA – confirmar com fornecedor)


@dataclass
class PedidoBanco:
    cliente: str = ""
    projeto: str = ""
    tipo: str = "dessintonizado"          # "dessintonizado" | "sintonizado"
    tensao_v: float = 440.0
    freq_hz: float = 60.0
    estagios_kvar: List[float] = field(default_factory=lambda: [25.0, 50.0, 50.0])
    p_pct: float = 7.0                    # dessintonizado: 5,67 / 7 / 14 %
    ordens: List[float] = field(default_factory=lambda: [5.0])   # sintonizado: harmônica de cada ramo (1 ramo por estágio)
    fator_sintonia: float = 0.95          # sintonizado: h_t = fator × h (abaixo da harmônica, margem de dessintonia)
    q_reator: float = 40.0                # fator de qualidade do reator na sintonia (sintonizado)
    harm_tensao_pct: Dict[int, float] = field(default_factory=lambda: dict(HARM_PADRAO))
    harm_carga_a: Dict[int, float] = field(default_factory=dict)   # corrente harmônica da CARGA na barra (A) – sintonizado
    trafo_kva: float = 1000.0
    trafo_z_pct: float = 6.0
    scc_rede_mva: float = 250.0
    amb_c: float = 40.0
    tol_c_pct: float = 5.0
    sobretensao: float = 1.10

    @staticmethod
    def from_dict(d):
        d = dict(d)
        for k in ("harm_tensao_pct", "harm_carga_a"):
            if k in d and d[k]:
                d[k] = {int(a): float(b) for a, b in d[k].items()}
        return PedidoBanco(**{k: v for k, v in d.items() if k in PedidoBanco.__dataclass_fields__})


def _x_rede(ped):
    """Reatância de curto-circuito na barra (Ω, por fase) = rede + transformador."""
    Un = ped.tensao_v
    xs = Un ** 2 / (ped.scc_rede_mva * 1e6)
    xt = ped.trafo_z_pct / 100 * Un ** 2 / (ped.trafo_kva * 1e3)
    return xs + xt


def capacitor_escolhido(U_c_max, Q_at_Un_cap_func):
    """Escolhe a tensão nominal padrão do capacitor ≥ U_c_max e devolve (U_nom, kvar nominal na U_nom)."""
    for v in V_CAP_PADRAO:
        if v >= U_c_max:
            return v, Q_at_Un_cap_func(v)
    return V_CAP_PADRAO[-1], Q_at_Un_cap_func(V_CAP_PADRAO[-1])


def estagio(ped, Q_kvar, p=None, ordem=None):
    """Cálculo completo de um estágio (dessintonizado: p; sintonizado: ordem h)."""
    Un, f1 = ped.tensao_v, ped.freq_hz
    w1 = 2 * math.pi * f1
    if ped.tipo == "sintonizado":
        ht = ped.fator_sintonia * ordem
        p = 1 / ht ** 2
    Q = Q_kvar * 1e3
    Xc = Un ** 2 / (Q * (1 - p))
    Xl = p * Xc
    C = 1 / (w1 * Xc)
    L = Xl / w1
    ft = f1 / math.sqrt(p)
    R = (Xl * (ft / f1)) / ped.q_reator if ped.tipo == "sintonizado" else (Xl * (ft / f1)) / 80.0
    hs = sorted(set(list(ped.harm_tensao_pct) + list(ped.harm_carga_a)))
    I1 = Q / (math.sqrt(3) * Un)
    Uc1 = Un / (1 - p)
    Ih, Uch = {}, {}
    Xs = _x_rede(ped)
    for h in hs:
        Zf = complex(R, h * Xl - Xc / h)
        Vh = ped.harm_tensao_pct.get(h, 0) / 100 * Un / math.sqrt(3)
        if ped.tipo == "sintonizado":     # fundo da rede como fonte de Thévenin atrás de j·h·Xs (o ramo divide com os outros depois)
            Ih[h] = abs(Vh / (complex(0, h * Xs) + Zf))
        else:                             # dessintonizado: tensão harmônica nos terminais do banco (prática dos guias – conservador)
            Ih[h] = abs(Vh / Zf)
        Uch[h] = Ih[h] * (Xc / h) * math.sqrt(3)
    return dict(Q_kvar=Q_kvar, p=p, p_pct=p * 100, ordem=ordem, f_sintonia=ft, h_sintonia=ft / f1, Xc=Xc, Xl=Xl, C_uF_estrela=C * 1e6,
                L_uH=L * 1e6, R_ohm=R, I1=I1, Ih=Ih, Uc1=Uc1, Uch=Uch)


def sintonizado_correntes_carga(ped, est_list):
    """Divide a corrente harmônica da carga entre a rede e os ramos sintonizados (divisor de impedâncias na barra)."""
    Xs = _x_rede(ped)
    for h, Ilh in ped.harm_carga_a.items():
        Zs = complex(0, h * Xs)
        Yf = [1 / complex(e["R_ohm"], h * e["Xl"] - e["Xc"] / h) for e in est_list]
        Ytot = 1 / Zs + sum(Yf)
        Vbus = Ilh / Ytot
        for e, y in zip(est_list, Yf):
            If = abs(Vbus * y)
            # soma em quadratura com a parcela da distorção de fundo (mesma frequência, fase desconhecida → conservador: soma)
            e["Ih"][h] = e["Ih"].get(h, 0) + If
            e["Uch"][h] = e["Ih"][h] * (e["Xc"] / h) * math.sqrt(3)
    return est_list


def varredura(ped, est_list, hmax=25, n=2400):
    """|Z| na barra (Ω) com e sem o banco; picos (ressonâncias paralelas)."""
    Xs = _x_rede(ped)
    h = np.linspace(1.0, hmax, n)
    Zs = 1j * h * Xs
    Yb = sum(1 / (e["R_ohm"] + 1j * (h * e["Xl"] - e["Xc"] / h)) for e in est_list)
    Z = 1 / (1 / Zs + Yb)
    picos = [float(h[i]) for i in range(1, n - 1) if abs(Z[i]) > abs(Z[i - 1]) and abs(Z[i]) > abs(Z[i + 1]) and abs(Z[i]) > 1.5 * abs(Zs[i])]
    return dict(h=h, Z=np.abs(Z), Zs=np.abs(Zs), picos=picos)


def thd_tensao(ped, est_list):
    """THD de tensão na barra causado pela corrente harmônica da carga, sem e com o filtro (sintonizado)."""
    if not ped.harm_carga_a:
        return None
    Xs = _x_rede(ped)
    Un_f = ped.tensao_v / math.sqrt(3)
    s0 = s1 = 0.0
    det = {}
    for h, Ilh in ped.harm_carga_a.items():
        Zs = complex(0, h * Xs)
        Yf = sum(1 / complex(e["R_ohm"], h * e["Xl"] - e["Xc"] / h) for e in est_list)
        v0 = abs(Ilh * Zs) / Un_f * 100
        v1 = abs(Ilh / (1 / Zs + Yf)) / Un_f * 100
        det[h] = (v0, v1)
        s0 += v0 ** 2
        s1 += v1 ** 2
    return dict(sem=math.sqrt(s0), com=math.sqrt(s1), por_h=det)


def requisitos_reator(ped, e):
    """Requisitos do reator de um estágio para o motor do indutor + espectro de tensão sobre ele."""
    f1 = ped.freq_hz
    I1 = e["I1"] * math.sqrt(ped.sobretensao) * (1 + ped.tol_c_pct / 100) ** 0.5
    Ih2 = sum(v ** 2 for v in e["Ih"].values())
    Ith = math.sqrt(I1 ** 2 + Ih2) * 1.05
    Ihs = math.sqrt(Ih2)
    hdom = max(e["Ih"], key=lambda h: e["Ih"][h] * h) if e["Ih"] else 5
    L = e["L_uH"] * 1e-6
    fh = np.array([h * f1 for h in sorted(e["Ih"])])
    Vh = np.array([math.sqrt(2) * e["Ih"][h] * 2 * math.pi * h * f1 * L for h in sorted(e["Ih"])])
    ipk = math.sqrt(2) * (I1 + sum(e["Ih"].values()))
    lin = 1.8 if ped.tipo == "dessintonizado" else 1.5
    req = dict(L=L, In=Ith, I1=I1, Ipk=ipk, Isat=max(math.sqrt(2) * lin * e["I1"] / 0.97, ipk), Iovl=math.sqrt(2) * 2.2 * e["I1"],
               Iinv=e["I1"], rpp=2 * math.sqrt(2) * Ihs, rrms=Ihs, fs=hdom * f1, f1=f1, V=ped.tensao_v,
               Vdc=math.sqrt(2) * ped.tensao_v * 1.1, classe="H", P_max=P_W_POR_KVAR * e["Q_kvar"], k_Pmax=0.88,
               aplicacao=("reator de banco dessintonizado" if ped.tipo == "dessintonizado" else f"reator de filtro sintonizado ({e['ordem']:g}ª)"),
               linearidade=lin, tol_L_pct=(3.0 if ped.tipo == "dessintonizado" else 2.0))
    return req, (fh, Vh)


def dimensionar(ped, cat=None):
    """Cálculo elétrico de todos os estágios + varredura + THD. Não projeta o reator (ver processar)."""
    est = []
    for i, Q in enumerate(ped.estagios_kvar):
        if ped.tipo == "sintonizado":
            ordem = ped.ordens[i] if i < len(ped.ordens) else ped.ordens[-1]
            est.append(estagio(ped, Q, ordem=ordem))
        else:
            est.append(estagio(ped, Q, p=ped.p_pct / 100))
    if ped.tipo == "sintonizado" and len(est) > 1:   # fundo da rede com TODOS os ramos ligados (divisor na barra)
        Xs = _x_rede(ped)
        for h in list(est[0]["Ih"]):
            Vh = ped.harm_tensao_pct.get(h, 0) / 100 * ped.tensao_v / math.sqrt(3)
            Yf = [1 / complex(e["R_ohm"], h * e["Xl"] - e["Xc"] / h) for e in est]
            Vbus = Vh / (1 + complex(0, h * Xs) * sum(Yf))
            for e, y in zip(est, Yf):
                e["Ih"][h] = abs(Vbus * y)
                e["Uch"][h] = e["Ih"][h] * (e["Xc"] / h) * math.sqrt(3)
    if ped.harm_carga_a:                  # parcela da corrente harmônica da carga que entra no banco/filtro (divisor na barra)
        sintonizado_correntes_carga(ped, est)
    for e in est:
        Uc_arit = e["Uc1"] + sum(e["Uch"].values())
        Uc_rms = math.sqrt(e["Uc1"] ** 2 + sum(v ** 2 for v in e["Uch"].values()))
        Umin = max(ped.sobretensao * Uc_rms, Uc_arit / 1.1)
        Qn = lambda v, e=e: v ** 2 / e["Xc"] / 1e3
        Ucap, Qcap = capacitor_escolhido(Umin, Qn)
        e.update(Uc_arit=Uc_arit, Uc_rms=Uc_rms, U_cap_nom=Ucap, Q_cap_nom_kvar=Qcap,
                 C_delta_uF=e["C_uF_estrela"] / 3, I_cap_rms=math.sqrt(e["I1"] ** 2 + sum(v ** 2 for v in e["Ih"].values())))
        e["requisitos"], e["espectro"] = requisitos_reator(ped, e)
        e["custo_cap_R"] = Qcap * R_POR_KVAR_CAP
    vr = varredura(ped, est)
    avisos = []
    hs_rel = [h for h, u in ped.harm_tensao_pct.items() if u >= 0.5] + list(ped.harm_carga_a)
    for pk in vr["picos"]:
        for h in hs_rel:
            if abs(pk - h) / h < 0.10:
                avisos.append(f"Ressonância paralela em {pk:.2f}ª harmônica, a menos de 10 % da {h}ª presente na rede/carga.")
    if ped.tipo == "dessintonizado":
        ft = est[0]["h_sintonia"]
        if ped.harm_tensao_pct.get(3, 0) >= 1.0 and ft > 3:
            avisos.append(f"3ª harmônica de {ped.harm_tensao_pct[3]:g} % com sintonia em {ft:.2f}ª: usar p = 14 % (sintonia abaixo da 3ª).")
    thd = thd_tensao(ped, est)
    return dict(estagios=est, varredura=vr, thd=thd, avisos=avisos, x_rede_ohm=_x_rede(ped),
                Q_total_kvar=sum(ped.estagios_kvar))


def reatores_distintos(res):
    """Agrupa estágios com o mesmo reator (mesma L e corrente) – um projeto de indutor por grupo."""
    grupos = {}
    for i, e in enumerate(res["estagios"]):
        k = (round(e["L_uH"], 1), round(e["requisitos"]["In"], 1), e.get("ordem"))
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
        if int(h) % 3 == 0:            # sequência zero: não circula em banco trifásico a 3 fios (fica só no cálculo térmico)
            continue
        if h < nh:
            F[int(h)] = v * math.sqrt(2) * n / 2
    from .ind_avancado import _normalizar
    ia = np.fft.irfft(F, n)
    return _normalizar(t, ia, f1, I1_rms)
