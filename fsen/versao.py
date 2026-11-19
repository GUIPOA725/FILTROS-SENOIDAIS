"""Nome e versão da plataforma – carimbados na tela e em TODOS os arquivos gerados (rastreabilidade)."""
import json
import os
import datetime as _dt

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NOME = "Plataforma FSEN – Filtros Senoidais (Electric Service)"
NOME_CURTO = "Plataforma FSEN"


def info():
    try:
        return json.load(open(os.path.join(RAIZ, "versao_plataforma.json"), encoding="utf-8"))
    except Exception:
        return {"versao": "?", "data": ""}


VERSAO = info().get("versao", "?")


def assinatura(curta=False, data=True):
    """Ex.: 'Plataforma FSEN v1.8.2 – gerado em 19/11/2026 16:50'."""
    v = info().get("versao", VERSAO)
    s = f"{NOME_CURTO if curta else NOME} v{v}"
    return s + (f" – gerado em {_dt.datetime.now():%d/%m/%Y %H:%M}" if data else "")


def carimbar_pasta(pasta, log=None):
    """Põe nome + versão em todos os documentos da pasta do projeto: rodapé dos .docx, propriedades + aba 'Plataforma'
    dos .xlsx, linha final dos e-mails/.txt e campo 'gerado_por' dos .json."""
    sig = assinatura()
    n = 0
    for raiz, _, fs in os.walk(pasta):
        for f in fs:
            c = os.path.join(raiz, f)
            try:
                if f.lower().endswith(".docx"):
                    from docx import Document
                    from docx.shared import Pt
                    d = Document(c)
                    for s in d.sections:
                        p = s.footer.add_paragraph()
                        r = p.add_run(sig)
                        r.font.size = Pt(7)
                    d.core_properties.comments = sig
                    d.core_properties.author = d.core_properties.author or NOME_CURTO
                    d.save(c)
                elif f.lower().endswith(".xlsx"):
                    from openpyxl import load_workbook
                    wb = load_workbook(c)
                    wb.properties.creator = NOME_CURTO
                    wb.properties.description = sig
                    if "Plataforma" not in wb.sheetnames:
                        ws = wb.create_sheet("Plataforma")
                        ws.append(["Gerado por", NOME])
                        ws.append(["Versão", info().get("versao", VERSAO)])
                        ws.append(["Data", f"{_dt.datetime.now():%d/%m/%Y %H:%M}"])
                        ws.column_dimensions["A"].width = 14
                        ws.column_dimensions["B"].width = 60
                    wb.save(c)
                elif f.lower().endswith(".txt") and f != "rodar_atp.bat":
                    with open(c, "a", encoding="utf-8") as fh:
                        fh.write(f"\n\n[Ref. interna: {sig}]\n")
                elif f.lower().endswith(".json"):
                    dd = json.load(open(c, encoding="utf-8"))
                    if isinstance(dd, dict):
                        dd["gerado_por"] = sig
                        json.dump(dd, open(c, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
                else:
                    continue
                n += 1
            except Exception as e:      # nunca derruba a geração por causa do carimbo
                if log:
                    log(f"(carimbo de versão não aplicado em {f}: {e})")
    return n
