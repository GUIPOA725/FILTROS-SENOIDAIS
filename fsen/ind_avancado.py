"""Avaliação avançada do indutor – acoplamento com as formas de onda da simulação do circuito (v1.12.0).

1) Formas de onda: correntes das 3 fases no pior ponto de operação, da simulação do filtro (a mesma conferida com o ATP);
   fundamental levada à corrente térmica de projeto, ondulação/harmônicas mantidas como simuladas.
2) Núcleo no TEMPO: B(t) de cada elemento do FEM (linear, superposição das 3 fases) →
     • parasitas clássicas EXATAS por linha do espectro, com efeito pelicular na lâmina (Lammeraner/Stafl);
     • perdas em excesso de Bertotti  ke·<|dB/dt|^1,5>;
     • histerese por contagem RAINFLOW dos laços (maior + menores) com fator de polarização CC por laço (iGSE com bias).
3) Campo espraiado em 3D (NGSolve): fluxo NORMAL às lâminas nas faces do núcleo junto aos entreferros → correntes no plano
   da lâmina (função de corrente 2D por camada) e perdas nos QUADROS/TIRANTES de aço por impedância de superfície.
   Substitui a fórmula empírica de Lee/McLyman.
4) Cobre: R CA em 8 frequências (malha refinada nas barras) aplicada a TODAS as linhas do espectro; resistividade iterada
   na temperatura calculada (acoplamento eletrotérmico).
5) Mapa térmico por diferenças finitas: corte da bobina (condutores, isolação, canal) e plano das lâminas do núcleo;
   ponto quente e média comparados com o modelo térmico de nós da plataforma.
"""
import math
import time
import numpy as np

MU0 = 4e-7 * math.pi
K_BIAS = 1.2           # laço menor sobre polarização CC: E = E0·(1 + K_BIAS·(Bm/1,7 T)²)  (literatura iGSE/bias, aço GO)
SIG_ACO_ESTR = 5.0e6   # aço carbono da estrutura (S/m)
MU_ACO_ESTR = 200.0    # permeabilidade relativa efetiva do aço da estrutura
K_FE_PLANO = 25.0      # condutividade térmica do pacote no plano da lâmina (W/m·K)
K_ISO = 0.25           # isolação aramida + resina (W/m·K)
K_TUBO = 0.30          # tubo vidro-epóxi (W/m·K)
K_CU = 390.0


# ===================================================================================================== 1) formas de onda
def formas_onda(proj, cat, I1_rms, pts=60):
    from .dimensionamento import avaliar, pontos_operacao
    from .modelos import Pedido
    from .simulacao import simular
    ped = Pedido.from_dict(proj.pedido) if isinstance(proj.pedido, dict) else proj.pedido
    b = proj.banco
    cap = next((c for c in cat["capacitores"] if c["id"] == b.cap_id), None) or dict(id=b.cap_id, uf=b.uf_unit, v_ac=b.v_unit, preco=0)
    vdc = 1.35 * ped.tensao_v
    L2 = proj.l2.l_uh * 1e-6 if proj.l2 else 0.0
    p, _, _ = avaliar(ped, cat, proj.l1.l_uh * 1e-6, cap, (b.ligacao, b.n_por_ramo, b.c_y_uf * 1e-6), proj.fs_hz, vdc,
                      L2=L2, pts_por_portadora=24)
    op = pontos_operacao(ped, vdc, proj.fs_hz)[0]["op"]
    r = simular(p, op, pts_por_portadora=pts, ciclos_analise=1)
    return _normalizar(np.asarray(r.t), np.asarray(r.i1), op.f1, I1_rms)


def _normalizar(t, ia, f1, I1_rms):
    dt = t[1] - t[0]
    n = int(round(1 / (f1 * dt)))
    ia = ia[-n:]
    F = np.fft.rfft(ia)
    a1 = 2 * abs(F[1]) / n
    if a1 > 0:
        F[1] *= I1_rms * math.sqrt(2) / a1                     # fundamental = corrente térmica de projeto
    F[0] = 0
    h = np.arange(len(F))
    Fs = [F, F * np.exp(-2j * np.pi * h / 3), F * np.exp(2j * np.pi * h / 3)]   # b e c: deslocamento de T/3 (equilibrado)
    i = np.array([np.fft.irfft(X, n) for X in Fs])
    I = np.array([2 * X / n for X in Fs])                      # amplitudes complexas (pico) por harmônica
    I[:, 0] = 0
    fh = h * f1
    return dict(t=np.arange(n) * dt, dt=dt, i=i, I=I, fh=fh, f1=f1, n=n,
                I1_rms=I1_rms, I_rip_rms=float(np.sqrt((np.abs(I[0, 4:]) ** 2).sum() / 2)),
                Ipk=float(np.abs(i).max()))


# ===================================================================================================== 2) núcleo no tempo
def _bu(d):
    from .ind_projeto import modelo
    M = modelo(d, d["gaps"], d["ng"])
    M.matriz_L(4000)
    B = [M.B(M._sol_unit[k]) for k in range(3)]
    Bx = np.array([b[0][M.ferro] for b in B])
    By = np.array([b[1][M.ferro] for b in B])
    return M, Bx, By


def _fat_pelicular(ch, f, mu_inc=1500.0):
    d, rho = ch["esp_mm"] * 1e-3, ch["rho"]
    w = 2 * np.pi * np.maximum(f, 1e-9)
    delta = np.sqrt(2 * rho / (w * MU0 * mu_inc))
    xi = d / delta
    return np.where(xi < 1e-3, 1.0, 3 / xi * (np.sinh(xi) - np.sin(xi)) / (np.cosh(xi) - np.cos(xi)))


def _rainflow_energia(Bt, kh_v):
    import rainflow
    E = 0.0
    for rng, mean, cnt, _, _ in rainflow.extract_cycles(Bt):
        E += cnt * kh_v * (rng / 2) ** 1.9 * (1 + K_BIAS * (mean / 1.7) ** 2)
    return E


def perdas_nucleo_tempo(d, ch, wf, n_clusters=48, n_s=7):
    from .ind_projeto import _steinmetz
    from scipy.cluster.vq import kmeans2
    M, Bx, By = _bu(d)
    vol = M.m.area[M.ferro] * d["b"] * ch["kf"]
    dl, rho, dens = ch["esp_mm"] * 1e-3, ch["rho"], ch["dens"]
    kh, k_exc, _ = _steinmetz(ch)
    I, fh, i, dt = wf["I"], wf["fh"], wf["i"], wf["dt"]
    # --- parasitas clássicas por linha do espectro (com pelicular na lâmina)
    g = (2 * np.pi * fh) ** 2 * dl ** 2 / (24 * rho) * _fat_pelicular(ch, fh)
    G = np.einsum("h,kh,lh->kl", g, I, np.conj(I)).real
    D = np.einsum("ke,le->kle", Bx, Bx) + np.einsum("ke,le->kle", By, By)
    p_ed = np.einsum("kl,kle->e", G, D)
    # separação fundamental × alta frequência (para comparar com o método da plataforma)
    g1 = g.copy()
    g1[2:] = 0
    p_ed1 = np.einsum("kl,kle->e", np.einsum("h,kh,lh->kl", g1, I, np.conj(I)).real, D)
    # --- excesso (Bertotti) no tempo
    pe_cl = (math.pi * dl * 1.7 * 50) ** 2 / (6 * rho * dens)
    c15 = float(np.mean(np.abs(np.cos(np.linspace(0, 2 * np.pi, 4001)[:-1])) ** 1.5))
    ke_v = (k_exc - 1) * pe_cl * dens / ((2 * np.pi * 50 * 1.7) ** 1.5 * c15)
    didt = np.gradient(i, dt, axis=1)
    p_ex = np.zeros(len(vol))
    bpk = np.zeros(len(vol))
    for s0 in range(0, len(vol), 800):
        bx = didt.T @ Bx[:, s0:s0 + 800]
        by = didt.T @ By[:, s0:s0 + 800]
        p_ex[s0:s0 + 800] = ke_v * np.mean((bx * bx + by * by) ** 0.75, axis=0)
        bpk[s0:s0 + 800] = np.sqrt(((i.T @ Bx[:, s0:s0 + 800]) ** 2 + (i.T @ By[:, s0:s0 + 800]) ** 2).max(0))
    # --- histerese: rainflow sobre a direção principal de cada elemento (agrupado por direção)
    C = np.cov(i)
    Cxx = np.einsum("kl,ke,le->e", C, Bx, Bx)
    Cyy = np.einsum("kl,ke,le->e", C, By, By)
    Cxy = np.einsum("kl,ke,le->e", C, Bx, By)
    th = 0.5 * np.arctan2(2 * Cxy, Cxx - Cyy)
    w = (Bx * np.cos(th) + By * np.sin(th)).T              # (Ne, 3) pesos das correntes na direção principal
    s = np.linalg.norm(w, axis=1) + 1e-30
    u = w / s[:, None]
    u = np.where(u[:, :1] < 0, -u, u)                         # sinal arbitrário da direção
    kc = min(n_clusters, max(4, len(u) // 50))
    np.random.seed(0)
    cent, lab = kmeans2(u, kc, minit="++", seed=0)
    kh_v = kh * dens
    p_hi = np.zeros(len(vol))
    for c in range(kc):
        sel = lab == c
        if not sel.any():
            continue
        uc = cent[c] / (np.linalg.norm(cent[c]) + 1e-30)
        base = uc @ i
        smin, smax = s[sel].min(), s[sel].max()
        sg = np.geomspace(max(smin, 1e-9), max(smax, smin * 1.0001, 1e-9), n_s)
        E = np.array([_rainflow_energia(sv * base, kh_v) for sv in sg])
        Ei = np.exp(np.interp(np.log(s[sel]), np.log(sg), np.log(np.maximum(E, 1e-30))))
        p_hi[sel] = Ei * wf["f1"]
    m_ed = (p_ed * vol).sum()
    out = dict(parasitas=float(m_ed), parasitas_60Hz=float((p_ed1 * vol).sum()), excesso=float((p_ex * vol).sum()),
               histerese=float((p_hi * vol).sum()))
    out["total"] = out["parasitas"] + out["excesso"] + out["histerese"]
    out["densidade_Wm3"] = (p_ed + p_ex + p_hi)
    out["_M"] = M
    out["Bpk_max_T"] = float(bpk.max())
    out["Bpk_p50_T"] = float(np.percentile(bpk, 50))
    return out


# ===================================================================================================== 4) cobre
def cobre_espectro(d, wf, f_fs):
    """R CA por fase em 8 frequências (malha refinada nas barras) → perdas em TODAS as linhas do espectro.
    Devolve também as perdas por condutor da fase central (para o mapa térmico), por A² de pico, interpoladas."""
    from .ind_projeto import modelo, h_condutor_final
    from .ind_fem import perdas_harmonico_multi
    hc = h_condutor_final(d, 4 * f_fs) if d.get("fio") else None
    M = modelo(d, d["gaps"], d["ng"], hcond=hc)
    sig = 1 / d["rhoT"]
    ell = [d["MLT"] / 2] * len(M.g["condutores"])
    fr = np.array([wf["f1"], 0.5 * f_fs, f_fs, 1.5 * f_fs, 2 * f_fs, 3 * f_fs, 4 * f_fs, 6 * f_fs])
    R = np.zeros((len(fr), 2))
    Pc = []
    for j, f in enumerate(fr):
        Ps, _ = perdas_harmonico_multi(M, f, [[1.0, 0, 0], [0, 1.0, 0]], sig, ell)
        R[j] = [Ps[0].sum() / 0.5, Ps[1].sum() / 0.5]
        Pc.append(Ps[1])                              # perdas por condutor, fase V excitada com 1 A de pico
    Pc = np.array(Pc)
    fh, I = wf["fh"], wf["I"]
    sel = fh > 0
    lf = np.log(np.clip(fh[sel], fr[0], fr[-1]))
    Rl = np.exp(np.interp(lf, np.log(fr), np.log(R[:, 0])))
    Rc = np.exp(np.interp(lf, np.log(fr), np.log(R[:, 1])))
    A2 = np.abs(I[:, sel]) ** 2
    P_h = 0.5 * (Rl * A2[0] + Rc * A2[1] + Rl * A2[2])
    h1 = np.argmin(np.abs(fh[sel] - wf["f1"]))
    P60 = float(P_h[h1])
    Paf = float(P_h.sum() - P60)
    # perdas por condutor (fase V) com o espectro real
    Pcl = np.exp(np.array([np.interp(lf, np.log(fr), np.log(np.maximum(Pc[:, j], 1e-30))) for j in range(Pc.shape[1])]))
    Pcond = (Pcl * A2[1][None, :]).sum(1)
    return dict(freqs=fr, R_lat=R[:, 0], R_cen=R[:, 1], P60=P60, P_AF=Paf, P_cond_V=Pcond, M=M, hcond=hc)


def rho_rel(cond_id, T, T0):
    a = 0.00393 if cond_id == "CU" else 0.00403
    return (1 + a * (T - 20)) / (1 + a * (T0 - 20))


# ===================================================================================================== 5) mapas térmicos
def _fd_solver(nx, ny, hx, hy, k, q, h_bnd, t_inf, fixo=None):
    """Condução 2D em regime (volumes finitos): k[i,j] condutividade, q[i,j] W/m³, h_bnd: dict borda→(h, T∞) ou por célula
    via arrays (hx_esq, ...) – aqui: h_bnd = (hW, hE, hS, hN) arrays por célula de borda; fixo: máscara/valores (Dirichlet)."""
    import scipy.sparse as sp
    import scipy.sparse.linalg as spla
    N = nx * ny
    idx = lambda i, j: i * ny + j
    rows, cols, vals = [], [], []
    b = q.ravel() * hx * hy
    diag = np.zeros(N)
    for (di, dj, area, dist) in ((1, 0, hy, hx), (-1, 0, hy, hx), (0, 1, hx, hy), (0, -1, hx, hy)):
        I, J = np.meshgrid(np.arange(nx), np.arange(ny), indexing="ij")
        I2, J2 = I + di, J + dj
        ok = (I2 >= 0) & (I2 < nx) & (J2 >= 0) & (J2 < ny)
        k1 = k[I[ok], J[ok]]
        k2 = k[I2[ok], J2[ok]]
        kk = np.where((k1 > 0) & (k2 > 0), 2 * k1 * k2 / (k1 + k2 + 1e-30), 0.0)
        G = kk * area / dist
        a = idx(I[ok], J[ok])
        c = idx(I2[ok], J2[ok])
        rows += list(a)
        cols += list(c)
        vals += list(-G)
        np.add.at(diag, a, G)
    # convecção (condutância por célula) e sumidouro volumétrico
    Gc, Tc = h_bnd
    diag += Gc.ravel()
    b += (Gc * Tc).ravel()
    A = sp.csr_matrix((list(vals) + list(diag), (rows + list(range(N)), cols + list(range(N)))), shape=(N, N))
    ativo = (k.ravel() > 0)
    T = np.full(N, np.nan)
    ia = np.where(ativo)[0]
    T[ia] = spla.spsolve(A[ia][:, ia].tocsc(), b[ia])
    return T.reshape(nx, ny)


def mapa_bobina(d, cu, T_amb, T_nucleo, h_conv, res=0.4e-3):
    """Corte da bobina da fase V do lado da janela: condutores (k cobre), isolação, canal de ventilação (convecção),
    tubo até o núcleo (temperatura do núcleo), superfície externa e cabeceiras (convecção)."""
    a = d["a"]
    M = cu["M"]
    conds = [(j, c) for j, c in enumerate(M.g["condutores"]) if c["fase"] == 1 and c["x0"] > M.xl[1] + a - 1e-9]
    xs0 = M.xl[1] + a                                         # face da coluna V (lado direito)
    x_in = xs0 + d["c"]                                       # início do tubo
    x_out = xs0 + d["c"] + d["build"]
    z0 = min(c["y0"] for _, c in conds) - 0.012
    z1 = max(c["y1"] for _, c in conds) + 0.012
    nx = int(round((x_out - xs0) / res)) + 1
    ny = int(round((z1 - z0) / res)) + 1
    xc = xs0 + (np.arange(nx) + 0.5) * res
    zc = z0 + (np.arange(ny) + 0.5) * res
    X, Z = np.meshgrid(xc, zc, indexing="ij")
    k = np.full((nx, ny), K_ISO)
    k[X < x_in] = 0.0                                         # espaço núcleo–tubo (ar parado) → tratado como fronteira
    k[(X >= x_in) & (X < x_in + d["tube"])] = K_TUBO
    q = np.zeros((nx, ny))
    ell = d["MLT"] / 2
    for j, c in conds:
        m = (X >= c["x0"]) & (X < c["x1"]) & (Z >= c["y0"]) & (Z < c["y1"])
        k[m] = K_CU
        q[m] = cu["P_cond_V"][j] / ((c["x1"] - c["x0"]) * (c["y1"] - c["y0"]) * ell)
    # canal de ventilação: faixa sem condutor entre camadas com largura ≥ 5 mm
    xcond = sorted({(round(c["x0"], 6), round(c["x1"], 6)) for _, c in conds})
    canais = []
    for (p0, p1), (q0, q1) in zip(xcond[:-1], xcond[1:]):
        if q0 - p1 > 5e-3:
            canais.append((p1 + 0.5e-3, q0 - 0.5e-3))
    for (c0, c1) in canais:
        k[(X >= c0) & (X < c1)] = 0.0
    Gc = np.zeros((nx, ny))
    Tc = np.zeros((nx, ny))
    ativo = k > 0

    def borda(mask_cell, area, h, Tinf):
        Gc[mask_cell] += h * area
        Tc[mask_cell] = Tinf
    viz = lambda di, dj: np.pad(ativo, 1)[1 + di:nx + 1 + di, 1 + dj:ny + 1 + dj]
    # face externa (x_out) e cabeceiras: ar ambiente; canais: 0,6·h; face interna do tubo: núcleo
    borda(ativo & ~viz(1, 0) & (X > x_in + 0.02 * (x_out - x_in)), res, h_conv, T_amb)
    borda(ativo & (~viz(0, 1) | ~viz(0, -1)), res, h_conv, T_amb)
    for (c0, c1) in canais:
        borda(ativo & ~viz(1, 0) & (X < c0) & (X > c0 - res * 1.5), res, 0.6 * h_conv, T_amb)
        borda(ativo & ~viz(-1, 0) & (X >= c1) & (X < c1 + res * 1.5), res, 0.6 * h_conv, T_amb)
    face_tubo = ativo & ~viz(-1, 0) & (X < x_in + res * 1.5)
    borda(face_tubo, res, 1 / (d["c"] / 0.03 + 1 / 6.0), T_nucleo)    # ar parado núcleo–tubo + contato
    T = _fd_solver(nx, ny, res, res, k, q, (Gc, Tc), T_amb)
    cu_mask = k == K_CU
    return dict(T=T, X=X, Z=Z, k=k, Tmax=float(np.nanmax(T)), Tmed_cobre=float(np.nanmean(T[cu_mask])),
                pos_max=(float(X.ravel()[np.nanargmax(T)] - xs0), float(Z.ravel()[np.nanargmax(T)])))


def mapa_nucleo(d, ch, nuc, p_face_xz=None, T_amb=50.0, h_conv=12.0, res=2e-3):
    """Plano das lâminas: condução no plano, troca pelas faces da frente/trás (2h/b por volume) e bordas expostas."""
    a, b, ww, hw = d["a"], d["b"], d["ww"], d["hw"]
    W, H = 3 * a + 2 * ww, 2 * a + hw
    M = nuc["_M"]
    nx, ny = int(W / res), int(H / res)
    xc = (np.arange(nx) + 0.5) * W / nx
    zc = (np.arange(ny) + 0.5) * H / ny
    X, Z = np.meshgrid(xc, zc, indexing="ij")
    ferro = np.ones((nx, ny), bool)
    for i in range(2):
        x0 = a + i * (a + ww)
        ferro &= ~((X > x0) & (X < x0 + ww) & (Z > a) & (Z < a + hw))
    for i, y0, y1 in M.gaps:
        ferro &= ~((X > M.xl[i]) & (X < M.xl[i] + a) & (Z > y0) & (Z < y1))
    # densidade de perdas → grade (vizinho mais próximo dos centróides)
    from scipy.spatial import cKDTree
    cen = M.m.cent[M.ferro]
    tr = cKDTree(cen)
    _, ix = tr.query(np.c_[X[ferro], Z[ferro]])
    q = np.zeros((nx, ny))
    q[ferro] = nuc["densidade_Wm3"][ix]
    if p_face_xz is not None:                                  # perdas do fluxo normal (W/m² de face, frente+trás) → volume
        q[ferro] += p_face_xz(X[ferro], Z[ferro]) / b
    # formulação por unidade de espessura do pacote (÷ b): faces frente/trás → 2h/b por volume; bordas → h por comprimento
    k = np.where(ferro, K_FE_PLANO, 0.0)
    culatra = (Z < a) | (Z > a + hw)
    f_face = np.where(culatra, 0.7, 1.0)                        # quadros em U cobrem parte das faces das culatras
    Gc = np.where(ferro, 2 * h_conv * f_face / b * res * res, 0.0)
    viz = lambda di, dj: np.pad(ferro, 1)[1 + di:nx + 1 + di, 1 + dj:ny + 1 + dj]
    externo = (X < res) | (X > W - res) | (Z < res) | (Z > H - res)
    for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        ext = ferro & ~viz(di, dj)
        Gc[ext] += h_conv * res * np.where(externo[ext], 1.0, 0.3)   # contorno externo; janelas cobertas pelas bobinas
    T = _fd_solver(nx, ny, res, res, k * 1.0, q, (Gc, np.full((nx, ny), T_amb)), T_amb)
    return dict(T=T, X=X, Z=Z, Tmax=float(np.nanmax(T)), Tmed=float(np.nanmean(T[ferro])),
                pos_max=(float(X.ravel()[np.nanargmax(T)]), float(Z.ravel()[np.nanargmax(T)])))


# ===================================================================================================== 3) espraiamento 3D
def espraiamento_3d(d, g_est, wf, h=0.02, log=print, aniso=True, com_estrutura=True, com_pele=True, so_L=False, debug=False):
    """Meio modelo 3D (y ≥ 0, simetria B_n = 0 no plano y = 0). Núcleo laminado ANISOTRÓPICO (μ no plano = 4000 μ0, μ no
    empilhamento ≈ μ0/(1−kf)); quadros e tirantes de aço como fronteira de blindagem (B_n = 0, limite de alta frequência);
    pele refinada nas faces do núcleo junto às juntas. Devolve perdas do fluxo normal às lâminas e da estrutura."""
    from netgen.occ import Box, Pnt, Glue, OCCGeometry, Z, X, Y, WorkPlane, Axes, Cylinder
    from ngsolve import (HCurl, BilinearForm, LinearForm, GridFunction, curl, dx, Mesh, CoefficientFunction, x, y, z,
                         IfPos, sqrt, InnerProduct, TaskManager, Preconditioner, solvers, Integrate)
    from .ind_verificacao import geometria, _rret_face
    t0 = time.time()
    a, b, ww, hw = d["a"], d["b"], d["ww"], d["hw"]
    W, H = 3 * a + 2 * ww, 2 * a + hw
    G = geometria(d)
    kf = d["chapa_dados"]["kf"]
    r_in, r_out = d["c"] + d["tube"], d["c"] + d["build"] - d["wrap"]
    zc0 = a + (hw - d["hc"]) / 2
    zb0 = zc0 + (d["hc"] - d["hf"]) / 2
    zb1 = zb0 + d["hf"]
    pele = 3e-3
    nucleo = Box(Pnt(0, 0, 0), Pnt(W, b / 2, H))
    for (x0, z0, x1, z1) in G["janelas"]:
        nucleo = nucleo - Box(Pnt(x0, -1, z0), Pnt(x1, 1, z1))
    gaps, peles = [], []
    for (x0, z0, x1, z1) in G["gaps"]:
        gb = Box(Pnt(x0, 0, z0), Pnt(x1, b / 2, z1))
        nucleo = nucleo - gb
        gb.solids.name = "gap"
        gb.solids.maxh = max((z1 - z0) / 1.5, 2.5e-3)
        gaps.append(gb)
    for (x0, z0, x1, z1) in (G["gaps"] if com_pele else []):
        for (za, zb_) in ((z0 - 0.03, z0), (z1, z1 + 0.03)):
            pb = Box(Pnt(x0, b / 2 - pele, za), Pnt(x1, b / 2, zb_))
            pb = pb * nucleo
            nucleo = nucleo - pb
            pb.solids.name = "ferro"
            pb.solids.maxh = 2.5e-3
            peles.append(pb)
    nucleo.solids.name = "ferro"
    nucleo.solids.maxh = h * 0.6
    bobinas = []
    for i in range(3):
        xc = a / 2 + i * (a + ww)
        ext = _rret_face(WorkPlane(Axes((xc, 0, zb0), n=Z, h=X)), a + 2 * r_out, b + 2 * r_out, r_out)
        inn = _rret_face(WorkPlane(Axes((xc, 0, zb0), n=Z, h=X)), a + 2 * r_in, b + 2 * r_in, r_in)
        anel = (ext - inn).Extrude(zb1 - zb0) * Box(Pnt(-1, 0, -1), Pnt(2, 1, 2))
        anel.solids.name = f"bob{i}"
        anel.solids.maxh = h * 0.6
        bobinas.append(anel)
    mg = 0.45 * max(W, H)
    ar = Box(Pnt(-mg, 0, -mg), Pnt(W + mg, b / 2 + mg, H + mg))
    ar.solids.name = "ar"
    ar.solids.maxh = 0.09
    ar.faces.name = "fora"
    ar.faces.Min(Y).name = "sim"
    # estrutura de aço carbono (meia, y > 0) – material MAGNÉTICO (μr 200) dentro do domínio; abas recortadas para não
    # sobrepor a alma; buchas omitidas (pequenas). Perdas: impedância de superfície com o H tangencial DENTRO do aço.
    estr = []
    y_w = g_est["y_w"] * 1e-3
    t_q = g_est["t"] * 1e-3
    for nome, mat, (x0, x1, y0, y1, z0, z1) in (g_est["caixas"] if com_estrutura else []):
        if mat == "estrutura" and y0 >= 0 and "Quadro" in nome:
            y0m, y1m = y0 * 1e-3, y1 * 1e-3
            if "aba" in nome:
                y0m = max(y0m, y_w + t_q)
            bx = Box(Pnt(x0 * 1e-3, y0m, z0 * 1e-3), Pnt(x1 * 1e-3, y1m, z1 * 1e-3))
            estr.append(("caixa", nome, (x0 * 1e-3, x1 * 1e-3, y0m, y1m, z0 * 1e-3, z1 * 1e-3), bx))
    for nome, mat, (xc_, yc_, z0, z1), r, _ in (g_est["cilindros"] if com_estrutura else []):
        if yc_ > 0 and nome.startswith("Tirante"):
            cy = Cylinder(Pnt(xc_ * 1e-3, yc_ * 1e-3, z0 * 1e-3), Z, r * 1e-3, (z1 - z0) * 1e-3)
            estr.append(("cil", nome, (xc_ * 1e-3, yc_ * 1e-3, z0 * 1e-3, z1 * 1e-3, r * 1e-3), cy))
    for s in [nucleo] + gaps + peles + bobinas:
        s.faces[Y < 1e-7].name = "sim"                      # plano de simetria também nas faces do núcleo, gaps e bobinas
        ar = ar - s
    solidos_aco = []
    for e in estr:
        e[3].solids.name = "aco"
        e[3].solids.maxh = 0.014
        ar = ar - e[3]
        solidos_aco.append(e[3])
    geo = Glue([ar, nucleo] + gaps + peles + bobinas + solidos_aco)
    with TaskManager():
        mesh = Mesh(OCCGeometry(geo).GenerateMesh(maxh=h * 3))
    log(f"     3D espraiamento: malha {mesh.ne} tetraedros ({time.time() - t0:.0f} s)")
    nu_pl = 1 / (MU0 * 4000)
    nu_y = ((1 - kf) / MU0 + kf / (MU0 * 4000)) if aniso else nu_pl
    nu_fe = CoefficientFunction((nu_pl, 0, 0, 0, nu_y, 0, 0, 0, nu_pl), dims=(3, 3))
    nu0 = CoefficientFunction((1 / MU0, 0, 0, 0, 1 / MU0, 0, 0, 0, 1 / MU0), dims=(3, 3))
    nu_aco = CoefficientFunction(tuple(np.eye(3).ravel() / (MU0 * MU_ACO_ESTR)), dims=(3, 3))
    nu = mesh.MaterialCF({"ferro": nu_fe, "aco": nu_aco}, default=nu0)
    fes = HCurl(mesh, order=1, dirichlet="fora|sim", nograds=True)
    u, v = fes.TnT()
    A = BilinearForm(fes)
    A += InnerProduct(nu * curl(u), curl(v)) * dx + 1e-6 / MU0 * u * v * dx
    pre = Preconditioner(A, "bddc")
    with TaskManager():
        A.Assemble()
    area = (r_out - r_in) * (zb1 - zb0)
    J0 = d["N"] / area
    sols = []
    Ts = []
    with TaskManager():
        for i in range(3):
            xc = a / 2 + i * (a + ww)
            dxv = IfPos(x - xc - a / 2, x - xc - a / 2, IfPos(xc - a / 2 - x, xc - a / 2 - x, 0))
            dyv = IfPos(y - b / 2, y - b / 2, IfPos(-b / 2 - y, -b / 2 - y, 0))
            rho = sqrt(dxv * dxv + dyv * dyv)
            Tm = IfPos(rho - r_out, 0, IfPos(rho - r_in, J0 * (r_out - rho), J0 * (r_out - r_in)))
            Tm = Tm * IfPos(z - zb0, 1, 0) * IfPos(zb1 - z, 1, 0)
            Tv = CoefficientFunction((0, 0, Tm))
            Ts.append(Tv)
            f = LinearForm(fes)
            f += InnerProduct(Tv, curl(v)) * dx
            f.Assemble()
            gf = GridFunction(fes)
            solvers.CG(mat=A.mat, pre=pre.mat, rhs=f.vec, sol=gf.vec, tol=1e-10, maxsteps=5000, printrates=debug)
            sols.append(gf)
        if debug:
            print({m: Integrate(CoefficientFunction(1), mesh, definedon=mesh.Materials(m)) for m in set(mesh.GetMaterials())})
        Lm = np.array([[2 * Integrate(InnerProduct(Ts[j], curl(sols[k])), mesh) for k in range(3)] for j in range(3)])
    Lp = np.array([Lm[k, k] - 0.5 * sum(Lm[k, j] for j in range(3) if j != k) for k in range(3)])
    log(f"     3D espraiamento: L (com estrutura, núcleo anisotrópico) = {', '.join(f'{v * 1e6:.1f}' for v in Lp)} µH ({time.time() - t0:.0f} s)")
    Bcf = [curl(s_) for s_ in sols]
    if so_L:
        return dict(L3d=Lp, n_el=mesh.ne)

    def _av(k, pts):
        try:
            mp = mesh(pts[:, 0], pts[:, 1], pts[:, 2])
            return np.asarray(Bcf[k](mp)).reshape(-1, 3)
        except Exception:
            if len(pts) == 1:
                return np.full((1, 3), np.nan)                 # ponto fora da malha (dentro de outra peça) → ignorado
            m = len(pts) // 2
            return np.vstack([_av(k, pts[:m]), _av(k, pts[m:])])

    def avaliar_B(k, P):
        out = np.zeros((len(P), 3))
        for s0 in range(0, len(P), 20000):
            out[s0:s0 + 20000] = _av(k, P[s0:s0 + 20000])
        return out
    # ------------------------------------------------ fluxo normal às lâminas: modos espaciais com blindagem exata
    # Em cada peça (lâminas separadas pela junta), o fluxo normal B_n na face é decomposto em modos sen(mπx/Lx)·sen(nπz/Lz).
    # Para cada modo (k) e cada linha do espectro (ω), no pacote anisotrópico (σ no plano, μp no plano, μn no empilhamento):
    #   α² = k²·μp/μn + jωσμp   (decaimento para dentro do pacote: espalhamento estático + blindagem por correntes parasitas)
    #   P/A = σ ω² |B_n|² / (4 k² Re α)          (perda por área de face, integrada na profundidade)
    sig = 1 / d["chapa_dados"]["rho"] * kf
    I, fh = wf["I"], wf["fh"]
    mu_p, mu_n = 4000 * MU0, MU0 / ((1 - kf) + kf / 4000)
    pecas = [("culatra inferior", 0, W, 0, a), ("culatra superior", 0, W, H - a, H)]
    for i in range(3):
        zs = sorted([(z0, z1) for (x0, z0, x1, z1) in G["gaps"] if abs(x0 - i * (a + ww)) < 1e-6])
        if len(zs) >= 2:
            pecas.append((f"coluna {'UVW'[i]}", i * (a + ww), i * (a + ww) + a, zs[0][1], zs[-1][0]))
    res = 2e-3
    perdas_pecas = {}
    mapa = []
    sel_h = np.abs(I).sum(0) > 1e-6 * np.abs(I).max()
    fhs, Is = fh[sel_h], I[:, sel_h]
    w = 2 * np.pi * fhs
    for nome, x0, x1, z0, z1 in pecas:
        Lx, Lz = x1 - x0, z1 - z0
        nx, nz = max(int(Lx / res), 8), max(int(Lz / res), 8)
        xc = x0 + (np.arange(nx) + 0.5) * Lx / nx
        zc = z0 + (np.arange(nz) + 0.5) * Lz / nz
        Xg, Zg = np.meshgrid(xc, zc, indexing="ij")
        P = np.c_[Xg.ravel(), np.full(Xg.size, b / 2 + 0.3e-3), Zg.ravel()]
        Bn = np.array([np.nan_to_num(avaliar_B(k, P)[:, 1]).reshape(nx, nz) for k in range(3)])
        # coeficientes de seno (DST-II) – modos que respeitam as bordas da lâmina
        from scipy.fft import dstn
        Mm, Nm = min(nx, 60), min(nz, 60)
        coef = np.array([dstn(Bn[k], type=2, norm="forward")[:Mm, :Nm] * 4 for k in range(3)])
        m_ = np.arange(1, Mm + 1)[:, None]
        n_ = np.arange(1, Nm + 1)[None, :]
        k2 = (m_ * np.pi / Lx) ** 2 + (n_ * np.pi / Lz) ** 2
        area_modo = Lx * Lz / 4                                      # ∫ sen² sen² dA
        # |Σ_k I_k(f) c_k|² para cada modo e linha (vetorizado por blocos de linhas)
        Ptot = 0.0
        qmap = np.zeros((Mm, Nm))
        for s0 in range(0, len(w), 400):
            ww_ = w[s0:s0 + 400]
            Bmf = np.einsum("kh,kmn->hmn", Is[:, s0:s0 + 400], coef)    # amplitude do modo em cada linha
            al = np.sqrt(k2[None] * mu_p / mu_n + 1j * ww_[:, None, None] * sig * mu_p)
            mu_ef = 1j * np.sqrt(k2)[None] * mu_p / al                   # permeância de superfície (correção do B_n)
            corr = np.abs(mu_ef / (MU0 + mu_ef)) * (1 + MU0 / (np.sqrt(mu_p * mu_n)))
            pa = sig * ww_[:, None, None] ** 2 * np.abs(Bmf * corr) ** 2 / (4 * k2[None] * al.real)
            qmap += pa.sum(0)
        Ptot = float(2 * (qmap * area_modo).sum())                        # frente + trás
        perdas_pecas[nome] = Ptot
        mapa.append((nome, x0, x1, z0, z1, Ptot))
    P_normal = sum(perdas_pecas.values())
    log(f"     3D espraiamento: fluxo normal às lâminas = {P_normal:.1f} W ({time.time() - t0:.0f} s)")
    # ------------------------------------------------ estrutura: impedância de superfície  P = ½ Rs |Ht|²
    Rs = np.sqrt(2 * np.pi * np.maximum(fh, 1e-9) * MU_ACO_ESTR * MU0 / (2 * SIG_ACO_ESTR))
    G3 = np.einsum("h,kh,lh->kl", Rs, I, np.conj(I)).real
    off = -0.3e-3                                                   # pontos 0,3 mm DENTRO do aço
    P_estr = {}
    for tipo, nome, geo_, _ in estr:
        pts, nrm, dA = [], [], []
        if tipo == "caixa":
            x0, x1, y0, y1, z0, z1 = geo_
            dims = dict(x=(x0, x1), y=(y0, y1), z=(z0, z1))
            for eixo in "xyz":
                outros = [e for e in "xyz" if e != eixo]
                for lado, val in ((-1, dims[eixo][0] - off), (1, dims[eixo][1] + off)):
                    u0, u1 = dims[outros[0]]
                    v0, v1 = dims[outros[1]]
                    nu_, nv_ = max(int((u1 - u0) / 4e-3), 2), max(int((v1 - v0) / 4e-3), 2)
                    us = u0 + (np.arange(nu_) + 0.5) * (u1 - u0) / nu_
                    vs = v0 + (np.arange(nv_) + 0.5) * (v1 - v0) / nv_
                    U, V = np.meshgrid(us, vs, indexing="ij")
                    c = {eixo: np.full(U.size, val), outros[0]: U.ravel(), outros[1]: V.ravel()}
                    pts.append(np.c_[c["x"], c["y"], c["z"]])
                    n = np.zeros(3)
                    n["xyz".index(eixo)] = lado
                    nrm.append(np.tile(n, (U.size, 1)))
                    dA.append(np.full(U.size, (u1 - u0) / nu_ * (v1 - v0) / nv_))
        else:
            xc_, yc_, z0, z1, r = geo_
            nth, nzz = 24, max(int((z1 - z0) / 6e-3), 2)
            th = (np.arange(nth) + 0.5) * 2 * np.pi / nth
            zz = z0 + (np.arange(nzz) + 0.5) * (z1 - z0) / nzz
            TH, ZZ = np.meshgrid(th, zz, indexing="ij")
            rr = r + off
            pts.append(np.c_[xc_ + rr * np.cos(TH.ravel()), yc_ + rr * np.sin(TH.ravel()), ZZ.ravel()])
            nrm.append(np.c_[np.cos(TH.ravel()), np.sin(TH.ravel()), np.zeros(TH.size)])
            dA.append(np.full(TH.size, 2 * np.pi * r / nth * (z1 - z0) / nzz))
        P = np.vstack(pts)
        Nn = np.vstack(nrm)
        dAa = np.concatenate(dA)
        ok = (P[:, 1] > 0) & (P[:, 0] > -mg) & (P[:, 0] < W + mg) & (P[:, 2] > -mg) & (P[:, 2] < H + mg)
        P, Nn, dAa = P[ok], Nn[ok], dAa[ok]
        Ht = []
        for k in range(3):
            Bk = avaliar_B(k, P) / (MU0 * MU_ACO_ESTR)
            Bk = Bk - (Bk * Nn).sum(1)[:, None] * Nn                  # componente tangencial (H dentro do aço)
            Ht.append(np.nan_to_num(Bk))
        S = np.array([[(Ht[k] * Ht[l]).sum(1) @ dAa for l in range(3)] for k in range(3)])
        P_estr[nome] = P_estr.get(nome, 0.0) + float(2 * 0.5 * (G3 * S).sum())   # ×2: metade da frente (simetria)
    P_est_tot = sum(P_estr.values())
    log(f"     3D espraiamento: quadros e tirantes = {P_est_tot:.1f} W ({time.time() - t0:.0f} s)")
    return dict(P_normal=P_normal, P_normal_pecas=perdas_pecas, P_estrutura=P_est_tot, P_estrutura_pecas=P_estr,
                L3d_estrutura=Lp, n_el=mesh.ne, tempo=time.time() - t0, mapa=mapa,
                param_reacao=float(MU0 * sig * d["chapa_dados"]["esp_mm"] * 1e-3 * a * 2 * np.pi * d["requisitos"]["fs"]))


def _lap1d(n, h):
    import scipy.sparse as sp
    return sp.diags([np.full(n - 1, 1.0), np.full(n, -2.0), np.full(n - 1, 1.0)], [-1, 0, 1]) / (h * h)


# ===================================================================================================== orquestrador
def avaliar(d, proj, cat, log=print, fazer_3d=True, iter_termica=4, wf=None):
    """Executa a avaliação avançada completa e devolve resultados + comparação com o método da plataforma."""
    from .ind_desenhos import geo_mm
    t0 = time.time()
    r = d["requisitos"]
    ch = d["chapa_dados"]
    amb = float(d["termico"].get("amb_painel_C", 50.0))
    h_conv = float(d["termico"].get("h_conv", 12.0))
    out = dict(tempos={})
    if wf is None:                     # v1.13.0: bancos/sintonizados passam as formas de onda do espectro harmônico
        wf = formas_onda(proj, cat, r["I1"])
    out["formas_onda"] = dict(f1=wf["f1"], Ipk=wf["Ipk"], I_rip_rms=wf["I_rip_rms"], n=wf["n"])
    log(f"     Avançado: formas de onda do circuito – f1 {wf['f1']:g} Hz, pico {wf['Ipk']:.0f} A, ondulação {wf['I_rip_rms']:.1f} A rms")
    t = time.time()
    nuc = perdas_nucleo_tempo(d, ch, wf)
    out["tempos"]["nucleo"] = time.time() - t
    log(f"     Avançado: núcleo no tempo = {nuc['total']:.0f} W (parasitas {nuc['parasitas']:.0f}, excesso {nuc['excesso']:.0f}, "
        f"histerese/rainflow {nuc['histerese']:.0f}); B pico {nuc['Bpk_max_T']:.2f} T")
    t = time.time()
    cu = cobre_espectro(d, wf, r["fs"])
    out["tempos"]["cobre"] = time.time() - t
    e3 = None
    if fazer_3d:
        try:
            from .ind_verificacao import disponivel
            if disponivel():
                g = geo_mm(d)
                e3 = espraiamento_3d(d, g["est"], wf, log=log)
                out["tempos"]["3d"] = e3["tempo"]
        except Exception as e:
            log(f"     Avançado: 3D não concluído ({type(e).__name__}: {e}) – usando a fórmula de Lee para o entreferro")
            out["erro_3d"] = f"{type(e).__name__}: {e}"
    P_norm = e3["P_normal"] if e3 else float(d["perdas"]["nucleo_entreferro"])
    P_estr = e3["P_estrutura"] if e3 else 0.0
    # ---------------- iteração eletrotérmica
    cond = d.get("cond", "CU")
    T0 = 40 + d.get("alvo", 100.0)                            # temperatura em que ρT foi calculada (pré-dimensionamento)
    T_cu = T0
    hist = []
    p_face = None
    if e3:
        mp = {m[0]: m for m in e3["mapa"]}

        def p_face(X, Zz, _mp=mp):
            q = np.zeros_like(X)
            for nome, x0, x1, z0, z1, P in _mp.values():
                sel = (X >= x0) & (X <= x1) & (Zz >= z0) & (Zz <= z1)
                # concentra junto às juntas (30 mm de cada extremidade da peça na direção z)
                perto = sel & ((Zz - z0 < 0.03) | (z1 - Zz < 0.03)) if nome.startswith("coluna") else sel & ((Zz > z1 - 0.03) if "inferior" in nome else (Zz < z0 + 0.03))
                area = max(perto.sum(), 1)
                q[perto] += P / area / ((x1 - x0) * 0 + 1)
            return q
    mn = mb = None
    for it in range(iter_termica):
        kr = rho_rel(cond, T_cu, T0)
        P60 = cu["P60"] * kr
        Paf = cu["P_AF"] * kr ** 0.5                           # regime pelicular: R_CA ∝ √ρ
        cu_it = dict(cu)
        cu_it["P_cond_V"] = cu["P_cond_V"] * kr
        res_n = 2e-3
        mn = mapa_nucleo(d, ch, nuc, (lambda X, Zz: p_face(X, Zz) / (res_n * res_n)) if p_face else None, amb, h_conv, res=res_n)
        Tcol = mn["Tmed"]
        mb = mapa_bobina(d, cu_it, amb, Tcol, h_conv)
        hist.append(dict(it=it + 1, T_cu_med=mb["Tmed_cobre"], T_cu_max=mb["Tmax"], T_fe_max=mn["Tmax"], P60=P60, P_AF=Paf))
        if abs(mb["Tmed_cobre"] - T_cu) < 0.5:
            T_cu = mb["Tmed_cobre"]
            break
        T_cu = mb["Tmed_cobre"]
    perdas = dict(enrolamento_60Hz=P60, enrolamento_AF=Paf, nucleo_tempo=nuc["total"], fluxo_normal_laminas=P_norm,
                  estrutura=P_estr)
    perdas["total"] = sum(perdas.values())
    out.update(perdas=perdas, nucleo={k: v for k, v in nuc.items() if not k.startswith("_") and k != "densidade_Wm3"},
               cobre=dict(freqs=cu["freqs"].tolist(), R_lat=cu["R_lat"].tolist(), R_cen=cu["R_cen"].tolist(),
                          P60_T0=cu["P60"], PAF_T0=cu["P_AF"], hcond_mm=(cu["hcond"] or 0) * 1e3),
               termico=dict(iteracoes=hist, T_cobre_med_C=mb["Tmed_cobre"], T_cobre_max_C=mb["Tmax"], pos_max_bobina_mm=[v * 1e3 for v in mb["pos_max"]],
                            T_nucleo_max_C=mn["Tmax"], T_nucleo_med_C=mn["Tmed"], pos_max_nucleo_mm=[v * 1e3 for v in mn["pos_max"]],
                            amb_C=amb, h_conv=h_conv),
               e3={k: (v.tolist() if isinstance(v, np.ndarray) else v) for k, v in (e3 or {}).items() if k != "mapa"},
               plataforma=dict(perdas={k: float(v) for k, v in d["perdas"].items()}, termico=dict(d["termico"])))
    out["_mapas"] = (mb, mn, wf, nuc)
    out["tempos"]["total"] = time.time() - t0
    lim_p = float(d.get("perdas_limite_w") or 0)
    cl_lim = float(d["termico"].get("limite_temp_C", 180))
    out["avisos"] = []
    if perdas["total"] > d["perdas"]["total"] * 1.05:
        out["avisos"].append(f"Método avançado prevê {perdas['total']:.0f} W, acima dos {d['perdas']['total']:.0f} W do projeto.")
    if mb["Tmax"] > cl_lim - 20:
        out["avisos"].append(f"Ponto quente da bobina {mb['Tmax']:.0f} °C – menos de 20 K abaixo do limite da classe ({cl_lim:.0f} °C).")
    log(f"     Avançado: perdas {perdas['total']:.0f} W (plataforma {d['perdas']['total']:.0f} W); bobina média {mb['Tmed_cobre']:.0f} °C, "
        f"ponto quente {mb['Tmax']:.0f} °C; núcleo máx. {mn['Tmax']:.0f} °C ({out['tempos']['total']:.0f} s)")
    return out


def figuras(av, pasta, cod):
    """PNG: formas de onda, densidade de perdas no núcleo, mapas térmicos."""
    import os
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    mb, mn, wf, nuc = av["_mapas"]
    arqs = {}
    fig, ax = plt.subplots(2, 1, figsize=(10, 6.4))
    t = wf["t"] * 1e3
    for k, cor in zip(range(3), ("#1f4e79", "#c55a11", "#548235")):
        ax[0].plot(t, wf["i"][k], lw=0.8, color=cor, label="UVW"[k])
    ax[0].set_ylabel("Corrente no indutor (A)")
    ax[0].set_title("Correntes das 3 fases – simulação do circuito no pior ponto (1 período)")
    ax[0].legend(loc="upper right", fontsize=8)
    ax[0].grid(alpha=0.3)
    sel = wf["fh"] > 0
    ax[1].semilogy(wf["fh"][sel] / 1e3, np.abs(wf["I"][0][sel]) / math.sqrt(2) + 1e-6, lw=0.6, color="#1f4e79")
    ax[1].set_xlim(0, min(wf["fh"].max(), 6 * 4000) / 1e3 * 1.0)
    ax[1].set_ylim(1e-2, None)
    ax[1].set_xlabel("Frequência (kHz)")
    ax[1].set_ylabel("A rms (fase U)")
    ax[1].grid(alpha=0.3, which="both")
    fig.tight_layout()
    arqs["formas"] = os.path.join(pasta, f"Avancado_formas_onda_{cod}.png")
    fig.savefig(arqs["formas"], dpi=150)
    plt.close(fig)
    fig, ax = plt.subplots(1, 2, figsize=(12, 5.2), gridspec_kw=dict(width_ratios=[2.3, 1]))
    im = ax[0].pcolormesh(mn["X"] * 1e3, mn["Z"] * 1e3, mn["T"], shading="auto", cmap="inferno")
    ax[0].set_aspect("equal")
    ax[0].set_title(f"Núcleo – plano das lâminas (máx. {mn['Tmax']:.0f} °C)")
    ax[0].set_xlabel("mm")
    plt.colorbar(im, ax=ax[0], label="°C", shrink=0.8)
    im2 = ax[1].pcolormesh(mb["X"] * 1e3, mb["Z"] * 1e3, mb["T"], shading="auto", cmap="inferno")
    ax[1].set_aspect("equal")
    ax[1].set_title(f"Bobina V – corte (máx. {mb['Tmax']:.0f} °C)")
    ax[1].set_xlabel("mm")
    plt.colorbar(im2, ax=ax[1], label="°C", shrink=0.8)
    fig.tight_layout()
    arqs["termico"] = os.path.join(pasta, f"Avancado_mapa_termico_{cod}.png")
    fig.savefig(arqs["termico"], dpi=150)
    plt.close(fig)
    return arqs


def salvar(av, arq):
    import json
    js = {k: v for k, v in av.items() if not k.startswith("_")}
    json.dump(js, open(arq, "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=lambda o: o.tolist() if hasattr(o, "tolist") else float(o))
    return arq


def relatorio(d, av, arq, figs):
    from .auditoria import Rel, _Doc, _esc
    from reportlab.platypus import Paragraph
    R = Rel()
    tit = "Análise avançada do indutor – formas de onda do circuito, 3D e mapa térmico"
    R.f.append(Paragraph(_esc(tit), R.st["CAPA"]))
    r = d["requisitos"]
    fo = av["formas_onda"]
    if r.get("aplicacao"):
        R.p(f"Reator {r['L']*1e6:.0f} µH / {r['In']:.0f} A ({_esc(r['aplicacao'])}). As correntes das 3 fases são montadas a partir do "
            f"espectro harmônico de projeto do banco (fundamental + harmônicas de tensão da rede, f1 = {fo['f1']:g} Hz, pico {fo['Ipk']:.0f} A, "
            f"harmônicas {fo['I_rip_rms']:.1f} A rms, em fase com a fundamental – conservador para o pico) e alimentam diretamente o "
            "cálculo do reator – o mesmo acoplamento circuito → campo que os softwares comerciais fazem.")
    else:
        R.p(f"Indutor {r['L']*1e6:.0f} µH / {r['In']:.0f} A. As correntes das 3 fases vêm da simulação do filtro no pior ponto de operação "
            f"(f1 = {fo['f1']:g} Hz, pico {fo['Ipk']:.0f} A, ondulação {fo['I_rip_rms']:.1f} A rms) e alimentam diretamente o cálculo do "
            "indutor – o mesmo acoplamento circuito → campo que os softwares comerciais fazem.")
    R.h1("Perdas – método avançado × método do projeto")
    P, Pp = av["perdas"], av["plataforma"]["perdas"]
    lin = [("Cobre – fundamental", f"{Pp.get('enrolamento_60Hz', 0):.0f} W", f"{P['enrolamento_60Hz']:.0f} W",
            "R CA na temperatura calculada (iteração eletrotérmica)"),
           ("Cobre – alta frequência", f"{Pp.get('enrolamento_AF', 0):.0f} W", f"{P['enrolamento_AF']:.0f} W",
            "R CA em 8 frequências × todas as linhas do espectro"),
           ("Núcleo (60 Hz + AF)", f"{Pp.get('nucleo_60Hz', 0) + Pp.get('nucleo_AF', 0):.0f} W", f"{P['nucleo_tempo']:.0f} W",
            "B(t) por elemento: parasitas exatas + excesso de Bertotti + histerese por rainflow com polarização"),
           ("Junto aos entreferros", f"{Pp.get('nucleo_entreferro', 0):.0f} W (Lee)", f"{P['fluxo_normal_laminas']:.0f} W",
            "3D: fluxo normal às lâminas, modos espaciais com blindagem por correntes parasitas"),
           ("Quadros e tirantes de aço", "–", f"{P['estrutura']:.1f} W", "3D: aço magnético, impedância de superfície"),
           ("TOTAL", f"{Pp['total']:.0f} W", f"{P['total']:.0f} W", "")]
    R.tab(["Parcela", "Projeto", "Avançado", "Como foi calculado"], lin, [3.0, 1.6, 1.6, 6.0], 7)
    nu = av["nucleo"]
    R.p(f"Núcleo no tempo: parasitas {nu['parasitas']:.0f} W, excesso {nu['excesso']:.0f} W, histerese {nu['histerese']:.0f} W; B de pico "
        f"{nu['Bpk_max_T']:.2f} T (mediana {nu['Bpk_p50_T']:.2f} T).")
    if av.get("e3"):
        e = av["e3"]
        R.p(f"Modelo 3D (NGSolve, {e['n_el']} tetraedros, núcleo anisotrópico, quadros e tirantes de aço): L = "
            + ", ".join(f"{v*1e6:.1f}" for v in e["L3d_estrutura"]) + " µH por fase. Perdas por peça: "
            + "; ".join(f"{k} {v:.1f} W" for k, v in e["P_normal_pecas"].items()) + ".")
        R.p("Estrutura: " + "; ".join(f"{k} {v:.1f} W" for k, v in e["P_estrutura_pecas"].items())
            + f". A alma dos quadros termina 20 mm antes da junta coluna–culatra (aço magnético rente ao entreferro desviaria fluxo e aqueceria).")
    R.h1("Temperaturas – mapa térmico por diferenças finitas")
    T, Tp = av["termico"], av["plataforma"]["termico"]
    R.tab(["Grandeza", "Projeto (modelo de nós)", "Avançado (mapa)"], [
        ("Bobina – elevação média", f"{Tp['elev_bobina_K']:.0f} K", f"{T['T_cobre_med_C'] - T['amb_C']:.0f} K"),
        ("Bobina – ponto quente", f"{Tp['ponto_quente_C']:.0f} °C (estimado)", f"{T['T_cobre_max_C']:.0f} °C (a {T['pos_max_bobina_mm'][0]:.0f} mm da coluna)"),
        ("Núcleo – elevação", f"{Tp['elev_nucleo_K']:.0f} K", f"máx. {T['T_nucleo_max_C'] - T['amb_C']:.0f} K / média {T['T_nucleo_med_C'] - T['amb_C']:.0f} K"),
        ("Limite da classe", f"{Tp['limite_temp_C']:.0f} °C", f"{Tp['limite_temp_C']:.0f} °C")], [4, 3.2, 4], 7.5)
    R.p(f"Ambiente {T['amb_C']:.0f} °C, convecção {T['h_conv']:.0f} W/m²K (mesma do projeto). Iterações eletrotérmicas: "
        + "; ".join(f"{h['it']}: cobre {h['T_cu_med']:.0f} °C" for h in T["iteracoes"]) + ".")
    for k in ("termico", "formas"):
        if figs.get(k):
            R.img(figs[k], 170)
    if av.get("avisos"):
        R.h2("Avisos")
        R.bul(av["avisos"])
    R.h1("Limites do método (o que ainda depende do protótipo)")
    R.bul(["Coeficientes da chapa (histerese/excesso) vêm do P1,7/50 do catálogo e da separação de Bertotti; o fator de polarização "
           "dos laços menores é da literatura.",
           "A convecção (h) é a mesma do projeto; o mapa térmico mostra a DISTRIBUIÇÃO e o ponto quente, não substitui o ensaio.",
           "O 3D trata a estrutura como aço magnético linear (μr 200) com impedância de superfície."])
    doc = _Doc(arq, tit, rotulo="ANÁLISE AVANÇADA – ELECTRIC SERVICE")
    doc.multiBuild(R.f)
    return arq
