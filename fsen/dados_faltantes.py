"""Dados faltantes no pedido: checklist técnico, análise de sensibilidade do projeto escolhido e e-mail ao cliente.

Para cada dado que não veio no pedido, a plataforma:
  1. registra a premissa adotada;
  2. quando o dado é simulável, refaz o projeto escolhido (mesmo L, C, fs) com valores plausíveis do dado e mede o impacto
     (aprovação, THD, corrente no capacitor, temperatura do indutor/capacitor);
  3. classifica: CRÍTICO (pode reprovar/alterar o filtro), IMPORTANTE (muda margens > 10 %) ou CONFIRMAR (baixo impacto);
  4. gera o e-mail ao cliente e o questionário técnico, ordenados por prioridade.
"""
from __future__ import annotations
import copy
import math
import re
from dataclasses import replace
from typing import Any, Dict, List, Optional

from .modelos import Pedido

# ---------------------------------------------------------------------------------------------------------------- checklist
# campo(s), pergunta ao cliente, por que importa, criticidade base (quando não simulável), grupo
CHECKLIST = [
    # --- inversor
    dict(id="inv_modelo", campos=["inversor"], grupo="Inversor de frequência", base="CRÍTICO",
         pergunta="Fabricante, modelo completo (código de compra) e versão de firmware do inversor",
         porque="Define frequências de chaveamento disponíveis, derating e o ajuste obrigatório para operar com filtro senoidal"),
    dict(id="inv_fs", campos=["fs_khz"], grupo="Inversor de frequência", base="CRÍTICO",
         pergunta="Frequência de chaveamento configurada hoje e se pode ser FIXADA (sem redução automática por temperatura)",
         porque="O filtro é sintonizado para uma fs mínima; se o inversor reduzir a fs, a ressonância do filtro é excitada"),
    dict(id="inv_controle", campos=["inversor_controle"], grupo="Inversor de frequência", base="CRÍTICO",
         pergunta="Modo de controle do motor (escalar V/f, vetorial com/sem encoder, DTC)",
         porque="DTC e alguns vetoriais não têm fs fixa ou precisam de parametrização específica para filtro senoidal"),
    dict(id="inv_corr", campos=["inversor_corrente_a"], grupo="Inversor de frequência", base="IMPORTANTE",
         pergunta="Corrente nominal do inversor (uso normal/pesado) e capacidade de sobrecarga",
         porque="A corrente capacitiva e a ondulação do filtro somam-se à corrente do motor no inversor"),
    dict(id="inv_emc", campos=["inversor_filtro_emc"], grupo="Inversor de frequência", base="IMPORTANTE",
         pergunta="Se o inversor tem filtro EMC interno (capacitores para o terra) ligado",
         porque="Fecha o caminho da corrente de modo comum/terra e define a tensão nos mancais do motor"),
    dict(id="fmax", campos=["f_saida_max_hz", "f_saida_min_hz"], grupo="Inversor de frequência", base="IMPORTANTE",
         pergunta="Faixa real de frequência de operação (mínima e máxima) e se há operação acima de 60 Hz",
         porque="A ressonância deve ficar ≥ 10× a frequência máxima e a queda de tensão é maior na f máx"),
    # --- motor
    dict(id="motor_placa", campos=["motor_corrente_a", "motor_cv", "motor_kw"], grupo="Motor", base="CRÍTICO",
         pergunta="Dados de placa do motor: potência, tensão, corrente, FP, rendimento, rpm, polos e fator de serviço (foto da placa)",
         porque="Corrente e FP definem o indutor, a queda de tensão e o aquecimento; a dispersão do motor entra na ressonância"),
    dict(id="motor_fp", campos=["motor_fp"], grupo="Motor", base="IMPORTANTE",
         pergunta="Fator de potência do motor na carga real (ou corrente medida em operação)",
         porque="Muda a tensão necessária no inversor (sobremodulação) e a corrente no indutor"),
    dict(id="motor_inv", campos=["motor_para_inversor"], grupo="Motor", base="CONFIRMAR",
         pergunta="Se o motor é próprio para inversor (NEMA MG1 Parte 31 / IEC TS 60034-25) e classe de isolamento",
         porque="Define os limites de Vpico e dv/dt nos terminais"),
    dict(id="mancal", campos=["mancal_isolado"], grupo="Motor", base="CONFIRMAR",
         pergunta="Se o motor tem mancal isolado ou escova de aterramento do eixo",
         porque="O filtro senoidal não reduz a tensão de modo comum que causa corrente nos mancais"),
    dict(id="carga", campos=["carga_tipo", "aplicacao"], grupo="Motor", base="CONFIRMAR",
         pergunta="Tipo de carga (bomba/ventilador – torque quadrático – ou torque constante) e regime de operação",
         porque="Define a corrente nas frequências baixas e o regime térmico"),
    # --- cabo
    dict(id="cabo_comp", campos=["cabo_m"], grupo="Cabos", base="CRÍTICO",
         pergunta="Comprimento real do cabo inversor → filtro e filtro → motor (m)",
         porque="A capacitância do cabo soma-se à do filtro, muda a ressonância, a corrente capacitiva e a corrente de terra"),
    dict(id="cabo_secao", campos=["cabo_secao_mm2", "cabo_paralelos"], grupo="Cabos", base="IMPORTANTE",
         pergunta="Seção do cabo, número de cabos em paralelo por fase e tipo de condutor de proteção (PE)",
         porque="Define os terminais do filtro e os parâmetros R-L-C do cabo na simulação"),
    dict(id="cabo_tipo", campos=["cabo_tipo", "cabo_blindado"], grupo="Cabos", base="IMPORTANTE",
         pergunta="Tipo do cabo (blindado simétrico para inversor ou unipolar em eletrocalha) e fabricante/modelo",
         porque="A capacitância fase-terra muda até 3× entre tipos e define a corrente de terra"),
    # --- instalação
    dict(id="amb", campos=["amb_max_c"], grupo="Local de instalação", base="CRÍTICO",
         pergunta="Temperatura ambiente máxima no local do painel (°C)",
         porque="O aquecimento é o maior risco do filtro: define ventilação, classe do indutor e vida dos capacitores"),
    dict(id="alt", campos=["altitude_m"], grupo="Local de instalação", base="IMPORTANTE",
         pergunta="Altitude do local (m) e se o ambiente tem poeira, umidade ou atmosfera agressiva",
         porque="Acima de 1000 m o ar refrigera menos; poeira define o grau de proteção e os filtros de ar"),
    dict(id="ip", campos=["ip", "instalacao"], grupo="Local de instalação", base="CONFIRMAR",
         pergunta="Instalação abrigada/ao tempo e grau de proteção exigido (IP)",
         porque="Define o tipo de caixa, a ventilação e o custo"),
    dict(id="dim", campos=["dim_max_mm", "entrada_cabos"], grupo="Local de instalação", base="CONFIRMAR",
         pergunta="Espaço disponível (largura × altura × profundidade) e entrada dos cabos (por baixo ou por cima)",
         porque="Define a caixa metálica e o arranjo interno"),
    dict(id="aux", campos=["alim_aux_v"], grupo="Local de instalação", base="CONFIRMAR",
         pergunta="Tensão auxiliar disponível para os ventiladores (ex.: 220 Vca) ou se devemos prever transformador",
         porque="Ventilação forçada é necessária para as perdas do filtro"),
    dict(id="aterr", campos=["aterramento"], grupo="Local de instalação", base="IMPORTANTE",
         pergunta="Sistema de aterramento da rede (TN-S, TN-C, IT – neutro isolado ou aterrado por resistência)",
         porque="Em rede IT o filtro EMC do inversor e o centro-estrela do filtro exigem cuidados específicos"),
    # --- requisitos
    dict(id="req", campos=["vpk_max_v", "dvdt_max_v_us"], grupo="Requisitos", base="CONFIRMAR",
         pergunta="Limites exigidos no motor (Vpico, dv/dt, THD) e normas/especificação técnica do cliente final",
         porque="São os critérios de aceitação do filtro"),
]

# valores plausíveis testados quando o dado falta (cenários de sensibilidade)
CENARIOS = {
    "inv_fs": [("fs real 2 kHz (padrão de fábrica de vários inversores)", dict(fs_khz=2.0))],
    "cabo_comp": [("cabo de 100 m", dict(ped=dict(cabo_m=100))), ("cabo de 200 m", dict(ped=dict(cabo_m=200)))],
    "cabo_tipo": [("cabo não blindado (unipolar em eletrocalha)", dict(ped=dict(cabo_blindado=False)))],
    "amb": [("ambiente 45 °C", dict(amb=45)), ("ambiente 50 °C", dict(amb=50))],
    "alt": [("altitude 2000 m (−20 % de refrigeração)", dict(vent=0.8))],
    "motor_fp": [("FP do motor 0,80", dict(ped=dict(motor_fp=0.80)))],
    "motor_placa": [("dispersão do motor 0,10 pu", dict(lm=0.10)), ("dispersão do motor 0,20 pu", dict(lm=0.20))],
    "fmax": [("operação até 66 Hz", dict(ped=dict(f_saida_max_hz=66)))],
}


def _informado(ped: Pedido, campo: str) -> bool:
    if ped.informados:
        return campo in ped.informados
    v = getattr(ped, campo, None)
    padrao = Pedido.__dataclass_fields__[campo].default
    return v not in (None, "", 0, []) and v != padrao


def itens_faltantes(ped: Pedido) -> List[Dict[str, Any]]:
    out = []
    for it in CHECKLIST:
        falt = [c for c in it["campos"] if not _informado(ped, c)]
        # item considerado faltante quando nenhum dos campos veio (ou, p/ grupos de 2, quando falta o principal)
        if len(falt) == len(it["campos"]) or (it["id"] in ("cabo_secao", "fmax", "dim") and it["campos"][0] in falt):
            out.append(dict(it, faltando=falt))
    return out


# ---------------------------------------------------------------------------------------------------------------- sensibilidade
def _metricas(proj):
    def num(item_ini):
        v = next((x.valor for x in proj.verificacoes if x.item.startswith(item_ini)), None)
        m = re.search(r"[-\d.]+", v or "")
        return float(m.group()) if m else None
    return dict(aprovado=all(v.ok for v in proj.verificacoes if v.critico),
                falhas=[v.item for v in proj.verificacoes if v.critico and not v.ok],
                thd=max(p["thd_v_saida_pct"] for p in proj.pontos), icap=proj.banco.i_unit_rms,
                fr=proj.fr_hz, t_ind=num("Térmico – Indutor"), t_cap=num("Térmico – Capacitores"),
                vpk=max(p.get("vpk_motor", p["vpk_saida"]) for p in proj.pontos))


def _rodar(proj, cat, ped: Pedido, cen: Dict[str, Any]):
    from .dimensionamento import projeto_manual, config_de_projeto
    from .mecanica import projetar_arranjo
    from .termico import aplicar_termico
    cfg = config_de_projeto(proj)
    c2 = copy.deepcopy(cat)
    p2 = Pedido.from_dict({**ped.to_dict(), **cen.get("ped", {})})
    if "fs_khz" in cen:
        cfg["fs_khz"] = cen["fs_khz"]
    if "amb" in cen:
        c2["projeto_padrao"]["amb_max_c"] = cen["amb"]
        c2.setdefault("termico", {})["amb_max_c"] = cen["amb"]
    if "vent" in cen:
        c2.setdefault("termico", {})["fator_filtro_vent"] = c2.get("termico", {}).get("fator_filtro_vent", 0.6) * cen["vent"]
    if "lm" in cen:
        c2.setdefault("motor_modelo", {})["l_disp_pu"] = cen["lm"]
    pr = projeto_manual(p2, c2, detalhado=False, **cfg)
    arr = projetar_arranjo(pr, c2)
    aplicar_termico(pr, arr, c2)
    return _metricas(pr)


def analisar(proj, cat, ped: Optional[Pedido] = None, log=lambda m: None) -> Dict[str, Any]:
    """Lista os dados faltantes, roda a sensibilidade do projeto escolhido e classifica a prioridade de cada item."""
    ped = ped or (Pedido.from_dict(proj.pedido) if isinstance(proj.pedido, dict) else proj.pedido)
    try:
        base = _rodar(proj, cat, ped, {})          # mesma rotina dos cenários (inclui estudo térmico)
    except Exception:
        base = _metricas(proj)
    itens = itens_faltantes(ped)
    for it in itens:
        it["cenarios"] = []
        prio = it["base"]
        for nome, cen in CENARIOS.get(it["id"], []):
            try:
                m = _rodar(proj, cat, ped, cen)
            except Exception as e:  # cenário inviável não bloqueia
                log(f"   sensibilidade '{nome}': {e}")
                continue
            d = lambda k: (100 * (m[k] - base[k]) / base[k]) if (m.get(k) is not None and base.get(k)) else 0.0
            var = max(abs(d("thd")), abs(d("icap")), abs(d("t_ind") if base.get("t_ind") else 0), abs(d("vpk")))
            efeito = ("REPROVA: " + "; ".join(f.split(" (")[0] for f in m["falhas"][:3])) if not m["aprovado"] else \
                     f"aprovado (variação máx. {var:.0f} %)"
            it["cenarios"].append(dict(cenario=nome, aprovado=m["aprovado"], efeito=efeito, thd=round(m["thd"], 2),
                                       icap=round(m["icap"], 2), t_ind=m["t_ind"], t_cap=m["t_cap"], var_pct=round(var, 1)))
            if not m["aprovado"]:
                prio = "CRÍTICO"
            elif var > 10 and prio == "CONFIRMAR":
                prio = "IMPORTANTE"
        it["prioridade"] = prio
    ordem = {"CRÍTICO": 0, "IMPORTANTE": 1, "CONFIRMAR": 2}
    itens.sort(key=lambda x: ordem[x["prioridade"]])
    premissas = _premissas(ped, proj, cat)
    return dict(itens=itens, base=base, premissas=premissas,
                n_criticos=sum(1 for i in itens if i["prioridade"] == "CRÍTICO"))


def _premissas(ped, proj, cat):
    pp = cat["projeto_padrao"]
    s = proj.sistema.get("_info", {}) if isinstance(getattr(proj, "sistema", None), dict) else {}
    return {
        "inv_fs": f"fs fixa {proj.fs_hz / 1000:g} kHz",
        "amb": f"{pp.get('amb_max_c', 40)} °C",
        "alt": "≤ 1000 m",
        "cabo_comp": f"{ped.cabo_m or cat.get('cabo_comprimento_padrao_m', 30):g} m",
        "cabo_secao": "dimensionado pela corrente (NBR 5410)",
        "cabo_tipo": "blindado simétrico para inversor",
        "motor_fp": f"FP {ped.motor_fp}",
        "motor_placa": "dispersão 0,15 pu (motor de indução típico)",
        "inv_controle": "controle escalar V/f com fs fixa",
        "inv_emc": "filtro EMC interno ligado (rede TN)",
        "aterr": "TN-S",
        "aux": "220 Vca disponível",
        "ip": ped.ip,
        "dim": "sem restrição de espaço",
        "fmax": f"{ped.f_saida_min_hz:g}–{ped.f_saida_max_hz:g} Hz",
    }


# ---------------------------------------------------------------------------------------------------------------- e-mail
def email_cliente(analise: Dict[str, Any], proj, cat) -> str:
    ped = proj.pedido if isinstance(proj.pedido, dict) else proj.pedido.to_dict()
    emp = cat["empresa"]
    nome = (ped.get("contato") or "").split(" ")[0] or "prezado(a)"
    from .desenhos import proj_codigo
    cod = proj_codigo(proj)
    grupos = {"CRÍTICO": [], "IMPORTANTE": [], "CONFIRMAR": []}
    for it in analise["itens"]:
        grupos[it["prioridade"]].append(it)
    pr = analise["premissas"]
    L = [f"Para: {ped.get('email_contato') or ''}",
         f"Assunto: {ped.get('referencia') or 'Filtro senoidal'} – dados técnicos para confirmar o dimensionamento ({cod})", "",
         f"Olá {nome},", "",
         f"Obrigado pela solicitação. Já dimensionamos e simulamos o filtro senoidal {ped['corrente_a']:g} A / {ped['tensao_v']:g} V "
         f"({proj.topologia}) para a aplicação informada. Para garantir que o filtro funcione sem aquecimento, ressonância ou "
         "queda de tensão excessiva na sua instalação, precisamos confirmar alguns dados que não vieram no pedido.", "",
         "Onde a informação faltou, adotamos a premissa indicada entre colchetes. Se ela estiver correta, basta responder \"ok\" "
         "no item.", ""]
    titulos = {"CRÍTICO": "1) IMPRESCINDÍVEIS – podem alterar o filtro",
               "IMPORTANTE": "2) IMPORTANTES – afetam margens, aquecimento e instalação",
               "CONFIRMAR": "3) PARA CONFIRMAR"}
    n = 0
    for g in ("CRÍTICO", "IMPORTANTE", "CONFIRMAR"):
        if not grupos[g]:
            continue
        L.append(titulos[g])
        for it in grupos[g]:
            n += 1
            prem = pr.get(it["id"])
            L.append(f"   {n}. {it['pergunta']}" + (f"  [premissa: {prem}]" if prem else ""))
            L.append(f"      Motivo: {it['porque']}.")
            rep = [c for c in it.get("cenarios", []) if not c["aprovado"]]
            if rep:
                L.append(f"      Na nossa simulação, com {rep[0]['cenario']}, o filtro não atende – por isso a confirmação é essencial.")
        L.append("")
    L += ["Se for mais prático, uma foto da placa do motor e do inversor, o print dos parâmetros do inversor e o desenho/lista de cabos "
          "já resolvem a maior parte dos itens.", "",
          "Segue também, em anexo, o questionário técnico para preenchimento.", "",
          "Atenciosamente,", emp["responsavel"], emp["nome"], f"{emp['email']} | {emp['telefone']}"]
    return "\n".join(L)


def questionario_docx(analise: Dict[str, Any], proj, cat, arquivo: str):
    from docx import Document
    from docx.shared import Pt
    ped = proj.pedido if isinstance(proj.pedido, dict) else proj.pedido.to_dict()
    d = Document()
    st = d.styles["Normal"]
    st.font.name = "Calibri"
    st.font.size = Pt(10)
    d.add_heading("Questionário técnico – filtro senoidal", 1)
    d.add_paragraph(f"Cliente: {ped.get('cliente')}   |   Referência: {ped.get('referencia') or '-'}   |   "
                    f"Filtro {ped['corrente_a']:g} A / {ped['tensao_v']:g} V")
    d.add_paragraph("Preencha a coluna 'Resposta'. Onde houver premissa e ela estiver correta, escreva 'ok'.")
    pr = analise["premissas"]
    t = d.add_table(rows=1, cols=5)
    t.style = "Light Grid Accent 1"
    for i, h in enumerate(["#", "Prioridade", "Pergunta", "Premissa adotada", "Resposta"]):
        t.rows[0].cells[i].text = h
    for k, it in enumerate(analise["itens"], 1):
        r = t.add_row().cells
        r[0].text, r[1].text, r[2].text, r[3].text, r[4].text = str(k), it["prioridade"], it["pergunta"], pr.get(it["id"], "-"), ""
    for row in t.rows:
        for c in row.cells:
            for p in c.paragraphs:
                for run in p.runs:
                    run.font.size = Pt(8.5)
    d.save(arquivo)
    return arquivo


def salvar_sensibilidade(analise, arquivo_xlsx):
    import pandas as pd
    lin = []
    for it in analise["itens"]:
        if not it.get("cenarios"):
            lin.append(dict(prioridade=it["prioridade"], item=it["pergunta"], cenario="(não simulável – criticidade de referência)",
                            resultado="", thd_pct=None, icap_A=None, t_indutor_C=None))
        for c in it.get("cenarios", []):
            lin.append(dict(prioridade=it["prioridade"], item=it["pergunta"], cenario=c["cenario"], resultado=c["efeito"],
                            thd_pct=c["thd"], icap_A=c["icap"], t_indutor_C=c["t_ind"]))
    pd.DataFrame(lin).to_excel(arquivo_xlsx, index=False)
    return arquivo_xlsx
