"""Dados do inversor retirados do MANUAL COMPLETO do fabricante – v1.33.0 (REQ-INV-010).

Engenheiro (26/11/2026): "vc precisa abrir o manual sempre do inversor do fabricante o completo e pegar as informações para
essa tomada de decisão ... casar se é o mesmo que o cliente passou ... informar que tal dado foi retirado do manual tal no
link tal pasta tal ... isso tem que estar no código".

Fonte: dados/inversores_manuais.yaml (um bloco por família, com documento, revisão, página, link e o que foi retirado).
  • identificar(modelo) → família, frame, IN pelo código do modelo, fatores de derating pela fs mínima;
  • fator_fs(info, fs_khz) → derating na fs fixada (interpolação linear entre pontos do manual);
  • conferencia(ped) → casa o modelo/corrente informados pelo cliente com o manual;
  • gerar(ped, fs, pasta, cod) → 01_Engenharia/7_Manuais_Tecnicos/Inversor_Manual_<cod>.md + .xlsx (rastreabilidade).
Sem cadastro: devolve None e a verificação fica em ATENÇÃO pedindo o cadastro do manual.
"""
from __future__ import annotations

import os
import re

import yaml

_ARQ = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dados", "inversores_manuais.yaml")
_CACHE = None


def _base():
    global _CACHE
    if _CACHE is None:
        try:
            with open(_ARQ, encoding="utf-8") as f:
                _CACHE = (yaml.safe_load(f) or {}).get("familias", {}) or {}
        except OSError:
            _CACHE = {}
    return _CACHE


def _in_do_codigo(fam, modelo):
    m = re.search(fam.get("regex_in", r"(\d+)A(\d?)"), modelo)
    if not m:
        return None
    inteiro, dec = m.group(1), (m.group(2) or "")
    return float(f"{int(inteiro)}.{dec}") if dec else float(inteiro)


def identificar(modelo):
    """Procura o modelo do inversor no cadastro de manuais. None se a família não está cadastrada."""
    mod = (modelo or "").upper().replace(" ", "")
    for nome, fam in _base().items():
        if re.search(fam.get("regex_modelo", "$^"), mod):
            i_n = _in_do_codigo(fam, mod)
            fr = next((f for f in fam.get("frames", []) if i_n is not None and f["de"] - 1e-6 <= i_n <= f["ate"] + 1e-6), None)
            fsen = (fam.get("filtro_senoidal_fabricante") or {}).get(f"{i_n:g}" if i_n else "", None)
            return dict(familia=nome, fabricante=fam.get("fabricante", ""), modelo=modelo, i_n=i_n,
                        frame=(fr or {}).get("frame"), derating={float(k): float(v) for k, v in ((fr or {}).get("derating") or {}).items()},
                        nota_frame=(fr or {}).get("nota", ""), fontes=fam.get("fontes", []), parametros=fam.get("parametros", ""),
                        status=fam.get("status", ""), pendente=fam.get("pendente", ""), consultado_em=fam.get("consultado_em", ""),
                        filtro_fabricante=fsen)
    return None


def fator_fs(info, fs_khz):
    """Derating na frequência MÍNIMA de chaveamento fixada (97.02 no ABB). Interpolação linear entre os pontos do manual;
    acima do último ponto tabelado → None (o manual não permite / não informa)."""
    tab = sorted((info or {}).get("derating", {}).items())
    if not tab:
        return None
    f = float(fs_khz)
    if f <= tab[0][0]:
        return tab[0][1]
    for (a, ka), (b, kb) in zip(tab, tab[1:]):
        if a <= f <= b:
            return ka + (kb - ka) * (f - a) / (b - a)
    return None


def sugerir_modelo(info, fs_khz, i_necessaria):
    """NÃO usado nos relatórios (REQ-GER-020: equipamento do cliente é fixo). Menor modelo da MESMA família (pelos limites de faixa dos frames do manual) que entrega i_necessaria na fs."""
    if not info:
        return None
    fam = _base().get(info["familia"], {})
    cands = []
    for fr in fam.get("frames", []):
        for i_n in sorted({float(fr["de"]), float(fr["ate"])}):
            k = fator_fs({"derating": {float(a): float(b) for a, b in (fr.get("derating") or {}).items()}}, fs_khz)
            if k is not None and len(fr.get("derating") or {}) > 1 and k * i_n >= i_necessaria - 0.5:
                cands.append((i_n, fr["frame"], k))
    return min(cands) if cands else None


def texto_fonte(info, curto=False):
    if not info or not info.get("fontes"):
        return "manual do inversor NÃO cadastrado"
    f0 = info["fontes"][0]
    if curto:
        return f"{f0['titulo']} {f0['codigo']} rev. {f0['revisao']}, {f0['paginas']}"
    return "; ".join(f"{f['titulo']} {f['codigo']} rev. {f['revisao']} – {f['paginas']} – {f['link']}" for f in info["fontes"])


def conferencia(ped):
    """Casa o que o cliente informou (modelo e corrente) com o manual. Devolve (ok, texto, info)."""
    modelo = getattr(ped, "inversor", None) or (ped.get("inversor") if isinstance(ped, dict) else "")
    i_cli = float((getattr(ped, "inversor_corrente_a", None) if not isinstance(ped, dict) else ped.get("inversor_corrente_a")) or 0)
    info = identificar(modelo)
    if not info:
        return False, (f"Inversor '{modelo or '-'}' sem manual cadastrado em dados/inversores_manuais.yaml – baixar o manual de "
                       "hardware COMPLETO do fabricante e cadastrar documento, revisão, página e link (derating pela fs, IN, sobrecarga)"), None
    if info["i_n"] and i_cli and abs(i_cli - info["i_n"]) > 0.5:
        return False, (f"Corrente informada {i_cli:g} A ≠ IN do manual {info['i_n']:g} A para {modelo} ({texto_fonte(info, True)}) – "
                       "conferir o modelo com o cliente"), info
    return True, f"{modelo}: frame {info['frame']}, IN {info['i_n']:g} A – {texto_fonte(info, True)}", info


def gerar(ped, fs_hz, pasta, cod, i_necessaria=None, log=print):
    """Relatório de rastreabilidade do inversor (md + xlsx) na pasta do projeto."""
    ok, txt, info = conferencia(ped)
    os.makedirs(pasta, exist_ok=True)
    fs_k = float(fs_hz) / 1000
    k = fator_fs(info, fs_k) if info else None
    i_n = (info or {}).get("i_n") or float(getattr(ped, "inversor_corrente_a", 0) or 0)
    i_disp = (k * i_n) if (k is not None and i_n) else None
    L = [f"# Inversor – dados do manual do fabricante ({cod})", "",
         f"Inversor informado pelo cliente: **{getattr(ped, 'inversor', '') or '-'}** – {getattr(ped, 'inversor_corrente_a', 0) or '-'} A",
         f"Conferência com o manual: **{'OK' if ok else 'ATENÇÃO'}** – {txt}", ""]
    if info:
        L += [f"- Família: {info['familia']} – frame **{info['frame'] or '?'}** – IN pelo código do modelo: {info['i_n']:g} A",
              f"- Frequência de chaveamento fixada no projeto: **{fs_k:g} kHz** (mínima = referência)",
              f"- Derating pela fs mínima (tabela do manual): " + ", ".join(f"{a:g} kHz → {b:g}" for a, b in sorted(info["derating"].items())),
              f"- Fator na fs de projeto: **{k:.3f}**" if k is not None else "- Fator na fs de projeto: **NÃO tabelado pelo fabricante – não usar esta fs**",
              (f"- Corrente do inversor nesta fs pelo manual: {i_disp:.0f} A – INFORMATIVO: inversor, motor e cabo do cliente são "
               "fixos e a capacidade do inversor não é avaliada pela Electric (REQ-GER-020); o filtro é projetado para o equipamento especificado")
              if i_disp else "",
              (f"- Filtro senoidal do próprio fabricante para este modelo: {info['filtro_fabricante']['tipo']}, I cont. máx. "
               f"{info['filtro_fabricante']['i_cont_max_a']:g} A (referência de mercado)") if info.get("filtro_fabricante") else "",
              f"- Parâmetros: {info['parametros']}", f"- Status do cadastro: {info['status']} (consultado em {info['consultado_em']})",
              (f"- Pendente: {info['pendente']}" if info.get("pendente") else ""), "", "## Fontes (documento, revisão, página, link)"]
        for f in info["fontes"]:
            L += [f"- **{f['titulo']}** – {f['codigo']} rev. {f['revisao']} – {f['paginas']}", f"  - Link: {f['link']}",
                  f"  - Retirado: {f['retirado']}"]
    arq = os.path.join(pasta, f"Inversor_Manual_{cod}.md")
    with open(arq, "w", encoding="utf-8") as fh:
        fh.write("\n".join(x for x in L if x is not None) + "\n")
    try:
        from openpyxl import Workbook
        wb = Workbook()
        ws = wb.active
        ws.title = "Inversor"
        ws.append(["Item", "Valor", "Fonte (documento, rev., página)", "Link", "Check"])
        fonte = texto_fonte(info, True) if info else "-"
        link = info["fontes"][0]["link"] if info and info.get("fontes") else ""
        ws.append(["Modelo informado", getattr(ped, "inversor", ""), "pedido do cliente", "", "OK" if ok else "ATENÇÃO"])
        if info:
            ws.append(["Frame / IN do manual", f"{info['frame']} / {info['i_n']:g} A", fonte, link, "OK" if ok else "ATENÇÃO"])
            ws.append(["fs fixada (97.01 = 97.02)", f"{fs_k:g} kHz", "projeto", "", ""])
            ws.append(["Fator de derating na fs (informativo)", f"{k:.3f}" if k is not None else "não tabelado", fonte, link, "INFO"])
            ws.append(["Corrente do inversor na fs (informativo – equipamento do cliente, não avaliado)",
                       f"{i_disp:.0f} A" if i_disp else "-", fonte, link, "INFO"])
            if info.get("filtro_fabricante"):
                ws.append(["Filtro senoidal do fabricante (I cont. máx.)", f"{info['filtro_fabricante']['i_cont_max_a']:g} A",
                           (info["fontes"][-1]["codigo"] + " rev. " + info["fontes"][-1]["revisao"]), info["fontes"][-1]["link"], "referência"])
            for f in info["fontes"]:
                ws.append(["Fonte", f["retirado"], f"{f['titulo']} {f['codigo']} rev. {f['revisao']} – {f['paginas']}", f["link"], ""])
        for col, w in zip("ABCDE", (34, 60, 60, 60, 12)):
            ws.column_dimensions[col].width = w
        wb.save(os.path.join(pasta, f"Inversor_Manual_{cod}.xlsx"))
    except Exception as e:
        log(f"   Inversor: planilha não gerada ({e})")
    log(f"   Inversor – manual do fabricante: {os.path.basename(arq)} ({'OK' if ok else 'ATENÇÃO'})")
    return dict(ok=ok, texto=txt, info=info, fator=k, i_disp=i_disp, arquivo=arq)
