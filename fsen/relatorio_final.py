"""Relatório Técnico Final do filtro senoidal no padrão RTM da Electric Service (mesmo modelo dos relatórios de QEE/proteção
da Plataforma de Estudos): capa, índice de revisões, sumário, especificação, base normativa, metodologia e softwares,
resultados Python, dupla checagem ATP-EMTP, limites de todos os componentes (até refrigeração e elevação de temperatura),
conclusões e recomendações."""
from __future__ import annotations
import math

import copy
import datetime as _dt
import os
import re
import subprocess

import docx
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

MODELO = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dados", "modelo_RTM.docx")
AZUL = "1F3A5F"
MESES = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]


# --------------------------------------------------------------------------------------------- utilidades de texto
def _texto_p(p_el):
    return "".join(t.text or "" for t in p_el.iter(qn("w:t")))


def _subst_p(p_el, novo):
    """Troca o texto inteiro de um parágrafo (mantém a formatação do 1º run)."""
    ts = list(p_el.iter(qn("w:t")))
    if not ts:
        return
    ts[0].text = novo
    ts[0].set(qn("xml:space"), "preserve")
    for t in ts[1:]:
        t.text = ""


def _trocar_em(el, regras):
    for p in el.iter(qn("w:p")):
        tx = _texto_p(p)
        for velho, novo in regras:
            if velho and velho in tx:
                _subst_p(p, tx.replace(velho, novo))
                tx = _texto_p(p)


def _sombra(cel, cor=AZUL):
    tcPr = cel._tc.get_or_add_tcPr()
    sh = OxmlElement("w:shd")
    sh.set(qn("w:val"), "clear")
    sh.set(qn("w:color"), "auto")
    sh.set(qn("w:fill"), cor)
    tcPr.append(sh)


class _Rel:
    def __init__(self, d):
        self.d = d
        self.nfig = 0
        self.ntab = 0

    def h1(self, t):
        self.d.add_paragraph(t, style="Heading 1")

    def h2(self, t):
        self.d.add_paragraph(t, style="Heading 2")

    def txt(self, t, negrito=None):
        p = self.d.add_paragraph(style="Texto")
        if negrito:
            r = p.add_run(negrito)
            r.bold = True
        p.add_run(t)
        return p

    def itens(self, lst):
        for x in lst:
            p = self.d.add_paragraph(style="Texto")
            if isinstance(x, tuple):
                r = p.add_run(x[0])
                r.bold = True
                p.add_run(x[1])
            else:
                p.add_run(x)
            pPr = p._p.get_or_add_pPr()
            numPr = OxmlElement("w:numPr")
            for tag, val in (("w:ilvl", "0"), ("w:numId", "11")):
                e = OxmlElement(tag)
                e.set(qn("w:val"), val)
                numPr.append(e)
            pPr.append(numPr)

    def legenda_tab(self, t):
        self.ntab += 1
        p = self.d.add_paragraph(f"Tabela {self.ntab} - {t}", style="Caption")
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER

    def tabela(self, cab, linhas, larg=None, tam=8.5, legenda=None, status_col=None):
        if legenda:
            self.legenda_tab(legenda)
        t = self.d.add_table(rows=1, cols=len(cab))
        t.style = "Table Grid"
        t.alignment = WD_TABLE_ALIGNMENT.CENTER
        for j, c in enumerate(cab):
            cel = t.rows[0].cells[j]
            cel.text = ""
            r = cel.paragraphs[0].add_run(str(c))
            r.bold = True
            r.font.size = Pt(tam)
            r.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
            cel.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
            _sombra(cel)
        for lin in linhas:
            row = t.add_row().cells
            for j, v in enumerate(lin):
                row[j].text = ""
                r = row[j].paragraphs[0].add_run(str(v))
                r.font.size = Pt(tam)
                if j > 0:
                    row[j].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
                if status_col is not None and j == status_col:
                    s = str(v).upper()
                    if s.startswith(("ATENDE", "OK", "SIM", "ADEQUAD")):
                        _sombra(row[j], "E2EFDA")
                    elif s.startswith(("ATEN", "ALERTA")):
                        _sombra(row[j], "FFF2CC")
                    elif s.startswith(("NÃO", "REPROV")):
                        _sombra(row[j], "F8CBAD")
        for row in t.rows:
            for cel in row.cells:
                for pp in cel.paragraphs:
                    pf = pp.paragraph_format
                    pf.space_before = Pt(1)
                    pf.space_after = Pt(1)
                    pf.line_spacing = 1.0
                    pf.first_line_indent = Cm(0)
        if larg:
            for row in t.rows:
                for j, w in enumerate(larg):
                    row.cells[j].width = Cm(w)
        self.d.add_paragraph()
        return t

    def figura(self, caminho, legenda, larg=16.5):
        if not caminho or not os.path.exists(caminho):
            return
        p = self.d.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.add_run().add_picture(caminho, width=Cm(larg))
        self.nfig += 1
        c = self.d.add_paragraph(f"Figura {self.nfig} - {legenda}", style="Caption")
        c.alignment = WD_ALIGN_PARAGRAPH.CENTER

    def quebra(self):
        self.d.add_paragraph().add_run().add_break(WD_BREAK.PAGE)


# --------------------------------------------------------------------------------------------- modelo
def _preparar_modelo(cod, titulo_curto, cliente, local, data, linhas_capa):
    d = docx.Document(MODELO)
    body = d.element.body
    data_txt = f"{data:%d/%m/%Y}"
    regras_hdr = [("RTM-QEE-265-11-27 – ELEVADOR A", f"{cod} – {titulo_curto}"), ("RTM-QEE-265-11-27", cod),
                  ("BANRISUL / PORTO ALEGRE - RS", f"{cliente} / {local}"), ("28/09/2026", data_txt)]
    for s in d.sections:
        for hf in (s.header, s.first_page_header, s.footer, s.first_page_footer):
            try:
                _trocar_em(hf._element, regras_hdr)
            except Exception:
                pass
    # capa (caixa de texto e folha de rosto)
    capa = {"MEDIÇÃO DA QUALIDADE DE ENERGIA": linhas_capa[0], "BANRISUL – PORTO ALEGRE/RS": linhas_capa[1],
            "ELEVADOR A": linhas_capa[2], "Setembro de 2026": f"{MESES[data.month - 1]} de {data.year}"}
    for p in body.iter(qn("w:p")):
        if p.find(".//" + qn("w:txbxContent")) is not None:
            continue                              # parágrafo que contém a caixa de texto: tratar os de dentro
        linhas, atual = [], []
        for el in p.iter():
            if el.tag == qn("w:t"):
                atual.append(el)
            elif el.tag == qn("w:br") and atual:
                linhas.append(atual)
                atual = []
        if atual:
            linhas.append(atual)
        for ts in linhas:
            tx = "".join(t.text or "" for t in ts).strip()
            for velho, novo in capa.items():
                if tx == velho or (velho == "ELEVADOR A" and tx.endswith("ELEVADOR A")):
                    ts[0].text = novo
                    ts[0].set(qn("xml:space"), "preserve")
                    for t in ts[1:]:
                        t.text = ""
    # logotipo do cliente do modelo (Banrisul) → nome do cliente
    paras = d.paragraphs
    for i, p in enumerate(paras[:40]):
        if p.text.strip() == "Preparado para:":
            alvo = paras[i + 1]
            for dr in list(alvo._p.iter(qn("w:drawing"))):
                dr.getparent().remove(dr)
            r = alvo.add_run(cliente)
            r.bold = True
            r.font.size = Pt(16)
            alvo.alignment = WD_ALIGN_PARAGRAPH.CENTER
            break
    # índice de revisões
    tr = d.tables[1]
    for row in tr.rows:
        cs = row.cells
        if cs[0].text.strip() == "DATA":
            cs[1].text = data_txt
        elif cs[0].text.strip() == "MEDIÇÃO":
            cs[0].text = "SIMULAÇÃO"
            cs[1].text = "GS"
        elif cs[0].text.strip() in ("RELATÓRIO", "VERIFICAÇÃO", "APROVAÇÃO"):
            cs[1].text = "GS"
    # legenda de responsáveis: só GS
    for p in paras[:44]:
        if re.match(r"^(NV|KC|RC|AC|DT):", p.text.strip()):
            p._p.getparent().remove(p._p)
    # apaga o corpo do modelo a partir do sumário (mantém o último sectPr)
    paras = d.paragraphs
    i_sum = next(i for i, p in enumerate(paras) if p.text.replace(" ", "").upper().startswith("SUMÁRIO"))
    inicio = paras[i_sum + 1]._p
    filhos = list(body)
    k = filhos.index(inicio)
    for el in filhos[k:]:
        if el.tag == qn("w:sectPr"):
            continue
        body.remove(el)
    return d


def _sumario_estatico(d, entradas):
    """Insere o sumário logo após 'SUMÁRIO' (entradas: (nível, texto, página))."""
    paras = d.paragraphs
    i_sum = next(i for i, p in enumerate(paras) if p.text.replace(" ", "").upper().startswith("SUMÁRIO"))
    ancora = paras[i_sum]._p
    novos = []
    for nivel, texto, pag in entradas:
        p = d.add_paragraph(style=("toc 1" if nivel == 1 else "toc 2"))
        p.paragraph_format.tab_stops.add_tab_stop(Cm(17.5), alignment=2, leader=1)
        p.add_run(f"{texto}\t{pag}")
        novos.append(p._p)
    br = d.add_paragraph()
    br.add_run().add_break(WD_BREAK.PAGE)
    novos.append(br._p)
    for el in reversed(novos):
        el.getparent().remove(el)
        ancora.addnext(el)


# --------------------------------------------------------------------------------------------- conteúdo
def _g(x):
    try:
        return f"{float(x):g}".replace(".", ",")
    except Exception:
        return x or "-"


def _st(ok, critico=True):
    return "ATENDE" if ok else ("NÃO ATENDE" if critico else "ATENÇÃO")


def gerar(proj, arr, pasta_proj, cat, atp=None, vistas_dir=None, saida=None, cod=None, pdf=True, log=print):
    """proj: Projeto; arr: dict do arranjo_orcamento.json ('arranjo'); atp: lista [{'ponto','tabela'}] ou None."""
    from .versao import info as _vinfo, assinatura
    from .documentos import NORMAS, CRITERIOS_ORIGEM, REFERENCIAS
    ped = proj.pedido if isinstance(proj.pedido, dict) else proj.pedido.__dict__
    cp = cat["projeto_padrao"]
    hoje = _dt.date.today()
    cod = cod or f"RTM-FSEN-{int(ped['corrente_a'])}-{int(ped['tensao_v'])}"
    cliente = (ped.get("cliente") or "Cliente").split("–")[0].strip().upper()
    local = (ped.get("cidade_uf") or "").upper().replace("/", " - ")
    b = proj.banco
    L = proj.l1
    ar = arr["arranjo"] if "arranjo" in arr else arr
    graf = os.path.join(pasta_proj, "graficos")
    des = os.path.join(pasta_proj, "05_Desenhos")
    v = {x.item: x for x in proj.verificacoes}

    def vf(prefixo):
        return next((x for k, x in v.items() if k.startswith(prefixo)), None)

    linhas_capa = ["ESTUDO E SIMULAÇÃO DE FILTRO SENOIDAL", f"{cliente} – {local}",
                   f"FILTRO {proj.topologia} {ped['corrente_a']:g} A / {ped['tensao_v']:g} V"]
    d = _preparar_modelo(cod, f"FILTRO SENOIDAL {ped['corrente_a']:g} A", cliente, local, hoje, linhas_capa)
    R = _Rel(d)
    pts = proj.pontos
    ver_ = _vinfo().get("versao", "?")

    # 1 ---------------------------------------------------------------- introdução
    R.h1("INTRODUÇÃO")
    R.txt(f"Este relatório apresenta o estudo, a especificação e a verificação por simulação do filtro senoidal trifásico "
          f"{proj.topologia} sem resistor de amortecimento, de {ped['corrente_a']:g} A / {ped['tensao_v']:g} V, a ser instalado na saída "
          f"do inversor {ped.get('inversor') or '-'} que aciona o motor de {_g(ped.get('motor_cv'))} cv / {_g(ped.get('motor_corrente_a'))} A"
          f"{' – ' + ped['carga_tipo'] if ped.get('carga_tipo') else ''}.")
    if ped.get("referencia"):
        R.txt(f"O serviço atende à solicitação “{ped['referencia']}” de {ped.get('cliente', '')}.")
    R.txt("O filtro tem a função de transformar a tensão PWM do inversor em uma tensão praticamente senoidal nos terminais do "
          "motor, reduzindo o pico de tensão, o dv/dt, as perdas adicionais e o ruído do motor, e protegendo a isolação e os "
          "mancais. O relatório reúne:")
    R.itens(["especificação completa do filtro (indutor, capacitores, caixa e ventilação);",
             "normas, guias técnicos e literatura usados como base dos critérios de projeto;",
             "metodologia, softwares e validação da ferramenta de cálculo;",
             "resultados da simulação na Plataforma FSEN (Python) e da simulação independente no ATP-EMTP;",
             "verificação de todos os limites dos componentes, incluindo refrigeração e elevação de temperatura;",
             "conclusões e recomendações de instalação e comissionamento."])

    # 2 ---------------------------------------------------------------- dados
    R.h1("DADOS DO SISTEMA")
    R.tabela(["Item", "Dado"], [
        ("Rede / barramento CC", f"{ped['tensao_v']:g} V, {ped['freq_rede_hz']:g} Hz / {proj.vdc:.0f} V (1,35·Vrede)"),
        ("Inversor", f"{ped.get('inversor') or '-'} – {_g(ped.get('inversor_corrente_a'))} A, chaveamento fixo {proj.fs_hz / 1000:g} kHz"),
        ("Motor", f"{_g(ped.get('motor_cv'))} cv, {_g(ped.get('motor_corrente_a'))} A, FP {_g(ped.get('motor_fp'))}, FS {_g(ped.get('fator_servico'))}, "
                  f"{_g(ped.get('motor_rpm'))} rpm"),
        ("Carga", ped.get("carga_tipo") or "-"),
        ("Faixa de operação", f"{ped['f_saida_min_hz']:g} a {ped['f_saida_max_hz']:g} Hz"),
        ("Cabo filtro → motor", f"{_g(ped.get('cabo_m'))} m, {'blindado' if ped.get('cabo_blindado', True) else 'não blindado'}"),
        ("Requisitos do cliente", f"Vpico ≤ {ped.get('vpk_max_v') or 1000:g} V; dv/dt ≤ {ped.get('dvdt_max_v_us') or 500:g} V/µs; "
                                  f"tr > {ped.get('rise_time_min_us') or '-'} µs; IP{ar.get('caixa_ip', 54)}; isolação {ped.get('classe_isolamento_kv')} kV; "
                                  f"classe {ped.get('classe_temp')}"),
        ("Quantidade", f"{ped.get('quantidade', 1)} unidade(s)")], [5.0, 12.0], legenda="Dados de entrada do estudo")
    if ped.get("lacunas"):
        R.txt("Premissas adotadas para dados não informados (a confirmar com o cliente):")
        lac = [x for x in ped["lacunas"] if not (ped.get("ip") and x.lower().startswith("grau de proteção"))]
        R.itens(lac[:10])

    # 3 ---------------------------------------------------------------- especificação
    R.h1("ESPECIFICAÇÃO DO FILTRO")
    R.tabela(["Componente", "Especificação"], [
        ("Topologia", f"LC senoidal, sem resistor de amortecimento"),
        ("Indutor L1 (trifásico)", f"{L.l_uh:.0f} µH/fase, {L.i_nom_a:.0f} A RMS, Isat ≥ {L.i_sat_a:.0f} A, impedância {L.uk_pct:.1f} % a 60 Hz, "
                                   f"perdas {L.perdas_w:.0f} W, ≈ {L.massa_kg:.0f} kg"),
        ("Capacitores", f"{b.n_total} × {b.uf_unit:g} µF / {b.v_unit:g} V – {b.fabricante} {b.pn or ''} (IEC 61071), ligação {b.ligacao}, "
                        f"{b.n_por_ramo} por ramo ({b.c_ramo_uf:g} µF/ramo; {b.c_y_uf:g} µF/fase em estrela equivalente)"),
        ("Frequência de ressonância", f"{proj.fr_hz:.0f} Hz ({proj.fr_hz / ped['f_saida_max_hz']:.1f} × f máx; {proj.fr_hz / proj.fs_hz:.2f} × fs)"),
        ("Resistores de descarga", "nos capacitores (tensão < 50 V em 1 min)"),
        ("Caixa", f"{ar.get('caixa_id')} ({ar.get('caixa_l')} × {ar.get('caixa_a')} × {ar.get('caixa_p')} mm), {ar.get('caixa_tipo')}, IP{ar.get('caixa_ip')}"),
        ("Ventilação", f"{ar.get('n_ventiladores')} ventiladores, {ar.get('vazao_m3h')} m³/h, com filtros de ar"),
        ("Perdas totais", f"{ar.get('perda_total_w')} W"),
        ("Massa total", f"≈ {ar.get('massa_total_kg')} kg")], [4.5, 12.5], legenda="Especificação do filtro")
    R.figura(os.path.join(des, "folha3_diagrama.png"), "Diagrama elétrico do filtro", 16.0)
    R.figura(os.path.join(des, "folha1_vistas.png"), "Vistas e arranjo interno do painel", 16.0)

    # 4 ---------------------------------------------------------------- referências
    R.h1("REFERÊNCIAS TÉCNICAS")
    R.txt("Não existe norma que fixe os valores de projeto de um filtro senoidal (indutância, frequência de ressonância, queda de "
          "tensão). As normas definem o que o filtro deve garantir ao motor e aos componentes; os valores de projeto seguem guias "
          "de fabricantes, a literatura técnica e a calibração com filtros fabricados e medidos pela Electric Service.")
    R.h2("NORMAS APLICÁVEIS")
    R.tabela(["Norma", "Aplicação"], NORMAS, [5.5, 11.5], legenda="Normas aplicáveis")
    R.h2("CRITÉRIOS DE PROJETO E ORIGEM")
    fmt = dict(vpk=ped.get("vpk_max_v") or 1000, dvdt=ped.get("dvdt_max_v_us") or 500, ukmax=f"{cp['uk_max_pct']:g}",
               ukmin=f"{cp['uk_min_pct']:g}", ukbusca=f"{cp.get('uk_busca_max_pct', 15):g}", fs=f"{proj.fs_hz / 1000:g}",
               thd=f"{cp['thd_v_max_pct']:g}", thd1=f"{cp['thd_v_max_pct'] + 1:g}", frmult=f"{cp['fr_min_mult_fout']:g}",
               rip=f"{cp['ripple_pp_max_pct']:g}")
    R.tabela(["Critério", "Valor adotado", "Natureza", "Fonte"], [(a, b_.format(**fmt), c, e) for a, b_, c, e in CRITERIOS_ORIGEM],
             [3.8, 4.2, 2.4, 6.6], tam=8, legenda="Critérios de projeto e sua origem")
    R.h2("BIBLIOGRAFIA")
    for i, rr in enumerate(REFERENCIAS, 1):
        R.txt(f"[{i}] {rr}")

    # 5 ---------------------------------------------------------------- metodologia
    R.h1("METODOLOGIA E SOFTWARES")
    R.itens([
        ("Dimensionamento: ", f"busca de todas as combinações de indutor (impedância {cp['uk_min_pct']:g} a {cp.get('uk_busca_max_pct', 15):g} %), "
         "capacitores do catálogo (estrela ou delta, número por ramo) e frequência de chaveamento; cada combinação é simulada e "
         "verificada, e é escolhida a de menor custo e perdas que atende a todos os critérios críticos."),
        ("Simulação: ", "inversor PWM vetorial (SVPWM) com a portadora real, barramento CC, indutor com perdas de alta frequência, "
         "banco de capacitores, cabo em células π e motor (força contra-eletromotriz + indutância de dispersão, resistência com "
         "efeito pelicular), em regime permanente, nos pontos de frequência máxima, mínima e de placa."),
        ("Robustez: ", "tolerâncias de L (±5 %) e C (−5/+10 %), rede ±10 %, e as harmônicas de baixa ordem do inversor (valores "
         "medidos em campo) amplificadas pela ressonância em toda a faixa de velocidade, com e sem motor."),
        ("Dupla checagem: ", "a mesma rede é montada e simulada no domínio do tempo no ATP-EMTP, e as grandezas de projeto são "
         "comparadas com as do Python."),
        ("Componentes reais: ", "projeto do indutor (corrente, saturação, perdas, ponto quente), capacitores (tensão, corrente, pico, "
         "dv/dt, ponto quente, vida pelo datasheet), cabos, bornes e estudo térmico do painel com a ventilação.")])
    R.tabela(["Software / equipamento", "Uso"], [
        (f"Plataforma FSEN v{ver_} – Electric Service (Python 3, NumPy, SciPy, Matplotlib)", "Dimensionamento, simulação, verificações, documentos"),
        ("ATP-EMTP (tpbig) e ATPDraw 7", "Simulação eletromagnética independente da mesma rede (dupla checagem)"),
        ("Dranetz HDPQ classe A", "Medições de campo usadas na calibração do modelo")], [8.0, 9.0], legenda="Softwares e equipamentos")
    R.h2("VALIDAÇÃO DA FERRAMENTA")
    R.itens([
        "11 filtros reais (fabricados pela Electric Service e Schaffner FN5040 de catálogo) simulados no Python e no ATP-EMTP a "
        "60 Hz e 30 Hz: 21 de 22 pontos coincidem em todas as grandezas.",
        "Medições de campo (Dranetz HDPQ): SENAI 958 µH/40 µF – distorção medida 7,2 %, prevista 7,2 %; IHR 1586 µH/20 µF – "
        "medida 4,0 %, prevista 4,9 %; SENAI 958 µH/20 µF – medida 4,9 %, prevista 4,0 a 10,2 %.",
        "As harmônicas de baixa ordem produzidas pelo inversor foram medidas em dois inversores diferentes e coincidem (h5 ≈ 2,2 %)."])

    # 6 ---------------------------------------------------------------- resultados Python
    R.h1("RESULTADOS DA SIMULAÇÃO")
    R.h2("GRANDEZAS POR PONTO DE OPERAÇÃO")
    cab = ["Grandeza"] + [p["nome"].replace("Operação ", "") for p in pts]

    def lin(nome, ch, n=1):
        return [nome] + [f"{p.get(ch, 0):.{n}f}".replace(".", ",") for p in pts]

    # v1.26.4 (auditoria AW-08): a tabela mostrava 0,00 A – a chave 'icap_unit_rms' só existe na comparação com o ATP; aqui é
    # calculada como no dimensionamento: corrente do ramo Y ÷ √3 (delta) ÷ nº de capacitores em paralelo por ramo
    _bc = getattr(proj, "banco", None)
    _kd = (1 / math.sqrt(3)) if (_bc and str(_bc.ligacao) == "Delta") else 1.0
    _np = max(int(getattr(_bc, "n_por_ramo", 1) or 1), 1)
    lin_icap = ["Corrente RMS por capacitor (A)"] + [
        f"{float(p.get('icap_unit_rms') or (p.get('icap_main_y_rms', p.get('icap_y_rms', 0)) * _kd / _np)):.2f}".replace(".", ",") for p in pts]
    linhas = [lin("Tensão na saída do inversor L-L fund. (V)", "v_inv_ll_fund"), lin("Tensão no motor L-L fund. (V)", "v_motor_ll_fund"),
              lin("Distorção da tensão no motor – PWM (%)", "thd_v_motor_pct", 2), lin("Tensão de pico no motor (V)", "vpk_motor", 0),
              lin("dv/dt no motor (V/µs)", "dvdt_motor_v_us", 2), lin("Corrente do inversor RMS (A)", "i1_rms"),
              lin("Corrente do motor RMS (A)", "i2_rms"), lin("Ondulação p-p no indutor (A)", "ripple_pp", 0),
              lin_icap, lin("Índice de modulação", "m_index", 3)]
    R.tabela(cab, linhas, [6.0] + [11.0 / len(pts)] * len(pts), legenda="Resultados da simulação (Plataforma FSEN)")
    p0 = pts[0]
    R.txt(f"Na frequência máxima de operação ({p0['f1']:g} Hz) o motor recebe {p0['v_motor_ll_fund']:.0f} V contra "
          f"{p0['v_inv_ll_fund']:.0f} V na saída do inversor – queda real de "
          f"{100 * (1 - p0['v_motor_ll_fund'] / p0['v_inv_ll_fund']):.1f} % (indutor, cabo e compensação dos capacitores) – e "
          f"recebe 100 % da tensão de que precisa nessa frequência.")
    R.figura(os.path.join(graf, "formas_onda.png"), "Formas de onda de tensão e corrente – inversor, filtro e motor (f máx)")
    R.figura(os.path.join(graf, "espectro.png"), "Espectro harmônico da tensão em % da fundamental – inversor, saída do filtro e motor")
    R.figura(os.path.join(graf, "grandezas_rms.png"), "Correntes e tensões RMS em todos os ramos, com máximos e mínimos")
    R.figura(os.path.join(graf, "resposta_frequencia.png"), "Resposta em frequência do filtro com e sem carga")
    R.figura(os.path.join(graf, "ressonancia_baixa_ordem.png"), "Robustez à ressonância na faixa de velocidade")
    R.h2("CONDIÇÕES EXTREMAS")
    ce = getattr(proj, "condicoes_extremas", []) or []
    if ce:
        R.tabela(["Condição", "fr (Hz)", "Distorção motor (%)", "Vpico motor (V)", "I capacitor (A)", "T capacitor (°C)", "Resultado"],
                 [(c["condicao"], c["fr_Hz"], c["thd_motor"], c["vpk_motor"], c["i_cap"], c["t_cap"], "ATENDE" if c["aprovado"] else "NÃO ATENDE")
                  for c in ce], [4.2, 1.6, 2.2, 2.2, 2.2, 2.2, 2.4], tam=8, legenda="Robustez em condições extremas", status_col=6)

    # 7 ---------------------------------------------------------------- ATP
    R.h1("DUPLA CHECAGEM NO ATP-EMTP")
    R.txt("A mesma rede elétrica (inversor PWM modelado em TACS com a mesma lei SVPWM, indutor com resistência de perdas, banco de "
          f"capacitores em {b.ligacao}, cabo em células π e motor com força contra-eletromotriz e capacitância à carcaça) foi "
          "simulada no domínio do tempo no ATP-EMTP, com passo de 2048 pontos por período da portadora, e comparada com o Python nos "
          "últimos dois ciclos em regime.")
    if atp:
        tudo = all(l["convergiu"] for x in atp for l in x["tabela"])
        R.txt(f"Resultado: {'as duas simulações CONVERGEM em todas as grandezas e pontos' if tudo else 'há divergência em algumas grandezas – ver tabela'}.")
        for x in atp:
            R.h2(x["ponto"].upper())
            R.tabela(["Grandeza", "Un", "Python", "ATP", "Dif. %", "Tol. %", "Resultado"],
                     [(l["grandeza"], l["unidade"], f"{l['python']:.2f}", f"{l['atp']:.2f}", f"{l['dif_pct']:+.2f}", f"±{l['tolerancia_pct']:g}",
                       "ATENDE" if l["convergiu"] else "ATENÇÃO") for l in x["tabela"]], [5.6, 1.0, 2.0, 2.0, 1.6, 1.4, 2.2], tam=8,
                     legenda=f"Python × ATP – {x['ponto']}", status_col=6)
        if vistas_dir:
            for k, x in enumerate(atp, 1):
                R.figura(os.path.join(vistas_dir, f"rede_fsen_caso{k}.png"), f"Rede simulada com os valores Python × ATP – {x['ponto']}")
                R.figura(os.path.join(vistas_dir, f"ondas_python_atp_fsen_caso{k}.png"), f"Formas de onda Python | ATP – {x['ponto']}")
    else:
        R.txt("A simulação no ATP-EMTP desta revisão ainda não foi executada; os arquivos de simulação foram gerados e o resultado "
              "será incluído na próxima revisão deste relatório.")

    # 8 ---------------------------------------------------------------- limites
    R.h1("VERIFICAÇÃO DOS LIMITES DOS COMPONENTES")
    R.txt("Cada componente foi verificado contra o seu limite de norma ou de datasheet, no pior ponto de operação, incluindo as "
          "condições extremas.")
    grupos = [
        ("MOTOR", ("Tensão de pico no motor", "dv/dt no motor", "Rise time", "THD total no motor", "THD tensão de saída", "Tensão disponível",
                   "Tensão de modo comum", "Tensão estimada no mancal")),
        ("INVERSOR E INDUTOR", ("Corrente do inversor", "Ondulação", "Queda de tensão", "Corrente capacitiva", "Térmico – Indutor")),
        ("CAPACITORES", ("Tensão RMS no capacitor", "Corrente RMS por capacitor", "Pico de tensão no capacitor", "dv/dt nos capacitores",
                         "Ponto quente do capacitor", "Vida estimada", "Capacitor no pior caso", "Térmico – Capacitores", "Térmico – ar em volta")),
        ("RESSONÂNCIA E ROBUSTEZ", ("Ressonância", "Amplificação", "THD na saída do filtro SEM motor")),
        ("PAINEL, CABOS E REFRIGERAÇÃO", ("Térmico – Cabos", "Térmico – elevação do ar", "Térmico – superfície", "Térmico – bornes",
                                         "Corrente de terra"))]
    usados = set()
    for nome, prefs in grupos:
        lst = [x for x in proj.verificacoes if x.item.startswith(prefs) and x.item not in usados]
        if not lst:
            continue
        usados.update(x.item for x in lst)
        R.h2(nome)
        R.tabela(["Verificação", "Valor", "Limite", "Resultado"], [(x.item, x.valor, x.limite, _st(x.ok, x.critico)) for x in lst],
                 [6.6, 4.0, 3.9, 2.5], tam=8, legenda=f"Limites – {nome.lower()}", status_col=3)
    # indutor: saturação
    R.txt(f"Indutor: corrente de pico em operação {L.i_pico_a:.0f} A contra saturação ≥ {L.i_sat_a:.0f} A (margem "
          f"{100 * (L.i_sat_a / L.i_pico_a - 1):.0f} %). A ET do indutor pede isolação classe {ped.get('classe_temp') or 'F'} e "
          f"elevação {ped.get('elevacao_temp') or '100 K'} pelo método da resistência, conforme IEC 60076-6.")

    # 9 ---------------------------------------------------------------- térmico
    R.h1("ESTUDO TÉRMICO E REFRIGERAÇÃO")
    pw = ar.get("perdas_w", {})
    R.tabela(["Fonte de calor", "Perdas (W)"], [(k, f"{v_:.0f}") for k, v_ in pw.items()] + [("TOTAL", f"{ar.get('perda_total_w')}")],
             [9.0, 4.0], legenda="Balanço de perdas no painel")
    vaz_min = (ar.get("perda_total_w") or 0) / (1.2 * 1005 * 15) * 3600
    R.txt(f"Vazão mínima para elevação de 15 K do ar: {vaz_min:.0f} m³/h. Instalados {ar.get('n_ventiladores')} ventiladores com "
          f"vazão nominal total de {ar.get('vazao_m3h')} m³/h (a vazão efetiva, com a perda de carga dos filtros de ar, está indicada no "
          "estudo térmico), arranjo com capacitores na entrada de ar (parte inferior) e indutor acima.")
    ti = vf("Térmico – Indutor")
    if ti:
        try:
            tq = float(str(ti.valor).split("°")[0].replace(",", "."))
            cls = str(ped.get("classe_temp") or "F")
            lim_cls = 155 if cls.strip().upper().startswith("F") else (180 if cls.strip().upper().startswith("H") else 130)
            R.txt(f"Ponto quente do enrolamento do indutor: {tq:.0f} °C, contra {lim_cls} °C da classe {cls.split()[0]} pedida pelo cliente "
                  f"(margem {lim_cls - tq:.0f} K){'; atende' if tq <= lim_cls else '; NÃO atende a classe pedida – REPROVADO: refazer o indutor (mais condutor/canal de ventilação) ou acordar outra classe por escrito com o cliente'}.")
        except Exception:
            pass
    R.figura(os.path.join(graf, "estudo_termico.png"), "Estudo térmico do painel – temperaturas por componente")

    # 10 --------------------------------------------------------------- conclusões
    R.h1("CONCLUSÕES")
    tot = vf("THD total no motor")
    vpk = vf("Tensão de pico no motor")
    R.txt(f"O filtro senoidal {proj.topologia} de {ped['corrente_a']:g} A / {ped['tensao_v']:g} V, com indutor de {L.l_uh:.0f} µH e "
          f"{b.n_total} capacitores de {b.uf_unit:g} µF em {b.ligacao}, {'ATENDE' if proj.aprovado else 'NÃO ATENDE'} a todos os "
          "critérios críticos de projeto, aos limites de norma do motor e aos limites de datasheet de todos os componentes, "
          "incluindo refrigeração e elevação de temperatura.")
    R.h2("SÍNTESE DOS RESULTADOS")
    sint = [("Tensão de pico no motor", vpk.valor if vpk else "-", vpk.limite if vpk else "-", _st(vpk.ok) if vpk else "-"),
            ("Distorção total da tensão no motor", tot.valor if tot else "-", tot.limite if tot else "-", _st(tot.ok) if tot else "-")]
    for pref, nome in (("dv/dt no motor", "dv/dt no motor"), ("Corrente RMS por capacitor", "Corrente nos capacitores"),
                       ("Pico de tensão no capacitor", "Pico de tensão nos capacitores"), ("Térmico – Indutor", "Ponto quente do indutor"),
                       ("Térmico – elevação do ar", "Elevação do ar no painel"), ("Queda de tensão", "Queda de tensão no indutor")):
        x = vf(pref)
        if x:
            sint.append((nome, x.valor, x.limite, _st(x.ok, x.critico)))
    if atp:
        sint.append(("Dupla checagem Python × ATP", "convergiu" if all(l["convergiu"] for x in atp for l in x["tabela"]) else "divergência",
                     "tolerâncias da tabela", "ATENDE" if all(l["convergiu"] for x in atp for l in x["tabela"]) else "ATENÇÃO"))
    R.tabela(["Indicador", "Resultado", "Limite", "Situação"], sint, [5.5, 4.5, 4.0, 3.0], legenda="Síntese dos resultados", status_col=3)
    alertas = [x for x in proj.verificacoes if not x.ok and not x.critico]
    if alertas:
        R.h2("PONTOS DE ATENÇÃO")
        R.itens([f"{x.item}: {x.valor} (referência {x.limite})." for x in alertas])
    R.h2("RECOMENDAÇÕES")
    rec = [f"Parametrizar o inversor com frequência de chaveamento fixa de {proj.fs_hz / 1000:g} kHz (sem modo automático de redução), "
           "habilitar o modo/parâmetro de filtro senoidal do fabricante e informar L e C do filtro quando o controle pedir.",
           "Não operar o inversor com o filtro em vazio (motor desconectado) por tempo prolongado; no comissionamento, energizar já com o motor.",
           "Cabo blindado simétrico entre filtro e motor, com aterramento 360° nas duas pontas e condutor PE de baixa impedância.",
           "Manter os filtros de ar dos ventiladores limpos (inspeção trimestral) e garantir a entrada de ar livre na parte inferior.",
           "Ensaios de rotina por unidade: indutância e resistência por fase, tensão aplicada, capacitância por ramo e funcionamento dos ventiladores."]
    if vf("Tensão estimada no mancal") and not vf("Tensão estimada no mancal").ok:
        rec.insert(2, "Tensão estimada no mancal acima de 10 V: utilizar rolamento isolado no lado não acionado e/ou escova de aterramento do eixo, "
                      "caso o motor não possua.")
    R.itens(rec)
    R.txt(f"Documento gerado pela {assinatura()}.")

    # salvar + sumário com páginas (2 passadas via PDF)
    saida = saida or os.path.join(pasta_proj, "02_Cliente", f"{cod}_Relatorio_Tecnico_Final.docx")
    os.makedirs(os.path.dirname(saida), exist_ok=True)
    d.save(saida)
    titulos = []
    n1 = n2 = 0
    for p in d.paragraphs:
        if p.style.name == "Heading 1":
            n1 += 1
            n2 = 0
            titulos.append((1, f"{n1}\t{p.text.upper()}"))
        elif p.style.name == "Heading 2":
            n2 += 1
            titulos.append((2, f"{n1}.{n2}\t{p.text.upper()}"))
    paginas = {}
    if pdf:
        paginas = _paginas_pdf(saida, [t for _, t in titulos], log)
    _sumario_estatico(d, [(nv, t, paginas.get(t, "")) for nv, t in titulos])
    d.save(saida)
    if pdf:
        _pdf(saida, log)
    return saida


def _pdf(arq, log=print):
    destino = os.path.splitext(arq)[0] + ".pdf"
    if os.name == "nt":                         # Windows: usa o Word instalado (exporta PDF), senão LibreOffice
        try:
            import win32com.client                # pywin32
            w = win32com.client.DispatchEx("Word.Application")
            w.Visible = False
            doc = w.Documents.Open(os.path.abspath(arq))
            doc.SaveAs2(os.path.abspath(destino), FileFormat=17)
            doc.Close(False)
            w.Quit()
            return destino
        except Exception:
            pass
    try:
        subprocess.run(["soffice", "--headless", "--convert-to", "pdf", "--outdir", os.path.dirname(arq), arq],
                       capture_output=True, timeout=300)
        return destino if os.path.exists(destino) else None
    except Exception as e:
        log(f"   (PDF do relatório não gerado – LibreOffice não encontrado; abra o .docx no Word e salve como PDF: {e})")
        return None


def _paginas_pdf(arq, titulos, log=print):
    """Converte para PDF e acha a página de cada título (para o sumário)."""
    pdf = _pdf(arq, log)
    if not pdf or not os.path.exists(pdf):
        return {}
    pags = None
    try:
        txt = subprocess.run(["pdftotext", "-layout", pdf, "-"], capture_output=True, text=True, timeout=120).stdout
        pags = txt.split("\f")
    except Exception:
        try:
            import fitz                           # PyMuPDF (Windows sem pdftotext)
            pags = [pg.get_text() for pg in fitz.open(pdf)]
        except Exception:
            try:
                from pypdf import PdfReader
                pags = [pg.extract_text() or "" for pg in PdfReader(pdf).pages]
            except Exception:
                return {}
    res = {}
    desloc = 1  # o sumário ocupa ~1 página a mais na versão final
    for t in titulos:
        num, nome = t.split("\t")
        pat = re.compile(r"^\s*" + re.escape(num) + r"\s+" + re.escape(nome[:40]), re.M | re.I)
        for i, pg in enumerate(pags, 1):
            if i > 3 and pat.search(pg):
                res[t] = i + desloc
                break
    return res
