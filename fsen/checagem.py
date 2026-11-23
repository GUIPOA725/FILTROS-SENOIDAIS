"""Coluna de CHECK padrão da plataforma (v1.22.0) – aprovado / atenção / reprovado em TODA tabela, planilha e gráfico
com resultado de simulação ou cálculo.

Forma usada (a mais comum em relatórios técnicos e softwares de estudo de sistemas elétricos – ETAP "Alert View"
marginal × crítico, PowerFactory "loading %", verificação de projeto por taxa de utilização do Eurocódigo, tabelas de
verificação "conforme / não conforme" da IEC 61439):
  • utilização U = valor ÷ limite (em %; para limite mínimo, limite ÷ valor);
  • APROVADO   U < 90 %                    (verde)
  • ATENÇÃO    90 % ≤ U ≤ 100 %  ou  critério de aviso violado  (âmbar) – margem pequena / conferir
  • REPROVADO  U > 100 % em critério obrigatório (vermelho) – não atende a norma/critério
  • INFO       caso mostrado de propósito (ex.: religamento proibido), não entra na aprovação (cinza)
Sempre texto + cor (nunca só cor): quem imprime em preto e branco ou tem daltonismo lê a palavra.
"""
from __future__ import annotations

import re

MARGEM_ATENCAO = 90.0          # % de utilização a partir do qual vira ATENÇÃO

APROVADO, ATENCAO, REPROVADO, INFO = "APROVADO", "ATENÇÃO", "REPROVADO", "INFO"
SIMBOLO = {APROVADO: "✔", ATENCAO: "⚠", REPROVADO: "✖", INFO: "ℹ"}
COR = {APROVADO: "#2E7D32", ATENCAO: "#F9A825", REPROVADO: "#C62828", INFO: "#757575"}
COR_FUNDO = {APROVADO: "#E8F5E9", ATENCAO: "#FFF8E1", REPROVADO: "#FFEBEE", INFO: "#F5F5F5"}


def utilizacao(valor, limite, tipo="max"):
    """% de utilização do limite (None quando não dá para calcular)."""
    try:
        valor, limite = float(valor), float(limite)
    except (TypeError, ValueError):
        return None
    if tipo == "min":
        return 100.0 * limite / valor if valor else None
    return 100.0 * valor / limite if limite else None


def check(ok=None, util=None, nivel="crit"):
    """Classifica. ok: critério atendido (bool) – se None, decide só pela utilização.
    nivel: "crit" (obrigatório → REPROVADO), "aviso" (→ ATENÇÃO), "info" (→ INFO)."""
    if nivel == "info":
        return INFO
    if ok is None:
        ok = util is None or util <= 100.0
    if not ok:
        return REPROVADO if nivel == "crit" else ATENCAO
    if util is not None and util >= MARGEM_ATENCAO:
        return ATENCAO
    return APROVADO


def texto(st, util=None):
    """'✔ APROVADO (72 %)' – para tabelas em texto/markdown."""
    u = f" ({util:.0f} %)" if util is not None else ""
    return f"{SIMBOLO.get(st, '')} {st}{u}".strip()


def pior(lista):
    """Pior check de uma lista (para o status de um caso/seção)."""
    ordem = [REPROVADO, ATENCAO, APROVADO, INFO]
    for o in ordem:
        if o in lista:
            return o
    return APROVADO


_RX = re.compile(r"(REPROVADO|ATENÇÃO|APROVADO|INFO)\b")


def de_texto(s):
    """Acha o check dentro de um texto de célula (para colorir tabelas já prontas)."""
    m = _RX.search(str(s or ""))
    return m.group(1) if m else None


def colorir_planilha(ws):
    """Pinta as células que contêm APROVADO/ATENÇÃO/REPROVADO/INFO numa aba do openpyxl."""
    from openpyxl.styles import Font, PatternFill
    for row in ws.iter_rows():
        for c in row:
            st = de_texto(c.value)
            if st:
                c.fill = PatternFill("solid", fgColor=COR_FUNDO[st].lstrip("#"))
                c.font = Font(bold=True, color=COR[st].lstrip("#"))


def selo(ax, st, texto_extra="", loc=(1.0, 1.015)):
    """Selo de check logo acima do canto direito do gráfico (fora da área das curvas e da legenda)."""
    ax.text(loc[0], loc[1], f"{SIMBOLO.get(st, '')} {st}" + (f" – {texto_extra}" if texto_extra else ""),
            transform=ax.transAxes, ha="right", va="bottom", fontsize=8, weight="bold", color="white",
            bbox=dict(boxstyle="round,pad=0.3", fc=COR[st], ec="none"))


_NUM = re.compile(r"[-+]?\d+(?:[.,]\d+)?")


def _num(s):
    m = _NUM.search(str(s or "").replace(" ", ""))
    return float(m.group(0).replace(",", ".")) if m else None


def util_de_textos(valor, limite):
    """Utilização a partir dos textos 'valor' e 'limite' (ex.: '842 V' e '≤ 1000 V'; '0,95' e '≥ 0,90')."""
    v, l = _num(valor), _num(limite)
    if v is None or l is None:
        return None
    lim = str(limite).strip()
    tipo = "min" if lim.startswith(("≥", ">", ">=")) else "max"
    if tipo == "max" and not lim.startswith(("≤", "<", "<=")) and "%" not in lim and "≤" not in lim:
        return None                                   # limite que não é "≤ x" (texto livre) – sem utilização
    return utilizacao(v, l, tipo)


def de_verificacao(ok, critico=True, valor=None, limite=None):
    """(check, utilização) para as verificações do filtro senoidal (Verificacao: ok/critico/valor/limite)."""
    u = util_de_textos(valor, limite)
    return check(bool(ok), u, "crit" if critico else "aviso"), u


def status_geral_md(texto):
    """v1.26.4 (REQ-GER-014): status GERAL do projeto a partir de TODAS as tabelas com coluna Check do RESUMO (verificações,
    arco elétrico, transitórios, IEC 61439, conferência) – nenhum resumo parcial pode dizer '0 REPROVADO' com item reprovado em
    outra tabela. Devolve as linhas markdown do bloco (para inserir logo abaixo do título)."""
    rep, at = [], 0
    for ln in texto.splitlines():
        if not ln.startswith("|"):
            continue
        if "✖ REPROVADO" in ln:
            cel = [c.strip() for c in ln.strip().strip("|").split("|")]
            rep.append(" – ".join(c for c in cel[:3] if c)[:230])
        elif "⚠ ATENÇÃO" in ln:
            at += 1
    if rep:
        cab = f"**✖ NÃO LIBERAR PARA FABRICAÇÃO – {len(rep)} item(ns) REPROVADO(S)** e {at} em ATENÇÃO (soma de todas as tabelas deste resumo)."
    elif at:
        cab = f"**⚠ SEM REPROVAÇÕES, {at} item(ns) em ATENÇÃO** – conferir cada um antes de liberar (soma de todas as tabelas deste resumo)."
    else:
        cab = "**✔ APROVADO** – nenhum item reprovado ou em atenção nas tabelas deste resumo."
    out = ["", "## Status geral do projeto", "", cab]
    if rep:
        out += ["", "Reprovados:"] + [f"- {r}" for r in rep]
    out += ["", "O status vale para o resultado MAIS SEVERO de cada grandeza (ex.: térmica do reator = pior entre o método de projeto e a "
            "análise avançada). Itens 'A CONFERIR' de catálogo continuam obrigatórios antes da ordem de compra.", ""]
    return out
