"""Calibração do cálculo do indutor com medições reais (v1.11.8).

Fluxo:
1) A plataforma gera `Resultados_Medidos_Indutor_<cód>.xlsx` (01_Engenharia/3_Indutor_Elementos_Finitos) com os valores PREVISTOS de
   cada ensaio e uma coluna "Medido" em branco.
2) O engenheiro preenche com o relatório do fabricante (protótipo) – ou com dados de indutores antigos – e carrega na tela
   de conferência.
3) `avaliar()` compara medido × previsto, aplica as tolerâncias, grava o histórico em dados/calibracao_indutores.json e
   devolve os fatores medidos/previstos. `fatores_sugeridos()` resume o histórico (mediana) – NÃO são aplicados
   automaticamente ao cálculo: o engenheiro decide (determinismo).
"""
import datetime as _dt
import json
import math
import os
import statistics

ARQ_HIST = os.path.join(os.path.dirname(os.path.dirname(__file__)), "dados", "calibracao_indutores.json")

GRANDEZAS = [
    # chave, descrição, unidade, tolerância (%), tipo ('bilateral' | 'max')
    ("L_U", "Indutância fase U (60 Hz, In)", "µH", 5, "bilateral"),
    ("L_V", "Indutância fase V (60 Hz, In)", "µH", 5, "bilateral"),
    ("L_W", "Indutância fase W (60 Hz, In)", "µH", 5, "bilateral"),
    ("L_sat_pct", "L em Isat (% da nominal)", "%", 0, "min90"),
    ("L_ovl_pct", "L na sobrecarga (% da nominal)", "%", 0, "min70"),
    ("Rdc", "Resistência CC por fase (20 °C)", "mΩ", 5, "bilateral"),
    ("Rs_60", "R série 60 Hz (LCR)", "mΩ", 10, "bilateral"),
    ("Rs_fs", "R série na frequência de chaveamento (LCR)", "mΩ", 30, "bilateral"),
    ("P_60", "Perdas em 60 Hz na In (3 fases)", "W", 15, "max"),
    ("P_tot", "Perdas totais com inversor", "W", 15, "max"),
    ("dT_bob", "Elevação média do enrolamento", "K", 15, "max"),
    ("dT_fe", "Elevação do núcleo", "K", 25, "max"),
    ("massa", "Massa", "kg", 10, "bilateral"),
]


def previstos(ind):
    """Valores previstos (unidades da tabela) a partir do projeto do indutor."""
    from . import ind_verificacao as V
    L = ind.get("L3d")
    L = [float(x) for x in L] if L is not None else [ind["requisitos"]["L"]] * 3
    sat = ind.get("saturacao") or []
    lsat = next((min(s.get("L_lat_pct") or 999, s.get("L_cen_pct") or 999) for s in sat if s["caso"].startswith("Isat")), None)
    lovl = next((s.get("L_lat_pct") for s in sat if s["caso"].startswith("Sobrecarga")), None)
    rac = {x["f"]: x for x in V.rac_previsto(ind)}
    fs = ind["requisitos"]["fs"]
    p = ind["perdas"]
    r1 = ind["requisitos"]["I1"]
    p60 = float(p.get("enrolamento_60Hz", 0)) + float(p.get("nucleo_60Hz", 0))
    rho20 = 1.72e-8
    rdc20 = float(ind.get("Rdc_ohm") or ind.get("R") or 0) * rho20 / float(ind.get("rhoT", rho20) or rho20)
    return dict(L_U=L[0] * 1e6, L_V=L[1] * 1e6, L_W=L[2] * 1e6, L_sat_pct=lsat, L_ovl_pct=lovl, Rdc=rdc20 * 1e3,
                Rs_60=rac.get(60.0, {}).get("R_tot", 0) * 1e3, Rs_fs=rac.get(float(fs), {}).get("R_tot", 0) * 1e3,
                P_60=p60, P_tot=float(p["total"]), dT_bob=float(ind["termico"]["elev_bobina_K"]),
                dT_fe=float(ind["termico"].get("elev_nucleo_K", 0)), massa=float(ind["massa_kg"]["total"]))


def planilha(ind, arq, cod):
    """Gera a planilha de resultados medidos (previsto preenchido, medido em branco)."""
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    wb = Workbook()
    ws = wb.active
    ws.title = "Medido x Previsto"
    ws["A1"] = f"Calibração do indutor – {cod} – preencher a coluna 'Medido' com o relatório do fabricante"
    ws["A1"].font = Font(bold=True, size=12)
    ws["A2"] = "Unidade/identificação:"
    ws["C2"] = ""
    ws["A3"] = "Origem dos dados (protótipo / unidade antiga / laboratório):"
    ws["C3"] = ""
    cab = ["Chave", "Grandeza", "Unidade", "Previsto", "Medido", "Tolerância", "Medido/Previsto", "Situação"]
    for j, c in enumerate(cab, start=1):
        x = ws.cell(row=5, column=j, value=c)
        x.font = Font(bold=True)
        x.fill = PatternFill("solid", fgColor="DDE6F3")
    pv = previstos(ind)
    for i, (k, desc, un, tol, tipo) in enumerate(GRANDEZAS, start=6):
        ws.cell(row=i, column=1, value=k)
        ws.cell(row=i, column=2, value=desc)
        ws.cell(row=i, column=3, value=un)
        v = pv.get(k)
        ws.cell(row=i, column=4, value=(round(v, 3) if isinstance(v, (int, float)) and v == v else None))
        ws.cell(row=i, column=5).fill = PatternFill("solid", fgColor="FFF6D5")
        ws.cell(row=i, column=6, value={"bilateral": f"±{tol} %", "max": f"≤ +{tol} %", "min90": "≥ 90 %", "min70": "≥ 70 %"}[tipo])
        ws.cell(row=i, column=7, value=f'=IF(E{i}="","",E{i}/D{i})')
    ws["A20"] = "Fatores medidos/previstos alimentam o histórico de calibração da plataforma (não são aplicados automaticamente)."
    for col, w in zip("ABCDEFGH", (11, 44, 8, 11, 11, 11, 15, 12)):
        ws.column_dimensions[col].width = w
    wb.save(arq)
    return arq


def avaliar(arq_xlsx, cod=None, gravar=True):
    """Lê a planilha preenchida, compara e (opcional) grava no histórico. Devolve lista de linhas e fatores."""
    from openpyxl import load_workbook
    ws = load_workbook(arq_xlsx, data_only=True).active
    tol = {k: (t, tp) for k, _, _, t, tp in GRANDEZAS}
    linhas, fatores = [], {}
    for row in ws.iter_rows(min_row=6, max_row=6 + len(GRANDEZAS) - 1, values_only=True):
        k, desc, un, prev, med = row[:5]
        if not k or k not in tol:
            continue
        if med in (None, ""):
            linhas.append(dict(chave=k, grandeza=desc, unidade=un, previsto=prev, medido=None, razao=None, situacao="não medido"))
            continue
        med = float(med)
        t, tp = tol[k]
        if tp == "min90":
            ok, razao = med >= 90, None
        elif tp == "min70":
            ok, razao = med >= 70, None
        else:
            razao = med / float(prev) if prev else None
            ok = razao is not None and ((abs(razao - 1) * 100 <= t) if tp == "bilateral" else ((razao - 1) * 100 <= t))
            if razao:
                fatores[k] = razao
        linhas.append(dict(chave=k, grandeza=desc, unidade=un, previsto=prev, medido=med, razao=razao, situacao="OK" if ok else "FORA"))
    if gravar and fatores:
        hist = historico()
        hist.append(dict(data=_dt.datetime.now().isoformat(timespec="seconds"), codigo=cod or os.path.basename(arq_xlsx),
                         unidade=str(ws["C2"].value or ""), origem=str(ws["C3"].value or ""), fatores=fatores))
        os.makedirs(os.path.dirname(ARQ_HIST) or ".", exist_ok=True)
        json.dump(hist, open(ARQ_HIST, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return dict(linhas=linhas, fatores=fatores)


def historico():
    try:
        return json.load(open(ARQ_HIST, encoding="utf-8"))
    except Exception:
        return []


def fatores_sugeridos():
    """Mediana dos fatores medido/previsto do histórico, por grandeza (com nº de amostras)."""
    acc = {}
    for h in historico():
        for k, v in h.get("fatores", {}).items():
            if isinstance(v, (int, float)) and math.isfinite(v):
                acc.setdefault(k, []).append(v)
    return {k: dict(fator=statistics.median(v), n=len(v)) for k, v in acc.items()}
