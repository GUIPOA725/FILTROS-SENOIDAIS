"""Estudo térmico do filtro montado: perdas por componente, escoamento de ar na caixa, temperatura do ar no ponto de
cada componente, temperatura do componente e limites (IEC 61439-1 cl.10.10, IEC TR 60890, IEC 60076-6, IEC 60831; fiação interna NBR IEC 61439-1 Anexo H).

Modelo (1-D, ventilação forçada de baixo para cima):
- o ar entra pela grelha inferior a T_amb e é aquecido pelas fontes que estão abaixo de cada altura:
      T_ar(z) = T_amb + Σ_{fontes abaixo de z} P_i·(1 − f_parede) / (ρ·cp·V̇_ef)
  (fração f_parede da potência sai pelas paredes por convecção natural – IEC TR 60890, k ≈ 5,5 W/m²K);
- cada componente: T = T_ar(local) + elevação própria (P/(h·A) para indutor e resistor, P·Rth para capacitor);
- vazão efetiva dos ventiladores = vazão livre × fator de filtros/contrapressão.
"""
from __future__ import annotations
import math
from typing import Dict, Any, List

RHO_CP = 1.2 * 1005 / 3600.0      # W·h/(m³·K) → P[W] = RHO_CP·V̇[m³/h]·ΔT


def _par(cat):
    t = dict(amb_max_c=cat["projeto_padrao"].get("amb_max_c", 40), fator_filtro_vent=0.6, k_parede_w_m2k=5.5,
             h_indutor_w_m2k=14.0, fator_area_indutor=2.5, fator_hotspot_indutor=1.15, classe_indutor_c=155,
             elevacao_indutor_k=100, h_resistor_w_m2k=25.0, t_resistor_max_c=300, elev_ar_saida_max_k=15,
             elev_superficie_max_k=30, elev_terminal_max_k=70, t_cabo_max_c=90, max_vent=6)
    t.update(cat.get("termico", {}))
    return t


def _perdas_componentes(proj, arr, cat):
    """Lista de fontes de calor com altura (centro) e área de troca."""
    comps = {c.tag: c for c in arr.componentes}
    fontes = []
    L = proj.l1
    c = comps.get("L1")
    if c:
        a = 2 * (c.w * c.h + c.w * c.d + c.h * c.d) / 1e6
        fontes.append(dict(nome="Indutor L1", tag="L1", p=L.perdas_w, z0=c.z, z1=c.z + c.h, area=a, tipo="indutor"))
    if proj.l2 and comps.get("L2"):
        c = comps["L2"]
        a = 2 * (c.w * c.h + c.w * c.d + c.h * c.d) / 1e6
        fontes.append(dict(nome="Indutor L2", tag="L2", p=proj.l2.perdas_w, z0=c.z, z1=c.z + c.h, area=a, tipo="indutor"))
    caps = [c for c in arr.componentes if c.tag.startswith("C") and "." in c.tag]
    e = getattr(proj, "estresse_capacitor", {}) or {}
    p_cap = e.get("perdas_w", 0.3)
    if caps:
        z0 = min(c.z for c in caps)
        z1 = max(c.z + c.h for c in caps)
        fontes.append(dict(nome=f"Capacitores ({len(caps)} pç)", tag="C", p=p_cap * len(caps) + 0.2 * len(caps), z0=z0, z1=z1,
                           area=0.0, tipo="capacitor", p_unit=p_cap, n=len(caps)))
    am = proj.amortecimento
    rds = [c for c in arr.componentes if c.tag.startswith("RD")]
    if am and rds:
        z0 = min(c.z for c in rds)
        z1 = max(c.z + c.h for c in rds)
        a = sum(math.pi * (c.h / 1000) * (c.w / 1000) for c in rds)
        fontes.append(dict(nome="Resistores de amortecimento", tag="RD", p=am.p_total_w, z0=z0, z1=z1, area=a, tipo="resistor"))
    # cabos e conexões internas: I²R
    i = max(proj.l1.i_nom_a, proj.pedido["corrente_a"])
    s_pot = arr.cabos[0]["secao"] if arr.cabos else 95
    r_km = 0.0175 * 1.25 / s_pot * 1000 / arr.cabos[0].get("n_par", 1) if arr.cabos else 0.2
    l_m = sum(cb["metros"] for cb in arr.cabos[:2]) if arr.cabos else 6
    p_cabos = (i ** 2) * r_km / 1000 * l_m / 1.0 + 6 * 2.0      # + 6 conexões ~2 W
    fontes.append(dict(nome="Cabos e conexões de potência", tag="CB", p=p_cabos, z0=0, z1=arr.caixa_a, area=0, tipo="cabo"))
    return fontes


def estudo_termico(proj, arr, cat, n_vent=None, vazao_unit=None) -> Dict[str, Any]:
    t = _par(cat)
    fontes = _perdas_componentes(proj, arr, cat)
    ptot = sum(f["p"] for f in fontes)
    L, A, P = arr.caixa_l / 1000, arr.caixa_a / 1000, arr.caixa_p / 1000
    # superfície efetiva de troca (IEC TR 60890: piso não conta; laterais/fundo parcialmente encostados – aproximação)
    ae = L * P + 2 * (A * P) * 0.8 + L * A * 2 * 0.9
    vazao_unit = vazao_unit or cat["miscelanea"]["ventilador_m3h"]
    n = n_vent if n_vent is not None else arr.n_ventiladores
    v_ef = n * vazao_unit * t["fator_filtro_vent"]
    T0 = t["amb_max_c"]
    # equilíbrio: P = (k·Ae + ρcp·V̇)·ΔT_saída/ (aprox. paredes à média da elevação)
    g_vent = RHO_CP * max(v_ef, 1e-6)
    g_par = t["k_parede_w_m2k"] * ae * 0.5
    dT_saida = ptot / (g_vent + g_par)
    f_parede = g_par * dT_saida / ptot if ptot else 0
    # perfil vertical
    zs = [i * arr.caixa_a / 40 for i in range(41)]

    def t_ar(z):
        acc = 0.0
        for f in fontes:
            if f["tipo"] == "cabo":
                frac = min(max(z / arr.caixa_a, 0), 1)
            elif z <= f["z0"]:
                frac = 0.0
            elif z >= f["z1"]:
                frac = 1.0
            else:
                frac = (z - f["z0"]) / max(f["z1"] - f["z0"], 1)
            acc += f["p"] * frac
        return T0 + acc * (1 - f_parede) / g_vent if v_ef > 0 else T0 + acc / max(g_par, 1)

    perfil = [(round(z), round(t_ar(z), 1)) for z in zs]
    linhas = []
    ver = []

    def add(nome, p, t_ar_loc, t_comp, lim, ok, ref, crit=True):
        linhas.append(dict(componente=nome, perdas_W=round(p, 1), t_ar_local_C=round(t_ar_loc, 1), t_componente_C=round(t_comp, 1),
                           limite=lim, ok=bool(ok), referencia=ref))
        ver.append(dict(item=f"Térmico – {nome}", valor=f"{t_comp:.1f} °C (ar local {t_ar_loc:.1f} °C)", limite=lim, ok=bool(ok),
                        referencia=ref, critico=crit))

    cap_ct = cat.get("capacitor_termico", {})
    capdef = next((c for c in cat["capacitores"] if c["id"] == proj.banco.cap_id), {})
    for f in fontes:
        zc = (f["z0"] + f["z1"]) / 2
        if f["tipo"] == "indutor":
            ta = t_ar(f["z1"])                   # v1.26.4 (auditoria AW-02): ar no TOPO do indutor (onde fica o ponto quente), não no quarto inferior
            fem = getattr(proj, "_ind_fem_termico", None) if f["tag"] == "L1" else None
            if fem and fem.get("p") and fem.get("elev"):
                # v1.11.1: elevação média do projeto FEM do indutor, escalada para as perdas usadas aqui (∝ P^0,8), + 15 K de
                # gradiente ao ponto quente (IEC 60076-11)
                elev = float(fem["elev"]) * (f["p"] / float(fem["p"])) ** 0.8
                th = ta + elev + 15.0
                # v1.26.4 (REQ-GER-014): limite = classe PEDIDA pelo cliente (antes: classe H do catálogo, mesmo com o cliente pedindo F)
                lim_c = min(float(t["classe_indutor_c"]), float(fem.get("limite_c") or t["classe_indutor_c"]))
                ok = th <= lim_c and elev <= t["elevacao_indutor_k"]
                add(f"{f['nome']} (ponto quente do enrolamento)", f["p"], ta, th,
                    f"≤ {lim_c:.0f} °C (classe do projeto) e elevação média ≤ {t['elevacao_indutor_k']} K", ok,
                    f"Projeto do indutor por elementos finitos ({fem.get('metodo') or 'método de projeto'}): elevação {fem['elev']:.0f} K a {fem['p']:.0f} W, escalada para "
                    f"{f['p']:.0f} W (limite contratual) → {elev:.0f} K + 15 K ao ponto quente")
                continue
            dT = f["p"] / (t["h_indutor_w_m2k"] * f["area"] * t["fator_area_indutor"]) * t["fator_hotspot_indutor"]
            th = ta + dT
            lim_c = t["classe_indutor_c"]
            ok = th <= lim_c and dT / t["fator_hotspot_indutor"] <= t["elevacao_indutor_k"]
            add(f"{f['nome']} (ponto quente do enrolamento)", f["p"], ta, th,
                f"≤ {lim_c} °C e elevação ≤ {t['elevacao_indutor_k']} K", ok,
                "IEC 60076-6 / classe de isolamento – área com dutos de ventilação (estimativa: confirmar com o fabricante)")
        elif f["tipo"] == "capacitor":
            ta = t_ar(f["z1"])          # pior capacitor: o mais alto
            th = ta + f["p_unit"] * capdef.get("rth_k_w", 12.0)
            from .dimensionamento import limites_capacitor
            lcap = limites_capacitor(capdef, cat)
            lim = lcap["t_hot"]
            add(f"{f['nome']} – unidade mais alta", f["p"], ta, th, f"≤ {lim:g} °C (ponto quente)", th <= lim,
                f"{lcap['norma_txt']} / datasheet: ponto quente máx. e vida do filme PP")
            vida = lcap["vida_h"] * 2 ** ((lcap["t_vida"] - th) / cap_ct.get("k_dobra_c", 7))
            linhas[-1]["vida_estimada_h"] = round(vida)
            amb_cat = 55
            ver.append(dict(item="Térmico – ar em volta dos capacitores (categoria de temperatura)", valor=f"{ta:.1f} °C",
                            limite=f"≤ {amb_cat} °C (categoria D)", ok=ta <= amb_cat, referencia="IEC 60831-1 – categoria −25/D",
                            critico=True))
        elif f["tipo"] == "resistor":
            ta = t_ar(f["z0"])
            ts = ta + f["p"] / max(t["h_resistor_w_m2k"] * f["area"], 1e-3)
            add(f["nome"] + " (superfície)", f["p"], ta, ts, f"≤ {t['t_resistor_max_c']} °C", ts <= t["t_resistor_max_c"],
                "Fabricante do resistor; manter 100 mm de afastamento de plásticos e capacitores", crit=False)
        else:
            ta = t_ar(arr.caixa_a)
            from . import fiacao_iec61439 as _FI                    # v1.29.0 (REQ-PNL-032): fiação interna pela NBR IEC 61439-1
            add("Cabos internos – ar no painel ≤ ar de projeto da fiação (Anexo H, condutor 70 °C)", f["p"], ta, ta,
                f"≤ {_FI.T_AR_INTERNO_C:g} °C (k1 {_FI.k1(ta):.2f} ≥ {_FI.k1(_FI.T_AR_INTERNO_C):.2f})",
                ta <= _FI.T_AR_INTERNO_C, "NBR IEC 61439-1 §10.10.4.3.1 f) / Anexo H Tab. H.2")
    t_saida = t_ar(arr.caixa_a)
    ver.append(dict(item="Térmico – elevação do ar na saída da caixa", valor=f"{t_saida - T0:.1f} K ({t_saida:.1f} °C)",
                    limite=f"≤ {t['elev_ar_saida_max_k']} K", ok=t_saida - T0 <= t["elev_ar_saida_max_k"],
                    referencia="IEC 61439-1 cl.10.10 / premissa dos componentes", critico=True))
    dT_sup = (ptot * f_parede) / (6.0 * ae)
    ver.append(dict(item="Térmico – superfície externa da caixa (acessível)", valor=f"+{dT_sup:.1f} K", limite=f"≤ {t['elev_superficie_max_k']} K",
                    ok=dT_sup <= t["elev_superficie_max_k"], referencia="IEC 61439-1 tab.6 (superfícies metálicas acessíveis)",
                    critico=False))
    dT_term = (t_ar(arr.caixa_a * 0.15) - T0) + 25
    ver.append(dict(item="Térmico – bornes de potência (elevação)", valor=f"≈ {dT_term:.0f} K", limite=f"≤ {t['elev_terminal_max_k']} K",
                    ok=dT_term <= t["elev_terminal_max_k"], referencia="IEC 61439-1 tab.6 (terminais para condutores externos)",
                    critico=False))
    return dict(perdas=[dict(componente=f["nome"], perdas_W=round(f["p"], 1)) for f in fontes], perdas_total_W=round(ptot),
                n_ventiladores=n, vazao_livre_m3h=n * vazao_unit, vazao_efetiva_m3h=round(v_ef), fracao_paredes=round(f_parede, 2),
                t_ambiente_C=T0, t_saida_C=round(t_saida, 1), perfil=perfil, componentes=linhas, verificacoes=ver,
                aprovado=all(v["ok"] for v in ver if v["critico"]))


def otimizar_ventilacao(proj, arr, cat):
    """Menor nº de ventiladores que atende a todos os limites térmicos críticos."""
    t = _par(cat)
    melhor = None
    for n in range(1, int(t["max_vent"]) + 1):
        r = estudo_termico(proj, arr, cat, n_vent=n)
        melhor = r
        if r["aprovado"]:
            break
    return melhor


def aplicar_termico(proj, arr, cat):
    """Roda o estudo térmico com os dois arranjos possíveis, escolhe o aprovado de menor ventilação e grava no projeto."""
    from .mecanica import projetar_arranjo
    from .dimensionamento import Verificacao
    opcoes = []
    for ordem in ("indutor_embaixo", "capacitores_embaixo"):
        a = arr if ordem == getattr(arr, "ordem", "indutor_embaixo") else projetar_arranjo(proj, cat, ordem=ordem)
        r = otimizar_ventilacao(proj, a, cat)
        tcap = next((c["t_componente_C"] for c in r["componentes"] if c["componente"].startswith("Capacitores")), 0)
        opcoes.append((not r["aprovado"], r["n_ventiladores"], a.caixa_preco, round(tcap / 5), ordem, a, r))
    # desempate: capacitor mais frio (vida útil) quando ventilação e caixa são iguais
    opcoes.sort(key=lambda x: x[:4])
    _, n, _, _, ordem, a, r = opcoes[0]
    a.n_ventiladores = n
    a.vazao_m3h = r["vazao_livre_m3h"]
    a.perda_total_w = r["perdas_total_W"]
    a.perdas_w = {p["componente"]: p["perdas_W"] for p in r["perdas"]}
    r["arranjo_escolhido"] = ordem
    r["comparacao_arranjos"] = [dict(arranjo=o[4], aprovado=not o[0], ventiladores=o[1], t_saida_C=o[6]["t_saida_C"],
                                     t_cap_C=next((c["t_componente_C"] for c in o[6]["componentes"] if c["componente"].startswith("Capacitores")), None))
                                for o in opcoes]
    proj.termico = r
    proj.verificacoes = [v for v in proj.verificacoes if not v.item.startswith("Térmico")] + \
        [Verificacao(v["item"], v["valor"], v["limite"], v["ok"], v["referencia"], v["critico"]) for v in r["verificacoes"]]
    proj.aprovado = all(v.ok for v in proj.verificacoes if v.critico)
    return a, r
