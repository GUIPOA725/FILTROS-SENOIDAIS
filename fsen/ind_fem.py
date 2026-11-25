"""Elementos finitos 2D magnetostáticos para o indutor trifásico de 3 colunas do filtro senoidal (v1.10.0).

Formulação: potencial vetor Az, triângulos lineares (P1), −∇·(ν∇Az) = Jz, Az = 0 no contorno externo (caixa de ar).
Corte no plano da janela (x horizontal, y vertical), profundidade = empilhamento do núcleo.
- Não-linear (curva B-H do aço GO) por substituição sucessiva com relaxação – usado para saturação no pico.
- Linear (permeabilidade incremental) – usado para indutância, matriz 3×3, ondulação de alta frequência e perdas parasitas.
- Perdas parasitas nos condutores (proximidade + espraiamento do entreferro): P = (σω²/2)∫|A − Ā|² dA · ℓ  (aproximação de
  baixa frequência, válida para espessura do condutor ≲ profundidade de penetração; o projeto limita a espessura a isso).
Sem dependências além de numpy/scipy.
"""
import math
import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla

MU0 = 4e-7 * math.pi

# Curva B-H típica de aço silício de grão orientado (direção de laminação), ex.: M120-27S / 27ZH100
BH_GO = (np.array([0, 8, 15, 25, 40, 80, 200, 1000, 3000, 10000, 30000, 100000.0]),
         np.array([0, 1.0, 1.4, 1.6, 1.7, 1.78, 1.86, 1.94, 1.99, 2.04, 2.08, 2.15]))


# v1.28.0 (REQ-SEN-022, auditoria NC-1.3): curva CONSERVADORA para a prova de linearidade – nos cantos e juntas o fluxo atravessa
# o grão da chapa GO (permeabilidade bem menor e joelho mais cedo). Indução da curva GO × 0,85 e μr limitado a 8000 (≈ chapa de grão
# não orientado). Se a indutância passa com esta curva, passa com folga na chapa real.
BH_CONSERVADORA = (BH_GO[0], BH_GO[1] * 0.85)
MU_MAX_CONSERVADOR = 8000.0


def _graded(p, q, h_l, h_r, hmax, r=1.25):
    """Pontos entre p e q (exclui p, inclui q) com tamanho crescendo de h_l (perto de p) e h_r (perto de q) até hmax."""
    L = q - p
    if L <= 0:
        return []
    pts_l, x, h = [], p, h_l
    pts_r, y, k = [], q, h_r
    # avança dos dois lados até se encontrarem
    while True:
        if x + h >= y - k - 1e-12:
            break
        if h <= k:
            x += h
            pts_l.append(x)
            h = min(h * r, hmax)
        else:
            y -= k
            pts_r.append(y)
            k = min(k * r, hmax)
    return pts_l + sorted(pts_r) + [q]


def linhas(chaves, hmin_map, hmax, faixa=None, hmax_fora=None):
    """chaves: coordenadas obrigatórias; hmin_map: dict coord→tamanho local mínimo.
    faixa=(lo, hi): fora dela (ar distante) usa hmax_fora (malha mais grossa)."""
    c = sorted(set(round(v, 7) for v in chaves))
    out = [c[0]]
    for p, q in zip(c[:-1], c[1:]):
        hm = hmax
        if faixa and hmax_fora and (q <= faixa[0] + 1e-9 or p >= faixa[1] - 1e-9):
            hm = hmax_fora
        hl = min(hmin_map.get(p, hm), q - p)
        hr = min(hmin_map.get(q, hm), q - p)
        out += _graded(p, q, hl, hr, hm)
    return np.array(out)


class Malha:
    def __init__(self, xs, ys):
        self.xs, self.ys = xs, ys
        nx, ny = len(xs), len(ys)
        X, Y = np.meshgrid(xs, ys)          # (ny, nx)
        self.p = np.column_stack([X.ravel(), Y.ravel()])
        idx = np.arange(nx * ny).reshape(ny, nx)
        a, b, c, d = idx[:-1, :-1].ravel(), idx[:-1, 1:].ravel(), idx[1:, 1:].ravel(), idx[1:, :-1].ravel()
        self.t = np.vstack([np.column_stack([a, b, c]), np.column_stack([a, c, d])])
        P = self.p[self.t]                  # (ne,3,2)
        self.cent = P.mean(axis=1)
        x1, y1 = P[:, 0, 0], P[:, 0, 1]
        x2, y2 = P[:, 1, 0], P[:, 1, 1]
        x3, y3 = P[:, 2, 0], P[:, 2, 1]
        self.area = 0.5 * ((x2 - x1) * (y3 - y1) - (x3 - x1) * (y2 - y1))
        self.bcoef = np.column_stack([y2 - y3, y3 - y1, y1 - y2])
        self.ccoef = np.column_stack([x3 - x2, x1 - x3, x2 - x1])
        bnd = np.zeros(nx * ny, bool)
        bnd[idx[0, :]] = bnd[idx[-1, :]] = bnd[idx[:, 0]] = bnd[idx[:, -1]] = True
        self.livre = np.where(~bnd)[0]
        # padrão de esparsidade
        self.I = np.repeat(self.t, 3, axis=1).ravel()
        self.J = np.tile(self.t, (1, 3)).ravel()
        self.ke = (np.einsum("ei,ej->eij", self.bcoef, self.bcoef) + np.einsum("ei,ej->eij", self.ccoef, self.ccoef)) / \
            (4 * self.area)[:, None, None]

    def rigidez(self, nu):
        v = (self.ke * nu[:, None, None]).ravel()
        n = len(self.p)
        return sp.csr_matrix((v, (self.I, self.J)), shape=(n, n))

    def carga(self, Je):
        n = len(self.p)
        f = np.zeros(n)
        np.add.at(f, self.t.ravel(), np.repeat(Je * self.area / 3.0, 3))
        return f

    def campo(self, A):
        Ae = A[self.t]
        dAdx = (self.bcoef * Ae).sum(1) / (2 * self.area)
        dAdy = (self.ccoef * Ae).sum(1) / (2 * self.area)
        return dAdy, -dAdx           # Bx, By


class ModeloIndutor:
    """Geometria (m):  g = dict(a, b, hw, ww, gaps=[g_limb0, g_limb1, g_limb2] (comprimento TOTAL por coluna), ng,
    condutores=[dict(x0,x1,y0,y1, fase, lado(+1/-1))], margem)."""

    def __init__(self, g, hmax=6e-3, hgap=None, hcond=None):
        self.g = g
        a, hw, ww, ng = g["a"], g["hw"], g["ww"], g["ng"]
        W, H = 3 * a + 2 * ww, 2 * a + hw
        M = g.get("margem", 0.6 * max(W, H))
        self.W, self.H = W, H
        self.xl = [i * (a + ww) for i in range(3)]          # borda esquerda de cada coluna
        # entreferros: "distribuido" = ng por coluna, centrados em alturas igualmente espaçadas na janela (multigap);
        # "culatra" = 2 por coluna, nas juntas coluna–culatra (em cima e embaixo) – padrão dos fabricantes nacionais (v1.11.1)
        self.gaps = []                                      # (coluna, y0, y1)
        self.pos_gap = g.get("pos_gap", "distribuido")
        for i in range(3):
            gi = g["gaps"][i] / ng
            for k in range(ng):
                if self.pos_gap == "culatra":
                    y0 = a if k % 2 == 0 else a + hw - gi
                    self.gaps.append((i, y0, y0 + gi))
                else:
                    yc = a + hw * (k + 0.5) / ng
                    self.gaps.append((i, yc - gi / 2, yc + gi / 2))
        gmin = min(y1 - y0 for _, y0, y1 in self.gaps)
        hg = hgap or max(gmin / 4, 1e-4)
        xs = [-M, W + M, 0, W] + [x for x0 in self.xl for x in (x0, x0 + a)]
        ys = [-M, H + M, 0, a, a + hw, H]
        hx, hy = {}, {}
        for _, y0, y1 in self.gaps:
            ys += [y0, y1]
            hy[round(y0, 7)] = hy[round(y1, 7)] = hg
        for x0 in self.xl:
            hx[round(x0, 7)] = hx[round(x0 + a, 7)] = min(1.5e-3, 4 * hg)
        for c in g["condutores"]:
            xs += [c["x0"], c["x1"]]
            ys += [c["y0"], c["y1"]]
            t = c["x1"] - c["x0"]
            for v in (c["x0"], c["x1"]):
                hx[round(v, 7)] = min(hx.get(round(v, 7), 1), max(t / 2, 2e-4) if hcond is None else hcond)
            if hcond is not None:                           # v1.11.8: refino também na altura do condutor (verificação)
                for v in (c["y0"], c["y1"]):
                    hy[round(v, 7)] = min(hy.get(round(v, 7), 1), hcond)
        for v in (a, a + hw):
            hy[round(v, 7)] = min(hy.get(round(v, 7), 1), 2e-3)
        # ar distante: malha até 4× mais grossa (a borda das bobinas externas define a faixa fina)
        cx0 = min([0.0] + [c["x0"] for c in g["condutores"]]) - 0.02
        cx1 = max([W] + [c["x1"] for c in g["condutores"]]) + 0.02
        xs += [cx0, cx1]
        ys += [-0.02, H + 0.02]
        self.m = Malha(linhas(xs, hx, hmax, (cx0, cx1), 4 * hmax), linhas(ys, hy, hmax, (-0.02, H + 0.02), 4 * hmax))
        cx, cy = self.m.cent[:, 0], self.m.cent[:, 1]
        ferro = (cx > 0) & (cx < W) & (cy > 0) & (cy < H)
        janela = np.zeros_like(ferro)
        for i in range(2):
            x0 = self.xl[i] + a
            janela |= (cx > x0) & (cx < x0 + ww) & (cy > a) & (cy < a + hw)
        ferro &= ~janela
        self.gap_el = np.zeros_like(ferro)
        for i, y0, y1 in self.gaps:
            self.gap_el |= (cx > self.xl[i]) & (cx < self.xl[i] + a) & (cy > y0) & (cy < y1)
        ferro &= ~self.gap_el
        self.ferro = ferro
        self.cond = -np.ones(len(cx), int)
        for j, c in enumerate(g["condutores"]):
            self.cond[(cx > c["x0"]) & (cx < c["x1"]) & (cy > c["y0"]) & (cy < c["y1"])] = j
        self.area_cond = np.array([self.m.area[self.cond == j].sum() for j in range(len(g["condutores"]))])

    # ------------------------------------------------------------------------------------------------------------
    def _J(self, correntes):
        """correntes: [Ia, Ib, Ic] (A) → densidade por elemento."""
        Je = np.zeros(len(self.m.area))
        for j, c in enumerate(self.g["condutores"]):
            sel = self.cond == j
            Je[sel] = c["lado"] * correntes[c["fase"]] / self.area_cond[j]
        return Je

    def resolver(self, correntes, mu_r=None, bh=BH_GO, iters=60, tol=5e-4, relax=0.6, mu_max=60000.0):
        """mu_r=None → não-linear com a curva B-H (substituição sucessiva com relaxação adaptativa); senão linear."""
        m = self.m
        nu = np.full(len(m.area), 1 / MU0)
        nu[self.ferro] = 1 / (MU0 * (mu_r or 3000))
        f = m.carga(self._J(correntes))
        A = np.zeros(len(m.p))
        L = m.livre
        dif_ant = 1e9
        self.convergiu, self.iters = True, 0
        for it in range(1 if mu_r else iters):
            K = m.rigidez(nu)
            A[L] = spla.spsolve(K[L][:, L].tocsc(), f[L])
            if mu_r:
                break
            Bx, By = m.campo(A)
            Bm = np.hypot(Bx, By)[self.ferro]
            Hm = np.interp(Bm, bh[1], bh[0])
            alto = Bm > bh[1][-1]
            Hm[alto] = bh[0][-1] + (Bm[alto] - bh[1][-1]) / MU0
            nu_new = np.where(Bm > 1e-6, Hm / np.maximum(Bm, 1e-6), 1 / (MU0 * 3000))
            nu_new = np.clip(nu_new, 1 / (MU0 * mu_max), 1 / MU0)
            dif = float(np.max(np.abs(nu_new - nu[self.ferro]) / nu[self.ferro]))
            lam = self.lambda_fases(A)
            if it > 0 and np.max(np.abs(lam - lam_ant)) <= tol * max(np.max(np.abs(lam)), 1e-12) and dif < 0.5:
                self.iters = it + 1
                break                                   # fluxo concatenado estabilizado (critério global, robusto a cantos)
            lam_ant = lam
            if dif > dif_ant:
                relax = max(relax * 0.5, 0.05)
            dif_ant = dif
            # relaxação em escala logarítmica (ν varia em ordens de grandeza na saturação)
            nu[self.ferro] = np.exp((1 - relax) * np.log(nu[self.ferro]) + relax * np.log(nu_new))
            self.iters = it + 1
            if dif < tol:
                break
        else:
            self.convergiu = mu_r is not None
        self.A, self.nu = A, nu
        return A

    def lambda_fases(self, A):
        """Fluxo concatenado de cada fase por unidade de profundidade (Wb/m)."""
        m = self.m
        Ae = A[m.t].mean(1)
        lam = np.zeros(3)
        for j, c in enumerate(self.g["condutores"]):
            sel = self.cond == j
            Abar = (Ae[sel] * m.area[sel]).sum() / self.area_cond[j]
            lam[c["fase"]] += c["lado"] * Abar
        return lam

    def matriz_L(self, mu_r=4000):
        """Matriz 3×3 de indutância 2D (por metro de profundidade) – linear."""
        m = self.m
        nu = np.full(len(m.area), 1 / MU0)
        nu[self.ferro] = 1 / (MU0 * mu_r)
        K = m.rigidez(nu)
        L = m.livre
        lu = spla.splu(K[L][:, L].tocsc())
        Lm = np.zeros((3, 3))
        self._sol_unit = []
        for k in range(3):
            cur = [0, 0, 0]
            cur[k] = 1.0
            f = m.carga(self._J(cur))
            A = np.zeros(len(m.p))
            A[L] = lu.solve(f[L])
            self._sol_unit.append(A)
            Lm[:, k] = self.lambda_fases(A)
        return Lm

    def perdas_parasitas(self, A, f_hz, sigma, ell_por_cond):
        """Perda média (W) nos condutores para um campo senoidal de amplitude A (solução linear), frequência f.
        ell_por_cond: comprimento efetivo de cada seção de condutor (m)."""
        m = self.m
        w = 2 * math.pi * f_hz
        Ae = A[m.t].mean(1)
        P = np.zeros(len(self.g["condutores"]))
        for j in range(len(P)):
            sel = self.cond == j
            Abar = (Ae[sel] * m.area[sel]).sum() / self.area_cond[j]
            P[j] = 0.5 * sigma * w * w * (((Ae[sel] - Abar) ** 2) * m.area[sel]).sum() * ell_por_cond[j]
        return P

    def B(self, A=None):
        Bx, By = self.m.campo(self.A if A is None else A)
        return Bx, By


# ---------------------------------------------------------------------------------------------------------------------
# Harmônico no tempo com correntes induzidas (correntes parasitas reais, com blindagem/efeito pelicular)
def perdas_harmonico(M, f_hz, correntes, sigma, ell_por_cond, mu_r=1500.0):
    """Compatível: uma excitação. Ver perdas_harmonico_multi para várias excitações com 1 fatoração."""
    P, A = perdas_harmonico_multi(M, f_hz, [correntes], sigma, ell_por_cond, mu_r)
    return P[0], A[0]


def perdas_harmonico_multi(M, f_hz, lista_correntes, sigma, ell_por_cond, mu_r=1500.0):
    """Resolve (K + jωσM)A − σB·u = 0 ;  −jωσBᵀA + σS·u = I_j  (corrente total imposta em cada seção de condutor).
    correntes: [Ia, Ib, Ic] amplitudes (complexas permitidas) da fase; cada seção leva lado·I_fase.
    Retorna perdas (W) por seção de condutor, já multiplicadas pelo comprimento efetivo."""
    m = M.m
    n = len(m.p)
    w = 2 * math.pi * f_hz
    nu = np.full(len(m.area), 1 / MU0)
    nu[M.ferro] = 1 / (MU0 * mu_r)
    K = m.rigidez(nu).tocsr()
    ce = M.cond >= 0
    t = m.t[ce]
    ar = m.area[ce]
    Me = np.array([[2, 1, 1], [1, 2, 1], [1, 1, 2]]) / 12.0
    Iv = np.repeat(t, 3, axis=1).ravel()
    Jv = np.tile(t, (1, 3)).ravel()
    Mv = (ar[:, None, None] * Me[None]).ravel() * sigma
    Ms = sp.csr_matrix((Mv, (Iv, Jv)), shape=(n, n))
    nc = len(M.g["condutores"])
    # B: n × nc  (∫N_i dS sobre o condutor j) · σ
    rows = t.ravel()
    cols = np.repeat(M.cond[ce], 3)
    vals = np.repeat(ar / 3.0, 3) * sigma
    B = sp.csr_matrix((vals, (rows, cols)), shape=(n, nc))
    S = sp.diags(M.area_cond * sigma)
    L = m.livre
    A11 = (K + 1j * w * Ms)[L][:, L]
    A12 = -B[L]
    A21 = -1j * w * B[L].T
    sysm = sp.bmat([[A11, A12], [A21, S]]).tocsc()
    lu = spla.splu(sysm)
    Ps, As = [], []
    for correntes in lista_correntes:
        rhs = np.zeros(len(L) + nc, complex)
        for j, c in enumerate(M.g["condutores"]):
            rhs[len(L) + j] = c["lado"] * correntes[c["fase"]]
        x = lu.solve(rhs)
        A = np.zeros(n, complex)
        A[L] = x[:len(L)]
        u = x[len(L):]
        # J nodal por elemento: σ(−jωA + u_j)
        Jn = sigma * (-1j * w * A[t] + u[M.cond[ce]][:, None])
        q = np.einsum("ei,ij,ej->e", Jn.conj(), Me, Jn).real * ar      # ∫|J|² dS
        P = np.zeros(nc)
        np.add.at(P, M.cond[ce], q)
        Ps.append(0.5 * P / sigma * np.asarray(ell_por_cond))
        As.append(A)
    return Ps, As
