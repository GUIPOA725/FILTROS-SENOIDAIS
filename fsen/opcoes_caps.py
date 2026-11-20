"""Mínimo de capacitores com o capacitor FORÇADO (estoque) – varredura de casos e opções (v1.9.13).

Para o capacitor escolhido (ex.: TDK 20 µF 480 V em Delta), varre nº de capacitores × indutância e avalia, em cada caso, TODOS
os critérios da plataforma (THD, ressonância, picos, correntes e tensões nos capacitores, tensão disponível no motor), a queda de
tensão máxima admitida e a robustez (L ±10 %, C ±5 %, cabo ¼×/4×, capacitância do motor ×3).

Regra de escolha FIXA (determinística – mesmo pedido, mesma resposta), ancorada no que o mercado já fabrica e testou:
  1º menos capacitores;  2º indutância mais próxima da faixa dos produtos de mercado para esta corrente (Schaffner FN5040 / REO
  CNW 933 interpolados; sem referência, faixa MTE 8–10 % de Zb);  3º menor custo;  4º menor L.
Só entram casos aprovados em todos os critérios críticos, robustos e com PERDA DE INSERÇÃO (queda real de tensão na saída,
com o FP do motor) ≤ limite (MTE ≤ 6 %). A queda reativa no indutor (ωL·I/V) também é mostrada, mas ela não é a tensão que o
motor perde: com carga indutiva só a parcela em fase conta (≈ X·I·senφ).
"""
import math

QUEDA_MAX_PADRAO = 6.0      # % na f máx de operação, In – MTE: queda de inserção do filtro senoidal ≤ ~6 %
FONTES = ["MTE Corp. – SineWave Guardian: queda de inserção típica ≤ 6 % e indutância 8–10 % da impedância nominal (T. Luu, IEEE 2020)",
          "IEC 60034-1 – zona A de tensão do motor ±5 % (por isso a plataforma exige tensão disponível ≥ 100 % do V/f na faixa de operação)",
          "IEC 61071 – capacitores para eletrônica de potência (corrente RMS, pico e Vcc máx)",
          "IEEE 519 / prática dos fabricantes de filtro senoidal – THD de tensão no motor ≤ 5 %"]


def _val(pr, chave):
    for v in pr.verificacoes:
        if chave in v.item:
            try:
                return float(str(v.valor).split("%")[0].replace(",", ".").split()[0])
            except Exception:
                return None
    return None


def varrer(ped, cat, fs_khz, caps, ligacoes=("Delta",), n_max=6, passo_uh=10, uk_min=4.0, uk_max=14.0,
           queda_max=QUEDA_MAX_PADRAO, log=None):
    from .dimensionamento import projeto_manual
    from .ponto_otimo import robustez
    w = 2 * math.pi * ped.freq_rede_hz
    Zb = ped.tensao_v / math.sqrt(3) / ped.corrente_a
    lb = Zb / w * 1e6
    Ls = list(range(int(math.ceil(uk_min / 100 * lb / passo_uh) * passo_uh), int(uk_max / 100 * lb) + 1, passo_uh))
    m_lo, m_hi = 0.08 * lb, 0.10 * lb
    try:
        from .spec_indutor import referencia_mercado
        _fx = referencia_mercado(float(ped.corrente_a), cat)[2]
        r_lo, r_hi = (_fx["l_mh"][0] * 1000, _fx["l_mh"][1] * 1000) if _fx else (m_lo, m_hi)
        ref_txt = "produtos de mercado (Schaffner FN5040 / REO CNW 933 interpolados)" if _fx else "faixa MTE 8–10 % de Zb"
    except Exception:
        r_lo, r_hi, ref_txt = m_lo, m_hi, "faixa MTE 8–10 % de Zb"
    dist = lambda L: max(r_lo - L, 0.0, L - r_hi)
    fp = float(getattr(ped, "motor_fp", 0) or 0.85)
    f_op = float(ped.f_saida_max_hz or ped.freq_rede_hz)

    def _insercao(L, i_a):
        vo = ped.tensao_v * min(f_op / ped.freq_rede_hz, 1.0) / math.sqrt(3)
        x = 2 * math.pi * f_op * L * 1e-6
        phi = -math.acos(max(min(fp, 1.0), 0.0))
        vi = complex(vo, 0) + 1j * x * i_a * complex(math.cos(phi), math.sin(phi))
        return 100 * (abs(vi) - vo) / abs(vi)
    linhas = []
    for cap_id in caps:
        for lig in ligacoes:
            for n in range(1, n_max + 1):
                for L in Ls:
                    try:
                        pr = projeto_manual(ped, cat, fs_khz, float(L), cap_id, lig, n, detalhado=False)
                    except Exception:
                        continue
                    r = dict(cap_id=cap_id, ligacao=lig, n_por_ramo=n, n_caps=int(pr.banco.n_total), L_uh=float(L),
                             uk_pct=round(pr.l1.uk_pct, 1), fr_hz=round(pr.fr_hz), fr_fs=round(pr.fr_hz / (fs_khz * 1000), 2),
                             aprovado=bool(pr.aprovado), falhas=[v.item for v in pr.verificacoes if v.critico and not v.ok],
                             thd=_val(pr, "THD total no motor"), thd_vazio=_val(pr, "SEM motor"), queda=round(pr.l1.queda_v_pct, 1),
                             insercao=round(_insercao(L, float(pr.l1.i_fund_a)), 1),
                             v_placa=_val(pr, "Placa do filtro"), ripple=round(pr.l1.ripple_pp_a), icap=round(pr.banco.i_unit_rms, 1),
                             perdas_l=round(pr.l1.perdas_w), massa_l=round(pr.l1.massa_kg), custo=round(pr.custo_componentes or 0),
                             robusto=None, thd_pior=None)
                    if r["aprovado"] and r["insercao"] <= queda_max:
                        rb = robustez(ped, cat, fs_khz, float(L), cap_id, lig, n, detalhar=False)
                        r["robusto"], r["thd_pior"] = bool(rb["ok"]), rb["thd_max"]
                    r["valida"] = bool(r["aprovado"] and r["robusto"] and r["insercao"] <= queda_max)
                    r["_ord"] = (r["n_caps"], round(dist(L)), r["custo"], L)
                    linhas.append(r)
            if log:
                log(f"   varredura {cap_id} {lig}: {sum(1 for x in linhas if x['valida'])} casos válidos até agora")
    validas = sorted([x for x in linhas if x["valida"]], key=lambda x: x["_ord"])
    rec = validas[0] if validas else None
    # melhor por quantidade de capacitores
    por_qtd = {}
    for x in validas:
        por_qtd.setdefault(x["n_caps"], x)
    # opções para apresentar: até 3 na quantidade mínima + a melhor de cada quantidade seguinte (até 3)
    opcoes = []
    if rec:
        opcoes = [x for x in validas if x["n_caps"] == rec["n_caps"]][:3]
        opcoes += [por_qtd[k] for k in sorted(por_qtd) if k > rec["n_caps"]][:3]
    # por que menos capacitores não serve
    abaixo = []
    if rec:
        for k in sorted({x["n_caps"] for x in linhas if x["n_caps"] < rec["n_caps"]}):
            cand = [x for x in linhas if x["n_caps"] == k]
            ap = [x for x in cand if x["aprovado"]]
            if ap:
                mot = []
                if not any(x["insercao"] <= queda_max for x in ap):
                    mot.append(f"só aprova com perda de inserção de {min(x['insercao'] for x in ap):.1f}–{max(x['insercao'] for x in ap):.1f} % "
                               f"(máx. {queda_max:g} %), L {min(x['L_uh'] for x in ap):.0f}–{max(x['L_uh'] for x in ap):.0f} µH")
                elif not any(x["robusto"] for x in ap if x["robusto"] is not None):
                    mot.append("aprova no valor nominal mas NÃO é robusto (com L ±10 % / C ±5 % o THD passa do limite)")
            else:
                from collections import Counter
                c = Counter(f for x in cand for f in x["falhas"])
                mot = ["nenhuma indutância aprova: " + "; ".join(f"{k2[:60]} ({v} casos)" for k2, v in c.most_common(2))]
            abaixo.append(dict(n_caps=k, motivo=" / ".join(mot)))
    crit = dict(queda_max=queda_max, faixa_mte_uh=(round(m_lo), round(m_hi)), faixa_ref_uh=(round(r_lo), round(r_hi)), ref_txt=ref_txt,
                uk_varrido=(uk_min, uk_max), passo_uh=passo_uh,
                regra=f"1º menos capacitores; 2º L mais perto da faixa dos {ref_txt}: {r_lo:.0f}–{r_hi:.0f} µH; 3º menor custo; 4º menor L")
    for x in linhas:
        x.pop("_ord", None)
    return dict(linhas=linhas, recomendada=rec, opcoes=opcoes, por_qtd=por_qtd, abaixo=abaixo, criterios=crit,
                caps=list(caps), ligacoes=list(ligacoes), fs_khz=fs_khz, fontes=FONTES)


def grafico(est, png):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    qmax = est["criterios"]["queda_max"]
    grupos = sorted({(x["cap_id"], x["ligacao"], x["n_caps"]) for x in est["linhas"]}, key=lambda g: g[2])[:5]
    fig, ax = plt.subplots(1, 2, figsize=(13, 4.8))
    cores = ["#2b6cb0", "#c05621", "#2f855a", "#6b46c1", "#b7791f"]
    for g, cor in zip(grupos, cores):
        xs = sorted([x for x in est["linhas"] if (x["cap_id"], x["ligacao"], x["n_caps"]) == g], key=lambda x: x["L_uh"])
        lab = f"{g[2]} × {g[0].replace('TDK_PEC_', '')} {g[1]}"
        ax[0].plot([x["L_uh"] for x in xs], [x["thd"] for x in xs], "-", color=cor, lw=1.6, label=lab)
        v = [x for x in xs if x["valida"]]
        ax[0].plot([x["L_uh"] for x in v], [x["thd"] for x in v], "o", color=cor, ms=5)
        if g == grupos[0]:
            ax[1].plot([x["L_uh"] for x in xs], [x["queda"] for x in xs], ":", color="0.55", lw=1.4,
                       label="queda reativa no indutor ωL·I (não é o que o motor perde)")
            ax[1].plot([x["L_uh"] for x in xs], [x["insercao"] for x in xs], "-", color="0.25", lw=1.8,
                       label="perda de inserção (queda real na saída)")
        if v:
            ax[1].plot([x["L_uh"] for x in v], [x["insercao"] for x in v], "o", color=cor, ms=6, label=f"válido: {lab}")
    ax[0].axhline(5, color="0.4", ls="--", lw=1)
    ax[0].text(ax[0].get_xlim()[0], 5.1, " 5 % (prática / IEEE 519)", fontsize=8, color="0.3")
    ax[1].axhline(qmax, color="0.4", ls="--", lw=1)
    ax[1].text(ax[1].get_xlim()[0], qmax + 0.15, f" inserção máx. {qmax:g} % (MTE)", fontsize=8, color="0.3")
    lo, hi = est["criterios"].get("faixa_ref_uh") or est["criterios"]["faixa_mte_uh"]
    for a in ax:
        a.axvspan(lo, hi, color="#38a169", alpha=0.08)
        a.set_xlabel("Indutância (µH)")
        a.grid(alpha=0.25)
    ax[0].set_ylim(0, 12)
    ax[0].set_ylabel("THD de tensão no motor (%)")
    ax[1].set_ylabel("Tensão @ f máx, In (%)")
    ax[0].legend(fontsize=8)
    ax[1].legend(fontsize=8, loc="upper left")
    ax[0].set_title("THD no motor × L  (● = caso válido: aprovado, robusto e inserção OK)", fontsize=10)
    ax[1].set_title(f"Queda × L  (faixa verde = produtos de mercado: {lo}–{hi} µH)", fontsize=10)
    fig.tight_layout()
    fig.savefig(png, dpi=150)
    plt.close(fig)
    return png


def _rot(o):
    return f"{o['L_uh']:.0f} µH + {o['n_caps']} × {o['cap_id'].replace('TDK_PEC_', '')} {o['ligacao']}"


def gerar_docx(proj, cat, est, pasta_eng, _novo, _tabela, _bullets):
    import os
    from docx.shared import Cm
    d = _novo("Estudo de Opções – Mínimo de Capacitores", "Capacitor forçado (estoque) × indutância – varredura de casos", proj, cat)
    c = est["criterios"]
    d.add_heading("1. Objetivo e critérios", 1)
    d.add_paragraph(f"Usar o MENOR número possível do capacitor escolhido ({', '.join(est['caps'])}, ligação {', '.join(est['ligacoes'])}), "
                    "compensando com o indutor, sem queda de tensão excessiva e atendendo a todos os critérios da plataforma.")
    _bullets(d, [f"Varredura: indutância de {c['uk_varrido'][0]:g} a {c['uk_varrido'][1]:g} % da impedância nominal, passo {c['passo_uh']} µH, "
                 f"× nº de capacitores por ramo; fs {est['fs_khz']:g} kHz. Total de {len(est['linhas'])} casos simulados.",
                 f"Caso válido = aprovado em TODOS os critérios críticos (THD, ressonância, picos, capacitores IEC 61071, tensão no motor) "
                 f"+ robusto (L ±10 %, C ±5 %, cabo ¼×/4×, motor) + perda de inserção (queda real de tensão na saída, FP do motor) "
                 f"≤ {c['queda_max']:g} % na f máx (MTE). A queda reativa no indutor (ωL·I) é maior, mas não é a tensão que o motor perde.",
                 f"Regra de escolha (fixa): {c['regra']}. Faixa MTE para este filtro: {c['faixa_mte_uh'][0]}–{c['faixa_mte_uh'][1]} µH."])
    d.add_heading("2. Resultado", 1)
    rec = est["recomendada"]
    if rec:
        d.add_paragraph(f"RECOMENDADA: {_rot(rec)} – ressonância {rec['fr_hz']} Hz, THD no motor {rec['thd']} % (pior caso {rec['thd_pior']} %), "
                        f"perda de inserção {rec['insercao']} % (queda reativa no indutor {rec['queda']} %), ondulação {rec['ripple']} A p-p, "
                        f"{rec['icap']} A por capacitor.")
    else:
        d.add_paragraph("Nenhum caso atendeu a todos os critérios com este capacitor – liberar outro capacitor ou aumentar a queda admitida.")
    for a in est["abaixo"]:
        d.add_paragraph(f"Com {a['n_caps']} capacitores NÃO serve: {a['motivo']}.")
    d.add_heading("3. Opções para comparar", 1)
    if est["opcoes"]:
        _tabela(d, ["Opção", "uk (%)", "fr (Hz)", "fr/fs", "THD (%)", "THD pior (%)", "THD vazio (%)", "Inserção (%)", "Queda L (%)",
                    "Ondul. (A p-p)", "I cap (A)", "Custo (R$)"],
                [(("★ " if o is rec else "") + _rot(o), o["uk_pct"], o["fr_hz"], o["fr_fs"], o["thd"], o["thd_pior"], o["thd_vazio"],
                  o["insercao"], o["queda"], o["ripple"], o["icap"], f"{o['custo']:,}".replace(",", "."))
                 for o in est["opcoes"]], [4.0, 1.0, 1.1, 1.0, 1.0, 1.2, 1.2, 1.2, 1.1, 1.3, 1.0, 1.4], 7)
    png = grafico(est, os.path.join(pasta_eng, "opcoes_min_capacitores.png"))
    d.add_picture(png, width=Cm(17))
    d.add_heading("4. Todos os casos válidos", 1)
    val = sorted([x for x in est["linhas"] if x["valida"]], key=lambda x: (x["n_caps"], x["L_uh"]))
    _tabela(d, ["Caps", "L (µH)", "uk (%)", "fr (Hz)", "THD (%)", "THD pior (%)", "Inserção (%)", "Queda L (%)", "Custo (R$)"],
            [(x["n_caps"], f"{x['L_uh']:.0f}", x["uk_pct"], x["fr_hz"], x["thd"], x["thd_pior"], x["insercao"], x["queda"],
              f"{x['custo']:,}".replace(",", ".")) for x in val], [1.2, 1.4, 1.2, 1.4, 1.4, 1.6, 1.5, 1.4, 1.8], 8)
    d.add_heading("5. Referências", 1)
    _bullets(d, est["fontes"])
    d.add_paragraph("Antes de fabricar: a opção escolhida passa pela dupla checagem no ATP-EMTP (automática ao emitir o projeto no PC "
                    "com ATP) e pelo estudo de elementos finitos do indutor.")
    arq = os.path.join(pasta_eng, "Estudo_Opcoes_Minimo_Capacitores.docx")
    d.save(arq)
    return arq


def tabela_ui(est):
    """Linhas para st.dataframe na tela."""
    return [dict(Opção=("★ " if o is est["recomendada"] else "") + _rot(o), **{"fr (Hz)": o["fr_hz"], "THD motor (%)": o["thd"],
                 "THD pior (%)": o["thd_pior"], "Perda de inserção (%)": o["insercao"], "Queda no indutor (%)": o["queda"], "Ondulação (A p-p)": o["ripple"], "I cap (A)": o["icap"],
                 "Custo comp. (R$)": o["custo"]}) for o in est["opcoes"]]
