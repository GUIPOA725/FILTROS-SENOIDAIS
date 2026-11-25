"""Lista de material (BOM) por fornecedor, custo e formação de preço."""
from __future__ import annotations
import math
from dataclasses import dataclass, asdict, field
from typing import List, Dict


@dataclass
class ItemBOM:
    item: int
    grupo: str              # INDUTOR, CAPACITOR, RESISTOR, CAIXA, CABOS_MISC, MONTAGEM
    fornecedor: str
    descricao: str
    especificacao: str
    qtd: float
    un: str
    custo_unit: float
    fornecido_por: str      # "Electric Service" (envia à montadora) ou "Montadora"
    tag: str = ""

    @property
    def total(self):
        return round(self.qtd * self.custo_unit, 2)


@dataclass
class Orcamento:
    itens: List[ItemBOM]
    custo_material: float
    custo_montagem: float
    custo_unit_total: float
    preco_unit: float
    preco_total: float
    quantidade: int
    impostos_pct: float
    margem_pct: float
    frete_pct: float
    comissao_pct: float
    divisor: float
    por_grupo: Dict[str, float] = field(default_factory=dict)

    def to_dict(self):
        d = asdict(self)
        for i, it in enumerate(self.itens):
            d["itens"][i]["total"] = it.total
        return d


NH = [16, 20, 25, 32, 40, 50, 63, 80, 100, 125, 160, 200, 250, 315, 400]


def montar_bom(proj, arr, cat) -> List[ItemBOM]:
    m = cat["miscelanea"]
    ped = proj.pedido
    forn = cat["fornecedores"]
    nome = lambda g: forn[g][0]["nome"] if forn.get(g) else g
    b = proj.banco
    am = proj.amortecimento
    itens: List[ItemBOM] = []

    def add(grupo, fornecedor, desc, spec, qtd, un, cu, por, tag=""):
        itens.append(ItemBOM(len(itens) + 1, grupo, fornecedor, desc, spec, qtd, un, round(cu, 2), por, tag))

    for L in [proj.l1] + ([proj.l2] if proj.l2 else []):
        add("INDUTOR", nome("indutor"), f"Indutor trifásico núcleo comum para filtro senoidal – {L.nome.split(' – ')[0]}",
            f"{L.l_uh:.0f} µH/fase ±5 %; In térmica {L.i_nom_a:.0f} A (fund. {L.i_fund_a:.0f} A + ondulação {L.ripple_rms_a:.0f} A RMS @ "
            f"{L.f_chav_hz / 1000:g} kHz); Isat ≥ {L.i_sat_a:.0f} A pico; isolação 1,1 kV; classe F/H; "
            f"perdas ≤ {L.perdas_w:.0f} W", 1, "pç", L.custo, "Electric Service", L.nome.split(" ")[0])
    add("CAPACITOR", f"{b.fabricante}", f"Capacitor monofásico MKP {b.uf_unit:g} µF {b.v_unit:g} V – {b.linha}",
        f"P/N {b.pn}; {_norma_cap(cat, b.cap_id)}; autorregenerativo c/ dispositivo de sobrepressão; Irms aplicada {b.i_unit_rms:.1f} A "
        f"(admissível {b.i_unit_max:.1f} A)",
        b.n_total, "pç", b.preco_unit, "Electric Service", "C")
    add("CAPACITOR", f"{b.fabricante}", "Resistor de descarga (se o capacitor não tiver interno)",
        f"{b.r_descarga_mohm * 1000:.0f} kΩ TOTAL por capacitor, ≥ 1 kV (se usar 2 em série para a tensão, cada um com "
        f"{b.r_descarga_mohm * 500:.0f} kΩ, {max(0.5, b.r_descarga_w / 2):g} W) – descarga ≤ 50 V em 60 s",
        b.n_total, "pç", m["preco_resistor_descarga"], "Montadora", "R")
    if am and am.tipo == "rc_paralelo":
        add("CAPACITOR", f"{b.fabricante}", f"Capacitor do ramo de amortecimento {b.uf_unit:g} µF {b.v_unit:g} V (mesmo tipo do banco)",
            f"{am.n_cd_por_ramo} por ramo, em série com o resistor de amortecimento", 3 * am.n_cd_por_ramo, "pç", b.preco_unit,
            "Electric Service", "CD")
    if am:
        add("RESISTOR", "Fabricante de resistores de potência", "Resistor de amortecimento " + ("do ramo RC paralelo" if am.tipo == "rc_paralelo" else "em série com o banco") + " (fio em tubo cerâmico)",
            f"{am.r_ramo_ohm:.3f} Ω ±10 %, {am.p_nominal_w:g} W, isolação 1,1 kV, Irms {am.i_ramo_rms:.0f} A "
            f"(componente HF até {3 * proj.fs_hz / 1000:g} kHz), baixa indutância", 3, "pç", 150 + 0.9 * am.p_nominal_w,
            "Montadora", "RD")
    add("CAIXA", nome("caixa"), f"Caixa/armário metálico {arr.caixa_tipo} {arr.caixa_l}x{arr.caixa_a}x{arr.caixa_p} mm IP{arr.caixa_ip}",
        "Chapa aço 1,5/2,0 mm, pintura epóxi-pó RAL 7035, placa de montagem, porta com fecho, chapa de passagem de cabos "
        "inferior, olhais de içamento" + (", soleira 100 mm" if arr.soleira_mm else ""), 1, "pç", arr.caixa_preco, "Montadora", "CX")
    add("CAIXA", nome("caixa"), "Ventilador com grelha e filtro de saída (exaustão)",
        f"{m['ventilador_m3h']} m³/h, 220 Vca, IP54", arr.n_ventiladores, "pç", m["preco_ventilador"], "Montadora", "M")
    add("CAIXA", nome("caixa"), "Grelha de entrada de ar com filtro", "Compatível com o ventilador, IP54",
        arr.n_ventiladores, "pç", 0.45 * m["preco_ventilador"], "Montadora", "GR")
    add("CABOS_MISC", nome("cabos_misc"), "Termostato NA para comando dos ventiladores", "Ajuste 0–60 °C, 10 A 250 V, trilho DIN",
        1, "pç", m["preco_termostato"], "Montadora", "TH")
    for c in arr.cabos:
        add("CABOS_MISC", nome("cabos_misc"), c["desc"], f"Cobre classe 5; {c['uso']}", c["metros"], "m",
            cat["preco_cabo_por_mm2_m"] * c["secao"] + 1.0, "Montadora")
    s_pot = arr.cabos[0]["secao"]
    n_term = 12 * arr.cabos[0]["n_par"] + 6
    add("CABOS_MISC", nome("cabos_misc"), f"Terminal tubular de compressão {s_pot} mm² (furo conforme borne)", "Cobre estanhado",
        n_term, "pç", 6 + 0.12 * s_pot, "Montadora")
    add("CABOS_MISC", nome("cabos_misc"), "Terminais/ilhós para cabos do banco e auxiliares", "Diversos", 1, "cj",
        60 + 4 * proj.banco.n_total, "Montadora")
    add("CABOS_MISC", nome("cabos_misc"), "Borne de potência / barramento isolado por polo (X1, X2)",
        f"≥ {proj.pedido['corrente_a'] * 1.25:.0f} A, 1 kV, para cabo {s_pot} mm²", 6, "pç", m["preco_terminal_pot"], "Montadora", "X1/X2")
    add("CABOS_MISC", nome("cabos_misc"), "Barramento de terra PE em cobre com isoladores", "Cu 25x5 mm, 8 furos", 1, "pç", 160,
        "Montadora", "PE")
    add("CABOS_MISC", nome("cabos_misc"), "Bornes auxiliares X3 + disjuntor/fusível auxiliar 2 A", "Trilho DIN", 1, "cj", 120,
        "Montadora", "X3")
    add("CABOS_MISC", nome("cabos_misc"), "Placas de advertência e identificação", "Risco elétrico NR-10, 'capacitores – aguardar 5 min', placa de dados",
        3, "pç", m["preco_placa_adv"], "Montadora")
    add("CABOS_MISC", nome("cabos_misc"), "Miscelânea de montagem", "Trilhos, canaletas, abraçadeiras, anilhas, parafusos inox, isoladores, perfis de fixação do indutor",
        1, "vb", m["preco_diversos"], "Montadora")
    mt = cat["montagem"]
    horas = mt["horas_base"] + mt["horas_por_capacitor"] * proj.banco.n_total + (2 if am else 0) + (3 if proj.l2 else 0)
    add("MONTAGEM", nome("montagem"), "Serviço de montagem, cabeação, ensaios de rotina e embalagem",
        f"{horas:.1f} h estimadas – conforme Caderno de Montagem", horas, "h", mt["valor_hora"], "Montadora")
    return itens


def formar_preco(proj, itens: List[ItemBOM], cat) -> Orcamento:
    c = cat["comercial"]
    imp = c["impostos"]
    impostos = imp["icms_interestadual_pct"] + imp["pis_pct"] + imp["cofins_pct"] + imp["irpj_csll_pct"]
    material = sum(i.total for i in itens if i.grupo != "MONTAGEM")
    montagem = sum(i.total for i in itens if i.grupo == "MONTAGEM")
    custo = material + montagem
    divisor = 1 - (impostos + c["margem_pct"] + c["comissao_pct"] + c["frete_pct"]) / 100
    preco = custo / divisor
    preco = math.ceil(preco / 50) * 50
    q = int(proj.pedido.get("quantidade", 1) or 1)
    grupos = {}
    for i in itens:
        grupos[i.grupo] = round(grupos.get(i.grupo, 0) + i.total, 2)
    return Orcamento(itens=itens, custo_material=round(material, 2), custo_montagem=round(montagem, 2), custo_unit_total=round(custo, 2),
                     preco_unit=preco, preco_total=preco * q, quantidade=q, impostos_pct=round(impostos, 2), margem_pct=c["margem_pct"],
                     frete_pct=c["frete_pct"], comissao_pct=c["comissao_pct"], divisor=round(divisor, 4), por_grupo=grupos)


def _norma_cap(cat, cap_id):
    from .dimensionamento import NOMES_NORMA
    cap = next((c for c in cat.get("capacitores", []) if c["id"] == cap_id), {})
    n = (cap.get("norma") or "IEC60831")
    return NOMES_NORMA.get(n, n)
