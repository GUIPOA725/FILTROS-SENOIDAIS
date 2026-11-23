"""Comparação do reator projetado com reatores REAIS (REQ-REA-015, v1.26.1).

O engenheiro conferia à mão: recebia o orçamento da Cootrans (L, A, tamanho, peso) e ia à internet ver se batia com os
fabricantes. Aqui a plataforma faz a mesma conferência em todo projeto e ela vira fator de aprovação.
Método (declarado): a energia armazenada E = L·I² dá o porte do reator; a massa de reatores de mesma construção cresce
≈ E^0,75 (lei de escala de magnéticos). A massa de cada referência é levada para a energia do projeto e comparada.
  • dentro de −15 % … +40 % do reator REAL instalado de mesma construção (Cootrans) → APROVADO;
  • mais LEVE que −15 % → ATENÇÃO (núcleo/condutor apertado – conferir saturação e aquecimento);
  • mais pesado que +40 % → ATENÇÃO (custo/espaço – conferir se a folga não ficou exagerada).
Referências de outros fabricantes (classe/condutor/FD diferentes) entram como INFORMAÇÃO.
"""
from __future__ import annotations

import os

import yaml

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARQ = os.path.join(RAIZ, "dados", "reatores_referencia.yaml")
EXP = 0.75
FAIXA = (-15.0, 40.0)


def referencias(tipo=None):
    try:
        refs = yaml.safe_load(open(ARQ, encoding="utf-8")) or []
    except Exception:
        return []
    return [r for r in refs if not tipo or r.get("tipo") == tipo]


def comparar(L_uH, I_A, massa_kg, perdas_W=None, medidas=None, tipo="dessintonizado"):
    """Linhas [referência, dado da referência, massa equivalente no porte do projeto, desvio %, Check]."""
    from . import checagem as CK
    E = L_uH * I_A ** 2
    out = []
    for r in referencias(tipo):
        try:
            Er = float(r["L_uH"]) * float(r["I_A"]) ** 2
            m_eq = float(r["massa_kg"]) * (E / Er) ** EXP
        except Exception:
            continue
        dv = (massa_kg / m_eq - 1) * 100
        if r.get("real_instalado"):
            st = CK.APROVADO if FAIXA[0] <= dv <= FAIXA[1] else CK.ATENCAO
        else:
            st = CK.INFO if hasattr(CK, "INFO") else CK.APROVADO
        out.append(dict(nome=r["nome"], dado=f"{r['L_uH']:g} µH / {r['I_A']:g} A / {r['massa_kg']:g} kg"
                        + (f" / {r['perdas_W']:g} W" if r.get("perdas_W") else "") + (f" / {r['medidas_mm']}" if r.get("medidas_mm") else "")
                        + f" / {r.get('condutor', '')} / classe {r.get('classe', '?')}",
                        massa_eq=m_eq, desvio_pct=dv, status=st, origem=r.get("origem", "")))
    return out


def tabela_md(nome_reator, L_uH, I_A, massa_kg, perdas_W=None, medidas=None, tipo="dessintonizado"):
    from . import checagem as CK
    lin = comparar(L_uH, I_A, massa_kg, perdas_W, medidas, tipo)
    if not lin:
        return []
    md = ["", f"## {nome_reator} × reatores reais (REQ-REA-015)", "",
          f"Projeto da plataforma: {L_uH:.0f} µH / {I_A:.1f} A / {massa_kg:.0f} kg" + (f" / {perdas_W:.0f} W" if perdas_W else "")
          + (f" / {medidas}" if medidas else "") + ".", "",
          "| Referência (L / I / massa / …) | Massa da referência no porte do projeto | Projeto × referência | Check |", "|---|---|---|---|"]
    for x in lin:
        md.append(f"| {x['nome']}: {x['dado']} | {x['massa_eq']:.0f} kg | {x['desvio_pct']:+.0f} % | {CK.texto(x['status'])} |")
    md += ["", f"Critério: massa ∝ (L·I²)^{EXP:g}; aprovado entre {FAIXA[0]:+.0f} % e {FAIXA[1]:+.0f} % do reator real instalado de mesma "
           "construção; outros fabricantes (classe, condutor ou FD diferentes) são informação."]
    return md
