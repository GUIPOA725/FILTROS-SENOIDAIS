"""Conferência obrigatória antes de publicar QUALQUER versão (regra desde a v1.18.0):
todo campo/botão das telas precisa ter dica – help= no próprio widget ou entrada em fsen/ajuda.py (DICAS).
Uso: python validacao/verificar_ajuda.py  → sai com código 1 e lista os campos sem dica."""
import os
import re
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
from fsen.ajuda import DICAS  # noqa: E402

TELAS = ["app.py", "telas_banco.py", "telas_ajuste.py", "telas_conferencia.py", "seletor.py", "fsen/ajuda.py", "telas_ia.py"]
RX = re.compile(r'\.(number_input|text_input|text_area|selectbox|radio|checkbox|file_uploader|slider|multiselect|button|toggle)'
                r'\(\s*"([^"]{2,120})"([^\n]*)')
IGNORAR = {"Salvar", "Adicionar", "Importar", "Perguntar", "Explicar este erro", "Pergunte ao assistente"}


def faltando():
    out = []
    for f in TELAS:
        p = os.path.join(RAIZ, f)
        if not os.path.exists(p):
            continue
        for n, linha in enumerate(open(p, encoding="utf-8"), 1):
            for m in RX.finditer(linha):
                lab = m.group(2).strip()
                if "help=" in m.group(3) or lab in DICAS or lab in IGNORAR or any(k.startswith(lab) for k in DICAS):
                    continue
                out.append(f"{f}:{n}  [{m.group(1)}]  {lab}")
    return out


if __name__ == "__main__":
    f = faltando()
    print(f"{len(DICAS)} dicas cadastradas; {len(f)} campo(s) sem dica")
    for x in f:
        print("  -", x)
    sys.exit(1 if f else 0)
