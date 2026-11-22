"""Componentes por fabricante (ABB, Schneider, Siemens, WEG, Epcos/TDK ou padrão Electric) – v1.20.0.
O reator é sempre Electric. Dados em dados/fabricantes.yaml (fonte e marcação 'conferir' por item)."""
from __future__ import annotations

import os

import yaml

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CACHE = {}
PADRAO = "Padrão Electric"


def catalogo():
    if "c" not in _CACHE:
        _CACHE["c"] = yaml.safe_load(open(os.path.join(RAIZ, "dados", "fabricantes.yaml"), encoding="utf-8"))
    return _CACHE["c"]


def marcas():
    return list(catalogo())


def _m(marca):
    return catalogo().get(marca or PADRAO) or catalogo()[PADRAO]


def unidades_cap(marca, Vcap):
    """(V nominal efetivo, [kvar 60 Hz]) da marca para a tensão pedida (ou a próxima maior disponível); None = padrão."""
    c = (_m(marca).get("capacitores") or {})
    u = c.get("unidades")
    if not u:
        return None
    vs = sorted(int(v) for v in u)
    v = next((x for x in vs if x >= Vcap), vs[-1])
    return v, [float(x) for x in u[v] if True]


def codigo_cap(marca, kvar, V):
    c = (_m(marca).get("capacitores") or {})
    cods = (c.get("codigos") or {}).get(int(V)) or {}
    k = int(kvar) if float(kvar).is_integer() else kvar
    if k in cods:
        return f"{marca} {c.get('serie', '')} {cods[k]} ({kvar:g} kvar {V:g} V 60 Hz)".strip(), False
    if not c:
        return None, False
    return f"{marca} {c.get('serie', '')} – " + c.get("codigo", "").format(kvar=f"{kvar:g}", V=f"{V:g}"), bool(c.get("conferir", True))


def contatora(marca, I_req, kvar_estagio, V, prefer=None):
    """Escolhe a contatora: comum (AC-1 ≥ I_req) ou para capacitor (kvar). Devolve dict(nome, tipo, ie, pico)."""
    m = _m(marca)
    if marca in (None, "", PADRAO):
        return None
    tipo = prefer or m.get("contatora_preferida", "comum")
    cts = m.get("contatoras") or {}
    if tipo == "comum" and cts.get("comum"):
        for nome, ie, pk in cts["comum"]:
            if ie >= I_req:
                return dict(nome=nome, tipo="comum (AC-3/AC-1)", ie=float(ie), pico=float(pk))
        nome, ie, pk = cts["comum"][-1]
        return dict(nome=nome, tipo="comum (AC-3/AC-1)", ie=float(ie), pico=float(pk))
    kv = kvar_estagio * (400.0 / V) ** 2 if V else kvar_estagio      # tabelas a 400 V
    for nome, kmax in cts.get("capacitor") or []:
        if kmax >= kv:
            return dict(nome=nome, tipo="para capacitor (AC-6b)", ie=float(kmax * 1e3 / (1.732 * 400) * 1.3), pico=None)
    return None


def item(marca, chave, **fmt):
    """Texto de um componente da marca (seccionadora_fusivel, fusivel_gG, disjuntor, controlador…)."""
    m = _m(marca)
    x = m.get(chave)
    if x is None:
        return None
    if isinstance(x, dict) and "codigo" in x:
        try:
            return x["codigo"].format(**fmt) + (" (conferir código)" if x.get("conferir") else "")
        except (KeyError, IndexError):
            return x["codigo"]
    return x


def _nh(A):
    return "00" if A <= 160 else "1" if A <= 250 else "2" if A <= 400 else "3"


def aplicar_projeto(P, ped, res):
    """Troca fabricante/código dos dispositivos do esquema (lista de material) pela marca escolhida. Reator continua Electric."""
    marca = getattr(ped, "marca", "") or PADRAO
    if marca == PADRAO:
        return
    from . import banco as B
    D = P.disp
    n = len(res["estagios"])

    def put(tag, cod, descr_extra=""):
        if tag in D and cod:
            D[tag]["fab"] = marca
            D[tag]["cod"] = cod
            if descr_extra:
                D[tag]["descr"] = D[tag]["descr"] + descr_extra
    pn = B.painel(ped, res)
    put("-Q0", item(marca, "seccionadora_fusivel", A=pn["geral_A"]) or "", f" – fusíveis {item(marca, 'fusivel_gG', A=pn['geral_A'], tam=_nh(pn['geral_A'])) or ''}")
    for t in ("-F01", "-F02", "-F03"):
        put(t, item(marca, "disjuntor_comando"))
    put("-K0", item(marca, "rele_falta_fase"))
    bt = _m(marca).get("botoes") or {}
    put("-S0", bt.get("emergencia"))
    put("-S1", bt.get("seletor"))
    put("-H0", bt.get("sinaleiro"))
    ctl = _m(marca).get("controlador") or {}
    passos = 6 if n <= 6 else 12
    cod_ctl = ctl.get(passos) or ctl.get(12) or ctl.get(6)
    if cod_ctl:
        put("-A1", cod_ctl + (" (conferir código)" if ctl.get("conferir") else ""))
        if "-A1" in D:
            D["-A1"]["descr"] = f"Controlador automático de fator de potência {passos} estágios – {cod_ctl}"
    tm = _m(marca).get("termostato") or {}
    put("-B0", tm.get("na"))
    put("-BT2", tm.get("nf"))
    vent = _m(marca).get("ventilador")
    for k in range(1, 9):
        put(f"-M{k}", item(marca, "ventilador", m3h="≥ 230") if vent else None)
    for i, e in enumerate(res["estagios"], start=1):
        pr = B.protecao_estagio(ped, e)
        put(f"-Q{i}", item(marca, "seccionadora_fusivel", A=pr["chave_A"]),
            f" – fusíveis {item(marca, 'fusivel_gG', A=pr['fusivel_A'], tam=_nh(pr['fusivel_A'])) or ''}")
        if f"-K{i}" in D:
            D[f"-K{i}"]["fab"] = marca
            D[f"-K{i}"]["cod"] = pr["contator"]
            D[f"-K{i}"]["descr"] = (f"Contatora {pr.get('contator_tipo', '')} {pr['contator']} – Ie AC-1 {pr['contator_In']:.0f} A"
                                    + (f", pico de fechamento ≤ {pr['contator_pico']:.0f} A" if pr.get("contator_pico") else "")
                                    + ", bobina 220 V (verificada no estudo de transitórios)")
        cod_c, conf = codigo_cap(marca, e["cap"][1], e["cap"][2])
        if cod_c:
            put(f"-C{i}", cod_c + (" (conferir código)" if conf else ""))
        put(f"-H{i}", bt.get("sinaleiro"))
