"""Relatório de AUDITORIA técnica (uso interno) – PDF completo para revisão por engenheiro externo (v1.10.0).

Reúne TUDO o que a plataforma calculou e decidiu, inclusive o que fica em segundo plano: entradas e premissas, modelo e
equações, varreduras e motivos de descarte, robustez, todas as verificações, ATP-EMTP, capacitores, projeto do indutor por
elementos finitos (perdas, térmico, isolação, desenhos), mecânica, custos, dados faltantes, normas, incertezas e itens em
aberto, e um formulário de parecer (OK / NÃO OK / ajustar) por item.
"""
import os
import json
import math
import datetime as _dt
import hashlib

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer, Table, TableStyle, Image, PageBreak,
                                KeepTogether)
from reportlab.platypus.tableofcontents import TableOfContents

AZ = colors.HexColor("#1b4f9c")

# Revisão dos filtros anteriores (planilhas do Drive) na plataforma v1.10 – fs 4 kHz, cabo 20 m, motor FP 0,85
HISTORICO = [
    ("IHR 2022 – 28 A 380 V", "1586 µH / 20 µF Y (fr 894 Hz)", "APROVADO – THD motor 5,3 %, ondulação 12 A p-p; alerta: amplificação "
     "teórica de baixa ordem 9,8 %", "NR por tensão: fr ≈ 1146 Hz (371,56 → 372,58 V) – divergente (ver nota)"),
    ("SENAI / Gelluns – 38 A 380 V", "958 µH / 40 µF Y (fr 813 Hz)", "APROVADO – THD motor 3,9 %; THD a vazio 7,1 % (alerta); "
     "amplificação de baixa ordem 10,9 % (alerta)", "NR por tensão: fr ≈ 831 Hz (364,1 → 366 V) – bate (2 %); termografia Gelluns 53 °C"),
    ("SENAI – 38 A 380 V", "958 µH / 20 µF Y (fr 1150 Hz)", "–", "NR por tensão: fr ≈ 1074 Hz – diferença 7 %"),
    ("AB-Powertrain – 48 A 380 V", "606 µH / 3×20 µF Δ (uk 5 %, fr 835 Hz)", "REPROVADO em 1 critério – ondulação 35 A p-p acima do "
     "limite (indutor de 5 % pequeno para fs 4 kHz); THD motor 5,0 %", "–"),
]
CINZA = colors.HexColor("#f2f4f7")


def _esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


class _Doc(BaseDocTemplate):
    def __init__(self, arq, cab, rotulo="USO INTERNO – VERIFICAÇÃO DO SISTEMA (não é auditoria independente)", **kw):
        self.rotulo = rotulo
        super().__init__(arq, pagesize=A4, leftMargin=16 * mm, rightMargin=16 * mm, topMargin=18 * mm, bottomMargin=16 * mm, **kw)
        self.cab = cab
        fr = Frame(self.leftMargin, self.bottomMargin, self.width, self.height, id="n")
        self.addPageTemplates([PageTemplate(id="p", frames=fr, onPage=self._pagina)])

    def _pagina(self, c, doc):
        c.saveState()
        c.setFont("Helvetica", 7)
        c.setFillColor(colors.grey)
        c.drawString(16 * mm, A4[1] - 11 * mm, self.cab)
        c.drawRightString(A4[0] - 16 * mm, A4[1] - 11 * mm, self.rotulo)
        c.drawString(16 * mm, 9 * mm, "Electric Service – Plataforma FSEN")
        c.drawRightString(A4[0] - 16 * mm, 9 * mm, f"pág. {doc.page}")
        c.restoreState()

    def afterFlowable(self, f):
        if isinstance(f, Paragraph) and f.style.name in ("H1", "H2"):
            lvl = 0 if f.style.name == "H1" else 1
            self.notify("TOCEntry", (lvl, f.getPlainText(), self.page))


class Rel:
    def __init__(self):
        ss = getSampleStyleSheet()
        self.st = dict(
            H1=ParagraphStyle("H1", parent=ss["Heading1"], fontSize=14, textColor=AZ, spaceBefore=10, spaceAfter=6),
            H2=ParagraphStyle("H2", parent=ss["Heading2"], fontSize=11, textColor=AZ, spaceBefore=8, spaceAfter=4),
            H3=ParagraphStyle("H3", parent=ss["Heading3"], fontSize=9.5, spaceBefore=6, spaceAfter=3),
            P=ParagraphStyle("P", parent=ss["BodyText"], fontSize=8.6, leading=11.2, spaceAfter=4),
            PP=ParagraphStyle("PP", parent=ss["BodyText"], fontSize=7.2, leading=9),
            M=ParagraphStyle("M", parent=ss["Code"], fontSize=7.4, leading=9.2, backColor=CINZA, borderPadding=3, spaceAfter=6),
            CAPA=ParagraphStyle("CAPA", parent=ss["Title"], fontSize=22, textColor=AZ, leading=26),
        )
        self.f = []
        self.n1 = 0
        self.n2 = 0

    def h1(self, t):
        self.n1 += 1
        self.n2 = 0
        self.f.append(Paragraph(f"{self.n1}. {_esc(t)}", self.st["H1"]))

    def h2(self, t):
        self.n2 += 1
        self.f.append(Paragraph(f"{self.n1}.{self.n2} {_esc(t)}", self.st["H2"]))

    def h3(self, t):
        self.f.append(Paragraph(_esc(t), self.st["H3"]))

    def p(self, t, raw=False):
        self.f.append(Paragraph(t if raw else _esc(t), self.st["P"]))

    def eq(self, t):
        self.f.append(Paragraph(_esc(t).replace("\n", "<br/>"), self.st["M"]))

    def bul(self, itens):
        for it in itens:
            self.f.append(Paragraph("• " + _esc(it), self.st["P"]))

    def tab(self, cab, linhas, larg=None, fs=7.0):
        st = ParagraphStyle("t", fontSize=fs, leading=fs * 1.22)
        dados = [[Paragraph(f"<b>{_esc(c)}</b>", st) for c in cab]] + [[Paragraph(_esc(_fmt(x)), st) for x in l] for l in linhas]
        W = 178 * mm
        if larg:
            s = sum(larg)
            larg = [W * x / s for x in larg]
        t = Table(dados, colWidths=larg, repeatRows=1)
        t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dde6f3")), ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
                               ("VALIGN", (0, 0), (-1, -1), "TOP"), ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, CINZA])]))
        self.f.append(t)
        self.f.append(Spacer(1, 5))

    def kv(self, d, titulo=None, fs=7.0):
        if titulo:
            self.h3(titulo)
        self.tab(["Grandeza", "Valor"], [(k, v) for k, v in _achatar(d)], [1.2, 2.4], fs)

    def img(self, path, w=178, legenda=None):
        if path and os.path.exists(path):
            from reportlab.lib.utils import ImageReader
            iw, ih = ImageReader(path).getSize()
            h = w * ih / iw
            if h > 235:
                w, h = w * 235 / h, 235
            self.f.append(Image(path, width=w * mm, height=h * mm))
            if legenda:
                self.f.append(Paragraph(f"<i>{_esc(legenda)}</i>", self.st["PP"]))
            self.f.append(Spacer(1, 5))

    def quebra(self):
        self.f.append(PageBreak())


def _fmt(x):
    if isinstance(x, bool):
        return "sim" if x else "não"
    if isinstance(x, float):
        if x != x:
            return "–"
        a = abs(x)
        return f"{x:.4g}" if (a < 0.01 or a >= 1e5) and a != 0 else (f"{x:.3f}" if a < 10 else f"{x:.1f}")
    if isinstance(x, (list, tuple)):
        return ", ".join(_fmt(v) for v in x[:40]) + (" …" if len(x) > 40 else "")
    return str(x)


def _achatar(d, pre=""):
    out = []
    if isinstance(d, dict):
        for k, v in d.items():
            if str(k).startswith("_"):
                continue
            if isinstance(v, dict) and len(v) <= 40:
                out += _achatar(v, f"{pre}{k}.")
            elif isinstance(v, list) and v and isinstance(v[0], dict):
                out.append((f"{pre}{k}", f"[{len(v)} registros – ver tabelas]"))
            else:
                out.append((f"{pre}{k}", v))
    return out


def _sha(path):
    try:
        return hashlib.sha256(open(path, "rb").read()).hexdigest()[:16]
    except Exception:
        return "–"


# ---------------------------------------------------------------------------------------------------------------------
def gerar(proj, arr, orc, cat, pasta, ind=None, graficos=None, log=print):
    from .versao import info as vinfo
    from .modelos import Pedido
    ped = Pedido.from_dict(proj.pedido) if isinstance(proj.pedido, dict) else proj.pedido
    v = vinfo()
    cod = os.path.basename(pasta)
    eng = os.path.join(pasta, "01_Engenharia")
    arq = os.path.join(eng, f"VERIFICACAO_SISTEMA_{cod}.pdf")   # v1.28.0: era AUDITORIA_ (auditoria D/§6.1)
    R = Rel()
    hoje = _dt.datetime.now()
    # ------------------------------------------------------------------ capa
    R.f.append(Spacer(1, 40 * mm))
    R.f.append(Paragraph("Relatório de Verificação do Sistema", R.st["CAPA"]))
    R.f.append(Paragraph(f"Filtro senoidal {proj.topologia} – {ped.corrente_a:g} A / {ped.tensao_v:g} V – {_esc(ped.cliente)}", R.st["H2"]))
    R.f.append(Spacer(1, 10 * mm))
    R.tab(["Campo", "Valor"], [("Projeto", cod), ("Emissão", hoje.strftime("%d/%m/%Y %H:%M")),
                               ("Plataforma", f"FSEN v{v.get('versao')} ({v.get('data')})"), ("Resumo da versão", v.get("resumo", "")),
                               ("Status do projeto", "APROVADO" if proj.aprovado else "REPROVADO"),
                               ("Finalidade", "Uso interno – dossiê gerado pela própria plataforma para SUBSIDIAR uma auditoria independente. NÃO é auditoria: "
                                              "foi gerado pelo mesmo sistema que fez o projeto. A auditoria só vale com o parecer assinado de um engenheiro externo.")],
          [1, 3])
    R.p("Este relatório reúne todos os dados, modelos, cálculos, simulações e decisões da plataforma para este projeto, "
        "inclusive os que não aparecem nos documentos ao cliente ou aos fornecedores. A seção final traz o formulário de parecer.")
    R.quebra()
    toc = TableOfContents()
    toc.levelStyles = [ParagraphStyle("t0", fontSize=9.5, leading=12, leftIndent=0), ParagraphStyle("t1", fontSize=8, leading=10, leftIndent=12)]
    R.f.append(Paragraph("Sumário", R.st["H1"]))
    R.f.append(toc)
    R.quebra()
    # ------------------------------------------------------------------ 1 instruções ao auditor
    R.h1("Escopo da auditoria e como ler este relatório")
    R.bul(["Verificar se as premissas e os dados de entrada são adequados à aplicação.",
           "Verificar o modelo de simulação (equações, parâmetros parasitas, pontos de operação) e a dupla checagem no ATP-EMTP.",
           "Verificar critérios de aprovação e limites adotados frente às normas citadas.",
           "Verificar a escolha da configuração (varreduras, robustez, regra de decisão) e o dimensionamento de capacitores e indutor.",
           "Verificar o projeto de referência do indutor (elementos finitos, perdas, térmico, sistema de isolação, desenhos).",
           "Apontar riscos não cobertos e ajustes recomendados no formulário de parecer (última seção)."])
    R.p("Convenções: valores em SI salvo indicação; 'crítico' = reprova o projeto; 'alerta' = não reprova, mas deve ser tratado.")
    # ------------------------------------------------------------------ 2 entradas
    R.h1("Dados de entrada e premissas")
    R.h2("Pedido (todos os campos)")
    pd_ = ped.to_dict()
    inf = set(pd_.get("informados") or [])
    R.tab(["Campo", "Valor", "Origem"], [(k, vv, "informado" if k in inf else "adotado/padrão") for k, vv in pd_.items()
                                        if k not in ("lacunas", "informados", "observacoes")], [1.3, 2.4, 0.8])
    R.h2("Lacunas e premissas adotadas")
    R.bul(pd_.get("lacunas") or ["–"])
    secao_corrente_pdf(R, getattr(proj, "corrente_dimensionamento", None))
    if pd_.get("observacoes"):
        R.h2("Observações da leitura do pedido")
        R.p(pd_["observacoes"])
    # ------------------------------------------------------------------ 3 normas
    R.h1("Normas e referências aplicadas")
    R.tab(["Referência", "Uso no projeto"], [
        ("IEEE 519 / prática de fabricantes", "THD de tensão no motor ≤ 5 % (meta), crítico ≤ 6 %"),
        ("IEC TS 60034-25 / NEMA MG1 Pt. 30-31", "pico, dv/dt e rise time no motor; motores alimentados por inversor"),
        ("IEC 60034-1", "zona de tensão do motor; tensão disponível ≥ 100 % do V/f na faixa de operação"),
        ("IEC 61071", "capacitores de eletrônica de potência: tensão, corrente RMS, pico, Vcc máx, vida"),
        ("IEC 60831 (contraponto)", "capacitor de correção de FP – NÃO aceito para filtro PWM"),
        ("IEC 60076-6 / IEC 60076-11", "reatores e secos: ensaios, dados de placa, limites de elevação de temperatura"),
        ("IEC 60085 / IEC 61857 / UL 1446", "classe térmica do SISTEMA de isolação"),
        ("IEC 60664-1 / IEC 61800-5-1", "distâncias de isolação (separação e escoamento), cat. III, PD3"),
        ("IEC 60404-8-7 / 60404-8-4", "aço-silício GO / GNO (perdas especificadas)"),
        ("IEC 60893-3-x", "laminados isolantes (EP GC 203, SI GC 202, UP GM 203)"),
        ("MTE Corp. (T. Luu, IEEE 2020); manual SineWave Guardian", "L 8–10 % de Zb; fr 25–35 % de fs; inserção ≤ 6 %"),
        ("Schaffner FN5040, REO CNW 933", "referências de L, perdas e massa por corrente"),
        ("FRAKO – guia de projeto PEC", "UN do capacitor ≥ Vcc máx; perdas dielétricas"),
        ("Dowell (1966); Lammeraner & Stafl", "perdas CA em folha; correntes parasitas em lâmina"),
        ("ATP-EMTP (ATPDraw/tpbig)", "dupla checagem independente das simulações"),
    ], [1.4, 2.6])
    # ------------------------------------------------------------------ 4 modelo
    R.h1("Modelo de simulação")
    R.p("Simulação no domínio do tempo do inversor PWM (portadora triangular, modulação senoidal com injeção de 3ª harmônica / SVPWM "
        "equivalente, tempo morto), filtro LC (L1 com R série e Q finito em alta frequência; banco de capacitores Y/Δ equivalente), "
        "cabo em células π (R, L, C fase-fase e fase-terra) e motor (R, L de dispersão, Lm, FCEM, capacitância enrolamento–carcaça). "
        "Os mesmos parâmetros vão para o deck do ATP-EMTP.")
    R.eq("Circuito por fase (equivalente Y):\n  L1·di1/dt = u_inv − v_c − R1·i1\n  C_y·dv_c/dt = i1 − i_cabo\n"
         "Ressonância: fr = 1/(2π·√(L1·C_y))   (C_y = 3·C_Δ por ramo, se Δ)\n"
         "Ondulação p-p (aprox.): ΔI ≈ Vcc/(8·L1·fs)·k_mod ;  THD por FFT até 4·fs (4,6·fs na comparação ATP)")
    try:
        R.kv(proj.circuito().__dict__, "Parâmetros do circuito usados")
    except Exception:
        pass
    for k in ("cabos_parametros", "motor_modelo", "modo_comum", "otimizacao", "projeto_padrao", "atp"):
        if k in cat and isinstance(cat[k], dict):
            R.kv(cat[k], f"Catálogo – {k}")
    R.h2("Pontos de operação simulados")
    if proj.pontos:
        chaves = list(proj.pontos[0].keys())[:9]
        R.tab(chaves, [[pt.get(k) for k in chaves] for pt in proj.pontos], fs=6.2)
    # ------------------------------------------------------------------ 5 seleção
    R.h1("Seleção da configuração")
    eo = getattr(proj, "estudo_opcoes", None)
    if eo:
        R.h2("Varredura – mínimo de capacitores (capacitor forçado)")
        R.p("Critérios: " + eo["criterios"]["regra"] + f". Perda de inserção máx. {eo['criterios']['queda_max']} %.")
        R.tab(["Caps", "L µH", "uk %", "fr Hz", "aprov.", "robusto", "THD %", "THD pior %", "inserção %", "queda L %", "custo R$", "falhas críticas"],
              [(x["n_caps"], x["L_uh"], x["uk_pct"], x["fr_hz"], x["aprovado"], x["robusto"], x["thd"], x["thd_pior"], x["insercao"],
                x["queda"], x["custo"], "; ".join(f[:40] for f in x["falhas"])) for x in sorted(eo["linhas"], key=lambda x: (x["n_caps"], x["L_uh"]))],
              [0.5, 0.6, 0.5, 0.6, 0.5, 0.6, 0.6, 0.7, 0.7, 0.6, 0.7, 3.0], fs=5.6)
        for a in eo.get("abaixo", []):
            R.p(f"{a['n_caps']} capacitores: {a['motivo']}")
    em = getattr(proj, "estudo_mercado", None)
    if em:
        R.h2("Ponto ótimo de mercado e robustez")
        R.kv({k: em[k] for k in ("atual", "recomendada", "faixa_mte_uh", "cap_vcc", "aviso_cabo") if k in em})
        for nome in ("robustez_atual", "robustez_recomendada"):
            rb = em.get(nome)
            if rb:
                R.h3(nome.replace("_", " "))
                R.tab(list(rb["casos"][0].keys())[:8], [[c.get(k) for k in list(rb["casos"][0].keys())[:8]] for c in rb["casos"]], fs=6.2)
    df = getattr(proj, "_otimizacao", None)
    if df is not None and len(df):
        R.h2("Otimização global (todas as configurações avaliadas – primeiras 60 por custo)")
        cols = [c for c in df.columns][:12]
        R.tab(cols, df.sort_values(df.columns[0]).head(60)[cols].values.tolist(), fs=5.4)
    # ------------------------------------------------------------------ 6 projeto final e verificações
    R.h1("Projeto final e verificações")
    R.kv(dict(topologia=proj.topologia, fs_hz=proj.fs_hz, vdc=proj.vdc, fr_hz=proj.fr_hz, aprovado=proj.aprovado,
              custo_componentes=proj.custo_componentes, q_hf=proj.q_hf, lm_h=proj.lm_h, rm_ohm=proj.rm_ohm), "Resumo")
    R.kv(proj.l1.__dict__, "Indutor L1 (modelo do circuito)")
    R.kv(proj.banco.__dict__, "Banco de capacitores")
    R.h2("Todas as verificações")
    R.tab(["Item", "Valor", "Limite", "OK", "Crítico"], [(x.item, x.valor, x.limite, x.ok, x.critico) for x in proj.verificacoes],
          [3.2, 1.6, 1.4, 0.4, 0.5], fs=6.4)
    if proj.condicoes_extremas:
        R.h2("Condições extremas")
        ks = list(proj.condicoes_extremas[0].keys())[:8]
        R.tab(ks, [[c.get(k) for k in ks] for c in proj.condicoes_extremas], fs=6.2)
    if proj.sistema:
        R.kv(proj.sistema, "Sistema (cabo, motor, modo comum)")
    if proj.avisos:
        R.h2("Avisos registrados")
        R.bul(proj.avisos)
    # ------------------------------------------------------------------ 7 gráficos
    if graficos:
        R.h1("Formas de onda, espectros e respostas")
        for k, pth in graficos.items():
            if isinstance(pth, str) and pth.lower().endswith(".png"):
                R.img(pth, 170, k)
    # ------------------------------------------------------------------ 8 ATP
    R.h1("Dupla checagem no ATP-EMTP")
    da = getattr(proj, "dupla_checagem_atp", None) or {}
    R.p(f"Status: {da.get('status', 'não executada neste computador')} – {da.get('msg', '')}")
    R.p("Método: mesmos parâmetros do Python exportados para deck .atp; tpbig executado automaticamente; leitura do .pl4 truncada no "
        "tamanho declarado no cabeçalho (evita cauda de execução anterior); ATP reamostrado na grade do Python e alinhado pela "
        "correlação cruzada da parcela de alta frequência (o f1 do deck é ajustado ao passo de tempo). Tolerâncias por grandeza na tabela.")
    for x in (da.get("resultados") or []):
        R.h3(str(x.get("ponto")))
        R.tab(["Grandeza", "Python", "ATP", "Dif. %", "Tol. %", "OK"], [(l.get("grandeza"), l.get("python"), l.get("atp"), l.get("dif_pct"),
                                                                      l.get("tol_pct"), l.get("convergiu")) for l in x.get("tabela", [])],
              [3, 1, 1, 0.7, 0.7, 0.5], fs=6.4)
    # ------------------------------------------------------------------ 9 capacitores
    R.h1("Capacitores")
    capd = next((c for c in cat["capacitores"] if c["id"] == proj.banco.cap_id), {})
    R.kv(capd, "Dados do capacitor (catálogo)")
    if proj.estresse_capacitor:
        R.kv(proj.estresse_capacitor, "Estresse calculado")
    # ------------------------------------------------------------------ 10 indutor
    if ind:
        _secao_indutor(R, ind, pasta)
    # ------------------------------------------------------------------ calibração e histórico
    R.h1("Calibração do método do indutor e revisão de filtros anteriores")
    try:
        from .ind_projeto import calibracao
        cal = calibracao()
        R.p("O mesmo método de pré-dimensionamento foi aplicado aos indutores que a Cootrans já forneceu à Electric. A comparação de "
            "massa e dimensões mostra se o método chega ao porte construtivo que o fabricante pratica (dados internos – espiras, seção, "
            "chapa – não disponíveis; quando chegarem, calibrar também perdas e elevação).")
        R.tab(["Indutor real", "Fonte", "Real A×L×P (mm) / kg", "Método A×L×P (mm) / kg", "N", "coluna (mm)", "folha (mm)", "Perdas est. (W)"],
              [(c["ref"]["nome"], c["ref"]["fonte"], f"{c['ref']['dims'][0]}×{c['ref']['dims'][1]}×{c['ref']['dims'][2]} / {c['ref']['massa']}",
                (f"{c['dims'][0]:.0f}×{c['dims'][1]:.0f}×{c['dims'][2]:.0f} / {c['massa']:.0f}" if c["ok"] else "sem solução"),
                c.get("N"), (f"{c['a']:.0f}×{c['b']:.0f}" if c["ok"] else ""), (f"{c['tf']:.1f}×{c['hf']:.0f}" if c["ok"] else ""),
                (f"{c['perdas']:.0f}" if c["ok"] else "")) for c in cal], [1.6, 1.6, 1.1, 1.1, 0.4, 0.7, 0.7, 0.7], fs=6.2)
    except Exception as e:
        R.p(f"Calibração não executada: {e}")
    try:
        R.h2("Filtros anteriores (planilha Filtro Senoidal LC) reavaliados na plataforma")
        R.tab(["Filtro", "L / C", "Resultado na plataforma (fs 4 kHz)", "Medição de campo"], HISTORICO, [1.3, 1.2, 2.6, 1.6], fs=6.4)
        R.p("Método da planilha: L pelo uk% da carga, C pela ressonância escolhida (≈ 13–15 × f). Não avalia a ondulação, a ressonância "
            "frente ao espectro PWM nem tolerâncias – é o que a plataforma passou a verificar. O cálculo 'NR por tensão' "
            "(fr/f = √(Vsaída/(Vsaída−Ventrada))) é sensível: diferenças de 1 V em 370 V estão na incerteza do medidor e a carga reduz a "
            "elevação de tensão, superestimando fr; usar como indicação, não como medida.")
    except Exception:
        pass
    # ------------------------------------------------------------------ 11 mecânica / térmico / custos
    R.h1("Arranjo mecânico, térmico do painel e custos")
    try:
        R.kv(arr.to_dict(), "Arranjo e térmico")
    except Exception:
        pass
    try:
        od = orc.to_dict()
        itens = od.pop("itens", None)
        R.kv(od, "Orçamento – resumo")
        if itens:
            ks = list(itens[0].keys())[:7]
            R.tab(ks, [[i.get(k) for k in ks] for i in itens], fs=6.0)
    except Exception:
        pass
    # ------------------------------------------------------------------ 12 dados faltantes
    df_ = getattr(proj, "dados_faltantes", None)
    if df_:
        R.h1("Dados faltantes e sensibilidade")
        ks = [k for k in df_["itens"][0].keys()][:6] if df_["itens"] else []
        if ks:
            R.tab(ks, [[i.get(k) for k in ks] for i in df_["itens"]], fs=6.0)
    # ------------------------------------------------------------------ 13 incertezas
    R.h1("Limitações, incertezas e itens em aberto")
    R.bul([
        "ATP-EMTP confirma a implementação matemática (mesmo modelo e parâmetros), não os valores reais dos parasitas: validação final por medição em campo (THD no motor, corrente no capacitor, temperatura do indutor).",
        "Parasitas de cabo e motor: valores típicos do catálogo; sensibilidade avaliada (cabo ¼×–4×, capacitância do motor ×3) com efeito pequeno no THD diferencial.",
        "Frequência de chaveamento: o projeto depende de fs fixa (ver proposta). Inversor que reduz fs por temperatura pode deslocar a operação para perto da ressonância – travar fs mínima no comissionamento.",
        "Alertas não críticos (amplificação teórica de harmônicas de tempo morto, THD a vazio, tensão no mancal): ver verificações; tratar no comissionamento/recomendações ao cliente.",
        "Modo comum: o filtro senoidal diferencial não reduz tensão de modo comum; risco de corrente de mancal em motor sem mancal isolado.",
        "Indutor: elementos finitos 2D com correção analítica 3D (±5 % em L); perdas no núcleo com PWM por separação de perdas calibrada no catálogo (±20–30 %); térmico por coeficiente global (±15 K) – protótipo com ensaio de aquecimento obrigatório.",
        "Referências de mercado interpoladas de catálogos; capacitância Schaffner por ramo assumida.",
    ])
    # ------------------------------------------------------------------ 14 anexos / rastreabilidade
    R.h1("Rastreabilidade")
    arqs = []
    for raiz, _, fs in os.walk(pasta):
        for f in fs:
            p = os.path.join(raiz, f)
            if os.path.getsize(p) < 60e6:
                arqs.append((os.path.relpath(p, pasta), f"{os.path.getsize(p) / 1024:.0f} kB", _sha(p)))
    R.tab(["Arquivo", "Tamanho", "SHA-256 (16)"], sorted(arqs)[:300], [3.4, 0.6, 1.0], fs=5.8)
    # ------------------------------------------------------------------ 15 parecer
    R.h1("Formulário de parecer do auditor")
    itens = ["Dados de entrada e premissas", "Normas e limites adotados", "Modelo de simulação e parâmetros", "Dupla checagem ATP",
             "Escolha da configuração (varredura/robustez)", "Capacitores (IEC 61071, Vcc, vida)", "Indutor – requisitos elétricos",
             "Indutor – projeto magnético e FEM", "Indutor – perdas e térmico", "Indutor – sistema de isolação e distâncias",
             "Indutor – mecânica, desenhos e lista de materiais", "Arranjo do painel e térmico", "Riscos de campo (fs, modo comum, mancal)",
             "Ensaios e critérios de aceitação"]
    R.tab(["#", "Item", "OK", "NÃO OK", "Ajustar", "Comentário do auditor"], [(i + 1, t, "☐", "☐", "☐", "") for i, t in enumerate(itens)],
          [0.3, 2.6, 0.4, 0.5, 0.5, 3.2], fs=7.5)
    R.p("Parecer final:  ☐ Aprovado   ☐ Aprovado com ressalvas   ☐ Reprovado          Auditor: ____________________   Data: ___/___/____")
    doc = _Doc(arq, f"{cod} – {ped.cliente} – FSEN v{v.get('versao')}")
    doc.multiBuild(R.f)
    log(f"   Relatório de auditoria gerado: {os.path.basename(arq)}")
    return arq


def secao_corrente_pdf(R, cc):
    """v1.11: base da corrente – o cobre vai pela carga, o ferro vai pelo inversor."""
    if not cc:
        return
    R.h2("Corrente de dimensionamento – definida pela carga (cobre) e pelo inversor (ferro)")
    if cc.get("base") != "carga":
        R.p("Corrente = informada pelo cliente. " + " ".join(cc.get("notas", [])))
        return
    R.p("A corrente térmica do filtro é definida pela Electric Service a partir da carga: motor × FS, soma fasorial com as correntes "
        "dos capacitores e do cabo (sem crédito da compensação capacitiva), ondulação de alta frequência em quadratura e margem. "
        "A saturação e a sobrecarga são verificadas com a corrente do inversor. A corrente do cliente é informativa.")
    R.tab(["Parcela", "Cálculo", "A", "Observação"],
          [(c["item"], c["conta"], f"{c['valor_a']:.1f}", c["obs"]) for c in cc["componentes"]]
          + [("Saturação: L ≥ 90 % até", "máx(1,25 × pico na I térmica; √2·I_inv + ripple/2)", f"{cc['isat_a']:.0f} pk", ""),
             ("Sobrecarga do inversor: L ≥ 70 % até", "1,5·√2·I_inv + ripple/2", f"{cc['iovl_a']:.0f} pk", "60 s, 1×/h"),
             ("Corrente pedida pelo cliente", "", f"{cc.get('i_cliente_a', 0):g}", "informativa")], [2.4, 2.6, 0.8, 2.0])
    R.eq("I_fund = max(|I_m·(FP − j·sen φ) + j·(I_cap + I_cabo)|, I_m)\nI_rms = √(I_fund² + I_ripple,rms²)\n"
         "I_term = ⌈margem · I_rms⌉\nIsat ≥ max(1,25·Î_sim(I_term), √2·I_inv + ΔI_pp/2)\nIovl = 1,5·√2·I_inv + ΔI_pp/2")
    R.bul(cc.get("notas") or [])


def _secao_indutor(R, d, pasta):
    r = d["requisitos"]
    R.h1("Indutor – projeto de referência para fabricação (elementos finitos)")
    secao_corrente_pdf(R, d.get("corrente_dimensionamento"))
    if d.get("comparacao_condutor"):
        R.h2("Melhor alumínio × melhor cobre (2 entreferros por coluna + fio/barra retangular)")
        R.tab(["Condutor", "Fio t×h×paralelos", "Chapa", "Espiras", "Coluna (mm)", "Perdas FEM (W)", "Custo triagem (R$)", "Escolhido"],
              [(c["condutor"], c["fio"], c["chapa"], c["N"], c["coluna"], c["perdas_W"], c["custo_triagem"],
                "sim" if c["escolhido"] else "") for c in d["comparacao_condutor"]], [0.8, 1.3, 1.0, 0.6, 0.8, 0.8, 0.9, 0.6])
    if d.get("triagem_fio"):
        R.h2("Triagem por elementos finitos dos candidatos de fio retangular")
        R.p("O pré-dimensionamento analítico gera os candidatos mais baratos (núcleo, espiras, bitola, paralelos, camadas); cada um é "
            "conferido no FEM com os 2 entreferros nas culatras (perda no enrolamento com espraiamento real) + núcleo + perda de "
            "entreferro (Lee). Fica o mais barato que passa nos limites.")
        R.tab(["Cond.", "Chapa", "Fio t×h×par. (mm)", "Esp.", "Cam.", "Coluna", "Enrol. (W)", "Total (W)", "Massa (kg)", "Custo (R$)", "Passa"],
              [(x["cond"], x["chapa"], x["fio"], x["N"], x["camadas"], x["coluna"], x["P_enrol_W"], x["P_total_W"], x.get("massa_kg", ""),
                x.get("custo") or "", "sim" if x["ok"] else "não") for x in d["triagem_fio"]],
              [0.45, 0.8, 1.1, 0.35, 0.35, 0.65, 0.6, 0.6, 0.6, 0.65, 0.4])
        R.p("Custo da triagem = chapa + condutor (R$/kg estimados) + perdas capitalizadas (R$ 1,5/W) + mão de obra R$ 10/kg (estimativa). "
            "Exige folga: perdas ≤ 92 % do limite e elevação ≤ 90 % da meta.")
    if d.get("perdas", {}).get("nucleo_entreferro"):
        R.p(f"Perda adicional no núcleo junto aos entreferros (fórmula empírica de Lee/McLyman, Pg = Ki·E·lg·f·B², Ki = 0,155 para "
            f"lâminas): {d['perdas']['nucleo_entreferro']:.0f} W – somada às perdas como margem para o efeito 3D que o FEM 2D não vê.")
    R.p("Condutor: " + __import__("fsen.ind_projeto", fromlist=["descr_condutor"]).descr_condutor(d) + ".")
    if d.get("avisos"):
        R.h2("Avisos do projeto do indutor")
        R.bul(d["avisos"])
    R.p(f"Construção do entreferro: {'2 por coluna nas juntas coluna–culatra (padrão nacional)' if d.get('pos_gap') == 'culatra' else str(d.get('ng')) + ' distribuídos por coluna (multigap, coluna em pacotes)'}.")
    R.h2("Requisitos elétricos (da simulação do filtro)")
    R.kv({k: v for k, v in r.items()})
    R.h2("Metodologia")
    R.bul(["Pré-dimensionamento analítico: varredura de espiras × seção do núcleo (incl. núcleo maior que o mínimo para reduzir "
           "perdas AF) × espessura e altura da folha × canais de ventilação; restrições: B(Isat) ≤ 1,45 T, entreferro por peça ≤ 3 mm, "
           "entreferro total ≤ 20 % da coluna, elevação ≤ meta; custo = material + R$1,5/W de perda.",
           "Elementos finitos 2D (potencial vetor, triângulos P1): não-linear com curva B-H GO para saturação; linear para matriz de "
           "indutâncias e ajuste do entreferro (com correção 3D do espraiamento nas faces frontal/traseira); harmônico no tempo com "
           "correntes induzidas e corrente imposta por condutor para as perdas no enrolamento de folha (blindagem e efeito pelicular reais).",
           "Perdas no núcleo elemento a elemento: 60 Hz por separação de perdas (Steinmetz + clássica + excesso, calibrado no P1,7/50 do "
           "aço); AF a partir do " + ("ESPECTRO HARMÔNICO de projeto do banco (V_h = ω_h·L·I_h)" if d["requisitos"].get("aplicacao")
                                      else "ESPECTRO REAL da tensão PWM sobre o indutor (simulação)") + ", correntes parasitas na lâmina com efeito "
           "pelicular (Lammeraner/Stafl) e laços menores de histerese com fator de polarização.",
           "Térmico: elevação média = perdas / (h·área efetiva), h = coeficiente global (convecção + radiação) do painel ventilado; "
           "ponto quente = ambiente do painel + elevação + 15 K (IEC 60076-11)."])
    R.eq("Correntes parasitas na lâmina (fluxo médio B imposto, freq. f, espessura d):\n"
         "  P_v = σω²d²B²/24 · (3/ξ)·(sinh ξ − sin ξ)/(cosh ξ − cos ξ),  ξ = d/δ,  δ = √(2ρ/(ωμ0μr))\n"
         "Perdas no enrolamento (FEM harmônico): J = σ(−jωA + u_j),  ∫J dS = I_j  →  P = ∫|J|²/(2σ) dS · ℓ\n"
         "Indutância de sequência positiva por fase: L+ = L_kk − ½·Σ_j≠k M_kj")
    R.h2("Geometria e materiais")
    geo = {k: d[k] for k in ("N", "kae", "a", "b", "tf", "hf", "nd", "c", "ng", "build", "hc", "hw", "ww", "MLT") if k in d}
    R.kv(geo)
    R.kv(dict(chapa=d["chapa_dados"], condutor=d["cond_dados"]))
    R.h2("Entreferros – estudo nº de peças × distância bobina–núcleo")
    R.tab(list(d["estudo_gap"][0].keys()), [list(e.values()) for e in d["estudo_gap"]], fs=6.5)
    R.p(f"Entreferro final (total por coluna): laterais {d['gaps'][0]*1e3:.2f} mm, central {d['gaps'][1]*1e3:.2f} mm, em {d['ng']} peças.")
    R.p(f"Indutância (3D corrigida): {', '.join(f'{x*1e6:.1f}' for x in d['L3d'])} µH; 2D: {', '.join(f'{x*1e6:.1f}' for x in d['L2d'])} µH.")
    R.h2("Saturação (FEM não-linear)")
    R.tab(list(d["saturacao"][0].keys()), [[(f"{x:.4g}" if isinstance(x, float) else x) for x in s.values()] for s in d["saturacao"]], fs=6.2)
    if d.get("saturacao_nota"):
        R.p(d["saturacao_nota"])
    R.h2("Perdas")
    R.kv(d["perdas"])
    R.kv(dict(Rdc_ohm=d.get("Rdc_ohm"), **(d.get("Rac_ohm") or {})), "Resistências (por fase)")
    R.h2("Térmico")
    R.kv(d["termico"])
    R.h2("Forças, dimensões e massas")
    R.kv(dict(forca_por_entreferro_N=d["forca_gap_N"], dims_mm=d["dims_mm"], massa_kg=d["massa_kg"]))
    R.h2("Sistema de isolação")
    R.tab(["Item", "Material", "Índice térmico °C", "Norma", "Por quê"], [(i["item"], i["mat"], i["ti"], i["norma"], i["por_que"])
                                                                         for i in d["isolacao"]], [1.2, 2.2, 0.6, 1.0, 2.0], fs=6.2)
    try:
        from .ind_desenhos import fabricacao
        fab = fabricacao(d)
        R.h2("Ficha de fabricação")
        R.p(f"Empilhamento ≈ {fab['n_lam']} lâminas de {fab['t']} mm; comprimento de {'fio (todos os paralelos)' if d.get('fio') else 'folha'} ≈ {fab['comp_folha']:.1f} m por bobina "
            f"({fab['massa_folha']:.1f} kg); espira média {fab['MLT']:.0f} mm; espessura radial {fab['build_real']:.1f} mm.")
        R.tab(["Peça", "Largura (mm)", "Comprimento", "Quantidade"], fab["corte"], [1.4, 0.8, 1.2, 2.0])
        R.tab(["Coluna", "calço (mm)", "pacotes (mm, de baixo p/ cima)"],
              [("Laterais U/W", f"{fab['gl']:.2f}", " / ".join(f"{p:.1f}" for p in fab["pac_l"])),
               ("Central V", f"{fab['gc']:.2f}", " / ".join(f"{p:.1f}" for p in fab["pac_c"]))], [1.0, 0.7, 3.0])
        R.h3("Tabela de bobinagem (por bobina)")
        R.tab(["Camada", "Espessura (mm)", "r inicial", "r final"], [(c[0], c[1], f"{c[2]:.1f}", f"{c[3]:.1f}") for c in fab["camadas"]],
              [3.2, 0.8, 0.7, 0.7], fs=6.2)
        R.h3("Sequência de fabricação, ajuste e ensaios")
        R.bul(fab["sequencia"])
        R.p(f"Força magnética por entreferro ≈ {fab['forca']:.0f} N (pico) – aperto mínimo {fab['aperto_N']:.0f} N por coluna; "
            "calços colados e conjunto impregnado (VPI) para não vibrar " + ("(100–1000 Hz)." if d["requisitos"].get("aplicacao") else "a 4–8 kHz."))
    except Exception as e:
        R.p(f"(ficha de fabricação não gerada: {e})")
    eng = os.path.join(pasta, "01_Engenharia")
    for f in sorted(os.listdir(eng)) if os.path.isdir(eng) else []:
        if f.startswith("Indutor_") and f.endswith(".png"):
            R.img(os.path.join(eng, f), 175, f)


def memorial_indutor(d, arq, titulo):
    """Memorial de cálculo do indutor (PDF) – para o fornecedor e para a auditoria."""
    R = Rel()
    R.f.append(Paragraph(_esc(titulo), R.st["CAPA"]))
    R.p("Projeto de referência calculado pela plataforma FSEN a partir das correntes e tensões reais simuladas do filtro. "
        "O fabricante emite o projeto de fabricação próprio e declara as diferenças; o protótipo com ensaio de aquecimento confirma.")
    _secao_indutor(R, d, os.path.dirname(os.path.dirname(arq)))
    doc = _Doc(arq, titulo, rotulo="PROJETO DE REFERÊNCIA – ELECTRIC SERVICE")
    doc.multiBuild(R.f)
    return arq
