# Registro de atualizações – Plataforma FSEN

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
