"""Documentos para o fabricante do indutor (v1.11.0).

  • Protocolo de Ensaio do Protótipo – critérios NUMÉRICOS de aceitação, colunas para o medido (DOCX editável)
  • Questionário ao fabricante – dados internos dos indutores já fornecidos (calibração do método)
  • INTERNO – fornecedores sugeridos para cotar em paralelo (fica em 01_Engenharia, NÃO vai ao fabricante)
"""
import math
import os

# tolerâncias de aceitação do protótipo (prática de reatores IEC 60076-6 / fabricantes de filtro)
TOL = dict(L_pct=5.0, deseq_pct=3.0, rdc_pct=10.0, perdas_pct=15.0, dim_pct=5.0, massa_pct=10.0, elev_k=100.0, elev_lim_k=125.0,
           ir_mohm=100.0, l_sat_pct=90.0, l_ovl_pct=70.0)

FORNECEDORES = [
    dict(nome="Cootrans", status="fornecedor atual", obs="Fabricou os indutores dos filtros anteriores (RTUC17 1586 µH/28 A, 958 µH/38 A, "
         "0,588 mH/135 A, 0,336 mH/217 A). Projeta para custo (núcleo menor, mais quente). Pouca experiência declarada em perdas de "
         "alta frequência, por isso vão o projeto de referência, o protocolo e o questionário."),
    dict(nome="Pólux (Pólux Transformadores)", status="cotar – CONCORRENTE", obs="Fabrica reatores e também vende filtro senoidal "
         "próprio: é concorrente. Mandar só a ET de desempenho (sem o projeto de referência completo) ou assinar NDA antes."),
    dict(nome="Cosmo Transformadores", status="cotar – CONCORRENTE", obs="Também oferece filtros senoidais/dV/dt de linha própria: "
         "concorrente. Mesmo cuidado (ET de desempenho, NDA)."),
    dict(nome="Eletromax", status="cotar", obs="Reatores e transformadores a seco sob encomenda. Confirmar se faz chapa 0,27 mm GO, "
         "enrolamento em folha e ensaio de aquecimento com inversor."),
    dict(nome="Tamura", status="NÃO indicado", obs="Linha de reatores até ~400 Hz e isolação classe B/F: não atende a ondulação de "
         "alta frequência nem a classe H pedida."),
]


def _fmt(x, n=0):
    return f"{x:,.{n}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def protocolo_prototipo(proj, cat, ind, pasta, cod, novo, tabela, bullets):
    """DOCX com os ensaios do protótipo e os critérios numéricos de aceitação."""
    r = ind["requisitos"] if ind else {}
    L_uh = float(proj.l1.l_uh)
    In = float(proj.l1.i_nom_a)
    cc = getattr(proj, "corrente_dimensionamento", None) or {}
    isat = float(r.get("Isat") or proj.l1.i_sat_a)
    iovl = float(r.get("Iovl") or 1.5 * math.sqrt(2) * In)
    p_pred = float(ind["perdas"]["total"]) if ind else float(proj.l1.perdas_w or 0)
    p_max = float(r.get("P_max") or 0) * float(r.get("k_Pmax") or 1) if r.get("P_max") else p_pred * 1.15
    rdc = float(ind.get("Rdc_ohm", 0)) * 1e3 if ind else 0.0
    el = float(ind["termico"]["elev_bobina_K"]) if ind else 100.0
    dims = ind.get("dims_mm", {}) if ind else {}
    massa = float(ind["massa_kg"]["total"]) if ind else float(proj.l1.massa_kg or 0)
    d = novo("Protocolo de Ensaio do Protótipo – Indutor", f"{L_uh:.0f} µH / {In:.0f} A – {cod}", proj, cat)
    d.add_heading("1. Objetivo", 1)
    d.add_paragraph("Aprovar o PROTÓTIPO antes da liberação da série. Cada ensaio tem critério numérico; a série só é liberada com "
                    "todos os itens 'OK' e o relatório assinado. Os valores previstos vêm do projeto de referência calculado por "
                    "elementos finitos (Memorial do Indutor). O fabricante preenche as colunas 'Medido' e 'Resultado' e devolve "
                    "com fotos, certificados dos instrumentos e o desenho de fabricação.")
    d.add_heading("2. Condições", 1)
    bullets(d, [f"Ambiente de ensaio registrado; resultados de temperatura corrigidos para {cat.get('projeto_padrao', {}).get('amb_max_c', 40):g} °C.",
                "Instrumentos calibrados (certificado com validade); LCR/ponte para L e R; wattímetro de banda larga (≥ 100 kHz) "
                "para perdas com inversor; termopares/PT100 nos pontos indicados no desenho (topo da bobina central, entreferro, núcleo).",
                f"Ensaio de aquecimento DE PREFERÊNCIA com inversor a {proj.fs_hz / 1000:g} kHz e corrente {In:.0f} A rms; se feito em "
                "60 Hz senoidal, acrescentar as perdas de alta frequência previstas (método de perdas equivalentes, IEC 60076-6 §7.8.6) e "
                "declarar como foi feito.",
                "Ensaio até estabilizar (variação < 1 K/h)."])
    d.add_heading("3. Ensaios e critérios de aceitação", 1)
    lin = [
        ("1", "Indutância por fase (In, 60 Hz)", f"{L_uh:.0f} µH", f"±{TOL['L_pct']:g} % → {L_uh * 0.95:.0f}–{L_uh * 1.05:.0f} µH", "", ""),
        ("2", "Desequilíbrio entre fases", "–", f"≤ {TOL['deseq_pct']:g} %", "", ""),
        ("3", "Resistência CC por fase (20 °C)", f"{rdc:.3f} mΩ".replace(".", ",") if rdc else "declarar",
         f"±{TOL['rdc_pct']:g} % do previsto" if rdc else "declarado ±10 %", "", ""),
        ("4", "Curva L × I (CC sobreposta ou pulso)", f"L ≥ 90 % até {isat:.0f} A pk", f"L({isat:.0f} A) ≥ {TOL['l_sat_pct']:g} %", "", ""),
        ("5", "Linearidade na sobrecarga do inversor", f"{iovl:.0f} A pk", f"L({iovl:.0f} A) ≥ {TOL['l_ovl_pct']:g} %", "", ""),
        ("6", "Perdas totais com inversor (ou 60 Hz + AF)", f"{p_pred:.0f} W",
         f"≤ previsto +{TOL['perdas_pct']:g} % ({p_pred * 1.15:.0f} W) e ≤ {p_max:.0f} W", "", ""),
        ("7", "Elevação média do enrolamento (resistência)", f"{el:.0f} K", f"≤ {TOL['elev_k']:g} K (sistema H, elevação F)", "", ""),
        ("8", "Ponto quente (termopar/termografia)", "–", f"elevação ≤ {TOL['elev_lim_k']:g} K; sem ponto > 180 °C a 40 °C", "", ""),
        ("9", "Tensão aplicada fase-terra e fase-fase", "3 kV / 2,5 kV", "1 min sem descarga", "", ""),
        ("10", "Resistência de isolamento (1000 V CC)", "–", f"≥ {TOL['ir_mohm']:g} MΩ", "", ""),
        ("11", "Termostato/PTC", "–", "atua na temperatura nominal; contato NF livre de potencial", "", ""),
        ("12", "Dimensões e furação", "×".join(f"{v:.0f}" for v in dims.values()) + " mm" if dims else "desenho",
         f"±{TOL['dim_pct']:g} %; furação conforme desenho", "", ""),
        ("13", "Massa", f"{massa:.0f} kg", f"±{TOL['massa_pct']:g} %", "", ""),
        ("14", "Declaração de materiais", "chapa, condutor, isolação, verniz",
         "classe do SISTEMA de isolação comprovada (IEC 61857/UL 1446) – não só do esmalte", "", ""),
        ("15", "Placa de identificação", "–", "L, In, fs, classe, perdas, massa, nº de série", "", ""),
    ]
    t = tabela(d, ["#", "Ensaio", "Previsto", "Critério de aceitação", "Medido", "Resultado"], lin, [0.8, 4.2, 2.6, 5.0, 2.2, 2.2], 8)
    d.add_heading("4. Base de corrente usada (para o ensaio)", 1)
    if cc.get("base") == "carga":
        d.add_paragraph(f"Corrente térmica de ensaio {In:.0f} A rms (definida pela carga: motor {cc['i_motor_placa_a']:g} A × FS, "
                        f"capacitores, cabo e ondulação, margem {cc['margem']:.2f}). Saturação e sobrecarga pelo inversor "
                        f"({cc['i_ref_pico_a']:.0f} A): {isat:.0f} A e {iovl:.0f} A de pico.")
    else:
        d.add_paragraph(f"Corrente térmica de ensaio {In:.0f} A rms.")
    d.add_heading("5. Critério de rejeição", 1)
    bullets(d, ["Qualquer item fora do critério reprova o protótipo; o fabricante corrige e repete os ensaios afetados.",
                "Divergência entre desenho/placa e o declarado na proposta (classe, material, chapa) é rejeição.",
                "Elevação dentro do limite mas perdas acima do previsto +15 %: alerta – a plataforma refaz o estudo térmico do painel "
                "com o valor medido antes de liberar."])
    d.add_heading("6. Assinaturas", 1)
    tabela(d, ["", "Nome", "Data", "Assinatura"], [("Fabricante", "", "", ""), ("Electric Service", "", "", "")], [3, 6, 3, 5], 9)
    cam = os.path.join(pasta, f"Protocolo_Ensaio_Prototipo_Indutor_{cod}.docx")
    d.save(cam)
    return cam


def questionario_fabricante(proj, cat, pasta, cod, novo, tabela, bullets):
    """DOCX pedindo os dados internos dos indutores já fornecidos – para calibrar o método da plataforma."""
    d = novo("Questionário Técnico ao Fabricante – Indutores já fornecidos", f"Calibração do projeto de referência – {cod}", proj, cat)
    d.add_paragraph("Para alinharmos o nosso cálculo ao padrão de fabricação de vocês, pedimos os dados internos dos indutores que já "
                    "fabricaram para a Electric Service. Os dados ficam só conosco e servem para calibrar o projeto de referência "
                    "(perdas e temperatura) com medições reais.")
    d.add_heading("1. Indutores", 1)
    unid = [("RTUC17 – D 192130 (IHR 2022)", "1586 µH / 28 A / 380 V"), ("958 µH (SENAI)", "958 µH / 38 A"),
            ("Filtro 48 A", "– / 48 A"), ("0,588 mH (orç. ABB 2018)", "588 µH / 135 A / 480 V"),
            ("0,336 mH (orç. ABB 2018)", "336 µH / 217 A / 440 V")]
    tabela(d, ["Unidade", "Dados conhecidos"], unid, [8, 9], 9)
    d.add_heading("2. Dados pedidos para cada unidade", 1)
    perg = [
        ("Espiras por bobina", ""), ("Seção da coluna (largura × empilhamento, mm) e fator de empilhamento", ""),
        ("Altura e largura da janela (mm)", ""), ("Chapa: fabricante, grau (ex.: M120-27S), espessura (mm)", ""),
        ("Corte das lâminas (E-I, step-lap, 45°) e montagem", ""),
        ("Entreferros: quantidade por coluna, espessura de cada um (mm), material do espaçador", ""),
        ("Condutor: cobre/alumínio, folha/fio/retangular, dimensões, nº de camadas", ""),
        ("Distâncias bobina–núcleo, bobina–bobina e canais de ventilação (mm)", ""),
        ("Sistema de isolação (materiais e classe do sistema), verniz e processo (VPI/imersão)", ""),
        ("Indução de trabalho de projeto (T)", ""), ("Resistência CC medida (mΩ, a °C)", ""), ("Indutância medida por fase", ""),
        ("Perdas medidas (W) – em 60 Hz e, se houver, com inversor", ""),
        ("Elevação de temperatura medida (K) e método (resistência/termopar)", ""), ("Massa (kg) e dimensões finais", ""),
        ("Software de projeto usado e método para perdas de alta frequência", ""),
        ("Ocorrências em campo (aquecimento, ruído, falha)", ""),
    ]
    tabela(d, ["Dado", "Resposta"], perg, [9, 8], 9)
    d.add_heading("3. Por que pedimos", 1)
    bullets(d, ["Já medimos em campo alguns desses filtros (frequência de ressonância e tensão no motor). Com os dados de construção "
                "conseguimos comparar o nosso cálculo de perdas e temperatura com o que vocês mediram.",
                "Assim o projeto de referência fica no padrão de fabricação de vocês, e só mudamos o que a alta frequência exigir."])
    cam = os.path.join(pasta, f"Questionario_Fabricante_Indutor_{cod}.docx")
    d.save(cam)
    return cam


def fornecedores_interno(pasta_eng, cod):
    """TXT interno – NÃO vai ao fabricante."""
    os.makedirs(pasta_eng, exist_ok=True)
    ls = [f"FORNECEDORES SUGERIDOS PARA O INDUTOR – {cod}  (USO INTERNO – não enviar ao fabricante)", "",
          "Cotar pelo menos 2 fornecedores além do atual. Confirmar razão social, contato e capacidade antes de enviar.", ""]
    for f in FORNECEDORES:
        ls += [f"• {f['nome']} [{f['status']}]", f"  {f['obs']}", ""]
    ls += ["O que mandar:",
           "  – Fornecedor de confiança (Cootrans): pasta 03_Fornecedores/1_Indutor inteira (ET, projeto de referência, CAD, memorial,",
           "    protocolo, questionário e e-mail).",
           "  – Concorrente (Pólux, Cosmo): só a ET de desempenho e o protocolo; projeto de referência/CAD/memorial só com NDA.",
           "", "Pedir sempre: preço do PROTÓTIPO separado do preço da SÉRIE, prazo de cada um e os dados declarados da ET."]
    cam = os.path.join(pasta_eng, f"INTERNO_Fornecedores_Sugeridos_Indutor_{cod}.txt")
    open(cam, "w", encoding="utf-8").write("\n".join(ls))
    return cam


def texto_email_extra(proj, ind, arqs_nomes):
    """Parágrafos extras do e-mail ao fabricante: base de corrente, protótipo × série, protocolo e questionário."""
    from . import corrente_carga as CC
    cc = getattr(proj, "corrente_dimensionamento", None) or {}
    ls = ["", "6) BASE DA CORRENTE", CC.texto(cc), "",
          "7) PROTÓTIPO E SÉRIE – favor cotar SEPARADO",
          "- Item A: 1 protótipo com os ensaios do Protocolo em anexo (preço e prazo).",
          f"- Item B: série de {int(proj.pedido.get('quantidade', 1) if isinstance(proj.pedido, dict) else 1)} peça(s), liberada após "
          "aprovação do protótipo (preço e prazo).",
          "- O Protocolo traz os critérios numéricos de aceitação (L ±5 %, desequilíbrio ≤ 3 %, perdas ≤ previsto +15 %, elevação ≤ 100 K, "
          "linearidade na saturação e na sobrecarga, dielétrico, isolamento, dimensões e massa).", "",
          "8) QUESTIONÁRIO – indutores que vocês já fabricaram para nós",
          "Pedimos, se possível, os dados internos dos indutores anteriores (espiras, núcleo, chapa, entreferros, condutor, perdas e "
          "temperatura medidas). Servem para calibrar o nosso cálculo ao padrão de fabricação de vocês.", "",
          "Anexos desta solicitação: " + ", ".join(arqs_nomes) + "."]
    return "\n".join(ls)
