"""Arranjo físico do filtro na caixa metálica, térmica e cabeagem interna."""
from __future__ import annotations
import math
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any


@dataclass
class Caixa2D:
    """Retângulo de um componente na vista frontal (x, z = canto inferior esquerdo) + profundidade y."""
    nome: str
    tag: str
    x: float
    z: float
    w: float
    h: float
    y: float
    d: float
    cor: str = "#cccccc"


@dataclass
class Arranjo:
    caixa_id: str
    caixa_l: int
    caixa_a: int
    caixa_p: int
    caixa_tipo: str
    caixa_ip: int
    caixa_preco: float
    soleira_mm: int
    componentes: List[Caixa2D]
    perdas_w: Dict[str, float]
    perda_total_w: float
    vazao_m3h: float
    n_ventiladores: int
    massa_total_kg: float
    cabos: List[Dict[str, Any]]
    obs: List[str] = field(default_factory=list)
    ordem: str = "indutor_embaixo"

    def to_dict(self):
        return asdict(self)


def secao_cabo(cat, corrente):
    tab = {int(k): v for k, v in cat["cabos_ampacidade"].items()}
    req = corrente * cat["cabo_fator_hf"] / cat["cabo_fator_painel"]
    for s in sorted(tab):
        if tab[s] >= req:
            return s, 1
    # paralelo
    maior = max(tab)
    n = math.ceil(req / (tab[maior] * 0.9))
    for s in sorted(tab):
        if n * tab[s] * 0.9 >= req:
            return s, n
    return maior, n


def secao_cabo_interno(cat, corrente, minimo=0.0):
    """v1.29.0 (REQ-PNL-032): fiação INTERNA do painel pela NBR IEC 61439-1 Anexo H (125 %, condutor 70 °C, ar interno 55 °C,
    força fora da canaleta, espaçados ≥ 1 diâmetro). O fator de efeito pelicular da ondulação (cabo_fator_hf) continua.
    secao_cabo() fica só para cabos de CAMPO (painel → motor, NBR 5410)."""
    from . import fiacao_iec61439 as FI
    c = FI.cabo(corrente * cat.get("cabo_fator_hf", 1.0), borne_min_mm2=minimo)
    return c["secao"], c["paralelos"], c


SECOES = [1.5, 2.5, 4, 6, 10, 16, 25, 35, 50, 70, 95, 120, 150, 185, 240, 300]


def secao_pe(s_fase):
    """Condutor de proteção: NBR IEC 61439-1 §8.4.3.2.3 / Tab. 5 (mesma regra da IEC 60364-5-54 / NBR 5410 tab. 58):
    S<=16 -> S; 16<S<=35 -> 16; S>35 -> S/2 (próxima padronizada)."""
    if s_fase <= 16:
        return s_fase
    if s_fase <= 35:
        return 16
    return next(x for x in SECOES if x >= s_fase / 2)


def projetar_arranjo(proj, cat, ordem: str = "indutor_embaixo") -> Arranjo:
    """ordem: 'indutor_embaixo' (padrão mecânico) ou 'capacitores_embaixo' (capacitores na entrada de ar fria)."""
    l1 = proj.l1
    banco = proj.banco
    am = proj.amortecimento
    capdef = next(c for c in cat["capacitores"] if c["id"] == banco.cap_id)
    cd, _, ch = capdef["dim_mm"]
    pitch_x = cd + 30
    linha_h = ch + 70
    n = banco.n_por_ramo + (am.n_cd_por_ramo if am and am.tipo == "rc_paralelo" else 0)   # Cd no mesmo suporte
    Wi, Hi, Di = l1.dim_mm
    Wi2 = Hi2 = Di2 = 0
    if proj.l2:
        Wi2, Hi2, Di2 = proj.l2.dim_mm

    pequeno = proj.pedido["corrente_a"] < 120
    folga = 80 if pequeno else 120
    zona_cabos = 120 if pequeno else 200      # chapa de passagem de cabos / prensa-cabos
    zona_bornes = 100 if pequeno else 140
    zona_topo = 110 if pequeno else 160       # exaustão
    h_rd = (150 if pequeno else 200) if am else 0

    obs = []
    ramos = ["U-V", "V-W", "W-U"] if banco.ligacao == "Delta" else ["U-N", "V-N", "W-N"]
    larg_ind = Wi + Wi2 + (folga if Wi2 else 0)

    def _layout(L):
        """Capacitores em grade: preferencialmente 1 ramo por linha; se o ramo é curto, vários ramos por linha."""
        por_linha = max(1, int((L - 2 * folga) // pitch_x))
        if n <= por_linha:
            ramos_por_linha = max(1, min(3, por_linha // n))
            linhas = math.ceil(3 / ramos_por_linha)
        else:
            ramos_por_linha = 1
            linhas = 3 * math.ceil(n / por_linha)
        return por_linha, ramos_por_linha, linhas

    escolha = None
    for cx in sorted(cat["caixas"], key=lambda c: c["preco"]):
        L = cx["l"]
        por_linha, rpl, linhas = _layout(L)
        largura_req = max(larg_ind + 2 * folga, min(n * rpl, por_linha) * pitch_x + 2 * folga, (360 + 2 * folga) if am else 0, 500)
        altura_req = zona_cabos + zona_bornes + 40 + max(Hi, Hi2) + folga + linhas * linha_h + h_rd + zona_topo
        prof_req = max(Di, Di2, ch + 60) + 2 * 90
        if L >= largura_req and cx["a"] >= altura_req and cx["p"] >= prof_req:
            escolha = cx
            break
    if escolha is None:
        escolha = max(cat["caixas"], key=lambda c: c["l"] * c["a"] * c["p"])
        obs.append("Nenhuma caixa do catálogo comporta o arranjo: usar caixa especial ou dividir em 2 colunas.")
    L, A, P = escolha["l"], escolha["a"], escolha["p"]
    por_linha, rpl, linhas = _layout(L)

    comps: List[Caixa2D] = []
    z = zona_cabos
    bw = min(70, (L - 2 * 60 - 160) / 6)
    comps.append(Caixa2D("Bornes de entrada X1 (U1 V1 W1) – do inversor", "X1", 50, z + 20, 3 * bw, 90, P - 220, 120, "#d9d2c3"))
    comps.append(Caixa2D("Bornes de saída X2 (U2 V2 W2) – para o motor", "X2", L - 50 - 3 * bw, z + 20, 3 * bw, 90, P - 220, 120, "#d9d2c3"))
    comps.append(Caixa2D("Barramento de terra PE", "PE", L / 2 - 70, z + 20, 140, 40, P - 200, 60, "#9bbf7a"))
    z += zona_bornes + 40
    def _indutores(z):
        if proj.l2:
            x0 = (L - larg_ind) / 2
            comps.append(Caixa2D("Indutor trifásico L1", "L1", x0, z, Wi, Hi, (P - Di) / 2, Di, "#7a8ca8"))
            comps.append(Caixa2D("Indutor trifásico L2", "L2", x0 + Wi + folga, z, Wi2, Hi2, (P - Di2) / 2, Di2, "#7a8ca8"))
            return z + max(Hi, Hi2) + folga
        else:
            comps.append(Caixa2D("Indutor trifásico L1", "L1", (L - Wi) / 2, z, Wi, Hi, (P - Di) / 2, Di, "#7a8ca8"))
            return z + Hi + folga

    def _capacitores(z):
        # capacitores
        pos = []
        if n <= por_linha:
            for r in range(3):
                lin, slot = divmod(r, rpl)
                for k in range(n):
                    pos.append((r, k, lin, slot * n + k + (slot if rpl > 1 else 0)))
            cols_max = rpl * n + (rpl - 1 if rpl > 1 else 0)
        else:
            lin_por_ramo = math.ceil(n / por_linha)
            for r in range(3):
                for k in range(n):
                    pos.append((r, k, r * lin_por_ramo + k // por_linha, k % por_linha))
            cols_max = por_linha
        x_ini = (L - cols_max * pitch_x) / 2 + (pitch_x - cd) / 2
        for r, k, lin, col in pos:
            comps.append(Caixa2D(f"Capacitor {banco.uf_unit:g} µF {banco.v_unit:g} V – ramo {ramos[r]}", f"C{r + 1}.{k + 1}",
                                 x_ini + col * pitch_x, z + lin * linha_h + 35, cd, ch, 40, cd, "#e3b04b"))
        return z + linhas * linha_h

    if ordem == "capacitores_embaixo":
        z = _capacitores(z)
        z = _indutores(z + 40)
    else:
        z = _indutores(z)
        z = _capacitores(z)
    if am:
        for r in range(3):
            comps.append(Caixa2D(f"Resistor de amortecimento {am.r_ramo_ohm:.3f} Ω {am.p_nominal_w:g} W", f"RD{r + 1}",
                                 (L - 360) / 2, z + 25 + r * 55, 360, 45, 80, 45, "#c97c5d"))
        z += h_rd
    comps.append(Caixa2D("Termostato + bornes auxiliares X3 (220 Vca)", "X3", 60, A - zona_topo + 20, 160, 70, P - 160, 80, "#d9d2c3"))

    # térmica
    perdas = {"Indutor L1": l1.perdas_w}
    if proj.l2:
        perdas["Indutor L2"] = proj.l2.perdas_w
    if am:
        perdas["Resistores de amortecimento"] = am.p_total_w
    perdas["Capacitores"] = round(0.5 * banco.kvar_60 + banco.n_total * 0.5, 1)   # MKP ~0,5 W/kvar + HF + resistores descarga
    perdas["Cabos/conexões"] = 0.0            # v1.32.0: calculado abaixo por I²·R real dos cabos internos (era 0,0002·V·I·0,5)
    ptot = sum(perdas.values())
    dt = cat["projeto_padrao"]["delta_t_painel_k"]
    vazao = 3.1 * ptot / dt
    nvent = max(1, math.ceil(vazao / cat["miscelanea"]["ventilador_m3h"]))
    massa = l1.massa_kg + (proj.l2.massa_kg if proj.l2 else 0) + banco.n_total * capdef["peso_kg"]
    massa_caixa = round(7.85 * 1.5 * 2 * (L * A + L * P + A * P) / 1e6, 0)   # chapa 1,5 mm
    massa += massa_caixa + 15

    # cabos internos
    i_lin = max(l1.i_nom_a, proj.pedido["corrente_a"])
    s_pot, n_par, _cpot = secao_cabo_interno(cat, i_lin)        # v1.29.0: NBR IEC 61439-1 Anexo H (era tabela de campo)
    lig_delta = banco.ligacao == "Delta"
    i_ramo = am.i_ramo_rms if am else (banco.i_unit_rms * n)
    s_cap, _, _ccap = secao_cabo_interno(cat, max(i_ramo * 1.3, 16), minimo=10)     # IEC 61921 §6.2.2: 1,3 × I do capacitor
    s_jump, _, _cjmp = secao_cabo_interno(cat, max(banco.i_unit_rms * 1.3, 8), minimo=6)
    alt_m = A / 1000
    cabos = [
        dict(desc=f"Cabo flexível 0,6/1 kV HEPR 90 °C {n_par}x{s_pot} mm² – X1→L1 (por fase) – força fora da canaleta, espaçados ≥ 1 diâmetro", secao=s_pot, n_par=n_par, calc=_cpot["texto"],
             metros=round(3 * n_par * (0.6 + 0.4 * alt_m), 1), uso="potência"),
        dict(desc=f"Cabo flexível 0,6/1 kV HEPR 90 °C {n_par}x{s_pot} mm² – L1→X2 (por fase) – força fora da canaleta, espaçados ≥ 1 diâmetro", secao=s_pot, n_par=n_par, calc=_cpot["texto"],
             metros=round(3 * n_par * (0.6 + 0.4 * alt_m), 1), uso="potência"),
        dict(desc=f"Cabo flexível 0,6/1 kV {s_cap} mm² – derivação L1 saída → banco de capacitores (fora da canaleta)", secao=s_cap, n_par=1, calc=_ccap["texto"],
             metros=round(3 * (0.8 + 0.5 * alt_m) * (2 if am else 1), 1), uso="ramo capacitivo"),
        dict(desc=f"Cabo flexível 750 V {s_jump} mm² – jumpers entre capacitores", secao=s_jump, n_par=1, calc=_cjmp["texto"],
             metros=round(banco.n_total * 2 * 0.25, 1), uso="jumpers"),
        dict(desc=f"Cabo flexível verde/amarelo {secao_pe(s_pot)} mm² – aterramento indutor/caixa/porta", secao=secao_pe(s_pot),
             n_par=1, metros=round(3.0 + alt_m, 1), uso="terra"),
        dict(desc="Cabo flexível 750 V 1,5 mm² – ventiladores/termostato", secao=1.5, n_par=1, metros=round(4 + 2 * alt_m, 1),
             uso="auxiliar"),
    ]
    # v1.32.0 (REQ-SEN-026, auditoria A&W): perdas dos cabos internos por I²·R real (NBR IEC 61439-1 Anexo H: Pv = I²·R20·[1+0,004·(Tc−20)],
    # Tc 70 °C) com a corrente REAL de cada trecho (não a de dimensionamento ×1,25/×1,3) + 20 % para conexões/terminais.
    from . import fiacao_iec61439 as _FI
    def _p_cabo(i_cond, secao, metros):
        r20 = _FI.H1.get(secao, (0.0,))[0] / 1000.0
        return (i_cond ** 2) * r20 * (1 + 0.004 * (70 - 20)) * metros
    _i_hf = cat.get("cabo_fator_hf", 1.0)
    p_cab = (_p_cabo(i_lin * _i_hf / n_par, s_pot, cabos[0]["metros"]) + _p_cabo(i_lin * _i_hf / n_par, s_pot, cabos[1]["metros"])
             + _p_cabo(i_ramo, s_cap, cabos[2]["metros"]) + _p_cabo(banco.i_unit_rms, s_jump, cabos[3]["metros"]))
    perdas["Cabos/conexões"] = round(1.2 * p_cab, 1)
    ptot = sum(perdas.values())
    vazao = 3.1 * ptot / dt
    nvent = max(1, math.ceil(vazao / cat["miscelanea"]["ventilador_m3h"]))
    if lig_delta is False:
        obs.append("Banco em estrela: neutro isolado (não aterrar o centro-estrela).")
    obs.append(f"Dissipação total estimada {ptot:.0f} W → vazão mínima {vazao:.0f} m³/h para ΔT = {dt} K "
               f"({nvent} ventilador(es) de {cat['miscelanea']['ventilador_m3h']} m³/h com filtro).")
    if escolha["tipo"] == "piso":
        obs.append("Caixa de piso: prever soleira de 100 mm e olhais de içamento; indutor fixado em perfis no fundo/base.")

    if ordem == "capacitores_embaixo":
        obs.append("Arranjo térmico: capacitores na entrada de ar (parte inferior) e indutor acima, sobre perfis reforçados.")
    return Arranjo(ordem=ordem, caixa_id=escolha["id"], caixa_l=L, caixa_a=A, caixa_p=P, caixa_tipo=escolha["tipo"], caixa_ip=escolha["ip"],
                   caixa_preco=escolha["preco"], soleira_mm=100 if escolha["tipo"] == "piso" else 0, componentes=comps,
                   perdas_w={k: round(v, 1) for k, v in perdas.items()}, perda_total_w=round(ptot, 0),
                   vazao_m3h=round(vazao, 0), n_ventiladores=nvent, massa_total_kg=round(massa, 0), cabos=cabos, obs=obs)
