"""Painel 2D de montagem (v1.25.0) – vistas ortogonais vetoriais COTADAS geradas do MESMO modelo do painel 3D
(painel3d.modelo): frontal sem porta, traseira sem porta, lateral em corte e topo. PDF A3 + DXF (camadas por função).
O 2D e o 3D nunca divergem: são a mesma lista de peças (medidas de catálogo / FEM). Cotas de posição de cada fileira e
de cada coluna para o montador conferir (REQ-PNL-011/016).
"""
from __future__ import annotations

import math
import os

COR_2D = {"estrutura": (0.45, 0.45, 0.45), "placa": (0.78, 0.39, 0.12), "frente": (0.1, 0.1, 0.1), "tras": (0.1, 0.1, 0.1),
          "base": (0.2, 0.2, 0.2), "teto": (0.5, 0.5, 0.5)}


def _bbox_malha(pc):
    pts = [q for f, _h in pc["faces"] for q in f]
    return [min(q[k] for q in pts) for k in range(3)], [max(q[k] for q in pts) for k in range(3)]


def _caixas(m, grupos):
    """Peças como retângulos 3D (x0,x1,y0,y1,z0,z1,grupo,cor) – cilindros e malhas pelo envelope, tubos como polilinhas."""
    bx, tubos = [], []
    for pc in m["pecas"]:
        g = pc.get("g")
        if g not in grupos:
            continue
        t = pc["t"]
        if t == "caixa":
            bx.append((pc["x"], pc["x"] + pc["L"], pc["y"], pc["y"] + pc["P"], pc["z"], pc["z"] + pc["A"], g, pc.get("cor"), "r"))
        elif t == "cil":
            r = pc["D"] / 2
            if pc.get("eixo", "z") == "z":
                bx.append((pc["x"] - r, pc["x"] + r, pc["y"] - r, pc["y"] + r, pc["z"], pc["z"] + pc["A"], g, pc.get("cor"), "cz"))
            else:
                bx.append((pc["x"] - r, pc["x"] + r, pc["y"] - pc["A"], pc["y"], pc["z"] - r, pc["z"] + r, g, pc.get("cor"), "cy"))
        elif t == "malha":
            mn, mx = _bbox_malha(pc)
            bx.append((mn[0], mx[0], mn[1], mx[1], mn[2], mx[2], g, pc.get("cor"), "r"))
        elif t == "tubo":
            tubos.append((pc["pts"], g, pc.get("cor"), pc["D"]))
    return bx, tubos


VISTAS2D = {
    "frontal": dict(eixo=("x", "z"), grupos={"estrutura", "base", "placa", "frente"}, titulo="VISTA FRONTAL (sem porta) – placa: frente"),
    "traseira": dict(eixo=("x", "z"), grupos={"estrutura", "base", "placa", "tras"}, titulo="VISTA TRASEIRA (sem porta) – reatores e barramento",
                     espelho=True),
    "lateral": dict(eixo=("y", "z"), grupos={"estrutura", "base", "placa", "frente", "tras"}, titulo="VISTA LATERAL (corte) – frente à esquerda"),
    "topo": dict(eixo=("x", "y"), grupos={"estrutura", "base", "placa", "frente", "tras", "teto"}, titulo="VISTA DE TOPO (sem teto)"),
}
_IDX = {"x": (0, 1), "y": (2, 3), "z": (4, 5)}


def _proj(b, eixo):
    (a0, a1), (b0, b1) = _IDX[eixo[0]], _IDX[eixo[1]]
    return b[a0], b[a1], b[b0], b[b1]


def desenhar_vista(c, m, vista, ox, oy, esc, mm):
    v = VISTAS2D[vista]
    bx, tubos = _caixas(m, v["grupos"])
    W = m["W"]
    ordem = {"estrutura": 0, "base": 0, "placa": 1, "tras": 2, "frente": 3, "teto": 4}
    if vista == "lateral":
        bx = [b for b in bx if b[1] - b[0] < m["W"] * 0.95 or b[6] in ("placa", "estrutura", "base")]
    for b in sorted(bx, key=lambda b: ordem.get(b[6], 2)):
        u0, u1, w0, w1 = _proj(b, v["eixo"])
        if v.get("espelho"):
            u0, u1 = W - u1, W - u0
        c.setStrokeColorRGB(*COR_2D.get(b[6], (0.1, 0.1, 0.1)))
        c.setLineWidth(0.35 if b[6] in ("frente", "tras") else 0.6)
        x, y, w, h = ox + u0 * esc, oy + w0 * esc, (u1 - u0) * esc, (w1 - w0) * esc
        if (b[8] == "cz" and vista == "topo") or (b[8] == "cy" and vista in ("frontal", "traseira")):
            c.circle(x + w / 2, y + h / 2, min(w, h) / 2, stroke=1, fill=0)
        else:
            c.rect(x, y, w, h, stroke=1, fill=0)
    c.setLineWidth(0.5)
    for pts, g, cor, D in tubos:
        k0, k1 = _IDX[v["eixo"][0]][0] // 2, _IDX[v["eixo"][1]][0] // 2
        cor_rgb = (0.75, 0.1, 0.1) if (cor or "").lower() in ("#b0201c",) else ((0.45, 0.65, 0.2) if (cor or "").lower() == "#8bc34a"
                                                                               else ((0.75, 0.46, 0.2) if (cor or "").lower() == "#b87333" else (0.15, 0.15, 0.15)))
        c.setStrokeColorRGB(*cor_rgb)
        p = c.beginPath()
        for i, q in enumerate(pts):
            u, w_ = q[k0], q[k1]
            if v.get("espelho"):
                u = W - u
            (p.moveTo if i == 0 else p.lineTo)(ox + u * esc, oy + w_ * esc)
        c.drawPath(p, stroke=1, fill=0)
    c.setStrokeColorRGB(0, 0, 0)


def _cota(c, x0, y0, x1, y1, txt, off, mm, vertical=False):
    c.setLineWidth(0.3)
    if vertical:
        xx = x0 + off
        c.line(xx, y0, xx, y1); c.line(x0, y0, xx + 2, y0); c.line(x0, y1, xx + 2, y1)
        for yy, s in ((y0, 1), (y1, -1)):
            c.line(xx, yy, xx - 1.2, yy + 3 * s); c.line(xx, yy, xx + 1.2, yy + 3 * s)
        c.saveState(); c.translate(xx - 2, (y0 + y1) / 2); c.rotate(90); c.setFont("Helvetica", 6.5)
        c.drawCentredString(0, 0, txt); c.restoreState()
    else:
        yy = y0 + off
        c.line(x0, yy, x1, yy); c.line(x0, y0, x0, yy - 2); c.line(x1, y0, x1, yy - 2)
        for xx, s in ((x0, 1), (x1, -1)):
            c.line(xx, yy, xx + 3 * s, yy + 1.2); c.line(xx, yy, xx + 3 * s, yy - 1.2)
        c.setFont("Helvetica", 6.5)
        c.drawCentredString((x0 + x1) / 2, yy + 1.5, txt)


def gerar(m, pasta, cod, ped, versao="", log=print):
    """PDF A3 (2 folhas) + DXF das vistas cotadas. Devolve dict(pdf, dxf)."""
    from reportlab.lib.pagesizes import A3, landscape
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas
    os.makedirs(pasta, exist_ok=True)
    arq = os.path.join(pasta, f"Painel_2D_Montagem_{cod}.pdf")
    W_, H_ = landscape(A3)
    c = canvas.Canvas(arq, pagesize=(W_, H_))
    W, H, D = m["W"], m["H"], m["D"]

    def moldura(folha, tit):
        c.setLineWidth(1); c.rect(10 * mm, 10 * mm, W_ - 20 * mm, H_ - 20 * mm)
        x0, y0, lw, lh = W_ - 200 * mm, 10 * mm, 190 * mm, 26 * mm
        c.rect(x0, y0, lw, lh)
        c.setFillColorRGB(0.78, 0.39, 0.12); c.rect(x0, y0 + lh - 7 * mm, lw, 7 * mm, fill=1, stroke=0)
        c.setFillColorRGB(1, 1, 1); c.setFont("Helvetica-Bold", 10)
        c.drawString(x0 + 3 * mm, y0 + lh - 5.2 * mm, "ELECTRIC SERVICE – Plataforma FSEN")
        c.drawRightString(x0 + lw - 3 * mm, y0 + lh - 5.2 * mm, f"Folha {folha}/2")
        c.setFillColorRGB(0, 0, 0); c.setFont("Helvetica-Bold", 9); c.drawString(x0 + 3 * mm, y0 + 13 * mm, tit)
        c.setFont("Helvetica", 7.5)
        c.drawString(x0 + 3 * mm, y0 + 8 * mm, f"Projeto {cod} – {getattr(ped, 'cliente', '')} – painel {W:.0f} × {H:.0f} × {D:.0f} mm – cotas em mm")
        c.drawString(x0 + 3 * mm, y0 + 3.5 * mm, f"Gerado do mesmo modelo do Painel 3D (medidas de catálogo / FEM) – {versao}")

    # folha 1: frontal + traseira (mesma escala)
    ox1, oy = 58 * mm, 48 * mm
    esc = min((W_ - ox1 - 30 * mm - 45 * mm) / (2 * W), (H_ - 80 * mm) / H)
    ox2 = ox1 + W * esc + 45 * mm
    for vista, ox in (("frontal", ox1), ("traseira", ox2)):
        desenhar_vista(c, m, vista, ox, oy, esc, mm)
        c.setFont("Helvetica-Bold", 9); c.drawString(ox, oy + H * esc + 8 * mm, VISTAS2D[vista]["titulo"])
        _cota(c, ox, oy, ox + W * esc, oy, f"{W:.0f}", -8 * mm, mm)
        _cota(c, ox + W * esc, oy, ox + W * esc, oy + H * esc, f"{H:.0f}", 8 * mm, mm, vertical=True)
        xa = 0
        for cc in m["colunas"]:                                         # cota de cada coluna
            _cota(c, ox + xa * esc, oy + H * esc, ox + (xa + cc["largura"]) * esc, oy + H * esc, f"{cc['largura']:.0f}", 4 * mm, mm)
            xa += cc["largura"]
    # cotas verticais das fileiras na vista frontal (posição de montagem)
    zs = sorted({round(pc["z"]) for pc in m["pecas"] if pc.get("g") == "frente" and pc["t"] == "caixa" and pc.get("A", 0) > 80})
    zs = [z for i, z in enumerate(zs) if i == 0 or z - zs[i - 1] > 60][:7]
    for k, z in enumerate(zs):
        _cota(c, ox1, oy, ox1, oy + z * esc, f"{z:.0f}", -(8 + 5 * k) * mm, mm, vertical=True)
    c.setFont("Helvetica", 7)
    c.drawString(ox1, oy - 16 * mm, f"Escala ≈ 1:{1 / (esc / mm):.0f}. Cotas verticais à esquerda = altura de montagem de cada fileira a partir do piso.")
    moldura(1, "PAINEL 2D DE MONTAGEM – VISTAS FRONTAL E TRASEIRA (sem portas)")
    c.showPage()
    # folha 2: lateral + topo
    esc2 = min((W_ - ox1 - 100 * mm) / (D + W), (H_ - 80 * mm) / max(H, D + 200))
    desenhar_vista(c, m, "lateral", ox1, oy, esc2, mm)
    c.setFont("Helvetica-Bold", 9); c.drawString(ox1, oy + H * esc2 + 8 * mm, VISTAS2D["lateral"]["titulo"])
    _cota(c, ox1, oy, ox1 + D * esc2, oy, f"{D:.0f}", -8 * mm, mm)
    _cota(c, ox1 + D * esc2, oy, ox1 + D * esc2, oy + H * esc2, f"{H:.0f}", 8 * mm, mm, vertical=True)
    ox3 = ox1 + D * esc2 + 60 * mm
    desenhar_vista(c, m, "topo", ox3, oy + 40 * mm, esc2, mm)
    c.setFont("Helvetica-Bold", 9); c.drawString(ox3, oy + 40 * mm + D * esc2 + 8 * mm, VISTAS2D["topo"]["titulo"])
    _cota(c, ox3, oy + 40 * mm, ox3 + W * esc2, oy + 40 * mm, f"{W:.0f}", -8 * mm, mm)
    _cota(c, ox3 + W * esc2, oy + 40 * mm, ox3 + W * esc2, oy + 40 * mm + D * esc2, f"{D:.0f}", 8 * mm, mm, vertical=True)
    moldura(2, "PAINEL 2D DE MONTAGEM – VISTA LATERAL (CORTE) E TOPO")
    c.save()
    dxf = None
    try:                                                                 # DXF 1:1 em mm, uma vista ao lado da outra, camadas
        import ezdxf
        doc = ezdxf.new("R2010")
        ms = doc.modelspace()
        for nome in ("ESTRUTURA", "PLACA", "COMPONENTES", "CABOS", "COTAS"):
            doc.layers.add(nome)
        x_off = 0
        for vista in ("frontal", "traseira", "lateral", "topo"):
            v = VISTAS2D[vista]
            bx, tubos = _caixas(m, v["grupos"])
            for b in bx:
                u0, u1, w0, w1 = _proj(b, v["eixo"])
                if v.get("espelho"):
                    u0, u1 = W - u1, W - u0
                lay = "ESTRUTURA" if b[6] in ("estrutura", "base", "teto") else ("PLACA" if b[6] == "placa" else "COMPONENTES")
                ms.add_lwpolyline([(x_off + u0, w0), (x_off + u1, w0), (x_off + u1, w1), (x_off + u0, w1)], close=True,
                                  dxfattribs={"layer": lay})
            for pts, g, cor, Dd in tubos:
                k0, k1 = _IDX[v["eixo"][0]][0] // 2, _IDX[v["eixo"][1]][0] // 2
                ms.add_lwpolyline([(x_off + ((W - q[k0]) if v.get("espelho") else q[k0]), q[k1]) for q in pts], dxfattribs={"layer": "CABOS"})
            ms.add_text(v["titulo"], dxfattribs={"layer": "COTAS", "height": 40}).set_placement((x_off, (H if vista != "topo" else D) + 80))
            x_off += (W if vista in ("frontal", "traseira", "topo") else D) + 600
        dxf = os.path.join(pasta, f"Painel_2D_Montagem_{cod}.dxf")
        doc.saveas(dxf)
    except Exception as ex:
        log(f"   (DXF do 2D não gerado: {type(ex).__name__}: {ex})")
    log(f"   Painel 2D de montagem: {arq}")
    return dict(pdf=arq, dxf=dxf)
