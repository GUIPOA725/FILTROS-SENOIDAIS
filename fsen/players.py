"""Comparação do filtro senoidal com os PLAYERS mundiais (Schaffner, TDK EPCOS, Block, Danfoss, MTE) – v1.30.0.

REQ-SEN-024 (engenheiro, 25/11/2026): "Vc sempre precisa buscar nos 4 players mundiais se o nosso dimensionamento segue o que
eles vendem ... criar uma pasta tipo concorrentes ou players com as informações que vc usou ... É uma busca mais profunda na
internet com critérios ... informações técnicas boas"; 23:56: "salvar em planilha comparativa também e no consolidado".

Critérios (só datasheet oficial – dados/players_filtro_senoidal.yaml, com link e data de consulta):
  • modelos vizinhos de cada fabricante (o menor ≥ corrente do projeto e o maior abaixo);
  • L por fase; C equivalente em estrela (Δ × 3); fr = 1/(2π√(L·Cy)); uk = 2π·f·L·I/(V/√3) na tensão e frequência do projeto;
  • perdas por ampère; massa por ampère; fs mínima; queda declarada; classe de isolação;
  • faixa de referência = mínimo–máximo dos modelos vizinhos sem "conferir"; Check:
      uk dentro da faixa (±1 ponto) · fr dentro da faixa (−20 %/+20 %) · perdas/A ≤ máximo + 10 %.
    Fora da faixa = ATENÇÃO com a explicação (não reprova: o projeto pode divergir de propósito, ex.: queda de tensão menor).
Saída: 01_Engenharia/6_Players_Mercado/Players_Mercado_Filtro_<cod>.xlsx (entra no consolidado) + bloco no RESUMO.
"""
from __future__ import annotations

import math
import os

import yaml

ARQ = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dados", "players_filtro_senoidal.yaml")


def carregar(arq=ARQ):
    with open(arq, encoding="utf-8") as f:
        return (yaml.safe_load(f) or {}).get("players", {})


def _linha(row):
    I, L, C, con, P, m, fs, q = (list(row) + [None] * 8)[:8]
    conferir = len(row) > 8 and str(row[8]).lower().startswith("conf")
    return dict(I=float(I), L_mH=L, C_uF=C, con=str(con or "Y").upper()[:1], P_W=P, m_kg=m, fs_min=fs, queda=q, conferir=conferir)


def _normaliza(r, V_ll, f_hz):
    Vf = V_ll / math.sqrt(3)
    Cy = None if r["C_uF"] is None else float(r["C_uF"]) * (3.0 if r["con"] == "D" else 1.0)
    L = None if r["L_mH"] is None else float(r["L_mH"]) * 1e-3
    fr = None if (L is None or Cy is None) else 1 / (2 * math.pi * math.sqrt(L * Cy * 1e-6))
    uk = None if L is None else 2 * math.pi * f_hz * L * r["I"] / Vf * 100
    return dict(r, Cy_uF=Cy, L_uH=None if L is None else L * 1e6, fr_Hz=fr, uk_pct=uk,
                W_por_A=None if r["P_W"] is None else r["P_W"] / r["I"], kg_por_A=None if r["m_kg"] is None else r["m_kg"] / r["I"])


def vizinhos(linhas, I):
    ls = sorted(linhas, key=lambda x: x["I"])
    acima = [x for x in ls if x["I"] >= I][:1]
    abaixo = [x for x in ls if x["I"] < I][-1:]
    return abaixo + acima


def comparar(I, V_ll, f_hz, L_uH, Cy_uF, perdas_W=None, massa_kg=None, fs_kHz=None, queda_pct=None, players=None):
    """Tabela normalizada (nosso projeto + vizinhos de cada player), faixa de referência e checks."""
    players = players if players is not None else carregar()
    Vf = V_ll / math.sqrt(3)
    nosso = dict(fabricante="Electric Service (este projeto)", modelo="projeto (massa com a caixa)", I=float(I), L_uH=L_uH, Cy_uF=Cy_uF,
                 fr_Hz=1 / (2 * math.pi * math.sqrt(L_uH * 1e-6 * Cy_uF * 1e-6)) if L_uH and Cy_uF else None,
                 uk_pct=2 * math.pi * f_hz * L_uH * 1e-6 * I / Vf * 100 if L_uH else None, P_W=perdas_W, m_kg=massa_kg,
                 W_por_A=(perdas_W / I) if perdas_W else None, kg_por_A=(massa_kg / I) if massa_kg else None,
                 fs_min=fs_kHz, queda=queda_pct, conferir=False, classe="H (180 °C) – REQ-SEN-021", url="", consulta="")
    linhas, fontes = [], []
    for nome, p in players.items():
        ls = [_linha(r) for r in p.get("linhas", [])]
        if not ls:
            continue
        vz = vizinhos(ls, I)
        if not vz or (min(abs(x["I"] - I) / I for x in vz) > 0.6):
            continue                                    # nenhum modelo perto desta corrente
        for r in vz:
            n = _normaliza(r, V_ll, f_hz)
            n.update(fabricante=nome, modelo=f"{r['I']:g} A", classe=p.get("classe", ""), url=p.get("url", ""),
                     consulta=p.get("consulta", ""))
            linhas.append(n)
        fontes.append(dict(player=nome, fabricante=p.get("fabricante", ""), url=p.get("url", ""), consulta=p.get("consulta", ""),
                           tensao=p.get("tensao", ""), classe=p.get("classe", ""), nota=p.get("nota", "")))
    ok = [x for x in linhas if not x["conferir"]]

    def faixa(k):
        v = [x[k] for x in ok if x.get(k) is not None]
        return (min(v), max(v)) if v else None
    fx = dict(uk_pct=faixa("uk_pct"), fr_Hz=faixa("fr_Hz"), Cy_uF=faixa("Cy_uF"), W_por_A=faixa("W_por_A"), L_uH=faixa("L_uH"))
    checks = []

    def chk(nome, val, lo, hi, txt_fora, unid="", fmt="{:.0f}"):
        if val is None or lo is None:
            return
        dentro = lo <= val <= hi
        checks.append(dict(item=nome, valor=fmt.format(val) + unid, faixa=f"{fmt.format(lo)}–{fmt.format(hi)}{unid}",
                           status="ok" if dentro else "atencao", nota="" if dentro else txt_fora))
    if fx["uk_pct"]:
        chk("Indutância (uk na tensão/frequência do projeto) × players", nosso["uk_pct"], fx["uk_pct"][0] - 1, fx["uk_pct"][1] + 1,
            "fora da faixa dos players: justificar (uk menor = queda de tensão menor e mais ondulação; uk maior = mais queda)", " %",
            "{:.1f}")
    if fx["fr_Hz"]:
        chk("Ressonância LC × players", nosso["fr_Hz"], fx["fr_Hz"][0] * 0.8, fx["fr_Hz"][1] * 1.2,
            "fora da faixa: conferir fr/fs (0,20–0,35) e a filtragem da fs", " Hz")
    if fx["W_por_A"] and nosso["W_por_A"]:
        chk("Perdas por ampère × players", nosso["W_por_A"], 0, fx["W_por_A"][1] * 1.1,
            "perdas acima dos players: rever indutor (núcleo/cobre) e ventilação", " W/A", "{:.2f}")
    return dict(nosso=nosso, linhas=linhas, faixa=fx, checks=checks, fontes=fontes, V_ll=V_ll, f_hz=f_hz, I=float(I))


def de_projeto(proj, arr=None):
    """Monta a comparação a partir do projeto do filtro senoidal.

    v1.32.0 (REQ-SEN-026, auditoria A&W A6) – comparação LIKE-FOR-LIKE:
      • massa: os players publicam o filtro ABERTO (IP00/IP20, sem armário) → comparar o CONJUNTO LC sem a caixa
        (indutor + capacitores); a massa com a caixa vai só como informação;
      • perdas: indutor + capacitores (+ resistores), sem cabos e ventilação do painel – como no datasheet dos players;
      • queda: os players declaram a perda de INSERÇÃO (queda real na saída) → comparar com a nossa inserção real, não com o
        uk (queda reativa X·I), que fica na coluna uk calculada igual para todos."""
    ped = proj.pedido
    V = float(ped.get("tensao_v") or 440)
    f = float(ped.get("freq_rede_hz") or 60)
    b = proj.banco
    try:
        from .documentos import insercao_pct
        queda = round(insercao_pct(proj), 1)
    except Exception:
        queda = None
    massa_tot = float(getattr(arr, "massa_total_kg", 0) or 0)
    massa_lc = None
    if massa_tot and arr is not None:
        try:
            m_cx = round(7.85 * 1.5 * 2 * (arr.caixa_l * arr.caixa_a + arr.caixa_l * arr.caixa_p + arr.caixa_a * arr.caixa_p) / 1e6, 0)
            massa_lc = max(massa_tot - m_cx - 15.0, 0.0) or None
        except Exception:
            massa_lc = None
    pw = dict(getattr(arr, "perdas_w", {}) or {})
    p_lc = sum(v for k, v in pw.items() if not str(k).lower().startswith(("cabos", "vent"))) or None
    comp = comparar(float(proj.l1.i_nom_a), V, f, float(proj.l1.l_uh), float(b.c_y_uf),
                    perdas_W=p_lc or (float(getattr(arr, "perda_total_w", 0) or 0) or None),
                    massa_kg=massa_lc or (massa_tot or None), fs_kHz=float(proj.fs_hz) / 1000, queda_pct=queda)
    comp["nosso"]["modelo"] = "conjunto LC sem caixa (comparável)" if massa_lc else "projeto (massa com a caixa)"
    if massa_lc and massa_tot:
        comp["nosso"]["nota"] = (f"massa com a caixa {massa_tot:.0f} kg; perdas do painel completo {float(arr.perda_total_w):.0f} W; "
                                 f"queda = perda de inserção real (uk reativo {proj.l1.queda_v_pct:.1f} %)")
    comp["base"] = ("Like-for-like: conjunto LC aberto (indutor + capacitores) × filtro aberto dos players; queda = inserção real. "
                    "Reator × reator não é comparável: os players não publicam o reator isolado.")
    return comp


def _f(v, fmt="{:.0f}"):
    return "–" if v is None else fmt.format(v)


def linhas_md(comp):
    from . import checagem as CK
    n = comp["nosso"]
    L = ["## Comparação com os players mundiais (REQ-SEN-024)", "",
         f"Normalizado para {comp['V_ll']:g} V / {comp['f_hz']:g} Hz: C em estrela (Δ × 3), fr = 1/(2π√(L·Cy)), uk = 2π·f·L·I/(V/√3). "
         "Só datasheet oficial (link e data na planilha 01_Engenharia/6_Players_Mercado).", comp.get("base", ""), "",
         "| Fabricante | Modelo | I (A) | L (µH) | C estrela (µF) | fr (Hz) | uk (%) | Perdas (W/A) | Massa (kg/A) | fs mín (kHz) | Queda (%) |",
         "|---|---|---|---|---|---|---|---|---|---|---|"]
    for x in [n] + comp["linhas"]:
        L.append(f"| {x['fabricante']}{' (conferir)' if x.get('conferir') else ''} | {x['modelo']} | {x['I']:g} | {_f(x.get('L_uH'))} | "
                 f"{_f(x.get('Cy_uF'), '{:.1f}')} | {_f(x.get('fr_Hz'))} | {_f(x.get('uk_pct'), '{:.1f}')} | {_f(x.get('W_por_A'), '{:.2f}')} | "
                 f"{_f(x.get('kg_por_A'), '{:.2f}')} | {_f(x.get('fs_min'), '{:g}')} | {_f(x.get('queda'), '{:g}')} |")
    if comp["checks"]:
        L += ["", "| Critério | Projeto | Faixa dos players | Check | Nota |", "|---|---|---|---|---|"]
        for c in comp["checks"]:
            st = CK.APROVADO if c["status"] == "ok" else CK.ATENCAO
            L.append(f"| {c['item']} | {c['valor']} | {c['faixa']} | {CK.texto(st)} | {c['nota']} |")
    L.append("")
    return L


def salvar_xlsx(comp, arq, cod=""):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    wb = Workbook()
    ws = wb.active
    ws.title = "Comparativo"
    ws.append([f"Filtro senoidal {cod} × players mundiais – {comp['I']:g} A, {comp['V_ll']:g} V, {comp['f_hz']:g} Hz (REQ-SEN-024)"])
    ws["A1"].font = Font(bold=True, size=12)
    ws.append(["C normalizado em estrela (Δ × 3); fr = 1/(2π√(L·Cy)); uk = 2π·f·L·I/(V/√3) na tensão/frequência do projeto. "
               "Linhas '(conferir)' não entram na faixa. " + comp.get("base", "")])
    ws.append([])
    cab = ["Fabricante", "Modelo", "I (A)", "L (µH)", "C publicado (µF)", "Conexão", "C estrela (µF)", "fr (Hz)", "uk (%)",
           "Perdas (W)", "Perdas (W/A)", "Massa (kg)", "Massa (kg/A)", "fs mín (kHz)", "Queda (%)", "Classe", "Fonte (link)", "Consulta"]
    ws.append(cab)
    for c in ws[4]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="1F3A5F")
        c.alignment = Alignment(wrap_text=True, vertical="center")
    n = comp["nosso"]
    rows = [n] + comp["linhas"]
    for x in rows:
        ws.append([x["fabricante"] + (" (conferir)" if x.get("conferir") else ""), x["modelo"], x["I"],
                   None if x.get("L_uH") is None else round(x["L_uH"], 1), x.get("C_uF", x.get("Cy_uF") if x is n else None),
                   x.get("con", "Y" if x is n else ""), None if x.get("Cy_uF") is None else round(x["Cy_uF"], 1),
                   None if x.get("fr_Hz") is None else round(x["fr_Hz"]), None if x.get("uk_pct") is None else round(x["uk_pct"], 2),
                   x.get("P_W"), None if x.get("W_por_A") is None else round(x["W_por_A"], 2), x.get("m_kg"),
                   None if x.get("kg_por_A") is None else round(x["kg_por_A"], 3), x.get("fs_min"), x.get("queda"), x.get("classe", ""),
                   x.get("url", ""), x.get("consulta", "")])
    for c in ws[5]:
        c.fill = PatternFill("solid", fgColor="FFF2CC")
        c.font = Font(bold=True)
    ws.append([])
    ws.append(["Critério", "Projeto", "Faixa dos players", "Check", "Nota"])
    for c in ws[ws.max_row]:
        c.font = Font(bold=True)
    for c in comp["checks"]:
        ws.append([c["item"], c["valor"], c["faixa"], "APROVADO" if c["status"] == "ok" else "ATENÇÃO", c["nota"]])
    for col, w in zip("ABCDEFGHIJKLMNOPQR", (30, 10, 8, 9, 12, 8, 12, 9, 8, 10, 11, 10, 11, 10, 9, 22, 60, 11)):
        ws.column_dimensions[col].width = w
    wf = wb.create_sheet("Fontes")
    wf.append(["Player", "Fabricante", "Tensão / condição", "Classe", "Nota", "Link do datasheet", "Consulta"])
    for c in wf[1]:
        c.font = Font(bold=True)
    for s in comp["fontes"]:
        wf.append([s["player"], s["fabricante"], s["tensao"], s["classe"], s["nota"], s["url"], s["consulta"]])
    for col, w in zip("ABCDEFG", (28, 34, 34, 22, 70, 70, 11)):
        wf.column_dimensions[col].width = w
    wc = wb.create_sheet("Criterios")
    for t in __doc__.strip().splitlines():
        wc.append([t])
    wc.column_dimensions["A"].width = 140
    os.makedirs(os.path.dirname(arq) or ".", exist_ok=True)
    wb.save(arq)
    return arq
