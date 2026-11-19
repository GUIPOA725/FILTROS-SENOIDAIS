"""Seleção de pastas SEM digitar caminho: botão "📁 Procurar..." (janela do Windows) + navegação por listas."""
import json
import os

import streamlit as st

PREFS = os.path.join(os.path.expanduser("~"), ".fsen", "prefs.json")


def _prefs():
    try:
        return json.load(open(PREFS, encoding="utf-8"))
    except Exception:
        return {}


def lembrar(chave, valor):
    try:
        os.makedirs(os.path.dirname(PREFS), exist_ok=True)
        d = _prefs()
        d[chave] = valor
        json.dump(d, open(PREFS, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    except Exception:
        pass


def lembrado(chave, padrao=None):
    return _prefs().get(chave, padrao)


def janela_windows(inicial=None, titulo="Selecione a pasta"):
    """Abre a janela padrão de seleção de pasta do sistema (o programa roda no próprio computador do usuário)."""
    try:
        import tkinter as tk
        from tkinter import filedialog
        r = tk.Tk()
        r.withdraw()
        r.wm_attributes("-topmost", 1)
        p = filedialog.askdirectory(initialdir=inicial if inicial and os.path.isdir(inicial) else None, title=titulo, parent=r)
        r.destroy()
        return os.path.normpath(p) if p else None
    except Exception:
        return None


def _subpastas(p):
    try:
        return sorted([d for d in os.listdir(p) if os.path.isdir(os.path.join(p, d)) and not d.startswith((".", "__"))], key=str.lower)
    except Exception:
        return []


def seletor_pasta(rotulo, chave, padrao, container=st, ajuda=None, lembrar_escolha=True):
    """Mostra a pasta escolhida + botão Procurar (janela do Windows) + navegação por caixas de seleção. Retorna o caminho."""
    sk = f"_pasta_{chave}"
    if sk not in st.session_state:
        st.session_state[sk] = (lembrado(chave) if lembrar_escolha else None) or padrao
    atual = st.session_state[sk]
    container.markdown(f"**{rotulo}**" + (f"  \n<small>{ajuda}</small>" if ajuda else ""), unsafe_allow_html=True)
    container.code(atual or "(nenhuma)", language=None)
    c1, c2 = container.columns(2)
    if c1.button("📁 Procurar...", key=f"{chave}_proc", help="Abre a janela do Windows para escolher a pasta"):
        p = janela_windows(atual, rotulo)
        if p:
            st.session_state[sk] = p
            if lembrar_escolha:
                lembrar(chave, p)
            st.rerun()
        else:
            container.caption("Janela não abriu (ou foi cancelada) – use a navegação abaixo.")
    nav = c2.toggle("Navegar", key=f"{chave}_nav")
    if nav:
        base = atual if atual and os.path.isdir(atual) else os.path.expanduser("~")
        pai = os.path.dirname(base.rstrip("\\/")) or base
        opcoes = ["⬆ (pasta acima)"] + _subpastas(base)
        esc = container.selectbox("Entrar em", opcoes, index=None, key=f"{chave}_sel", placeholder="escolha uma subpasta…")
        if esc:
            novo = pai if esc.startswith("⬆") else os.path.join(base, esc)
            st.session_state[sk] = novo
            if lembrar_escolha:
                lembrar(chave, novo)
            st.session_state.pop(f"{chave}_sel", None)
            st.rerun()
        if os.name == "nt":
            drives = [f"{l}:\\" for l in "CDEFGHIJ" if os.path.exists(f"{l}:\\")]
            dv = container.selectbox("…ou unidade", drives, index=None, key=f"{chave}_drv", placeholder="C:\\, G:\\ …")
            if dv:
                st.session_state[sk] = dv
                st.session_state.pop(f"{chave}_drv", None)
                st.rerun()
    return st.session_state[sk]
