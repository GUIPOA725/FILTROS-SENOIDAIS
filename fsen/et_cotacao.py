"""Partes comuns das ETs de cotação (Word) e do e-mail curto que as acompanha – v1.31.0.

REQ-DOC-020 (engenheiro, 26/11/2026): "como é um texto longo é melhor fazer um word com ET ... fazer para todos os itens, pois
como é longo prefiro anexar no email, faz um word de ET bacana bonito fácil de ler e bem organizado ... para a montadora ela não
é um fornecedor ... em filtro senoidal eu forneço indutor e capacitor, em filtro dessintonizado só forneço indutor, em filtro
sintonizado forneço indutor e capacitor".

Regra: o e-mail é CURTO (o que se pede, quantidade, prazo de resposta e lista de anexos); TUDO o que é técnico – requisitos e
motivo, dados a declarar, ensaios, protótipo, critérios de aceitação e "o que a proposta deve trazer" – fica na ET em Word.
Escopo de fornecimento Electric (o que vai a fornecedor): senoidal = indutor + capacitor; dessintonizado = reator;
sintonizado = reator + capacitor. O resto é da montadora (pacote de cotação de montagem, não é fornecedor).
"""
import os

from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor

AZUL = "1F3A5F"
AZUL_CLARO = "E8EEF6"
AMARELO = "FFF2CC"

ESCOPO_ELECTRIC = {
    "senoidal": "indutor e capacitores",
    "dessintonizado": "reatores",
    "sintonizado": "reatores e capacitores",
}

DESCR_ANEXO = [
    ("ET_", "Especificação técnica (este documento)"),
    ("Formulario_Resposta", "Planilha de resposta técnica – preencher e devolver com a proposta"),
    ("Questionario", "Questionário técnico do fabricante"),
    ("Protocolo_Ensaio", "Protocolo de ensaio do protótipo"),
    ("Projeto_Referencia", "Projeto de referência da Electric (desenhos) – orientação, não imposição"),
    ("Memorial_Indutor", "Memorial de cálculo do indutor (referência)"),
    ("Anexo_Tecnico", "Anexo técnico com as referências usadas"),
    ("Forma_de_onda", "Forma de onda simulada da corrente/tensão"),
    ("Corrente_Capacitor", "Forma de onda da corrente no capacitor"),
    ("_2D_", "Desenho 2D (DXF)"),
    ("_3D_", "Modelo 3D (STEP)"),
    ("Indutor_Trifasico", "Especificação do reator (formato carta Electric)"),
    ("Indutor_Monofasico", "Especificação do reator (formato carta Electric)"),
    ("Esquema_Eletrico", "Esquema elétrico"),
    ("Layout_Painel", "Layout do painel"),
    ("Painel_3D", "Painel 3D (medidas reais de catálogo)"),
    ("Painel_2D", "Painel 2D de montagem"),
    ("Lista_Material", "Lista de material"),
    ("Etiquetas", "Etiquetas e plaquetas"),
    ("Etiqueta_Arco", "Etiqueta de arco elétrico"),
    ("Lista_DePara", "Lista de-para das etiquetas"),
    ("Caderno_Montagem", "Caderno de montagem"),
    ("_desenhos", "Desenhos do painel (vistas, 3D, diagrama, cabos)"),
    ("ET_Caixa", "ET da caixa metálica (compra da montadora)"),
    ("ET_Plaqueta", "ET da plaqueta e adesivos (compra da montadora)"),
    ("LM_Cabos", "Lista de cabos e miscelânea (compra da montadora)"),
    ("Conferencia_Esquema", "Conferência esquema × painel × lista"),
    ("ET_Painel", "Especificação para fornecimento do painel"),
]


def _sombrear(cel, cor):
    tcPr = cel._tc.get_or_add_tcPr()
    sh = OxmlElement("w:shd")
    sh.set(qn("w:val"), "clear")
    sh.set(qn("w:color"), "auto")
    sh.set(qn("w:fill"), cor)
    tcPr.append(sh)


def _cel(cel, texto, negrito=False, cor_txt=None, tam=10):
    cel.text = ""
    p = cel.paragraphs[0]
    r = p.add_run(str(texto))
    r.bold = negrito
    r.font.size = Pt(tam)
    if cor_txt:
        r.font.color.rgb = RGBColor.from_string(cor_txt)


def quadro_resumo(d, titulo, pares, nota=None):
    """Quadro sombreado 'O que estamos cotando' logo no início da ET."""
    t = d.add_table(rows=1, cols=2)
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.style = "Table Grid"
    c = t.rows[0].cells[0].merge(t.rows[0].cells[1])
    _cel(c, titulo, True, "FFFFFF", 11)
    _sombrear(c, AZUL)
    for k, (a, b) in enumerate(pares):
        r = t.add_row().cells
        _cel(r[0], a, True)
        _cel(r[1], b)
        _sombrear(r[0], AZUL_CLARO)
        if k % 2:
            _sombrear(r[1], "F7F9FC")
    if nota:
        r = t.add_row().cells
        c = r[0].merge(r[1])
        _cel(c, nota, False, None, 9)
        _sombrear(c, AMARELO)
    d.add_paragraph()
    return t


def secao_proposta(d, num, itens, formulario=None):
    d.add_heading(f"{num}. O que a proposta deve trazer – para a nossa análise técnica", 1)
    d.add_paragraph("A proposta é comparada, item a item, com o nosso modelo de cálculo do componente. Propostas sem os dados "
                    "técnicos abaixo não conseguem ser aprovadas pela engenharia da Electric Service.")
    for i, t in enumerate(itens, 1):
        d.add_paragraph(f"{t}", style="List Number")
    if formulario:
        p = d.add_paragraph()
        p.add_run("Planilha de resposta: ").bold = True
        p.add_run(f"{formulario} (em anexo) – um item por linha, com a unidade. Basta preencher a coluna 'Valor declarado' e devolver "
                  "junto com a proposta; o que não souberem, deixar em branco e dizer por quê.")


def secao_anexos(d, num, arquivos):
    arquivos = [a for a in arquivos if a]
    if not arquivos:
        return
    d.add_heading(f"{num}. Documentos anexos a esta cotação", 1)
    t = d.add_table(rows=1, cols=2)
    t.style = "Table Grid"
    for c, txt in zip(t.rows[0].cells, ("Arquivo", "Conteúdo")):
        _cel(c, txt, True, "FFFFFF", 9)
        _sombrear(c, AZUL)
    for k, a in enumerate(arquivos):
        n = os.path.basename(a)
        desc = next((dsc for pre, dsc in DESCR_ANEXO if pre in n), "")
        r = t.add_row().cells
        _cel(r[0], n, False, None, 9)
        _cel(r[1], desc, False, None, 9)
        if k % 2:
            _sombrear(r[0], "F7F9FC")
            _sombrear(r[1], "F7F9FC")


def secao_contato(d, num, cat):
    emp = (cat or {}).get("empresa") or {}
    d.add_heading(f"{num}. Contato técnico", 1)
    d.add_paragraph(f"{emp.get('responsavel', 'Engenharia')} – {emp.get('nome', 'Electric Service')} • {emp.get('email', '')} • "
                    f"{emp.get('telefone', '')}. Se for útil, fazemos uma call rápida com a engenharia de vocês para alinhar a especificação.")


def email_curto(ola, pedido, resumo, et_nome, anexos, assin, extra=None):
    """Corpo do e-mail de cotação: curto – o técnico está na ET anexa."""
    ls = [ola, "", pedido, ""]
    if resumo:
        ls += ["Resumo:"] + [f"- {x}" for x in resumo] + [""]
    ls += [f"A especificação completa está no Word em anexo ({et_nome}): requisitos e o motivo de cada um, dados que vocês precisam "
           "declarar, ensaios, critérios de aceitação e o que a proposta deve trazer para a nossa análise técnica."]
    if extra:
        ls += ["", extra]
    nomes = [os.path.basename(a) for a in anexos if a]
    if nomes:
        ls += ["", "Anexos:"] + [f"- {n}" for n in nomes]
    ls += ["", "Fico à disposição para uma call com a engenharia de vocês, se ajudar."]
    return "\n".join(ls) + assin
