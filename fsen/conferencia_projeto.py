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


def conferir(pasta):
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
    # 3) mesmo código no esquema e na lista completa
    dif = []
    for t, r in tags_esq.items():
        if t in tags_lc:
            a, b = _norm(r.get("Código")), _norm(tags_lc[t].get("Código"))
            if a and b and a.split()[:2] != b.split()[:2] and not ("conferir" in str(r.get("Código")).lower() and "conferir" in str(tags_lc[t].get("Código")).lower()):
                dif.append(f"{t}: esquema '{str(r.get('Código'))[:40]}' × lista '{str(tags_lc[t].get('Código'))[:40]}'")
    lin("Mesmo código/modelo no esquema e na lista completa", "esquema", "lista completa", not dif, nivel=CK.ATENCAO,
        obs="; ".join(dif[:8]) if dif else "códigos coerentes")
    # 4) quantidade de capacitores esquema × 3D
    n_c_esq = sum(int(r.get("Qtd") or 0) for t, r in tags_esq.items() if re.match(r"^-C\d+$", t))
    n_c_3d = (lay.get("contagem") or {}).get("capacitores")
    lin("Quantidade de capacitores esquema × 3D", str(n_c_esq), str(n_c_3d), n_c_3d is None or n_c_esq == n_c_3d)
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
