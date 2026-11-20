"""Alternativa de indutância na faixa de mercado (v1.9.9).

Quando o L escolhido pela otimização fica ABAIXO da faixa dos fabricantes especializados (Schaffner/REO), a ondulação de
alta frequência é maior que a usual e o indutor fica mais difícil de fabricar (mais perdas HF, mais fluxo espraiado no
entreferro). Esta rotina simula alternativas com L dentro da faixa de mercado, reajustando o nº de capacitores (mexer em L
exige mexer em C: senão a ressonância cai em cima das harmônicas de baixa ordem), e devolve as aprovadas para que o
fornecedor possa cotar as duas opções.
"""
from .spec_indutor import referencia_mercado


def _thd(pr, chave):
    for v in pr.verificacoes:
        if chave in v.item:
            try:
                return float(str(v.valor).split("%")[0].replace(",", ".").split()[-1])
            except Exception:
                return None
    return None


def _linha(pr, rotulo):
    l1, b = pr.l1, pr.banco
    return dict(rotulo=rotulo, l_uh=float(l1.l_uh), n_por_ramo=int(b.n_por_ramo), n_total=int(b.n_total), cap=b.cap_id, ligacao=b.ligacao,
                fr_hz=round(float(pr.fr_hz)), ripple_pp=round(float(l1.ripple_pp_a)), queda_pct=round(float(l1.queda_v_pct), 1),
                thd_motor=_thd(pr, "THD total no motor"), thd_vazio=_thd(pr, "SEM motor"), perdas_l=round(float(l1.perdas_w)),
                massa_l=round(float(l1.massa_kg)), custo=round(float(pr.custo_componentes or 0)), aprovado=bool(pr.aprovado),
                falhas=[v.item for v in pr.verificacoes if v.critico and not v.ok])


def alternativas(proj, cat, max_opcoes=3):
    from .dimensionamento import projeto_manual, config_de_projeto
    from .modelos import Pedido
    if proj.topologia != "LC" or proj.l2:
        return dict(necessaria=False, motivo="só para LC")
    ped = Pedido.from_dict(proj.pedido) if isinstance(proj.pedido, dict) else proj.pedido
    _, _, fx = referencia_mercado(float(proj.l1.i_nom_a), cat)
    atual = _linha(proj, "Projeto atual")
    if not fx:
        return dict(necessaria=False, motivo="corrente fora da faixa de referência", atual=atual)
    lo, hi = fx["l_mh"][0] * 1000, fx["l_mh"][1] * 1000
    nec = atual["l_uh"] < 0.85 * lo
    if not nec:
        return dict(necessaria=False, motivo="L dentro da faixa de mercado", faixa=(lo, hi), atual=atual)
    cfg = config_de_projeto(proj)
    alvos = sorted({int(round(x / 5.0) * 5) for x in (lo, (lo + hi) / 2, hi)})
    nmax = max(cfg["n_por_ramo"] + 1, 2)
    ops = []
    for L in alvos:
        for n in range(1, nmax + 1):
            try:
                pr = projeto_manual(ped, cat, cfg["fs_khz"], float(L), cfg["cap_id"], cfg["ligacao"], n, detalhado=False)
            except Exception:
                continue
            if pr.aprovado:
                ops.append(_linha(pr, f"{L} µH + {pr.banco.n_total} cap."))
    # por L: a de menor custo; depois ordena por L
    melhor = {}
    for o in ops:
        if o["l_uh"] not in melhor or o["custo"] < melhor[o["l_uh"]]["custo"]:
            melhor[o["l_uh"]] = o
    ops = sorted(melhor.values(), key=lambda o: o["l_uh"])[:max_opcoes]
    # refaz a recomendada com simulação completa (valores finais)
    rec = None
    if ops:
        r0 = min(ops, key=lambda o: (o["ripple_pp"] > 0.85 * atual["ripple_pp"], o["custo"]))
        try:
            pr = projeto_manual(ped, cat, cfg["fs_khz"], r0["l_uh"], cfg["cap_id"], cfg["ligacao"], r0["n_por_ramo"])
            rec = _linha(pr, f"RECOMENDADA: {r0['l_uh']:.0f} µH + {pr.banco.n_total} cap.")
            rec["aprovado"] = bool(pr.aprovado)
            rec["_proj"] = pr
        except Exception:
            rec = r0
    return dict(necessaria=True, faixa=(lo, hi), atual=atual, opcoes=ops, recomendada=rec,
                motivo=f"L do projeto ({atual['l_uh']:.0f} µH) abaixo da faixa de mercado ({lo:.0f}–{hi:.0f} µH)")


def escrever_secao(d, alt, _tabela, titulo_num="9"):
    if not alt or not alt.get("necessaria"):
        return
    d.add_heading(f"{titulo_num}. Alternativa de indutância (cotar também)", 1)
    d.add_paragraph(f"{alt['motivo']}. POR QUÊ cotar a alternativa: com indutância maior a ondulação de alta frequência cai, o "
                    "indutor perde menos em alta frequência e o entreferro é menos crítico de fabricar. O nº de capacitores é "
                    "reajustado junto, para a ressonância não cair sobre as harmônicas de baixa ordem do inversor. Todas as opções "
                    "abaixo foram simuladas e aprovadas pela plataforma.")
    linhas = []
    for o in [alt["atual"]] + ([alt["recomendada"]] if alt.get("recomendada") else []) + \
            [o for o in alt.get("opcoes", []) if not alt.get("recomendada") or o["l_uh"] != alt["recomendada"]["l_uh"]]:
        linhas.append((o["rotulo"], f"{o['l_uh']:.0f}", f"{o['n_total']}", f"{o['fr_hz']}", f"{o['ripple_pp']}", f"{o['queda_pct']}",
                       "–" if o["thd_motor"] is None else f"{o['thd_motor']:.1f}", f"{o['custo']:,.0f}".replace(",", ".")))
    _tabela(d, ["Opção", "L (µH)", "Capacitores", "fr (Hz)", "Ondulação (A p-p)", "Queda (%)", "THD motor (%)", "Custo comp. (R$)"],
            linhas, [4.2, 1.5, 1.8, 1.5, 2.2, 1.6, 2.0, 2.2], 8)
    at = (alt.get("recomendada") or {}).get("atp") or {}
    if at.get("status") == "rodou":
        d.add_paragraph("Dupla checagem da alternativa recomendada no ATP-EMTP (referência do setor): " + at["msg"] + ".")
        _tabela(d, ["Ponto", "Grandeza", "Python", "ATP", "Dif. (%)", "OK"],
                [(x["ponto"], x["grandeza"], f"{x['python']:.4g}", f"{x['atp']:.4g}", f"{x['dif']:+.1f}", "sim" if x["ok"] else "NÃO")
                 for x in at["tabela"]], [3.6, 5.2, 1.9, 1.9, 1.6, 1.0], 8)
    else:
        d.add_paragraph("Dupla checagem da alternativa no ATP-EMTP: " + (at.get("msg") or "não executada") +
                        ". Rodar o projeto na plataforma no PC com ATP antes de fechar a alternativa.")


def texto_email(alt):
    if not alt or not alt.get("necessaria") or not alt.get("recomendada"):
        return ""
    r, a = alt["recomendada"], alt["atual"]
    at = (r.get("atp") or {})
    conf = " (simulada na plataforma e confirmada no ATP-EMTP)" if at.get("status") == "rodou" and at.get("convergiu") else ""
    return (f"\n6) ALTERNATIVA – FAVOR COTAR TAMBÉM{conf}\n"
            f"Indutância {r['l_uh']:.0f} µH (mesma corrente). Com ela a ondulação cai de {a['ripple_pp']} para {r['ripple_pp']} A p-p, "
            "o que reduz as perdas de alta frequência e facilita o entreferro. Se for mais fácil de fabricar ou der mais margem "
            "térmica, prefiro esta opção.\n")


def atp_alternativa(alt, cat, cod, log=None):
    """Dupla checagem no ATP-EMTP da alternativa RECOMENDADA (f máx e f mín), como no projeto principal.
    Só roda no PC com o ATP instalado; senão registra 'nao_instalado'."""
    import os
    rec = (alt or {}).get("recomendada")
    if not rec or "_proj" not in rec:
        return
    from . import atp as A
    cfg = cat.get("atp", {})
    if not cfg.get("habilitado", True):
        rec["atp"] = dict(status="desabilitado")
        return
    tp = A.achar_tpbig(cat)
    if not tp:
        rec["atp"] = dict(status="nao_instalado", msg="ATP não instalado neste computador – alternativa verificada só no Python")
        return
    try:
        trab = os.path.join(cfg.get("pasta_trabalho", A.PASTA_TRABALHO_PADRAO), f"{cod}_ALT")
        casos = A.preparar_casos(rec["_proj"], cat, trab)[:2]
        for c in casos:
            r = A.rodar_atp(os.path.join(trab, c["nome"] + ".atp"), tp)
            if not r["ok"]:
                rec["atp"] = dict(status="falhou", msg=f"ATP falhou em {c['ponto']}")
                return
        res = A.comparar_casos(casos, trab)
        chaves = ("THD tensão de saída", "Tensão de saída L-L fundamental", "Ondulação p-p", "Corrente RMS por capacitor", "Pico tensão L-L no banco")
        tab = [dict(ponto=x["ponto"], grandeza=l["grandeza"], python=l["python"], atp=l["atp"], dif=l["dif_pct"], ok=l["convergiu"])
               for x in res for l in x["tabela"] if any(l["grandeza"].startswith(k) for k in chaves)]
        conv = all(l["convergiu"] for x in res for l in x["tabela"])
        rec["atp"] = dict(status="rodou", convergiu=conv, tabela=tab,
                          msg="ATP-EMTP confirmou a alternativa (convergiu com o Python)" if conv else
                          "ATP-EMTP rodou e há DIVERGÊNCIA com o Python na alternativa – revisar antes de oferecer")
        if log:
            log("   ATP – alternativa de indutância: " + rec["atp"]["msg"])
    except Exception as e:
        rec["atp"] = dict(status="falhou", msg=f"{type(e).__name__}: {e}")


def limpar(alt):
    """Remove objetos não serializáveis antes de gravar o JSON."""
    if alt and alt.get("recomendada"):
        alt["recomendada"].pop("_proj", None)
    return alt
