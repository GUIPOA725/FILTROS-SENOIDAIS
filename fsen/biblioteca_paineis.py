"""Biblioteca de PAINÉIS APROVADOS – motor de experiência (REQ-GER-008).

Cada projeto grava o arranjo do painel (parâmetros + resumo) em 05_Desenhos/4_Painel_3D/layout_painel.json.
Quando o engenheiro APROVA (botão na tela ou `python -m fsen.biblioteca_paineis aprovar <pasta_projeto> "observação"`),
o layout vai para a biblioteca (Drive: PLATAFORMA FILTROS SENOIDAIS\\BIBLIOTECA_PAINEIS; sem Drive: dados/paineis_aprovados).
O próximo projeto PARTE do último aprovado compatível (mesmo tipo, nº de estágios próximo) – não do zero – e o que o
engenheiro corrigir vira a nova versão aprovada. Assim cada projeto melhora o seguinte e a experiência fica com a equipe.
"""
from __future__ import annotations

import glob
import json
import os
import sys
from datetime import datetime

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DRIVE = r"G:\Drives compartilhados\Engenharia\15 - TEMPLATES-PLANILHA ESTUDOS\PLATAFORMA FILTROS SENOIDAIS\BIBLIOTECA_PAINEIS"
LOCAL = os.path.join(RAIZ, "dados", "paineis_aprovados")

# Regras de partida (antes do 1º aprovado) – vindas dos layouts AGCO/Panatlântica e das regras de montagem:
PADRAO = {
    "folga_componentes_mm": 30,          # entre componente e canaleta/parede
    "folga_capacitores_mm": 20,          # entre latas (ar + aperto do terminal)
    "capacitores_fileiras_prof_max": 2,  # fileiras na profundidade (3ª fileira não dá acesso ao terminal)
    "folga_vertical_min_mm": 40,         # mínimo componente ↔ canaleta (as canaletas já dão o espaço dos cabos)
    "afastamento_lateral_min_mm": 30,    # entre chaves/contatoras vizinhas (ar e ferramenta)
    "canaleta_horizontal_mm": 60,
    "canaleta_vertical_mm": 60,
    "folga_reator_placa_mm": 40,
    "folga_cabos_tras_mm": 70,
    "folga_vertical_reatores_mm": 110,   # entre prateleiras de reatores (ar sobe para o exaustor)
}


def _pastas():
    return [d for d in (DRIVE, LOCAL) if os.path.isdir(d) or d == LOCAL]


def parametros(base=None):
    p = dict(PADRAO)
    if base:
        p.update({k: v for k, v in (base.get("parametros") or {}).items() if k in PADRAO})
        p["_origem"] = f"{base.get('id', '?')} (aprovado em {base.get('aprovado_em', '?')} – {base.get('observacao', '')})"
    else:
        p["_origem"] = "regras de partida (ainda sem painel aprovado na biblioteca)"
    return p


def ultimo_aprovado(tipo="banco", n_estagios=None):
    """Último layout APROVADO compatível (mesmo tipo; nº de estágios mais próximo; mais recente)."""
    cands = []
    for d in _pastas():
        for f in glob.glob(os.path.join(d, "*.json")):
            try:
                j = json.load(open(f, encoding="utf-8"))
            except Exception:
                continue
            if j.get("status") != "APROVADO" or j.get("tipo") != tipo:
                continue
            dn = abs((j.get("n_estagios") or 0) - (n_estagios or 0)) if n_estagios else 0
            cands.append((dn, -datetime.fromisoformat(j.get("aprovado_em", "2000-01-01")).timestamp(), j))
    if not cands:
        return None
    cands.sort(key=lambda x: (x[0], x[1]))
    return cands[0][2]


def salvar_layout(m, pasta, cod, ped):
    os.makedirs(pasta, exist_ok=True)
    j = dict(id=cod, tipo=getattr(ped, "tipo", "banco"), cliente=getattr(ped, "cliente", ""), status="GERADO",
             gerado_em=datetime.now().isoformat(timespec="minutes"), n_estagios=m["n_est"],
             dimensoes_mm=dict(L=m["W"], A=m["H"], P=m["D"]), colunas=[c["largura"] for c in m["colunas"]],
             reator_mm=m["reator"], capacitor_mm=m["cap"], parametros={k: v for k, v in m["params"].items() if not k.startswith("_")},
             partiu_de=m.get("base_aprovada"), verificacoes=m["verificacoes"])
    arq = os.path.join(pasta, "layout_painel.json")
    json.dump(j, open(arq, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return arq


def aprovar(pasta_projeto, observacao="", aprovador="engenheiro", ajustes=None):
    """Aprova o painel do projeto: copia o layout para a biblioteca (Drive, senão local) com status APROVADO.
    `ajustes` (dict) = correções do engenheiro nos parâmetros (ex.: folga_vertical_min_mm=100) – já entram na versão aprovada."""
    fs = glob.glob(os.path.join(pasta_projeto, "**", "layout_painel.json"), recursive=True)
    if not fs:
        raise FileNotFoundError("layout_painel.json não encontrado no projeto")
    j = json.load(open(fs[0], encoding="utf-8"))
    if ajustes:
        j["parametros"].update({k: v for k, v in ajustes.items() if k in PADRAO})
    j.update(status="APROVADO", aprovado_em=datetime.now().isoformat(timespec="minutes"), aprovador=aprovador, observacao=observacao)
    dest = DRIVE if os.path.isdir(os.path.dirname(DRIVE)) else LOCAL
    os.makedirs(dest, exist_ok=True)
    arq = os.path.join(dest, f"{j['tipo']}_{j['id']}_{datetime.now():%Y%m%d_%H%M}.json")
    json.dump(j, open(arq, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return arq


def listar():
    out = []
    for d in _pastas():
        for f in sorted(glob.glob(os.path.join(d, "*.json"))):
            try:
                j = json.load(open(f, encoding="utf-8"))
                out.append((f, j.get("tipo"), j.get("id"), j.get("aprovado_em"), j.get("observacao", "")))
            except Exception:
                pass
    return out


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "aprovar":
        print(aprovar(sys.argv[2], " ".join(sys.argv[3:])))
    else:
        for x in listar():
            print(*x, sep=" | ")
