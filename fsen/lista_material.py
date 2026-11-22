"""Lista de material COMPLETA do painel, até parafuso, terminal e torque (REQ-PNL-021/022, REQ-GER-010) – v1.25.0.

Fonte única dos componentes: dados/componentes_db.yaml (por marca: ABB, SCHNEIDER, ELECTRIC = padrão Panatlântica 2024).
Projeto ABB → itens ABB; Schneider → Schneider; padrão Electric → os da Panatlântica; item que a marca não tem → equivalente
ELECTRIC, registrado na coluna "Origem". Valor não confirmado no catálogo sai como "CONFERIR" (nunca como certo).
Cálculos: barramento pela DIN 43671 com correção da temperatura interna; cabos pela NBR 5410 (banco.cabo_nbr5410);
torques de barramento pela DIN 43673; terminais de compressão DIN 46235.
"""
from __future__ import annotations

import math
import os

import yaml

from . import banco as B

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def db():
    return yaml.safe_load(open(os.path.join(RAIZ, "dados", "componentes_db.yaml"), encoding="utf-8"))


def _marca(ped):
    m = (getattr(ped, "marca", "") or "").lower()
    return "ABB" if "abb" in m else ("SCHNEIDER" if "schneider" in m else "ELECTRIC")


_MAP_FAB = {"chave_fusivel_nh00": "seccionadora_fusivel", "fusivel_nh00": "fusivel_gG", "disjuntor_geral": "disjuntor",
            "disjuntor_comando": "disjuntor_comando", "rele_falta_fase": "rele_falta_fase"}


def item(d, marca, chave, ped=None, **fmt):
    """Componente da marca. FONTE ÚNICA de código = dados/fabricantes.yaml (o mesmo do esquema elétrico); componentes_db.yaml
    só completa medidas/torque/bobina. Se a marca não tiver o item, o equivalente ELECTRIC. Devolve (registro, origem)."""
    if ped is not None:
        from . import fabricantes as FB
        mc = getattr(ped, "marca", "") or FB.PADRAO
        cod = None
        if chave == "disjuntor_geral":
            cod = FB.disjuntor_geral(mc, fmt.get("A", 800))
        elif chave == "capacitor_25kvar_525V":
            cp = FB._m(mc).get("capacitores") or {}
            kv, V = fmt.get("kvar"), fmt.get("V")
            cod = ((cp.get("codigos") or {}).get(V) or {}).get(kv) or (cp.get("codigo", "").format(kvar=kv, V=V) if cp.get("codigo") else None)
            if cod and cp.get("conferir"):
                cod += " (conferir código)"
        elif chave == "controlador":
            n = fmt.get("n", 12)
            ctl = FB._m(mc).get("controlador") or {}
            cod = ctl.get(6 if n <= 6 else 12)
        elif chave in _MAP_FAB:
            cod = FB.item(mc, _MAP_FAB[chave], **fmt)
        if cod:
            extra = (d["marcas"].get(marca) or {}).get(chave) or {}
            return dict(extra, codigo=cod, conferir=("conferir" in cod) or extra.get("conferir", False)), mc
    r = (d["marcas"].get(marca) or {}).get(chave)
    if r:
        return r, marca
    return (d["marcas"]["ELECTRIC"].get(chave) or {"codigo": f"{chave} (a definir)", "conferir": True}), "ELECTRIC (equivalente)"


def barramento(I, T_int, d):
    f = d["ferragens"]
    ft = {float(t): v for t, v in f["fator_temp_barra"].items() if str(t).replace(".", "").isdigit()}
    k = next((v for t, v in sorted(ft.items()) if T_int <= t), 0.74)
    for nome, i0 in sorted(((n, a) for n, a in f["barra_ampacidade_A"].items() if n != "fonte" and n != "conferir"), key=lambda x: x[1]):
        if i0 * k >= I:
            return nome, i0, k
    return "2x50x10", 1510, k


def _parafuso(furo_mm):
    return {6: "M6", 8: "M8", 10: "M10", 12: "M12"}.get(furo_mm, "M10")


def montar(ped, res, gab, prot, ext=None):
    """Lista [grupo, tag, descrição, código, qtd, unid, origem, status/conferir, cálculo/observação]."""
    d = db()
    mc = _marca(ped)
    n = len(res["estagios"])
    n_cap = res["estagios"][0]["cap"][0]
    pn = B.painel(ped, res)
    djg, trc = pn["disjuntor_geral"], pn["trafo_comando"]
    dim = (gab or pn["gabinete"])["dimensoes_mm"]
    W = dim["largura"]
    T_int = B.T_INTERNA_PROJETO_C
    tq = d["ferragens"]["torque_barramento_Nm"]
    L = []

    def add(g, tag, desc, cod, q, un, orig, st, obs=""):
        L.append([g, tag, desc, cod, q, un, orig, st, obs])

    def stt(r):
        return "CONFERIR catálogo" if r.get("conferir") else ("ATIVO" if r.get("status") == "ATIVO" else "verificar se ainda é vendido")

    # ------------------------------------------------ proteção geral
    r, o = item(d, mc, "disjuntor_geral", ped, A=djg["In"])
    add("1 Proteção geral", "-Q0", djg["texto"], r.get("codigo"), 1, "pç", o, stt(r),
        f"In ≥ 1,30·ΣI ({djg['It']:.0f} A) → {djg['In']} A; Icu ≥ 1,1·Icc ({djg['Icc_kA']:.1f} kA) → {djg['Icu_kA']} kA")
    add("1 Proteção geral", "-Q0", "Mecanismo de manopla rotativa externa com eixo prolongado, intertravamento de porta e "
        "dispositivo para cadeado (NR-10)", "acessório do -Q0 (mesma marca)", 1, "cj", o, "CONFERIR código do acessório", "NR-10 10.4.1/10.6.5")
    ce = B.cabos_entrada(ped, djg["In"])
    add("1 Proteção geral", "-X0", f"Cabos do cliente até o -Q0: {ce['texto']} – fornecimento do cliente; painel com flange de "
        f"entrada {'no teto' if str(getattr(ped, 'entrada_cabos', 'baixo')).startswith('c') else 'na base'} e prensa-cabos",
        "flange + prensa-cabos", 1, "cj", "ELECTRIC", "calculado", f"NBR 5410 a {ce['T']:g} °C: {ce.get('Iz_total')} A ≥ {djg['In']} A")
    add("1 Proteção geral", "-X0", f"Terminal de compressão {ce['secao']} mm² furo conforme borne do -Q0 (cabos do cliente)",
        f"terminal {ce['secao']} mm²", 3 * ce["paralelos"], "pç", "ELECTRIC", "calculado", "")
    # ------------------------------------------------ barramento geral único
    nb, i0, k = barramento(djg["In"], T_int, d)
    comp_m = (W - 120) / 1000
    esp = [int(x) for x in nb.replace("2x", "").split("x")]
    nbarras = 2 if nb.startswith("2x") else 1
    kg = 3 * nbarras * comp_m * esp[0] * esp[1] * 1e-6 * 8960
    add("2 Barramento", "-R2/-S2/-T2", f"Barramento geral ÚNICO Cu eletrolítico estanhado {nb} mm por fase (L1/L2/L3), identificado, com "
        f"isolação termocontrátil", d["marcas"]["ELECTRIC"]["barramento"]["codigo"], round(kg, 1), "kg", "ELECTRIC", "calculado",
        f"DIN 43671: {i0} A × {k} ({T_int:g} °C interno) = {i0 * k:.0f} A ≥ {djg['In']} A; {comp_m:.2f} m × 3 fases")
    n_iso = 3 * nbarras * (math.ceil(comp_m / 0.40) + 1)
    add("2 Barramento", "", "Isolador epóxi suporte de barramento (vão ≤ 400 mm – esforço de curto)", "isolador 40 × 40 M8" if esp[0] >= 40
        else "isolador 30 × 30 M6", n_iso, "pç", "ELECTRIC", "calculado", f"vão 400 mm, Icc {djg['Icc_kA']:.1f} kA")
    pf = "M10" if esp[0] >= 40 else "M8"
    n_deriv = 3 * n
    add("2 Barramento", "W n.1", f"Derivação barramento → entrada da chave NH: CABO flexível {prot['cabo_calc']['secao']} mm² (padrão Electric), "
        f"com terminal parafusado na barra e passa-cabo na placa", f"{prot['cabo_calc']['secao']} mm² classe 5", round(n_deriv * 0.9, 1), "m",
        "ELECTRIC", "calculado", f"{n} estágios × 3 fases × ~0,9 m (mesmo cabo W n.1 do esquema)")
    add("2 Barramento", "", f"Parafuso sextavado {pf} classe 8.8 zincado + arruela lisa + arruela de pressão + porca (derivações e emendas)",
        f"{pf}×35 8.8", 2 * n_deriv + 12, "cj", "ELECTRIC", "calculado", f"torque {tq[pf]} N·m (DIN 43673) – marcar com caneta de torque")
    add("2 Barramento", "", "Barreira de policarbonato transparente 4 mm do compartimento do barramento (IPXXB, forma 2b) + suportes",
        "policarbonato 4 mm", 1, "cj", "ELECTRIC", "calculado", f"{comp_m:.2f} × 0,25 m")
    add("2 Barramento", "", "Pino esférico para aterramento temporário (NR-10 10.4.6), Ø20 mm, fixado no barramento", "pino esférico Ø20",
        3, "pç", "ELECTRIC", "CONFERIR código", "1 por fase")
    # ------------------------------------------------ estágios
    for chave, tag, q, desc in (("chave_fusivel_nh00", "-Q1…-Q%d" % n, n, f"Chave seccionadora-fusível tripolar NH00 {prot['chave_A']} A"),
                                ("fusivel_nh00", "-F1…", 3 * n, f"Fusível NH00 gG {prot['fusivel_A']} A 500 V"),
                                ("contatora_capacitor", "-K1…-K%d" % n, n, f"Contatora do estágio ({prot['contator']})"),
                                ("capacitor_25kvar_525V", "-C1…-C%d" % n, n * n_cap, f"Capacitor {res['estagios'][0]['cap'][1]:g} kvar {res['estagios'][0]['cap'][2]:g} V")):
        r, o = item(d, mc, chave, ped, A=prot["chave_A"] if "chave" in chave else prot["fusivel_A"], tam="00",
                    kvar=res["estagios"][0]["cap"][1], V=res["estagios"][0]["cap"][2])
        if chave == "contatora_capacitor":
            r = dict(r, codigo=prot["contator"])                       # mesma contatora do esquema/proteção
        add("3 Estágios", tag, desc, r.get("codigo"), q, "pç", o, stt(r), f"torque terminais: {r.get('torque_Nm') or 'CONFERIR catálogo'}")
    _cr = " / ".join(dict.fromkeys(str(e.get("codigo", "")) for e in res["estagios"]))        # código do reator = o do esquema
    add("3 Estágios", "-L1…-L%d" % n, "Reator de dessintonia – projeto Electric (FEM) – fornecimento Electric (ver ET do reator)", _cr, n, "pç",
        "ELECTRIC", "projeto", "")
    add("3 Estágios", "-B1…-B%d" % n, "Termostato NF na bobina de cada reator (desliga o estágio) – fornecido com o reator", f"no reator {_cr}",
        n, "pç", "ELECTRIC", "projeto", "IEC 61921")
    cb, cc = prot["cabo_calc"], prot["cabo_cap_calc"]
    comp_est = 0.6 + 1.6 + 0.5                        # barra→chave (cordoalha à parte); chave→contatora; contatora→reator; folga
    add("4 Cabos de força", "", f"Cabo flexível 0,6/1 kV HEPR 90 °C {cb['secao']} mm² preto (fases do estágio: chave → contatora → reator)",
        f"{cb['secao']} mm² classe 5", round(3 * n * comp_est, 1), "m", "ELECTRIC", "calculado",
        f"NBR 5410: I0 {cb['I0']} A × FCT {cb['FCT']} × FCA {cb['FCA']} = {cb['Iz']:.0f} A ≥ {cb['I']:.0f} A")
    add("4 Cabos de força", "", f"Cabo flexível 0,6/1 kV HEPR 90 °C {cc['secao']} mm² preto (reator → cada capacitor)",
        f"{cc['secao']} mm² classe 5", round(3 * n * n_cap * 1.2, 1), "m", "ELECTRIC", "calculado",
        f"NBR 5410: Iz {cc['Iz']:.0f} A ≥ {cc['I']:.0f} A")
    n_term_e = 3 * n * 4
    add("4 Cabos de força", "", f"Terminal de compressão tubular Cu estanhado {cb['secao']} mm² (DIN 46235), furo conforme borne",
        f"terminal {cb['secao']} mm²", n_term_e, "pç", "ELECTRIC", "calculado", "2 pontas × 2 trechos × 3 fases × estágio; prensagem hexagonal")
    add("4 Cabos de força", "", f"Terminal de compressão/ponteira {cc['secao']} mm² no borne de cada capacitor", f"terminal {cc['secao']} mm²",
        3 * n * n_cap, "pç", "ELECTRIC", "calculado", "1 cabo por fase de CADA capacitor (REQ-PNL-027)")
    add("4 Cabos de força", "", f"Terminal de compressão ÚNICO para os {n_cap} cabos de {cc['secao']} mm² por fase no borne de saída do reator "
        f"(seção equivalente {n_cap} × {cc['secao']} mm²)", f"terminal {n_cap}×{cc['secao']} mm²", 3 * n, "pç", "ELECTRIC", "CONFERIR modelo",
        "cabos dos capacitores e do reator afastados entre si e dos terminais (sem encostar)")
    add("4 Cabos de força", "", "Luva termocontrátil de identificação de fase (L1 marrom / L2 preto / L3 cinza) e anilhas DE/PARA",
        "termocontrátil + anilhas", 1, "cj", "ELECTRIC", "calculado", "conforme Lista DE/PARA")
    add("4 Cabos de força", "", "Prensa-cabo / passa-cabo de borracha na placa (passagem frente → reatores)", "passa-cabo Ø50", 2 * n,
        "pç", "ELECTRIC", "calculado", "2 por estágio (ida ao reator e retorno aos capacitores)")
    # ------------------------------------------------ comando
    for chave, tag, desc in (("controlador", "-A1", "Controlador de fator de potência"), ("rele_falta_fase", "-K0", "Relé de falta/sequência de fase")):
        r, o = item(d, mc, chave, ped, n=n)
        add("5 Comando", tag, desc, r.get("codigo"), 1, "pç", o, stt(r), "")
    add("5 Comando", "-T1", f"Transformador de comando {ped.tensao_v:g}/220 V {trc['Sn']} VA", f"Rasatronic (ou Wise) – transformador isolador monofásico IP-00 {ped.tensao_v:g}/220 V {trc['Sn']} VA (sob encomenda)",
        1, "pç", "Rasatronic / Wise", "calculado – medidas pelo desenho do fornecedor", f"carga: retenção {trc['S_ret']} VA; pior manobra {trc['S_inst']} VA")
    from . import fabricantes as _FBd
    _mk = getattr(ped, "marca", "") or _FBd.PADRAO
    _real = any(x in _mk.lower() for x in ("abb", "schneider"))
    _st = "catálogo" if _real else "CONFERIR código"
    add("5 Comando", "-F02", trc["dj_pri"], _FBd.dj_comando(_mk, 2, "D", trc["dj_pri_A"]), 1, "pç", _mk, _st, "proteção do primário")
    add("5 Comando", "-F03", trc["dj_sec"], _FBd.dj_comando(_mk, 2, "C", trc["dj_sec_A"]), 1, "pç", _mk, _st, "proteção do secundário")
    add("5 Comando", "-F01", "Disjuntor tripolar 2 A curva C (alimentação do relé de falta de fase / medição)", _FBd.dj_comando(_mk, 3, "C", 2),
        1, "pç", _mk, _st, "")
    add("5 Comando", "-X1", "Bornes de passagem 2,5/4 mm² + bornes PE + tampas, separadores e marcadores", "bornes trilho DIN",
        40, "pç", "ELECTRIC", "calculado", "comando e sinais")
    add("5 Comando", "", "Cabo flexível 750 V 1,5 mm² (comando, cores conforme NBR 5410) + 2,5 mm² (alimentação do comando)",
        "1,5/2,5 mm²", 60 + 8 * n, "m", "ELECTRIC", "estimado pelo esquema", "conferir no DE/PARA")
    add("5 Comando", "", "Terminal tubular (ponteira) isolado 1,5/2,5 mm²", "ponteira", 300, "pç", "ELECTRIC", "estimado", "")
    nm = pn["gabinete"]["ventilacao"]["n_exaustores"]
    for t, desc, q in (("-S0", "Botoeira de emergência Ø22 com trava, 1NF+1NA", 1), ("-S1", "Chave seletora 2 posições Ø22", 1),
                       ("-H0/-H1…-H%d" % n, "Sinaleiro LED Ø22 220 V (energizado + estágio ligado)", n + 1),
                       ("-B0", "Termostato de painel NA (liga os exaustores a 35 °C)", 1),
                       ("-BT2", "Termostato de painel NF (55 °C desliga o banco)", 1),
                       ("-M1…-M%d" % nm, "Ventilador com filtro 230 V IP54 (porta traseira) – vazão/consumo do catálogo", nm)):
        from . import fabricantes as _FB
        _m_ = _FB._m(getattr(ped, "marca", "") or _FB.PADRAO)
        _bt, _tm = _m_.get("botoes") or {}, _m_.get("termostato") or {}
        _cod = {"-S0": _bt.get("emergencia"), "-S1": _bt.get("seletor"), "-H0": _bt.get("sinaleiro"),
                "-B0": _tm.get("na"), "-BT2": _tm.get("nf"),
                "-M1": __import__("fsen.painel_gabinete", fromlist=["x"]).EXAUSTOR_REAL["codigo"]
                }.get(t.split("/")[0].split("…")[0])
        add("5 Comando", t, desc, _cod or "linha da marca do projeto", q, "pç", mc,
            ("CONFERIR código" if (not _cod or (_bt.get("conferir") if t[:2] in ("-S", "-H") else (False if t.startswith("-M") else _tm.get("conferir")))) else "catálogo"), "")
    from . import painel_gabinete as _PGl
    add("5 Comando", "", "Grelha de entrada com filtro (porta, embaixo) – uma por ventilador", _PGl.EXAUSTOR_REAL["grelha"], nm, "pç", "Schneider",
        "catálogo", "IEC 60890 – entrada de ar")
    # ------------------------------------------------ PE e segurança
    s_pe = 16 if cb["secao"] <= 16 else (cb["secao"] / 2 if cb["secao"] > 35 else 16)
    add("6 Aterramento e segurança", "-PE2", "Barra PE Cu 30 × 5 mm sobre isoladores, por coluna", "barra 30 × 5", len(pn["gabinete"]["colunas"]),
        "pç", "ELECTRIC", "calculado", "NR-10 10.4.4")
    add("6 Aterramento e segurança", "", f"Cordoalha/cabo verde-amarelo {s_pe:g} mm² para portas, placa e estrutura + terminais",
        f"{s_pe:g} mm² VA", 4 * len(pn["gabinete"]["colunas"]) + 2, "pç", "ELECTRIC", "calculado", "NBR 5410 tab. 58")
    add("6 Aterramento e segurança", "", "Indicador de presença de tensão na porta (NR-10 10.13)", "indicador de tensão Ø22", 1, "pç", mc,
        "CONFERIR código", "")
    add("6 Aterramento e segurança", "", "Placas NR-10 (tensão, choque, arco, acesso restrito) + etiqueta de energia incidente", "placas",
        1, "cj", "ELECTRIC", "calculado", "Etiqueta_Arco_Eletrico do projeto")
    # ------------------------------------------------ infraestrutura
    n_col = len(pn["gabinete"]["colunas"])
    add("7 Infraestrutura", "", "Canaleta recortada 60 × 60 mm cinza com tampa", "canaleta 60×60", round(n_col * (4 * 0.9 + 2 * 1.5), 1),
        "m", "ELECTRIC", "calculado", "4 horizontais + 2 verticais por coluna")
    add("7 Infraestrutura", "", "Trilho DIN 35 mm perfurado", "trilho DIN 35", round(n_col * 1.0, 1), "m", "ELECTRIC", "calculado", "")
    add("7 Infraestrutura", "", "Prateleira/suporte dos capacitores e dos reatores (cantoneira perfurada pintada preta)", "suportes", 1, "cj",
        "ELECTRIC", "calculado", "conforme Painel 3D")
    add("7 Infraestrutura", "", "Parafusos M6/M8 autoatarraxantes/porcas-gaiola para fixação de componentes na placa + abraçadeiras de nylon",
        "fixação", 1, "cj", "ELECTRIC", "estimado", "")
    add("7 Infraestrutura", "", "Plaquetas de identificação acrílico preto letra branca (tags do esquema)", "plaquetas", 3 * n + 15, "pç",
        "ELECTRIC", "calculado", "Lista de plaquetas do projeto")
    return L


def planilha(L, arq, ped, cod, versao=""):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    wb = Workbook()
    ws = wb.active
    ws.title = "Lista completa"
    ws.append([f"LISTA DE MATERIAL COMPLETA DO PAINEL – {cod} – {getattr(ped, 'cliente', '')} – marca: {_marca(ped)} – {versao}"])
    ws.append(["Grupo", "Tag", "Descrição", "Código", "Qtd", "Unid", "Origem (marca)", "Status", "Cálculo / observação"])
    for r in L:
        ws.append(r)
    for c in ws[2]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="C8641E")
    for i, w in enumerate([22, 12, 70, 40, 8, 6, 20, 24, 60]):
        ws.column_dimensions[chr(65 + i)].width = w
    for row in ws.iter_rows(min_row=3):
        for c in row:
            c.alignment = Alignment(wrap_text=True, vertical="top")
        st = str(row[7].value or "")
        row[7].fill = PatternFill("solid", fgColor=("FFF2CC" if "CONFERIR" in st or "verificar" in st else "E2EFDA"))
    ws.freeze_panes = "C3"
    wb.save(arq)
    return arq
