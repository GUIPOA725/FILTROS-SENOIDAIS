"""Memória do projeto e registro de uso da IA (REQ-IA-012, v1.26.0).

  • MEMÓRIA: gestao/MEMORIA_PROJETO.md – texto leve com o histórico organizado (o que é a plataforma, regras do engenheiro, decisões,
    referências, últimas mudanças). É gerado na publicação (python gestao/gerar_memoria.py) a partir do registro de requisitos e
    vai junto com o programa; uma cópia fica no Drive em MEMORIA_IA. A IA da plataforma lê este texto a cada pergunta/comando –
    assim o colega que nunca viu o projeto conversa com uma IA que já conhece o histórico.
  • REGISTRO DE USO: tudo que cada pessoa pergunta ou manda executar vai para o Drive, em
    MEMORIA_IA\\uso\\AAAA-MM_<usuário>.jsonl (um arquivo por pessoa e mês → sem conflito com 3–4 usando ao mesmo tempo).
    Sem Drive, fica em ~/.fsen/uso e sobe na próxima vez. As dúvidas recentes de TODOS entram no contexto da IA.
A IA não "aprende sozinha": ela relê estes arquivos a cada uso; o engenheiro revisa o registro e transforma em regra/requisito.
"""
from __future__ import annotations

import datetime as _dt
import glob
import json
import os

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DRIVE_BASE = r"G:\Drives compartilhados\Engenharia\15 - TEMPLATES-PLANILHA ESTUDOS\PLATAFORMA FILTROS SENOIDAIS"
PASTA_DRIVE = os.path.join(DRIVE_BASE, "MEMORIA_IA")
PASTA_LOCAL = os.path.join(os.path.expanduser("~"), ".fsen", "uso")
ARQ_MEMORIA = os.path.join(RAIZ, "gestao", "MEMORIA_PROJETO.md")


def _usuario():
    return (os.environ.get("USERNAME") or os.environ.get("USER") or "?").strip().lower()


def _pasta_uso():
    d = os.path.join(PASTA_DRIVE, "uso")
    try:
        if os.path.isdir(DRIVE_BASE):
            os.makedirs(d, exist_ok=True)
            return d, True
    except OSError:
        pass
    os.makedirs(PASTA_LOCAL, exist_ok=True)
    return PASTA_LOCAL, False


def _subir_pendentes():
    """Registros feitos sem Drive sobem quando o Drive volta (acrescenta ao arquivo do mês e apaga o local)."""
    try:
        if not os.path.isdir(DRIVE_BASE):
            return
        dst = os.path.join(PASTA_DRIVE, "uso")
        os.makedirs(dst, exist_ok=True)
        for f in glob.glob(os.path.join(PASTA_LOCAL, "*.jsonl")):
            with open(os.path.join(dst, os.path.basename(f)), "a", encoding="utf-8") as fh:
                fh.write(open(f, encoding="utf-8").read())
            os.remove(f)
    except OSError:
        pass


def registrar_uso(tipo, pedido, resposta="", extra=None):
    """tipo: pergunta | comando | execucao | erro | alteracao_codigo | componente. Nunca levanta exceção."""
    try:
        _subir_pendentes()
        d, _ = _pasta_uso()
        reg = dict(quando=f"{_dt.datetime.now():%Y-%m-%d %H:%M:%S}", usuario=_usuario(), tipo=tipo, pedido=str(pedido)[:4000],
                   resposta=str(resposta)[:6000])
        if extra:
            reg["extra"] = extra
        try:
            reg["versao"] = json.load(open(os.path.join(RAIZ, "versao_plataforma.json"), encoding="utf-8")).get("versao")
        except Exception:
            pass
        with open(os.path.join(d, f"{_dt.datetime.now():%Y-%m}_{_usuario()}.jsonl"), "a", encoding="utf-8") as fh:
            fh.write(json.dumps(reg, ensure_ascii=False, default=str) + "\n")
        return True
    except Exception:
        return False


def uso_recente(n=25, tipos=("pergunta", "comando", "execucao", "erro")):
    """Últimos registros de TODOS os usuários (mais novos primeiro)."""
    regs = []
    for d in (os.path.join(PASTA_DRIVE, "uso"), PASTA_LOCAL):
        for f in sorted(glob.glob(os.path.join(d, "*.jsonl")), reverse=True)[:12]:
            try:
                for ln in open(f, encoding="utf-8"):
                    j = json.loads(ln)
                    if j.get("tipo") in tipos:
                        regs.append(j)
            except (OSError, ValueError):
                continue
    regs.sort(key=lambda j: j.get("quando", ""), reverse=True)
    return regs[:n]


def memoria_texto(max_chars=42000):
    """Memória do projeto: a do Drive (MEMORIA_IA\\MEMORIA_PROJETO.md) se for mais nova; senão a que veio com o programa."""
    cands = [os.path.join(PASTA_DRIVE, "MEMORIA_PROJETO.md"), ARQ_MEMORIA]
    cands = [c for c in cands if os.path.exists(c)]
    if not cands:
        return ""
    arq = max(cands, key=os.path.getmtime)
    try:
        return open(arq, encoding="utf-8").read()[:max_chars]
    except OSError:
        return ""


def contexto_ia(max_chars=46000):
    """Texto para o prompt da IA: memória do projeto + o que os colegas perguntaram/executaram por último."""
    partes = []
    m = memoria_texto(max_chars - 3500)
    if m:
        partes.append("MEMÓRIA DO PROJETO (histórico, regras e decisões do engenheiro responsável):\n" + m)
    rec = uso_recente(15)
    if rec:
        partes.append("USO RECENTE DA EQUIPE (dúvidas e execuções – mais novo primeiro):\n" + "\n".join(
            f"- {r.get('quando', '')[:16]} {r.get('usuario')}: [{r.get('tipo')}] {str(r.get('pedido'))[:160]} → {str(r.get('resposta'))[:160]}"
            for r in rec))
    return "\n\n".join(partes)[:max_chars]
