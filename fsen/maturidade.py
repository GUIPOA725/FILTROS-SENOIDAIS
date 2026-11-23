"""Nível de MATURIDADE dos projetos e do que é reaproveitado deles (REQ-GER-016, v1.27.0).

Pedido do engenheiro (23/11/2026): "criar um nível de pontuação" – projeto só salvo/desenhado; rodado, calculado e verificado;
vendido; testado (TAF); montado e verificado em campo. E: "eu posso esquecer – achar uma forma de fazer isso automaticamente".

  Nível 0 – NÃO USAR em projetos novos (recusado pelo engenheiro, componente fora de linha)
  Nível 1 – Salvo / desenhado (o projeto rodou mas tem item REPROVADO, ou só existe o desenho)
  Nível 2 – Calculado e verificado (projeto rodado sem nenhum REPROVADO nas tabelas com Check)
  Nível 3 – Vendido / fabricado            (evidência: pedido de compra, ordem de produção, nota fiscal)
  Nível 4 – Testado em fábrica (TAF)       (evidência: relatório de TAF/ensaio do fabricante)
  Nível 5 – Instalado e medido em campo    (evidência: comissionamento, medição, termografia)

Regras (as mesmas das escalas de maturidade da indústria – PLM e TRL): os níveis 1 e 2 a plataforma dá SOZINHA ao rodar o
projeto; do 3 em diante só sobe com EVIDÊNCIA – um arquivo colocado na subpasta correspondente de `06_Evidencias` do projeto
(qualquer PDF, foto, planilha ou e-mail). A plataforma relê as pastas sozinha: achou o arquivo, sobe o nível; não achou, o
projeto aparece na lista "sem evidência" da página Biblioteca para o engenheiro responder (vendido? não vendido?). Nível alto
NÃO dispensa a conferência: o módulo/reator reaproveitado é sempre reconferido contra as correntes do local novo.
"""
from __future__ import annotations

import datetime as _dt
import json
import os

NIVEIS = {0: "Não usar em projetos novos", 1: "Salvo / desenhado", 2: "Calculado e verificado", 3: "Vendido / fabricado",
          4: "Testado em fábrica (TAF)", 5: "Instalado e medido em campo"}
PASTA_EVID = "06_Evidencias"
SUBPASTAS = {3: "3_Vendido_Fabricado", 4: "4_TAF_Ensaio_de_fabrica", 5: "5_Campo_Comissionamento_Medicao"}
ARQ = "maturidade.json"
IGNORAR = ("leia-me", "leia_me", "desktop.ini", "thumbs.db")
LEIA_ME = """EVIDÊNCIAS DO PROJETO – nível de maturidade (Plataforma FSEN)

Coloque aqui os documentos que provam em que etapa este projeto chegou. A plataforma lê estas pastas sozinha e sobe o nível:

  3_Vendido_Fabricado              pedido de compra do cliente, ordem de produção, nota fiscal            → nível 3
  4_TAF_Ensaio_de_fabrica          relatório de TAF, ensaios do fabricante (reator, painel)               → nível 4
  5_Campo_Comissionamento_Medicao  relatório de comissionamento, medição de QEE, termografia, fotos       → nível 5

Qualquer arquivo serve (PDF, foto, planilha, e-mail salvo). Sem arquivo, o projeto fica no nível que a plataforma calculou
(1 = salvo com reprovação; 2 = calculado e verificado). Nada sobe sem evidência.
"""


def _evidencias(pasta):
    out = {}
    for nv, sub in SUBPASTAS.items():
        p = os.path.join(pasta, PASTA_EVID, sub)
        try:
            fs = sorted(f for f in os.listdir(p) if os.path.isfile(os.path.join(p, f)) and not f.lower().startswith(IGNORAR)
                        and not f.startswith(("~", ".")))
        except OSError:
            fs = []
        out[nv] = fs
    return out


def _ler(pasta):
    try:
        return json.load(open(os.path.join(pasta, ARQ), encoding="utf-8"))
    except Exception:
        return {}


def avaliar(pasta):
    """Nível atual do projeto da pasta (lê RESUMO.md e as evidências). Não grava nada."""
    reg = _ler(pasta)
    resumo = os.path.join(pasta, "RESUMO.md")
    txt = ""
    try:
        txt = open(resumo, encoding="utf-8").read()
    except OSError:
        pass
    nrep = sum(1 for ln in txt.splitlines() if ln.startswith("|") and "✖ REPROVADO" in ln and not ln.startswith("| Arco elétrico |"))
    if not txt:
        nrep += 0
    senoidal_rep = "**Status:** ❌ REPROVADO" in txt
    nivel = 2 if (txt and nrep == 0 and not senoidal_rep) else 1
    motivo = ("projeto rodado sem reprovação" if nivel == 2 else
              (f"{nrep} item(ns) REPROVADO(S) no resumo" if nrep else ("status REPROVADO" if senoidal_rep else "sem RESUMO.md – só salvo")))
    ev = _evidencias(pasta)
    for nv in (3, 4, 5):
        if ev[nv]:
            nivel = max(nivel, nv)                     # a evidência do mundo real vale mais que o status calculado
            motivo = f"evidência em {SUBPASTAS[nv]}: {ev[nv][0]}" + (f" (+{len(ev[nv]) - 1})" if len(ev[nv]) > 1 else "")
    if reg.get("nao_usar"):
        nivel, motivo = 0, f"marcado NÃO USAR: {reg.get('nao_usar')}"
    return dict(nivel=nivel, nome=NIVEIS[nivel], motivo=motivo, evidencias=ev, reprovados=nrep,
                resposta=reg.get("resposta"), respondido_em=reg.get("respondido_em"), criado_em=reg.get("criado_em"),
                codigo=reg.get("codigo"), tipo=reg.get("tipo"), cliente=reg.get("cliente"))


def iniciar(pasta, codigo="", tipo="", cliente="", log=None):
    """Chamado no fim de cada projeto: cria 06_Evidencias (com LEIA-ME), grava maturidade.json e devolve a avaliação."""
    try:
        for sub in SUBPASTAS.values():
            os.makedirs(os.path.join(pasta, PASTA_EVID, sub), exist_ok=True)
        lm = os.path.join(pasta, PASTA_EVID, "LEIA-ME.txt")
        if not os.path.exists(lm):
            open(lm, "w", encoding="utf-8").write(LEIA_ME)
    except OSError:
        pass
    reg = _ler(pasta)
    reg.setdefault("criado_em", f"{_dt.datetime.now():%Y-%m-%d %H:%M}")
    reg.update(codigo=codigo or reg.get("codigo"), tipo=tipo or reg.get("tipo"), cliente=cliente or reg.get("cliente"))
    av = avaliar(pasta)
    reg.update(nivel=av["nivel"], nome=av["nome"], motivo=av["motivo"], atualizado_em=f"{_dt.datetime.now():%Y-%m-%d %H:%M}")
    try:
        json.dump(reg, open(os.path.join(pasta, ARQ), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    except OSError:
        pass
    if log:
        log(f"   Maturidade do projeto: nível {av['nivel']} – {av['nome']} ({av['motivo']}); evidências em {PASTA_EVID}")
    return av


def responder(pasta, resposta, nao_usar=None):
    """Resposta do engenheiro à pergunta 'foi vendido?' (para a plataforma parar de perguntar) ou marcação NÃO USAR."""
    reg = _ler(pasta)
    reg.update(resposta=resposta, respondido_em=f"{_dt.datetime.now():%Y-%m-%d %H:%M}",
               respondido_por=(os.environ.get("USERNAME") or os.environ.get("USER") or "?").lower())
    if nao_usar is not None:
        reg["nao_usar"] = nao_usar or None
    json.dump(reg, open(os.path.join(pasta, ARQ), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return avaliar(pasta)


def md(av):
    """Bloco markdown para o RESUMO."""
    L = ["", "## Maturidade do projeto (REQ-GER-016)", "",
         f"**Nível {av['nivel']} de 5 – {av['nome']}** ({av['motivo']}).", "",
         "| Nível | Significado | Como sobe |", "|---|---|---|",
         "| 1 | Salvo / desenhado | automático (projeto com item reprovado fica aqui) |",
         "| 2 | Calculado e verificado | automático – projeto rodado sem nenhum REPROVADO |",
         f"| 3 | Vendido / fabricado | arquivo em {PASTA_EVID}/{SUBPASTAS[3]} (pedido de compra, ordem de produção, NF) |",
         f"| 4 | Testado em fábrica (TAF) | arquivo em {PASTA_EVID}/{SUBPASTAS[4]} (relatório de TAF/ensaio) |",
         f"| 5 | Instalado e medido em campo | arquivo em {PASTA_EVID}/{SUBPASTAS[5]} (comissionamento, medição, termografia) |",
         "", "Nada sobe sem evidência. O que for reaproveitado deste projeto (reator, módulo) leva este nível junto e é sempre "
         "reconferido contra as correntes do local novo.", ""]
    return L


def listar(pasta_projetos, max_prof=2):
    """Todos os projetos (pastas com RESUMO.md ou maturidade.json) abaixo de PROJETOS, com o nível atual – para a tela."""
    out = []
    try:
        clientes = sorted(os.listdir(pasta_projetos))
    except OSError:
        return out
    for c in clientes:
        pc = os.path.join(pasta_projetos, c)
        if not os.path.isdir(pc):
            continue
        try:
            subs = sorted(os.listdir(pc))
        except OSError:
            continue
        for s in subs:
            p = os.path.join(pc, s)
            if os.path.isdir(p) and (os.path.exists(os.path.join(p, "RESUMO.md")) or os.path.exists(os.path.join(p, ARQ))):
                av = avaliar(p)
                av.update(pasta=p, cliente=av.get("cliente") or c, projeto=s)
                out.append(av)
    return out


def pendentes(lista, dias=14):
    """Projetos nos níveis 1–2 sem evidência e sem resposta há mais de `dias` – a plataforma PERGUNTA (o engenheiro não precisa lembrar)."""
    hoje = _dt.datetime.now()
    out = []
    for av in lista:
        if av["nivel"] not in (1, 2) or av.get("resposta"):
            continue
        try:
            t0 = _dt.datetime.strptime(av.get("criado_em") or "", "%Y-%m-%d %H:%M")
        except ValueError:
            try:
                t0 = _dt.datetime.fromtimestamp(os.path.getmtime(os.path.join(av["pasta"], "RESUMO.md")))
            except OSError:
                continue
        if (hoje - t0).days >= dias:
            out.append(av)
    return out


def nivel_de_origem(pasta_origem):
    """Nível do projeto de origem de um reator/módulo da biblioteca (None se a pasta não está acessível)."""
    if pasta_origem and os.path.isdir(pasta_origem):
        return avaliar(pasta_origem)["nivel"]
    return None
