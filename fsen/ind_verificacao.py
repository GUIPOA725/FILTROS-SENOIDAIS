"""Verificação independente do cálculo do indutor (v1.11.8).

1) Comparação com OUTRO software de elementos finitos – NGSolve/Netgen (malha e solver próprios, sem código em comum com o
   FEM da plataforma): indutância 2D (mesmo corte), indutância 3D completa (núcleo, entreferros, bobinas reais – confere a
   correção 3D da plataforma) e resistência CA da bobina em 60 Hz / chaveamento (correntes parasitas na barra, campo do entreferro).
2) Casos de resultado conhecido (analíticos) e sensibilidade à malha do FEM da plataforma.
3) Exportação de um script FEMM (.lua) – o engenheiro roda no FEMM (Windows, gratuito) e a plataforma importa o resultado.

Unidades SI internamente (m, A, H, Ω).
"""
import json
import math
import os
import time
import numpy as np

MU0 = 4e-7 * math.pi


def disponivel():
    try:
        import ngsolve  # noqa: F401
        import netgen.occ  # noqa: F401
        return True
    except Exception:
        return False


# ------------------------------------------------------------------------------------------------- geometria comum
def geometria(d):
    """Retângulos do corte 2D, idênticos aos do FEM da plataforma (mesmos condutores, mesmos entreferros)."""
    from .ind_projeto import modelo
    M = modelo(d, d["gaps"], d["ng"])
    a, ww, hw = d["a"], d["ww"], d["hw"]
    W, H = 3 * a + 2 * ww, 2 * a + hw
    janelas = [(a + i * (a + ww), a, a + i * (a + ww) + ww, a + hw) for i in range(2)]
    gaps = [(M.xl[i], y0, M.xl[i] + a, y1) for i, y0, y1 in M.gaps]
    cond = [dict(c) for c in M.g["condutores"]]
    return dict(W=W, H=H, a=a, b=d["b"], janelas=janelas, gaps=gaps, cond=cond, margem=0.6 * max(W, H), M=M)


# ------------------------------------------------------------------------------------------------- NGSolve 2D
def _malha2d(G, h_ar=0.02, h_fe=0.008, hcond=None):
    from netgen.occ import WorkPlane, Glue, OCCGeometry
    W, H, mg = G["W"], G["H"], G["margem"]

    def ret(x0, y0, x1, y1):
        return WorkPlane().MoveTo(x0, y0).Rectangle(x1 - x0, y1 - y0).Face()
    nucleo = ret(0, 0, W, H)
    for j in G["janelas"]:
        nucleo = nucleo - ret(*j)
    gfaces = []
    for k, gp in enumerate(G["gaps"]):
        f = ret(*gp)
        nucleo = nucleo - f
        f.faces.name = "gap"
        hmin = (gp[3] - gp[1])
        f.faces.maxh = max(hmin / 3, 4e-4)
        gfaces.append(f)
    nucleo.faces.name = "ferro"
    nucleo.faces.maxh = h_fe
    cfaces = []
    for j, c in enumerate(G["cond"]):
        f = ret(c["x0"], c["y0"], c["x1"], c["y1"])
        f.faces.name = f"c{j}"
        f.faces.maxh = hcond or max(min(c["x1"] - c["x0"], c["y1"] - c["y0"]) / 2.5, 5e-4)
        cfaces.append(f)
    ar = ret(-mg, -mg, W + mg, H + mg)
    ar.faces.name = "ar"
    ar.faces.maxh = h_ar
    ar.edges.name = "fora"
    for f in [nucleo] + gfaces + cfaces:
        ar = ar - f
    geo = Glue([ar, nucleo] + gfaces + cfaces)
    from ngsolve import Mesh
    return Mesh(OCCGeometry(geo, dim=2).GenerateMesh(maxh=h_ar))


def ngsolve_L2d(d, mu_r=4000, G=None, ordem=2, mesh=None):
    """Matriz de indutância 3×3 (H) do corte 2D × profundidade b, e L por fase (como na plataforma)."""
    from ngsolve import H1, BilinearForm, LinearForm, GridFunction, grad, dx, Integrate, CoefficientFunction
    G = G or geometria(d)
    mesh = mesh or _malha2d(G)
    nu_map = {"ferro": 1 / (MU0 * mu_r)}
    nu = mesh.MaterialCF(nu_map, default=1 / MU0)
    fes = H1(mesh, order=ordem, dirichlet="fora")
    u, v = fes.TnT()
    A = BilinearForm(nu * grad(u) * grad(v) * dx).Assemble()
    inv = A.mat.Inverse(fes.FreeDofs(), inverse="sparsecholesky")
    areas = [Integrate(CoefficientFunction(1), mesh, definedon=mesh.Materials(f"c{j}")) for j in range(len(G["cond"]))]
    Lm = np.zeros((3, 3))
    for k in range(3):
        f = LinearForm(fes)
        for j, c in enumerate(G["cond"]):
            if c["fase"] == k:
                f += (c["lado"] / areas[j]) * v * dx(f"c{j}")
        f.Assemble()
        gf = GridFunction(fes)
        gf.vec.data = inv * f.vec
        lam = np.zeros(3)
        for j, c in enumerate(G["cond"]):
            lam[c["fase"]] += c["lado"] * Integrate(gf, mesh, definedon=mesh.Materials(f"c{j}")) / areas[j]
        Lm[:, k] = lam * G["b"]
    Lp = np.array([Lm[k, k] - 0.5 * sum(Lm[k, j] for j in range(3) if j != k) for k in range(3)])
    return Lp, Lm, mesh


def ngsolve_Rac2d(d, freqs, G=None, mesh=None, mu_r=1500.0, hcond=1e-3):
    """Resistência CA da fase (Ω), média das 3 fases como na plataforma: corrente total imposta em cada seção de condutor
    (espiras em série), correntes parasitas reais na barra. Discretização NGSolve (malha não estruturada, elementos P2,
    malha fina dentro da barra para resolver a profundidade de penetração); o acoplamento das correntes é resolvido em
    scipy. Comprimento efetivo de cada seção = MLT/2."""
    import scipy.sparse as sp
    import scipy.sparse.linalg as spla
    from ngsolve import H1, BilinearForm, LinearForm, grad, dx, Integrate, CoefficientFunction
    G = G or geometria(d)
    mesh = mesh or _malha2d(G, hcond=hcond)
    sig = 1.0 / d["rhoT"]
    nc = len(G["cond"])
    ell = d["MLT"] / 2
    nu = mesh.MaterialCF({"ferro": 1 / (MU0 * mu_r)}, default=1 / MU0)
    fes = H1(mesh, order=2, dirichlet="fora")
    u, v = fes.TnT()

    def csr(bf):
        r, c, vals = bf.mat.COO()
        return sp.csr_matrix((np.array(vals), (np.array(r), np.array(c))), shape=(fes.ndof, fes.ndof))
    K = csr(BilinearForm(nu * grad(u) * grad(v) * dx).Assemble())
    cnd = "|".join(f"c{j}" for j in range(nc))
    Mc = csr(BilinearForm(u * v * dx(cnd)).Assemble())                 # ∫N N sobre todos os condutores
    Bc = np.zeros((fes.ndof, nc))
    for j in range(nc):
        lf = LinearForm(v * dx(f"c{j}")).Assemble()
        Bc[:, j] = lf.vec.FV().NumPy()
    S = np.array([Integrate(CoefficientFunction(1), mesh, definedon=mesh.Materials(f"c{j}")) for j in range(nc)])
    free = np.array([fes.FreeDofs()[i] for i in range(fes.ndof)], bool)
    idx = np.where(free)[0]
    K, Mc, Bf = K[idx][:, idx], Mc[idx][:, idx], sp.csr_matrix(Bc[idx])
    out = {}
    for f_hz in freqs:
        w = 2 * math.pi * f_hz
        A11 = (K + 1j * w * sig * Mc).tocsc()
        sysm = sp.bmat([[A11, -sig * Bf], [-1j * w * sig * Bf.T, sp.diags(sig * S)]]).tocsc()
        lu = spla.splu(sysm)
        Rk = []
        for k in (0, 1):
            rhs = np.zeros(len(idx) + nc, complex)
            for j, c in enumerate(G["cond"]):
                if c["fase"] == k:
                    rhs[len(idx) + j] = c["lado"]
            x = lu.solve(rhs)
            A = x[:len(idx)]
            uu = x[len(idx):]
            bA = Bf.T @ A                                                   # ∫A por condutor
            # P = ½σ Σ ∫|−jωA + u_j|² · ℓ
            P = 0.5 * sig * (w * w * np.real(np.conj(A) @ (Mc @ A)) + np.sum(S * np.abs(uu) ** 2)
                             + 2 * np.sum(np.real(-1j * w * bA * np.conj(uu)))) * ell
            Rk.append(P / 0.5)
        out[f_hz] = (2 * Rk[0] + Rk[1]) / 3
    return out


# ------------------------------------------------------------------------------------------------- NGSolve 3D
def ngsolve_L3d(d, mu_r=4000, h=0.02, log=None):
    """Indutância por fase em 3D completo (núcleo laminado como meio linear μr, 2 entreferros por coluna, 3 bobinas como
    regiões de densidade de corrente uniforme circulando em volta da coluna). Formulação A (H(curl)), estática."""
    from netgen.occ import Box, Pnt, Glue, OCCGeometry, X, Y, Z, WorkPlane, Axes
    from ngsolve import (HCurl, BilinearForm, LinearForm, GridFunction, curl, dx, Mesh, CoefficientFunction, x, y, z,
                         IfPos, sqrt, Integrate, InnerProduct, TaskManager)
    a, b, ww, hw = d["a"], d["b"], d["ww"], d["hw"]
    W, H = 3 * a + 2 * ww, 2 * a + hw
    N = d["N"]
    G = geometria(d)
    r_in = d["c"] + d["tube"]
    r_out = d["c"] + d["build"] - d["wrap"]
    zc0 = a + (hw - d["hc"]) / 2
    zb0 = zc0 + (d["hc"] - d["hf"]) / 2
    zb1 = zb0 + d["hf"]
    # núcleo: caixas (x ao longo do núcleo, y profundidade, z vertical)
    nucleo = Box(Pnt(0, -b / 2, 0), Pnt(W, b / 2, H))
    for (x0, z0, x1, z1) in G["janelas"]:
        nucleo = nucleo - Box(Pnt(x0, -b, z0), Pnt(x1, b, z1))
    gaps = []
    for (x0, z0, x1, z1) in G["gaps"]:
        gb = Box(Pnt(x0, -b / 2, z0), Pnt(x1, b / 2, z1))
        nucleo = nucleo - gb
        gb.solids.name = "gap"
        gb.solids.maxh = max((z1 - z0) / 1.5, 2.5e-3)
        gaps.append(gb)
    nucleo.solids.name = "ferro"
    nucleo.solids.maxh = h * 0.6
    bobinas = []
    for i in range(3):
        xc = a / 2 + i * (a + ww)

        # bobina = (retângulo arredondado externo − interno) extrudado
        wp = WorkPlane(Axes((xc, 0, zb0), n=Z, h=X))
        ext = _rret_face(wp, a + 2 * r_out, b + 2 * r_out, r_out)
        wp2 = WorkPlane(Axes((xc, 0, zb0), n=Z, h=X))
        inn = _rret_face(wp2, a + 2 * r_in, b + 2 * r_in, r_in)
        anel = (ext - inn).Extrude(zb1 - zb0)
        anel.solids.name = f"bob{i}"
        anel.solids.maxh = h * 0.6
        bobinas.append(anel)
    mg = 0.45 * max(W, H)
    ar = Box(Pnt(-mg, -mg - b / 2, -mg), Pnt(W + mg, b / 2 + mg, H + mg))
    ar.solids.name = "ar"
    ar.faces.name = "fora"
    ar.solids.maxh = 0.09
    for s in [nucleo] + gaps + bobinas:
        ar = ar - s
    geo = Glue([ar, nucleo] + gaps + bobinas)
    t0 = time.time()
    with TaskManager():
        mesh = Mesh(OCCGeometry(geo).GenerateMesh(maxh=h * 3))
    if log:
        log(f"     NGSolve 3D: malha {mesh.ne} tetraedros ({time.time() - t0:.0f} s)")
    nu = mesh.MaterialCF({"ferro": 1 / (MU0 * mu_r)}, default=1 / MU0)
    fes = HCurl(mesh, order=1, dirichlet="fora", nograds=True)
    u, v = fes.TnT()
    A = BilinearForm(fes)
    A += nu * curl(u) * curl(v) * dx + 1e-6 / MU0 * u * v * dx
    from ngsolve import Preconditioner, solvers
    pre = Preconditioner(A, "bddc")
    with TaskManager():
        A.Assemble()
    area = (r_out - r_in) * (zb1 - zb0)
    J0 = N / area
    # potencial de corrente T = T(ρ) ẑ na faixa de altura do enrolamento: J = rot T circula em volta da coluna e tem divergência
    # nula por construção (fonte compatível com a formulação H(curl)); ρ = distância à seção retangular da coluna.
    Ts = []
    for i in range(3):
        xc = a / 2 + i * (a + ww)
        dxv = IfPos(x - xc - a / 2, x - xc - a / 2, IfPos(xc - a / 2 - x, xc - a / 2 - x, 0))
        dyv = IfPos(y - b / 2, y - b / 2, IfPos(-b / 2 - y, -b / 2 - y, 0))
        rho = sqrt(dxv * dxv + dyv * dyv)
        Tm = IfPos(rho - r_out, 0, IfPos(rho - r_in, J0 * (r_out - rho), J0 * (r_out - r_in)))
        Tm = Tm * IfPos(z - zb0, 1, 0) * IfPos(zb1 - z, 1, 0)
        Ts.append(CoefficientFunction((0, 0, Tm)))
    L = np.zeros((3, 3))
    sols = []
    with TaskManager():
        for k in range(3):
            f = LinearForm(fes)
            f += InnerProduct(Ts[k], curl(v)) * dx
            f.Assemble()
            gf = GridFunction(fes)
            solvers.CG(mat=A.mat, pre=pre.mat, rhs=f.vec, sol=gf.vec, tol=1e-10, maxsteps=5000, printrates=False)
            sols.append(gf)
        for k in range(3):
            for j in range(3):
                L[j, k] = Integrate(InnerProduct(Ts[j], curl(sols[k])), mesh)          # λ_j = ∫ T_j · B_k
    Lp = np.array([L[k, k] - 0.5 * sum(L[k, j] for j in range(3) if j != k) for k in range(3)])
    return Lp, L, mesh.ne


def _rret_face(wp, w, h, r):
    """Retângulo de cantos arredondados centrado na origem do plano de trabalho."""
    r = min(r, w / 2 * 0.999, h / 2 * 0.999)
    wp.MoveTo(-w / 2 + r, -h / 2)
    wp.Line(w - 2 * r).Arc(r, 90).Line(h - 2 * r).Arc(r, 90).Line(w - 2 * r).Arc(r, 90).Line(h - 2 * r).Arc(r, 90)
    return wp.Face()


# ------------------------------------------------------------------------------------------------- FEM da plataforma
def plataforma(d, freqs):
    from .ind_projeto import modelo, L_fases, correcao_3d, h_condutor_final
    from .ind_fem import perdas_harmonico_multi
    M = modelo(d, d["gaps"], d["ng"])
    Lp2, Lm = L_fases(M, d["b"])
    L3 = correcao_3d(d, Lp2, M)
    sig = 1 / d["rhoT"]
    hc = h_condutor_final(d, 4 * d["requisitos"]["fs"]) if d.get("fio") else None
    Mr = modelo(d, d["gaps"], d["ng"], hcond=hc)                     # mesma malha da avaliação final de perdas
    ell = [d["MLT"] / 2] * len(Mr.g["condutores"])
    Rac = {}
    for f in freqs:
        Ps, _ = perdas_harmonico_multi(Mr, f, [[1.0, 0, 0], [0, 1.0, 0]], sig, ell)
        Rk = [P.sum() / 0.5 for P in Ps]
        Rac[f] = (2 * Rk[0] + Rk[1]) / 3
    return dict(L2d=Lp2, L3d=L3, Rac=Rac, n_el=len(M.m.area))


def malha_sensibilidade(d, freq):
    """FEM da plataforma com a malha de projeto e com refino dentro das barras (1 mm, 0,6 mm): L 2D e Rac em fs."""
    from .ind_projeto import _condutores, L_fases
    from .ind_fem import ModeloIndutor, perdas_harmonico_multi
    out = []
    a = d["a"]
    xl = [i * (a + d["ww"]) for i in range(3)]
    cond = _condutores(d, xl, a)
    sig = 1 / d["rhoT"]
    from .ind_projeto import h_condutor_final
    hf = h_condutor_final(d, 4 * d["requisitos"]["fs"])
    for nome, hc in (("triagem (malha grossa)", None), (f"projeto final (barras {hf*1e3:.1f} mm)", hf),
                     (f"verificação (barras {hf*0.6e3:.2f} mm)", hf * 0.6)):
        M = ModeloIndutor(dict(a=a, b=d["b"], hw=d["hw"], ww=d["ww"], ng=d["ng"], gaps=list(d["gaps"]), condutores=cond,
                               pos_gap=d.get("pos_gap", "distribuido")), hcond=hc)
        Lp, _ = L_fases(M, d["b"])
        Ps, _ = perdas_harmonico_multi(M, freq, [[1.0, 0, 0], [0, 1.0, 0]], sig, [d["MLT"] / 2] * len(cond))
        Rk = [P.sum() / 0.5 for P in Ps]
        out.append(dict(malha=nome, n_el=len(M.m.area), L2d_uH=float(Lp.mean() * 1e6), Rac_mohm=float((2 * Rk[0] + Rk[1]) / 3 * 1e3)))
    return out


def casos_analiticos(d):
    """1) Ferro ideal + entreferro: L → μ0 N² A / g quando o espraiamento some (entreferro pequeno, ferro μr→∞).
       2) Resistência CC: o FEM harmônico em 1 Hz deve reproduzir R = ρ N MLT / A."""
    from .ind_projeto import modelo, L_fases, area_espira
    from .ind_fem import perdas_harmonico_multi
    res = []
    for g_mm in (0.5, 2.0):
        dd = dict(d, gaps=[g_mm * 1e-3 * d["ng"]] * 3)
        M = modelo(dd, dd["gaps"], dd["ng"])
        Lp, _ = L_fases(M, d["b"], mu_r=1e7)          # L de fase (trifásico equilibrado) = μ0 N² A / g no limite ideal
        Lk = Lp[1]
        L0 = MU0 * d["N"] ** 2 * d["a"] * d["b"] / (g_mm * 1e-3 * d["ng"])
        res.append(dict(caso=f"Ferro ideal, entreferro {g_mm:g} mm/peça: L de fase FEM / μ0N²A/g (excesso = espraiamento 2D)",
                        valor=Lk / L0, esperado="≥ 1,00 e → 1 quando g → 0", ok=bool(1.0 <= Lk / L0 < (1.12 if g_mm < 1 else 1.6))))
    M = modelo(d, d["gaps"], d["ng"])
    sig = 1 / d["rhoT"]
    Ps, _ = perdas_harmonico_multi(M, 1.0, [[1.0, 0, 0]], sig, [d["MLT"] / 2] * len(M.g["condutores"]))
    R_fem = Ps[0].sum() / 0.5
    R_an = d["rhoT"] * d["N"] * d["MLT"] / area_espira(d)
    res.append(dict(caso="Resistência CC: FEM harmônico a 1 Hz / ρ·N·MLT/A", valor=R_fem / R_an, esperado="1,00 ± 0,02",
                    ok=bool(abs(R_fem / R_an - 1) < 0.02)))
    return res


# ------------------------------------------------------------------------------------------------- comparação completa
def inducao_coluna(d, G=None, mesh=None, mu_r=4000):
    """Indução MÉDIA na coluna (T) com a corrente de pico de operação – plataforma × NGSolve × fórmula (REQ-REA-012, v1.26.3).
    O engenheiro pediu a indução conferida em outro software. Fluxo por metro de profundidade numa coluna = diferença do potencial
    vetor A entre as duas faces da coluna (2D) → B médio = |A(x1) − A(x0)| / a. Caso: fase lateral no pico (I, −I/2, −I/2) e fase
    central no pico (−I/2, I, −I/2). Linear (μr igual nos dois programas, para comparar os SOLVERS) e não-linear (curva B-H, só na
    plataforma – é o valor de projeto)."""
    from ngsolve import H1, BilinearForm, LinearForm, GridFunction, grad, dx, Integrate, CoefficientFunction
    G = G or geometria(d)
    M = G["M"]
    r = d["requisitos"]
    I = float(r.get("Ipk") or 2 ** 0.5 * r["In"])
    a, ww, hw = d["a"], d["ww"], d["hw"]
    y0 = a + hw / 2
    gys = sorted((g_[1] + g_[3]) / 2 for g_ in G["gaps"])
    if gys:                                                        # nível no FERRO, o mais longe possível dos entreferros
        cand = np.linspace(a + 0.08 * hw, a + 0.92 * hw, 41)
        y0 = float(max(cand, key=lambda y: min(abs(y - gy) for gy in gys)))
    cols = {"lateral": (0.0, a, [I, -I / 2, -I / 2]), "central": (a + ww, 2 * a + ww, [-I / 2, I, -I / 2])}
    P = np.asarray(M.m.p)

    def no(x, y):
        return int(np.argmin((P[:, 0] - x) ** 2 + (P[:, 1] - y) ** 2))
    mesh = mesh or _malha2d(G)
    nu = mesh.MaterialCF({"ferro": 1 / (MU0 * mu_r)}, default=1 / MU0)
    fes = H1(mesh, order=2, dirichlet="fora")
    u, v = fes.TnT()
    Am = BilinearForm(nu * grad(u) * grad(v) * dx).Assemble()
    inv = Am.mat.Inverse(fes.FreeDofs(), inverse="sparsecholesky")
    areas = [Integrate(CoefficientFunction(1), mesh, definedon=mesh.Materials(f"c{j}")) for j in range(len(G["cond"]))]
    out = dict(I_pk=I, y_m=y0, mu_r=mu_r, colunas={})
    L2 = None
    for nome, (x0, x1, cur) in cols.items():
        Al = M.resolver(cur, mu_r=mu_r)
        b_lin = abs(Al[no(x1, y0)] - Al[no(x0, y0)]) / a
        An = M.resolver(cur)
        b_nl = abs(An[no(x1, y0)] - An[no(x0, y0)]) / a
        f = LinearForm(fes)
        for j, c in enumerate(G["cond"]):
            f += (c["lado"] * cur[c["fase"]] / areas[j]) * v * dx(f"c{j}")
        f.Assemble()
        gf = GridFunction(fes)
        gf.vec.data = inv * f.vec
        e_ = 1e-6
        b_ng = abs(gf(mesh(x1 - e_, y0)) - gf(mesh(x0 + e_, y0))) / a
        out["colunas"][nome] = dict(plataforma_linear_T=float(b_lin), ngsolve_linear_T=float(b_ng), plataforma_nao_linear_T=float(b_nl))
    try:
        from .ind_projeto import L_fases
        L2, _ = L_fases(M, d["b"])
        out["formula_T"] = float(L2.mean() * I / (d["N"] * a * d["b"]))       # B = L·I/(N·A) – conta de mão
    except Exception:
        out["formula_T"] = None
    out["B_proj_T"] = float(r.get("B_proj_T") or 1.45)
    return out


def comparar(d, log=print, fazer_3d=True, h3d=0.02):
    fs = d["requisitos"]["fs"]
    freqs = [60.0, float(fs), 2.0 * fs]
    t0 = time.time()
    P = plataforma(d, freqs)
    out = dict(freqs=freqs, plataforma=P, tempos={})
    out["tempos"]["plataforma"] = time.time() - t0
    G = geometria(d)
    t0 = time.time()
    mesh = _malha2d(G)
    Lp2, Lm2, _ = ngsolve_L2d(d, G=G, mesh=mesh)
    out["ng_L2d"], out["ng_n_el2d"] = Lp2, mesh.ne
    log(f"     NGSolve 2D: L = {Lp2.mean() * 1e6:.1f} µH (plataforma {P['L2d'].mean() * 1e6:.1f} µH), malha {mesh.ne} elementos")
    out["ng_Rac"] = ngsolve_Rac2d(d, freqs, G=G)
    out["tempos"]["ngsolve_2d"] = time.time() - t0
    log("     NGSolve 2D: Rac " + ", ".join(f"{f:g} Hz {out['ng_Rac'][f] * 1e3:.2f} mΩ (plat. {P['Rac'][f] * 1e3:.2f})" for f in freqs))
    if fazer_3d:
        t0 = time.time()
        try:
            Lp3, Lm3, ne3 = ngsolve_L3d(d, h=h3d, log=log)
            out["ng_L3d"], out["ng_n_el3d"] = Lp3, ne3
            log(f"     NGSolve 3D: L = {', '.join(f'{v * 1e6:.1f}' for v in Lp3)} µH (plataforma 3D corrigida "
                f"{', '.join(f'{v * 1e6:.1f}' for v in P['L3d'])} µH)")
        except Exception as e:
            out["erro_3d"] = f"{type(e).__name__}: {e}"
            log(f"     NGSolve 3D não concluído: {out['erro_3d']}")
        out["tempos"]["ngsolve_3d"] = time.time() - t0
    try:                                                # v1.26.3 (REQ-REA-012): indução na coluna conferida no 2º software
        out["B_col"] = inducao_coluna(d, G=G, mesh=mesh)
        bl = out["B_col"]["colunas"]["lateral"]
        log(f"     Indução na coluna em {out['B_col']['I_pk']:.0f} A de pico: plataforma {bl['plataforma_linear_T']:.3f} T × NGSolve "
            f"{bl['ngsolve_linear_T']:.3f} T (linear); não-linear {bl['plataforma_nao_linear_T']:.3f} T; fórmula "
            f"{out['B_col'].get('formula_T') or 0:.3f} T; limite de projeto {out['B_col']['B_proj_T']:.2f} T")
    except Exception as e:
        out["erro_B"] = f"{type(e).__name__}: {e}"
        log(f"     (indução na coluna não comparada: {out['erro_B']})")
    out["malha"] = malha_sensibilidade(d, fs)
    out["analiticos"] = casos_analiticos(d)
    return out


TOL = dict(L2d=3.0, L3d=5.0, Rac60=5.0, RacAF=15.0, B=3.0)


def linhas_comparacao(cmp):
    P = cmp["plataforma"]
    fs = cmp["freqs"]
    L = []

    def lin(nome, vp, vn, un, tol, fmt="{:.1f}"):
        dif = (vn / vp - 1) * 100 if vp else float("nan")
        L.append((nome, fmt.format(vp) + " " + un, fmt.format(vn) + " " + un, f"{dif:+.1f} %", f"±{tol:g} %",
                  "OK" if abs(dif) <= tol else "VERIFICAR"))
    for k, f in enumerate("UVW"):
        lin(f"L 2D fase {f} (mesmo corte)", P["L2d"][k] * 1e6, cmp["ng_L2d"][k] * 1e6, "µH", TOL["L2d"])
    if "ng_L3d" in cmp:
        for k, f in enumerate("UVW"):
            lin(f"L 3D fase {f} (plataforma: 2D + correção 3D; NGSolve: 3D completo)", P["L3d"][k] * 1e6, cmp["ng_L3d"][k] * 1e6, "µH", TOL["L3d"])
        Lng = np.asarray(cmp["ng_L3d"], float)
        dq = (Lng.max() - Lng.min()) / Lng.mean() * 100
        L.append(("Desequilíbrio entre fases no 3D (NGSolve)", "–", f"{dq:.1f} %", "–", "≤ 3 %", "OK" if dq <= 3.0 else "VERIFICAR"))
        aj = cmp.get("ajuste_gap_3d")
        if aj:                                          # v1.28.0: resultado DEPOIS do ajuste do entreferro (o que vai ao desenho)
            alvo = float(cmp.get("L_alvo") or 0) or None
            for k, f in enumerate("UVW"):
                vp = aj["L3_ng_previsto"][k] * 1e6
                dif = (vp / (alvo * 1e6) - 1) * 100 if alvo else float("nan")
                L.append((f"L 3D fase {f} APÓS o ajuste do entreferro (prevista) × alvo", f"{alvo * 1e6:.1f} µH" if alvo else "–", f"{vp:.1f} µH",
                          f"{dif:+.1f} %", "±5 %", "OK" if abs(dif) <= 5.0 else "VERIFICAR"))
            L.append(("Desequilíbrio APÓS o ajuste (previsto)", "–", f"{aj['deseq_previsto_pct']:.1f} %", "–", "≤ 3 %",
                      "OK" if aj["deseq_previsto_pct"] <= 3.0 else "VERIFICAR"))
    for nome, bc in ((cmp.get("B_col") or {}).get("colunas") or {}).items():
        lin(f"Indução média na coluna {nome} em {cmp['B_col']['I_pk']:.0f} A de pico (linear, mesmo μr)", bc["plataforma_linear_T"],
            bc["ngsolve_linear_T"], "T", TOL["B"], "{:.3f}")
    for f in fs:
        lin(f"R CA da fase em {f:g} Hz", P["Rac"][f] * 1e3, cmp["ng_Rac"][f] * 1e3, "mΩ", TOL["Rac60"] if f < 100 else TOL["RacAF"], "{:.2f}")
    return L


# ------------------------------------------------------------------------------------------------- FEMM (.lua)
def _celulas(G):
    """Subdivisão retilínea do corte em células de material único (ar, ferro, gap, condutor j)."""
    xs = {-G["margem"], G["W"] + G["margem"], 0.0, G["W"]}
    ys = {-G["margem"], G["H"] + G["margem"], 0.0, G["H"]}
    for r in G["janelas"] + G["gaps"]:
        xs |= {r[0], r[2]}
        ys |= {r[1], r[3]}
    for c in G["cond"]:
        xs |= {c["x0"], c["x1"]}
        ys |= {c["y0"], c["y1"]}
    xs = sorted({round(v, 7) for v in xs})
    ys = sorted({round(v, 7) for v in ys})

    def mat(xm, ym):
        for j, c in enumerate(G["cond"]):
            if c["x0"] < xm < c["x1"] and c["y0"] < ym < c["y1"]:
                return f"c{j}"
        for r in G["gaps"]:
            if r[0] < xm < r[2] and r[1] < ym < r[3]:
                return "gap"
        if 0 < xm < G["W"] and 0 < ym < G["H"]:
            for r in G["janelas"]:
                if r[0] < xm < r[2] and r[1] < ym < r[3]:
                    return "ar"
            return "ferro"
        return "ar"
    M = [[mat((xs[i] + xs[i + 1]) / 2, (ys[j] + ys[j + 1]) / 2) for j in range(len(ys) - 1)] for i in range(len(xs) - 1)]
    return xs, ys, M


def femm_lua(d, arq, arq_saida="resultado_femm_FSEN.csv"):
    """Script FEMM 4.2: mesmo corte 2D (planar, profundidade = empilhamento), núcleo linear μr 4000, condutores de cobre sólidos
    em circuitos série por fase. Calcula L (magnetostático) e R CA (60 Hz, fs, 2fs) e grava um CSV ao lado do script."""
    G = geometria(d)
    xs, ys, Mt = _celulas(G)
    nx, ny = len(xs) - 1, len(ys) - 1
    mm = lambda v: v * 1e3
    segs = set()
    for i in range(nx):
        for j in range(ny):
            if i + 1 < nx and Mt[i][j] != Mt[i + 1][j]:
                segs.add(((xs[i + 1], ys[j]), (xs[i + 1], ys[j + 1])))
            if j + 1 < ny and Mt[i][j] != Mt[i][j + 1]:
                segs.add(((xs[i], ys[j + 1]), (xs[i + 1], ys[j + 1])))
    # contorno externo
    X0, X1, Y0, Y1 = xs[0], xs[-1], ys[0], ys[-1]
    borda = [((X0, Y0), (X1, Y0)), ((X1, Y0), (X1, Y1)), ((X1, Y1), (X0, Y1)), ((X0, Y1), (X0, Y0))]
    # regiões conexas de mesmo material → 1 rótulo cada
    vis = [[False] * ny for _ in range(nx)]
    rotulos = []
    for i in range(nx):
        for j in range(ny):
            if vis[i][j]:
                continue
            m = Mt[i][j]
            pilha, cel = [(i, j)], []
            vis[i][j] = True
            while pilha:
                p, q = pilha.pop()
                cel.append((p, q))
                for (r, s) in ((p + 1, q), (p - 1, q), (p, q + 1), (p, q - 1)):
                    if 0 <= r < nx and 0 <= s < ny and not vis[r][s] and Mt[r][s] == m:
                        vis[r][s] = True
                        pilha.append((r, s))
            p, q = max(cel, key=lambda c: (xs[c[0] + 1] - xs[c[0]]) * (ys[c[1] + 1] - ys[c[1]]))
            rotulos.append((m, (xs[p] + xs[p + 1]) / 2, (ys[q] + ys[q + 1]) / 2))
    fs = d["requisitos"]["fs"]
    sigma_ms = 1e-6 / d["rhoT"]
    L = ["-- FSEN – verificação do indutor no FEMM 4.2 (gerado pela plataforma; não editar)",
         f"-- Indutor {d['requisitos']['L'] * 1e6:.0f} uH / {d['requisitos']['In']:.0f} A – corte 2D planar, profundidade {mm(d['b']):.1f} mm",
         "-- Uso: FEMM > File > Open Lua Script (ou arraste este arquivo). Ao terminar, envie o CSV gerado para a plataforma.",
         "showconsole()", "clearconsole()",
         f"saida = openfile(\"{arq_saida}\", \"w\")", "write(saida, \"freq_hz;excitacao;fase;I_re;I_im;V_re;V_im;fluxo_re;fluxo_im\\n\")",
         "function monta(freq)",
         "  newdocument(0)",
         f"  mi_probdef(freq, \"millimeters\", \"planar\", 1e-8, {mm(d['b']):.3f}, 30)",
         "  mi_addmaterial(\"Ar\", 1, 1, 0, 0, 0, 0, 0, 1, 0, 0, 0)",
         "  mi_addmaterial(\"Nucleo\", 4000, 4000, 0, 0, 0, 0, 0, 1, 0, 0, 0)",
         f"  mi_addmaterial(\"Cobre\", 1, 1, 0, 0, {sigma_ms:.4f}, 0, 0, 1, 0, 0, 0)",
         "  mi_addboundprop(\"A0\", 0, 0, 0, 0, 0, 0, 0, 0, 0)",
         "  mi_addcircprop(\"A\", 0, 1)", "  mi_addcircprop(\"B\", 0, 1)", "  mi_addcircprop(\"C\", 0, 1)"]
    nos = set()
    for (p, q) in list(segs) + borda:
        nos.add(p)
        nos.add(q)
    for (x, y) in sorted(nos):
        L.append(f"  mi_addnode({mm(x):.4f}, {mm(y):.4f})")
    for (p, q) in sorted(segs):
        L.append(f"  mi_addsegment({mm(p[0]):.4f}, {mm(p[1]):.4f}, {mm(q[0]):.4f}, {mm(q[1]):.4f})")
    for (p, q) in borda:
        L.append(f"  mi_addsegment({mm(p[0]):.4f}, {mm(p[1]):.4f}, {mm(q[0]):.4f}, {mm(q[1]):.4f})")
        L.append(f"  mi_selectsegment({mm((p[0] + q[0]) / 2):.4f}, {mm((p[1] + q[1]) / 2):.4f})")
    L.append("  mi_setsegmentprop(\"A0\", 0, 1, 0, 0)")
    L.append("  mi_clearselected()")
    for m, x, y in rotulos:
        L.append(f"  mi_addblocklabel({mm(x):.4f}, {mm(y):.4f})")
        L.append(f"  mi_selectlabel({mm(x):.4f}, {mm(y):.4f})")
        if m.startswith("c"):
            c = G["cond"][int(m[1:])]
            turns = c["lado"]
            L.append(f"  mi_setblockprop(\"Cobre\", 1, 0, \"{'ABC'[c['fase']]}\", 0, 0, {turns:g})")
        elif m == "ferro":
            L.append("  mi_setblockprop(\"Nucleo\", 1, 0, \"<None>\", 0, 0, 0)")
        else:
            L.append("  mi_setblockprop(\"Ar\", 1, 0, \"<None>\", 0, 0, 0)")
        L.append("  mi_clearselected()")
    L += ["  mi_saveas(\"fsen_verif_femm.fem\")", "end",
          "for _, freq in {0, 60, " + f"{fs:g}, {2 * fs:g}" + "} do",
          "  monta(freq)",
          "  for _, ex in {\"A\", \"B\", \"C\"} do",
          "    mi_setcurrent(\"A\", 0) mi_setcurrent(\"B\", 0) mi_setcurrent(\"C\", 0)",
          "    mi_setcurrent(ex, 1)",
          "    mi_analyze(1) mi_loadsolution()",
          "    for _, fa in {\"A\", \"B\", \"C\"} do",
          "      i, v, fl = mo_getcircuitproperties(fa)",
          "      write(saida, freq, \";\", ex, \";\", fa, \";\", re(i), \";\", im(i), \";\", re(v), \";\", im(v), \";\", re(fl), \";\", im(fl), \"\\n\")",
          "    end",
          "    mo_close()",
          "  end",
          "  mi_close()",
          "end",
          "closefile(saida)",
          "print(\"FSEN: verificação concluída – arquivo " + arq_saida + "\")"]
    import unicodedata
    txt = "\n".join(L).replace("–", "-").replace("µ", "u")
    txt = unicodedata.normalize("NFKD", txt).encode("ascii", "ignore").decode("ascii")
    with open(arq, "w", encoding="ascii") as fh:
        fh.write(txt + "\n")
    return arq


def ler_femm_csv(arq, d):
    """Lê o CSV do FEMM → L por fase (2D, H) e Rac por frequência (Ω, média das fases como na plataforma)."""
    import csv
    linhas = list(csv.DictReader(open(arq, encoding="latin-1"), delimiter=";"))
    fl = {}
    for r in linhas:
        f = float(r["freq_hz"])
        fl.setdefault(f, {})[(r["excitacao"], r["fase"])] = (complex(float(r["V_re"]), float(r["V_im"])),
                                                           complex(float(r["fluxo_re"]), float(r["fluxo_im"])))
    res = dict(Rac={})
    if 0.0 in fl:
        Lm = np.zeros((3, 3))
        for k, ex in enumerate("ABC"):
            for j, fa in enumerate("ABC"):
                Lm[j, k] = fl[0.0][(ex, fa)][1].real
        res["L2d"] = np.array([Lm[k, k] - 0.5 * sum(Lm[k, j] for j in range(3) if j != k) for k in range(3)])
    for f, tab in fl.items():
        if f <= 0:
            continue
        Rk = [tab[(ex, ex)][0].real / 1.0 for ex in "AB"]
        # a R da fase k vista pela fonte inclui as perdas induzidas nas outras fases → como a plataforma: (2 R_A + R_B)/3
        res["Rac"][f] = (2 * Rk[0] + Rk[1]) / 3 * (d["MLT"] / 2) / d["b"]
    return res


# ------------------------------------------------------------------------------------------------- relatório
def relatorio(d, cmp, arq, eng_dir=None, femm=None):
    from .auditoria import Rel, _Doc, _esc
    R = Rel()
    tit = "Verificação independente do indutor – comparação com outro software"
    from reportlab.platypus import Paragraph
    R.f.append(Paragraph(_esc(tit), R.st["CAPA"]))
    r = d["requisitos"]
    R.p(f"Indutor {r['L']*1e6:.0f} µH / {r['In']:.0f} A, {d['N']} espiras, 2 entreferros por coluna. O mesmo indutor foi recalculado no "
        "NGSolve/Netgen – programa de elementos finitos independente (malha, elementos e solver próprios; elementos de 2ª ordem em 2D, "
        "H(curl) em 3D) – e comparado com o FEM da plataforma (triângulos lineares próprios).")
    R.h1("Resultado da comparação")
    lin = linhas_comparacao(cmp)
    R.tab(["Grandeza", "Plataforma", "NGSolve", "Diferença", "Critério", "Situação"], lin, [3.6, 1.3, 1.3, 1.0, 0.9, 1.0], 6.8)
    nok = sum(1 for l in lin if l[-1] != "OK")
    R.p(("Todas as grandezas dentro do critério: o cálculo da plataforma está confirmado por um segundo software." if nok == 0 else
         f"{nok} grandeza(s) fora do critério – ver a nota abaixo e conferir antes de usar o resultado."))
    R.bul(["L 2D: mesmo corte, mesmo material linear (μr 4000): confere a montagem do problema e o solver.",
           "L 3D: o NGSolve modela o indutor inteiro em 3D (núcleo, entreferros, 3 bobinas de cantos arredondados); a plataforma usa o "
           "2D com correção do espraiamento nas faces da frente e de trás. É a comparação que valida a correção 3D.",
           "R CA: corrente total imposta em cada espira, correntes parasitas reais na barra (efeito pelicular, proximidade e campo do "
           "entreferro). Em alta frequência a malha e a ordem dos elementos pesam mais – critério ±15 %."])
    if femm:
        R.h2("FEMM (rodado pelo engenheiro)")
        lf = []
        P = cmp["plataforma"]
        if "L2d" in femm:
            for k, f in enumerate("UVW"):
                dv = (femm["L2d"][k] / P["L2d"][k] - 1) * 100
                lf.append((f"L 2D fase {f}", f"{P['L2d'][k]*1e6:.1f} µH", f"{femm['L2d'][k]*1e6:.1f} µH", f"{dv:+.1f} %"))
        for f, v in sorted(femm["Rac"].items()):
            if f in P["Rac"]:
                dv = (v / P["Rac"][f] - 1) * 100
                lf.append((f"R CA {f:g} Hz", f"{P['Rac'][f]*1e3:.2f} mΩ", f"{v*1e3:.2f} mΩ", f"{dv:+.1f} %"))
        R.tab(["Grandeza", "Plataforma", "FEMM", "Diferença"], lf, [3, 1.4, 1.4, 1.1], 7)
    R.h1("Casos de resultado conhecido (verificação do código)")
    R.tab(["Caso", "Resultado", "Esperado", "Situação"],
          [(c["caso"], f"{c['valor']:.4f}", c["esperado"], "OK" if c["ok"] else "VERIFICAR") for c in cmp["analiticos"]], [4, 1, 1.6, 0.9], 7)
    R.h1("Sensibilidade à malha (FEM da plataforma)")
    m = cmp["malha"]
    R.tab(["Malha", "Elementos", "L 2D", f"R CA {r['fs']/1e3:g} kHz"],
          [(x["malha"], f"{x['n_el']}", f"{x['L2d_uH']:.2f} µH", f"{x['Rac_mohm']:.3f} mΩ") for x in m], [2, 1.2, 1.3, 1.5], 7)
    if len(m) >= 2:
        dl = (m[-1]["L2d_uH"] / m[0]["L2d_uH"] - 1) * 100
        fsx = float(r["fs"])
        rng = cmp["ng_Rac"].get(fsx)
        R.p(f"Indutância: refino muda {dl:+.2f} % (independente da malha). R CA em {fsx/1e3:g} kHz: com o refino dentro das barras o "
            f"FEM da plataforma tende ao valor do NGSolve ({rng*1e3:.2f} mΩ, malha fina convergida)" if rng else "")
        R.p(f"Malha de triagem: {m[0]['Rac_mohm']:.2f} mΩ; malha final do projeto: {m[1]['Rac_mohm']:.2f} mΩ "
            f"({(m[1]['Rac_mohm'] / (rng * 1e3) - 1) * 100:+.1f} % do NGSolve convergido). Desde a v1.11.8 a avaliação final das perdas "
            "usa a malha refinada nas barras (a comparação com o NGSolve mostrou que a malha de triagem subestimava a R CA em 2·fs)."
            if rng else "")
    est = cmp.get("estudo_camadas")
    if est:
        R.h1("Variações do nº de camadas da bobina (mesmas regras de projeto)")
        R.tab(["Camadas", "Espiras", "Barra (mm)", "Coluna (mm)", "Janela (mm)", "Massa", "Perdas", "Elevação", "Saídas"],
              [((f"{e['n_cam']}" + (" (escolhido)" if e.get("escolhido") else "")), str(e.get("N", "–")), e.get("barra", "–"),
                e.get("coluna", "–"), e.get("janela", "–"), (f"{e['massa_kg']:.0f} kg" if "massa_kg" in e else "–"),
                (f"{e['perdas_w']:.0f} W" if "perdas_w" in e else "–"), (f"{e['elev_k']:.0f} K" if "elev_k" in e else "–"),
                e.get("saidas", e.get("erro", "")[:40])) for e in est], [1.4, 0.9, 1.1, 1.1, 1.1, 0.9, 0.9, 0.9, 1.6], 6.8)
        R.p("Nº ímpar de camadas leva o início da bobina para cima e o fim para baixo (como os reatores nacionais); nº par deixa as duas "
            "saídas em cima. A escolha final pondera massa, perdas e o processo do fabricante.")
    R.h1("Como conferir no FEMM (Windows, gratuito)")
    R.bul(["Instalar o FEMM 4.2 (www.femm.info).",
           "Abrir o arquivo Verificacao_FEMM_<código>.lua (FEMM > File > Open Lua Script). O script desenha o mesmo corte, roda a "
           "indutância e as perdas em 60 Hz e na frequência de chaveamento e grava resultado_femm_FSEN.csv na mesma pasta.",
           "Na plataforma, aba de conferência do indutor, carregar o CSV: a comparação FEMM entra neste relatório."])
    R.h1("Tempos de cálculo")
    R.p("; ".join(f"{k}: {v:.0f} s" for k, v in cmp["tempos"].items()))
    doc = _Doc(arq, tit, rotulo="VERIFICAÇÃO – ELECTRIC SERVICE")
    doc.multiBuild(R.f)
    return arq


# ------------------------------------------------------------------------------------------------- dados para o protocolo
def sensibilidade_gap(d, delta_mm=0.1):
    """ΔL (%) de cada fase quando AS DUAS peças do entreferro de UMA coluna aumentam delta_mm cada (L 3D corrigida)."""
    from .ind_projeto import modelo, L_fases, correcao_3d
    base = list(d["gaps"])
    M = modelo(d, base, d["ng"])
    L0 = correcao_3d(d, L_fases(M, d["b"])[0], M)
    out = []
    for k in range(3):
        g = list(base)
        g[k] += delta_mm * 1e-3 * d["ng"]
        Mk = modelo(d, g, d["ng"])
        Lk = correcao_3d(d, L_fases(Mk, d["b"])[0], Mk)
        out.append(dict(coluna="UVW"[k], gap_peca_mm=base[k] / d["ng"] * 1e3, dL_pct=list((Lk / L0 - 1) * 100)))
    return out


def ajuste_gap_3d(d, Lng3, tol_pct=1.0):
    """v1.28.0 (REQ-SEN-022, auditoria NC-1.4): quando a verificação 3D independente (NGSolve) mostra fase fora de ±5 % ou
    desequilíbrio > 3 % – típico da coluna CENTRAL de núcleo trifásico, que a correção 3D analítica não pega –, recalcula o
    entreferro de cada coluna pela matriz de sensibilidade (ΔL por +0,1 mm em cada coluna) para levar as 3 fases do 3D ao
    alvo. Devolve None se já está dentro de tol_pct; senão os novos entreferros e a L 3D prevista depois do ajuste."""
    alvo = float(d["requisitos"]["L"])
    Lng = np.asarray(Lng3, float)
    erro = (alvo / Lng - 1) * 100                        # quanto cada fase precisa subir (%)
    if np.all(np.abs(erro) <= tol_pct):
        return None
    sens = sensibilidade_gap(d, 0.1)
    S = np.array([[sens[k]["dL_pct"][i] for k in range(3)] for i in range(3)])   # S[i,k] = ΔL_i % por +0,1 mm/peça na coluna k
    passos = np.linalg.lstsq(S, erro, rcond=None)[0]    # em unidades de +0,1 mm por peça
    passos[0] = passos[2] = (passos[0] + passos[2]) / 2  # colunas laterais iguais (simetria)
    ng = int(d["ng"])
    gaps_novos = [max(g + p_ * 0.1e-3 * ng, 0.2e-3 * ng) for g, p_ in zip(d["gaps"], passos)]
    L_prev = Lng * (1 + S @ passos / 100)
    return dict(gaps_antes=list(d["gaps"]), gaps=gaps_novos, L3_ng_antes=list(Lng), L3_ng_previsto=list(L_prev),
                delta_mm_peca=[float(p_ * 0.1) for p_ in passos],
                deseq_antes_pct=float((Lng.max() - Lng.min()) / Lng.mean() * 100),
                deseq_previsto_pct=float((L_prev.max() - L_prev.min()) / L_prev.mean() * 100))


def ensaio_60hz(d):
    """Degraus do ensaio trifásico em 60 Hz: corrente eficaz, pico, tensão fase-neutro esperada e L mínima admitida."""
    r = d["requisitos"]
    L = r["L"]
    w = 2 * math.pi * 60.0
    Rdc = float(d.get("Rdc_ohm") or d.get("R") or 0)
    sat = {s["caso"][:4]: s for s in (d.get("saturacao") or [])}
    degraus = [(0.25, "25 % In", None), (0.5, "50 % In", None), (1.0, "100 % In", "±5 % do nominal"),
               (r["Isat"] / math.sqrt(2) / r["In"], "Isat (pico)", 90), (r["Iovl"] / math.sqrt(2) / r["In"], "Sobrecarga 150 % inversor (pico)", 70)]
    out = []
    for k, nome, lmin in degraus:
        I = k * r["In"]
        V = I * math.hypot(w * L, Rdc)
        out.append(dict(nome=nome, I_rms=I, I_pk=I * math.sqrt(2), V_fn=V, V_ff=V * math.sqrt(3), L_min_pct=lmin,
                        kVA=3 * V * I / 1e3))
    return out


def rac_previsto(d):
    """R série prevista por fase em 60 Hz, fs e 2fs: enrolamento (FEM harmônico) + parcela equivalente do núcleo/entreferro
    em alta frequência (perdas de AF do núcleo ÷ 3 I_ripple²) – o que uma ponte LCR mede com a bobina montada no núcleo."""
    r = d["requisitos"]
    rac = {float(k.split()[0]): v for k, v in (d.get("Rac_ohm") or {}).items()}
    p = d["perdas"]
    irr = float(r.get("I_AF_rms_espectro") or r.get("rrms") or 1)
    r_fe = (float(p.get("nucleo_AF", 0)) + float(p.get("nucleo_entreferro", 0))) / (3 * irr ** 2)
    fs = float(r["fs"])
    out = []
    for f in sorted(rac):
        fe = r_fe * (f / fs) ** 1.5 if f >= 1000 else 0.0      # parasitas no núcleo ∝ f², histerese/entreferro ∝ f → ~f^1,5
        out.append(dict(f=f, R_enr=rac[f], R_fe=fe, R_tot=rac[f] + fe))
    return out


def salvar_cmp(cmp, arq):
    def conv(o):
        if isinstance(o, np.ndarray):
            return o.tolist()
        if isinstance(o, dict):
            return {str(k): conv(v) for k, v in o.items()}
        if isinstance(o, (list, tuple)):
            return [conv(x) for x in o]
        if isinstance(o, (np.floating, np.integer)):
            return o.item()
        return o
    json.dump(conv(cmp), open(arq, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return arq


def carregar_cmp(arq):
    c = json.load(open(arq, encoding="utf-8"))
    P = c["plataforma"]
    P["L2d"], P["L3d"] = np.array(P["L2d"]), np.array(P["L3d"])
    P["Rac"] = {float(k): v for k, v in P["Rac"].items()}
    c["ng_L2d"] = np.array(c["ng_L2d"])
    if "ng_L3d" in c:
        c["ng_L3d"] = np.array(c["ng_L3d"])
    c["ng_Rac"] = {float(k): v for k, v in c["ng_Rac"].items()}
    c["freqs"] = [float(x) for x in c["freqs"]]
    return c
