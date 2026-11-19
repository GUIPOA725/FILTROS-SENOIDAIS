# Registro de atualizações – Plataforma FSEN

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
