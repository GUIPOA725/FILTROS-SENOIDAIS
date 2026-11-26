"""Motor e cabo pelos manuais/catálogos do fabricante – v1.34.0 (REQ-INV-011).

Engenheiro (26/11/2026): "e se conseguir TB o manual do motor, isso ajuda muito, e o manual do cabo, imagina ficaria muito
completo com essas informações técnicas". Mesma regra do inversor (REQ-INV-010, fsen/inversor_manual.py): todo dado com
documento, revisão, página e link (dados/manuais_motor_cabo.yaml).

MOTOR: limites de isolamento do fabricante (pico, dv/dt, rise time) para a tensão nominal × valores GARANTIDOS pelo filtro;
       proteção de mancal pela carcaça.
CABO:  do catálogo saem diâmetro do condutor, Rcc 20 °C e dimensões; daí se CALCULA (memória no relatório):
         R ca 90 °C = Rcc20·[1 + 0,00393·(90 − 20)]·(1 + ys)    (IEC 60287-1-1, efeito pelicular ys)
         L (trifólio encostado) = 0,05 + 0,2·ln(2·De/dc) mH/km  (De = diâmetro externo, dc = diâmetro do condutor)
         C condutor-blindagem (cabo blindado) = 55,63·εr / ln(Di/dc) nF/km
       e compara com os parâmetros usados na simulação (dados/catalogo.yaml → cabos_parametros). Com fabricante e modelo
       informados no pedido, R e L do fabricante passam a valer na simulação (dimensionamento.parametros_sistema).
Sem fabricante/modelo no pedido: usa a referência cadastrada e marca ATENÇÃO.
"""
from __future__ import annotations

import math
import os
import re

import yaml

_ARQ = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dados", "manuais_motor_cabo.yaml")
_C = None


def _base():
    global _C
    if _C is None:
        try:
            with open(_ARQ, encoding="utf-8") as f:
                _C = yaml.safe_load(f) or {}
        except OSError:
            _C = {}
    return _C


def _g(ped, k, d=None):
    return (ped.get(k, d) if isinstance(ped, dict) else getattr(ped, k, d))


# ----------------------------------------------------------------------------------------------------------------- motor
def motor(ped):
    b = _base()
    txt = f"{_g(ped, 'motor_fabricante', '') or ''} {_g(ped, 'motor_modelo', '') or ''}".upper()
    ref = False
    nome = next((n for n, m in (b.get("motores") or {}).items() if txt.strip() and re.search(m.get("regex", "$^"), txt)), None)
    if not nome:
        nome, ref = b.get("referencia_motor"), True
    m = (b.get("motores") or {}).get(nome)
    if not m:
        return None
    un = float(_g(ped, "tensao_v", 440) or 440)
    lim = next((x for x in m.get("isolamento", []) if un < x["un_ate"]), (m.get("isolamento") or [{}])[-1])
    carc = re.search(r"\d{2,4}", str(_g(ped, "motor_carcaca", "") or ""))
    carc = int(carc.group(0)) if carc else None
    # v1.34.1: modelo de catálogo pela potência e polos (acha a carcaça e confere corrente/FP da placa do cliente)
    kw = float(_g(ped, "motor_kw", 0) or 0) or float(_g(ped, "motor_cv", 0) or 0) * 0.7355
    pol = int(_g(ped, "motor_polos", 4) or 4)
    mod = next((x for x in (m.get("modelos") or []) if kw and abs(x["kw"] - kw) <= 0.03 * x["kw"] and int(x["polos"]) == pol), None)
    carc_cat = False
    if carc is None and mod and not ref:
        carc = int(re.search(r"\d{2,4}", mod["carcaca"]).group(0))
        carc_cat = True
    return dict(nome=nome, referencia=ref, fabricante=m.get("fabricante"), un=un, vpk_max=lim.get("vpk"), dvdt_max=lim.get("dvdt"),
                rise_min_us=m.get("rise_time_min_us"), mancal=m.get("mancal"), carcaca=carc,
                proteger_mancal=(carc is not None and carc >= m.get("carcaca_proteger_desde", 315)),
                modelo_catalogo=mod, carcaca_do_catalogo=carc_cat, catalogo_eletrico=m.get("catalogo_eletrico"),
                fontes=m.get("fontes", []), status=m.get("status"), consultado_em=m.get("consultado_em"))


# ------------------------------------------------------------------------------------------------------------------ cabo
def _ys(r_ohm_km, f=60.0, ks=1.0):
    r = r_ohm_km / 1000.0
    xs2 = 8 * math.pi * f / r * 1e-7 * ks
    return xs2 ** 2 / (192 + 0.8 * xs2 ** 2)


def cabo(ped, secao):
    b = _base()
    txt = f"{_g(ped, 'cabo_fabricante', '') or ''} {_g(ped, 'cabo_modelo', '') or ''} {_g(ped, 'cabo_tipo', '') or ''}".upper()
    blind = bool(_g(ped, "cabo_blindado", False))
    nome = next((n for n, c in (b.get("cabos") or {}).items()
                 if (_g(ped, "cabo_fabricante", "") or _g(ped, "cabo_modelo", "")) and re.search(c.get("regex", "$^"), txt)), None)
    ref = nome is None
    if ref:
        nome = b.get("referencia_cabo_blindado" if blind else "referencia_cabo_nao_blindado")
    c = (b.get("cabos") or {}).get(nome)
    if not c or not c.get("secoes"):
        return None
    secs = {float(k): v for k, v in c["secoes"].items()}
    s = min(secs, key=lambda x: abs(x - float(secao or 0)))
    dc, rcc, esp, di, de = secs[s]
    r90 = rcc * (1 + 0.00393 * 70)
    r90 *= 1 + _ys(r90)
    L = 0.05 + 0.2 * math.log(2 * de / dc)
    C = (55.63 * float(c.get("epsilon_r", 3.0)) / math.log(di / dc)) if (c.get("blindado") and di and di > dc) else None
    return dict(nome=nome, referencia=ref, fabricante=c.get("fabricante"), blindado=c.get("blindado"), secao=s,
                secao_pedida=float(secao or 0), dc=dc, rcc20=rcc, de=de, di=di, r90=r90, L_mH_km=L, C_nF_km=C,
                fonte=c.get("fonte", {}), status=c.get("status"), consultado_em=c.get("consultado_em"), dc_estimado=bool(c.get("dc_estimado")))


def comparar_cabo(cb, cat):
    tab = {int(k): v for k, v in (cat or {}).get("cabos_parametros", {}).items()}
    if not cb or not tab:
        return None
    k = min(tab, key=lambda x: abs(x - cb["secao"]))
    R, L, Cpg, Cpp = tab[k]
    return dict(secao_cat=k, R_cat=R, L_cat=L, Cpg_cat=Cpg, dR=100 * (cb["r90"] - R) / R, dL=100 * (cb["L_mH_km"] - L) / L)


# ------------------------------------------------------------------------------------------------------------- relatório
def gerar(ped, proj, cat, pasta, cod, garantias=None, log=print):
    os.makedirs(pasta, exist_ok=True)
    mo = motor(ped)
    sec = ((getattr(proj, "sistema", None) or {}).get("cabo_secao_mm2") or _g(ped, "cabo_secao_mm2", 0) or 0)
    cb = cabo(ped, sec)
    cmp_ = comparar_cabo(cb, cat)
    g = garantias or {}
    linhas = []            # (item, valor, limite/fonte, check)
    L = [f"# Motor e cabo – dados dos manuais/catálogos do fabricante ({cod})", ""]
    if mo:
        vpk, dvdt = g.get("vpk"), g.get("dvdt")
        L += ["## Motor", f"- Pedido: {_g(ped, 'motor_fabricante', '') or 'fabricante NÃO informado'} {_g(ped, 'motor_modelo', '') or ''} – "
              f"{_g(ped, 'motor_cv', 0) or '-'} cv, {_g(ped, 'motor_corrente_a', 0) or '-'} A, carcaça {mo['carcaca'] or 'NÃO informada'}",
              f"- Base usada: **{mo['nome']}**" + (" (REFERÊNCIA – confirmar fabricante e modelo com o cliente)" if mo["referencia"] else ""),
              f"- Limites de isolamento do fabricante para Un {mo['un']:g} V: pico ≤ {mo['vpk_max']} V, dV/dt ≤ {mo['dvdt_max']} V/µs, "
              f"rise time ≥ {mo['rise_min_us']} µs"]
        if vpk:
            ok = vpk <= mo["vpk_max"]
            L.append(f"- Pico GARANTIDO pelo filtro {vpk:.0f} V × {mo['vpk_max']} V → {'ATENDE' if ok else 'NÃO ATENDE'} "
                     f"({100 * vpk / mo['vpk_max']:.0f} %)")
            linhas.append(("Motor – pico garantido × limite do fabricante", f"{vpk:.0f} V", f"≤ {mo['vpk_max']} V", "OK" if ok else "REPROVADO"))
        if dvdt:
            ok = dvdt <= mo["dvdt_max"]
            L.append(f"- dV/dt GARANTIDO {dvdt:.0f} V/µs × {mo['dvdt_max']} V/µs → {'ATENDE' if ok else 'NÃO ATENDE'}")
            linhas.append(("Motor – dV/dt garantido × limite do fabricante", f"{dvdt:.0f} V/µs", f"≤ {mo['dvdt_max']} V/µs", "OK" if ok else "REPROVADO"))
        mc = mo.get("modelo_catalogo")
        if mc:
            ce = mo.get("catalogo_eletrico") or {}
            i_cli, fp_cli = float(_g(ped, "motor_corrente_a", 0) or 0), float(_g(ped, "motor_fp", 0) or 0)
            L.append(f"- Catálogo {ce.get('codigo', '')} ({ce.get('paginas', '')}): {mc['linha']} {mc['kw']:g} kW {mc['polos']}P → carcaça "
                     f"{mc['carcaca']}, In {mc['in_440']:g} A @ 440 V, FP {mc['fp']}, rendimento {mc['rend']} % – link {ce.get('link', '')}")
            if i_cli:
                ok_i = abs(i_cli - mc["in_440"]) <= 0.03 * mc["in_440"]
                linhas.append(("Motor – corrente do cliente × catálogo", f"{i_cli:g} A", f"{mc['in_440']:g} A ({mc['linha']})", "OK" if ok_i else "ATENÇÃO"))
            if fp_cli:
                ok_f = abs(fp_cli - mc["fp"]) <= 0.02
                linhas.append(("Motor – FP do cliente × catálogo (100 % de carga)", f"{fp_cli:g}", f"{mc['fp']}", "OK" if ok_f else "ATENÇÃO"))
            if mo.get("carcaca_do_catalogo"):
                L.append(f"- Carcaça não veio no pedido: adotada {mc['carcaca']} pelo catálogo (confirmar na placa).")
        L.append(f"- Mancais: {mo['mancal']}" + (" → esta carcaça PEDE proteção de mancal." if mo["proteger_mancal"] else
                                                (" → carcaça não informada: confirmar." if mo["carcaca"] is None else "")))
        linhas.append(("Motor – proteção de mancal pela carcaça", str(mo["carcaca"] or "não informada"), mo["mancal"][:60],
                       "ATENÇÃO" if (mo["proteger_mancal"] or mo["carcaca"] is None) else "OK"))
        linhas.append(("Motor – fabricante/modelo", f"{_g(ped, 'motor_fabricante', '') or '-'} {_g(ped, 'motor_modelo', '') or ''}",
                       mo["nome"], "ATENÇÃO" if mo["referencia"] else "OK"))
        L += ["", "### Fontes do motor"] + [f"- **{f['titulo']}** – {f['codigo']} – {f['revisao']} – {f['paginas']}\n  - Link: {f['link']}\n  - Retirado: {f['retirado']}"
                                             for f in mo["fontes"]]
    if cb:
        f = cb["fonte"]
        L += ["", "## Cabo inversor/filtro → motor",
              f"- Pedido: {_g(ped, 'cabo_fabricante', '') or 'fabricante NÃO informado'} {_g(ped, 'cabo_modelo', '') or ''} – "
              f"{'blindado' if _g(ped, 'cabo_blindado', False) else 'não blindado'}, {cb['secao_pedida']:g} mm², {_g(ped, 'cabo_m', 0) or '-'} m",
              f"- Base usada: **{cb['nome']} {cb['secao']:g} mm²**" + (" (REFERÊNCIA – confirmar fabricante e modelo com o cliente)" if cb["referencia"] else ""),
              f"- Catálogo: condutor {cb['dc']} mm{' (estimado 1,13·√S – não consta no catálogo)' if cb.get('dc_estimado') else ''}, Rcc 20 °C {cb['rcc20']} Ω/km, diâmetro externo {cb['de']} mm",
              f"- Calculado: R ca 90 °C = {cb['r90']:.4f} Ω/km (IEC 60287-1-1); L trifólio encostado = {cb['L_mH_km']:.3f} mH/km"
              + (f"; C condutor-blindagem = {cb['C_nF_km']:.0f} nF/km (εr HEPR 3,0)" if cb["C_nF_km"] else "; C fase-terra depende da instalação (não blindado)")]
        if cmp_:
            L.append(f"- Simulação usa (catalogo.yaml, {cmp_['secao_cat']} mm²): R {cmp_['R_cat']} Ω/km ({cmp_['dR']:+.0f} %), "
                     f"L {cmp_['L_cat']} mH/km ({cmp_['dL']:+.0f} %)" + (" – com fabricante/modelo no pedido, R e L do fabricante passam a valer." ))
            ok = abs(cmp_["dR"]) <= 15 and abs(cmp_["dL"]) <= 25
            linhas.append(("Cabo – R e L da simulação × catálogo do fabricante", f"R {cmp_['dR']:+.0f} %, L {cmp_['dL']:+.0f} %",
                           "R ±15 %, L ±25 %", "OK" if ok else "ATENÇÃO"))
        _gen = cb["referencia"] and not cb.get("blindado")
        linhas.append(("Cabo – fabricante/modelo", f"{_g(ped, 'cabo_fabricante', '') or '-'} {_g(ped, 'cabo_modelo', '') or ''}",
                       (f"genérico sem blindagem – padrão do engenheiro (REQ-SEN-029); referência {cb['nome']}" if _gen else cb["nome"]),
                       "ATENÇÃO" if (cb["referencia"] and not _gen) else "OK"))
        L += ["", "### Fonte do cabo", f"- **{f.get('titulo')}** – {f.get('codigo')} – {f.get('revisao')} – {f.get('paginas')}",
              f"  - Link: {f.get('link')}", f"  - Retirado: {f.get('retirado')}"]
    L += ["", "## Resumo (Check)", "| Item | Valor | Limite / base | Check |", "|---|---|---|---|"] + [f"| {a} | {b} | {c} | {d} |" for a, b, c, d in linhas]
    arq = os.path.join(pasta, f"Motor_Cabo_Manual_{cod}.md")
    with open(arq, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")
    try:
        from openpyxl import Workbook
        wb = Workbook()
        ws = wb.active
        ws.title = "Motor_Cabo"
        ws.append(["Item", "Valor", "Limite / base", "Check", "Fonte"])
        fm = (mo["fontes"][0]["codigo"] + " – " + mo["fontes"][0]["link"]) if mo and mo.get("fontes") else ""
        fc = (cb["fonte"].get("codigo", "") + " – " + cb["fonte"].get("link", "")) if cb else ""
        for a, b, c, d in linhas:
            ws.append([a, b, c, d, fm if a.startswith("Motor") else fc])
        for col, w in zip("ABCDE", (48, 28, 40, 12, 90)):
            ws.column_dimensions[col].width = w
        wb.save(os.path.join(pasta, f"Motor_Cabo_Manual_{cod}.xlsx"))
    except Exception as e:
        log(f"   Motor/cabo: planilha não gerada ({e})")
    log(f"   Motor e cabo – manuais do fabricante: {os.path.basename(arq)}")
    return dict(motor=mo, cabo=cb, comparacao=cmp_, linhas=linhas, arquivo=arq)
