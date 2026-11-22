"""Relatório CONSOLIDADO do projeto – v1.19.0.

Um único PDF na raiz da pasta do projeto (00_RELATORIO_CONSOLIDADO_<código>.pdf) para o engenheiro ler tudo de uma vez,
nos 3 tipos (filtro senoidal, banco dessintonizado, filtro sintonizado):
  1. capa e sumário (com a página de cada parte);
  2. resumo do projeto (o mesmo conteúdo do RESUMO.md: solução, verificações, avisos);
  3. como o projeto foi decidido – leitura da IA, critério aplicado, premissas/lacunas e origem de cada número;
  4. painel (gabinete, ventilação, termostatos) quando houver;
  5. figuras principais (espectro, varredura, reator/indutor, campo FEM, mapa térmico);
  6. índice de TODOS os arquivos gerados, por pasta, com o que é cada um;
  7. anexos: todos os PDFs do projeto em ordem de leitura (relatório técnico, memorial, auditoria, reator/indutor,
     desenhos, esquema elétrico, layout do painel, etiquetas), com marcadores no PDF para navegar.
Arquivos que não são PDF (Word, Excel, DXF, STEP, QET) ficam listados no índice com o caminho.
Determinístico: mesma pasta → mesmo relatório (exceto data/hora de geração).
"""
from __future__ import annotations

import datetime as _dt
import os
import re

from pypdf import PdfReader, PdfWriter
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle)

AZUL = colors.HexColor("#1F3A5F")
VERMELHO = colors.HexColor("#C62828")

# ordem de leitura dos anexos: (padrão no nome do arquivo, título do marcador)
ORDEM_ANEXOS = [
    (r"Relatorio_Tecnico_Final", "Relatório técnico final (RTM)"),
    (r"Memorial_de_Calculo", "Memorial de cálculo"),
    (r"AUDITORIA", "Auditoria do projeto"),
    (r"Analise_Avancada", "Análise avançada do reator/indutor (FEM)"),
    (r"Verificacao_Independente", "Verificação independente (NGSolve)"),
    (r"Memorial_(Reator|Indutor)", "Memorial do reator/indutor (fornecedor)"),
    (r"Anexo_Tecnico_Referencias", "Anexo técnico – referências do indutor"),
    (r"Projeto_Referencia", "Projeto de referência do reator/indutor (desenhos)"),
    (r"_desenhos", "Desenhos do painel"),
    (r"Layout_Painel", "Layout do painel"),
    (r"Esquema_Eletrico", "Esquema elétrico"),
    (r"Etiquetas", "Etiquetas e plaquetas"),
]
FIGURAS = [
    (r"espectro", "Espectro harmônico"),
    (r"varredura", "Varredura de impedância / ressonância"),
    (r"render_geral", "Reator/indutor – vista 3D"),
    (r"campo_FEM", "Campo magnético (elementos finitos)"),
    (r"mapa_termico", "Mapa térmico"),
    (r"formas_onda", "Formas de onda"),
    (r"Transitorio_", "Transitório eletromagnético"),
]
DESCR = [
    (r"Proposta", "Proposta técnica e comercial ao cliente"),
    (r"Memorial_de_Calculo", "Memorial de cálculo do banco/filtro"),
    (r"Relatorio_Tecnico_Final", "Relatório técnico final (padrão RTM)"),
    (r"ESTAGIO", "Planilha ESTAGIO (padrão Electric)"),
    (r"Indutor_Trifasico|Especificacao.*(Reator|Indutor)", "Especificação do reator/indutor para o fornecedor"),
    (r"Email_", "Texto do e-mail ao fornecedor/montadora/cliente"),
    (r"ET_Painel", "Especificação técnica do painel (montadora)"),
    (r"Esquema_Eletrico.*\.qet$", "Esquema elétrico – arquivo QElectroTech (editável)"),
    (r"Esquema_Eletrico.*\.dxf$", "Esquema elétrico – DXF (CAD)"),
    (r"Esquema_Eletrico.*\.pdf$", "Esquema elétrico – PDF"),
    (r"Layout_Painel.*\.dxf$", "Layout do painel – DXF (CAD)"),
    (r"Layout_Painel.*\.pdf$", "Layout do painel – PDF"),
    (r"Lista_DePara", "Lista DE/PARA de fios e etiquetas"),
    (r"Lista_Material", "Lista de material, bornes e cabos"),
    (r"Transitorios_.*\.xlsx$", "Transitórios: critérios por caso e comparação Python × ATP"),
    (r"trans_.*\.atp$", "Deck ATP do caso de transitório"),
    (r"\.pl4$", "Resultado do ATP (PlotXY)"),
    (r"Etiquetas.*\.pdf$", "Etiquetas de fio e plaquetas"),
    (r"\.step$", "Modelo 3D (STEP)"),
    (r"_2D\.dxf$|\.dxf$", "Desenho CAD (DXF)"),
    (r"\.lua$", "Script FEMM para conferência"),
    (r"Resultados_Medidos", "Planilha para os resultados medidos do reator/indutor"),
    (r"Analise_Avancada", "Análise avançada do reator/indutor"),
    (r"Verificacao_Independente", "Verificação independente (NGSolve)"),
    (r"Projeto_Referencia", "Projeto de referência do reator/indutor"),
    (r"Memorial_(Reator|Indutor)", "Memorial do reator/indutor"),
    (r"Questionario", "Questionário técnico de dados faltantes"),
    (r"Sensibilidade", "Sensibilidade aos dados faltantes"),
    (r"\.json$", "Dados do projeto (JSON)"),
    (r"\.png$", "Figura"),
    (r"\.atp$", "Deck ATP-EMTP"),
    (r"RESUMO\.md$", "Resumo em texto"),
]


# ----------------------------------------------------------------------------------------------------- fonte e texto
def _fonte():
    cands = [r"C:\Windows\Fonts\arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
             "/usr/share/fonts/dejavu/DejaVuSans.ttf", "/Library/Fonts/Arial.ttf"]
    negr = {r"C:\Windows\Fonts\arial.ttf": r"C:\Windows\Fonts\arialbd.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf": "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/dejavu/DejaVuSans.ttf": "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
            "/Library/Fonts/Arial.ttf": "/Library/Fonts/Arial Bold.ttf"}
    for c in cands:
        if os.path.exists(c):
            try:
                pdfmetrics.registerFont(TTFont("FSEN", c))
                b = negr.get(c)
                pdfmetrics.registerFont(TTFont("FSEN-B", b if b and os.path.exists(b) else c))
                pdfmetrics.registerFontFamily("FSEN", normal="FSEN", bold="FSEN-B", italic="FSEN", boldItalic="FSEN-B")
                return "FSEN", "FSEN-B"
            except Exception:
                continue
    return "Helvetica", "Helvetica-Bold"


def _limpa(s):
    """Texto seguro para o PDF: emojis → palavras, escapa <>&, **negrito** → <b>."""
    s = str(s)
    for a, b in (("✅", "[OK]"), ("⚠️", "[ATENÇÃO]"), ("⚠", "[ATENÇÃO]"), ("❌", "[FALHA]"), ("🔎", ""), ("🛟", ""),
                 ("→", "→"), ("\u200b", "")):
        s = s.replace(a, b)
    s = re.sub(r"[\U0001F300-\U0001FAFF\u2600-\u26FF\u2700-\u27BF]", "", s)
    s = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"(?<!\*)\*(?!\s)(.+?)(?<!\s)\*(?!\*)", r"<i>\1</i>", s)
    return s


def _estilos(f, fb):
    ss = getSampleStyleSheet()
    base = ParagraphStyle("base", parent=ss["Normal"], fontName=f, fontSize=9, leading=12)
    return dict(
        base=base,
        peq=ParagraphStyle("peq", parent=base, fontSize=7.5, leading=9.5, textColor=colors.HexColor("#444444")),
        h1=ParagraphStyle("h1", parent=base, fontName=fb, fontSize=14, leading=18, textColor=AZUL, spaceBefore=6, spaceAfter=6),
        h2=ParagraphStyle("h2", parent=base, fontName=fb, fontSize=11, leading=14, textColor=AZUL, spaceBefore=8, spaceAfter=4),
        cap=ParagraphStyle("cap", parent=base, fontName=fb, fontSize=22, leading=28, alignment=TA_CENTER, textColor=AZUL),
        capsub=ParagraphStyle("capsub", parent=base, fontSize=12, leading=16, alignment=TA_CENTER),
        bul=ParagraphStyle("bul", parent=base, leftIndent=10, bulletIndent=2),
        cel=ParagraphStyle("cel", parent=base, fontSize=7.5, leading=9),
        celb=ParagraphStyle("celb", parent=base, fontName=fb, fontSize=7.5, leading=9, textColor=colors.white),
    )


def _tabela(linhas, E, larg=None, cab=True):
    dados = [[Paragraph(_limpa(c), E["celb"] if (cab and i == 0) else E["cel"]) for c in r] for i, r in enumerate(linhas)]
    t = Table(dados, colWidths=larg, repeatRows=1 if cab else 0)
    st = [("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#999999")), ("VALIGN", (0, 0), (-1, -1), "TOP"),
          ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3)]
    if cab:
        st.append(("BACKGROUND", (0, 0), (-1, 0), AZUL))
    t.setStyle(TableStyle(st))
    return t


def _markdown(txt, E):
    """Converte o RESUMO.md (títulos, listas, tabelas |…|) em elementos do PDF."""
    out, tab = [], []

    def fecha_tab():
        if tab:
            linhas = [r for r in tab if not re.match(r"^\s*\|?\s*:?-{3,}", "|".join(r))]
            n = max(len(r) for r in linhas)
            linhas = [r + [""] * (n - len(r)) for r in linhas]
            out.append(_tabela(linhas, E, larg=[(180 * mm) / n] * n))
            out.append(Spacer(1, 4))
            tab.clear()

    for ln in (txt or "").splitlines():
        s = ln.rstrip()
        if s.strip().startswith("|"):
            tab.append([c.strip() for c in s.strip().strip("|").split("|")])
            continue
        fecha_tab()
        if not s.strip():
            continue
        if s.startswith("# "):
            out.append(Paragraph(_limpa(s[2:]), E["h2"]))
        elif s.startswith("#"):
            out.append(Paragraph(_limpa(s.lstrip("#").strip()), E["h2"]))
        elif re.match(r"^\s*[-•]\s+", s):
            out.append(Paragraph(_limpa(re.sub(r"^\s*[-•]\s+", "", s)), E["bul"], bulletText="•"))
        else:
            out.append(Paragraph(_limpa(s), E["base"]))
    fecha_tab()
    return out


# ----------------------------------------------------------------------------------------------------- arquivos
def _listar(pasta):
    arqs = []
    for raiz, dirs, fs in os.walk(pasta):
        dirs.sort()
        for f in sorted(fs):
            if f.startswith("00_RELATORIO_CONSOLIDADO") or f.startswith("~$") or f.endswith(".zip"):
                continue
            arqs.append(os.path.join(raiz, f))
    return arqs


def _descr(nome):
    for pad, d in DESCR:
        if re.search(pad, nome, re.I):
            return d
    return os.path.splitext(nome)[1].lstrip(".").upper() or "arquivo"


def _anexos(arqs):
    """PDFs em ordem de leitura, sem repetir cópias (mesmo nome e tamanho em pastas diferentes)."""
    vistos, out = set(), []
    pdfs = [a for a in arqs if a.lower().endswith(".pdf")]
    for pad, tit in ORDEM_ANEXOS:
        for a in pdfs:
            chave = (os.path.basename(a), os.path.getsize(a))
            if chave in vistos or not re.search(pad, os.path.basename(a), re.I):
                continue
            vistos.add(chave)
            nome = os.path.splitext(os.path.basename(a))[0]
            out.append((f"{tit} – {nome}" if tit.split()[0].lower() not in nome.lower() else nome, a))
    for a in pdfs:                                    # qualquer outro PDF que não casou com a ordem
        chave = (os.path.basename(a), os.path.getsize(a))
        if chave not in vistos:
            vistos.add(chave)
            out.append((os.path.splitext(os.path.basename(a))[0], a))
    return out


def _figuras(arqs):
    out, vistos = [], set()
    pngs = [a for a in arqs if a.lower().endswith(".png")]
    for pad, tit in FIGURAS:
        for a in pngs:
            if re.search(pad, os.path.basename(a), re.I) and os.path.basename(a) not in vistos:
                vistos.add(os.path.basename(a))
                out.append((tit, a))
    return out


def _img(caminho, larg_max=170 * mm, alt_max=110 * mm):
    try:
        from reportlab.lib.utils import ImageReader
        w, h = ImageReader(caminho).getSize()
        k = min(larg_max / w, alt_max / h)
        return Image(caminho, width=w * k, height=h * k)
    except Exception:
        return None


# ----------------------------------------------------------------------------------------------------- relatório
def gerar(pasta, cod, titulo, versao, cliente="", projeto="", tipo="", leitura=None, painel=None, extras=None, log=print):
    """Gera 00_RELATORIO_CONSOLIDADO_<cod>.pdf na raiz da pasta do projeto e devolve o caminho.
    leitura: dict(fonte, justificativa[list], observacoes, lacunas[list], evidencias[list]) – da tela de leitura por IA.
    painel: dict do gabinete (painel_gabinete.gabinete) quando houver.
    extras: lista de (título, [linhas de texto]) para seções específicas do tipo."""
    f, fb = _fonte()
    E = _estilos(f, fb)
    arqs = _listar(pasta)
    anexos = _anexos(arqs)
    figs = _figuras(arqs)
    resumo_md = ""
    rp = os.path.join(pasta, "RESUMO.md")
    if os.path.exists(rp):
        resumo_md = open(rp, encoding="utf-8").read()
    agora = _dt.datetime.now()
    saida = os.path.join(pasta, f"00_RELATORIO_CONSOLIDADO_{cod}.pdf")
    frente = saida + ".frente.pdf"

    def corpo(pag_anexos):
        h = []
        h += [Spacer(1, 45 * mm), Paragraph("RELATÓRIO CONSOLIDADO DO PROJETO", E["cap"]), Spacer(1, 6 * mm),
              Paragraph(_limpa(titulo), E["capsub"]), Spacer(1, 4 * mm), Paragraph(_limpa(cod), E["capsub"]), Spacer(1, 14 * mm)]
        cab = [["Cliente", cliente or "–"], ["Projeto / local", projeto or "–"], ["Tipo", tipo or "–"],
               ["Gerado por", f"{versao} – Electric Service"], ["Data", agora.strftime("%d/%m/%Y %H:%M")],
               ["Pasta", pasta]]
        h += [_tabela(cab, E, larg=[40 * mm, 130 * mm], cab=False), Spacer(1, 10 * mm),
              Paragraph("Tudo o que a plataforma gerou neste projeto, num só documento: resumo, como foi decidido, premissas, painel, "
                        "figuras, índice de arquivos e, em anexo, todos os PDFs (memorial, reator/indutor, desenhos, esquema "
                        "elétrico, layout e etiquetas). Use os marcadores do PDF para navegar.", E["peq"]), PageBreak()]
        # sumário
        h.append(Paragraph("Sumário", E["h1"]))
        sec = ["1  Resumo do projeto", "2  Como o projeto foi decidido (leitura, critério e premissas)"]
        n = 3
        if painel:
            sec.append(f"{n}  Painel – gabinete, ventilação e termostatos"); n += 1
        for t_, _ in (extras or []):
            sec.append(f"{n}  {t_}"); n += 1
        if figs:
            sec.append(f"{n}  Figuras principais"); n += 1
        sec.append(f"{n}  Índice de todos os arquivos gerados"); n += 1
        sec.append(f"{n}  Anexos")
        for s_ in sec:
            h.append(Paragraph(_limpa(s_), E["base"]))
        if pag_anexos:
            linhas = [["Anexo", "Página"]] + [[t_, str(p_)] for t_, p_ in pag_anexos]
            h += [Spacer(1, 4), _tabela(linhas, E, larg=[150 * mm, 20 * mm])]
        h.append(PageBreak())
        # 1 resumo
        h.append(Paragraph("1  Resumo do projeto", E["h1"]))
        h += _markdown(resumo_md, E) or [Paragraph("RESUMO.md não encontrado.", E["base"])]
        # 2 leitura
        h.append(Paragraph("2  Como o projeto foi decidido", E["h1"]))
        L = leitura or {}
        if L.get("fonte"):
            h.append(Paragraph(_limpa(f"Leitura do pedido: {L['fonte']}"), E["peq"]))
        if L.get("justificativa"):
            h.append(Paragraph("Critério aplicado", E["h2"]))
            h += [Paragraph(_limpa(x), E["bul"], bulletText="•") for x in L["justificativa"]]
        if L.get("observacoes"):
            h += [Paragraph("Observações da leitura", E["h2"]), Paragraph(_limpa(L["observacoes"]), E["base"])]
        if L.get("lacunas"):
            h.append(Paragraph("Premissas e dados faltantes (confirmar com o cliente)", E["h2"]))
            h += [Paragraph(_limpa(x), E["bul"], bulletText="•") for x in L["lacunas"]]
        if L.get("evidencias"):
            h.append(Paragraph("De onde saíram os números", E["h2"]))
            h += [Paragraph(_limpa(x), E["bul"], bulletText="•") for x in L["evidencias"]]
        if not any(L.get(k) for k in ("justificativa", "observacoes", "lacunas", "evidencias")):
            h.append(Paragraph("Projeto gerado sem a etapa de leitura por IA (dados digitados na tela) – ver o resumo e o memorial.",
                               E["base"]))
        n = 3
        if painel:
            h.append(Paragraph(f"{n}  Painel", E["h1"])); n += 1
            d = painel.get("dimensoes_mm") or {}
            v = painel.get("ventilacao") or {}
            p = painel.get("perdas_w") or {}
            linhas = [["Item", "Valor"],
                      ["Dimensões (A × L × P)", f"{d.get('altura')} × {d.get('largura')} × {d.get('profundidade')} mm"],
                      ["Arranjo", f"{painel.get('arranjo', '')} – {len(painel.get('colunas') or [])} coluna(s)"],
                      ["Perdas internas", f"{p.get('total', '–')} W (reatores {p.get('reatores', '–')} W, capacitores "
                                          f"{p.get('capacitores', '–')} W, contatoras {p.get('contatoras', '–')} W)"],
                      ["Ventilação", f"{v.get('n_exaustores', '–')} exaustor(es) de {v.get('exaustor_m3h', '–')} m³/h – ar interno "
                                     f"{v.get('t_interna_c', '–')} °C (ΔT {v.get('dt_k', '–')} K)"],
                      ["Entrada de ar", f"{v.get('area_entrada_cm2', '–')} cm²"],
                      ["Termostatos", "; ".join(f"{t['tag']} {t['ajuste_c']} °C – {t['funcao']}" for t in v.get("termostatos") or [])]]
            h.append(_tabela(linhas, E, larg=[50 * mm, 120 * mm]))
            for a in painel.get("avisos") or []:
                h.append(Paragraph(_limpa("[ATENÇÃO] " + a), E["base"]))
            if painel.get("base"):
                h.append(Paragraph(_limpa("Base: " + painel["base"]), E["peq"]))
        for t_, linhas in (extras or []):
            h.append(Paragraph(f"{n}  {_limpa(t_)}", E["h1"])); n += 1
            h += [Paragraph(_limpa(x), E["bul"], bulletText="•") for x in linhas]
        if figs:
            h += [PageBreak(), Paragraph(f"{n}  Figuras principais", E["h1"])]; n += 1
            for t_, a in figs:
                im = _img(a)
                if im:
                    h.append(KeepTogether([Paragraph(_limpa(f"{t_} – {os.path.basename(a)}"), E["h2"]), im, Spacer(1, 4)]))
        h += [PageBreak(), Paragraph(f"{n}  Índice de todos os arquivos gerados", E["h1"])]; n += 1
        linhas = [["Pasta", "Arquivo", "O que é"]]
        for a in arqs:
            rel = os.path.relpath(os.path.dirname(a), pasta)
            linhas.append(["(raiz)" if rel == "." else rel, os.path.basename(a), _descr(os.path.basename(a))])
        h.append(_tabela(linhas, E, larg=[55 * mm, 75 * mm, 50 * mm]))
        h += [PageBreak(), Paragraph(f"{n}  Anexos", E["h1"])]
        if anexos:
            h.append(Paragraph("Os PDFs do projeto vêm a seguir, nesta ordem (marcadores do PDF para navegar):", E["base"]))
            h += [Paragraph(_limpa(t_), E["bul"], bulletText="•") for t_, _ in anexos]
        else:
            h.append(Paragraph("Nenhum PDF encontrado na pasta do projeto.", E["base"]))
        return h

    def rodape(c, doc):
        c.saveState()
        c.setFont(f, 7)
        c.setFillColor(colors.HexColor("#666666"))
        c.drawString(15 * mm, 8 * mm, f"{cod} – Relatório consolidado – {versao}")
        c.drawRightString(195 * mm, 8 * mm, f"pág. {doc.page}")
        c.restoreState()

    def montar(pag_anexos):
        doc = SimpleDocTemplate(frente, pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm, topMargin=15 * mm,
                                bottomMargin=15 * mm, title=f"Relatório consolidado {cod}", author=f"Electric Service – {versao}")
        doc.build(corpo(pag_anexos), onFirstPage=rodape, onLaterPages=rodape)
        return len(PdfReader(frente).pages)

    # 2 passadas: a 1ª mede a frente, a 2ª escreve o sumário com a página de cada anexo
    leitores = []
    for t_, a in anexos:
        try:
            leitores.append((t_, a, PdfReader(a)))
        except Exception as ex:
            log(f"   (relatório consolidado: {os.path.basename(a)} não anexado – {type(ex).__name__})")
    n_frente = montar([(t_, 0) for t_, _, _ in leitores])
    pag, pos = [], n_frente + 1
    for t_, _, r in leitores:
        pag.append((t_, pos))
        pos += len(r.pages)
    n2 = montar(pag)
    if n2 != n_frente:                                # o sumário mudou de tamanho – refaz com as páginas certas
        pag, pos = [], n2 + 1
        for t_, _, r in leitores:
            pag.append((t_, pos))
            pos += len(r.pages)
        montar(pag)
    w = PdfWriter()
    fr = PdfReader(frente)
    for p_ in fr.pages:
        w.add_page(p_)
    w.add_outline_item("Relatório consolidado – resumo, critério, premissas, painel, índice", 0)
    raiz = w.add_outline_item("Anexos", len(fr.pages)) if leitores else None
    for t_, _, r in leitores:
        ini = len(w.pages)
        for p_ in r.pages:
            w.add_page(p_)
        w.add_outline_item(t_, ini, parent=raiz)
    w.add_metadata({"/Title": f"Relatório consolidado {cod}", "/Author": f"Electric Service – {versao}"})
    with open(saida, "wb") as fh:
        w.write(fh)
    os.remove(frente)
    log(f"   Relatório consolidado: {os.path.basename(saida)} ({len(w.pages)} páginas, {len(leitores)} anexos)")
    return saida
