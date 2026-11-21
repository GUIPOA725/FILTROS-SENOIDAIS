"""Estrutura mecânica e saídas do indutor – padrão construtivo de reatores trifásicos nacionais (v1.11.6).

Baseado na montagem usual dos reatores de banco dessintonizado (ex.: Cootrans): quadros em U de chapa dobrada zincada
prendendo as culatras (frente e trás), tirantes roscados passando por buchas soldadas na aba dos quadros (FORA das bobinas,
nos vãos entre fases), pés de fixação na aba inferior do quadro de baixo, furo de içamento na ponta do quadro de cima,
placa de identificação colada na culatra superior e saídas pela PRÓPRIA BARRA da bobina, horizontais, todas para o mesmo lado
(frente = lado dos cabos), terminadas em barra de cobre estanhada aparafusada.

Fonte única da geometria: vista realista (ind_render), desenhos 2D/3D (ind_desenhos) e CAD STEP/DXF (ind_cad).
Coordenadas em mm: x ao longo do núcleo (0..W), y profundidade (frente = y negativo), z vertical (0..H = núcleo).
"""
import math

EXT_X = 40.0            # quadro passa 40 mm além do núcleo em cada ponta (furo de içamento / pés)
ISO_QUADRO = 2.0        # EP GC 203 entre quadro e núcleo
DESCE_PE = 10.0         # quadro de baixo 10 mm abaixo da culatra (núcleo não encosta no piso)
FOLGA_JUNTA = 20.0      # v1.12.0: alma do quadro termina 20 mm antes da junta coluna–culatra (entreferro) – o 3D mostrou que
                        # aço magnético rente ao entreferro desvia fluxo e aquece (correntes parasitas pelo campo espraiado)
FURO_NEMA = 44.5


def perfil_quadro(a):
    """Chapa dobrada em U: espessura e diâmetro do tirante por tamanho de culatra."""
    if a <= 100:
        return dict(t=4.75, d_tir=12, rosca="M12", r_bucha=12.0)
    if a <= 150:
        return dict(t=6.35, d_tir=16, rosca="M16", r_bucha=15.0)
    return dict(t=7.94, d_tir=20, rosca="M20", r_bucha=18.0)


def barra_terminal(i_a):
    """Barra de cobre estanhada do terminal (largura, espessura) pela corrente."""
    if i_a <= 400:
        return 40.0, 6.0
    if i_a <= 630:
        return 50.0, 8.0
    return 60.0, 10.0


def _base(a, b, c, build):
    pq = perfil_quadro(a)
    Ec = b + 2 * (c + build)
    y_w = b / 2 + ISO_QUADRO                       # face interna da alma do quadro
    y_tip = max(Ec / 2 + 12.0, y_w + 45.0)          # ponta da aba (cobre a bobina + 12 mm)
    y_r = y_tip + pq["r_bucha"] - 1.0               # eixo dos tirantes (bucha soldada na ponta da aba)
    return pq, Ec, y_w, y_tip, y_r


def envelope_mm(a, b, c, build, W, H):
    """Dimensões externas (C × P × A) – usado no arranjo do painel sem precisar da geometria completa."""
    pq, Ec, y_w, y_tip, y_r = _base(a, b, c, build)
    y_front = y_tip + 80.0                           # terminais
    y_back = y_r + pq["r_bucha"] + 1.0
    return dict(largura=W + 2 * EXT_X, profundidade=y_front + y_back, altura=H + 2 * DESCE_PE + 28.0)


def estrutura(g, d=None):
    """Devolve dict com caixas, cilindros, furos, terminais e envelope (mm)."""
    a, b, W, H = g["a"], g["b"], g["W"], g["H"]
    pq, Ec, y_w, y_tip, y_r = _base(a, b, g["c"], g["build"])
    t = pq["t"]
    x0, x1 = -EXT_X, W + EXT_X
    cx, cil, furos, notas = [], [], [], []
    fj = min(FOLGA_JUNTA, a * 0.4)
    quadros = dict(inf=(-DESCE_PE, a - fj), sup=(H - a + fj, H + DESCE_PE))
    for nome, (z0, z1) in quadros.items():
        for s, lado in ((-1, "frente"), (1, "tras")):
            ya, yb_ = s * y_w, s * (y_w + t)
            cx.append((f"Quadro {nome} {lado} – alma", "estrutura", (x0, x1, min(ya, yb_), max(ya, yb_), z0, z1)))
            yt = s * y_tip
            for (za, zb) in ((z0, z0 + t), (z1 - t, z1)):
                cx.append((f"Quadro {nome} {lado} – aba", "estrutura", (x0, x1, min(ya, yt), max(ya, yt), za, zb)))
            if nome == "sup":                                       # furo de içamento na ponta do quadro de cima
                for xf in (x0 + EXT_X / 2, x1 - EXT_X / 2):
                    furos.append(((xf, s * (y_w + t / 2), (z0 + z1) / 2), "y", 11.0, "içamento Ø22"))
            else:                                                   # pés: furo oblongo na aba inferior
                for xf in (x0 + EXT_X / 2, x1 - EXT_X / 2):
                    furos.append(((xf, s * (y_w + y_tip) / 2, z0 + t / 2), "z", 7.0, "oblongo 14×25"))
    # tirantes nos vãos entre fases (fora das bobinas), buchas soldadas na ponta das abas
    rb = pq["r_bucha"]
    hb = 35.0
    xw = [a + g["ww"] / 2 + k * (a + g["ww"]) for k in range(2)]
    z_b0, z_b1 = a - fj - hb, a - fj           # bucha do quadro de baixo (na aba superior)
    z_t0, z_t1 = H - a + fj, H - a + fj + hb   # bucha do quadro de cima (na aba inferior)
    hp = 0.9 * pq["d_tir"]                      # altura da porca
    tirantes = []
    for xr in xw:
        for s in (-1, 1):
            yr = s * y_r
            cil.append(("Bucha soldada", "estrutura", (xr, yr, z_b0, z_b1), rb, 24))
            cil.append(("Bucha soldada", "estrutura", (xr, yr, z_t0, z_t1), rb, 24))
            cil.append((f"Tirante {pq['rosca']}", "zinco", (xr, yr, z_b0 - hp - 8, z_t1 + hp + 8), pq["d_tir"] / 2, 16))
            cil.append(("Porca", "zinco", (xr, yr, z_b0 - hp, z_b0), pq["d_tir"] * 0.85, 6))
            cil.append(("Porca", "zinco", (xr, yr, z_t1, z_t1 + hp), pq["d_tir"] * 0.85, 6))
            tirantes.append((xr, yr))
    # placa de identificação colada na culatra superior (face de cima) e caixa do PTC
    cx.append(("Placa de identificação", "placa", (W / 2 - 60, W / 2 + 60, -min(35, b / 2 - 8), min(35, b / 2 - 8), H, H + 0.8)))
    cx.append(("Caixa de bornes PTC", "ptc", (x1 - 75, x1 - 20, -y_tip, -y_tip + 32, H + DESCE_PE, H + DESCE_PE + 28)))
    # ---------------- saídas (terminais) ----------------
    term = terminais(g, d, y_tip)
    for tr in term:
        cx.append((f"Saída {tr['nome']}", "cobre_bar", tr["barra"]))
        cx.append((f"Terminal {tr['nome']}", "estanho", tr["chapa"]))
        for (hx, hy, hz) in tr["furos"]:
            furos.append(((hx, hy, hz), "z", 6.5, "Ø13"))
    y_front = y_tip + 80.0
    env = (x0, x1, -y_front, y_r + rb + 1.0, -DESCE_PE, H + DESCE_PE + 28.0)
    return dict(caixas=cx, cilindros=cil, furos=furos, terminais=term, env=env, perfil=pq, y_w=y_w, y_tip=y_tip, y_r=y_r,
                xw=xw, tirantes=tirantes, quadros=quadros, ext=EXT_X, t=t)


def terminais(g, d, y_tip):
    """Saídas pela própria barra da bobina, horizontais para a FRENTE (lado dos cabos).
    nº de camadas ÍMPAR: início em cima e fim embaixo (como os reatores dessintonizados nacionais);
    PAR (ou folha): as duas saídas em cima – a interna sai pela cabeceira, deitada, por cima das camadas."""
    fio = g.get("fio")
    i_n = float(((d or {}).get("requisitos") or {}).get("In", 300))
    wt, tt = barra_terminal(i_n)
    if fio:
        tb, hb = fio["t"], fio["h"]
        impar = fio["n_cam"] % 2 == 1
    else:
        tb, hb = max(g["tf"], 6.0), 30.0
        impar = False
    zc0, hc, hf = g["yc0"], g["hc"], g["hf"]
    zb0 = zc0 + (hc - hf) / 2
    cab = (hc - hf) / 2
    y_coil = -(g["Ec"] / 2 - g["wrap"])           # superfície externa da bobina
    y_in = -(g["b"] / 2 + g["c"] + g["tube"] + 1)  # face interna do enrolamento
    y_lead_end = -(y_tip - 5)                      # fim da barra da bobina (sob a chapa estanhada)
    y_c0, y_c1 = -(y_tip - 30), -(y_tip + 80)      # chapa estanhada
    xoff = max(g["a"] * 0.375, 14 + wt / 2 + 6)
    out = []
    for i, xc in enumerate(g["xc"]):
        f = "UVW"[i]
        if impar:
            sai = [(f + "1", xc, zb0 + hf - hb / 2, "sup", y_coil, tb, hb),
                   (f + "2", xc, zb0 + hb / 2, "inf", y_coil, tb, hb)]
        else:
            z_in = zb0 + hf + min(cab, tb + 4) / 2 + 1        # saída interna deitada na cabeceira
            sai = [(f + "1", xc - xoff, z_in, "sup", y_in, hb, tb),
                   (f + "2", xc + xoff, zb0 + hf - hb / 2, "sup", y_coil, tb, hb)]
        for nome, x, z, pos, y_ini, larg, alt in sai:
            barra = (x - larg / 2, x + larg / 2, y_lead_end, y_ini, z - alt / 2, z + alt / 2)
            zc_ = z + alt / 2 + tt / 2 - 0.01 if pos == "sup" else z - alt / 2 - tt / 2 + 0.01
            chapa = (x - wt / 2, x + wt / 2, y_c1, y_c0, zc_ - tt / 2, zc_ + tt / 2)
            fz = (x, -(y_tip + 15), zc_), (x, -(y_tip + 15 + FURO_NEMA), zc_)
            out.append(dict(nome=nome, x=x, z=z, pos=pos, barra=barra, chapa=chapa, furos=list(fz), wt=wt, tt=tt))
    return out


def texto_padrao(g, d):
    """Descrição curta para BOM/sequência/e-mail."""
    e = estrutura(g, d)
    pq = e["perfil"]
    fio = g.get("fio")
    impar = bool(fio and fio["n_cam"] % 2 == 1)
    wt, tt = barra_terminal(float(d["requisitos"]["In"]))
    return dict(
        quadro=(f"Quadros de aperto em U de chapa dobrada {pq['t']:.2f}".replace(".", ",") + " mm, aço carbono zincado (frente e trás de cada culatra), "
                f"isolados do núcleo por EP GC 203 {ISO_QUADRO:.0f} mm; a alma termina {FOLGA_JUNTA:.0f} mm ANTES da junta coluna–culatra "
                "(não encostar aço magnético no entreferro); quadro superior com furo de içamento Ø22 nas pontas; "
                "aba inferior do quadro de baixo com 4 furos oblongos 14×25 (pés)"),
        tirante=(f"4 tirantes {pq['rosca']} classe 8.8 zincados, nos vãos entre fases, FORA das bobinas, passando por buchas "
                 "soldadas na ponta das abas; porca + arruela de pressão"),
        saida=(f"Saída pela própria barra da bobina, horizontal para a frente (lado dos cabos), "
               + ("início em CIMA e fim EMBAIXO" if impar else "início e fim em CIMA (saída interna deitada na cabeceira)")
               + f", brasada em barra Cu estanhada {wt:.0f}×{tt:.0f} com 2 furos Ø13 (NEMA, 44,5 mm)"),
        impar=impar)
