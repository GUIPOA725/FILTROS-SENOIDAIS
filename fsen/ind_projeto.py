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
GAP_MAX_FRAC_A = 0.20
SUB_ISO_MM = 0.5          # isolação entre as partes do condutor subdividido (papel/esmalte + folga)       # entreferro total por coluna ≤ 20 % da largura da coluna (fluxo de dispersão pela janela)

# ---------------------------------------------------------------------------------------------------------------------
# Materiais
CHAPAS = {
    "GO_M085-18": dict(nome="Aço-silício de grão orientado alta permeabilidade 0,18 mm (ex.: M085-18P / 18ZDKH)", norma="IEC 60404-8-7",
                       esp_mm=0.18, p17_50=0.85, rho=50e-8, dens=7650, kf=0.95, preco_kg=40.0),
    "GO_M120-27S": dict(nome="Aço-silício de grão orientado M120-27S (0,27 mm)", norma="IEC 60404-8-7", esp_mm=0.27,
                        p17_50=1.20, rho=48e-8, dens=7650, kf=0.96, preco_kg=28.0),
    "GO_M110-23S": dict(nome="Aço-silício de grão orientado M110-23S (0,23 mm)", norma="IEC 60404-8-7", esp_mm=0.23,
                        p17_50=1.10, rho=48e-8, dens=7650, kf=0.955, preco_kg=32.0),
    # v1.11.3 – graus GO da Aperam (único fabricante nacional; catálogo "Aços Elétricos GO e GNO", perdas máximas garantidas
    # P1,7/50 Hz, revestimento C-5, densidade 7,65). Preço R$/kg: ESTIMATIVA relativa (confirmar cotação).
    "GO_APERAM_M108-23": dict(nome="Aço GO Aperam M108-23 (E003-9) 0,23 mm", norma="IEC 60404-8-7 / Aperam", esp_mm=0.23,
                              p17_50=1.08, rho=48e-8, dens=7650, kf=0.945, preco_kg=34.0),
    "GO_APERAM_M117-23": dict(nome="Aço GO Aperam M117-23 (E003-9) 0,23 mm", norma="IEC 60404-8-7 / Aperam", esp_mm=0.23,
                              p17_50=1.17, rho=48e-8, dens=7650, kf=0.945, preco_kg=32.0),
    "GO_APERAM_M112-27": dict(nome="Aço GO Aperam M112-27 (E004-7) 0,27 mm", norma="IEC 60404-8-7 / Aperam", esp_mm=0.27,
                              p17_50=1.12, rho=48e-8, dens=7650, kf=0.95, preco_kg=30.0),
    "GO_APERAM_M125-27": dict(nome="Aço GO Aperam M125-27 (E004-7) 0,27 mm", norma="IEC 60404-8-7 / Aperam", esp_mm=0.27,
                              p17_50=1.24, rho=48e-8, dens=7650, kf=0.95, preco_kg=28.0),
    "GO_APERAM_M130-30": dict(nome="Aço GO Aperam M130-30 (E005-4) 0,30 mm", norma="IEC 60404-8-7 / Aperam", esp_mm=0.30,
                              p17_50=1.30, rho=48e-8, dens=7650, kf=0.955, preco_kg=27.0),
    "GO_APERAM_M140-30": dict(nome="Aço GO Aperam M140-30 (E005-4) 0,30 mm", norma="IEC 60404-8-7 / Aperam", esp_mm=0.30,
                              p17_50=1.40, rho=48e-8, dens=7650, kf=0.955, preco_kg=26.0),
    "GO_APERAM_M150-35": dict(nome="Aço GO Aperam M150-35 (E006-2) 0,35 mm", norma="IEC 60404-8-7 / Aperam", esp_mm=0.35,
                              p17_50=1.50, rho=48e-8, dens=7650, kf=0.96, preco_kg=25.0),
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
MARGEM_TERMICA_K = 10.0               # v1.26.4 (REQ-GER-014/REQ-REA-013): folga mínima entre o ponto quente e o limite da classe
ALVO_ELEV_EXT = None                  # v1.26.4: meta de elevação imposta de fora (fechamento térmico com a análise avançada)


def meta_elevacao(r, amb_c):
    """Meta de elevação média do enrolamento (K): a da classe, limitada para o PONTO QUENTE ficar MARGEM_TERMICA_K abaixo do
    limite de temperatura (da classe ou do cliente – r['temp_max_C']) no ambiente real do painel."""
    cl = CLASSE[r["classe"]]
    t_lim = float(r.get("temp_max_C") or cl["temp"])
    if ALVO_ELEV_EXT:
        return float(ALVO_ELEV_EXT)
    return max(min(cl["elev_media"], META_ELEV_MAX, t_lim - amb_c - PONTO_QUENTE_ACRESCIMO_K - MARGEM_TERMICA_K), 40.0)


def sistema_isolacao(classe):
    """Sistema de isolação (EIS) – cada componente com índice térmico ≥ classe. IEC 60085: a classe é do SISTEMA, avaliada
    conforme IEC 61857 / IEC 61858 (ou UL 1446); não basta um componente 'classe H'."""
    H = classe == "H"
    return [
        dict(item="Isolação entre espiras/camadas", mat=("Papel aramida (Nomex® 410 ou equiv.) 0,13 mm, 2 camadas" if H else
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
def _temp_classe_cliente(txt):
    """Temperatura-limite da classe térmica pedida pelo cliente ('F (155 °C)' → 155). Sem pedido → classe F (padrão Electric)."""
    t = str(txt or "F").strip().upper()
    for letra, temp in (("H", 180.0), ("F", 155.0), ("B", 130.0)):
        if t.startswith(letra) or f"CLASSE {letra}" in t:
            return temp
    return 155.0


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
                classe="H",          # padrão Electric: sistema de isolação classe H com elevação limitada à de classe F (margem)
                temp_max_C=_temp_classe_cliente(getattr(ped, "classe_temp", None)))   # v1.26.4: ponto quente ≤ classe PEDIDA pelo cliente


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


def descr_condutor(d, curto=False):
    """Texto do condutor do enrolamento (folha ou fio retangular) para desenhos, BOM, ET e memorial (v1.11.2)."""
    f = d.get("fio")
    mat = "alumínio 1350-O" if d.get("cond", "AL") == "AL" else "cobre ETP recozido"
    if not f:
        return (f"folha {d['tf'] * 1e3:.1f} × {d['hf'] * 1e3:.0f} mm" if curto else
                f"Folha de {mat} {d['tf'] * 1e3:.1f} × {d['hf'] * 1e3:.0f} mm, {d['N']} espiras (1 espira por camada)")
    t, h = f["t"] * 1e3, f["h"] * 1e3
    tipo = "barra retangular" if (t >= 5.0 or h >= 16.0) else "fio retangular"
    par = f"{f['np']} em paralelo transpostos" if f["np"] > 1 else "condutor ÚNICO (sem paralelos, sem transposição)"
    if curto:
        return f"{tipo} {t:.2f} × {h:.1f} mm" + (f" × {f['np']}" if f["np"] > 1 else " (única)")
    return (f"{tipo[0].upper() + tipo[1:]} de {mat} {t:.2f} × {h:.1f} mm (IEC 60317-0-2 / NBR), isolada com papel aramida enrolado "
            f"(classe H, +{f['iso'] * 1e3:.1f} mm), {par} por espira; {f['n_cam']} camada(s) × {f['n_ax']} espiras = {d['N']} espiras; "
            f"aramida {f['t_cam'] * 1e3:.2f} mm entre camadas")


def area_espira(d):
    """Seção de cobre/alumínio de uma espira (m²): folha tf×hf ou fio retangular np×t×h (v1.11.2)."""
    f = d.get("fio")
    return f["np"] * f["t"] * f["h"] if f else d["tf"] * d["hf"]


def _geo(r, N, a, b, tf, hf, nd, c, cond, ch, fio=None):
    """Geometria e massas para um candidato (unidades SI). fio = enrolamento em camadas de fio retangular (v1.11.2)."""
    ti = 0.26e-3                                   # 2 × 0,13 mm de aramida
    wd = 8e-3                                      # canal de ventilação axial
    tube, wrap = 3e-3, 1.5e-3
    if fio:
        build = fio["n_cam"] * (fio["np"] * (fio["t"] + fio["iso"]) + fio["t_cam"]) + 4 * 0.13e-3 + nd * wd + tube + wrap
    else:
        build = N * (tf + ti) + 4 * 0.13e-3 + nd * wd + tube + wrap
    hc = hf + 2 * DIST["borda_folha_mm"] * 1e-3
    hw = hc + 2 * DIST["bobina_culatra_mm"] * 1e-3
    ww = 2 * (c + build) + DIST["entre_fases_mm"] * 1e-3
    MLT = 2 * (a + b) + 8 * (c + tube) + math.pi * build
    kf = ch["kf"]
    m_fe = (3 * a * b * hw + 2 * (3 * a + 2 * ww) * a * b) * kf * ch["dens"]
    A_esp = fio["np"] * fio["t"] * fio["h"] if fio else tf * hf
    m_cond = 3 * N * MLT * A_esp * cond["dens"]
    return dict(build=build, hc=hc, hw=hw, ww=ww, MLT=MLT, m_fe=m_fe, m_cond=m_cond, ti=ti, wd=wd, tube=tube, wrap=wrap)


def pre_dimensionar(r, chapa="GO_M120-27S", cond_id="AL", h_conv=12.0, alvo_elev=None, amb_c=50.0, espectro=None, nd_min=0, fixo=None):
    """Varredura analítica: escolhe N, a, b, espessura e altura da folha, nº de canais, minimizando custo de material com a
    elevação média ≤ alvo e B(Isat) ≤ 1,45 T (garante L ≥ 90 % em Isat e ≥ 70 % na sobrecarga – conferido depois no FEM)."""
    ch, cond = CHAPAS[chapa], CONDUTORES[cond_id]
    cl = CLASSE[r["classe"]]
    alvo = alvo_elev or meta_elevacao(r, amb_c)   # meta: elevação de classe F mesmo com materiais classe H (margem)
    T = 40 + alvo
    rhoT = cond["rho20"] * (1 + cond["alfa"] * (T - 20))
    delta = math.sqrt(rhoT / (math.pi * r["fs"] * MU0))
    Bsat_d = float(r.get("B_proj_T") or 1.45)            # v1.26.1 (REQ-REA-013): reator de banco/filtro projeta com 1,30 T
    c = 15e-3
    melhor = None
    if fixo:
        N, a, b, tf, hf = fixo["N"], fixo["a"], fixo["b"], fixo["tf"], fixo["hf"]
        fio = fixo.get("fio")
        Aen = a * b * ch["kf"]
        g = _geo(r, N, a, b, tf, hf, nd_min, c, cond, ch, fio=fio)
        Bpk = r["L"] * r["I1"] * math.sqrt(2) / (N * Aen)
        dB = r["L"] * r["rpp"] / (N * Aen)
        R = rhoT * N * g["MLT"] / (fio["np"] * fio["t"] * fio["h"] if fio else tf * hf)
        p1, ps = perdas_nucleo_W(ch, g["m_fe"], Bpk, r["f1"], dB, r["fs"], espectro, N * Aen)
        d = dict(kae=None, N=N, a=a, b=b, tf=tf, hf=hf, nd=nd_min, c=c, Bpk=Bpk, dBpp=dB, custo=None, P_cu=None, P_fe1=p1, P_fes=ps,
                 dT_w=None, dT_fe=None, Fr=_dowell(N, tf / delta), delta=delta, R=R, rhoT=rhoT, **g)
        d.update(chapa=chapa, cond=cond_id, h_conv=h_conv, alvo=alvo, amb_c=amb_c)
        if fio:
            d["fio"] = dict(fio)
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
KI_LEE_LAMINADO = 0.155   # McLyman, Transformer and Inductor Design Handbook, tab. 10-1 (laminações)


def perda_entreferro_lee(d, r, gaps, ch):
    """Perda adicional no núcleo junto aos entreferros (fluxo espraiado entrando perpendicular às lâminas) – fórmula empírica
    de Lee/McLyman Pg = Ki·E·lg·f·B² (E = largura da coluna em cm, lg em cm, B de pico 60 Hz em T). O FEM 2D não vê esse
    efeito 3D; somado como margem conservadora (v1.11.2). Aplicada só a entreferros CONCENTRADOS (peça > 3 mm), que é o caso
    para o qual a fórmula foi levantada; com entreferros distribuídos pequenos o espraiamento é pequeno e o FEM 2D cobre."""
    ng = 2 if str(d.get("pos_gap", "")).startswith("culatra") else max(int(d.get("ng") or 1), 1)
    if max(gaps) / ng * 1e3 <= GAP_MAX_PECA_MM:          # entreferros distribuídos pequenos: fórmula não aplicável (FEM 2D cobre)
        return 0.0
    Bc = r["L"] * r["I1"] * math.sqrt(2) / (d["N"] * d["a"] * d["b"] * ch["kf"])
    return float(KI_LEE_LAMINADO * d["a"] * 100 * sum(gaps) * 100 * r["f1"] * Bc ** 2)


def _perdas_nucleo_lin(d, M, r, esp, ch):
    """Perdas no núcleo pelo campo do FEM LINEAR (μr 4000) – usado na triagem dos candidatos de fio (rápido)."""
    M.matriz_L()
    I1p = r["I1"] * math.sqrt(2)
    Bu = []
    for k in range(3):
        Bx, By = M.B(M._sol_unit[k])
        Bu.append((Bx[M.ferro], By[M.ferro]))
    Bpk_el = np.zeros(int(M.ferro.sum()))
    for k in range(3):
        cur = [-I1p / 2] * 3
        cur[k] = I1p
        bx = sum(cur[j] * Bu[j][0] for j in range(3))
        by = sum(cur[j] * Bu[j][1] for j in range(3))
        Bpk_el = np.maximum(Bpk_el, np.hypot(bx, by))
    dBpp_el = np.sqrt(sum((np.hypot(*Bu[k]) * r["rpp"]) ** 2 for k in range(3)))
    m_el = M.m.area[M.ferro] * d["b"] * ch["kf"] * ch["dens"]
    kh, k_exc, dlam = _steinmetz(ch)
    P1 = float((m_el * (kh * r["f1"] * Bpk_el ** 1.9 + k_exc * (math.pi * dlam * r["f1"] * Bpk_el) ** 2 / (6 * ch["rho"] * ch["dens"]))).sum())
    NAe = d["N"] * d["a"] * d["b"] * ch["kf"]
    dB_ref = r["L"] * r["rpp"] / NAe
    p_ref_e = (K_EXC_AF * p_parasitas_lamina_Wkg(ch, esp[0], esp[1] / (2 * math.pi * esp[0] * NAe)) if esp is not None else
               K_EXC_AF * dlam ** 2 / (12 * ch["rho"] * ch["dens"]) * (2 * dB_ref * r["fs"]) ** 2)
    Ps = float((m_el * (1.3 * kh * r["fs"] * (dBpp_el / 2) ** 2 + p_ref_e * (dBpp_el / dB_ref) ** 2)).sum())
    return P1, Ps


# ---------------------------------------------------------------------------------------------------------------------
# v1.11.2 – fio retangular (padrão dos fabricantes nacionais com 2 entreferros por coluna nas culatras)
FIO_T_MM = (0.80, 0.90, 1.00, 1.12, 1.25, 1.40, 1.60, 1.80, 2.00, 2.24, 2.50, 2.80, 3.15, 3.55, 4.00, 4.50, 5.00, 5.60, 6.30, 7.10,
            8.00, 9.00, 10.0)   # espessura (radial) – série R20 da IEC 60317-0-2 (fio e barra retangular)
FIO_H_MM = (2.00, 2.24, 2.50, 2.80, 3.15, 3.55, 4.00, 4.50, 5.00, 5.60, 6.30, 7.10, 8.00, 9.00, 10.0, 11.2, 12.5, 14.0, 16.0,
            18.0, 20.0, 22.4, 25.0, 28.0, 31.5)   # largura (axial) – série R20; relação largura/espessura 1,4 a 8
CHAPAS_FIO = ("GO_APERAM_M108-23", "GO_APERAM_M117-23", "GO_APERAM_M112-27", "GO_APERAM_M125-27", "GO_APERAM_M130-30",
              "GO_APERAM_M140-30", "GO_APERAM_M150-35")
CONDS_FIO = ("AL", "CU")
PARALELOS_FIO = (1, 2, 3, 4, 6)
CAMADAS_FIO = (1, 2, 3, 4, 6, 8)
FIO_ISO_MM = 0.40       # isolação total por fio (papel aramida enrolado 2 × 0,10 mm por lado – classe H)
FIO_T_CAM_MM = 0.25     # isolação entre camadas (aramida 0,25 mm)
FIO_K_ESPRAIO = 1.65   # entreferro real / ideal com 2 entreferros nas culatras (FEM A&W: 16,9 / 11,0 mm × 1,10 ≈ 1,7)
META_ELEV_MAX = 100.0     # meta de elevação média do enrolamento (K) – 100 K = elevação de classe F com materiais classe H
SELECAO_FIO = "custo"     # "custo" (menor custo total) ou "massa" (indutor mais leve que passa)
MAO_OBRA_R_KG = 10.0      # mão de obra/estrutura do fabricante proporcional à massa (estimativa – fabricantes cotam por kg)
FOLGA_PERDAS_FIO = 0.92   # o candidato precisa ficar ≥ 8 % abaixo do limite de perdas (margem de fabricação)
FOLGA_ELEV_FIO = 0.90     # e ≥ 10 % abaixo da meta de elevação
FIO_FR60 = 1.25         # fator de espraiamento das juntas na perda 60 Hz usado só na triagem (o FEM decide)


def _pre_fio_um(r, chapa="GO_M120-27S", cond_id="AL", h_conv=12.0, alvo_elev=None, amb_c=50.0, espectro=None, nd_min=0,
                n_cand=16):
    """Triagem analítica do enrolamento em CAMADAS de fio retangular: devolve os n_cand candidatos mais baratos (núcleo, espiras,
    dimensão do fio, nº de fios em paralelo e de camadas) que passam na estimativa térmica; o FEM escolhe entre eles."""
    ch, cond = CHAPAS[chapa], CONDUTORES[cond_id]
    cl = CLASSE[r["classe"]]
    alvo = alvo_elev or meta_elevacao(r, amb_c)
    T = 40 + alvo
    rhoT = cond["rho20"] * (1 + cond["alfa"] * (T - 20))
    delta = math.sqrt(rhoT / (math.pi * r["fs"] * MU0))
    Bsat_d, c = float(r.get("B_proj_T") or 1.45), 15e-3  # v1.26.1 (REQ-REA-013)
    iso, tcam = FIO_ISO_MM * 1e-3, FIO_T_CAM_MM * 1e-3
    Jmin, Jmax = (0.8e6, 3.0e6) if cond_id == "AL" else (1.2e6, 4.5e6)     # densidade de corrente admissível (A/m²)
    combos = [(t * 1e-3, h * 1e-3, npar, nd) for t in FIO_T_MM for h in FIO_H_MM if 1.4 <= h / t <= 8.0
              for npar in PARALELOS_FIO for nd in range(nd_min, 3)
              if r["In"] / Jmax <= npar * t * h * 1e-6 <= r["In"] / Jmin]
    if not combos:
        return []
    T_, H_, NP_, ND_ = (np.array(v, dtype=float) for v in zip(*combos))
    A_ = NP_ * T_ * H_
    ok_J = np.ones_like(A_, dtype=bool)
    eta_ = H_ / (H_ + iso)
    wd, tube, wrap = 8e-3, 3e-3, 1.5e-3
    bc, borda, entre = DIST["bobina_culatra_mm"] * 1e-3, DIST["borda_folha_mm"] * 1e-3, DIST["entre_fases_mm"] * 1e-3

    def dowell_v(m, x):
        x = np.maximum(x, 1e-6)
        aa = (np.sinh(2 * x) + np.sin(2 * x)) / (np.cosh(2 * x) - np.cos(2 * x))
        bb = (np.sinh(x) - np.sin(x)) / (np.cosh(x) + np.cos(x))
        return x * (aa + 2 * (m * m - 1) / 3 * bb)

    cands = []
    kh, k_exc, dl = _steinmetz(ch)
    for N in list(range(8, 41)) + list(range(42, 61, 2)):
        for n_cam in CAMADAS_FIO:
            if N % n_cam:
                continue
            n_ax = N // n_cam
            build_ = n_cam * (NP_ * (T_ + iso) + tcam) + 4 * 0.13e-3 + ND_ * wd + tube + wrap
            hf_ = n_ax * (H_ + iso)
            hc_ = hf_ + 2 * borda
            hw_ = hc_ + 2 * bc
            ww_ = 2 * (c + build_) + entre
            Fr_ = dowell_v(n_cam * NP_, T_ / delta * np.sqrt(eta_))
            for kae in (1.0, 1.25, 1.5, 2.0):
                Ae = kae * r["L"] * r["Isat"] / (N * Bsat_d)
                for a_mm in range(40, 261, 10):
                    a = a_mm * 1e-3
                    b = Ae / (ch["kf"] * a)
                    if not (0.9 <= b / a <= 2.2):
                        continue
                    b = math.ceil(b * 1e3 / 5) * 5e-3
                    Aen = a * b * ch["kf"]
                    g_tot = MU0 * N * N * a * b * FIO_K_ESPRAIO / r["L"]
                    if g_tot > GAP_MAX_FRAC_A * a or g_tot / 2 > GAP_MAX_PECA_CULATRA_MM * 1e-3:
                        continue
                    Bpk = r["L"] * r["I1"] * math.sqrt(2) / (N * Aen)
                    dB = r["L"] * r["rpp"] / (N * Aen)
                    _, ps1 = perdas_nucleo_W(ch, 1.0, Bpk, r["f1"], dB, r["fs"], espectro, N * Aen)
                    p1_kg = kh * r["f1"] * Bpk ** 1.9 + k_exc * (math.pi * dl * r["f1"] * Bpk) ** 2 / (6 * ch["rho"] * ch["dens"])
                    MLT_ = 2 * (a + b) + 8 * (c + tube) + math.pi * build_
                    m_fe_ = (3 * a * b * hw_ + 2 * (3 * a + 2 * ww_) * a * b) * ch["kf"] * ch["dens"]
                    m_cond_ = 3 * N * MLT_ * A_ * cond["dens"]
                    R_ = rhoT * N * MLT_ / A_
                    P_cu_ = 3 * R_ * (FIO_FR60 * r["I1"] ** 2 + Fr_ * r["rrms"] ** 2) * 1.10
                    p1_, ps_ = m_fe_ * p1_kg, m_fe_ * ps1
                    perim_out = 2 * (a + b) + 8 * (c + build_)
                    perim_in = 2 * (a + b) + 8 * c
                    A_w = (perim_out + 0.5 * perim_in + ND_ * 2 * 0.6 * (perim_in + perim_out) / 2) * hc_
                    dT_w_ = (P_cu_ / 3) / (h_conv * A_w)
                    A_fe = 2 * (3 * a + 2 * ww_) * (2 * a + hw_) * 0.55 + 2 * (3 * a + 2 * ww_) * b
                    dT_fe_ = (p1_ + ps_) / (h_conv * A_fe)
                    val = ok_J & (dT_w_ <= alvo) & (dT_fe_ <= alvo)
                    if r.get("P_max"):
                        val &= (P_cu_ + p1_ + ps_) <= r["P_max"] * r.get("k_Pmax", 0.88)
                    if not val.any():
                        continue
                    custo_ = m_fe_ * ch["preco_kg"] + m_cond_ * cond["preco_kg"] * 1.15 + CAPITALIZACAO_R_W * (P_cu_ + p1_ + ps_)
                    _met = custo_ if SELECAO_FIO == "custo" else (m_fe_ + m_cond_) + 1e-4 * custo_
                    idx = [int(np.argmin(np.where(val, _met, np.inf)))]
                    if r.get("L_env_max_mm"):                    # v1.24.3: também o melhor que CABE na coluna (largura externa)
                        from .ind_estrutura import EXT_X as _EXT
                        cabe_ = (3 * a + 2 * ww_) * 1e3 + 2 * _EXT <= r["L_env_max_mm"]
                        if (val & cabe_).any():
                            j = int(np.argmin(np.where(val & cabe_, _met, np.inf)))
                            if j != idx[0]:
                                idx.append(j)
                    for i in idx:
                        fio = dict(t=float(T_[i]), h=float(H_[i]), np=int(NP_[i]), n_cam=n_cam, n_ax=n_ax, iso=iso, t_cam=tcam)
                        g = _geo(r, N, a, b, fio["np"] * fio["t"], float(hf_[i]), int(ND_[i]), c, cond, ch, fio=fio)
                        cands.append(dict(kae=kae, N=N, a=a, b=b, tf=fio["np"] * fio["t"], hf=float(hf_[i]), nd=int(ND_[i]), c=c, Bpk=Bpk,
                                          dBpp=dB, custo=float(custo_[i]) if SELECAO_FIO == "custo" else float(m_fe_[i] + m_cond_[i]), P_cu=float(P_cu_[i]), P_fe1=float(p1_[i]), P_fes=float(ps_[i]),
                                          dT_w=float(dT_w_[i]), dT_fe=float(dT_fe_[i]), Fr=float(Fr_[i]), delta=delta, R=float(R_[i]),
                                          rhoT=rhoT, fio=fio, cabe_coluna=len(idx) > 1 and i == idx[-1], **g))
    cands.sort(key=lambda x: x["custo"])
    out, vistos = [], set()
    for cd in cands:                                   # candidatos distintos (núcleo/espiras/fio)
        k = (cd["N"], round(cd["a"] * 1e3), round(cd["b"] * 1e3), cd["fio"]["n_cam"])
        if k in vistos:
            continue
        vistos.add(k)
        cd.update(chapa=chapa, cond=cond_id, h_conv=h_conv, alvo=alvo, amb_c=amb_c)
        out.append(cd)
        if len(out) >= n_cand:
            break
    fit = [c_ for c_ in cands if c_.get("cabe_coluna") and c_ not in out]
    for cd in fit[:4]:                                   # v1.24.3: garante candidatos que cabem 2 por coluna no FEM
        cd.update(chapa=chapa, cond=cond_id, h_conv=h_conv, alvo=alvo, amb_c=amb_c)
        out.append(cd)
    return out


def pre_dimensionar_fio(r, chapas=None, conds=None, h_conv=12.0, alvo_elev=None, amb_c=50.0, espectro=None, nd_min=0,
                        por_combo=2, n_global=10, log=None):
    """v1.11.3 – varre TODAS as chapas (graus GO Aperam) × condutores (Al, Cu) × fio/barra (série R20 IEC 60317-0-2) × paralelos ×
    camadas × espiras × núcleo; devolve os 2 melhores de cada chapa×condutor + os 10 melhores no geral para o FEM conferir."""
    chapas = chapas or CHAPAS_FIO
    conds = conds or CONDS_FIO
    todos, resumo = [], []
    for ch_id in chapas:
        for c_id in conds:
            lst = _pre_fio_um(r, ch_id, c_id, h_conv, alvo_elev, amb_c, espectro, nd_min, n_cand=max(por_combo, n_global))
            resumo.append((ch_id, c_id, len(lst), lst[0]["custo"] if lst else None))
            todos.extend(lst)
    if log:
        ok = [x for x in resumo if x[2]]
        log(f"     base: {len(FIO_T_MM)}×{len(FIO_H_MM)} bitolas IEC 60317-0-2 × {len(PARALELOS_FIO)} paralelos × {len(CAMADAS_FIO)} camadas × "
            f"{len(chapas)} chapas × {len(conds)} condutores → {len(ok)} combinações chapa×condutor com solução")
    escolhidos, vistos = [], set()

    def chave(x):
        return (x["chapa"], x["cond"], x["N"], round(x["a"] * 1e3), round(x["b"] * 1e3), x["fio"]["n_cam"], x["fio"]["np"],
                round(x["fio"]["t"] * 1e4), round(x["fio"]["h"] * 1e4))
    for ch_id in chapas:
        for c_id in conds:
            sub = sorted([x for x in todos if x["chapa"] == ch_id and x["cond"] == c_id], key=lambda x: x["custo"])[:por_combo]
            for x in sub:
                if chave(x) not in vistos:
                    vistos.add(chave(x))
                    escolhidos.append(x)
    for x in sorted(todos, key=lambda x: x["custo"])[:n_global]:
        if chave(x) not in vistos:
            vistos.add(chave(x))
            escolhidos.append(x)
    for x in sorted([x for x in todos if x.get("cabe_coluna")], key=lambda x: x["custo"])[:6]:   # v1.24.3: os que cabem na coluna
        if chave(x) not in vistos:
            vistos.add(chave(x))
            escolhidos.append(x)
    escolhidos.sort(key=lambda x: x["custo"])
    return escolhidos


# ---------------------------------------------------------------------------------------------------------------------
def _condutores(d, gaps_xl, a, ng_lado=None):
    """Lista de condutores (folha) para o modelo FEM: cada espira = 1 retângulo de cada lado de cada coluna."""
    out = []
    y0 = a + DIST["bobina_culatra_mm"] * 1e-3 + DIST["borda_folha_mm"] * 1e-3
    y1 = y0 + d["hf"]
    f = d.get("fio")
    if f:
        # v1.11.2: fio retangular em CAMADAS – n_cam camadas (radial) × n_ax espiras por camada (axial), espiras em série
        # (cada uma leva I); cada espira = np fios em paralelo empilhados no raio, transpostos (I/np cada)
        pos_canal = set(round((k + 1) * f["n_cam"] / (d["nd"] + 1)) for k in range(d["nd"]))
        p_ax = f["h"] + f["iso"]
        for i, x0 in enumerate(gaps_xl):
            r = d["c"] + d["tube"] + 2 * 0.13e-3
            for j in range(f["n_cam"]):
                if j in pos_canal:
                    r += d["wd"]
                for p in range(f["np"]):
                    rr = r + p * (f["t"] + f["iso"]) + f["iso"] / 2
                    for k in range(f["n_ax"]):
                        ya = y0 + k * p_ax + f["iso"] / 2
                        yb = ya + f["h"]
                        esp = j * f["n_ax"] + k
                        out.append(dict(x0=x0 + a + rr, x1=x0 + a + rr + f["t"], y0=ya, y1=yb, fase=i, lado=-1.0 / f["np"], esp=esp))
                        out.append(dict(x0=x0 - rr - f["t"], x1=x0 - rr, y0=ya, y1=yb, fase=i, lado=+1.0 / f["np"], esp=esp))
                r += f["np"] * (f["t"] + f["iso"]) + f["t_cam"]
        return out
    passo = d["tf"] + d["ti"]
    # canais distribuídos igualmente entre as camadas
    pos_canal = set(round((k + 1) * d["N"] / (d["nd"] + 1)) for k in range(d["nd"]))
    # v1.11.2: condutor subdividido na altura (m fitas/fios retangulares em paralelo, transpostos) – cada parte leva I/m
    m = max(int(d.get("sub_axial", 1) or 1), 1)
    t_iso = SUB_ISO_MM * 1e-3
    hs = (d["hf"] - (m - 1) * t_iso) / m
    faixas = [(y0 + j * (hs + t_iso), y0 + j * (hs + t_iso) + hs) for j in range(m)]
    for i, x0 in enumerate(gaps_xl):
        r = d["c"] + d["tube"] + 2 * 0.13e-3
        for k in range(d["N"]):
            if k in pos_canal:
                r += d["wd"]
            xr0 = x0 + a + r
            xl1 = x0 - r
            for (ya, yb) in faixas:
                out.append(dict(x0=xr0, x1=xr0 + d["tf"], y0=ya, y1=yb, fase=i, lado=-1.0 / m, esp=k))
                out.append(dict(x0=xl1 - d["tf"], x1=xl1, y0=ya, y1=yb, fase=i, lado=+1.0 / m, esp=k))
            r += passo
    return out


def modelo(d, gaps, ng, hcond=None):
    a = d["a"]
    xl = [i * (a + d["ww"]) for i in range(3)]
    cond = _condutores(d, xl, a)
    return ModeloIndutor(dict(a=a, b=d["b"], hw=d["hw"], ww=d["ww"], ng=ng, gaps=list(gaps), condutores=cond,
                              pos_gap=d.get("pos_gap", "distribuido")), hcond=hcond)


def h_condutor_final(d, f_max):
    """v1.11.8: malha dentro das barras para a avaliação FINAL das perdas de AF – resolve a profundidade de penetração na maior
    frequência usada (a malha de triagem é grossa; a verificação independente com o NGSolve mostrou ~25 % a menos em 2·fs)."""
    delta = math.sqrt(d["rhoT"] / (math.pi * f_max * MU0))
    return max(min(delta / 1.5, 1.0e-3), 0.3e-3)


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


def projetar(proj, cat=None, chapa="GO_M120-27S", cond_id="AL", h_conv=12.0, amb_c=50.0, log=print, construcao="distribuido",
             condutor="barra_cu"):
    """condutor (só para 2 entreferros + fio): "barra_cu" = barra retangular de COBRE única por espira (mais fácil de fabricar –
    padrão); "barra_al" = barra/chapa de ALUMÍNIO única (padrão Electric dos reatores de banco dessintonizado/sintonizado); "livre" = fio ou barra, Cu ou Al, até 6 em paralelo transpostos (mais leve)."""
    global PARALELOS_FIO, CONDS_FIO
    _p0, _c0 = PARALELOS_FIO, CONDS_FIO
    if construcao == "culatra_fio" and condutor == "barra_cu":
        PARALELOS_FIO, CONDS_FIO = (1,), ("CU",)
    elif construcao == "culatra_fio" and condutor == "barra_al":      # v1.14.0: padrão Electric dos reatores de banco (alumínio)
        PARALELOS_FIO, CONDS_FIO = (1,), ("AL",)
    try:
        d = _projetar_construcao(proj, cat, chapa, cond_id, h_conv, amb_c, log, construcao)
    finally:
        PARALELOS_FIO, CONDS_FIO = _p0, _c0
    d["opcao_condutor"] = condutor if construcao == "culatra_fio" else None
    return d


def _projetar_construcao(proj, cat=None, chapa="GO_M120-27S", cond_id="AL", h_conv=12.0, amb_c=50.0, log=print, construcao="distribuido"):
    """Projeto completo. Com 2 entreferros nas culatras + fio retangular, calcula alumínio E cobre e fica com o de menor custo
    total (material + perdas capitalizadas) que passa em todas as verificações (v1.11.2)."""
    if construcao != "culatra_fio":
        return _projetar_tent(proj, cat, chapa, cond_id, h_conv, amb_c, log, construcao)
    log("   Indutor – 2 entreferros/coluna + fio/barra retangular: busca em toda a base (chapas Aperam × Al/Cu × bitolas IEC)...")
    d = _projetar_tent(proj, cat, chapa, cond_id, h_conv, amb_c, log, construcao)
    tri = d.get("triagem_fio") or []
    comp = []
    for cnd in ("AL", "CU"):
        oks = [x for x in tri if x["cond"] == cnd and x["ok"]]
        if oks:
            x = min(oks, key=lambda y: y["custo"])
            comp.append(dict(condutor=("alumínio" if cnd == "AL" else "cobre"), fio=x["fio"], chapa=x["chapa"], N=x["N"],
                             coluna=x["coluna"], perdas_W=x["P_total_W"], custo_triagem=x["custo"],
                             escolhido=(cnd == d["cond"] and x["fio"] == f"{d['fio']['t']*1e3:.2f}×{d['fio']['h']*1e3:.1f}×{d['fio']['np']}")))
    d["comparacao_condutor"] = comp
    log(f"   → escolhido: {('alumínio' if d['cond'] == 'AL' else 'cobre')}, {d['chapa_dados']['nome']}, {descr_condutor(d, curto=True)}, "
        f"{d['N']} espiras, coluna {d['a']*1e3:.0f}×{d['b']*1e3:.0f} mm, {d['perdas']['total']:.0f} W, {d['massa_kg']['total']:.0f} kg")
    return d


def _projetar_tent(proj, cat, chapa, cond_id, h_conv, amb_c, log, construcao):
    """Projeto completo; se a elevação calculada no FEM passar da meta, acrescenta canal de ventilação e refaz (até 3×)."""
    nd_min, fixo, k_pmax = 0, None, 0.88
    for tent in range(5):
        d = _projetar(proj, cat, chapa, cond_id, h_conv, amb_c, log, nd_min, fixo, k_pmax, construcao)
        chapa, cond_id = d.get("chapa", chapa), d.get("cond", cond_id)
        pmax = d["requisitos"].get("P_max")
        if pmax and d["perdas"]["total"] > pmax and fixo is None and k_pmax > 0.6:
            k_pmax -= 0.08
            log(f"   Perdas {d['perdas']['total']:.0f} W > {pmax:.0f} W (mercado) → refazendo com limite mais apertado")
            continue
        if d["termico"]["elev_bobina_K"] <= d["termico"]["meta_elev_K"] + 0.5:
            break
        nd_min = d["nd"] + 1
        fixo = dict(N=d["N"], a=d["a"], b=d["b"], tf=d["tf"], hf=d["hf"], fio=d.get("fio"))   # mesmo núcleo e condutor: só acrescenta canal
        log(f"   Elevação {d['termico']['elev_bobina_K']:.0f} K > meta {d['termico']['meta_elev_K']:.0f} K → refazendo com {nd_min} canal(is)")
    d["tentativas_termico"] = tent + 1
    return d


_REQ_EXT = None     # v1.13.0: requisitos/espectro externos (bancos dessintonizados, filtros sintonizados – sem Projeto de filtro senoidal)


def projetar_requisitos(req, espectro, cat=None, log=print, construcao="culatra_fio", condutor="barra_cu", **kw):
    """Motor completo do indutor para QUALQUER aplicação: req = dict(L, In, I1, Ipk, Isat, Iovl, rpp, rrms, fs, f1, V, Vdc,
    classe, P_max, aplicacao); espectro = (f_h, V_h pico) da tensão sobre o indutor (linhas acima da fundamental)."""
    global _REQ_EXT
    _REQ_EXT = (dict(req), espectro)
    try:
        return projetar(None, cat, log=log, construcao=construcao, condutor=condutor, **kw)
    finally:
        _REQ_EXT = None


def _projetar(proj, cat, chapa, cond_id, h_conv, amb_c, log, nd_min=0, fixo=None, k_pmax=0.88, construcao="distribuido", sub_axial=1):
    if _REQ_EXT is not None:
        r = dict(_REQ_EXT[0])
        esp = _REQ_EXT[1]
    else:
        r = requisitos(proj, cat)
        try:
            esp = espectro_tensao_indutor(proj, cat)
        except Exception as e:
            log(f"   (espectro da tensão no indutor não obtido: {e}; usando ondulação triangular)")
            esp = None
    r["V_AF_rms"] = float(np.sqrt((esp[1] ** 2).sum() / 2)) if esp is not None else None
    if _REQ_EXT is None:
        try:
            from .spec_indutor import referencia_mercado
            _fx = referencia_mercado(r["In"], cat or {})[2]
            r["P_max"] = float(_fx["perdas_w"][1]) if _fx else None
        except Exception:
            r["P_max"] = None
    r["k_Pmax"] = k_pmax
    eh_fio = construcao == "culatra_fio"
    cands = None
    if eh_fio and not fixo:
        cands = pre_dimensionar_fio(r, None, None, h_conv, amb_c=amb_c, espectro=esp, nd_min=nd_min, log=log)
        d = cands[0] if cands else None
    else:
        d = pre_dimensionar(r, chapa, cond_id, h_conv, amb_c=amb_c, espectro=esp, nd_min=nd_min, fixo=fixo)
    if not d:
        raise RuntimeError("pré-dimensionamento sem solução – rever limites")
    d["sub_axial"] = int((fixo or {}).get("sub_axial") or sub_axial or 1)
    if d.get("fio"):
        log(f"   Indutor: triagem de fio retangular – {len(cands or [])} candidatos (2 entreferros por coluna nas culatras)")
    else:
        log(f"   Indutor: pré-dimensionamento N={d['N']}, coluna {d['a']*1e3:.0f}×{d['b']*1e3:.0f} mm, folha {d['tf']*1e3:.1f}×{d['hf']*1e3:.0f} mm, "
            f"{d['nd']} canais")
    cond = CONDUTORES[cond_id]
    ch = CHAPAS[chapa]
    sig = 1 / d["rhoT"]
    # ------------------------------------------------ 1) nº de entreferros × distância bobina–núcleo (FEM harmônico)
    fh_i, Ih = (esp[0], esp[1] / (2 * math.pi * esp[0] * r["L"])) if esp is not None else (np.array([r["fs"]]), np.array([r["rrms"] * math.sqrt(2)]))
    r["I_AF_rms_espectro"] = float(np.sqrt((Ih ** 2).sum() / 2))
    g_tot0 = MU0 * d["N"] ** 2 * d["a"] * d["b"] * 1.10 / r["L"]

    def perdas_enrolamento(dd, gaps, ng, freqs=None, hcond=None):
        M = modelo(dd, gaps, ng, hcond=hcond)
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

    if cands:
        # v1.11.2: o FEM (2 entreferros nas culatras) confere a perda real de cada candidato de fio; fica o mais barato que passa
        pmx = (r.get("P_max") or 1e9) * k_pmax
        avals = []
        for cd in cands:
            cd["pos_gap"] = "culatra"
            sig = 1 / cd["rhoT"]
            ch = CHAPAS[cd["chapa"]]
            cond = CONDUTORES[cd["cond"]]
            gt = MU0 * cd["N"] ** 2 * cd["a"] * cd["b"] * FIO_K_ESPRAIO / r["L"]
            pe_c = perdas_enrolamento(cd, [gt] * 3, 2, freqs=[2 * r["fs"]])
            Pw = pe_c["P60"] + pe_c["P_AF"]
            try:
                p1c, psc = _perdas_nucleo_lin(cd, pe_c["M"], r, esp, ch)
            except Exception:
                p1c, psc = cd["P_fe1"], cd["P_fes"]
            Ptot = Pw + p1c + psc + perda_entreferro_lee(cd, r, [gt] * 3, ch)
            dTw = cd["dT_w"] * Pw / max(cd["P_cu"], 1e-9)
            m_tot = cd["m_fe"] + cd["m_cond"]
            custo = (cd["m_fe"] * ch["preco_kg"] + cd["m_cond"] * cond["preco_kg"] * 1.15 + CAPITALIZACAO_R_W * Ptot
                     + MAO_OBRA_R_KG * m_tot)
            try:                                         # entreferro que o FEM pede para chegar em L (coluna central = a pior)
                Lp2d_c, _ = L_fases(pe_c["M"], cd["b"])
                L1 = float(max(correcao_3d(cd, Lp2d_c, pe_c["M"])))
                g1 = gt * L1 / r["L"]                                   # 1ª estimativa (L ∝ 1/g)
                M2 = modelo(cd, [g1] * 3, 2)
                Lp2d_2, _ = L_fases(M2, cd["b"])
                L2 = float(max(correcao_3d(cd, Lp2d_2, M2)))
                k = math.log(L1 / L2) / math.log(g1 / gt) if abs(g1 - gt) > 1e-6 else 1.0   # L ∝ g^-k (secante log)
                g_need = g1 * (L2 / r["L"]) ** (1 / max(k, 0.3))
            except Exception:
                g_need = gt
            ok_gap = g_need <= GAP_MAX_FRAC_A * cd["a"] * 0.90 and g_need / 2 <= GAP_MAX_PECA_CULATRA_MM * 1e-3 * 0.90   # folga p/ o ajuste final (+7 %)
            cd["_g_need"] = g_need
            ok_c = Ptot <= FOLGA_PERDAS_FIO * pmx and dTw <= FOLGA_ELEV_FIO * cd["alvo"] and ok_gap
            from .ind_estrutura import EXT_X as _EXT
            larg_env = (3 * cd["a"] + 2 * cd["ww"]) * 1e3 + 2 * _EXT       # largura externa (quadros + saídas)
            cd["_larg_env"] = larg_env
            cabe = larg_env <= (r.get("L_env_max_mm") or 1e9)
            f = cd["fio"]
            log(f"     {cd['cond']} {cd['chapa'].replace('GO_APERAM_', '')} | fio {f['t']*1e3:.2f}×{f['h']*1e3:.1f} mm ×{f['np']} | {cd['N']} esp ({f['n_cam']} cam × {f['n_ax']}) | coluna "
                f"{cd['a']*1e3:.0f}×{cd['b']*1e3:.0f}: enrol. {Pw:.0f} W, total {Ptot:.0f} W, ΔT≈{dTw:.0f} K, entreferro "
                f"{g_need*1e3:.1f} mm/col, largura {larg_env:.0f} mm {'✓' if ok_c else '✗'}{'' if cabe else ' (não cabe na coluna)'}")
            cd["_m_tot"] = m_tot
            avals.append((not ok_c, (custo if SELECAO_FIO == "custo" else m_tot) if ok_c else Ptot, cd, Pw, Ptot, cabe))
        # v1.24.3 (REQ-REA-002): 1º passa em tudo E cabe na coluna; 2º passa em tudo; 3º cabe (perda acima do teto – AVISA);
        # nunca mais escolher em silêncio o de menor perda (o maior)
        avals.sort(key=lambda x: ((0 if x[5] else 1) if not x[0] else (2 if x[5] else 3), x[1]))
        d = avals[0][2]
        if avals[0][0]:
            d.setdefault("avisos_selecao", []).append(
                "Nenhum candidato passou em perdas/elevação/entreferro com a folga de projeto; escolhido o de menor perda"
                + ((f" que cabe na coluna (largura {d['_larg_env']:.0f} mm ≤ {r['L_env_max_mm']:.0f} mm)" if avals[0][5] else
                    f", que NÃO cabe 2 por coluna (largura {d['_larg_env']:.0f} mm > {r['L_env_max_mm']:.0f} mm) – painel com colunas maiores")
                   if r.get("L_env_max_mm") else f" (largura {d['_larg_env']:.0f} mm)")
                + " – projeto de COMPROMISSO: conferir o teto de perdas e a elevação com o fabricante.")
        elif not avals[0][5]:
            d.setdefault("avisos_selecao", []).append(
                f"O melhor candidato não cabe 2 por coluna de 800 mm (largura {d['_larg_env']:.0f} mm) – painel com colunas maiores.")
        chapa, cond_id = d["chapa"], d["cond"]
        ch, cond = CHAPAS[chapa], CONDUTORES[cond_id]
        d["triagem_fio"] = [dict(cond=x[2]["cond"], chapa=x[2]["chapa"].replace("GO_APERAM_", ""), custo=round(x[1]) if not x[0] else None,
                                 fio=f"{x[2]['fio']['t']*1e3:.2f}×{x[2]['fio']['h']*1e3:.1f}×{x[2]['fio']['np']}", N=x[2]["N"],
                                 camadas=x[2]["fio"]["n_cam"], coluna=f"{x[2]['a']*1e3:.0f}×{x[2]['b']*1e3:.0f}",
                                 P_enrol_W=round(x[3]), P_total_W=round(x[4]), massa_kg=round(x[2].get("_m_tot", 0) * 1.12),
                                 ok=not x[0]) for x in avals]
        sig = 1 / d["rhoT"]
        g_tot0 = MU0 * d["N"] ** 2 * d["a"] * d["b"] * 1.10 / r["L"]
    estudo_gap = []
    d["pos_gap"] = "culatra" if construcao.startswith("culatra") else "distribuido"
    lista_ng = (2,) if construcao.startswith("culatra") else (1, 2, 3, 4, 6, 8)
    for ng in lista_ng:
        if not construcao.startswith("culatra") and g_tot0 / ng > GAP_MAX_PECA_MM * 1e-3 * 1.2:
            continue
        for c_mm in (15, 25):
            dd = dict(d, c=c_mm * 1e-3)
            dd.update(_geo(r, d["N"], d["a"], d["b"], d["tf"], d["hf"], d["nd"], dd["c"], cond, ch, fio=d.get("fio")))
            pe = perdas_enrolamento(dd, [g_tot0] * 3, ng, freqs=[2 * r["fs"]])
            estudo_gap.append(dict(ng=ng, c_mm=c_mm, g_cada_mm=g_tot0 / ng * 1e3, P60_W=pe["P60"], P_AF_W=pe["P_AF"],
                                   P_W=pe["P60"] + pe["P_AF"]))
            log(f"     ng={ng} c={c_mm} mm: enrolamento {pe['P60']:.0f} W (60 Hz) + {pe['P_AF']:.0f} W (AF)")
    # escolha: menor nº de entreferros cuja perda total no enrolamento fica ≤ 5 % acima da melhor; depois menor c
    Pmin = min(e["P_W"] for e in estudo_gap)
    lim_peca = GAP_MAX_PECA_CULATRA_MM if construcao.startswith("culatra") else GAP_MAX_PECA_MM
    ok = [e for e in estudo_gap if e["P_W"] <= 1.05 * Pmin and e["g_cada_mm"] * 1.15 <= lim_peca] or \
         [e for e in estudo_gap if e["P_W"] <= 1.05 * Pmin]
    esc = min(ok, key=lambda e: (e["ng"], e["c_mm"]))
    d["c"] = esc["c_mm"] * 1e-3
    d.update(_geo(r, d["N"], d["a"], d["b"], d["tf"], d["hf"], d["nd"], d["c"], cond, ch, fio=d.get("fio")))
    d["R"] = d["rhoT"] * d["N"] * d["MLT"] / area_espira(d)
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
    d["avisos"] = list(d.get("avisos_selecao", []))
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
    for nome, I in (("Pico em operação", r["Ipk"]), ("Isat (exigido ≥ 90 %)", r["Isat"]), (("Sobrecarga 2,2×I1 (exigido ≥ 70 %)" if r.get("aplicacao") else "Sobrecarga 1,5×I inversor (exigido ≥ 70 %)"), r["Iovl"])) + (
            (("Linearidade 2,5 × I fundamental (NEPSI – exigido ≥ 90 %)", r["Ilin"]),) if r.get("Ilin") else ()):
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
    for s_ in sat:                                           # v1.26.1 (REQ-REA-013): folga de segurança contra saturação
        if s_["caso"].startswith("Linearidade") and s_["L_lat_pct"] < 90.0:
            d.setdefault("avisos", []).append(f"Linearidade: em 2,5 × a corrente fundamental ({s_['I']:.0f} A de pico) a indutância cai para "
                                              f"{s_['L_lat_pct']:.0f} % (critério NEPSI ≥ 90 %) – aumentar o núcleo.")
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
    _hc = h_condutor_final(d, 4 * r["fs"]) if d.get("fio") else None
    pe = perdas_enrolamento(d, gaps, ng, hcond=_hc)
    d["malha_final_condutor_mm"] = (_hc * 1e3) if _hc else None
    d["Rac_ohm"] = {f"{k:.0f} Hz": v for k, v in pe["Rac"].items()}
    d["Rdc_ohm"] = d["R"]
    P_gap = perda_entreferro_lee(d, r, gaps, ch)
    d["perdas"] = dict(enrolamento_60Hz=pe["P60"], enrolamento_AF=pe["P_AF"], nucleo_60Hz=P_fe1, nucleo_AF=P_fes, nucleo_entreferro=P_gap)
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
    dT_fe = (P_fe1 + P_fes + P_gap) / (h_conv * A_fe)
    cl = CLASSE[r["classe"]]
    d["termico"] = dict(h_conv=h_conv, A_bobina_m2=A_w, elev_bobina_K=dT_w, elev_nucleo_K=dT_fe,
                        ponto_quente_C=amb_c + dT_w + PONTO_QUENTE_ACRESCIMO_K, amb_painel_C=amb_c,
                        limite_elev_K=cl["elev_media"], limite_temp_C=float(r.get("temp_max_C") or cl["temp"]), meta_elev_K=d["alvo"],
                        limite_classe_C=cl["temp"])
    # ------------------------------------------------ 6) forças no entreferro, dimensões, massa
    Bg = d["Bpk_coluna"]
    Ag = a * b
    d["forca_gap_N"] = Bg ** 2 * Ag / (2 * MU0)
    W = 3 * a + 2 * d["ww"]
    H = 2 * a + d["hw"]
    D = b + 2 * (c + d["build"]) + 2 * 0.03
    from .ind_estrutura import envelope_mm          # v1.11.6: quadros U + saídas horizontais (padrão reator nacional)
    d["dims_mm"] = envelope_mm(a * 1e3, b * 1e3, c * 1e3, d["build"] * 1e3, W * 1e3, H * 1e3)
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
