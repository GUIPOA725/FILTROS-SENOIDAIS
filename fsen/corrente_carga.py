"""Corrente de dimensionamento do filtro definida PELA ELECTRIC a partir da carga (v1.11.0).

Regra: "o cobre vai pela carga, o ferro vai pelo inversor".
  • Corrente TÉRMICA (cobre, aquecimento, placa do filtro):
        I_motor = I_placa × FS            (sem placa: estimada por cv/kW, rendimento e FP)
        I_fund  = |I_motor (FP) + I_cap + I_cabo|, sem tomar crédito da compensação capacitiva (≥ I_motor)
        I_rms   = √(I_fund² + I_ripple_rms²)                (ripple de alta frequência soma em quadratura)
        I_term  = I_rms × margem (1,10)  → arredondada para cima (A inteiro)
  • Correntes de PICO (ferro, saturação, esforços):
        Isat  ≥ máx(1,25 × pico simulado na I_term ; √2 × I_inversor + ripple_pp/2)    L ≥ 90 %
        Iovl  = 1,5 × √2 × I_inversor + ripple_pp/2   (sobrecarga do inversor, 60 s)    L ≥ 70 %
A corrente pedida pelo cliente fica só como informação (e como fallback quando não há dado do motor).
"""
import math

MARGEM_PADRAO = 1.10
RIPPLE_PROVISORIO = 0.05      # ripple rms ≈ 5 % da fundamental (1ª passada, antes da simulação)
C_CABO_UF_KM = 0.30           # capacitância fase-terra típica de cabo blindado VFD (µF/km) – conservador


def _cfg(cat):
    c = (cat or {}).get("corrente_carga") or {}
    return dict(margem=float(c.get("margem", MARGEM_PADRAO)), c_cabo_uf_km=float(c.get("c_cabo_uf_km", C_CABO_UF_KM)),
                rendimento=float(c.get("rendimento_motor", 0.94)))


def corrente_motor(ped, cat=None):
    """(I_motor×FS, origem, I_placa). Sem placa, estima por potência."""
    fs = max(float(ped.fator_servico or 1.0), 1.0)
    if ped.motor_corrente_a:
        return float(ped.motor_corrente_a) * fs, "placa do motor × FS", float(ped.motor_corrente_a)
    p_kw = float(ped.motor_kw or 0) or float(ped.motor_cv or 0) * 0.7355
    if p_kw > 0:
        cfg = _cfg(cat)
        i = p_kw * 1000 / (math.sqrt(3) * ped.tensao_v * cfg["rendimento"] * (ped.motor_fp or 0.85))
        return i * fs, f"estimada pela potência ({p_kw:.0f} kW, η {cfg['rendimento']:.2f}, FP {ped.motor_fp or 0.85:.2f}) × FS", i
    return 0.0, "", 0.0


def _tensao_fmax(ped):
    # conservador: o inversor pode ser programado até a frequência nominal mesmo que o pedido diga menos
    fmax = max(float(ped.f_saida_max_hz or ped.freq_rede_hz), float(ped.freq_rede_hz), 1.0)
    v = min(ped.tensao_v * fmax / ped.freq_rede_hz, ped.tensao_v)
    return v, fmax


def calcular(ped, cat=None, c_y_uf=None, ripple_rms_a=None, ripple_pp_a=None, ipk_sim_a=None, isat_margem=1.25):
    """Decomposição completa. c_y_uf/ripple None = 1ª passada (estimativas)."""
    cfg = _cfg(cat)
    i_m, origem, i_placa = corrente_motor(ped, cat)
    i_cli = float(getattr(ped, "corrente_cliente_a", None) or ped.corrente_a or 0)
    i_inv = float(ped.inversor_corrente_a or 0)
    if i_m <= 0:          # sem dado de carga: fica a corrente do cliente
        return dict(base="cliente", i_term_a=i_cli, i_cliente_a=i_cli, i_inversor_a=i_inv, componentes=[],
                    notas=["Sem dados do motor (corrente de placa ou potência): mantida a corrente informada pelo cliente."])
    v, fmax = _tensao_fmax(ped)
    vph = v / math.sqrt(3)
    w = 2 * math.pi * fmax
    fp = min(max(float(ped.motor_fp or 0.85), 0.5), 1.0)
    # capacitores do filtro (estrela equivalente) – a corrente deles passa pelo indutor
    estimado_c = c_y_uf is None
    c_y = float(c_y_uf) if c_y_uf else 0.0
    i_cap = vph * w * c_y * 1e-6
    # capacitância do cabo do motor (também passa pelo indutor)
    c_cabo = cfg["c_cabo_uf_km"] * float(ped.cabo_m or 0) / 1000.0
    i_cabo = vph * w * c_cabo * 1e-6
    # soma fasorial (motor indutivo, capacitores e cabo capacitivos) – sem crédito da compensação
    ia = i_m * fp
    ir = i_m * math.sqrt(1 - fp * fp) - (i_cap + i_cabo)
    i_vet = math.hypot(ia, ir)
    i_fund = max(i_vet, i_m, i_cap + i_cabo)
    i_vazio = i_cap + i_cabo
    estimado_r = ripple_rms_a is None
    i_rip = float(ripple_rms_a) if ripple_rms_a is not None else RIPPLE_PROVISORIO * i_fund
    i_rms = math.hypot(i_fund, i_rip)
    i_term_exata = i_rms * cfg["margem"]
    i_term = float(math.ceil(i_term_exata - 1e-9))
    rpp = float(ripple_pp_a) if ripple_pp_a is not None else 2 * math.sqrt(3) * i_rip
    i_ref_pico = i_inv if i_inv > 0 else max(i_cli, i_term)
    isat_inv = math.sqrt(2) * i_ref_pico + rpp / 2
    isat_carga = isat_margem * (float(ipk_sim_a) if ipk_sim_a else (math.sqrt(2) * i_term + rpp / 2))
    iovl = 1.5 * math.sqrt(2) * i_ref_pico + rpp / 2
    comp = [
        ("Motor: corrente × fator de serviço", f"{i_placa:.1f} A × {max(float(ped.fator_servico or 1), 1):.2f}", i_m, origem),
        ("Capacitores do filtro (fundamental, f máx)", f"{vph:.0f} V × 2π·{fmax:g} Hz × {c_y:.0f} µF (Y eq.)", i_cap,
         "estimativa – recalculada com o banco escolhido" if estimado_c else "banco escolhido"),
        ("Capacitância do cabo do motor", f"{cfg['c_cabo_uf_km']:.2f} µF/km × {float(ped.cabo_m or 0):g} m", i_cabo, "cabo blindado típico"),
        ("Fundamental no indutor (soma fasorial, sem crédito capacitivo)", f"FP motor {fp:.2f}", i_fund, "≥ corrente do motor"),
        ("Ripple de alta frequência (rms)", "soma em quadratura", i_rip,
         "estimativa 5 % (1ª passada)" if estimado_r else "simulação no pior ponto"),
        ("Corrente rms total", "√(I_fund² + I_ripple²)", i_rms, ""),
        (f"Margem de projeto", f"× {cfg['margem']:.2f}", i_term_exata, "envelhecimento, tensão de rede, tolerâncias"),
        ("CORRENTE TÉRMICA DE PROJETO (arredondada)", "", i_term, "define cobre, perdas e elevação de temperatura"),
    ]
    notas = []
    if i_inv and i_term > i_inv * 1.0001:
        notas.append(f"A corrente térmica pela carga ({i_term:.0f} A) é maior que a nominal do inversor ({i_inv:.0f} A): "
                     "verificar se o inversor está subdimensionado para o motor. O filtro foi dimensionado pela carga.")
    if i_cli and abs(i_cli - i_term) / i_cli > 0.03:
        notas.append(f"O cliente pediu {i_cli:g} A; a Electric dimensiona pela carga real: {i_term:.0f} A térmicos "
                     f"(o ferro continua dimensionado pela corrente do inversor, {i_ref_pico:.0f} A, com sobrecarga de 150 %).")
    return dict(base="carga", i_term_a=i_term, i_term_exata_a=round(i_term_exata, 2), i_cliente_a=i_cli, i_inversor_a=i_inv,
                i_motor_a=round(i_m, 2), i_motor_placa_a=round(i_placa, 2), origem_motor=origem, i_cap_a=round(i_cap, 2),
                i_cabo_a=round(i_cabo, 3), i_fund_a=round(i_fund, 2), i_vetorial_a=round(i_vet, 2), i_vazio_a=round(i_vazio, 2),
                i_ripple_rms_a=round(i_rip, 2), i_ripple_pp_a=round(rpp, 2), i_rms_a=round(i_rms, 2), margem=cfg["margem"],
                f_max_hz=fmax, v_fmax=round(v, 1), c_y_uf=c_y, estimado=bool(estimado_c or estimado_r),
                isat_inversor_a=round(isat_inv, 1), isat_carga_a=round(isat_carga, 1), isat_a=round(max(isat_inv, isat_carga), 1),
                iovl_a=round(iovl, 1), i_ref_pico_a=i_ref_pico,
                componentes=[dict(item=a, conta=b, valor_a=round(float(c), 2), obs=d) for a, b, c, d in comp], notas=notas)


def exata_do_projeto(ped, cat, proj):
    """2ª passada: com o banco e o ripple simulados do projeto."""
    l1 = proj.l1
    return calcular(ped, cat, c_y_uf=proj.banco.c_y_uf, ripple_rms_a=float(l1.ripple_rms_a or 0),
                    ripple_pp_a=float(l1.ripple_pp_a or 0), ipk_sim_a=float(l1.i_pico_a or 0),
                    isat_margem=float(cat.get("projeto_padrao", {}).get("isat_margem", 1.25)))


def texto(cc, curto=False):
    """Texto (pt-BR) da base de corrente para ET / e-mail / memorial."""
    if not cc or cc.get("base") != "carga":
        return ("Corrente de dimensionamento: a informada pelo cliente"
                + (f" ({cc.get('i_term_a', 0):g} A)" if cc else "") + ".")
    if curto:
        return (f"Corrente térmica {cc['i_term_a']:.0f} A definida pela carga (motor {cc['i_motor_placa_a']:g} A × FS = "
                f"{cc['i_motor_a']:.1f} A + capacitores + cabo + ripple, margem {cc['margem']:.2f}); "
                f"saturação ≥ {cc['isat_a']:.0f} A pico (inversor {cc['i_ref_pico_a']:.0f} A), "
                f"sobrecarga 150 % do inversor: {cc['iovl_a']:.0f} A pico.")
    ls = ["BASE DA CORRENTE (definida pela Electric Service a partir da carga – o cliente não define a corrente do indutor):"]
    for c in cc["componentes"]:
        ls.append(f"  • {c['item']}: {c['valor_a']:.1f} A" + (f"  ({c['conta']})" if c["conta"] else "")
                  + (f" – {c['obs']}" if c["obs"] else ""))
    ls.append(f"  • Saturação (L ≥ 90 %): Isat ≥ {cc['isat_a']:.0f} A pico = máx(1,25 × pico na corrente térmica "
              f"{cc['isat_carga_a']:.0f} A; √2 × I_inversor {cc['i_ref_pico_a']:.0f} A + ripple/2 = {cc['isat_inversor_a']:.0f} A)")
    ls.append(f"  • Sobrecarga do inversor 150 % / 60 s (L ≥ 70 %): {cc['iovl_a']:.0f} A pico")
    if cc.get("i_cliente_a"):
        ls.append(f"  • Corrente pedida pelo cliente: {cc['i_cliente_a']:g} A (informativa)")
    for n in cc.get("notas", []):
        ls.append(f"  ! {n}")
    return "\n".join(ls)
