"""Geração de documentos Word (.docx), e-mails e planilha de custos."""
from __future__ import annotations
import math
import os
import datetime as _dt
from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

from .desenhos import proj_codigo

AZUL = RGBColor(0x1F, 0x3A, 0x5F)
HOJE = _dt.date.today()


# ------------------------------------------------------------------ utilitários
def _novo(titulo, subtitulo, proj, cat):
    d = Document()
    sec = d.sections[0]
    sec.page_height, sec.page_width = Cm(29.7), Cm(21.0)
    sec.left_margin = sec.right_margin = Cm(2.0)
    sec.top_margin, sec.bottom_margin = Cm(2.0), Cm(1.8)
    st = d.styles["Normal"]
    st.font.name = "Calibri"
    st.font.size = Pt(11)
    st.element.rPr.rFonts.set(qn("w:eastAsia"), "Calibri")
    for nome, tam in (("Heading 1", 14), ("Heading 2", 12), ("Heading 3", 11)):
        h = d.styles[nome]
        h.font.name = "Calibri"
        h.font.size = Pt(tam)
        h.font.color.rgb = AZUL
        h.font.bold = True
    emp = cat["empresa"]
    hp = sec.header.paragraphs[0]
    hp.text = f"{emp['nome']} – Engenharia  |  {proj_codigo(proj)}"
    hp.runs[0].font.size = Pt(8)
    hp.runs[0].font.color.rgb = RGBColor(0x55, 0x55, 0x55)
    fp = sec.footer.paragraphs[0]
    fp.text = f"{emp['nome']} • {emp['email']} • {emp['telefone']} • {emp['cidade']}"
    fp.runs[0].font.size = Pt(8)
    fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p = d.add_paragraph()
    r = p.add_run(titulo)
    r.bold = True
    r.font.size = Pt(18)
    r.font.color.rgb = AZUL
    if subtitulo:
        p2 = d.add_paragraph()
        r2 = p2.add_run(subtitulo)
        r2.font.size = Pt(11)
        r2.font.color.rgb = RGBColor(0x55, 0x55, 0x55)
    d.add_paragraph(f"Documento {proj_codigo(proj)} • Emissão {HOJE:%d/%m/%Y} • Rev. 00")
    return d


def _sombra(cel, cor="1F3A5F"):
    tcPr = cel._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), cor)
    tcPr.append(shd)


def _tabela(d, cab, linhas, larguras=None, tam=9):
    t = d.add_table(rows=1, cols=len(cab))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, c in enumerate(cab):
        cel = t.rows[0].cells[i]
        cel.text = ""
        r = cel.paragraphs[0].add_run(str(c))
        r.bold = True
        r.font.size = Pt(tam)
        r.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        _sombra(cel)
    for k, lin in enumerate(linhas):
        row = t.add_row().cells
        for i, v in enumerate(lin):
            row[i].text = ""
            r = row[i].paragraphs[0].add_run("" if v is None else str(v))
            r.font.size = Pt(tam)
            if k % 2:
                _sombra(row[i], "EEF2F7")
    if larguras:
        t.autofit = False
        grid = t._tbl.tblGrid
        for i, gc in enumerate(grid.findall(qn("w:gridCol"))):
            if i < len(larguras):
                gc.set(qn("w:w"), str(int(larguras[i] * 567)))
        for row in t.rows:
            for i, w in enumerate(larguras):
                row.cells[i].width = Cm(w)
    d.add_paragraph()
    return t


def _kv(d, pares, tam=10):
    return _tabela(d, ["Item", "Valor"], pares, [6.5, 10.5], tam)


def _img(d, caminho, largura=16.5, legenda=None):
    if caminho and os.path.exists(caminho):
        d.add_picture(caminho, width=Cm(largura))
        d.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
        if legenda:
            p = d.add_paragraph(legenda)
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.runs[0].italic = True
            p.runs[0].font.size = Pt(9)


def _bullets(d, itens):
    for i in itens:
        d.add_paragraph(i, style="List Bullet")


def _f(x, n=1):
    try:
        return f"{float(x):,.{n}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return str(x)


def _rs(x):
    return "R$ " + _f(x, 2)


NORMAS = [
    ("IEC 61800-2 / IEC 61800-5-1", "Sistemas de acionamento de velocidade variável – requisitos gerais e segurança elétrica/térmica do filtro de saída"),
    ("IEC TS 60034-25 / IEC TS 60034-17", "Motores alimentados por conversor: limites de tensão de pico e dv/dt nos terminais"),
    ("IEC TS 61800-8", "Especificação da tensão na interface de potência do acionamento (inclui o efeito de filtros de saída)"),
    ("NEMA MG1 Part 30 / Part 31", "Motores de uso geral (≤ 1000 V pico) e motores para inversor (≤ 1600 V pico, tr ≥ 0,1 µs)"),
    ("IEC 60076-6", "Reatores – indutância, tolerâncias, elevação de temperatura e ensaios"),
    ("IEC 61558-2-20", "Pequenos reatores – construção e ensaios de isolamento"),
    ("IEC 60831-1/2 e IEC 61071", "Capacitores de potência autorregenerativos e capacitores para eletrônica de potência"),
    ("IEC 61000-2-4 / IEEE 519-2022", "Referência de distorção harmônica de tensão (≤ 5 %)"),
    ("IEC 61439-1/2 / NBR IEC 61439", "Conjuntos de manobra e controle de baixa tensão (caixa, elevação de temperatura, ensaios)"),
    ("NBR 5410 / IEC 60364-5-52", "Dimensionamento de condutores e condutor de proteção"),
    ("IEC 60529 / NR-10", "Grau de proteção IP e segurança em instalações elétricas (placas, descarga de capacitores)"),
]


CRITERIOS_ORIGEM = [
    # (critério, valor adotado (formatado depois), origem/natureza, fonte)
    ("Tensão de pico e dv/dt no motor", "{vpk} V / {dvdt} V/µs (cliente) – NEMA ≤ 1000 V", "Norma",
     "NEMA MG1 Pt 30/31; IEC TS 60034-17 / 60034-25"),
    ("Capacitores: tensão, corrente, pico, dv/dt, vida", "datasheet + 1,10·Un contínuo", "Norma + datasheet",
     "IEC 61071 (eletrônica de potência) / IEC 60831; datasheet TDK B3236"),
    ("Queda de tensão no indutor", "≤ {ukmax} % na f máx (busca {ukmin}–{ukbusca} %)", "Guia de fabricante",
     "Danfoss – Output Filters Design Guide: 4–10 % para filtro senoidal"),
    ("Frequência de chaveamento fixa e mínima", "{fs} kHz (parametrizada no inversor)", "Guia de fabricante",
     "Danfoss: não operar abaixo de 80 % da fs nominal do filtro"),
    ("Distorção (THD) da tensão no motor", "≤ {thd} % (PWM) e ≤ {thd1} % total com baixa ordem", "Prática de mercado",
     "Catálogos de filtros senoidais (Schaffner, ABB, WEG); IEC 61000-2-4 como referência de 5 %"),
    ("Faixa da frequência de ressonância", "≥ {frmult}·f saída máx e ≤ fs/2", "Artigo + calibração",
     "Liserre, Blaabjerg, Hansen – IEEE Trans. Ind. Appl. 2005 (10·f < fr < fs/2); 13× calibrado nos filtros fabricados"),
    ("Ondulação de corrente no indutor", "≤ {rip} % do pico nominal", "Prática de projeto",
     "Holmes & Lipo (espectro PWM); limita perdas HF, ruído e corrente nos capacitores"),
    ("Harmônicas de baixa ordem do inversor", "h5 2,3 · h7 0,7 · h11 1,1 · h13 0,5 … %", "Medição de campo",
     "Dranetz HDPQ: SENAI (958 µH/40 e 20 µF) e IHR 2022 – saída do inversor"),
    ("Amortecimento real da ressonância", "Q equivalente 4", "Medição de campo",
     "Ganho de pico medido 17–26 nas mesmas medições"),
    ("Caso sem motor (teste/comissionamento)", "alerta; capacitor verificado", "Medição de campo",
     "Ressonância medida na fr do LC sem motor (SENAI 40 µF: 7,2 % medido = previsto)"),
]

REFERENCIAS = [
    "IEC TS 60034-17 – Cage induction motors when fed from converters – Application guide.",
    "IEC TS 60034-25 – Rotating electrical machines – AC electrical machines used in power drive systems – Application guide.",
    "NEMA MG 1 – Motors and Generators, Parts 30 e 31 (motores alimentados por inversor).",
    "IEC TS 61800-8 – Adjustable speed electrical power drive systems – Specification of voltage on the power interface.",
    "IEC 61071 – Capacitors for power electronics. IEC 60076-6 – Reactors.",
    "Danfoss – Output Filters Design Guide (MG90N5): filtros dU/dt e senoidais, queda de tensão 4–10 %.",
    "M. Liserre, F. Blaabjerg, S. Hansen – Design and control of an LCL-filter-based three-phase active rectifier, "
    "IEEE Trans. Industry Applications, 2005.",
    "J. K. Steinke – Use of an LC filter to achieve a motor-friendly performance of the PWM voltage source inverter, "
    "IEEE Trans. Energy Conversion, 1999.",
    "A. von Jouanne, P. N. Enjeti – Design considerations for an inverter output filter to mitigate the effects of long motor leads "
    "in ASD applications, IEEE Trans. Industry Applications.",
    "R. Peña-Alzola et al. – Robust design of LCL filters / análise de perdas do amortecimento passivo, IEEE Trans. Ind. Informatics, 2014.",
    "D. G. Holmes, T. A. Lipo – Pulse Width Modulation for Power Converters (IEEE Press/Wiley).",
    "B. Wu – High-Power Converters and AC Drives (IEEE Press/Wiley).",
    "N. Mohan, T. Undeland, W. Robbins – Power Electronics: Converters, Applications and Design (Wiley).",
]


def _secao_base_tecnica(d, proj, cat):
    """2. Normas, critérios (com a origem de cada um), referências, metodologia, softwares e validação."""
    cp = cat["projeto_padrao"]
    ped = proj.pedido
    d.add_heading("2. Base normativa e critérios de projeto", 1)
    d.add_paragraph("Não existe norma que fixe os valores de projeto de um filtro senoidal (indutância, ressonância, queda). "
                    "As normas definem o que o filtro deve garantir ao motor e aos componentes; os valores de projeto seguem guias de "
                    "fabricantes, a literatura técnica e a calibração com filtros fabricados e medidos pela Electric Service. "
                    "A tabela 2.2 mostra a origem de cada critério.")
    d.add_heading("2.1 Normas aplicáveis", 2)
    _tabela(d, ["Norma / referência", "Aplicação no projeto"], NORMAS, [5.5, 11.5])
    d.add_heading("2.2 Critérios de projeto e sua origem", 2)
    fmt = dict(vpk=ped.get("vpk_max_v") or 1000, dvdt=ped.get("dvdt_max_v_us") or 500, ukmax=f"{cp['uk_max_pct']:g}",
               ukmin=f"{cp['uk_min_pct']:g}", ukbusca=f"{cp.get('uk_busca_max_pct', 15):g}", fs=f"{proj.fs_hz / 1000:g}",
               thd=f"{cp['thd_v_max_pct']:g}", thd1=f"{cp['thd_v_max_pct'] + 1:g}", frmult=f"{cp['fr_min_mult_fout']:g}",
               rip=f"{cp['ripple_pp_max_pct']:g}")
    _tabela(d, ["Critério", "Valor adotado", "Natureza", "Fonte"],
            [(a, b.format(**fmt), c, e) for a, b, c, e in CRITERIOS_ORIGEM], [3.8, 4.2, 2.4, 6.6], tam=8)
    d.add_heading("2.3 Metodologia", 2)
    _bullets(d, [
        "Dimensionamento: busca de todas as combinações de indutor (uk {0}–{1} %), capacitores do catálogo (estrela/delta, nº por ramo) "
        "e topologia; cada combinação é simulada e verificada; escolhe-se a de menor custo/perdas que passa em todos os critérios críticos."
        .format(cp["uk_min_pct"], cp.get("uk_busca_max_pct", 15)),
        "Simulação no domínio do tempo e da frequência: inversor PWM vetorial (SVPWM) com a portadora real, barramento CC = 1,35·Vrede, "
        "indutor com perdas de alta frequência, banco de capacitores, cabo em células π (R, L, C fase-terra e fase-fase) e motor "
        "(f.c.e.m. + indutância de dispersão, resistência com efeito pelicular).",
        "Pontos de operação: frequência máxima, mínima e condição de placa do filtro; cantos de tolerância de L (±5 %) e C (−5/+10 %).",
        "Robustez: harmônicas de baixa ordem do inversor (valores medidos) amplificadas pela ressonância em toda a faixa de velocidade, "
        "com e sem motor; consequência no capacitor (corrente e pico) verificada nos dois casos.",
        "Dupla checagem independente: a mesma rede é montada e simulada no ATP-EMTP; as grandezas de projeto são comparadas com o "
        "Python (seção 5.5).",
        "Componentes reais: indutor (núcleo, perdas, elevação de temperatura), capacitores (datasheet, ponto quente, vida), "
        "estudo térmico do painel e arranjo mecânico (seções 6 e 7)."])
    d.add_heading("2.4 Softwares utilizados", 2)
    from .versao import info as _info
    _tabela(d, ["Software", "Uso"], [
        (f"Plataforma FSEN v{_info().get('versao', '?')} (Python 3, NumPy, SciPy, Matplotlib)",
         "Dimensionamento, simulação, verificações, otimização, documentos"),
        ("ATP-EMTP (tpbig) + ATPDraw 7", "Simulação eletromagnética independente da mesma rede (dupla checagem) e desenho do circuito"),
        ("Dranetz HDPQ + leitor de arquivos .ddbx", "Medições de campo usadas na calibração (formas de onda e harmônicas)")], [7.5, 9.5], tam=9)
    d.add_heading("2.5 Validação da plataforma", 2)
    _bullets(d, [
        "11 filtros reais (fabricados pela Electric Service e Schaffner FN5040 de catálogo) simulados no Python e no ATP-EMTP em 60 Hz e "
        "30 Hz: 21 de 22 pontos coincidem em todas as grandezas (tensões, picos, correntes no indutor e nos capacitores, THD).",
        "Medições de campo (Dranetz HDPQ, sem motor): SENAI 958 µH/40 µF – THD medido 7,2 %, previsto 7,2 %; IHR 1586 µH/20 µF – "
        "medido 4,0 %, previsto 4,9 %; SENAI 958 µH/20 µF – medido 4,9 %, previsto 4,0 % (com motor) a 10,2 % (sem motor).",
        "As harmônicas que o inversor produz foram medidas em dois inversores diferentes e coincidem (h5 ≈ 2,2 %).",
        "Corrente medida no capacitor (IHR): 2,3 A RMS; calculada 2,6 A (plena carga)."])
    d.add_heading("2.6 Referências bibliográficas", 2)
    for i, r_ in enumerate(REFERENCIAS, 1):
        d.add_paragraph(f"[{i}] {r_}")


def _resumo_executivo(d, proj, cat):
    ped = proj.pedido
    b = proj.banco
    pts = proj.pontos
    v = {x.item: x for x in proj.verificacoes}
    def achar(prefixo):
        return next((x for k, x in v.items() if k.startswith(prefixo)), None)
    d.add_heading("Resumo para o cliente", 1)
    linhas = [("Filtro", f"Senoidal {proj.topologia} sem resistor de amortecimento – {ped['corrente_a']:g} A / {ped['tensao_v']:g} V"),
              ("Indutor L1", f"{proj.l1.l_uh:.0f} µH/fase, {proj.l1.i_nom_a:.0f} A (impedância {proj.l1.uk_pct:.1f} % a 60 Hz)"),
              ("Capacitores", f"{b.n_total} × {b.uf_unit:g} µF {b.v_unit:g} V ({b.fabricante}) em {b.ligacao}, {b.n_por_ramo} por ramo"),
              ("Frequência de ressonância", f"{proj.fr_hz:.0f} Hz"),
              ("Frequência de chaveamento do inversor", f"{proj.fs_hz / 1000:g} kHz (fixa)")]
    for pref, rot in (("THD total no motor", "Distorção da tensão no motor (total)"), ("Tensão de pico no motor", "Tensão de pico no motor"),
                      ("dv/dt no motor", "dv/dt no motor"), ("Queda de tensão", "Queda de tensão no indutor")):
        x = achar(pref)
        if x:
            linhas.append((rot, f"{x.valor}  (limite {x.limite})"))
    if pts:
        p0 = pts[0]
        if p0.get("v_inv_ll_fund"):
            q = 100 * (1 - p0["v_motor_ll_fund"] / p0["v_inv_ll_fund"])
            linhas.append((f"Tensão no motor – {p0['nome']}", f"{p0['v_motor_ll_fund']:.0f} V (inversor {p0['v_inv_ll_fund']:.0f} V; queda real {q:.1f} %)"))
    da = getattr(proj, "dupla_checagem_atp", None) or {}
    linhas.append(("Dupla checagem no ATP-EMTP", "convergiu com o Python" if da.get("convergiu") else
                   ("divergência – ver 5.5" if da.get("resultados") else "não executada nesta emissão")))
    linhas.append(("Resultado", "APROVADO em todas as verificações críticas" if proj.aprovado else "REPROVADO – ver seção 4"))
    _kv(d, linhas)
    alertas = [x for x in proj.verificacoes if not x.ok and not x.critico]
    if alertas:
        d.add_paragraph("Pontos de atenção (não impedem a aprovação):")
        _bullets(d, [f"{x.item}: {x.valor}" for x in alertas])
    d.add_paragraph("Como o projeto foi verificado: (1) simulação completa do inversor, filtro, cabo e motor na Plataforma FSEN; "
                    "(2) simulação independente da mesma rede no ATP-EMTP; (3) critérios calibrados em filtros já fabricados e em "
                    "medições de campo (Dranetz). Detalhes nas seções 2 e 5.")


# ------------------------------------------------------------------ memorial técnico
def secao_corrente(d, proj, titulo="1.1 Corrente de dimensionamento – definida pela carga (v1.11)"):
    """Tabela da base da corrente: o cobre vai pela carga, o ferro vai pelo inversor."""
    cc = getattr(proj, "corrente_dimensionamento", None) or {}
    if not cc:
        return
    d.add_heading(titulo, 2)
    if cc.get("base") != "carga":
        d.add_paragraph("Corrente de dimensionamento = corrente informada pelo cliente (" + "; ".join(cc.get("notas", [])) + ").")
        return
    d.add_paragraph("A corrente do filtro é definida pela Electric Service a partir da carga, não pelo número pedido pelo cliente. "
                    "O COBRE (aquecimento, perdas, placa) vai pela carga real: motor × fator de serviço, somado fasorialmente às "
                    "correntes dos capacitores e do cabo (sem crédito da compensação capacitiva), mais a ondulação de alta frequência "
                    "em quadratura e margem de 10 %. O FERRO (saturação) vai pela corrente que o INVERSOR consegue entregar, com "
                    "sobrecarga de 150 % por 60 s.")
    _tabela(d, ["Parcela", "Cálculo", "A", "Observação"],
            [(c["item"], c["conta"], f"{c['valor_a']:.1f}", c["obs"]) for c in cc["componentes"]]
            + [("Saturação: L ≥ 90 % até", "máx(1,25 × pico na I térmica; √2·I_inv + ripple/2)", f"{cc['isat_a']:.0f} pk", ""),
               ("Sobrecarga do inversor: L ≥ 70 % até", "1,5·√2·I_inv + ripple/2", f"{cc['iovl_a']:.0f} pk", "60 s, 1×/h"),
               ("Corrente pedida pelo cliente", "", f"{cc.get('i_cliente_a', 0):g}", "informativa")],
            [5.2, 5.6, 1.8, 4.4], tam=8)
    for n in cc.get("notas", []):
        d.add_paragraph("• " + n)


def memorial(proj, arr, orc, graf, desenhos_png, cat, pasta):
    ped = proj.pedido
    d = _novo("Memorial de Cálculo e Relatório de Simulação",
              f"Filtro senoidal {proj.topologia} – {ped['corrente_a']:g} A / {ped['tensao_v']:g} V – {ped['cliente']}", proj, cat)
    status = "APROVADO – atende a todos os critérios críticos" if proj.aprovado else "REPROVADO – ver verificações em vermelho"
    p = d.add_paragraph()
    r = p.add_run(f"Resultado: {status}")
    r.bold = True
    r.font.color.rgb = RGBColor(0x1B, 0x7F, 0x3A) if proj.aprovado else RGBColor(0xC0, 0x1E, 0x1E)
    for a in proj.avisos:
        d.add_paragraph("Aviso: " + a)
    try:
        _resumo_executivo(d, proj, cat)
    except Exception as _e:
        d.add_paragraph(f"(resumo não gerado: {_e})")

    d.add_heading("1. Dados de entrada (solicitação do cliente)", 1)
    _kv(d, [("Cliente", ped["cliente"]), ("CNPJ / Município", f"{ped['cnpj']} – {ped['cidade_uf']}"),
            ("Referência", ped["referencia"]), ("Quantidade", ped["quantidade"]),
            ("Tensão / frequência de rede", f"{ped['tensao_v']:g} V / {ped['freq_rede_hz']:g} Hz"),
            ("Corrente nominal do filtro (térmica, de projeto)", f"{ped['corrente_a']:g} A"
             + (f" – definida pela carga; o cliente pediu {ped.get('corrente_cliente_a'):g} A (informativo)"
                if ped.get("corrente_cliente_a") and abs(float(ped["corrente_cliente_a"]) - float(ped["corrente_a"])) > 0.5 else "")),
            ("Inversor", f"{ped['inversor']} ({ped['inversor_corrente_a'] or '-'} A)"),
            ("Motor", f"{ped['motor_cv'] or '-'} cv, {ped['motor_corrente_a'] or '-'} A, FP {ped['motor_fp']}, FS {ped['fator_servico']}, "
                      f"{ped['motor_rpm'] or '-'} rpm, {ped['motor_polos']} polos"),
            ("Aplicação", ped["aplicacao"] or "-"), ("Faixa de operação", f"{ped['f_saida_min_hz']:g}–{ped['f_saida_max_hz']:g} Hz"),
            ("Cabo inversor-motor", f"{ped['cabo_m']:g} m"),
            ("Requisitos do cliente", f"Vpico ≤ {ped['vpk_max_v'] or '-'} V; dv/dt ≤ {ped['dvdt_max_v_us'] or '-'} V/µs; "
                                      f"tr > {ped['rise_time_min_us'] or '-'} µs; isolação {ped['classe_isolamento_kv']} kV; "
                                      f"classe {ped['classe_temp']}; elevação {ped['elevacao_temp']}")])
    if ped.get("lacunas"):
        d.add_heading("Premissas adotadas (dados ausentes no pedido)", 3)
        _bullets(d, ped["lacunas"])
    dfx = getattr(proj, "dados_faltantes", None)
    if dfx and dfx["itens"]:
        d.add_heading("Dados a confirmar e sensibilidade do projeto às premissas", 3)
        d.add_paragraph("Cada dado ausente foi substituído por uma premissa. Quando simulável, o projeto escolhido (mesmos L, C e fs) "
                        "foi refeito com valores plausíveis do dado para medir o impacto. CRÍTICO = pode reprovar ou alterar o filtro.")
        linhas = []
        for it in dfx["itens"]:
            prem = dfx["premissas"].get(it["id"], "-")
            if it.get("cenarios"):
                for c in it["cenarios"]:
                    linhas.append((it["prioridade"], it["pergunta"][:70], prem, c["cenario"], c["efeito"]))
            else:
                linhas.append((it["prioridade"], it["pergunta"][:70], prem, "-", "não simulável"))
        _tabela(d, ["Prioridade", "Dado", "Premissa", "Cenário testado", "Resultado"], linhas, [2.2, 5.5, 3.3, 3.3, 3.2], tam=7.5)

    secao_corrente(d, proj)
    _secao_base_tecnica(d, proj, cat)

    d.add_heading("3. Resultado do dimensionamento", 1)
    b = proj.banco
    am = proj.amortecimento
    from .otimizacao import TOPOLOGIAS
    linhas = [("Topologia", TOPOLOGIAS.get(proj.topologia, {}).get("nome", proj.topologia)), ("Frequência de chaveamento de projeto (fixa)", f"{proj.fs_hz / 1000:g} kHz"),
              ("Barramento CC", f"{proj.vdc:.0f} V"),
              ("L1 (indutor de saída do inversor)", f"{proj.l1.l_uh:.0f} µH/fase  (uk = {proj.l1.uk_pct:.1f} %)")]
    if proj.l2:
        linhas.append(("L2 (indutor lado motor)", f"{proj.l2.l_uh:.0f} µH/fase"))
    linhas += [("Banco de capacitores", f"{b.n_total} × {b.uf_unit:g} µF / {b.v_unit:g} V ({b.fabricante}) – ligação {b.ligacao}, "
                                        f"{b.n_por_ramo} por ramo"),
               ("C equivalente estrela", f"{b.c_y_uf:g} µF/fase  (por ramo {b.c_ramo_uf:g} µF)"),
               ("Potência reativa do banco (60 Hz, Un capacitor)", f"{b.kvar_60:.1f} kvar"),
               ("Frequência de ressonância", f"{proj.fr_hz:.0f} Hz")]
    if am and am.tipo == "rc_paralelo":
        linhas.append(("Amortecimento", f"Ramo RC paralelo por ramo do banco: {am.n_cd_por_ramo} × {b.uf_unit:g} µF em série com "
                                        f"{am.r_ramo_ohm:.3f} Ω ({am.p_ramo_w:.0f} W dissipados, especificado {am.p_nominal_w:g} W)"))
    elif am:
        linhas.append(("Amortecimento", f"Resistor {am.r_ramo_ohm:.3f} Ω em série com cada ramo ({am.p_ramo_w:.0f} W dissipados, "
                                        f"especificado {am.p_nominal_w:g} W) – Q ≈ {am.q_alvo:g}"))
    else:
        linhas.append(("Amortecimento", "Não necessário (sem resistor)"))
    _kv(d, linhas)

    d.add_heading("4. Verificações", 1)
    from . import checagem as CK                  # v1.23.2: coluna Check padrão da plataforma (3 filtros)
    _ck = [CK.de_verificacao(v.ok, v.critico, v.valor, v.limite) for v in proj.verificacoes]
    _tabela(d, ["Verificação", "Valor", "Limite", "Utilização", "Check", "Referência"],
            [(v.item, v.valor, v.limite, "–" if u is None else f"{u:.0f} %", c, v.referencia)
             for v, (c, u) in zip(proj.verificacoes, _ck)], [4.2, 2.6, 2.2, 1.3, 1.7, 5.0], tam=8)

    d.add_heading("5. Simulação por ponto de operação", 1)
    cab = ["Grandeza"] + [p["nome"] for p in proj.pontos]
    def lin(nome, chave, n=1, fator=1.0):
        return [nome] + [_f(p[chave] * fator, n) for p in proj.pontos]
    _tabela(d, cab, [lin("Tensão saída L-L fundamental (V)", "v_saida_ll_fund"), lin("THD tensão saída (%)", "thd_v_saida_pct", 2),
                     lin("THD tensão inversor (%)", "thd_v_inversor_pct", 1), lin("Índice de modulação m", "m_index", 3),
                     lin("Corrente inversor RMS (A)", "i1_rms"), lin("Corrente motor RMS (A)", "i2_rms"),
                     lin("THD corrente motor (%)", "i2_thd_pct", 2), lin("Corrente capacitores Y RMS (A)", "icap_y_rms"),
                     lin("Ondulação p-p indutor (A)", "ripple_pp", 0), lin("Tensão de pico motor (V)", "vpk_saida", 0),
                     lin("dv/dt motor (V/µs)", "dvdt_saida_v_us", 2), lin("dv/dt saída inversor (V/µs)", "dvdt_inversor_v_us", 0)],
            [5.2] + [11.8 / len(proj.pontos)] * len(proj.pontos), tam=8)
    _img(d, graf.get("formas_onda"), 16.5, "Figura 1 – Formas de onda de tensão e corrente (ponto de f máxima).")
    _img(d, graf.get("espectro"), 16.5, "Figura 2 – Espectro harmônico da tensão de linha em % da fundamental: inversor × saída do filtro × motor, "
                                          "com a tabela de DHTv %.")
    _img(d, graf.get("bode"), 16.5, "Figura 3 – Resposta em frequência (ganho e fase) com e sem carga e efeito do amortecimento.")
    _img(d, graf.get("impedancia"), 16.0, "Figura 4 – Impedância vista pelo inversor.")
    _img(d, graf.get("baixa_ordem"), 16.0, "Figura 5 – Robustez à ressonância na faixa de operação.")
    _img(d, graf.get("fluxo"), 16.0, "Figura 6 – Fluxo de correntes por ramo e ponto de operação.")
    _img(d, graf.get("rms"), 16.5, "Figura 6b – Correntes e tensões RMS em todos os ramos (inversor/L1, capacitores, motor), "
                                   "por ponto de operação, com máximos e mínimos.")

    d.add_heading("5.1 Modelo do sistema simulado", 2)
    si = getattr(proj, "sistema", {}) or {}
    _kv(d, [("Cabo filtro → motor", f"{si.get('cabo_paralelos', 1)} × {si.get('cabo_secao_mm2', '-')} mm² por fase, {si.get('cabo_m', '-')} m, "
                                     f"{'blindado' if ped.get('cabo_blindado', True) else 'não blindado'} – modelo π distribuído (R, L, C fase-terra e fase-fase)"),
            ("Motor", f"{si.get('motor_kw', '-')} kW – f.c.e.m. + dispersão 0,15 pu, resistência com efeito pelicular √h; "
                      f"C enrolamento–carcaça ≈ {si.get('Cwf_nF', '-')} nF (modo comum)"),
            ("Modo comum", "Fonte de sequência zero do PWM → indutância de sequência zero do indutor → capacitância do cabo e do motor "
                           "→ PE/blindagem → filtro EMC do inversor"),
            ("Pontos simulados", "f máx, f mín e placa (60 Hz, In) – tensão e corrente impostas nos terminais do motor")])

    d.add_heading("5.2 Modo comum, corrente de terra e mancais", 2)
    d.add_paragraph("O filtro senoidal LC atua entre fases. A tensão de modo comum do inversor (degraus de Vcc/3 em cada comutação) "
                    "passa praticamente inalterada para o motor; ela circula pela capacitância do cabo e do enrolamento para a carcaça "
                    "e volta pelo PE/blindagem. Por isso o filtro senoidal sozinho não elimina correntes de mancal (IEC TS 60034-25).")
    from . import checagem as CK
    _tabela(d, ["Verificação", "Valor", "Limite", "Check"], [(v.item, v.valor, v.limite, CK.de_verificacao(v.ok, False, v.valor, v.limite)[0])
            for v in proj.verificacoes if any(k in v.item for k in ("modo comum", "terra", "mancal"))], [6.5, 4.0, 3.0, 2.0], tam=8)
    _bullets(d, ["Se a tensão no mancal passar do limite: rolamento isolado no lado oposto ao acionamento e/ou escova de aterramento do eixo.",
                 "Alternativas no filtro: banco em estrela com centro ligado ao barramento CC (filtro 'all-pole') ou núcleo de modo comum "
                 "(nanocristalino) na saída do inversor.",
                 "Cabo blindado simétrico com aterramento 360° nas duas pontas e condutor PE de baixa impedância."])

    d.add_heading("5.3 Suportabilidade dos capacitores", 2)
    e = getattr(proj, "estresse_capacitor", {}) or {}
    b0 = proj.banco
    _kv(d, [("Ligação / por ramo", f"{b0.ligacao}, {b0.n_por_ramo} × {b0.uf_unit:g} µF {b0.v_unit:g} V"),
            ("Tensão RMS / pico no capacitor", f"{b0.v_cap_rms:.0f} V / {e.get('vpk', 0):.0f} V"),
            ("Corrente RMS por capacitor (fund. + HF)", f"{e.get('irms', 0):.2f} A (limite {b0.i_unit_max:.2f} A)"),
            ("Perdas por capacitor (ESR + dielétrico)", f"{e.get('perdas_w', 0):.2f} W"),
            ("Ponto quente / vida estimada", f"{e.get('t_hotspot_c', 0):.1f} °C / {e.get('vida_h', 0) / 1000:.0f} mil h (ar de projeto {e.get('t_interno_c', 55)} °C)")])

    d.add_heading("5.4 Condições extremas (robustez)", 2)
    ce = getattr(proj, "condicoes_extremas", []) or []
    if ce and "fr_Hz" in ce[0]:
        _tabela(d, ["Condição", "fr Hz", "THD motor %", "Vpico V", "m", "I cap A", "T cap °C", "Baixa ordem %", "OK"],
                [(c["condicao"], c["fr_Hz"], c["thd_motor"], c["vpk_motor"], c["m_max"], c["i_cap"], c["t_cap"], c["baixa_ordem"],
                  "sim" if c["aprovado"] else "NÃO") for c in ce], tam=7.5)

    d.add_heading("5.5 Dupla checagem no ATP (ATP-EMTP)", 2)
    da = getattr(proj, "dupla_checagem_atp", None)
    if da and da.get("resultados"):
        d.add_paragraph("A mesma rede (inversor PWM em TACS com a mesma lei SVPWM, indutor com Rp de perdas, banco "
                        f"{proj.banco.ligacao}, cabo em células π, motor R-L com f.c.e.m. por Norton e Cwf) foi simulada no domínio do tempo "
                        "no ATP, executado automaticamente pela plataforma. Comparação com o Python (R constante) nos últimos 2 ciclos em regime. "
                        f"Resultado: {'CONVERGIU' if da.get('convergiu') else 'DIVERGÊNCIA – revisar'}.")
        for r in da["resultados"]:
            d.add_heading(r["ponto"], 3)
            _tabela(d, ["Grandeza", "Un", "Python", "ATP", "Dif. %", "Tol. %", "OK"],
                    [(l["grandeza"], l["unidade"], f"{l['python']:.2f}", f"{l['atp']:.2f}", f"{l['dif_pct']:+.2f}", f"±{l['tolerancia_pct']:g}",
                      "sim" if l["convergiu"] else "NÃO") for l in r["tabela"]], tam=8)
        pasta_atp = os.path.dirname(da["graficos"][0]) if da.get("graficos") else None
        for v in da.get("vistas") or []:
            if pasta_atp:
                _img(d, os.path.join(pasta_atp, v["rede"]), 16.5, f"Rede elétrica simulada com os valores Python × ATP – {v['ponto']}")
                _img(d, os.path.join(pasta_atp, v["ondas"]), 16.5, f"Formas de onda: Python | ATP | sobreposição – {v['ponto']}")
                _img(d, os.path.join(pasta_atp, v["espectro"]), 16.5, f"Espectro Python × ATP (% da fundamental) – {v['ponto']}")
    else:
        d.add_paragraph(f"ATP NÃO executado nesta emissão – {(da or {}).get('msg', 'sem registro')}. "
                        "Os decks .atp ficam em 01_Engenharia/ATP para rodar e comparar.")

    d.add_heading("6. Especificação dos componentes reais", 1)
    for L in [proj.l1] + ([proj.l2] if proj.l2 else []):
        d.add_heading(L.nome, 3)
        _kv(d, [("Indutância", f"{L.l_uh:.1f} µH/fase ±5 % (medida a 60 Hz, In)"), ("Corrente térmica RMS", f"{L.i_nom_a:.0f} A"),
                ("Corrente fundamental máx.", f"{L.i_fund_a:.0f} A"), ("Ondulação", f"{L.ripple_pp_a:.0f} A p-p / {L.ripple_rms_a:.0f} A RMS @ {L.f_chav_hz / 1000:g} kHz"),
                ("Corrente de pico de operação", f"{L.i_pico_a:.0f} A"), ("Linearidade", f"L ≥ 90 % do nominal até {L.i_sat_a:.0f} A pico"),
                ("Energia armazenada (3 fases)", f"{L.energia_j:.1f} J"), ("Perdas", (f"calculadas {proj._ind_perdas_calc_w:.0f} W (pior método); máximo garantido {L.perdas_w:.0f} W"
                             if getattr(proj, "_ind_perdas_calc_w", None) and L is proj.l1 else f"máximo garantido {L.perdas_w:.0f} W")),
                ("Massa / dimensões estimadas", f"{L.massa_kg:.0f} kg / {L.dim_mm[0]}×{L.dim_mm[1]}×{L.dim_mm[2]} mm (L×A×P)")])
    d.add_heading("Banco de capacitores", 3)
    _kv(d, [("Capacitor", f"{b.fabricante} – {b.linha} – {b.uf_unit:g} µF {b.v_unit:g} V – P/N {b.pn}"),
            ("Quantidade / ligação", f"{b.n_total} pç – {b.ligacao}, {b.n_por_ramo} em paralelo por ramo"),
            ("Tensão no capacitor (máx.)", f"{b.v_cap_rms:.0f} V RMS"), ("Corrente por capacitor", f"{b.i_unit_rms:.2f} A RMS (fund. {b.i_unit_fund:.2f} A) – limite {b.i_unit_max:.2f} A"),
            ("Resistor de descarga por capacitor", f"{b.r_descarga_mohm * 1000:.0f} kΩ / {b.r_descarga_w:g} W (≤ 50 V em 60 s)")])

    d.add_heading("7. Estudo térmico do painel", 1)
    tm = getattr(proj, "termico", None)
    if tm:
        d.add_paragraph(f"Modelo de ventilação forçada de baixo para cima (IEC TR 60890 / IEC 61439-1 cl.10.10): ambiente {tm['t_ambiente_C']} °C, "
                        f"{tm['n_ventiladores']} ventilador(es) – {tm['vazao_livre_m3h']} m³/h livres, {tm['vazao_efetiva_m3h']} m³/h efetivos "
                        f"com filtros; {100 * tm['fracao_paredes']:.0f} % do calor sai pelas paredes. Ar na saída: {tm['t_saida_C']} °C. "
                        f"Arranjo escolhido: {'capacitores na entrada de ar (embaixo), indutor acima' if tm['arranjo_escolhido'] == 'capacitores_embaixo' else 'indutor embaixo, capacitores acima'}.")
        from . import checagem as CK
        _tabela(d, ["Componente", "Perdas W", "Ar local °C", "Componente °C", "Limite", "Check"],
                [(c["componente"], c["perdas_W"], c["t_ar_local_C"], c["t_componente_C"], c["limite"],
                  CK.de_verificacao(c["ok"], True, c["t_componente_C"], c["limite"])[0])
                 for c in tm["componentes"]], [5.5, 1.8, 2.0, 2.2, 3.8, 1.2], tam=8)
        _tabela(d, ["Verificação", "Valor", "Limite", "Check"], [(v["item"], v["valor"], v["limite"], CK.de_verificacao(v["ok"], True, v["valor"], v["limite"])[0])
                for v in tm["verificacoes"] if not v["item"].startswith("Térmico – Indutor") and not v["item"].startswith("Térmico – Capacitores")],
                [6.5, 4.0, 3.5, 2.0], tam=8)
        _tabela(d, ["Arranjo", "Aprovado", "Ventiladores", "Ar saída °C", "Capacitor °C"],
                [(a["arranjo"], "sim" if a["aprovado"] else "não", a["ventiladores"], a["t_saida_C"], a["t_cap_C"]) for a in tm["comparacao_arranjos"]],
                tam=8)
        _img(d, graf.get("termico"), 16.5, "Figura – Mapa térmico e perfil vertical da temperatura do ar na caixa.")

    d.add_heading("7.1 Arranjo mecânico", 1)
    _kv(d, [("Caixa", f"{arr.caixa_id} – {arr.caixa_tipo}, {arr.caixa_l}×{arr.caixa_a}×{arr.caixa_p} mm, IP{arr.caixa_ip}"),
            ("Massa total estimada", f"{arr.massa_total_kg:.0f} kg"),
            ("Perdas", "; ".join(f"{k}: {v:.0f} W" for k, v in arr.perdas_w.items()) + f"  → total {arr.perda_total_w:.0f} W"),
            ("Ventilação", f"{arr.vazao_m3h:.0f} m³/h → {arr.n_ventiladores} ventilador(es)")])
    _bullets(d, arr.obs)
    for p in desenhos_png[:2]:
        _img(d, p, 17.0)

    d.add_heading("8. Parametrização do inversor (comissionamento)", 1)
    _bullets(d, [f"Frequência de chaveamento FIXA em {proj.fs_hz / 1000:g} kHz (mínima = referência). Nunca operar com fs < {proj.fs_hz / 1000:g} kHz.",
                 f"Frequência de saída máxima limitada a {ped['f_saida_max_hz']:g} Hz; evitar operação contínua abaixo de 5 Hz.",
                 "Controle escalar V/f recomendado. Em controle vetorial/DTC, informar L e C do filtro quando o inversor permitir.",
                 f"Dados para o inversor: L = {proj.l1.l_uh / 1000:.3f} mH; C por fase (estrela equivalente) = {b.c_y_uf:g} µF.",
                 proj.notas_inversor])

    d.add_heading("9. Ensaios de rotina recomendados (por unidade)", 1)
    _bullets(d, ["Inspeção visual, dimensional e de torque das conexões.",
                 "Medição de indutância por fase (LCR a 60 Hz ou ensaio com corrente) – tolerância ±5 %.",
                 "Medição de capacitância por ramo – tolerância −5/+10 %.",
                 "Resistência de isolamento a 1000 Vcc (≥ 100 MΩ) e tensão aplicada 2,5 kV/1 min fase-terra (com capacitores e resistores desconectados do PE).",
                 "Teste funcional de ventiladores/termostato e verificação do tempo de descarga dos capacitores.",
                 f"Comissionamento: conferir e registrar a frequência de chaveamento do inversor FIXA em {proj.fs_hz / 1000:g} kHz, com a redução "
                 "automática por temperatura desabilitada, e medir a tensão no motor (THD e pico) na menor e na maior velocidade de operação.",
                 "Opcional (tipo, 1ª unidade): ensaio em carga com inversor, medição de THD, Vpico e dv/dt e termografia."])

    d.add_heading("10. Otimização global multiobjetivo", 1)
    df = getattr(proj, "_otimizacao", None)
    if df is not None:
        d.add_paragraph(f"Foram simuladas {len(df)} configurações (fs × uk × tipo/ligação/quantidade de capacitores × amortecimento); "
                        f"{int(df.viavel.sum())} atendem a todos os critérios críticos e {int(df.pareto.sum())} formam a fronteira de Pareto "
                        "(nenhuma outra é melhor em custo, volume, perdas, THD e confiabilidade ao mesmo tempo). A escolhida tem a maior nota "
                        "ponderada (pesos em catalogo.yaml → otimizacao.pesos). Tabela completa: planilha *_Otimizacao_todas_configuracoes.xlsx.")
        _img(d, graf.get("pareto"), 17, "Figura 7 – Mapa das configurações viáveis: custo × perdas e ressonância × THD.")
    _tabela(d, ["fs kHz", "uk %", "Capacitor", "Lig.", "n/ramo", "Rd Ω", "fr Hz", "THD %", "Custo R$", "Nota"],
            [(a.get("fs_khz", proj.fs_hz / 1000), a["uk"], a["capacitor"], a["ligacao"][0], a["n_por_ramo"], a.get("Rd_y_ohm", 0), a["fr_Hz"],
              a["thd_pct"], _f(a["custo_est"], 0), a.get("nota", "")) for a in proj.alternativas[:10]], tam=7.5)
    caminho = os.path.join(pasta, f"{proj_codigo(proj)}_Memorial_de_Calculo.docx")
    d.save(caminho)
    return caminho


# ------------------------------------------------------------------ proposta e folha de dados
def proposta(proj, arr, orc, cat, pasta):
    ped = proj.pedido
    com = cat["comercial"]
    emp = cat["empresa"]
    d = _novo("Proposta Técnico-Comercial", f"{ped['cliente']} – {ped['referencia']}", proj, cat)
    d.add_paragraph(f"A/C {ped['contato'] or 'Compras'}\n{ped['cliente']} – CNPJ {ped['cnpj']} – {ped['cidade_uf']}")
    d.add_paragraph("Prezados, agradecemos a consulta. Apresentamos nossa proposta para fornecimento do item abaixo, "
                    "projetado e simulado especificamente para a aplicação informada.")
    d.add_heading("1. Escopo de fornecimento", 1)
    desc = (f"Filtro trifásico senoidal {proj.topologia} para saída de inversor de frequência – {ped['corrente_a']:g} A, {ped['tensao_v']:g} V, "
            f"{ped['freq_rede_hz']:g} Hz, montado em caixa metálica IP{arr.caixa_ip} ({arr.caixa_l}×{arr.caixa_a}×{arr.caixa_p} mm), "
            f"ventilação forçada, bornes de entrada/saída e barramento de terra.")
    _tabela(d, ["Item", "Qtd", "Un", "Descrição", "Preço unit.", "Preço total"],
            [("01", orc.quantidade, "pç", desc, _rs(orc.preco_unit), _rs(orc.preco_total))], [1.2, 1.2, 1.0, 8.6, 2.5, 2.5])
    d.add_heading("2. Características técnicas garantidas", 1)
    pior = lambda k: max(p[k] for p in proj.pontos)
    _tabela(d, ["Requisito do cliente", "Solicitado", "Ofertado (simulado)"], [
        ("Tipo", "Senoidal", f"Senoidal {proj.topologia}, fr = {proj.fr_hz:.0f} Hz"),
        ("Corrente nominal", f"{ped.get('corrente_cliente_a') or ped['corrente_a']:g} A",
         (lambda cc: (f"{ped['corrente_a']:g} A contínuos, dimensionado pela carga real (motor {cc['i_motor_placa_a']:g} A × FS = "
                      f"{cc['i_motor_a']:.0f} A + capacitores + ondulação, margem 10 %); núcleo para o inversor de "
                      f"{cc['i_ref_pico_a']:.0f} A com sobrecarga de 150 % / 60 s sem saturar")
          if cc.get("base") == "carga" else f"{ped['corrente_a']:g} A")(getattr(proj, "corrente_dimensionamento", None) or {})),
        ("Tensão máx. de pico no motor", f"{ped['vpk_max_v'] or '-'} V", f"{pior('vpk_saida'):.0f} V"),
        ("Rise time", f"> {ped['rise_time_min_us'] or '-'} µs", f"> 100 µs (forma senoidal)"),
        ("dv/dt máximo", f"{ped['dvdt_max_v_us'] or '-'} V/µs", f"{pior('dvdt_saida_v_us'):.1f} V/µs"),
        ("THD de tensão no motor", "-", f"{pior('thd_v_saida_pct'):.1f} % (fs = {proj.fs_hz / 1000:g} kHz)"),
        ("Classe de isolamento", f"{ped['classe_isolamento_kv']} kV", "1,1 kV"),
        ("Classe de temperatura", ped["classe_temp"], "H (180 °C) – padrão Electric para filtro senoidal (igual ou superior à solicitada)"),
        ("Elevação de temperatura", ped["elevacao_temp"], "média do enrolamento conforme o estudo térmico (limite da classe H: 125 K)"),
        ("Queda de tensão", "-", f"{proj.l1.queda_v_pct:.1f} % @ {ped['f_saida_max_hz']:g} Hz"),
        ("Perdas totais", "-", f"≈ {arr.perda_total_w:.0f} W"),
        ("Frequência de chaveamento do inversor", "-", f"≥ {proj.fs_hz / 1000:g} kHz fixa"),
    ], [5.5, 4.0, 7.5])
    d.add_heading("3. Condições comerciais", 1)
    _kv(d, [("Preço", "Valores unitários com impostos inclusos (ICMS, PIS, COFINS)"),
            ("NCM", f"{com['ncm_sugerido']} (indutores – confirmar)"), ("ICMS", f"{com['impostos']['icms_interestadual_pct']:g} % (RS → {ped['cidade_uf'][-2:] or 'UF'}, contribuinte – revenda)"),
            ("Substituição tributária", "Não aplicável ao NCM informado (confirmar)"), ("IPI", f"{com['impostos']['ipi_pct']:g} %"),
            ("Frete", "FOB – Porto Alegre/RS (CIF sob consulta)"), ("Prazo de entrega", com["prazo_entrega"]),
            ("Condição de pagamento", com["pagamento"]), ("Validade da proposta", f"{com['validade_dias']} dias"),
            ("Garantia", com["garantia"] + " contra defeitos de fabricação")])
    d.add_heading("4. Documentos que acompanham a proposta", 1)
    _bullets(d, ["Folha de dados técnica do filtro (catálogo/ficha técnica).", "Memorial de cálculo e relatório de simulação.",
                 "Desenho dimensional e diagrama elétrico.", "Relatório de ensaios de rotina emitido na entrega de cada unidade."])
    d.add_heading("5. Observações", 1)
    _bullets(d, [f"O inversor deve operar com frequência de chaveamento fixa de {proj.fs_hz / 1000:g} kHz e controle escalar (ou com parâmetros de filtro).",
                 "Instalação abrigada, temperatura ambiente até 40 °C, altitude até 1000 m.",
                 "Cabo blindado entre filtro e motor recomendado; aterramento conforme NBR 5410."])
    d.add_paragraph(f"\nAtenciosamente,\n\n{emp['responsavel']}\n{emp['nome']}\n{emp['email']} • {emp['telefone']}")
    caminho = os.path.join(pasta, f"{proj_codigo(proj)}_Proposta_Comercial.docx")
    d.save(caminho)
    return caminho


def vpk_garantia(proj):
    """v1.28.0 (REQ-SEN-022, auditoria D9): tensão de pico GARANTIDA ao cliente = maior pico simulado entre os pontos de operação
    e as condições extremas (rede +10 %, tolerâncias L/C, cabo), + 5 %, arredondado para cima de 5 V. Antes a garantia usava só a
    rede nominal e ficava abaixo do próprio pior caso simulado."""
    import math as _m
    v = max([float(p.get("vpk_saida", 0) or 0) for p in proj.pontos] + [float(p.get("vpk_motor", 0) or 0) for p in proj.pontos]
            + [float(c.get("vpk_motor", 0) or 0) for c in (getattr(proj, "condicoes_extremas", None) or []) if isinstance(c, dict)])
    return _m.ceil(v * 1.05 / 5.0) * 5.0


def folha_dados(proj, arr, cat, pasta, desenhos_png):
    ped = proj.pedido
    d = _novo("Folha de Dados Técnica", f"Filtro senoidal {proj.topologia} {ped['corrente_a']:g} A {ped['tensao_v']:g} V", proj, cat)
    b = proj.banco
    pior = lambda k: max(p[k] for p in proj.pontos)
    _kv(d, [("Modelo", proj_codigo(proj)), ("Tensão nominal", f"{ped['tensao_v']:g} V ±10 %, 3~"),
            ("Corrente nominal", f"{ped['corrente_a']:g} A (40 °C)"), ("Frequência de saída", f"0–{max(ped['f_saida_max_hz'], 60):g} Hz"),
            ("Frequência de chaveamento", f"FIXA em {proj.fs_hz / 1000:g} kHz – redução automática do inversor desabilitada (requisito)"), ("Indutância", f"{proj.l1.l_uh:.0f} µH/fase"),
            ("Capacitância (Y equivalente)", f"{b.c_y_uf:g} µF/fase ({b.ligacao})"), ("Frequência de ressonância", f"{proj.fr_hz:.0f} Hz"),
            ("THD de tensão de saída", f"< {max(3.0, round(pior('thd_v_saida_pct') + 0.5)):.0f} %"),
            ("Tensão de pico no motor", f"< {vpk_garantia(proj):.0f} V (pior caso: rede +10 % e tolerâncias)"), ("dv/dt", f"< {max(5, pior('dvdt_saida_v_us') * 2):.0f} V/µs"),
            ("Queda de tensão", f"{proj.l1.queda_v_pct:.1f} % @ {ped['f_saida_max_hz']:g} Hz"),
            ("Perdas", f"≈ {arr.perda_total_w:.0f} W"), ("Isolação", "1,1 kV; ensaio 2,5 kV / 1 min"),
            ("Classe térmica", "Sistema de isolação classe H (180 °C), elevação média ≤ 125 K – igual ou superior à classe solicitada"), ("Grau de proteção", f"IP{arr.caixa_ip}"),
            ("Dimensões (L×A×P)", f"{arr.caixa_l}×{arr.caixa_a}×{arr.caixa_p} mm"), ("Massa", f"≈ {arr.massa_total_kg:.0f} kg"),
            ("Refrigeração", f"Forçada, {arr.n_ventiladores} ventilador(es), alimentação auxiliar 220 Vca"),
            ("Normas", "IEC 61800-5-1, IEC 60076-6, IEC 60831, IEC 61439, NBR 5410")])
    if desenhos_png:
        _img(d, desenhos_png[1], 17)
    caminho = os.path.join(pasta, f"{proj_codigo(proj)}_Folha_de_Dados.docx")
    d.save(caminho)
    return caminho


# ------------------------------------------------------------------ fornecedores: ETs e e-mails
def _email(pasta, nome, para, assunto, corpo):
    c = os.path.join(pasta, nome)
    with open(c, "w", encoding="utf-8") as f:
        f.write(f"Para: {para}\nAssunto: {assunto}\n\n{corpo}\n")
    return c


def _extenso(n):
    return {1: "um", 2: "dois", 3: "três", 4: "quatro", 5: "cinco", 6: "seis", 7: "sete", 8: "oito", 9: "nove", 10: "dez"}.get(int(n), str(n))


def _ola(f):
    t = (f or {}).get("tratamento") or ""
    return f"Olá {t}, tudo bem?" if t else "Olá, tudo bem?"


def _para(f):
    if not f:
        return "a definir"
    return f"{f.get('contato') or f.get('nome')} <{f.get('email')}>" if f.get("contato") else f.get("email", "a definir")


def _classe_ind(cat):
    c = cat.get("termico", {}).get("classe_indutor_c", 155)
    e = cat.get("termico", {}).get("elevacao_indutor_k", 100)
    return ({130: "B", 155: "F", 180: "H", 200: "N", 220: "R"}.get(int(c), "?"), int(c), int(e))


def et_fornecedores(proj, arr, orc, cat, pasta, desenhos_pdf):
    emp = cat["empresa"]
    ped = proj.pedido
    forn = cat["fornecedores"]
    q = int(ped.get("quantidade", 1) or 1)
    cod = proj_codigo(proj)
    saidas = {}
    assin = f"\n\nAtenciosamente,\n{emp['responsavel']}\n{emp['nome']}\n{emp['email']} | {emp['telefone']}"

    # --- INDUTOR
    from . import alternativa_l as ALT
    try:
        alt = ALT.alternativas(proj, cat)
    except Exception as _e:
        alt = dict(necessaria=False, motivo=f"erro: {_e}")
    try:
        ALT.atp_alternativa(alt, cat, cod)
    except Exception:
        pass
    proj.alternativa_l = alt
    try:
        import json as _json
        _eng = os.path.join(os.path.dirname(pasta), "01_Engenharia")
        if os.path.isdir(_eng):
            _json.dump({k: v for k, v in alt.items()} | {"recomendada": {k: v for k, v in (alt.get("recomendada") or {}).items()
                                                                            if k != "_proj"}},
                       open(os.path.join(_eng, "alternativa_indutancia.json"), "w", encoding="utf-8"), ensure_ascii=False,
                       indent=1, default=str)
    except Exception:
        pass
    for L in [proj.l1] + ([proj.l2] if proj.l2 else []):
        tag = L.nome.split(" ")[0]
        d = _novo(f"Especificação Técnica – Indutor {tag}", f"Reator trifásico para filtro senoidal – {cod}", proj, cat)
        from . import spec_indutor as SI
        fig = None
        if L is proj.l1:
            try:
                fig = SI.grafico_forma_onda(proj, cat, os.path.join(pasta, f"_forma_onda_indutor_{tag}.png"),
                                            pasta_atp=os.path.join(os.path.dirname(pasta), "01_Engenharia", "ATP"))
            except Exception:
                fig = None
        SI.escrever_et(d, L, proj, arr, cat, ped, q, _kv, _tabela, _bullets, _f, figura=fig)
        if L is proj.l1:
            ALT.escrever_secao(d, alt, _tabela)
        if fig:
            try:
                os.replace(fig, os.path.join(pasta, f"Forma_de_onda_Indutor_{tag}_{cod}.png"))
            except OSError:
                pass
        p = os.path.join(pasta, f"ET_Indutor_{tag}_{cod}.docx")
        d.save(p)
        f0 = forn["indutor"][0]
        from . import conferencia as _CF                # v1.28.0 (REQ-SEN-023): planilha de resposta do fabricante
        _xl = f"Formulario_Resposta_Indutor_{tag}_{cod}.xlsx"
        try:
            _CF.formulario_xlsx("indutor", os.path.join(pasta, _xl), cod, f"Resposta técnica – Indutor {tag} {L.l_uh:.0f} µH / {L.i_nom_a:.0f} A")
            _txt_prop = _CF.texto_email_proposta("indutor", _xl)
        except Exception as _ex:
            _txt_prop = ""
        e = _email(pasta, f"Email_Indutor_{tag}.txt", _para(f0),
                   f"Cotação: Indutor trifásico p/ filtro senoidal {L.l_uh:.0f} µH @ {L.i_nom_a:.0f} A – {ped['tensao_v']:g} V "
                   f"({q} pç) + dados técnicos e ensaios ({cod})",
                   SI.corpo_email(L, proj, arr, cat, ped, q, tag, _ola(f0), _extenso, f0.get("ref"))
                   .replace("\nCritério de aceitação", (ALT.texto_email(alt) if L is proj.l1 else "") + "\nCritério de aceitação", 1)
                   + "\n" + _txt_prop + assin)
        saidas[f"indutor_{tag}"] = (p, e)

    # --- CAPACITORES
    b = proj.banco
    from .dimensionamento import limites_capacitor
    capd = next((c for c in cat.get("capacitores", []) if c["id"] == b.cap_id), {}) or dict(uf=b.uf_unit, v_ac=b.v_unit)
    lc = limites_capacitor(capd, cat)
    est = int(capd.get("estoque", 0) or 0)
    n_nec = b.n_total * q
    n_comp = max(0, n_nec - est)
    e_ = getattr(proj, "estresse_capacitor", {}) or {}
    d = _novo("Especificação Técnica – Capacitores", f"Banco de capacitores para filtro senoidal – {cod}", proj, cat)
    from . import spec_capacitor as SC
    figc = None
    try:
        figc = SC.grafico_corrente(proj, cat, os.path.join(pasta, f"Corrente_Capacitor_{cod}.png"),
                                   pasta_atp=os.path.join(os.path.dirname(pasta), "01_Engenharia", "ATP"))
    except Exception:
        figc = None
    SC.escrever_et(d, proj, cat, ped, q, _kv, _tabela, _bullets, _f, figura=figc)
    p = os.path.join(pasta, f"ET_Capacitores_{cod}.docx")
    d.save(p)
    fc = forn["capacitor"][0]
    from . import conferencia as _CF
    _xlc = f"Formulario_Resposta_Capacitor_{cod}.xlsx"
    try:
        _CF.formulario_xlsx("capacitor", os.path.join(pasta, _xlc), cod, f"Resposta técnica – Capacitor {b.uf_unit:g} µF {b.v_unit:g} V")
        _txt_pc = _CF.texto_email_proposta("capacitor", _xlc)
    except Exception:
        _txt_pc = ""
    e = _email(pasta, "Email_Capacitores.txt", _para(fc),
               f"Cotação – capacitor {b.pn} {b.uf_unit:g} µF {b.v_unit:g} V – {n_nec} pç – filtro senoidal ({cod})",
               SC.corpo_email(proj, cat, ped, q, _ola(fc), fc.get("ref")) + "\n" + _txt_pc + assin)
    saidas["capacitores"] = (p, e)

    # --- RESISTORES DE AMORTECIMENTO
    am = proj.amortecimento
    if am:
        d = _novo("Especificação Técnica – Resistores de Amortecimento", cod, proj, cat)
        _kv(d, [("Tipo", "Resistor de potência fio em tubo cerâmico (ou grade inox), baixa indutância"),
                ("Resistência", f"{am.r_ramo_ohm:.3f} Ω ±10 %"), ("Potência nominal", f"{am.p_nominal_w:g} W (dissipação de operação {am.p_ramo_w:.0f} W)"),
                ("Corrente", f"{am.i_ramo_rms:.0f} A RMS com componentes até {3 * proj.fs_hz / 1000:g} kHz"),
                ("Isolação", "1,1 kV para massa"), ("Montagem", "Suportes isolados, terminais parafusados"),
                ("Quantidade", f"{3 * q} peças")])
        p = os.path.join(pasta, f"ET_Resistores_Amortecimento_{cod}.docx")
        d.save(p)
        e = _email(pasta, "Email_Resistores.txt", "confirmar",
                   f"Cotação – {3 * q} resistores {am.r_ramo_ohm:.2f} Ω {am.p_nominal_w:g} W ({cod})",
                   f"Olá,\n\nSolicito cotação de {3 * q} resistores de potência {am.r_ramo_ohm:.3f} Ω, {am.p_nominal_w:g} W, "
                   f"{am.i_ramo_rms:.0f} A RMS, isolação 1,1 kV, baixa indutância, conforme ET anexa." + assin)
        saidas["resistores"] = (p, e)

    # --- CAIXA
    d = _novo("Especificação Técnica – Caixa Metálica", cod, proj, cat)
    _kv(d, [("Tipo", f"Armário {arr.caixa_tipo} {arr.caixa_l}×{arr.caixa_a}×{arr.caixa_p} mm (L×A×P)"),
            ("Material", "Aço carbono 1,5 mm (corpo) / 2,0 mm (porta e placa) – pintura epóxi-pó RAL 7035, 70 µm"),
            ("Grau de proteção", f"IP{arr.caixa_ip} (com ventiladores e filtros)"),
            ("Acessórios", "Placa de montagem galvanizada; chapa de passagem de cabos inferior removível; fecho com chave; "
                           "olhais de içamento; terminal de aterramento na porta" + ("; soleira 100 mm" if arr.soleira_mm else "")),
            ("Recortes", f"{arr.n_ventiladores} recortes para ventilador (topo da porta) e {arr.n_ventiladores} para grelha de entrada (base da porta) – conforme desenho"),
            ("Reforço", "Perfis na base para fixação do indutor (massa estimada " + f"{proj.l1.massa_kg:.0f} kg)"),
            ("Quantidade", f"{q}")])
    d.add_paragraph("Desenho de referência: ver folhas 1 e 2 do arquivo de desenhos anexo.")
    p = os.path.join(pasta, f"ET_Caixa_Metalica_{cod}.docx")
    d.save(p)
    fx = forn["caixa"][0]
    e = _email(pasta, "Email_Caixa.txt", _para(fx),
               f"Cotação – {q} armário(s) {arr.caixa_l}x{arr.caixa_a}x{arr.caixa_p} mm IP{arr.caixa_ip} para filtro senoidal ({cod})",
               f"{_ola(fx)}\n\n(Usar somente se a caixa não for comprada pela montadora.)\n\n"
               f"Solicito cotação de {q} armário(s) {arr.caixa_tipo} {arr.caixa_l} × {arr.caixa_a} × {arr.caixa_p} mm (L × A × P), IP{arr.caixa_ip}, "
               "RAL 7035, conforme ET e desenho anexos:\n"
               "- placa de montagem galvanizada e chapa de passagem de cabos inferior removível;\n"
               f"- {arr.n_ventiladores} recortes para ventiladores no topo da porta e {arr.n_ventiladores} para grelhas de entrada na base;\n"
               f"- reforço na base para o indutor (≈ {proj.l1.massa_kg:.0f} kg) e olhais de içamento;\n"
               "- fecho com chave e aterramento da porta.\n\n"
               "Favor informar preço, prazo e frete." + assin)
    saidas["caixa"] = (p, e)

    # --- CABOS E MISCELÂNEA
    itens = [i for i in orc.itens if i.grupo == "CABOS_MISC" or (i.grupo == "CAIXA" and "Caixa/armário" not in i.descricao)]
    d = _novo("Lista de Material – Cabos e Miscelânea", cod, proj, cat)
    _tabela(d, ["#", "Descrição", "Especificação", "Qtd/filtro", "Un", f"Qtd total ({q})"],
            [(k + 1, i.descricao, i.especificacao, _f(i.qtd, 1), i.un, _f(i.qtd * q, 1)) for k, i in enumerate(itens)],
            [0.8, 5.5, 5.5, 1.8, 1.0, 2.4], tam=8)
    p = os.path.join(pasta, f"LM_Cabos_Miscelanea_{cod}.docx")
    d.save(p)
    fm = forn["cabos_misc"][0]
    e = _email(pasta, "Email_Cabos_Misc.txt", _para(fm), f"Cotação – cabos e materiais elétricos para {q} filtro(s) senoidal(is) ({cod})",
               f"{_ola(fm)}\n\n(Usar somente se o material não for comprado pela montadora.)\n\n"
               f"Solicito cotação dos materiais da lista anexa para {q} filtro(s): cabos flexíveis 0,6/1 kV HEPR 90 °C "
               f"({arr.cabos[0]['desc'] if arr.cabos else 'conforme lista'}), terminais de compressão, barramentos/bornes, "
               f"{arr.n_ventiladores * q} ventiladores com filtro, termostatos, grelhas e acessórios – quantidades totais na última coluna.\n\n"
               "Favor informar preço, prazo e disponibilidade." + assin)
    saidas["cabos_misc"] = (p, e)

    # --- PLAQUETA DE IDENTIFICAÇÃO E ADESIVOS
    fe = (forn.get("etiquetas") or [{}])[0]
    b = proj.banco
    dados_placa = [("Fabricante", emp["nome"]), ("Produto", f"Filtro senoidal {proj.topologia} – {cod}"),
                   ("Corrente nominal", f"{ped['corrente_a']:g} A"), ("Tensão nominal", f"{ped['tensao_v']:g} V – {ped['freq_rede_hz']:g} Hz (saída 0–{max(ped['f_saida_max_hz'], 60):g} Hz)"),
                   ("Frequência de chaveamento", f"{proj.fs_hz / 1000:g} kHz fixa (mínima)"), ("Indutância", f"{proj.l1.l_uh:.0f} µH/fase"),
                   ("Capacitância", f"{b.n_total} × {b.uf_unit:g} µF {b.v_unit:g} V em {b.ligacao.lower()}"),
                   ("Perdas", f"{arr.perda_total_w:.0f} W"), ("Grau de proteção", f"IP{arr.caixa_ip}"), ("Massa", f"{arr.massa_total_kg:.0f} kg"),
                   ("Nº de série / data", "___ / ___")]
    d = _novo("Especificação – Plaqueta de identificação e adesivos", cod, proj, cat)
    d.add_heading("1. Plaqueta de identificação (aço inox ou alumínio anodizado, gravação permanente, 100 × 70 mm)", 2)
    _kv(d, dados_placa)
    d.add_heading("2. Adesivos (vinil com laminação UV)", 2)
    _bullets(d, ["Advertência de choque elétrico (ISO 7010 W012) – porta",
                 "\"Capacitores – aguarde 5 min após desligar antes de abrir\" – porta",
                 "\"Superfície quente\" (ISO 7010 W017) – próximo ao indutor",
                 f"\"Inversor deve operar com frequência de chaveamento FIXA ≥ {proj.fs_hz / 1000:g} kHz\" – porta, interna",
                 "Identificação de bornes: ENTRADA INVERSOR U1 V1 W1 / SAÍDA MOTOR U2 V2 W2 / PE",
                 "Logotipo Electric Service"])
    p = os.path.join(pasta, f"ET_Plaqueta_Adesivos_{cod}.docx")
    d.save(p)
    e = _email(pasta, "Email_Plaqueta_Adesivos.txt", _para(fe),
               f"[ORÇAMENTO] – Plaquetas e adesivos para {q} painel(is) de filtro senoidal ({cod})",
               f"{_ola(fe)}\n\nPreciso de orçamento para {q} jogo(s) de identificação de painel, conforme especificação anexa:\n"
               f"- {q} plaqueta(s) de identificação 100 × 70 mm, gravação permanente, com os dados técnicos do filtro;\n"
               f"- {q} jogo(s) de adesivos: advertência de choque elétrico, capacitores (aguardar 5 min), superfície quente, "
               "aviso de frequência de chaveamento fixa, identificação de bornes e logotipo.\n\n"
               "Favor informar preço e prazo." + assin)
    saidas["plaqueta"] = (p, e)
    return saidas


# ------------------------------------------------------------------ montadora: RFQ e caderno de montagem
def rfq_montagem(proj, arr, orc, cat, pasta):
    ped = proj.pedido
    q = int(ped.get("quantidade", 1) or 1)
    cod = proj_codigo(proj)
    d = _novo("Solicitação de Orçamento de Montagem", f"Filtro senoidal {proj.topologia} {ped['corrente_a']:g} A – {q} unidade(s) – {cod}", proj, cat)
    d.add_heading("1. Objeto", 1)
    d.add_paragraph(f"Montagem completa de {q} filtro(s) senoidal(is) em caixa metálica, incluindo compra dos materiais indicados como "
                    "'Montadora', cabeação, identificação, ensaios de rotina, embalagem e relatório. "
                    "A Electric Service fornecerá os indutores e capacitores (material de terceiros sob guarda da montadora).")
    d.add_heading("2. Materiais e responsabilidade", 1)
    _tabela(d, ["#", "Descrição", "Qtd/filtro", "Un", "Fornecido por"],
            [(i.item, i.descricao, _f(i.qtd, 1), i.un, i.fornecido_por) for i in orc.itens if i.grupo != "MONTAGEM"],
            [0.8, 9.5, 2.0, 1.2, 3.5], tam=8)
    d.add_heading("3. Dados de montagem", 1)
    _kv(d, [("Caixa", f"{arr.caixa_l}×{arr.caixa_a}×{arr.caixa_p} mm {arr.caixa_tipo} IP{arr.caixa_ip}"),
            ("Massa do indutor", f"≈ {proj.l1.massa_kg:.0f} kg (estimado)"), ("Nº de capacitores", f"{proj.banco.n_total} por filtro"),
            ("Cabo de potência", arr.cabos[0]["desc"]), ("Dissipação", f"{arr.perda_total_w:.0f} W – {arr.n_ventiladores} ventiladores")])
    d.add_heading("4. Solicitamos informar", 1)
    _bullets(d, ["Preço de mão de obra por unidade e preço dos materiais da montadora (separados).",
                 "Prazo de fabricação após recebimento de indutores/capacitores.", "Condição de pagamento e validade.",
                 "Ensaios inclusos (isolamento, tensão aplicada, continuidade, funcional) e formato do relatório.",
                 "Embalagem (palete/engradado para transporte rodoviário) e frete até Porto Alegre ou direto ao cliente."])
    d.add_paragraph("Anexos: desenhos (vistas, 3D, diagrama elétrico, lista de cabos) e Caderno de Montagem.")
    p = os.path.join(pasta, f"RFQ_Montagem_{cod}.docx")
    d.save(p)
    f0 = cat["fornecedores"]["montagem"][0]
    emp = cat["empresa"]
    b = proj.banco
    e = _email(pasta, "Email_Montagem.txt", _para(f0), f"Orçamento de montagem – {q} filtro(s) senoidal(is) {ped['corrente_a']:g} A / {ped['tensao_v']:g} V ({cod})",
               f"{_ola(f0)}\n\nSegue solicitação de orçamento para a montagem completa de {q} filtro(s) senoidal(is) "
               f"{proj.topologia} {ped['corrente_a']:g} A / {ped['tensao_v']:g} V, conforme RFQ, desenhos e caderno de montagem anexos.\n\n"
               "Escopo resumido:\n"
               f"- Armário {arr.caixa_l} × {arr.caixa_a} × {arr.caixa_p} mm IP{arr.caixa_ip} com {arr.n_ventiladores} ventiladores "
               f"(dissipação ≈ {arr.perda_total_w:.0f} W por filtro);\n"
               f"- 1 indutor trifásico de ≈ {proj.l1.massa_kg:.0f} kg e {b.n_total} capacitores {b.uf_unit:g} µF em {b.ligacao.lower()} "
               f"({b.n_por_ramo} por ramo) – FORNECIDOS POR NÓS;\n"
               f"- cabeação de potência ({(arr.cabos[0]['desc'] if arr.cabos else '').lower()}), bornes, identificação, plaqueta e adesivos;\n"
               "- Ensaios de rotina: continuidade, isolamento, tensão aplicada, conferência do fechamento do banco, medição de C por ramo "
               "e teste funcional dos ventiladores, com relatório;\n"
               "- Embalagem para transporte rodoviário.\n\n"
               "Favor informar separadamente: mão de obra por unidade, materiais de vocês, prazo após o recebimento dos indutores e "
               "capacitores, condição de pagamento e frete (Porto Alegre ou direto ao cliente)."
               f"\n\nAtenciosamente,\n{emp['responsavel']}\n{emp['nome']}\n{emp['email']} | {emp['telefone']}")
    return p, e


def caderno_montagem(proj, arr, orc, cat, pasta, desenhos_png):
    ped = proj.pedido
    cod = proj_codigo(proj)
    b = proj.banco
    am = proj.amortecimento
    d = _novo("Caderno de Montagem e Ensaios", f"Filtro senoidal {proj.topologia} {ped['corrente_a']:g} A {ped['tensao_v']:g} V – {cod}", proj, cat)
    d.add_paragraph("Documento para a empresa montadora após confirmação do pedido. Seguir rigorosamente os desenhos anexos; "
                    "qualquer divergência deve ser consultada à Electric Service antes da execução.")
    d.add_heading("1. Segurança", 1)
    _bullets(d, ["Capacitores armazenam energia: manter curto-circuitados até a conexão final; após ensaios, aguardar 5 min e verificar ausência de tensão.",
                 f"Indutor com massa ≈ {proj.l1.massa_kg:.0f} kg: içar apenas pelos olhais, com equipamento adequado.",
                 "NR-10 e NR-12 aplicáveis às atividades de montagem e ensaio."])
    d.add_heading("2. Recebimento de materiais", 1)
    _bullets(d, [f"Conferir indutor(es): placa de identificação, indutância declarada {proj.l1.l_uh:.0f} µH, relatório de ensaio.",
                 f"Conferir {b.n_total} capacitores {b.uf_unit:g} µF {b.v_unit:g} V: integridade, data de fabricação, ausência de estufamento.",
                 "Registrar números de série no formulário de rastreabilidade (Anexo A)."])
    d.add_heading("3. Sequência de montagem", 1)
    passos = [
        "Preparar a caixa: verificar recortes de ventilação, instalar ventiladores (exaustão no topo) e grelhas com filtro (entrada na base).",
        "Instalar perfis de reforço na base e fixar o indutor L1 com parafusos M10 classe 8.8 + arruela de pressão (furos conforme desenho do fabricante).",
        "Instalar na placa de montagem: suportes do banco de capacitores (3 linhas – ramos " + ("U-V, V-W, W-U" if b.ligacao == "Delta" else "U-N, V-N, W-N") + "), "
        "mantendo 30 mm entre capacitores e 50 mm de qualquer fonte de calor.",
    ]
    if am:
        passos.append(f"Instalar os 3 resistores de amortecimento ({am.r_ramo_ohm:.3f} Ω / {am.p_nominal_w:g} W) acima do banco, em suportes isolados, "
                      "com afastamento mínimo de 100 mm dos capacitores e de cabos – dissipam ~" + f"{am.p_ramo_w:.0f} W cada.")
    passos += [
        "Instalar bornes de potência X1 (entrada do inversor) e X2 (saída para o motor), barramento PE e bornes auxiliares X3.",
        f"Cabeação de potência: {arr.cabos[0]['desc']}; terminais tubulares prensados com matriz hexagonal; torque conforme fabricante dos bornes.",
        "Derivação para o banco: a partir dos terminais de SAÍDA do indutor (lado motor); identificar com anilhas.",
        f"Ligar capacitores de cada ramo em paralelo ({b.n_por_ramo} por ramo) com jumpers {arr.cabos[3]['secao']} mm²; respeitar torque dos terminais do capacitor.",
        f"Instalar resistor de descarga ({b.r_descarga_mohm * 1000:.0f} kΩ) em cada capacitor, caso não possua interno.",
        "Aterramento: carcaça do indutor, placa, porta (trança) e caixa ao barramento PE.",
        "Circuito auxiliar: termostato NA ajustado em 40 °C comandando os ventiladores (220 Vca externo via X3).",
        "Identificação: anilhas em todos os cabos, etiquetas de componentes (L1, C1.x…, RD, X1, X2, X3, PE), placa de dados e placas de advertência.",
    ]
    for k, s in enumerate(passos, 1):
        d.add_paragraph(f"{k}. {s}")
    d.add_heading("4. Desenhos", 1)
    for pth in desenhos_png:
        _img(d, pth, 17)
    d.add_heading("5. Ensaios de rotina (registrar no relatório)", 1)
    _tabela(d, ["Ensaio", "Critério", "Resultado"], [
        ("Inspeção visual e torque", "Conforme desenho/torque", ""),
        ("Indutância por fase (LCR 60 Hz)", f"{proj.l1.l_uh:.0f} µH ±5 %", ""),
        ("Capacitância por ramo", f"{b.c_ramo_uf:g} µF −5/+10 %", ""),
        ("Resistência dos resistores de amortecimento", f"{am.r_ramo_ohm:.3f} Ω ±10 %" if am else "n/a", ""),
        ("Isolamento 1000 Vcc fase-terra", "≥ 100 MΩ", ""),
        ("Tensão aplicada 2,5 kV / 1 min fase-terra", "Sem descarga", ""),
        ("Continuidade PE", "≤ 0,1 Ω", ""),
        ("Funcional ventiladores / termostato", "Partida a 40 °C", ""),
        ("Descarga dos capacitores", "≤ 50 V em 60 s", ""),
    ], [6.5, 5.5, 5.0])
    d.add_heading("6. Embalagem e expedição", 1)
    _bullets(d, ["Fixar o indutor contra vibração; calçar capacitores.", "Palete de madeira com fixação da caixa, filme stretch e cantoneiras.",
                 "Anexar relatório de ensaio e diagrama elétrico dentro da porta (porta-documentos)."])
    d.add_heading("Anexo A – Rastreabilidade", 1)
    _tabela(d, ["Componente", "Fabricante", "Nº de série / lote"], [("Indutor L1", "", "")] + ([("Indutor L2", "", "")] if proj.l2 else [])
            + [(f"Capacitores ramo {r}", b.fabricante, "") for r in (1, 2, 3)] + [("Caixa", "", "")], [6, 5, 6])
    p = os.path.join(pasta, f"Caderno_Montagem_{cod}.docx")
    d.save(p)
    return p


# ------------------------------------------------------------------ planilha
def planilha_custos(proj, arr, orc, cat, pasta):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
    wb = Workbook()
    ws = wb.active
    ws.title = "BOM"
    cab = ["Item", "Grupo", "Fornecedor", "Descrição", "Especificação", "Qtd/filtro", "Un", "Custo unit. (R$)", "Total/filtro (R$)", "Fornecido por"]
    ws.append(cab)
    for i in orc.itens:
        ws.append([i.item, i.grupo, i.fornecedor, i.descricao, i.especificacao, i.qtd, i.un, i.custo_unit, None, i.fornecido_por])
        r = ws.max_row
        ws.cell(r, 9).value = f"=F{r}*H{r}"
    n = ws.max_row
    ws.append([])
    ws.append(["", "", "", "CUSTO TOTAL POR FILTRO", "", "", "", "", f"=SUM(I2:I{n})"])
    tot_row = ws.max_row
    azul = PatternFill("solid", fgColor="1F3A5F")
    for c in ws[1]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = azul
        c.alignment = Alignment(wrap_text=True, vertical="center")
    for row in ws.iter_rows(min_row=2, max_row=n):
        for c in row:
            c.alignment = Alignment(wrap_text=True, vertical="top")
        row[7].number_format = row[8].number_format = '"R$" #,##0.00'
    ws.cell(tot_row, 4).font = Font(bold=True)
    ws.cell(tot_row, 9).font = Font(bold=True)
    ws.cell(tot_row, 9).number_format = '"R$" #,##0.00'
    for k, w in enumerate([6, 12, 20, 45, 55, 10, 6, 14, 15, 16], 1):
        ws.column_dimensions[get_column_letter(k)].width = w
    ws.freeze_panes = "A2"

    # Preço
    wp = wb.create_sheet("Preço")
    com = cat["comercial"]
    imp = com["impostos"]
    linhas = [("Custo por filtro (R$)", f"=BOM!I{tot_row}"), ("ICMS (%)", imp["icms_interestadual_pct"]), ("PIS (%)", imp["pis_pct"]),
              ("COFINS (%)", imp["cofins_pct"]), ("IRPJ+CSLL presumido (%)", imp["irpj_csll_pct"]), ("Margem (%)", com["margem_pct"]),
              ("Comissão (%)", com["comissao_pct"]), ("Frete (%)", com["frete_pct"]),
              ("Divisor", "=1-SUM(B3:B9)/100"), ("Preço unitário calculado (R$)", "=B2/B10"),
              ("Preço unitário arredondado (R$)", "=CEILING(B11,50)"), ("Quantidade", orc.quantidade),
              ("Preço total (R$)", "=B12*B13"), ("Lucro bruto por filtro (R$)", "=B12*B7/100"), ("IPI (%) – por fora", imp["ipi_pct"])]
    wp.append(["Parâmetro", "Valor"])
    for a, bb in linhas:
        wp.append([a, bb])
    for c in wp[1]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = azul
    for r in (2, 11, 12, 14, 15):
        wp.cell(r, 2).number_format = '"R$" #,##0.00'
    for r in range(3, 10):
        wp.cell(r, 2).fill = PatternFill("solid", fgColor="FFF4CC")
    wp.column_dimensions["A"].width = 34
    wp.column_dimensions["B"].width = 18
    wp["D2"] = "Células amarelas são editáveis; o preço recalcula automaticamente."

    # Lista técnica
    wt = wb.create_sheet("Lista técnica")
    wt.append(["Grandeza", "Valor"])
    b = proj.banco
    dados = [("Topologia", proj.topologia), ("fs (kHz)", proj.fs_hz / 1000), ("L1 (µH)", proj.l1.l_uh), ("uk (%)", proj.l1.uk_pct),
             ("I térmica L1 (A)", proj.l1.i_nom_a), ("Isat L1 (A pico)", proj.l1.i_sat_a), ("Capacitores", f"{b.n_total} x {b.uf_unit} µF {b.v_unit} V {b.ligacao}"),
             ("C Y equivalente (µF)", b.c_y_uf), ("fr (Hz)", round(proj.fr_hz)), ("Rd por ramo (Ω)", proj.amortecimento.r_ramo_ohm if proj.amortecimento else 0),
             ("Caixa", arr.caixa_id), ("Perdas (W)", arr.perda_total_w), ("Massa (kg)", arr.massa_total_kg)]
    for x in dados:
        wt.append(list(x))
    wt.column_dimensions["A"].width = 26
    wt.column_dimensions["B"].width = 34
    # Verificações
    wv = wb.create_sheet("Verificações")
    from . import checagem as CK
    wv.append(["Verificação", "Valor", "Limite", "Utilização (%)", "Check", "Referência"])
    for v in proj.verificacoes:
        c_, u_ = CK.de_verificacao(v.ok, v.critico, v.valor, v.limite)
        wv.append([v.item, v.valor, v.limite, None if u_ is None else round(u_, 1), c_, v.referencia])
    CK.colorir_planilha(wv)
    for k, w in enumerate([55, 26, 22, 12, 14, 55], 1):
        wv.column_dimensions[get_column_letter(k)].width = w
    p = os.path.join(pasta, f"{proj_codigo(proj)}_BOM_Custos_Preco.xlsx")
    wb.save(p)
    return p
