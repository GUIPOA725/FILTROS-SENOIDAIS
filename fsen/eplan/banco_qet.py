"""Esquema elétrico do painel de banco dessintonizado / filtro sintonizado no padrão do projeto AGCO Ibirubá (EPLAN 2023,
gabarito Electric), gerado como projeto QElectroTech (.qet) + PDF + DXF (v1.16.0).

Sequência de folhas (mesma do projeto AGCO): capa | índice | alimentação | estágios (2 por folha, com os capacitores de cada
estágio e seção dos cabos) | controlador (BR6000, relé falta de fase, TC externo, saídas → bobinas, espelho de contatos) |
comando, emergência e sinalização | ventilação | régua de bornes | lista de conexão | lista de peças.
Marcação de fio como no EPLAN Electric: força "PT" (preto) com seção; comando "VM 1,5 mm²"; TC "PT 2,5 mm²"; PE "VD/AM".
"""
import datetime as _dt

from .qet import ProjetoQet, W_PX, H_PX, COLW

Y_R, Y_S, Y_T, Y_PE = 40, 60, 80, 600     # barramentos nas folhas de estágios
X_STG = (150, 560)                        # posição dos 2 estágios na folha


def _f(x, n=1):
    return f"{float(x):.{n}f}".replace(".", ",")


def _barras(f, xs_tap, nomes=("-R2", "-S2", "-T2")):
    """Barramentos R/S/T com pontos de derivação nos x pedidos (cada fase deslocada 20 px como nos elementos 3P)."""
    nos = {}
    for k, (y, nm) in enumerate(zip((Y_R, Y_S, Y_T), nomes)):
        pts = sorted({30} | {x + 20 * (k - 1) for x in xs_tap} | {W_PX - 30})
        prev = None
        for x in pts:
            n = f.no(x, y, barra=nm)
            nos[(k, x)] = n
            if prev is not None:
                f.fio(prev.term("n"), n.term("n"), potencia=True)
            prev = n
        f.texto(8, y - 4, nm, 9, "#1f4e8c")
    return nos


def _secao_geral(I):
    """Seção do cabo/barra da chave geral (cobre 90 °C, fator 0,62 do painel – mesma regra dos estágios)."""
    from .. import banco as B
    for s_, cap in B.CABO_90C:
        if cap * 0.62 >= I:
            return f"{s_:g}"
    return "barra"


def _secao_pe(I):
    """Condutor de proteção (NBR 5410 tab. 58): S ≤ 16 → S; 16 < S ≤ 35 → 16; S > 35 → S/2."""
    s_ = _secao_geral(I)
    try:
        s_ = float(s_)
    except ValueError:
        return "50"
    return f"{s_ if s_ <= 16 else 16 if s_ <= 35 else s_ / 2:g}"


def _barra_pe(f, xs):
    pts = sorted({30} | set(xs) | {W_PX - 30})
    nos, prev = {}, None
    for x in pts:
        n = f.no(x, Y_PE, barra="-PE2")
        nos[x] = n
        if prev is not None:
            f.fio(prev.term("n"), n.term("n"), cor="#2e7d32", marca="VD/AM", potencia=True)
        prev = n
    f.texto(8, Y_PE - 4, "-PE2 BARRA PE", 8, "#2e7d32")
    return nos


def construir(ped, res, cod, versao, P_lista=None):
    """P_lista: ProjetoEletrico (banco_eletrico) com dispositivos/bornes/cabos – usado para os dados de lista de peças."""
    from .. import banco as B
    sint = ped.tipo == "sintonizado"
    E = res["estagios"]
    n = len(E)
    V = ped.tensao_v
    titulo = f"{'Filtro de harmônicas sintonizado' if sint else 'Banco de capacitores dessintonizado'} {res['Q_total_kvar']:.0f} kVAr {V:g} V"
    Q = ProjetoQet(titulo, ped.cliente or "–", f"ESQ-{cod}", f"{_dt.date.today():%d/%m/%Y}", versao)
    pn = B.painel(ped, res)
    info = lambda tag: dict((P_lista.disp.get(tag) or {}).items()) if P_lista else {}

    def inf(tag, extra=""):
        d = info(tag)
        return dict(designation=d.get("descr", ""), manufacturer=d.get("fab", ""), manufacturer_reference=d.get("cod", ""),
                    quantity=d.get("qtd", 1), dados=extra or d.get("dados", ""))

    # ------------------------------------------------------------------ 1 capa, 2 índice
    capa = Q.folio("Capa", "GERAL")
    capa.texto(80, 180, "ESQUEMA ELÉTRICO", 26)
    capa.texto(80, 230, titulo, 16)
    capa.texto(80, 270, f"Cliente: {ped.cliente or '–'}    Projeto: {ped.projeto or '–'}", 12)
    capa.texto(80, 300, f"{n} estágios  |  {V:g} V  {ped.freq_hz:g} Hz  |  código {cod}", 12)
    capa.texto(80, 340, "Identificação IEC 81346 – símbolos IEC 60617 (biblioteca QElectroTech) – painel NBR IEC 61439", 9, "#555555")
    ind = Q.folio("Índice", "GERAL")
    # ------------------------------------------------------------------ 3 alimentação
    fa = Q.folio("Alimentação e distribuição", "ALIM")
    xq = 150
    bx = [fa.el("borne_continuite", xq + 20 * (k - 1), 300, f"-X0:{nm}") for k, nm in enumerate(("L1", "L2", "L3"))]
    fa.texto(xq - 48, 292, "-X0", 9, "#1f4e8c")
    fa.texto(xq - 60, 268, f"ALIMENTAÇÃO {V:g} V 3F+PE {ped.freq_hz:g} Hz – cabo do cliente", 7, "#c62828")
    q0 = fa.el("sectionneur_3_fusibles", xq, 420, "-Q0", inf("-Q0", f"{pn['geral_A']} A NH"))
    for k in range(3):
        fa.fio(bx[k].term("s"), q0.term("n", k), potencia=True, secao=_secao_geral(pn["geral_A"]), marca="PT")
    nos = _barras(fa, [340, 520, 760])
    for k in range(3):
        n_ = fa.no(xq + 20 * (k - 1), 520 - 10 * k)
        fa.fio(q0.term("s", k), n_.term("n"), potencia=True, marca="PT", secao=_secao_geral(pn["geral_A"]))
        nb = fa.no(320 + 20 * k, 520 - 10 * k)
        fa.fio(n_.term("n"), nb.term("n"), potencia=True)
        fa.fio(nb.term("n"), nos[(k, 320 + 20 * k)].term("n"), potencia=True)
    fa.texto(340, 470, "→ barramentos -R2/-S2/-T2 (folhas dos estágios)", 7, "#555555")
    # relé falta de fase e trafo de comando
    f01 = fa.el("disjonct-m_3f", 520, 160, "-F01", inf("-F01", "10 A"))
    for k in range(3):
        fa.fio(nos[(k, 520 + 20 * (k - 1))].term("n"), f01.term("n", k), marca="VM", secao="1,5")
    k0 = fa.el("rele_ff", 520, 280, "-K0", inf("-K0"))
    for k in range(3):
        fa.fio(f01.term("s", k), k0.term("n", k), marca="VM", secao="1,5")
    f02 = fa.el("disjonct-m_2f", 760, 160, "-F02", inf("-F02", "10 A"))
    for k in range(2):
        fa.fio(nos[(k, 760 + 20 * (k - 1))].term("n"), f02.term("n", k), marca="VM", secao="1,5")
    t1 = fa.el("transfo_mono", 760, 300, "-T1", inf("-T1", f"{V:g}/220 V"))
    fa.fio(f02.term("s", 0), t1.term("n", 0), marca="VM", secao="1,5")
    fa.fio(f02.term("s", 1), t1.term("n", 1), marca="VM", secao="1,5")
    for k_, pt_ in enumerate(("L220", "N220")):        # secundário do -T1 → potenciais 220 V do comando (folhas 6 e 7)
        n220 = fa.no(t1.term("s", k_)[1], 380, pot=pt_)
        fa.fio(t1.term("s", k_), n220.term("n"), marca="VM" if k_ == 0 else "AZ", secao="1,5", num=pt_)
    fa.texto(800, 360, "220 V → comando (folha do controlador)", 7, "#555555")
    # ------------------------------------------------------------------ estágios (2 por folha)
    bobinas = {}
    contatos_pot = {}
    grupos_folha, i_ = [], 0          # 2 estágios por folha (padrão AGCO); 1 por folha quando o estágio tem > 4 capacitores
    while i_ < n:
        if i_ + 1 < n and E[i_]["cap"][0] <= 4 and E[i_ + 1]["cap"][0] <= 4:
            grupos_folha.append([i_, i_ + 1])
            i_ += 2
        else:
            grupos_folha.append([i_])
            i_ += 1
    for grupo in grupos_folha:
        k0_ = grupo[0]
        fs = Q.folio(f"Estágios do filtro {k0_+1}" + (f"-{grupo[-1]+1}" if len(grupo) > 1 else ""), "ESTAGIOS")
        xs = [X_STG[j] for j in range(len(grupo))]
        nos = _barras(fs, xs)
        pe_x, pe_tag = [], {}
        for j, i in enumerate(grupo):
            e = E[i]
            pr = B.protecao_estagio(ped, e)
            x = xs[j]
            tg = i + 1
            ff = fs.el("sectionneur_3_fusibles", x, 160, f"-FF{tg}", inf(f"-Q{tg}", f"{pr['base']}/{pr['fusivel_A']}A"))
            km = fs.el("com_puiss4", x, 270, f"-K{tg}", inf(f"-K{tg}", pr["contator"].split("(")[0].strip()))
            contatos_pot[tg] = km
            ln = fs.el("reator3", x, 390, f"-L{tg}", inf(f"-L{tg}", f"{e['L_uH']:.0f}uH-{e['requisitos']['In']:.0f}A"))
            sec = f"{pr['cabo_mm2']:g}"
            sec2 = f"{pr['cabo_ind_cap_mm2']:g}"
            for k in range(3):
                fs.fio(nos[(k, x + 20 * (k - 1))].term("n"), ff.term("n", k), potencia=True, secao=sec, marca="PT" if k else "PT")
                fs.fio(ff.term("s", k), km.term("n", k), potencia=True, secao=sec, marca="PT")
                fs.fio(km.term("s", k), ln.term("n", k), potencia=True, secao=sec, marca="PT")
            ncap = e["cap"][0]
            caps = []
            for c in range(ncap):
                if len(grupo) == 1 and ncap > 4:
                    cx = x - 60 + c * min(70, (W_PX - 140 - (x - 60)) / max(ncap - 1, 1))
                else:
                    cx = x - 30 + c * (80 if ncap <= 4 else 60) - (0 if ncap <= 2 else 40 * (ncap - 2) / 2)
                cp = fs.el("cap3", cx, 520, f"-C{tg}.{c+1}" if ncap > 1 else f"-C{tg}",
                           inf(f"-C{tg}", f"{_f(e['cap'][1])}kVAr {e['cap'][2]}V"), chave=c)
                caps.append(cp)
                pe_x.append(cx)
                pe_tag[cx] = cp.label
            yt = caps[0].term("n", 0)[2]
            for k in range(3):
                fs.fio(ln.term("s", k), caps[0].term("n", k), potencia=True, secao=sec2, marca="PT", ym=yt - 34 + 7 * k)
                for c in range(1, ncap):
                    fs.fio(caps[c - 1].term("n", k), caps[c].term("n", k), potencia=True, secao=sec2, marca="PT", ym=yt - 8 - 5 * (2 - k))
            fs.texto(x - 70, 630, f"ESTÁGIO {tg}  {e['Q_kvar']:.0f} kVAr", 10, "#1f4e8c")
            fs.texto(x - 70, 640, f"{e['codigo']} | I60 {e['I60']:.0f} A | Iproj {e['requisitos']['In']:.0f} A | FD {_f(e['p_pct'], 2)} %", 6.5,
                     "#555555")
        nos_pe = _barra_pe(fs, pe_x)
        for cx in pe_x:
            nc = fs.no(cx + 28, 548, pe_de=pe_tag.get(cx, ""))
            fs.fio(nc.term("n"), nos_pe[cx].term("n") if cx in nos_pe else nc.term("n"), cor="#2e7d32", marca="VD/AM", secao="1,5")
    # ------------------------------------------------------------------ controlador
    fc = Q.folio("CFP – controlador BR6000", "COMANDO")
    yL, yN = 40, 600
    xs_ctrl = sorted({60, 120, 200, 260} | {400 + 60 * i for i in range(n)} | {W_PX - 40})
    railL, railN = {}, {}
    for rail, y, nm in ((railL, yL, "L 220 V (-T1)"), (railN, yN, "N 220 V (-T1)")):
        prev = None
        for x in xs_ctrl:
            nd = fc.no(x, y, pot="L220" if rail is railL else "N220")
            rail[x] = nd
            if prev is not None:
                fc.fio(prev.term("n"), nd.term("n"), marca="VM" if rail is railL else "AZ", secao="1,5")
            prev = nd
        fc.texto(8, y - 4, nm, 8, "#c62828")
    s0 = fc.el("arret_urgence_verrou", 60, 110, "-S0", inf("-S0"))
    fc.fio(railL[60].term("n"), s0.term("n"), marca="VM", secao="1,5")
    k0c = fc.el("con_simple", 60, 210, "-K0", dict(contato="11-14"))
    Q.ligar(k0c, k0)
    fc.fio(s0.term("s"), k0c.term("n"), marca="VM", secao="1,5")
    s1 = fc.el("commut_2_position_fixe", 60, 300, "-S1", inf("-S1"))
    fc.fio(k0c.term("s"), s1.term("n"), marca="VM", secao="1,5")
    nh = fc.no(60, 360)
    fc.fio(s1.term("s"), nh.term("n"), marca="VM", secao="1,5")
    fc.texto(70, 372, "L-HAB", 7, "#c62828")
    ctrl = fc.el(f"ctrl{6 if n <= 6 else 12}", 300, 150, "-U1", inf("-A1"))
    fc.fio(railL[260].term("n"), ctrl.term("n", 0), marca="VM", secao="1,5")
    fc.texto(ctrl.term("n", 1)[1] - 38, 92, "-X1", 9, "#1f4e8c")
    xk1 = fc.el("borne_continuite", ctrl.term("n", 1)[1], 100, "-X1:1")
    xk2 = fc.el("borne_continuite", ctrl.term("n", 2)[1], 100, "-X1:2")
    fc.fio(xk1.term("s"), ctrl.term("n", 1), marca="PT", secao="2,5")
    fc.fio(xk2.term("s"), ctrl.term("n", 2), marca="PT", secao="2,5")
    fc.texto(ctrl.term("n", 1)[1] - 10, 70, "TC externo …/5 A (cliente)", 7, "#555555")
    fc.fio(ctrl.term("s", 0), railN[260].term("n") if 260 in railN else railN[200].term("n"), marca="AZ", secao="1,5")
    fc.fio(nh.term("n"), ctrl.term("s", 1), marca="VM", secao="1,5")
    lampadas = []
    for i in range(n):
        tg = i + 1
        x = 400 + 60 * i
        out = ctrl.term("s", 2 + i)
        b = fc.el("thermostat_nc", x, 330, f"-B{tg}", inf(f"-B{tg}", "θ reator"))
        fc.fio(out, b.term("n"), marca="VM", secao="1,5", num=f"{tg}0", ym=out[2] + 14 + 12 * i)
        bo = fc.el("bobine3", x, 460, f"-K{tg}", dict(designation=f"Contator estágio {tg}", contato=""))
        bobinas[tg] = bo
        fc.fio(b.term("s"), bo.term("n"), marca="VM", secao="1,5", num=f"{tg}1")
        fc.fio(bo.term("s"), railN[x].term("n"), marca="AZ", secao="1,5")
        km = contatos_pot.get(tg)
        if km:
            km.info["contato"] = "1-2/3-4/5-6"
            Q.ligar(km, bo)
    # ------------------------------------------------------------------ sinalização e ventilação
    fsn = Q.folio("Sinalização e ventilação", "COMANDO")
    xs2 = sorted({40} | {100 + 50 * i for i in range(n)} | {700, 760, 820, 880, 940} | {W_PX - 40})
    rL, rN = {}, {}
    for rail, y, nm in ((rL, yL, "L 220 V"), (rN, yN, "N 220 V")):
        prev = None
        for x in xs2:
            nd = fsn.no(x, y, pot="L220" if rail is rL else "N220")
            rail[x] = nd
            if prev is not None:
                fsn.fio(prev.term("n"), nd.term("n"), marca="VM" if rail is rL else "AZ", secao="1,5")
            prev = nd
        fsn.texto(8, y - 4, nm, 8, "#c62828")
    for i in range(n):
        tg = i + 1
        x = 100 + 50 * i
        ca = fsn.el("con_simple", x, 200, f"-K{tg}", dict(contato="13-14"), chave="aux")
        Q.ligar(ca, bobinas[tg])
        fsn.fio(rL[x].term("n"), ca.term("n"), marca="VM", secao="1,5")
        h = fsn.el("lampe2", x, 380, f"-H{tg}", inf(f"-H{tg}"))
        fsn.fio(ca.term("s"), h.term("n"), marca="VM", secao="1,5")
        fsn.fio(h.term("s"), rN[x].term("n"), marca="AZ", secao="1,5")
    b0 = fsn.el("thermostat_01", 700, 160, "-B0", inf("-B0", "35 °C"))
    fsn.fio(rL[700].term("n"), b0.term("n"), marca="VM", secao="1,5")
    nv = fsn.no(700, 260)
    fsn.fio(b0.term("s"), nv.term("n"), marca="VM", secao="1,5")
    nvent = 2 if n <= 4 else 4
    prev = nv
    for k in range(nvent):
        x = 760 + 60 * k
        m = fsn.el("moteur_mono", x, 380, f"-M{k+1}", inf(f"-M{k+1}"))
        nt = fsn.no(m.term("n", 0)[1], 260)
        fsn.fio(prev.term("n"), nt.term("n"), marca="VM", secao="1,5")
        fsn.fio(nt.term("n"), m.term("n", 0), marca="VM", secao="1,5")
        nn = fsn.no(m.term("n", 1)[1], 560)
        fsn.fio(m.term("n", 1), nn.term("n"), marca="AZ", secao="1,5")
        fsn.fio(nn.term("n"), rN[min(rN, key=lambda xx: abs(xx - nn.x))].term("n"), marca="AZ", secao="1,5")
        prev = nt
    fsn.texto(700, 120, "Ventilação forçada – liga pelo termostato do painel (-B0)", 7, "#555555")
    # índice
    for k, f in enumerate(Q.folios):
        ind.texto(80, 80 + 22 * k, f"{f.n:>3}   {f.titulo}", 11)
        ind.texto(620, 80 + 22 * k, "=" + f.funcao + " +PAINEL", 9, "#555555")
    return Q


def lista_conexao(Q):
    linhas = []
    for f in Q.folios:
        for c in f.conexoes():
            linhas.append((c["de"], c["para"], c["num"], c["marca"], c["secao"], f"{c['folha']}"))
    return linhas


def gerar(ped, res, pasta, cod, versao, n_banco=1, log=print):
    """Gera .qet + PDF (folhas QET + bornes, conexões, peças) + DXF + XLSX."""
    import os
    from . import banco_eletrico as BE
    from .qet import render_pdf, render_dxf
    P = BE.construir(ped, res, cod, versao, n_banco)          # dispositivos, bornes, cabos (lista de peças)
    Q = construir(ped, res, cod, versao, P)
    arq_qet = Q.salvar_qet(os.path.join(pasta, f"Esquema_Eletrico_{cod}.qet"))
    # folhas de lista (bornes, conexões, peças) pelo renderizador de listas
    P.folhas = []
    from . import etiquetas as ET
    con = [(l["de"], l["para"], l["fio"], l["cor"], l["secao"], str(l["folha_de"])) for l in ET.de_para(Q)]
    BE.listas_folhas(P, conexoes=con)
    for f in P.folhas:
        f.n += len(Q.folios)
    total = len(Q.folios) + len(P.folhas)
    tmp_listas = os.path.join(pasta, "_listas.pdf")
    P.pdf(tmp_listas, total_override=total)
    arq_pdf = render_pdf(Q, os.path.join(pasta, f"Esquema_Eletrico_{cod}.pdf"), pdf_extra=tmp_listas, png_dir=pasta)
    os.remove(tmp_listas)
    arq_dxf = render_dxf(Q, os.path.join(pasta, f"Esquema_Eletrico_{cod}.dxf"))
    arq_xlsx = BE.planilha(P, os.path.join(pasta, f"Lista_Material_Bornes_Cabos_{cod}.xlsx"), conexoes=con)
    V = ped.tensao_v
    cabos = [dict(tag="-W0", de="-X0:L1/L2/L3/PE", para="Alimentação (QGBT do cliente)", formacao=f"3F+PE {V:g} V – conforme ET",
                  funcao="Alimentação do painel"),
             dict(tag="-W1", de="-X1:1/2", para="TC do cliente (fase L1)", formacao="2×2,5 mm² (blindado recomendado)",
                  funcao="Sinal de corrente do controlador")]
    n_est = len(res["estagios"])
    from .. import banco as B
    pn = B.painel(ped, res)
    funcoes = {f"-H{i + 1}": f"ESTÁGIO {i + 1} LIGADO" for i in range(n_est)}
    funcoes.update({"-S0": "EMERGÊNCIA", "-S1": "MANUAL – 0 – AUTOMÁTICO", "-U1": "CONTROLADOR DE FATOR DE POTÊNCIA",
                    "-Q0": "CHAVE GERAL", "-B0": "TERMOSTATO DO PAINEL"})
    for i in range(n_est):
        funcoes[f"-FF{i + 1}"] = f"PROTEÇÃO ESTÁGIO {i + 1}"
        funcoes[f"-K{i + 1}"] = f"CONTATOR ESTÁGIO {i + 1}"
        funcoes[f"-L{i + 1}"] = f"REATOR ESTÁGIO {i + 1}"
    massas = [f"-L{i + 1}" for i in range(n_est)] + ["-X0", "PORTA", "PLACA DE MONTAGEM", "ESTRUTURA DO PAINEL"]
    et = ET.gerar(Q, pasta, cod, cabos_externos=cabos, versao=versao, titulo=Q.titulo, funcoes=funcoes, pe_massas=massas,
                  secao_pe=_secao_pe(pn["geral_A"]),
                  extra_componentes=[(f"=FILTRO {cod}", Q.titulo, "Porta (placa de identificação do painel)")])
    log(f"   Esquema elétrico (padrão AGCO/EPLAN): {total} folhas – .qet (QElectroTech) + PDF + DXF + planilha")
    log(f"   Lista DE/PARA: {et['n_fios']} fios, {et['n_etq_fios']} etiquetas de fio, {et['n_componentes']} plaquetas de componente")
    return dict(pdf=arq_pdf, dxf=arq_dxf, xlsx=arq_xlsx, qet=arq_qet, projeto=Q, etq_xlsx=et["xlsx"], etq_pdf=et["pdf"])
