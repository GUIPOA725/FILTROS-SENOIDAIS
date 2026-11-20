"""Arquivos CAD editáveis do indutor (v1.10.4):
- STEP AP214 (3D): sólidos B-rep verdadeiros (MANIFOLD_SOLID_BREP com faces planas), um sólido por peça, com nome e cor –
  abre e edita no FreeCAD, SolidWorks, Inventor, Fusion 360, Solid Edge, Creo. Escritor próprio, sem dependências.
- DXF (2D): vistas frontal, lateral, superior, planta do núcleo e cortes, em escala 1:1 (mm), com camadas e cotas associativas
  (ezdxf) – abre no AutoCAD, LibreCAD, DraftSight, QCAD, BricsCAD.
"""
import math
import datetime as _dt

from .ind_desenhos import geo_mm, fabricacao, _rret_pts


# ---------------------------------------------------------------------------------------------------------------------
# Sólidos poliédricos: lista de faces planas; cada face = (contorno_externo, [furos]) com vértices em sentido anti-horário
# visto de FORA (normal para fora).
def caixa(x0, y0, z0, dx, dy, dz):
    X, Y, Z = (x0, x0 + dx), (y0, y0 + dy), (z0, z0 + dz)
    v = lambda i, j, k: (X[i], Y[j], Z[k])
    return [([v(0, 0, 0), v(0, 1, 0), v(1, 1, 0), v(1, 0, 0)], []),      # z-
            ([v(0, 0, 1), v(1, 0, 1), v(1, 1, 1), v(0, 1, 1)], []),      # z+
            ([v(0, 0, 0), v(1, 0, 0), v(1, 0, 1), v(0, 0, 1)], []),      # y-
            ([v(0, 1, 0), v(0, 1, 1), v(1, 1, 1), v(1, 1, 0)], []),      # y+
            ([v(0, 0, 0), v(0, 0, 1), v(0, 1, 1), v(0, 1, 0)], []),      # x-
            ([v(1, 0, 0), v(1, 1, 0), v(1, 1, 1), v(1, 0, 1)], [])]      # x+


def tubo_arred(cx, cy, w_ext, h_ext, r_ext, w_int, h_int, r_int, z0, z1, n=6):
    """Bobina: prisma de retângulo arredondado oco (eixo z)."""
    pe = _rret_pts(cx, cy, w_ext, h_ext, r_ext, n)[:-1]
    pi = _rret_pts(cx, cy, w_int, h_int, r_int, n)[:-1]
    fs = []
    for p in (pe,):
        for i in range(len(p)):
            a, b = p[i], p[(i + 1) % len(p)]
            fs.append(([(a[0], a[1], z0), (b[0], b[1], z0), (b[0], b[1], z1), (a[0], a[1], z1)], []))
    for i in range(len(pi)):                                       # parede interna: normal para dentro do furo
        a, b = pi[i], pi[(i + 1) % len(pi)]
        fs.append(([(b[0], b[1], z0), (a[0], a[1], z0), (a[0], a[1], z1), (b[0], b[1], z1)], []))
    topo_ext = [(x, y, z1) for x, y in pe]
    topo_int = [(x, y, z1) for x, y in reversed(pi)]
    fs.append((topo_ext, [topo_int]))
    base_ext = [(x, y, z0) for x, y in reversed(pe)]
    base_int = [(x, y, z0) for x, y in pi]
    fs.append((base_ext, [base_int]))
    return fs


# ---------------------------------------------------------------------------------------------------------------------
class EscritorSTEP:
    def __init__(self):
        self.lin = []
        self.n = 0

    def e(self, txt):
        self.n += 1
        self.lin.append(f"#{self.n}={txt};")
        return f"#{self.n}"

    @staticmethod
    def f(x):
        s = f"{x:.6f}".rstrip("0")
        return s + "0" if s.endswith(".") else s

    def ponto(self, p):
        return self.e(f"CARTESIAN_POINT('',({self.f(p[0])},{self.f(p[1])},{self.f(p[2])}))")

    def direcao(self, d):
        return self.e(f"DIRECTION('',({self.f(d[0])},{self.f(d[1])},{self.f(d[2])}))")

    def solido(self, nome, faces):
        """Cria MANIFOLD_SOLID_BREP a partir de faces planas (arestas compartilhadas por chave de vértices)."""
        vert, arest = {}, {}

        def k(p):
            return (round(p[0], 4), round(p[1], 4), round(p[2], 4))

        def vtx(p):
            kk = k(p)
            if kk not in vert:
                vert[kk] = self.e(f"VERTEX_POINT('',{self.ponto(p)})")
            return vert[kk]

        def aresta(p, q):
            kp, kq = k(p), k(q)
            chave = (kp, kq) if kp < kq else (kq, kp)
            if chave not in arest:
                a, b = (p, q) if kp < kq else (q, p)
                d = [b[i] - a[i] for i in range(3)]
                L = math.sqrt(sum(x * x for x in d)) or 1.0
                vec = self.e(f"VECTOR('',{self.direcao([x / L for x in d])},{self.f(L)})")
                ln = self.e(f"LINE('',{self.ponto(a)},{vec})")
                arest[chave] = (self.e(f"EDGE_CURVE('',{vtx(a)},{vtx(b)},{ln},.T.)"), kp < kq)
            ec, mesmo = arest[chave]
            return f"ORIENTED_EDGE('',*,*,{ec},{'.T.' if (kp < kq) else '.F.'})"

        def laco(pts):
            oes = [self.e(aresta(pts[i], pts[(i + 1) % len(pts)])) for i in range(len(pts))]
            return self.e(f"EDGE_LOOP('',({','.join(oes)}))")

        ids = []
        for ext, furos in faces:
            p0, p1, p2 = ext[0], ext[1], ext[2]
            # normal pelo método de Newell (robusto a pontos colineares)
            nx = ny = nz = 0.0
            for i in range(len(ext)):
                a, b = ext[i], ext[(i + 1) % len(ext)]
                nx += (a[1] - b[1]) * (a[2] + b[2])
                ny += (a[2] - b[2]) * (a[0] + b[0])
                nz += (a[0] - b[0]) * (a[1] + b[1])
            L = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
            nrm = (nx / L, ny / L, nz / L)
            ref = (1, 0, 0) if abs(nrm[0]) < 0.9 else (0, 1, 0)
            # eixo X do plano ortogonal à normal
            dot = sum(ref[i] * nrm[i] for i in range(3))
            xd = [ref[i] - dot * nrm[i] for i in range(3)]
            lx = math.sqrt(sum(x * x for x in xd))
            xd = [x / lx for x in xd]
            ax = self.e(f"AXIS2_PLACEMENT_3D('',{self.ponto(p0)},{self.direcao(nrm)},{self.direcao(xd)})")
            pl = self.e(f"PLANE('',{ax})")
            bounds = [self.e(f"FACE_OUTER_BOUND('',{laco(ext)},.T.)")]
            for h in furos:
                bounds.append(self.e(f"FACE_BOUND('',{laco(h)},.T.)"))
            ids.append(self.e(f"ADVANCED_FACE('',({','.join(bounds)}),{pl},.T.)"))
        sh = self.e(f"CLOSED_SHELL('',({','.join(ids)}))")
        return self.e(f"MANIFOLD_SOLID_BREP('{nome}',{sh})")

    def cor(self, item, rgb):
        c = self.e(f"COLOUR_RGB('',{self.f(rgb[0])},{self.f(rgb[1])},{self.f(rgb[2])})")
        fsc = self.e(f"FILL_AREA_STYLE_COLOUR('',{c})")
        fa = self.e(f"FILL_AREA_STYLE('',({fsc}))")
        ssfa = self.e(f"SURFACE_STYLE_FILL_AREA({fa})")
        sss = self.e(f"SURFACE_SIDE_STYLE('',({ssfa}))")
        su = self.e(f"SURFACE_STYLE_USAGE(.BOTH.,{sss})")
        psa = self.e(f"PRESENTATION_STYLE_ASSIGNMENT(({su}))")
        return self.e(f"STYLED_ITEM('color',({psa}),{item})")

    def gravar(self, arq, nome_prod, solidos_cores):
        # contexto e produto
        app = self.e("APPLICATION_CONTEXT('automotive design')")
        self.e(f"APPLICATION_PROTOCOL_DEFINITION('international standard','automotive_design',2000,{app})")
        pc = self.e(f"PRODUCT_CONTEXT('',{app},'mechanical')")
        prod = self.e(f"PRODUCT('{nome_prod}','{nome_prod}','',({pc}))")
        pdfw = self.e(f"PRODUCT_DEFINITION_FORMATION('','',{prod})")
        pdc = self.e(f"PRODUCT_DEFINITION_CONTEXT('part definition',{app},'design')")
        pd = self.e(f"PRODUCT_DEFINITION('design','',{pdfw},{pdc})")
        pds = self.e(f"PRODUCT_DEFINITION_SHAPE('','',{pd})")
        lu = self.e("(LENGTH_UNIT()NAMED_UNIT(*)SI_UNIT(.MILLI.,.METRE.))")
        au = self.e("(NAMED_UNIT(*)PLANE_ANGLE_UNIT()SI_UNIT($,.RADIAN.))")
        su = self.e("(NAMED_UNIT(*)SI_UNIT($,.STERADIAN.)SOLID_ANGLE_UNIT())")
        unc = self.e(f"UNCERTAINTY_MEASURE_WITH_UNIT(LENGTH_MEASURE(1.E-05),{lu},'distance_accuracy_value','')")
        ctx = self.e(f"(GEOMETRIC_REPRESENTATION_CONTEXT(3)GLOBAL_UNCERTAINTY_ASSIGNED_CONTEXT(({unc}))"
                     f"GLOBAL_UNIT_ASSIGNED_CONTEXT(({lu},{au},{su}))REPRESENTATION_CONTEXT('',''))")
        orig = self.e(f"AXIS2_PLACEMENT_3D('',{self.ponto((0, 0, 0))},{self.direcao((0, 0, 1))},{self.direcao((1, 0, 0))})")
        itens = [s for s, _ in solidos_cores]
        rep = self.e(f"ADVANCED_BREP_SHAPE_REPRESENTATION('',({','.join([orig] + itens)}),{ctx})")
        self.e(f"SHAPE_DEFINITION_REPRESENTATION({pds},{rep})")
        estilos = [self.cor(s, c) for s, c in solidos_cores]
        self.e(f"MECHANICAL_DESIGN_GEOMETRIC_PRESENTATION_REPRESENTATION('',({','.join(estilos)}),{ctx})")
        agora = _dt.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        cab = ["ISO-10303-21;", "HEADER;",
               "FILE_DESCRIPTION(('Indutor trifasico p/ filtro senoidal - projeto de referencia Plataforma FSEN'),'2;1');",
               f"FILE_NAME('{nome_prod}.step','{agora}',('Electric Service'),('Electric Service'),'FSEN','FSEN ind_cad','');",
               "FILE_SCHEMA(('AUTOMOTIVE_DESIGN { 1 0 10303 214 1 1 1 1 }'));", "ENDSEC;", "DATA;"]
        with open(arq, "w", encoding="ascii", errors="replace") as fh:
            fh.write("\n".join(cab + self.lin + ["ENDSEC;", "END-ISO-10303-21;"]) + "\n")
        return arq


# ---------------------------------------------------------------------------------------------------------------------
def pecas_3d(d):
    """Lista (nome, faces, cor RGB 0–1). Coordenadas: x ao longo do núcleo, y profundidade, z vertical (mm)."""
    g = geo_mm(d)
    fab = fabricacao(d)
    a, b, W, H, hw, ww = g["a"], g["b"], g["W"], g["H"], g["hw"], g["ww"]
    FE, BO, ACO, CU, GAP, ISO = (0.67, 0.71, 0.75), (0.85, 0.56, 0.18), (0.42, 0.42, 0.42), (0.77, 0.48, 0.24), (0.84, 0.15, 0.16), (0.24, 0.60, 0.36)
    P = []
    P.append(("Culatra inferior", caixa(0, -b / 2, 0, W, b, a), FE))
    P.append(("Culatra superior", caixa(0, -b / 2, H - a, W, b, a), FE))
    for i in range(3):
        x0 = i * g["pitch"]
        gc = fab["gl"] if i != 1 else fab["gc"]
        pac = fab["pac_l"] if i != 1 else fab["pac_c"]
        z = a
        for k, ph in enumerate(pac):
            if ph > 0.05:
                P.append((f"Coluna {'UVW'[i]} pacote {k + 1}", caixa(x0, -b / 2, z, a, b, ph), FE))
            z += ph
            if k < len(pac) - 1:
                P.append((f"Calco entreferro {'UVW'[i]}{k + 1}", caixa(x0, -b / 2, z, a, b, gc), GAP))
                z += gc
        xc = g["xc"][i]
        # tubo isolante e bobina
        ri = g["c"]
        P.append((f"Tubo isolante {'UVW'[i]}", tubo_arred(xc, 0, a + 2 * (ri + g["tube"]), b + 2 * (ri + g["tube"]), ri + g["tube"],
                                                          a + 2 * ri, b + 2 * ri, max(ri, 1), g["yc0"] - 6, g["yc0"] + g["hc"] + 6), ISO))
        rb0 = ri + g["tube"]
        rb1 = g["c"] + g["build"]
        P.append((f"Bobina {'UVW'[i]}", tubo_arred(xc, 0, a + 2 * rb1, b + 2 * rb1, rb1, a + 2 * rb0, b + 2 * rb0, rb0,
                                                   g["yc0"], g["yc0"] + g["hc"]), BO))
        for s, lab in ((-1, "1"), (1, "2")):
            xt = xc + s * g["Dc"] * 0.28
            z0 = g["yc0"] + g["hc"]
            P.append((f"Terminal {'UVW'[i]}{lab}", caixa(xt - 20, -b / 2 - g["c"] - 6, z0, 40, 6, H + g["fr"] + g["term_h"] - z0), CU))
    xr0, xr1 = g["xr"]
    for zz, nome in ((-g["fr"], "inferior"), (H, "superior")):
        for yy, lado in ((-b / 2 - g["fe"], "frente"), (b / 2, "tras")):
            P.append((f"Cantoneira {nome} {lado}", caixa(xr0 - 18, yy, zz, xr1 - xr0 + 36, g["fe"], g["fr"]), ACO))
            yab = yy - 44 if lado == "frente" else yy + g["fe"]
            P.append((f"Cantoneira {nome} {lado} aba", caixa(xr0 - 18, yab, zz if nome == "inferior" else zz + g["fr"] - g["fe"],
                                                              xr1 - xr0 + 36, 44, g["fe"]), ACO))
    for x in (xr0, xr1):
        for yy in (-b / 2 - 25, b / 2 + 25):
            P.append(("Tirante M12", caixa(x - 6, yy - 6, -g["fr"] - 12, 12, 12, H + 2 * g["fr"] + 24), (0.8, 0.8, 0.8)))
    yb = -g["fr"] - g["base_h"]
    xb0 = xr0 - 40
    for s in (-1, 1):
        y0 = -g["Bb"] / 2 if s < 0 else g["Bb"] / 2 - 50
        P.append((f"Base perfil U {'frente' if s < 0 else 'tras'}", caixa(xb0, y0, yb, g["Lb"], 50, g["base_h"]), (0.55, 0.55, 0.55)))
    P.append(("Caixa de bornes PTC", caixa(xr1 - 70, -b / 2 - g["fe"] - 30, H + g["fr"], 50, 30, 28), (0.9, 0.9, 0.9)))
    return P


def gerar_step(d, arq, nome="INDUTOR_FSEN"):
    st = EscritorSTEP()
    sc = []
    for nm, faces, cor in pecas_3d(d):
        nm_ascii = nm.encode("ascii", "replace").decode()
        sc.append((st.solido(nm_ascii, faces), cor))
    return st.gravar(arq, nome, sc)


# ---------------------------------------------------------------------------------------------------------------------
def gerar_dxf(d, arq, info=None):
    import ezdxf
    from ezdxf.enums import TextEntityAlignment
    g = geo_mm(d)
    fab = fabricacao(d)
    doc = ezdxf.new("R2010", setup=True)
    doc.units = ezdxf.units.MM
    camadas = {"NUCLEO": 8, "BOBINA": 30, "ESTRUTURA": 252, "TERMINAIS": 32, "CALCOS": 1, "COTAS": 5, "EIXOS": 1, "TEXTO": 7,
               "ISOLACAO": 3}
    for n, c in camadas.items():
        doc.layers.add(n, color=c)
    doc.layers.get("EIXOS").dxf.linetype = "CENTER"
    msp = doc.modelspace()
    ds = doc.dimstyles.get("EZDXF")
    ds.dxf.dimtxt = 5
    ds.dxf.dimasz = 4
    ds.dxf.dimlfac = 1.0          # estilo EZDXF vem para cm (×100) – aqui mm 1:1
    ds.dxf.dimdec = 1
    ds.dxf.dimzin = 8

    def ret(x, y, w, h, layer, ox=0, oy=0):
        msp.add_lwpolyline([(ox + x, oy + y), (ox + x + w, oy + y), (ox + x + w, oy + y + h), (ox + x, oy + y + h)], close=True,
                           dxfattribs={"layer": layer})

    def rret(cx, cy, w, h, r, layer, ox=0, oy=0):
        pts = _rret_pts(cx, cy, w, h, r, 8)
        msp.add_lwpolyline([(ox + x, oy + y) for x, y in pts], close=True, dxfattribs={"layer": layer})

    def cota(p1, p2, base, ang=0):
        dim = msp.add_linear_dim(base=base, p1=p1, p2=p2, angle=ang, dimstyle="EZDXF", dxfattribs={"layer": "COTAS"})
        dim.render()

    def txt(x, y, t, h=6):
        msp.add_text(t, height=h, dxfattribs={"layer": "TEXTO"}).set_placement((x, y))

    a, b, W, H, hw, ww = g["a"], g["b"], g["W"], g["H"], g["hw"], g["ww"]
    xr0, xr1 = g["xr"]
    yb = -g["fr"] - g["base_h"]
    ytop = H + g["fr"] + g["term_h"]
    # ---- VISTA FRONTAL (origem 0,0) ----
    ret(xr0 - 40, yb, g["Lb"], g["base_h"], "ESTRUTURA")
    ret(xr0 - 18, -g["fr"], xr1 - xr0 + 36, g["fr"], "ESTRUTURA")
    ret(xr0 - 18, H, xr1 - xr0 + 36, g["fr"], "ESTRUTURA")
    ret(0, 0, W, H, "NUCLEO")
    for i in range(2):
        ret(a + i * g["pitch"], a, ww, hw, "NUCLEO")
    for i, xc in enumerate(g["xc"]):
        ret(xc - g["Dc"] / 2, g["yc0"], g["Dc"], g["hc"], "BOBINA")
        msp.add_line((xc, yb - 10), (xc, ytop + 10), dxfattribs={"layer": "EIXOS"})
        for s, lab in ((-1, "1"), (1, "2")):
            xt = xc + s * g["Dc"] * 0.28
            ret(xt - 20, g["yc0"] + g["hc"], 40, ytop - g["yc0"] - g["hc"], "TERMINAIS")
            msp.add_circle((xt, ytop - 14), 6.5, dxfattribs={"layer": "TERMINAIS"})
            txt(xt - 6, ytop + 6, "UVW"[i] + lab)
    for x in (xr0, xr1):
        ret(x - 6, -g["fr"] - 12, 12, H + 2 * g["fr"] + 24, "ESTRUTURA")
    cota((xr0 - 40, yb), (xr0 - 40 + g["Lb"], yb), (0, yb - 40))
    cota((0, yb), (W, yb), (0, yb - 70))
    xs = [0, a, a + ww, 2 * a + ww, 2 * a + 2 * ww, W]
    for p, q in zip(xs[:-1], xs[1:]):
        cota((p, 0), (q, 0), (0, yb - 100))
    cota((g["xc"][0], ytop), (g["xc"][1], ytop), (0, ytop + 30))
    cota((g["xc"][1], ytop), (g["xc"][2], ytop), (0, ytop + 30))
    cota((xr1 + 60, yb), (xr1 + 60, ytop), (xr1 + 120, 0), ang=90)
    cota((W, 0), (W, H), (xr1 + 90, 0), ang=90)
    txt(0, ytop + 70, "VISTA FRONTAL (1:1, mm)", 10)
    # ---- VISTA LATERAL (deslocada em x) ----
    ox = xr1 + 400
    ret(-g["Bb"] / 2, yb, g["Bb"], g["base_h"], "ESTRUTURA", ox)
    ret(-b / 2, 0, b, H, "NUCLEO", ox)
    ret(-g["Ec"] / 2, g["yc0"], g["Ec"], g["hc"], "BOBINA", ox)
    for s in (-1, 1):
        x0 = b / 2 if s > 0 else -b / 2 - g["fe"]
        ret(x0, -g["fr"], g["fe"], g["fr"], "ESTRUTURA", ox)
        ret(x0, H, g["fe"], g["fr"], "ESTRUTURA", ox)
    cota((ox - g["Bb"] / 2, yb), (ox + g["Bb"] / 2, yb), (ox, yb - 40))
    cota((ox - g["Ec"] / 2, yb), (ox + g["Ec"] / 2, yb), (ox, yb - 70))
    txt(ox - g["Bb"] / 2, ytop + 70, "VISTA LATERAL ESQUERDA", 10)
    # ---- VISTA SUPERIOR (abaixo) ----
    oy = yb - 250 - g["Bb"] / 2
    ret(xr0 - 40, -g["Bb"] / 2, g["Lb"], g["Bb"], "ESTRUTURA", 0, oy)
    ret(0, -b / 2, W, b, "NUCLEO", 0, oy)
    for xc in g["xc"]:
        rret(xc, 0, g["Dc"], g["Ec"], g["rc"], "BOBINA", 0, oy)
        ret(xc - a / 2, -b / 2, a, b, "NUCLEO", 0, oy)
    xf0, xf1 = xr0 - 15, xr1 + 15
    for x in (xf0, xf1):
        for y in (-g["Bb"] / 2 + 20, g["Bb"] / 2 - 20):
            rret(x, y, 25, 14, 7, "ESTRUTURA", 0, oy)
    cota((xf0, oy), (xf1, oy), (0, oy - g["Bb"] / 2 - 40))
    txt(0, oy + g["Bb"] / 2 + 20, "VISTA SUPERIOR / FURACAO DA BASE (4x oblongo 14x25)", 10)
    # ---- PLANTA DO NÚCLEO com calços ----
    ox2, oy2 = xr1 + 400 + g["Bb"] + 300, 0
    ret(0, 0, W, H, "NUCLEO", ox2, oy2)
    for i in range(2):
        ret(a + i * g["pitch"], a, ww, hw, "NUCLEO", ox2, oy2)
    for i in range(3):
        x0 = i * g["pitch"]
        gc = fab["gl"] if i != 1 else fab["gc"]
        pac = fab["pac_l"] if i != 1 else fab["pac_c"]
        z = a
        for k, ph in enumerate(pac[:-1]):
            z += ph
            ret(x0, z, a, gc, "CALCOS", ox2, oy2)
            z += gc
    for xx in (0, W):
        s = 1 if xx == 0 else -1
        msp.add_line((ox2 + xx, 0), (ox2 + xx + s * a, a), dxfattribs={"layer": "NUCLEO"})
        msp.add_line((ox2 + xx, H), (ox2 + xx + s * a, H - a), dxfattribs={"layer": "NUCLEO"})
    z = a
    for k, ph in enumerate(fab["pac_l"]):
        if ph > 0.05:
            cota((ox2, z), (ox2, z + ph), (ox2 - 30, 0), ang=90)
        z += ph + (fab["gl"] if k < len(fab["pac_l"]) - 1 else 0)
    cota((ox2, 0), (ox2 + W, 0), (ox2, -40))
    cota((ox2 + W, 0), (ox2 + W, H), (ox2 + W + 40, 0), ang=90)
    txt(ox2, H + 40, f"NUCLEO – calcos EP GC 203: laterais {fab['gl']:.2f} mm, central {fab['gc']:.2f} mm, {d['ng']} por coluna", 8)
    # ---- CORTE A-A (bobina) ----
    ox3, oy3 = ox2, oy - 50
    ret(-a / 2, -b / 2, a, b, "NUCLEO", ox3, oy3)
    r = g["c"]
    rret(0, 0, a + 2 * r, b + 2 * r, r, "ISOLACAO", ox3, oy3)
    r += g["tube"]
    rret(0, 0, a + 2 * r, b + 2 * r, r, "ISOLACAO", ox3, oy3)
    canais = sorted(set(round((k + 1) * g["N"] / (g["nd"] + 1)) for k in range(g["nd"])))
    r += 0.26
    for k in range(g["N"]):
        if k in canais:
            r += g["wd"]
        r += g["tf"]
        rret(0, 0, a + 2 * r, b + 2 * r, r, "BOBINA", ox3, oy3)
        r += 0.26 + (0.13 if k in (0, 1, g["N"] - 2, g["N"] - 1) else 0)
    r += g["wrap"]
    rret(0, 0, a + 2 * r, b + 2 * r, r, "BOBINA", ox3, oy3)
    cota((ox3 - a / 2 - r, oy3), (ox3 + a / 2 + r, oy3), (ox3, oy3 + b / 2 + r + 30))
    _cd = (f"fio {d['fio']['t']*1e3:.2f} x {d['fio']['h']*1e3:.1f} mm x{d['fio']['np']} ({d['fio']['n_cam']} cam.)" if d.get("fio")
           else f"folha {g['tf']:.1f} x {g['hf']:.0f} mm")
    txt(ox3 - a / 2 - r, oy3 - b / 2 - r - 30, f"CORTE A-A – {g['N']} espiras {_cd}, tubo {g['tube']:.0f} mm, c = {g['c']:.0f} mm", 7)
    # carimbo simples
    i = info or {}
    txt(0, oy - g["Bb"] / 2 - 120, f"ELECTRIC SERVICE – {i.get('titulo', 'Indutor')} – {i.get('versao', '')} – {i.get('data', '')}", 9)
    txt(0, oy - g["Bb"] / 2 - 140, "Projeto de referencia (mm, escala 1:1). Camadas: NUCLEO, BOBINA, ISOLACAO, CALCOS, ESTRUTURA, TERMINAIS, COTAS, EIXOS.", 7)
    doc.saveas(arq)
    return arq
