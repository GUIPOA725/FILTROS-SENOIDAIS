"""Projeto de referência do indutor trifásico para filtro senoidal – para fabricação (v1.10.0).

Fluxo:  requisitos (da simulação do filtro) → pré-dimensionamento analítico (varredura núcleo × espiras × folha × canais)
        → elementos finitos 2D (ind_fem): ajuste do entreferro para L alvo, equalização das colunas, saturação no pico e na
          sobrecarga, nº de entreferros × distância bobina–núcleo (perdas por espraiamento), perdas no núcleo elemento a elemento
        → perdas totais → elevação de temperatura (IEC 60076-11) → sistema de isolação classe F/H (IEC 60085 / IEC 61857)
        → distâncias de isolação (IEC 60664-1 / IEC 61800-5-1) → forças no entreferro → lista de materiais e processo.

Todas as fórmulas e constantes estão aqui, com a origem. Incertezas declaradas no documento (2D, perdas no ferro com PWM).
"""
import math
import numpy as np

from .ind_fem import ModeloIndutor, MU0, BH_GO, perdas_harmonico, perdas_harmonico_multi

# Critério de escolha: MENOR CUSTO de material (como o fabricante) com perdas totais ≤ P_max = topo da faixa de mercado
# (Schaffner/REO interpolados para a corrente) – o mesmo número de "perdas desejadas" da ET do indutor.
CAPITALIZACAO_R_W = 1.5      # pequeno peso às perdas; o limite efetivo é P_max (faixa de mercado, igual à ET)
GAP_MAX_PECA_MM = 3.0       # entreferro máximo por peça (espraiamento e força); acima disso dividir em mais entreferros
GAP_MAX_PECA_CULATRA_MM = 10.0   # 2 entreferros nas juntas coluna–culatra (padrão nacional): calço de fibra até ~10 mm
GAP_MAX_FRAC_A = 0.20       # entreferro total por coluna ≤ 20 % da largura da coluna (fluxo de dispersão pela janela)

# ---------------------------------------------------------------------------------------------------------------------
# Materiais
CHAPAS = {
    "GO_M085-18": dict(nome="Aço-silício de grão orientado alta permeabilidade 0,18 mm (ex.: M085-18P / 18ZDKH)", norma="IEC 60404-8-7",
                       esp_mm=0.18, p17_50=0.85, rho=50e-8, dens=7650, kf=0.95, preco_kg=40.0),
    "GO_M120-27S": dict(nome="Aço-silício de grão orientado M120-27S (0,27 mm)", norma="IEC 60404-8-7", esp_mm=0.27,
                        p17_50=1.20, rho=48e-8, dens=7650, kf=0.96, preco_kg=28.0),
    "GO_M110-23S": dict(nome="Aço-silício de grão orientado M110-23S (0,23 mm)", norma="IEC 60404-8-7", esp_mm=0.23,
                        p17_50=1.10, rho=48e-8, dens=7650, kf=0.955, preco_kg=32.0),
    "GNO_M400-50A": dict(nome="Aço-silício de grão NÃO orientado M400-50A (0,50 mm) – só para comparação", norma="IEC 60404-8-4",
                         esp_mm=0.50, p17_50=5.6, rho=42e-8, dens=7700, kf=0.97, preco_kg=14.0),
}
CONDUTORES = {
    "AL": dict(nome="Alumínio para fins elétricos 1350-O (99,5 %) em folha", rho20=2.826e-8, alfa=0.00403, dens=2703,
               preco_kg=45.0, norma="ASTM B209 / ABNT NBR 7556 (folha 1350-O)"),
    "CU": dict(nome="Cobre eletrolítico ETP (C11000) recozido em folha", rho20=1.724e-8, alfa=0.00393, dens=8890,
               preco_kg=80.0, norma="IEC 60028 / ASTM B152"),
}
# Limites de elevação de temperatura do enrolamento (média, por resistência) – IEC 60076-11 (secos), ambiente 40 °C
CLASSE = {
    "F": dict(temp=155, elev_media=100, nome="F (155 °C)"),
    "H": dict(temp=180, elev_media=125, nome="H (180 °C)"),
}
PONTO_QUENTE_ACRESCIMO_K = 15.0       # IEC 60076-11: θ_classe = 40 + elevação média + 15 K (ponto quente)


def sistema_isolacao(classe):
    """Sistema de isolação (EIS) – cada componente com índice térmico ≥ classe. IEC 60085: a classe é do SISTEMA, avaliada
    conforme IEC 61857 / IEC 61858 (ou UL 1446); não basta um componente 'classe H'."""
    H = classe == "H"
    return [
        dict(item="Isolação entre camadas da folha", mat=("Papel aramida (Nomex® 410 ou equiv.) 0,13 mm, 2 camadas" if H else
                                                          "DMD 0,18 mm (poliéster-filme-poliéster) ou papel aramida"),
             ti=220 if H else 155, norma="IEC 60819 / IEC 60626", por_que="isola espira–espira; o DMD é classe F e NÃO serve em classe H"),
        dict(item="Reforço nas 2 primeiras e 2 últimas espiras", mat="+1 camada de papel aramida 0,13 mm", ti=220,
             norma="IEC 61800-5-1 / IEC 60034-18-41 (conceito)", por_que="os degraus de tensão do PWM (kV/µs) se concentram nas espiras de entrada"),
        dict(item="Cilindro/tubo da bobina (sobre o núcleo)", mat=("Laminado vidro-epóxi EP GC 203, 3 mm" if H else
                                                                   "Laminado vidro-epóxi EP GC 202/203, 3 mm"),
             ti=180 if H else 155, norma="IEC 60893-3-2", por_que="suporte mecânico e isolação bobina–núcleo"),
        dict(item="Espaçadores dos canais de ventilação (réguas)", mat=("Vidro-epóxi EP GC 203 ou vidro-silicone SI GC 202" if H else
                                                                       "Vidro-poliéster UP GM 203 (GPO-3) ou vidro-epóxi"),
             ti=180 if H else 155, norma="IEC 60893-3-2 / IEC 60893-3-5", por_que="o GPO-3 (UP GM 203) é 155 °C – só vale para classe F"),
        dict(item="Calços do entreferro", mat="Laminado vidro-epóxi EP GC 203 retificado (tolerância ±0,05 mm), colado com epóxi classe H",
             ti=180, norma="IEC 60893-3-2", por_que="define o entreferro e a indutância; precisa estabilidade dimensional a quente"),
        dict(item="Blocos de extremidade / calços de aperto", mat="Vidro-epóxi EP GC 203 ou pressboard aramídico (Nomex 993)",
             ti=180 if H else 155, norma="IEC 60893-3-2", por_que="fixação axial da bobina e distância à culatra"),
        dict(item="Impregnação", mat=("Verniz/resina classe H por VPI (poliéster-imida ou silicone, índice térmico ≥ 180 °C)" if H else
                                      "Verniz classe F por VPI ou imersão + estufa"),
             ti=180 if H else 155, norma="IEC 60464 / IEC 60455", por_que="consolida a bobina, reduz vibração/ruído a 4 kHz e protege contra umidade"),
        dict(item="Fitas de amarração", mat="Fita de fibra de vidro (ou vidro-poliéster termocontrátil classe H)", ti=180 if H else 155,
             norma="IEC 61067", por_que="amarração externa da bobina"),
        dict(item="Cabos/terminais de saída (se houver cabo)", mat="Cabo silicone 180 °C, 1 kV, ou barra direta", ti=180,
             norma="IEC 60245 / NBR NM 247", por_que="não pode ser PVC 70 °C/105 °C perto da bobina"),
        dict(item="Sensor térmico", mat=("PTC DIN 44081/44082 TNF 160 °C, 1 por bobina, em série" if H else
                                         "PTC DIN 44081/44082 TNF 140 °C, 1 por bobina, em série"),
             ti=None, norma="DIN 44081 / DIN 44082", por_que="desliga/alarma antes de o ponto quente passar da classe"),
    ]


# Distâncias de isolação adotadas (projeto) – base IEC 60664-1 / IEC 61800-5-1, tensão de isolação 1000 V (barramento PWM até
# ~650 V CC), categoria de sobretensão III (impulso 6 kV → separação ≥ 5,5 mm), grau de poluição 3 (painel ventilado com pó)
# → escoamento ≥ 12,5 mm (grupo IIIa). Valores adotados com folga:
DIST = dict(separacao_mm=10.0, escoamento_mm=16.0, bobina_culatra_mm=25.0, entre_fases_mm=20.0, borda_folha_mm=12.0)


# ---------------------------------------------------------------------------------------------------------------------
def requisitos(proj, cat=None):
    from .modelos import Pedido
    ped = Pedido.from_dict(proj.pedido) if isinstance(proj.pedido, dict) else proj.pedido
    l1 = proj.l1
    In = float(l1.i_nom_a)
    rpp = float(l1.ripple_pp_a)
    # v1.11: cobre pela carga (In térmica); ferro pelo inversor (Isat, sobrecarga 150 %)
    i_inv = max(float(ped.inversor_corrente_a or getattr(ped, "corrente_cliente_a", None) or In), In)
    return dict(L=float(l1.l_uh) * 1e-6, In=In, I1=float(l1.i_fund_a), Ipk=float(l1.i_pico_a),
                Isat=max(float(l1.i_sat_a), math.sqrt(2) * i_inv + rpp / 2), Iinv=i_inv,
                Iovl=1.5 * i_inv * math.sqrt(2) + rpp / 2, rpp=rpp, rrms=float(l1.ripple_rms_a), fs=float(proj.fs_hz),
                f1=float(ped.freq_rede_hz), V=float(ped.tensao_v), Vdc=1.35 * float(ped.tensao_v) * 1.10,
                classe="H")          # padrão Electric: sistema de isolação classe H com elevação limitada à de classe F (margem)


def _dowell(m, delta):
    """Fator de resistência CA de Dowell para m camadas de folha com espessura relativa delta = t/δ."""
    d = max(delta, 1e-6)
    a = (math.sinh(2 * d) + math.sin(2 * d)) / (math.cosh(2 * d) - math.cos(2 * d))
    b = (math.sinh(d) - math.sin(d)) / (math.cosh(d) + math.cos(d))
    return d * (a + 2 * (m * m - 1) / 3 * b)


def _steinmetz(ch):
    """Separação de perdas do aço: P(W/kg) = kh·f·B^β + ke·(f·B)^2 calibrado no P1,7/50 do catálogo (excesso k_exc = 2)."""
    d = ch["esp_mm"] * 1e-3
    pe_cl = (math.pi * d * 1.7 * 50) ** 2 / (6 * ch["rho"] * ch["dens"])      # W/kg clássica a 1,7 T / 50 Hz
    k_exc = 2.0
    ph = max(ch["p17_50"] - k_exc * pe_cl, 0.25 * ch["p17_50"])
    kh = ph / (50 * 1.7 ** 1.9)
    return kh, k_exc, d


MU_R_INC = 1500.0        # permeabilidade incremental dos laços menores sobre a polarização (GO, ~1 T) – para δ na lâmina


def espectro_tensao_indutor(proj, cat):
    """Espectro da tensão PWM sobre UM indutor (componente diferencial de fase), da simulação da plataforma no ponto de
    operação de f máx. Retorna (f_h [Hz], V_h [V pico]) só da alta frequência (exclui até 3·f1)."""
    from .dimensionamento import avaliar, pontos_operacao
    from .modelos import Pedido
    from .simulacao import simular
    ped = Pedido.from_dict(proj.pedido) if isinstance(proj.pedido, dict) else proj.pedido
    b = proj.banco
    cap = next((c for c in cat["capacitores"] if c["id"] == b.cap_id), None) or dict(id=b.cap_id, uf=b.uf_unit, v_ac=b.v_unit, preco=0)
    vdc = 1.35 * ped.tensao_v
    L2 = proj.l2.l_uh * 1e-6 if proj.l2 else 0.0
    p, _, _ = avaliar(ped, cat, proj.l1.l_uh * 1e-6, cap, (b.ligacao, b.n_por_ramo, b.c_y_uf * 1e-6), proj.fs_hz, vdc,
                      L2=L2, pts_por_portadora=24)
    op = pontos_operacao(ped, vdc, proj.fs_hz)[0]["op"]
    r = simular(p, op, pts_por_portadora=120, ciclos_analise=2)
    t = np.asarray(r.t)
    vl = np.asarray(r.u_ab) - np.asarray(r.vc_ab)
    n = len(vl)
    dt = t[1] - t[0]
    F = np.fft.rfft(vl) / n
    f = np.fft.rfftfreq(n, dt)
    V = 2 * np.abs(F) / math.sqrt(3)               # linha → fase (componente diferencial, sistema equilibrado)
    sel = f > 3 * op.f1
    return f[sel], V[sel]


def p_parasitas_lamina_Wkg(ch, f_h, B_h):
    """Perda por correntes parasitas (W/kg) na lâmina para fluxo médio imposto de amplitude B_h em cada frequência f_h,
    com efeito pelicular na lâmina: P = σω²d²B²/24 · (3/ξ)(sinh ξ − sin ξ)/(cosh ξ − cos ξ), ξ = d/δ (Lammeraner/Stafl)."""
    d, rho, dens = ch["esp_mm"] * 1e-3, ch["rho"], ch["dens"]
    w = 2 * math.pi * np.asarray(f_h)
    delta = np.sqrt(2 * rho / (w * MU0 * MU_R_INC))
    xi = d / delta
    fat = np.where(xi < 1e-3, 1.0, 3 / xi * (np.sinh(xi) - np.sin(xi)) / (np.cosh(xi) - np.cos(xi)))
    pv = (w ** 2) * d * d * np.asarray(B_h) ** 2 / (24 * rho) * fat
    return float((pv / dens).sum())


def perdas_nucleo_W(ch, massa_kg, Bpk_f, f1, dBpp, fs, espectro=None, NAe=None):
    kh, k_exc, d = _steinmetz(ch)
    rho, dens = ch["rho"], ch["dens"]
    ph1 = kh * f1 * Bpk_f ** 1.9
    pe1 = k_exc * (math.pi * d * f1 * Bpk_f) ** 2 / (6 * rho * dens)
    k_bias = 1.3                                                    # laços menores sobre polarização CC (literatura iGSE)
    phs = k_bias * kh * fs * (dBpp / 2) ** 2.0
    if espectro is not None and NAe:
        # P ∝ B² (a correção pelicular não depende de B): calcula 1× para NAe = 1 e escala por 1/NAe²
        chave = (id(espectro), ch["esp_mm"], ch["rho"])
        if chave not in _CACHE_AF:
            fh, Vh = espectro
            _CACHE_AF[chave] = K_EXC_AF * p_parasitas_lamina_Wkg(ch, fh, Vh / (2 * math.pi * fh * 1.0))
        pes = _CACHE_AF[chave] / NAe ** 2
    else:
        pes = K_EXC_AF * d * d / (12 * rho * dens) * (2 * dBpp * fs) ** 2  # fluxo triangular: <(dB/dt)²> = (2ΔBpp·fs)²
    return massa_kg * (ph1 + pe1), massa_kg * (phs + pes)


_CACHE_AF = {}
K_EXC_AF = 1.3        # perdas em excesso (paredes de domínio) sobre a clássica em AF – GO fino, laços menores (literatura)


def _geo(r, N, a, b, tf, hf, nd, c, cond, ch):
    """Geometria e massas para um candidato (unidades SI)."""
    ti = 0.26e-3                                   # 2 × 0,13 mm de aramida
    wd = 8e-3                                      # canal de ventilação axial
    tube, wrap = 3e-3, 1.5e-3
    build = N * (tf + ti) + 4 * 0.13e-3 + nd * wd + tube + wrap
    hc = hf + 2 * DIST["borda_folha_mm"] * 1e-3
    hw = hc + 2 * DIST["bobina_culatra_mm"] * 1e-3
    ww = 2 * (c + build) + DIST["entre_fases_mm"] * 1e-3
    MLT = 2 * (a + b) + 8 * (c + tube) + math.pi * build
    kf = ch["kf"]
    m_fe = (3 * a * b * hw + 2 * (3 * a + 2 * ww) * a * b) * kf * ch["dens"]
    m_cond = 3 * N * MLT * tf * hf * cond["dens"]
    return dict(build=build, hc=hc, hw=hw, ww=ww, MLT=MLT, m_fe=m_fe, m_cond=m_cond, ti=ti, wd=wd, tube=tube, wrap=wrap)


def pre_dimensionar(r, chapa="GO_M120-27S", cond_id="AL", h_conv=12.0, alvo_elev=None, amb_c=50.0, espectro=None, nd_min=0, fixo=None):
    """Varredura analítica: escolhe N, a, b, espessura e altura da folha, nº de canais, minimizando custo de material com a
    elevação média ≤ alvo e B(Isat) ≤ 1,45 T (garante L ≥ 90 % em Isat e ≥ 70 % na sobrecarga – conferido depois no FEM)."""
    ch, cond = CHAPAS[chapa], CONDUTORES[cond_id]
    cl = CLASSE[r["classe"]]
    alvo = alvo_elev or min(cl["elev_media"], 100.0)     # meta: elevação de classe F mesmo com materiais classe H (margem)
    T = 40 + alvo
    rhoT = cond["rho20"] * (1 + cond["alfa"] * (T - 20))
    delta = math.sqrt(rhoT / (math.pi * r["fs"] * MU0))
    Bsat_d = 1.45
    c = 15e-3
    melhor = None
    if fixo:
        N, a, b, tf, hf = fixo["N"], fixo["a"], fixo["b"], fixo["tf"], fixo["hf"]
        Aen = a * b * ch["kf"]
        g = _geo(r, N, a, b, tf, hf, nd_min, c, cond, ch)
        Bpk = r["L"] * r["I1"] * math.sqrt(2) / (N * Aen)
        dB = r["L"] * r["rpp"] / (N * Aen)
        R = rhoT * N * g["MLT"] / (tf * hf)
        p1, ps = perdas_nucleo_W(ch, g["m_fe"], Bpk, r["f1"], dB, r["fs"], espectro, N * Aen)
        d = dict(kae=None, N=N, a=a, b=b, tf=tf, hf=hf, nd=nd_min, c=c, Bpk=Bpk, dBpp=dB, custo=None, P_cu=None, P_fe1=p1, P_fes=ps,
                 dT_w=None, dT_fe=None, Fr=_dowell(N, tf / delta), delta=delta, R=R, rhoT=rhoT, **g)
        d.update(chapa=chapa, cond=cond_id, h_conv=h_conv, alvo=alvo, amb_c=amb_c)
        return d
    Ns = sorted(set(list(range(6, 41)) + list(range(42, 81, 2)) + list(range(85, 161, 5))))
    TF = np.array([0.2, 0.3, 0.4, 0.5, 0.6, 0.8, 1.0, 1.2, 1.5, 2.0]) * 1e-3
    HF = np.arange(40, 601, 20) * 1e-3
    ND = np.arange(nd_min, 5)
    tf_, hf_, nd_ = np.meshgrid(TF, HF, ND, indexing="ij")
    tf_, hf_, nd_ = tf_.ravel(), hf_.ravel(), nd_.ravel()
    ok_tf = tf_ <= 1.3 * delta
    ti, wd, tube, wrap = 0.26e-3, 8e-3, 3e-3, 1.5e-3
    for N in Ns:
        for kae in (1.0, 1.25, 1.5, 1.75, 2.0, 2.5):
            Ae = kae * r["L"] * r["Isat"] / (N * Bsat_d)
            for a_mm in range(30, 261, 10):
                a = a_mm * 1e-3
                b = Ae / (ch["kf"] * a)
                if not (0.9 <= b / a <= 2.2):
                    continue
                b = math.ceil(b * 1e3 / 5) * 5e-3
                Aen = a * b * ch["kf"]
                g_tot = MU0 * N * N * a * b * 1.10 / r["L"]
                if g_tot > GAP_MAX_FRAC_A * a or g_tot > 8 * GAP_MAX_PECA_MM * 1e-3:
                    continue
                Bpk = r["L"] * r["I1"] * math.sqrt(2) / (N * Aen)
                dB = r["L"] * r["rpp"] / (N * Aen)
                build = N * (tf_ + ti) + 4 * 0.13e-3 + nd_ * wd + tube + wrap
                hc = hf_ + 2 * DIST["borda_folha_mm"] * 1e-3
                hw = hc + 2 * DIST["bobina_culatra_mm"] * 1e-3
                ww = 2 * (c + build) + DIST["entre_fases_mm"] * 1e-3
                MLT = 2 * (a + b) + 8 * (c + tube) + math.pi * build
                m_fe = (3 * a * b * hw + 2 * (3 * a + 2 * ww) * a * b) * ch["kf"] * ch["dens"]
                m_cond = 3 * N * MLT * tf_ * hf_ * cond["dens"]
                R = rhoT * N * MLT / (tf_ * hf_)
                Fr = np.array([_dowell(N, t / delta) for t in TF])[np.searchsorted(TF, tf_)]
                P_cu = 3 * R * (r["I1"] ** 2 + Fr * r["rrms"] ** 2) * 1.10
                kh, k_exc, dl = _steinmetz(ch)
                p1_kg = kh * r["f1"] * Bpk ** 1.9 + k_exc * (math.pi * dl * r["f1"] * Bpk) ** 2 / (6 * ch["rho"] * ch["dens"])
                _, ps1 = perdas_nucleo_W(ch, 1.0, Bpk, r["f1"], dB, r["fs"], espectro, N * Aen)
                p1 = m_fe * p1_kg
                ps = m_fe * ps1
                perim_out = 2 * (a + b) + 8 * (c + build)
                perim_in = 2 * (a + b) + 8 * c
                A_w = (perim_out + 0.5 * perim_in + nd_ * 2 * 0.6 * (perim_in + perim_out) / 2) * hc
                dT_w = (P_cu / 3) / (h_conv * A_w)
                A_fe = 2 * (3 * a + 2 * ww) * (2 * a + hw) * 0.55 + 2 * (3 * a + 2 * ww) * b
                dT_fe = (p1 + ps) / (h_conv * A_fe)
                custo = m_fe * ch["preco_kg"] + m_cond * cond["preco_kg"] + CAPITALIZACAO_R_W * (P_cu + p1 + ps)
                val = ok_tf & (dT_w <= alvo) & (dT_fe <= alvo)
                if r.get("P_max"):
                    val &= (P_cu + p1 + ps) <= r["P_max"] * r.get("k_Pmax", 0.88)
                if not val.any():
                    continue
                i = int(np.argmin(np.where(val, custo, np.inf)))
                if melhor is None or custo[i] < melhor["custo"]:
                    g = _geo(r, N, a, b, float(tf_[i]), float(hf_[i]), int(nd_[i]), c, cond, ch)
                    melhor = dict(kae=kae, N=N, a=a, b=b, tf=float(tf_[i]), hf=float(hf_[i]), nd=int(nd_[i]), c=c, Bpk=Bpk, dBpp=dB,
                                  custo=float(custo[i]), P_cu=float(P_cu[i]), P_fe1=float(p1[i]), P_fes=float(ps[i]), dT_w=float(dT_w[i]),
                                  dT_fe=float(dT_fe[i]), Fr=float(Fr[i]), delta=delta, R=float(R[i]), rhoT=rhoT, **g)
    if melhor:
        melhor.update(chapa=chapa, cond=cond_id, h_conv=h_conv, alvo=alvo, amb_c=amb_c)
    return melhor


# ---------------------------------------------------------------------------------------------------------------------
def _condutores(d, gaps_xl, a, ng_lado=None):
    """Lista de condutores (folha) para o modelo FEM: cada espira = 1 retângulo de cada lado de cada coluna."""
    out = []
    y0 = a + DIST["bobina_culatra_mm"] * 1e-3 + DIST["borda_folha_mm"] * 1e-3
    y1 = y0 + d["hf"]
    passo = d["tf"] + d["ti"]
    # canais distribuídos igualmente entre as camadas
    pos_canal = set(round((k + 1) * d["N"] / (d["nd"] + 1)) for k in range(d["nd"]))
    for i, x0 in enumerate(gaps_xl):
        r = d["c"] + d["tube"] + 2 * 0.13e-3
        for k in range(d["N"]):
            if k in pos_canal:
                r += d["wd"]
            xr0 = x0 + a + r
            out.append(dict(x0=xr0, x1=xr0 + d["tf"], y0=y0, y1=y1, fase=i, lado=-1, esp=k))
            xl1 = x0 - r
            out.append(dict(x0=xl1 - d["tf"], x1=xl1, y0=y0, y1=y1, fase=i, lado=+1, esp=k))
            r += passo
    return out


def modelo(d, gaps, ng):
    a = d["a"]
    xl = [i * (a + d["ww"]) for i in range(3)]
    cond = _condutores(d, xl, a)
    return ModeloIndutor(dict(a=a, b=d["b"], hw=d["hw"], ww=d["ww"], ng=ng, gaps=list(gaps), condutores=cond,
                              pos_gap=d.get("pos_gap", "distribuido")))


def L_fases(M, b, mu_r=4000, extra_3d=None):
    Lm = M.matriz_L(mu_r) * b
    Lp = np.array([Lm[k, k] - 0.5 * sum(Lm[k, j] for j in range(3) if j != k) for k in range(3)])
    return Lp, Lm


def correcao_3d(d, Lp2d, M, mu_r=4000):
    """O corte 2D vê o espraiamento e a dispersão só nas faces laterais da coluna (profundidade b); no 3D eles existem também
    nas faces da frente e de trás (largura a) e nas cabeceiras da bobina. Correção: parcela 'não ideal' × (a+b)/b."""
    N = d["N"]
    L0 = MU0 * N * N * d["a"] * d["b"] / np.array(M.g["gaps"])        # sem espraiamento, ferro ideal
    # ferro ideal: refaz com μr muito alto para isolar espraiamento + dispersão
    Lp_ideal, _ = L_fases(M, d["b"], mu_r=1e6)
    extra2d = Lp_ideal - L0
    fator_ferro = Lp2d / Lp_ideal
    return (L0 + extra2d * (d["a"] + d["b"]) / d["b"]) * fator_ferro


def projetar(proj, cat=None, chapa="GO_M120-27S", cond_id="AL", h_conv=12.0, amb_c=50.0, log=print, construcao="distribuido"):
    """Projeto completo; se a elevação calculada no FEM passar da meta, acrescenta canal de ventilação e refaz (até 3×)."""
    nd_min, fixo, k_pmax = 0, None, 0.88
    for tent in range(5):
        d = _projetar(proj, cat, chapa, cond_id, h_conv, amb_c, log, nd_min, fixo, k_pmax, construcao)
        pmax = d["requisitos"].get("P_max")
        if pmax and d["perdas"]["total"] > pmax and fixo is None and k_pmax > 0.6:
            k_pmax -= 0.08
            log(f"   Perdas {d['perdas']['total']:.0f} W > {pmax:.0f} W (mercado) → refazendo com limite mais apertado")
            continue
        if d["termico"]["elev_bobina_K"] <= d["termico"]["meta_elev_K"] + 0.5:
            break
        nd_min = d["nd"] + 1
        fixo = dict(N=d["N"], a=d["a"], b=d["b"], tf=d["tf"], hf=d["hf"])     # mesmo núcleo e folha: só acrescenta canal
        log(f"   Elevação {d['termico']['elev_bobina_K']:.0f} K > meta {d['termico']['meta_elev_K']:.0f} K → refazendo com {nd_min} canal(is)")
    d["tentativas_termico"] = tent + 1
    return d


def _projetar(proj, cat, chapa, cond_id, h_conv, amb_c, log, nd_min=0, fixo=None, k_pmax=0.88, construcao="distribuido"):
    r = requisitos(proj, cat)
    try:
        esp = espectro_tensao_indutor(proj, cat)
    except Exception as e:
        log(f"   (espectro da tensão no indutor não obtido: {e}; usando ondulação triangular)")
        esp = None
    r["V_AF_rms"] = float(np.sqrt((esp[1] ** 2).sum() / 2)) if esp is not None else None
    try:
        from .spec_indutor import referencia_mercado
        _fx = referencia_mercado(r["In"], cat or {})[2]
        r["P_max"] = float(_fx["perdas_w"][1]) if _fx else None
    except Exception:
        r["P_max"] = None
    r["k_Pmax"] = k_pmax
    d = pre_dimensionar(r, chapa, cond_id, h_conv, amb_c=amb_c, espectro=esp, nd_min=nd_min, fixo=fixo)
    if not d:
        raise RuntimeError("pré-dimensionamento sem solução – rever limites")
    log(f"   Indutor: pré-dimensionamento N={d['N']}, coluna {d['a']*1e3:.0f}×{d['b']*1e3:.0f} mm, folha {d['tf']*1e3:.1f}×{d['hf']*1e3:.0f} mm, "
        f"{d['nd']} canais")
    cond = CONDUTORES[cond_id]
    ch = CHAPAS[chapa]
    sig = 1 / d["rhoT"]
    # ------------------------------------------------ 1) nº de entreferros × distância bobina–núcleo (FEM harmônico)
    fh_i, Ih = (esp[0], esp[1] / (2 * math.pi * esp[0] * r["L"])) if esp is not None else (np.array([r["fs"]]), np.array([r["rrms"] * math.sqrt(2)]))
    r["I_AF_rms_espectro"] = float(np.sqrt((Ih ** 2).sum() / 2))
    g_tot0 = MU0 * d["N"] ** 2 * d["a"] * d["b"] * 1.10 / r["L"]

    def perdas_enrolamento(dd, gaps, ng, freqs=None):
        M = modelo(dd, gaps, ng)
        ell = [dd["MLT"] / 2] * len(M.g["condutores"])
        fr = freqs or [r["fs"], 2 * r["fs"], 4 * r["fs"]]
        Rac = {}
        for f in [r["f1"]] + fr:
            Ps, _ = perdas_harmonico_multi(M, f, [[1.0, 0, 0], [0, 1.0, 0]], sig, ell)   # 1 fatoração, 2 excitações
            Rk = [P.sum() / 0.5 for P in Ps]             # R_ac da fase k (inclui correntes induzidas nas outras fases)
            Rac[f] = (2 * Rk[0] + Rk[1]) / 3            # média das 3 fases (a = c)
        P60 = 3 * 0.5 * (r["I1"] * math.sqrt(2)) ** 2 * Rac[r["f1"]]
        lf = np.log(np.array(fr))
        lr = np.log(np.array([Rac[f] for f in fr]))
        x = np.log(fh_i)
        if len(lf) > 1:
            y = np.interp(x, lf, lr)
            k_ext = max((lr[-1] - lr[-2]) / (lf[-1] - lf[-2]), 0.5)
        else:
            y = np.full_like(x, lr[0])
            k_ext = 0.5                                   # acima da última frequência: R ∝ f^k (pelicular ≥ 0,5)
        y = np.where(x > lf[-1], lr[-1] + k_ext * (x - lf[-1]), y)
        y = np.where(x < lf[0], lr[0] + 0.5 * (x - lf[0]), y)
        R_h = np.exp(y)
        P_AF = 3 * float((0.5 * Ih ** 2 * R_h).sum())
        return dict(P60=P60, P_AF=P_AF, Rac=Rac, M=M)

    estudo_gap = []
    d["pos_gap"] = "culatra" if construcao == "culatra" else "distribuido"
    lista_ng = (2,) if construcao == "culatra" else (1, 2, 3, 4, 6, 8)
    for ng in lista_ng:
        if construcao != "culatra" and g_tot0 / ng > GAP_MAX_PECA_MM * 1e-3 * 1.2:
            continue
        for c_mm in (15, 25):
            dd = dict(d, c=c_mm * 1e-3)
            dd.update(_geo(r, d["N"], d["a"], d["b"], d["tf"], d["hf"], d["nd"], dd["c"], cond, ch))
            pe = perdas_enrolamento(dd, [g_tot0] * 3, ng, freqs=[2 * r["fs"]])
            estudo_gap.append(dict(ng=ng, c_mm=c_mm, g_cada_mm=g_tot0 / ng * 1e3, P60_W=pe["P60"], P_AF_W=pe["P_AF"],
                                   P_W=pe["P60"] + pe["P_AF"]))
            log(f"     ng={ng} c={c_mm} mm: enrolamento {pe['P60']:.0f} W (60 Hz) + {pe['P_AF']:.0f} W (AF)")
    # escolha: menor nº de entreferros cuja perda total no enrolamento fica ≤ 5 % acima da melhor; depois menor c
    Pmin = min(e["P_W"] for e in estudo_gap)
    lim_peca = GAP_MAX_PECA_CULATRA_MM if construcao == "culatra" else GAP_MAX_PECA_MM
    ok = [e for e in estudo_gap if e["P_W"] <= 1.05 * Pmin and e["g_cada_mm"] * 1.15 <= lim_peca] or \
         [e for e in estudo_gap if e["P_W"] <= 1.05 * Pmin]
    esc = min(ok, key=lambda e: (e["ng"], e["c_mm"]))
    d["c"] = esc["c_mm"] * 1e-3
    d.update(_geo(r, d["N"], d["a"], d["b"], d["tf"], d["hf"], d["nd"], d["c"], cond, ch))
    d["R"] = d["rhoT"] * d["N"] * d["MLT"] / (d["tf"] * d["hf"])
    ng = esc["ng"]
    log(f"   FEM: {ng} entreferro(s) por coluna, bobina a {esc['c_mm']} mm do núcleo")
    # ------------------------------------------------ 2) ajuste do entreferro para L alvo (3D corrigido) e equalização
    gaps = [g_tot0] * 3
    for it in range(6):
        M = modelo(d, gaps, ng)
        Lp2d, Lm = L_fases(M, d["b"])
        L3 = correcao_3d(d, Lp2d, M)
        if np.all(np.abs(L3 / r["L"] - 1) < 0.003):
            break
        gaps = [g * (L3[k] / r["L"]) ** 1.0 for k, g in enumerate(gaps)]
    d["gaps"] = gaps
    d["ng"] = ng
    d["avisos"] = []
    _gmax = max(gaps)
    _lim_p = GAP_MAX_PECA_CULATRA_MM if d.get("pos_gap") == "culatra" else GAP_MAX_PECA_MM
    if _gmax > GAP_MAX_FRAC_A * d["a"] or _gmax / ng * 1e3 > _lim_p * 1.15:
        d["avisos"].append(f"Entreferro após o ajuste de L: {_gmax * 1e3:.1f} mm por coluna ({_gmax / ng * 1e3:.1f} mm por peça) – acima do "
                           f"recomendado (≤ {GAP_MAX_FRAC_A * 100:.0f} % da coluna = {GAP_MAX_FRAC_A * d['a'] * 1e3:.0f} mm; ≤ {_lim_p:g} mm por "
                           "peça). Construção pouco recomendada: espraiamento alto, força e ruído maiores.")
        log("   ! " + d["avisos"][-1])
    d["L3d"] = L3
    d["L2d"] = Lp2d
    d["Lmat"] = Lm
    # ------------------------------------------------ 3) saturação: L aparente em Ipk, Isat e sobrecarga (não-linear)
    sat = []
    for nome, I in (("Pico em operação", r["Ipk"]), ("Isat (exigido ≥ 90 %)", r["Isat"]), ("Sobrecarga 1,5×I inversor (exigido ≥ 70 %)", r["Iovl"])):
        Mn = modelo(d, gaps, ng)
        A = Mn.resolver([I, -I / 2, -I / 2])
        lam = Mn.lambda_fases(A) * d["b"]
        # fase a com correntes (I, −I/2, −I/2): λa = (Laa − Mab/2 − Mac/2)·I  → L+ aparente da coluna lateral
        Lap2 = lam[0] / I
        if nome.startswith("Isat"):
            A2 = Mn.resolver([-I / 2, I, -I / 2])
            lam2 = Mn.lambda_fases(A2) * d["b"]
            Lbp = lam2[1] / I
        else:
            Lbp = float("nan")                          # coluna central só em Isat (economia de tempo; lateral é o pior caso)
        Bx, By = Mn.B(A)
        Bmax = float(np.hypot(Bx, By)[Mn.ferro].max())
        sat.append(dict(caso=nome, I=I, L_lat_pct=100 * Lap2 / Lp2d[0], L_cen_pct=100 * Lbp / Lp2d[1], Bmax=Bmax))
        if nome.startswith("Pico"):
            d["campo_pico"] = (Mn, A)
    d["saturacao"] = sat
    # ------------------------------------------------ 4) perdas: núcleo (por elemento), enrolamento (CC + CA + espraiamento)
    Mn, A = d["campo_pico"]
    Bpk_el = np.zeros(int(Mn.ferro.sum()))
    I1p = r["I1"] * math.sqrt(2)
    for k in range(2):                                  # fases U e V; W é o espelho de U (simetria do núcleo)
        cur = [-I1p / 2] * 3
        cur[k] = I1p
        Ak = Mn.resolver(cur)
        Bx, By = Mn.B(Ak)
        Bk = np.hypot(Bx, By)
        Bpk_el = np.maximum(Bpk_el, Bk[Mn.ferro])
        if k == 0:                                      # espelho x → W − x
            cx = Mn.m.cent[Mn.ferro, 0]
            cy = Mn.m.cent[Mn.ferro, 1]
            from scipy.spatial import cKDTree
            arv = cKDTree(np.column_stack([cx, cy]))
            _, idx = arv.query(np.column_stack([Mn.W - cx, cy]))
            Bpk_el = np.maximum(Bpk_el, Bk[Mn.ferro][idx])
    Ml = modelo(d, gaps, ng)
    Ml.matriz_L()
    dB2 = np.zeros(int(Ml.ferro.sum()))
    for k in range(3):
        Bx, By = Ml.B(Ml._sol_unit[k])
        dB2 += (np.hypot(Bx, By)[Ml.ferro] * r["rpp"]) ** 2
    dBpp_el = np.sqrt(dB2)
    vol_el = Mn.m.area[Mn.ferro] * d["b"] * ch["kf"]
    m_el = vol_el * ch["dens"]
    kh, k_exc, dlam = _steinmetz(ch)
    P_fe1 = float((m_el * (kh * r["f1"] * Bpk_el ** 1.9 + k_exc * (math.pi * dlam * r["f1"] * Bpk_el) ** 2 / (6 * ch["rho"] * ch["dens"]))).sum())
    NAe = d["N"] * d["a"] * d["b"] * ch["kf"]
    dB_ref = r["L"] * r["rpp"] / NAe
    p_ref_e = (K_EXC_AF * p_parasitas_lamina_Wkg(ch, esp[0], esp[1] / (2 * math.pi * esp[0] * NAe)) if esp is not None else
               K_EXC_AF * dlam ** 2 / (12 * ch["rho"] * ch["dens"]) * (2 * dB_ref * r["fs"]) ** 2)
    P_fes = float((m_el * (1.3 * kh * r["fs"] * (dBpp_el / 2) ** 2 + p_ref_e * (dBpp_el / dB_ref) ** 2)).sum())
    d["m_fe_fem"] = float(m_el.sum())
    pe = perdas_enrolamento(d, gaps, ng)
    d["Rac_ohm"] = {f"{k:.0f} Hz": v for k, v in pe["Rac"].items()}
    d["Rdc_ohm"] = d["R"]
    d["perdas"] = dict(enrolamento_60Hz=pe["P60"], enrolamento_AF=pe["P_AF"], nucleo_60Hz=P_fe1, nucleo_AF=P_fes)
    d["perdas"]["total"] = sum(d["perdas"].values())
    d["Bpk_max"] = float(Bpk_el.max())
    d["Bpk_coluna"] = float(np.percentile(Bpk_el, 50))
    d["dBpp_coluna"] = float(np.percentile(dBpp_el, 50))
    # ------------------------------------------------ 5) térmico (IEC 60076-11)
    a, b, c = d["a"], d["b"], d["c"]
    perim_out = 2 * (a + b) + 8 * (c + d["build"])
    perim_in = 2 * (a + b) + 8 * c
    A_w = (perim_out + 0.5 * perim_in + d["nd"] * 2 * 0.6 * (perim_in + perim_out) / 2) * d["hc"]
    P_w = (d["perdas"]["enrolamento_60Hz"] + d["perdas"]["enrolamento_AF"]) / 3
    dT_w = P_w / (h_conv * A_w)
    A_fe = 2 * (3 * a + 2 * d["ww"]) * (2 * a + d["hw"]) * 0.55 + 2 * (3 * a + 2 * d["ww"]) * b
    dT_fe = (P_fe1 + P_fes) / (h_conv * A_fe)
    cl = CLASSE[r["classe"]]
    d["termico"] = dict(h_conv=h_conv, A_bobina_m2=A_w, elev_bobina_K=dT_w, elev_nucleo_K=dT_fe,
                        ponto_quente_C=amb_c + dT_w + PONTO_QUENTE_ACRESCIMO_K, amb_painel_C=amb_c,
                        limite_elev_K=cl["elev_media"], limite_temp_C=cl["temp"], meta_elev_K=d["alvo"])
    # ------------------------------------------------ 6) forças no entreferro, dimensões, massa
    Bg = d["Bpk_coluna"]
    Ag = a * b
    d["forca_gap_N"] = Bg ** 2 * Ag / (2 * MU0)
    W = 3 * a + 2 * d["ww"]
    H = 2 * a + d["hw"]
    D = b + 2 * (c + d["build"]) + 2 * 0.03
    d["dims_mm"] = dict(largura=W * 1e3 + 2 * 15, altura=H * 1e3 + 60, profundidade=max(D, b + 0.12) * 1e3)
    d["massa_kg"] = dict(nucleo=d["m_fe"], condutor=d["m_cond"], isolacao_ferragens=0.12 * (d["m_fe"] + d["m_cond"]))
    d["massa_kg"]["total"] = sum(d["massa_kg"].values())
    d["requisitos"] = r
    d["estudo_gap"] = estudo_gap
    d["isolacao"] = sistema_isolacao(r["classe"])
    d["chapa_dados"], d["cond_dados"] = ch, cond
    return d


# Indutores Cootrans já fornecidos à Electric (dados de placa/desenho/orçamento) – usados para calibrar o método
INDUTORES_REFERENCIA = [
    dict(nome="Cootrans RTUC17 (D 192130) – IHR 2022", L=1586e-6, In=28, V=380, fs=4000, massa=20, dims=(320, 270, 150),
         fonte="desenho D 192130 (máx. 270 × 320 × 150, 20 kg, classe F, Al)"),
    dict(nome="Cootrans 0,588 mH / 135 A (orç. ABB 2018)", L=588e-6, In=135, V=480, fs=4000, massa=90, dims=(480, 410, 240),
         fonte="descritivo/preço Cootrans (A 480 × L 410 × P 240, 90 kg)"),
    dict(nome="Cootrans 0,336 mH / 217 A (orç. ABB 2018)", L=336e-6, In=217, V=440, fs=4000, massa=130, dims=(600, 440, 260),
         fonte="descritivo/preço Cootrans (A 600 × L 440 × P 260, 130 kg)"),
]


def calibracao(chapa="GO_M120-27S", cond_id="AL"):
    """Roda o pré-dimensionamento (mesmo método) para os indutores Cootrans reais e compara massa e dimensões."""
    out = []
    for ref in INDUTORES_REFERENCIA:
        L, In, V, fs = ref["L"], ref["In"], ref["V"], ref["fs"]
        vdc = 1.35 * V
        rpp = min(vdc / (8 * L * fs) * 1.5, 0.6 * In)
        r = dict(L=L, In=In, I1=In * 0.98, Ipk=In * 1.414 + rpp / 2, Isat=1.25 * In * 1.414 + rpp / 2, Iovl=1.5 * In * 1.414 + rpp / 2,
                 rpp=rpp, rrms=rpp / math.sqrt(12), fs=fs, f1=60, V=V, Vdc=vdc * 1.1, classe="H")
        d = pre_dimensionar(r, chapa, cond_id, h_conv=12.0, alvo_elev=100, amb_c=40)
        if not d:
            out.append(dict(ref=ref, ok=False))
            continue
        W = (3 * d["a"] + 2 * d["ww"]) * 1e3
        H = (2 * d["a"] + d["hw"]) * 1e3 + 110
        D = (d["b"] + 2 * (d["c"] + d["build"])) * 1e3
        out.append(dict(ref=ref, ok=True, N=d["N"], a=d["a"] * 1e3, b=d["b"] * 1e3, tf=d["tf"] * 1e3, hf=d["hf"] * 1e3,
                        dims=(H, W, D), massa=(d["m_fe"] + d["m_cond"]) * 1.12, perdas=d["P_cu"] + d["P_fe1"] + d["P_fes"]))
    return out
