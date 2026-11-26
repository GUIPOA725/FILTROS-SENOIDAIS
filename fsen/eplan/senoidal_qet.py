"""Esquema elétrico do FILTRO SENOIDAL no mesmo modelo QElectroTech do banco/filtro sintonizado (v1.16.1).

Folhas: capa, índice, força (X1 do inversor → -L1 [→ -L2] → X2 para o motor, derivação para o banco de capacitores,
barra PE), comando (X3 220 V → -F1 → -B0 termostato do painel → ventiladores -M1..; alarme do PTC do reator (via relé -K1) em X3:3/4).
Gera .qet + PDF + DXF e a lista DE/PARA + etiquetas (fios, componentes, cabos externos) pelo mesmo módulo dos bancos.
"""
from __future__ import annotations

import datetime as _dt
import os

from .qet import ProjetoQet, W_PX

YU, YV, YW = 200, 220, 240          # fases na folha de força (horizontal: inversor à esquerda, motor à direita)


def _sec(it_cabos, uso, padrao=""):
    for c in it_cabos or []:
        if c.get("uso") == uso:
            return f"{c['secao']:g}"
    return padrao


def _cabo_motor(proj, s_pot):
    """v1.28.0 (REQ-SEN-022, auditoria D12): o cabo -W2 é o MESMO da simulação (seção, paralelos e blindagem do modelo do
    sistema); antes o esquema repetia a seção interna do painel e escrevia 'blindado' sempre."""
    si = getattr(proj, "sistema", {}) or {}
    pd = proj.pedido if isinstance(proj.pedido, dict) else {}
    sec = si.get("cabo_secao_mm2") or s_pot or "?"
    par = int(si.get("cabo_paralelos") or 1)
    bl = bool(pd.get("cabo_blindado", True))
    form = (f"{par}×" if par > 1 else "") + f"3×{sec:g} mm² + PE" if isinstance(sec, (int, float)) else f"3×{sec} mm² + PE"
    return form, ("blindado" if bl else "NÃO blindado"), bl


def construir(proj, arr, cod, versao):
    l1, l2, b = proj.l1, proj.l2, proj.banco
    pd = proj.pedido
    lcl = l2 is not None
    V = pd.get("tensao_v") or 0
    titulo = f"Filtro senoidal {'LCL' if lcl else 'LC'} {l1.i_nom_a:.0f} A {V:g} V"
    Q = ProjetoQet(titulo, pd.get("cliente") or "–", f"ESQ-{cod}", f"{_dt.date.today():%d/%m/%Y}", versao)
    s_pot = _sec(arr.cabos, "potência", "")
    s_cap = _sec(arr.cabos, "ramo capacitivo", "")
    s_jmp = _sec(arr.cabos, "jumpers", s_cap)
    s_pe = _sec(arr.cabos, "terra", "")
    s_aux = _sec(arr.cabos, "auxiliar", "1,5").replace(".", ",")

    def inf(desig, fab="", ref="", qtd=1, dados=""):
        return dict(designation=desig, manufacturer=fab, manufacturer_reference=ref, quantity=qtd, dados=dados)

    capa = Q.folio("Capa", "GERAL")
    capa.texto(80, 180, "ESQUEMA ELÉTRICO", 26)
    capa.texto(80, 230, titulo, 16)
    capa.texto(80, 270, f"Cliente: {pd.get('cliente') or '–'}    Inversor: {pd.get('inversor') or '–'}", 12)
    capa.texto(80, 300, f"fs = {proj.fs_hz / 1000:g} kHz (fixa)  |  fr = {proj.fr_hz:.0f} Hz  |  código {cod}", 12)
    capa.texto(80, 340, "Identificação IEC 81346 – símbolos IEC 60617 (biblioteca QElectroTech) – painel NBR IEC 61439", 9, "#555555")
    ind = Q.folio("Índice", "GERAL")

    # ------------------------------------------------------------------ força (rotacionado: corrente da esquerda p/ direita)
    fp = Q.folio("Força – filtro senoidal", "FORCA")
    fases = ("U", "V", "W")
    # ---- fora do painel: inversor e cabo -W1 (em cima, à esquerda)
    ext = dict(externo=True)
    inv = fp.el("inversor", 140, 50, "-U1", dict(ext, designation=f"Inversor {pd.get('inversor') or ''}".strip(),
                                                  dados=f"fs = {proj.fs_hz / 1000:g} kHz fixa"))
    _fm, _bl_txt, _bl = _cabo_motor(proj, s_pot)
    w1 = fp.el("cabo3", 140, 130, "-W1", dict(ext, designation=f"Cabo {'blindado' if _bl else 'NÃO blindado'} inversor → filtro"))
    x1 = [fp.el("borne_continuite", 120 + 20 * k, 200, f"-X1:{f}1", inf("Borne de potência entrada (inversor)")) for k, f in enumerate(fases)]
    x1pe = fp.el("borne_continuite", 180, 200, "-X1:PE", inf("Borne PE entrada"))
    fp.texto(76, 192, "-X1", 9, "#1f4e8c")
    for k in range(3):
        fp.fio(inv.term("s", k), w1.term("n", k), potencia=True, marca="PT")
        fp.fio(w1.term("s", k), x1[k].term("n"), potencia=True, marca="PT")
    fp.fio(inv.term("s", 3), w1.term("n", 3), marca="VD/AM", cor="#2e7d32")
    fp.fio(w1.term("s", 3), x1pe.term("n"), marca="VD/AM", cor="#2e7d32")
    fp.texto(250, 140, f"-W1  3×{s_pot or '?'} mm² + PE, " + ("blindado, blindagem aterrada 360° nas duas pontas" if _bl else
                                                            "NÃO blindado (premissa da simulação – confirmar com o cliente)"), 6.5, "#555555")
    xL1 = 300
    L1 = fp.el("reator3", xL1, 330, "-L1", inf(f"Indutor do filtro {l1.l_uh:.0f} µH/fase", ref="projeto FSEN",
                                                  dados=f"{l1.l_uh:.0f}uH-{l1.i_nom_a:.0f}A"))
    for k in range(3):
        fp.fio(x1[k].term("s"), L1.term("n", k), potencia=True, secao=s_pot, marca="PT", ym=250 + 8 * k)
    nos_saida = []
    for k in range(3):
        n_ = fp.no(L1.term("s", k)[1], 460 + 12 * k)
        fp.fio(L1.term("s", k), n_.term("n"), potencia=True, secao=s_pot, marca="PT")
        nos_saida.append(n_)
    if lcl:
        # -L2 girado 180°: entra por baixo (vindo dos nós de saída do -L1) e sai por cima para o -X2 – sem cruzar os símbolos
        L2 = fp.el("reator3", 600, 330, "-L2", inf(f"Indutor de saída {l2.l_uh:.0f} µH/fase", ref="projeto FSEN",
                                                       dados=f"{l2.l_uh:.0f}uH"), ori=2)
        ent = sorted([L2.term("s", k) for k in range(3)], key=lambda t: "UVW".index(t[4]) if t[4] in "UVW" else 0)
        sai = sorted([L2.term("n", k) for k in range(3)], key=lambda t: "XYZ".index(t[4]) if t[4] in "XYZ" else 0)
        for k in range(3):
            fp.fio(nos_saida[k].term("n"), ent[k], potencia=True, secao=s_pot, marca="PT", ym=nos_saida[k].y)
        orig_x2 = sai
    else:
        orig_x2 = [nos_saida[k].term("n") for k in range(3)]
    # ---- saída X2 (lado direito, dentro do painel) → cabo -W2 → motor (fora do painel, à direita)
    x2 = [fp.el("borne_continuite", 760 + 20 * k, 330, f"-X2:{f}2", inf("Borne de potência saída (motor)")) for k, f in enumerate(fases)]
    x2pe = fp.el("borne_continuite", 820, 330, "-X2:PE", inf("Borne PE saída"))
    fp.texto(716, 322, "-X2", 9, "#1f4e8c")
    w2 = fp.el("cabo3", 920, 420, "-W2", dict(ext, designation=f"Cabo {_bl_txt} filtro → motor"))
    mot = fp.el("motor3", 920, 520, "-M", dict(ext, designation="Motor",
                                              dados=f"{pd.get('motor_cv') or '?'} cv {pd.get('motor_corrente_a') or '?'} A"))
    if lcl:     # -L2 sai por cima: entra no -X2 por cima; cabo do motor sai por baixo do -X2
        for k in range(3):
            fp.fio(orig_x2[k], x2[k].term("n"), potencia=True, secao=s_pot, marca="PT", ym=260 + 8 * k)
            fp.fio(x2[k].term("s"), w2.term("n", k), potencia=True, marca="PT", ym=360 + 8 * k)
        fp.fio(x2pe.term("s"), w2.term("n", 3), marca="VD/AM", cor="#2e7d32", ym=384)
        pe_x2 = x2pe.term("n")
    else:       # LC: fios do -L1 chegam por baixo do -X2; cabo do motor sai por cima e desce até o motor
        for k in range(3):
            a_ = orig_x2[k]
            fp.fio(a_, x2[k].term("s"), potencia=True, secao=s_pot, marca="PT", ym=a_[2])
            fp.fio(x2[k].term("n"), w2.term("n", k), potencia=True, marca="PT", ym=292 - 8 * k)
        fp.fio(x2pe.term("n"), w2.term("n", 3), marca="VD/AM", cor="#2e7d32", ym=268)
        pe_x2 = x2pe.term("s")
    for k in range(3):
        fp.fio(w2.term("s", k), mot.term("n", k), potencia=True, marca="PT")
    fp.fio(w2.term("s", 3), mot.term("n", 3), marca="VD/AM", cor="#2e7d32")
    fp.texto(870, 600, f"-W2  {_fm} {_bl_txt} (o mesmo da simulação)", 6.5, "#555555")
    fp.texto(870, 612, f"comprimento {pd.get('cabo_m') or '?'} m", 6.5, "#555555")
    fp.ret(70, 170, 790, 480, "+PAINEL – filtro senoidal")
    # banco de capacitores: n_por_ramo blocos de 3 capacitores (1 por ramo) em paralelo
    nb = b.n_por_ramo
    dados_c = f"3× {b.uf_unit:g} µF {b.v_unit:g} V"
    lig = "triângulo" if b.ligacao == "Delta" else "estrela (neutro isolado)"
    caps, pe_tag = [], {}
    passo = min(80, (W_PX - 160 - 160) / max(nb, 1))
    for c in range(nb):
        cx = 180 + c * passo
        cp = fp.el("cap3", cx, 560, f"-C{c + 1}", inf(f"Capacitores {dados_c} em {lig} (1 por ramo){' + resistor de descarga' if b.r_descarga_mohm else ''}",
                                                    fab=b.fabricante, ref=b.pn, qtd=3, dados=dados_c), chave=c)
        caps.append(cp)
        pe_tag[cx] = cp.label
    yt = caps[0].term("n", 0)[2]
    for k in range(3):
        fp.fio(nos_saida[k].term("n"), caps[0].term("n", k), potencia=True, secao=s_cap, marca="PT", ym=yt - 34 + 7 * k)
        for c in range(1, nb):
            fp.fio(caps[c - 1].term("n", k), caps[c].term("n", k), potencia=True, secao=s_jmp, marca="PT", ym=yt - 8 - 5 * (2 - k))
    # barra PE
    xpe1, xpe2 = 690, 715                     # descidas do PE das massas dos indutores (fora da área do banco)
    pe_pts = sorted({110, 840, xpe1, 820} | ({xpe2} if lcl else set()))
    prev, nos_pe = None, {}
    for x in pe_pts:
        n_ = fp.no(x, 645, barra="-PE")
        nos_pe[x] = n_
        if prev is not None:
            fp.fio(prev.term("n"), n_.term("n"), marca="VD/AM", secao=s_pe, potencia=True)
        prev = n_
    fp.texto(76, 641, "-PE", 8, "#2e7d32")
    for xr, tg in ((xpe1, "-L1"),) + (((xpe2, "-L2"),) if lcl else ()):
        nm = fp.no(xr, 410 if tg == "-L1" else 395, pe_de=tg)
        fp.fio(nm.term("n"), nos_pe[xr].term("n"), marca="VD/AM", secao=s_pe, potencia=True)
        fp.texto(xr + 4, 406 if tg == "-L1" else 391, f"PE massa {tg}", 6, "#2e7d32")
    fp.fio(x1pe.term("s"), nos_pe[110].term("n"), marca="VD/AM", secao=s_pe, potencia=True, ym=228)
    fp.fio(pe_x2, nos_pe[820].term("n"), marca="VD/AM", secao=s_pe, potencia=True)
    fp.texto(160, 620, f"Banco: {b.n_total} × {b.uf_unit:g} µF / {b.v_unit:g} V {b.fabricante} ({b.pn}), ligação {lig}", 6.5, "#555555")
    fp.texto(160, 630, f"C eq. Y = {b.c_y_uf:g} µF/fase; descarga {b.r_descarga_mohm * 1000:.0f} kΩ em cada capacitor", 6.5, "#555555")
    if proj.amortecimento:
        am = proj.amortecimento
        fp.texto(160, 634, f"Amortecimento: {am.tipo} – R {am.r_ramo_ohm:.2f} Ω {am.p_nominal_w:g} W por ramo (ver memorial)", 6.5, "#c62828")

    # ------------------------------------------------------------------ comando: ventilação e alarme
    fc = Q.folio("Comando – ventilação e alarme", "COMANDO")
    x3 = {i: fc.el("borne_continuite", 60 + 40 * (i - 1), 80, f"-X3:{i}", inf("Borne auxiliar 220 V / alarme")) for i in (1, 2)}
    fc.texto(20, 50, "-X3  220 Vca externo (cliente)", 8, "#1f4e8c")
    f1 = fc.el("disjonct-m_2f", 200, 170, "-F1", inf("Disjuntor/fusível auxiliar 2 A"))
    fc.fio(x3[1].term("s"), f1.term("n", 0), marca="VM", secao=s_aux, num="L")
    fc.fio(x3[2].term("s"), f1.term("n", 1), marca="AZ", secao=s_aux, num="N")
    b0 = fc.el("thermostat_01", 180, 300, "-B0", inf("Termostato do painel (NA, 40 °C) – liga a ventilação", dados="40 °C"))
    fc.fio(f1.term("s", 0), b0.term("n"), marca="VM", secao=s_aux)
    nv = max(1, int(getattr(arr, "n_ventiladores", 1) or 1))
    nl = fc.no(180, 400)
    fc.fio(b0.term("s"), nl.term("n"), marca="VM", secao=s_aux)
    nn0 = fc.no(220, 600)
    fc.fio(f1.term("s", 1), nn0.term("n"), marca="AZ", secao=s_aux, ym=560)
    prevL, prevN = nl, nn0
    for k in range(nv):
        x = 320 + 80 * k
        m = fc.el("moteur_mono", x, 480, f"-M{k + 1}", inf("Ventilador de exaustão com filtro 220 V"))
        nt = fc.no(m.term("n", 0)[1], 400)
        fc.fio(prevL.term("n"), nt.term("n"), marca="VM", secao=s_aux)
        fc.fio(nt.term("n"), m.term("n", 0), marca="VM", secao=s_aux)
        nn = fc.no(m.term("n", 1)[1], 600)
        fc.fio(m.term("n", 1), nn.term("n"), marca="AZ", secao=s_aux)
        fc.fio(prevN.term("n"), nn.term("n"), marca="AZ", secao=s_aux)
        prevL, prevN = nt, nn
    # alarme: termostato do reator NF em X3:3/4
    x33 = fc.el("borne_continuite", 700, 80, "-X3:3", inf("Borne alarme"))
    x34 = fc.el("borne_continuite", 760, 80, "-X3:4", inf("Borne alarme"))
    from ..ind_projeto import ptc_tnf_c          # v1.32.0 (REQ-SEN-026): um único dispositivo – PTC 160 °C, borne TH1/TH2 (igual ET/BOM)
    b1 = fc.el("thermostat_nc", 700, 300, "-B1", inf(f"PTC do reator -L1 (DIN 44081, 3 em série, TNF {ptc_tnf_c(True)} °C) – bornes TH1/TH2 "
                                                     "→ relé de PTC -K1 (ou entrada de termistor do inversor), contato NF de alarme",
                                                     dados=f"PTC {ptc_tnf_c(True)} °C"))
    fc.fio(x33.term("s"), b1.term("n"), marca="CZ", secao=s_aux, num="AL1")
    fc.fio(b1.term("s"), x34.term("s"), marca="CZ", secao=s_aux, num="AL2", ym=420)
    fc.texto(700, 40, "Alarme de temperatura do indutor: PTC 160 °C (TH1/TH2) → relé -K1, contato NF para o CLP/inversor do cliente", 7, "#555555")
    for k, f in enumerate(Q.folios):
        ind.texto(80, 80 + 22 * k, f"{f.n:>3}   {f.titulo}", 11)
        ind.texto(620, 80 + 22 * k, "=" + f.funcao + " +PAINEL", 9, "#555555")
    return Q


def gerar(proj, arr, pasta, cod, versao, log=print):
    from .qet import render_pdf, render_dxf
    from . import etiquetas as ET
    os.makedirs(pasta, exist_ok=True)
    Q = construir(proj, arr, cod, versao)
    arq_qet = Q.salvar_qet(os.path.join(pasta, f"Esquema_Eletrico_{cod}.qet"))
    arq_pdf = render_pdf(Q, os.path.join(pasta, f"Esquema_Eletrico_{cod}.pdf"))
    arq_dxf = render_dxf(Q, os.path.join(pasta, f"Esquema_Eletrico_{cod}.dxf"))
    pd = proj.pedido
    s_pot = _sec(arr.cabos, "potência", "conforme ET")
    _fm, _bl_txt, _bl = _cabo_motor(proj, None)
    cabos = [dict(tag="-W1", de="-X1:U1/V1/W1/PE", para=f"Inversor {pd.get('inversor') or ''}".strip(),
                  formacao=f"3×{s_pot} mm² + PE ({'blindado' if _bl else 'NÃO blindado'})", funcao="Entrada do filtro (saída do inversor)"),
             dict(tag="-W2", de="-X2:U2/V2/W2/PE", para="Motor", formacao=f"{_fm} ({_bl_txt}, o mesmo da simulação), {pd.get('cabo_m') or '?'} m",
                  funcao="Saída do filtro para o motor"),
             dict(tag="-W3", de="-X3:1/2", para="220 Vca do cliente", formacao="2×1,5 mm²", funcao="Alimentação da ventilação"),
             dict(tag="-W4", de="-X3:3/4", para="CLP/inversor do cliente", formacao="2×1,0 mm²", funcao="Alarme de temperatura do indutor")]
    funcoes = {"-L1": "INDUTOR DO FILTRO", "-L2": "INDUTOR DE SAÍDA", "-F1": "AUXILIAR 220 V", "-B0": "TERMOSTATO DO PAINEL",
               "-B1": "TERMOSTATO DO INDUTOR", "-X1": "ENTRADA – DO INVERSOR", "-X2": "SAÍDA – PARA O MOTOR"}
    massas = ["-L1"] + (["-L2"] if proj.l2 is not None else []) + ["PORTA", "PLACA DE MONTAGEM", "ESTRUTURA DO PAINEL"]
    et = ET.gerar(Q, pasta, cod, cabos_externos=cabos, versao=versao, titulo=Q.titulo, funcoes=funcoes,
                  pe_massas=[m for m in massas if m not in ("-L1", "-L2")],
                  secao_pe=_sec(arr.cabos, "terra", "16"),
                  extra_componentes=[(f"=FILTRO {cod}", Q.titulo, "Porta (placa de identificação do painel)")])
    _cf = getattr(Q, "conferencia_desenho", [])
    log(f"   Conferência do desenho: {len(_cf)} sobreposição(ões) de texto" + (" – " + "; ".join(f"folha {c['folha']}: {c['a']} × {c['b']}" for c in _cf[:5]) if _cf else ""))
    log(f"   Esquema elétrico (QElectroTech): {len(Q.folios)} folhas – .qet + PDF + DXF; DE/PARA {et['n_fios']} fios, "
        f"{et['n_etq_fios']} etiquetas de fio, {et['n_componentes']} plaquetas")
    return dict(pdf=arq_pdf, dxf=arq_dxf, qet=arq_qet, etq_xlsx=et["xlsx"], etq_pdf=et["pdf"], projeto=Q)
