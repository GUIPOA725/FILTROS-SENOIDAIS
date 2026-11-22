"""Biblioteca de referências (v1.23.1): copia os documentos de um projeto antigo (pastas profundas do Drive) para uma
pasta LOCAL rasa, com o caminho original no nome do arquivo – para a IA ler projetos reais (CVI, PLASBIL, Pirelli, AGCO…)
sem ninguém precisar mover nada no Drive. Não copia vídeo nem arquivo muito grande; não altera o original.
"""
from __future__ import annotations

import os
import re
import shutil

PADRAO_DESTINO = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "FSEN", "referencias")
EXTENSOES = (".pdf", ".docx", ".doc", ".xlsx", ".xls", ".xlsm", ".csv", ".txt", ".eml", ".msg", ".dxf", ".dwg", ".stp", ".step",
             ".jpg", ".jpeg", ".png", ".rpt", ".prj", ".acp", ".atp", ".pl4", ".md", ".json", ".zip", ".rar")
MAX_MB = 60


def _nome_plano(rel):
    s = re.sub(r"[\\/]+", "__", rel)
    s = re.sub(r'[<>:"|?*]', "_", s)
    if len(s) > 180:
        base, ext = os.path.splitext(s)
        s = base[:120] + "…" + base[-40:] + ext
    return s


def copiar(origem, nome=None, destino_raiz=PADRAO_DESTINO, max_mb=MAX_MB, fotos=True, log=print):
    """Copia (achatado) os documentos de `origem` para destino_raiz/<nome>. Devolve dict(pasta, n, mb, pulados)."""
    origem = os.path.normpath(origem)
    if not os.path.isdir(origem):
        raise FileNotFoundError(origem)
    nome = nome or re.sub(r"[^\w\- ]+", "_", os.path.basename(origem))[:60]
    dst = os.path.join(destino_raiz, nome)
    os.makedirs(dst, exist_ok=True)
    n, tot, pul = 0, 0, []
    lista = []
    for raiz, _dirs, fs in os.walk(origem):
        for f in fs:
            a = os.path.join(raiz, f)
            ext = os.path.splitext(f)[1].lower()
            if ext not in EXTENSOES or (not fotos and ext in (".jpg", ".jpeg", ".png")):
                continue
            try:
                mb = os.path.getsize(a) / 1e6
            except OSError:
                continue
            rel = os.path.relpath(a, origem)
            if mb > max_mb:
                pul.append(f"{rel} ({mb:.0f} MB)")
                continue
            alvo = os.path.join(dst, _nome_plano(rel))
            try:
                if not os.path.exists(alvo) or os.path.getsize(alvo) != os.path.getsize(a):
                    shutil.copy2(a, alvo)
                n += 1
                tot += mb
                lista.append(f"{_nome_plano(rel)}\t{rel}\t{mb:.2f}")
            except OSError as ex:
                pul.append(f"{rel} ({type(ex).__name__})")
    with open(os.path.join(dst, "_INDICE_ORIGEM.txt"), "w", encoding="utf-8") as fh:
        fh.write(f"Origem: {origem}\n\n" + "\n".join(lista) + ("\n\nPulados:\n" + "\n".join(pul) if pul else ""))
    log(f"Biblioteca: {n} arquivo(s), {tot:.0f} MB copiados para {dst}" + (f" – {len(pul)} pulado(s)" if pul else ""))
    return dict(pasta=dst, n=n, mb=round(tot, 1), pulados=pul)


def limpar(nome=None, destino_raiz=PADRAO_DESTINO):
    """Apaga a cópia local (libera espaço no notebook)."""
    alvo = os.path.join(destino_raiz, nome) if nome else destino_raiz
    if os.path.isdir(alvo):
        shutil.rmtree(alvo)
        return True
    return False


def tela(st, onde=None):
    """Expander da biblioteca (sidebar do app e topo das telas)."""
    box = (onde or st).expander("📚 Biblioteca de referências (projetos antigos)", expanded=False)
    with box:
        st.caption("Copia só os documentos de uma pasta de projeto antigo (mesmo bem funda no Drive) para uma pasta local, "
                   "para a IA estudar. O original não é alterado; fotos, vídeos e arquivos > 25 MB ficam de fora.")
        src = st.text_input("Pasta do projeto antigo", key="ref_src")
        nome = st.text_input("Nome curto (ex.: CVI_sintonizado)", key="ref_nome")
        if st.button("Copiar para a biblioteca", key="ref_btn") and src.strip():
            try:
                r = copiar(src.strip().strip('"'), nome.strip() or None, max_mb=25, fotos=False, log=lambda *a: None)
                st.success(f"{r['n']} arquivo(s), {r['mb']} MB → {r['pasta']}" + (f" ({len(r['pulados'])} pulados)" if r["pulados"] else ""))
            except Exception as ex:
                st.error(f"Não copiou: {type(ex).__name__}: {ex}")
        if st.button("Apagar as cópias locais (liberar espaço)", key="ref_limpar"):
            st.info("Cópias apagadas." if limpar() else "Nada para apagar.")
