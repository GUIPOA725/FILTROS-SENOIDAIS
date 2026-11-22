"""Ajuda embutida para quem usa a plataforma pela primeira vez (v1.18.0).

Três camadas, sem manual para ler:
  1. DICAS – passar o mouse no "?" de cada campo mostra o que ele faz, de onde vem o valor e o padrão Electric.
     Ficam TODAS aqui (um lugar só para manter); `instalar_dicas()` coloca a dica em qualquer campo que ainda não tenha.
  2. PASSO A PASSO – na barra lateral, o roteiro da tela aberta (o que fazer agora, o que vem depois).
  3. ASSISTENTE – pergunta livre ("por que deu 400 kvar?", "o que é FD?", "deu erro, e agora?"): responde com a mesma IA
     configurada para ler os pedidos, sabendo em que tela o usuário está, o que preencheu, o último log e o último erro.
     Todo erro mostrado na tela fica registrado (~/.fsen/erros.log) e ganha o botão "Explicar este erro".
Perguntas e respostas ficam em ~/.fsen/ajuda_historico.jsonl – o desenvolvedor vê as dúvidas mais comuns e melhora as dicas.
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import traceback

PASTA = os.path.join(os.path.expanduser("~"), ".fsen")
ARQ_ERROS = os.path.join(PASTA, "erros.log")
ARQ_HIST = os.path.join(PASTA, "ajuda_historico.jsonl")
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ------------------------------------------------------------------------------------------------ 1. dicas por campo
DICAS = {
    "Marca dos componentes": "Fabricante dos componentes do painel: Padrão Electric, ABB, Schneider, Siemens, WEG ou Epcos. O reator é "
                             "sempre Electric. Os capacitores da marca entram no cálculo da sintonia; a contatora (comum AC-3/AC-1 com "
                             "reator em série, ou AC-6b) é conferida no estudo de transitórios contra o pico de fechamento do catálogo.",
    # ---- barra lateral / geral
    "Tipo de filtro": "Escolha o produto: filtro senoidal (saída de inversor → motor), banco de capacitores dessintonizado "
                      "(correção de FP com reator, padrão Electric FD 8,16 %) ou filtro sintonizado (5ª/7ª/11ª, quando a "
                      "distorção é alta). Na dúvida entre dessintonizado e sintonizado, carregue a medição: a plataforma sugere.",
    "Menu": "Nova solicitação = projeto do zero. Ajuste manual = mexer num projeto já gerado e ressimular. Conferir proposta = "
            "comparar o que o fornecedor cotou com o especificado.",
    "IA para ler os pedidos": "Qual IA lê e-mails, relatórios e planilhas. 'Claude – sua assinatura' usa o Claude Code logado "
                              "no computador (sem custo extra). Sem IA a leitura é por regras simples e você confere tudo.",
    "Modelo Claude": "Modelo usado na leitura. O padrão já é o recomendado; troque só se o suporte pedir.",
    "Esforço": "Quanto a IA 'pensa' antes de responder. Alto = leitura mais cuidadosa de relatórios longos (mais lento).",
    "Testar IA": "Faz uma pergunta curta para a IA e mostra se está respondendo. Use quando a leitura falhar.",
    "Pasta onde ficam os projetos": "Onde a plataforma grava cada projeto (uma pasta por cliente, uma subpasta por projeto "
                                    "com data e hora). A escolha fica lembrada no seu usuário do Windows.",
    # ---- filtro senoidal
    "Cliente": "Nome do cliente como vai sair nos documentos e no nome da pasta.",
    "CNPJ": "Opcional – sai na proposta.", "Cidade/UF": "Opcional – sai na proposta.",
    "Quantidade": "Quantos filtros iguais. Afeta só proposta e pedidos aos fornecedores.",
    "Contato": "Pessoa do cliente (sai na proposta).", "E-mail": "E-mail do contato (sai na proposta).",
    "Topologia": "LC = indutor + capacitor (padrão). LCL = mais um indutor do lado do motor, para cabos longos ou dv/dt baixo.",
    "Revenda": "Marque se o filtro é para revenda – muda textos e margens da proposta.",
    "Tensão (V)": "Tensão de linha na saída do inversor (fase-fase).",
    "Corrente do filtro (A)": "Corrente nominal do filtro – normalmente a corrente nominal do inversor (não a do motor).",
    "Freq. rede (Hz)": "Frequência da rede de alimentação (60 Hz no Brasil).",
    "fs chaveamento (kHz, 0 = padrão do inversor)": "Frequência de chaveamento do inversor. Deixe 0 para usar o valor típico "
                                                     "do modelo informado; informe se o cliente souber (vem no parâmetro do inversor).",
    "Inversor": "Fabricante e modelo do inversor (ex.: WEG CFW11). Ajuda a IA a achar fs e limites.",
    "Corrente inversor (A)": "Corrente nominal do inversor.",
    "f saída mín (Hz)": "Menor frequência de operação do motor.", "f saída máx (Hz)": "Maior frequência de operação do motor.",
    "Motor (cv)": "Potência do motor.", "Corrente motor (A)": "Corrente nominal do motor (placa).",
    "FP motor": "Fator de potência do motor (placa).", "Fator de serviço": "Fator de serviço do motor (placa, ex.: 1,15).",
    "Cabo (m)": "Comprimento do cabo entre o filtro/inversor e o motor – decide reflexão de onda e Vpico.",
    "Vpico máx (V)": "Pico de tensão máximo admitido no motor (NEMA MG1 parte 31 ou dado do fabricante).",
    "dv/dt máx (V/µs)": "Taxa de subida máxima admitida no motor.",
    "Rise time mín (µs)": "Tempo de subida mínimo admitido no motor.",
    "Seção do cabo ao motor (mm², 0 = automática)": "Seção do cabo do motor. 0 = a plataforma escolhe pela corrente.",
    "Cabos em paralelo por fase (0 = automático)": "Número de cabos por fase. 0 = automático.",
    "Cabo blindado (VFD)": "Marque se o cabo ao motor é blindado para inversor (muda a capacitância do cabo).",
    "Centro-estrela ao barramento CC (all-pole)": "Liga o centro-estrela dos capacitores ao barramento CC (filtro all-pole, "
                                                   "reduz também a tensão de modo comum).",
    "Aplicação": "Texto livre da aplicação (bomba, ventilador…).",
    "Cole aqui o e-mail do cliente": "Cole o e-mail do pedido. Junto com os anexos, a IA preenche os campos; depois confira.",
    "Anexos (PDF, imagem, DOCX)": "Arraste pedido, placa do motor/inversor, fotos, folhas de dados. Tudo é lido pela IA.",
    "🔎 Ler solicitação": "Lê o e-mail e os anexos e preenche os campos. Os valores lidos aparecem marcados; confira antes de dimensionar.",
    "Topologias": "Quais topologias a plataforma avalia na otimização.",
    "Prioridade do projeto": "O que pesa mais na escolha da solução: custo, perdas ou desempenho.",
    "⚙️ Dimensionar, simular e gerar todos os documentos": "Roda tudo: cálculo, simulação, projeto do indutor por elementos finitos, "
                                                           "memorial, especificações, desenhos e proposta. Pode levar alguns minutos.",
    # ---- banco / sintonizado
    "Usar medição do ícone QEE": "Usa os resultados (resumo/ficha/anexo) gerados pela Plataforma de Estudos – ícone QEE.",
    "A medição foi feita na barra onde o filtro será ligado?": "Se a medição foi em outro ponto, a plataforma ajusta a corrente "
                                                               "e a distorção para a barra do filtro.",
    "Usar estudo de proteção / curto": "Usa o estudo de proteção/curto (PDF do ícone de proteção) para tirar Scc, X/R e cenários da barra.",
    "Estudo": "Escolha o PDF do estudo de proteção.",
    "Barra/equipamento onde o filtro será ligado (como no estudo)": "Digite o nome da barra como aparece no estudo (ex.: QDF-03).",
    "Barra do estudo (confira)": "Barra encontrada no estudo – confira se é a certa.",
    "E-mail / pedido do cliente": "Cole o pedido. Junto com a medição e o estudo, a IA extrai kvar, tensão, harmônicas, trafo…",
    "🔎 Ler solicitação e medições": "Lê pedido, medição e estudo e propõe o banco com a justificativa. Confira as lacunas listadas.",
    "Como dimensionar o montante (kvar)": "Reativo das medições = o que a medição pede, sem folga. Com folga Electric = soma "
                                          "crescimento + perdas do trafo e garante o necessário mesmo perdendo 1–2 estágios "
                                          "(ex.: Panatlântica 300 → 400 kvar). A outra opção aparece como referência.",
    "Folga p/ crescimento (%)": "Margem para aumento de carga (padrão 15 %). Só vale no modo 'Com folga Electric'.",
    "Estágios de reserva (N-k)": "Quantos estágios podem falhar e o banco ainda entregar o necessário. Automático: 2 a partir de 250 kvar.",
    "Medição na BT (somar perdas reativas do trafo)": "Se a medição foi no secundário, soma o reativo consumido pelo próprio trafo.",
    "Acesso ao painel": "Frontal/traseiro: prof. 800, capacitores na frente, reatores atrás (padrão AGCO/Panatlântica). "
                        "Frontal: prof. 400, painel mais largo.",
    "Projeto / local": "Identificação do projeto/local (sai nos documentos).",
    "Tensão da rede (V)": "Tensão de linha da barra onde o banco será ligado (ex.: 380, 415, 440 V).",
    "Frequência (Hz)": "Frequência da rede.",
    "Estágios (kvar efetivos na rede, separados por +)": "kvar que cada estágio entrega NA REDE (já com o efeito do reator), "
                                                        "ex.: 50+50+50+50. O capacitor (maior, ex.: 3×25 kvar 525 V) a plataforma escolhe.",
    "Quantidade de bancos/filtros": "Quantos painéis iguais (afeta pedidos e proposta).",
    "Ambiente (°C)": "Temperatura do local do painel (padrão 40 °C) – entra na ventilação e nos reatores.",
    "Harmônica de cada ramo (na ordem dos estágios)": "Sintonizado: ordem de cada ramo, ex.: 5,5,7,11.",
    "Nr = fator × h": "Sintonizado: sintonia um pouco abaixo da harmônica (padrão 0,94 × h; Electric 4,4–4,8 na 5ª).",
    "DHTi drenada da rede (%)": "Sintonizado: distorção de corrente que o filtro vai absorver (informativo para a proposta).",
    "Pasta do projeto antigo": "Caminho completo da pasta de um projeto antigo (ex.: G:\\Drives compartilhados\\Engenharia\\1 - SERVIÇOS\\…\\PROJETO). "
                               "Os documentos são copiados para %LOCALAPPDATA%\\FSEN\\referencias para a IA estudar.",
    "Nome curto (ex.: CVI_sintonizado)": "Nome da subpasta da cópia local (sem espaços longos). Vazio = nome da pasta de origem.",
    "Copiar para a biblioteca": "Copia só documentos (PDF, Word, Excel, e-mail, CAD, ATP/PTW) até 25 MB cada – sem fotos e vídeos, "
                                "para gastar pouco espaço no computador.",
    "Apagar as cópias locais (liberar espaço)": "Apaga a pasta %LOCALAPPDATA%\\FSEN\\referencias inteira (o Drive não é tocado).",
    "Construção do filtro sintonizado": "Padrão: reator trifásico + capacitor trifásico seco PPM (ex. TDK série F). Robusta "
                                        "(ex. Pirelli Gravataí, a maior entrega de sintonizados da Electric): 3 reatores monofásicos de 2 colunas "
                                        "por ramo + capacitor trifásico impregnado em óleo – mais robusto térmica e mecanicamente, para serviço pesado.",
    "3 reatores monofásicos de 2 colunas por ramo": "Usa 3 reatores monofásicos em vez de 1 trifásico (correntes altas – ex. Cootrans 2016).",
    "Fator de dessintonia": "FD 8,16 % (Nr 3,5, 210 Hz) é o padrão Electric. FD 14 % (Nr 2,67) quando há 3ª harmônica relevante.",
    "k = I_projeto / I60": "Corrente de projeto do reator ÷ corrente a 60 Hz (padrão 1,3 dessintonizado / 1,8 sintonizado).",
    "Fator de qualidade FQ": "Fator de qualidade do reator (padrão 60 dessintonizado / 100 sintonizado).",
    "Tolerância de L (±%)": "Tolerância de indutância exigida do fabricante (Electric: ±2 %).",
    "Classe térmica": "Classe de isolação térmica do reator (Electric: F, 155 °C).",
    "Enrolamento": "Material do enrolamento do reator (Electric: chapa/barra de alumínio).",
    "Capacitores por estágio (opcional)": "Force o capacitor (ex.: 3x25x525). Vazio = a plataforma escolhe.",
    "Transformador (kVA)": "Potência do trafo que alimenta a barra – entra na ressonância e nas perdas.",
    "Impedância do transformador (%)": "Z% de placa do trafo (típico 5–6 %).",
    "Scc da rede em MT (MVA)": "Potência de curto na MT (concessionária ou estudo de proteção).",
    "Verificação independente + análise avançada dos reatores (NGSolve, ~2–3 min por reator)": "Confere o projeto do reator com um "
        "segundo motor de elementos finitos. Recomendado antes de mandar ao fornecedor.",
    # ---- ajuste manual (senoidal)
    "↺ Voltar para a solução automática": "Descarta os ajustes e volta ao que a plataforma calculou.",
    "Frequência de chaveamento (kHz)": "fs usada na ressimulação.",
    "Definir indutância por": "Informe o indutor por uk % ou direto em µH.",
    "uk (%) @ rede, In": "Queda de tensão no indutor na corrente nominal (típico 3–5 %).",
    "L1 (µH/fase)": "Indutância do indutor do lado do inversor.", "L2 (µH/fase)": "Indutância do indutor do lado do motor (LCL).",
    "Topologia LCL (indutor L2 no lado do motor)": "Liga a topologia LCL.",
    "Capacitor": "Capacitor do catálogo usado no filtro.", "Fabricante": "Fabricante do capacitor.", "Linha": "Série/linha do capacitor.",
    "µF": "Capacitância de cada unidade.", "Imax RMS (A, 0 = 1,3·In)": "Corrente máxima do capacitor. 0 = 1,3 × nominal.",
    "Preço (R$)": "Preço unitário para o custo.", "Fechamento": "Estrela ou triângulo dos capacitores.",
    "Ressonância desejada (Hz)": "Frequência de corte do filtro LC.", "Capacitores por ramo": "Unidades em paralelo por fase.",
    "Amortecimento": "Resistor de amortecimento (Rd) para não amplificar na ressonância.",
    "Q desejado (2 = muito amortecido, 10 = leve)": "Fator de qualidade do filtro.",
    "R por ramo (Ω)": "Resistência série por ramo.", "Rd por ramo (Ω)": "Resistor de amortecimento por ramo.",
    "▶ Ressimular": "Roda a simulação com os valores atuais (rápido).",
    "📦 Gerar pacote completo com esta configuração": "Gera todos os documentos com a configuração ajustada.",
    "Comparar topologias": "Simula as topologias lado a lado.",
    "Abrir projeto": "Carrega um projeto já gerado para ajuste.",
    "Ponto de operação": "Frequência/carga para abrir no PlotXY/ATPDraw.",
    # ---- conferência
    "Componente": "Qual componente da proposta do fornecedor conferir.",
    "Carregar a planilha preenchida (.xlsx)": "Planilha de conferência devolvida pelo fornecedor.",
    "Carregar resultado_femm_FSEN.csv": "Resultado do FEMM rodado pelo script gerado pela plataforma (verificação independente).",
    "Projeto": "Projeto já gerado (mais recente primeiro).",
    # ---- complementos (conferidos por validacao/verificar_ajuda.py)
    "Modelo": "Nome do modelo da IA para este provedor. Deixe o padrão, a menos que o suporte indique outro.",
    "Carregar exemplo A&W 293 A": "Preenche um pedido real de exemplo (A&W, 293 A) para treinar ou testar a plataforma.",
    "Avaliar somente": "Limita a otimização às topologias marcadas (vazio = todas).",
    "Capacitores a considerar / FORÇAR capacitor do estoque (vazio = todos)": "Restringe a escolha a estes capacitores – use para aproveitar estoque.",
    "Ligação do banco de capacitores": "Estrela ou triângulo; vazio = a plataforma avalia as duas.",
    "Perda de inserção máxima admitida @ f máx (%) – queda real de tensão na saída": "Queda de tensão máxima que o filtro pode causar "
        "na maior frequência de saída (típico 3–5 %). Mais folga = indutor maior e melhor filtragem.",
    "Usar a corrente informada pelo cliente (desmarcado = a Electric define pela carga: motor × FS + capacitores + cabo + ripple, "
    "margem 10 %; o ferro vai pela corrente do inversor)": "Marcado: usa a corrente do pedido. Desmarcado (padrão Electric): calcula "
        "pela carga real; o núcleo continua dimensionado pela corrente do inversor.",
    "Construção do indutor (projeto de referência por elementos finitos)": "Tipo construtivo do indutor de referência mandado ao fornecedor.",
    "Condutor do enrolamento (construção com 2 entreferros)": "Fio, barra ou chapa – muda perdas e temperatura.",
    "Verificação independente + análise avançada do indutor (NGSolve 2D/3D, térmico; +4 a 8 min)": "Confere o indutor com um segundo "
        "motor de elementos finitos e análise térmica. Recomendado antes de enviar ao fornecedor.",
    "Estudo 1 / 2 / 3 camadas da bobina (+2 a 4 min)": "Compara bobinas de 1, 2 e 3 camadas (perdas × custo × temperatura).",
    "➕ Adicionar esta pasta à lista": "Inclui a pasta escolhida na lista de pastas a importar para o histórico.",
    "Pastas a importar": "Pastas de projetos antigos que alimentam o histórico de clientes.",
    "Exportar planilha de clientes": "Gera Clientes_Fornecidos.xlsx com tudo o que já foi fornecido.",
    "Fornecedor": "Nome do fornecedor da cotação.",
    "Energia do indutor (J) – ver memorial": "Energia armazenada ½·L·I² do indutor (está no memorial) – base para comparar preços.",
    "Salvar cotação": "Guarda a cotação no histórico para calibrar custos futuros.",
    "catalogo.yaml": "Catálogo de componentes (capacitores, núcleos, preços). Edite com cuidado – vale para todos os projetos.",
    "Salvar catálogo": "Grava o catálogo editado.",
    "Nova melhoria / pedido": "Anote uma melhoria ou problema – vai para a lista do desenvolvedor (MELHORIAS.md).",
    "Anexos: pedido, unifilar, placa do trafo, fotos, relatório de QEE, medições (xlsx, csv, txt, pdf, docx, imagens)": "Arraste tudo "
        "o que tiver do cliente. Relatórios de QEE e exportações do Dranview/Fluke são lidos pela IA (médias, P95, máximos).",
    "Gerar projeto completo (reatores, desenhos, CAD, memorial, planilhas ESTAGIO, especificações, ET painel, proposta)": "Gera o "
        "pacote inteiro na pasta de projetos: reatores por elementos finitos, esquema elétrico, layout do painel, plaquetas, DE/PARA, "
        "memorial, especificações para Cootrans/montadora e proposta.",
    "Definir por": "Escolha como definir o capacitor: pela ressonância desejada ou pelo número de unidades.",
    "Definir": "Escolha como definir o amortecimento: pelo Q desejado ou pelo valor do resistor.",
    "Capacitores Cd por ramo (mesmo tipo)": "Capacitores do ramo de amortecimento (em série com Rd).",
    "Rd": "Resistor de amortecimento: calcular automaticamente ou informar.",
    "Carregar no ajuste manual": "Topologia da comparação a levar para o ajuste manual.",
    "Carregar esta topologia": "Leva a topologia escolhida para o ajuste manual.",
    "fs mínima avaliada (kHz)": "Menor frequência de chaveamento considerada nos critérios de projeto.",
    "fs máxima avaliada (kHz)": "Maior frequência de chaveamento considerada nos critérios de projeto.",
    "Salvar critérios": "Grava os critérios de projeto (valem para os próximos projetos).",
    "Onde procurar": "Na pasta de projetos padrão ou em outra pasta.",
    "Projeto (mais recente primeiro)": "Projeto a abrir.",
    "🖥️ Abrir este ponto no PlotXY (ATP + Python) e no ATPDraw": "Gera os arquivos do ponto escolhido para conferir no ATP. "
        "Os programas não são abertos automaticamente – abra-os você.",
    "🌙 Fundo escuro": "Deixa a tela com fundo escuro. O padrão é fundo branco; a escolha fica lembrada neste computador.",
    "Navegar": "Liga a navegação por pastas para escolher sem digitar o caminho.",
    "Entrar em": "Subpasta para entrar.",
    "…ou unidade": "Troca de unidade/drive (C:, G: …).",
}

# ------------------------------------------------------------------------------------------------ 2. passo a passo
GUIAS = {
    "senoidal": ["Escolha **Filtro senoidal** em Tipo de filtro.",
                 "Cole o e-mail e arraste os anexos → **🔎 Ler solicitação**.",
                 "Confira os campos (tensão, corrente, cabo, motor). Campo com dúvida? Passe o mouse no **?**.",
                 "Clique **⚙️ Dimensionar, simular e gerar** e aguarde (alguns minutos).",
                 "Abra a pasta do projeto: 02_Cliente (proposta/memorial), 03_Fornecedores (indutor, montadora), 05_Desenhos.",
                 "Quer mudar algo? Menu → **Ajuste manual e ressimulação**."],
    "dessintonizado": ["Escolha **Banco de capacitores dessintonizado** em Tipo de filtro.",
                       "Opcional: em *Medição (QEE) e estudo de proteção*, aponte as pastas e a barra do filtro.",
                       "Cole o pedido do cliente → **🔎 Ler solicitação e medições**.",
                       "Leia a **justificativa** e as **lacunas** (o que faltou e qual premissa foi usada).",
                       "Escolha o montante: **reativo medido** ou **com folga Electric** (crescimento, perdas do trafo, N-1/N-2).",
                       "Confira estágios, tensão, FD e trafo → gere o pacote.",
                       "Confira 03_Fornecedores/2_Painel_Montadora: ET do painel, esquema, layout, plaquetas, DE/PARA."],
    "sintonizado": ["Escolha **Filtro harmônico sintonizado** em Tipo de filtro.",
                    "Carregue a medição (harmônicas de corrente por ordem são essenciais).",
                    "**🔎 Ler solicitação e medições** → confira as ordens dos ramos (5ª/7ª/11ª) e o Nr.",
                    "Escolha o montante (medido ou com folga) e confira o trafo e o Scc (ressonância).",
                    "Gere o pacote e confira as especificações dos reatores e o painel."],
}


def guia(tipo):
    return GUIAS.get(tipo, GUIAS["senoidal"])


# ------------------------------------------------------------------------------------------------ instalação das dicas
_WIDGETS = ("number_input", "text_input", "text_area", "selectbox", "radio", "checkbox", "file_uploader", "slider",
            "multiselect", "button", "toggle", "date_input", "select_slider", "download_button")


def instalar_dicas():
    """Coloca a dica de DICAS em todo widget sem help= (st.* e colunas/sidebar/expander). Idempotente.
    Também passa a registrar todo st.error/st.exception para o assistente explicar."""
    import streamlit as st
    from streamlit.delta_generator import DeltaGenerator
    if getattr(DeltaGenerator, "_fsen_ajuda", False):
        return
    for nome in _WIDGETS:
        orig = getattr(DeltaGenerator, nome, None)
        if orig is None:
            continue

        def emb(orig=orig):
            def f(self, label=None, *a, **k):
                if not k.get("help") and isinstance(label, str):
                    d = DICAS.get(label.strip())
                    if d:
                        k["help"] = d
                return orig(self, label, *a, **k)
            f.__name__ = orig.__name__
            f.__doc__ = orig.__doc__
            return f
        setattr(DeltaGenerator, nome, emb())
    for nome in ("error", "exception"):
        orig = getattr(DeltaGenerator, nome)

        def emb_e(orig=orig, nome=nome):
            def f(self, body, *a, **k):
                try:
                    registrar_erro(body if isinstance(body, BaseException) else str(body), tela=st.session_state.get("ajuda_tela", ""))
                except Exception:
                    pass
                return orig(self, body, *a, **k)
            return f
        setattr(DeltaGenerator, nome, emb_e())
    DeltaGenerator._fsen_ajuda = True


# ------------------------------------------------------------------------------------------------ erros
def registrar_erro(erro, tela="", contexto=None):
    """Guarda o erro (texto ou exceção com traceback) para o assistente e para o desenvolvedor."""
    import streamlit as st
    if isinstance(erro, BaseException):
        txt = "".join(traceback.format_exception(type(erro), erro, erro.__traceback__))[-4000:]
    else:
        txt = str(erro)[:4000]
    reg = dict(quando=f"{_dt.datetime.now():%Y-%m-%d %H:%M:%S}", tela=tela, erro=txt, contexto=contexto or {})
    try:
        st.session_state["ajuda_ultimo_erro"] = reg
    except Exception:
        pass
    try:
        os.makedirs(PASTA, exist_ok=True)
        with open(ARQ_ERROS, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(reg, ensure_ascii=False, default=str) + "\n")
    except OSError:
        pass
    return reg


# ------------------------------------------------------------------------------------------------ 3. assistente
INSTRUCAO = """Você é o assistente de ajuda da Plataforma FSEN da Electric Service (projeto de filtros senoidais, bancos de
capacitores dessintonizados e filtros harmônicos sintonizados). Quem pergunta é um engenheiro/colega usando a plataforma pela
primeira vez. Responda em português, curto e prático (no máximo ~10 linhas): diga ONDE clicar/preencher (nome exato do campo ou
botão), o que o valor significa e qual o padrão Electric. Se a pergunta for sobre um resultado (ex.: por que deu X kvar), explique
usando a justificativa/log do contexto. Se for um erro, diga a causa provável em linguagem simples e o que fazer agora; se for
falha de programa, diga para enviar ao desenvolvedor o arquivo ~/.fsen/erros.log. Não invente campos que não existem na lista."""


def _base_conhecimento(tipo):
    partes = ["CAMPOS DA TELA E O QUE FAZEM:\n" + "\n".join(f"- {k}: {v}" for k, v in DICAS.items()),
              "PASSO A PASSO DESTA TELA:\n" + "\n".join(f"{i + 1}. {p}" for i, p in enumerate(guia(tipo)))]
    try:
        ch = open(os.path.join(RAIZ, "CHANGELOG.md"), encoding="utf-8").read()
        partes.append("ÚLTIMAS MUDANÇAS DA PLATAFORMA:\n" + ch[:6000])
    except OSError:
        pass
    return "\n\n".join(partes)


def _contexto_txt(ctx):
    linhas = []
    for k, v in (ctx or {}).items():
        s = json.dumps(v, ensure_ascii=False, default=str) if not isinstance(v, str) else v
        linhas.append(f"{k}: {s[:2500]}")
    return "\n".join(linhas)


def perguntar(pergunta, tipo="senoidal", contexto=None, provedor=None):
    """Resposta em texto livre, pela mesma IA da leitura de pedidos. Sem IA: responde com as dicas encontradas."""
    from .leitor_ia import config_ia, status_provedores, _claude_cli, carregar_chaves
    cfg = config_ia()
    provedor = provedor or cfg.get("provedor_padrao", "claude")
    prompt = (f"{INSTRUCAO}\n\n{_base_conhecimento(tipo)}\n\nCONTEXTO ATUAL DO USUÁRIO:\n{_contexto_txt(contexto)}\n\n"
              f"PERGUNTA: {pergunta}")
    resp = None
    try:
        if not status_provedores().get(provedor, {}).get("pronto"):
            raise RuntimeError("IA não configurada")
        pc = cfg["provedores"][provedor]
        if pc["tipo"] == "claude_code":
            import subprocess
            import tempfile
            exe = _claude_cli()
            cmd = [exe, "-p", "--output-format", "json", "--model", pc["modelo"]]
            r = subprocess.run(cmd, input=prompt, capture_output=True, text=True, encoding="utf-8", timeout=180,
                               cwd=tempfile.gettempdir(), creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            resp = str(json.loads(r.stdout).get("result", "")).strip()
        elif pc["tipo"] == "anthropic":
            import anthropic
            carregar_chaves()
            cli = anthropic.Anthropic(api_key=os.environ.get(pc.get("env_chave") or "ANTHROPIC_API_KEY"))
            m = cli.messages.create(model=pc["modelo"], max_tokens=1500, messages=[{"role": "user", "content": prompt}])
            resp = "".join(getattr(b, "text", "") for b in m.content).strip()
        else:
            from openai import OpenAI
            env = pc.get("env_chave") or ""
            cli = OpenAI(base_url=pc["base_url"], api_key=os.environ.get(env, "") if env else "ollama")
            m = cli.chat.completions.create(model=pc["modelo"], temperature=0.2, messages=[{"role": "user", "content": prompt}])
            resp = m.choices[0].message.content.strip()
    except Exception as e:
        achados = [f"**{k}** – {v}" for k, v in DICAS.items()
                   if any(p in (k + " " + v).lower() for p in pergunta.lower().split() if len(p) > 3)][:5]
        resp = (f"(Assistente sem IA: {type(e).__name__}. Dicas relacionadas:)\n\n" + "\n\n".join(achados)) if achados else \
               f"Assistente sem IA ({type(e).__name__}: {str(e)[:120]}). Passe o mouse no **?** dos campos ou veja o passo a passo acima."
    try:
        os.makedirs(PASTA, exist_ok=True)
        with open(ARQ_HIST, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(dict(quando=f"{_dt.datetime.now():%Y-%m-%d %H:%M}", tipo=tipo, pergunta=pergunta,
                                     resposta=resp[:3000]), ensure_ascii=False) + "\n")
    except OSError:
        pass
    return resp


def novidades(max_chars=900):
    """Primeira seção do CHANGELOG (versão atual) – aparece na ajuda para os colegas saberem o que mudou."""
    try:
        ch = open(os.path.join(RAIZ, "CHANGELOG.md"), encoding="utf-8").read()
        i = ch.index("## v")
        j = ch.find("\n## v", i + 4)
        sec = ch[i:j if j > 0 else None].strip().replace("## ", "**", 1)
        sec = sec.replace("\n", "**\n", 1) if sec.startswith("**") else sec
        return sec[:max_chars] + ("…" if len(sec) > max_chars else "")
    except (OSError, ValueError):
        return ""


CSS_ESCURO = """<style>
.stApp, [data-testid="stHeader"] {background:#0e1117 !important; color:#e6e6e6 !important;}
[data-testid="stSidebar"] > div:first-child {background:#161a23 !important;}
.stApp p, .stApp span, .stApp label, .stApp li, .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp div[data-testid="stMarkdownContainer"],
[data-testid="stSidebar"] * {color:#e6e6e6 !important;}
.stApp input, .stApp textarea, .stApp [data-baseweb="select"] > div, .stApp [data-baseweb="input"] > div,
.stApp [data-testid="stFileUploaderDropzone"], .stApp [data-testid="stExpander"] details {background:#1f2430 !important; color:#e6e6e6 !important; border-color:#3a4150 !important;}
.stApp [data-baseweb="popover"] *, div[data-testid="stPopoverBody"] {background:#1f2430 !important; color:#e6e6e6 !important;}
.stApp details summary, .stApp [data-testid="stExpander"] summary {background:#1f2430 !important; color:#e6e6e6 !important;}
.stApp [data-testid="stAlert"], [data-testid="stSidebar"] [data-testid="stAlert"] {background:#262c38 !important;}
.stApp [data-testid="stAlert"] * {color:#e6e6e6 !important;}
.stApp button[kind="secondary"] {background:#262c38 !important; color:#e6e6e6 !important; border-color:#3a4150 !important;}
</style>"""


def _lembrado(chave, padrao=None):
    try:
        from seletor import lembrado
        return lembrado(chave, padrao)
    except Exception:
        return padrao


def _lembrar(chave, valor):
    try:
        from seletor import lembrado, lembrar
        if lembrado(chave, None) != valor:
            lembrar(chave, valor)
    except Exception:
        pass


PACOTES = ("streamlit", "numpy", "scipy", "pandas", "matplotlib", "openpyxl", "python-docx", "ezdxf", "pdfplumber", "pypdf",
           "cadquery", "ngsolve", "netgen-mesher", "anthropic", "openai", "pywebview", "playwright")


def versoes_software():
    """Programas e bibliotecas que a plataforma usa neste computador, com a versão instalada (para o 'Sobre')."""
    import platform
    import shutil
    import subprocess
    from importlib import metadata
    out = [("Plataforma FSEN", _versao_fsen()), ("Python", f"{platform.python_version()} ({platform.architecture()[0]})"),
           ("Sistema", f"{platform.system()} {platform.release()}")]
    for p in PACOTES:
        try:
            out.append((p, metadata.version(p)))
        except Exception:
            out.append((p, "não instalado"))
    try:
        exe = shutil.which("claude") or shutil.which("claude.cmd")
        v = subprocess.run([exe, "--version"], capture_output=True, text=True, timeout=15).stdout.strip() if exe else ""
        out.append(("Claude Code (IA pela assinatura)", v or "não encontrado"))
    except Exception:
        out.append(("Claude Code (IA pela assinatura)", "não encontrado"))
    try:
        from .atp import achar_tpbig
        out.append(("ATP (tpbig)", achar_tpbig() or "não encontrado"))
    except Exception:
        pass
    return out


def _versao_fsen():
    try:
        return json.load(open(os.path.join(RAIZ, "versao_plataforma.json"), encoding="utf-8")).get("versao", "?")
    except Exception:
        return "?"


def sobre():
    """Bloco discreto no fim da barra lateral: versões de tudo o que a plataforma usa."""
    import streamlit as st
    with st.sidebar.expander("ℹ️ Sobre / versões dos programas"):
        if "ajuda_versoes" not in st.session_state:
            st.session_state["ajuda_versoes"] = versoes_software()
        st.markdown("\n".join(f"- **{n}**: {v}" for n, v in st.session_state["ajuda_versoes"]))
        st.caption("Python recomendado: 3.12 ou 3.13 (Anaconda). Versões muito novas (ex.: 3.15) às vezes ainda não têm "
                   "bibliotecas como NGSolve/onnxruntime/pythonnet.")


def painel(tipo, contexto=None, provedor=None):
    """Bloco da barra lateral: passo a passo + pergunta ao assistente + explicar o último erro."""
    import streamlit as st
    st.session_state["ajuda_tela"] = tipo
    # v1.18.2: botão grande no TOPO da tela (canto direito) – na barra lateral ficava escondido lá embaixo
    _, cesc, cdir = st.columns([8, 2, 2])
    escuro = cesc.toggle("🌙 Fundo escuro", key="tema_escuro", value=_lembrado("tema_escuro", False),
                         help="Fundo escuro. O padrão é fundo branco; a escolha fica lembrada neste computador.")
    _lembrar("tema_escuro", escuro)
    if escuro:
        st.markdown(CSS_ESCURO, unsafe_allow_html=True)
    pop = cdir.popover("🛟 Ajuda", use_container_width=True, help="Passo a passo desta tela, novidades da versão e assistente com IA")
    st.sidebar.info("🛟 **Ajuda**: botão no canto superior direito da tela (passo a passo, assistente, explicar erros).")
    with pop:
        q = st.text_input("Pergunte ao assistente", key="ajuda_q", placeholder="ex.: por que deu 400 kvar? o que é FD?",
                          help="Pergunta livre. O assistente sabe em que tela você está, o que preencheu e o último log/erro.")
        ctx = dict(contexto or {})
        err = st.session_state.get("ajuda_ultimo_erro")
        if err:
            ctx["ultimo_erro"] = err
        c1, c2 = st.columns(2)
        if c1.button("Perguntar", key="ajuda_btn", disabled=not q):
            with st.spinner("Pensando…"):
                st.session_state["ajuda_resp"] = perguntar(q, tipo, ctx, provedor)
            st.session_state["ajuda_aberta"] = True
        if err and c2.button("Explicar este erro", key="ajuda_err", help="Explica o último erro mostrado na tela e o que fazer."):
            with st.spinner("Analisando o erro…"):
                st.session_state["ajuda_resp"] = perguntar("Explique o último erro e o que eu faço agora.", tipo, ctx, provedor)
            st.session_state["ajuda_aberta"] = True
        if st.session_state.get("ajuda_resp"):
            st.info(st.session_state["ajuda_resp"])
        if err:
            st.caption(f"Último erro ({err['quando']}) registrado em {ARQ_ERROS} – envie ao desenvolvedor se não resolver.")
        st.markdown("**O que fazer nesta tela**")
        st.markdown("\n".join(f"{i + 1}. {p}" for i, p in enumerate(guia(tipo))))
        st.caption("Passe o mouse no **?** ao lado de cada campo para ver o que ele faz.")
        nov = novidades()
        if nov:
            with st.expander("Novidades desta versão"):
                st.markdown(nov)
