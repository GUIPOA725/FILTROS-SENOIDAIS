"""Organiza a pasta do projeto em subpastas por tipo de documento / fornecedor (v1.11.0).

Roda no final do processamento. Os arquivos de DADOS (projeto.json, arranjo_orcamento.json, indutor_projeto.json,
alternativa_indutancia.json, pedido.json) e a pasta ATP ficam onde estão, porque a plataforma os lê para reabrir o projeto,
conferir propostas e mostrar o ATP.
"""
import os
import re
import shutil

# (pasta principal, subpasta, padrões de nome – regex, sem distinção de maiúsculas)
REGRAS = [
    ("01_Engenharia", "1_Memorial_e_Custos", [r"Memorial_de_Calculo", r"BOM_Custos"]),
    ("01_Engenharia", "2_Estudos_Opcoes_e_Robustez", [r"Estudo_Opcoes", r"opcoes_min_capacitores", r"Estudo_Ponto_Otimo",
                                                      r"Otimizacao_todas", r"Sensibilidade_Dados"]),
    ("01_Engenharia", "3_Indutor_Elementos_Finitos", [r"^Indutor_.*\.png$", r"^Verificacao_", r"^Resultados_Medidos_Indutor",
                                                      r"^verificacao_indutor\.json$", r"^estudo_camadas_indutor\.json$",
                                                      r"^Analise_Avancada_", r"^Avancado_", r"^avancado_indutor\.json$"]),
    ("01_Engenharia", "4_Verificacao_do_sistema", [r"^VERIFICACAO_SISTEMA_", r"^AUDITORIA_"]),
    ("01_Engenharia", "5_Compras_Interno", [r"^INTERNO_"]),
    ("01_Engenharia", "6_Players_Mercado", [r"^Players_Mercado_"]),
    ("01_Engenharia", "7_Inversor_Manual", [r"^Inversor_Manual_"]),
    ("02_Cliente", "1_Proposta_e_Email", [r"Proposta_Comercial", r"Email_Resposta_Cliente"]),
    ("02_Cliente", "2_Folha_de_Dados", [r"Folha_de_Dados"]),
    ("02_Cliente", "3_Relatorio_Tecnico", [r"Relatorio_Tecnico"]),
    ("02_Cliente", "4_Dados_Faltantes", [r"Email_Solicitacao_Dados", r"Questionario_Tecnico"]),
    ("03_Fornecedores", "1_Indutor", [r"Indutor", r"^Parecer_Proposta_Indutor"]),
    ("03_Fornecedores", "2_Capacitores", [r"Capacitor"]),
    ("03_Fornecedores", "3_Resistores", [r"Resistores"]),
    ("04_Montadora", "1_Cotacao_Montagem", [r"RFQ_Montagem", r"Email_Montagem", r"^ET_Caixa", r"^ET_Plaqueta", r"^LM_Cabos"]),
    ("04_Montadora", "2_Caderno_Montagem", [r"Caderno_Montagem"]),
    ("04_Montadora", "3_Desenhos", [r"_desenhos\.pdf$"]),
    ("05_Desenhos", "1_Painel", [r"_desenhos\.pdf$", r"^folha\d"]),
]
LEIA_ME = """ORGANIZAÇÃO DESTE PROJETO (Plataforma FSEN)

01_Engenharia ............ USO INTERNO – não enviar para fora
   1_Memorial_e_Custos ...... memorial de cálculo, lista de material, custos e preço
   2_Estudos_Opcoes_e_Robustez  estudo de mínimo de capacitores, ponto ótimo/robustez, todas as configurações, sensibilidade
   3_Indutor_Elementos_Finitos  mapa de campo e folhas do projeto do indutor (imagens)
   4_Verificacao_do_sistema . Verificação do sistema (PDF) – dossiê para um auditor externo; não é auditoria
   5_Compras_Interno ........ fornecedores sugeridos para cotar (NÃO enviar a fornecedor)
   6_Players_Mercado ....... comparação com os players mundiais (Schaffner, TDK, Block, Danfoss, MTE) – fontes e critérios
   7_Inversor_Manual ....... dados do inversor retirados do manual completo do fabricante (documento, revisão, página, link)
   ATP ...................... decks, resultados e comparação Python × ATP-EMTP
   (arquivos .json na raiz: dados que a plataforma lê para reabrir o projeto – não mover)

02_Cliente ............... vai para o CLIENTE
   1_Proposta_e_Email ....... proposta comercial + texto do e-mail de resposta
   2_Folha_de_Dados ......... folha de dados do filtro
   3_Relatorio_Tecnico ...... relatório técnico (padrão RTM)
   4_Dados_Faltantes ........ e-mail e questionário pedindo os dados que faltaram

03_Fornecedores .......... uma subpasta por COMPONENTE – mandar só a subpasta do fornecedor
   1_Indutor ................ ET + projeto de referência (desenhos, CAD) + memorial + protocolo do protótipo + questionário + e-mail → fabricante (ex.: Cootrans)
   2_Capacitores ............ ET + figura da corrente + e-mail
   (escopo Electric no filtro senoidal: indutor + capacitores; caixa, plaqueta, cabos e miscelânea são da MONTADORA)
   (os pareceres de conferência de proposta são gravados na subpasta do componente)

04_Montadora ............. NÃO é fornecedor: pacote de cotação da montagem (RFQ + e-mail + ETs dos itens que ela compra:
                           caixa, plaqueta/adesivos, cabos e miscelânea), caderno de montagem, desenhos do painel
05_Desenhos .............. 1_Painel (vistas, 3D, diagrama, cabos)  |  2_Indutor (projeto de referência)
graficos ................. figuras da simulação
"""
FICAM = {"projeto.json", "arranjo_orcamento.json", "indutor_projeto.json", "alternativa_indutancia.json", "pedido.json"}


def subpasta_fornecedor(pasta_proj, componente):
    """Caminho da subpasta do fornecedor (usado pela conferência de propostas)."""
    nome = {"indutor": "1_Indutor", "capacitor": "2_Capacitores", "capacitores": "2_Capacitores"}.get(componente, "")
    p = os.path.join(pasta_proj, "03_Fornecedores", nome) if nome else os.path.join(pasta_proj, "03_Fornecedores")
    os.makedirs(p, exist_ok=True)
    return p


def organizar(pasta, arquivos=None, log=None):
    """Move os documentos para as subpastas. Atualiza o dict 'arquivos' (caminhos) se passado. Retorna nº de movidos."""
    movidos = {}
    for principal, sub, pads in REGRAS:
        base = os.path.join(pasta, principal)
        if not os.path.isdir(base):
            continue
        for f in sorted(os.listdir(base)):
            orig = os.path.join(base, f)
            if not os.path.isfile(orig) or f in FICAM or orig in movidos:
                continue
            if any(re.search(p, f, re.I) for p in pads):
                dest_dir = os.path.join(base, sub)
                os.makedirs(dest_dir, exist_ok=True)
                dest = os.path.join(dest_dir, f)
                if os.path.exists(dest):
                    os.remove(dest)
                shutil.move(orig, dest)
                movidos[orig] = dest
    # cópia dos desenhos do indutor também em 05_Desenhos/2_Indutor (desenhos todos num lugar só)
    ind = os.path.join(pasta, "03_Fornecedores", "1_Indutor")
    if os.path.isdir(ind):
        for f in os.listdir(ind):
            if f.startswith("Projeto_Referencia_Indutor") and f.endswith(".pdf"):
                d2 = os.path.join(pasta, "05_Desenhos", "2_Indutor")
                os.makedirs(d2, exist_ok=True)
                shutil.copy2(os.path.join(ind, f), os.path.join(d2, f))
    with open(os.path.join(pasta, "LEIA-ME_PASTAS.txt"), "w", encoding="utf-8") as fh:
        fh.write(LEIA_ME)
    if arquivos is not None:
        for k, v in list(arquivos.items()):
            if isinstance(v, str) and v in movidos:
                arquivos[k] = movidos[v]
    if log:
        log(f"   Pastas organizadas por tipo/fornecedor ({len(movidos)} arquivos em subpastas)")
    return len(movidos)


def achar(pasta_principal, padrao):
    """Procura um arquivo numa pasta principal e nas subpastas (projetos antigos sem subpastas também funcionam)."""
    for raiz, _, fs in os.walk(pasta_principal):
        for f in fs:
            if re.search(padrao, f, re.I):
                return os.path.join(raiz, f)
    return None
