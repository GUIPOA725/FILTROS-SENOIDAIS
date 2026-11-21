"""Anexo técnico à cotação do indutor (v1.11.7): o que fabricantes, literatura e normas dizem sobre indutor trifásico de
núcleo com 2 entreferros por coluna e bobina de barra retangular de cobre – e como o nosso projeto atende.

Conteúdo de pesquisa fixo (revisado em 20/11/2026) + números do projeto atual. Vai para 03_Fornecedores/1_Indutor e é
listado como anexo no e-mail ao fabricante.
"""
import os
import glob

from reportlab.platypus import Paragraph, PageBreak

FONTES = [
    ("MTE – SineWave Guardian Filter Specification (EUA)", "https://mtecorp.com/wp-content/uploads/SineWave-Guardian-Filter-Specification_Rev.-01.pdf"),
    ("Mirus – AUSF Sine Wave Filter, especificação técnica (Canadá)", "https://www.mirusinternational.com/downloads/AUSF-TS001-A0-Sine-Wave-Filter.pdf"),
    ("BLOCK – Sine filters (Alemanha)", "https://www.block.eu/en_EN/products/reactors-filters/sine-filters"),
    ("Ergun Elektrik – catálogo de reatores (Turquia)", "https://www.gae.id/userdata/uploads/pdf/Catalogue_Ergun1154.pdf"),
    ("Trafox – Detuned reactors 400 V (Finlândia)", "https://pdf.directindustry.com/pdf/muuntosaehkoe-oy-trafox/detuned-reactors-400v-3inpp7/110911-385537.html"),
    ("Passive Device – Sine wave filter (China)", "https://www.passivedevice.com/3c-wave-filter.html"),
    ("Chifon – Copper foil output reactor (China)", "https://chifon0571.en.made-in-china.com/product/lGNRFptraEhS/China-Copper-Foil-Output-Reactor-for-Electric-Drive-Use-with-H-F-Insulation-Class-Reactor.html"),
    ("REO – Three-phase sine wave filter CNW 933", "https://reo-ag.com/?p=15833"),
    ("Schaffner – FN5040/FN5045 installation manual", "https://www.schaffner.com/fileadmin/user_upload/Media/Downloads/installation-manual-FN5040-FN5045-FN5040HV-sine-wave-filter.pdf"),
    ("R. Severns – Additional Losses in High Frequency Magnetics due to Non Ideal Field Distributions (APEC 1992)",
     "https://antennasbyn6lf.com/Rudy_tech_papers/APEC.1992.Additional%20Losses%20in%20HIgh%20Freuency%20Magnetics%20due%20to%20Non%20Ideal%20Field%20Distributions.pdf"),
    ("A. Dönük – Modeling and Design of Iron-Core Shunt Reactors with Discretely Distributed Air-Gaps (METU, 2012)",
     "https://open.metu.edu.tr/bitstream/handle/11511/22046/index.pdf"),
    ("E. Altayef et al. – On the Effects of Lamination Artificial Faults in a 15 kVA Three-Phase Transformer Core (IEEE Access, 2022)",
     "https://orca.cardiff.ac.uk/id/eprint/147452/2/On_the_Effects_of_Lamination_Artificial_Faults_in_a_15_kVA_Three-Phase_Transformer_Core.pdf"),
    ("T. Belgrand et al. – Thin grain oriented electrical steel for PWM voltages fed magnetic cores (AIP Advances, 2018)",
     "https://openaccess.library.uitm.edu.my/Record/doaj-acc39ab634cc4ad1bd0e0538a4a172f5"),
    ("IEC 60076-6:2007 – Reactors (sumário: cláusula 9, reatores de filtro)", "https://cdn.standards.iteh.ai/samples/12716/7a4d4dd654f8444f837eb6fab5f4d84b/IEC-60076-6-2007.pdf"),
]

MERCADO = [
    ("MTE SineWave Guardian (EUA)", "Fio ou folha de cobre", "Lâminas de aço-silício cintadas", "Classe N 200 °C (Nomex 410); vácuo + epóxi",
     "Elevação ≤ 135 K; 150 %/1 min; ≤ 75 dB a 1 m"),
    ("Mirus AUSF (Canadá)", "Fio ou folha de cobre", "Núcleo COM entreferro (controle de saturação)", "–",
     "L ≥ 50 % a 200 % In; 150 %/60 s a cada 10 min"),
    ("BLOCK (Alemanha)", "\"Future Winding\" – menos perdas por proximidade", "–", "–", "Até 460 A (catálogo); terminais em barra chata; EN 61558-2-20"),
    ("Ergun (Turquia) – reatores de filtro", "Fio de cobre chato/redondo ou folha Cu/Al", "Chapa de transformador selecionada, com entreferro",
     "Classe F; verniz classe H a vácuo", "Terminais em barra de cobre; EN 61558-2-20 / IEC 60076-6"),
    ("Trafox (Finlândia) – dessintonizados", "–", "Vários entreferros COLADOS (baixo ruído)", "150–180 °C", "IEC 60076 / VDE 0532"),
    ("Fabricantes chineses (Passive Device, Chifon)", "Folha de Al ou Cu", "Silício laminado a frio", "Classe F/H; VPI", "Saídas em barra de cobre; 3 kV/1 min"),
    ("Reatores dessintonizados nacionais (recebidos pela Electric)", "BARRA de cobre, fita com traçador + verniz", "3 colunas, quadros U zincados, tirantes",
     "Verniz (classe a confirmar)", "Saídas em barra horizontais; placa na culatra"),
]


def gerar(ind, proj, arq, eng_dir=None):
    from .auditoria import Rel, _Doc, _esc
    from .ind_desenhos import geo_mm
    from .ind_estrutura import texto_padrao
    from .doc_indutor_fornecedor import exigencias_chapa
    R = Rel()
    g = geo_mm(ind)
    fw = g.get("fio") or {}
    tp = texto_padrao(g, ind)
    gap_peca = g["gaps"][0] / max(g["ng"], 1)
    dist = g["yc0"] - g["a"]
    r = ind["requisitos"]
    titulo = "Anexo técnico – indutor trifásico com 2 entreferros por coluna e bobina de barra de cobre"
    R.f.append(Paragraph(_esc(titulo), R.st["CAPA"]))
    R.p(f"Filtro senoidal {r['L']*1e6:.0f} µH / {r['In']:.0f} A / chaveamento {r['fs']/1e3:g} kHz. Este anexo reúne o que fabricantes, "
        "literatura técnica e normas publicam sobre a construção escolhida, e mostra como o projeto de referência atende cada ponto. "
        "Pesquisa revisada em 20/11/2026.")
    R.h1("Resumo")
    R.bul([
        "Nenhum fabricante publica, em catálogo, a construção interna detalhada; quando informam, usam fio/barra chata de cobre ou folha "
        "Cu/Al, núcleo de aço-silício COM entreferro, isolação classe F a N e impregnação a vácuo (VPI).",
        "Folha condutora é comum na Europa e na China com entreferro DISTRIBUÍDO (muitos pedaços). Com 2 entreferros concentrados, o "
        "campo espraiado atinge a borda da folha de frente – por isso escolhemos BARRA retangular, que só expõe a face estreita.",
        "A construção com 2 entreferros por coluna, nas juntas com as culatras, e bobina de barra de cobre é o padrão dos reatores "
        "nacionais (bancos dessintonizados) – fabricável no Brasil sem ferramental especial.",
        f"A literatura recomenda afastar o enrolamento do entreferro 2 a 3 vezes o comprimento do entreferro. Aqui: entreferro de "
        f"{gap_peca:.1f} mm por peça → 2–3× = {2*gap_peca:.0f}–{3*gap_peca:.0f} mm; projeto usa {dist:.0f} mm ({dist/gap_peca:.1f}×).",
        "Rebarba e revestimento danificado nas lâminas aumentam muito a corrente a vazio e geram aquecimento localizado: a chapa "
        "precisa ser NOVA, certificada e conferida no recebimento.",
        "O ensaio que decide é o aquecimento COM INVERSOR (IEC 60076-6 trata a elevação de temperatura como ensaio de tipo)."])
    R.h1("O que os fabricantes publicam")
    R.tab(["Fabricante / produto", "Condutor", "Núcleo / entreferro", "Isolação / impregnação", "Outros dados"], MERCADO,
          [2.2, 2.0, 2.2, 2.0, 2.4], 6.6)
    R.p("Observação: catálogos de filtros senoidais grandes (REO, Schaffner, Siemens) dão massa, perdas e dimensões, mas não a "
        "construção interna. Referência de mercado usada na plataforma: REO CNW 933 ≈ 92 kg / 655 W e Schaffner FN5040 ≈ 128 kg / "
        f"893 W na faixa de 200 µH / 260 A. Projeto de referência: {ind['massa_kg']['total']:.0f} kg / {ind['perdas']['total']:.0f} W.")
    R.h1("Literatura técnica e o que ela implica no projeto")
    R.tab(["Fonte", "Achado", "Como o projeto atende"], [
        ("Severns, APEC 1992", "Enrolamento junto ao entreferro chegou a 5,5× a perda prevista; afastado 2× o entreferro, ficou só "
         "≈ 24 % acima do ideal. Regra: 2–3× o comprimento do entreferro.",
         f"Distância bobina–junta {dist:.0f} mm = {dist/gap_peca:.1f}× o entreferro por peça ({gap_peca:.1f} mm). Perdas nas barras das "
         "pontas calculadas por elementos finitos harmônicos."),
        ("Dönük, METU 2012", "Distribuir o entreferro reduz espraiamento e indutância de dispersão; ótimo 20–40 pedaços em reatores "
         "shunt grandes, com custo maior.",
         "Mantidos 2 entreferros (padrão nacional, menor custo); compensado com distância maior, barra estreita no campo e "
         "verificação por FEM (L, saturação, perdas)."),
        ("Altayef et al., IEEE Access 2022", "Rebarba e falha de isolação entre lâminas elevaram a corrente a vazio de ≈ 46 % a 100 % "
         "e causam aquecimento localizado.", "Exigida chapa nova certificada, rebarba ≤ 0,02 mm e inspeção de recebimento."),
        ("Belgrand et al., AIP Advances 2018", "Caracterização de aço-silício GO fino sob tensão PWM (ensaios Epstein).",
         f"Chapa GO {ind['chapa_dados']['nome']} ({ind['chapa_dados']['esp_mm']} mm); perdas de AF calculadas por FEM."),
        ("Física clássica", "Perda por correntes parasitas ∝ (espessura)² × f²: 0,35 mm ≈ 2,3× e 0,50 mm ≈ 4,7× a de 0,23 mm.",
         "Espessura máxima admitida 0,27 mm; ensaio com inversor comprova.")], [1.6, 3.2, 3.2], 6.8)
    R.h1("Normas e ensaios")
    R.bul(["IEC 60076-6, cláusula 9 (reatores de filtro): rotina – indutância, perdas/fator de qualidade, sobretensão entre espiras; "
           "tipo – elevação de temperatura na corrente contínua nominal, impulso; especiais – nível de ruído, curto-circuito, etc.",
           "EN/IEC 61558-2-20 (reatores pequenos) é a norma citada pelos fabricantes de catálogo (BLOCK, Ergun).",
           "O Protocolo de Ensaio do Protótipo em anexo aplica esses ensaios com critérios numéricos, incluindo o aquecimento com "
           "inversor, a linearidade (L × I) e o recebimento da chapa."])
    R.h1("Recomendações de fabricação da bobina de barra")
    R.bul([
        f"Condutor: barra de cobre ETP {fw.get('t', 0):.0f} × {fw.get('h', 0):.0f} mm, cantos arredondados, isolada com papel aramida "
        "(Nomex 410, 0,13–0,18 mm, 50 % de sobreposição) – pode ser comprada já isolada (papel aramida ou fibra de vidro + verniz classe H). "
        "Barra apenas esmaltada não atende.",
        f"{g['N']} espiras por bobina em {fw.get('n_cam', 1)} camada(s) de {fw.get('n_ax', g['N'])}: bobinadeira lenta com molde "
        "retangular de cantos arredondados, desbobinador com freio e tensionador; assentar cada espira com martelo de nylon.",
        "Tubo de vidro-epóxi EP GC 203 3 mm sobre o molde; entre camadas aramida 0,25 mm + réguas de vidro-epóxi formando canal de "
        "ventilação; calço de cunha e blocos de extremidade até a culatra.",
        "Enfaixamento externo com fita de poliéster-vidro e impregnação VPI com resina classe H (bobinas montadas no núcleo).",
        tp["saida"] + ".", tp["quadro"] + ".", tp["tirante"] + "."])
    R.h2("Chapa do núcleo – exigência")
    R.bul(exigencias_chapa(proj))
    # figuras
    R.f.append(PageBreak())
    R.h1("Figuras")
    if eng_dir:
        for nome, leg in (("Indutor_render_geral.png", "Projeto de referência – vista realista (bobina U em corte)."),
                          ("Indutor_render_corte.png", "Detalhe: coluna, calços do entreferro nas juntas, tubo, barras isoladas, enfaixamento.")):
            achados = glob.glob(os.path.join(eng_dir, "**", nome), recursive=True)
            if achados:
                R.img(achados[0], 150, leg)
    ref = os.path.join(os.path.dirname(os.path.dirname(__file__)), "dados", "referencias_montagem")
    fotos = sorted(glob.glob(os.path.join(ref, "*.jpg")))
    if fotos:
        R.h2("Referência de montagem – reatores dessintonizados de fabricação nacional")
        R.p("Fotos de reatores de banco dessintonizado recebidos pela Electric Service: mesma concepção mecânica (3 colunas, quadros "
            "em U, tirantes, bobina de barra, saídas em barra). O filtro senoidal muda o \"por dentro\": chapa GO fina nova, isolação "
            "classe H com VPI, distância bobina–junta e ensaio com inversor.")
        for f in fotos[:3]:
            R.img(f, 120)
    R.h1("Fontes")
    for t, u in FONTES:
        R.p(f"{_esc(t)} – <link href='{u}'>{_esc(u)}</link>", raw=True)
    doc = _Doc(arq, titulo, rotulo="ANEXO TÉCNICO – ELECTRIC SERVICE")
    doc.multiBuild(R.f)
    return arq
