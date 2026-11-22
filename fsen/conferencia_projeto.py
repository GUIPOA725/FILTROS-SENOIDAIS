"""Conferência cruzada OBRIGATÓRIA (REQ-PNL-028): projeto elétrico (esquema de força e comando, DE/PARA, lista de material do
esquema) × desenhos de montagem (2D/3D – mesmo modelo) × lista de material completa. Zero diferença: tudo que está no esquema
tem que estar no 2D/3D e na lista, com o mesmo código e a mesma seção de cabo – senão REPROVADO (o montador não pode dizer
que "não tinha"). Resultado em 01_Engenharia/6_Conferencia_Projeto (xlsx) e no RESUMO.
"""
from __future__ import annotations

import glob
import json
import os
import re

from . import checagem as CK


def _expand(tag):
    """'-K1…-K8' → [-K1..-K8]; '-Q1…-Q%d' já formatado; '-X1/-X2' → [-X1,-X2]."""
    tag = str(tag or "").strip()
    out = []
    for parte in re.split(r"[/,]", tag):
        parte = parte.strip()
        m = re.match(r"^(-[A-Z]+)(\d+)…-?[A-Z]*(\d+)$", parte)
        if m:
            out += [f"{m.group(1)}{k}" for k in range(int(m.group(2)), int(m.group(3)) + 1)]
        elif re.match(r"^-[A-Z]+\d*$", parte):
            out.append(parte)
    return out


def _xlsx(arq, aba, linha_cab):
    import openpyxl
    ws = openpyxl.load_workbook(arq, data_only=True)[aba]
    rows = list(ws.iter_rows(values_only=True))
    cab = [str(c or "") for c in rows[linha_cab]]
    return [dict(zip(cab, r)) for r in rows[linha_cab + 1:] if any(r)]


def _norm(cod):
    s = re.sub(r"\(.*?\)", "", str(cod or "")).lower()
    return " ".join(re.findall(r"[a-z]+\d*[a-z0-9]*", s)[:3])


def _num(x):
    try:
        return float(str(x).replace(",", "."))
    except Exception:
        return None


def _kv(txt):
    """'… 25 kvar / 525 V …' → (25.0, 525.0)."""
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*k[vV][aA]?[rR]\s*/?\s*(\d{3,4})\s*V", str(txt or ""))
    return (_num(m.group(1)), _num(m.group(2))) if m else (None, None)


def capacitores_por_estagio(pasta, tags_esq, tags_lc, dp, lay, res=None):
    """REQ-GER-011 – regra para TODOS os filtros: nº de capacitores por estágio/indutor, kvar e tensão da lata iguais em todos os
    documentos. Devolve linhas [item, referência (cálculo), encontrado, Check, obs]."""
    out = []
    try:
        if res is None:
            res = json.load(open(os.path.join(pasta, "01_Engenharia", "banco_resultado.json"), encoding="utf-8"))
        calc = [tuple(e["cap"][:3]) for e in res["estagios"]]
    except Exception as ex:
        return [["Capacitores por estágio – cálculo", "-", "-", CK.texto(CK.REPROVADO), f"sem resultado do cálculo: {ex}"]]
    ref = "; ".join(f"E{i + 1}: {n}×{q:g} kvar/{v:g} V" for i, (n, q, v) in enumerate(calc))
    falhas = {k: [] for k in ("esquema", "DE/PARA", "lista completa", "2D/3D", "ET do reator")}
    for i, (n, q, v) in enumerate(calc, start=1):
        r = tags_esq.get(f"-C{i}")
        if not r:
            falhas["esquema"].append(f"-C{i} ausente")
        else:
            qe, ve = _kv(r.get("Descrição"))
            if int(_num(r.get("Qtd")) or 0) != n or (qe and abs(qe - q) > 0.05) or (ve and abs(ve - v) > 0.5):
                falhas["esquema"].append(f"-C{i}: {r.get('Qtd')}× {qe} kvar/{ve} V")
        nd = len({t for row in dp for t in [str(row.get("PARA (tag:borne)") or "").split(":")[0],
                                             str(row.get("DE (tag:borne)") or "").split(":")[0]] if re.match(rf"^-C{i}\.\d+$", t)})
        if nd and nd != n:
            falhas["DE/PARA"].append(f"-C{i}: {nd} latas ligadas")
    # lista completa: soma das linhas -C… e kvar/V da descrição
    lcs = {id(r): r for t, r in tags_lc.items() if re.match(r"^-C\d+$", t)}.values()
    n_lc = sum(int(_num(r.get("Qtd")) or 0) for r in lcs)
    for r in lcs:
        ql, vl = _kv(str(r.get("Descrição")) + " " + str(r.get("Código")))
        if ql and not any(abs(ql - q) < 0.05 for _, q, _ in calc) or vl and not any(abs(vl - v) < 0.5 for *_, v in calc):
            falhas["lista completa"].append(f"lata {ql} kvar/{vl} V")
    if n_lc != sum(n for n, _, _ in calc):
        falhas["lista completa"].append(f"total {n_lc} ≠ {sum(n for n, _, _ in calc)}")
    cg = lay.get("contagem") or {}
    pe3 = cg.get("capacitores_por_estagio")
    if pe3 is not None and list(pe3) != [n for n, _, _ in calc]:
        falhas["2D/3D"].append(f"por estágio {pe3}")
    if cg.get("capacitores") is not None and cg["capacitores"] != sum(n for n, _, _ in calc):
        falhas["2D/3D"].append(f"total {cg['capacitores']}")
    try:                                                         # ET do reator: "Capacitor Associado: 75 kVAr/525 V (3 × 25 kVAr/525 V)"
        import docx
        ets = glob.glob(os.path.join(pasta, "03_Fornecedores", "*Reator*", "*.docx"))
        for f in ets:
            d = docx.Document(f)
            t = "\n".join(p_.text for p_ in d.paragraphs) + "\n".join(c.text for tb in d.tables for rw in tb.rows for c in rw.cells)
            m = re.search(r"\((\d+)\s*[×x]\s*(\d+(?:[.,]\d+)?)\s*kVAr\s*/\s*(\d+)\s*V\)", t)
            if not m:
                falhas["ET do reator"].append(f"{os.path.basename(f)}: sem 'n × kvar/V'")
            elif (int(m.group(1)), _num(m.group(2)), _num(m.group(3))) not in [(n, q, v) for n, q, v in calc]:
                falhas["ET do reator"].append(f"{os.path.basename(f)}: {m.group(0)}")
    except Exception as ex:
        falhas["ET do reator"].append(f"não lida ({type(ex).__name__})")
    for k, f in falhas.items():
        out.append([f"Capacitores por estágio/indutor: cálculo × {k} (REQ-GER-011)", ref if k == "esquema" else "= cálculo",
                    "igual" if not f else "; ".join(dict.fromkeys(f))[:300], CK.texto(CK.APROVADO if not f else CK.REPROVADO), ""])
    return out


def conferir(pasta, res=None):
    pnl = os.path.join(pasta, "03_Fornecedores", "2_Painel_Montadora")
    L, err = [], []

    def lin(item, a, b, ok, nivel=CK.REPROVADO, obs=""):
        L.append([item, a, b, CK.texto(CK.APROVADO if ok else nivel), obs])

    try:
        esq = _xlsx(glob.glob(os.path.join(pnl, "Lista_Material_Bornes_Cabos_*.xlsx"))[0], "Lista de material", 2)
        cabos_esq = _xlsx(glob.glob(os.path.join(pnl, "Lista_Material_Bornes_Cabos_*.xlsx"))[0], "Cabos", 2)
        lc = _xlsx(glob.glob(os.path.join(pnl, "Lista_Material_Completa_*.xlsx"))[0], "Lista completa", 1)
        lay = json.load(open(glob.glob(os.path.join(pasta, "**", "layout_painel.json"), recursive=True)[0], encoding="utf-8"))
        dp = _xlsx(glob.glob(os.path.join(pnl, "Lista_DePara_Etiquetas_*.xlsx"))[0], "DE-PARA", 1)
    except Exception as ex:
        return [["Arquivos da conferência", "-", "-", CK.texto(CK.REPROVADO), f"faltou arquivo: {type(ex).__name__}: {ex}"]]
    tags_esq = {}
    for r in esq:
        t = str(r.get("Tag") or "").strip()
        if t.startswith("-"):
            tags_esq[t] = r
    tags_3d = set(lay.get("tags") or [])
    tags_lc = {}
    for r in lc:
        for t in _expand(r.get("Tag")):
            tags_lc.setdefault(t, r)
    tags_dp = set()
    for r in dp:
        for k in ("DE (tag:borne)", "PARA (tag:borne)"):
            v = str(r.get(k) or "")
            if v.startswith("-"):
                tags_dp.add(v.split(":")[0])
    ignorar_3d = {"-W"}                                          # -W = cabos (lista de cabos), não peça
    for t in ("-R2", "-S2", "-T2", "-PE2"):                       # barras do esquema (DE/PARA) também têm que estar no 3D
        if t in tags_dp:
            tags_esq.setdefault(t, {"Tag": t, "Código": "", "Qtd": 1})
    # 1) todo componente do esquema está no 2D/3D
    falt3d = sorted(t for t in tags_esq if t not in tags_3d and t not in ignorar_3d)
    lin("Componentes do esquema presentes no 2D/3D", f"{len(tags_esq)} tags no esquema", f"{len(tags_3d)} tags no 3D", not falt3d,
        obs=("faltam no 2D/3D: " + ", ".join(falt3d)) if falt3d else "todos presentes")
    extra3d = sorted(t for t in tags_3d if t not in tags_esq)
    lin("Componentes do 2D/3D que não estão no esquema", "-", f"{len(extra3d)}", not extra3d, nivel=CK.REPROVADO,
        obs=("sobram no 2D/3D: " + ", ".join(extra3d)) if extra3d else "nenhum")
    # 2) todo componente do esquema está na lista completa (e vice-versa)
    faltlc = sorted(t for t in tags_esq if t not in tags_lc and t not in ignorar_3d and not t.startswith("-X1"))
    lin("Componentes do esquema presentes na lista de material completa", f"{len(tags_esq)}", f"{len(tags_lc)}", not faltlc,
        obs=("faltam na lista: " + ", ".join(faltlc)) if faltlc else "todos presentes")
    sobra_lc = sorted(t for t in tags_lc if t not in tags_esq and t not in ("-R2", "-S2", "-T2", "-PE2") and not t.startswith(("-W", "-X0")))
    lin("Componentes da lista de material completa que não estão no esquema", "-", f"{len(sobra_lc)}", not sobra_lc,
        obs=("sobram na lista: " + ", ".join(sobra_lc)) if sobra_lc else "nenhum")
    # 3) mesmo código no esquema e na lista completa
    dif = []
    for t, r in tags_esq.items():
        if t in tags_lc:
            a, b = _norm(r.get("Código")), _norm(tags_lc[t].get("Código"))
            if a and b and a.split()[:2] != b.split()[:2] and not ("conferir" in str(r.get("Código")).lower() and "conferir" in str(tags_lc[t].get("Código")).lower()):
                dif.append(f"{t}: esquema '{str(r.get('Código'))[:40]}' × lista '{str(tags_lc[t].get('Código'))[:40]}'")
    lin("Mesmo código/modelo no esquema e na lista completa", "esquema", "lista completa", not dif, nivel=CK.ATENCAO,
        obs="; ".join(dif[:8]) if dif else "códigos coerentes")
    # 4) REQ-GER-011: capacitores POR ESTÁGIO/INDUTOR (quantidade × kvar × V) iguais em cálculo, esquema, DE/PARA, lista, 3D e ET do reator
    lin_cap = capacitores_por_estagio(pasta, tags_esq, tags_lc, dp, lay, res=res)
    L.extend(lin_cap)
    # 5) seção dos cabos de força esquema × lista completa
    sec_esq = sorted({str(r.get("Seção (mm²)")) for r in cabos_esq if str(r.get("Cabo") or "").startswith("W") and r.get("Seção (mm²)")})
    sec_lc = sorted({m.group(1) for r in lc for m in [re.search(r"(\d+) mm² (?:preto|classe)", str(r.get("Descrição") or "") + " " + str(r.get("Código") or ""))] if m})
    falt_sec = [s_ for s_ in sec_esq if s_.replace(".0", "") not in sec_lc and s_.isdigit()]
    lin("Seções de cabo de força do esquema presentes na lista completa", ", ".join(sec_esq) or "-", ", ".join(sec_lc) or "-", not falt_sec,
        nivel=CK.ATENCAO, obs=("seções do esquema sem item na lista: " + ", ".join(falt_sec)) if falt_sec else "coerentes")
    # 6) DE/PARA só usa tags existentes
    infra = {"-R2", "-S2", "-T2", "-PE2"}                        # barras de fase e PE (desenhadas no 3D com essas tags)
    sem = sorted(t for t in tags_dp if t not in tags_esq and t.split(".")[0] not in tags_esq and t not in infra
                 and not t.startswith(("-X", "-W")))
    lin("Ligações do DE/PARA só entre componentes do esquema", f"{len(tags_dp)} tags no DE/PARA", "-", not sem,
        obs=("tags do DE/PARA sem componente: " + ", ".join(sem)) if sem else "coerente")
    return L


def planilha(L, arq):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    wb = Workbook()
    ws = wb.active
    ws.title = "Conferência cruzada"
    ws.append(["Conferência", "Projeto elétrico", "2D/3D / lista", "Check", "Diferenças"])
    for r in L:
        ws.append(r)
    for c in ws[1]:
        c.font = Font(bold=True, color="FFFFFF"); c.fill = PatternFill("solid", fgColor="C8641E")
    for i, w in enumerate([48, 22, 22, 16, 110]):
        ws.column_dimensions[chr(65 + i)].width = w
    for row in ws.iter_rows(min_row=2):
        for c in row:
            c.alignment = Alignment(wrap_text=True, vertical="top")
    CK.colorir_planilha(ws)
    os.makedirs(os.path.dirname(arq), exist_ok=True)
    wb.save(arq)
    return arq
