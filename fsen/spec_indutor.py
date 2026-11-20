"""Especificação técnica DETALHADA do indutor de filtro senoidal – padrão da plataforma para QUALQUER fornecedor.

Filosofia (definida com o usuário em 20/11/2026):
- especificar DESEMPENHO (perdas, temperatura, linearidade, ensaios) e não impor a construção – o fornecedor escolhe como
  chegar lá, mas DECLARA os dados e PROVA em ensaio;
- comparar com a referência de mercado (Schaffner FN5040, REO N CNW 933 – catálogos públicos) para detectar propostas
  subdimensionadas (massa muito baixa / perdas muito altas);
- entreferro: pedir o MEIO-TERMO viável em fábrica de reator comum (2 a 4 entreferros por coluna, bobina afastada da região
  do entreferro, sem fita condutora junto ao entreferro), não exigir "entreferro distribuído";
- protótipo com ensaio de aquecimento antes da série nos indutores grandes, critérios de aceitação/rejeição por escrito.
"""
import math

# Referência de mercado: filtros senoidais completos 380–500 V (o indutor responde pela maior parte das perdas e da massa).
# Fonte: catálogos públicos Schaffner FN5040 (datasheet) e REO N CNW 933 (reo-ag.com), consultados em 20/11/2026.
REF_MERCADO_PADRAO = {
    "Schaffner FN5040": [(4.5, 13, 65, 3.3), (8, 6.9, 80, 4.6), (10, 5.2, 90, 6.1), (17, 3.1, 115, 7.8), (24, 2.4, 150, 14.4),
                         (38, 1.6, 170, 25), (48, 1.1, 260, 33), (62, 0.85, 280, 36), (75, 0.75, 330, 42), (115, 0.5, 500, 68),
                         (180, 0.3, 680, 86), (260, 0.2, 880, 125), (410, 0.13, 1100, 184), (480, 0.11, 1350, 235),
                         (660, 0.14, 2000, 310), (750, 0.12, 2800, 470), (880, 0.11, 3400, 640), (1200, 0.075, 3800, 680)],
    "REO N CNW 933": [(2, 25, 37, 1.15), (4, 12.5, 30, 2.4), (6, 7.5, 40, 2.9), (8, 5.8, 65, 3.0), (10, 5.6, 50, 4.6),
                      (12, 4.7, 60, 6.3), (16, 3.4, 167, 7.8), (20, 2.9, 212, 9.3), (24, 2.4, 85, 11), (30, 1.9, 240, 16),
                      (37, 1.6, 160, 22.5), (48, 1.2, 190, 22), (60, 0.95, 230, 27), (75, 0.79, 225, 34), (90, 0.68, 317, 40),
                      (115, 0.51, 320, 60), (120, 0.5, 340, 58), (150, 0.326, 310, 61), (180, 0.325, 390, 76),
                      (200, 0.293, 550, 79), (250, 0.236, 620, 89), (350, 0.167, 810, 104), (400, 0.146, 980, 106),
                      (450, 0.13, 1210, 181), (500, 0.118, 1420, 208), (600, 0.098, 1590, 227), (700, 0.085, 1570, 258),
                      (750, 0.078, 1750, 259), (800, 0.074, 1910, 297), (900, 0.065, 2360, 315), (1000, 0.059, 2610, 370),
                      (1200, 0.05, 2980, 417)],
}
FONTES_MERCADO = ["Schaffner FN5040/FN5045 – datasheet (TE Connectivity)", "REO AG – Three-phase sine wave filter N CNW 933 (reo-ag.com)"]
DADOS_MERCADO_COMUNS = ("Sobrecarga 1,5 × In por 1 min (1×/h); ensaio dielétrico 2,5–3 kV / 1 min (fase-fase e fase-terra); "
                        "ambiente 40–45 °C sem derating; normas do indutor EN 60076-6 / EN 61558-2-20; chaveamento mínimo "
                        "1,5–3 kHz nos tamanhos grandes")
I_PROTOTIPO_A = 100.0          # a partir desta corrente o protótipo com ensaio de aquecimento é exigido antes da série


def _ref_tabela(cat):
    r = (cat or {}).get("referencias_mercado_filtro")
    if r:
        return {k: [tuple(x) for x in v] for k, v in r.items()}
    return REF_MERCADO_PADRAO


def _interp(tab, i):
    """Interpolação log-log em corrente: devolve (L_mH, perdas_W, massa_kg) ou None fora da faixa."""
    tab = sorted(tab)
    if i < tab[0][0] or i > tab[-1][0]:
        return None
    for a, b in zip(tab, tab[1:]):
        if a[0] <= i <= b[0]:
            if b[0] == a[0]:
                return a[1:]
            t = (math.log(i) - math.log(a[0])) / (math.log(b[0]) - math.log(a[0]))
            return tuple(math.exp(math.log(x) + t * (math.log(y) - math.log(x))) for x, y in zip(a[1:], b[1:]))
    return tab[-1][1:]


def referencia_mercado(In, cat=None):
    """Modelos vizinhos de cada fabricante + faixa interpolada para a corrente In."""
    linhas, interp = [], []
    for fab, tab in _ref_tabela(cat).items():
        tab = sorted(tab)
        abaixo = [x for x in tab if x[0] <= In][-1:]
        acima = [x for x in tab if x[0] > In][:1]
        for x in abaixo + acima:
            linhas.append((fab, x[0], x[1], x[2], x[3]))
        v = _interp(tab, In)
        if v:
            interp.append((fab,) + tuple(v))
    faixa = None
    if interp:
        faixa = dict(l_mh=(min(x[1] for x in interp), max(x[1] for x in interp)),
                     perdas_w=(min(x[2] for x in interp), max(x[2] for x in interp)),
                     massa_kg=(min(x[3] for x in interp), max(x[3] for x in interp)))
    return linhas, interp, faixa


def requisitos(L, proj, arr, cat, ped):
    """Números-chave da especificação (usados na ET e no e-mail)."""
    In = float(L.i_nom_a)
    rpp = float(L.ripple_pp_a or 0)
    ipk = float(L.i_pico_a or In * math.sqrt(2))
    ipk_sat = max(float(L.i_sat_a or 0), ipk * 1.1)
    ipk_sobrec = 1.5 * In * math.sqrt(2) + rpp / 2
    fs = float(L.f_chav_hz or proj.fs_hz)
    fmx = max(float(ped.get("f_saida_max_hz") or 60), 60.0)
    v = float(ped["tensao_v"])
    vdc = v * 1.35 * 1.1
    linhas, interp, faixa = referencia_mercado(In, cat)
    perdas_plat = float(L.perdas_w or 0)
    # meta de perdas: o menor entre a estimativa da plataforma e o teto da referência de mercado (filtro completo)
    perdas_meta = min(perdas_plat, faixa["perdas_w"][1]) if (faixa and perdas_plat) else perdas_plat
    return dict(perdas_meta=perdas_meta, In=In, rpp=rpp, rrms=float(L.ripple_rms_a or 0), ifund=float(L.i_fund_a or In), ipk=ipk, ipk_sat=ipk_sat,
                ipk_sobrec=ipk_sobrec, fs=fs, fmx=fmx, v=v, vdc=vdc, l_uh=float(L.l_uh), perdas=float(L.perdas_w or 0),
                massa=float(L.massa_kg or 0), prototipo=In >= I_PROTOTIPO_A, ref_linhas=linhas, ref_interp=interp,
                ref_faixa=faixa, ripple_rel=(rpp / (2 * ipk) * 100 if ipk else 0))


def _classe(cat):
    c = cat.get("termico", {}).get("classe_indutor_c", 155)
    e = cat.get("termico", {}).get("elevacao_indutor_k", 100)
    return ({130: "B", 155: "F", 180: "H", 200: "N", 220: "R"}.get(int(c), "?"), int(c), int(e))


def grafico_forma_onda(proj, cat, arquivo_png):
    """Figura para o fornecedor: corrente no indutor (fundamental + ondulação) e tensão PWM sobre ele.
    Mostra que o indutor NÃO trabalha com 60 Hz senoidal puro."""
    import os
    import numpy as np
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from .dimensionamento import avaliar, pontos_operacao
    from .modelos import Pedido
    from .simulacao import simular
    ped = Pedido.from_dict(proj.pedido) if isinstance(proj.pedido, dict) else proj.pedido
    b = proj.banco
    cap = next((c for c in cat["capacitores"] if c["id"] == b.cap_id), None) or dict(id=b.cap_id, uf=b.uf_unit, v_ac=b.v_unit, preco=0)
    vdc = 1.35 * ped.tensao_v
    L2 = proj.l2.l_uh * 1e-6 if proj.l2 else 0.0
    p, _, _ = avaliar(ped, cat, proj.l1.l_uh * 1e-6, cap, (b.ligacao, b.n_por_ramo, b.c_y_uf * 1e-6), proj.fs_hz, vdc,
                      L2=L2, pts_por_portadora=24)
    op = pontos_operacao(ped, vdc, proj.fs_hz)[0]["op"]
    r = simular(p, op, pts_por_portadora=120, ciclos_analise=2)
    t = np.asarray(r.t) * 1e3
    i1 = np.asarray(r.i1)
    vl = np.asarray(r.u_ab) - np.asarray(r.vc_ab)             # tensão sobre os dois indutores entre fases (La − Lb)
    n = len(i1)
    F = np.fft.rfft(i1) / n
    k = 2                                                     # 2 ciclos na janela → fundamental no bin 2
    fund = 2 * np.abs(F[k]) * np.cos(2 * np.pi * op.f1 * np.asarray(r.t) + np.angle(F[k]))
    fig, ax = plt.subplots(3, 1, figsize=(11, 9))
    ax[0].plot(t, i1, color="#c0392b", lw=0.8, label="Corrente REAL no indutor (fundamental + ondulação PWM)")
    ax[0].plot(t, fund, color="#1b4f9c", lw=1.2, ls="--", label=f"Só a fundamental ({op.f1:g} Hz) – o que um reator de linha vê")
    ax[0].set_ylabel("Corrente fase A (A)")
    ax[0].set_title(f"Indutor do filtro senoidal – {op.f1:g} Hz de saída, chaveamento {proj.fs_hz / 1000:g} kHz", fontsize=11)
    ax[0].legend(loc="lower left", fontsize=8, framealpha=0.95)
    T1 = 1e3 / op.f1
    j = int(np.argmax(i1[: int(n / 2)]))
    t0 = max(0.0, t[j] - 0.5)
    sel = (t >= t0) & (t <= t0 + 1.0)
    ax[1].plot(t[sel], i1[sel], color="#c0392b", lw=1.0)
    ax[1].set_ylabel("Corrente (A) – zoom 1 ms")
    ax[1].set_title(f"Zoom de 1 ms no pico: ondulação de alta frequência (até {proj.l1.ripple_pp_a:.0f} A p-p) a "
                    f"{proj.fs_hz / 1000:g} kHz e múltiplos", fontsize=10)
    ax[2].plot(t[sel], vl[sel], color="#6c3483", lw=0.8)
    ax[2].set_ylabel("Tensão sobre os indutores\nentre fases (V)")
    ax[2].set_xlabel("t (ms)")
    ax[2].set_title(f"O indutor recebe PULSOS retangulares de tensão a {proj.fs_hz / 1000:g} kHz (bordas de kV/µs), "
                    "não uma senoide de 60 Hz", fontsize=10)
    for a_ in ax:
        a_.grid(alpha=0.3)
    fig.tight_layout()
    os.makedirs(os.path.dirname(arquivo_png) or ".", exist_ok=True)
    fig.savefig(arquivo_png, dpi=130)
    plt.close(fig)
    return arquivo_png


def escrever_et(d, L, proj, arr, cat, ped, q, _kv, _tabela, _bullets, _f, figura=None):
    """Escreve no documento `d` (python-docx) a ET completa do indutor – cada requisito com o PORQUÊ."""
    from docx.shared import Cm
    R = requisitos(L, proj, arr, cat, ped)
    cl, cc, ce = _classe(cat)
    amb = cat.get("projeto_padrao", {}).get("amb_max_c", 40)
    d.add_heading("1. Aplicação", 1)
    d.add_paragraph(
        f"Indutor série trifásico de filtro senoidal LC instalado na saída de inversor PWM ({ped.get('inversor') or 'a definir'}), "
        f"frequência de chaveamento {R['fs'] / 1000:g} kHz, alimentando motor de indução "
        f"{ped.get('motor_cv') or ''} cv / {R['v']:g} V.")
    d.add_paragraph("Esta especificação define DESEMPENHO. A construção (material, número de entreferros, tipo de condutor) "
                    "fica a critério do fabricante, desde que os valores abaixo sejam DECLARADOS na proposta e COMPROVADOS em ensaio. "
                    "Cada requisito vem com o motivo, para que o projeto do indutor considere o uso real.")

    d.add_heading("2. Por que este indutor NÃO é um reator de 60 Hz", 1)
    _bullets(d, [
        f"A tensão que o indutor recebe NÃO é senoidal: o inversor aplica pulsos retangulares de até ≈ {R['vdc']:.0f} V, "
        f"{R['fs'] / 1000:g} mil vezes por segundo, com bordas muito rápidas (kV/µs). A senoide só aparece DEPOIS do filtro, no motor.",
        f"A corrente é a fundamental (0–{R['fmx']:g} Hz, {R['ifund']:.0f} A) MAIS uma ondulação triangular de "
        f"{R['rpp']:.0f} A pico a pico a {R['fs'] / 1000:g} kHz ({R['ripple_rel']:.0f} % do pico). Um reator de linha praticamente "
        "não tem essa componente.",
        "A ondulação de alta frequência produz no núcleo perdas por histerese e correntes parasitas que crescem com a frequência; "
        "chapa grossa ou de perdas altas, adequada a 60 Hz, esquenta muito mais.",
        "No enrolamento, a alta frequência concentra a corrente na superfície do condutor (efeito pelicular e de proximidade): "
        "condutores grossos e fitas largas têm resistência efetiva muito maior que a medida em corrente contínua.",
        "No entreferro, parte do fluxo de alta frequência se espalha para fora do núcleo e atravessa o condutor próximo, gerando "
        "pontos quentes localizados – é a causa mais comum de falha desse tipo de indutor.",
        "A frequência fundamental VARIA (o motor muda de velocidade): o indutor precisa funcionar de 0 a "
        f"{R['fmx']:g} Hz, e em baixa frequência a ondulação relativa é ainda maior.",
        "Consequência: projetar só pela corrente de 60 Hz subdimensiona o indutor. O ensaio de aquecimento deve, de preferência, "
        "ser feito com inversor."])
    if figura:
        try:
            d.add_picture(figura, width=Cm(16.5))
            d.add_paragraph("Figura – forma de onda simulada pela plataforma para este projeto: corrente no indutor (com a "
                            "fundamental tracejada para comparação), zoom da ondulação e tensão PWM aplicada ao indutor.")
        except Exception:
            pass

    d.add_heading("3. Características elétricas exigidas – e por quê", 1)
    _tabela(d, ["Item", "Valor exigido", "Por quê"], [
        ("Tipo", "Trifásico a seco, núcleo de ferro de 3 colunas (ou 3 monofásicos), uso interno em painel",
         "Montagem no armário do filtro, com ventilação forçada."),
        ("Tensão", f"{R['v']:g} V ±10 % fase-fase PWM; barramento CC até ≈ {R['vdc']:.0f} V",
         "O pico dos pulsos é a tensão do barramento CC, não o valor eficaz."),
        ("Indutância", f"{R['l_uh']:.1f} µH/fase ±5 % na In; desequilíbrio ≤ 3 %",
         "Define a frequência de ressonância e a ondulação; desequilíbrio gera tensão desigual no motor."),
        ("Corrente nominal térmica", f"{R['In']:.0f} A RMS contínua, ambiente {amb:g} °C",
         "Já inclui a parcela RMS da ondulação de alta frequência."),
        ("Composição da corrente", f"{R['ifund']:.0f} A fundamental (0–{R['fmx']:g} Hz) + {R['rrms']:.0f} A RMS / {R['rpp']:.0f} A p-p "
                                   f"em {R['fs'] / 1000:g} kHz",
         "As perdas de alta frequência dependem da ondulação, não da corrente de 60 Hz."),
        ("Pico em operação", f"{R['ipk']:.0f} A", "Pico da fundamental somado à metade da ondulação."),
        ("Linearidade", f"L ≥ 90 % até {R['ipk_sat']:.0f} A pico; L ≥ 70 % até {R['ipk_sobrec']:.0f} A pico (sobrecarga)",
         "Se o núcleo saturar, a indutância cai, a ondulação dispara e o inversor pode desarmar por sobrecorrente."),
        ("Sobrecarga", "1,5 × In por 60 s, 1×/h", "Partida e regime transitório do motor (prática dos fabricantes de filtro)."),
        ("Frequência fundamental", f"0–{R['fmx']:g} Hz", "Velocidade variável; em baixa frequência a ondulação relativa é maior."),
        ("Chaveamento", f"{R['fs'] / 1000:g} kHz nominal (inversor travado em ≥ {R['fs'] / 1000:g} kHz); informar perdas a 2/3 desse valor",
         "Abaixo da frequência de projeto a ondulação aumenta e o indutor esquenta mais."),
        ("dv/dt", "Isolação reforçada entre espiras/camadas das primeiras espiras e bobina-núcleo",
         "As bordas dos pulsos (kV/µs) concentram tensão nas primeiras espiras do lado do inversor."),
        ("Isolação / dielétrico", "1,1 kV; 2,5 kV fase-fase e 3 kV fase-terra, 1 min", "Padrão dos fabricantes de filtro senoidal."),
        ("Classe térmica", f"{cl} ({cc} °C) efetivamente fornecida; elevação média ≤ {ce} K; classe no desenho e na placa",
         "O estudo térmico do filtro foi feito com esta classe; classe menor reduz a vida útil."),
        ("Impregnação", "VPI ou imersão a vácuo", "Fixa espiras e chapas: em alta frequência, partes soltas vibram, fazem ruído e se desgastam."),
        ("Proteção térmica", "Termostato NF ou PTC na coluna central, 2 fios em borne (TH1/TH2)",
         "Permite desligar o inversor antes de danificar a isolação se a ventilação falhar."),
        ("Perdas", f"≤ {_f(R['perdas_meta'], 0)} W totais (desejado); máximo admissível {_f(R['perdas'], 0)} W",
         "Dimensionam a ventilação do painel; a meta segue a referência de mercado (item 8)."),
        ("Refrigeração", "Ventilação forçada de baixo para cima; informar a vazão considerada", "Coerência com o painel."),
        ("Terminais", "Barras/terminais para os cabos; U1/V1/W1 (inversor) – U2/V2/W2 (motor); aterramento do núcleo",
         "O lado do inversor recebe os pulsos – precisa ser identificado."),
        ("Espaço", f"até {arr.caixa_l - 150}×700×{arr.caixa_p - 150} mm (L×A×P); estimativa {L.dim_mm[0]}×{L.dim_mm[1]}×{L.dim_mm[2]} mm, "
                   f"≈ {R['massa']:.0f} kg", "Armário padrão do filtro."),
        ("Placa", "Fabricante, modelo, nº de série, L, In, chaveamento, classe, perdas, massa, data", "Rastreabilidade e conferência."),
        ("Normas", "IEC 60076-6 / IEC 61558-2-20 / NBR 5356; IEC 60085", "Normas de reatores usadas pelos fabricantes de filtro."),
        ("Quantidade", f"{q} peça(s)", "")], [3.6, 7.0, 6.4], 8)

    d.add_heading("4. Construção recomendada – orientação e motivo (não é imposição)", 1)
    _bullets(d, [
        "Núcleo de chapa de aço-silício de baixas perdas e espessura reduzida (0,23–0,30 mm) ou material próprio para alta frequência. "
        "POR QUÊ: as perdas por correntes parasitas no núcleo crescem com o quadrado da espessura da chapa e com a frequência – "
        "a ondulação de alta frequência torna a escolha da chapa decisiva. Informar material, espessura e indução de trabalho.",
        "Entreferro em 2 a 4 partes menores por coluna (coluna dividida em blocos com espaçador de epóxi/cerâmica, ou entreferros "
        "nas duas junções coluna-travessa) em vez de um único entreferro grande. Entreferro distribuído contínuo NÃO é exigido. "
        "POR QUÊ: o fluxo que se espalha para fora do núcleo cresce com o tamanho de cada entreferro; vários pequenos espalham "
        "muito menos fluxo que um grande.",
        "Bobina afastada da região do entreferro (ou entreferros posicionados fora da altura da bobina). POR QUÊ: o fluxo espraiado "
        "se estende cerca do comprimento do entreferro para fora do núcleo; o condutor dentro dessa região é atravessado por campo "
        "de alta frequência e aquece localmente (ponto quente que não aparece na medição de resistência).",
        "Evitar fita (folha) condutora atravessando a região do entreferro; preferir condutor retangular ou fios em paralelo nessa "
        "região. POR QUÊ: o campo espraiado incide perpendicularmente à face larga da fita e induz correntes parasitas elevadas.",
        "Dutos de ventilação alinhados com o fluxo de ar vertical do painel. POR QUÊ: a ventilação forçada é parte do projeto térmico do filtro.",
        "Núcleo prensado e impregnado. POR QUÊ: em alta frequência as forças magnéticas fazem chapas e espiras soltas vibrarem "
        "(ruído audível e desgaste da isolação)."])

    d.add_heading("5. Dados que o fornecedor deve DECLARAR na proposta", 1)
    _tabela(d, ["Dado", "Unidade", "Por quê / valor declarado"], [
        ("Material e espessura da chapa; indução de trabalho (B pico)", "– / T", "Avaliar perdas de alta frequência e saturação"),
        ("Número e posição dos entreferros por coluna", "–", "Avaliar o aquecimento por fluxo espraiado"),
        ("Material do enrolamento (Cu/Al) e tipo de condutor", "–", "Avaliar perdas por efeito pelicular/proximidade"),
        ("Indutância por fase na In e a 50 % In", "µH", "Conferir valor e linearidade"),
        ("Curva L × I até a corrente de sobrecarga", "tabela", "Comprovar que não satura"),
        ("Resistência por fase a 20 °C", "mΩ", "Perdas no cobre e ensaio de aquecimento"),
        ("Perdas no cobre a 60 Hz e In", "W", "Parcela de baixa frequência"),
        (f"Perdas núcleo + cobre em alta frequência ({R['fs'] / 1000:g} kHz, {R['rpp']:.0f} A p-p)", "W", "Parcela que um reator de linha não tem"),
        ("Perdas totais garantidas", "W", "Projeto da ventilação do painel"),
        ("Elevação média / ponto mais quente", "K / °C", "Conferir com a classe térmica"),
        ("Classe térmica do sistema de isolação", "°C", "Conferir com o pedido"),
        ("Massa, dimensões e furação (desenho)", "kg / mm", "Montagem e comparação com o mercado"),
        ("Prazo, preço, garantia", "–", "")], [7.5, 2.5, 7])

    d.add_heading("6. Ensaios", 1)
    d.add_paragraph("Rotina (todas as peças, relatório individual por nº de série):")
    _bullets(d, ["Indutância por fase na corrente nominal e desequilíbrio (≤ 3 %).", "Resistência ôhmica dos enrolamentos.",
                 "Tensão aplicada: 2,5 kV fase-fase e 3 kV fase-terra, 1 min.", "Resistência de isolamento.",
                 "Verificação dimensional, de terminais, placa e proteção térmica."])
    d.add_paragraph("Tipo (1 peça – protótipo ou primeira peça da série):")
    _bullets(d, ["Curva L × I até a corrente de sobrecarga. POR QUÊ: comprova a linearidade.",
                 "Medição de perdas a 60 Hz e, quando possível, com alta frequência/inversor. POR QUÊ: a perda de 60 Hz sozinha "
                 "subestima o aquecimento real.",
                 "Elevação de temperatura na In até estabilizar (Δθ < 1 K/h), de preferência alimentado por inversor na frequência de "
                 "chaveamento especificada; temperatura do enrolamento por variação de resistência. POR QUÊ: é o único ensaio que "
                 "mostra o efeito da ondulação.",
                 "Termografia ao final do aquecimento. POR QUÊ: revela pontos quentes na altura dos entreferros, que a medição por "
                 "resistência (média) não mostra."])

    d.add_heading("7. Protótipo e critérios de aceitação", 1)
    if R["prototipo"]:
        d.add_paragraph(f"Para esta corrente ({R['In']:.0f} A ≥ {I_PROTOTIPO_A:.0f} A) é exigida 1 peça protótipo com os ensaios de "
                        "tipo do item 6 ANTES da liberação da série. POR QUÊ: em indutores grandes o efeito da alta frequência é "
                        "maior e um erro de projeto só aparece no ensaio de aquecimento.")
    else:
        d.add_paragraph("Aceita-se relatório de ensaio de tipo de produto similar (mesma família, corrente e chaveamento próximos); "
                        "na falta dele, ensaio de tipo na primeira peça.")
    _bullets(d, [f"Indutância {R['l_uh']:.1f} µH ±5 % na In; desequilíbrio ≤ 3 %.",
                 f"L ≥ 90 % a {R['ipk_sat']:.0f} A de pico e ≥ 70 % a {R['ipk_sobrec']:.0f} A de pico.",
                 "Perdas medidas ≤ perdas garantidas (+10 %).",
                 f"Elevação dentro da classe {cl} ({ce} K médio); nenhum ponto da termografia acima do limite da classe "
                 f"(ambiente corrigido para {amb:g} °C).",
                 "Ensaio dielétrico sem descarga.",
                 "Classe térmica, material do enrolamento e dados de placa conforme a proposta – divergência entre pedido e "
                 "desenho/placa é motivo de rejeição.",
                 "Não conformidade: substituição/correção por conta do fornecedor, sem custo, mantida a garantia."])

    d.add_heading("8. Referência de mercado (catálogos públicos)", 1)
    d.add_paragraph("Valores de filtros senoidais COMPLETOS de fabricantes especializados (o indutor responde pela maior parte das "
                    "perdas e da massa). POR QUÊ: massa muito ABAIXO ou perdas muito ACIMA desta faixa indicam indutor "
                    "subdimensionado para a ondulação de alta frequência.")
    if R["ref_linhas"]:
        _tabela(d, ["Fabricante / modelo", "In (A)", "L (mH)", "Perdas (W)", "Massa (kg)"],
                [(a, f"{b:g}", f"{c:g}", f"{e:g}", f"{m:g}") for a, b, c, e, m in R["ref_linhas"]], [5.5, 2.5, 2.5, 3, 3])
    if R["ref_faixa"]:
        fx = R["ref_faixa"]
        d.add_paragraph(f"Faixa interpolada para {R['In']:.0f} A: L {fx['l_mh'][0] * 1000:.0f}–{fx['l_mh'][1] * 1000:.0f} µH, perdas "
                        f"{fx['perdas_w'][0]:.0f}–{fx['perdas_w'][1]:.0f} W (filtro completo), massa "
                        f"{fx['massa_kg'][0]:.0f}–{fx['massa_kg'][1]:.0f} kg. Este projeto: L {R['l_uh']:.0f} µH, ondulação "
                        f"{R['rpp']:.0f} A p-p.")
        if R["l_uh"] < 0.85 * fx["l_mh"][0] * 1000:
            d.add_paragraph("Atenção: a indutância deste projeto está abaixo da faixa de mercado – a ondulação de alta frequência é "
                            "maior que a usual e o projeto térmico do indutor merece atenção redobrada (perdas e entreferro).")
    else:
        d.add_paragraph("Corrente fora da faixa dos catálogos de referência.")
    d.add_paragraph("Requisitos comuns nesses catálogos: " + DADOS_MERCADO_COMUNS + ".")
    d.add_paragraph("Fontes: " + "; ".join(FONTES_MERCADO) + ".")
    return R


def corpo_email(L, proj, arr, cat, ped, q, tag, ola, extenso, ref_fornecedor=None):
    R = requisitos(L, proj, arr, cat, ped)
    cl, cc, ce = _classe(cat)
    fx = R["ref_faixa"]
    ref = (f"\n5) REFERÊNCIA DE MERCADO (catálogos Schaffner FN5040 / REO N CNW 933)\n"
           f"Filtros completos na faixa de {R['In']:.0f} A: perdas {fx['perdas_w'][0]:.0f}–{fx['perdas_w'][1]:.0f} W e massa "
           f"{fx['massa_kg'][0]:.0f}–{fx['massa_kg'][1]:.0f} kg. Se a proposta de vocês ficar muito abaixo na massa ou acima nas "
           "perdas, peço que expliquem como a ondulação de alta frequência foi tratada.\n") if fx else ""
    prot = (f"\n4) PROTÓTIPO\nPor ser um indutor de {R['In']:.0f} A, preciso de 1 peça protótipo com os ensaios de tipo antes de liberar a "
            "série. A série só é liberada após a aprovação do relatório.\n") if R["prototipo"] else \
           "\n4) ENSAIO DE TIPO\nAceito relatório de ensaio de tipo de produto similar; na falta dele, ensaio na primeira peça.\n"
    return (
        f"{ola}\n\n"
        f"Gostaria de uma proposta para {q} ({extenso(q)}) indutor(es) trifásico(s) para filtro senoidal na saída de inversor "
        f"{ped.get('inversor') or ''}, conforme a especificação técnica em anexo (resumo abaixo). Além do preço, preciso que a "
        "proposta traga os dados técnicos declarados e os ensaios indicados, porque o filtro segue com relatório técnico para o cliente.\n\n"
        "IMPORTANTE – POR QUE NÃO É UM REATOR DE 60 Hz\n"
        f"O indutor fica entre o inversor e os capacitores do filtro. Ele recebe PULSOS de tensão de até ≈ {R['vdc']:.0f} V a "
        f"{R['fs'] / 1000:g} kHz (bordas de kV/µs), não uma senoide; a corrente é a fundamental de 0–{R['fmx']:g} Hz MAIS uma "
        f"ondulação triangular de {R['rpp']:.0f} A pico a pico a {R['fs'] / 1000:g} kHz. Essa ondulação gera perdas no núcleo, no "
        "enrolamento (efeito pelicular/proximidade) e aquecimento perto do entreferro que um reator de linha não tem. Por isso "
        "pedimos os dados de alta frequência e o ensaio de aquecimento abaixo. A ET em anexo tem a forma de onda simulada e o "
        "motivo de cada requisito.\n\n"
        f"1) ESPECIFICAÇÃO – INDUTOR {tag}\n"
        "- Tipo: trifásico a seco, núcleo de ferro de 3 colunas, uso interno em painel ventilado\n"
        f"- Tensão: {R['v']:g} V (±10 %) fase-fase PWM; barramento CC até ≈ {R['vdc']:.0f} V\n"
        f"- L: {R['l_uh']:.0f} µH por fase ±5 % na corrente nominal; desequilíbrio entre fases ≤ 3 %\n"
        f"- Corrente nominal: {R['In']:.0f} A RMS (fundamental {R['ifund']:.0f} A, 0–{R['fmx']:g} Hz)\n"
        f"- Ondulação de alta frequência sobreposta: {R['rpp']:.0f} A pico a pico ({R['rrms']:.0f} A RMS) a {R['fs'] / 1000:g} kHz\n"
        f"- Pico em operação: {R['ipk']:.0f} A – L ≥ 90 % do nominal até {R['ipk_sat']:.0f} A e ≥ 70 % até {R['ipk_sobrec']:.0f} A "
        "(sobrecarga), sem saturação\n"
        "- Sobrecarga: 1,5 × In por 1 minuto, 1 vez por hora\n"
        f"- Chaveamento: {R['fs'] / 1000:g} kHz nominal\n"
        f"- Classe térmica: {cl} ({cc} °C) efetivamente fornecida (constar no desenho e na placa), elevação ≤ {ce} K; impregnação VPI\n"
        "- Isolação 1,1 kV; ensaio aplicado 2,5 kV fase-fase / 3 kV fase-terra, 1 min; isolação reforçada nas primeiras espiras (dv/dt)\n"
        "- Proteção térmica: termostato ou PTC no enrolamento, 2 fios em borne\n"
        f"- Perdas totais desejadas: ≤ {R['perdas_meta']:.0f} W (60 Hz + ondulação); máximo admissível {R['perdas']:.0f} W\n"
        f"- Espaço: até {arr.caixa_l - 150} × 700 × {arr.caixa_p - 150} mm (L × A × P), painel com ventilação forçada de baixo para cima\n"
        "- Placa: L, In, frequência de chaveamento, classe, perdas, massa, nº de série\n\n"
        "2) DADOS QUE PRECISO QUE VOCÊS DECLAREM\n"
        "- Indução de trabalho (motivo: margem contra saturação no pico)\n"
        "- Quantos entreferros por coluna e onde ficam em relação à bobina. Não exigimos entreferro distribuído: 2 a 4 por coluna e "
        "a bobina afastada da região do entreferro já atendem (motivo: o fluxo de alta frequência que se espalha no entreferro "
        "aquece o condutor que estiver perto)\n"
        "- Material do enrolamento (cobre/alumínio) e tipo de condutor; evitar fita atravessando a região do entreferro (motivo: "
        "o campo espraiado bate na face larga da fita e gera correntes parasitas)\n"
        "- Material e espessura da chapa (motivo: as perdas de alta frequência no núcleo crescem com a espessura)\n"
        "- Perdas: cobre 60 Hz, cobre em alta frequência e núcleo com a ondulação; perdas totais garantidas\n"
        "- Elevação de temperatura (média e ponto mais quente) e curva L × I\n"
        "- Massa, dimensões e desenho com furação\n\n"
        "3) ENSAIOS\n"
        "- Rotina (todas as peças): L por fase na In, desequilíbrio, resistência, tensão aplicada, isolamento – relatório por nº de série\n"
        "- Tipo: curva L × I, medição de perdas, elevação de temperatura até estabilizar (de preferência com inversor) e termografia\n"
        f"{prot}{ref}\n"
        "Critério de aceitação: valores medidos dentro do declarado; divergência entre pedido e desenho/placa (classe, material) é "
        "motivo de rejeição, com troca por conta do fornecedor.\n\n"
        "Se for melhor, podemos fazer uma call rápida com a engenharia de vocês para alinhar a parte de alta frequência."
        + (f"\n\nReferência: {ref_fornecedor}." if ref_fornecedor else ""))
