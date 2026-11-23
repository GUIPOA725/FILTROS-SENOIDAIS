"""Biblioteca de REATORES PADRÃO (REQ-REA-014, v1.26.3).

Pedido do engenheiro (22/11/2026): não projetar um reator novo a cada projeto. Os reatores padrão (estágios de 12,5 – 25 – 50 – 75 –
100 kvar; só muda a tensão) ficam MODELADOS, SALVOS e CONFIRMADOS; em cada projeto a plataforma só confere se o reator padrão
atende as correntes daquele caso. Casos diferentes também ficam salvos – a biblioteca cresce e os projetos saem mais rápido.

  Drive: PLATAFORMA FILTROS SENOIDAIS\\BIBLIOTECA_REATORES
      propostas\\<chave>_<data>_<usuário>.json   → A_CONFERIR (gravado automaticamente a cada reator projetado)
      aprovados\\<mesmo arquivo>.json             → APROVADO (só o engenheiro / autorizados_edicao.txt)
      recusados\\…
  • No projeto: `buscar()` procura um reator APROVADO da mesma família (tipo, tensão, frequência, FD/ordem, kvar do estágio,
    capacitor associado, condutor, classe) cuja indutância bate (±1 %) e cujos requisitos de projeto COBREM os do caso
    (corrente térmica, pico, saturação, linearidade, cada harmônica). Achou → usa o modelo salvo (não reprojeta) e mostra a
    tabela de verificação. Não achou → projeta, e o novo fica como proposta para o engenheiro aprovar.
  • Só reatores APROVADOS são reutilizados (regra do engenheiro: "ter eles modelados, salvos e depois do confirma").
"""
from __future__ import annotations

import datetime as _dt
import glob
import json
import os
import re

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DRIVE_BASE = r"G:\Drives compartilhados\Engenharia\15 - TEMPLATES-PLANILHA ESTUDOS\PLATAFORMA FILTROS SENOIDAIS"
PASTA_LOCAL = os.path.join(os.path.expanduser("~"), ".fsen", "biblioteca_reatores")
TOL_L_PCT = 1.0
CAMPOS_REQ = ("In", "Ipk", "Isat", "Ilin", "Iovl", "I1")          # o reator da biblioteca tem que ter sido projetado para ≥ estes


def _base():
    b = os.environ.get("FSEN_BIB_REATORES") or (os.path.join(DRIVE_BASE, "BIBLIOTECA_REATORES") if os.path.isdir(DRIVE_BASE) else PASTA_LOCAL)
    for s in ("propostas", "aprovados", "recusados"):
        try:
            os.makedirs(os.path.join(b, s), exist_ok=True)
        except OSError:
            pass
    return b


def _usuario():
    return (os.environ.get("USERNAME") or os.environ.get("USER") or "?").strip().lower()


def _json_default(o):
    try:
        import numpy as np
        if isinstance(o, np.ndarray):
            return o.tolist()
        if isinstance(o, (np.floating, np.integer)):
            return o.item()
    except Exception:
        pass
    return str(o)


def familia(ped, e):
    """O que define a FAMÍLIA do reator padrão (tem que ser igual)."""
    sint = ped.tipo == "sintonizado"
    return dict(tipo=ped.tipo, tensao_v=float(ped.tensao_v), freq_hz=float(ped.freq_hz),
                sintonia=(f"H{e.get('ordem'):g} Nr{e['nr']:.2f}" if sint else f"FD{e['p_pct']:.2f}"),
                kvar_estagio=float(e["Q_alvo"]), capacitor=[int(e["cap"][0]), float(e["cap"][1]), float(e["cap"][2])],
                condutor=str(ped.condutor), classe=str(ped.classe), monofasico=bool(getattr(ped, "monofasico", False)))


def _slug(f, e):
    s = f"{f['tipo'][:4]}_{f['tensao_v']:g}V_{f['sintonia']}_{f['kvar_estagio']:g}kvar_{e['L_uH']:.0f}uH_{e['requisitos']['In']:.0f}A"
    return re.sub(r"[^A-Za-z0-9_,.-]+", "-", s.replace(" ", "-"))


def propor(ped, e, d, projeto=""):
    """Grava o reator projetado como proposta (A_CONFERIR). Não duplica: se já existe proposta/aprovado igual, devolve o existente."""
    f = familia(ped, e)
    for it in listar():
        if it["familia"] == f and abs(it["L_uH"] / e["L_uH"] - 1) * 100 <= 0.2 and abs(it["requisitos"].get("In", 0) - e["requisitos"]["In"]) < 0.5 \
                and abs(it["massa_kg"] - d["massa_kg"]["total"]) < 0.5:
            return it["_arquivo"]
    reg = dict(status="A_CONFERIR", familia=f, L_uH=float(e["L_uH"]), requisitos={k: float(v) for k, v in e["requisitos"].items()
                                                                                 if isinstance(v, (int, float))},
               espectro_A={str(h): float(i) for h, i in (e.get("Ih_projeto") or {}).items()},
               massa_kg=float(d["massa_kg"]["total"]), perdas_W=float(d["perdas"]["total"]), elev_K=float(d["termico"]["elev_bobina_K"]),
               dims_mm=d.get("dims_mm"), resumo=dict(N=d.get("N"), coluna_mm=[round(d["a"] * 1e3), round(d["b"] * 1e3)], ng=d.get("ng"),
                                                     chapa=(d.get("chapa_dados") or {}).get("nome")),
               codigo=e.get("codigo"), projeto_origem=projeto, proposto_por=_usuario(), proposto_em=f"{_dt.datetime.now():%Y-%m-%d %H:%M}",
               projeto={k: v for k, v in d.items() if k not in ("campo_pico",)})
    arq = os.path.join(_base(), "propostas", f"{_slug(f, e)}_{_dt.datetime.now():%Y%m%d_%H%M}_{_usuario()}.json")
    with open(arq, "w", encoding="utf-8") as fh:
        json.dump(reg, fh, ensure_ascii=False, indent=1, default=_json_default)
    try:
        from . import memoria as ME
        ME.registrar_uso("componente", f"reator proposto para a biblioteca: {os.path.basename(arq)}", projeto)
    except Exception:
        pass
    return arq


def _ler(arq, completo=False):
    try:
        j = json.load(open(arq, encoding="utf-8"))
        j["_arquivo"] = arq
        if not completo:
            j.pop("projeto", None)
        return j
    except Exception:
        return None


def listar(status=None, completo=False):
    b, out = _base(), []
    for sub, st_ in (("aprovados", "APROVADO"), ("propostas", "A_CONFERIR")):
        if status and status != st_:
            continue
        for f in sorted(glob.glob(os.path.join(b, sub, "*.json"))):
            j = _ler(f, completo)
            if j:
                j["status"] = st_
                out.append(j)
    return out


def pode_aprovar():
    from . import protecao as PR
    return PR.usuario() in PR.autorizados()


def _mover(arquivo, destino, **extra):
    if not pode_aprovar():
        raise PermissionError("Só o engenheiro responsável aprova/recusa reatores da biblioteca.")
    j = _ler(arquivo, completo=True) or {}
    j.pop("_arquivo", None)
    j.update(extra)
    dst = os.path.join(_base(), destino, os.path.basename(arquivo))
    with open(dst, "w", encoding="utf-8") as fh:
        json.dump(j, fh, ensure_ascii=False, indent=1, default=_json_default)
    os.remove(arquivo)
    return dst


def aprovar(arquivo, observacao=""):
    return _mover(arquivo, "aprovados", status="APROVADO", aprovado_por=_usuario(), aprovado_em=f"{_dt.datetime.now():%Y-%m-%d %H:%M}",
                  obs_aprovacao=observacao)


def recusar(arquivo, motivo):
    return _mover(arquivo, "recusados", status="RECUSADO", recusado_por=_usuario(), motivo=motivo)


def conferir(reg, e):
    """Linhas [grandeza, reator padrão, este projeto, ok] – o padrão tem que COBRIR o caso."""
    rl, rp = reg["requisitos"], e["requisitos"]
    lin = [("Indutância (µH)", reg["L_uH"], e["L_uH"], abs(reg["L_uH"] / e["L_uH"] - 1) * 100 <= TOL_L_PCT)]
    nomes = dict(In="Corrente térmica de projeto (A)", Ipk="Pico de operação (A)", Isat="Corrente de saturação exigida (A pico)",
                 Ilin="Linearidade 2,5 × fundamental (A pico)", Iovl="Sobrecarga (A pico)", I1="Fundamental (A)")
    for k in CAMPOS_REQ:
        if rp.get(k) is None:
            continue
        lin.append((nomes[k], rl.get(k), rp[k], rl.get(k) is not None and rl[k] >= rp[k] * 0.995))
    el, ep = reg.get("espectro_A") or {}, e.get("Ih_projeto") or {}
    for h in sorted(ep, key=lambda x: int(float(x))):
        vl = el.get(str(h), el.get(str(int(float(h)))))
        lin.append((f"Harmônica {int(float(h))}ª (A)", vl, ep[h], vl is not None and vl >= float(ep[h]) * 0.995))
    return lin


def buscar(ped, e, log=print):
    """Reator APROVADO que cobre o estágio → (projeto d, registro, linhas de conferência) ou (None, None, motivo)."""
    f = familia(ped, e)
    cand, quase = [], []
    for reg in listar("APROVADO"):
        if reg["familia"] != f:
            continue
        lin = conferir(reg, e)
        if all(x[3] for x in lin):
            cand.append((reg["massa_kg"], reg, lin))
        else:
            quase.append((reg, [x for x in lin if not x[3]]))
    if not cand:
        if quase:
            reg, falt = quase[0]
            return None, None, (f"reator padrão {os.path.basename(reg['_arquivo'])} NÃO cobre este caso: "
                                + "; ".join(f"{n}: padrão {a if a is None else round(a, 1)} × caso {b:.1f}" for n, a, b, _ in falt[:4]))
        return None, None, "nenhum reator padrão aprovado para esta família"
    _, reg, lin = min(cand, key=lambda x: x[0])                       # o mais leve que cobre
    full = _ler(reg["_arquivo"], completo=True)
    d = full.get("projeto")
    if not d:
        return None, None, "registro da biblioteca sem o modelo salvo"
    try:                                                # o mapa de campo no pico não é gravado (objeto do FEM) – recalcula do modelo salvo
        from .ind_projeto import modelo
        Mn = modelo(d, d["gaps"], d["ng"])
        I = float(d["requisitos"]["Ipk"])
        d["campo_pico"] = (Mn, Mn.resolver([I, -I / 2, -I / 2]))
    except Exception as ex:
        return None, None, f"modelo salvo não pôde ser recalculado ({type(ex).__name__}: {ex})"
    return d, reg, lin


def tabela_md(reg, lin):
    md = ["", "## Reator PADRÃO da biblioteca (REQ-REA-014)", "",
          f"Usado o reator aprovado **{os.path.basename(reg['_arquivo'])}** (aprovado por {reg.get('aprovado_por')} em {reg.get('aprovado_em')}; "
          f"projeto de origem: {reg.get('projeto_origem') or '—'}) – {reg['massa_kg']:.0f} kg, {reg['perdas_W']:.0f} W. O modelo de elementos "
          "finitos não foi refeito; conferido se o padrão cobre as correntes deste caso:", "",
          "| Grandeza | Reator padrão (projetado para) | Este projeto (exige) | Check |", "|---|---|---|---|"]
    for n, a, b, ok in lin:
        md.append(f"| {n} | {'—' if a is None else f'{a:.1f}'} | {b:.1f} | {'✔ APROVADO' if ok else '✖ REPROVADO'} |")
    return md
