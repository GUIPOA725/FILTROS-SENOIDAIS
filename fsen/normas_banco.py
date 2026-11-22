"""Folha de dados (valores garantidos) e verificação de projeto IEC 61439-1/2 + conformidade IEC 61921 – v1.23.0.

Banco dessintonizado e filtro sintonizado. Objetivo: entregar pelo menos o que ABB (Hitachi Energy APCQ) e Schneider
(VarSet) declaram – "type tested IEC 61439-1/2 e IEC 61921", IP31/IP54, IK10, IPxxB com porta aberta, proteção térmica,
Modbus – e, além disso, a verificação calculada deste projeto, item a item, com coluna de CHECK.

Verificação de projeto (IEC 61439-1 cl. 10) – o que dá para provar por CÁLCULO/REGRA de projeto é calculado aqui:
  10.4  distâncias de isolação e de escoamento (Tabelas 1 e 2 – Uimp 6 kV, grau de poluição 3, grupo IIIa)
  10.10 elevação de temperatura (método de cálculo IEC 60890 – perdas × ventilação; limites dos componentes)
  10.11 suportabilidade a curto-circuito (Icc na barra pela rede+trafo × Icw/Icc do painel, fusíveis e coordenação)
O que só se prova com ENSAIO/DECLARAÇÃO da montadora (IP, IK, dielétrico, rotina) sai como ATENÇÃO "exigido na ET e
na inspeção de recebimento" – nunca como aprovado sem prova.
"""
from __future__ import annotations

import math
import os

from . import banco as B
from . import checagem as CK

ICW_PADRAO = (25, 36, 50, 65, 80, 100)            # kA – valores usuais de Icw/Ipk de quadros BT
FOLGA_ISOLACAO_MM = 30                            # projeto Electric (painel_gabinete.folgas_mm)


def _icc_barra_ka(ped):
    """Icc trifásica na barra BT (trafo + rede MT), kA."""
    s = ped.trafo_kva * 1e3
    z_tr = ped.trafo_z_pct / 100
    z_rede = (ped.trafo_kva / 1e3) / max(ped.scc_rede_mva, 1e-6)
    i_n = s / (math.sqrt(3) * ped.tensao_v)
    return i_n / (z_tr + z_rede) / 1e3


def _linha(clausula, item, valor, limite, ck, metodo):
    return [clausula, item, valor, limite, CK.texto(ck), metodo]


def verificacao(ped, res, gab, prot, trans=None):
    """Lista de linhas [cláusula, verificação, valor do projeto, requisito, check, método/evidência]."""
    L = []
    Ue = ped.tensao_v
    Ui = 500 if Ue <= 500 else 800
    # ---------------------------------------------------------------- 10.4 isolação
    dist_ar = 5.5                                   # Uimp 6 kV – IEC 61439-1 Tabela 1
    escoamento = {500: 8.0, 800: 12.5}[Ui]         # Ui, poluição 3, grupo IIIa – Tabela 2
    u = CK.utilizacao(FOLGA_ISOLACAO_MM, dist_ar, "min")
    L.append(_linha("61439-1 §10.4", "Distância de isolação no ar entre fases / fase-massa (Uimp 6 kV)",
                    f"{FOLGA_ISOLACAO_MM} mm (projeto)", f"≥ {dist_ar} mm", CK.check(True, u), "Tabela 1 + layout"))
    u = CK.utilizacao(FOLGA_ISOLACAO_MM, escoamento, "min")
    L.append(_linha("61439-1 §10.4", f"Distância de escoamento (Ui {Ui} V, poluição 3, grupo IIIa)",
                    f"{FOLGA_ISOLACAO_MM} mm (projeto)", f"≥ {escoamento} mm", CK.check(True, u), "Tabela 2 + layout"))
    # ---------------------------------------------------------------- 10.10 temperatura
    v = (gab or {}).get("ventilacao") or {}
    if v:
        t_int = v.get("t_interna_c")
        u = CK.utilizacao(t_int, 55)
        L.append(_linha("61439-1 §10.10", "Temperatura do ar interno (ambiente de projeto "
                        f"{ped.amb_c:g} °C) × categoria do capacitor -25/D (máx. 55 °C, IEC 60831-1)",
                        f"{t_int:.1f} °C", "≤ 55 °C", CK.check(t_int <= 55, u), "IEC 60890: perdas × vazão"))
        u = CK.utilizacao(v.get("vazao_necessaria_m3h"), v.get("vazao_instalada_m3h"))
        L.append(_linha("61439-1 §10.10", "Vazão de ar instalada × necessária para as perdas "
                        f"({(gab.get('perdas_w') or {}).get('total', 0):.0f} W)",
                        f"{v.get('vazao_instalada_m3h')} m³/h instalados", f"≥ {v.get('vazao_necessaria_m3h')} m³/h",
                        CK.check(v.get("vazao_instalada_m3h", 0) >= v.get("vazao_necessaria_m3h", 1e9), u), "balanço térmico"))
        for t in v.get("termostatos") or []:
            L.append(_linha("61921 / 61439", f"Termostato {t['tag']} – {t['funcao']}", f"ajuste {t['ajuste_c']} °C",
                            "presente no esquema", CK.APROVADO, "esquema elétrico"))
    # ---------------------------------------------------------------- 10.11 curto-circuito
    icc = _icc_barra_ka(ped)
    icw = next((x for x in ICW_PADRAO if x >= 1.1 * icc), ICW_PADRAO[-1])
    u = CK.utilizacao(icc, icw)
    L.append(_linha("61439-1 §10.11", f"Corrente de curto na barra (trafo {ped.trafo_kva:g} kVA Z {ped.trafo_z_pct:g} % + "
                    f"rede {ped.scc_rede_mva:g} MVA) × Icw especificado do painel (1 s)", f"Icc {icc:.1f} kA",
                    f"Icw ≥ {icw} kA (especificado na ET)", CK.check(icc <= icw, u), "IEC 60909 simplificado"))
    u = CK.utilizacao(icc, 100)
    L.append(_linha("61439-1 §10.11", "Capacidade de interrupção dos fusíveis NH gG da proteção geral e dos estágios "
                    "(IEC 60269-2, 500 V)", f"Icc {icc:.1f} kA", "≤ 100 kA", CK.check(icc <= 100, u), "catálogo NH gG"))
    L.append(_linha("61439-1 §10.11", f"Coordenação fusível gG {prot['fusivel_A']} A × contatora {prot['contator']} "
                    "(IEC 60947-4-1 tipo 2)", f"gG {prot['fusivel_A']} A", "tabela de coordenação do fabricante",
                    CK.ATENCAO, "conferir tabela tipo 2 do fabricante na compra"))
    # ---------------------------------------------------------------- 61921 – banco
    lim_i = 1.30                                    # IEC 60831-1 / IEC 61921: 1,3·In incluindo harmônicas
    vistos = set()
    for i, e in enumerate(res["estagios"]):
        ch = (e["codigo"], round(e["Q_kvar"], 1))
        if ch in vistos:
            continue
        vistos.add(ch)
        d = {n: (val, lim) for n, val, lim in e["limites_cap"]}
        vr, _ = d.get("Tensão rms", (None, None))
        ir, _ = d.get("Corrente rms", (None, None))
        if vr is not None:
            L.append(_linha("60831-1 / 61921", f"Sobretensão permanente no capacitor ({e['codigo']})", f"{vr * 100:.0f} % Un",
                            "≤ 110 % Un", CK.check(vr <= 1.10, CK.utilizacao(vr, 1.10)), "espectro de projeto"))
        if ir is not None:
            L.append(_linha("60831-1 / 61921", f"Sobrecorrente permanente no capacitor ({e['codigo']}) – com harmônicas",
                            f"{ir * 100:.0f} % In", f"≤ {lim_i * 100:.0f} % In", CK.check(ir <= lim_i, CK.utilizacao(ir, lim_i)),
                            "espectro de projeto"))
    est = (trans or {}).get("estudo") if trans else None
    if est:
        td = est.get("t_descarga_s")
        L.append(_linha("60831-1 §22 / 61921", "Descarga do capacitor até 75 V", f"{td:.0f} s", "≤ 180 s",
                        CK.check(td <= 180, CK.utilizacao(td, 180)), "simulação (resistor de descarga)"))
        ipk = max((c["metricas"].get("ipk", 0) for c in est["casos"] if c["codigo"] in ("E1", "E2", "E3", "E4")), default=0)
        s0 = est["parametros"]["estagios"][0]
        L.append(_linha("60831-1 / 61921", "Corrente de energização (inrush) no capacitor – pior caso de manobra",
                        f"{ipk:.0f} A", f"≤ 100·In = {100 * s0['In_cap']:.0f} A",
                        CK.check(ipk <= 100 * s0["In_cap"], CK.utilizacao(ipk, 100 * s0["In_cap"])), "transitórios (ATP)"))
        c = est.get("contatora") or {}
        L.append(_linha("60947-4-1 / 61921", "Contatora adequada à manobra do estágio (pico × catálogo)",
                        f"pico {c.get('pico_pior_A', 0):.0f} A", f"≤ {c.get('lim_pico_A', 0):.0f} A (catálogo)", CK.check(bool(c.get("comum_serve", True)), CK.utilizacao(c.get("pico_pior_A"), c.get("lim_pico_A"))),
                        "transitórios (ATP)"))
    L.append(_linha("61921", "Proteção térmica de cada reator (termostato NF na bobina desliga o estágio)",
                    "1 por reator", "presente no esquema", CK.APROVADO, "esquema elétrico (-Bn)"))
    L.append(_linha("61921", "Bloqueio de religamento no controlador (capacitor descarregado antes de religar)",
                    "programado no controlador", "≥ tempo de descarga", CK.APROVADO if est else CK.ATENCAO,
                    "parâmetro do controlador"))
    # ---------------------------------------------------------------- declarados / ensaio – exigidos da montadora
    for cl, it, req in (
            ("61439-1 §10.3", "Grau de proteção do invólucro", "IP31 (IP54 opcional) – IEC 60529"),
            ("61439-1 §10.2.6", "Resistência a impacto", "IK10 – IEC 62262"),
            ("61439-1 §8.4", "Proteção contra contato direto com a porta aberta", "IPXXB (barreiras/policarbonato)"),
            ("61439-1 §10.5", "Continuidade do circuito de proteção (PE) e equipotencialização das portas", "≤ 0,1 Ω"),
            ("61439-1 §10.9", "Ensaio dielétrico de rotina", "conforme Tabela 8 (Ui) – laudo da montadora"),
            ("61439-1 §11", "Verificação de rotina (fiação, torque, funcionamento, placa de identificação)", "laudo + fotos"),
            ("61921 §9", "Ensaios de rotina do banco (inspeção, dielétrico, descarga, operação do controlador)", "laudo da montadora")):
        L.append(_linha(cl, it, "exigido na ET", req, CK.ATENCAO, "comprovar na inspeção de recebimento (FAT)"))
    # ---------------------------------------------------------------- v1.24.3: disjuntor geral, trafo de comando, cabos (REQ-PNL-017/020)
    try:
        from . import banco as _B
        djg = _B.disjuntor_geral(ped, res)
        L.append(_linha("61921 / 60831-1", f"Disjuntor geral {djg['In']} A × 1,30 × ΣI dos capacitores ({djg['It']:.0f} A rms c/ harmônicas)",
                        f"Ir {djg['Ir']} A ({djg['Ir_frac']}·In)", f"≥ {1.30 * djg['It']:.0f} A", CK.check(djg["In"] >= 1.30 * djg["It"],
                        CK.utilizacao(1.30 * djg["It"], djg["In"])), "cálculo da plataforma"))
        L.append(_linha("61439-1 §10.11", "Capacidade de interrupção do disjuntor geral × Icc na barra", f"Icu {djg['Icu_kA']} kA",
                        f"≥ {djg['Icc_kA']:.1f} kA", CK.check(djg["Icu_kA"] >= djg["Icc_kA"], CK.utilizacao(djg["Icc_kA"], djg["Icu_kA"])),
                        "IEC 60909 simplificado"))
        trc = _B.trafo_comando(ped, res, prot, n_exaust=((gab or {}).get("ventilacao") or {}).get("n_exaustores", 2))
        L.append(_linha("61439-1 / NBR 5410", f"Trafo de comando {trc['Sn']} VA × carga (retenção {trc['S_ret']} VA; pior manobra "
                        f"{trc['S_inst']} VA com {trc['sim']} bobinas partindo)", f"{trc['Sn']} VA", f"≥ {trc['S_req']} VA",
                        CK.check(trc["Sn"] >= trc["S_req"], CK.utilizacao(trc["S_req"], trc["Sn"])), "ΣS_ret/0,8 e S_inst/3"))
        for nome, cb in (("estágio (chave → contatora → reator)", prot.get("cabo_calc")), ("reator → capacitor", prot.get("cabo_cap_calc"))):
            if cb:
                L.append(_linha("NBR 5410 §6.2.5", f"Cabo do {nome}: {cb['secao']} mm² – I0 {cb['I0']} A × FCT {cb['FCT']} ({cb['T_int']:g} °C "
                                f"interno) × FCA {cb['FCA']} ({cb['n_agrup']} circuitos na canaleta)", f"Iz {cb['Iz']:.0f} A",
                                f"≥ {cb['I']:.0f} A", CK.check(cb["Iz"] >= cb["I"], CK.utilizacao(cb["I"], cb["Iz"])), "tab. 36/40/42"))
    except Exception as ex:
        L.append(_linha("—", f"Cálculo do geral/comando/cabos não feito: {type(ex).__name__}", "-", "-", CK.ATENCAO, "-"))
    # ---------------------------------------------------------------- NR-10 (Portaria MTE 737/2026) – itens de projeto
    nr10 = [("10.4.1", "Dispositivo de desligamento com impedimento de reenergização e sinalização da condição", "disjuntor geral c/ cadeado + sinaleiro"),
            ("10.4.2", "Seccionamento de ação simultânea (3 polos)", "disjuntor geral tripolar"),
            ("10.4.3.1", "Circuitos de finalidades distintas separados (força × comando)", "zona de comando separada + canaletas próprias"),
            ("10.4.4", "Aterramento das partes condutoras (portas, placa, estrutura)", "barra PE + cordoalhas"),
            ("10.4.6", "Condições para aterramento temporário", "pinos esféricos no barramento"),
            ("10.4.12", "Estudo de energia incidente", "IEEE 1584-2018 – Estudo_Energia_Incidente + etiqueta na porta"),
            ("10.6.1/10.6.2", "Partes vivas inacessíveis (barreiras/invólucros)", "policarbonato no barramento, protetores de borne (IPXXB)"),
            ("10.6.5", "Medidas contra arco: abertura sob carga, intertravamento, limitação de corrente, tempo curto", "disjuntor c/ intertravamento; fusíveis NH limitadores nos estágios"),
            ("10.7.7.1", "Porta fechada + sinalização de tensão, choque, arco e acesso restrito", "manopla com intertravamento + placas NR-10"),
            ("10.13", "Sequência de desenergização/reenergização prevista em projeto", "memorial descritivo / manual"),
            ("10.4.9", "Memorial descritivo (proteções, identificação de circuitos, restrições de acesso, princípio das proteções)", "memorial + plaquetas DE/PARA")]
    for it, req, como in nr10:
        L.append(_linha(f"NR-10 {it}", req, como, "obrigatório (pior caso)", CK.APROVADO,
                        "projeto Electric (conferir no FAT)"))
    return L


def folha_dados(ped, res, gab, prot, trans=None, inds=None, marca=""):
    """Folha de dados do produto (valores garantidos) – estilo catálogo dos grandes fabricantes."""
    E = res["estagios"]
    q = sum(e["Q_kvar"] for e in E)
    e0 = E[0]
    v = (gab or {}).get("ventilacao") or {}
    dim = (gab or {}).get("dimensoes_mm") or {}
    est = (trans or {}).get("estudo") if trans else None
    thd = res.get("thd") or {}
    massa_r = sum((d or {}).get("massa_kg", {}).get("total", 0) * 1 for d in (inds or []))
    tipo = "Filtro de harmônicas sintonizado" if ped.tipo == "sintonizado" else "Banco de capacitores dessintonizado"
    linhas = [
        ("Produto", f"{tipo} automático – Electric Service"),
        ("Tensão nominal / frequência", f"{ped.tensao_v:g} V / {ped.freq_hz:g} Hz, trifásico"),
        ("Potência reativa efetiva na rede", f"{q:.0f} kvar em {len(E)} estágios: " + " + ".join(f"{e['Q_kvar']:.0f}" for e in E)),
        ("Sintonia", (f"FD {e0['p_pct']:.2f} % – Nr {e0['nr']:.2f} ({e0['f_sintonia']:.0f} Hz)" if ped.tipo != "sintonizado"
                      else ", ".join(dict.fromkeys(f"{e['ordem'] if 'ordem' in e else ''}ª – {e['f_sintonia']:.0f} Hz" for e in E)))),
        ("Distorção de tensão admissível", f"projeto com {sum(v_ ** 2 for v_ in ped.harm_tensao_pct.values()) ** 0.5:.1f} % de DHTv "
                                           "nos terminais – verificação dos limites do capacitor em todos os estágios"),
        ("DHTv na barra com o banco", f"{thd['com']:.2f} % (sem banco {thd['sem']:.2f} %)" if thd else "–"),
        ("Capacitores", f"{e0['cap'][0]} × {e0['cap'][1]:g} kvar / {e0['U_cap_nom']} V por estágio – {B.texto_capacitor(ped)} "
                        "(75 V em ≤ 180 s)"
                        + (f" – {marca}" if marca and marca != "Padrão Electric" else "")),
        ("Reatores", ("Electric – 3 monofásicos de 2 colunas por ramo – " if ped.monofasico else "Electric – trifásico – ")
                     + f"{e0['L_uH']:.0f} µH, I projeto {e0['requisitos']['In']:.0f} A, classe {ped.classe}, núcleo de "
                     "aço-silício com entreferros distribuídos, linear até a corrente de projeto, termostato NF na bobina, "
                     "projeto por elementos finitos com relatório"),
        ("Manobra por estágio", f"{prot['contator']} ({prot.get('contator_tipo', '')}) – pico de manobra verificado no ATP"),
        ("Proteção por estágio", f"chave seccionadora-fusível {prot['chave_A']} A com fusíveis NH gG {prot['fusivel_A']} A "
                                 "(opcional: disjuntor por estágio)"),
        ("Controlador", "automático, 4 quadrantes, medição de DHT de tensão e corrente, alarmes de DHT, temperatura e "
                        "sobretensão, contador de manobras, comunicação Modbus RS-485"),
        ("Corrente de curto suportável (Icw)", f"≥ {next((x for x in ICW_PADRAO if x >= 1.1 * _icc_barra_ka(ped)), 100)} kA / 1 s "
                                               f"(Icc calculada na barra {_icc_barra_ka(ped):.1f} kA)"),
        ("Invólucro", f"autoportante {dim.get('altura', '–')} × {dim.get('largura', '–')} × {dim.get('profundidade', '–')} mm "
                      "(A × L × P), RAL 7035, IP31 (IP54 opcional), IK10, IPXXB com porta aberta, entrada de cabos por baixo "
                      "(por cima opcional)"),
        ("Ventilação", f"{v.get('n_exaustores', '–')} exaustor(es) {v.get('exaustor_m3h', '–')} m³/h com filtro, termostatos "
                       "35 °C (liga ventilação) e 55 °C (desliga o banco); ar interno ≤ "
                       f"{v.get('t_interna_c', 0):.0f} °C com {ped.amb_c:g} °C externos"),
        ("Perdas totais", f"{(gab or {}).get('perdas_w', {}).get('total', 0):.0f} W (reatores {(gab or {}).get('perdas_w', {}).get('reatores', 0):.0f} W)"),
        ("Massa dos reatores", f"{massa_r:.0f} kg por reator distinto (total do painel conforme lista de material)" if massa_r else "–"),
        ("Transitórios", ((f"{est['max_simultaneos']} estágios podem ligar juntos; bloqueio de religamento ≥ "
                           f"{math.ceil(est['t_religar_s'] / 10) * 10:.0f} s; estudo Plataforma = ATP") if est else "–")),
        ("Normas", "IEC 61439-1/2 (verificação de projeto), IEC 61921, IEC 60831-1/2, IEC 60076-6, IEC 60947-4-1, "
                   "IEC 60269, IEEE 519-2022, IEEE 18, IEC 60890"),
        ("Documentação", "memorial de cálculo, estudo de transitórios (Plataforma × ATP), projeto do reator por elementos "
                         "finitos, esquema elétrico, layout, lista DE/PARA, lista de material, relatório consolidado"),
    ]
    return linhas


def verificacao_md(L):
    out = ["", "## Verificação de projeto IEC 61439-1/2 e conformidade IEC 61921 (check)", "",
           "| Cláusula | Verificação | Projeto | Requisito | Check | Método |", "|---|---|---|---|---|---|"]
    out += ["| " + " | ".join(str(c).replace("|", "/") for c in r) + " |" for r in L]
    n = {k: sum(1 for r in L if k in r[4]) for k in (CK.APROVADO, CK.ATENCAO, CK.REPROVADO)}
    out += ["", f"Resumo: {n[CK.APROVADO]} APROVADO, {n[CK.ATENCAO]} ATENÇÃO (comprovar no recebimento ou conferir), "
            f"{n[CK.REPROVADO]} REPROVADO."]
    return out


def pdf_padrao(arq, cod, cliente, FD, L, versao=""):
    """PDF padrão da plataforma (mesmo formato nos 3 filtros): folha de dados + verificação de normas com Check."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer
    from . import consolidado as CONS
    f, fb = CONS._fonte()
    E = CONS._estilos(f, fb)
    h = [Paragraph("FOLHA DE DADOS – VALORES GARANTIDOS", E["h1"]), Paragraph(CONS._limpa(f"{cod} – {cliente}"), E["h2"]),
         CONS._tabela([["Característica", "Valor"]] + [list(x) for x in FD], E, larg=[50 * mm, 130 * mm]), PageBreak(),
         Paragraph("VERIFICAÇÃO DE PROJETO E DE NORMAS (CHECK)", E["h1"]),
         Paragraph("Itens calculados neste projeto e itens exigidos do fornecedor/montadora (ensaio/declaração). Check: APROVADO "
                   "(< 90 % do limite), ATENÇÃO (90–100 %, aviso ou comprovação pendente), REPROVADO (acima do limite).",
                   E["peq"]), Spacer(1, 4),
         CONS._tabela([["Cláusula", "Verificação", "Projeto", "Requisito", "Check", "Método"]] + L, E,
                      larg=[22 * mm, 58 * mm, 26 * mm, 28 * mm, 22 * mm, 24 * mm])]
    doc = SimpleDocTemplate(arq, pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm, topMargin=15 * mm, bottomMargin=15 * mm,
                            title=f"Folha de dados e verificação {cod}", author=f"Electric Service – {versao}")
    doc.build(h)
    return arq


def gerar_pdf(ped, res, gab, prot, cod, pasta, trans=None, inds=None, versao="", log=print):
    """Folha de dados + verificação IEC num PDF (01_Engenharia/5_Normas_Folha_de_Dados) – devolve (pdf, linhas)."""
    os.makedirs(pasta, exist_ok=True)
    L = verificacao(ped, res, gab, prot, trans)
    FD = folha_dados(ped, res, gab, prot, trans, inds, getattr(ped, "marca", ""))
    arq = pdf_padrao(os.path.join(pasta, f"Folha_de_Dados_e_Verificacao_IEC_{cod}.pdf"), cod, ped.cliente, FD, L, versao)
    log(f"   Folha de dados e verificação IEC 61439/61921: {os.path.basename(arq)}")
    return arq, L
