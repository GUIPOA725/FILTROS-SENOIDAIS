"""Biblioteca COMPARTILHADA de componentes no Drive (REQ-CMP-006, v1.26.0).

Um único lugar para tudo que o engenheiro e os colegas cadastrarem – antes de criar algo novo, PESQUISAR aqui.
  Drive: PLATAFORMA FILTROS SENOIDAIS\\BIBLIOTECA_COMPONENTES
      propostas\\AAAAMMDD_HHMM_<usuário>_<nome>.yaml   → status A_CONFERIR (qualquer colega grava; 1 arquivo por proposta = sem conflito)
      aprovados\\<mesmo arquivo>.yaml                   → status APROVADO (só quem está em autorizados_edicao.txt aprova)
      recusados\\...                                    → com o motivo
  • Componente APROVADO entra no catálogo de medidas de todos (painel 3D/2D, lista) na próxima abertura – sem mexer no código.
  • Componente A_CONFERIR pode ser usado por quem propôs/qualquer um, mas sai marcado "a conferir" (vermelho no 3D) e o projeto
    não fica liberado para cotação (REQ-CMP-002) até o engenheiro aprovar.
Projetos ficam em PROJETOS (por cliente) e painéis aprovados em BIBLIOTECA_PAINEIS – `pesquisar()` procura nos três.
"""
from __future__ import annotations

import datetime as _dt
import glob
import os
import re
import shutil

import yaml

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DRIVE_BASE = r"G:\Drives compartilhados\Engenharia\15 - TEMPLATES-PLANILHA ESTUDOS\PLATAFORMA FILTROS SENOIDAIS"
PASTA = os.path.join(DRIVE_BASE, "BIBLIOTECA_COMPONENTES")
PASTA_LOCAL = os.path.join(os.path.expanduser("~"), ".fsen", "biblioteca_componentes")
GRUPOS = ("capacitores", "contatoras", "seccionadoras_fusivel", "disjuntores", "disjuntores_modulares", "reles", "controladores",
          "ventiladores", "trafos_comando", "outros")
CAMPOS_OBRIG = ("grupo", "nome", "fabricante", "codigo", "fonte")


def _base():
    b = PASTA if os.path.isdir(DRIVE_BASE) else PASTA_LOCAL
    for s in ("propostas", "aprovados", "recusados"):
        try:
            os.makedirs(os.path.join(b, s), exist_ok=True)
        except OSError:
            pass
    return b


def _usuario():
    return (os.environ.get("USERNAME") or os.environ.get("USER") or "?").strip().lower()


def _slug(s):
    return re.sub(r"[^A-Za-z0-9]+", "-", str(s)).strip("-")[:50] or "componente"


def _ler(arq):
    try:
        d = yaml.safe_load(open(arq, encoding="utf-8")) or {}
        d["_arquivo"] = arq
        return d
    except Exception:
        return None


def listar(status=None):
    """Todas as fichas (propostas + aprovados). status: 'A_CONFERIR' | 'APROVADO' | None."""
    b, out = _base(), []
    for sub, st_ in (("aprovados", "APROVADO"), ("propostas", "A_CONFERIR")):
        if status and status != st_:
            continue
        for f in sorted(glob.glob(os.path.join(b, sub, "*.yaml"))):
            d = _ler(f)
            if d:
                d["status"] = st_
                out.append(d)
    return out


def propor(grupo, nome, fabricante, codigo, fonte, medidas=None, dados=None, observacao=""):
    """Grava uma proposta (A_CONFERIR). medidas: dict(L, A, P) em mm ou dict(D, A, terminal). Devolve o arquivo."""
    falt = [k for k, v in (("grupo", grupo), ("nome", nome), ("fabricante", fabricante), ("codigo", codigo), ("fonte", fonte)) if not str(v or "").strip()]
    if falt:
        raise ValueError("Faltou preencher: " + ", ".join(falt) + " (a fonte é o catálogo/site do fabricante de onde saíram os dados)")
    ja = [d for d in pesquisar(codigo) if str(d.get("codigo", "")).strip().lower() == str(codigo).strip().lower()]
    if ja:
        raise ValueError(f"Já existe na biblioteca: {ja[0].get('nome')} ({ja[0].get('status')}) – use o existente em vez de criar outro.")
    ficha = dict(grupo=grupo, nome=str(nome).strip(), fabricante=str(fabricante).strip(), codigo=str(codigo).strip(), fonte=str(fonte).strip(),
                 medidas_mm={k: float(v) for k, v in (medidas or {}).items() if v not in (None, "", 0)}, dados=dados or {},
                 observacao=observacao, proposto_por=_usuario(), proposto_em=f"{_dt.datetime.now():%Y-%m-%d %H:%M}", status="A_CONFERIR")
    arq = os.path.join(_base(), "propostas", f"{_dt.datetime.now():%Y%m%d_%H%M}_{_usuario()}_{_slug(nome)}.yaml")
    yaml.safe_dump(ficha, open(arq, "w", encoding="utf-8"), allow_unicode=True, sort_keys=False)
    try:
        from . import memoria as ME
        ME.registrar_uso("componente", f"proposta: {nome} ({codigo})", arq)
    except Exception:
        pass
    return arq


def pode_aprovar():
    from . import protecao as PR
    return PR.usuario() in PR.autorizados()


def aprovar(arquivo, observacao=""):
    """Só o engenheiro (ou quem ele autorizou em autorizados_edicao.txt). Move a ficha para 'aprovados'."""
    if not pode_aprovar():
        raise PermissionError("Só o engenheiro responsável aprova componentes para a biblioteca de todos.")
    d = _ler(arquivo) or {}
    d.pop("_arquivo", None)
    d.update(status="APROVADO", aprovado_por=_usuario(), aprovado_em=f"{_dt.datetime.now():%Y-%m-%d %H:%M}", obs_aprovacao=observacao)
    dst = os.path.join(_base(), "aprovados", os.path.basename(arquivo))
    yaml.safe_dump(d, open(dst, "w", encoding="utf-8"), allow_unicode=True, sort_keys=False)
    os.remove(arquivo)
    return dst


def recusar(arquivo, motivo):
    if not pode_aprovar():
        raise PermissionError("Só o engenheiro responsável recusa/aprova componentes.")
    d = _ler(arquivo) or {}
    d.pop("_arquivo", None)
    d.update(status="RECUSADO", recusado_por=_usuario(), motivo=motivo)
    dst = os.path.join(_base(), "recusados", os.path.basename(arquivo))
    yaml.safe_dump(d, open(dst, "w", encoding="utf-8"), allow_unicode=True, sort_keys=False)
    os.remove(arquivo)
    return dst


def catalogo_extra():
    """Fichas no formato do dados/dimensoes_componentes.yaml: {grupo: {nome: {L, A, P | D, A, terminal, fonte, conferir}}}.
    APROVADO → conferir False; A_CONFERIR → conferir True (desenhado como 'a conferir')."""
    out = {}
    for d in listar():
        med = dict(d.get("medidas_mm") or {})
        if not med:
            continue
        reg = dict(med, tipo="cilindro" if "D" in med else "caixa", fonte=f"{d.get('fonte')} – biblioteca ({d.get('status')}, {d.get('proposto_por')})",
                   conferir=d.get("status") != "APROVADO", biblioteca=True)
        reg.update({k: v for k, v in (d.get("dados") or {}).items() if k not in reg})
        out.setdefault(d.get("grupo") or "outros", {})[f"{d.get('fabricante')} {d.get('codigo')}"] = reg
    return out


def _catalogo_base():
    itens = []
    for arq in ("dimensoes_componentes.yaml",):
        try:
            cat = yaml.safe_load(open(os.path.join(RAIZ, "dados", arq), encoding="utf-8")) or {}
        except Exception:
            cat = {}
        for g, tab in cat.items():
            if isinstance(tab, dict):
                for nome, v in tab.items():
                    if isinstance(v, dict) and (v.get("fonte") or v.get("L") or v.get("D")):
                        itens.append(dict(grupo=g, nome=nome, codigo=nome, fabricante=nome.split()[0], fonte=v.get("fonte", ""),
                                          medidas_mm={k: v[k] for k in ("L", "A", "P", "D") if k in v},
                                          status="CATÁLOGO DA PLATAFORMA" + (" (a conferir)" if v.get("conferir") else "")))
    try:
        fab = yaml.safe_load(open(os.path.join(RAIZ, "dados", "fabricantes.yaml"), encoding="utf-8")) or {}
        for marca, m in fab.items():
            for chave, v in (m or {}).items():
                if isinstance(v, dict) and v.get("codigo"):
                    itens.append(dict(grupo=chave, nome=f"{marca} – {chave}", codigo=str(v["codigo"]), fabricante=marca, fonte="dados/fabricantes.yaml",
                                      medidas_mm={}, status="CATÁLOGO DA PLATAFORMA" + (" (a conferir)" if v.get("conferir") else "")))
    except Exception:
        pass
    return itens


def pesquisar(texto, incluir_projetos=False):
    """Procura (todas as palavras) no catálogo da plataforma + biblioteca do Drive (+ pastas de projetos e painéis aprovados)."""
    pal = [p for p in re.split(r"\s+", str(texto or "").lower().strip()) if p]
    todos = listar() + _catalogo_base()
    out = [d for d in todos if all(p in " ".join(str(d.get(k, "")) for k in ("grupo", "nome", "fabricante", "codigo", "fonte", "observacao")).lower()
                                   for p in pal)]
    if incluir_projetos and pal:
        for base, rot in ((os.path.join(DRIVE_BASE, "PROJETOS"), "PROJETO"), (os.path.join(DRIVE_BASE, "BIBLIOTECA_PAINEIS"), "PAINEL APROVADO")):
            try:
                for cli in os.listdir(base):
                    pc = os.path.join(base, cli)
                    nomes = [cli] + (os.listdir(pc) if os.path.isdir(pc) else [])
                    for n in nomes:
                        if all(p in (cli + " " + n).lower() for p in pal):
                            out.append(dict(grupo=rot, nome=n, codigo="", fabricante=cli, fonte=os.path.join(pc, n) if n != cli else pc,
                                            medidas_mm={}, status=rot))
            except OSError:
                pass
    return out[:80]


def resumo_txt(max_itens=40):
    """Lista curta para o contexto da IA."""
    it = listar()
    if not it:
        return ""
    return "BIBLIOTECA DE COMPONENTES DO DRIVE (criados pela equipe):\n" + "\n".join(
        f"- [{d.get('status')}] {d.get('grupo')}: {d.get('fabricante')} {d.get('codigo')} – {d.get('nome')} (por {d.get('proposto_por')})"
        for d in it[:max_itens])
