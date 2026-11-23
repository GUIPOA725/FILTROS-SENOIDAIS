"""Proteção do código e atualização (REQ-GER-012, v1.26.0).

Regra do engenheiro: só ele edita o código; colegas só com autorização dele. 3–4 pessoas usam ao mesmo tempo.
  • ATUALIZAÇÃO: o ABRIR_FSEN.bat copia a versão do Drive (PROGRAMAS\\FSEN_v1.7.1) para o computador a CADA abertura; com a
    plataforma aberta, `nova_versao()` avisa quando o Drive tem versão mais nova (fechar e abrir para atualizar).
  • PROTEÇÃO: `manifesto_codigo.json` (gerado na publicação) guarda o SHA-256 de cada arquivo de código. `verificar()` compara a
    cópia local; arquivo alterado por quem NÃO está em PROGRAMAS\\autorizados_edicao.txt → aviso na tela + som no alto-falante +
    arquivo oficial restaurado do Drive + registro no Drive (quem, quando, qual arquivo).
  • O bloqueio de verdade é a permissão do Drive: a pasta PROGRAMAS deve ficar só leitura para os colegas (o engenheiro configura).
Uso na publicação:  python -m fsen.protecao gerar
"""
from __future__ import annotations

import getpass
import hashlib
import json
import os
import shutil
import sys
import threading
import time

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DRIVE_BASE = r"G:\Drives compartilhados\Engenharia\15 - TEMPLATES-PLANILHA ESTUDOS\PLATAFORMA FILTROS SENOIDAIS"
ARQ_MANIFESTO = "manifesto_codigo.json"
EXT_CODIGO = (".py", ".bat")
IGNORAR_DIRS = {"__pycache__", "saidas", "saida", ".git", "exemplos", "terceiros"}
AUTORIZADOS_PADRAO = {"guila"}               # usuário Windows do engenheiro (Guilherme)


def usuario():
    try:
        return (os.environ.get("USERNAME") or getpass.getuser() or "?").strip().lower()
    except Exception:
        return "?"


def origem_drive():
    """Pasta oficial do programa no Drive (de onde o ABRIR_FSEN.bat copia)."""
    o = os.environ.get("FSEN_ORIGEM") or os.path.join(DRIVE_BASE, "PROGRAMAS", "FSEN_v1.7.1")
    return o.rstrip("\\/")


def _sha(arq):
    h = hashlib.sha256()
    with open(arq, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 16), b""):
            h.update(b)
    return h.hexdigest()


def arquivos_codigo(raiz=RAIZ):
    out = []
    for d, dirs, fs in os.walk(raiz):
        dirs[:] = [x for x in dirs if x not in IGNORAR_DIRS and not x.startswith(".")]
        for f in fs:
            if f.lower().endswith(EXT_CODIGO):
                out.append(os.path.relpath(os.path.join(d, f), raiz).replace("\\", "/"))
    return sorted(out)


def gerar_manifesto(raiz=RAIZ):
    try:
        ver = json.load(open(os.path.join(raiz, "versao_plataforma.json"), encoding="utf-8")).get("versao", "?")
    except Exception:
        ver = "?"
    m = dict(versao=ver, gerado_em=time.strftime("%Y-%m-%d %H:%M"), arquivos={a: _sha(os.path.join(raiz, a)) for a in arquivos_codigo(raiz)})
    json.dump(m, open(os.path.join(raiz, ARQ_MANIFESTO), "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    return m


def _manifesto(raiz):
    try:
        return json.load(open(os.path.join(raiz, ARQ_MANIFESTO), encoding="utf-8"))
    except Exception:
        return None


def autorizados():
    """Usuários Windows autorizados a editar o código: PROGRAMAS\\autorizados_edicao.txt no Drive (um por linha) + o engenheiro."""
    aut = set(AUTORIZADOS_PADRAO)
    try:
        arq = os.path.join(os.path.dirname(origem_drive()), "autorizados_edicao.txt")
        for ln in open(arq, encoding="utf-8"):
            ln = ln.split("#")[0].strip().lower()
            if ln:
                aut.add(ln)
    except OSError:
        pass
    return aut


def nova_versao():
    """Versão do Drive, se for diferente da que está rodando (None = igual ou Drive fora do ar)."""
    try:
        vd = json.load(open(os.path.join(origem_drive(), "versao_plataforma.json"), encoding="utf-8")).get("versao")
        vl = json.load(open(os.path.join(RAIZ, "versao_plataforma.json"), encoding="utf-8")).get("versao")
        return vd if vd and vd != vl else None
    except Exception:
        return None


def alarme(vezes=6):
    """Som no alto-falante (Windows) – sem travar a tela."""
    def _toca():
        try:
            import winsound
            for _ in range(vezes):
                winsound.Beep(1400, 350)
                winsound.Beep(900, 350)
        except Exception:
            try:
                sys.stdout.write("\a" * vezes)
                sys.stdout.flush()
            except Exception:
                pass
    threading.Thread(target=_toca, daemon=True).start()


def _registrar(alterados, restaurados):
    try:
        from . import memoria as ME
        ME.registrar_uso("alteracao_codigo", "tentativa de editar o código sem autorização",
                         f"alterados: {', '.join(alterados)} | restaurados: {', '.join(restaurados) or 'nenhum'}")
    except Exception:
        pass


def verificar(raiz=RAIZ, restaurar=True):
    """Compara a cópia local com o manifesto. Devolve dict(alterados, restaurados, autorizado, usuario, sem_manifesto)."""
    r = dict(alterados=[], restaurados=[], autorizado=usuario() in autorizados(), usuario=usuario(), sem_manifesto=False)
    m = _manifesto(raiz)
    if not m:
        r["sem_manifesto"] = True
        return r
    md = _manifesto(origem_drive())
    if md and md.get("versao") != m.get("versao"):
        return r                                    # Drive já tem outra versão: é atualização pendente, não alteração indevida
    for rel, h in m["arquivos"].items():
        loc = os.path.join(raiz, rel)
        try:
            ok = os.path.exists(loc) and _sha(loc) == h
        except OSError:
            ok = True
        if not ok:
            r["alterados"].append(rel)
    extras = [a for a in arquivos_codigo(raiz) if a not in m["arquivos"]]
    r["alterados"] += [a + " (arquivo novo)" for a in extras]
    if r["alterados"] and not r["autorizado"]:
        if restaurar:
            for rel in list(r["alterados"]):
                rel0 = rel.replace(" (arquivo novo)", "")
                src, dst = os.path.join(origem_drive(), rel0), os.path.join(raiz, rel0)
                try:
                    if rel.endswith("(arquivo novo)"):
                        os.replace(dst, dst + ".bloqueado")
                        r["restaurados"].append(rel0 + " (removido)")
                    elif os.path.exists(src) and _sha(src) == m["arquivos"].get(rel0):
                        shutil.copy2(src, dst)
                        r["restaurados"].append(rel0)
                except OSError:
                    pass
        _registrar(r["alterados"], r["restaurados"])
    return r


def tela(st):
    """Chamar no topo do app: avisa versão nova e bloqueia a tela (com som) se o código foi alterado sem autorização.
    A conferência roda no máximo a cada 60 s (leve: ~100 arquivos pequenos)."""
    agora = time.time()
    ss = st.session_state
    if agora - ss.get("_prot_t", 0) > 60:
        ss["_prot_t"] = agora
        ss["_prot_r"] = verificar()
        ss["_prot_nv"] = nova_versao()
        if ss["_prot_r"]["alterados"] and not ss["_prot_r"]["autorizado"]:
            ss["_prot_bloq"] = ss["_prot_r"]                     # fica bloqueado até fechar e abrir (o módulo alterado já estava na memória)
            alarme()
    r, nv = ss.get("_prot_bloq") or ss.get("_prot_r") or {}, ss.get("_prot_nv")
    if nv:
        st.warning(f"🔄 Há uma versão nova da plataforma no Drive (v{nv}). Feche e abra de novo pelo atalho **FSEN Filtros** para atualizar.")
    if r.get("alterados") and not r.get("autorizado"):
        st.error("## ⛔ VOCÊ NÃO PODE EDITAR O CÓDIGO DA PLATAFORMA\n\n"
                 f"Usuário **{r.get('usuario')}** – foram encontrados arquivos de programa alterados neste computador:\n\n"
                 + "\n".join(f"- `{a}`" for a in r["alterados"][:15]) + "\n\n"
                 "Só o engenheiro responsável (Guilherme) altera o código. A versão oficial foi **restaurada do Drive** "
                 f"({len(r.get('restaurados') or [])} arquivo(s)) e a tentativa ficou **registrada**. "
                 "Precisa de uma mudança? Peça a ele – ou escreva o pedido no **🤖 Assistente IA**, que fica salvo para ele ver.\n\n"
                 "Feche e abra a plataforma para continuar.")
        st.stop()
    elif r.get("alterados") and r.get("autorizado"):
        st.sidebar.caption(f"🔧 Código local diferente do publicado ({len(r['alterados'])} arquivo(s)) – usuário autorizado: {r.get('usuario')}.")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "gerar":
        m = gerar_manifesto()
        print(f"manifesto v{m['versao']}: {len(m['arquivos'])} arquivos")
    else:
        print(json.dumps(verificar(restaurar=False), ensure_ascii=False, indent=1))
