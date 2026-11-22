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


# ------------------------------------------------------------------------------ folha 1 – externo
def _seta(f, x0, y0, x1, y1):
    f.lin(x0, y0, x1, y1, lw=0.25, cam="AR")
    a = math.atan2(y1 - y0, x1 - x0)
    for d in (2.6, -2.6):
        f.lin(x1, y1, x1 - 2.2 * math.cos(a + d * 0.2), y1 - 2.2 * math.sin(a + d * 0.2), lw=0.25, cam="AR")


def _frontal_portas(v, gab, ped, res):
    D = gab["dimensoes_mm"]
    H, L = D["altura"], D["largura"]
    v.ret(0, 0, L, RODAPE, lw=0.35, preench="0.85")
    for i, (x, w, c) in enumerate(_xs(gab)):
        v.ret(x, RODAPE, w, H - RODAPE, lw=0.5)
        v.ret(x + 15, RODAPE + 15, w - 30, H - RODAPE - 30, lw=0.25)              # porta
        v.ret(x + w - 50, RODAPE + (H - RODAPE) / 2 - 60, 15, 120, lw=0.25)       # fecho
        _grelha(v, x + w * 0.2, RODAPE + 60, w * 0.6, 220, n=8)                    # entrada de ar (embaixo)
        v.txt(x + w / 2, RODAPE + 310, "ENTRADA DE AR", fs=1.2)
        if i == 0:
            yc = H - 480
            v.ret(x + w / 2 - 72, yc, 144, 144, lw=0.35)                          # controlador 144×144
            v.txt(x + w / 2, yc + 72, "CFP", fs=1.6)
            n = len(res["estagios"])
            passo = min(45, (w - 120) / max(n, 1))
            for k in range(n):                                                    # sinaleiros Ø22
                v.circ(x + w / 2 + (k - (n - 1) / 2) * passo, yc - 60, 11)
            v.circ(x + w / 2 - 60, yc - 140, 14)                                  # seletora
            v.circ(x + w / 2 + 60, yc - 140, 20)                                  # emergência
            v.txt(x + w / 2 - 60, yc - 185, "D/A", fs=1.3)
            v.txt(x + w / 2 + 60, yc - 185, "EMERG.", fs=1.3)
            v.ret(x + w / 2 - 100, yc + 200, 200, 60, lw=0.25)                    # plaqueta TAG
            v.txt(x + w / 2, yc + 230, "TAG DO PAINEL", fs=1.2)
    v.cota_h(0, L, 0, off=-7)
    if len(gab["colunas"]) > 1:
        for x, w, c in _xs(gab):
            v.cota_h(x, x + w, H, off=5)
    v.cota_v(0, H, 0, off=-7)


def _lateral(v, gab):
    D = gab["dimensoes_mm"]
    H, P = D["altura"], D["profundidade"]
    v.ret(0, 0, P, RODAPE, lw=0.35, preench="0.85")
    v.ret(0, RODAPE, P, H - RODAPE, lw=0.5)
    v.cota_h(0, P, 0, off=-7)
    v.cota_v(0, H, P, off=7)
    v.txt(P * 0.25, H + 60, "TRÁS", fs=1.4)
    v.txt(P * 0.75, H + 60, "FRENTE", fs=1.4)


def _superior(v, gab):
    D = gab["dimensoes_mm"]
    L, P = D["largura"], D["profundidade"]
    v.ret(0, 0, L, P, lw=0.5)
    v.lin(0, P / 2, L, P / 2, lw=0.13, tracejado=True)                            # chapa divisória (projeção)
    cols = _xs(gab)
    n = gab["ventilacao"]["n_exaustores"]
    por = math.ceil(n / len(cols))
    k = 0
    for x, w, c in cols:
        for j in range(por):
            if k >= n:
                break
            r = min(w / por, P / 2) * 0.32
            cx = x + w * (j + 0.5) / por
            cy = P * 0.28                                                         # sobre o compartimento traseiro
            v.circ(cx, cy, r, lw=0.35)
            v.lin(cx - r, cy, cx + r, cy, lw=0.13)
            v.lin(cx, cy - r, cx, cy + r, lw=0.13)
            k += 1
    v.txt(L + 60, P * 0.25, "TRÁS (reatores)", fs=1.3, ha="left")
    v.txt(L + 60, P * 0.75, "FRENTE (capacitores)", fs=1.3, ha="left")
    v.cota_h(0, L, 0, off=-7)
    v.cota_v(0, P, 0, off=-7)


# ------------------------------------------------------------------------------ folha 2 – frente e trás sem portas
def _ind_dim(e):
    q = float(e["Q_kvar"])
    w = 240 if q <= 30 else 300 if q <= 60 else 360
    return w, int(w * 0.8)


def _frontal_interno(v, gab, ped, res):
    """Frente sem porta no padrão do layout Electric Panatlântica 2024 (Painel 400 kVAr): UMA placa de montagem por todas as
    colunas; no topo comando (controlador/trafo/relés em trilho DIN); abaixo os estágios em FAIXAS VERTICAIS lado a lado –
    chave seccionadora-fusível NH, contatora e capacitores embaixo (atrás da chapa divisória ficam os reatores)."""
    D = gab["dimensoes_mm"]
    H, L = D["altura"], D["largura"]
    est = res["estagios"]
    n = len(est)
    v.ret(0, 0, L, RODAPE, lw=0.35, preench="0.85")
    v.ret(0, RODAPE, L, H - RODAPE, lw=0.5)
    for x, w, c in _xs(gab)[1:]:
        v.lin(x, RODAPE, x, H, lw=0.25)
    xp, yp, wp, hp = 38, RODAPE + 120, L - 76, H - RODAPE - 260         # placa de montagem (Panatlântica: 1523 × 1702)
    v.ret(xp, yp, wp, hp, lw=0.3)
    v.cota_h(xp, xp + wp, RODAPE, off=-7)
    y = yp + hp
    v.ret(xp + wp / 2 - 110, y - 120, 220, 80, lw=0.3)                  # trafo de comando
    v.txt(xp + wp / 2, y - 80, "-T1", fs=1.3)
    v.lin(xp + wp * 0.65, y - 190, xp + wp - 40, y - 190, lw=0.6)       # trilho DIN de comando
    for k in range(6):
        v.ret(xp + wp * 0.65 + 15 + k * 40, y - 225, 25, 70, lw=0.2)
    v.txt(xp + wp * 0.82, y - 250, "-F01/-F02/-B0/-BT2/-KF", fs=1.1)
    v.ret(xp + wp / 2 - 110, y - 330, 220, 80, lw=0.3)                  # canaleta/relé falta de fase
    v.txt(xp + wp / 2, y - 290, "-K0  /  -Q0", fs=1.3)
    passo = wp / max(n, 1)
    y_fus, y_ctt, y_cap = y - 560, y - 830, yp + 40
    for k, e in enumerate(est):
        cx = xp + passo * (k + 0.5)
        v.circ(cx, y - 430, 18)                                         # passagem de cabos (furo)
        wf = min(110, passo * 0.8)
        v.ret(cx - wf / 2, y_fus, wf, 170, lw=0.3)                     # chave NH tripolar
        v.txt(cx, y_fus - 18, f"-FF{k + 1}", fs=1.1)
        wc = min(70, passo * 0.55)
        v.ret(cx - wc / 2, y_ctt, wc, 120, lw=0.3)                     # contatora
        v.txt(cx, y_ctt - 18, f"-K{k + 1}", fs=1.1)
        v.circ(cx, y_ctt - 80, 15)
        latas = int((e.get("cap") or [3])[0])
        dl = min(76, passo / max(latas, 1) - 6)
        for j_ in range(latas):
            xl = cx - latas * (dl + 6) / 2 + j_ * (dl + 6) + 3
            v.ret(xl, y_cap, dl, 230, lw=0.25)                          # capacitores embaixo
        v.txt(cx, y_cap + 250, f"-C{k + 1}", fs=1.1)
    v.txt(L / 2, H - 40, "COMANDO", fs=1.3)


def _ind_dim(e):
    q = float(e["Q_kvar"])
    w = 240 if q <= 30 else 300 if q <= 60 else 360
    return w, int(w * 0.9)


def _traseira_interna(v, gab, res):
    """Traseira sem porta (Panatlântica 2024): reatores em grade 2 × 2 por coluna, em duas prateleiras na metade inferior;
    exaustores no topo de cada coluna; venezianas de entrada embaixo."""
    D = gab["dimensoes_mm"]
    H, L = D["altura"], D["largura"]
    est = res["estagios"]
    v.ret(0, 0, L, RODAPE, lw=0.35, preench="0.85")
    cols = list(reversed(_xs(gab)))                                     # vista por trás: espelhada
    for (x, w, c) in cols:
        xm = L - x - w
        v.ret(xm, RODAPE, w, H - RODAPE, lw=0.5)
        for kx in (0.3, 0.7):                                           # exaustores no topo
            v.ret(xm + w * kx - 55, H - 160, 110, 90, lw=0.3)
        lote = c["estagios"]
        por_lin = 2
        lin = max(1, math.ceil(len(lote) / por_lin))
        y0 = RODAPE + 60
        hh = min(380, (H * 0.55) / lin)
        for li in range(lin):
            ys = y0 + li * (hh + 40)
            v.lin(xm + 20, ys - 10, xm + w - 20, ys - 10, lw=0.35)     # prateleira
            for ci in range(por_lin):
                idx = li * por_lin + ci
                if idx >= len(lote):
                    break
                k = lote[idx]
                iw, ih = _ind_dim(est[k])
                iw = min(iw, w / 2 - 40)
                ih = min(ih, hh - 20)
                cx = xm + w * (0.27 + 0.46 * ci)
                v.ret(cx - iw / 2, ys, iw, ih, lw=0.35)
                for b_ in range(3):
                    v.ret(cx - iw / 2 + iw * (0.1 + 0.3 * b_), ys + ih * 0.1, iw * 0.2, ih * 0.8, lw=0.13)
                v.txt(cx, ys + ih + 18, f"-L{k + 1}  {est[k]['L_uH'] / 1000:.3f} mH", fs=1.0)
        _grelha(v, xm + w * 0.2, RODAPE + 10, w * 0.6, 40, n=3)
    v.cota_h(0, L, 0, off=-7)


# ------------------------------------------------------------------------------ folha 3 – corte e isométricas
def _corte(v, gab, res):
    D = gab["dimensoes_mm"]
    H, P = D["altura"], D["profundidade"]
    from .painel_gabinete import PROF_TRAS
    f = v.f
    v.ret(0, 0, P, RODAPE, lw=0.35, preench="0.85")
    v.ret(0, RODAPE, P, H - RODAPE, lw=0.5)
    xd = PROF_TRAS + 20
    v.lin(xd, RODAPE + 250, xd, H - 220, lw=0.6)                                  # chapa divisória
    v.txt(xd + 15, H / 2, "CHAPA DIVISÓRIA", fs=1.2, rot=90, ha="center")
    v.ret(PROF_TRAS * 0.15, H - 160, PROF_TRAS * 0.7, 120, lw=0.3)                # exaustor no teto, atrás
    lin = max(1, math.ceil(len(gab["colunas"][0]["estagios"]) / 2))
    hh = min(380, (H * 0.55) / lin)
    for li in range(lin):                                                          # reatores (trás, 2 prateleiras embaixo)
        ys = RODAPE + 60 + li * (hh + 40)
        v.ret(60, ys, PROF_TRAS - 120, hh - 20, lw=0.35)
        v.lin(30, ys - 10, xd - 10, ys - 10, lw=0.35)
    xp = xd + 40                                                                   # placa de montagem (frente)
    v.lin(xp, RODAPE + 120, xp, H - 140, lw=0.5)
    for (y0, h0, w0, t) in ((H - 760, 170, 150, "-FF"), (H - 1030, 120, 130, "-K"), (RODAPE + 160, 230, 90, "-C")):
        v.ret(xp, y0, w0, h0, lw=0.3)
        v.txt(xp + w0 + 30, y0 + h0 / 2, t, fs=1.2, ha="left")
    v.ret(xp, H - 330, 160, 90, lw=0.3)
    v.txt(xp + 190, H - 285, "COMANDO", fs=1.1, ha="left")
    a, b = v.p(P - 30, RODAPE + 120)
    c, d = v.p(30, RODAPE + 120)
    _seta(f, a + 6, b, a - 3, b)
    _seta(f, c - 6, d, c + 3, d)
    a, b = v.p(xd / 2, RODAPE + 200)
    _seta(f, a, b, a, b + (H - 600) / v.e)
    a, b = v.p(xd + 150, RODAPE + 200)
    _seta(f, a, b, a, b + (H - 900) / v.e)
    a, b = v.p(PROF_TRAS / 2, H)
    _seta(f, a, b, a, b + 8)
    v.txt(P * 0.25, -150, "TRÁS (reatores)", fs=1.3)
    v.txt(P * 0.75, -150, "FRENTE (capacitores)", fs=1.3)
    v.cota_h(0, xd, H, off=5, txt=f"{xd:.0f}")
    v.cota_h(xd, P, H, off=5, txt=f"{P - xd:.0f}")


def _iso(f, ox, oy, gab, esc, com_portas=True):
    D = gab["dimensoes_mm"]
    H, L, P = D["altura"], D["largura"], D["profundidade"]
    ang = math.radians(30)
    def q(x, y, z):
        return (ox + (x + y * math.cos(ang) * 0.6) / esc, oy + (z + y * math.sin(ang) * 0.6) / esc)
    def L_(a, b, lw=0.35, tracejado=False):
        f.lin(*q(*a), *q(*b), lw=lw, cam="GABINETE", tracejado=tracejado)
    for a, b in [((0, 0, 0), (L, 0, 0)), ((L, 0, 0), (L, 0, H)), ((L, 0, H), (0, 0, H)), ((0, 0, H), (0, 0, 0)),
                 ((0, 0, H), (0, P, H)), ((L, 0, H), (L, P, H)), ((L, 0, 0), (L, P, 0)), ((0, P, H), (L, P, H)),
                 ((L, P, H), (L, P, 0)), ((0, 0, RODAPE), (L, 0, RODAPE))]:
        L_(a, b, 0.5)
    for x, w, c in _xs(gab):
        L_((x, 0, RODAPE), (x, 0, H), 0.35)
        L_((x, 0, H), (x, P, H), 0.18)
        cx, cy = q(x + w / 2, P * 0.72, H)                                         # exaustor sobre os reatores
        f.circ(cx, cy, w * 0.13 / esc, lw=0.25, cam="GABINETE")
        if com_portas:
            for a, b in [((x + 15, 0, RODAPE + 15), (x + w - 15, 0, RODAPE + 15)), ((x + w - 15, 0, RODAPE + 15), (x + w - 15, 0, H - 15)),
                         ((x + w - 15, 0, H - 15), (x + 15, 0, H - 15)), ((x + 15, 0, H - 15), (x + 15, 0, RODAPE + 15))]:
                L_(a, b, 0.18)
            for k in range(6):
                zz = RODAPE + 70 + k * 35
                L_((x + w * 0.2, 0, zz), (x + w * 0.8, 0, zz), 0.13)
        else:
            for (z0, t) in ((H - 650, "Fusíveis"), (H - 930, "Contatoras"), (RODAPE + 400, "Capacitores")):
                L_((x + 30, 0, z0), (x + w - 30, 0, z0), 0.18)
                f.txt(*q(x + w / 2, 0, z0 + 60), t, fs=1.2, ha="center", va="center", cam="TEXTOS")
            for k in range(len(c["estagios"]) + 1):
                xx = x + 30 + (w - 60) * k / max(len(c["estagios"]), 1)
                L_((xx, 0, RODAPE + 150), (xx, 0, H - 600), 0.1)
            L_((x, P / 2, RODAPE), (x, P / 2, H), 0.18, tracejado=True)


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
    f2 = pr.nova("LAYOUT INTERNO", "=PAINEL", "+GAB")
    esc2 = _escala(2 * L + 500, H + 400, X1 - X0 - 30, area_h)
    v2 = _Vista(f2, X0 + 20, area_y0 + 14, esc2)
    _frontal_interno(v2, gab, ped, res)
    _titulo(f2, v2, L / 2, "VISTA FRONTAL S/ PORTA (CAPACITORES)")
    v3 = _Vista(f2, X0 + 20 + (L + 400) / esc2, area_y0 + 14, esc2)
    _traseira_interna(v3, gab, res)
    _titulo(f2, v3, L / 2, "VISTA TRASEIRA S/ PORTA (REATORES)")
    f2.txt(X1 - 4, area_y0 - 14, f"ESCALA 1:{esc2}", fs=2.0, ha="right")
    f3 = pr.nova("CORTE E ISOMÉTRICAS", "=PAINEL", "+GAB")
    esc3 = _escala(P + 2 * (L + P * 0.6) + 900, H + P, X1 - X0 - 30, area_h)
    vc = _Vista(f3, X0 + 22, area_y0 + 8, esc3)
    _corte(vc, gab, res)
    _titulo(f3, vc, P / 2, "CORTE LATERAL – FLUXO DE AR")
    ox = X0 + 22 + (P + 400) / esc3
    _iso(f3, ox, area_y0 + 8, gab, esc3, True)
    f3.txt(ox + L / 2 / esc3, area_y0 - 6, "ISOMÉTRICA", fs=2.2, ha="center", negrito=True)
    ox2 = ox + (L + P * 0.6 + 350) / esc3
    _iso(f3, ox2, area_y0 + 8, gab, esc3, False)
    f3.txt(ox2 + L / 2 / esc3, area_y0 - 6, "ISOMÉTRICA S/ PORTAS", fs=2.2, ha="center", negrito=True)
    _folhas_listas(pr, ped, res, gab)
    return pr


# ------------------------------------------------------------------------------ listas (modelo FEMSA/Novemp)
TIPOS_PLAQUETA = {   # tipo: (linhas máx., altura letra mm, caracteres/linha, A mm, B mm) – acrílico 3 mm, fundo preto, letras brancas
    "A": (3, 10, 23, 150, 45), "B": (3, 7, 20, 80, 30), "C": (3, 3, 22, 60, 20), "E": (2, 3, 14, 35, 15)}


def plaquetas(ped, res, gab):
    """Lista de plaquetas do gabinete no modelo FEMSA (item, tipo, quantidade, inscrição)."""
    est = res["estagios"]
    tipo = "DESSINTONIZADO" if ped.tipo == "dessintonizado" else "SINTONIZADO"
    out = [("PAINEL", "A", 1, f"BANCO DE CAPACITORES {tipo} | {res['Q_total_kvar']:.0f} kVAr | 3F-{ped.tensao_v:.0f}V+PE-{ped.freq_hz:.0f}Hz"),
           ("PERIGO", "B", len(gab["colunas"]) * 2, "PERIGO | ALTA TENSÃO | AGUARDAR 5 min DESCARGA"),
           ("-U1", "C", 1, "CONTROLADOR | FATOR DE POTÊNCIA"),
           ("-S1", "E", 1, "DESL. | AUTOM."),
           ("-S0", "E", 1, "EMERGÊNCIA"),
           ("-Q0", "C", 1, "PROTEÇÃO | GERAL"),
           ("-B0", "E", 1, "TERMOST. | 35 °C"),
           ("-BT2", "E", 1, "TERMOST. | 55 °C"),
           ("-T1", "C", 1, f"TRAFO COMANDO | {ped.tensao_v:.0f}/220 V")]
    for k, e in enumerate(est, 1):
        q = e["codigo"].split("-")[-1]
        out += [(f"-H{k}", "E", 1, f"ESTÁGIO {k} | {q} kvar"),
                (f"-FF{k}", "C", 1, f"FUSÍVEIS | ESTÁGIO {k}"),
                (f"-K{k}", "C", 1, f"CONTATORA | ESTÁGIO {k}"),
                (f"-C{k}", "C", 1, f"CAPACITORES | ESTÁGIO {k} | {q} kvar"),
                (f"-L{k}", "C", 1, f"REATOR {k} | {e['L_uH'] / 1000:.3f} mH")]
    for i in range(gab["ventilacao"]["n_exaustores"]):
        out.append((f"-M{i + 1}", "E", 1, f"EXAUSTOR {i + 1}"))
    return out


def material_gabinete(ped, res, gab):
    D = gab["dimensoes_mm"]
    v = gab["ventilacao"]
    n_col, n = len(gab["colunas"]), len(res["estagios"])
    return [
        ("Gabinete autoportante modular, chapa 2,0 mm, pintura RAL 7035, IP 42 (padrão das propostas Electric), com soleira 100 mm",
         f"{D['altura']}×{gab['colunas'][0]['largura']}×{D['profundidade']} mm", n_col, "pç"),
        ("Porta frontal com fecho, venezianas inferiores (entrada de ar) e filtro", "", n_col, "pç"),
        ("Porta traseira com fecho e venezianas inferiores", "", n_col, "pç"),
        ("Chapa divisória vertical frente/trás (capacitores | reatores), galvanizada 1,5 mm", "", n_col, "pç"),
        ("Placa de montagem por estágio (chave-fusível + contatora + capacitores)", "", n, "pç"),
        ("Prateleira/suporte de reator, com isoladores", "", n, "pç"),
        (f"Exaustor 230 V {v['exaustor_m3h']} m³/h com grelha e filtro de saída (teto)", "", v["n_exaustores"], "pç"),
        ("Termostato NF 0–60 °C (-B0 35 °C liga exaustores)", "", 1, "pç"),
        ("Termostato NF 0–60 °C (-BT2 55 °C desliga o banco)", "", 1, "pç"),
        ("Barramento de cobre principal (L1/L2/L3) com isoladores", f"{D['largura']} mm", 3, "barra"),
        ("Barra de terra (PE) com conectores", f"{D['largura']} mm", 1, "barra"),
        ("Placa de entrada de cabos (teto ou fundo) com prensa-cabos", "", 1, "pç"),
        ("Olhal de içamento M12", "", 4 * n_col, "pç"),
        ("Plaquetas de acrílico (ver lista de plaquetas)", "", len(plaquetas(ped, res, gab)), "pç"),
    ]


def _tabela_folha(f, titulo, cab, larg, linhas, y0=None):
    x0, y = X0 + 6, (y0 or Y1 - 12)
    f.txt(x0, y, titulo, fs=3.0, ha="left", va="bottom", negrito=True)
    y -= 7
    xs = [x0]
    for w in larg:
        xs.append(xs[-1] + w)
    f.ret(x0, y - 0.5, xs[-1] - x0, 6, lw=0.3, cam="TEXTOS")
    for x, c in zip(xs, cab):
        f.txt(x + 1.2, y + 1.3, c, fs=2.0, ha="left", va="bottom", negrito=True)
    for ln in linhas:
        y -= 5.2
        if y < Y0 + CAR_H + 6:
            break
        for x, t, w in zip(xs, ln, larg):
            t = str(t)
            fs = min(2.0, (w - 2) / max(len(t), 1) * 1.75)
            f.txt(x + 1.2, y + 1.2, t, fs=fs, ha="left", va="bottom")
        f.lin(x0, y - 0.3, xs[-1], y - 0.3, lw=0.1, cam="TEXTOS")
    return y


def _folhas_listas(pr, ped, res, gab):
    pl = plaquetas(ped, res, gab)
    porf = 38
    for k0 in range(0, len(pl), porf):
        f = pr.nova("LISTA DE PLAQUETAS" + (f" ({k0 // porf + 1})" if len(pl) > porf else ""), "=PAINEL", "+GAB", tipo="lista")
        _tabela_folha(f, "Lista de plaquetas", ("ITEM", "TIPO", "QUANT.", "INSCRIÇÃO ( | = quebra de linha)"),
                      (28, 16, 18, 210), pl[k0:k0 + porf])
        leg = [(t, d[0], d[1], d[2], f"{d[3]} × {d[4]}") for t, d in TIPOS_PLAQUETA.items()]
        x = X1 - 120
        f.txt(x, Y1 - 12, "Tipos de plaqueta", fs=2.6, ha="left", va="bottom", negrito=True)
        cab = ("TIPO", "LINHAS", "ALT. LETRA", "CARAC.", "A × B mm")
        xs = [x, x + 14, x + 30, x + 50, x + 66]
        y = Y1 - 19
        for xx, c in zip(xs, cab):
            f.txt(xx, y, c, fs=1.9, ha="left", va="bottom", negrito=True)
        for ln in leg:
            y -= 5
            for xx, t in zip(xs, ln):
                f.txt(xx, y, str(t), fs=1.9, ha="left", va="bottom")
        for i, t in enumerate(["MATERIAL: ACRÍLICO", "ESPESSURA: 3 mm", "FUNDO: PRETO", "LETRAS: BRANCAS",
                               "Fixação: rebite ou fita dupla face VHB"]):
            f.txt(x, y - 8 - 4.5 * i, t, fs=1.9, ha="left", va="bottom")
    f = pr.nova("LISTA DE MATERIAL DO GABINETE", "=PAINEL", "+GAB", tipo="lista")
    _tabela_folha(f, "Lista de material – gabinete e ventilação", ("ITEM", "DESCRIÇÃO", "DADOS", "QTD.", "UN."),
                  (14, 230, 70, 18, 16), [(i + 1, *ln) for i, ln in enumerate(material_gabinete(ped, res, gab))])


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
              f"Arranjo: capacitores na frente, reatores atrás, separados por chapa divisória",
              f"Entrada de ar ≥ {v['area_entrada_cm2']} cm² embaixo; saída pelos exaustores no teto",
              "Termostatos: -B0 35 °C liga exaustores · -BT2 55 °C desliga o banco",
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
