"""Gera a planilha de validação (filtros reais × plataforma) a partir de resultado_todos.json."""
import json, os, sys
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

AQUI = os.path.dirname(os.path.abspath(__file__))
dados = json.load(open(os.path.join(AQUI, "resultado_todos.json")))
saida = sys.argv[1] if len(sys.argv) > 1 else os.path.join(AQUI, "Validacao_FSEN_casos_reais.xlsx")

wb = Workbook()
ws = wb.active
ws.title = "Comparação"
cab = ["Caso", "Cliente / referência", "Status em campo", "V", "I (A)", "fs (kHz)",
       "SEU: L (µH)", "SEU: uk %", "SEU: capacitores", "SEU: C Y (µF)", "SEU: fr (Hz)", "SEU: THD %", "SEU: I cap (A/un)",
       "SEU: aprovado na v1.8?", "SEU: alertas",
       "PLATAFORMA: topologia", "PLATAFORMA: L (µH)", "PLATAFORMA: uk %", "PLATAFORMA: capacitores", "PLATAFORMA: C Y (µF)",
       "PLATAFORMA: fr (Hz)", "PLATAFORMA: THD %", "PLATAFORMA: I cap (A/un)", "PLATAFORMA: custo comp. (R$)",
       "SEU: custo comp. modelo (R$)", "SEU: custo real planilha (R$)", "Δ L %", "Δ C %"]
ws.append(cab)
azul = PatternFill("solid", fgColor="DDEBF7")
verde = PatternFill("solid", fgColor="E2EFDA")
for c in ws[1]:
    c.font = Font(bold=True)
    c.alignment = Alignment(wrap_text=True, vertical="top")
    c.fill = azul if c.value.startswith("SEU") else (verde if c.value.startswith("PLATAFORMA") else PatternFill())
for k, d in dados.items():
    c, r, a = d["caso"], d["real"], d["auto"]
    ws.append([k, c["cliente"], c["status"], c["tensao_v"], c["corrente_a"], c["fs_khz"],
               r["L1_uH"], r["uk"], r["cap"], r["C_y_uF"], r["fr"], r["thd_max"], r["i_cap_unit"],
               "SIM" if r["aprovado"] else "NÃO: " + "; ".join(r["falhas"]), "; ".join(r["alertas"]),
               a["topologia"], a["L1_uH"], a["uk"], a["cap"], a["C_y_uF"], a["fr"], a["thd_max"], a["i_cap_unit"], a["custo_comp"],
               r["custo_comp"], c["real"].get("custo"),
               round(100 * (a["L1_uH"] / r["L1_uH"] - 1)), round(100 * (a["C_y_uF"] / r["C_y_uF"] - 1))])
larg = [11, 34, 30, 6, 7, 7, 9, 7, 22, 9, 8, 7, 9, 30, 60, 11, 9, 7, 22, 9, 8, 7, 9, 11, 11, 11, 7, 7]
for i, w in enumerate(larg, 1):
    ws.column_dimensions[get_column_letter(i)].width = w
for row in ws.iter_rows(min_row=2):
    for c in row:
        c.alignment = Alignment(wrap_text=True, vertical="top")
ws.freeze_panes = "C2"

m = wb.create_sheet("Medições de campo")
m.append(["Medição", "Filtro", "Condição", "Grandeza", "Medido", "Previsto plataforma", "Observação"])
for c in m[1]:
    c.font = Font(bold=True)
for linha in json.load(open(os.path.join(AQUI, "medicoes.json"))):
    m.append(linha)
for i, w in enumerate([26, 26, 30, 26, 16, 18, 70], 1):
    m.column_dimensions[get_column_letter(i)].width = w
for row in m.iter_rows(min_row=2):
    for c in row:
        c.alignment = Alignment(wrap_text=True, vertical="top")

n = wb.create_sheet("Conclusões")
for t in json.load(open(os.path.join(AQUI, "conclusoes.json"))):
    n.append([t])
n.column_dimensions["A"].width = 140
for row in n.iter_rows():
    for c in row:
        c.alignment = Alignment(wrap_text=True, vertical="top")
n["A1"].font = Font(bold=True, size=13)
wb.save(saida)
print(saida)
