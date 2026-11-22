"""Leitura automática de solicitações de BANCO DESSINTONIZADO / FILTRO SINTONIZADO (v1.14.0).

Mesmo caminho de IA do filtro senoidal (leitor_ia.extrair_dados: Claude Code pela assinatura, API Anthropic ou compatível
OpenAI): o engenheiro cola o e-mail e solta os anexos – pedido, unifilar, placa do trafo, fotos, relatório de QEE e as
EXPORTAÇÕES DE MEDIÇÃO (Dranview, Fluke, CSV/XLSX: séries longas viram média/P95/máximo por coluna). A IA extrai os dados e
`decidir()` aplica o critério de engenharia da Electric: kvar pelo FP alvo, estágios em módulos padrão, tipo de filtro
(dessintonizado × sintonizado), FD (8,16 % padrão; 14 % com 3ª harmônica) e ordens sintonizadas.
"""
import math
import re

from . import banco as B

CAMPOS = {
    "cliente": "string", "projeto": "string", "local_instalacao": "string", "contato": "string", "email_contato": "string",
    "tipo_pedido": "string", "tensao_v": "number", "freq_hz": "number", "kw_carga": "number", "kva_carga": "number",
    "fp_atual": "number", "fp_alvo": "number", "kvar_necessario": "number", "kvar_existente": "number",
    "estagios_kvar": "array", "nr": "number", "fd_pct": "number", "ordens": "array", "dhti_carga_pct": "number",
    "dhtv_pct": "number", "corrente_fundamental_a": "number", "harm_tensao_pct": "object", "harm_corrente_a": "object",
    "harm_corrente_pct": "object", "trafo_kva": "number", "trafo_z_pct": "number", "scc_rede_mva": "number",
    "amb_c": "number", "quantidade": "integer", "modulo_ou_painel": "string", "observacoes": "string",
}

INSTRUCAO = """Você é engenheiro de aplicação de correção de fator de potência e filtros de harmônicas em baixa tensão
(bancos de capacitores DESSINTONIZADOS com reator, e filtros SINTONIZADOS 5ª/7ª/11ª). Extraia da solicitação (e-mail e
anexos: pedido, unifilar, placa do transformador, relatório de qualidade de energia, planilhas/exportações de MEDIÇÃO) os dados
e chame a ferramenta `registrar_banco`.
Regras:
- Use somente o que está escrito ou medido; não invente. Campos ausentes: omita e liste em `lacunas` com a premissa sugerida.
- tipo_pedido: "dessintonizado", "sintonizado" ou "indefinido" (o que o cliente pediu; 'filtro de harmônica dessintonizado'
  = dessintonizado; 'FHSBT', 'filtro sintonizado', 'filtro de 5ª' = sintonizado).
- Medições: para harmônicas use o P95 (ou o máximo, se só houver máximo) das TRÊS fases, a pior fase. harm_tensao_pct em % da
  fundamental por ordem, ex. {"3": 0.8, "5": 4.2, "7": 2.1}; harm_corrente_a em ampères por ordem (ou harm_corrente_pct em %
  da fundamental se só houver %); dhti_carga_pct e dhtv_pct em %. corrente_fundamental_a = corrente de 60 Hz (P95).
- kw_carga = demanda ativa (P95 ou máxima) do ponto medido; fp_atual = fator de potência medido (sem o banco); fp_alvo
  padrão 0,95 se não informado (0,92 é o mínimo da ANEEL).
- estagios_kvar: só se o cliente definiu os estágios (lista em kvar, ex. [25, 50, 50]). kvar_existente = banco já instalado.
- fd_pct ou nr: só se pedido (ex. FD 7 %, 8,16 %, 14 %). ordens: harmônicas a sintonizar se pedidas (ex. [5, 7]).
- trafo_kva, trafo_z_pct (impedância %), scc_rede_mva (potência de curto na MT) – da placa/unifilar.
- modulo_ou_painel: "modulo" (cliente já tem painel/contatoras e quer só módulos) ou "painel" (painel completo).
"""


def _ferramenta():
    props = {}
    for k, v in CAMPOS.items():
        if v == "array":
            props[k] = {"type": "array", "items": {"type": "number"}}
        elif v == "object":
            props[k] = {"type": "object", "additionalProperties": {"type": "number"}}
        else:
            props[k] = {"type": v}
    props["lacunas"] = {"type": "array", "items": {"type": "string"}}
    props["evidencias"] = {"type": "array", "items": {"type": "string"},
                           "description": "De onde saiu cada número importante (arquivo/aba/coluna), para conferência."}
    return {"name": "registrar_banco", "description": "Registra os dados de um banco dessintonizado ou filtro sintonizado.",
            "input_schema": {"type": "object", "properties": props, "required": ["tensao_v"]}}


def ler_com_ia(texto, anexos, provedor=None):
    from .leitor_ia import extrair_dados
    dados, pc = extrair_dados(texto, anexos, INSTRUCAO, _ferramenta(), "", provedor)
    dados["_fonte"] = f"IA – {pc['nome']} / {pc['modelo']}" + (f" / esforço {pc['esforco']}" if pc.get("esforco") else "")
    return dados


def ler_por_regras(texto):
    """Sem IA: tensão, kvar, FD e harmônica pelo texto (o resto fica para o engenheiro)."""
    t = texto or ""
    d = {"lacunas": ["Leitura por REGRAS (sem IA) – confira tudo."], "_fonte": "REGRAS (sem IA)"}
    m = re.search(r"(\d{3})\s*V\b", t)
    if m:
        d["tensao_v"] = float(m.group(1))
    ks = [float(x.replace(",", ".")) for x in re.findall(r"(\d+(?:[.,]\d+)?)\s*k[Vv][Aa]?[Rr]", t)]
    if ks:
        d["kvar_necessario"] = max(ks)
    m = re.search(r"FD\s*(\d+(?:[.,]\d+)?)\s*%", t, re.I)
    if m:
        d["fd_pct"] = float(m.group(1).replace(",", "."))
    if re.search(r"sintoniz|FHS", t, re.I):
        d["tipo_pedido"] = "sintonizado"
    elif re.search(r"dessintoniz|BCD", t, re.I):
        d["tipo_pedido"] = "dessintonizado"
    return d


def ler(texto, anexos=None, provedor=None):
    from .leitor_ia import status_provedores, config_ia, _texto_anexos
    provedor = provedor or config_ia().get("provedor_padrao", "claude")
    if status_provedores().get(provedor, {}).get("pronto"):
        try:
            return ler_com_ia(texto, anexos, provedor)
        except Exception as e:
            d = ler_por_regras((texto or "") + "\n" + _texto_anexos(anexos))
            d["lacunas"].insert(0, f"⚠️ A IA ({provedor}) falhou: {type(e).__name__}: {str(e)[:200]}")
            return d
    return ler_por_regras((texto or "") + "\n" + _texto_anexos(anexos))


def _num_dict(x):
    out = {}
    for k, v in (x or {}).items():
        try:
            h = int(float(str(k).replace("h", "").replace("ª", "")))
            if h >= 2 and v is not None and float(v) > 0:
                out[h] = float(v)
        except Exception:
            pass
    return out


def estagios_padrao(kvar, V=380):
    """Módulos padrão Electric de 25 e 50 kvar; com 3+ estágios um deles é de 25 (degrau fino para o controlador)."""
    if kvar <= 0:
        return [25.0]
    if kvar < 37.5:
        return [25.0]
    n = int(kvar // 50)
    r = kvar - 50 * n
    est = [50.0] * n
    if r >= 37.5:
        est.append(50.0)
    elif r >= 12.5:
        est.append(25.0)
    if len(est) >= 3 and 25.0 not in est:
        est[-1] = 25.0
        if sum(est) < kvar * 0.95:
            est.append(25.0)
    return sorted(est)


CRESCIMENTO_PCT = 15.0        # folga para crescimento de carga (critério Electric – Panatlântica 2024)
N_RESERVA = 2                 # critério N-2 a partir de 250 kvar necessários (abaixo, N-1): perdendo 1/2 estágios ainda entrega o necessário
MODULO_KVAR = 50.0            # módulo padrão dos bancos maiores (todos iguais → qualquer estágio perdido vale o mesmo)
I0_TRAFO_PCT = 1.0            # corrente de magnetização típica (% de In) – trafo a óleo/seco de distribuição


def perdas_reativas_trafo(kva, z_pct, s_carga_kva):
    """kvar consumidos no próprio transformador (magnetização + dispersão) – não aparecem na medição feita na BT."""
    if not kva:
        return 0.0
    carga = min(1.2, (s_carga_kva or 0) / kva)
    return kva * (I0_TRAFO_PCT + z_pct * carga ** 2) / 100


def folga_electric(q_base, dados, j, lac):
    """Critério Electric para o montante do banco (explicado pelo eng. Guilherme no teste Panatlântica):
    (1) folga para crescimento de carga; (2) perdas reativas do trafo quando a medição foi na BT;
    (3) N-k: perdendo k estágios (falha de capacitor/contatora) ainda sobra o montante necessário.
    O banco final é o maior dos três critérios, arredondado para módulos iguais de 50 kvar."""
    cres = float(dados.get("crescimento_pct") if dados.get("crescimento_pct") is not None else CRESCIMENTO_PCT)
    nres = int(dados.get("n_reserva") if dados.get("n_reserva") is not None else (N_RESERVA if q_base >= 250 else 1))
    medido_bt = dados.get("medido_bt", True)
    kva = float(dados.get("trafo_kva") or 0)
    z = float(dados.get("trafo_z_pct") or 6.0)
    s_c = float(dados.get("kva_carga") or 0) or (float(dados.get("kw_carga") or 0) / 0.8)
    qt = perdas_reativas_trafo(kva, z, s_c) if medido_bt else 0.0
    q1 = q_base * (1 + cres / 100) + qt
    q2 = q_base + nres * MODULO_KVAR
    alvo = max(q1, q2)
    n = max(2, math.ceil(alvo / MODULO_KVAR - 1e-6))
    est = [MODULO_KVAR] * n
    j.append(f"Folga Electric sobre {q_base:g} kvar necessários: crescimento {cres:g} %"
             + (f" + perdas reativas do trafo {kva:g} kVA ({qt:.0f} kvar, medição na BT)" if qt else "")
             + f" = {q1:.0f} kvar; critério N-{nres} (perdendo {nres} estágio(s) de {MODULO_KVAR:g} ainda sobram "
             f"{q_base:g}) = {q2:.0f} kvar → {n} × {MODULO_KVAR:g} = {n * MODULO_KVAR:g} kvar.")
    if not dados.get("trafo_kva"):
        lac.append("Potência do trafo não informada – perdas reativas do trafo não incluídas na folga.")
    return n * MODULO_KVAR, est


def decidir(dados, tipo_forcado=None):
    """Critério Electric → PedidoBanco + justificativa (lista de frases para a tela)."""
    j, lac = [], list(dados.get("lacunas") or [])
    V = float(dados.get("tensao_v") or 380)
    f = float(dados.get("freq_hz") or 60)
    hv = _num_dict(dados.get("harm_tensao_pct"))
    hi = _num_dict(dados.get("harm_corrente_a"))
    I1 = float(dados.get("corrente_fundamental_a") or 0)
    if not hi and dados.get("harm_corrente_pct") and I1:
        hi = {h: v / 100 * I1 for h, v in _num_dict(dados["harm_corrente_pct"]).items()}
    dhti = float(dados.get("dhti_carga_pct") or (100 * math.sqrt(sum(v ** 2 for v in hi.values())) / I1 if hi and I1 else 0))
    dhtv = float(dados.get("dhtv_pct") or (math.sqrt(sum(v ** 2 for v in hv.values())) if hv else 0))
    # ---- kvar
    kvar = float(dados.get("kvar_necessario") or 0)
    P = float(dados.get("kw_carga") or 0)
    fp1, fp2 = dados.get("fp_atual"), float(dados.get("fp_alvo") or 0.95)
    if not kvar and P and fp1:
        fp1 = float(fp1)
        kvar = P * (math.tan(math.acos(min(fp1, 0.999))) - math.tan(math.acos(min(fp2, 0.999))))
        j.append(f"kvar pelo FP: P = {P:.0f} kW, FP {fp1:.3f} → {fp2:.2f}: Q = P·(tanφ1 − tanφ2) = {kvar:.0f} kvar.")
    kex = float(dados.get("kvar_existente") or 0)
    if kex and kvar and kvar <= kex:
        # v1.17.1 (teste Panatlântica): a IA traz o MONTANTE TOTAL necessário na barra e o banco existente; quando o total
        # não passa do existente, o projeto é de SUBSTITUIÇÃO (painel novo do mesmo porte) – não subtrair (antes dava 0 → 50 kvar)
        j.append(f"Banco existente de {kex:g} kvar cobre o necessário ({kvar:g} kvar): painel novo dimensionado para SUBSTITUIR o "
                 f"existente ({kvar:g} kvar) – se for ampliação, informe o kvar adicional.")
        lac.append("Escopo: substituição do banco existente (premissa) × ampliação – confirmar com o cliente.")
    else:
        kvar -= kex
    est = [float(x) for x in (dados.get("estagios_kvar") or []) if x]
    if not est and kvar >= 100:
        # v1.17.3: o engenheiro escolhe – "medido" (reativo das medições, como Panatlântica 300 kvar) ou "folga"
        # (crescimento + perdas do trafo + N-k). A plataforma sempre calcula as duas e mostra a outra como referência.
        modo = (dados.get("criterio_montante") or "medido").lower()
        jj, ll = [], []
        kf, ef = folga_electric(kvar, dados, jj, ll)
        if modo == "folga":
            kvar, est = kf, ef
            j += jj
            lac += ll
        else:
            j.append(f"Montante pelo REATIVO DAS MEDIÇÕES: {kvar:g} kvar (sem folga). Referência – com o critério de folga "
                     f"Electric (crescimento + perdas do trafo + N-k) seria {kf:g} kvar ({len(ef)} × {ef[0]:g}); para usar, "
                     "marque 'Com folga Electric'.")
    if not est:
        est = estagios_padrao(kvar or 50, V)
        j.append(f"Estágios em módulos padrão: {' + '.join(f'{x:g}' for x in est)} = {sum(est):g} kvar"
                 + ("" if kvar else " (kvar não informado – PREMISSA, confirmar)"))
        if not kvar:
            lac.append("Potência reativa não informada nem calculável (faltam kW e FP) – adotado 50 kvar.")
    # ---- tipo
    tp = (dados.get("tipo_pedido") or "").lower()
    if tipo_forcado:
        tipo = tipo_forcado
    elif tp in ("dessintonizado", "sintonizado"):
        tipo = tp
        j.append(f"Tipo pedido pelo cliente: {tipo}.")
    else:
        tipo = "sintonizado" if (dhti >= 40 or dhtv >= 5 or hv.get(5, 0) >= 3.5) else "dessintonizado"
        if not (dhti or dhtv or hv):
            j.append("Sem medição de harmônicas: dessintonizado (padrão Electric) – carregar a medição para confirmar o tipo.")
        else:
            j.append(f"Tipo escolhido pela medição: DHTi {dhti:.0f} %, DHTv {dhtv:.1f} % → {tipo} "
                     "(sintonizado quando DHTi ≥ 40 %, DHTv ≥ 5 % ou V5 ≥ 3,5 %; senão dessintonizado).")
    ped = B.PedidoBanco(cliente=dados.get("cliente") or "", projeto=dados.get("projeto") or dados.get("local_instalacao") or "",
                        tipo=tipo, tensao_v=V, freq_hz=f, estagios_kvar=est, dhti_carga_pct=dhti or 50.0)
    for k in ("trafo_kva", "trafo_z_pct", "scc_rede_mva", "amb_c"):
        if dados.get(k):
            setattr(ped, k, float(dados[k]))
        elif k != "amb_c":
            lac.append(f"{k} não informado – adotado {getattr(ped, k):g}.")
    if tipo == "dessintonizado":
        nr = dados.get("nr")
        if not nr and dados.get("fd_pct"):
            nr = 1 / math.sqrt(float(dados["fd_pct"]) / 100)
        if nr:
            ped.nr = min(B.NR_DESSINT, key=lambda x: abs(x - float(nr)))
            j.append(f"FD pedido: Nr {ped.nr:g}.")
        elif hv.get(3, 0) >= 1.0 or (hi.get(3, 0) > 0.15 * I1 if I1 else False):
            ped.nr = 2.67
            j.append(f"3ª harmônica relevante (V3 {hv.get(3, 0):.1f} %) → FD 14 % (Nr 2,67), sintonia abaixo da 3ª.")
        else:
            ped.nr = 3.5
            j.append("FD 8,16 % (Nr 3,5) – padrão Electric.")
        ped.harm_tensao_pct = {h: max(v, B.HARM_PADRAO.get(h, 0)) for h, v in {**B.HARM_PADRAO, **hv}.items()}
        if hv:
            j.append("Distorção de projeto = máximo entre a medição e o padrão dos guias (conservador para o reator).")
    else:
        ords = [float(x) for x in (dados.get("ordens") or []) if x]
        if not ords:
            base = hi or {h: v for h, v in hv.items()}
            ords = [5.0]
            if base.get(7, 0) >= 0.5 * base.get(5, 1e-9) and len(est) >= 2:
                ords.append(7.0)
            if base.get(11, 0) >= 0.35 * base.get(5, 1e-9) and len(est) >= 3:
                ords.append(11.0)
        ordens = [ords[min(i * len(ords) // len(est), len(ords) - 1)] for i in range(len(est))]
        ped.ordens = ordens
        j.append("Ramos sintonizados: " + ", ".join(f"{o:g}ª" for o in ordens) + f" (Nr = {ped.fator_sintonia:g}·h).")
        ped.harm_tensao_pct = hv and {h: v for h, v in hv.items()} or dict(B.HARM_PADRAO_SINT)
        if hv:
            j.append("ATENÇÃO: a distorção de tensão medida já inclui a carga; usada como fundo da rede (conservador).")
    if hi:
        ped.harm_carga_a = hi
    return ped, j, list(dict.fromkeys(lac))
