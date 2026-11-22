"""Desenhos do gabinete do banco – formato das folhas Electric/TECHNIP 2016 (v1.17.0, em construção).

Folhas (A3, mesmo carimbo/moldura dos esquemas – PDF vetorial + DXF por camadas):
  1. LAYOUT – vista frontal com portas, vista lateral, vista superior (cotas gerais, itens de porta, exaustores)
  2. LAYOUT INTERNO – vista frontal sem portas (zonas, componentes em escala) e vista traseira (admissão de ar)
  3. VISTA ISOMÉTRICA – com portas e sem portas
Tudo vem de painel_gabinete.gabinete() + dimensionamento do banco – determinístico.
"""
from __future__ import annotations

import math

from . import banco as B
from .eplan.folha import ProjetoEletrico, X0, X1, Y0, Y1, CAR_H

ESCALAS = (10, 15, 20, 25, 30, 40, 50)
RODAPE = 100                  # soleira/base (mm) – incluída na altura total
H_EXAUST = 200                # faixa do exaustor no topo


def _escala(larg_total_mm, alt_total_mm, area_w, area_h):
    for e in ESCALAS:
        if larg_total_mm / e <= area_w and alt_total_mm / e <= area_h:
            return e
    return ESCALAS[-1]


class _Vista:
    """Converte mm reais → mm de papel com origem e escala."""

    def __init__(self, f, ox, oy, esc):
        self.f, self.ox, self.oy, self.e = f, ox, oy, esc

    def p(self, x, y):
        return self.ox + x / self.e, self.oy + y / self.e

    def ret(self, x, y, w, h, lw=0.35, cam="GABINETE", tracejado=False, preench=None):
        px, py = self.p(x, y)
        self.f.ret(px, py, w / self.e, h / self.e, lw=lw, cam=cam, tracejado=tracejado, preench=preench)

    def lin(self, x0, y0, x1, y1, lw=0.25, cam="GABINETE", tracejado=False):
        a, b = self.p(x0, y0)
        c, d = self.p(x1, y1)
        self.f.lin(a, b, c, d, lw=lw, cam=cam, tracejado=tracejado)

    def circ(self, x, y, r, lw=0.25, cam="GABINETE"):
        a, b = self.p(x, y)
        self.f.circ(a, b, r / self.e, lw=lw, cam=cam)

    def txt(self, x, y, t, fs=1.8, ha="center", va="center", rot=0, cam="TEXTOS", negrito=False):
        a, b = self.p(x, y)
        self.f.txt(a, b, t, fs=fs, ha=ha, va=va, rot=rot, cam=cam, negrito=negrito)

    def cota_h(self, x0, x1, y, txt=None, off=-8):
        """Cota horizontal (off em mm de papel, negativo = abaixo)."""
        a, b = self.p(x0, y)
        c, _ = self.p(x1, y)
        yy = b + off
        f = self.f
        f.lin(a, b, a, yy - 1.5 * (1 if off < 0 else -1), lw=0.13, cam="COTAS")
        f.lin(c, b, c, yy - 1.5 * (1 if off < 0 else -1), lw=0.13, cam="COTAS")
        f.lin(a, yy, c, yy, lw=0.18, cam="COTAS")
        for xx in (a, c):
            f.lin(xx - 0.9, yy - 0.9, xx + 0.9, yy + 0.9, lw=0.25, cam="COTAS")
        f.txt((a + c) / 2, yy + 0.6, txt or f"{x1 - x0:.0f}", fs=1.9, ha="center", va="bottom", cam="COTAS")

    def cota_v(self, y0, y1, x, txt=None, off=-8):
        a, b = self.p(x, y0)
        _, d = self.p(x, y1)
        xx = a + off
        f = self.f
        f.lin(a, b, xx - 1.5 * (1 if off < 0 else -1), b, lw=0.13, cam="COTAS")
        f.lin(a, d, xx - 1.5 * (1 if off < 0 else -1), d, lw=0.13, cam="COTAS")
        f.lin(xx, b, xx, d, lw=0.18, cam="COTAS")
        for yy in (b, d):
            f.lin(xx - 0.9, yy - 0.9, xx + 0.9, yy + 0.9, lw=0.25, cam="COTAS")
        f.txt(xx - 0.6, (b + d) / 2, txt or f"{y1 - y0:.0f}", fs=1.9, ha="center", va="bottom", rot=90, cam="COTAS")


def _xs(gab):
    xs, x = [], 0
    for c in gab["colunas"]:
        xs.append((x, c["largura"], c))
        x += c["largura"]
    return xs


def _grelha(v, x, y, w, h, n=6):
    for i in range(n):
        yy = y + h * (i + 0.5) / n
        v.lin(x, yy, x + w, yy, lw=0.13)


# ------------------------------------------------------------------------------ folha 1
def _frontal_portas(v, gab, ped, res):
    D = gab["dimensoes_mm"]
    H, L = D["altura"], D["largura"]
    v.ret(0, 0, L, RODAPE, lw=0.35, preench="0.85")
    for x, w, c in _xs(gab):
        v.ret(x, RODAPE, w, H - RODAPE, lw=0.5)
        v.ret(x + 15, RODAPE + 15, w - 30, H - RODAPE - 30, lw=0.25)          # porta
        v.ret(x + w - 45, RODAPE + (H - RODAPE) / 2 - 60, 15, 120, lw=0.25)   # fecho
        if "EXAUSTOR" in c["zonas"]:
            _grelha(v, x + w * 0.2, H - 170, w * 0.6, 110)
        if c["funcao"] in ("única", "operação/comando"):
            yc = H - 520
            v.ret(x + w / 2 - 72, yc, 144, 144, lw=0.35)                      # controlador 144×144
            v.txt(x + w / 2, yc + 72, "CFP", fs=1.6)
            n = len(res["estagios"])
            for i in range(n):                                                # sinaleiros Ø22
                cx = x + w / 2 + (i - (n - 1) / 2) * min(40, (w - 80) / max(n, 1))
                v.circ(cx, yc - 60, 11)
            v.circ(x + w / 2 - 50, yc - 130, 14)                              # chave
            v.circ(x + w / 2 + 50, yc - 130, 20)                              # emergência
            v.txt(x + w / 2, yc - 175, "D/L/A   EMERG.", fs=1.4)
    v.cota_h(0, L, 0, off=-7)
    if len(gab["colunas"]) > 1:
        for x, w, c in _xs(gab):
            v.cota_h(x, x + w, H, off=5)
    v.cota_v(0, H, 0, off=-7)
    v.txt(L / 2, -0, "", fs=1)


def _lateral(v, gab, com_admissao=True):
    D = gab["dimensoes_mm"]
    H, P = D["altura"], D["profundidade"]
    v.ret(0, 0, P, RODAPE, lw=0.35, preench="0.85")
    v.ret(0, RODAPE, P, H - RODAPE, lw=0.5)
    v.lin(P - 25, RODAPE, P - 25, H, lw=0.18, tracejado=True)                 # porta (frente à direita)
    v.cota_h(0, P, 0, off=-7)
    v.cota_v(0, H, P, off=7)


def _superior(v, gab):
    D = gab["dimensoes_mm"]
    L, P = D["largura"], D["profundidade"]
    v.ret(0, 0, L, P, lw=0.5)
    vent = gab["ventilacao"]
    quentes = [(x, w) for x, w, c in _xs(gab) if "EXAUSTOR" in c["zonas"] and c["funcao"] != "operação/comando"] or \
              [(x, w) for x, w, c in _xs(gab)]
    n = vent["n_exaustores"]
    for i in range(n):
        x, w = quentes[i % len(quentes)]
        k = i // len(quentes)
        r = min(w, P) * 0.22
        cx = x + w / 2
        cy = P * (0.35 + 0.3 * k) if n > len(quentes) else P * 0.45
        v.circ(cx, cy, r, lw=0.35)
        v.lin(cx - r, cy, cx + r, cy, lw=0.13)
        v.lin(cx, cy - r, cx, cy + r, lw=0.13)
    v.cota_h(0, L, 0, off=-7)
    v.cota_v(0, P, L, off=7)


# ------------------------------------------------------------------------------ folha 2
def _ind_dim(e):
    q = float(e["Q_kvar"])
    w = 220 if q <= 30 else 280 if q <= 60 else 340
    return w, int(w * 0.85)


def _frontal_interno(v, gab, ped, res):
    D = gab["dimensoes_mm"]
    H, L = D["altura"], D["largura"]
    est = res["estagios"]
    v.ret(0, 0, L, RODAPE, lw=0.35, preench="0.85")
    cols = _xs(gab)
    ind_cols = [c for c in cols if c[2]["funcao"].startswith("indutores")]
    cap_cols = [c for c in cols if c[2]["funcao"].startswith("capacitores")]
    for x, w, c in cols:
        v.ret(x, RODAPE, w, H - RODAPE, lw=0.5)
        v.ret(x + 30, RODAPE + 20, w - 60, H - RODAPE - 40, lw=0.13, tracejado=True)   # placa/estrutura
        if "EXAUSTOR" in c["zonas"]:
            v.ret(x + w * 0.25, H - H_EXAUST + 20, w * 0.5, H_EXAUST - 40, lw=0.25)
            v.txt(x + w / 2, H - H_EXAUST / 2, "EXAUSTOR", fs=1.4)
    if gab["colunas"][0]["funcao"] == "única":
        x, w, c = cols[0]
        y_cmd = H - H_EXAUST - 380
        v.ret(x + 50, y_cmd, w - 100, 360, lw=0.25)
        v.txt(x + w / 2, y_cmd + 180, "COMANDO / PROTEÇÃO / FUSÍVEIS / CONTATORAS", fs=1.3)
        y_cap = y_cmd - 650
        _capacitores(v, x + 40, y_cap, w - 80, 620, est)
        _indutores(v, x + 40, RODAPE + 40, w - 80, y_cap - RODAPE - 60, est)
        return
    x, w, c = cols[0]                                   # coluna de operação
    v.ret(x + 40, H - H_EXAUST - 520, w - 80, 480, lw=0.25)
    v.txt(x + w / 2, H - H_EXAUST - 280, "COMANDO", fs=1.4)
    v.ret(x + 40, RODAPE + 300, w - 80, 900, lw=0.25)
    v.txt(x + w / 2, RODAPE + 750, "PROTEÇÃO GERAL", fs=1.4, rot=90)
    for i in range(3):                                  # barramento horizontal (rede)
        v.lin(x + 20, H - H_EXAUST - 600 - i * 40, L - 20, H - H_EXAUST - 600 - i * 40, lw=0.6, cam="BARRAMENTO")
    per = [est[i::len(cap_cols)] for i in range(len(cap_cols))]
    for (x, w, c), lote in zip(cap_cols, per):
        y_top = H - H_EXAUST - 720
        for k, e in enumerate(lote):                    # fusíveis + contatora por estágio
            yy = y_top - k * 170
            for f in range(3):
                v.ret(x + 50 + f * 40, yy - 120, 30, 120, lw=0.25)
            v.ret(x + 190, yy - 120, 80, 120, lw=0.25)
            v.txt(x + w - 40, yy - 60, e["codigo"].split("-")[-1] + " kvar", fs=1.2, ha="right")
        y_cap_top = y_top - len(lote) * 170 - 40
        _capacitores(v, x + 40, RODAPE + 40, w - 80, y_cap_top - RODAPE - 40, lote)
    per = [est[i::len(ind_cols)] for i in range(len(ind_cols))]
    for (x, w, c), lote in zip(ind_cols, per):
        _indutores(v, x + 40, RODAPE + 40, w - 80, H - H_EXAUST - RODAPE - 80, lote)


def _capacitores(v, x, y, w, h, est):
    latas = sum(int((e.get("cap") or [3])[0]) for e in est)
    d = 76.0
    por_lin = max(1, int(w // (d + 12)))
    lin = math.ceil(latas / por_lin)
    hh = min(230, h / max(lin, 1) - 20)
    if hh < 60:                                          # não cabe em escala: desenha o que cabe e anota
        lin = max(1, int(h // 80))
        hh = 60
        latas_d = lin * por_lin
    else:
        latas_d = latas
    k = 0
    for i in range(lin):
        for j in range(min(por_lin, latas_d - k)):
            v.ret(x + j * (d + 12), y + h - (i + 1) * (hh + 20), d, hh, lw=0.25)
            k += 1
    v.txt(x + w / 2, y + h + 15, f"CAPACITORES ({latas} un.)" + ("" if latas_d >= latas else " – ver lista"), fs=1.2)


def _indutores(v, x, y, w, h, est):
    yy = y
    for e in est:
        iw, ih = _ind_dim(e)
        iw = min(iw, w - 20)
        if yy + ih > y + h:
            break
        v.ret(x + (w - iw) / 2, yy, iw, ih, lw=0.35)
        for k in range(3):
            v.ret(x + (w - iw) / 2 + iw * (0.12 + 0.3 * k), yy + ih * 0.1, iw * 0.18, ih * 0.8, lw=0.13)
        v.txt(x + w / 2, yy + ih + 12, f"L {e['L_uH']/1000:.3f} mH", fs=1.1)
        v.lin(x, yy - 10, x + w, yy - 10, lw=0.25)    # prateleira
        yy += ih + 70


def _traseira(v, gab):
    D = gab["dimensoes_mm"]
    H, L = D["altura"], D["largura"]
    v.ret(0, 0, L, RODAPE, lw=0.35, preench="0.85")
    v.ret(0, RODAPE, L, H - RODAPE, lw=0.5)
    for x, w, c in _xs(gab):
        v.lin(x, RODAPE, x, H, lw=0.25)
        if c["funcao"] == "única" or c["funcao"].startswith("indutores"):
            _grelha(v, x + w * 0.15, RODAPE + 80, w * 0.7, 300, n=8)
            v.txt(x + w / 2, RODAPE + 420, "ADMISSÃO DE AR", fs=1.3)
    v.cota_h(0, L, 0, off=-7)


# ------------------------------------------------------------------------------ folha 3
def _iso(f, ox, oy, gab, esc, com_portas=True):
    D = gab["dimensoes_mm"]
    H, L, P = D["altura"], D["largura"], D["profundidade"]
    ang = math.radians(30)
    def q(x, y, z):                                     # x largura, y profundidade, z altura
        return (ox + (x - y * math.cos(ang)) / esc * 0.95, oy + (z + y * math.sin(ang) * 0.6) / esc)
    def L_(a, b, lw=0.35, tracejado=False):
        f.lin(*q(*a), *q(*b), lw=lw, cam="GABINETE", tracejado=tracejado)
    pts = [(0, 0, 0), (L, 0, 0), (L, 0, H), (0, 0, H)]
    for a, b in zip(pts, pts[1:] + pts[:1]):
        L_(a, b, 0.5)
    for a in [(0, 0, H), (L, 0, H), (0, 0, 0)]:
        L_(a, (a[0], P, a[2]), 0.5)
    L_((0, P, 0), (0, P, H), 0.5)
    L_((0, P, H), (L, P, H), 0.5)
    L_((0, 0, RODAPE), (L, 0, RODAPE), 0.25)
    for x, w, c in _xs(gab):
        L_((x, 0, RODAPE), (x, 0, H), 0.35)
        if com_portas:
            for a, b in [((x + 15, 0, RODAPE + 15), (x + w - 15, 0, RODAPE + 15)), ((x + w - 15, 0, RODAPE + 15), (x + w - 15, 0, H - 15)),
                         ((x + w - 15, 0, H - 15), (x + 15, 0, H - 15)), ((x + 15, 0, H - 15), (x + 15, 0, RODAPE + 15))]:
                L_(a, b, 0.18)
        else:
            zs = c["zonas"]
            hz = (H - RODAPE) / len(zs)
            for k, z in enumerate(zs):
                z0 = H - (k + 1) * hz
                L_((x + 30, 0, z0 + 15), (x + w - 30, 0, z0 + 15), 0.18)
                f.txt(*q(x + w / 2, 0, z0 + hz / 2), z.split(" (")[0].title(), fs=1.3, ha="center", va="center", cam="TEXTOS")
    for x, w, c in _xs(gab):                            # exaustores no teto
        if "EXAUSTOR" in c["zonas"] and c["funcao"] != "operação/comando":
            cx, cy = q(x + w / 2, P / 2, H)
            f.circ(cx, cy, min(w, P) * 0.18 / esc, lw=0.25, cam="GABINETE")


# ------------------------------------------------------------------------------ montagem
def construir(ped, res, gab, cod, versao):
    D = gab["dimensoes_mm"]
    H, L, P = D["altura"], D["largura"], D["profundidade"]
    tipo = "DESSINTONIZADO" if ped.tipo == "dessintonizado" else "SINTONIZADO"
    titulo_eq = f"BANCO DE CAPACITOR {tipo} {ped.tensao_v:.0f} V – {res['Q_total_kvar']:.0f} kVAr – {ped.freq_hz:.0f} Hz"
    curto = f"Banco {tipo.lower()} {ped.tensao_v:.0f} V {res['Q_total_kvar']:.0f} kVAr"
    pr = ProjetoEletrico(ped.cliente, (ped.projeto or curto)[:40], cod, "", versao,
                         norma="NBR IEC 61439-1/2 · IEC 60890 · NBR 5410")
    area_y0 = Y0 + CAR_H + 22
    area_h = Y1 - area_y0 - 14
    # folha 1: frontal | lateral | superior
    f = pr.nova("LAYOUT EXTERNO", "=PAINEL", "+GAB")
    esc = _escala(L + P + 900, H + P + 700, X1 - X0 - 150, area_h)
    v = _Vista(f, X0 + 22, area_y0 + P / esc + 30, esc)
    _frontal_portas(v, gab, ped, res)
    _titulo(f, v, L / 2, "VISTA FRONTAL")
    vl = _Vista(f, X0 + 22 + (L + 350) / esc, area_y0 + P / esc + 30, esc)
    _lateral(vl, gab)
    _titulo(f, vl, P / 2, "VISTA LATERAL")
    vs = _Vista(f, X0 + 22, area_y0 + 8, esc)
    _superior(vs, gab)
    _titulo(f, vs, L / 2, "VISTA SUPERIOR")
    _tabela_itens(f, gab, ped, res, titulo_eq, esc)
    # folha 2: interno + traseira
    f2 = pr.nova("LAYOUT INTERNO", "=PAINEL", "+GAB")
    esc2 = _escala(2 * L + 500, H + 400, X1 - X0 - 30, area_h)
    v2 = _Vista(f2, X0 + 20, area_y0 + 14, esc2)
    _frontal_interno(v2, gab, ped, res)
    _titulo(f2, v2, L / 2, "VISTA FRONTAL S/ PORTAS")
    v3 = _Vista(f2, X0 + 20 + (L + 400) / esc2, area_y0 + 14, esc2)
    _traseira(v3, gab)
    _titulo(f2, v3, L / 2, "VISTA TRASEIRA")
    f2.txt(X1 - 4, area_y0 - 14, f"ESCALA 1:{esc2}", fs=2.0, ha="right")
    # folha 3: isométricas
    f3 = pr.nova("ISOMÉTRICAS", "=PAINEL", "+GAB")
    esc3 = _escala(2 * (L + P) + 600, H + P, X1 - X0 - 30, area_h)
    _iso(f3, X0 + 20 + P * 0.9 / esc3, area_y0 + 8, gab, esc3, True)
    f3.txt(X0 + 20 + (L / 2 + P * 0.3) / esc3, area_y0 - 6, "VISTA ISOMÉTRICA", fs=2.2, ha="center", negrito=True)
    ox2 = X0 + 20 + (L + P * 1.9 + 400) / esc3
    _iso(f3, ox2, area_y0 + 8, gab, esc3, False)
    f3.txt(ox2 + (L / 2 - P * 0.6) / esc3, area_y0 - 6, "VISTA ISOMÉTRICA S/ PORTAS", fs=2.2, ha="center", negrito=True)
    return pr


def _titulo(f, v, x, t):
    a, b = v.p(x, 0)
    f.txt(a, b - 14, t, fs=2.4, ha="center", va="top", negrito=True)


def _tabela_itens(f, gab, ped, res, titulo_eq, esc):
    v = gab["ventilacao"]
    p = gab["perdas_w"]
    D = gab["dimensoes_mm"]
    linhas = [titulo_eq,
              f"Gabinete {D['altura']} (A) × {D['largura']} (L) × {D['profundidade']} (P) mm – {len(gab['colunas'])} coluna(s)",
              "Colunas: " + " | ".join(f"{c['funcao']} {c['largura']}" for c in gab["colunas"]),
              f"Perdas internas: {p['total']} W (reatores {p['reatores']} W, capacitores {p['capacitores']} W)",
              f"Ventilação: {v['n_exaustores']} × {v['exaustor_m3h']} m³/h (instalado {v['vazao_instalada_m3h']} m³/h c/ filtro)",
              f"Ar interno estimado: {v['t_interna_c']} °C com ambiente {ped.amb_c:.0f} °C (IEC 60890)",
              f"Escala 1:{esc} · cotas em mm · base/soleira {RODAPE} mm incluída na altura"]
    x, y = X1 - 135, Y1 - 10
    f.ret(x - 2, y - 4.2 * len(linhas) - 3, 133, 4.2 * len(linhas) + 5, lw=0.25, cam="TEXTOS")
    for i, t in enumerate(linhas):
        f.txt(x, y - 4.2 * (i + 1), t, fs=1.9 if i else 2.1, ha="left", va="bottom", negrito=(i == 0))


def gerar(ped, res, pasta, cod, versao, log=print):
    import os
    from .painel_gabinete import gabinete
    gab = gabinete(ped, res)
    pr = construir(ped, res, gab, cod, versao)
    os.makedirs(pasta, exist_ok=True)
    pdf = os.path.join(pasta, f"Layout_Painel_{cod}.pdf")
    dxf = os.path.join(pasta, f"Layout_Painel_{cod}.dxf")
    pr.pdf(pdf)
    pr.dxf(dxf)
    log(f"Painel: gabinete {gab['dimensoes_mm']} – {len(gab['colunas'])} coluna(s), {gab['ventilacao']['n_exaustores']} exaustor(es), "
        f"ar interno {gab['ventilacao']['t_interna_c']} °C")
    for a in gab["avisos"]:
        log("AVISO painel: " + a)
    return dict(pdf=pdf, dxf=dxf, gabinete=gab)
