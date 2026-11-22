"""Estilo gráfico dos esquemas APRENDIDO dos projetos EPLAN da Electric (v1.16.3).

`aprender(pdfs)` lê PDFs vetoriais exportados do EPLAN (ex.: "Filtro AGCO 300kVAr_v3.pdf") e mede o que o EPLAN usa de verdade:
espessuras de traço, fonte e alturas de texto por função (tag, nº de borne/dados, seção), cores por camada, grade de colunas.
O resultado vai para dados/estilo_eplan.json e o renderizador da plataforma (qet.render_pdf) desenha com esses valores –
quanto mais projetos EPLAN forem lidos, mais o padrão se firma (a medida é a moda de todas as folhas).
Sem JSON, vale o PADRAO (medido no projeto AGCO Ibirubá, 19 folhas).
"""
from __future__ import annotations

import collections
import json
import os

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ARQ = os.path.join(RAIZ, "dados", "estilo_eplan.json")

PADRAO = {
    "origem": "Filtro AGCO 300kVAr_v3.pdf (EPLAN, 19 folhas) – medido em 22/11/2026",
    "folha": "A3 420×297 mm",
    "colunas": 10,
    "traco_mm": 0.25,            # condutores e símbolos
    "traco_fino_mm": 0.13,       # hachuras, molduras internas
    "traco_grosso_mm": 0.35,     # moldura / carimbo
    "fonte": "Tahoma",
    "alt_tag_mm": 3.11,          # -K1, -FF1, -R2 …
    "alt_borne_mm": 2.24,        # 1/2, 3/4, A1/A2, dados do componente, referência cruzada
    "alt_secao_mm": 1.61,        # "25 mm²" junto do traço oblíquo
    "alt_titulo_mm": 3.11,
    "cor_tag": "#0000ff",
    "cor_barra": "#0000ff",
    "cor_secao": "#ff0000",
    "cor_xref": "#00a000",
    "cor_fio": "#000000",
    "cor_pe": "#00a000",
    "cor_neutro": "#0000ff",
}


def _hex(c):
    try:
        if isinstance(c, (list, tuple)) and len(c) == 3:
            return "#%02x%02x%02x" % tuple(int(round(float(v) * 255)) for v in c)
        if isinstance(c, (list, tuple)) and len(c) == 1:
            g = int(round(float(c[0]) * 255))
            return "#%02x%02x%02x" % (g, g, g)
    except (TypeError, ValueError):
        pass
    return None


def aprender(pdfs, salvar=True, log=print):
    """Mede os PDFs do EPLAN e grava o estilo. Retorna o dicionário aprendido (com o nº de folhas e amostras)."""
    import pdfplumber
    mm = 25.4 / 72
    lw, fontes, cores_txt, cores_lin, cols = collections.Counter(), collections.Counter(), collections.Counter(), collections.Counter(), []
    folhas = 0
    for arq in pdfs:
        with pdfplumber.open(arq) as pdf:
            for p in pdf.pages:
                if abs(p.width - 1191) > 30:         # só A3
                    continue
                folhas += 1
                for l in p.lines + p.curves:
                    lw[round(l.get("linewidth", 0) * mm, 2)] += 1
                    c = _hex(l.get("stroking_color"))
                    if c:
                        cores_lin[c] += 1
                for ch in p.chars:
                    nome = ch["fontname"].split("+")[-1].split("-")[0]
                    fontes[(nome, round(ch["size"] * mm, 2))] += 1
                    c = _hex(ch.get("non_stroking_color"))
                    if c:
                        cores_txt[(c, round(ch["size"] * mm, 2))] += 1
                topo = [w for w in p.extract_words() if w["top"] < 30 and w["text"].isdigit()]
                if len(topo) >= 5:
                    cols.append(len(topo))
    if not folhas:
        raise ValueError("Nenhuma folha A3 vetorial encontrada nos PDFs.")
    est = dict(PADRAO)
    tr = [w for w, _ in lw.most_common() if w > 0]
    est["traco_mm"] = tr[0]
    finos = [w for w in tr if w < est["traco_mm"]]
    grossos = [w for w in tr if w > est["traco_mm"]]
    est["traco_fino_mm"] = finos[0] if finos else est["traco_fino_mm"]
    est["traco_grosso_mm"] = grossos[0] if grossos else est["traco_grosso_mm"]
    tamanhos = collections.Counter()
    for (nome, alt), n in fontes.items():
        tamanhos[alt] += n
        est["fonte"] = fontes.most_common(1)[0][0][0]
    alts = sorted(a for a, _ in tamanhos.most_common(4))
    if len(alts) >= 3:
        est["alt_secao_mm"], est["alt_borne_mm"], est["alt_tag_mm"] = alts[0], tamanhos.most_common(1)[0][0], alts[-1]
        est["alt_titulo_mm"] = alts[-1]
    tag_cor = [c for (c, a), _ in cores_txt.most_common() if abs(a - est["alt_tag_mm"]) < 0.05 and c not in ("#000000",)]
    if tag_cor:
        est["cor_tag"] = tag_cor[0]
    sec_cor = [c for (c, a), _ in cores_txt.most_common() if abs(a - est["alt_secao_mm"]) < 0.05 and c not in ("#000000",)]
    if sec_cor:
        est["cor_secao"] = sec_cor[0]
    if cols:
        est["colunas"] = collections.Counter(cols).most_common(1)[0][0]
    est["origem"] = f"{len(pdfs)} PDF(s) EPLAN, {folhas} folhas A3: " + ", ".join(os.path.basename(a) for a in pdfs)[:300]
    est["amostras"] = dict(tracos=dict(lw.most_common(6)), fontes={f"{k[0]} {k[1]} mm": v for k, v in fontes.most_common(6)},
                           cores_linhas=dict(cores_lin.most_common(6)))
    if salvar:
        os.makedirs(os.path.dirname(ARQ), exist_ok=True)
        json.dump(est, open(ARQ, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        log(f"Estilo EPLAN aprendido de {folhas} folhas → {ARQ}")
    return est


def carregar():
    try:
        d = json.load(open(ARQ, encoding="utf-8"))
        return {**PADRAO, **d}
    except (OSError, ValueError):
        return dict(PADRAO)


def pt(alt_mm):
    """Altura de texto (mm, como o EPLAN mede) → tamanho de fonte em pontos para o matplotlib."""
    return alt_mm * 72 / 25.4
