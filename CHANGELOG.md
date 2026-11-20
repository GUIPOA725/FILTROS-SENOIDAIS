# Registro de atualizações – Plataforma FSEN

## v1.11.3 – 20/11/2026 – Base de dados completa para o indutor de 2 entreferros por coluna
- Chapas: os 7 graus de grão orientado da Aperam (único fabricante nacional), perdas garantidas do catálogo "Aços Elétricos GO
  e GNO": M108-23, M117-23, M112-27, M125-27, M130-30, M140-30, M150-35 (preço R$/kg estimado – confirmar cotação).
- Condutores: série R20 COMPLETA da IEC 60317-0-2 – 23 espessuras (0,80 a 10 mm) × 25 larguras (2 a 31,5 mm), relação 1,4 a 8
  (de fio retangular a barra), em alumínio e cobre; 1 a 6 fios em paralelo; 1 a 8 camadas.
- Busca: triagem analítica de todas as combinações chapa × condutor × bitola × paralelos × camadas × espiras × núcleo; os 2
  melhores de cada chapa×condutor + os 10 melhores no geral vão para o FEM (perdas reais com os 2 entreferros, núcleo, perda de
  entreferro de Lee e o ENTREFERRO necessário para chegar em L, calculado por 2 pontos no FEM).
- Folgas exigidas: perdas ≤ 92 % do limite, elevação ≤ 90 % da meta, entreferro ≤ 90 % de 20 % da coluna e de 10 mm por peça –
  o escolhido sai sem nenhum aviso.
- Custo da escolha inclui mão de obra proporcional à massa (R$ 10/kg, estimativa); tabela de todos os candidatos com massa e custo
  no memorial/auditoria.

## v1.11.2 – 20/11/2026 – Indutor com 2 entreferros por coluna + fio retangular (padrão nacional)
- Nova construção (agora a PADRÃO): 2 entreferros por coluna nas juntas coluna–culatra + enrolamento em CAMADAS de fio
  retangular (espiras em série; fios em paralelo transpostos). É o padrão dos fabricantes nacionais (a Cootrans usou fio nos
  indutores menores).
  - Modelo FEM do enrolamento em fio: cada fio de cada espira é um condutor com corrente imposta (série) e I/np nos paralelos.
  - Triagem: o pré-dimensionamento analítico gera os 16 candidatos mais baratos (núcleo, espiras, bitola IEC 60317-0-2,
    paralelos, camadas) e o FEM confere a perda REAL de cada um com os 2 entreferros; fica o mais barato que passa.
  - Calcula alumínio E cobre e escolhe o de menor custo total (material + perdas capitalizadas) que passa em tudo.
  - Restrições de fabricação: entreferro ≤ 10 mm por peça e ≤ 20 % da coluna (espraiamento ×1,65 calibrado no FEM).
- Perda adicional no núcleo junto aos entreferros concentrados (fórmula de Lee/McLyman, Ki = 0,155 lâminas) somada às perdas e
  ao térmico do núcleo – margem para o efeito 3D que o FEM 2D não vê. Não se aplica a entreferros distribuídos ≤ 3 mm.
- Desenhos, lista de materiais, CAD (texto), memorial/auditoria e e-mail ao fabricante tratam o fio retangular: tabela de
  bobinagem por camada, corte B-B com cada fio, transposição dos paralelos, saída com barra, tabelas Al × Cu e triagem FEM.
- Tela: "Construção do indutor" com 3 opções – 2 entreferros + fio retangular (padrão), multigap + folha, 2 entreferros + folha.

## v1.11.1 – 20/11/2026 – Painel com o indutor real + opção de entreferros (multigap × 2 nas culatras)
- CORREÇÃO: o painel (arranjo, térmico, caixa, ventiladores) usava a estimativa simplificada do indutor (A&W: 400×300×200 mm,
  87 kg, 1463 W). Agora o projeto do indutor por elementos finitos roda ANTES do painel e o painel usa as dimensões e a massa
  reais (A&W: 500×480×230 mm, 103 kg) e, como perdas, o LIMITE CONTRATUAL do indutor (FEM + 15 %, teto de mercado) – o mesmo
  valor do protocolo de ensaio. ET e protocolo ficam coerentes com o térmico do painel.
- Nova opção na tela "Entreferros do indutor": distribuídos – multigap (padrão) ou 2 por coluna nas juntas coluna–culatra
  (padrão nacional). Modelo de elementos finitos, desenhos (núcleo com colunas inteiras e junta de topo), STEP/DXF e sequência
  de fabricação tratam as duas construções. Aviso automático quando o entreferro passa de 20 % da coluna ou do limite por peça.
- E-mail ao fabricante: item 9 pergunta se fazem coluna em pacotes com calços; se o padrão for só 2 entreferros, refazemos.
- Avisos: removido o texto "configuração definida manualmente" nas escolhas automáticas (mercado / mínimo de capacitores).
- Dupla checagem ATP: quando a THD passa pela tolerância absoluta (±0,5 ponto percentual) e não pela relativa, o texto diz isso.

## v1.11.0 – 20/11/2026 – Corrente definida pela Electric (carga × inversor) + pacote para o fabricante do indutor
- REGRA NOVA: "o cobre vai pela carga, o ferro vai pelo inversor". A corrente pedida pelo cliente passa a ser só informativa.
  - Corrente térmica = ⌈1,10 × √(I_fund² + I_ripple²)⌉, com I_fund = máx(|motor×FS (FP) + capacitores + cabo|, motor×FS) – sem
    crédito da compensação capacitiva. Sem corrente de placa, estima pela potência (cv/kW, η 0,94, FP). Sem dado do motor, usa a
    do cliente.
  - Duas passadas: 1ª com ripple estimado (5 %), 2ª com o banco e o ripple simulados; redimensiona se mudar mais que 2 %.
  - Saturação: Isat ≥ máx(1,25 × pico simulado; √2 × I_inversor + ripple/2). Sobrecarga: 1,5 × √2 × I_inversor + ripple/2 (L ≥ 70 %).
  - Aviso se a corrente da carga passar a do inversor. Opção na tela "Usar a corrente informada pelo cliente" (padrão desmarcado),
    com prévia da corrente antes de dimensionar e tabela da composição no resultado.
  - Composição da corrente no memorial (1.1), na proposta (Corrente nominal: pedida × ofertada), na ET do indutor (3.1), no
    e-mail ao fabricante, no memorial do indutor e no relatório de auditoria. Catálogo: bloco corrente_carga (margem, C do cabo).
  - Ajuste manual mantém a corrente definida pela carga.
- 03_Fornecedores/1_Indutor ganhou:
  - Protocolo_Ensaio_Prototipo_Indutor (DOCX editável): 15 ensaios com critério numérico (L ±5 %, desequilíbrio ≤ 3 %, Rdc ±10 %,
    L ≥ 90 % na Isat e ≥ 70 % na sobrecarga, perdas ≤ previsto +15 % e ≤ teto de mercado, elevação ≤ 100 K, ponto quente,
    3 kV/1 min, ≥ 100 MΩ, PTC, dimensões, massa, declaração do sistema de isolação, placa) e colunas Medido/Resultado.
  - Questionario_Fabricante_Indutor (DOCX): dados internos dos indutores já fornecidos (espiras, núcleo, chapa, entreferros,
    condutor, perdas e temperatura medidas, software) para calibrar o método.
  - E-mail ao fabricante: base da corrente, protótipo e série cotados SEPARADOS, protocolo e questionário, lista de anexos.
- 01_Engenharia/5_Compras_Interno: fornecedores sugeridos para cotar (Cootrans; Pólux e Cosmo com aviso de CONCORRENTE – só ET
  ou NDA; Eletromax; Tamura não indicado). Não vai ao fornecedor.
- Conferência de proposta do indutor: campos novos (espiras, coluna a × b, entreferro total, ponto quente) e tabela
  "Nosso cálculo × proposta" no parecer, comparando com o projeto de referência por elementos finitos.

## v1.10.4 – 20/11/2026 – CAD editável do indutor (STEP + DXF)
- Indutor_3D_<projeto>.step: STEP AP214 com sólidos B-rep (um por peça: culatras, pacotes das colunas, calços, tubos,
  bobinas, terminais, cantoneiras, tirantes, base, caixa do PTC), com nome e cor. Escritor próprio sem dependências (o
  OpenCascade/CadQuery não tem versão para Python 3.15). Validado: 68 sólidos lidos e válidos no OpenCascade (motor do FreeCAD).
- Indutor_2D_<projeto>.dxf: vistas frontal, lateral, superior/furação, planta do núcleo com calços e corte da bobina em
  escala 1:1 (mm), camadas (NUCLEO, BOBINA, ISOLACAO, CALCOS, ESTRUTURA, TERMINAIS, COTAS, EIXOS) e cotas associativas (ezdxf).
- Os dois vão para 03_Fornecedores/1_Indutor e são citados no e-mail ao fabricante. Dependência nova: ezdxf (instalação automática).

## v1.10.3 – 20/11/2026 – Desenhos do indutor padrão fábrica + ficha de fabricação
- 5 folhas A3 (ABNT NBR 10068/10582): carimbo completo com nº do desenho, escala normalizada, 1º diedro (símbolo), tabela de
  revisões, tolerâncias gerais ISO 2768-m; desenho em mm reais com escala por vista.
- Folha 1 Conjunto: vistas frontal, lateral esquerda e superior/furação da base, cotas em cadeia (colunas, janelas, passo,
  distância entre bobinas, altura total, furação), balões numerados = itens da lista de materiais, tirantes FORA das bobinas,
  olhais, caixa de bornes do PTC, placa, PE, quadro de características.
- Folha 2 Núcleo: planta das chapas com juntas a 45°, posição e espessura dos calços por coluna, alturas dos pacotes cotadas,
  detalhe step-lap, tabela de corte e de calços, força no entreferro e aperto mínimo.
- Folha 3 Bobina: cortes A-A e B-B cotados, tabela de bobinagem camada a camada (raios), comprimento/massa da folha, sentido de
  bobinagem, posição do PTC, detalhe do terminal (solda TIG, placa bimetálica, furação NEMA).
- Folha 4: vista 3D sombreada (bobinas arredondadas) + características. Folha 5: lista de materiais, sequência de fabricação
  (corte, montagem, calços, bobinagem, prensagem, ajuste de L no ensaio, VPI, ensaios) e notas.
- Memorial do indutor: nova seção "Ficha de fabricação" (lâminas, corte, pacotes/calços, bobinagem, sequência, aperto).

## v1.10.2 – 20/11/2026 – Pastas e tela organizadas
- Cada pasta principal do projeto agora tem subpastas: 01_Engenharia (memorial/custos, estudos, indutor FEM, auditoria, ATP),
  02_Cliente (proposta, folha de dados, relatório técnico, dados faltantes), 03_Fornecedores (1_Indutor, 2_Capacitores,
  3_Caixa_Metalica, 4_Plaqueta_Adesivos, 5_Cabos_Miscelanea), 04_Montadora (cotação, caderno, desenhos), 05_Desenhos (painel,
  indutor). Arquivo LEIA-ME_PASTAS.txt na raiz de cada projeto explica o que vai para quem.
- Os dados que a plataforma lê (projeto.json etc.) e a pasta ATP ficam no lugar – abrir projeto, ajuste manual e conferência
  continuam funcionando, inclusive com projetos antigos.
- Tela "Nova solicitação": arquivos gerados agrupados por pasta/subpasta (Fornecedores aberto por padrão).
- Conferência de proposta: parecer gravado na subpasta do componente (1_Indutor / 2_Capacitores).

## v1.10.1 – 20/11/2026 – Elemento finito do indutor mais rápido (notebook)
- Malha até 4× mais grossa no ar distante (fora da caixa núcleo+bobinas), metade dos nós com a mesma indutância (validação
  repetida: 427,7/435,1 µH idênticos).
- Perdas harmônicas: 1 fatoração por frequência para as 2 excitações; saturação da coluna central só em Isat; indução de pico
  da fase W pela simetria da fase U. Projeto A&W: 162 s → 71 s, resultados idênticos (671 W, 75 K, 180 µH).

## v1.10.0 – 20/11/2026 – Indutor por elementos finitos (projeto de referência para fabricação) + Relatório de Auditoria
- Novo solver de elementos finitos 2D próprio (fsen/ind_fem.py): magnetostático não-linear (curva B-H do aço GO) para saturação,
  linear para matriz de indutâncias 3×3 e ajuste do entreferro, e HARMÔNICO NO TEMPO com correntes induzidas e corrente imposta
  por condutor (blindagem/efeito pelicular reais na folha) para as perdas do enrolamento. Validado: limite CC exato e indutância
  entre o valor sem espraiamento e McLyman.
- Novo projeto magnético (fsen/ind_projeto.py): varredura de espiras × núcleo (inclusive maior que o mínimo para reduzir perda
  AF) × folha × canais; entreferro por peça ≤ 3 mm; estudo nº de entreferros × distância bobina–núcleo; equalização das colunas;
  saturação em pico/Isat/sobrecarga; perdas no núcleo elemento a elemento com o ESPECTRO REAL da tensão PWM sobre o indutor e
  correntes parasitas na lâmina com efeito pelicular; elevação de temperatura (IEC 60076-11); forças no entreferro; sistema de
  isolação classe F/H componente a componente (IEC 60085/61857: DMD e GPO-3 só servem em classe F); distâncias IEC 60664-1.
- Desenhos do projeto de referência (fsen/ind_desenhos.py), 4 folhas A3: vistas, cortes A-A/B-B, detalhes de entreferro e
  terminal, vista 3D, lista de materiais com normas e notas. Memorial de cálculo do indutor em PDF. Ambos vão para
  03_Fornecedores e são citados no e-mail ao fabricante.
- Novo Relatório de Auditoria (fsen/auditoria.py, 01_Engenharia/AUDITORIA_<projeto>.pdf, uso interno): entradas e origem de
  cada dado, normas, modelo e parâmetros, varreduras e motivos de descarte, robustez, todas as verificações, ATP completo,
  capacitores, indutor (FEM, perdas, térmico, isolação, desenhos), mecânica, custos, dados faltantes, incertezas, rastreabilidade
  (SHA-256 dos arquivos) e formulário de parecer do auditor.
- Calibração: o mesmo método aplicado aos indutores Cootrans já fornecidos (1586 µH/28 A, 0,588 mH/135 A, 0,336 mH/217 A) chega
  a massa e dimensões na mesma faixa (16/80/134 kg × reais 20/90/130 kg). Filtros anteriores (IHR, SENAI/Gelluns, AB) reavaliados
  na plataforma – resultados no relatório de auditoria.
- Dependência nova: reportlab (instalada automaticamente pelo ABRIR_FSEN).

## v1.9.13 – 20/11/2026 – Mínimo de capacitores com o capacitor do estoque
- Nova prioridade na tela "Nova solicitação": "MÍNIMO de capacitores com o capacitor escolhido (estoque)". Marque o capacitor
  (ex.: TDK 20 µF 480 V) e a ligação (ex.: Delta); a plataforma varre nº de capacitores × indutância (uk 4–14 %), simula todos
  os casos e escolhe o de MENOS capacitores aprovado em todos os critérios, robusto e com perda de inserção ≤ 6 % (MTE).
- Regra de escolha fixa, ancorada no que o mercado já fabrica: 1º menos capacitores; 2º L mais perto dos produtos de mercado
  para a corrente (Schaffner FN5040 / REO CNW 933 interpolados; sem referência, MTE 8–10 %); 3º menor custo.
- Critério de queda corrigido: a perda de inserção (queda real de tensão na saída, com o FP do motor) é o que vale para o motor
  (MTE ≤ 6 %); a queda reativa ωL·I no indutor continua mostrada, mas não é a tensão que o motor perde.
- Novo documento 01_Engenharia/Estudo_Opcoes_Minimo_Capacitores.docx: critérios, por que menos capacitores não serve, tabela de
  opções, gráfico THD × L e inserção × L, todos os casos válidos e referências. Tabela de opções também na tela.
- Alternativa "favor cotar também" da ET do indutor: 2ª melhor indutância com a MESMA quantidade de capacitores.

## v1.9.12 – 20/11/2026 – Alternativa de indutância com o capacitor que a empresa tem
- A varredura de ponto ótimo (e a alternativa "favor cotar também" da ET do indutor) passa a usar o MESMO capacitor do projeto
  (ex.: 20 µF 480 V, que é o que há em estoque) – a alternativa não pode depender de um capacitor que não temos.
  Para liberar outros capacitores na varredura: `alternativa_mesmo_capacitor: false` no catálogo.
- Regra de escolha FIXA e documentada (determinística): 1º menos capacitores; 2º indutância mais próxima da faixa MTE
  (8–10 % da impedância nominal); 3º menor custo. Só entram opções aprovadas em todos os critérios E robustas
  (L ±10 %, C ±5 %, cabo, motor).
- Teste de repetibilidade: o mesmo pedido rodado 3× dá resultado idêntico (projeto, verificações e alternativa).

## v1.9.11 – 20/11/2026 – Ponto ótimo de mercado e robustez (referências MTE / FRAKO / Schaffner / REO)
- Novo fsen/ponto_otimo.py e documento 01_Engenharia/Estudo_Ponto_Otimo_e_Robustez.docx em TODO projeto:
  - critérios de referência: MTE (L = 8–10 % da impedância nominal; fr 25–35 % de fs), FRAKO/IEC 61071 (UN do capacitor ≥ Vcc máx
    – em filtro PWM o pico pode chegar ao barramento), Schaffner/REO (L, perdas, massa por corrente);
  - robustez do projeto: THD no motor com L ±5/±10 %, C ±5 %, cabo ¼× e 4×, capacitância do motor ×3;
  - varredura "indutor de mercado (uk 7–10 %) × capacitores (IEC 61071) × ligação × nº por ramo", só aprovadas E robustas,
    ordenadas por nº de capacitores e custo; recomendação + robustez completa da recomendada;
  - seção explicando como cabo e motor entram no modelo e o que o ATP confirma (a conta) e o que só a medição confirma.
- Tela "Nova solicitação": escolha da prioridade – "Menor custo" ou "Indutor de mercado e MENOS capacitores (robusto)".
- A alternativa de indutância da ET do indutor passa a ser o ponto ótimo de mercado (com dupla checagem no ATP no PC).
- Fontes salvas no próprio estudo (MTE: artigo T. Luu IEEE 2020, manual SineWave Guardian, patentes US 9.571.058 e
  US 9.548.154; FRAKO: guia de projeto PEC, também no Gmail técnico; Schaffner; REO).

## v1.9.10 – 20/11/2026 – ATP-EMTP como referência em tudo que vai para o fornecedor
- Figuras das ETs (corrente no indutor e corrente no capacitor): quando o ATP rodou no projeto, a mesma corrente calculada no
  ATP é sobreposta (laranja tracejado) e o título mostra RMS ATP × Python.
- Alinhamento Python × ATP pela correlação da parcela de alta frequência (padrão PWM), em vez do cálculo de fase pelo f1 –
  o f1 do deck é ajustado ao passo de tempo do ATP e deslocava a ondulação no zoom. Vale também para o gráfico de dupla
  checagem (comparacao_fsen_casoN.png). Conferido com o ATP da A&W (138 µH): corrente no indutor 0,8–1,5 % de erro ponto a
  ponto do RMS (60 e 48 Hz); picos de corrente no capacitor no ATP 4–9 % maiores que no Python (Python limitado a 4,6·fs) –
  a exigência de Î na ET tem margem 1,5×.
- Alternativa de indutância recomendada passa pela dupla checagem no ATP (f máx e f mín) no PC com ATP; resultado na seção 9
  da ET do indutor e no e-mail ("confirmada no ATP-EMTP"). Sem ATP, a ET diz que a alternativa foi verificada só no Python.

## v1.9.9 – 20/11/2026 – Proteção contra erros de fornecedor (alta frequência)
- ET de CAPACITORES no padrão detalhado (fsen/spec_capacitor.py): "por que NÃO serve capacitor de correção de FP",
  figura da corrente real em um capacitor (Corrente_Capacitor_*.png), requisitos com coluna "Por quê" (IEC 61071, Imax,
  UN de pico, Î, ESR, ponto quente, vida, sobrepressão, lote ≤ 12 meses), dados a declarar, recebimento e critérios de
  aceitação (IEC 60831 = rejeição). E-mail reescrito no mesmo padrão.
- NOVA tela "Conferir proposta de fornecedor" (fsen/conferencia.py + telas_conferencia.py): digita-se o que o fornecedor
  declarou (indutor: L, linearidade, perdas 60 Hz/HF/total, massa, classe, chapa, entreferros, condutor, ensaios, protótipo,
  dimensões; capacitor: norma, UN, Imax, Î, ESR, ponto quente, sobrepressão, lote). A plataforma compara item a item com o
  porquê, aponta o que NÃO foi declarado (ex.: perdas de alta frequência), refaz o estudo térmico do painel com as perdas
  declaradas e o ponto quente do capacitor com a ESR declarada, e emite Parecer_Proposta_*.docx (+ .json) e o e-mail de
  resposta com as pendências em 03_Fornecedores. Parecer: APROVADO / COM RESSALVAS / INCOMPLETO / REPROVADO.
- Alternativa de indutância de mercado (fsen/alternativa_l.py): quando o L do projeto fica abaixo da faixa Schaffner/REO,
  simula L na faixa com o nº de capacitores reajustado, guarda as aprovadas (01_Engenharia/alternativa_indutancia.json),
  acrescenta a seção 9 na ET do indutor e pede no e-mail que o fornecedor cote também a recomendada.

## v1.9.8 – 20/11/2026 – Especificação detalhada do indutor (padrão para qualquer fornecedor)
- Nova ET_Indutor (fsen/spec_indutor.py), escrita para fornecedor que não conhece filtro senoidal:
  - "Por que este indutor NÃO é um reator de 60 Hz" + figura da forma de onda simulada do projeto (corrente com ondulação,
    zoom e pulsos de tensão PWM) – também salva como Forma_de_onda_Indutor_*.png para anexar;
  - tabela de requisitos com coluna "Por quê" (linearidade L × I até o pico e a sobrecarga, classe efetivamente fornecida,
    VPI, proteção térmica PTC/termostato, isolação para dv/dt, placa);
  - construção recomendada com o motivo (chapa fina, 2–4 entreferros por coluna – sem exigir entreferro distribuído –,
    bobina afastada do entreferro, sem fita atravessando o entreferro);
  - dados que o fornecedor deve DECLARAR, ensaios de rotina e de tipo (aquecimento com inversor + termografia), protótipo
    obrigatório ≥ 100 A, critérios de aceitação/rejeição;
  - referência de mercado (Schaffner FN5040 / REO N CNW 933) com faixa interpolada de L, perdas e massa; alerta se o L do
    projeto estiver abaixo da faixa; meta de perdas = menor entre a estimativa da plataforma e o teto do mercado.
- E-mail ao fornecedor reescrito no mesmo padrão, com o "por quê" de cada pedido.

## v1.9.7 – 19/11/2026 – Correção da leitura do ATP (.pl4 antigo)
- O tpbig não trunca um .pl4 que já existe. Quando a rodada anterior na mesma pasta de trabalho era mais longa (ex.: caso a
  30 Hz → 0,60 s), o fim do arquivo novo (41 Hz → 0,44 s) ficava com dados velhos e a comparação lia esse trecho.
  Foi o que gerou a falsa divergência na A&W v1.8.8 a 41 Hz (ATP 126 V × Python 302 V). Relido com a correção: 301,8 V × 302,1 V.
- Agora: .pl4/.lis/.dbg antigos são apagados antes de cada rodada; a leitura corta o arquivo no tamanho gravado no cabeçalho
  e para no primeiro salto de tempo (dupla proteção).
- Gráfico Python × ATP: a corrente no ramo do banco em triângulo agora também mostra a curva do Python (antes só a do ATP).

## v1.9.6 – 19/11/2026 – Relatório Técnico Final (padrão RTM)
- Novo documento em 02_Cliente: RTM-FSEN-<I>-<V>_Relatorio_Tecnico_Final.docx (+ PDF quando há Word/LibreOffice), no mesmo
  modelo dos relatórios de QEE/proteção da Plataforma de Estudos (capa Electric, índice de revisões, sumário com páginas):
  introdução, dados do sistema, especificação, referências técnicas (normas, critérios COM A ORIGEM de cada um, bibliografia),
  metodologia e softwares, validação da ferramenta, resultados Python, condições extremas, dupla checagem ATP-EMTP, limites de
  todos os componentes (motor, inversor/indutor, capacitores, ressonância, painel/cabos/refrigeração), estudo térmico,
  conclusões, síntese, pontos de atenção e recomendações.
- Memorial de cálculo: novo "Resumo para o cliente" e seção 2 com base normativa, origem dos critérios, metodologia,
  softwares, validação e bibliografia.

## v1.9.5 – 19/11/2026 – Medições sem motor
- As medições Dranetz de calibração foram SEM motor (confirmado pelo usuário). O modelo sem motor bate com elas.
- THD total ≤ 6 % a f máx (crítico) passa a ser calculado COM o motor (operação real); novo ALERTA "THD na saída do filtro
  SEM motor (teste/comissionamento a vazio)". Corrente e pico no capacitor continuam verificados com e sem motor (crítico).
- Validação: 8 de 11 projetos reais aprovados; GRATT 105 A, ASA e Franklin reprovam por pouco (6,1–6,4 %).

## v1.9.4 – 19/11/2026 – Calibração com as medições Dranetz
- Medições lidas direto dos .ddbx (leitor da Plataforma de Estudos, em cópia separada): SENAI 110/111 (958 µH/40 µF),
  112 (958 µH/20 µF) e IHR 2022 (1586 µH/20 µF) – saída do inversor × saída do filtro, harmônica a harmônica.
- Tabela de harmônicas de baixa ordem do inversor = medição (h5 2,3 · h7 0,7 · h11 1,1 · h13 0,5 · h17 0,45 · h19 0,5 %…);
  substitui a tabela teórica ×1,4 da v1.9.3.
- Amortecimento da ressonância de baixa ordem ajustado ao ganho de pico medido (Q equivalente 4).
- Pior caso considera também o filtro sem o motor (as 3 medições têm a ressonância na fr do LC sem motor).
  Resultado: SENAI 40 µF previsto 7,2 % (medido 7,2 %), IHR 4,9 % (medido 4,0 %), SENAI 20 µF 4,0–10,2 % (medido 4,9 %).
- Capacitores TDK B32361 10 µF (Imax 10 A, Î 400 A) e 30 µF (Imax 25 A, Î 800 A) com dados do datasheet.

## v1.9.3 – 19/11/2026 – Revisão dos filtros reais com ATP + calibração
- ATP: passo de tempo 2048 por período da portadora (antes 512). Com 512 a quantização das bordas do PWM gerava harmônicas
  falsas perto da ressonância (FN5040-24 a 30 Hz: 10,9 % no ATP × 2,4 % no Python; com 2048: 2,41 %). ~4× mais lento.
- Comparação Python × ATP: THD converge também com diferença absoluta ≤ 0,5 ponto; ondulação com tolerância 8 %.
- Calibração de campo: harmônicas de baixa ordem do inversor (tempo morto) × 1,4 (SENAI 958 µH/40 µF, Fluke: 3,6 % medido).
- Não abre mais ATPDraw/PlotXY ao terminar (pedido): roda o ATP em segundo plano e mostra na tela/diagramas; botão manual mantido.
- validacao/: decks_reais.py, comparar_atp_reais.py, aba "Python × ATP" e "Plataforma" na planilha de validação.

## v1.9.2 – 19/11/2026 – Desenho da rede no ATPDraw
- Em TODO projeto e em TODOS os pontos de operação a plataforma gera 01_Engenharia/ATP/fsen_casoN_desenho.xml: a MESMA
  rede do deck .atp desenhada no ATPDraw 7 (abre direto no programa): TACS do SVPWM (objetos FORTRAN 98 com as mesmas
  expressões), 3 fontes TACS tipo 60, sondas de tensão/corrente no inversor, banco e motor, L1 // Rp, banco Δ ou Y (com
  saída de corrente), cabo em células π (Cfase-terra e Cfase-fase), motor Rm+Lm em estrela + f.c.e.m. por fontes de corrente
  (Norton) + Cwf/3 à carcaça. Os valores do Python ficam no próprio desenho (comentário no topo do .atp que o ATPDraw gera).
- Conferido no ATPDraw 7.7 deste PC: o desenho rodado no próprio ATPDraw (F2) deu os MESMOS resultados do deck da
  plataforma (A&W Δ: DHTv banco 4,31 %, motor 4,28 %, I inversor 240,7 A, I motor 242,6 A, I ramo cap. 16,5 A – iguais),
  e bate com o Python (DHTv 4,20 % / 4,17 %; I 240,6 A / 242,5 A). Também conferido com banco em Y.
- Ao terminar a simulação abre juntos: PlotXY com o .pl4 do ATP + .mat do Python, e o ATPDraw com o desenho da rede.
- Caminho do ATPDraw corrigido para C:\ATP\ATPDraw77\Atpdraw.exe (catálogo e busca automática).

## v1.9.1 – 19/11/2026 – Abrir no PlotXY / ATPDraw
- Ao terminar a dupla checagem (Windows), abre sozinho o .pl4 do ATP no PlotXY JUNTO com as ondas do Python
  (fsen_casoN_python.mat, MATLAB v4, mesmas grandezas com sufixo _PY: V_INV_AB, V_CP_AB, V_MT_AB, I_L1_A, I_MT_A, I_CAP_RAMO),
  para sobrepor Python × ATP no próprio PlotXY; e abre o desenho .acp no ATPDraw quando existir.
- Botão "🖥️ Abrir este ponto no PlotXY (ATP + Python) e no ATPDraw" na tela de resultados.
- Catálogo: atp.plotxy, atp.atpdraw (caminhos) e atp.abrir_ao_terminar.
- PENDENTE: gerar o desenho ATPDraw (.acp) da rede – precisa do .acp de referência (PWMMOTOR_Jul_2023_filtro_LCL.acp) para
  copiar o formato exato da versão do ATPDraw instalada.

## v1.9.0 – 19/11/2026 – Simulação Python × ATP lado a lado
- Para cada ponto de operação, três vistas (tela, pasta 01_Engenharia/ATP e memorial 5.5):
  1. Rede elétrica simulada (inversor → L1 → banco Δ/Y → cabo π → motor) com os valores de CADA ramo calculados pelos dois
     programas: Python | ATP | diferença % (correntes, tensões, DHTv, picos, ondulação, corrente por capacitor).
  2. Formas de onda em 3 colunas – Python | ATP | sobreposição – para tensão do inversor, tensão no banco, tensão no motor,
     corrente do inversor/L1, corrente do motor e corrente do ramo do banco, com máx/mín/RMS em cada gráfico.
  3. Espectro em % da fundamental (linear) da tensão no banco e no motor, Python × ATP, com o DHTv de cada um.
- Quando há divergência, o quadro do ATP diz QUAIS grandezas divergiram (ponto, Python × ATP, %).
- O deck .atp passa a gravar também a tensão de saída do inversor (nós VLA/VLB/VLC) e os .pl4 ficam na pasta do projeto.
- Sem ATP no computador, as vistas mostram só o Python (coluna ATP vazia) e dizem que o ATP não rodou.

## v1.8.9 – 19/11/2026 – ATP sempre visível
- Barra lateral: "ATP: encontrado (caminho do tpbig)" em verde ou "ATP NÃO encontrado" em amarelo.
- Resultado do projeto: quadro destacado "Dupla checagem no ATP" – ✅ rodou e convergiu / ❌ divergência / ⚠️ não rodou (motivo),
  com hora, programa usado, tempo, tabela Python × ATP por ponto (diferença e tolerância) e as formas de onda sobrepostas.
- RESUMO.md ganha a seção "Dupla checagem no ATP" (sempre, inclusive quando não rodou e por quê).
- 01_Engenharia/ATP/status_atp.json registra o que aconteceu; o memorial (5.5) diz o motivo quando o ATP não roda.

## v1.8.8 – 19/11/2026 – Pastas sem digitar caminho
- Toda escolha de pasta agora é por botão "📁 Procurar..." (abre a janela do Windows) ou por "Navegar" (caixas de seleção:
  subpastas, pasta acima, unidades C:, G:…). Vale para a pasta de saída (menu lateral, lembrada no computador),
  "Abrir projeto já feito" (outra pasta) e "Importar pastas antigas" (lista montada por seleção).
- "Abrir um projeto já feito": lista o que existe de fato na pasta, inclusive subpastas antigas do cliente (até 3 níveis),
  clientes e projetos do mais recente para o mais antigo, com data/hora; caminho completo do projeto selecionado.

## v1.8.7 – 19/11/2026 – Leitura do pedido sem surpresas
- Problema visto no projeto das 17:16 (pasta "Cliente sem nome"): o pedido gravado tinha só corrente, quantidade e limites
  (sem cliente, motor, cabo, faixa 41–48 Hz, inversor) → simulação genérica e e-mail ao cliente perguntando tudo de novo.
- Agora, depois de "🔎 Ler solicitação", a tela mostra: quem leu (IA – modelo/esforço, ou REGRAS), hora, tempo e quais arquivos
  foram lidos; e um aviso com os campos essenciais NÃO encontrados (cliente, motor, cabo, inversor, faixa de operação).
  Se os dados não vieram de uma leitura nesta sessão, avisa. Ler de novo limpa o resultado anterior.
- Cliente passa a ser obrigatório para dimensionar (não cria mais "Cliente sem nome").
- IA pela assinatura: esquema JSON vai no texto do pedido (no Windows o claude.cmd estragava o --json-schema na linha de comando).
- Pasta do cliente sem traço sobrando no fim ("A & W Suprimentos Industriais –" → "A & W Suprimentos Industriais").

## v1.8.6 – 19/11/2026 – Questionário específico de cada pedido
- Corrigido (aviso do usuário: "faz sempre o mesmo questionário"): a leitura sem IA não reconhecia fs, tipo de controle,
  temperatura ambiente, altitude, IP, seção/blindagem do cabo, aterramento, filtro EMC, motor para inversor, mancal isolado,
  tensão auxiliar, espaço e tipo de carga → esses itens eram perguntados de novo mesmo quando vinham no pedido.
  Também valores iguais ao padrão (ex.: 60 Hz, IP54) contavam como "não informados".
- E-mail e questionário agora mostram "Dados que JÁ recebemos e usamos" e só perguntam o que falta NESTE pedido.
  Itens que não mudam nada na simulação deste projeto viram uma linha "Opcional" (montagem/caixa), não perguntas numeradas.
- Teste: pedido sem dados → 21 perguntas; A&W → 8 perguntas + opcionais; pedido completo → 2 perguntas.

## v1.8.5 – 19/11/2026 – IA pela assinatura + gráficos
- IA padrão agora usa a SUA ASSINATURA Claude (Claude Code instalado e logado no computador) – sem chave de API.
  Modelo (Opus 5.5 padrão) e esforço (médio padrão) por lista; botão "Testar IA". "Claude via API" continua como opção.
  Teste com a solicitação 0796/2026 + ficha + cartão: leu 3 pç, 293 A, 440 V, motor 211 A, cabo 20 m, 41–48 Hz e
  também o contato do cartão (Marcos Maia, comercial01@...).
- Espectro: escala LINEAR em % da fundamental (inversor em cima; saída do filtro e motor embaixo com escala própria),
  caixas com o máximo de cada um e tabela de DHTv % – Inversor | Saída do filtro | Motor – por ponto de operação.
- Novo gráfico "Correntes e tensões RMS por ramo": inversor/L1, ramo capacitivo, capacitor por unidade, motor e ondulação;
  tensões do inversor (PWM e fundamental), saída do filtro, motor, capacitor e queda no L1 – com máx/mín de cada ramo,
  In do filtro, Imax e V nominal do capacitor. Entra na tela, no memorial (Fig. 6b) e na pasta graficos.
- Formas de onda: caixas de máximo, mínimo e RMS em todas as curvas (inversor, filtro, i1, i2, iC) e a tensão no motor.

## v1.8.4 – 19/11/2026 – IA na leitura dos pedidos
- Menu lateral: lista para escolher o modelo Claude (Opus 5.5 – padrão, Sonnet 5.5, Haiku 5.5, Fable 5.2) e o esforço
  (baixo / médio – padrão / alto / muito alto / máximo → output_config.effort da API).
- 🔑 Chave da API: campo para colar a chave + botões Salvar e Testar IA. A chave fica só no computador
  (%USERPROFILE%\.fsen\chaves.json), nunca no Drive/GitHub. Preferências de modelo/esforço em %USERPROFILE%\.fsen\ia_usuario.yaml
  (não são apagadas quando o ABRIR_FSEN.bat atualiza o programa).
- Status visível: verde "IA ativa: modelo · esforço" ou amarelo "IA DESLIGADA – usando regras".
- Se a IA falhar (chave, rede, crédito), a leitura cai para regras e o motivo aparece nas premissas – não falha mais em silêncio.
- Chamada compatível com os modelos 5.x (thinking adaptativo): tool_choice auto, max_tokens 16000.

## v1.8.3 – 19/11/2026 – Leitura do pedido sem IA (docx com tabela)
- Corrigido (aviso do usuário: "não é 100 A o filtro"): sem chave de IA, a leitura por regras IGNORAVA os anexos .docx
  (só lia PDF/TXT). A solicitação da A&W vem em tabela no Word → corrente ficava 0 e o formulário preenchia 100 A escondido;
  motor (211 A, 175 CV, FP 0,88, FS 1,15) e cabo (20 m) também se perdiam.
- Agora lê parágrafos + tabelas do .docx; quantidade pela linha da tabela (Item | Qtd | Descrição).
  Teste com a solicitação 0796/2026: 3 pç, 293 A, 440 V, ACS580 293 A, motor 211 A, cabo 20 m, 41–48 Hz, 750 V, 375 V/µs, 2 µs.
- Formulário: sem valor padrão escondido – se faltar corrente/tensão, avisa e bloqueia; mostra a linha "Entra na simulação: ...".

## v1.8.2 – 19/11/2026 – Rastreabilidade da versão
- Nome e versão da plataforma na tela (menu lateral e aba do navegador) e em TODOS os arquivos gerados:
  RESUMO, rodapé dos .docx (memorial, proposta, folha de dados, ETs, RFQ, caderno), aba "Plataforma" e propriedades dos .xlsx,
  carimbo dos desenhos (PDF/PNG), linha "Ref. interna" no fim dos e-mails .txt, campo "gerado_por" dos .json e cabeçalho dos decks ATP.
- Corrigido: ao atualizar com a plataforma aberta aparecia "ImportError: cannot import name ..." (módulos antigos na memória);
  agora a plataforma recarrega os módulos sozinha quando a versão muda.

## v1.8.1 – 19/11/2026 – Abrir projeto já feito
- Novo painel "📂 Abrir um projeto já feito" em **Nova solicitação** e em **Ajuste manual e ressimulação**: escolha Cliente → Projeto
  (lista o que está em PROJETOS) ou cole o caminho da pasta do cliente/projeto. Carrega pedido, configuração (L, C, fs, ligação),
  resumo, gráficos, e-mails e arquivos; dá para ressimular, ajustar e gerar de novo.

## v1.8.0 – 19/11/2026 – Validação com os filtros fabricados
- Rodados 9 projetos reais (IHR/Randon, SENAI, Gelluns, Install, AB-Powertrain, GRATT, Franklin, ASA) + Schaffner FN5040 e medições Fluke (SENAI, IHR).
- Corrigido: o "pior caso teórico" de ressonância de baixa ordem (velocidade exata + tolerâncias) era crítico e reprovava todo LC sem resistor – agora é ALERTA.
  Críticos novos: consequência no capacitor nesse pior caso (I e Û) e THD total nominal na f máx (PWM + baixa ordem ≤ 6 %).
- Padrão Electric: SÓ LC sem resistor (cascata_topologias = [LC]); RC/LCL apenas por escolha na tela de comparação.
- fr mínima = 13 × f saída máx (calibrada nos filtros que funcionam em campo: 13,3–15×).
- Pasta validacao/: casos_reais.py (roda tudo de novo) e relatorio.py (planilha comparativa).

## v1.7.3 – 19/11/2026
- **Correção – sobremodulação** (aviso do usuário: a corrente do filtro saía menor que a da carga).
  - No ponto 60 Hz/In, com tensão de barramento insuficiente, a simulação mantinha a f.c.e.m. fixa e a corrente do motor caía (293 → 247 A).
  - Agora a CORRENTE de carga é mantida e só a tensão cai (função `op_efetivo`), no Python e no deck ATP.
  - A&W: inversor 289 A, motor 293 A e capacitores 11,5 A ∠+90°; a soma é vetorial.
- **ATP**: passo de tempo = submúltiplo exato da portadora (meio passo de defasagem no TACS).
  Isso elimina o jitter numérico das bordas, que gerava harmônica espúria a 48 Hz.
- **Nova verificação (alerta)**: ressonância natural do LC com o motor em paralelo × harmônicas altas do tempo morto (h29–h49).
  - Encontrada pela dupla checagem ATP: na A&W, a 41 Hz a h35 (1435 Hz) cai sobre a ressonância natural (~1430 Hz).
  - LC puro tem ganho ~55 nesse ponto; LC + RC tem ganho 2,4.
- Pastas de cliente: reaproveita a pasta existente mesmo com o nome escrito de forma diferente (acentos, LTDA etc.).

## v1.7.2 – 19/11/2026
- Projetos organizados em **uma pasta por cliente**: `PROJETOS\<Cliente>\<data>_<código>`.
  - O nome do cliente sai sem LTDA, S/A, (REVENDA) etc.
  - Quando a mesma solicitação é reprocessada no mesmo dia, ganha o sufixo _hhmm e a anterior não é sobrescrita.
- `ABRIR_FSEN.bat`: abre a plataforma com dois cliques.
  - Copia o programa do drive para o computador, encontra o Python (Anaconda primeiro) e instala as bibliotecas na primeira vez.
  - Abre o navegador automaticamente.

## v1.7.1 – 19/11/2026
- E-mails e ETs de fornecedores reescritos com contatos reais e conteúdo técnico completo:
  - **Cootrans** – Geraldo Nascimento, geraldogan@cootrans.com.br. O e-mail segue o padrão das cotações de 2022/23:
    L, Ir com ondulação, linearidade, sobrecarga, fs, dv/dt, classe H, perdas, espaço disponível e terminais.
  - **IFG** – André, ifg@ifg.com.br: capacitor B32361A4206J080, quantidade, norma IEC 61071, corrente aplicada × Imax.
    Desconta o estoque do catálogo e cita a OC anterior.
  - **Stampgraf** – Thiago, comercial3@stampgraf.com.br: novo e-mail e ET de plaqueta de identificação e adesivos.
  - Montagem, caixa e cabos: e-mails detalhados; a montadora continua "a definir".
- Indutor: classe H (180 °C, elevação ≤ 125 K) como padrão, como nas compras anteriores da Cootrans.
  A A&W passa a ter margem térmica de 27 K no indutor.
- Catálogo: os fornecedores ganharam os campos tratamento, telefone e referência.

## v1.7.0 – 19/11/2026
- **Dados faltantes automático** (novo módulo `fsen/dados_faltantes.py`):
  - checklist técnico de 20 itens: inversor, motor, cabos, local de instalação e requisitos;
  - detecta o que não veio no pedido (o leitor de IA registra os campos informados);
  - análise de sensibilidade: o projeto escolhido (mesmos L, C e fs) é refeito com valores plausíveis de cada dado
    ausente e classificado em CRÍTICO (reprova), IMPORTANTE ou CONFIRMAR. Valores testados:
    - fs 2 kHz;
    - ambiente 45 e 50 °C;
    - cabo de 100 e 200 m, cabo não blindado;
    - altitude 2000 m;
    - FP 0,80;
    - dispersão do motor 0,10 e 0,20 pu;
    - operação a 66 Hz.
  - Gera o e-mail ao cliente por prioridade, com a premissa adotada e o motivo de cada pergunta.
  - Gera o questionário técnico (.docx) e a planilha de sensibilidade.
  - Acrescenta uma tabela no memorial e uma seção no RESUMO.
  - Na tela, o e-mail aparece logo após o dimensionamento.
- Pedido: novos campos para esses dados; o leitor de IA passa a extraí-los dos e-mails:
  - temperatura ambiente, altitude, modo de controle, filtro EMC e aterramento;
  - motor para inversor, mancal isolado, tipo e seção do cabo;
  - alimentação auxiliar, espaço disponível, entrada de cabos e tipo de carga.
- A&W: 13 itens a confirmar, 3 críticos:
  - fs fixa: com 2 kHz reprova;
  - modo de controle;
  - temperatura ambiente: a 45 °C o indutor classe F reprova.

## v1.6.0 – 19/11/2026
- **Dupla checagem automática no ATP-EMTP** (novo módulo `fsen/atp.py`):
  - a plataforma gera o deck .atp da mesma rede simulada no Python:
    - inversor PWM em TACS com a mesma SVPWM de amostragem regular;
    - L1 com Rp de perdas e banco Δ/Y com ramo RC opcional;
    - cabo em células π;
    - motor R-L com f.c.e.m. por Norton e Cwf.
  - O ATP do PC (C:\ATP\atpmingw\tpbig.exe) roda em segundo plano, sem janela.
  - A plataforma lê o .pl4 e compara 12 grandezas por ponto de operação, com tolerância.
  - Gera a planilha de comparação, os gráficos sobrepostos e a seção 5.5 do memorial.
  - Sem ATP no computador: deixa os decks e o rodar_atp.bat em 01_Engenharia/ATP.
- Parâmetro `pelicular` na simulação: R constante para a comparação com o ATP.
- Catálogo: bloco `atp:` (habilitado, tpbig, pasta_trabalho).
- Validação na A&W em delta, 3 pontos (41, 48 e 60 Hz):
  - 36 de 36 grandezas convergiram;
  - tensões e correntes: diferença ≤ 0,6 %;
  - picos: ≤ 1,7 %;
  - THD: +6 % relativo (≈ 0,2 ponto percentual).

## v1.5.0 – 19/11/2026
- **Suportabilidade do capacitor conforme a norma do tipo do capacitor** (nova função `limites_capacitor`):
  - IEC 61071 (eletrônica de potência / filtro AC): Irms, Û recorrente (UN pico), dv/dt = Î/C, ponto quente e vida, todos do datasheet.
    Nas condições extremas de curta duração admite 1,10·UN (IEC 61071).
  - IEC 60831-1/2 (capacitor de correção de FP): 1,10·UN; Imax pelo fator do datasheet (mínimo 1,3·IN); Û ≤ 1,2·√2·UN.
  - IEEE Std 18 (informativo, só para capacitor IEC 60831): 110 % V, 120 % Vpico, 135 % I, 135 % kvar.
- Capacitor de estoque corrigido pela placa (fotos dos projetos IFG/New Technologies) e pela OC IFG:
  **EPCOS/TDK B32361A4206J080** (FilterCap MKP AC, chamado de "PEC"), 20 µF ±5 %, 480 V RMS, UN 680 V pico, IEC 61071.
  Imax 20 A, Î 800 A, Rs 4,3 mΩ, ponto quente 85 °C, 100 mil h, Ø63,5 × 70 mm, 0,3 kg, R$ 129,40.
  - Antes: tratado como PFC IEC 60831 com limite de 1,3·IN = 4,7 A.
- Ponto quente, vida e estudo térmico do painel passam a usar os limites próprios de cada capacitor.
- ET e BOM informam a norma do capacitor e a corrente aplicada versus a admissível.
- A&W 293 A / 440 V reprocessado:
  - LC puro em **Delta** aprovado com **6 capacitores**.
  - Estrela com 15 capacitores.

## v1.4.1 – 19/11/2026
- Correção: teste de condições extremas aplicava a tolerância de L/C duas vezes (resultado pessimista).

## v1.4.0 – 19/11/2026
- **Modelo do sistema**: cabo filtro→motor em células π (R, L, C fase-terra e fase-fase; seção, paralelos, comprimento, blindado) e motor com dispersão, efeito pelicular e capacitância enrolamento–carcaça. Tensão, THD, pico e dv/dt avaliados nos TERMINAIS DO MOTOR.
- **Modo comum e terra**: tensão de modo comum no motor, corrente no PE/blindagem (RMS e pico nas comutações) e tensão estimada no mancal; opção de filtro "all-pole" (centro-estrela ao barramento CC).
- **Suportabilidade dos capacitores** (Δ e Y): pico de tensão com harmônicas, corrente RMS, perdas ESR + dielétrico, ponto quente, vida estimada, dv/dt.
- **Estudo térmico do painel** (IEC TR 60890 / IEC 61439-1): perdas por componente, perfil de temperatura do ar, temperatura de cada componente (indutor, capacitores, resistores, cabos, bornes, superfície), escolha automática do nº de ventiladores e do arranjo (indutor embaixo × capacitores na entrada de ar), mapa térmico.
- **Robustez**: ressonância de baixa ordem verificada nos cantos de tolerância (L ±5 %, C −5/+10 %) e teste de condições extremas (rede ±10 %, L/C, cabo 2×, sem cabo).
- **Ligação Δ/Y** selecionável no pedido e no catálogo.

## v1.3.0 – 19/11/2026
- **Topologias** (prática dos fabricantes): LC sem resistor (padrão – Schaffner, TDK, ABB, Danfoss, TCI), LC + ramo RC paralelo (Rd ótimo de Erickson), LC + resistor série, LCL, LCL + RC. Resistor em paralelo com o indutor descartado (dissiparia a tensão de chaveamento).
- **Cascata automática**: o otimizador tenta primeiro LC sem resistor; só passa às outras se nenhuma configuração LC for aprovada. Na tela de pedido é possível forçar topologias.
- Tela de ajuste: escolha do amortecimento (nenhum / RC paralelo / série), Cd por ramo, Rd ótimo ou em Ω; painel **Comparar topologias** com carregamento direto no ajuste.
- Simulação inclui ramo RC (perdas e corrente dos capacitores de amortecimento verificadas).
- **Capacitores permitidos**: restringir a otimização aos capacitores do estoque (tela do pedido, `--capacitor` na linha de comando ou `capacitores_permitidos` no catálogo).
- **IA selecionável**: Claude (padrão), ChatGPT, DeepSeek, Gemini, Mistral, Grok, OpenRouter e Ollama local (offline); modelo editável; queda automática para leitura por regras sem chave/rede. Configuração em dados/ia.yaml.

## v1.2.0 – 19/11/2026
- **Tela "Ajuste manual e ressimulação"**: abre com a solução automática e permite editar fs, L1 (em µH ou uk %), L2 (LCL), capacitor do catálogo ou personalizado (µF, tensão, Imax, preço), fechamento Δ/Y, nº por ramo ou ressonância desejada, resistor de amortecimento (por Q ou em Ω). Ressimula em ~1–3 s com todas as verificações, gráficos e comparação lado a lado com o automático; gera o pacote completo com a configuração manual (pasta *_AJUSTE-MANUAL-hhmm*).
- **Tela "Critérios de projeto"**: limites (THD, ressonância, uk, ondulação, capacitores, tensão no motor, térmica) e pesos da otimização editáveis, gravados no catálogo preservando comentários.

## v1.1.0 – 19/11/2026
- **Otimização global multiobjetivo como motor padrão** (todos os pedidos): varre fs do inversor (2–8 kHz), uk 4–15 %, tipo/ligação/quantidade de capacitores e amortecimento; ~1.000–4.000 configurações simuladas por pedido; fronteira de Pareto e nota ponderada (custo, confiabilidade, tamanho, perdas, THD, queda).
- **Simulação PWM exata**: instantes de chaveamento analíticos (amostragem regular simétrica) e espectro sem quantização. Corrige harmônicas falsas da v1.0 que levavam a ressonâncias baixas e resistor de amortecimento desnecessário.
- Pré-filtro de THD recalibrado; ripple medido com resolução fina.
- Perdas do indutor calibradas na linha Schaffner FN5040 (cobre + núcleo/Steinmetz em fs).
- Derating do inversor por frequência de chaveamento.
- Índice de confiabilidade (capacitores, resistor, margem de ressonância, regra europeia fr ≥ 20·f máx, densidade de perdas).
- Custo da versão IP00 (sem caixa) calculado em cada configuração.
- Memorial com mapa de Pareto; planilha com todas as configurações simuladas.
- Caso A&W 293 A: uk 8,5 %, 12 × 30 µF em estrela, fr ≈ 1,04 kHz, sem resistor; −R$ 2,2 mil e −710 W por filtro vs v1.0.

## v1.0.0 – 19/11/2026
- Primeira versão: substitui a planilha "Filtro Senoidal LC_Ver_1.0".
- Leitura automática de solicitações (Claude API + extrator por regras de reserva).
- Otimizador LC/LCL: varre uk 4–10 %, frequência de ressonância e arranjos reais de capacitores (Δ/Y, n por ramo, TDK PEC / WEG UCW 20 µF 480 V), com opção de resistor de amortecimento.
- Simulação PWM (SVPWM) em regime permanente exato: THD, Vpico, dv/dt, correntes por ramo, ondulação, reserva de tensão do inversor; resposta em frequência; robustez à ressonância de harmônicas de tempo morto.
- Componentes reais: indutor (L, In térmica, Isat, ripple, perdas, massa), banco de capacitores (V, I por unidade, descarga), resistores de amortecimento.
- Arranjo na caixa metálica, térmica/ventilação, cabos (NBR 5410), desenhos A3 (vistas, cortes, 3D, vista externa, diagrama trifilar, lista de cabos).
- Documentos: memorial de cálculo, proposta, folha de dados, ET + e-mail por fornecedor, RFQ de montagem, caderno de montagem, planilha BOM/custos/preço.
- Histórico SQLite de projetos e clientes, importador de pastas antigas, calibração de custo por cotações reais.
- Interface web (Streamlit) e monitor de e-mail (IMAP) com rascunho automático de resposta.
- Caso de validação: A&W Suprimentos – 3 × 293 A / 440 V (ACS580-01-293A-4, bomba 175 cv).
