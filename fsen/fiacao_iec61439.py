"""Fiação INTERNA dos painéis (banco dessintonizado, filtro sintonizado e filtro senoidal) pela ABNT NBR IEC 61439-1 – v1.29.0.

REQ-PNL-031/032 (engenheiro, 25/11/2026): o painel é um CONJUNTO de manobra e comando – a fiação interna segue a
NBR IEC 61439-1/-2 (e, nos bancos, a IEC 61921, que manda atender a 61439). A NBR 5410 (§1.4) só trata dos conjuntos
"no que concerne à sua seleção e condições de instalação" – ela fica para os cabos de CAMPO (cliente → painel, painel → motor).

Prática Electric (engenheiro, 25/11 21:50): canaleta é só COMANDO; os cabos de FORÇA correm por fora das canaletas,
normalmente espaçados (≥ 1 diâmetro, dá para medir) – no máximo encostados uns nos outros.

Método (NBR IEC 61439-1, verificação da elevação de temperatura por cálculo – §10.10.4.2.1 f) / §10.10.4.3.1 f)):
  • seção mínima para 125 % da corrente do circuito;
  • cabos escolhidos pela IEC 60364-5-52 com o exemplo de adaptação do Anexo H: Imax = I30 × k1 × k2, condutor a 70 °C
    (os bornes dos dispositivos são ensaiados com condutor a 70 °C), k1 pela temperatura do ar DENTRO do painel (Tab. H.2),
    k2 pelo arranjo (0,80 canaleta / 0,88 encostados / 1,00 espaçados ≥ 1 diâmetro);
  • se o fabricante do dispositivo pedir seção maior (borne), usar a maior;
  • componentes a no máximo 80 % da corrente térmica ao ar livre (Ith) / In (contatora: AC-1) – §10.10.4.x c);
  • perdas dos condutores: Pv = I²·R20·[1 + 0,004·(Tc − 20)] por condutor (entram na térmica do painel).
"""
import math

NORMA = "NBR IEC 61439-1 §10.10.4.3.1 f) + Anexo H (IEC 60364-5-52)"

# Tabela H.1 – cabo unipolar de cobre, condutor 70 °C, ar interno 55 °C: seção → (R20 Ω/km, canaleta, encostados, espaçados) [A]
H1 = {1.5: (12.1, 7.6, 9.6, 15), 2.5: (7.41, 10, 13, 21), 4: (4.61, 14, 18, 28), 6: (3.08, 18, 24, 36), 10: (1.83, 24, 33, 50),
      16: (1.15, 33, 45, 67), 25: (0.727, 43, 61, 89), 35: (0.524, 54, 76, 110), 50: (0.387, 65, 93, 134),
      70: (0.268, 83, 120, 171), 95: (0.193, 101, 147, 208), 120: (0.153, 117, 171, 242), 150: (0.124, None, 198, 278),
      185: (0.099, None, 227, 318), 240: (0.075, None, 269, 375), 300: (0.060, None, 311, 432)}
# Tabela H.2 – k1 (condutor 70 °C) × temperatura do ar dentro do conjunto (extrato da IEC 60364-5-52 Tab. B.52.14)
H2 = {20: 1.12, 25: 1.06, 30: 1.00, 35: 0.94, 40: 0.87, 45: 0.79, 50: 0.71, 55: 0.61, 60: 0.50}
ARRANJOS = {"canaleta": (1, "em canaleta (k2 0,80)"), "encostados": (2, "encostados ao ar/placa (k2 0,88)"),
            "espacados": (3, "espaçados ≥ 1 diâmetro ao ar (k2 1,00)")}
# Ar interno de projeto = limite verificado da térmica do painel (IEC 60890, ≤ 55 °C) – a seção vale enquanto a térmica passar
T_AR_INTERNO_C = 55.0
ARRANJO_FORCA = "espacados"          # padrão Electric: força por fora da canaleta, espaçados (medível)
FATOR_125 = 1.25


def k1(T):
    ks = sorted(H2)
    T = min(max(float(T), ks[0]), ks[-1])
    for a, b in zip(ks, ks[1:]):
        if a <= T <= b:
            return H2[a] + (H2[b] - H2[a]) * (T - a) / (b - a)
    return H2[ks[-1]]


def imax(secao, arranjo=ARRANJO_FORCA, T_ar=T_AR_INTERNO_C):
    """Corrente máxima (A) do cabo unipolar de cobre no painel (Anexo H) – None se a tabela não tem o caso."""
    col = ARRANJOS[arranjo][0]
    v = H1[secao][col]
    return None if v is None else v * k1(T_ar) / H2[55]


def d_ext_mm(secao):
    """Diâmetro externo estimado do cabo flexível 0,6/1 kV (classe 5) – o espaçamento é ≥ 1 diâmetro."""
    iso = {1.5: 0.8, 2.5: 0.8, 4: 1.0, 6: 1.0, 10: 1.0, 16: 1.0, 25: 1.2, 35: 1.2, 50: 1.4, 70: 1.4, 95: 1.6, 120: 1.6,
           150: 1.8, 185: 2.0, 240: 2.2, 300: 2.4}.get(secao, 1.6)
    return round(1.15 * 1.128 * math.sqrt(secao) + 2 * iso, 1)


def cabo(I, arranjo=ARRANJO_FORCA, T_ar=T_AR_INTERNO_C, borne_min_mm2=0.0, max_secao=240, fator=FATOR_125):
    """Menor seção (e nº de cabos em paralelo por fase) com Imax ≥ fator × I. Devolve dict com a memória de cálculo."""
    I = float(I)
    req = fator * I
    for npar in (1, 2, 3, 4):
        for s in sorted(H1):
            if s > max_secao or s < borne_min_mm2:
                continue
            im = imax(s, arranjo, T_ar)
            if im and npar * im * (0.88 if (npar > 1 and arranjo != "espacados") else 1.0) >= req:
                Iz = npar * im * (0.88 if (npar > 1 and arranjo != "espacados") else 1.0)
                R20 = H1[s][0]
                Tc = 70.0
                pv = (I / npar) ** 2 * R20 / 1000 * (1 + 0.004 * (Tc - 20))      # W/m por condutor (pior caso: 70 °C)
                return dict(secao=s, paralelos=npar, Iz=round(Iz, 1), I=round(I, 1), I_req=round(req, 1), arranjo=arranjo,
                            arranjo_txt=ARRANJOS[arranjo][1], T_ar=T_ar, k1=round(k1(T_ar), 3), fator=fator,
                            d_ext_mm=d_ext_mm(s), Pv_W_m=round(pv, 2), norma=NORMA,
                            texto=(f"{npar}×{s:g} mm² Cu" if npar > 1 else f"{s:g} mm² Cu") +
                                  f" – {ARRANJOS[arranjo][1]}, ar interno {T_ar:g} °C (k1 {k1(T_ar):.2f}), condutor 70 °C: "
                                  f"Imax {Iz:.0f} A ≥ 125 % × {I:.0f} A = {req:.0f} A ({NORMA})",
                            # compatibilidade com quem lia o dict antigo (cabo_nbr5410)
                            I0=round(Iz / max(k1(T_ar), 1e-6), 1), FCT=round(k1(T_ar), 3), FCA=1.0, T_int=T_ar, n_agrup=1)
    s = max(x for x in H1 if x <= max_secao)
    return dict(secao=s, paralelos=4, Iz=0.0, I=round(I, 1), I_req=round(req, 1), arranjo=arranjo, arranjo_txt=ARRANJOS[arranjo][1],
                T_ar=T_ar, k1=round(k1(T_ar), 3), fator=fator, d_ext_mm=d_ext_mm(s), Pv_W_m=0.0, norma=NORMA,
                texto=f"SEM SOLUÇÃO até 4×{s:g} mm² – rever arranjo/corrente", I0=0, FCT=k1(T_ar), FCA=1.0, T_int=T_ar, n_agrup=1)


def componente_ok(I_circuito, I_nominal_componente):
    """§10.10.4.x c): corrente do circuito ≤ 80 % da corrente térmica/nominal do componente."""
    return float(I_circuito) <= 0.8 * float(I_nominal_componente)


def regra_texto():
    return ("Fiação interna pela NBR IEC 61439-1 (§10.10.4.3.1 f), Anexo H): seção para 125 % da corrente, condutor a 70 °C, "
            f"ar interno {T_AR_INTERNO_C:g} °C (limite da térmica do painel), cabos de FORÇA fora das canaletas e espaçados "
            "≥ 1 diâmetro (canaleta só para comando); componentes a ≤ 80 % da corrente nominal (§10.10.4.3.1 c). "
            "NBR 5410 só para os cabos de campo (cliente → painel, painel → motor).")
