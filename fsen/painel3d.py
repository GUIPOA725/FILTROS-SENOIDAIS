"""Painel 2D/3D no padrão Electric (v1.24.0 – em construção) – mesmo gerador para os 3 filtros.

Folhas no padrão dos layouts Electric (AGCO Ibirubá 2022, CVI 2021 – feitos no SolidWorks), melhorados e automáticos:
  1. painel fechado (isométrica frente e fundo) com cotas gerais;   2. portas abertas;   3. sem chapas (estrutura);
  4. placa de montagem (capacitores, seccionadoras, contatoras) e reatores atrás;   5. vistas frontal / lateral / traseira.
Medidas: SÓ de catálogo (dados/dimensoes_componentes.yaml) ou do projeto FEM do reator Electric. O que não tem medida
confirmada é desenhado em vermelho translúcido e listado como "medida a confirmar" – nunca chutado como se fosse real.
Verificações com Check: reator cabe na coluna, componentes cabem na placa, folgas de ventilação/isolação.
Render: pyvista (VTK, offscreen) – leve, sem SolidWorks.
"""
from __future__ import annotations

import math
import os

import yaml

from . import checagem as CK

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CINZA, LARANJA, PRETO, METAL = "#b8bcc2", "#d9772b", "#2b2b2b", "#d8d8d8"
VERM = "#e53935"
FOLGA = 30            # mm entre componentes / parede (painel_gabinete.folgas_mm)
CHAPA = 2             # mm


def catalogo_dim():
    try:
        return yaml.safe_load(open(os.path.join(RAIZ, "dados", "dimensoes_componentes.yaml"), encoding="utf-8")) or {}
    except Exception:
        return {}


def achar_dim(codigo, grupo):
    """Medida de catálogo pelo código (casamento por trecho do nome). None = a confirmar."""
    cat = catalogo_dim().get(grupo) or {}
    cod = (codigo or "").lower()
    for k, v in cat.items():
        chave = k.lower().split(" (")[0]
        if chave in cod or cod in k.lower() or any(t in cod for t in [p for p in chave.split() if len(p) > 5]):
            if not v.get("conferir") or v.get("L") or v.get("D"):
                return dict(v, nome=k)
    return None


def _caixa(pl, x0, y0, z0, L, P, A, cor, opac=1.0, borda=True):
    import pyvista as pv
    m = pv.Box(bounds=(x0, x0 + L, y0, y0 + P, z0, z0 + A))
    pl.add_mesh(m, color=cor, opacity=opac, show_edges=borda, edge_color="#555555", line_width=0.6, smooth_shading=False)


def _cil(pl, xc, yc, z0, D, A, cor):
    import pyvista as pv
    pl.add_mesh(pv.Cylinder(center=(xc, yc, z0 + A / 2), direction=(0, 0, 1), radius=D / 2, height=A, resolution=40),
                color=cor, smooth_shading=True)
    pl.add_mesh(pv.Cylinder(center=(xc, yc, z0 + A + 8), direction=(0, 0, 1), radius=D / 6, height=16, resolution=20),
                color="#444444")


def modelo(ped, res, gab, prot, inds=None, caps_cod=None):
    """Arranjo físico (lista de peças com posição e medida) + verificações. Unidades: mm. Eixos: x largura, y profundidade
    (0 = frente), z altura."""
    dim = gab["dimensoes_mm"]
    H, W, D = dim["altura"], dim["largura"], dim["profundidade"]
    base = 100
    pecas, faltam, ver = [], [], []
    # reator Electric (FEM)
    d0 = (inds or [None])[0] or {}
    rd = d0.get("dims_mm") or {}
    rL, rP, rA = rd.get("largura"), rd.get("profundidade"), rd.get("altura")
    # capacitor e manobra
    e0 = res["estagios"][0]
    capd = achar_dim(caps_cod or "", "capacitores")
    ctt = achar_dim(prot.get("contator", ""), "contatoras")
    sec = achar_dim("Fupact ISFT160" if prot.get("chave_A", 160) <= 160 else "Fupact ISFT400", "seccionadoras_fusivel")
    for nome, x in (("capacitor", capd), ("contatora", ctt), ("seccionadora-fusível", sec)):
        if not x:
            faltam.append(nome)
    n_cap = e0["cap"][0]
    cols = gab["colunas"]
    x_col = 0
    for c in cols:
        Lc = c["largura"]
        n_est = len(c["estagios"])
        # placa de montagem frontal (laranja) – meia profundidade
        y_pl = D * 0.45
        pecas.append(dict(t="placa", x=x_col + 40, y=y_pl, z=base + 40, L=Lc - 80, P=CHAPA * 2, A=H - base - 260, cor=LARANJA))
        # capacitores na parte de baixo, à frente da placa
        cd = capd or dict(D=116, A=291, nome="capacitor (a confirmar)")
        dcap, acap = cd.get("D", 116), cd.get("A", 291)
        n_tot = n_cap * n_est
        por_linha = max(1, int((Lc - 80 - FOLGA) // (dcap + FOLGA)))
        for k in range(n_tot):
            lin, colk = divmod(k, por_linha)
            pecas.append(dict(t="cil", x=x_col + 40 + FOLGA + dcap / 2 + colk * (dcap + FOLGA), y=y_pl - dcap / 2 - 10 - lin * (dcap + 10),
                              z=base + 60, D=dcap, A=acap, cor=METAL if capd else VERM))
        # seccionadoras e contatoras (fileiras acima)
        z_sec = base + 60 + acap + 120
        sd = sec or dict(L=106, A=194, P=80)
        kd = ctt or dict(L=70, A=110, P=108)
        passo = max(sd["L"], kd["L"]) + FOLGA
        for i in range(n_est):
            xx = x_col + 60 + i * passo
            pecas.append(dict(t="caixa", x=xx, y=y_pl - sd["P"], z=z_sec, L=sd["L"], P=sd["P"], A=sd["A"], cor="#3b3f45" if sec else VERM))
            pecas.append(dict(t="caixa", x=xx, y=y_pl - kd["P"], z=z_sec + sd["A"] + 60, L=kd["L"], P=kd["P"], A=kd["A"],
                              cor="#5f6670" if ctt else VERM))
        larg_fileira = 60 + n_est * passo
        ver.append(["Placa de montagem", f"Fileira de {n_est} seccionadoras/contatoras ({c['funcao']})", f"{larg_fileira:.0f} mm",
                    f"≤ {Lc - 80} mm", CK.texto(CK.check(larg_fileira <= Lc - 80, CK.utilizacao(larg_fileira, Lc - 80)))])
        # reatores atrás, em prateleiras (1 por nível se não couberem 2 lado a lado)
        if rL:
            por_niv = max(1, int((Lc - 2 * FOLGA) // (rL + FOLGA)))
            niveis = math.ceil(n_est / por_niv)
            alt_disp = H - base - 300
            alt_nec = niveis * (rA + 80)
            for i in range(n_est):
                niv, pos = divmod(i, por_niv)
                pecas.append(dict(t="caixa", x=x_col + FOLGA + pos * (rL + FOLGA), y=D - rP - 60, z=base + 40 + niv * (rA + 80),
                                  L=rL, P=rP, A=rA, cor="#c9a46a"))
                pecas.append(dict(t="caixa", x=x_col + 20, y=D - rP - 80, z=base + 30 + niv * (rA + 80), L=Lc - 40, P=rP + 40, A=10,
                                  cor=PRETO))
            ver.append(["Reatores", f"{n_est} reator(es) {rL:.0f}×{rP:.0f}×{rA:.0f} mm na coluna ({por_niv} por nível, {niveis} níveis)",
                        f"{alt_nec:.0f} mm de altura", f"≤ {alt_disp:.0f} mm",
                        CK.texto(CK.check(alt_nec <= alt_disp, CK.utilizacao(alt_nec, alt_disp)))])
            ver.append(["Reatores", "Profundidade: placa frontal + reator atrás + folga de ar", f"{y_pl + rP + 60:.0f} mm", f"≤ {D} mm",
                        CK.texto(CK.check(y_pl + rP + 60 <= D, CK.utilizacao(y_pl + rP + 60, D)))])
        x_col += Lc
    return dict(H=H, W=W, D=D, base=base, pecas=pecas, faltam=faltam, verificacoes=ver, colunas=cols, controlador=True)


def _cena(m, vista="fechado", tam=(1600, 1150)):
    import pyvista as pv
    pv.OFF_SCREEN = True
    pl = pv.Plotter(off_screen=True, window_size=tam)
    pl.set_background("white")
    pl.enable_anti_aliasing("ssaa")
    H, W, D, b = m["H"], m["W"], m["D"], m["base"]
    _caixa(pl, 0, 0, 0, W, D, b, PRETO)                                     # base/soleira
    estrutura = vista in ("portas_abertas", "sem_chapas", "frontal", "lateral", "traseira", "fechado_tras", "fechado")
    if estrutura:
        xs = [0] + [sum(c["largura"] for c in m["colunas"][:i + 1]) - 20 for i in range(len(m["colunas"]))]
        for x in sorted(set([min(max(v, 0), W - 40) for v in xs] + [W - 40])):
            for y in (0, D - 40):
                _caixa(pl, x, y, b, 40, 40, H - b, "#9ea3a8", borda=False)
        for z in (b, H - 40):
            _caixa(pl, 0, 0, z, W, 40, 40, "#9ea3a8", borda=False)
            _caixa(pl, 0, D - 40, z, W, 40, 40, "#9ea3a8", borda=False)
    if vista in ("fechado", "fechado_tras"):
        _caixa(pl, 0, 0, b, W, D, H - b, CINZA)
        x0 = 0
        for c in m["colunas"]:
            for y_, s_ in ((-8, 1), (D, 1)):                                    # portas frontais e tampas traseiras
                _caixa(pl, x0 + 6, y_, b + 10, c["largura"] - 12, 8, H - b - 20, "#a7acb2")
            _caixa(pl, x0 + c["largura"] * 0.2, -14, b + 120, 140, 6, 90, "#d5d8dc")   # venezianas (entrada de ar)
            _caixa(pl, x0 + c["largura"] * 0.6, -14, b + 120, 140, 6, 90, "#d5d8dc")
            _caixa(pl, x0 + c["largura"] * 0.5 - 130, D * 0.5 - 130, H, 260, 260, 60, "#ececec")  # exaustor no teto
            x0 += c["largura"]
        if m.get("controlador"):
            _caixa(pl, m["colunas"][0]["largura"] * 0.55, -16, H * 0.62, 144, 8, 144, "#38536b")
    if vista == "portas_abertas":
        x0 = 0
        for c in m["colunas"]:
            _caixa(pl, x0 + 6, -c["largura"] + 20, b + 10, 8, c["largura"] - 30, H - b - 20, "#a7acb2", opac=0.9)
            x0 += c["largura"]
        _caixa(pl, 0, 0, b, 4, D, H - b, CINZA)                              # lateral
        _caixa(pl, 0, 0, H - 4, W, D, 4, CINZA)                              # teto
    if vista not in ("fechado", "fechado_tras"):
        for p in m["pecas"]:
            if p["t"] == "cil":
                _cil(pl, p["x"], p["y"], p["z"], p["D"], p["A"], p["cor"])
            else:
                _caixa(pl, p["x"], p["y"], p["z"], p["L"], p["P"], p["A"], p["cor"], opac=0.55 if p["cor"] == VERM else 1.0)
    cx, cy, cz = W / 2, D / 2, H / 2
    dist = 3.2 * max(W, H, D)
    pos = {"fechado": (cx - 1.0 * dist, cy - 1.3 * dist, cz + 0.7 * dist), "portas_abertas": (cx - 1.0 * dist, cy - 1.3 * dist, cz + 0.7 * dist),
           "sem_chapas": (cx - 1.0 * dist, cy - 1.3 * dist, cz + 0.7 * dist), "componentes": (cx - 1.0 * dist, cy - 1.3 * dist, cz + 0.7 * dist),
           "fechado_tras": (cx + 1.0 * dist, cy + 1.3 * dist, cz + 0.7 * dist), "traseira": (cx, cy + dist, cz),
           "frontal": (cx, cy - dist, cz), "lateral": (cx - dist, cy, cz)}[vista]
    pl.camera_position = [pos, (cx, cy, cz), (0, 0, 1)]
    if vista in ("frontal", "lateral", "traseira"):
        pl.enable_parallel_projection()
    pl.reset_camera()
    pl.camera.zoom(1.05)
    return pl


VISTAS = (("fechado", "Painel fechado – frente"), ("fechado_tras", "Painel fechado – fundo"), ("portas_abertas", "Portas abertas"),
          ("sem_chapas", "Sem chapas – estrutura e componentes"), ("componentes", "Componentes: placa de montagem (frente) e reatores (atrás)"),
          ("frontal", "Vista frontal (sem portas)"), ("lateral", "Vista lateral (corte)"), ("traseira", "Vista traseira (sem tampas)"))


def renders(m, pasta, cod):
    os.makedirs(pasta, exist_ok=True)
    out = []
    for vista, tit in VISTAS:
        pl = _cena(m, vista)
        arq = os.path.join(pasta, f"Painel3D_{vista}_{cod}.png")
        pl.screenshot(arq)
        pl.close()
        try:                                                    # recorta o branco em volta (folha aproveita a área)
            from PIL import Image, ImageChops
            im = Image.open(arq).convert("RGB")
            bb = ImageChops.difference(im, Image.new("RGB", im.size, "white")).getbbox()
            if bb:
                mg = 20
                im.crop((max(bb[0] - mg, 0), max(bb[1] - mg, 0), min(bb[2] + mg, im.width), min(bb[3] + mg, im.height))).save(arq)
        except Exception:
            pass
        out.append((tit, arq))
    return out


def capacitor_codigo(ped, e0):
    """Código de catálogo do capacitor (só os que têm desenho no catálogo de dimensões)."""
    n, q, u = e0["cap"]
    marca = (getattr(ped, "marca", "") or "").lower()
    if "schneider" in marca and abs(q - 25) < 1 and u in (525,):
        return "Schneider BLRCH250A300B52"
    if abs(q - 40) < 1 and u >= 690:
        return "Epcos B32344E4401F080"
    return None


def gerar(ped, res, gab, prot, inds, pasta, cod, versao="", log=print):
    """Folhas 3D do painel (A3 paisagem, 2 folhas) + PNGs das 8 vistas. Devolve dict(pdf, pngs, verificacoes, faltam)."""
    from reportlab.lib.pagesizes import A3, landscape
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas

    m = modelo(ped, res, gab, prot, inds, capacitor_codigo(ped, res["estagios"][0]))
    pngs = renders(m, os.path.join(pasta, "vistas"), cod)
    arq = os.path.join(pasta, f"Painel_3D_{cod}.pdf")
    W_, H_ = landscape(A3)
    c = canvas.Canvas(arq, pagesize=(W_, H_))
    c.setTitle(f"Painel 3D {cod}")

    def carimbo(folha, titulo):
        c.setLineWidth(1.2)
        c.rect(10 * mm, 10 * mm, W_ - 20 * mm, H_ - 20 * mm)
        x0, y0, lw, lh = W_ - 190 * mm, 10 * mm, 180 * mm, 28 * mm
        c.rect(x0, y0, lw, lh)
        c.setFillColor("#d9772b"); c.rect(x0, y0 + lh - 7 * mm, lw, 7 * mm, fill=1, stroke=0); c.setFillColor("black")
        c.setFont("Helvetica-Bold", 10); c.drawString(x0 + 3 * mm, y0 + lh - 5.2 * mm, "ELECTRIC SERVICE – Plataforma FSEN")
        c.setFont("Helvetica-Bold", 9); c.drawString(x0 + 3 * mm, y0 + 15 * mm, titulo)
        c.setFont("Helvetica", 8)
        c.drawString(x0 + 3 * mm, y0 + 10 * mm, f"Projeto: {cod}   Cliente: {getattr(ped, 'cliente', '') or '-'}")
        c.drawString(x0 + 3 * mm, y0 + 5.5 * mm, f"Painel {m['W']:.0f} × {m['H']:.0f} × {m['D']:.0f} mm (L × A × P)   "
                                                 f"Folha {folha}/2   A3   Sem escala (3D)   {versao}")
        c.drawString(x0 + 3 * mm, y0 + 1.5 * mm, "Medidas dos componentes: catálogo do fabricante; reator: projeto FEM Electric")

    def grade(lista, y_top, alt):
        n = len(lista)
        lw = (W_ - 30 * mm) / n
        for i, (tit, png) in enumerate(lista):
            x = 15 * mm + i * lw
            c.setFont("Helvetica-Bold", 9); c.drawString(x, y_top - 5 * mm, tit)
            c.drawImage(png, x, y_top - alt, width=lw - 4 * mm, height=alt - 8 * mm, preserveAspectRatio=True, anchor="c")

    lst = list(pngs)
    # folha 1: fechado frente/fundo, portas abertas, sem chapas
    alt = (H_ - 60 * mm) / 2
    grade(lst[0:2], H_ - 15 * mm, alt)
    grade(lst[2:4], H_ - 15 * mm - alt, alt)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(15 * mm, 42 * mm, f"Dimensões gerais: {m['W']:.0f} mm (largura) × {m['H']:.0f} mm (altura) × {m['D']:.0f} mm (profundidade) "
                                   f"– {len(m['colunas'])} coluna(s): " + " + ".join(f"{cc['largura']:.0f}" for cc in m["colunas"]) + " mm")
    carimbo(1, "PAINEL – VISTAS 3D (fechado, portas abertas, estrutura)")
    c.showPage()
    # folha 2: componentes + vistas ortogonais + verificações
    alt2 = (H_ - 60 * mm) * 0.62
    grade(lst[4:8], H_ - 15 * mm, alt2)
    y = H_ - 15 * mm - alt2 - 4 * mm
    c.setFont("Helvetica-Bold", 10); c.drawString(15 * mm, y, "Verificações de arranjo físico (Check)"); y -= 5 * mm
    cols = (15, 60, 190, 230, 265)
    c.setFont("Helvetica-Bold", 8)
    for x, h in zip(cols, ("Item", "Verificação", "Valor", "Limite", "Check")):
        c.drawString(x * mm, y, h)
    y -= 4.5 * mm
    c.setFont("Helvetica", 8)
    vistas = set()
    for v in m["verificacoes"]:
        chave = tuple(v[1:])
        if chave in vistas:
            continue
        vistas.add(chave)
        for x, t in zip(cols, v):
            if x == 265:
                st = CK.de_texto(t)
                c.setFillColor(CK.COR.get(st, "black")); c.setFont("Helvetica-Bold", 8)
            c.drawString(x * mm, y, (str(t).replace("✔", "").replace("⚠", "").replace("✖", "").strip())[:95]); c.setFillColor("black"); c.setFont("Helvetica", 8)
        y -= 4.2 * mm
    if m["faltam"]:
        c.setFillColor(VERM)
        c.drawString(15 * mm, y - 2 * mm, "Medida a confirmar no catálogo (desenhado em vermelho translúcido): " + ", ".join(m["faltam"]))
        c.setFillColor("black")
    carimbo(2, "PAINEL – COMPONENTES E VISTAS FRONTAL / LATERAL / TRASEIRA")
    c.save()
    log(f"   Painel 3D: {arq} ({len(pngs)} vistas" + (f"; a confirmar: {', '.join(m['faltam'])}" if m["faltam"] else "") + ")")
    return dict(pdf=arq, pngs=[a for _, a in pngs], verificacoes=m["verificacoes"], faltam=m["faltam"])
