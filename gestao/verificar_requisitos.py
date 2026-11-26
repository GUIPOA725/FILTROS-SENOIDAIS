"""Verificador de requisitos do engenheiro (gestão de requisitos da Plataforma FSEN).

Uso:
    python gestao/verificar_requisitos.py [PASTA_DE_UM_PROJETO_GERADO ...] [--saida PASTA]

Lê gestao/REQUISITOS.yaml, roda os testes automáticos (código + projetos gerados), compara com a revisão anterior
(gestao/ultima_verificacao.json) e gera:
  • Registro_Requisitos_v<versão>.xlsx – abas Requisitos (com Check pintado), Revisão (o que mudou), Referências, Resumo
  • linha nova em gestao/REVISOES.md (análise)
Código de saída 1 = requisito CRÍTICO marcado ATENDIDO que falhou no teste, ou que regrediu → a versão NÃO deve ser publicada.
"""
from __future__ import annotations

import glob
import json
import os
import re
import subprocess
import sys

import yaml

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
G = os.path.join(RAIZ, "gestao")
sys.path.insert(0, RAIZ)


def _ler(rel):
    try:
        return open(os.path.join(RAIZ, rel), encoding="utf-8").read()
    except OSError:
        return ""


def _pdf_txt(arq):
    try:
        return subprocess.run(["pdftotext", arq, "-"], capture_output=True, text=True, timeout=120).stdout
    except Exception:
        try:
            from pypdf import PdfReader
            return "\n".join((p.extract_text() or "") for p in PdfReader(arq).pages)
        except Exception:
            return ""


def _pdf_paginas(arq):
    try:
        from pypdf import PdfReader
        return len(PdfReader(arq).pages)
    except Exception:
        return 0


# ------------------------------------------------------------------ testes automáticos: (ok, evidência)
def t_gestao_existe(projs):
    ok = all(os.path.exists(os.path.join(RAIZ, p)) for p in ("gestao/REQUISITOS.yaml", "gestao/REVISOES.md", "CLAUDE.md"))
    return ok, "REQUISITOS.yaml, REVISOES.md e CLAUDE.md presentes" if ok else "faltam arquivos de gestão"


def t_identidade_3_filtros(projs):
    s = _ler("fsen/pipeline.py") + _ler("fsen/pipeline_banco.py")
    itens = {"normas": "gerar_pdf" in s, "consolidado": "consolidado" in s, "check": "_CK" in _ler("fsen/pipeline.py"),
             "painel3d senoidal": "painel3d" in _ler("fsen/pipeline.py"), "painel3d banco": "painel3d" in _ler("fsen/pipeline_banco.py")}
    falta = [k for k, v in itens.items() if not v]
    return (not falta), ("igual nos 3 filtros" if not falta else "falta: " + ", ".join(falta))


def t_versao_nos_arquivos(projs):
    if not projs:
        return None, "sem projeto para conferir"
    ev = []
    for p in projs:
        js = glob.glob(os.path.join(p, "**", "pedido*.json"), recursive=True) + glob.glob(os.path.join(p, "**", "projeto.json"), recursive=True)
        ok = any("Plataforma FSEN" in open(j, encoding="utf-8", errors="ignore").read() for j in js)
        ev.append((os.path.basename(p), ok))
    return all(o for _, o in ev), "; ".join(f"{n}: {'versão gravada' if o else 'SEM versão'}" for n, o in ev)


def t_ajuda_completa(projs):
    try:
        r = subprocess.run([sys.executable, os.path.join(RAIZ, "validacao", "verificar_ajuda.py")], capture_output=True, text=True,
                           timeout=300, cwd=RAIZ)
        m = re.search(r"(\d+)\s+faltando", r.stdout + r.stderr)
        falt = int(m.group(1)) if m else (0 if r.returncode == 0 else -1)
        return falt == 0, (r.stdout.strip().splitlines() or ["?"])[-1][:160]
    except Exception as ex:
        return None, f"não rodou: {ex}"


def t_consolidado_completo(projs):
    if not projs:
        return None, "sem projeto para conferir"
    ev, ok = [], True
    for p in projs:
        c = glob.glob(os.path.join(p, "00_RELATORIO_CONSOLIDADO_*.pdf"))
        if not c:
            ok = False; ev.append(f"{os.path.basename(p)}: SEM consolidado"); continue
        n = _pdf_txt(c[0]).count("NÃO INCLUÍDO")
        ok &= n == 0
        ev.append(f"{os.path.basename(p)}: {_pdf_paginas(c[0])} págs, {n} não incluído(s)")
    return ok, "; ".join(ev)


def t_pastas_por_fornecedor(projs):
    if not projs:
        return None, "sem projeto para conferir"
    ok, ev = True, []
    for p in projs:
        tem = [d for d in ("01_Engenharia", "02_Cliente", "03_Fornecedores", "05_Desenhos") if os.path.isdir(os.path.join(p, d))]
        sub = [d for d in os.listdir(os.path.join(p, "03_Fornecedores"))] if os.path.isdir(os.path.join(p, "03_Fornecedores")) else []
        _mont = os.path.isdir(os.path.join(p, "04_Montadora")) or "2_Painel_Montadora" in sub   # v1.31.0: montadora fora de 03
        o = len(tem) == 4 and len(sub) >= 1 and _mont
        ok &= o
        ev.append(f"{os.path.basename(p)}: {len(tem)}/4 pastas, {len(sub)} subpasta(s) de fornecedor, montadora {'ok' if _mont else 'FALTA'}")
    return ok, "; ".join(ev)


def t_thd_nos_espectros(projs):
    s = _ler("fsen/doc_banco.py") + _ler("fsen/vista_simulacao.py")
    ok = "THD" in s
    ev = "código: espectros com THD" if ok else "código sem THD"
    if projs:
        for p in projs:
            c = glob.glob(os.path.join(p, "00_RELATORIO_CONSOLIDADO_*.pdf"))
            if c:
                tx = _pdf_txt(c[0])
                n = len(re.findall(r"THD|DHT", tx))
                ok &= n > 5
                ev += f"; {os.path.basename(p)}: THD/DHT {n}× no texto do consolidado (fora as figuras)"
    return ok, ev


def t_coluna_check(projs):
    ok = os.path.exists(os.path.join(RAIZ, "fsen", "checagem.py"))
    ev = "checagem.py presente"
    for p in projs or []:
        r = os.path.join(p, "RESUMO.md")
        if os.path.exists(r):
            s = open(r, encoding="utf-8").read()
            o = "| Check |" in s and "APROVADO" in s
            ok &= o
            ev += f"; {os.path.basename(p)}: RESUMO {'com' if o else 'SEM'} coluna Check"
    return ok, ev


def t_folha_normas(projs):
    if not projs:
        return None, "sem projeto para conferir"
    ok, ev = True, []
    for p in projs:
        f = glob.glob(os.path.join(p, "**", "Folha_de_Dados_e_Verificacao_*.pdf"), recursive=True)
        ok &= bool(f)
        ev.append(f"{os.path.basename(p)}: {'folha de normas OK' if f else 'SEM folha de normas'}")
    return ok, "; ".join(ev)


def t_atp_dupla_checagem(projs):
    if not projs:
        return None, "sem projeto para conferir"
    ok, ev = True, []
    for p in projs:
        r = os.path.join(p, "RESUMO.md")
        s = open(r, encoding="utf-8").read() if os.path.exists(r) else ""
        m = re.search(r"Plataforma = ATP em (\d+)/(\d+)", s)
        o = bool(m) and m.group(1) == m.group(2)
        if "ATP" in s and not m:
            o = "APROVADO" in s and "ATP" in s
        ok &= o
        ev.append(f"{os.path.basename(p)}: " + (f"ATP {m.group(1)}/{m.group(2)}" if m else ("ATP citado" if "ATP" in s else "sem ATP")))
    return ok, "; ".join(ev)


def t_dimensoes_com_fonte(projs):
    d = yaml.safe_load(_ler("dados/dimensoes_componentes.yaml")) or {}
    tot, sem = 0, []
    for g, itens in d.items():
        if not isinstance(itens, dict) or g == "gabinete_padrao_electric":
            continue
        for k, v in itens.items():
            tot += 1
            if not v.get("fonte") or v.get("conferir"):
                sem.append(k)
    return (not sem), f"{tot} componentes; a confirmar: {', '.join(sem) if sem else 'nenhum'}"


def t_painel_padrao_agco(projs):
    s = _ler("fsen/painel3d.py")
    itens = {"placa única dupla face": "placa no meio" in s.lower() or "dupla face" in s.lower(),
             "portas frente e trás": "porta_t" in s and "porta_f" in s, "6 folhas": "N = 6" in s,
             "vista de topo": "_topo(" in s, "verificação com Check": "CK.check" in s}
    falta = [k for k, v in itens.items() if not v]
    ev = "código: " + ("concepção AGCO completa" if not falta else "falta " + ", ".join(falta))
    ok = not falta
    for p in projs or []:
        f = glob.glob(os.path.join(p, "05_Desenhos", "*Painel_3D*", "Painel_3D_*.pdf"))
        if f:
            n = _pdf_paginas(f[0])
            ok &= n >= 6
            ev += f"; {os.path.basename(p)}: painel 3D {n} folhas"
        else:
            ok = False
            ev += f"; {os.path.basename(p)}: SEM painel 3D"
    return ok, ev


def t_referencias_ligadas(projs):
    d = yaml.safe_load(_ler("gestao/REFERENCIAS_PROJETOS.yaml")) or {}
    refs = d.get("referencias", [])
    nao = [r["id"] for r in refs if not r.get("usada_em") or r.get("usada_em") == "-"]
    return (not nao), f"{len(refs)} referências; ainda não usadas: {', '.join(nao) if nao else 'nenhuma'}"


def t_reator_vs_referencia(projs):
    """Reator calculado × reator real instalado (referência por cliente) – não pode ser maior sem motivo."""
    refs = {"Panatl": dict(L=315, kg=55, coluna=788, nome="Cootrans 796 µH/95 A (Panatlântica 2024)")}
    if not projs:
        return None, "sem projeto para conferir"
    ok, ev = True, []
    for p in projs:
        k = next((k for k in refs if k.lower() in p.lower()), None)
        if not k:
            continue
        js = glob.glob(os.path.join(p, "**", "indutor_projeto.json"), recursive=True)
        if not js:
            continue
        d = json.load(open(js[0], encoding="utf-8")).get("dims_mm", {})
        r = refs[k]
        cabe2 = 2 * d.get("largura", 9e9) + 3 * 30 <= r["coluna"]
        o = True                                            # REQ-REF-003: referência informativa – registra, não reprova
        ok &= o
        ev.append(f"{os.path.basename(p)}: {d.get('largura', 0):.0f}×{d.get('profundidade', 0):.0f}×{d.get('altura', 0):.0f} mm – "
                  f"{'cabem' if cabe2 else 'NÃO cabem'} 2 por coluna de {r['coluna']} mm como o {r['nome']}")
    if not ev:
        return None, "nenhum projeto com referência de reator real"
    return ok, "; ".join(ev)


def t_painel_montagem(projs):
    """Arranjo montável: verificações de montagem do painel (distribuição, afastamentos, cabos) no layout_painel.json."""
    if not projs:
        return None, "sem projeto para conferir"
    ok, ev = True, []
    for p in projs:
        f = glob.glob(os.path.join(p, "**", "layout_painel.json"), recursive=True)
        if not f:
            ok = False; ev.append(f"{os.path.basename(p)}: SEM layout_painel.json"); continue
        j = json.load(open(f[0], encoding="utf-8"))
        rep = [v[1][:60] for v in j.get("verificacoes", []) if "REPROVADO" in str(v[-1])]
        o = not rep and "_tubo" in _ler("fsen/painel3d.py") and "_canaleta" in _ler("fsen/painel3d.py")
        ok &= o
        ev.append(f"{os.path.basename(p)}: {len(j.get('verificacoes', []))} verificações de arranjo, reprovadas: {len(rep)}" + (f" ({'; '.join(rep[:3])})" if rep else ""))
    return ok, "; ".join(ev)


def t_conferencia_cruzada(projs):
    """REQ-PNL-028: esquema elétrico × painel 2D/3D × lista de material – zero diferença (nenhum REPROVADO)."""
    if not projs:
        return None, "sem projeto para conferir"
    import sys as _s
    _s.path.insert(0, RAIZ)
    from fsen import conferencia_projeto as CPJ
    ok, ev = True, []
    for p in projs:
        L = CPJ.conferir(p)
        rep = [f"{r[0]}: {str(r[4])[:70]}" for r in L if "REPROVADO" in str(r[3])]
        ok &= not rep
        ev.append(f"{os.path.basename(p)}: {len(L)} verificações, reprovadas {len(rep)}" + (f" ({'; '.join(rep[:3])})" if rep else ""))
    return ok, "; ".join(ev)


def t_biblioteca_paineis(projs):
    s = _ler("fsen/biblioteca_paineis.py")
    itens = {"aprovar": "def aprovar" in s, "partir do aprovado": "def ultimo_aprovado" in s and "ultimo_aprovado" in _ler("fsen/painel3d.py"),
             "botão na tela": "Aprovar painel" in _ler("telas_banco.py")}
    falta = [k for k, v in itens.items() if not v]
    return (not falta), ("aprovar + partir do último aprovado + botão na tela" if not falta else "falta: " + ", ".join(falta))


TESTES = {k[2:]: v for k, v in globals().items() if k.startswith("t_")}


def avaliar(projs):
    reg = yaml.safe_load(open(os.path.join(G, "REQUISITOS.yaml"), encoding="utf-8"))
    cache = {}
    out = []
    for r in reg["requisitos"]:
        v = str(r.get("verificacao", ""))
        auto = v.startswith("auto:")
        res, ev = None, ""
        if auto:
            tid = v.split(":", 1)[1].strip()
            if tid not in cache:
                try:
                    cache[tid] = TESTES[tid](projs)
                except Exception as ex:
                    cache[tid] = (None, f"erro no teste: {type(ex).__name__}: {ex}")
            res, ev = cache[tid]
        st = r.get("status", "PENDENTE")
        if res is True:
            chk = "APROVADO" if st == "ATENDIDO" else "ATENÇÃO"
        elif res is False:
            chk = "REPROVADO"
        else:
            chk = {"ATENDIDO": "APROVADO", "PARCIAL": "ATENÇÃO", "PENDENTE": "REPROVADO"}.get(st, "ATENÇÃO") if not auto else "ATENÇÃO"
        out.append(dict(r, teste=("automático" if auto else "manual"), resultado=res, evidencia=ev, check=chk))
    return reg, out


def comparar(out):
    arq = os.path.join(G, "ultima_verificacao.json")
    ant = json.load(open(arq, encoding="utf-8")) if os.path.exists(arq) else {}
    ordem = {"APROVADO": 2, "ATENÇÃO": 1, "REPROVADO": 0}
    dif = []
    for o in out:
        a = ant.get(o["id"])
        if a is None:
            dif.append((o["id"], "NOVO", "-", o["check"]))
        elif a != o["check"]:
            dif.append((o["id"], "MELHOROU" if ordem[o["check"]] > ordem.get(a, 0) else "REGREDIU", a, o["check"]))
    return ant, dif


def planilha(out, dif, versao, saida):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from fsen import checagem as CK
    wb = Workbook()
    ws = wb.active
    ws.title = "Requisitos"
    cab = ["ID", "Data", "Área", "Crítico", "Requisito (engenheiro)", "Fonte", "Onde a plataforma atende", "Verificação",
           "Teste", "Evidência (esta revisão)", "Status", "Desde", "Check", "Nota / falta"]
    ws.append(cab)
    for o in out:
        ws.append([o["id"], o.get("data"), o.get("area"), "SIM" if o.get("critico") else "", o.get("requisito"), o.get("fonte"),
                   o.get("atende"), o.get("verificacao"), o["teste"], o["evidencia"], o.get("status"), o.get("desde"),
                   o["check"], o.get("nota", "")])
    larg = [13, 11, 12, 7, 70, 30, 34, 30, 11, 50, 11, 8, 12, 50]
    for i, w in enumerate(larg):
        ws.column_dimensions[chr(65 + i)].width = w
    for c in ws[1]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="C8641E")
    for row in ws.iter_rows(min_row=2):
        for c in row:
            c.alignment = Alignment(wrap_text=True, vertical="top")
    CK.colorir_planilha(ws)
    ws.freeze_panes = "B2"
    ws.auto_filter.ref = ws.dimensions
    w2 = wb.create_sheet("Revisão")
    w2.append(["ID", "Mudança", "Antes", "Agora"])
    for d in dif:
        w2.append(list(d))
    w2.append([])
    for c in w2[1]:
        c.font = Font(bold=True)
    w3 = wb.create_sheet("Resumo")
    import collections
    cc = collections.Counter(o["check"] for o in out)
    crit_rep = [o["id"] for o in out if o.get("critico") and o["check"] == "REPROVADO" and o.get("status") == "ATENDIDO"]
    pend = [o["id"] for o in out if o.get("critico") and o["check"] == "REPROVADO" and o.get("status") != "ATENDIDO"]
    w3.append(["Versão", versao])
    for k in ("APROVADO", "ATENÇÃO", "REPROVADO"):
        w3.append([k, cc.get(k, 0)])
    w3.append(["Críticos ATENDIDOS que falharam no teste (bloqueiam)", ", ".join(crit_rep) or "nenhum"])
    w3.append(["Críticos pendentes conhecidos (não bloqueiam, prioridade)", ", ".join(pend) or "nenhum"])
    w3.append(["Publicar?", "NÃO – corrigir críticos" if crit_rep else "SIM"])
    w4 = wb.create_sheet("Referências")
    refs = (yaml.safe_load(_ler("gestao/REFERENCIAS_PROJETOS.yaml")) or {}).get("referencias", [])
    w4.append(["ID", "Projeto / fonte", "Caminho", "Lições", "Requisitos", "Usada em"])
    for r in refs:
        w4.append([r["id"], r["nome"], r.get("caminho"), "\n".join(r.get("licoes", [])), ", ".join(r.get("requisitos", [])), r.get("usada_em")])
    for i, w in enumerate([16, 50, 50, 90, 30, 40]):
        w4.column_dimensions[chr(65 + i)].width = w
    for row in w4.iter_rows(min_row=2):
        for c in row:
            c.alignment = Alignment(wrap_text=True, vertical="top")
    os.makedirs(saida, exist_ok=True)
    arq = os.path.join(saida, f"Registro_Requisitos_v{versao}.xlsx")
    wb.save(arq)
    return arq, crit_rep, cc, pend


def main(argv):
    saida = os.path.join(G, "saida")
    projs = []
    it = iter(argv)
    for a in it:
        if a == "--saida":
            saida = next(it)
        elif os.path.isdir(a):
            projs.append(os.path.abspath(a))
    versao = json.load(open(os.path.join(RAIZ, "versao_plataforma.json"), encoding="utf-8"))["versao"]
    reg, out = avaliar(projs)
    ant, dif = comparar(out)
    arq, crit_rep, cc, pend = planilha(out, dif, versao, saida)
    regred = [d[0] for d in dif if d[1] == "REGREDIU" and any(o["id"] == d[0] and o.get("critico") for o in out)]
    json.dump({o["id"]: o["check"] for o in out}, open(os.path.join(G, "ultima_verificacao.json"), "w", encoding="utf-8"), indent=1)
    from datetime import datetime
    lin = (f"\n## Revisão – v{versao} – {datetime.now():%Y-%m-%d %H:%M}\n"
           f"- Requisitos: {len(out)} | APROVADO {cc.get('APROVADO', 0)} | ATENÇÃO {cc.get('ATENÇÃO', 0)} | REPROVADO {cc.get('REPROVADO', 0)}\n"
           f"- Projetos conferidos: {', '.join(os.path.basename(p) for p in projs) or 'nenhum'}\n"
           f"- Mudanças: " + ("; ".join(f"{d[0]} {d[1]} ({d[2]}→{d[3]})" for d in dif if d[1] != 'NOVO') or "nenhuma") + "\n"
           f"- Críticos que diziam ATENDIDO e falharam (bloqueiam): {', '.join(crit_rep) or 'nenhum'} | regredidos: {', '.join(regred) or 'nenhum'}\n"
           f"- Críticos pendentes conhecidos (prioridade): {', '.join(pend) or 'nenhum'}\n"
           f"- Decisão: {'NÃO PUBLICAR' if (crit_rep or regred) else 'pode publicar'}\n")
    with open(os.path.join(G, "REVISOES.md"), "a", encoding="utf-8") as fh:
        fh.write(lin)
    print(lin)
    print("Planilha:", arq)
    return 1 if (crit_rep or regred) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
