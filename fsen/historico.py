"""Banco de projetos/clientes (SQLite) + importador das pastas antigas do Drive.

- Cada projeto processado é registrado (cliente, dados técnicos, L, C, preço, status).
- `buscar_similares` devolve projetos anteriores parecidos (tensão, corrente, topologia) para
  reaproveitar soluções já testadas/fornecidas.
- `importar_pastas` varre a árvore de pastas antigas (ex.: "6 - FILTRO SENOIDAL LC") e cataloga
  clientes e arquivos, extraindo corrente/tensão do nome das pastas e arquivos.
"""
from __future__ import annotations
import os
import re
import json
import sqlite3
import datetime as _dt
from typing import List, Dict, Any, Optional

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PADRAO = os.path.join(RAIZ, "dados", "historico.db")

ESQUEMA = """
CREATE TABLE IF NOT EXISTS projetos (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  codigo TEXT, data TEXT, cliente TEXT, cnpj TEXT, cidade_uf TEXT, revenda INTEGER,
  topologia TEXT, tensao_v REAL, corrente_a REAL, quantidade INTEGER, inversor TEXT, fs_khz REAL,
  motor_cv REAL, aplicacao TEXT, l_uh REAL, c_y_uf REAL, capacitor TEXT, n_capacitores INTEGER, ligacao TEXT,
  rd_ohm REAL, fr_hz REAL, caixa TEXT, custo_unit REAL, preco_unit REAL, status TEXT, origem TEXT,
  pasta TEXT, json TEXT
);
CREATE TABLE IF NOT EXISTS arquivos_legado (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  pasta_cliente TEXT, cliente TEXT, topologia TEXT, arquivo TEXT, caminho TEXT, extensao TEXT,
  corrente_a REAL, tensao_v REAL, modificado TEXT
);
CREATE TABLE IF NOT EXISTS cotacoes_fornecedor (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  data TEXT, fornecedor TEXT, grupo TEXT, descricao TEXT, parametro REAL, preco REAL, prazo TEXT, projeto TEXT
);
"""


def conectar(db: str = DB_PADRAO):
    os.makedirs(os.path.dirname(db), exist_ok=True)
    con = sqlite3.connect(db)
    con.executescript(ESQUEMA)
    return con


def registrar_projeto(proj, arr, orc, pasta, status="cotado", origem="plataforma", db: str = DB_PADRAO):
    from .desenhos import proj_codigo
    ped = proj.pedido
    con = conectar(db)
    con.execute("""INSERT INTO projetos (codigo,data,cliente,cnpj,cidade_uf,revenda,topologia,tensao_v,corrente_a,quantidade,inversor,
                 fs_khz,motor_cv,aplicacao,l_uh,c_y_uf,capacitor,n_capacitores,ligacao,rd_ohm,fr_hz,caixa,custo_unit,preco_unit,status,origem,pasta,json)
                 VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (proj_codigo(proj), _dt.datetime.now().isoformat(timespec="seconds"), ped["cliente"], ped["cnpj"], ped["cidade_uf"],
                 int(bool(ped["revenda"])), proj.topologia, ped["tensao_v"], ped["corrente_a"], ped["quantidade"], ped["inversor"],
                 proj.fs_hz / 1000, ped["motor_cv"], ped["aplicacao"], proj.l1.l_uh, proj.banco.c_y_uf, proj.banco.cap_id,
                 proj.banco.n_total, proj.banco.ligacao, proj.amortecimento.r_ramo_ohm if proj.amortecimento else 0.0, proj.fr_hz,
                 arr.caixa_id, orc.custo_unit_total, orc.preco_unit, status, origem, pasta,
                 json.dumps(ped, ensure_ascii=False)))
    con.commit()
    con.close()


def buscar_similares(tensao_v: float, corrente_a: float, topologia: str = "LC", n: int = 5, db: str = DB_PADRAO) -> List[Dict[str, Any]]:
    con = conectar(db)
    con.row_factory = sqlite3.Row
    rows = con.execute("SELECT * FROM projetos").fetchall()
    leg = con.execute("SELECT * FROM arquivos_legado WHERE corrente_a IS NOT NULL").fetchall()
    con.close()
    res = []
    for r in rows:
        dist = abs(r["corrente_a"] - corrente_a) / max(corrente_a, 1) + 2 * abs(r["tensao_v"] - tensao_v) / max(tensao_v, 1) \
            + (0.3 if r["topologia"] != topologia else 0)
        res.append({**dict(r), "distancia": round(dist, 3), "fonte": "projeto"})
    vistos = set()
    for r in leg:
        chave = (r["pasta_cliente"], r["corrente_a"])
        if chave in vistos:
            continue
        vistos.add(chave)
        tv = r["tensao_v"] or tensao_v
        dist = abs(r["corrente_a"] - corrente_a) / max(corrente_a, 1) + 2 * abs(tv - tensao_v) / max(tensao_v, 1) \
            + (0.3 if (r["topologia"] or topologia) != topologia else 0)
        res.append({"cliente": r["cliente"], "corrente_a": r["corrente_a"], "tensao_v": r["tensao_v"], "topologia": r["topologia"],
                    "pasta": r["pasta_cliente"], "arquivo": r["arquivo"], "distancia": round(dist, 3), "fonte": "legado"})
    res.sort(key=lambda x: x["distancia"])
    return res[:n]


RE_CORR = re.compile(r"(\d{1,4}(?:[.,]\d)?)\s*A(?![a-z])", re.I)
RE_TENS = re.compile(r"(220|380|400|440|460|480|500|525|575|600|690)\s*V", re.I)


def _cliente_de_pasta(nome):
    n = re.sub(r"^\d+\s*[-–_.]\s*", "", nome).strip()
    n = re.sub(r"\b(FILTRO|SENOIDAL|LCL|LC|SINE|WAVE)\b", "", n, flags=re.I).strip(" -_")
    return n or nome


def importar_pastas(raizes: List[str], db: str = DB_PADRAO) -> Dict[str, Any]:
    """Varre pastas de projetos antigos. Estrutura esperada: <raiz>/<CLIENTE ou PROJETO>/arquivos.
    `raizes` = caminhos locais (Google Drive para desktop, ex.: G:/Meu Drive/.../6 - FILTRO SENOIDAL LC)."""
    con = conectar(db)
    n = 0
    clientes = set()
    for raiz in raizes:
        topo = "LCL" if "LCL" in os.path.basename(raiz).upper() else "LC"
        for pasta_cli in sorted(os.listdir(raiz)):
            cam_cli = os.path.join(raiz, pasta_cli)
            if not os.path.isdir(cam_cli):
                continue
            cliente = _cliente_de_pasta(pasta_cli)
            clientes.add((cliente, topo))
            for dirpath, _, files in os.walk(cam_cli):
                for f in files:
                    txt = f"{pasta_cli} {os.path.relpath(dirpath, cam_cli)} {f}"
                    mc = RE_CORR.search(txt)
                    mt = RE_TENS.search(txt)
                    cam = os.path.join(dirpath, f)
                    mod = _dt.datetime.fromtimestamp(os.path.getmtime(cam)).isoformat(timespec="seconds")
                    con.execute("INSERT INTO arquivos_legado (pasta_cliente,cliente,topologia,arquivo,caminho,extensao,corrente_a,tensao_v,modificado) "
                                "VALUES (?,?,?,?,?,?,?,?,?)",
                                (pasta_cli, cliente, topo, f, cam, os.path.splitext(f)[1].lower(),
                                 float(mc.group(1).replace(",", ".")) if mc else None, float(mt.group(1)) if mt else None, mod))
                    n += 1
    con.commit()
    con.close()
    return {"arquivos": n, "clientes": sorted(clientes)}


def exportar_clientes_xlsx(caminho: str, db: str = DB_PADRAO):
    """Planilha 'Clientes fornecidos' consolidando projetos da plataforma e pastas legadas."""
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    con = conectar(db)
    con.row_factory = sqlite3.Row
    wb = Workbook()
    ws = wb.active
    ws.title = "Clientes"
    ws.append(["Cliente", "Topologia", "Corrente (A)", "Tensão (V)", "Qtd", "Data", "Preço unit. (R$)", "Status", "Origem", "Pasta"])
    for r in con.execute("SELECT * FROM projetos ORDER BY data DESC"):
        ws.append([r["cliente"], r["topologia"], r["corrente_a"], r["tensao_v"], r["quantidade"], r["data"][:10], r["preco_unit"],
                   r["status"], "plataforma", r["pasta"]])
    q = """SELECT pasta_cliente, cliente, topologia, MAX(corrente_a) ca, MAX(tensao_v) tv, MAX(modificado) m, COUNT(*) n
           FROM arquivos_legado GROUP BY pasta_cliente, topologia ORDER BY m DESC"""
    for r in con.execute(q):
        ws.append([r["cliente"], r["topologia"], r["ca"], r["tv"], None, (r["m"] or "")[:10], None, "fornecido (legado)",
                   f"pasta antiga ({r['n']} arquivos)", r["pasta_cliente"]])
    for c in ws[1]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="1F3A5F")
    for col, w in zip("ABCDEFGHIJ", [40, 10, 12, 10, 6, 12, 16, 18, 22, 50]):
        ws.column_dimensions[col].width = w
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    wa = wb.create_sheet("Arquivos legados")
    wa.append(["Pasta", "Cliente", "Topologia", "Arquivo", "Corrente", "Tensão", "Modificado", "Caminho"])
    for r in con.execute("SELECT * FROM arquivos_legado ORDER BY pasta_cliente"):
        wa.append([r["pasta_cliente"], r["cliente"], r["topologia"], r["arquivo"], r["corrente_a"], r["tensao_v"], r["modificado"], r["caminho"]])
    con.close()
    wb.save(caminho)
    return caminho


def registrar_cotacao_fornecedor(fornecedor, grupo, descricao, parametro, preco, prazo="", projeto="", db: str = DB_PADRAO):
    """Guarda preço real recebido (ex.: indutor: parametro = energia J). Usado para recalibrar o modelo de custo."""
    con = conectar(db)
    con.execute("INSERT INTO cotacoes_fornecedor (data,fornecedor,grupo,descricao,parametro,preco,prazo,projeto) VALUES (?,?,?,?,?,?,?,?)",
                (_dt.date.today().isoformat(), fornecedor, grupo, descricao, parametro, preco, prazo, projeto))
    con.commit()
    con.close()


def calibrar_custo_indutor(db: str = DB_PADRAO) -> Optional[Dict[str, float]]:
    """Regressão linear preço = base + k·energia com as cotações reais de indutores (≥ 2 pontos)."""
    import numpy as np
    con = conectar(db)
    pts = con.execute("SELECT parametro, preco FROM cotacoes_fornecedor WHERE grupo='INDUTOR' AND parametro>0").fetchall()
    con.close()
    if len(pts) < 2:
        return None
    x = np.array([p[0] for p in pts])
    y = np.array([p[1] for p in pts])
    k, base = np.polyfit(x, y, 1)
    return {"base": float(max(base, 0)), "k_energia": float(k), "n": len(pts)}
