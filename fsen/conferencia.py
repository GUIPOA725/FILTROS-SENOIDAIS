"""Conferência da PROPOSTA do fornecedor (indutor e capacitores) contra a especificação da plataforma (v1.9.9).

Você digita o que o fornecedor DECLAROU; a plataforma:
- compara item a item com o que foi exigido na ET (com o porquê de cada critério);
- refaz o estudo térmico do painel com as perdas DECLARADAS do indutor e a ESR DECLARADA do capacitor;
- aponta o que ele NÃO declarou (sinal de que não considerou a alta frequência);
- emite o parecer (APROVADO / APROVADO COM RESSALVAS / INCOMPLETO / REPROVADO) em .docx e o e-mail de resposta ao fornecedor
  com as pendências e reprovações, cada uma com o motivo.
"""
import copy
import datetime as _dt
import json
import os

OK, ALERTA, REPROVA, PENDENTE = "OK", "ALERTA", "REPROVA", "PENDENTE"

CAMPOS_INDUTOR = [
    # chave, rótulo, unidade, tipo
    ("fornecedor", "Fornecedor", "", "txt"), ("proposta", "Nº da proposta / desenho", "", "txt"),
    ("l_uh", "Indutância nominal declarada", "µH", "num"), ("desequilibrio_pct", "Desequilíbrio entre fases", "%", "num"),
    ("l_pico_pct", "L no pico de operação (% do nominal)", "%", "num"), ("l_sobrec_pct", "L no pico de sobrecarga (% do nominal)", "%", "num"),
    ("perdas_60hz_w", "Perdas no cobre a 60 Hz", "W", "num"), ("perdas_hf_w", "Perdas de alta frequência (núcleo + cobre HF)", "W", "num"),
    ("perdas_total_w", "Perdas totais garantidas", "W", "num"), ("massa_kg", "Massa", "kg", "num"),
    ("classe_c", "Classe térmica (temperatura da classe)", "°C", "num"), ("elevacao_k", "Elevação média declarada", "K", "num"),
    ("chapa_mm", "Espessura da chapa", "mm", "num"), ("chapa_material", "Material da chapa", "", "txt"),
    ("n_entreferros", "Entreferros por coluna", "", "num"),
    ("condutor", "Tipo de condutor", "", ["não declarado", "fio redondo", "retangular", "fios em paralelo / Litz", "fita (folha)"]),
    ("material_enrol", "Material do enrolamento", "", ["não declarado", "cobre", "alumínio"]),
    ("dieletrico_kv", "Ensaio dielétrico (fase-terra)", "kV", "num"), ("vpi", "Impregnação VPI / a vácuo", "", "bool"),
    ("protecao_termica", "Termostato/PTC no enrolamento", "", "bool"),
    ("ensaio_aquecimento", "Ensaio de aquecimento", "", ["não oferece", "60 Hz senoidal", "com inversor / alta frequência"]),
    ("prototipo", "Aceita protótipo antes da série", "", "bool"), ("ensaio_rotina", "Relatório de rotina por nº de série", "", "bool"),
    ("dim_l", "Largura", "mm", "num"), ("dim_a", "Altura", "mm", "num"), ("dim_p", "Profundidade", "mm", "num"),
    ("preco", "Preço unitário", "R$", "num"), ("prazo_dias", "Prazo", "dias", "num"),
]
CAMPOS_CAPACITOR = [
    ("fornecedor", "Fornecedor", "", "txt"), ("codigo", "Código ofertado", "", "txt"),
    ("norma", "Norma do produto", "", ["não declarada", "IEC 61071 (eletrônica de potência)", "IEC 60831 (correção de FP)", "outra"]),
    ("uf", "Capacitância", "µF", "num"), ("v_rms", "Tensão nominal URMS", "V", "num"), ("un_pico_v", "Tensão de pico recorrente UN", "V", "num"),
    ("imax_a", "Corrente RMS máxima Imax", "A", "num"), ("ipk_a", "Corrente de pico repetitiva Î", "A", "num"),
    ("esr_mohm", "ESR (na fs ou 10 kHz)", "mΩ", "num"), ("t_hot_c", "Ponto quente máximo", "°C", "num"), ("vida_h", "Vida declarada", "h", "num"),
    ("sobrepressao", "Dispositivo de sobrepressão", "", "bool"), ("data_fab_meses", "Idade do lote", "meses", "num"),
    ("certificado_lote", "Certificado de rotina do lote", "", "bool"), ("preco", "Preço unitário", "R$", "num"),
]


def _v(d, k):
    x = (d or {}).get(k)
    if x in (None, "", "não declarado", "não declarada"):
        return None
    return x


def carregar_projeto(pasta, cat):
    """Reconstrói e ressimula o projeto salvo (pedido.json + 01_Engenharia/projeto.json)."""
    from .modelos import Pedido
    from .dimensionamento import projeto_manual
    ped = Pedido.from_dict(json.load(open(os.path.join(pasta, "pedido.json"), encoding="utf-8")))
    pj = json.load(open(os.path.join(pasta, "01_Engenharia", "projeto.json"), encoding="utf-8"))
    b, am = pj.get("banco") or {}, pj.get("amortecimento") or {}
    tipo = am.get("tipo") if am else None
    pr = projeto_manual(ped, cat, float(pj.get("fs_hz", 4000)) / 1000, float(pj["l1"]["l_uh"]), b.get("cap_id"),
                        b.get("ligacao", "Estrela"), int(b.get("n_por_ramo", 1)),
                        rd_ramo_ohm=float(am.get("r_ramo_ohm", 0.0)) if tipo == "serie" else 0.0,
                        L2_uH=float((pj.get("l2") or {}).get("l_uh") or 0.0),
                        amort_tipo=("nenhum" if not tipo else ("rc" if tipo == "rc_paralelo" else "serie")),
                        nd_por_ramo=int(am.get("n_cd_por_ramo", 0)) if tipo == "rc_paralelo" else 0,
                        rdp_ramo_ohm=float(am.get("r_ramo_ohm", 0.0)) if tipo == "rc_paralelo" else 0.0)
    return pr


def _item(itens, nome, declarado, exigido, status, porque):
    itens.append(dict(item=nome, declarado=declarado, exigido=exigido, status=status, porque=porque))


def conferir_indutor(proj, arr, cat, decl):
    from .spec_indutor import requisitos, I_PROTOTIPO_A
    from .termico import estudo_termico
    ped = proj.pedido
    L = proj.l1
    R = requisitos(L, proj, arr, cat, ped)
    t = cat.get("termico", {})
    classe_req = int(t.get("classe_indutor_c", 155))
    itens = []
    f = lambda k: _v(decl, k)

    x = f("l_uh")
    if x is None:
        _item(itens, "Indutância", "não declarada", f"{R['l_uh']:.0f} µH ±5 %", PENDENTE, "Sem ela não dá para confirmar a ressonância.")
    else:
        dif = 100 * (float(x) - R["l_uh"]) / R["l_uh"]
        _item(itens, "Indutância", f"{x:g} µH ({dif:+.1f} %)", f"{R['l_uh']:.0f} µH ±5 %", OK if abs(dif) <= 5 else REPROVA,
              "Fora de ±5 % muda a frequência de ressonância e a ondulação simuladas.")
    x = f("desequilibrio_pct")
    _item(itens, "Desequilíbrio entre fases", "não declarado" if x is None else f"{x:g} %", "≤ 3 %",
          PENDENTE if x is None else (OK if x <= 3 else REPROVA), "Desequilíbrio gera tensões diferentes no motor.")
    x = f("l_pico_pct")
    _item(itens, f"Linearidade no pico ({R['ipk_sat']:.0f} A)", "não declarada (sem curva L × I)" if x is None else f"{x:g} %", "≥ 90 %",
          PENDENTE if x is None else (OK if x >= 90 else REPROVA),
          "Se saturar, a indutância cai, a ondulação dispara e o inversor pode desarmar.")
    x = f("l_sobrec_pct")
    _item(itens, f"Linearidade na sobrecarga ({R['ipk_sobrec']:.0f} A)", "não declarada" if x is None else f"{x:g} %", "≥ 70 %",
          PENDENTE if x is None else (OK if x >= 70 else REPROVA), "Partida do motor / sobrecarga de 1 minuto.")

    pt, ph, p60 = f("perdas_total_w"), f("perdas_hf_w"), f("perdas_60hz_w")
    if pt is None:
        _item(itens, "Perdas totais garantidas", "não declaradas", f"≤ {R['perdas_meta']:.0f} W (máx. {R['perdas']:.0f} W)", PENDENTE,
              "Sem perdas garantidas não há como validar a ventilação do painel.")
    else:
        st = OK if pt <= R["perdas_meta"] else (ALERTA if pt <= R["perdas"] else REPROVA)
        _item(itens, "Perdas totais garantidas", f"{pt:g} W", f"≤ {R['perdas_meta']:.0f} W desejado; máx. {R['perdas']:.0f} W", st,
              "Acima do máximo o estudo térmico do painel deixa de valer (ver recálculo abaixo).")
    if ph is None:
        _item(itens, "Perdas de alta frequência declaradas", "NÃO declaradas", "declarar núcleo + cobre HF", PENDENTE,
              "Indício de que o projeto considerou só 60 Hz – é exatamente o erro que esta conferência quer pegar.")
    else:
        frac = 100 * ph / pt if pt else 0
        st = OK if (R["ripple_rel"] < 15 or frac >= 15) else ALERTA
        _item(itens, "Perdas de alta frequência declaradas", f"{ph:g} W ({frac:.0f} % do total)" if pt else f"{ph:g} W",
              "coerente com a ondulação" + (f" ({R['ripple_rel']:.0f} % do pico)" if R["ripple_rel"] else ""), st,
              "Com ondulação alta, perdas HF muito pequenas no total são pouco prováveis – pedir o cálculo.")
    m = f("massa_kg")
    fx = R["ref_faixa"]
    if m is None:
        _item(itens, "Massa", "não declarada", "declarar", PENDENTE, "Indicador de folga térmica (comparar com o mercado).")
    else:
        lo = fx["massa_kg"][0] if fx else None
        st = OK if (lo is None or m >= 0.7 * lo) else ALERTA
        _item(itens, "Massa", f"{m:g} kg", (f"mercado {fx['massa_kg'][0]:.0f}–{fx['massa_kg'][1]:.0f} kg (filtro completo); "
                                            f"plataforma ≈ {R['massa']:.0f} kg") if fx else f"plataforma ≈ {R['massa']:.0f} kg", st,
              "Massa muito abaixo do mercado indica núcleo/cobre reduzidos e perdas de alta frequência maiores.")
    c = f("classe_c")
    _item(itens, "Classe térmica", "não declarada" if c is None else f"{c:g} °C", f"≥ {classe_req} °C", PENDENTE if c is None else
          (OK if c >= classe_req else REPROVA), "O estudo térmico do filtro foi feito com esta classe; menor reduz a vida da isolação.")
    e = f("elevacao_k")
    if e is not None:
        lim = int(t.get("elevacao_indutor_k", 100))
        _item(itens, "Elevação média declarada", f"{e:g} K", f"≤ {lim} K", OK if e <= lim else REPROVA, "Limite da classe/projeto térmico.")
    ch = f("chapa_mm")
    _item(itens, "Espessura da chapa", "não declarada" if ch is None else f"{ch:g} mm ({f('chapa_material') or '?'})", "0,23–0,30 mm (recomendado)",
          PENDENTE if ch is None else (OK if ch <= 0.30 else (ALERTA if ch <= 0.35 else REPROVA)),
          "Perdas por correntes parasitas no núcleo crescem com o quadrado da espessura e com a frequência.")
    ne = f("n_entreferros")
    cond = f("condutor")
    _item(itens, "Entreferros por coluna", "não declarado" if ne is None else f"{ne:g}", "2 a 4 (recomendado)",
          PENDENTE if ne is None else (OK if ne >= 2 else ALERTA),
          "Um entreferro único e grande espalha mais fluxo de alta frequência sobre a bobina (ponto quente).")
    _item(itens, "Tipo de condutor", cond or "não declarado", "evitar fita na região do entreferro",
          PENDENTE if cond is None else (ALERTA if (cond.startswith("fita") and (ne or 1) < 2) else OK),
          "Campo espraiado bate na face larga da fita e gera correntes parasitas.")
    me = f("material_enrol")
    if me:
        _item(itens, "Material do enrolamento", me, "cobre ou alumínio (declarar)", OK,
              "Alumínio é aceitável se as perdas e a elevação garantidas atenderem.")
    dk = f("dieletrico_kv")
    _item(itens, "Ensaio dielétrico", "não declarado" if dk is None else f"{dk:g} kV", "≥ 2,5 kV (3 kV fase-terra)",
          PENDENTE if dk is None else (OK if dk >= 2.5 else REPROVA), "Padrão dos fabricantes de filtro; bordas de kV/µs do inversor.")
    for k, nome, porque in (("vpi", "Impregnação VPI / a vácuo", "Evita vibração e ruído em alta frequência."),
                            ("protecao_termica", "Proteção térmica no enrolamento", "Desliga o inversor se a ventilação falhar."),
                            ("ensaio_rotina", "Relatório de rotina por nº de série", "Rastreabilidade de L, resistência e dielétrico.")):
        x = decl.get(k)
        _item(itens, nome, "sim" if x else ("não" if x is False else "não declarado"), "sim", OK if x else (ALERTA if x is False else PENDENTE), porque)
    ea = f("ensaio_aquecimento")
    req_prot = R["In"] >= I_PROTOTIPO_A
    if ea is None or ea == "não oferece":
        st = REPROVA if req_prot else ALERTA
    elif ea.startswith("60 Hz"):
        st = ALERTA
    else:
        st = OK
    _item(itens, "Ensaio de aquecimento", ea or "não declarado", "com inversor (ou perdas HF somadas)", st,
          "É o único ensaio que mostra o efeito da ondulação; a 60 Hz puro subestima o aquecimento.")
    if req_prot:
        x = decl.get("prototipo")
        _item(itens, "Protótipo antes da série", "sim" if x else ("não" if x is False else "não declarado"), "sim",
              OK if x else (REPROVA if x is False else PENDENTE), f"Exigido para In ≥ {I_PROTOTIPO_A:.0f} A.")
    dims = [f("dim_l"), f("dim_a"), f("dim_p")]
    if all(v is not None for v in dims):
        lim = (arr.caixa_l - 150, 700, arr.caixa_p - 150)
        okd = all(a <= b for a, b in zip(dims, lim))
        _item(itens, "Dimensões", "×".join(f"{v:g}" for v in dims) + " mm", "≤ " + "×".join(str(v) for v in lim) + " mm",
              OK if okd else REPROVA, "Precisa caber no armário com espaço para ventilação.")

    term = None
    if pt is not None:
        p2 = copy.deepcopy(proj)
        p2.l1.perdas_w = float(pt)
        try:
            term = estudo_termico(p2, arr, cat)
            ind = next((c for c in term["componentes"] if "Indutor L1" in c["componente"]), None)
            if ind:
                _item(itens, "RECÁLCULO TÉRMICO com as perdas declaradas", f"{ind['t_componente_C']:.0f} °C no ponto quente "
                      f"(ar local {ind['t_ar_local_C']:.0f} °C, {term['n_ventiladores']} ventilador(es))", ind["limite"],
                      OK if ind["ok"] else REPROVA, "Estudo térmico do painel refeito pela plataforma com o valor do fornecedor.")
            if not term["aprovado"]:
                _item(itens, "Painel completo com as perdas declaradas", "algum limite térmico excedido", "todos os limites", ALERTA,
                      "Pode exigir mais ventilação – ver tabela do estudo térmico.")
        except Exception as ex:
            _item(itens, "Recálculo térmico", f"não foi possível ({ex})", "", ALERTA, "")
    return dict(itens=itens, termico=term, parecer=_parecer(itens), R=R)


def conferir_capacitor(proj, cat, decl):
    from .spec_capacitor import requisitos
    from .dimensionamento import estresse_capacitor
    ped = proj.pedido
    R = requisitos(proj, cat, ped, int(ped.get("quantidade", 1) or 1))
    b, lc, capd = R["b"], R["lc"], R["capd"]
    itens = []
    f = lambda k: _v(decl, k)
    cod = f("codigo")
    _item(itens, "Código ofertado", cod or "não informado", b.pn, PENDENTE if not cod else (OK if cod.replace(" ", "") == b.pn else ALERTA),
          "Substituto só com datasheet aprovado.")
    nm = f("norma")
    _item(itens, "Norma", nm or "não declarada", "IEC 61071", PENDENTE if nm is None else (OK if "61071" in nm else REPROVA),
          "Capacitor de correção de FP (IEC 60831) aquece com a corrente de alta frequência e perde vida rápido.")
    x = f("uf")
    _item(itens, "Capacitância", "não declarada" if x is None else f"{x:g} µF", f"{b.uf_unit:g} µF", PENDENTE if x is None else
          (OK if abs(x - b.uf_unit) <= 0.05 * b.uf_unit else REPROVA), "Define a ressonância.")
    x = f("v_rms")
    _item(itens, "URMS", "não declarada" if x is None else f"{x:g} V", f"≥ {b.v_unit:g} V", PENDENTE if x is None else
          (OK if x >= b.v_unit else REPROVA), "Margem para rede +10 %.")
    vreq = R["vpk_req"]
    x = f("un_pico_v")
    _item(itens, "UN (pico recorrente)", "não declarada" if x is None else f"{x:g} V", f"≥ {vreq:.0f} V", PENDENTE if x is None else
          (OK if x >= vreq else REPROVA), "A ondulação soma ao pico da fundamental.")
    ireq = R["imax_req"]
    x = f("imax_a")
    _item(itens, "Imax RMS", "não declarada" if x is None else f"{x:g} A", f"≥ {ireq:.1f} A (operação {R['i_rms']:.1f} A)",
          PENDENTE if x is None else (OK if x >= ireq else (ALERTA if x >= R["i_rms"] else REPROVA)), "Aquecimento por ESR.")
    pkreq = R["ipk_nec"] * 1.5
    x = f("ipk_a")
    _item(itens, "Î pico repetitivo", "não declarada" if x is None else f"{x:g} A", f"≥ {pkreq:.0f} A", PENDENTE if x is None else
          (OK if x >= pkreq else REPROVA), "Bordas rápidas de tensão (dv/dt).")
    x = f("sobrepressao")
    _item(itens, "Dispositivo de sobrepressão", "sim" if decl.get("sobrepressao") else ("não" if decl.get("sobrepressao") is False else "não declarado"),
          "sim", OK if decl.get("sobrepressao") else (REPROVA if decl.get("sobrepressao") is False else PENDENTE), "Falha segura no fim de vida.")
    x = f("data_fab_meses")
    if x is not None:
        _item(itens, "Idade do lote", f"{x:g} meses", "≤ 12 meses", OK if x <= 12 else ALERTA, "Vida em estoque.")
    esr = f("esr_mohm")
    if esr is None:
        _item(itens, "ESR", "não declarada", "declarar", PENDENTE, "Sem a ESR não dá para calcular perdas e ponto quente.")
    else:
        cap2 = dict(capd, esr_mohm=float(esr))
        if f("t_hot_c"):
            cap2["t_hotspot_max_c"] = float(f("t_hot_c"))
        try:
            e = estresse_capacitor(cat, cap2, b.ligacao, b.n_por_ramo, proj.pontos)
            th_max = float(f("t_hot_c") or lc["t_hot"])
            _item(itens, "RECÁLCULO do ponto quente com a ESR declarada", (f"{e['t_hotspot_c']:.0f} °C; vida ≈ {e['vida_h']:,.0f} h".replace(",", ".") if e["vida_h"] < 200000 else f"{e['t_hotspot_c']:.0f} °C; vida > 200.000 h"),
                  f"≤ {th_max:g} °C", OK if e["t_hotspot_c"] <= th_max else REPROVA, "Perdas = ESR × corrente² (incluindo a alta frequência).")
        except Exception as ex:
            _item(itens, "Recálculo do capacitor", f"não foi possível ({ex})", "", ALERTA, "")
    x = decl.get("certificado_lote")
    _item(itens, "Certificado do lote", "sim" if x else ("não" if x is False else "não declarado"), "sim", OK if x else ALERTA,
          "Capacitância e ensaio de tensão por lote.")
    return dict(itens=itens, parecer=_parecer(itens), R=R)


def _parecer(itens):
    s = [i["status"] for i in itens]
    if REPROVA in s:
        return "REPROVADO"
    if PENDENTE in s:
        return "INCOMPLETO – pedir os dados pendentes"
    if ALERTA in s:
        return "APROVADO COM RESSALVAS"
    return "APROVADO"


def gerar_parecer(proj, arr, cat, pasta_proj, componente, decl, res):
    """Grava o parecer .docx + e-mail de resposta ao fornecedor em 03_Fornecedores. Retorna (docx, txt)."""
    from .documentos import _novo, _tabela, _sombra
    pasta = os.path.join(pasta_proj, "03_Fornecedores")
    os.makedirs(pasta, exist_ok=True)
    forn = (decl.get("fornecedor") or "fornecedor").strip()
    tag = "Indutor" if componente == "indutor" else "Capacitores"
    agora = _dt.datetime.now()
    d = _novo(f"Parecer Técnico – Proposta de {tag}", f"{forn} – {decl.get('proposta') or decl.get('codigo') or ''}", proj, cat)
    p = d.add_paragraph()
    r = p.add_run(f"PARECER: {res['parecer']}")
    r.bold = True
    d.add_paragraph(f"Conferência feita pela plataforma em {agora:%d/%m/%Y %H:%M} com os dados declarados pelo fornecedor. Cada item "
                    "traz o motivo do critério.")
    t = _tabela(d, ["Item", "Declarado", "Exigido", "Situação", "Por quê"],
                [(i["item"], i["declarado"], i["exigido"], i["status"], i["porque"]) for i in res["itens"]], [3.6, 3.4, 3.2, 1.8, 5.0], 8)
    cores = {OK: "C6EFCE", ALERTA: "FFEB9C", REPROVA: "FFC7CE", PENDENTE: "DDEBF7"}
    for k, i in enumerate(res["itens"]):
        try:
            _sombra(t.rows[k + 1].cells[3], cores[i["status"]])
        except Exception:
            pass
    term = res.get("termico")
    if term:
        d.add_heading("Estudo térmico refeito com as perdas declaradas", 1)
        _tabela(d, ["Componente", "Perdas (W)", "Ar local (°C)", "Componente (°C)", "Limite", "OK"],
                [(c["componente"], c["perdas_W"], c["t_ar_local_C"], c["t_componente_C"], c["limite"], "sim" if c["ok"] else "NÃO")
                 for c in term["componentes"]], [4.5, 1.8, 2, 2.3, 4, 1.2], 8)
    d.add_heading("Dados declarados (registro)", 1)
    _tabela(d, ["Campo", "Valor"], [(k, str(v)) for k, v in decl.items() if v not in (None, "")], [7, 10], 8)
    slug = "".join(ch for ch in forn if ch.isalnum())[:20] or "fornecedor"
    cam = os.path.join(pasta, f"Parecer_Proposta_{tag}_{slug}_{agora:%Y%m%d_%H%M}.docx")
    d.save(cam)
    json.dump(dict(componente=componente, declarado=decl, parecer=res["parecer"], itens=res["itens"], data=agora.isoformat()),
              open(cam.replace(".docx", ".json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
    pend = [i for i in res["itens"] if i["status"] in (PENDENTE, REPROVA, ALERTA)]
    linhas = []
    for i in pend:
        acao = {PENDENTE: "favor declarar", REPROVA: "não atende – favor rever", ALERTA: "favor esclarecer"}[i["status"]]
        linhas.append(f"- {i['item']}: {acao}. Exigido: {i['exigido']}; declarado: {i['declarado']}. Motivo: {i['porque']}")
    corpo = (f"Olá, tudo bem?\n\nObrigado pela proposta {decl.get('proposta') or ''}. Fizemos a conferência técnica "
             f"({res['parecer']}). Para seguir, precisamos dos pontos abaixo:\n\n" + ("\n".join(linhas) or "- Nenhuma pendência.") +
             "\n\nLembrando que o componente trabalha em filtro senoidal na saída de inversor: há corrente/tensão de alta frequência "
             "sobreposta à fundamental, conforme a ET e a figura de forma de onda enviadas.\n")
    txt = cam.replace(".docx", "_Email_Resposta.txt")
    open(txt, "w", encoding="utf-8").write(f"Assunto: Conferência técnica da proposta – {tag} ({forn})\n\n{corpo}")
    return cam, txt
