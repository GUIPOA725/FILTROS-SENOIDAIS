"""Lista DE/PARA e ETIQUETAS (fios de força e comando, cabos externos e componentes) a partir do projeto QET (v1.16.1).

Vale para todos os filtros (senoidal, dessintonizado, sintonizado): qualquer esquema montado com eplan.qet passa por aqui.

Como a lista é montada (igual à lista de conexões do EPLAN):
  1. cada condutor do desenho liga dois bornes; os pontos de ligação (nós) e os nomes de potencial/barra juntam os condutores
     em POTENCIAIS (nets), inclusive entre folhas (mesmo nome de barra/potencial = mesmo potencial);
  2. potencial com BARRA (cobre: -R2/-S2/-T2, -PE2): cada borne vai à barra (estrela);
     potencial sem barra (fiação de comando, rede 220 V, ligações ponto a ponto): bornes ligados em cadeia, na ordem do desenho
     (folha, coluna) – é o fio que o montador passa de verdade;
  3. cada fio recebe o número (o do desenho, quando houver, senão folha.sequência), a seção e a cor do desenho.
Etiquetas:
  • fio: uma etiqueta em CADA PONTA, com o número do fio e o destino da outra ponta (padrão ponto a ponto: "4.03 → -K1:2");
  • componente: plaqueta com a tag (IEC 81346) e a descrição, separada por local (placa de montagem / porta);
  • cabo externo (cliente): tag do cabo, origem, destino, formação.
Saídas: XLSX (DE-PARA, etiquetas de fio, de componente e de cabo, prontas para importar no software da impressora de etiquetas
Brady / Hellermann / Phoenix – colunas Linha1/Linha2) e PDF para imprimir/conferir.
"""
from __future__ import annotations

import os
import re
from collections import defaultdict

PORTA = ("-S", "-H", "-U", "-P")     # componentes de porta (comando, sinalização, controlador, medidor)


def _nome_term(t):
    """Nome do borne: o do símbolo; senão a ordem do terminal no elemento."""
    e, nm = t[3], t[4]
    if nm:
        return nm
    if e.d.nome == "borne_continuite":
        return ""                       # a tag já tem o borne (-X0:L1)
    m = re.match(r"ctrl(\d+)", e.d.nome)
    if m:
        n = int(m.group(1))
        i = e.tid.index(t[0])
        nomes = ["L", "k", "l", "N", "C"] + [str(k + 1) for k in range(n)] + ["ALM"]
        return nomes[i] if i < len(nomes) else str(i + 1)
    if e.d.nome == "tore1":
        return ("S1", "S2")[e.tid.index(t[0]) % 2]
    return str(e.tid.index(t[0]) + 1)


def _ref(t):
    e = t[3]
    nm = _nome_term(t)
    return f"{e.label}:{nm}" if nm else e.label


def potenciais(Q):
    """Une condutores em potenciais. Retorna lista de dict(bornes=[(folha, x, y, ref, elem)], barra, pot, conds=[...])."""
    pai = {}

    def ach(a):
        while pai.setdefault(a, a) != a:
            pai[a] = pai[pai[a]]
            a = pai[a]
        return a

    def une(a, b):
        ra, rb = ach(a), ach(b)
        if ra != rb:
            pai[rb] = ra

    nomes = {}
    for f in Q.folios:
        for e in f.elems:
            if e.d.nome == "no":
                for t in e.tid:
                    une(("t", t), ("e", e.uuid))
                nm = e.info.get("barra") or e.info.get("pot")
                if nm:
                    une(("e", e.uuid), ("nome", nm))
                    nomes[("nome", nm)] = (nm, bool(e.info.get("barra")))
        for c in f.conds:
            une(("t", c["a"][0]), ("t", c["b"][0]))
    grupos = defaultdict(lambda: dict(bornes={}, barra="", pot="", conds=[], por_borne=defaultdict(list)))
    for f in Q.folios:
        for c in f.conds:
            g = grupos[ach(("t", c["a"][0]))]
            g["conds"].append((f.n, c))
            for t in (c["a"], c["b"]):
                e = t[3]
                if e.d.nome == "no":
                    if e.info.get("pe_de"):
                        ref = f"{e.info['pe_de']}:PE"
                        g["bornes"].setdefault(ref, (f.n, e.x, e.y, ref, e))
                        g["por_borne"][ref].append(c)
                    continue
                ref = _ref(t)
                g["bornes"].setdefault(ref, (f.n, t[1], t[2], ref, e))
                g["por_borne"][ref].append(c)
    for k, (nm, barra) in nomes.items():
        r = ach(k)
        if r in grupos:
            if barra:
                grupos[r]["barra"] = nm
            else:
                grupos[r]["pot"] = nm
    out = []
    for g in grupos.values():
        g["bornes"] = _cadeia(list(g["bornes"].values()), g["conds"])
        if g["bornes"]:
            out.append(g)
    out.sort(key=lambda g: (g["bornes"][0][0], g["bornes"][0][1], g["bornes"][0][2]))
    return out


def _cadeia(bs, conds=()):
    """Ordem da fiação em cadeia: segue o próprio desenho (busca em profundidade pelos condutores, começando no borne -X ou
    no ponto mais acima/à esquerda) – o fio vai de um componente ao seguinte como está desenhado; folhas diferentes em sequência."""
    ref_de_t, pos = {}, {}
    for b in bs:
        pos[b[3]] = b
    adj = defaultdict(list)
    for fl, c in conds:
        ka, kb = ("t", c["a"][0]), ("t", c["b"][0])
        adj[ka].append(kb)
        adj[kb].append(ka)
        for t, k in ((c["a"], ka), (c["b"], kb)):
            e = t[3]
            if e.d.nome == "no":
                if e.info.get("pe_de"):
                    ref_de_t[k] = f"{e.info['pe_de']}:PE"
                # nós com o mesmo nome (potencial/barra) em folhas diferentes continuam o caminho
                nm = e.info.get("pot") or e.info.get("barra")
                if nm:
                    adj[k].append(("nome", nm))
                    adj[("nome", nm)].append(k)
            else:
                ref_de_t[k] = _ref(t)
    coord = {}
    for fl, c in conds:
        for t in (c["a"], c["b"]):
            coord[("t", t[0])] = (fl, t[1], t[2])
    ini = sorted(bs, key=lambda b: (b[0], not b[3].startswith("-X"), b[2], b[1]))[0]
    k0 = next((k for k, r in ref_de_t.items() if r == ini[3]), None)
    if k0 is None:
        return sorted(bs, key=lambda b: (b[0], b[2], b[1]))
    out, vis, pilha = [], set(), [k0]
    while pilha:
        k = pilha.pop()
        if k in vis:
            continue
        vis.add(k)
        r = ref_de_t.get(k)
        if r and r in pos and pos[r] not in out:
            out.append(pos[r])
        c0 = coord.get(k, (0, 0, 0))
        viz = sorted(adj[k], key=lambda v: -(abs(coord.get(v, c0)[1] - c0[1]) + abs(coord.get(v, c0)[2] - c0[2]) + 1e4 * (coord.get(v, c0)[0] != c0[0])))
        pilha.extend(v for v in viz if v not in vis)
    out += [b for b in bs if b not in out]
    return sorted(out, key=lambda b: b[0])        # estável: dentro da folha mantém a ordem do desenho


def _tipo(g):
    marcas = " ".join(c["marca"] for _, c in g["conds"]).upper()
    if g["barra"].startswith("-PE") or "VD/AM" in marcas:
        return "PE"
    if any(c["pot"] for _, c in g["conds"]) or "PT" in marcas.split():
        return "Força"
    return "Comando"


def _fios_desenhados(g):
    """Fios físicos de um potencial sem barra, pela TOPOLOGIA do desenho: cada ponto de ligação (nó) é absorvido pelo borne
    vizinho de maior seção (mais próximo no empate) – é nesse borne que os terminais se encontram; cada condutor desenhado
    vira o fio entre os bornes donos das suas pontas (com a seção e a cor DESSE condutor). Potenciais com o mesmo nome em
    folhas diferentes (L220, N220…) ligam-se pelo primeiro ponto de cada folha. → (pares, atributos)"""
    f_ = lambda s: float(str(s).replace(",", ".")) if s else 0.0
    ref_t, info_t, adj, arestas = {}, {}, defaultdict(list), []
    pos = {b[3]: b for b in g["bornes"]}
    nomes = defaultdict(list)
    for fl, c in g["conds"]:
        ka, kb = c["a"][0], c["b"][0]
        arestas.append((ka, kb, c))
        adj[ka].append((kb, c))
        adj[kb].append((ka, c))
        for t in (c["a"], c["b"]):
            e = t[3]
            info_t[t[0]] = (fl, t[1], t[2])
            if e.d.nome == "no":
                if e.info.get("pe_de"):
                    ref_t[t[0]] = f"{e.info['pe_de']}:PE"
                nm = e.info.get("pot")
                if nm and t[0] not in [x for x, _ in nomes[nm]]:
                    nomes[nm].append((t[0], (fl, t[2], t[1])))
            else:
                ref_t[t[0]] = _ref(t)
    dono = dict(ref_t)
    for _ in range(50):                      # nó → borne vizinho de maior seção; nó sem borne vizinho herda do nó vizinho
        mudou = False
        for k in list(adj):
            if k in dono:
                continue
            c0 = info_t.get(k, (0, 0, 0))
            cand = [(f_(c["secao"]), -abs(info_t.get(v, c0)[1] - c0[1]) - abs(info_t.get(v, c0)[2] - c0[2]), dono[v])
                    for v, c in adj[k] if v in dono]
            if cand:
                dono[k] = max(cand)[2]
                mudou = True
        if not mudou:
            break
    vistos, pares, attrs = set(), [], []

    def add(ra, rb, c):
        if not ra or not rb or ra == rb or ra not in pos or rb not in pos:
            return
        ch = tuple(sorted((ra, rb)))
        if ch in vistos:
            return
        vistos.add(ch)
        a_, b_ = pos[ra], pos[rb]
        if (b_[0], b_[2], b_[1]) < (a_[0], a_[2], a_[1]):
            a_, b_ = b_, a_
        pares.append((a_, b_))
        attrs.append(dict(secao=c["secao"], marca=c["marca"]) if c else None)
    for ka, kb, c in arestas:
        add(dono.get(ka), dono.get(kb), c)
    for nm, lst in nomes.items():            # continuação entre folhas: 1º ponto de cada folha em sequência
        por_folha = {}
        for k, chave in sorted(lst, key=lambda x: x[1]):
            por_folha.setdefault(chave[0], k)
        ks = [por_folha[f] for f in sorted(por_folha)]
        c_ref = next((c for _, _, c in arestas if c["secao"]), None)
        for k1, k2 in zip(ks[:-1], ks[1:]):
            add(dono.get(k1), dono.get(k2), c_ref)
    ordem = sorted(range(len(pares)), key=lambda i: (pares[i][0][0], pares[i][0][2], pares[i][0][1]))
    return [pares[i] for i in ordem], [attrs[i] for i in ordem]


def de_para(Q):
    """Lista DE/PARA (um registro por fio físico)."""
    linhas, seq = [], defaultdict(int)
    for g in potenciais(Q):
        conds = [c for _, c in g["conds"]]
        num = next((c["num"] for c in conds if c["num"]), "")
        tipo = _tipo(g)

        def atrib(*refs):
            """Seção e cor do fio que chega nestes bornes (não do potencial inteiro – a barra tem cabos de várias seções)."""
            cs = [c for r in refs if r for c in g["por_borne"].get(r, [])] or conds
            f_ = lambda s: float(s.replace(",", "."))
            por = [max((c["secao"] for c in g["por_borne"].get(r, []) if c["secao"]), key=f_, default="") for r in refs if r]
            por = [x for x in por if x]
            sec = min(por, key=f_) if por else max((c["secao"] for c in cs if c["secao"]), key=f_, default="")
            mc = next((c["marca"] for c in cs if c["marca"] and c["marca"] != "PT"), None) or next((c["marca"] for c in cs if c["marca"]), "")
            return sec, mc
        bs = g["bornes"]
        if g["barra"]:
            pares = [(b, None) for b in bs]
            attrs = [None] * len(pares)
        else:
            if len(bs) < 2:
                continue
            pares, attrs = _fios_desenhados(g)
        for i, (a, b) in enumerate(pares):
            if num:
                n = num if len(pares) == 1 else f"{num}.{i + 1}"
            else:
                seq[a[0]] += 1
                n = f"{a[0]}.{seq[a[0]]:02d}"
            secao, marca = atrib(a[3], b[3] if b else None)
            if attrs[i]:
                secao, marca = attrs[i]["secao"] or secao, attrs[i]["marca"] or marca
            linhas.append(dict(fio=n, de=a[3], para=(b[3] if b else g["barra"]), secao=secao, cor=marca or ("VD/AM" if tipo == "PE" else ""),
                               tipo=tipo, folha_de=a[0], folha_para=(b[0] if b else a[0]), potencial=g["barra"] or g["pot"] or num))
    return linhas


def etiquetas_fios(lin):
    """Duas etiquetas por fio (uma em cada ponta): número do fio + destino da outra ponta."""
    out = []
    for l in lin:
        out.append(dict(fio=l["fio"], ponta=l["de"], linha1=l["fio"], linha2=f"→ {l['para']}", secao=l["secao"], cor=l["cor"], tipo=l["tipo"]))
        out.append(dict(fio=l["fio"], ponta=l["para"], linha1=l["fio"], linha2=f"→ {l['de']}", secao=l["secao"], cor=l["cor"], tipo=l["tipo"]))
    return out


def etiquetas_componentes(Q, extra=()):
    """Plaquetas: uma por tag (IEC 81346) com a descrição. extra = [(tag, descrição, local)] (ex.: placa do painel)."""
    vistos, out = set(), []
    for f in Q.folios:
        for e in f.elems:
            tag = e.label
            if not tag or e.d.nome == "no":
                continue
            base = tag.split(":")[0] if e.d.nome == "borne_continuite" else re.sub(r"\.\d+$", "", tag) if False else tag
            if base in vistos:
                continue
            vistos.add(base)
            desc = (e.info.get("designation") or e.d.pt or e.d.nome).strip()
            if e.d.nome == "borne_continuite":
                desc = "Régua de bornes"
            local = "Porta" if base.startswith(PORTA) else "Placa de montagem"
            out.append(dict(tag=base, descricao=desc, local=local, folha=f.n, coluna=Q.coluna(e.x) if hasattr(Q, "coluna") else ""))
    for tag, desc, local in extra:
        out.append(dict(tag=tag, descricao=desc, local=local, folha="", coluna=""))
    return sorted(out, key=lambda d: (d["local"] != "Porta", _chave_tag(d["tag"])))


def _chave_tag(t):
    m = re.match(r"-?([A-Z]+)(\d*)\.?(\d*)", t.upper())
    return (m.group(1), int(m.group(2) or 0), int(m.group(3) or 0)) if m else (t, 0, 0)


def gerar(Q, pasta, cod, cabos_externos=(), extra_componentes=(), versao="", titulo="", funcoes=None, pe_massas=(), secao_pe="6"):
    """Gera XLSX + PDF de DE/PARA e etiquetas.
    cabos_externos = [dict(tag, de, para, formacao, funcao)]; funcoes = {tag: texto da plaqueta de porta, ex. 'ESTÁGIO 1'};
    pe_massas = tags cujas carcaças vão ao PE (reatores, porta, placa) – entram na DE/PARA como fios PE.n."""
    lin = de_para(Q)
    barra_pe = next((l["para"] for l in lin if l["tipo"] == "PE" and l["para"].startswith("-PE")), "-PE")
    for i, tg in enumerate(pe_massas):
        lin.append(dict(fio=f"PE.{i + 1}", de=f"{tg}:PE", para=barra_pe, secao=secao_pe, cor="VD/AM", tipo="PE",
                        folha_de="", folha_para="", potencial=barra_pe))
    ef = etiquetas_fios(lin)
    ec = etiquetas_componentes(Q, extra_componentes)
    for c in ec:
        c["funcao"] = (funcoes or {}).get(c["tag"], "")
    arq_x = os.path.join(pasta, f"Lista_DePara_Etiquetas_{cod}.xlsx")
    _xlsx(arq_x, lin, ef, ec, cabos_externos, cod, versao, titulo)
    arq_p = os.path.join(pasta, f"Etiquetas_{cod}.pdf")
    _pdf(arq_p, lin, ef, ec, cabos_externos, cod, versao, titulo)
    return dict(xlsx=arq_x, pdf=arq_p, de_para=lin, n_fios=len(lin), n_etq_fios=len(ef), n_componentes=len(ec))


def _xlsx(arq, lin, ef, ec, cabos, cod, versao, titulo):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    wb = Workbook()
    cab_f, fill = Font(bold=True, color="FFFFFF"), PatternFill("solid", fgColor="1F4E8C")

    def aba(ws, cab, linhas, larg):
        ws.append([f"{titulo} – {cod} – {versao}"])
        ws["A1"].font = Font(bold=True, size=12)
        ws.append(cab)
        for c in ws[2]:
            c.font, c.fill, c.alignment = cab_f, fill, Alignment(horizontal="center")
        for l in linhas:
            ws.append(l)
        for i, w in enumerate(larg):
            ws.column_dimensions[chr(65 + i)].width = w
        ws.freeze_panes = "A3"
        ws.auto_filter.ref = f"A2:{chr(64 + len(cab))}{ws.max_row}"

    ws = wb.active
    ws.title = "DE-PARA"
    aba(ws, ["Nº fio", "DE (tag:borne)", "PARA (tag:borne)", "Seção (mm²)", "Cor", "Tipo", "Folha DE", "Folha PARA", "Potencial"],
        [[l["fio"], l["de"], l["para"], l["secao"], l["cor"], l["tipo"], l["folha_de"], l["folha_para"], l["potencial"]] for l in lin],
        [10, 22, 22, 11, 9, 10, 9, 10, 16])
    aba(wb.create_sheet("Etiquetas fios"), ["Nº fio", "Ponta (onde colar)", "Linha1", "Linha2", "Seção", "Cor", "Tipo"],
        [[e["fio"], e["ponta"], e["linha1"], e["linha2"], e["secao"], e["cor"], e["tipo"]] for e in ef], [10, 22, 10, 24, 8, 8, 10])
    aba(wb.create_sheet("Etiquetas componentes"), ["Tag", "Descrição", "Local", "Folha", "Coluna", "Linha1", "Linha2"],
        [[c["tag"], c["descricao"], c["local"], c["folha"], c["coluna"], c["tag"], (c.get("funcao") or c["descricao"])[:40]] for c in ec],
        [12, 44, 18, 7, 8, 12, 40])
    aba(wb.create_sheet("Etiquetas cabos"), ["Tag do cabo", "DE", "PARA", "Formação", "Função", "Linha1", "Linha2"],
        [[c["tag"], c["de"], c["para"], c["formacao"], c.get("funcao", ""), c["tag"], f"{c['de']} → {c['para']}"] for c in cabos],
        [12, 26, 26, 22, 26, 12, 40])
    wi = wb.create_sheet("Como usar")
    for t in ("Lista DE/PARA e etiquetas geradas pela plataforma FSEN a partir do esquema elétrico (mesmos números do desenho).",
              "Fios: uma etiqueta em CADA ponta – Linha1 = número do fio, Linha2 = destino da outra ponta (ponto a ponto).",
              "Força ≥ 6 mm²: anilha/etiqueta termorretrátil; comando 1,5 mm²: anilha tipo luva ou etiqueta de bandeira.",
              "Componentes: plaqueta de acrílico/poliéster gravada (porta: 70×20 mm; placa de montagem: 40×12 mm), junto do componente.",
              "Cabos externos (cliente): etiqueta de cabo nas duas pontas.",
              "Importar no software da impressora (Brady Workstation, Hellermann TAGPRINT, Phoenix PROJECT complete): colunas Linha1/Linha2.",
              "Norma: identificação IEC 81346-2 / NBR IEC 61439-1 (cl. 6 – marcação), cores de condutor NBR 5410 / IEC 60445."):
        wi.append([t])
    wi.column_dimensions["A"].width = 120
    wb.save(arq)


def _pdf(arq, lin, ef, ec, cabos, cod, versao, titulo):
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas
    c = canvas.Canvas(arq, pagesize=A4)
    W, H = A4

    def cabec(t, pag):
        c.setFont("Helvetica-Bold", 11)
        c.drawString(15 * mm, H - 14 * mm, t)
        c.setFont("Helvetica", 7)
        c.drawString(15 * mm, H - 19 * mm, f"{titulo} – {cod} – {versao}")
        c.drawRightString(W - 15 * mm, 8 * mm, f"Electric Service – plataforma FSEN   pág. {pag}")

    pag = 1
    # ---------------- DE/PARA
    cols = [("Nº fio", 18), ("DE", 40), ("PARA", 40), ("Seção", 15), ("Cor", 14), ("Tipo", 16), ("Fl. DE", 12), ("Fl. PARA", 14)]
    i = 0
    while i < len(lin) or i == 0:
        cabec("LISTA DE / PARA – fiação interna do painel", pag)
        y = H - 28 * mm
        x = 15 * mm
        c.setFont("Helvetica-Bold", 7)
        for nm, w in cols:
            c.drawString(x, y, nm)
            x += w * mm
        c.line(15 * mm, y - 1.5 * mm, W - 15 * mm, y - 1.5 * mm)
        y -= 5 * mm
        c.setFont("Helvetica", 7)
        while i < len(lin) and y > 15 * mm:
            l = lin[i]
            x = 15 * mm
            for v, (_, w) in zip((l["fio"], l["de"], l["para"], l["secao"], l["cor"], l["tipo"], l["folha_de"], l["folha_para"]), cols):
                c.drawString(x, y, str(v)[:28])
                x += w * mm
            y -= 4.2 * mm
            i += 1
        c.showPage()
        pag += 1
        if i >= len(lin):
            break
    # ---------------- etiquetas de fio (folha A4, 4 colunas × 26 linhas de 45×9 mm)
    lw, lh, nc, nr = 45 * mm, 9 * mm, 4, 26
    x0, y0 = (W - nc * lw) / 2, H - 25 * mm
    for k0 in range(0, len(ef), nc * nr):
        cabec("ETIQUETAS DE FIO – uma em cada ponta (Linha1 nº do fio, Linha2 destino)", pag)
        for j, e in enumerate(ef[k0:k0 + nc * nr]):
            cx, cy = x0 + (j % nc) * lw, y0 - (j // nc + 1) * lh
            c.setStrokeGray(0.75)
            c.rect(cx, cy, lw, lh)
            c.setFont("Helvetica-Bold", 8)
            c.drawString(cx + 2 * mm, cy + 5 * mm, e["linha1"])
            c.setFont("Helvetica", 6)
            c.drawRightString(cx + lw - 2 * mm, cy + 5.2 * mm, f"{e['secao']} {e['cor']}".strip())
            c.drawString(cx + 2 * mm, cy + 1.6 * mm, f"{e['ponta']}  {e['linha2']}"[:40])
        c.showPage()
        pag += 1
    # ---------------- plaquetas de componentes (3 colunas de 60×18 mm)
    lw, lh, nc = 60 * mm, 18 * mm, 3
    nr = int((H - 40 * mm) // lh)
    x0, y0 = (W - nc * lw) / 2, H - 25 * mm
    for k0 in range(0, len(ec), nc * nr):
        cabec("PLAQUETAS DE IDENTIFICAÇÃO DOS COMPONENTES (porta e placa de montagem)", pag)
        for j, e in enumerate(ec[k0:k0 + nc * nr]):
            cx, cy = x0 + (j % nc) * lw, y0 - (j // nc + 1) * lh
            c.setStrokeGray(0.6)
            c.roundRect(cx + 1, cy + 1, lw - 2, lh - 2, 2 * mm)
            c.setFont("Helvetica-Bold", 13)
            c.drawCentredString(cx + lw / 2, cy + 9.5 * mm, e["tag"])
            if e.get("funcao"):
                c.setFont("Helvetica-Bold", 7)
                c.drawCentredString(cx + lw / 2, cy + 5 * mm, e["funcao"][:40])
            else:
                c.setFont("Helvetica", 6)
                c.drawCentredString(cx + lw / 2, cy + 5 * mm, e["descricao"][:46])
            c.setFont("Helvetica-Oblique", 5)
            c.drawCentredString(cx + lw / 2, cy + 2.2 * mm, e["local"])
        c.showPage()
        pag += 1
    # ---------------- cabos externos
    if cabos:
        cabec("ETIQUETAS DE CABOS EXTERNOS (nas duas pontas)", pag)
        y = H - 30 * mm
        for cb in cabos:
            c.setStrokeGray(0.6)
            c.rect(15 * mm, y - 12 * mm, 110 * mm, 12 * mm)
            c.setFont("Helvetica-Bold", 10)
            c.drawString(18 * mm, y - 5 * mm, cb["tag"])
            c.setFont("Helvetica", 7)
            c.drawString(40 * mm, y - 5 * mm, f"{cb['de']} → {cb['para']}")
            c.drawString(18 * mm, y - 10 * mm, f"{cb['formacao']}  {cb.get('funcao', '')}")
            y -= 15 * mm
        c.showPage()
    c.save()
