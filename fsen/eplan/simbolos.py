"""Símbolos IEC 60617 para as folhas (v1.15.0). Coordenadas em mm; corrente de cima para baixo.
Comando: um caminho vertical por símbolo (passo 10 mm). Força: três polos a ±PF do eixo (L1, L2, L3).
Cada função desenha, registra a posição do dispositivo (referências cruzadas) e devolve o y de saída."""
import math

PF = 6.0          # espaçamento entre polos na força (mm)
FS = 2.0          # altura de texto padrão (mm)


def _tag(f, x, y, tag, sub="", lado=1):
    f.txt(x + lado * 4.0, y, tag, fs=2.4, ha="left" if lado > 0 else "right", va="center", negrito=True)
    if sub:
        f.txt(x + lado * 4.0, y - 3.0, sub, fs=1.7, ha="left" if lado > 0 else "right", va="center", cor="0.25")


def borne(f, x, y, regua, n, lado=1):
    f.circ(x, y, 0.9, lw=0.25)
    f.txt(x - lado * 1.6, y, f"{regua}:{n}", fs=1.6, ha="right" if lado > 0 else "left", va="center", cor="0.2")


# ------------------------------------------------------------------------------------ comando
def contato(f, x, y, tag, nf=False, b=("13", "14"), ref=None, atuador=None, l=10.0, sub=""):
    """Contato NA (nf=False) ou NF, comprimento l. atuador: None | 'emerg' | 'giro' | 'termo' | 'pulso'."""
    a, c = y - (l - 6) / 2, y - (l - 6) / 2 - 6
    f.lin(x, y, x, a)
    f.lin(x, c, x, y - l)
    if nf:
        f.lin(x, c, x + 2.6, a + 0.6, lw=0.4, cam="SIMBOLOS")
        f.lin(x, a, x + 3.0, a, lw=0.4, cam="SIMBOLOS")
    else:
        f.lin(x, c, x - 2.8, a + 0.4, lw=0.4, cam="SIMBOLOS")
    f.txt(x - 1.2, y - 0.8, b[0], fs=1.5, ha="right", va="top", cor="0.3")
    f.txt(x - 1.2, y - l + 0.8, b[1], fs=1.5, ha="right", va="bottom", cor="0.3")
    xm = x - 1.3
    if atuador == "emerg":
        f.lin(xm - 1.5, (a + c) / 2, xm - 6, (a + c) / 2, tracejado=True, lw=0.25, cam="SIMBOLOS")
        f.arco(xm - 7.5, (a + c) / 2, 1.8, 90, 270, lw=0.4)
        f.lin(xm - 7.5, (a + c) / 2 + 1.8, xm - 7.5, (a + c) / 2 - 1.8, lw=0.4, cam="SIMBOLOS")
    elif atuador == "giro":
        f.lin(xm - 1.5, (a + c) / 2, xm - 6, (a + c) / 2, tracejado=True, lw=0.25, cam="SIMBOLOS")
        f.pol([(xm - 6, (a + c) / 2 - 1.5), (xm - 7.2, (a + c) / 2 - 1.5), (xm - 7.2, (a + c) / 2 + 1.5), (xm - 8.4, (a + c) / 2 + 1.5)])
    elif atuador == "termo":
        f.ret(xm - 8, (a + c) / 2 - 1.6, 4, 3.2, lw=0.3)
        f.txt(xm - 6, (a + c) / 2, "θ", fs=2.2, ha="center", va="center")
        f.lin(xm - 4, (a + c) / 2, xm - 1.5, (a + c) / 2, tracejado=True, lw=0.25, cam="SIMBOLOS")
    elif atuador == "pulso":
        f.lin(xm - 1.5, (a + c) / 2, xm - 6, (a + c) / 2, tracejado=True, lw=0.25, cam="SIMBOLOS")
        f.pol([(xm - 6, (a + c) / 2 + 1.5), (xm - 7.2, (a + c) / 2 + 1.5), (xm - 7.2, (a + c) / 2 - 1.5), (xm - 6, (a + c) / 2 - 1.5)])
    _tag(f, x, (a + c) / 2 + 1.5, tag, sub)
    if ref:
        f.txt(x + 4.0, (a + c) / 2 - 3.2, ref, fs=1.6, ha="left", va="center", cor="#1f4e8c")
    return y - l


def bobina(f, x, y, tag, sub="", b=("A1", "A2"), l=12.0, contatos=None):
    """Bobina (retângulo 6×4) + espelho de contatos (lista de (papel, texto)) abaixo."""
    yc = y - l / 2
    f.lin(x, y, x, yc + 2)
    f.ret(x - 3, yc - 2, 6, 4, lw=0.45)
    f.lin(x, yc - 2, x, y - l)
    f.txt(x - 1.2, y - 0.8, b[0], fs=1.5, ha="right", va="top", cor="0.3")
    f.txt(x - 1.2, y - l + 0.8, b[1], fs=1.5, ha="right", va="bottom", cor="0.3")
    _tag(f, x, yc + 1, tag, sub)
    f.proj.registra(tag, "bobina", f, x)
    if contatos:
        yy = y - l - 2
        for papel, txt in contatos:
            f.txt(x + 1.5, yy, txt, fs=1.4, ha="left", va="top", cor="0.25")
            f.txt(x + 17, yy, f.proj.ref(tag, papel), fs=1.4, ha="left", va="top", cor="#1f4e8c")
            yy -= 2.4
    return y - l


def lampada(f, x, y, tag, sub="", cor="vermelha", l=12.0):
    yc = y - l / 2
    f.lin(x, y, x, yc + 2.5)
    f.circ(x, yc, 2.5, lw=0.4)
    d = 2.5 / math.sqrt(2)
    f.lin(x - d, yc - d, x + d, yc + d, lw=0.3, cam="SIMBOLOS")
    f.lin(x - d, yc + d, x + d, yc - d, lw=0.3, cam="SIMBOLOS")
    f.lin(x, yc - 2.5, x, y - l)
    _tag(f, x, yc + 1, tag, sub or cor)
    return y - l


def motor_vent(f, x, y, tag, sub="", l=12.0):
    yc = y - l / 2
    f.lin(x, y, x, yc + 3)
    f.circ(x, yc, 3, lw=0.45)
    f.txt(x, yc, "M", fs=2.4, ha="center", va="center", negrito=True)
    f.txt(x, yc - 1.9, "1~", fs=1.4, ha="center", va="center")
    f.lin(x, yc - 3, x, y - l)
    _tag(f, x, yc + 1, tag, sub)
    return y - l


def disjuntor_cmd(f, x, y, tag, sub="", l=10.0, polos=1):
    a, c = y - 2, y - 8
    for k in range(polos):
        xx = x + k * PF
        f.lin(xx, y, xx, a)
        f.lin(xx, c, xx, y - l)
        f.lin(xx, c, xx - 2.6, a + 0.6, lw=0.4, cam="SIMBOLOS")
        f.lin(xx - 0.9, a - 0.9, xx + 0.9, a + 0.9, lw=0.35, cam="SIMBOLOS")
        f.lin(xx - 0.9, a + 0.9, xx + 0.9, a - 0.9, lw=0.35, cam="SIMBOLOS")
    if polos > 1:
        f.lin(x - 1.3, (a + c) / 2, x + (polos - 1) * PF - 1.3, (a + c) / 2, tracejado=True, lw=0.25, cam="SIMBOLOS")
    _tag(f, x + (polos - 1) * PF, (a + c) / 2 + 1, tag, sub)
    return y - l


def trafo_cmd(f, x, y, tag, sub=""):
    """Transformador de comando (primário 2 fios em x-3/x+3 em cima; secundário embaixo)."""
    f.circ(x, y - 4, 3.2, lw=0.4)
    f.circ(x, y - 8.5, 3.2, lw=0.4)
    _tag(f, x + 1.5, y - 6.2, tag, sub)
    return y - 11.7


def controlador(f, x, y, w, h, tag, sub, terminais_sup=(), terminais_inf=()):
    """Caixa do controlador / relé com terminais (lista de (dx, rótulo))."""
    f.ret(x, y - h, w, h, lw=0.45)
    f.txt(x + w / 2, y - h / 2 + 1.2, tag, fs=2.6, ha="center", va="center", negrito=True)
    f.txt(x + w / 2, y - h / 2 - 2.2, sub, fs=1.7, ha="center", va="center", cor="0.25")
    for dx, r in terminais_sup:
        f.txt(x + dx, y - 1.0, r, fs=1.4, ha="center", va="top", cor="0.3")
    for dx, r in terminais_inf:
        f.txt(x + dx, y - h + 1.0, r, fs=1.4, ha="center", va="bottom", cor="0.3")


# ------------------------------------------------------------------------------------ força (3 polos)
def _polos(x):
    return (x - PF, x, x + PF)


def seccionadora_fusivel(f, x, y, tag, sub="", l=22.0):
    """Chave seccionadora-fusível tripolar (NH): lâmina + fusível em cada polo."""
    for xx in _polos(x):
        f.lin(xx, y, xx, y - 3, cam="POTENCIA", lw=0.5)
        f.lin(xx, y - 9, xx - 2.8, y - 3.6, lw=0.45, cam="SIMBOLOS")
        f.ret(xx - 1.1, y - 17, 2.2, 6, lw=0.4)
        f.lin(xx, y - 9, xx, y - 11, cam="POTENCIA", lw=0.5)
        f.lin(xx, y - 11, xx, y - 17, lw=0.25, cam="SIMBOLOS")
        f.lin(xx, y - 17, xx, y - l, cam="POTENCIA", lw=0.5)
    f.lin(x - PF - 1.4, y - 6.2, x + PF - 1.4, y - 6.2, tracejado=True, lw=0.25, cam="SIMBOLOS")
    _tag(f, x + PF, y - 8, tag, sub)
    f.proj.registra(tag, "polo", f, x)
    return y - l


def disjuntor_3p(f, x, y, tag, sub="", l=16.0):
    for xx in _polos(x):
        f.lin(xx, y, xx, y - 3, cam="POTENCIA", lw=0.5)
        f.lin(xx, y - 10, xx - 2.8, y - 3.6, lw=0.45, cam="SIMBOLOS")
        f.lin(xx - 0.9, y - 3 - 0.9, xx + 0.9, y - 3 + 0.9, lw=0.35, cam="SIMBOLOS")
        f.lin(xx - 0.9, y - 3 + 0.9, xx + 0.9, y - 3 - 0.9, lw=0.35, cam="SIMBOLOS")
        f.lin(xx, y - 10, xx, y - l, cam="POTENCIA", lw=0.5)
    f.lin(x - PF - 1.4, y - 6.5, x + PF - 1.4, y - 6.5, tracejado=True, lw=0.25, cam="SIMBOLOS")
    _tag(f, x + PF, y - 7, tag, sub)
    f.proj.registra(tag, "polo", f, x)
    return y - l


def contator_3p(f, x, y, tag, sub="", l=16.0):
    """Contatos principais 1-2 / 3-4 / 5-6 com o semicírculo de contator; referência à bobina."""
    for k, xx in enumerate(_polos(x)):
        f.lin(xx, y, xx, y - 4, cam="POTENCIA", lw=0.5)
        f.arco(xx, y - 4 - 0.9, 0.9, 90, 270, lw=0.35)
        f.lin(xx, y - 10, xx - 2.8, y - 4.6, lw=0.45, cam="SIMBOLOS")
        f.lin(xx, y - 10, xx, y - l, cam="POTENCIA", lw=0.5)
        f.txt(xx + 0.6, y - 0.6, str(2 * k + 1), fs=1.4, ha="left", va="top", cor="0.3")
        f.txt(xx + 0.6, y - l + 0.6, str(2 * k + 2), fs=1.4, ha="left", va="bottom", cor="0.3")
    f.lin(x - PF - 1.4, y - 7.2, x + PF - 1.4, y - 7.2, tracejado=True, lw=0.25, cam="SIMBOLOS")
    _tag(f, x + PF, y - 6.5, tag, sub)
    f.txt(x + PF + 4, y - 12, f.proj.ref(tag, "bobina"), fs=1.6, ha="left", va="center", cor="#1f4e8c")
    f.proj.registra(tag, "polo", f, x)
    return y - l


def tc(f, x, y, tag, sub=""):
    """Transformador de corrente no polo x (círculo atravessado)."""
    f.circ(x, y, 2.0, lw=0.4)
    f.lin(x + 2.0, y, x + 5, y, lw=0.3, cam="SIMBOLOS")
    f.txt(x + 5.5, y + 0.2, tag, fs=1.9, ha="left", va="center", negrito=True)
    if sub:
        f.txt(x + 5.5, y - 2.4, sub, fs=1.5, ha="left", va="center", cor="0.25")


def reator_3f(f, x, y, tag, sub="", l=26.0, termostato_ref=None):
    """Reator trifásico (3 enrolamentos em série nos polos) com núcleo e termostato NF indicado."""
    for xx in _polos(x):
        f.lin(xx, y, xx, y - 5, cam="POTENCIA", lw=0.5)
        for k in range(4):
            f.arco(xx, y - 6.25 - k * 2.5, 1.25, 270, 90, lw=0.45)
        f.lin(xx, y - 15, xx, y - l, cam="POTENCIA", lw=0.5)
    f.lin(x - PF - 2.6, y - 5, x - PF - 2.6, y - 15, lw=0.45, cam="SIMBOLOS")
    f.lin(x - PF - 3.4, y - 5, x - PF - 3.4, y - 15, lw=0.45, cam="SIMBOLOS")
    f.ret(x - PF - 5, y - 18, 2 * PF + 10, 15.5, lw=0.25, tracejado=True)
    _tag(f, x + PF + 5, y - 7, tag, sub)
    f.txt(x + PF + 9, y - 13.5, (lambda: "θ NF → " + ((termostato_ref() if callable(termostato_ref) else termostato_ref) or "")),
          fs=1.5, ha="left", va="center", cor="#1f4e8c")
    f.proj.registra(tag, "polo", f, x)
    return y - l


def capacitor_3f(f, x, y, tag, sub="", l=20.0):
    """Capacitor trifásico em triângulo (interno) com resistores de descarga."""
    for xx in _polos(x):
        f.lin(xx, y, xx, y - 4, cam="POTENCIA", lw=0.5)
    f.ret(x - PF - 3, y - l, 2 * PF + 6, l - 4, lw=0.4)
    cx, cy, r = x, y - 4 - (l - 4) / 2, 4.5
    pts = [(cx - r, cy - r * 0.6), (cx + r, cy - r * 0.6), (cx, cy + r * 0.9)]
    for xx, (px, py) in zip(_polos(x), (pts[0], pts[2], pts[1])):
        f.lin(xx, y - 4, px if xx != x else cx, py, lw=0.3, cam="SIMBOLOS")
    for (a, b) in ((pts[0], pts[1]), (pts[1], pts[2]), (pts[2], pts[0])):
        mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
        ang = math.atan2(b[1] - a[1], b[0] - a[0])
        ux, uy = math.cos(ang), math.sin(ang)
        nx, ny = -uy, ux
        g = 0.6
        f.lin(a[0], a[1], mx - ux * g, my - uy * g, lw=0.3, cam="SIMBOLOS")
        f.lin(b[0], b[1], mx + ux * g, my + uy * g, lw=0.3, cam="SIMBOLOS")
        for s in (-g, g):
            f.lin(mx + ux * s - nx * 1.5, my + uy * s - ny * 1.5, mx + ux * s + nx * 1.5, my + uy * s + ny * 1.5, lw=0.5, cam="SIMBOLOS")
    _tag(f, x + PF + 3, y - 7, tag, sub)
    f.proj.registra(tag, "polo", f, x)
    return y - l


def barramento(f, x0, x1, ys, nomes=("L1", "L2", "L3", "PE"), lw=0.9):
    for y, n in zip(ys, nomes):
        f.lin(x0, y, x1, y, lw=lw, cam="POTENCIA", cor="#7a1f1f" if n != "PE" else "#2e7d32")
        f.txt(x0 - 1.5, y, n, fs=2.0, ha="right", va="center", negrito=True)


def derivacao(f, x, y_bus, y_ate):
    """Ponto de derivação do barramento até y_ate."""
    f.ponto(x, y_bus)
    f.lin(x, y_bus, x, y_ate, cam="POTENCIA", lw=0.5)


def terra(f, x, y):
    f.lin(x, y, x, y - 2)
    for k, w in enumerate((2.4, 1.6, 0.8)):
        f.lin(x - w, y - 2 - k * 0.8, x + w, y - 2 - k * 0.8, lw=0.35, cam="SIMBOLOS")
