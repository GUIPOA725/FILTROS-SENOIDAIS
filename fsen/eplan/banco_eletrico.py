"""Esquema elétrico completo do painel de BANCO DESSINTONIZADO / FILTRO SINTONIZADO (v1.15.0) – estilo EPLAN.

Folhas: capa + índice | força: alimentação geral | força: estágios (3 por folha) | comando: alimentação, segurança,
controlador e ventilação | comando: estágios | régua de bornes | lista de cabos | lista de material.
Identificação IEC 81346: -Q0 geral, -Qn seccionadora-fusível do estágio, -Kn contator, -Ln reator, -Cn capacitor, -Bn termostato
do reator, -Hn sinaleiro, -A1 controlador, -K0 relé falta de fase, -S0 emergência, -S1 seletor, -T1 trafo de comando,
-F01..F03 disjuntores de comando, -M1.. ventiladores, -B0 termostato do painel; sintonizado: -T1n TCs e -Pn multimedidor.
Os componentes vêm das MESMAS regras da ET Electric (banco.protecao_estagio / banco.painel).
"""
import datetime as _dt


def _f(x, n=1):
    return f"{float(x):.{n}f}".replace(".", ",")

from . import simbolos as S
from .folha import ProjetoEletrico, col_x, X0, X1, Y0, Y1, CAR_H

BR6000 = {6: ("Epcos BR6000-R6 (6 saídas a relé)", "B44066R6006E230"), 12: ("Epcos BR6000-R12 (12 saídas a relé)", "B44066R6012E230")}
COD_EPCOS = {"S2011": "B44066S2011J230", "S3312": "B44066S3312J230", "S6012": "B44066S6012J230", "S7410": "B44066S7410J230",
             "S9910": "B44066S9910J230"}
Y_BUS = (262.0, 256.0, 250.0, 244.0)     # L1 L2 L3 PE nas folhas de força
Y_L, Y_N = 262.0, 52.0                   # trilhos de comando (fase / neutro do 220 V)


def _cod_contator(nome):
    for k, v in COD_EPCOS.items():
        if k in nome:
            return "Epcos", v
    return "Schneider", nome.split()[1] if len(nome.split()) > 1 else ""


def construir(ped, res, cod, versao, n_banco=1):
    from .. import banco as B
    sint = ped.tipo == "sintonizado"
    E = res["estagios"]
    n = len(E)
    pn = B.painel(ped, res)
    P = ProjetoEletrico(ped.cliente or "–", f"{'Filtro sintonizado' if sint else 'Banco dessintonizado'} "
                        f"{res['Q_total_kvar']:.0f} kvar {ped.tensao_v:g} V", f"ESQ-{cod}", f"{_dt.date.today():%d/%m/%Y}", versao)
    V = ped.tensao_v
    # --------------------------------------------------------------------------- dispositivos gerais
    P.dispositivo("-Q0", f"Disjuntor geral caixa moldada tripolar {pn['geral_A']} A com manopla rotativa externa, intertravamento "
                  f"da porta e bloqueio por cadeado (NR-10)", "ABB/Schneider/WEG (conforme marca do projeto)", "", 1, grupo="Proteção geral")
    P.dispositivo("-F01", "Disjuntor tripolar 10 A curva C (relé falta de fase / medição)", "WEG/Siemens (equiv.)", "", 1, grupo="Comando")
    P.dispositivo("-F02", "Disjuntor bipolar 10 A curva C (primário do trafo de comando)", "WEG/Siemens (equiv.)", "", 1, grupo="Comando")
    P.dispositivo("-F03", "Disjuntor bipolar 10 A curva C (secundário 220 V)", "WEG/Siemens (equiv.)", "", 1, grupo="Comando")
    kva = 500 if n <= 6 else 1000
    P.dispositivo("-T1", f"Transformador de comando {V:g}/220 V {kva} VA", "Trafo nacional (equiv.)", "", 1, grupo="Comando")
    P.dispositivo("-K0", f"Relé de falta e sequência de fase {V:g} V, 1 contato reversível", "WEG/Coel (equiv.)", "", 1, grupo="Comando")
    P.dispositivo("-S0", "Botão de emergência cogumelo Ø40 com trava, 1NF + 1NA, Ø22 mm", "WEG/Schneider (equiv.)", "", 1, grupo="Comando")
    P.dispositivo("-S1", "Chave seletora 2 posições (0 – desligado / 1 – automático) Ø22 mm 1NA", "WEG/Schneider (equiv.)", "", 1, grupo="Comando")
    nr = 6 if n <= 6 else 12
    P.dispositivo("-A1", f"Controlador automático de fator de potência {BR6000[nr][0]}", "Epcos (TDK)", BR6000[nr][1], 1, grupo="Controle")
    P.dispositivo("-B0", "Termostato de painel NA ajustável 0–60 °C (liga ventilação a 35 °C)", "Rittal/Finder (equiv.)", "", 1, grupo="Ventilação")
    P.dispositivo("-BT2", "Termostato de painel NF ajustável 0–60 °C (sobretemperatura: abre a 55 °C e desliga o banco)",
                  "Rittal/Finder (equiv.)", "", 1, grupo="Ventilação", dados="55 °C")
    nvent = 2 if n <= 4 else 4
    for k in range(1, nvent + 1):
        P.dispositivo(f"-M{k}", "Ventilador com filtro 220 V 50/60 Hz, ≥ 230 m³/h (ver cálculo térmico)", "Rittal/Mundial (equiv.)", "", 1,
                      grupo="Ventilação")
    P.dispositivo("-H0", "Sinaleiro LED verde Ø22 mm 220 V (painel energizado)", "WEG/Schneider (equiv.)", "", 1, grupo="Comando")
    # --------------------------------------------------------------------------- dispositivos por estágio
    for i, e in enumerate(E, start=1):
        pr = B.protecao_estagio(ped, e)
        fab, cc = _cod_contator(pr["contator"])
        P.dispositivo(f"-Q{i}", f"Chave seccionadora-fusível tripolar {pr['chave_A']} A {pr['base']} + 3 fusíveis gG {pr['fusivel_A']} A",
                      "WEG/Siemens/Holec (equiv.)", "", 1, grupo=f"Estágio {i}", dados=f"{e['Q_kvar']:.1f} kvar")
        P.dispositivo(f"-K{i}", f"Contator para manobra de capacitor {pr['contator']} – IN {pr['contator_In']:.0f} A, bobina 220 V",
                      fab, cc, 1, grupo=f"Estágio {i}")
        P.dispositivo(f"-L{i}", f"Reator trifásico {e['L_uH']:.0f} µH/fase, {e['requisitos']['In']:.0f} A, Nr {e['nr']:.2f} – classe "
                      f"{ped.classe}, termostato NF – FORNECIMENTO ELECTRIC", "Electric Service", e["codigo"], 1, grupo=f"Estágio {i}")
        P.dispositivo(f"-C{i}", f"Capacitor trifásico {e['cap'][1]:g} kvar / {e['cap'][2]} V" + (" especial para filtro" if sint else "")
                      + " com resistores de descarga", "WEG/Epcos (equiv.)", "", e["cap"][0], grupo=f"Estágio {i}")
        P.dispositivo(f"-H{i}", "Sinaleiro LED vermelho Ø22 mm 220 V (estágio ligado)", "WEG/Schneider (equiv.)", "", 1, grupo=f"Estágio {i}")
        if sint:
            Imx = next(x for x in B.NH if x >= e["requisitos"]["In"])
            P.dispositivo(f"-T1{i}", f"Transformador de corrente {Imx}/5 A, 2,5 VA, classe 1 (3 por estágio)", "Kron/Siemens (equiv.)", "", 3,
                          grupo=f"Estágio {i}")
            P.dispositivo(f"-P{i}", "Multimedidor de proteção Embrasul MD4040 com saída a relé (sobrecorrente / harmônicas)",
                          "Embrasul", "MD4040", 1, grupo=f"Estágio {i}")
    # --------------------------------------------------------------------------- folha 1: capa
    capa = P.nova("Capa e índice", "=GERAL")
    capa.txt(210, 230, "ESQUEMA ELÉTRICO", fs=9, ha="center", negrito=True)
    capa.txt(210, 215, P.projeto, fs=5.5, ha="center")
    capa.txt(210, 205, f"Cliente: {P.cliente}    |    Tensão {V:g} V {ped.freq_hz:g} Hz    |    {n} estágios", fs=3.2, ha="center")
    capa.txt(210, 198, "Força e comando – identificação IEC 81346, símbolos IEC 60617, painel NBR IEC 61439-1/2", fs=2.6, ha="center",
             cor="0.3")
    # --------------------------------------------------------------------------- força: alimentação
    f = P.nova("Força – alimentação geral", "=ALIM")
    S.barramento(f, 185, X1 - 5, Y_BUS)
    xe = col_x(2)
    for k, (xx, nm) in enumerate(zip((xe - S.PF, xe, xe + S.PF), ("L1", "L2", "L3"))):
        f.circ(xx, 205, 0.9, lw=0.25)
        f.txt(xx, 207.5 + 2.6 * k, f"X0:{nm}", fs=1.5, ha="center", cor="0.2")
        f.lin(xx, 205, xx, 160 + k * 0, cam="POTENCIA", lw=0.5)
    f.txt(xe, 219, "Alimentação do cliente – cabo dimensionado pelo cliente", fs=1.8, ha="center", cor="0.3")
    f.txt(xe, 223, f"{V:g} V 3F + PE  {ped.freq_hz:g} Hz", fs=2.2, ha="center", negrito=True)
    y = S.disjuntor_3p(f, xe, 160, "-Q0", f"{pn['geral_A']} A – manopla externa")
    f.txt(xe + 14, 150, "Intertravamento c/ porta + cadeado (NR-10)", fs=1.5, ha="left", cor="0.25")
    for k, xx in enumerate((xe - S.PF, xe, xe + S.PF)):
        f.lin(xx, y, xx, 120, cam="POTENCIA", lw=0.5)
        f.lin(xx, 120, 150 - 2 + k * 0, 120, cam="POTENCIA", lw=0.0)
    # sobe para o barramento
    for k, (xx, yb) in enumerate(zip((xe - S.PF, xe, xe + S.PF), Y_BUS[:3])):
        f.lin(xx, 120 - k * 4, 165 + k * 3, 120 - k * 4, cam="POTENCIA", lw=0.5)
        f.lin(xx, 120, xx, 120 - k * 4, cam="POTENCIA", lw=0.5)
        f.lin(165 + k * 3, 120 - k * 4, 165 + k * 3, yb, cam="POTENCIA", lw=0.5)
        f.lin(165 + k * 3, yb, 185, yb, cam="POTENCIA", lw=0.5)
    f.circ(xe + 3 * S.PF, 205, 0.9, lw=0.25)
    f.txt(xe + 3 * S.PF + 1.5, 207.5, "X0:PE", fs=1.5, cor="0.2")
    f.lin(xe + 3 * S.PF, 205, xe + 3 * S.PF, 100, cam="POTENCIA", lw=0.5)
    f.lin(xe + 3 * S.PF, 100, 162, 100, cam="POTENCIA", lw=0.5)
    f.lin(162, 100, 162, Y_BUS[3], cam="POTENCIA", lw=0.5)
    f.lin(162, Y_BUS[3], 185, Y_BUS[3], cam="POTENCIA", lw=0.5)
    # derivações de comando
    xc = col_x(6)
    for k, xx in enumerate((xc - S.PF, xc, xc + S.PF)):
        S.derivacao(f, xx, Y_BUS[k], 225)
    y = S.disjuntor_3p(f, xc, 225, "-F01", "10 A – relé falta de fase")
    for xx, t in zip((xc - S.PF, xc, xc + S.PF), ("L1", "L2", "L3")):
        f.lin(xx, y, xx, y - 8, lw=0.35)
        f.txt(xx, y - 9, t, fs=1.6, ha="center", va="top")
    f.txt(xc + S.PF + 4, y - 6, P.ref("-K0", "bobina"), fs=1.7, cor="#1f4e8c")
    xt = col_x(8)
    for k, xx in enumerate((xt - S.PF / 2, xt + S.PF / 2)):
        S.derivacao(f, xx, Y_BUS[k], 225)
    y = S.disjuntor_cmd(f, xt - S.PF / 2, 225, "-F02", "10 A", polos=2)
    f.lin(xt - S.PF / 2, y, xt - S.PF / 2, y - 4)
    f.lin(xt + S.PF / 2, y, xt + S.PF / 2, y - 4)
    y2 = S.trafo_cmd(f, xt, y - 4, "-T1", f"{V:g}/220 V {kva} VA")
    f.txt(xt, y2 - 2, "220 V → " , fs=1.7, ha="center", va="top")
    f.txt(xt + 7, y2 - 2, P.ref("-F03", "polo"), fs=1.7, va="top", cor="#1f4e8c")
    # TC do controlador (no alimentador do cliente – fornecimento/instalação na obra)
    S.tc(f, xe - S.PF, 185, "", "")
    f.lin(xe - S.PF - 2, 185, xe - S.PF - 12, 185, lw=0.3)
    f.txt(xe - S.PF - 13, 186.5, "TC do cliente …/5 A", fs=1.7, ha="right", negrito=True)
    f.txt(xe - S.PF - 13, 183, "fase L1, alimentador geral", fs=1.5, ha="right", cor="0.3")
    f.txt(xe - S.PF - 13, 179.5, "S1/S2 → X1:1/2", fs=1.5, ha="right")
    f.txt(xe - S.PF - 13, 176.5, P.ref("-A1", "bobina"), fs=1.5, ha="right", cor="#1f4e8c")
    f.txt(190, 238, "→ barramento continua nas folhas dos estágios", fs=1.8, cor="0.3")
    # --------------------------------------------------------------------------- força: estágios (3 por folha)
    por = 3
    for k0 in range(0, n, por):
        f = P.nova(f"Força – estágios {k0+1} a {min(k0+por, n)}", "=ESTAGIOS")
        S.barramento(f, 30, X1 - 5, Y_BUS)
        f.txt(32, Y_BUS[0] + 3, "← da folha 2 (alimentação)", fs=1.7, cor="0.3")
        for j, i in enumerate(range(k0 + 1, min(k0 + por, n) + 1)):
            e = E[i - 1]
            pr = B.protecao_estagio(ped, e)
            x = 75 + j * 120
            for kk, xx in enumerate(S._polos(x)):
                S.derivacao(f, xx, Y_BUS[kk], 228)
            y = S.seccionadora_fusivel(f, x, 228, f"-Q{i}", f"{pr['chave_A']} A {pr['base']} / gG {pr['fusivel_A']} A")
            for xx in S._polos(x):
                f.lin(xx, y, xx, y - 12, cam="POTENCIA", lw=0.5)
            y -= 12
            f.txt(x - S.PF - 8, y + 2, f"{pr['cabo_mm2']} mm²", fs=1.6, ha="right", rot=90, cor="0.3")
            y = S.contator_3p(f, x, y, f"-K{i}", pr["contator"].split("(")[0].strip())
            for xx in S._polos(x):
                f.lin(xx, y, xx, y - 14, cam="POTENCIA", lw=0.5)
            y -= 14
            if sint:
                for kk, xx in enumerate(S._polos(x)):
                    S.tc(f, xx, y - 4, f"-T1{i}" if kk == 2 else "", "")
                f.txt(x + S.PF + 6, y - 7, f"→ -P{i} " , fs=1.6, cor="#1f4e8c")
                f.txt(x + S.PF + 14, y - 7, P.ref(f"-P{i}", "bobina"), fs=1.6, cor="#1f4e8c")
                for xx in S._polos(x):
                    f.lin(xx, y, xx, y - 10, cam="POTENCIA", lw=0.5)
                y -= 10
            y = S.reator_3f(f, x, y, f"-L{i}", f"{e['L_uH']:.0f} µH / {e['requisitos']['In']:.0f} A",
                            termostato_ref=P.ref(f"-B{i}", "contato"))
            f.txt(x - S.PF - 8, y + 2, f"{pr['cabo_ind_cap_mm2']} mm²", fs=1.6, ha="right", rot=90, cor="0.3")
            for xx in S._polos(x):
                f.lin(xx, y, xx, y - 14, cam="POTENCIA", lw=0.5)
            y -= 14
            y = S.capacitor_3f(f, x, y, f"-C{i}", f"{e['cap'][0]}×{_f(e['cap'][1])} kvar/{e['cap'][2]} V")
            f.txt(x, y - 4, f"Estágio {i}: {_f(e['Q_kvar'])} kvar efetivos", fs=2.2, ha="center", va="top", negrito=True)
            f.txt(x, y - 7.5, f"I60 {e['I60']:.0f} A | I projeto {e['requisitos']['In']:.0f} A | {e['codigo']}", fs=1.7, ha="center", va="top",
                  cor="0.25")
            f.lin(x + S.PF + 3, y + 3, x + S.PF + 8, y + 3, lw=0.35)
            S.terra(f, x + S.PF + 8, y + 3)
    # --------------------------------------------------------------------------- comando: alimentação, segurança, controlador
    f = P.nova("Comando – alimentação 220 V, segurança, controlador e ventilação", "=COMANDO")
    f.lin(X0 + 8, Y_L, X1 - 8, Y_L, lw=0.5)
    f.lin(X0 + 8, Y_N, X1 - 8, Y_N, lw=0.5)
    f.txt(X0 + 6, Y_L, "L", fs=2.2, ha="right", va="center", negrito=True)
    f.txt(X0 + 6, Y_N, "N", fs=2.2, ha="right", va="center", negrito=True)
    x = col_x(1)
    f.txt(x, Y_L + 9, "do -T1 (220 V)", fs=1.6, ha="center", cor="0.3")
    f.txt(x + 10, Y_L + 9, P.ref("-T1", "polo"), fs=1.6, cor="#1f4e8c")
    y = S.disjuntor_cmd(f, x, Y_L + 6, "-F03", "10 A 2P", l=6)
    P.registra("-F03", "polo", f, x)
    P.registra("-T1", "polo", f, x)
    # cadeia de segurança: emergência + relé falta de fase → contator auxiliar "habilita" (rail L1 habilitada)
    x = col_x(2)
    S.derivacao(f, x, Y_L, Y_L - 2)
    y = S.contato(f, x, Y_L - 2, "-S0", nf=True, b=("11", "12"), atuador="emerg", sub="emergência")
    y = S.contato(f, x, y - 2, "-K0", nf=False, b=("11", "14"), sub="falta de fase OK", ref=P.ref("-K0", "bobina"))
    P.registra("-K0", "c11-14", f, x)
    y = S.contato(f, x, y - 2, "-S1", nf=False, b=("13", "14"), atuador="giro", sub="0 – desl. / 1 – auto")
    f.lin(x, y - 2, x, 150)
    f.ponto(x, 150)
    f.lin(x, 150, X1 - 8, 150, lw=0.5)
    f.txt(X1 - 9, 151, "L-HAB (habilitado) → estágios", fs=1.7, ha="right", cor="0.3")
    # relé falta de fase
    x = col_x(3)
    S.controlador(f, x - 8, 230, 16, 14, "-K0", "falta de fase", [(3, "L1"), (8, "L2"), (13, "L3")], [(8, "11-12-14")])
    f.txt(x - 8, 233, P.ref("-F01", "polo"), fs=1.6, cor="#1f4e8c")
    P.registra("-K0", "bobina", f, x)
    # sinaleiro painel energizado
    x = col_x(4)
    S.derivacao(f, x, Y_L, Y_L - 2)
    S.lampada(f, x, Y_L - 2, "-H0", "verde – energizado")
    f.lin(x, Y_L - 14, x, Y_N)
    f.ponto(x, Y_N)
    # controlador
    x = col_x(5)
    S.derivacao(f, x, Y_L, 220)
    S.controlador(f, x - 5, 220, 50, 26, "-A1", BR6000[nr][0].split("(")[0],
                  [(5, "L"), (28, "k"), (38, "l")], [(5, "C"), (10, "N"), (17, "1"), (24, "2"), (31, "3"), (39, "…"), (47, "ALM")])
    P.registra("-A1", "bobina", f, x)
    f.lin(x + 5, 194, x + 5, 150 - 0, lw=0.35, tracejado=True)
    f.txt(x + 6, 196, "comum das saídas ← L-HAB", fs=1.5, va="top", cor="0.3")
    f.lin(x + 10, 194, x + 10, Y_N, lw=0.35)
    f.ponto(x + 10, Y_N)
    f.lin(x + 10, 220, x + 10, 194, lw=0.0)
    xk = x + 23
    S.borne(f, xk, 232, "X1", 1)
    S.borne(f, xk + 10, 232, "X1", 2)
    f.lin(xk, 232, xk, 220, lw=0.35)
    f.lin(xk + 10, 232, xk + 10, 220, lw=0.35)
    f.txt(xk + 5, 236, "TC do cliente (S1/S2)", fs=1.6, ha="center", cor="0.3")
    f.txt(x + 3, 192, "saídas 1…n → bobinas dos estágios (folhas seguintes)", fs=1.5, va="top", cor="0.3")
    # ventilação
    for k in range(1, nvent + 1):
        x = col_x(7) + (k - 1) * 14
        if k == 1:
            S.derivacao(f, x - 7, Y_L, Y_L - 2)
            S.contato(f, x - 7, Y_L - 2, "-B0", nf=False, b=("1", "2"), atuador="termo", sub="35 °C")
            f.lin(x - 7, Y_L - 12, x - 7, 228)
            f.lin(x - 7, 228, col_x(7) + (nvent - 1) * 14, 228)
        f.ponto(x, 228)
        f.lin(x, 228, x, 222)
        S.motor_vent(f, x, 222, f"-M{k}", "")
        f.lin(x, 210, x, Y_N)
        f.ponto(x, Y_N)
    # --------------------------------------------------------------------------- comando: estágios (5 por folha)
    por = 5
    for k0 in range(0, n, por):
        f = P.nova(f"Comando – estágios {k0+1} a {min(k0+por, n)}", "=COMANDO")
        f.lin(X0 + 8, Y_L, X1 - 8, Y_L, lw=0.5)
        f.lin(X0 + 8, Y_N, X1 - 8, Y_N, lw=0.5)
        f.txt(X0 + 7, Y_L + 2.5, "L-HAB", fs=2.0, ha="left", va="bottom", negrito=True)
        f.txt(X0 + 6, Y_N, "N", fs=2.2, ha="right", va="center", negrito=True)
        for j, i in enumerate(range(k0 + 1, min(k0 + por, n) + 1)):
            x = col_x(1 + 2 * j)
            xl = col_x(2 + 2 * j)
            S.derivacao(f, x, Y_L, Y_L - 3)
            y = S.contato(f, x, Y_L - 3, f"-A1", b=("C", str(i)), sub=f"saída {i}", ref=P.ref("-A1", "bobina"))
            y = S.contato(f, x, y - 8, f"-B{i}", nf=True, b=("1", "2"), atuador="termo", sub=f"termostato -L{i}")
            P.registra(f"-B{i}", "contato", f, x)
            P.dispositivo(f"-B{i}", f"Termostato NF do reator -L{i} (integrado ao reator, abre a "
                                    f"{130 if ped.classe == 'F' else 140} °C)", "Electric Service (no reator)", "", 1, grupo=f"Estágio {i}")
            S.borne(f, x, y - 1.5, "X1", 10 + 2 * i - 1)
            if sint:
                y = S.contato(f, x, y - 8, f"-P{i}", nf=True, b=("R1", "R2"), sub="proteção", ref=None)
                P.registra(f"-P{i}", "bobina", f, x)
            y = S.bobina(f, x, y - 10, f"-K{i}", f"{E[i-1]['Q_kvar']:.0f} kvar",
                         contatos=[("polo", "1-2 / 3-4 / 5-6"), (f"c13-14", "13-14")])
            f.lin(x, y, x, Y_N)
            f.ponto(x, Y_N)
            # sinaleiro pelo auxiliar 13-14
            S.derivacao(f, xl, Y_L, Y_L - 3)
            y2 = S.contato(f, xl, Y_L - 3, f"-K{i}", b=("13", "14"), ref=P.ref(f"-K{i}", "bobina"))
            P.registra(f"-K{i}", "c13-14", f, xl)
            y2 = S.lampada(f, xl, y2 - 8, f"-H{i}", "estágio ligado")
            f.lin(xl, y2, xl, Y_N)
            f.ponto(xl, Y_N)
        f.txt(X0 + 10, Y_N - 8, "Termostato do reator em série com a bobina: sobretemperatura desliga o estágio; religa ao esfriar "
                                "(o controlador refaz a manobra respeitando o tempo de descarga do capacitor ≥ 60 s).", fs=1.7, cor="0.3")
    # --------------------------------------------------------------------------- bornes e cabos
    P.bornes += [dict(regua="X0", n=nm, fio="", de="Cabo do cliente", para="-Q0", funcao=f"Alimentação {nm}") for nm in ("L1", "L2", "L3", "PE")]
    P.bornes += [dict(regua="X1", n=1, fio="S1", de="TC do cliente", para="-A1:k", funcao="Corrente p/ controlador"),
                 dict(regua="X1", n=2, fio="S2", de="TC do cliente", para="-A1:l", funcao="Corrente p/ controlador")]
    for i in range(1, n + 1):
        P.bornes += [dict(regua="X1", n=10 + 2 * i - 1, fio=f"{i}T1", de=f"-A1:{i}", para=f"-L{i}:θ1", funcao=f"Termostato reator {i}"),
                     dict(regua="X1", n=10 + 2 * i, fio=f"{i}T2", de=f"-L{i}:θ2", para=f"-K{i}:A1", funcao=f"Termostato reator {i}")]
    pr0 = None
    for i, e in enumerate(E, start=1):
        pr = B.protecao_estagio(ped, e)
        P.cabos += [dict(id=f"W{i}.1", de="Barramento", para=f"-Q{i}", tipo="Cabo flexível 0,6/1 kV 90 °C (HEPR)", secao=pr["cabo_mm2"],
                         n_cond=3, comp_m=1.0, funcao=f"Estágio {i}"),
                    dict(id=f"W{i}.2", de=f"-Q{i}", para=f"-K{i}", tipo="Cabo flexível 0,6/1 kV 90 °C (HEPR)", secao=pr["cabo_mm2"], n_cond=3,
                         comp_m=0.8, funcao=f"Estágio {i}"),
                    dict(id=f"W{i}.3", de=f"-K{i}", para=f"-L{i}", tipo="Cabo flexível 0,6/1 kV 90 °C (HEPR)", secao=pr["cabo_mm2"], n_cond=3,
                         comp_m=1.5, funcao=f"Estágio {i}"),
                    dict(id=f"W{i}.4", de=f"-L{i}", para=f"-C{i}", tipo="Cabo flexível 0,6/1 kV 90 °C (HEPR)", secao=pr["cabo_ind_cap_mm2"],
                         n_cond=3 * e["cap"][0], comp_m=1.2 * e["cap"][0], funcao=f"Estágio {i}")]
    P.cabos += [dict(id="W0.1", de="X0", para="-Q0", tipo="Barramento de cobre / cabo", secao=f"{pn['geral_A']} A", n_cond=3, comp_m=1.0,
                     funcao="Entrada"),
                dict(id="WC", de="Comando", para="diversos", tipo="Cabo flexível 750 V 1,5 mm² (comando) / 2,5 mm² (TC)", secao="1,5 / 2,5",
                     n_cond=0, comp_m=6.0 * n + 20, funcao="Comando – estimado")]
    # demais itens da ET (não aparecem como símbolo)
    P.dispositivo("-X0", "Régua de bornes de força / barramento de entrada com isoladores", "Conexel/Phoenix (equiv.)", "", 1, grupo="Montagem")
    P.dispositivo("-X1", f"Régua de bornes de comando 2,5 mm² ({2 + 2 * n} bornes + 10 % reserva) com terminais", "Conexel/Phoenix (equiv.)",
                  "", 2 + 2 * n + max(2, (2 + 2 * n) // 10), unid="bornes", grupo="Montagem")
    P.dispositivo("=PAINEL", pn["itens"][0][0], "Montadora", "", n_banco, grupo="Montagem")
    P.dispositivo("-W", "Barramento de cobre eletrolítico, isoladores, canaletas, trilhos DIN, terminais, etiquetas, base de capacitores "
                        "e de reatores", "Montadora", "", 1, unid="cj", grupo="Montagem")
    from .. import fabricantes as _FB          # v1.20.0: marca escolhida pelo cliente (reator sempre Electric)
    _FB.aplicar_projeto(P, ped, res)
    return P


def listas_folhas(P, conexoes=None):
    """Folhas de tabela: régua de bornes, lista de cabos, lista de material (no próprio PDF do esquema)."""
    def tabela(titulo, cab, larg, linhas, funcao):
        porf = 38
        for k0 in range(0, max(len(linhas), 1), porf):
            f = P.nova(titulo + (f" ({k0 // porf + 1})" if len(linhas) > porf else ""), funcao, tipo="lista")
            x, y = X0 + 5, Y1 - 10
            h = 5.6
            f.ret(x, y - h, sum(larg), h, lw=0.4, preench="#dde6f3")
            cx = x
            for c, w in zip(cab, larg):
                f.txt(cx + 1.2, y - h + 1.6, c, fs=2.1, negrito=True)
                cx += w
            for r, lin in enumerate(linhas[k0:k0 + porf]):
                yy = y - (r + 2) * h
                f.lin(x, yy, x + sum(larg), yy, lw=0.15, cam="MOLDURA", cor="0.6")
                cx = x
                for v, w in zip(lin, larg):
                    s = str(v)
                    lim = int(w / 1.25)
                    f.txt(cx + 1.2, yy + 1.6, s if len(s) <= lim else s[:lim - 1] + "…", fs=1.9)
                    cx += w
            f.ret(x, y - (min(porf, len(linhas) - k0) + 1) * h, sum(larg), (min(porf, len(linhas) - k0) + 1) * h, lw=0.4)
    tabela("Régua de bornes", ["Régua", "Borne", "Fio", "De", "Para", "Função"], [20, 18, 22, 60, 60, 200],
           [(b["regua"], b["n"], b["fio"], b["de"], b["para"], b["funcao"]) for b in P.bornes], "=BORNES")
    if conexoes:
        tabela("Lista de conexão", ["De (tag:borne)", "Para (tag:borne)", "Fio", "Cor", "Seção (mm²)", "Folha"], [70, 70, 30, 30, 40, 30],
               conexoes, "=CONEXOES")
    tabela("Lista de cabos", ["Cabo", "De", "Para", "Tipo", "Seção (mm²)", "Condutores", "Comprimento (m)", "Função"],
           [18, 34, 34, 120, 26, 24, 32, 90],
           [(c["id"], c["de"], c["para"], c["tipo"], c["secao"], c["n_cond"] or "–", f"{c['comp_m']:.1f}", c["funcao"]) for c in P.cabos], "=CABOS")
    tabela("Lista de peças", ["Item", "Tag", "Descrição", "Fabricante", "Código", "Qtd", "Un.", "Grupo"],
           [12, 20, 185, 50, 38, 14, 14, 47], lista_material(P), "=MATERIAL")


def lista_material(P):
    linhas = []
    ordem = ["Proteção geral", "Controle", "Comando", "Ventilação"] + sorted({d["grupo"] for d in P.disp.values() if d["grupo"].startswith("Estágio")},
                                                                           key=lambda s: int(s.split()[-1])) + ["Montagem"]
    k = 1
    for g in ordem:
        for d in P.disp.values():
            if d["grupo"] == g:
                linhas.append((k, d["tag"], d["descr"], d["fab"], d["cod"] or "a cotar", d["qtd"], d["unid"], g))
                k += 1
    return linhas


def lista_consolidada(P):
    """Material agrupado por descrição (para cotação): soma das quantidades por item igual."""
    acc = {}
    for d in P.disp.values():
        k = (d["descr"].split(" – FORNECIMENTO")[0], d["fab"], d["cod"])
        a = acc.setdefault(k, dict(descr=k[0], fab=k[1], cod=k[2], qtd=0, unid=d["unid"], tags=[]))
        a["qtd"] += d["qtd"]
        a["tags"].append(d["tag"])
    return list(acc.values())


def planilha(P, arq, conexoes=None):
    """Lista de material, bornes e cabos em XLSX (para cotação e para a montadora)."""
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    wb = Workbook()
    az = PatternFill("solid", fgColor="DDE6F3")
    def aba(ws, titulo, cab, linhas, larg):
        ws["A1"] = f"{titulo} – {P.projeto} – {P.cliente} – {P.codigo}"
        ws["A1"].font = Font(bold=True, size=12)
        ws.append([])
        ws.append(cab)
        for c in ws[3]:
            c.font = Font(bold=True)
            c.fill = az
        for l in linhas:
            ws.append(list(l))
        for col, w in zip("ABCDEFGHIJ", larg):
            ws.column_dimensions[col].width = w
    ws = wb.active
    ws.title = "Lista de material"
    aba(ws, "Lista de material (por tag)", ["Item", "Tag", "Descrição", "Fabricante", "Código", "Qtd", "Un.", "Grupo"], lista_material(P),
        (6, 10, 95, 28, 20, 6, 7, 16))
    ws = wb.create_sheet("Cotação (consolidada)")
    aba(ws, "Material consolidado para cotação", ["Item", "Descrição", "Fabricante sugerido", "Código", "Qtd", "Un.", "Tags", "Preço unit. (R$)",
                                                   "Total (R$)"],
        [(k + 1, a["descr"], a["fab"], a["cod"] or "a cotar", a["qtd"], a["unid"], " ".join(a["tags"]), None, f"=E{k+4}*H{k+4}")
         for k, a in enumerate(lista_consolidada(P))], (6, 95, 28, 20, 6, 7, 30, 15, 15))
    ws = wb.create_sheet("Bornes")
    aba(ws, "Régua de bornes", ["Régua", "Borne", "Fio", "De", "Para", "Função"],
        [(b["regua"], b["n"], b["fio"], b["de"], b["para"], b["funcao"]) for b in P.bornes], (8, 8, 8, 22, 22, 40))
    ws = wb.create_sheet("Cabos")
    aba(ws, "Lista de cabos", ["Cabo", "De", "Para", "Tipo", "Seção (mm²)", "Condutores", "Comprimento (m)", "Função"],
        [(c["id"], c["de"], c["para"], c["tipo"], c["secao"], c["n_cond"], c["comp_m"], c["funcao"]) for c in P.cabos],
        (8, 14, 14, 50, 12, 11, 15, 22))
    if conexoes:
        ws = wb.create_sheet("Lista de conexão")
        aba(ws, "Lista de conexão", ["De (tag:borne)", "Para (tag:borne)", "Fio", "Cor", "Seção (mm²)", "Folha"], conexoes, (22, 22, 8, 8, 12, 8))
    wb.save(arq)
    return arq


def indice(P):
    """Escreve o índice de folhas na capa (folha 1)."""
    capa = P.folhas[0]
    y = 180
    capa.txt(60, y + 8, "Índice de folhas", fs=3.2, negrito=True)
    for f in P.folhas:
        capa.txt(60, y, f"{f.n:>3}", fs=2.4)
        capa.txt(72, y, f.titulo, fs=2.4)
        capa.txt(260, y, f"{f.funcao} {f.local}", fs=2.2, cor="0.3")
        y -= 5
        if y < 40:
            break


def gerar(ped, res, pasta, cod, versao, n_banco=1, log=print):
    import os
    P = construir(ped, res, cod, versao, n_banco)
    listas_folhas(P)
    indice(P)
    arq_pdf = P.pdf(os.path.join(pasta, f"Esquema_Eletrico_{cod}.pdf"), png_dir=pasta)
    arq_dxf = P.dxf(os.path.join(pasta, f"Esquema_Eletrico_{cod}.dxf"))
    arq_xlsx = planilha(P, os.path.join(pasta, f"Lista_Material_Bornes_Cabos_{cod}.xlsx"))
    log(f"   Esquema elétrico: {len(P.folhas)} folhas (força, comando, bornes, cabos, material) + DXF + planilha")
    return dict(pdf=arq_pdf, dxf=arq_dxf, xlsx=arq_xlsx, projeto=P)
