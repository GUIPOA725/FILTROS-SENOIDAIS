"""Projeto QElectroTech (.qet) gerado pela plataforma + renderização própria em PDF e DXF (v1.16.0).

O engenheiro não precisa abrir o QElectroTech: a plataforma monta o projeto com os componentes OFICIAIS da biblioteca
do QElectroTech (licença CC-BY, ver qet_elementos/LICENCA_ELEMENTOS_QET.txt) e componentes próprios (reator trifásico,
capacitor trifásico, controlador, ponto de ligação), liga os fios borne a borne (o .qet abre e edita como um projeto feito
à mão, com referências cruzadas mestre/escravo e lista de material pelas informações dos componentes) e desenha o MESMO
conteúdo em PDF (A3, carimbo Electric) e DXF – sem precisar do QElectroTech instalado.
Coordenadas QET: px, y para baixo; folha 17 colunas × 60 px, 8 linhas × 80 px.
"""
import math
import os
import re
import uuid as _uuid
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape

DIR_ELEM = os.path.join(os.path.dirname(__file__), "qet_elementos")
COLS, COLW, ROWS, ROWH = 10, 102, 8, 80          # 10 colunas como as folhas EPLAN da Electric (estilo aprendido)
W_PX, H_PX = COLS * COLW, ROWS * ROWH
ORI = {"n": 0, "e": 1, "s": 2, "w": 3}


def _u():
    return "{" + str(_uuid.uuid4()) + "}"


def _uuid_det(*k):
    """UUID determinístico (mesma entrada → mesmo arquivo: determinismo da plataforma)."""
    return "{" + str(_uuid.uuid5(_uuid.NAMESPACE_URL, "fsen/" + "/".join(map(str, k)))) + "}"


# ------------------------------------------------------------------------------------------- definições de elementos
def _def_propria(nome):
    """Componentes próprios (XML no formato de elemento do QElectroTech)."""
    st = 'style="line-style:normal;line-weight:normal;filling:none;color:black"'
    stf = 'style="line-style:normal;line-weight:normal;filling:black;color:black"'
    std = 'style="line-style:dashed;line-weight:thin;filling:none;color:black"'
    if nome == "no":
        return (f'<definition type="element" width="10" height="10" hotspot_x="5" hotspot_y="5" link_type="simple" version="0.90">'
                f'<names><name lang="pt">Ponto de ligação</name><name lang="en">Junction</name></names><informations>FSEN</informations>'
                f'<description><circle x="-1.5" y="-1.5" diameter="3" antialias="true" {stf}/>'
                f'<terminal x="0" y="0" orientation="n"/></description></definition>')
    if nome == "reator3":
        d = []
        for x in (-20, 0, 20):
            d.append(f'<line x1="{x}" y1="-30" x2="{x}" y2="-20" {st}/>')
            for k in range(4):
                d.append(f'<arc x="{x-5}" y="{-20 + k*10}" width="10" height="10" start="90" angle="-180" {st}/>')
            d.append(f'<line x1="{x}" y1="20" x2="{x}" y2="30" {st}/>')
        d.append(f'<line x1="-32" y1="-20" x2="-32" y2="20" {st}/><line x1="-35" y1="-20" x2="-35" y2="20" {st}/>')
        d.append(f'<rect x="-40" y="-24" width="70" height="48" {std}/>')
        d.append('<input x="34" y="-6" size="9" text="_" tagg="label"/>')
        for x in (-20, 0, 20):
            d.append(f'<terminal x="{x}" y="-30" orientation="n"/>')
        for x in (-20, 0, 20):
            d.append(f'<terminal x="{x}" y="30" orientation="s"/>')
        return (f'<definition type="element" width="80" height="70" hotspot_x="40" hotspot_y="35" link_type="simple" version="0.90">'
                f'<names><name lang="pt">Reator trifásico com núcleo de ferro</name><name lang="en">3-phase reactor</name></names>'
                f'<informations>FSEN – Electric Service</informations><description>{"".join(d)}</description></definition>')
    if nome == "cap3":
        d = [f'<rect x="-30" y="-12" width="60" height="44" {st}/>']
        for x in (-20, 0, 20):
            d.append(f'<line x1="{x}" y1="-20" x2="{x}" y2="-12" {st}/>')
        pa, pb, pc = (-16, 26), (16, 26), (0, -2)
        for (a, b) in ((pa, pb), (pb, pc), (pc, pa)):
            mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
            ang = math.atan2(b[1] - a[1], b[0] - a[0])
            ux, uy, nx, ny = math.cos(ang), math.sin(ang), -math.sin(ang), math.cos(ang)
            g = 1.5
            d.append(f'<line x1="{a[0]}" y1="{a[1]}" x2="{mx-ux*g:.2f}" y2="{my-uy*g:.2f}" {st}/>')
            d.append(f'<line x1="{b[0]}" y1="{b[1]}" x2="{mx+ux*g:.2f}" y2="{my+uy*g:.2f}" {st}/>')
            for s in (-g, g):
                d.append(f'<line x1="{mx+ux*s-nx*4:.2f}" y1="{my+uy*s-ny*4:.2f}" x2="{mx+ux*s+nx*4:.2f}" y2="{my+uy*s+ny*4:.2f}" {st}/>')
        d.append(f'<line x1="-20" y1="-12" x2="{pa[0]}" y2="{pa[1]}" {st}/><line x1="0" y1="-12" x2="{pc[0]}" y2="{pc[1]}" {st}/>'
                 f'<line x1="20" y1="-12" x2="{pb[0]}" y2="{pb[1]}" {st}/>')
        d.append('<input x="34" y="4" size="9" text="_" tagg="label"/>')
        for x in (-20, 0, 20):
            d.append(f'<terminal x="{x}" y="-20" orientation="n"/>')
        return (f'<definition type="element" width="70" height="60" hotspot_x="35" hotspot_y="22" link_type="simple" version="0.90">'
                f'<names><name lang="pt">Capacitor trifásico (triângulo) com resistores de descarga</name><name lang="en">3-phase capacitor</name>'
                f'</names><informations>FSEN</informations><description>{"".join(d)}</description></definition>')
    m = re.match(r"ctrl(\d+)", nome)
    if m:
        n = int(m.group(1))
        w = max(140, 20 * (n + 4))
        d = [f'<rect x="0" y="0" width="{w}" height="60" {st}/>', '<input x="8" y="34" size="10" text="_" tagg="label"/>',
             f'<text x="8" y="48" size="6" text="Controlador de fator de potência"/>']
        tops = [("L", 10), ("k", w - 40), ("l", w - 20)]
        bots = [("N", 10), ("C", 30)] + [(str(i + 1), 50 + 20 * i) for i in range(n)] + [("ALM", 50 + 20 * n)]
        for t, x in tops:
            d.append(f'<text x="{x-3}" y="10" size="5" text="{t}"/><terminal x="{x}" y="-10" orientation="n"/>'
                     f'<line x1="{x}" y1="-10" x2="{x}" y2="0" {st}/>')
        for t, x in bots:
            d.append(f'<text x="{x-3}" y="56" size="5" text="{t}"/><terminal x="{x}" y="70" orientation="s"/>'
                     f'<line x1="{x}" y1="60" x2="{x}" y2="70" {st}/>')
        return (f'<definition type="element" width="{w+10}" height="90" hotspot_x="0" hotspot_y="10" link_type="simple" version="0.90">'
                f'<names><name lang="pt">Controlador automático de FP ({n} saídas)</name><name lang="en">PF controller</name></names>'
                f'<informations>FSEN</informations><description>{"".join(d)}</description></definition>')
    if nome == "inversor":                  # inversor de frequência (externo): retângulo com ~/~, saídas U V W embaixo + PE
        d = [f'<rect x="-45" y="-30" width="90" height="50" {st}/>', f'<line x1="-45" y1="20" x2="45" y2="-30" {st}/>',
             '<text x="-38" y="-14" size="10" text="~"/>', '<text x="28" y="14" size="10" text="~"/>',
             '<input x="-45" y="-36" size="10" text="_" tagg="label"/>']
        for k, (t, x) in enumerate((("U", -20), ("V", 0), ("W", 20))):
            d.append(f'<line x1="{x}" y1="20" x2="{x}" y2="30" {st}/><terminal x="{x}" y="30" orientation="s"/>')
        d.append(f'<line x1="40" y1="20" x2="40" y2="30" {st}/><terminal x="40" y="30" orientation="s"/>')
        return (f'<definition type="element" width="100" height="70" hotspot_x="50" hotspot_y="35" link_type="simple" version="0.90">'
                f'<names><name lang="pt">Inversor de frequência</name><name lang="en">Variable frequency drive</name></names>'
                f'<informations>FSEN</informations><description>{"".join(d)}</description></definition>')
    if nome == "motor3":                    # motor trifásico (externo): círculo M 3~, entradas U V W em cima + PE
        d = [f'<circle x="-22" y="-12" diameter="44" {st}/>', '<text x="-7" y="10" size="12" text="M"/>',
             '<text x="-6" y="21" size="8" text="3~"/>', '<input x="26" y="6" size="10" text="_" tagg="label"/>']
        for t, x in (("U", -20), ("V", 0), ("W", 20)):
            y1 = -12 + 22 - (22 ** 2 - x ** 2) ** 0.5 if abs(x) < 22 else -2
            d.append(f'<line x1="{x}" y1="-30" x2="{x}" y2="{y1:.1f}" {st}/><terminal x="{x}" y="-30" orientation="n"/>')
        d.append(f'<line x1="30" y1="-30" x2="30" y2="0" {st}/><line x1="30" y1="0" x2="20" y2="10" {st}/>'
                 f'<terminal x="30" y="-30" orientation="n"/>')
        return (f'<definition type="element" width="70" height="80" hotspot_x="35" hotspot_y="40" link_type="simple" version="0.90">'
                f'<names><name lang="pt">Motor trifásico</name><name lang="en">Three-phase motor</name></names>'
                f'<informations>FSEN</informations><description>{"".join(d)}</description></definition>')
    if nome == "cabo3":                     # cabo multipolar blindado (externo): 3 vias + PE passando, elipse do cabo e da blindagem
        d = [f'<ellipse x="-30" y="-6" width="80" height="12" {st}/>', f'<ellipse x="-34" y="-9" width="88" height="18" {std}/>',
             '<input x="54" y="4" size="9" text="_" tagg="label"/>']
        for x in (-20, 0, 20, 40):
            d.append(f'<line x1="{x}" y1="-20" x2="{x}" y2="20" {st}/><terminal x="{x}" y="-20" orientation="n"/>'
                     f'<terminal x="{x}" y="20" orientation="s"/>')
        return (f'<definition type="element" width="100" height="40" hotspot_x="40" hotspot_y="20" link_type="simple" version="0.90">'
                f'<names><name lang="pt">Cabo blindado</name><name lang="en">Shielded cable</name></names>'
                f'<informations>FSEN</informations><description>{"".join(d)}</description></definition>')
    if nome == "rele_ff":
        d = [f'<rect x="-30" y="-15" width="60" height="30" {st}/>', '<input x="-26" y="2" size="9" text="_" tagg="label"/>',
             '<text x="-26" y="11" size="5" text="falta/seq. de fase"/>']
        for x, t in ((-20, "L1"), (0, "L2"), (20, "L3")):
            d.append(f'<terminal x="{x}" y="-25" orientation="n"/><line x1="{x}" y1="-25" x2="{x}" y2="-15" {st}/>'
                     f'<text x="{x+1}" y="-17" size="4" text="{t}"/>')
        return (f'<definition type="element" width="70" height="60" hotspot_x="35" hotspot_y="30" link_type="master" version="0.90">'
                f'<names><name lang="pt">Relé de falta de fase</name><name lang="en">Phase failure relay</name></names>'
                f'<kindInformations><kindInformation name="type" show="1">coil</kindInformation></kindInformations>'
                f'<informations>FSEN</informations><description>{"".join(d)}</description></definition>')
    raise KeyError(nome)


class Def:
    """Definição de elemento (oficial ou própria): primitivas + terminais."""

    def __init__(self, nome):
        self.nome = nome
        arq = os.path.join(DIR_ELEM, nome + ".elmt")
        self.xml = open(arq, encoding="utf-8").read() if os.path.exists(arq) else _def_propria(nome)
        # QET ≥ 0.8: cada terminal da definição precisa de uuid (o condutor aponta element+terminal por uuid)
        self.tuuid = []
        cont = iter(range(10 ** 6))

        def _poe_uuid(m):
            i = next(cont)
            u = _uuid_det("elmt", nome, i)
            self.tuuid.append(u)
            tag = re.sub(r'\suuid="[^"]*"', "", m.group(0))
            return tag.replace("<terminal ", f'<terminal uuid="{u}" ', 1)
        self.xml = re.sub(r"<terminal\s[^>]*>", _poe_uuid, self.xml)
        self.raiz = ET.fromstring(self.xml)
        self.link = self.raiz.get("link_type", "simple")
        self.terms = [(float(t.get("x")), float(t.get("y")), t.get("orientation", "n")) for t in self.raiz.iter("terminal")]
        self.pt = None
        for nm in self.raiz.iter("name"):
            if nm.get("lang") == "pt":
                self.pt = nm.text
        if not self.pt:
            for nm in self.raiz.iter("name"):
                if nm.get("lang") in ("en", "fr"):
                    self.pt = nm.text
                    break


_CACHE = {}


def definicao(nome):
    if nome not in _CACHE:
        _CACHE[nome] = Def(nome)
    return _CACHE[nome]


# ------------------------------------------------------------------------------------------- projeto
NOMES_TERM = {
    "sectionneur_3_fusibles": {("n", 0): "1", ("n", 1): "3", ("n", 2): "5", ("s", 0): "2", ("s", 1): "4", ("s", 2): "6"},
    "com_puiss4": {("n", 0): "1", ("n", 1): "3", ("n", 2): "5", ("s", 0): "2", ("s", 1): "4", ("s", 2): "6"},
    "disjonct-m_3f": {("n", 0): "1", ("n", 1): "3", ("n", 2): "5", ("s", 0): "2", ("s", 1): "4", ("s", 2): "6"},
    "disjonct-m_2f": {("n", 0): "1", ("n", 1): "3", ("s", 0): "2", ("s", 1): "4"},
    "reator3": {("n", 0): "U", ("n", 1): "V", ("n", 2): "W", ("s", 0): "X", ("s", 1): "Y", ("s", 2): "Z"},
    "cap3": {("n", 0): "x1", ("n", 1): "x2", ("n", 2): "x3"},
    "bobine3": {("n", 0): "A1", ("s", 0): "A2"},
    "con_simple": {("n", 0): "13", ("s", 0): "14"},
    "con_simple_nf": {("n", 0): "11", ("s", 0): "12"},
    "lampe2": {("n", 0): "X1", ("s", 0): "X2"},
    "thermostat_nc": {("n", 0): "1", ("s", 0): "2"},
    "thermostat_01": {("n", 0): "1", ("s", 0): "2"},
    "arret_urgence_verrou": {("n", 0): "11", ("s", 0): "12"},
    "commut_2_position_fixe": {("n", 0): "13", ("s", 0): "14"},
    "moteur_mono": {("n", 0): "1", ("n", 1): "2"},
    "rele_ff": {("n", 0): "L1", ("n", 1): "L2", ("n", 2): "L3"},
    "transfo_mono": {("n", 0): "H1", ("n", 1): "H2", ("s", 0): "X1", ("s", 1): "X2"},
    "inversor": {("s", 0): "U", ("s", 1): "V", ("s", 2): "W", ("s", 3): "PE"},
    "motor3": {("n", 0): "U", ("n", 1): "V", ("n", 2): "W", ("n", 3): "PE"},
}


class Elemento:
    def __init__(self, folio, nome, x, y, label="", info=None, ori=0, chave=None):
        self.folio, self.d, self.x, self.y, self.label, self.ori = folio, definicao(nome), x, y, label, ori
        self.info = info or {}
        self.uuid = _uuid_det(folio.proj.codigo, folio.n, nome, x, y, label, chave)
        self.tid = []
        for _ in self.d.terms:
            folio.proj.prox_t += 1
            self.tid.append(folio.proj.prox_t)
        self.links = []

    def _rot(self, x, y):
        for _ in range(self.ori % 4):
            x, y = -y, x
        return x, y

    def term(self, lado, k=0):
        """k-ésimo terminal do lado ('n','s','e','w') ordenado por x (n/s) ou y (e/w) → (id, xabs, yabs)."""
        cand = []
        for i, (tx, ty, o) in enumerate(self.d.terms):
            oo = "nesw"[("nesw".index(o) + self.ori) % 4]
            rx, ry = self._rot(tx, ty)
            if oo == lado:
                cand.append((rx if lado in "ns" else ry, i, rx, ry))
        cand.sort()
        _, i, rx, ry = cand[k]
        # nome do borne pela posição ORIGINAL no símbolo (vale também para elemento girado)
        o = self.d.terms[i][2]
        mesmos = sorted((tx if o in "ns" else ty, j) for j, (tx, ty, oj) in enumerate(self.d.terms) if oj == o)
        k0 = [j for _, j in mesmos].index(i)
        return (self.tid[i], self.x + rx, self.y + ry, self, NOMES_TERM.get(self.d.nome, {}).get((o, k0), ""))


class Folio:
    def __init__(self, proj, titulo, funcao=""):
        self.proj, self.titulo, self.funcao = proj, titulo, funcao
        self.elems, self.conds, self.textos, self.retangulos = [], [], [], []
        self.n = len(proj.folios) + 1

    def el(self, nome, x, y, label="", info=None, ori=0, chave=None):
        e = Elemento(self, nome, x, y, label, info, ori, chave)
        self.elems.append(e)
        if label and info is not None:
            self.proj.registra(label, e)
        return e

    def no(self, x, y, barra="", pot="", pe_de=""):
        """Ponto de ligação. barra = barramento de cobre (-R2, -PE2…); pot = nome de potencial que continua em outra folha
        (L220, N220…); pe_de = tag do componente cuja carcaça vai ao PE neste ponto (lista DE/PARA e etiquetas)."""
        info = {k: v for k, v in dict(barra=barra, pot=pot, pe_de=pe_de).items() if v}
        e = self.el("no", x, y, chave=len(self.elems))
        e.info.update(info)
        return e

    def fio(self, ta, tb, num="", secao="", cor="", potencia=False, marca="", ym=None):
        """Fio borne a borne. secao em mm² (texto), marca = cor do cabo (ex. 'VM', 'PT', 'VD/AM') – como no EPLAN Electric."""
        self.conds.append(dict(a=ta, b=tb, num=str(num), secao=secao, cor=cor, pot=potencia, marca=marca, ym=ym))

    def conexoes(self):
        """Lista de conexão (estilo EPLAN): origem tag:borne → destino tag:borne, fio, seção, cor."""
        out = []
        for c in self.conds:
            ea, eb = c["a"][3], c["b"][3]
            if ea.d.nome == "no" and eb.d.nome == "no":
                continue
            out.append(dict(de=f"{ea.label or '•'}:{c['a'][4]}".rstrip(":"), para=f"{eb.label or '•'}:{c['b'][4]}".rstrip(":"),
                            num=c["num"], secao=c["secao"], marca=c["marca"], folha=self.n, pot=c["pot"]))
        return out

    def texto(self, x, y, t, size=9, cor="#000000"):
        self.textos.append((x, y, t, size, cor))

    def ret(self, x, y, w, h, rotulo=""):
        """Contorno tracejado de local (ex.: +PAINEL) – como a moldura de localização do EPLAN."""
        self.retangulos.append((x, y, w, h, rotulo))


class ProjetoQet:
    def __init__(self, titulo, cliente, codigo, data, versao, autor="Electric Service – plataforma FSEN"):
        self.titulo, self.cliente, self.codigo, self.data, self.versao, self.autor = titulo, cliente, codigo, data, versao, autor
        self.folios = []
        self.prox_t = 0
        self.por_label = {}

    def folio(self, titulo, funcao=""):
        f = Folio(self, titulo, funcao)
        self.folios.append(f)
        return f

    def registra(self, label, e):
        self.por_label.setdefault(label, []).append(e)

    def ligar(self, escravo, mestre):
        """Referência cruzada mestre/escravo (bobina ↔ contatos), nos dois sentidos como o QElectroTech grava."""
        escravo.links.append(mestre.uuid)
        mestre.links.append(escravo.uuid)

    # ------------------------------------------------------------------ posição para referências cruzadas
    @staticmethod
    def coluna(x):
        return max(1, min(COLS, int(x // COLW) + 1))

    @staticmethod
    def linha(y):
        return "ABCDEFGH"[max(0, min(ROWS - 1, int(y // ROWH)))]

    def pos(self, e):
        return f"{e.folio.n}-{self.linha(e.y)}{self.coluna(e.x)}"

    # ------------------------------------------------------------------ gravação .qet
    def salvar_qet(self, arq):
        usados = {}
        for f in self.folios:
            for e in f.elems:
                usados[e.d.nome] = e.d
        L = [f'<project title="{escape(self.titulo)}" version="0.100" uuid="{_uuid_det(self.codigo)}">',
             '<properties><property name="saveddate" show="1">' + escape(self.data) + '</property></properties>',
             '<newdiagrams><border cols="10" colsize="102" rows="8" rowsize="80" displaycols="true" displayrows="true"/>'
             '<inset author="" date="null" title="" folio="%id/%total" filename=""/>'
             '<conductors type="multi" num="" numsize="7" condsize="1" displaytext="1"/></newdiagrams>']
        for f in self.folios:
            L.append(f'<diagram title="{escape(f.titulo)}" author="{escape(self.autor)}" date="null" folio="%id/%total" '
                     f'filename="{escape(self.codigo)}" plant="{escape(self.cliente)}" locmach="{escape(f.funcao)}" indexrev="" '
                     f'order="{f.n}" cols="{COLS}" colsize="{COLW}" rows="{ROWS}" rowsize="{ROWH}" height="{H_PX + 20}" '
                     f'displaycols="true" displayrows="true" displayAt="bottom" version="0.100" uuid="{_uuid_det(self.codigo, "f", f.n)}" '
                     f'freezeNewElement="false" freezeNewConductor="false" auto_page_num="">')
            L.append('<defaultconductor type="multi" num="" numsize="7" condsize="1" displaytext="1" formula="" function="" '
                     'tension_protocol="" conductor_color="" conductor_section="" bicolor="false" color2="#000000" dash-size="2" '
                     'onetextperfolio="0" vertirotatetext="270" horizrotatetext="0" text_color="#000000" cable="" bus="" '
                     'horizontal-alignment="AlignBottom" vertical-alignment="AlignRight"/>')
            L.append("<elements>")
            for e in f.elems:
                L.append(f'<element type="embed://import/fsen/{e.d.nome}.elmt" x="{e.x:g}" y="{e.y:g}" z="10" orientation="{e.ori}" '
                         f'uuid="{e.uuid}" prefix="" freezeLabel="false" is_movable="1">')
                L.append("<terminals>")
                for (tx, ty, o), tid in zip(e.d.terms, e.tid):
                    L.append(f'<terminal id="{tid}" x="{tx:g}" y="{ty:g}" orientation="{ORI[o]}"/>')
                L.append("</terminals><inputs/>")
                if e.links:
                    L.append("<links_uuids>" + "".join(f'<link_uuid uuid="{u}"/>' for u in e.links) + "</links_uuids>")
                if e.label or e.info:
                    L.append("<elementInformations>")
                    if e.label:
                        L.append(f'<elementInformation name="label" show="1">{escape(e.label)}</elementInformation>')
                    for k, v in e.info.items():
                        if v not in (None, ""):
                            L.append(f'<elementInformation name="{k}" show="0">{escape(str(v))}</elementInformation>')
                    L.append("</elementInformations>")
                if e.label and e.d.nome != "no":
                    lb = [q for q in primitivas_elemento(e) if q[0] == "lbl"]
                    lx, ly = (lb[0][1] - e.x, lb[0][2] - e.y - 9) if lb else (12, -8)
                    if lb and len(lb[0]) > 6 and lb[0][6] == "right":
                        lx -= 6.2 * len(e.label)
                    fs = 6 if e.d.nome == "borne_continuite" else 9
                    L.append(f'<dynamic_texts><dynamic_elmt_text x="{lx:g}" y="{ly:g}" rotation="0" uuid="{_uuid_det(e.uuid, "lbl")}" '
                             f'font="Sans Serif,{fs},-1,5,75,0,0,0,0,0" frame="false" text_from="ElementInfo" Halignment="AlignLeft" '
                             f'Valignment="AlignTop" text_width="-1" keep_visual_rotation="true" color="#1f4e8c">'
                             f'<text>{escape(e.label)}</text><info_name>label</info_name></dynamic_elmt_text></dynamic_texts>'
                             f'<texts_groups/></element>')
                else:
                    L.append("<dynamic_texts/><texts_groups/></element>")
            L.append("</elements><conductors>")
            for c in f.conds:
                ea, eb = c["a"][3], c["b"][3]
                ua, ub = ea.d.tuuid[ea.tid.index(c["a"][0])], eb.d.tuuid[eb.tid.index(c["b"][0])]
                L.append(f'<conductor element1="{ea.uuid}" terminal1="{ua}" element2="{eb.uuid}" terminal2="{ub}" x="0" y="0" type="multi" num="{escape(c["num"])}" '
                         f'numsize="7" condsize="1" displaytext="1" formula="" function="" tension_protocol="" '
                         f'conductor_color="{escape(c.get("marca") or "")}" conductor_section="{escape(c["secao"])}" bicolor="false" color2="#000000" '
                         f'dash-size="2" onetextperfolio="0" vertirotatetext="270" horizrotatetext="0" text_color="#000000" cable="" bus="" '
                         f'horizontal-alignment="AlignBottom" vertical-alignment="AlignRight" freezeLabel="false">{_segmentos(c)}<sequentialNumbers/></conductor>')
            L.append("</conductors><inputs>")
            for (x, y, t, size, cor) in f.textos:
                L.append(f'<input x="{x:g}" y="{y:g}" text="{escape(t)}" size="{size}" color="{cor}"/>')
            L.append("</inputs></diagram>")
        L.append('<collection><category name="import"><names><name lang="pt">elementos importados</name>'
                 '<name lang="en">Imported elements</name></names><category name="fsen"><names><name lang="pt">FSEN – Electric</name>'
                 '<name lang="en">FSEN</name></names>')
        for nome, d in sorted(usados.items()):
            L.append(f'<element name="{nome}.elmt">{d.xml if not d.xml.startswith("<?xml") else d.xml.split("?>", 1)[1]}</element>')
        L.append("</category></category></collection></project>")
        with open(arq, "w", encoding="utf-8") as fh:
            fh.write('<?xml version="1.0" encoding="UTF-8"?>\n' + "\n".join(L))
        return arq


# ------------------------------------------------------------------------------------------- renderização (PDF/DXF)
def _num(v, p=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return p


_PINO_TXT = re.compile(r"^(\d{1,2}|[LT]\s?[123]|A[12]|NO|NC|NA|NF)(\s+\S+)?$")


def primitivas_elemento(e):
    """Primitivas do elemento em coordenadas ABSOLUTAS do folio (px, y para baixo)."""
    out = []
    ang = e.ori * 90

    def P(x, y):
        rx, ry = e._rot(x, y)
        return e.x + rx, e.y + ry
    for p in e.d.raiz.find("description") if e.d.raiz.find("description") is not None else []:
        tag = p.tag
        sty = p.get("style", "")
        tr = "dashed" in sty or "dotted" in sty
        fill = "filling:black" in sty
        if tag == "line":
            out.append(("lin", [P(_num(p.get("x1")), _num(p.get("y1"))), P(_num(p.get("x2")), _num(p.get("y2")))], tr))
        elif tag == "polygon":
            pts, k = [], 1
            while p.get(f"x{k}") is not None:
                pts.append(P(_num(p.get(f"x{k}")), _num(p.get(f"y{k}"))))
                k += 1
            if p.get("closed", "true") != "false":
                pts.append(pts[0])
            out.append(("pol", pts, tr, fill))
        elif tag == "rect":
            x, y, w, h = (_num(p.get(a)) for a in ("x", "y", "width", "height"))
            out.append(("pol", [P(x, y), P(x + w, y), P(x + w, y + h), P(x, y + h), P(x, y)], tr, fill))
        elif tag in ("circle", "ellipse", "arc"):
            if tag == "circle":
                x, y = _num(p.get("x")), _num(p.get("y"))
                w = h = _num(p.get("diameter"))
                a0, da = 0.0, 360.0
            else:
                x, y, w, h = (_num(p.get(a)) for a in ("x", "y", "width", "height"))
                a0, da = (_num(p.get("start")), _num(p.get("angle"))) if tag == "arc" else (0.0, 360.0)
            cx, cy = x + w / 2, y + h / 2
            n = max(8, int(abs(da) / 10))
            pts = []
            for k in range(n + 1):
                t = math.radians(a0 + da * k / n)
                pts.append(P(cx + w / 2 * math.cos(t), cy - h / 2 * math.sin(t)))     # Qt: ângulo anti-horário, y para baixo
            out.append(("pol", pts, tr, fill and tag != "arc"))
        elif tag == "text":
            x, y = P(_num(p.get("x")), _num(p.get("y")))
            out.append(("txt", x, y, p.get("text", ""), _num(p.get("size"), 9), ang if p.get("rotate") == "true" else 0))
        elif tag == "input" and p.get("tagg") == "label":
            continue
        elif tag == "input":
            x, y = P(_num(p.get("x")), _num(p.get("y")))
            out.append(("txt", x, y, p.get("text", ""), _num(p.get("size"), 9), 0))
    if e.label and e.d.nome != "no":
        xs = [q[0] for o in out if o[0] in ("lin", "pol") for q in o[1]]
        ys = [q[1] for o in out if o[0] in ("lin", "pol") for q in o[1]]
        xs += [o[1] - 2 for o in out if o[0] == "txt" and o[3] and not _PINO_TXT.match(str(o[3]).strip())]   # θ, M… fora do traço
        if xs:
            if e.d.nome == "cap3":          # capacitores lado a lado: rótulo e dados embaixo do símbolo
                out.append(("lbl", min(xs) + 2, max(ys) + 11, e.label, 8.0, 0))
                if e.info.get("dados"):
                    out.append(("dad", min(xs) + 2, max(ys) + 19, e.info["dados"], 6.5, 0))
            elif e.d.nome == "borne_continuite":   # nº do borne à direita do fio, acima do círculo (não fica sobre o fio)
                out.append(("lbl", (min(xs) + max(xs)) / 2 + 3, min(ys) + 2, e.label.split(":")[-1], 6.5, 0))
            elif e.d.nome in ("reator3", "ctrl6", "ctrl12", "inversor", "motor3", "cabo3") or e.d.nome.startswith("ctrl") or e.d.nome == "rele_ff":
                out.append(("lbl", max(xs) + 4, (min(ys) + max(ys)) / 2 + 3, e.label, 10.0, 0))
                if e.info.get("dados"):
                    out.append(("dad", max(xs) + 4, (min(ys) + max(ys)) / 2 + 12, e.info["dados"], 6.5, 0))
            else:                           # padrão EPLAN: tag à ESQUERDA do símbolo, alinhada à direita, dados embaixo
                out.append(("lbl", min(xs) - 5, (min(ys) + max(ys)) / 2 + 2, e.label, 10.0, 0, "right"))
                if e.info.get("dados"):
                    out.append(("dad", min(xs) - 5, (min(ys) + max(ys)) / 2 + 10, e.info["dados"], 6.5, 0, "right"))
    return out


def _lado_term(t):
    """Lado (n/e/s/w) do terminal t=(tid,x,y,elem,nome) já considerando a rotação do elemento."""
    e = t[3]
    i = e.tid.index(t[0])
    o = e.d.terms[i][2]
    return "nesw"[("nesw".index(o) + e.ori) % 4]


def _segmentos(c, doca=4.0):
    """Segmentos QET (mesma rota do PDF) – o QET usa estes trechos em vez do roteamento automático."""
    a, b = c["a"], c["b"]
    dv = dict(n=(0, -doca), s=(0, doca), e=(doca, 0), w=(-doca, 0))
    la, lb = _lado_term(a), _lado_term(b)
    pa = (a[1] + dv[la][0], a[2] + dv[la][1])
    pb = (b[1] + dv[lb][0], b[2] + dv[lb][1])
    pts = rota(a[1:3], b[1:3], c.get("ym"))
    pts = [pa] + [p for p in pts[1:-1]] + [pb]
    # ajusta pontos intermediários para manter ortogonalidade após a doca
    if len(pts) == 2 and abs(pa[0] - pb[0]) > 0.01 and abs(pa[1] - pb[1]) > 0.01:
        return ""
    out = []
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        dx, dy = x1 - x0, y1 - y0
        if abs(dx) > 0.01 and abs(dy) > 0.01:
            return ""
        if abs(dx) > 0.01:
            out.append(f'<segment orientation="horizontal" length="{dx:g}"/>')
        elif abs(dy) > 0.01:
            out.append(f'<segment orientation="vertical" length="{dy:g}"/>')
    return "".join(out)


def rota(a, b, ym=None):
    """Rota ortogonal entre dois terminais (x, y) – reta se alinhados, senão em L/Z (ym = altura do trecho horizontal)."""
    (xa, ya), (xb, yb) = a, b
    if abs(xa - xb) < 0.5 or (abs(ya - yb) < 0.5 and ym is None):
        return [a, b]
    ym = (ya + yb) / 2 if ym is None else ym
    return [a, (xa, ym), (xb, ym), b]


# ------------------------------------------------------------------------------------------- PDF / DXF (A3, carimbo Electric)
S_MM = 395.0 / W_PX
OX, OY = 15.0, 279.0          # px (0,0) → mm (OX, OY); y do papel cresce para cima
COR_POT, COR_CMD, COR_PE = "#c62828", "#1f4e8c", "#2e7d32"
LOGO = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "dados", "marca", "logo_electric.png")


def _mm(x, y):
    return OX + x * S_MM, OY - y * S_MM


def _xrefs(proj):
    """Textos de referência cruzada: escravo → posição do mestre; mestre → lista dos escravos."""
    por_uuid = {e.uuid: e for f in proj.folios for e in f.elems}
    out = {}
    for f in proj.folios:
        for e in f.elems:
            if not e.links:
                continue
            if e.d.link == "slave":
                out[e.uuid] = [f"/{proj.pos(por_uuid[u])}" for u in e.links if u in por_uuid]
            elif e.d.link == "master":
                out[e.uuid] = [f"{por_uuid[u].info.get('contato', '')} /{proj.pos(por_uuid[u])}".strip() for u in e.links if u in por_uuid]
    return out


def _carimbo(ax, proj, f, total, pt):
    from matplotlib.patches import Rectangle
    k = dict(lw=0.6 * pt / 2.83, color="k")
    ax.add_patch(Rectangle((10, 5), 400, 287, fill=False, lw=0.5))
    # faixa de colunas (topo) e linhas (lateral)
    for c in range(COLS + 1):
        x = OX + c * COLW * S_MM
        ax.plot([x, x], [287, 292], **k)
        if c < COLS:
            ax.text(x + COLW * S_MM / 2, 289.5, str(c + 1), fontsize=5.5, ha="center", va="center")
    ax.plot([10, 410], [287, 287], **k)
    for r in range(ROWS):
        y = OY - (r + 0.5) * ROWH * S_MM
        ax.text(12.5, y, "ABCDEFGH"[r], fontsize=5.5, ha="center", va="center")
    ax.plot([15, 15], [27, 287], **k)
    # carimbo no padrão dos diagramas Electric (EPLAN 2023)
    y0, h = 5.0, 22.0
    ax.plot([10, 410], [y0 + h, y0 + h], **k)
    xs = [10, 32, 52, 70, 112, 152, 222, 292, 352, 410]
    for x in xs[1:-1]:
        ax.plot([x, x], [y0, y0 + h], **k)
    for yy in (y0 + 5.5, y0 + 11, y0 + 16.5):
        ax.plot([10, 112], [yy, yy], lw=0.3, color="0.4")
    ax.text(11, y0 + 1.5, "Alteração", fontsize=4.5)
    ax.text(33, y0 + 1.5, "Data", fontsize=4.5)
    ax.text(53, y0 + 1.5, "Nome", fontsize=4.5)
    ax.text(11, y0 + 12.5, "00", fontsize=5)
    ax.text(33, y0 + 12.5, proj.data, fontsize=4.6)
    ax.text(53, y0 + 12.5, "Emissão", fontsize=4.6)
    for k_, (r, v) in enumerate((("Orig", "FSEN"), ("Verif", ""), ("Editor", "plataforma"), ("Data", proj.data))):
        ax.text(71, y0 + 1.5 + k_ * 5.5, r, fontsize=4.5)
        ax.text(86, y0 + 1.5 + k_ * 5.5, v, fontsize=4.6)
    ax.text(113, y0 + 1.5, "Em substituição de", fontsize=4.5)
    ax.text(153, y0 + 1.5, "Substituído por", fontsize=4.5)
    ax.text(113, y0 + 15, f"Cliente: {proj.cliente}", fontsize=5.2, weight="bold")
    ax.text(113, y0 + 9, proj.titulo[:60], fontsize=4.8)
    if os.path.exists(LOGO):
        import matplotlib.image as mpimg
        ax.imshow(mpimg.imread(LOGO), extent=(156, 218, y0 + 3, y0 + 3 + 62 * 209 / 909), zorder=5)
    t = f.titulo
    ax.text(224, y0 + 15, t[:44], fontsize=6.2, weight="bold")
    if len(t) > 44:
        ax.text(224, y0 + 10, t[44:88], fontsize=6.2, weight="bold")
    ax.text(224, y0 + 3, f"{proj.codigo}  |  {proj.versao}", fontsize=4.6, color="0.3")
    ax.plot([292, 352], [y0 + 11, y0 + 11], **k)
    ax.text(294, y0 + 15, "=" + (f.funcao or ""), fontsize=6)
    ax.text(294, y0 + 4, "+PAINEL", fontsize=6)
    ax.plot([352, 410], [y0 + 11, y0 + 11], **k)
    ax.text(354, y0 + 15, "Folha", fontsize=5)
    ax.text(408, y0 + 15, str(f.n), fontsize=6, ha="right", weight="bold")
    ax.text(354, y0 + 4, "Página", fontsize=5)
    ax.text(408, y0 + 4, f"{f.n} / {total}", fontsize=6, ha="right", weight="bold")


_PINO = re.compile(r"^(\d{1,2}|[LT]\s?[123]|A[12]|NO|NC|NA|NF)$")
AZUL_EPLAN, VERDE_XR, VERM_SEC = "#1f3fbf", "#5b8c32", "#d32f2f"


def _pinos(e):
    """(x, y, nome, lado) de cada borne com nome – desenhados junto do terminal, como no EPLAN."""
    out = []
    for lado in "nesw":
        k = 0
        while True:
            try:
                t = e.term(lado, k)
            except IndexError:
                break
            if t[4]:
                out.append((t[1], t[2], t[4], lado))
            k += 1
    return out


def _textos_sobrepostos(fig, ax, f):
    """Conferência automática do desenho: textos que se encostam/sobrepõem na folha (o que o desenhista corrigiria)."""
    fig.canvas.draw()
    r = fig.canvas.get_renderer()
    caixas = []
    for t in ax.texts:
        if not t.get_text().strip() or t.get_position()[1] < 32:     # carimbo/nota de rodapé ficam fora
            continue
        bb = t.get_window_extent(r)
        caixas.append((bb.x0 + 0.5, bb.y0 + 0.5, bb.x1 - 0.5, bb.y1 - 0.5, t.get_text()))
    out = []
    for i in range(len(caixas)):
        a = caixas[i]
        for b in caixas[i + 1:]:
            if a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]:
                out.append(dict(folha=f.n, titulo=f.titulo, a=a[4], b=b[4]))
    # texto atravessado por condutor (fio passando por cima de letra)
    tr = ax.transData
    segs = []
    for c in f.conds:
        pts = [tr.transform(_mm(x, y)) for x, y in rota(c["a"][1:3], c["b"][1:3], c.get("ym"))]
        segs += list(zip(pts, pts[1:]))
    for (x0, y0, x1, y1, txt) in caixas:
        for (p, q) in segs:
            if abs(p[0] - q[0]) < 0.5:          # vertical
                if x0 < p[0] < x1 and min(p[1], q[1]) < y1 and max(p[1], q[1]) > y0:
                    out.append(dict(folha=f.n, titulo=f.titulo, a=txt, b="(fio)"))
                    break
            elif abs(p[1] - q[1]) < 0.5:
                if y0 < p[1] < y1 and min(p[0], q[0]) < x1 and max(p[0], q[0]) > x0:
                    out.append(dict(folha=f.n, titulo=f.titulo, a=txt, b="(fio)"))
                    break
    return out


def render_pdf(proj, arq, pdf_extra=None, png_dir=None):
    """Folhas A3 no padrão gráfico do EPLAN (gabarito Electric): traço fino uniforme (0,25 mm), barramentos em azul com
    pontos de derivação vazados, seção marcada por traço oblíquo + texto vermelho só no último condutor do grupo, número de
    borne junto de cada terminal, tag à esquerda do símbolo em azul, dados em preto, referência cruzada em verde."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages
    from matplotlib.patches import Circle
    from . import estilo as _E
    E = _E.carregar()                       # estilo aprendido dos PDFs do EPLAN (dados/estilo_eplan.json)
    pt = 72 / 25.4
    LW = E["traco_mm"] * pt
    F_TAG, F_BOR, F_SEC = _E.pt(E["alt_tag_mm"]), _E.pt(E["alt_borne_mm"]), _E.pt(E["alt_secao_mm"])
    AZ, VM, VD, XR = E["cor_tag"], E["cor_secao"], E["cor_pe"], E["cor_xref"]
    xr = _xrefs(proj)
    tmp = arq if not pdf_extra else arq + ".tmp.pdf"
    rc = {"font.family": [E["fonte"], "Tahoma", "Arial", "Liberation Sans", "DejaVu Sans"], "pdf.fonttype": 42}
    conferencia = []
    with matplotlib.rc_context(rc), PdfPages(tmp) as pdf:
        for f in proj.folios:
            fig = plt.figure(figsize=(420 / 25.4, 297 / 25.4))
            ax = fig.add_axes([0, 0, 1, 1])
            ax.set_xlim(0, 420)
            ax.set_ylim(0, 297)
            ax.set_aspect("equal")
            ax.axis("off")
            _carimbo(ax, proj, f, len(proj.folios) + (_n_paginas(pdf_extra) if pdf_extra else 0), pt)
            grau = {}
            for c in f.conds:
                for t in (c["a"], c["b"]):
                    grau[t[0]] = grau.get(t[0], 0) + 1
            marcas, cmd_sec, todos_segs = [], {}, []
            for c in f.conds:
                pts = [_mm(x, y) for x, y in rota(c["a"][1:3], c["b"][1:3], c.get("ym"))]
                ea, eb = c["a"][3], c["b"][3]
                barra = ea.d.nome == "no" and eb.d.nome == "no" and ea.info.get("barra") and eb.info.get("barra")
                mc = (c.get("marca") or "").upper()
                if barra and not ea.info["barra"].startswith("-PE"):
                    cor, lw = AZ, LW * 1.4
                elif c["cor"] == "#2e7d32" or "VD" in mc:
                    cor, lw = VD, LW
                elif mc == "AZ":
                    cor, lw = AZ, LW
                else:
                    cor, lw = "k", LW
                ax.plot([p[0] for p in pts], [p[1] for p in pts], color=cor, lw=lw, solid_capstyle="butt", zorder=2)
                segs = list(zip(pts, pts[1:]))
                (x0, y0), (x1, y1) = max(segs, key=lambda sg: abs(sg[0][0] - sg[1][0]) + abs(sg[0][1] - sg[1][1]))
                xm, ym = (x0 + x1) / 2, (y0 + y1) / 2
                vert = abs(x0 - x1) < 0.2
                todos_segs.extend(segs)
                if c["secao"] and not barra and c["pot"] and abs(x0 - x1) + abs(y0 - y1) > 6:
                    marcas.append((xm, ym, vert, c["secao"], (x0, y0, x1, y1)))
                elif c["secao"] and not c["pot"]:
                    cmd_sec[(c["secao"], (c.get("marca") or "").upper())] = cmd_sec.get((c["secao"], (c.get("marca") or "").upper()), 0) + 1
                if c["num"] and not barra:
                    ax.text(xm + (0.9 if vert else 0), ym + (2.2 if vert else 0.7), c["num"], fontsize=F_BOR * 0.85, rotation=90 if vert else 0,
                            ha="left" if vert else "center", va="bottom", color="k", zorder=3)
            if cmd_sec:                              # comando: nota geral (como no EPLAN), sem marcar fio a fio
                cores = {"VM": "vermelho", "AZ": "azul", "PT": "preto", "CZ": "cinza", "VD/AM": "verde/amarelo"}
                secs = sorted({k[0] for k in cmd_sec})
                cs = sorted({cores.get(k[1], k[1]) for k in cmd_sec if k[1]})
                ax.text(16, 30.5, f"Fiação de comando: {' / '.join(x + ' mm²' for x in secs)} – cabo flexível 750 V, cores: "
                        f"{', '.join(cs)} (fase vermelho, neutro azul, sinal/alarme cinza), salvo indicação.", fontsize=F_BOR, color="0.25", zorder=5)
            ocupados, sem_lugar = [], []            # caixas de texto já colocadas (mm) – evita colisão entre marcas

            def livre(bx):
                x0_, y0_, x1_, y1_ = bx
                for (p_, q_) in todos_segs:
                    if abs(p_[0] - q_[0]) < 0.05:
                        if x0_ < p_[0] < x1_ and min(p_[1], q_[1]) < y1_ and max(p_[1], q_[1]) > y0_:
                            return False
                    elif y0_ < p_[1] < y1_ and min(p_[0], q_[0]) < x1_ and max(p_[0], q_[0]) > x0_:
                        return False
                return not any(x0_ < o[2] and o[0] < x1_ and y0_ < o[3] and o[1] < y1_ for o in ocupados)
            ch_mm = E["alt_secao_mm"]
            for (xm, ym, vert, sec, sg) in marcas:  # traço oblíquo em todos; texto só no último do grupo, em lugar livre
                txt = f"{sec} mm²" if sec != "barra" else "barra"
                w = 0.62 * ch_mm * len(txt)
                vizinho = any(abs(o[1] - ym) < 4 and 0 < o[0] - xm < 9 and o[3] == sec for o in marcas) if vert else \
                    any(abs(o[0] - xm) < 9 and 0 < ym - o[1] < 9 and o[3] == sec for o in marcas)
                x0, y0, x1, y1 = sg
                pos = (0.5, 0.35, 0.65, 0.2, 0.8)
                escolhido = None
                for t_ in pos:
                    tx, ty = x0 + (x1 - x0) * t_, y0 + (y1 - y0) * t_
                    cand = [(tx + 1.4, ty - ch_mm / 2), (tx - 1.4 - w, ty - ch_mm / 2)] if vert else \
                        [(tx + 1.2, ty + 0.4), (tx + 1.2, ty - 0.4 - ch_mm)]
                    for (cx_, cy_) in cand:
                        if vizinho or livre((cx_, cy_, cx_ + w, cy_ + ch_mm)):
                            escolhido = (tx, ty, cx_, cy_)
                            break
                    if escolhido:
                        break
                if not escolhido and not vizinho:   # sem lugar livre: escreve no fio mais à direita/abaixo do grupo
                    continue_txt = False
                else:
                    continue_txt = True
                tx, ty, cx_, cy_ = escolhido or (xm, ym, xm + 1.4, ym - ch_mm / 2)
                d = 0.8
                ax.plot([tx - d, tx + d], [ty - d, ty + d], color="k", lw=LW, zorder=3)
                if not vizinho and continue_txt:
                    ax.text(cx_, cy_, txt, fontsize=F_SEC, color=VM, va="bottom", ha="left", zorder=3)
                    ocupados.append((cx_, cy_, cx_ + w, cy_ + ch_mm))
                elif not vizinho:
                    sem_lugar.append((tx, ty, txt))
            for (tx, ty, txt) in sem_lugar:         # seção sem lugar livre: vai numa legenda no rodapé da folha
                pass
            if sem_lugar:
                ax.text(16, 284.5, "Seções não indicadas no desenho por falta de espaço: " + "; ".join(sorted({t for _, _, t in sem_lugar}))
                        + " – ver lista DE/PARA.", fontsize=F_SEC * 1.2, color=VM, zorder=5)
            for e in f.elems:
                if e.d.nome == "no":                 # ponto de derivação: só onde há derivação (3+ condutores)
                    g = sum(grau.get(t, 0) for t in e.tid)
                    if g >= 3:
                        x, y = _mm(e.x, e.y)
                        if e.info.get("barra") and not e.info["barra"].startswith("-PE"):
                            ax.add_patch(Circle((x, y), 0.75, fc="white", ec=AZ, lw=LW, zorder=6))
                        else:
                            ax.add_patch(Circle((x, y), 0.55, fc="k", ec="k", lw=0, zorder=6))
                    continue
                for p in primitivas_elemento(e):
                    if p[0] == "lin":
                        (x0, y0), (x1, y1) = _mm(*p[1][0]), _mm(*p[1][1])
                        ax.plot([x0, x1], [y0, y1], color="k", lw=LW, ls=(0, (3, 2)) if p[2] else "-", zorder=4)
                    elif p[0] == "pol":
                        q = [_mm(*a) for a in p[1]]
                        if p[3]:
                            ax.fill([a[0] for a in q], [a[1] for a in q], color="k", zorder=4)
                        else:
                            ax.plot([a[0] for a in q], [a[1] for a in q], color="k", lw=LW, ls=(0, (3, 2)) if p[2] else "-", zorder=4)
                    elif p[0] == "dad":
                        x, y = _mm(p[1], p[2])
                        ha = p[6] if len(p) > 6 else "left"
                        for k, ln in enumerate(str(p[3]).split("\n")):
                            ax.text(x, y - k * 2.6, ln, fontsize=F_BOR, color="k", va="baseline", ha=ha, zorder=5)
                    elif p[0] in ("txt", "lbl"):
                        if p[0] == "txt" and str(p[3]).split() and all(_PINO.match(tk) for tk in str(p[3]).split()):
                            continue                # nº de borne do símbolo: redesenhado abaixo, junto do terminal
                        x, y = _mm(p[1], p[2])
                        if p[3]:
                            ha = p[6] if len(p) > 6 else "left"
                            ax.text(x, y, p[3], fontsize=(p[4] * S_MM * pt * 0.95) if p[0] == "txt" else (F_TAG if p[4] > 7 else F_BOR), rotation=-p[5] if p[5] else 0,
                                    ha=ha, va="baseline", color=AZ if p[0] == "lbl" else "k", zorder=5)
                if e.d.nome not in ("borne_continuite",):
                    for (tx, ty, nm, lado) in _pinos(e):
                        X, Y = _mm(tx, ty)
                        if lado == "n":
                            ax.text(X + 0.6, Y - 1.4, nm, fontsize=F_BOR, color="k", ha="left", va="top", zorder=5)
                        elif lado == "s":
                            ax.text(X + 0.6, Y + 1.4, nm, fontsize=F_BOR, color="k", ha="left", va="bottom", zorder=5)
                        elif lado == "e":
                            ax.text(X - 1.0, Y + 0.5, nm, fontsize=F_BOR, color="k", ha="right", va="bottom", zorder=5)
                        else:
                            ax.text(X + 1.0, Y + 0.5, nm, fontsize=F_BOR, color="k", ha="left", va="bottom", zorder=5)
                if e.uuid in xr and xr[e.uuid]:
                    lb = [p for p in primitivas_elemento(e) if p[0] == "lbl"]
                    if e.d.link == "slave":
                        off = 17 if e.info.get("dados") else 8
                        x, y = _mm(lb[0][1], lb[0][2] + off) if lb else _mm(e.x + 14, e.y + 14)
                        ha = lb[0][6] if lb and len(lb[0]) > 6 else "left"
                        ax.text(x, y, " ".join(xr[e.uuid]), fontsize=F_BOR, color=XR, ha=ha, zorder=5)
                    else:                           # espelho de contatos sob a bobina, à direita do fio que desce
                        x, y = _mm(e.x + 5, e.y + 28)
                        ax.plot([x, x + 16], [y + 1.4, y + 1.4], color="k", lw=LW * 0.8, zorder=5)
                        for k, t in enumerate(xr[e.uuid][:8]):
                            ax.text(x, y - k * 2.6, t, fontsize=F_BOR * 0.9, color=XR, zorder=5)
            for (x, y, w, h, rot) in f.retangulos:
                (X0, Y0), (X1, Y1) = _mm(x, y), _mm(x + w, y + h)
                ax.plot([X0, X1, X1, X0, X0], [Y0, Y0, Y1, Y1, Y0], color="0.35", lw=LW, ls=(0, (8, 2, 1, 2)), zorder=1)
                if rot:
                    ax.text(X1 - 1, Y0 - 1.2, rot, fontsize=5.5, color="0.35", va="top", ha="right", zorder=1)
            for (x, y, t, size, cor) in f.textos:
                X, Y = _mm(x, y)
                ax.text(X, Y, t, fontsize=size * S_MM * pt, color=AZ if cor == "#1f4e8c" else cor, va="baseline", zorder=5)
            conferencia.extend(_textos_sobrepostos(fig, ax, f))
            if png_dir and f.n <= 4:
                fig.savefig(os.path.join(png_dir, f"esquema_folha_{f.n:02d}.png"), dpi=110)
            pdf.savefig(fig)
            plt.close(fig)
    proj.conferencia_desenho = conferencia
    if pdf_extra:
        from pypdf import PdfWriter, PdfReader
        w = PdfWriter()
        for a in (tmp, pdf_extra):
            for pg in PdfReader(a).pages:
                w.add_page(pg)
        with open(arq, "wb") as fh:
            w.write(fh)
        os.remove(tmp)
    return arq


def _n_paginas(pdf):
    from pypdf import PdfReader
    return len(PdfReader(pdf).pages)


def render_dxf(proj, arq):
    """Folhas lado a lado (passo 450 mm), camadas FIOS_FORCA / FIOS_COMANDO / SIMBOLOS / TEXTOS / MOLDURA."""
    import ezdxf
    doc = ezdxf.new("R2010", setup=True)
    msp = doc.modelspace()
    for nome, cor in (("MOLDURA", 8), ("FIOS_FORCA", 1), ("FIOS_COMANDO", 5), ("SIMBOLOS", 7), ("TEXTOS", 3)):
        doc.layers.add(nome, color=cor)
    xr = _xrefs(proj)
    for k, f in enumerate(proj.folios):
        ox = k * 450.0
        msp.add_lwpolyline([(ox + 10, 5), (ox + 410, 5), (ox + 410, 292), (ox + 10, 292)], close=True, dxfattribs={"layer": "MOLDURA"})
        msp.add_line((ox + 10, 27), (ox + 410, 27), dxfattribs={"layer": "MOLDURA"})
        msp.add_text(f"{proj.cliente} – {proj.titulo} – {f.titulo} – folha {f.n}/{len(proj.folios)}", height=3.0,
                     dxfattribs={"layer": "MOLDURA"}).set_placement((ox + 15, 15))
        for c in f.conds:
            pts = [_mm(x, y) for x, y in rota(c["a"][1:3], c["b"][1:3], c.get("ym"))]
            msp.add_lwpolyline([(ox + x, y) for x, y in pts], dxfattribs={"layer": "FIOS_FORCA" if c["pot"] else "FIOS_COMANDO"})
        for e in f.elems:
            for p in primitivas_elemento(e):
                if p[0] == "lin":
                    (x0, y0), (x1, y1) = _mm(*p[1][0]), _mm(*p[1][1])
                    msp.add_line((ox + x0, y0), (ox + x1, y1), dxfattribs={"layer": "SIMBOLOS"})
                elif p[0] == "pol":
                    msp.add_lwpolyline([(ox + a, b) for a, b in (_mm(*q) for q in p[1])], dxfattribs={"layer": "SIMBOLOS"})
                elif p[0] in ("txt", "lbl", "dad") and p[3]:
                    x, y = _mm(p[1], p[2])
                    msp.add_text(str(p[3]), height=max(p[4] * S_MM * 0.8, 1.2), dxfattribs={"layer": "TEXTOS"}).set_placement((ox + x, y))
            if xr.get(e.uuid):
                x, y = _mm(e.x + 14, e.y + 14)
                msp.add_text(" ".join(xr[e.uuid])[:80], height=1.2, dxfattribs={"layer": "TEXTOS"}).set_placement((ox + x, y))
        for (x, y, t, size, cor) in f.textos:
            X, Y = _mm(x, y)
            msp.add_text(t, height=size * S_MM * 0.8, dxfattribs={"layer": "TEXTOS"}).set_placement((ox + X, Y))
    doc.saveas(arq)
    return arq
