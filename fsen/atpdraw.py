"""Desenho da MESMA rede do deck FSEN no ATPDraw (formato XML do ATPDraw 7, abre direto no programa).

A rede é montada a partir dos mesmos objetos usados para gerar o deck .atp (ParamCircuito + saída de gerar_deck):
  TACS (SVPWM, objetos FORTRAN 98 idênticos ao deck) → 3 fontes TACS tipo 60 (VLA/VLB/VLC) → coletor 3φ
  → sonda V (inversor) → sonda I → L1 (RLC3) // Rp → nó CP (sonda V) → banco (RLCD3 Δ ou RLCY3 Y)
  → [L2] → cabo (células π: série RLC3, Cfase-terra RLCY3 aterrado, Cfase-fase RLCD3) → MT (sonda V)
  → sonda I → MI → Rm+Lm (RLCY3, estrela NMOT, 1 MΩ à terra) + Norton (ACSOURCE de corrente) + Cwf/3 à carcaça.
Unidades no desenho: XOPT = COPT = 0 → L em mH, C em µF (igual ao deck).
"""
from __future__ import annotations

import math
import re
from typing import Any, Dict, List
from xml.sax.saxutils import escape, quoteattr

from .simulacao import _n_secoes


def _asc(t):
    import unicodedata
    t = str(t).replace("µ", "u").replace("–", "-").replace("Ω", "Ohm")
    return unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode()


def _rot(x, y, ang):
    """Orientação do ATPDraw (eixo y para baixo), conferida no programa: 90 → (y, −x), 180 → (−x, y), 270 → (−y, x)."""
    return {0: (x, y), 90: (y, -x), 180: (-x, y), 270: (-y, x)}[ang % 360]   # 180 = espelho horizontal


def _g(x: float) -> str:
    return f"{x:.10g}"


class _Desenho:
    def __init__(self):
        self.obj: List[Any] = []
        self.pontos = set()

    # ------------------------------------------------------------------ primitivas
    def comp(self, nome, x, y, nos, dados=(), angulo=0, caption=None, comentario=None, ordem=None, extra="",
             probe=None, fases_probe=3, datastring=None, oculto=False, cap_pos=None):
        caption = _asc(caption) if caption else caption
        comentario = _asc(comentario) if comentario else comentario
        datastring = _asc(datastring) if datastring is not None else None
        cpx, cpy = cap_pos or ((12, -6) if angulo % 180 else (-20, -22))
        cap = (f' Caption={quoteattr(caption)} CapAngl="0" CapPosX="{cpx}" CapPosY="{cpy}"' if caption else "")
        s = [f'    <comp Name="{nome}"' + (' Hidden="true"' if oculto else "") + cap + ">"]
        attrs = (f' Order="{ordem}"' if ordem is not None else "") + (f' Angle="{angulo}"' if angulo else "")
        s.append(f'      <comp_content{attrs} PosX="{x}" PosY="{y}" HighRes="false"{extra} Icon="default">')
        for n in nos:
            if not n.get("off"):                     # posições no XML = padrão da biblioteca (ângulo 0)
                rx, ry = _rot(n["px"], n["py"], angulo)
                self.pontos.add((x + rx, y + ry))
            a = (f' Value={quoteattr(n.get("valor", ""))}' + (' UserNamed="true"' if n.get("valor") else "")
                 + (f' NumPhases="{n["fases"]}"' if n.get("fases", 1) > 1 else "") + (f' Kind="{n.get("kind", 1)}"' if n.get("kind", 1) is not None else "")
                 + f' PosX="{n["px"]}" PosY="{n["py"]}" NamePosX="{4 if n["px"] >= 0 else -4}" NamePosY="0"'
                 + (' Ground="1"' if n.get("terra") else "") + (' Disabled="true"' if n.get("off") else "")
                 + (' Internal="true"' if n.get("interno") else ""))
            s.append(f'        <node Name="{n["nome"]}"{a}/>')
        for d in dados:
            s.append(f'        <data Name="{d[0]}" Unit="{d[1]}" Value="{d[2]}"/>')
        if comentario:
            s.append(f"        <comment>{escape(comentario)}</comment>")
        if datastring is not None:
            s.append(f"        <datastring>{escape(datastring)}</datastring>")
        s.append("      </comp_content>")
        if probe:
            s.append('      <probe CaptureSteadyState="false" OnScreen="0" ScreenFormat="0" ScreenShow="0" CurrNode="false"'
                     ' FontSize="0" Precision="0" TimeOnScreen="false">')
            for k in range(1, fases_probe + 1):
                s.append(f'        <monitor Phase="{k}"/>')
            s.append("      </probe>")
        s.append("    </comp>")
        self.obj.append("\n".join(s))

    def fio(self, x1, y1, x2, y2, fases=3):
        if (x1, y1) != (x2, y2):
            self.obj.append(("fio", x1, y1, x2, y2, fases))
            self.pontos.update([(x1, y1), (x2, y2)])

    def serializar(self) -> List[str]:
        """Fios são quebrados em todo ponto de derivação (o ATPDraw só conecta em extremidades/nós)."""
        out = []
        for o in self.obj:
            if isinstance(o, str):
                out.append(o)
                continue
            _, x1, y1, x2, y2, fases = o
            meio = sorted([pt for pt in self.pontos if pt not in ((x1, y1), (x2, y2))
                           and (x2 - x1) * (pt[1] - y1) == (y2 - y1) * (pt[0] - x1)
                           and min(x1, x2) <= pt[0] <= max(x1, x2) and min(y1, y2) <= pt[1] <= max(y1, y2)],
                          key=lambda pt: abs(pt[0] - x1) + abs(pt[1] - y1))
            seq = [(x1, y1)] + meio + [(x2, y2)]
            nf = f' NumPhases="{fases}"' if fases > 1 else ""
            for (a, b), (c, d) in zip(seq, seq[1:]):
                out.append(f'    <conn>\n      <conn_content{nf} Pos1X="{a}" Pos1Y="{b}" Pos2X="{c}" Pos2Y="{d}" Color="0"/>\n    </conn>')
        return out

    # ------------------------------------------------------------------ componentes
    def rlc3(self, x, y, R, L_mH, C_uF, n_in="", n_out="", caption=None, comentario=None, angulo=0):
        pin, pout = (-20, 0), (20, 0)
        dados = []
        for k in (1, 2, 3):
            dados += [(f"R_{k}", "Ohms", _g(R)), (f"L_{k}", "XOPT", _g(L_mH)), (f"C_{k}", "COPT", _g(C_uF))]
        self.comp("RLC3", x, y, [dict(nome="IN1", valor=n_in, fases=3, px=pin[0], py=pin[1]),
                                 dict(nome="OUT1", valor=n_out, fases=3, px=pout[0], py=pout[1])],
                  dados, angulo=angulo, caption=caption, comentario=comentario)

    def rlcy3(self, x, y, R, L_mH, C_uF, n_in="", n_out="", terra=False, caption=None, comentario=None, angulo=270, cap_pos=None, saida_corrente=False):
        """Estrela: IN 3φ, OUT = ponto comum (aterrado se terra=True). Ângulo 270 → IN em cima, OUT embaixo."""
        pin, pout = (-20, 0), (20, 0)
        dados = []
        for k in (1, 2, 3):
            dados += [(f"R_{k}", "Ohm", _g(R)), (f"L_{k}", "XOPT", _g(L_mH)), (f"C_{k}", "COPT", _g(C_uF))]
        self.comp("RLCY3", x, y, [dict(nome="IN", valor=n_in, fases=3, px=pin[0], py=pin[1]),
                                  dict(nome="OUT", valor=n_out, px=pout[0], py=pout[1], terra=terra)],
                  dados, angulo=angulo, caption=caption, comentario=comentario, cap_pos=cap_pos,
                  extra=(' Output="1"' if saida_corrente else ""))

    def rlcd3(self, x, y, R, L_mH, C_uF, n_in="", caption=None, comentario=None, acima=False, saida_corrente=False, cap_pos=None):
        ang = 90 if acima else 270
        p = (-20, 0)
        dados = []
        for k in (1, 2, 3):
            dados += [(f"R_{k}", "Ohms", _g(R)), (f"L_{k}", "XOPT", _g(L_mH)), (f"C_{k}", "COPT", _g(C_uF))]
        self.comp("RLCD3", x, y, [dict(nome="IN", valor=n_in, fases=3, px=p[0], py=p[1])], dados, angulo=ang,
                  caption=caption, comentario=comentario, extra=(' Output="1"' if saida_corrente else ""), cap_pos=cap_pos)

    def sonda_v(self, x, y_no, nome_no=""):
        """Sonda de tensão 3φ com o nó em (x, y_no) (o símbolo fica acima do fio)."""
        self.comp("PROBE_V", x, y_no - 20, [dict(nome="OUT", valor=nome_no, fases=3, px=0, py=20)],
                  [("Scale", "/pu", "1"), ("Freq", "Hz", "50"), ("Time", "sec", "0")], extra=' NumPhases="3"',
                  probe=True)

    def sonda_i(self, x, y, n_out=""):
        self.comp("PROBE_I", x, y, [dict(nome="IN", fases=3, px=-20, py=0),
                                    dict(nome="OUT", valor=n_out, fases=3, px=20, py=0),
                                    dict(nome="CURR", fases=3, px=0, py=-10, off=True)],
                  [("SCALE", "/pu", "1"), ("FREQ", "Hz", "50"), ("TIME", "s", "0")], extra=' NumPhases="3"',
                  probe=True)

    def resistor_terra(self, x, y_topo, R, n_topo=""):
        self.comp("RESISTOR", x, y_topo + 20, [dict(nome="From", valor=n_topo, px=-20, py=0),
                                               dict(nome="To", px=20, py=0, terra=True)],
                  [("R", "Ohm", _g(R))], angulo=270)


def gerar_atpdraw_xml(p, deck: Dict[str, Any], ligacao: str, arquivo: str, titulo: str = "FSEN",
                      resumo_python: Dict[str, Any] | None = None) -> str:
    """Grava o desenho ATPDraw (.xml) da rede do deck `deck` (saída de atp.gerar_deck) e devolve o caminho."""
    from .versao import assinatura
    D = _Desenho()
    X0, Y = 4000, 5200
    rp = getattr(p, "Q_hf", 0) * 2 * math.pi * getattr(p, "fs_ref", 0) * p.L1
    py = resumo_python or {}

    # ---------------- TACS: as MESMAS expressões 98 do deck, na mesma ordem (objetos FORTRAN1)
    tacs = []
    for lin in deck["texto"].splitlines():
        m = re.match(r"^98(\S+)\s*=(.*)$", lin)
        if m:
            tacs.append((m.group(1).strip(), m.group(2).strip()))
    ncol = 6
    for i, (nome, expr) in enumerate(tacs):
        cx = X0 + 40 + (i % ncol) * 110
        cy = 4640 + (i // ncol) * 60
        D.comp("FORTRAN1", cx, cy, [dict(nome="OUT", valor=nome, px=0, py=20, kind=None)], [("Type", "Use 98", "98")],
               caption=nome, ordem=i + 1, datastring=expr,
               comentario=(f"TACS 98 {nome} = {expr}" + ("   (SVPWM regular simetrica, igual ao Python)" if i == 0 else "")))

    # ---------------- inversor: 3 fontes TACS tipo 60 ±Vcc/2 → coletor 3φ
    xs = X0 + 200
    D.comp("SPLITTER", xs, Y, [dict(nome="IN", valor="VL", fases=3, px=-20, py=0),
                               dict(nome="OUTA", px=20, py=-10), dict(nome="OUTB", px=20, py=0),
                               dict(nome="OUTC", px=20, py=10)], angulo=180)
    # nós das fontes sem nome próprio: o ATPDraw herda VL + fase do coletor (VLA/VLB/VLC = variáveis TACS)
    for k, (fx, fy) in zip("ABC", [(xs - 140, -10), (xs - 100, 0), (xs - 60, 10)]):
        D.comp("TACSSOUR", fx, Y + 80, [dict(nome="TACS", valor="", px=20, py=0)],
               [("U/I", "", "0"), ("TStart", "sec", "-1"), ("TStop", "sec", "100")], angulo=90,
               caption=f"VL{k}", comentario=f"Fonte TACS tipo 60 - perna {k} do inversor (+/- Vcc/2)")
        D.fio(fx, Y + 60, fx, Y + fy, 1)
        D.fio(fx, Y + fy, xs - 20, Y + fy, 1)
    x = xs + 20
    D.sonda_v(x + 20, Y, "")
    D.fio(x, Y, x + 40, Y)
    x += 40
    D.sonda_i(x + 20, Y, "LI")                                    # corrente do inversor
    x += 40
    # ---------------- L1 // Rp
    cap_l1 = f"L1 = {p.L1 * 1e6:.0f} uH"
    D.fio(x, Y, x + 20, Y)
    x += 20
    D.rlc3(x + 20, Y, p.R1, p.L1 * 1e3, 0, n_in="LI", n_out="CP", caption=cap_l1,
           comentario=f"Reator L1 {p.L1 * 1e6:.1f} uH, R serie {p.R1 * 1e3:.3f} mOhm (Python)")
    if rp:
        D.rlc3(x + 20, Y - 60, rp, 0, 0, caption=f"Rp = {rp:.1f} Ohm",
               comentario="Perdas HF do nucleo de L1 (resistor em paralelo, igual ao Python)")
        D.fio(x, Y, x, Y - 60)
        D.fio(x + 40, Y, x + 40, Y - 60)
    x += 40
    # ---------------- nó CP: banco de capacitores
    D.fio(x, Y, x + 60, Y)
    xc = x + 30
    D.sonda_v(xc + 20, Y, "CP")
    D.fio(xc, Y, xc, Y + 30)
    if ligacao == "Delta":
        D.rlcd3(xc, Y + 50, 3 * p.Rd if p.Rd else 1e-6, 0, p.C_y / 3 * 1e6, saida_corrente=True,
                caption=f"C = {p.C_y / 3 * 1e6:.1f} uF/ramo (Delta)", cap_pos=(-150, -6),
                comentario=f"Banco em Delta: {p.C_y / 3 * 1e6:.2f} uF por ramo (= {p.C_y * 1e6:.1f} uF/fase em Y)")
        if p.Cd > 0:
            D.rlcd3(xc + 40, Y + 50, 3 * p.Rdp, 0, p.Cd / 3 * 1e6, caption="Cd (RC)")
            D.fio(xc, Y + 30, xc + 40, Y + 30)
    else:
        D.rlcy3(xc, Y + 50, p.Rd if p.Rd else 1e-6, 0, p.C_y * 1e6, n_out="NCAP", saida_corrente=True,
                caption=f"C = {p.C_y * 1e6:.1f} uF/fase (Y)", cap_pos=(-130, -6))
        D.resistor_terra(xc, Y + 70, 1e6)
        if p.Cd > 0:
            D.rlcy3(xc + 40, Y + 50, p.Rdp, 0, p.Cd * 1e6, n_out="NCAP", caption="Cd (RC)")
            D.fio(xc, Y + 30, xc + 40, Y + 30)
    x += 60
    D.fio(x, Y, x + 60, Y)
    x += 60
    no_ini = "CP"
    # ---------------- L2 (LCL)
    if p.L2 > 0:
        D.rlc3(x + 20, Y, p.R2 or 1e-6, p.L2 * 1e3, 0, n_out="L2", caption=f"L2 = {p.L2 * 1e6:.0f} uH")
        x += 40
        D.fio(x, Y, x + 20, Y)
        x += 20
        no_ini = "L2"
    # ---------------- cabo: células π (capacitâncias de nós vizinhos somadas, rede elétrica equivalente)
    n = _n_secoes(p)
    if n:
        lsec = p.cabo_m / 1000 / n
        for j in range(n + 1):
            fator = 1 if j in (0, n) else 2
            if p.cabo_Cpg_km:
                D.rlcy3(x, Y + 50, 0, 0, p.cabo_Cpg_km * lsec / 2 * fator * 1e6, terra=True,
                        caption=("Cabo C fase-terra" if j == 0 else None))
                D.fio(x, Y, x, Y + 30)
            if p.cabo_Cpp_km:
                D.rlcd3(x, Y - 50, 0, 0, p.cabo_Cpp_km * lsec / 2 * fator * 1e6,
                        caption=("Cabo C fase-fase" if j == 0 else None), acima=True)
                D.fio(x, Y, x, Y - 30)
            if j < n:
                nxt = f"C{j + 1:02d}" if j < n - 1 else "MT"
                D.fio(x, Y, x + 30, Y)
                D.rlc3(x + 50, Y, max(p.cabo_R_km * lsec, 1e-7), p.cabo_L_km * lsec * 1e3, 0, n_out=nxt,
                       caption=(f"Cabo {p.cabo_m:g} m ({n} celulas pi)" if j == 0 else None),
                       comentario=f"Cabo: celula pi {j + 1}/{n}, {lsec * 1000:.1f} m")
                D.fio(x + 70, Y, x + 100, Y)
                x += 100
    else:
        D.rlc3(x + 20, Y, 1e-6, 0, 0, n_out="MT")
        x += 40
    # ---------------- motor
    D.sonda_v(x + 20, Y, "MT")
    D.fio(x, Y, x + 40, Y)
    if p.Cwf:
        D.rlcy3(x + 20, Y + 70, 0, 0, p.Cwf / 3 * 1e6, terra=True, caption="Cwf/3 (carcaca)", cap_pos=(-110, -6))
        D.fio(x + 20, Y, x + 20, Y + 50)
    x += 40
    D.sonda_i(x + 20, Y, "MI")                                    # corrente do motor
    x += 40
    D.fio(x, Y, x + 40, Y)
    xm = x + 20
    amp = [deck["norton"][k][0] for k in "ABC"]
    fas = [deck["norton"][k][1] for k in "ABC"]
    D.comp("ACSOURCE", xm, Y + 60,
           [dict(nome="AC", valor="MI", fases=3, px=20, py=0), dict(nome="ACNEG", fases=3, px=-20, py=0, off=True),
            dict(nome="Internal", fases=3, px=0, py=0, off=True, interno=True)],
           [("Kind", "Volt/Curr", "-1"), ("AmplitudeA", "SOURCE", _g(amp[0])), ("AmplitudeB", "SOURCE", _g(amp[1])),
            ("AmplitudeC", "SOURCE", _g(amp[2])), ("Frequency", "Hz", _g(deck["f1"])),
            ("PhaseAngleA", "degrees", _g(fas[0])), ("PhaseAngleB", "degrees", _g(fas[1])),
            ("PhaseAngleC", "degrees", _g(fas[2])), ("Power", "VA", "0"), ("cosPhi", "-1..+1", "0"),
            ("StartA", "sec", "-1"), ("StartB", "sec", "-1"), ("StartC", "sec", "-1"),
            ("StopA", "sec", "100"), ("StopB", "sec", "100"), ("StopC", "sec", "100"),
            ("AngleUnit", "0/1", "0"), ("Phases", "0/1/2", "1"), ("Scaling", "0/1/2", "0"), ("Grounding", "0/1", "0")],
           angulo=90, caption="f.c.e.m. (Norton)",
           comentario=f"Forca contra-eletromotriz do motor como Norton: {amp[0]:.1f} A pico, {deck['f1']:.3f} Hz")
    D.fio(xm, Y, xm, Y + 40)
    x += 40
    D.rlcy3(x + 20, Y, max(p.Rm, 1e-6), p.Lm * 1e3, 0, n_out="NMOT", angulo=0,
            caption=f"Motor Rm+Lm ({p.Lm * 1e3:.3f} mH)", comentario="Motor: Rm + Lm em estrela isolada (NMOT)")
    D.resistor_terra(x + 40, Y + 20, 1e6)
    D.fio(x + 40, Y, x + 40, Y + 20, 1)

    # ---------------- anotação com os resultados do Python
    txt = [f"{titulo} | {assinatura(curta=True)}",
           f"f1 = {deck['f1']:.3f} Hz, fs = {deck['fs_ef']:.1f} Hz (mf = {deck['mf']}), m = {deck['m']:.4f}, ligacao {ligacao}"]
    for k, v in py.items():
        txt.append(f"Python: {k} = {v}")
    D.comp("ADDITIONAL", X0 + 40, 5480, [], [("Kind", "", "0")], datastring="C " + "\nC ".join(t[:78] for t in txt),
           comentario="Valores do Python (Plataforma FSEN) para comparar com este caso no ATP")

    tl = f'TopLeftX="{X0 - 40}" TopLeftY="4580"'
    xml = ['<?xml version="1.0"?>', '<project Application="ATPDraw" Version="7" VersionXML="1">',
           f'  <header Timestep="{_g(deck["dt"])}" Tmax="{_g(deck["tmax"])}" XOPT="0" COPT="0" EPSILN="1E-12" '
           f'SysFreq="{_g(round(deck["f1"], 3))}" {tl}>',
           f'    <header_output IOUT="999999" IPLOT="{deck.get("iplot", 8)}" ICAT="1" MEMSAVE="0" AutoError="true" '
           'AutoCode="1" IDOUBLE="1" KSSOUT="0" MAXOUT="1"/>',
           '    <header_format SORT_C="true" SORT_O="true" SORT_X="false" FORCE_V="false" AutoPath="false" AutoCode="1" '
           'ExactPE="false" PL4Comments="false" TACSHybrid="true"/>',
           '    <header_um INITUM="0" INPU="0" ICOMP="1"/>', "  </header>", "  <objects>"]
    xml += D.serializar()
    xml += ["  </objects>", '  <variables NumSim="1" IOPCVP="0" UseParser="false"/>', "</project>", ""]
    with open(arquivo, "w", encoding="utf-8", newline="\r\n") as f:
        f.write("\n".join(xml))
    return arquivo
