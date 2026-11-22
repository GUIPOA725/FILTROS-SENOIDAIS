"""
FSEN – Integração com a Plataforma de Estudos (v1.16.0) (ícones Qualidade de Energia e Proteção).

Cada fonte é lida SOZINHA e vira o mesmo dicionário de dados do leitor de bancos (leitor_banco.CAMPOS), com a origem de
cada número. Funciona com qualquer combinação, inclusive de clientes/estudos separados:
  • só medição de QEE  → carga e harmônicas medidas; rede (trafo, curto) = premissa sinalizada;
  • só estudo de proteção → rede real (curto por barra e cenário, trafos); carga = premissa ou informada/IA;
  • as duas            → tudo real; QEE manda na carga, proteção manda na rede;
  • nenhuma            → e-mail/anexos pela IA (caminho já existente) ou padrão.
Regra de mesclagem: dado digitado na tela > QEE (carga) / Proteção (rede) > IA (e-mail/anexos) > premissa padrão.

Fontes reconhecidas (saídas do GeradorQEE 3.x e do GeradorProtecao, sem nada novo a gravar):
  QEE: pasta "relatorios" do ponto medido – resumo - *.json, ficha - *.json, anexo - *.xlsx (aba Harmônicas),
       consumo e geração por hora - *.xlsx
  Proteção: PDF do estudo (Tabela de curto no ponto de conexão, dados dos transformadores, tabelas "Simétrico e X/R"
       por cenário) – ou .json/.xlsx do gerador de proteção, quando existirem.
"""
from __future__ import annotations

import glob
import json
import math
import os
import re
import subprocess

from . import banco as B

VERSAO_INTEGRACAO = "1.0"


# ============================================================================================ utilidades
def _num(s):
    if s is None:
        return None
    if isinstance(s, (int, float)):
        return float(s)
    s = str(s).strip().replace(".", "").replace(",", ".") if re.search(r"\d\.\d{3}(,|$)", str(s)) else str(s).strip().replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def _arq(pasta, prefixo, ext):
    c = sorted(glob.glob(os.path.join(pasta, f"{prefixo}*{ext}")))
    return c[0] if c else None


# ============================================================================================ QEE
def e_pasta_qee(pasta):
    return bool(pasta and os.path.isdir(pasta) and _arq(pasta, "resumo - ", ".json"))


def ler_qee(pasta):
    """Pasta 'relatorios' do GeradorQEE → (dados, evidencias). Usa P95 da pior fase (critério do leitor de bancos)."""
    dados, ev = {}, []
    fr = _arq(pasta, "resumo - ", ".json")
    if not fr:
        raise FileNotFoundError("Pasta sem 'resumo - *.json' do gerador de qualidade de energia.")
    r = json.load(open(fr, encoding="utf-8"))
    nome = os.path.basename(fr)
    ff = _arq(pasta, "ficha - ", ".json")
    fi = json.load(open(ff, encoding="utf-8")) if ff else {}
    dados["cliente"] = r.get("cliente") or ""
    dados["projeto"] = r.get("ponto") or ""
    dados["local_instalacao"] = r.get("ponto") or ""
    if r.get("vn_ff"):
        dados["tensao_v"] = float(r["vn_ff"])
    dados["freq_hz"] = 60.0
    if r.get("pmax"):
        dados["kw_carga"] = float(r["pmax"])
    if r.get("dmax"):
        dados["kva_carga"] = float(r["dmax"])
    if r.get("fp") is not None:
        dados["fp_atual"] = float(r["fp"])
    if fi.get("fp_alvo"):
        dados["fp_alvo"] = _num(fi["fp_alvo"])
    if r.get("dtt95") is not None:
        dados["dhtv_pct"] = float(r["dtt95"])
    if r.get("tdd95") is not None:
        dados["dhti_carga_pct"] = float(r["tdd95"])
    if r.get("il"):
        dados["corrente_fundamental_a"] = float(r["il"])
    if _num(r.get("banco_kvar")):
        dados["kvar_existente"] = _num(r["banco_kvar"])
    if _num(r.get("banco_dessintonia_pct")):
        dados["fd_pct"] = _num(r["banco_dessintonia_pct"])
    if r.get("scc_kva"):
        dados["scc_barra_mva"] = float(r["scc_kva"]) / 1000
    ev.append(f"QEE {nome}: V {dados.get('tensao_v', 0):g} V, Pmáx {dados.get('kw_carga', 0):.0f} kW, Dmáx "
              f"{dados.get('kva_carga', 0):.0f} kVA, FP {dados.get('fp_atual', 0):.3f}, DTT95 {dados.get('dhtv_pct', 0):.2f} %, "
              f"TDD95 {dados.get('dhti_carga_pct', 0):.2f} %, IL {dados.get('corrente_fundamental_a', 0):.0f} A "
              f"(período {r.get('t0', '?')} a {r.get('t1', '?')}).")
    # ---- espectro (aba Harmônicas do anexo) – P95 da pior fase
    fa = _arq(pasta, "anexo - ", ".xlsx")
    if fa:
        import openpyxl
        wb = openpyxl.load_workbook(fa, read_only=True, data_only=True)
        if "Harmônicas" in wb.sheetnames:
            ws = wb["Harmônicas"]
            linhas = list(ws.iter_rows(values_only=True))
            cab = [str(c or "") for c in linhas[0]]
            iv = [i for i, c in enumerate(cab) if c.startswith("Vh P95")]
            ia = [i for i, c in enumerate(cab) if c.startswith("Ih P95") and "(A)" in c]
            hv, hi = {}, {}
            for ln in linhas[1:]:
                if not ln or ln[0] is None:
                    continue
                h = int(ln[0])
                v = max((float(ln[i]) for i in iv if ln[i] is not None), default=None)
                a = max((float(ln[i]) for i in ia if ln[i] is not None), default=None)
                if v is not None and v >= 0.05:
                    hv[str(h)] = round(v, 3)
                if a is not None and a >= 0.1:
                    hi[str(h)] = round(a, 2)
            if hv:
                dados["harm_tensao_pct"] = hv
            if hi:
                dados["harm_corrente_a"] = hi
            ev.append(f"QEE {os.path.basename(fa)} aba Harmônicas: {len(hv)} ordens de tensão e {len(hi)} de corrente "
                      f"(P95, pior fase); V5 {hv.get('5', 0):.2f} %, V7 {hv.get('7', 0):.2f} %, I5 {hi.get('5', 0):.1f} A.")
    # ---- perfil horário (estágios)
    fc = _arq(pasta, "consumo e geração por hora - ", ".xlsx")
    if fc:
        try:
            dados["_perfil_horario"] = _perfil(fc)
            if dados["_perfil_horario"]:
                q = [p["kvar"] for p in dados["_perfil_horario"] if p.get("kvar") is not None]
                ev.append(f"QEE {os.path.basename(fc)}: {len(q)} horas; Q de 0 a {max(q or [0]):.0f} kvar (base dos estágios).")
        except Exception as ex:      # perfil é complemento: não derruba a leitura
            ev.append(f"Perfil horário não lido ({ex}).")
    dados["_fonte_qee"] = pasta
    return dados, ev


def _perfil(arq):
    import openpyxl
    wb = openpyxl.load_workbook(arq, read_only=True, data_only=True)
    out = []
    for ws in wb.worksheets:
        linhas = list(ws.iter_rows(values_only=True))
        if not linhas:
            continue
        cab = [str(c or "").lower() for c in linhas[0]]
        ik = next((i for i, c in enumerate(cab) if "kw" in c and "kwh" not in c), None) or \
            next((i for i, c in enumerate(cab) if "kwh" in c), None)
        iq = next((i for i, c in enumerate(cab) if "kvar" in c), None)
        if ik is None or iq is None:
            continue
        for ln in linhas[1:]:
            if ln and isinstance(ln[ik], (int, float)) and isinstance(ln[iq], (int, float)):
                out.append(dict(t=ln[0], kw=float(ln[ik]), kvar=float(ln[iq])))
        if out:
            break
    return out


# ============================================================================================ PROTEÇÃO
def _texto_pdf(arq):
    try:
        t = subprocess.run(["pdftotext", "-layout", arq, "-"], capture_output=True, text=True, timeout=180).stdout
        if t.strip():
            return t
        raise RuntimeError("pdftotext vazio")
    except Exception:       # Windows sem poppler: pypdf em modo layout (mesmas colunas do pdftotext -layout)
        import logging
        from pypdf import PdfReader
        logging.getLogger("pypdf").setLevel(logging.ERROR)
        out = []
        for p in PdfReader(arq).pages:
            try:
                out.append(p.extract_text(extraction_mode="layout") or "")
            except TypeError:
                out.append(p.extract_text() or "")
        return "\n".join(out)


def ler_protecao(arq_pdf):
    """Estudo de proteção (PDF do GeradorProtecao) → rede: ponto de conexão, trafos e curto por barra/cenário."""
    t = _texto_pdf(arq_pdf)
    rede = dict(arquivo=os.path.basename(arq_pdf), trafos=[], barras={}, cenarios=[])
    m = re.search(r"CLIENTE/LOCAL:.*?\n\s*(.+?)\s{2,}", t, re.S)
    rede["cliente"] = m.group(1).strip() if m else ""
    # ponto de conexão
    m = re.search(r"Icc\s*[–-]\s*3LG\s+([\d.,]+)\s+([\d.,]+)\s+([\d.,]+)", t)
    if m:
        rede["pac"] = dict(icc3_ka=_num(m.group(1)), scc_mva=_num(m.group(2)), xr=_num(m.group(3)))
    m = re.search(r"atendida (?:na tensão de |em )([\d.,]+)\s*kV", t)
    if m:
        rede["v_mt_kv"] = _num(m.group(1))
    # transformadores (linhas "TF-xx  kVA ... Z X/R ...")
    vistos = set()
    for ln in t.splitlines():
        mm = re.match(r"\s*-?\s*(TF-?\S+)\s+([\d.,]+)\s+([\d.,]+)\s+([\d.,]+)\s+([\d.,]+)\s+([\d.,]+)\s+([\d.,]+)\s+\S+\s+(Dyn\d+|Dy\d+|YNyn\d+|\S+)\s+(Seco|Óleo|Oleo)", ln)
        if mm and mm.group(1) not in vistos:
            vistos.add(mm.group(1))
            rede["trafos"].append(dict(tag=mm.group(1), kva=_num(mm.group(2)), v_at_kv=_num(mm.group(4)),
                                       v_bt_kv=_num(mm.group(5)), z_pct=_num(mm.group(6)), xr=_num(mm.group(7)),
                                       ligacao=mm.group(8), tipo=mm.group(9)))
            continue
        mm = re.match(r"\s*(TF-?\S+)\s+([\d.,]+)\s+([\d.,]+)\s+([\d.,]+)\s+([\d.,]+)\s+(Seco|Óleo|Oleo)", ln)
        if mm and mm.group(1) not in vistos:
            vistos.add(mm.group(1))
            rede["trafos"].append(dict(tag=mm.group(1), kva=_num(mm.group(2)), v_bt_kv=_num(mm.group(3)) / 1000,
                                       z_pct=_num(mm.group(4)), xr=_num(mm.group(5)), tipo=mm.group(6)))
    # tabelas simétricas por cenário
    blocos = re.split(r"Tabela \d+ – Resultados da Simulação de Curto-Circuito", t)
    for bl in blocos[1:]:
        cab = re.match(r".*?Simétrico e X/R\s*\n?\s*[–-]\s*(.+?)\.\s*\n", bl, re.S)
        if not cab:
            continue
        nome = re.sub(r"\s+", " ", cab.group(1)).strip()
        barras = {}
        for ln in bl.splitlines():
            mm = re.match(r"\s*(.+?)\s{2,}(\d{3,6})\s+(\d+)\s+([\d,]+)\s+(\d+)\s+([\d,]+)", ln)
            if mm and not mm.group(1).strip().startswith(("TAG", "CORRENTE")):
                tag = mm.group(1).strip()
                V, I3, xr = float(mm.group(2)), float(mm.group(3)), _num(mm.group(4))
                barras[tag] = dict(v=V, icc3_a=I3, xr=xr, scc_mva=math.sqrt(3) * V * I3 / 1e6)
        if barras:
            rede["cenarios"].append(dict(nome=nome, barras=barras))
            for k, v in barras.items():
                rede["barras"].setdefault(k, v["v"])
    return rede


def barras_bt(rede, v_max=1000):
    """Barras de baixa tensão (candidatas ao banco); as que parecem 'banco/capacitor' vêm primeiro."""
    bs = [b for b, v in rede["barras"].items() if v <= v_max]
    return sorted(bs, key=lambda b: (0 if re.search(r"banco|capacit|bc\b|fp\b", b, re.I) else 1, b))


def cenarios_barra(rede, barra):
    out = []
    for c in rede["cenarios"]:
        if barra in c["barras"]:
            d = c["barras"][barra]
            out.append(dict(nome=c["nome"], scc_mva=d["scc_mva"], xr=d["xr"], icc3_a=d["icc3_a"], v=d["v"]))
    return out


def dados_de_protecao(rede, barra=None):
    """Rede → campos do pedido. Escolhe a barra do banco (pelo nome, se não indicada) e o trafo de mesma tensão."""
    dados, ev = {}, []
    barra = barra or (barras_bt(rede) or [None])[0]
    if not barra:
        return dados, ["Proteção: nenhuma barra de baixa tensão encontrada."]
    cen = cenarios_barra(rede, barra)
    V = rede["barras"][barra]
    dados["tensao_v"] = V
    tr = [x for x in rede["trafos"] if x.get("v_bt_kv") and abs(x["v_bt_kv"] * 1000 - V) / V < 0.1]
    if tr:
        dados["trafo_kva"] = sum(x["kva"] for x in tr) if len(tr) > 1 else tr[0]["kva"]
        dados["trafo_z_pct"] = tr[0]["z_pct"]
        ev.append(f"Proteção: trafo(s) {', '.join(x['tag'] for x in tr)} – {tr[0]['kva']:g} kVA, Z {tr[0]['z_pct']:g} %, "
                  f"X/R {tr[0].get('xr') or '-'}" + (f" ({len(tr)} em paralelo)" if len(tr) > 1 else "") + ".")
    if rede.get("pac"):
        dados["scc_rede_mva"] = rede["pac"]["scc_mva"]
        ev.append(f"Proteção: ponto de conexão {rede['pac']['scc_mva']:g} MVA (Icc3F {rede['pac']['icc3_ka']:g} kA, X/R {rede['pac']['xr']:g}).")
    if cen:
        normal = cen[0]
        dados["scc_barra_mva"] = normal["scc_mva"]
        dados["_cenarios_rede"] = cen
        ev.append(f"Proteção: barra '{barra}' ({V:g} V) – " + "; ".join(
            f"{c['nome'][:48]}: {c['scc_mva']:.1f} MVA" for c in cen) + ".")
    dados["_barra"] = barra
    dados["cliente"] = rede.get("cliente") or ""
    dados["_fonte_protecao"] = rede.get("arquivo")
    return dados, ev


# ============================================================================================ mesclagem
CARGA = ("kw_carga", "kva_carga", "fp_atual", "fp_alvo", "dhtv_pct", "dhti_carga_pct", "corrente_fundamental_a",
         "harm_tensao_pct", "harm_corrente_a", "harm_corrente_pct", "kvar_existente", "fd_pct", "_perfil_horario")
REDE = ("trafo_kva", "trafo_z_pct", "scc_rede_mva", "scc_barra_mva", "_cenarios_rede", "_barra")


def mesclar(digitado=None, qee=None, protecao=None, ia=None):
    """Junta as fontes (cada uma pode faltar). Retorna (dados, origem{campo: fonte}, avisos)."""
    dados, origem, av = {}, {}, []
    camadas = [("IA (e-mail/anexos)", ia or {}), ("Proteção", protecao or {}), ("QEE", qee or {}), ("Digitado", digitado or {})]
    for nome, d in camadas:
        for k, v in d.items():
            if v in (None, "", {}, []):
                continue
            if nome == "Proteção" and (k in CARGA or (k == "cliente" and (qee or {}).get("cliente"))):
                continue
            if nome == "QEE" and k in REDE and protecao and protecao.get(k):
                continue            # rede: proteção manda
            if k in dados and k == "tensao_v" and abs(float(dados[k]) - float(v)) / float(v) > 0.05:
                av.append(f"Tensão diferente entre fontes: {origem[k]} {dados[k]:g} V × {nome} {float(v):g} V – usado {nome}.")
            dados[k], origem[k] = v, nome
    if qee and protecao:
        cq, cp = (qee.get("cliente") or "").upper(), (protecao.get("cliente") or "").upper()
        if cq and cp and cq.split()[0] not in cp and cp.split()[0] not in cq:
            av.append(f"Medição (QEE: {qee.get('cliente')}) e estudo de proteção ({protecao.get('cliente')}) parecem de clientes "
                      "diferentes – conferir antes de usar a rede de um com a carga do outro.")
    if not (qee or ia or digitado) or not any(k in dados for k in ("kw_carga", "kvar_necessario", "estagios_kvar")):
        av.append("Sem medição de carga: kvar/estágios por premissa – informar kW e FP, ou carregar a medição do ícone QEE.")
    if not any(k in dados for k in ("trafo_kva", "scc_barra_mva")):
        av.append("Sem estudo de proteção: trafo e curto por premissa (1000 kVA, 6 %, 250 MVA) – a verificação de ressonância "
                  "usa valores típicos.")
    return dados, origem, av


def aplicar_rede(ped, dados):
    """Coloca a potência de curto REAL da barra no pedido (equivalente de rede que reproduz a Scc da barra)."""
    scc = dados.get("scc_barra_mva")
    if not scc:
        return ped
    Un = ped.tensao_v
    x_tr = ped.trafo_z_pct / 100 * Un ** 2 / (ped.trafo_kva * 1e3)
    x_tot = Un ** 2 / (scc * 1e6)
    x_rede = x_tot - x_tr
    if x_rede > 0:
        ped.scc_rede_mva = Un ** 2 / x_rede / 1e6
    else:   # barra mais forte que o trafo informado (vários trafos/geração): mantém a Scc ajustando o Z equivalente
        ped.scc_rede_mva = 1e5
        ped.trafo_z_pct = 100 * (x_tot - Un ** 2 / 1e11) * ped.trafo_kva * 1e3 / Un ** 2
    return ped


def verificar_cenarios(ped, cenarios):
    """Repete o dimensionamento com a Scc de cada cenário da proteção → ressonância e avisos por cenário."""
    import copy
    out = []
    for c in cenarios or []:
        p = aplicar_rede(copy.deepcopy(ped), {"scc_barra_mva": c["scc_mva"]})
        try:
            r = B.dimensionar(p)
        except Exception as ex:
            out.append(dict(nome=c["nome"], scc_mva=c["scc_mva"], erro=str(ex)))
            continue
        Q = sum(e["Q_cap_nom_kvar"] for e in r["estagios"]) or 1
        hr_sem = math.sqrt(c["scc_mva"] * 1000 / Q)
        out.append(dict(nome=c["nome"], scc_mva=round(c["scc_mva"], 2), hr_sem_reator=round(hr_sem, 2),
                        avisos=[a for a in r.get("avisos", []) if "resson" in a.lower()]))
    return out


def necessidade(dados):
    """Há o que corrigir? → (precisa: bool, motivos). Evita projetar banco/filtro quando a medição mostra que não precisa."""
    mot, precisa = [], False
    P, fp1, fp2 = dados.get("kw_carga"), dados.get("fp_atual"), float(dados.get("fp_alvo") or 0.95)
    if dados.get("kvar_necessario") or dados.get("estagios_kvar"):
        return True, ["Potência/estágios informados."]
    if P and fp1 is not None:
        q = P * (math.tan(math.acos(min(float(fp1), 0.9999))) - math.tan(math.acos(min(fp2, 0.9999))))
        if q > 0.05 * P:
            precisa = True
            mot.append(f"FP medido {float(fp1):.3f} < alvo {fp2:.2f}: faltam {q:.0f} kvar.")
        else:
            mot.append(f"FP medido {float(fp1):.3f} ≥ alvo {fp2:.2f}: não há reativo a compensar.")
    dv, di = dados.get("dhtv_pct"), dados.get("dhti_carga_pct")
    if dv is not None:
        if dv > 8:     # PRODIST Módulo 8 (DTT95 ≤ 10 % até 2,3 kV) – margem de 80 %
            precisa = True
            mot.append(f"DTT95 {dv:.1f} % próximo/acima do limite do PRODIST (10 %): filtro de harmônicas indicado.")
        else:
            mot.append(f"DTT95 {dv:.1f} % dentro do PRODIST (≤ 10 %).")
    if di is not None and di > 8:
        precisa = True
        mot.append(f"TDD95 {di:.1f} % acima do limite típico da IEEE 519 (5–8 %): filtro indicado.")
    elif di is not None:
        mot.append(f"TDD95 {di:.1f} % dentro da IEEE 519.")
    if P is None and fp1 is None and dv is None:
        return True, ["Sem medição: segue o pedido (premissas sinalizadas)."]
    return precisa, mot


# ============================================================================================ ponto de ligação indicado pelo usuário
def achar_barra(rede, texto):
    """Barra/equipamento digitado pelo usuário ('QDF-03', 'banco do QDF 3', 'TF-02') → nome exato da barra do estudo."""
    import difflib
    if not texto:
        return None
    nomes = list(rede["barras"])
    t = texto.strip().upper()
    exatos = [b for b in nomes if b.upper() == t]
    if exatos:
        return exatos[0]
    m = re.search(r"TF-?\s*0*(\d+)", t)
    if m:                                 # equipamento trafo → barra do secundário
        sec = [b for b in nomes if re.search(rf"SEC\s*TF-?0*{m.group(1)}\b", b.upper())]
        if sec:
            return sec[0]
    contem = [b for b in nomes if t in b.upper()]
    if contem:
        return sorted(contem, key=len)[0]
    norm = lambda s: re.sub(r"[^A-Z0-9]", "", s.upper())
    alvo = norm(t)
    melhor = difflib.get_close_matches(alvo, [norm(b) for b in nomes], n=1, cutoff=0.5)
    return next((b for b in nomes if norm(b) == melhor[0]), None) if melhor else None


def ponto_de_ligacao(dados_qee, medicao_no_ponto):
    """Ajusta a medição conforme o lugar onde foi feita.
    medicao_no_ponto=True  → harmônicas e carga valem como estão (medição na barra do filtro).
    medicao_no_ponto=False → a medição é de outro ponto: tensão harmônica de projeto = máx(medida, padrão dos guias);
                             correntes harmônicas e kvar ficam como estimativa, sinalizadas no memorial."""
    if not dados_qee:
        return dados_qee, []
    d = dict(dados_qee)
    if medicao_no_ponto:
        return d, ["Medição feita na barra de ligação do filtro: carga e harmônicas usadas diretamente."]
    hv = {str(h): max(float(v), B.HARM_PADRAO.get(int(h), 0)) for h, v in {**{str(k): v for k, v in B.HARM_PADRAO.items()},
                                                                          **(d.get("harm_tensao_pct") or {})}.items()}
    d["harm_tensao_pct"] = hv
    return d, ["Medição feita em OUTRO ponto da instalação: tensão harmônica de projeto = máximo entre a medida e o padrão dos "
               "guias (conservador); correntes harmônicas e potência da medição tratadas como estimativa da carga da barra – "
               "confirmar a carga da barra escolhida."]


def pdfs_protecao(pasta):
    """PDFs de estudo de proteção numa pasta (o mais novo primeiro) – inclui ESTUDOS-PLATAFORMA e subpastas."""
    if not pasta or not os.path.isdir(pasta):
        return []
    c = []
    for raiz, _d, arqs in os.walk(pasta):
        if raiz[len(pasta):].count(os.sep) > 3:
            continue
        for a in arqs:
            if a.lower().endswith(".pdf") and re.search(r"prote|curto", a, re.I) and not re.search(r"energia incidente|etiqueta", a, re.I):
                c.append(os.path.join(raiz, a))
    return sorted(c, key=lambda f: -os.path.getmtime(f))
