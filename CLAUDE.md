# Plataforma FSEN – instruções obrigatórias para qualquer sessão de IA

Engenheiro responsável: Guilherme (Electric Service). Responder em português.

## Antes de mexer em qualquer coisa
1. Ler `gestao/REQUISITOS.yaml` (registro de requisitos do engenheiro) e `gestao/REFERENCIAS_PROJETOS.yaml`.
2. Ler a última revisão em `gestao/REVISOES.md`.

## Durante a conversa
- SEM PEDIR AUTORIZAÇÃO (REQ-GER-007): TODA instrução, dica, exemplo, crítica ou referência nova do engenheiro entra NA HORA no `gestao/REQUISITOS.yaml`
  (novo REQ-<área>-<nº>, com as palavras dele, data, fonte, status PENDENTE) – antes de programar. Nada fica solto no chat.
- Referência nova (projeto antigo, foto, medição) entra em `gestao/REFERENCIAS_PROJETOS.yaml` com as lições e os REQ ligados.
- Ao implementar: atualizar `atende`, `status`, `desde` e `nota` do requisito.

## Antes de publicar uma versão
1. Gerar um projeto de teste e rodar `python gestao/verificar_requisitos.py <pasta_do_projeto>`.
2. Código de saída 1 (crítico reprovado ou regredido) → NÃO publicar; corrigir primeiro.
3. Escrever a análise da revisão em `gestao/REVISOES.md` e copiar `gestao/saida/Registro_Requisitos_v<versão>.xlsx`
   para o Drive em ATUALIZACOES-MELHORIAS\GESTAO.
4. Publicação (REQ-PUB-001): commit+push, zip em PROGRAMAS, arquivos em PROGRAMAS\FSEN_v1.7.1, CHANGELOG em
   ATUALIZACOES-MELHORIAS, cópia em %LOCALAPPDATA%\FSEN\programa; versão visível no app e nos arquivos.

   Antes do commit (v1.26.0): `python gestao/gerar_memoria.py` (memória que a IA da plataforma lê – copiar também para o Drive em
   MEMORIA_IA\MEMORIA_PROJETO.md) e, por ÚLTIMO, `python -m fsen.protecao gerar` (manifesto do código – qualquer .py/.bat alterado
   depois dele dispara o bloqueio "não pode editar o código" nos colegas). Publicar SEMPRE o manifesto_codigo.json junto.

## Regras que não podem ser esquecidas (resumo – o registro é a fonte)
- Só o engenheiro edita o código (REQ-GER-012); colegas usam o Assistente IA e a Biblioteca de componentes (A CONFERIR até ele aprovar).
- Nunca digitar senhas; não usar robô no ATPDraw; não instalar programas nem apagar tarefas/projetos de teste sem o engenheiro.
- Consolidado com TUDO; THD em todo espectro; coluna Check em todo resultado; pastas por fornecedor/análise.
- Desenho do painel só com medidas reais de catálogo/FEM, no padrão AGCO (SolidWorks) ou melhor, igual nos 3 filtros.
- Comparar sempre com o projeto real anterior do cliente quando existir (ex.: reator Cootrans da Panatlântica 2024).
- Inversor (REQ-INV-010): dados de fs, derating, IN e frame SEMPRE do manual completo do fabricante, cadastrado em
  `dados/inversores_manuais.yaml` com documento, revisão, página e link; conferir com o modelo que o cliente passou.
