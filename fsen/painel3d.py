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


def _tubo(lst, g, pts, D, cor):
    """Cabo/condutor flexível por pontos (rota de montagem)."""
    lst.append(dict(t="tubo", g=g, pts=[tuple(map(float, q)) for q in pts], D=D, cor=cor))


# ---- componentes com a forma do catálogo (medidas externas do catálogo; detalhes proporcionais dentro do envelope)
def _capacitor(p, xc, yc, z, d, a, ok, term=45):
    """Capacitor cilíndrico (VarPlus Can / PhiCap): lata de alumínio com friso, tampa com bloco de terminais e capa."""
    cor = C_CAP if ok else C_VERM
    op = 1.0 if ok else 0.6
    _cl(p, "frente", xc, yc, z, d, a * 0.86, cor, op=op)
    _cl(p, "frente", xc, yc, z + a * 0.86, d * 0.95, a * 0.03, "#c9c9c9", op=op)              # friso (rebordo)
    _cl(p, "frente", xc, yc, z + a * 0.89, d, a * 0.11, cor, op=op)
    _cl(p, "frente", xc, yc, z + a * 0.25, d * 1.004, a * 0.22, "#d2d8de", op=op)             # etiqueta
    _cl(p, "frente", xc, yc, z + a, d * 0.62, term * 0.55, "#2b2b2b")                         # bloco de terminais
    for k in range(3):
        ang = 2 * math.pi * k / 3 + math.pi / 2
        _cl(p, "frente", xc + d * 0.18 * math.cos(ang), yc + d * 0.18 * math.sin(ang), z + a + term * 0.55, 12, term * 0.3, "#b0b0b0")
    _cl(p, "frente", xc, yc, z + a + term * 0.55, d * 0.2, term * 0.2, "#1a1a1a")             # resistor de descarga (topo)


def _secc(p, x, y_face, z, d, ok):
    """Chave seccionadora-fusível NH (Fupact ISFT): base, tampa frontal articulada com punho, protetores de terminais."""
    L, A, P = d["L"], d["A"], d["P"]
    cb = "#d9d9d9" if ok else C_VERM
    op = 1.0 if ok else 0.6
    _cx(p, "frente", x, y_face - P * 0.45, z, L, P * 0.45, A, cb, op)                        # base
    _cx(p, "frente", x + L * 0.04, y_face - P, z + A * 0.14, L * 0.92, P * 0.55, A * 0.72, "#55595e", op)   # tampa (porta-fusíveis)
    for k in range(3):                                                                       # janelas de indicação dos fusíveis
        _cx(p, "frente", x + L * (0.12 + 0.28 * k), y_face - P - 2, z + A * 0.5, L * 0.18, 2, A * 0.12, "#d0d0d0")
    _cx(p, "frente", x + L * 0.30, y_face - P - 22, z + A * 0.26, L * 0.40, 22, A * 0.08, "#1c1c1c")   # punho
    for zz in (z, z + A * 0.86):                                                             # protetores de terminais
        _cx(p, "frente", x + L * 0.06, y_face - P * 0.55, zz, L * 0.88, P * 0.12, A * 0.14, "#9c9c9c")


def _contatora(p, x, y_face, z, d, ok):
    """Contatora (TeSys D / AF): corpo escalonado, frente com janela de indicação, bornes em cima e embaixo, bobina A1/A2."""
    L, A, P = d["L"], d["A"], d["P"]
    cb = "#34373a" if ok else C_VERM
    op = 1.0 if ok else 0.6
    _cx(p, "frente", x, y_face - P * 0.55, z, L, P * 0.55, A, cb, op)                        # corpo (trilho/placa)
    _cx(p, "frente", x + L * 0.08, y_face - P * 0.85, z + A * 0.14, L * 0.84, P * 0.30, A * 0.72, "#43474b", op)
    _cx(p, "frente", x + L * 0.2, y_face - P, z + A * 0.32, L * 0.6, P * 0.15, A * 0.36, "#4f5458", op)   # frente (porta-etiqueta)
    _cx(p, "frente", x + L * 0.38, y_face - P - 2, z + A * 0.44, L * 0.24, 2, A * 0.12, "#e6e6e6")          # janela de indicação
    for zz in (z + A * 0.02, z + A * 0.86):                                                  # bornes de potência
        for k in range(3):
            _cl(p, "frente", x + L * (0.2 + 0.3 * k), y_face - P * 0.68, zz + A * 0.06, 9, A * 0.05, "#c0c0c0", eixo="y")
    _cx(p, "frente", x + L * 0.78, y_face - P * 0.9, z + A * 0.78, L * 0.16, P * 0.08, A * 0.08, "#b0b0b0")   # A1/A2


def _reator(p, x, y, z, L, P, A):
    """Reator trifásico Electric (FEM): núcleo laminado (colunas + culatras), 3 bobinas com enfaixamento, quadros em U
    zincados com tirantes, pés, saídas em barra de cobre por fase e caixa do termostato – medidas externas do projeto FEM."""
    hy = A * 0.14
    pn = P * 0.42                                                                              # espessura do pacote do núcleo
    yn = y + (P - pn) / 2
    _cx(p, "tras", x + L * 0.03, yn, z + 14, L * 0.94, pn, hy, C_NUC)                          # culatra inferior
    _cx(p, "tras", x + L * 0.03, yn, z + A - hy - 30, L * 0.94, pn, hy, C_NUC)                 # culatra superior
    for yy in (yn - 6, yn + pn):                                                               # quadros em U (frente/trás)
        for zz in (z + 10, z + A - hy - 34):
            _cx(p, "tras", x, yy, zz, L, 6, hy + 8, "#a9adb2")
    db = min(L / 3.1, P * 0.95)
    hb = A - 2 * hy - 60
    for k in range(3):
        xc = x + db / 2 + 6 + k * (L - db - 12) / 2
        _cl(p, "tras", xc, y + P / 2, z + hy + 22, db, hb, C_BOB)
        _cl(p, "tras", xc, y + P / 2, z + hy + 22 + hb * 0.45, db * 1.01, hb * 0.07, "#8f6f3c")   # faixa/enfaixamento
        _cx(p, "tras", xc - 12, y + P * 0.05, z + A - hy - 30 + hy + 6, 24, 8, 54, "#b87333")    # saída (barra Cu)
        _cx(p, "tras", xc - 12, y + P * 0.05, z + A - hy - 30 + hy + 50, 24, 30, 8, "#b87333")
    for k in range(2):                                                                         # tirantes nos vãos entre fases
        xt = x + db + 6 + k * (L - db - 12) / 2 + (L - 3 * db - 12) / 4
        _cl(p, "tras", xt, yn - 10, z + 10, 10, A - 30, "#8a8a8a")
    for xx in (x - 20, x + L - 30):                                                            # pés (cantoneira com furos)
        _cx(p, "tras", xx, y, z, 50, P, 12, "#2f2f2f")
    _cx(p, "tras", x + L * 0.72, yn - 40, z + A - hy - 20, 50, 34, 40, "#e0e0e0")              # caixa do termostato


def _prateleira(p, x, y, z, L, P):
    for yy in (y, y + P - PERFIL):
        _cx(p, "tras", x, yy, z, L, PERFIL, PERFIL, C_PRAT)
    for xx in (x, x + L - PERFIL):
        _cx(p, "tras", xx, y, z, PERFIL, P, PERFIL, C_PRAT)
    for k in range(1, 3):                                                                      # travessas de apoio
        _cx(p, "tras", x, y + P * k / 3 - 15, z, L, 30, 25, C_PRAT)


def _canaleta(p, g, x, y_face, z, L, A, P=60, vertical=False):
    """Canaleta recortada (cinza) com tampa – percurso dos cabos de força/comando."""
    _cx(p, g, x, y_face - P, z, L, P, A, "#8f9499")
    if vertical:
        _cx(p, g, x + 4, y_face - P - 3, z, L - 8, 3, A, "#b4b8bc")
    else:
        _cx(p, g, x, y_face - P - 3, z + 4, L, 3, A - 8, "#b4b8bc")


def _barramento(p, x0, x1, y_face, z, n=3, esp=45):
    """Barramento de cobre (L1/L2/L3) sobre isoladores."""
    for f in range(n):
        zz = z + f * esp
        _cx(p, "frente", x0, y_face - 95, zz, x1 - x0, 10, 30, C_BARRA)
        for xx in (x0 + 40, (x0 + x1) / 2, x1 - 40):
            _cl(p, "frente", xx, y_face - 45, zz + 15, 26, 85, "#7a1d1d", eixo="y")


# ---- arranjo
def _dist_vertical(z0, z1, blocos, gap_min):
    """Distribui os blocos (altura) entre z0 e z1 com folgas IGUAIS ≥ gap_min (sem espaço vazio concentrado)."""
    soma = sum(blocos)
    livre = (z1 - z0) - soma
    n = len(blocos) + 1
    gap = max(livre / n, gap_min if livre >= gap_min * n else livre / n)
    zs, z = [], z0 + gap
    for h in blocos:
        zs.append(z)
        z += h + gap
    return zs, gap, livre


def modelo(ped, res, gab, prot, inds=None, caps_cod=None, base=None):
    """Arranjo físico (peças com posição e medida, mm; x largura, y profundidade 0 = frente, z altura) + verificações.
    `base` = parâmetros do último painel APROVADO compatível (biblioteca de painéis) – parte dele em vez do zero."""
    from . import biblioteca_paineis as BP
    prm = BP.parametros(base)
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
    cd = capd or dict(D=116, A=291, terminal=45)
    sd = sec or dict(L=106, A=194, P=80)
    kd = ctt or dict(L=70, A=110, P=108)
    rL, rP, rA = rL or 320, rP or 240, rA or 320
    n_cap = e0["cap"][0]
    cols = gab["colunas"]
    folga = prm["folga_componentes_mm"]
    # placa posicionada pela profundidade que os reatores precisam atrás (com cabos e ar) – resto fica na frente
    prof_tras = CHAPA / 2 + prm["folga_reator_placa_mm"] + rP + prm["folga_cabos_tras_mm"]
    yp = min(D / 2 + 60, max(D / 2 - 60, D - PERFIL - prof_tras))
    zt = H - 40
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
    x0c = cols[0]["largura"] * 0.5 - 72                               # controlador, sinaleiros e emergência na porta
    _cx(p, "porta_f", x0c, -24, H * 0.62, 144, 6, 144, "#20384e")
    _cx(p, "porta_f", x0c + 14, -27, H * 0.62 + 50, 116, 3, 70, "#3fa7d6")
    n_est_tot = len(res["estagios"])
    for k in range(n_est_tot):
        _cl(p, "porta_f", x0c - 120 + k * 50, -30, H * 0.55, 22, 12, "#2e7d32", eixo="y")
    _cl(p, "porta_f", x0c + 230, -32, H * 0.62 + 30, 40, 16, "#d32f2f", eixo="y")
    # ---------- por coluna: placa dupla face; frente distribuída sem vazio; trás reatores; cabos e barras montáveis
    for i, c in enumerate(cols):
        x0, Lc = xs[i], c["largura"]
        n_est = len(c["estagios"])
        zp0, zp1 = BASE + 60, H - 140
        xa, xb = x0 + 40, x0 + Lc - 40                               # placa útil
        _cx(p, "placa", xa, yp - CHAPA / 2, zp0, xb - xa, CHAPA, zp1 - zp0, C_PLACA)
        yf = yp - CHAPA / 2
        cv = prm["canaleta_vertical_mm"]
        xu0, xu1 = xa + 10 + cv + folga, xb - 10 - cv - folga        # largura útil entre canaletas (zona da manobra)
        xk0, xk1 = xa + folga, xb - folga                            # capacitores usam a largura toda (canaletas param acima)
        # capacitores: fileiras na largura, no máx. N fileiras na profundidade; o resto vai para um 2º nível (prateleira)
        dcap, acap, tcap = cd.get("D", 116), cd.get("A", 291), cd.get("terminal", 45)
        n_tot = n_cap * n_est
        passo_c = dcap + prm["folga_capacitores_mm"]
        por_linha = max(1, int((xk1 - xk0 + prm["folga_capacitores_mm"]) // passo_c))
        nprof_max = max(1, int((yf - PERFIL - 30) // (dcap + 15)))
        nprof = min(prm["capacitores_fileiras_prof_max"], nprof_max)
        por_nivel = por_linha * nprof
        niveis_c = math.ceil(n_tot / por_nivel)
        h_cap = acap + tcap + 25
        # contatoras e chaves NH: fileira única por coluna, passo distribuído por toda a largura útil (afastadas = ar e ferramenta)
        passo = (xu1 - xu0) / n_est
        dut = prm["canaleta_horizontal_mm"]
        # níveis de capacitores empilhados (só a prateleira entre eles); canaleta acima dos capacitores, entre contatoras e
        # chaves e abaixo do barramento; folgas iguais distribuídas no que sobra (sem vazio concentrado)
        blocos_c = [niveis_c * h_cap + (niveis_c - 1) * 40, dut, kd["A"], dut, sd["A"], dut, 3 * 45 + 30]
        zs, gap, livre = _dist_vertical(zp0 + 40, zp1 - 30, blocos_c, prm["folga_vertical_min_mm"])
        z_caps = [zs[0] + k * (h_cap + 40) for k in range(niveis_c)]
        z_dut = [zs[1], zs[3], zs[5]]
        z_km, z_sc, z_bb = zs[2], zs[4], zs[6]
        zv0 = z_dut[0]
        _canaleta(p, "frente", xa + 10, yf, zv0, cv, zp1 - 20 - zv0, vertical=True)   # canaletas verticais laterais (acima dos capacitores)
        _canaleta(p, "frente", xb - 10 - cv, yf, zv0, cv, zp1 - 20 - zv0, vertical=True)
        for zd in z_dut:
            _canaleta(p, "frente", xu0 - folga, yf, zd, xu1 - xu0 + 2 * folga, dut)
        # capacitores
        k = 0
        for nv, zc in enumerate(z_caps):
            yprat = yf - nprof * (dcap + 15) - 20
            _cx(p, "frente", xk0 - 10, yprat, zc - 22, xk1 - xk0 + 20, nprof * (dcap + 15) + 20, 22, C_PRAT)   # prateleira/trilho
            n_lv = min(por_nivel, n_tot - nv * por_nivel)
            n_l = min(por_linha, math.ceil(n_lv / nprof))
            passo_r = (xk1 - xk0) / n_l                                   # latas espalhadas por igual na largura (ar entre elas)
            xc0 = xk0 + passo_r / 2
            for _ in range(por_nivel):
                if k >= n_tot:
                    break
                lin, ck = divmod(k - nv * por_nivel, por_linha)
                lin, ck = divmod(k - nv * por_nivel, n_l)
                _capacitor(p, xc0 + ck * passo_r, yf - dcap / 2 - 15 - lin * (dcap + 15), zc, dcap, acap, bool(capd), tcap)
                k += 1
        for j in range(n_est):
            xm = xu0 + passo * (j + 0.5)
            _contatora(p, xm - kd["L"] / 2, yf, z_km, kd, bool(ctt))
            _secc(p, xm - sd["L"] / 2, yf, z_sc, sd, bool(sec))
            # rotas de montagem por fase: barra → chave (cordoalha) | chave → contatora (pela canaleta) | contatora → passa-cabo
            for f in range(3):
                dx = (f - 1) * sd["L"] * 0.28
                ycab = yf - 35
                _tubo(p, "frente", [(xm + dx, yf - 70, z_bb + f * 45 + 15), (xm + dx, yf - 70, z_sc + sd["A"] + 10)], 10, "#b87333")
                _tubo(p, "frente", [(xm + dx, ycab, z_sc), (xm + dx, ycab, z_dut[1] + dut / 2),
                                    (xm + dx * 0.8, ycab, z_km + kd["A"])], 12, "#1e1e1e")
                _tubo(p, "frente", [(xm + dx * 0.8, ycab, z_km), (xm + dx * 0.8, ycab, z_dut[0] + dut / 2),
                                    (xm + dx * 0.8, yp, z_dut[0] + dut / 2)], 12, "#1e1e1e")
            _cl(p, "placa", xm, yp, z_dut[0] + dut / 2, 50, 8, "#f2f2f2", eixo="y")   # passa-cabos (prensa) na placa
        _barramento(p, xu0 - folga + 10, xu1 + folga - 10, yf, z_bb + 15)
        # verificações de montagem (Check)
        ocup = sum(blocos_c) / (zp1 - zp0 - 70)
        ver.append(["Placa – frente", f"Distribuição vertical sem vazio concentrado ({c['funcao']}): folga igual entre fileiras",
                    f"{gap:.0f} mm", f"≥ {prm['folga_vertical_min_mm']} mm (cabos e ar)",
                    CK.texto(CK.check(gap >= prm["folga_vertical_min_mm"], CK.utilizacao(prm["folga_vertical_min_mm"], max(gap, 1))))])
        esp_lat = passo - max(kd["L"], sd["L"])
        ver.append(["Placa – frente", f"Afastamento lateral entre chaves/contatoras ({n_est} por coluna, passo {passo:.0f} mm) – {c['funcao']}",
                    f"{esp_lat:.0f} mm", f"≥ {prm['afastamento_lateral_min_mm']} mm (ar e ferramenta)",
                    CK.texto(CK.check(esp_lat >= prm["afastamento_lateral_min_mm"],
                                      CK.utilizacao(prm["afastamento_lateral_min_mm"], max(esp_lat, 1))))])
        prof_frente = nprof * (dcap + 15) + 20
        ver.append(["Placa – frente", f"Capacitores: {n_tot} em {niveis_c} nível(is) × {nprof} fileira(s) na profundidade – {c['funcao']}",
                    f"{prof_frente:.0f} mm", f"≤ {yf - PERFIL - 30:.0f} mm",
                    CK.texto(CK.check(prof_frente <= yf - PERFIL - 30, CK.utilizacao(prof_frente, yf - PERFIL - 30)))])
        ver.append(["Placa – frente", f"Ocupação da altura útil da placa ({c['funcao']})", f"{ocup * 100:.0f} %",
                    "50–90 % (nem vazia, nem apertada)",
                    CK.texto(CK.check(0.5 <= ocup <= 0.9, ocup * 100 / 90 * 100 if ocup > 0.5 else 95))])
        # trás: reatores em prateleiras, cabos pela passagem da placa
        yr = yp + CHAPA / 2 + prm["folga_reator_placa_mm"]
        por_niv = max(1, int((xb - xa - FOLGA) // (rL + FOLGA)))
        niveis = math.ceil(n_est / por_niv)
        # prateleiras distribuídas por igual na altura (mais ar entre os reatores; nada de vazio concentrado em cima)
        h_niv = PERFIL + rA + 40
        zs_r, gap_r, _ = _dist_vertical(BASE + 40, zp1 - 250, [h_niv] * niveis, prm["folga_vertical_reatores_mm"])
        gap_r = min(gap_r, 2.5 * prm["folga_vertical_reatores_mm"])          # não espalhar demais: ar sobe para o exaustor
        zs_r = [BASE + 40 + k * (h_niv + gap_r) for k in range(niveis)]
        passo_niv = h_niv + gap_r
        for nv in range(niveis):
            _prateleira(p, xa, yr - 10, zs_r[nv], xb - xa, rP + 30)
        for j in range(n_est):
            nv, pos = divmod(j, por_niv)
            usado = min(por_niv, n_est - nv * por_niv)
            sobra = (xb - xa) - usado * rL
            esp = sobra / (usado + 1)                                   # reatores afastados por igual (ar entre eles)
            xr = xa + esp + pos * (rL + esp)
            zr = zs_r[nv] + PERFIL
            _reator(p, xr, yr, zr, rL, rP, rA)
            xm = xu0 + passo * (j % n_est + 0.5)
            zpass = z_dut[0] + dut / 2
            zt_r = zr + rA + 45
            yb_ = yp + CHAPA / 2 + 16                                   # cabos amarrados no verso da placa (folga placa–reator)
            for f in range(3):                                          # rota ortogonal: passa-cabo → verso da placa → topo do reator → saída
                xt = xr + rL * (0.17 + 0.33 * f)
                dz = (f - 1) * 14
                xv = xm + (f - 1) * 18
                _tubo(p, "tras", [(xv, yp, zpass), (xv, yb_, zpass), (xv, yb_, zt_r + dz), (xt, yb_, zt_r + dz),
                                  (xt, yr + rP * 0.09, zt_r + dz), (xt, yr + rP * 0.09, zr + rA - 5)], 11, C_CABO)
        alt_nec = zs_r[-1] + h_niv
        ver.append(["Reatores", f"{n_est} reator(es) {rL:.0f}×{rP:.0f}×{rA:.0f} mm atrás da placa ({por_niv} por prateleira, "
                    f"{niveis} prateleira(s)) – {c['funcao']}", f"{alt_nec:.0f} mm de altura", f"≤ {zp1:.0f} mm",
                    CK.texto(CK.check(alt_nec <= zp1, CK.utilizacao(alt_nec, zp1)))])
        ver.append(["Reatores", f"Profundidade atrás da placa: folga + reator + cabos ({c['funcao']})", f"{prof_tras:.0f} mm",
                    f"≤ {D - PERFIL - yp:.0f} mm", CK.texto(CK.check(prof_tras <= D - PERFIL - yp, CK.utilizacao(prof_tras, D - PERFIL - yp)))])
        esp_r = ((xb - xa) - por_niv * rL) / (por_niv + 1)
        ver.append(["Reatores", f"Afastamento entre reatores na prateleira ({por_niv} lado a lado) – {c['funcao']}", f"{esp_r:.0f} mm",
                    f"≥ {FOLGA} mm (ar)", CK.texto(CK.check(esp_r >= FOLGA, CK.utilizacao(FOLGA, max(esp_r, 1))))])
    return dict(H=H, W=W, D=D, base=BASE, pecas=p, faltam=faltam, verificacoes=ver, colunas=cols, xs=xs,
                reator=(rL, rP, rA), cap=(cd.get("D"), cd.get("A")), n_est=n_est_tot, params=prm, base_aprovada=prm.get("_origem"))


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
    import numpy as np
    import pyvista as pv
    if pc["t"] == "tubo":
        ln = pv.lines_from_points(np.array(pc["pts"]))
        pl.add_mesh(ln.tube(radius=pc["D"] / 2, n_sides=12), color=pc["cor"], smooth_shading=True)
    elif pc["t"] == "caixa":
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

    from . import biblioteca_paineis as BP
    base = BP.ultimo_aprovado(tipo=getattr(ped, "tipo", "banco"), n_estagios=len(res["estagios"]))
    m = modelo(ped, res, gab, prot, inds, base=base)
    BP.salvar_layout(m, pasta, cod, ped)
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
