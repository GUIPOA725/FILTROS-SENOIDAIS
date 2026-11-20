"""Ponto ótimo "de mercado" + robustez + referências internacionais (v1.9.11; regra da alternativa v1.9.12).

Pedido do usuário (20/11/2026): usar a IA para aprofundar as análises antes de fabricar – comparar o modelo com fabricantes
de referência (MTE, Schaffner, REO, FRAKO/TDK), priorizar indutor maior e MENOS capacitores (capacitor 20 µF/480 V difícil
de comprar), testar a robustez (tolerâncias de L e C, cabo, capacitância do motor) e documentar tudo na plataforma.

Critérios de referência (fontes no fim do arquivo):
- MTE (T. Luu, IEEE 2020): indutância de 8–10 % da impedância nominal; ressonância 25–35 % da frequência de chaveamento
  (regra para fs ≤ 2 kHz). SineWave Guardian 305 A: 945 W, ≈118 kg, fs 2–8 kHz, queda ≤ 6 % a 60 Hz, termostato 180 °C.
- FRAKO (guia de projeto de capacitores para eletrônica de potência, IEC 61071): em filtros PWM a tensão de pico no capacitor
  pode chegar à tensão do barramento CC → UN do capacitor ≥ Vcc máx. Exemplo do guia: 100 hp/480 V/120 A, fs 2 kHz,
  L = 570 µH (≈ 9 % → coerente com a MTE), corrente no capacitor dominada pela alta frequência (19,9 A RMS × 9,4 A a 60 Hz).
- Schaffner FN5040 / REO N CNW 933: faixas de L, perdas e massa por corrente (spec_indutor.REF_MERCADO_PADRAO).
"""
import copy
import dataclasses
import math

UK_MERCADO = (7.0, 10.0)          # % – MTE 8–10 %, com 1 ponto de folga para baixo
FS_FR_MERCADO = (0.20, 0.35)      # fr / fs
FONTES = [
    "MTE Corp. – T. Luu, 'Modeling and Practical Design Dual-Mode Sinewave and Common Mode Filter for PWM Motor Drives', IEEE 2020",
    "MTE Corp. – SineWave Guardian, manual técnico e folheto (305 A: 945 W, ≈118 kg, fs 2–8 kHz)",
    "FRAKO GmbH – Projektierungsleitfaden Leistungselektronik-Kondensatoren (IEC 61071) – exemplo de filtro senoidal 120 A / 2 kHz",
    "Schaffner FN5040/FN5045 – datasheet; REO N CNW 933 – catálogo",
    "MTE – patentes US 9.571.058 (indutor com bobinas acopladas/derivação) e US 9.548.154 (núcleo com blocos de baixa permeabilidade)",
]


def _val(pr, chave):
    for v in pr.verificacoes:
        if chave in v.item:
            try:
                return float(str(v.valor).split("%")[0].replace(",", ".").split()[-1])
            except Exception:
                return None
    return None


def _thd_lim(cat):
    return float(cat.get("projeto_padrao", {}).get("thd_motor_max_pct", 6.0))


def _ped(proj_or_ped):
    from .modelos import Pedido
    p = getattr(proj_or_ped, "pedido", proj_or_ped)
    return Pedido.from_dict(p) if isinstance(p, dict) else p


def robustez(ped, cat, fs_khz, L_uh, cap_id, lig, n, detalhar=True):
    """THD no motor com L ±10 %, C ±5 %, cabo curto/longo e Cwf ×3. ok = todos aprovados e THD ≤ limite."""
    from .dimensionamento import projeto_manual
    cap = next(c for c in cat["capacitores"] if c["id"] == cap_id)
    lim = _thd_lim(cat)
    casos = []

    def run(nome, ped_=ped, cat_=cat, L=L_uh, capc=None):
        try:
            pr = projeto_manual(ped_, cat_, fs_khz, L, cap_id, lig, n, cap_custom=capc, detalhado=False)
            t = _val(pr, "THD total no motor")
            casos.append(dict(caso=nome, thd=t, aprovado=bool(pr.aprovado)))
        except Exception as e:
            casos.append(dict(caso=nome, thd=None, aprovado=False, erro=str(e)))
    run("Nominal")
    for k in (0.9, 0.95, 1.05, 1.1):
        run(f"L {100 * (k - 1):+.0f} %", L=L_uh * k)
    for k in (0.95, 1.05):
        run(f"C {100 * (k - 1):+.0f} %", capc=dict(cap, uf=cap["uf"] * k, id=cap_id))
    if detalhar:
        base_m = ped.cabo_m or cat.get("cabo_comprimento_padrao_m", 30)
        for m in (max(base_m * 0.25, 2), base_m * 4):
            run(f"Cabo {m:.0f} m", ped_=dataclasses.replace(ped, cabo_m=m))
        c2 = copy.deepcopy(cat)
        c2["motor_modelo"]["cwf_nf_por_raiz_kw"] = c2["motor_modelo"].get("cwf_nf_por_raiz_kw", 0.35) * 3
        run("Capacitância do motor ×3", cat_=c2)
    thds = [c["thd"] for c in casos if c["thd"] is not None]
    ok = all(c["aprovado"] for c in casos[:7]) and (max(thds) if thds else 99) <= lim
    return dict(casos=casos, thd_max=max(thds) if thds else None, ok=ok, limite=lim)


def otimizar_mercado(ped, cat, fs_khz=None, caps=None, ligacoes=("Delta", "Estrela"), n_max=6, passo_uh=10, max_resultados=8):
    """Varre L na faixa de mercado (uk 7–10 %) × capacitores × ligação × nº por ramo. Mantém aprovados e ROBUSTOS e ordena por
    nº de capacitores, depois PROXIMIDADE da faixa MTE (8–10 % de Zb), depois custo (v1.9.12 – regra fixa, determinística).
    Retorna lista de dicts (o primeiro é o recomendado)."""
    from .dimensionamento import projeto_manual
    fs_khz = fs_khz or (ped.fs_khz or 4.0)
    w = 2 * math.pi * ped.freq_rede_hz
    Zb = ped.tensao_v / math.sqrt(3) / ped.corrente_a
    l_lo = UK_MERCADO[0] / 100 * Zb / w * 1e6
    l_hi = UK_MERCADO[1] / 100 * Zb / w * 1e6
    Ls = list(range(int(math.floor(l_lo / passo_uh) * passo_uh), int(math.ceil(l_hi / passo_uh) * passo_uh) + 1, passo_uh))
    caps = caps or [c["id"] for c in cat["capacitores"] if (c.get("norma") or "").replace(" ", "") == "IEC61071"] or \
        [c["id"] for c in cat["capacitores"]]
    cand = []
    for cap_id in caps:
        for lig in ligacoes:
            for n in range(1, n_max + 1):
                for L in Ls:
                    try:
                        pr = projeto_manual(ped, cat, fs_khz, float(L), cap_id, lig, n, detalhado=False)
                    except Exception:
                        continue
                    if not pr.aprovado:
                        continue
                    cand.append(dict(L_uh=float(L), cap_id=cap_id, ligacao=lig, n_por_ramo=n, n_caps=pr.banco.n_total,
                                     fr_hz=round(pr.fr_hz), uk_pct=round(pr.l1.uk_pct, 1), ripple=round(pr.l1.ripple_pp_a),
                                     thd=_val(pr, "THD total no motor"), thd_vazio=_val(pr, "SEM motor"),
                                     queda=round(pr.l1.queda_v_pct, 1), custo=round(pr.custo_componentes or 0),
                                     massa_l=round(pr.l1.massa_kg), fr_fs=round(pr.fr_hz / (fs_khz * 1000), 2),
                                     icap=round(pr.banco.i_unit_rms, 1)))
    m_lo, m_hi = 8 / 100 * Zb / w * 1e6, 10 / 100 * Zb / w * 1e6
    dist_mte = lambda L: max(m_lo - L, 0.0, L - m_hi)
    cand.sort(key=lambda c: (c["n_caps"], round(dist_mte(c["L_uh"])), c["custo"], c["L_uh"]))
    out, vistos = [], set()
    for c in cand:
        chave = (c["cap_id"], c["ligacao"], c["n_por_ramo"])
        if chave in vistos:
            continue
        rb = robustez(ped, cat, fs_khz, c["L_uh"], c["cap_id"], c["ligacao"], c["n_por_ramo"], detalhar=False)
        if not rb["ok"]:
            continue
        c["thd_robusto_max"] = rb["thd_max"]
        vistos.add(chave)
        out.append(c)
        if len(out) >= max_resultados:
            break
    return out


def checar_capacitor_vcc(proj, cat):
    """FRAKO: em filtro PWM o pico no capacitor pode chegar a Vcc → UN do capacitor ≥ Vcc máx (rede +10 %)."""
    ped = _ped(proj)
    b = proj.banco
    capd = next((c for c in cat["capacitores"] if c["id"] == b.cap_id), {})
    vcc = 1.35 * ped.tensao_v * 1.10
    un = capd.get("vn_pico_v") or (math.sqrt(2) * capd.get("v_ac", b.v_unit) * 1.2)
    return dict(vcc_max=round(vcc), un=round(un), ok=un >= vcc, margem_pct=round(100 * (un / vcc - 1), 1))


def estudo(proj, cat, log=None):
    """Estudo completo: projeto atual (robustez completa) + varredura de mercado + checagens + referências."""
    ped = _ped(proj)
    fs_khz = proj.fs_hz / 1000
    b = proj.banco
    atual = dict(L_uh=float(proj.l1.l_uh), cap_id=b.cap_id, ligacao=b.ligacao, n_por_ramo=int(b.n_por_ramo), n_caps=int(b.n_total),
                 fr_hz=round(proj.fr_hz), uk_pct=round(proj.l1.uk_pct, 1), ripple=round(proj.l1.ripple_pp_a),
                 thd=_val(proj, "THD total no motor"), queda=round(proj.l1.queda_v_pct, 1), custo=round(proj.custo_componentes or 0),
                 fr_fs=round(proj.fr_hz / proj.fs_hz, 2))
    rb_atual = robustez(ped, cat, fs_khz, atual["L_uh"], b.cap_id, b.ligacao, b.n_por_ramo, detalhar=True)
    if log:
        log("   Ponto ótimo de mercado: varrendo L (uk 7–10 %) × capacitores × ligação...")
    # v1.9.12: a alternativa usa o MESMO capacitor do projeto (o que a empresa tem/compra), salvo se o catálogo pedir outra coisa
    caps_alt = [b.cap_id] if cat.get("alternativa_mesmo_capacitor", True) else None
    ops = otimizar_mercado(ped, cat, fs_khz, caps=caps_alt) if proj.topologia == "LC" and not proj.l2 else []
    rec = ops[0] if ops else None
    rb_rec = robustez(ped, cat, fs_khz, rec["L_uh"], rec["cap_id"], rec["ligacao"], rec["n_por_ramo"], detalhar=True) if rec else None
    w = 2 * math.pi * ped.freq_rede_hz
    Zb = ped.tensao_v / math.sqrt(3) / ped.corrente_a
    faixa_mte = (8 / 100 * Zb / w * 1e6, 10 / 100 * Zb / w * 1e6)
    cabo_m = ped.cabo_m or cat.get("cabo_comprimento_padrao_m", 30)
    aviso_cabo = None
    if cabo_m > 150:
        aviso_cabo = (f"Cabo de {cabo_m:.0f} m: a capacitância do cabo passa a somar com a do filtro e baixa a ressonância; "
                      "conferir no estudo de robustez (caso 'Cabo') e no ATP.")
    return dict(atual=atual, robustez_atual=rb_atual, opcoes=ops, recomendada=rec, robustez_recomendada=rb_rec,
                faixa_mte_uh=(round(faixa_mte[0]), round(faixa_mte[1])), uk_atual=atual["uk_pct"],
                cap_vcc=checar_capacitor_vcc(proj, cat), aviso_cabo=aviso_cabo, fontes=FONTES)


def gerar_docx(proj, cat, est, pasta_eng, _novo, _tabela, _bullets):
    import os
    d = _novo("Estudo de Ponto Ótimo e Robustez", "Comparação com fabricantes de referência (MTE, Schaffner, REO, FRAKO)", proj, cat)
    a, rec = est["atual"], est["recomendada"]
    d.add_heading("1. Objetivo", 1)
    d.add_paragraph("Verificar, antes de fabricar, se o filtro está dentro da prática dos fabricantes de referência, se continua "
                    "atendendo com as tolerâncias reais dos componentes e da instalação, e qual configuração usa MENOS capacitores "
                    "com indutor na faixa de mercado.")
    d.add_heading("2. Critérios de referência", 1)
    _bullets(d, [f"MTE: indutância de 8–10 % da impedância nominal → {est['faixa_mte_uh'][0]}–{est['faixa_mte_uh'][1]} µH para este "
                 f"filtro (projeto atual: {a['L_uh']:.0f} µH, uk {a['uk_atual'] if 'uk_atual' in a else est['uk_atual']} %).",
                 f"MTE: ressonância 25–35 % da frequência de chaveamento (regra para fs ≤ 2 kHz) – projeto atual fr/fs = {a['fr_fs']:.2f}.",
                 f"FRAKO (IEC 61071): UN do capacitor ≥ Vcc máx – Vcc máx {est['cap_vcc']['vcc_max']} V, UN {est['cap_vcc']['un']} V "
                 f"({'atende' if est['cap_vcc']['ok'] else 'NÃO atende'}, margem {est['cap_vcc']['margem_pct']:+.1f} %).",
                 "Schaffner/REO: faixas de L, perdas e massa por corrente (ver ET do indutor, item 8)."])
    d.add_heading("3. Robustez do projeto atual", 1)
    _tab_rb(d, est["robustez_atual"], _tabela)
    d.add_heading("4. Varredura – menos capacitores com indutor de mercado", 1)
    d.add_paragraph("Todas as opções abaixo foram simuladas, aprovadas em todos os critérios e passaram no teste de robustez "
                    "(L ±10 %, C ±5 %). Ordenadas por nº de capacitores e custo.")
    if est["opcoes"]:
        _tabela(d, ["#", "L (µH)", "uk (%)", "Capacitor", "Lig.", "Cap.", "fr (Hz)", "fr/fs", "Ondul. (A)", "THD (%)", "THD pior (%)",
                    "Queda (%)", "Custo (R$)"],
                [(i + 1, f"{o['L_uh']:.0f}", o["uk_pct"], o["cap_id"].replace("TDK_PEC_", ""), o["ligacao"][:5], o["n_caps"], o["fr_hz"],
                  o["fr_fs"], o["ripple"], o["thd"], o.get("thd_robusto_max"), o["queda"], f"{o['custo']:,}".replace(",", "."))
                 for i, o in enumerate(est["opcoes"])], [0.6, 1.1, 1.0, 1.6, 1.0, 0.9, 1.1, 1.0, 1.2, 1.1, 1.3, 1.1, 1.6], 7)
    else:
        d.add_paragraph("Nenhuma opção na faixa de mercado passou em todos os critérios e na robustez.")
    d.add_heading("5. Recomendação", 1)
    if rec:
        d.add_paragraph(f"Recomendada: {rec['L_uh']:.0f} µH + {rec['n_caps']} × {rec['cap_id'].replace('TDK_PEC_', '')} em {rec['ligacao']} "
                        f"(fr {rec['fr_hz']} Hz, THD {rec['thd']} %, pior caso {rec.get('thd_robusto_max')} %, queda {rec['queda']} %). "
                        f"Projeto atual: {a['L_uh']:.0f} µH + {a['n_caps']} capacitores (THD {a['thd']} %).")
        if est.get("robustez_recomendada"):
            _tab_rb(d, est["robustez_recomendada"], _tabela)
        d.add_paragraph("Antes de fabricar: emitir o projeto com a opção escolhida (dupla checagem no ATP automática) e conferir a "
                        "proposta do fornecedor do indutor na tela 'Conferir proposta de fornecedor'.")
    if est.get("aviso_cabo"):
        d.add_paragraph("Atenção – " + est["aviso_cabo"])
    d.add_heading("6. Cabos e motor no modelo", 1)
    d.add_paragraph("O modelo inclui o cabo inversor–motor em células π (R, L, capacitância fase-terra e fase-fase por seção) e o "
                    "motor (resistência, indutância de dispersão, força contraeletromotriz e capacitância enrolamento–carcaça). O "
                    "filtro torna a tensão senoidal ANTES do cabo, por isso essas capacitâncias quase não alteram o THD (casos "
                    "'Cabo' e 'Capacitância do motor ×3' acima). Elas passam a importar em cabos muito longos (centenas de metros) e "
                    "no modo comum (corrente de mancal), que o filtro senoidal diferencial não resolve. O ATP usa os mesmos valores: "
                    "confirma a conta, não as capacitâncias – a confirmação delas é a medição em campo com o motor.")
    d.add_heading("Fontes", 1)
    _bullets(d, est["fontes"])
    cam = os.path.join(pasta_eng, "Estudo_Ponto_Otimo_e_Robustez.docx")
    d.save(cam)
    return cam


def _tab_rb(d, rb, _tabela):
    _tabela(d, ["Caso", "THD no motor (%)", "Aprovado"],
            [(c["caso"], "–" if c["thd"] is None else f"{c['thd']:.2f}", "sim" if c["aprovado"] else "NÃO") for c in rb["casos"]],
            [7, 4, 3], 8)
    d.add_paragraph(f"Pior THD: {rb['thd_max']} % (limite {rb['limite']:g} %) → {'ROBUSTO' if rb['ok'] else 'NÃO ROBUSTO – revisar'}.")
