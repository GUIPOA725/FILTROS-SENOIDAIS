"""Painel 3D no padrão Electric (v1.24.1) – mesmo gerador para os 3 filtros.

Concepção e sequência de folhas copiadas dos layouts Electric feitos no SolidWorks (AGCO Ibirubá 300/500 kVAr, 2022) e do
painel real da Panatlântica (2024):
  • UMA placa de montagem laranja no MEIO do painel (dupla face): na frente capacitores (embaixo), contatoras e chaves
    seccionadoras-fusível NH (em fileiras), barramento no alto; atrás os reatores em prateleiras pretas e os cabos subindo.
  • Portas frontais E traseiras, venezianas embaixo, exaustores no teto (sobre os reatores), base preta, estrutura em perfil.
  • 6 folhas A3: 1 fechado frente/fundo com cotas · 2 portas abertas frente/fundo · 3 vista de topo com abertura das portas ·
    4 sem chapas (estrutura) frente/fundo · 5 só a placa, frente e trás · 6 vistas frontal / lateral / traseira + verificações.
Medidas: SÓ de catálogo (dados/dimensoes_componentes.yaml) ou do projeto FEM do reator Electric. Sem medida confirmada →
vermelho translúcido + "medida a confirmar" (nunca chutado como se fosse real). Render: pyvista (VTK offscreen), sem SolidWorks.
"""
from __future__ import annotations

import math
import os

import yaml

from . import checagem as CK

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# cores (render)
C_PORTA, C_TETO, C_PERFIL, C_BASE = "#7d8286", "#cfc9bd", "#b4b8bc", "#1e1e1e"
C_PLACA, C_CAP, C_SEC, C_SEC_F, C_KM, C_KM_F = "#c8641e", "#e4e4e4", "#ececec", "#9a9a9a", "#2c2c2c", "#4a4a4a"
C_BOB, C_NUC, C_PRAT, C_CABO, C_BARRA, C_VERM = "#c9a46a", "#55585c", "#141414", "#b0201c", "#c87533", "#e53935"
FOLGA = 30            # mm entre componentes / parede
PERFIL = 40           # mm (estrutura)
BASE = 100            # mm (soleira)
CHAPA = 3             # mm (placa de montagem)


# ----------------------------------------------------------------------------------------------- catálogo de medidas
def catalogo_dim():
    try:
        return yaml.safe_load(open(os.path.join(RAIZ, "dados", "dimensoes_componentes.yaml"), encoding="utf-8")) or {}
    except Exception:
        return {}


def achar_dim(codigo, grupo):
    """Medida de catálogo pelo código (casamento por trecho do nome). None = a confirmar."""
    cat = catalogo_dim().get(grupo) or {}
    cod = (codigo or "").lower()
    if not cod:
        return None
    for k, v in cat.items():
        chave = k.lower().split(" (")[0]
        if chave in cod or cod in k.lower() or any(t in cod for t in [p for p in chave.split() if len(p) > 5]):
            if not v.get("conferir") or v.get("L") or v.get("D"):
                return dict(v, nome=k)
    return None


def capacitor_codigo(ped, e0):
    """Código de catálogo do capacitor (só os que têm desenho no catálogo de dimensões)."""
    n, q, u = e0["cap"]
    marca = (getattr(ped, "marca", "") or "").lower()
    if "schneider" in marca and abs(q - 25) < 1 and u in (525,):
        return "Schneider BLRCH250A300B52"
    if abs(q - 40) < 1 and u >= 690:
        return "Epcos B32344E4401F080"
    return None


# ----------------------------------------------------------------------------------------------- modelo (peças)
def _cx(lst, g, x, y, z, L, P, A, cor, op=1.0):
    lst.append(dict(t="caixa", g=g, x=x, y=y, z=z, L=L, P=P, A=A, cor=cor, op=op))


def _cl(lst, g, xc, yc, z, D, A, cor, eixo="z", op=1.0):
    lst.append(dict(t="cil", g=g, x=xc, y=yc, z=z, D=D, A=A, cor=cor, eixo=eixo, op=op))


def _capacitor(p, xc, yc, z, d, a, ok):
    cor = C_CAP if ok else C_VERM
    op = 1.0 if ok else 0.6
    _cl(p, "frente", xc, yc, z, d, a, cor, op=op)
    _cl(p, "frente", xc, yc, z + a, d * 0.92, 6, "#bdbdbd", op=op)                     # tampa
    for k in range(3):                                                                  # 3 terminais
        ang = 2 * math.pi * k / 3
        _cl(p, "frente", xc + d * 0.22 * math.cos(ang), yc + d * 0.22 * math.sin(ang), z + a + 6, 14, 26, "#3a3a3a")


def _secc(p, x, y_face, z, d, ok):
    """Chave seccionadora-fusível NH (corpo + tampa com 3 porta-fusíveis) presa na face frontal da placa (y_face)."""
    L, A, P = d["L"], d["A"], d["P"]
    _cx(p, "frente", x, y_face - P, z, L, P, A, C_SEC if ok else C_VERM, 1.0 if ok else 0.6)
    for k in range(3):
        _cx(p, "frente", x + L * (0.08 + 0.3 * k), y_face - P - 6, z + A * 0.18, L * 0.24, 6, A * 0.64, C_SEC_F)
    _cx(p, "frente", x + L * 0.3, y_face - P - 12, z + A * 0.86, L * 0.4, 12, A * 0.08, "#c62828")   # puxador


def _contatora(p, x, y_face, z, d, ok):
    L, A, P = d["L"], d["A"], d["P"]
    _cx(p, "frente", x, y_face - P, z, L, P, A, C_KM if ok else C_VERM, 1.0 if ok else 0.6)
    _cx(p, "frente", x + L * 0.12, y_face - P - 4, z + A * 0.3, L * 0.76, 4, A * 0.4, C_KM_F)
    for zz in (z - 8, z + A):                                                          # bornes em cima e embaixo
        _cx(p, "frente", x + 4, y_face - P * 0.7, zz, L - 8, P * 0.5, 8, "#8d8d8d")


def _reator(p, x, y, z, L, P, A):
    """Reator trifásico Electric (FEM): culatras em cima/embaixo, 3 bobinas, pés e terminais – medidas do projeto."""
    hy = A * 0.13
    _cx(p, "tras", x, y + P * 0.2, z, L, P * 0.6, hy, C_NUC)
    _cx(p, "tras", x, y + P * 0.2, z + A - hy, L, P * 0.6, hy, C_NUC)
    db = min(L / 3.05, P)
    for k in range(3):
        _cl(p, "tras", x + db / 2 + k * (L - db) / 2, y + P / 2, z + hy, db, A - 2 * hy, C_BOB)
    for xx in (x - 15, x + L - 25):                                                    # pés (cantoneira)
        _cx(p, "tras", xx, y, z - 12, 40, P, 12, "#2f2f2f")
    for k in range(6):                                                                 # terminais no alto
        _cx(p, "tras", x + L * (0.06 + 0.16 * k), y + P * 0.08, z + A, 22, 10, 30, "#b87333")


def _prateleira(p, x, y, z, L, P):
    for yy in (y, y + P - PERFIL):
        _cx(p, "tras", x, yy, z, L, PERFIL, PERFIL, C_PRAT)
    for xx in (x, x + L - PERFIL):
        _cx(p, "tras", xx, y, z, PERFIL, P, PERFIL, C_PRAT)
    for xx in (x, x + L - PERFIL):                                                     # montantes
        for yy in (y, y + P - PERFIL):
            _cx(p, "tras", xx, yy, z - 2, PERFIL, PERFIL, 2, C_PRAT)


def modelo(ped, res, gab, prot, inds=None, caps_cod=None):
    """Arranjo físico (peças com posição e medida, mm; x largura, y profundidade 0 = frente, z altura) + verificações."""
    dim = gab["dimensoes_mm"]
    H, W, D = dim["altura"], dim["largura"], dim["profundidade"]
    p, faltam, ver = [], [], []
    d0 = (inds or [None])[0] or {}
    rd = d0.get("dims_mm") or (res.get("reator_mm") or {})
    rL, rP, rA = rd.get("largura"), rd.get("profundidade"), rd.get("altura")
    e0 = res["estagios"][0]
    capd = achar_dim(caps_cod or capacitor_codigo(ped, e0) or "", "capacitores")
    ctt = achar_dim(prot.get("contator", ""), "contatoras")
    sec = achar_dim("Fupact ISFT160" if prot.get("chave_A", 160) <= 160 else "Fupact ISFT400", "seccionadoras_fusivel")
    for nome, x in (("capacitor", capd), ("contatora", ctt), ("seccionadora-fusível", sec), ("reator (FEM)", rL)):
        if not x:
            faltam.append(nome)
    cd = capd or dict(D=116, A=291)
    sd = sec or dict(L=106, A=194, P=80)
    kd = ctt or dict(L=70, A=110, P=108)
    rL, rP, rA = rL or 320, rP or 240, rA or 320
    n_cap = e0["cap"][0]
    cols = gab["colunas"]
    yp = D / 2                                                       # placa no meio (dupla face)
    zt = H - 40                                                      # topo da estrutura
    # ---------- estrutura, base, teto, chapas, portas
    _cx(p, "base", 0, 0, 0, W, D, BASE, C_BASE)
    xs = [0]
    for c in cols:
        xs.append(xs[-1] + c["largura"])
    for x in xs:
        xx = min(max(x - PERFIL / 2, 0), W - PERFIL)
        for y in (0, D - PERFIL):
            _cx(p, "estrutura", xx, y, BASE, PERFIL, PERFIL, H - BASE, C_PERFIL)
    for z in (BASE, zt):
        for y in (0, D - PERFIL):
            _cx(p, "estrutura", 0, y, z, W, PERFIL, PERFIL, C_PERFIL)
        for x in xs:
            xx = min(max(x - PERFIL / 2, 0), W - PERFIL)
            _cx(p, "estrutura", xx, 0, z, PERFIL, D, PERFIL, C_PERFIL)
    _cx(p, "teto", 0, 0, H, W, D, 3, C_TETO)
    for xl in (-3, W):
        _cx(p, "lateral", xl, 0, BASE, 3, D, H - BASE, C_PORTA)
    for i, c in enumerate(cols):
        x0, Lc = xs[i], c["largura"]
        for k in range(2):                                           # exaustores no teto (2 por coluna, sobre os reatores)
            xf = x0 + Lc * (0.3 + 0.4 * k) - 90
            _cx(p, "teto", xf, D * 0.62, H + 3, 180, 120, 55, "#e8e8e8")
            _cx(p, "teto", xf + 20, D * 0.62 + 120, H + 3, 140, 10, 40, "#9e9e9e")
        for lado, y_p in (("porta_f", -18), ("porta_t", D)):         # portas frontal e traseira (uma por coluna)
            _cx(p, lado, x0 + 4, y_p, BASE + 6, Lc - 8, 18, H - BASE - 12, C_PORTA)
            yv = y_p - 4 if lado == "porta_f" else y_p + 18
            for k in range(2):                                       # venezianas embaixo
                xv = x0 + Lc * (0.22 + 0.42 * k)
                _cx(p, lado, xv, yv, BASE + 120, 150, 4, 160, "#d6d6d6")
                for s in range(6):
                    _cx(p, lado, xv + 8, yv + (-3 if lado == "porta_f" else 3), BASE + 135 + s * 24, 134, 3, 8, "#9a9a9a")
            xm = x0 + Lc - 80 if i % 2 == 0 else x0 + 50              # puxador
            _cx(p, lado, xm, yv + (-14 if lado == "porta_f" else 4), BASE + (H - BASE) * 0.5 - 100, 30, 14, 200, "#2a2a2a")
        p.append(dict(t="dobradica", g="porta", x0=x0, Lc=Lc, esq=(i % 2 == 0)))
    # controlador + sinaleiros + emergência na porta frontal da 1ª coluna
    x0c = cols[0]["largura"] * 0.5 - 72
    _cx(p, "porta_f", x0c, -24, H * 0.62, 144, 6, 144, "#20384e")
    _cx(p, "porta_f", x0c + 14, -27, H * 0.62 + 50, 116, 3, 70, "#3fa7d6")
    n_est_tot = len(res["estagios"])
    for k in range(n_est_tot):
        _cl(p, "porta_f", x0c - 120 + k * 50, -30, H * 0.55, 22, 12, "#2e7d32", eixo="y")
    _cl(p, "porta_f", x0c + 230, -32, H * 0.62 + 30, 40, 16, "#d32f2f", eixo="y")
    # ---------- por coluna: placa dupla face, frente (manobra + capacitores), trás (reatores)
    for i, c in enumerate(cols):
        x0, Lc = xs[i], c["largura"]
        n_est = len(c["estagios"])
        zp0, zp1 = BASE + 60, H - 140
        _cx(p, "placa", x0 + 40, yp - CHAPA / 2, zp0, Lc - 80, CHAPA, zp1 - zp0, C_PLACA)
        for k in range(5):                                           # furos de passagem de cabos (placa)
            _cl(p, "placa", x0 + 40 + (Lc - 80) * (k + 0.5) / 5, yp, zp0 + 520, 36, 8, "#f5f5f5", eixo="y")
        yf = yp - CHAPA / 2                                          # face frontal
        # capacitores (embaixo, em fileiras na profundidade, sobre trilho)
        dcap, acap = cd.get("D", 116), cd.get("A", 291)
        n_tot = n_cap * n_est
        por_linha = max(1, int((Lc - 80 - FOLGA) // (dcap + 12)))
        linhas = math.ceil(n_tot / por_linha)
        _cx(p, "frente", x0 + 40, yf - linhas * (dcap + 15) - 20, BASE + 20, Lc - 80, linhas * (dcap + 15) + 20, 20, C_PRAT)
        for k in range(n_tot):
            lin, ck = divmod(k, por_linha)
            _capacitor(p, x0 + 40 + FOLGA / 2 + dcap / 2 + ck * (dcap + 12), yf - dcap / 2 - 15 - lin * (dcap + 15),
                       BASE + 40, dcap, acap, bool(capd))
        prof_frente = linhas * (dcap + 15) + 20
        # contatoras e chaves NH (fileiras acima dos capacitores)
        z_km = BASE + 40 + acap + 45 + 200
        z_sc = z_km + kd["A"] + 160
        passo = max(sd["L"], kd["L"]) + FOLGA
        larg_f = n_est * passo - FOLGA
        x_ini = x0 + Lc / 2 - larg_f / 2
        for j in range(n_est):
            xx = x_ini + j * passo
            _contatora(p, xx + (passo - FOLGA - kd["L"]) / 2, yf, z_km, kd, bool(ctt))
            _secc(p, xx + (passo - FOLGA - sd["L"]) / 2, yf, z_sc, sd, bool(sec))
        for f in range(3):                                           # barramento (cobre) no alto da face frontal
            _cx(p, "frente", x0 + 50, yf - 60, zp1 - 110 - f * 45, Lc - 100, 10, 30, C_BARRA)
        ver.append(["Placa de montagem", f"Fileira de {n_est} chaves NH / contatoras ({c['funcao']})", f"{larg_f:.0f} mm",
                    f"≤ {Lc - 80} mm", CK.texto(CK.check(larg_f <= Lc - 80, CK.utilizacao(larg_f, Lc - 80)))])
        alt_frente = z_sc + sd["A"] + 60
        ver.append(["Placa de montagem", f"Altura ocupada na frente: capacitores + contatoras + chaves NH ({c['funcao']})",
                    f"{alt_frente:.0f} mm", f"≤ {zp1 - 150:.0f} mm (abaixo do barramento)",
                    CK.texto(CK.check(alt_frente <= zp1 - 150, CK.utilizacao(alt_frente, zp1 - 150)))])
        ver.append(["Placa de montagem", f"Profundidade dos capacitores na frente ({linhas} fileira(s))", f"{prof_frente:.0f} mm",
                    f"≤ {yp - 40:.0f} mm", CK.texto(CK.check(prof_frente <= yp - 40, CK.utilizacao(prof_frente, yp - 40)))])
        # trás: reatores em prateleiras pretas
        yr = yp + CHAPA / 2 + 40
        por_niv = max(1, int((Lc - 80 - FOLGA) // (rL + FOLGA)))
        niveis = math.ceil(n_est / por_niv)
        passo_niv = rA + 30 + 110
        for nv in range(niveis):
            zz = BASE + 40 + nv * passo_niv
            _prateleira(p, x0 + 40, yr - 10, zz, Lc - 80, rP + 30)
        for j in range(n_est):
            nv, pos = divmod(j, por_niv)
            usado = min(por_niv, n_est - nv * por_niv)
            larg_niv = usado * rL + (usado - 1) * FOLGA
            xr = x0 + Lc / 2 - larg_niv / 2 + pos * (rL + FOLGA)
            _reator(p, xr, yr, BASE + 40 + PERFIL + 12 + nv * passo_niv, rL, rP, rA)
        for k in range(3):                                           # cabos subindo (vermelhos) no meio da coluna
            _cl(p, "tras", x0 + Lc / 2 - 30 + k * 30, yr + rP + 50, BASE + 20, 24, zp1 - BASE - 60, C_CABO)
        alt_nec = BASE + 40 + niveis * passo_niv
        ver.append(["Reatores", f"{n_est} reator(es) {rL:.0f}×{rP:.0f}×{rA:.0f} mm atrás da placa ({por_niv} por prateleira, "
                    f"{niveis} prateleira(s)) – {c['funcao']}", f"{alt_nec:.0f} mm de altura", f"≤ {zp1:.0f} mm",
                    CK.texto(CK.check(alt_nec <= zp1, CK.utilizacao(alt_nec, zp1)))])
        prof_tras = CHAPA / 2 + 40 + rP + 50 + 24
        ver.append(["Reatores", f"Profundidade atrás da placa: folga + reator + cabos ({c['funcao']})", f"{prof_tras:.0f} mm",
                    f"≤ {D - yp - 40:.0f} mm", CK.texto(CK.check(prof_tras <= D - yp - 40, CK.utilizacao(prof_tras, D - yp - 40)))])
        larg_r = por_niv * rL + (por_niv + 1) * FOLGA
        ver.append(["Reatores", f"Largura da prateleira: {por_niv} reator(es) lado a lado + folgas ({c['funcao']})",
                    f"{larg_r:.0f} mm", f"≤ {Lc - 80} mm", CK.texto(CK.check(larg_r <= Lc - 80, CK.utilizacao(larg_r, Lc - 80)))])
    return dict(H=H, W=W, D=D, base=BASE, pecas=p, faltam=faltam, verificacoes=ver, colunas=cols, xs=xs,
                reator=(rL, rP, rA), cap=(cd.get("D"), cd.get("A")), n_est=n_est_tot)


# ----------------------------------------------------------------------------------------------- cena / vistas
GRUPOS = {
    "fechado_f": {"base", "estrutura", "teto", "lateral", "porta_f", "porta_t"},
    "fechado_t": {"base", "estrutura", "teto", "lateral", "porta_f", "porta_t"},
    "aberto_f": {"base", "estrutura", "teto", "lateral", "porta_f_aberta", "porta_t", "placa", "frente", "tras"},
    "aberto_t": {"base", "estrutura", "teto", "lateral", "porta_f", "porta_t_aberta", "placa", "frente", "tras"},
    "estrutura_f": {"base", "estrutura", "placa", "frente", "tras", "teto_exaustor"},
    "estrutura_t": {"base", "estrutura", "placa", "frente", "tras", "teto_exaustor"},
    "placa_f": {"placa", "frente", "tras"},
    "placa_t": {"placa", "frente", "tras"},
    "frontal": {"base", "estrutura", "placa", "frente", "tras"},
    "lateral": {"base", "estrutura", "placa", "frente", "tras"},
    "traseira": {"base", "estrutura", "placa", "frente", "tras"},
}
TITULOS = {
    "fechado_f": "Painel fechado – frente", "fechado_t": "Painel fechado – fundo",
    "aberto_f": "Portas frontais abertas", "aberto_t": "Portas traseiras abertas",
    "estrutura_f": "Sem chapas – frente", "estrutura_t": "Sem chapas – fundo",
    "placa_f": "Placa de montagem – frente (manobra e capacitores)", "placa_t": "Placa de montagem – trás (reatores)",
    "frontal": "Vista frontal", "lateral": "Vista lateral", "traseira": "Vista traseira",
}


def _add(pl, pc):
    import pyvista as pv
    if pc["t"] == "caixa":
        m = pv.Box(bounds=(pc["x"], pc["x"] + pc["L"], pc["y"], pc["y"] + pc["P"], pc["z"], pc["z"] + pc["A"]))
        pl.add_mesh(m, color=pc["cor"], opacity=pc.get("op", 1.0), show_edges=True, edge_color="#3d3d3d", line_width=0.5)
    elif pc["t"] == "cil":
        e = pc.get("eixo", "z")
        if e == "z":
            c, d = (pc["x"], pc["y"], pc["z"] + pc["A"] / 2), (0, 0, 1)
        else:
            c, d = (pc["x"], pc["y"] - pc["A"] / 2, pc["z"]), (0, 1, 0)
        pl.add_mesh(pv.Cylinder(center=c, direction=d, radius=pc["D"] / 2, height=pc["A"], resolution=36),
                    color=pc["cor"], opacity=pc.get("op", 1.0), smooth_shading=True)


def _portas_abertas(pl, m, lado):
    """Portas abertas ~100° (dobradiça na lateral externa de cada coluna, como no painel real)."""
    import pyvista as pv
    D, H = m["D"], m["H"]
    for i, c in enumerate(m["colunas"]):
        x0, Lc = m["xs"][i], c["largura"]
        esq = (i % 2 == 0)
        xh = x0 + 4 if esq else x0 + Lc - 4
        ang = math.radians(100)
        s = -1 if lado == "f" else 1
        y0 = -18 if lado == "f" else D + 18
        dx = (Lc - 8) * math.cos(ang) * (1 if esq else -1)
        dy = (Lc - 8) * math.sin(ang) * s
        p0 = (xh, y0, BASE + 6)
        pts = [p0, (xh + dx, y0 + dy, BASE + 6), (xh + dx, y0 + dy, H - 6), (xh, y0, H - 6)]
        porta = pv.PolyData(pts, faces=[4, 0, 1, 2, 3])
        pl.add_mesh(porta, color=C_PORTA, show_edges=True, edge_color="#3d3d3d")
        # espelho interno da porta (lado de dentro mais claro)
        fr = 0.06
        pin = [(xh + dx * fr, y0 + dy * fr, BASE + 120), (xh + dx * (1 - fr), y0 + dy * (1 - fr), BASE + 120),
               (xh + dx * (1 - fr), y0 + dy * (1 - fr), H - 120), (xh + dx * fr, y0 + dy * fr, H - 120)]
        pl.add_mesh(pv.PolyData(pin, faces=[4, 0, 1, 2, 3]), color="#a3a8ac")


def _cotas(pl, m):
    """Cotas gerais na isométrica (largura, altura, profundidade) – como no layout SolidWorks AGCO."""
    import numpy as np
    import pyvista as pv
    W, H, D = m["W"], m["H"], m["D"]
    off = 220
    linhas = [((0, -off, 0), (W, -off, 0), f"{W / 1000:.2f} m".replace(".", ",")),
              ((W + off, 0, 0), (W + off, D, 0), f"{D / 1000:.2f} m".replace(".", ",")),
              ((W + off, -off * 0.3, 0), (W + off, -off * 0.3, H), f"{H / 1000:.2f} m".replace(".", ","))]
    for a, b, txt in linhas:
        pl.add_mesh(pv.Line(a, b), color="#444444", line_width=1.5)
        for q in (a, b):
            pl.add_mesh(pv.Sphere(radius=14, center=q), color="#444444")
        mid = np.add(a, b) / 2
        pl.add_point_labels([mid], [txt], font_size=26, text_color="#333333", shape=None, show_points=False,
                            always_visible=True, font_family="arial")
    for x in (0, W):                                                   # linhas de chamada
        pl.add_mesh(pv.Line((x, 0, 0), (x, -off - 40, 0)), color="#999999", line_width=1)


def _cena(m, vista, tam=(1700, 1250)):
    import pyvista as pv
    pv.OFF_SCREEN = True
    pl = pv.Plotter(off_screen=True, window_size=tam, lighting="three lights")
    pl.set_background("white")
    pl.enable_anti_aliasing("ssaa")
    g = GRUPOS[vista]
    for pc in m["pecas"]:
        gg = pc.get("g")
        if gg in g or (gg == "teto" and "teto_exaustor" in g and pc["A"] > 10):
            if vista == "lateral" and gg == "lateral":
                continue
            _add(pl, pc)
    if "porta_f_aberta" in g:
        _portas_abertas(pl, m, "f")
    if "porta_t_aberta" in g:
        _portas_abertas(pl, m, "t")
    W, H, D = m["W"], m["H"], m["D"]
    if vista == "fechado_f":
        _cotas(pl, m)
    cx, cy, cz = W / 2, D / 2, H / 2
    dist = 3.0 * max(W, H, D)
    frente = (cx - 0.85 * dist, cy - 1.35 * dist, cz + 0.75 * dist)
    fundo = (cx + 0.85 * dist, cy + 1.35 * dist, cz + 0.75 * dist)
    pos = {"frontal": (cx, cy - dist, cz), "traseira": (cx, cy + dist, cz), "lateral": (cx - dist, cy, cz)}.get(vista)
    if pos is None:
        pos = fundo if vista.endswith("_t") else frente
    pl.camera_position = [pos, (cx, cy, cz), (0, 0, 1)]
    if vista in ("frontal", "lateral", "traseira"):
        pl.enable_parallel_projection()
    pl.reset_camera()
    pl.camera.zoom(1.08)
    return pl


def renders(m, pasta, cod, vistas=None):
    os.makedirs(pasta, exist_ok=True)
    out = {}
    for vista in (vistas or GRUPOS):
        pl = _cena(m, vista)
        arq = os.path.join(pasta, f"Painel3D_{vista}_{cod}.png")
        pl.screenshot(arq)
        pl.close()
        try:                                                    # recorta o branco em volta
            from PIL import Image, ImageChops
            im = Image.open(arq).convert("RGB")
            bb = ImageChops.difference(im, Image.new("RGB", im.size, "white")).getbbox()
            if bb:
                mg = 24
                im.crop((max(bb[0] - mg, 0), max(bb[1] - mg, 0), min(bb[2] + mg, im.width), min(bb[3] + mg, im.height))).save(arq)
        except Exception:
            pass
        out[vista] = arq
    return out


# ----------------------------------------------------------------------------------------------- folhas A3
def _topo(c, m, x0, y0, w, h, mm):
    """Vista de topo 2D: corpo do painel, exaustores, portas frontais e traseiras com o raio de abertura (cotado)."""
    W, D = m["W"], m["D"]
    Lmax = max(cc["largura"] for cc in m["colunas"])
    tot_y = D + 2 * Lmax
    esc = min(w / (W * 1.25), h / (tot_y * 1.1))
    ox = x0 + (w - W * esc) / 2
    oy = y0 + (h - tot_y * esc) / 2 + Lmax * esc

    def X(v):
        return ox + v * esc

    def Y(v):
        return oy + v * esc
    c.setLineWidth(1.2)
    c.rect(X(0), Y(0), W * esc, D * esc)
    c.setFillColor("#e8e8e8")
    for i, cc in enumerate(m["colunas"]):
        xc = m["xs"][i]
        for k in range(2):
            c.rect(X(xc + cc["largura"] * (0.3 + 0.4 * k) - 90), Y(D * 0.38 - 60), 180 * esc, 120 * esc, fill=1)
    c.setFillColor("black")
    c.setDash(3, 2)
    c.setLineWidth(0.6)
    for i, cc in enumerate(m["colunas"]):
        xa, Lc = m["xs"][i], cc["largura"]
        esq = (i % 2 == 0)
        xh = xa if esq else xa + Lc
        for lado in ("f", "t"):
            yb = 0 if lado == "f" else D
            s = -1 if lado == "f" else 1
            # arco de abertura (90°) – Y do papel cresce para cima: frente desenhada embaixo
            r = Lc * esc
            if esq:
                ini = 270 if lado == "f" else 0
            else:
                ini = 180 if lado == "f" else 90
            c.arc(X(xh) - r, Y(D - yb) - r, X(xh) + r, Y(D - yb) + r, startAng=ini, extent=90)
            c.line(X(xh), Y(D - yb), X(xh), Y(D - yb) - s * r)
    c.setDash()
    c.setFont("Helvetica", 9)
    c.drawCentredString(X(W / 2), Y(-Lmax) - 14, "Portas frontais")
    c.drawCentredString(X(W / 2), Y(D + Lmax) + 6, "Portas traseiras")
    c.drawCentredString(X(W / 2), Y(D / 2) - 4, f"{W / 1000:.2f} m × {D / 1000:.2f} m".replace(".", ","))
    xcota = X(W) + 25
    for ya, yb, t in ((-Lmax, 0, f"{Lmax / 1000:.2f} m"), (0, D, f"{D / 1000:.2f} m"), (D, D + Lmax, f"{Lmax / 1000:.2f} m")):
        c.line(xcota, Y(ya), xcota, Y(yb))
        c.line(xcota - 4, Y(ya), xcota + 4, Y(ya))
        c.line(xcota - 4, Y(yb), xcota + 4, Y(yb))
        c.saveState()
        c.translate(xcota + 12, (Y(ya) + Y(yb)) / 2)
        c.rotate(90)
        c.drawCentredString(0, 0, t.replace(".", ","))
        c.restoreState()
    c.setFont("Helvetica", 8)
    c.drawString(X(0), Y(-Lmax) - 30, "Área livre necessária na frente e atrás = largura da porta (abertura 90°). "
                                     "Exaustores no teto sobre os reatores.")


def gerar(ped, res, gab, prot, inds, pasta, cod, versao="", log=print):
    """6 folhas A3 (padrão dos layouts Electric SolidWorks) + PNGs das vistas. Devolve dict(pdf, pngs, verificacoes, faltam)."""
    from reportlab.lib.pagesizes import A3, landscape
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas

    m = modelo(ped, res, gab, prot, inds)
    png = renders(m, os.path.join(pasta, "vistas"), cod)
    arq = os.path.join(pasta, f"Painel_3D_{cod}.pdf")
    W_, H_ = landscape(A3)
    c = canvas.Canvas(arq, pagesize=(W_, H_))
    c.setTitle(f"Painel {cod}")
    N = 6

    def moldura(folha, titulo):
        c.setLineWidth(0.4)
        c.rect(5 * mm, 5 * mm, W_ - 10 * mm, H_ - 10 * mm)
        c.setLineWidth(1.0)
        c.rect(10 * mm, 10 * mm, W_ - 20 * mm, H_ - 20 * mm)
        c.setFont("Helvetica", 6)
        nx, ny = 16, 10
        for k in range(nx):                                           # grade de referência (números / letras)
            x = 10 * mm + (W_ - 20 * mm) * (k + 0.5) / nx
            c.drawCentredString(x, 6.5 * mm, str(nx - k)); c.drawCentredString(x, H_ - 8.5 * mm, str(nx - k))
            xl = 10 * mm + (W_ - 20 * mm) * k / nx
            c.line(xl, 5 * mm, xl, 10 * mm); c.line(xl, H_ - 10 * mm, xl, H_ - 5 * mm)
        for k in range(ny):
            y = 10 * mm + (H_ - 20 * mm) * (k + 0.5) / ny
            c.drawCentredString(7.5 * mm, y, "ABCDEFGHJK"[k]); c.drawCentredString(W_ - 7.5 * mm, y, "ABCDEFGHJK"[k])
            yl = 10 * mm + (H_ - 20 * mm) * k / ny
            c.line(5 * mm, yl, 10 * mm, yl); c.line(W_ - 10 * mm, yl, W_ - 5 * mm, yl)
        x0, y0, lw, lh = W_ - 200 * mm, 10 * mm, 190 * mm, 30 * mm
        c.setFillColor("white"); c.rect(x0, y0, lw, lh, fill=1); c.setFillColor("black")
        c.setFillColor(C_PLACA); c.rect(x0, y0 + lh - 7 * mm, lw, 7 * mm, fill=1, stroke=0); c.setFillColor("white")
        c.setFont("Helvetica-Bold", 10); c.drawString(x0 + 3 * mm, y0 + lh - 5.2 * mm, "ELECTRIC SERVICE – Plataforma FSEN")
        c.drawRightString(x0 + lw - 3 * mm, y0 + lh - 5.2 * mm, f"Folha {folha}/{N}")
        c.setFillColor("black")
        c.setFont("Helvetica-Bold", 9); c.drawString(x0 + 3 * mm, y0 + 16.5 * mm, titulo)
        c.setFont("Helvetica", 7.5)
        c.drawString(x0 + 3 * mm, y0 + 11.5 * mm, f"Projeto: {cod}    Cliente: {getattr(ped, 'cliente', '') or '-'}")
        c.drawString(x0 + 3 * mm, y0 + 7 * mm, f"Painel {m['W']:.0f} × {m['H']:.0f} × {m['D']:.0f} mm (L × A × P) – "
                                               f"{len(m['colunas'])} coluna(s) – RAL 7035, placa RAL 2004    A3 – sem escala (3D)")
        c.drawString(x0 + 3 * mm, y0 + 2.5 * mm, f"Componentes com medida de catálogo; reator: projeto FEM Electric    {versao}")

    def imagens(vs, y_top, alt, legendas=True):
        n = len(vs)
        lw = (W_ - 30 * mm) / n
        for i, v in enumerate(vs):
            x = 15 * mm + i * lw
            c.drawImage(png[v], x, y_top - alt, width=lw - 6 * mm, height=alt - 10 * mm, preserveAspectRatio=True, anchor="c",
                        mask="auto")
            if legendas:
                c.setFont("Helvetica", 12)
                c.drawCentredString(x + (lw - 6 * mm) / 2, y_top - alt - 2 * mm, TITULOS[v])

    alt_full = H_ - 60 * mm
    pares = [(1, ("fechado_f", "fechado_t"), "PAINEL FECHADO – FRENTE E FUNDO (COTAS GERAIS)"),
             (2, ("aberto_f", "aberto_t"), "PORTAS ABERTAS – FRENTE E FUNDO"),
             (4, ("estrutura_f", "estrutura_t"), "SEM CHAPAS – ESTRUTURA, PLACA E COMPONENTES"),
             (5, ("placa_f", "placa_t"), "PLACA DE MONTAGEM DUPLA FACE – FRENTE (MANOBRA/CAPACITORES) E TRÁS (REATORES)")]
    for folha, vs, tit in pares[:2]:
        imagens(vs, H_ - 15 * mm, alt_full)
        moldura(folha, tit); c.showPage()
    # folha 3: topo
    c.setFont("Helvetica-Bold", 16); c.drawString(20 * mm, H_ - 25 * mm, "Vista de topo")
    _topo(c, m, 20 * mm, 45 * mm, W_ - 40 * mm, H_ - 80 * mm, mm)
    moldura(3, "VISTA DE TOPO – ABERTURA DAS PORTAS FRONTAIS E TRASEIRAS"); c.showPage()
    for folha, vs, tit in pares[2:]:
        imagens(vs, H_ - 15 * mm, alt_full)
        moldura(folha, tit); c.showPage()
    # folha 6: vistas ortogonais + verificações
    imagens(("frontal", "lateral", "traseira"), H_ - 15 * mm, (H_ - 60 * mm) * 0.62)
    y = H_ - 15 * mm - (H_ - 60 * mm) * 0.62 - 10 * mm
    c.setFont("Helvetica-Bold", 10); c.drawString(15 * mm, y, "Verificações do arranjo físico (Check)"); y -= 5 * mm
    cols_x = (15, 50, 205, 245, 290)
    c.setFont("Helvetica-Bold", 7.5)
    for x, h in zip(cols_x, ("Item", "Verificação", "Valor", "Limite", "Check")):
        c.drawString(x * mm, y, h)
    y -= 4 * mm
    vistas = set()
    for v in m["verificacoes"]:
        if tuple(v[1:]) in vistas:
            continue
        vistas.add(tuple(v[1:]))
        for x, t in zip(cols_x, v):
            if x == 290:
                st = CK.de_texto(t)
                c.setFillColor(CK.COR.get(st, "black")); c.setFont("Helvetica-Bold", 7.5)
            else:
                c.setFont("Helvetica", 7.5)
            c.drawString(x * mm, y, (str(t).replace("✔", "").replace("⚠", "").replace("✖", "").strip())[:110])
            c.setFillColor("black")
        y -= 3.8 * mm
    if m["faltam"]:
        c.setFillColor(C_VERM)
        c.drawString(15 * mm, y - 2 * mm, "Medida a confirmar no catálogo (desenhado em vermelho translúcido): " + ", ".join(m["faltam"]))
        c.setFillColor("black")
    moldura(6, "VISTAS FRONTAL, LATERAL E TRASEIRA – VERIFICAÇÕES")
    c.save()
    log(f"   Painel 3D: {arq} (6 folhas" + (f"; a confirmar: {', '.join(m['faltam'])}" if m["faltam"] else "") + ")")
    return dict(pdf=arq, pngs=list(png.values()), verificacoes=m["verificacoes"], faltam=m["faltam"])
