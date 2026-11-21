"""Vista REALISTA do indutor (v1.11.4): render 3D com materiais (aço-silício laminado, cobre, papel aramida, vidro-epóxi,
resina VPI, estrutura pintada), uma bobina em corte mostrando a construção interna, e chamadas numeradas.

Usa pyvista/VTK (render fora da tela). Se não estiver instalado, a plataforma segue sem esta vista (as outras folhas não
dependem dela). Unidades em mm (geo_mm do projeto do indutor).
"""
import math
import numpy as np

COR = dict(
    aco=(0.56, 0.58, 0.62), aco2=(0.47, 0.49, 0.53), cobre=(0.80, 0.45, 0.22), aluminio=(0.78, 0.79, 0.80),
    aramida=(0.93, 0.85, 0.60), vidro_epoxi=(0.42, 0.62, 0.40), calco=(0.70, 0.22, 0.16), espacador=(0.84, 0.74, 0.48),
    resina=(0.86, 0.78, 0.58), estrutura=(0.74, 0.76, 0.78), zinco=(0.76, 0.77, 0.80), estanho=(0.86, 0.86, 0.82),
    base=(0.30, 0.34, 0.40), cabo=(0.92, 0.92, 0.92), fita=(0.95, 0.93, 0.85),
    cobre_bar=(0.80, 0.45, 0.22), placa=(0.93, 0.93, 0.95), ptc=(0.88, 0.88, 0.88), furo=(0.12, 0.12, 0.14),
    tracador=(0.78, 0.12, 0.10))


def disponivel():
    try:
        import pyvista  # noqa: F401
        return True
    except Exception:
        return False


def _loop(cx, cy, w, h, r, n_arc=10):
    """Contorno de retângulo arredondado (anti-horário), começando no meio do lado +x. Devolve (pts Nx2, parâmetro s 0..1)."""
    r = max(min(r, w / 2 - 1e-3, h / 2 - 1e-3), 0.0)
    pts = []
    cantos = [(cx + w / 2 - r, cy + h / 2 - r, 0), (cx - w / 2 + r, cy + h / 2 - r, 90),
              (cx - w / 2 + r, cy - h / 2 + r, 180), (cx + w / 2 - r, cy - h / 2 + r, 270)]
    pts.append((cx + w / 2, cy))
    for (qx, qy, a0) in cantos:
        for k in range(n_arc + 1):
            t = math.radians(a0 + 90 * k / n_arc)
            pts.append((qx + r * math.cos(t), qy + r * math.sin(t)))
    pts.append((cx + w / 2, cy - 1e-6))
    P = np.array(pts)
    seg = np.hypot(*np.diff(P, axis=0).T)
    s = np.concatenate([[0], np.cumsum(seg)])
    return P, s / s[-1]


def _anel(pv, cx, cy, w_in, h_in, r_in, esp, z0, z1, corte=None):
    """Sólido em anel (bobina/camada) com contorno de retângulo arredondado. corte=(s0, s1): trecho removido (0..1)."""
    Pi, si = _loop(cx, cy, w_in, h_in, r_in)
    Po, _ = _loop(cx, cy, w_in + 2 * esp, h_in + 2 * esp, r_in + esp)
    n = len(Pi)
    keep = np.ones(n - 1, dtype=bool)
    if corte:
        sm = (si[:-1] + si[1:]) / 2
        keep = ~((sm > corte[0]) & (sm < corte[1]))
    verts, faces = [], []

    def v(p):
        verts.append(p)
        return len(verts) - 1
    for k in range(n - 1):
        if not keep[k]:
            continue
        a, b = k, k + 1
        ib0, ib1 = v((*Pi[a], z0)), v((*Pi[b], z0))
        ob0, ob1 = v((*Po[a], z0)), v((*Po[b], z0))
        it0, it1 = v((*Pi[a], z1)), v((*Pi[b], z1))
        ot0, ot1 = v((*Po[a], z1)), v((*Po[b], z1))
        faces += [[4, ob0, ob1, ot1, ot0], [4, ib1, ib0, it0, it1], [4, it0, ot0, ot1, it1], [4, ib0, ib1, ob1, ob0]]
        if corte is not None:                       # tampas nas faces do corte
            if k + 1 < n - 1 and not keep[k + 1]:
                faces.append([4, ib1, ob1, ot1, it1])
            if k - 1 >= 0 and not keep[k - 1]:
                faces.append([4, ib0, it0, ot0, ob0])
    if not faces:
        return None
    return pv.PolyData(np.array(verts, dtype=float), np.hstack(faces))


def _caixa(pv, x0, x1, y0, y1, z0, z1):
    return pv.Box(bounds=(min(x0, x1), max(x0, x1), min(y0, y1), max(y0, y1), min(z0, z1), max(z0, z1)))


def montar(d, g, fab):
    """Monta a cena: devolve lista de (malha, material, rótulo) e pontos de chamada {nº: (x,y,z)}."""
    import pyvista as pv
    a, b, hw, H, W = g["a"], g["b"], g["hw"], g["H"], g["W"]
    pecas, ancora = [], {}
    fio = g.get("fio")
    culatra = d.get("pos_gap") == "culatra"
    ng = g["ng"]
    gl, gc = fab["gl"], fab["gc"]
    # ---------------- núcleo: pacotes de lâminas (faixas alternadas para mostrar o empilhamento) ----------------
    n_faixa = 14

    def laminado(x0, x1, z0, z1, tag):
        for k in range(n_faixa):
            y0 = -b / 2 + b * k / n_faixa
            y1 = -b / 2 + b * (k + 1) / n_faixa - b * 0.004
            pecas.append((_caixa(pv, x0, x1, y0, y1, z0, z1), "aco" if k % 2 == 0 else "aco2", tag))
    laminado(0, W, 0, a, "culatra")
    laminado(0, W, a + hw, H, "culatra")
    for i, xc in enumerate(g["xc"]):
        gi = gl if i != 1 else gc
        if culatra:
            z_ini, z_fim = a + gi, a + hw - gi
            laminado(xc - a / 2, xc + a / 2, z_ini, z_fim, "coluna")
            for zz in (a, a + hw - gi):
                pecas.append((_caixa(pv, xc - a / 2, xc + a / 2, -b / 2, b / 2, zz, zz + gi), "calco", "calço"))
        else:
            z = a
            pac = fab["pac_c"] if i == 1 else fab["pac_l"]
            for k, ph in enumerate(pac):
                laminado(xc - a / 2, xc + a / 2, z, z + ph, "coluna")
                z += ph
                if k < len(pac) - 1:
                    pecas.append((_caixa(pv, xc - a / 2, xc + a / 2, -b / 2, b / 2, z, z + gi), "calco", "calço"))
                    z += gi
    # ---------------- bobinas ----------------
    zc0 = g["yc0"]
    hc = g["hc"]
    hf = g["hf"]
    zb0 = zc0 + (hc - hf) / 2
    c = g["c"]
    for i, xc in enumerate(g["xc"]):
        corte = (0.56, 0.93) if i == 0 else None            # bobina U em corte (lado esquerdo + frente)
        w0, h0 = a + 2 * c, b + 2 * c
        r = c
        # tubo de vidro-epóxi
        m = _anel(pv, xc, 0, w0, h0, r, g["tube"], zc0 - 6, zc0 + hc + 6, corte)
        pecas.append((m, "vidro_epoxi", "tubo"))
        rr = c + g["tube"] + 0.26
        if fio and corte:
            # corte do enrolamento: bloco de papel aramida (fundo, recuado) + cada fio de cobre saliente no plano do corte
            esp_cam = fio["np"] * (fio["t"] + fio["iso"])
            r_ini = rr
            r_fim = rr + fio["n_cam"] * (esp_cam + fio["t_cam"])
            fundo = (corte[0] - 0.012, corte[1] + 0.012)
            blk = _anel(pv, xc, 0, a + 2 * r_ini, b + 2 * r_ini, r_ini, r_fim - r_ini, zb0 - 3, zb0 + hf + 3, fundo)
            pecas.append((blk, "aramida", "papel"))
            for j in range(fio["n_cam"]):
                for p in range(fio["np"]):
                    r_f = rr + p * (fio["t"] + fio["iso"]) + fio["iso"] / 2
                    for k in range(fio["n_ax"]):
                        z0 = zb0 + k * (fio["h"] + fio["iso"]) + fio["iso"] / 2
                        cu = _anel(pv, xc, 0, a + 2 * r_f, b + 2 * r_f, r_f, fio["t"], z0, z0 + fio["h"], corte)
                        pecas.append((cu, "cobre" if d.get("cond") == "CU" else "aluminio", "condutor"))
                rr += esp_cam + fio["t_cam"]
        elif corte:
            for k in range(g["N"]):
                fol = _anel(pv, xc, 0, a + 2 * rr, b + 2 * rr, rr, g["tf"], zb0, zb0 + hf, corte)
                pecas.append((fol, "aluminio" if d.get("cond") == "AL" else "cobre", "condutor"))
                rr += g["tf"]
                ar = _anel(pv, xc, 0, a + 2 * rr, b + 2 * rr, rr, 0.26, zb0 - 6, zb0 + hf + 6, corte)
                pecas.append((ar, "aramida", "papel"))
                rr += 0.26
        # enfaixamento externo + resina VPI (casca brilhante) – nas bobinas inteiras é o que se vê
        r_ext = c + g["build"] - g["wrap"]
        casca = _anel(pv, xc, 0, a + 2 * r_ext, b + 2 * r_ext, r_ext, g["wrap"], zc0, zc0 + hc, corte)
        pecas.append((casca, "resina", "resina"))
        if not corte:
            corpo = _anel(pv, xc, 0, a + 2 * (c + g["tube"]), b + 2 * (c + g["tube"]), c + g["tube"],
                          g["build"] - g["tube"] - g["wrap"], zc0, zc0 + hc)
            pecas.append((corpo, "resina", "resina"))
        else:
            # faixas de isolação de cabeceira (aramida + vidro-epóxi) acima/abaixo do enrolamento
            for (z0, z1) in ((zc0, zb0), (zb0 + hf, zc0 + hc)):
                m = _anel(pv, xc, 0, a + 2 * (c + g["tube"]), b + 2 * (c + g["tube"]), c + g["tube"],
                          g["build"] - g["tube"] - g["wrap"], z0, z1, corte)
                pecas.append((m, "espacador", "cabeceira"))
        # blocos de extremidade (calços de aperto) entre bobina e culatras
        for zz in (a, a + hw - (zc0 - a)):
            for (dx, dy) in ((0, -(b / 2 + c + g["build"] / 2)), (0, b / 2 + c + g["build"] / 2)):
                pecas.append((_caixa(pv, xc - 14, xc + 14, dy - g["build"] / 2, dy + g["build"] / 2, zz, zz + (zc0 - a)),
                              "espacador", "bloco"))
        if i == 0:
            ancora[2] = (xc - (a / 2 + c + g["build"] / 2) * 0.95, -(b / 2) * 0.55, zb0 + hf * 0.55)     # condutor no corte
            ancora[4] = (xc - (a / 2 + c + g["tube"] / 2) * 0.98, -(b / 2) * 0.30, zc0 + hc * 0.85)       # tubo
            ancora[5] = (xc - (a / 2 + c + g["build"] * 0.55), -(b / 2) * 0.55, zb0 + hf * 0.25)          # isolação/papel
        if i == 1:
            ancora[6] = (xc, -(b / 2 + c + g["build"]), zc0 + hc * 0.45)                                # resina VPI
    # ---------------- estrutura (padrão nacional: quadros U, tirantes nas buchas, saídas horizontais) ----------------
    est = g["est"]
    for nome, mat, (x0, x1, y0, y1, z0, z1) in est["caixas"]:
        pecas.append((_caixa(pv, x0, x1, y0, y1, z0, z1), mat, nome))
    for nome, mat, (xc_, yc_, z0, z1), r, res in est["cilindros"]:
        pecas.append((pv.Cylinder(center=(xc_, yc_, (z0 + z1) / 2), direction=(0, 0, 1), radius=r, height=z1 - z0,
                                  resolution=res), mat, nome))
    for (hx, hy, hz), eixo, r, lab in est["furos"]:
        dirv = dict(x=(1, 0, 0), y=(0, 1, 0), z=(0, 0, 1))[eixo]
        esp = (est["terminais"][0]["tt"] if lab == "Ø13" else est["t"]) + 1.2
        pecas.append((pv.Cylinder(center=(hx, hy, hz), direction=dirv, radius=r, height=esp, resolution=24), "furo", "furo"))
    # fio traçador vermelho do enfaixamento (como nos reatores nacionais)
    r_ext = c + g["build"]
    for i, xc in enumerate(g["xc"]):
        corte = (0.56, 0.93) if i == 0 else None
        z = zc0 + 6
        while z < zc0 + hc - 4:
            m = _anel(pv, xc, 0, a + 2 * r_ext, b + 2 * r_ext, r_ext, 0.35, z, z + 0.9, corte)
            pecas.append((m, "tracador", "fita"))
            z += 9.0
    tr = est["terminais"]
    t_last = tr[-1]
    ch = t_last["chapa"]
    ancora[1] = (g["xc"][0] + a * 0.15, -b / 2 - 0.5, a + hw * 0.62)  # núcleo (coluna U, visível pelo corte)
    ancora[3] = (g["xc"][2], -b / 2 - 0.5, a + gl * 0.5) if culatra else (g["xc"][2], -b / 2, a + fab["pac_l"][0] + gl / 2)
    zq0, zq1 = est["quadros"]["sup"]
    ancora[7] = (W + est["ext"] * 0.6, -est["y_w"] - est["t"], (zq0 + zq1) / 2)          # quadro U
    xr, yr = est["tirantes"][0]
    ancora[8] = (xr, yr, (a + H - a) / 2)                                                   # tirante
    zp0, _ = est["quadros"]["inf"]
    ancora[9] = (-est["ext"] / 2, -(est["y_w"] + est["y_tip"]) / 2, zp0)                    # pé
    ancora[10] = (g["xc"][1], -(b / 2 + c + g["build"] / 2), a + (zc0 - a) * 0.5)          # bloco de extremidade
    ancora[11] = ((ch[0] + ch[1]) / 2, ch[2] + 12, ch[5])                                   # terminal
    ancora[12] = (W / 2 + 40, 0, H + 1)                                                     # placa
    return pecas, ancora


def render(d, png, largura=2400, altura=1700, vista="geral"):
    """Renderiza a vista realista. Devolve dict {nº chamada: (x_px, y_px)} para o desenho das chamadas, ou None."""
    import pyvista as pv
    from .ind_desenhos import geo_mm, fabricacao
    g = geo_mm(d)
    fab = fabricacao(d)
    pecas, ancora = montar(d, g, fab)
    p = pv.Plotter(off_screen=True, window_size=(largura, altura), lighting="none")
    p.set_background("white")
    MAT = dict(aco=dict(specular=0.35, specular_power=20), aco2=dict(specular=0.35, specular_power=20),
               cobre=dict(specular=0.8, specular_power=40), aluminio=dict(specular=0.6, specular_power=30),
               resina=dict(specular=0.9, specular_power=60), estanho=dict(specular=0.7, specular_power=30),
               zinco=dict(specular=0.6, specular_power=30), estrutura=dict(specular=0.55, specular_power=25),
               cobre_bar=dict(specular=0.8, specular_power=40))
    agrup = {}
    for m, mat, _ in pecas:
        if m is None:
            continue
        agrup.setdefault(mat, []).append(m)
    for mat, ms in agrup.items():
        malha = ms[0].merge(ms[1:]) if len(ms) > 1 else ms[0]
        kw = MAT.get(mat, dict(specular=0.15, specular_power=10))
        p.add_mesh(malha, color=COR[mat], smooth_shading=False, ambient=0.25, diffuse=0.75, **kw)
    W, H = g["W"], g["H"]
    p.add_light(pv.Light(position=(-W * 1.5, -W * 2.5, H * 2.5), focal_point=(W / 2, 0, H / 2), intensity=0.85))
    p.add_light(pv.Light(position=(W * 2.5, -W * 1.0, H * 1.2), focal_point=(W / 2, 0, H / 2), intensity=0.45))
    p.add_light(pv.Light(position=(W / 2, W * 2, H * 3), focal_point=(W / 2, 0, H / 2), intensity=0.25))
    try:
        p.enable_ssao(radius=12)
    except Exception:
        pass
    try:
        p.enable_anti_aliasing("ssaa")
    except Exception:
        pass
    if vista == "corte":                                # aproximação da bobina U em corte
        xc = g["xc"][0]
        zc = g["yc0"] + g["hc"] / 2
        xf = xc + g["a"] / 2 + g["c"] + g["build"] * 0.5          # face do corte (lado +x da bobina U, voltada para a frente)
        p.camera_position = [(xf - g["Dc"] * 1.0, -g["Ec"] * 3.0, zc + g["hc"] * 0.75), (xf - g["Dc"] * 0.25, -g["b"] * 0.2, zc), (0, 0, 1)]
        p.camera.view_angle = 30
    else:
        p.camera_position = [(-W * 0.95, -W * 2.6, H * 1.25), (W * 0.48, 0, H * 0.40), (0, 0, 1)]
        e = g["est"]["env"]
        p.reset_camera(bounds=(e[0] - 10, e[1] + 10, e[2] - 10, e[3] + 10, e[4] - 10, e[5] + 10))
        p.camera.zoom(1.15)
    p.render()
    import vtk
    coord = vtk.vtkCoordinate()
    coord.SetCoordinateSystemToWorld()
    px = {}
    for n, pt in ancora.items():
        coord.SetValue(*pt)
        x, y = coord.GetComputedDisplayValue(p.renderer)
        px[n] = (x, altura - y)
    p.screenshot(png)
    p.close()
    return px


ITENS_VISTA = [
    (1, "Núcleo", "chapa de aço-silício GO, lâminas empilhadas, colunas com junta de topo nas culatras"),
    (2, "Enrolamento", "barra retangular de cobre isolada com papel aramida (corte)"),
    (3, "Calço do entreferro", "vidro-epóxi EP GC 203 retificado, colado com epóxi classe H"),
    (4, "Tubo da bobina", "vidro-epóxi EP GC 203, 3 mm – isolação bobina–núcleo"),
    (5, "Isolação espira/camada", "papel aramida (Nomex 410) – classe 220 °C"),
    (6, "Enfaixamento + VPI", "fita de poliéster-vidro com traçador, impregnada com resina classe H (VPI)"),
    (7, "Quadros de aperto em U", "chapa dobrada zincada, frente e trás das culatras, isolados do núcleo (EP GC 203 2 mm)"),
    (8, "Tirantes", "M12 8.8 zincados nas buchas soldadas – vãos entre fases, FORA das bobinas"),
    (9, "Pés de fixação", "aba inferior do quadro de baixo, 4 furos oblongos 14×25"),
    (10, "Blocos de extremidade", "vidro-epóxi/pressboard aramídico – distância bobina–culatra"),
    (11, "Saídas / terminais", "a própria barra da bobina, horizontal p/ frente; barra Cu estanhada 40×6, 2 furos Ø13"),
    (12, "Placa de identificação", "colada na culatra superior (dados, nº de série, massa)"),
]
