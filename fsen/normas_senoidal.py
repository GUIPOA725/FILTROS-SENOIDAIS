"""Filtro senoidal – folha de dados e verificação de normas no MESMO padrão do banco/sintonizado (v1.23.2).

Mesma pasta (01_Engenharia/5_Normas_Folha_de_Dados, cópia em 02_Cliente), mesmo PDF e mesma coluna de Check.
Verificações técnicas = as do dimensionamento (motor: NEMA MG1 Pt.30/31 e IEC TS 60034-25; inversor; capacitor IEC 61071;
térmico) + painel IEC 61439 (isolação calculada; IP/IK/dielétrico/rotina exigidos e comprovados no recebimento).
"""
from __future__ import annotations

import os

from . import checagem as CK
from .normas_banco import pdf_padrao, _linha

# v1.32.0 (REQ-SEN-026, auditoria A&W): ordem importa (o 1º que casar vale) – capacitor ANTES de 'pico' para a tensão de pico no
# capacitor não sair como NEMA MG1 (que é só do MOTOR); THD e queda não são da IEC 61800-2 (critério de projeto / guia de fabricante).
REF = {"capacitor": "IEC 61071", "mancal": "IEC TS 60034-25", "modo comum": "IEC TS 60034-25", "terra": "IEC TS 60034-25",
       "pico": "NEMA MG1 Pt.30/31 (motor)", "dv/dt": "IEC TS 60034-25", "THD": "critério de projeto (fabricantes 3–5 %)",
       "Queda": "guia Danfoss/MTE (4–10 %)", "Derating": "manual do inversor", "Portadora": "projeto",
       "inversor": "dados do inversor", "Térmico": "IEC 60076-6 / 60890", "Ressonância": "projeto", "Ondulação": "projeto",
       "Tensão disponível": "projeto"}


def _clausula(item):
    for k, r in REF.items():
        if k.lower() in item.lower():
            return r
    return "projeto"


def verificacao(proj, arr):
    L = []
    for v in proj.verificacoes:
        c, u = CK.de_verificacao(v.ok, v.critico, v.valor, v.limite)
        L.append([_clausula(v.item), v.item, v.valor, v.limite, CK.texto(c, None), (v.referencia or "")[:90]])
    ped = proj.pedido
    ue = float(ped["tensao_v"])
    dist_ar, escoamento = 5.5, (8.0 if ue <= 500 else 12.5)
    L.append(_linha("61439-1 §10.4", "Distância de isolação no ar (Uimp 6 kV) – barramentos e terminais", "≥ 30 mm (projeto)",
                    f"≥ {dist_ar} mm", CK.check(True, CK.utilizacao(30, dist_ar, "min")), "Tabela 1 + layout"))
    L.append(_linha("61439-1 §10.4", f"Distância de escoamento (Ui {500 if ue <= 500 else 800} V, poluição 3)", "≥ 30 mm (projeto)",
                    f"≥ {escoamento} mm", CK.check(True, CK.utilizacao(30, escoamento, "min")), "Tabela 2 + layout"))
    for cl, it, req in (
            *((("61439-1 §10.3", "Grau de proteção – filtro ABERTO (IP00)", "proteção contra contato (≥ IPXXB) pelo painel do cliente – guia de instalação"),)
              if getattr(proj, "forma", "caixa") == "aberto" else
              (("61439-1 §10.3", "Grau de proteção do invólucro", f"IP{arr.caixa_ip} – IEC 60529"),
               ("61439-1 §10.2.6", "Resistência a impacto", "IK10 – IEC 62262"))),
            ("60076-6", "Ensaio dielétrico do indutor (aplicada 2,5 kV / 1 min) e medição de L e perdas", "laudo do fabricante do indutor"),
            ("61439-1 §10.5", "Continuidade do PE e equipotencialização", "≤ 0,1 Ω"),
            ("61439-1 §11", "Verificação de rotina do painel (fiação, torque, funcionamento, placa)", "laudo + fotos")):
        L.append(_linha(cl, it, "exigido na ET", req, CK.ATENCAO, "comprovar na inspeção de recebimento (FAT)"))
    return L


def folha_dados(proj, arr):
    """v1.32.0: valores garantidos da FONTE ÚNICA documentos.garantias() – igual à folha Word e à proposta."""
    from .documentos import garantias
    from .ind_projeto import protecao_termica_txt
    ped = proj.pedido
    b = proj.banco
    g = garantias(proj)
    L = [
        ("Produto", f"Filtro senoidal {proj.topologia} para saída de inversor – Electric Service"),
        ("Tensão nominal / corrente", f"{ped['tensao_v']:g} V ±10 %, trifásico / {ped['corrente_a']:g} A (40 °C)"),
        ("Frequência de saída / chaveamento", f"0–{max(ped['f_saida_max_hz'], 60):g} Hz / {proj.fs_hz / 1000:g} kHz FIXA"),
        ("Indutância / capacitância", f"{proj.l1.l_uh:.0f} µH/fase / {b.c_y_uf:g} µF/fase Y ({b.ligacao})"),
        ("Frequência de ressonância", f"{proj.fr_hz:.0f} Hz"),
        ("THD de tensão na saída do filtro", g["txt_thd_saida"]),
        ("THD total de tensão no motor", g["txt_thd_total"]),
        ("Tensão de pico / dv/dt no motor", f"{g['txt_vpk']} / {g['txt_dvdt']}"),
        ("Queda de tensão", g["txt_queda"]),
        ("Capacitores", f"{b.n_total} × {b.uf_unit:g} µF {b.v_unit:g} V ({b.fabricante}) em {b.ligacao} – IEC 61071"),
        ("Indutor", f"Electric – {proj.l1.l_uh:.0f} µH, {proj.l1.i_nom_a:.0f} A, L ≥ 90 % até {proj.l1.i_sat_a:.0f} A pico, "
                    f"sistema de isolação classe H (180 °C), projeto por elementos finitos com relatório, {protecao_termica_txt(True)}"),
        ("Perdas", f"≈ {arr.perda_total_w:.0f} W"),
    ]
    if getattr(proj, "forma", "caixa") == "aberto":       # v1.36.0 (REQ-SEN-031)
        from .documentos import _folha_aberto
        L += _folha_aberto(proj, arr)
    else:
        L += [("Invólucro", f"{arr.caixa_l} × {arr.caixa_a} × {arr.caixa_p} mm (L × A × P), IP{arr.caixa_ip}, IK10 (projeto; comprovar no FAT), RAL 7035"),
              ("Refrigeração", f"forçada, {arr.n_ventiladores} ventilador(es) 220 Vca com termostato")]
    L += [
        ("Isolação", "1,1 kV; ensaio 2,5 kV / 1 min"),
        ("Ruído", g["txt_ruido"]),
        ("Normas", g["txt_normas"]),
    ]
    if g["txt_mancal"]:
        L.append(("Mancal do motor", g["txt_mancal"]))
    L.append(("Documentação", "memorial de cálculo, simulação por ponto de operação, dupla checagem ATP, projeto do indutor por elementos "
                              "finitos, esquema elétrico, desenhos, ET aos fornecedores, relatório consolidado"))
    return L


def gerar_pdf(proj, arr, cod, pasta, versao="", log=print):
    os.makedirs(pasta, exist_ok=True)
    L = verificacao(proj, arr)
    arq = pdf_padrao(os.path.join(pasta, f"Folha_de_Dados_e_Verificacao_Normas_{cod}.pdf"), cod, proj.pedido.get("cliente", ""),
                     folha_dados(proj, arr), L, versao)
    log(f"   Folha de dados e verificação de normas: {os.path.basename(arq)}")
    return arq, L
