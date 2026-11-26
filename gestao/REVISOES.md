# Revisões e análise – Plataforma FSEN

Registro de cada versão contra o REGISTRO DE REQUISITOS do engenheiro (gestao/REQUISITOS.yaml).
As linhas "Revisão – vX" são geradas por `python gestao/verificar_requisitos.py <projetos>`; a análise é escrita à mão abaixo de cada uma.

## v1.31.1 – 26/11/2026 – correção Python 3.11 (REQ-GER-017)
**Erro (print do engenheiro):** SyntaxError f-string em fsen/pipeline.py:105 ao abrir a v1.31.0 – o notebook roda Python 3.11 (servidor.log); a f-string com aspas aninhadas entrou na v1.28.0, então v1.28.0–1.31.0 não abriam no notebook. A nuvem usa 3.13 e não acusou.
**Correção:** f-string reescrita; teste automático compila todos os .py com python3.11 (todos ok).
**Lição:** testar sempre na versão de Python do notebook – agora é check do verificador.

## v1.31.0 – 26/11/2026 – cotações em Word + e-mail curto (REQ-DOC-020)
**Feito:** fsen/et_cotacao.py (quadro resumo, o que a proposta deve trazer, anexos, contato, e-mail curto); ETs do indutor e capacitor do senoidal fechadas no fim do pipeline com os anexos reais; ET do reator do banco reformatada; ET nova dos capacitores do sintonizado; montadora em 04_Montadora (senoidal e banco).
**Testes:** A&W (senoidal) – e-mails de 30 linhas, ETs com quadro e seções finais, pacote da montadora com 3 ETs; Panatlântica (dessintonizado) – verificador "pode publicar"; sintonizado 2 × 100 kVAr h5 – ET dos capacitores gerada (sem verificação 3D do reator no teste: a nuvem sem memória matou o NGSolve 3D).
**Pendente:** contato da montadora no catálogo ("a definir"); ETs de caixa/plaqueta ainda simples.

## v1.30.0 – 26/11/2026 – filtro senoidal × players mundiais
**Pedido:** REQ-SEN-024 ("buscar nos 4 players mundiais... pasta players... planilha comparativa e no consolidado").
**Feito:** dados/players_filtro_senoidal.yaml (Schaffner, TDK, Block, Danfoss – C 115–260 A "conferir" –, MTE), fsen/players.py, planilha em 01_Engenharia/6_Players_Mercado, bloco no RESUMO e no consolidado.
**Teste:** A&W (pedido do projeto, prioridade mercado) – 9 modelos vizinhos de 5 fabricantes; uk 8,4 % (faixa 6,7–14), fr 1158 Hz (623–1359), 3,15 W/A (≤ 3,72) – APROVADO. Mudança isolada no filtro senoidal (banco não afetado).
**Pendente:** conferir C da Danfoss 115–260 A no PDF original; estender ao reator do banco (Epcos, Schneider, ABB, Frako, Cootrans); REQ-SEN-025 (estrela × delta).

## v1.29.0 – 25/11/2026 – fiação interna pela NBR IEC 61439-1 nos 3 filtros
**Pedido:** "então vc precisa mudar todo o codigo para a fiação ... NBR IEC 61439-1 nos 3 filtros"; "A canaleta é comando, os cabos de força são por fora das canaletas".
**Pesquisa:** gestao/analises/2026-11-25_norma_fiacao_interna_IEC61439.md (NBR IEC 61439-1:2016 obrigatória desde 12/2021; IEC 61921 manda atender a 61439; NBR 5410 §1.4).
**Feito:** fsen/fiacao_iec61439.py (Anexo H: 125 %, 70 °C, ar 55 °C, força fora da canaleta espaçada ≥ 1 diâmetro; opção encostados); contatora ≤ 80 % (AC-1) e ≥ 1,3 × I60; cabos de capacitor 1,3 × In; senoidal (mecanica/termico); EPLAN; lista (espaçadores; canaleta só comando); normas; 3D sem cabos de força em canaleta.
**Testes:** Panatlântica ABB – sem reprovações, 22 atenção; 50 mm² + AF80 (antes 70 + AF116); verificador "pode publicar". A&W (pedido do dossiê) – APROVADO; cabos X1→L1 1×240 mm² espaçados (269 A × 1,05 × 1,25 = 353 A ≤ 375 A).
**Pendente:** confirmar com o engenheiro se algum projeto usa cabos encostados (marcar no pedido).

## v1.28.1 – 25/11/2026 – banco: borne da contatora e arco nos terminais de entrada
**Pedido:** "Vc não consegue corrigir esses problemas?" (os 2 REPROVADOS da Panatlântica na v1.28.0).
**Feito (regra geral):** REQ-BCO-006: a contatora sobe sozinha até uma cujo borne de catálogo aceite o cabo NBR 5410. Bornes ABB conferidos nas folhas de dados de 25/11. REQ-SEG-015: o lado de linha do -Q0 passa a ser tratado como energia do alimentador do cliente: tampa e IPXXB na lista, medida no estudo, ATENÇÃO até 40 cal/cm², tempo real da proteção lido do pedido ou pedido como lacuna.
**Teste:** Panatlântica ABB (t1281_ABB): passou de NÃO LIBERAR (2 reprovados) para SEM REPROVAÇÕES, 25 em ATENÇÃO. Estágios de 50 kvar com AF116-30-00-13 e 70 mm²; terminais de entrada 19,8 cal/cm² em ATENÇÃO (500 ms adotado). Verificador: 0 regressões → pode publicar.
**Pendente para o engenheiro:** pedir à Panatlântica o tempo da proteção a montante; decidir se prefere 2 × 35 mm² por fase na AF52 em vez da AF116 (custo/espaço).

## Análise inicial – 2026-11-22 (criação da gestão de requisitos)
- Causa raiz apontada pelo engenheiro: instruções, exemplos e referências (AGCO, CVI, Pirelli, Panatlântica, Google Fotos, campo)
  ficavam só na conversa; com conversas longas o detalhe se perdia e não era aplicado (ex.: desenho do painel abaixo do padrão
  SolidWorks AGCO, reator maior que o Cootrans instalado na Panatlântica).
- Correção: registro único de requisitos (67 itens na criação, recuperados da conversa e do histórico CHANGELOG v1.0–v1.24),
  catálogo de referências com lições, verificador automático com Check e bloqueio de publicação, e CLAUDE.md obrigando
  qualquer sessão a ler e atualizar o registro.
- Limitação honesta: o histórico literal das conversas de 19–21/11 não está mais disponível nesta sessão (foi resumido);
  os requisitos desse período foram recuperados do CHANGELOG (que registrava cada pedido/aviso). O engenheiro deve conferir
  a planilha e apontar o que faltar – cada item apontado entra como REQ novo.
- Pendentes críticos na criação: REQ-REA-002 (reator × Cootrans real), REQ-PNL-001 (acabamento padrão SolidWorks),
  REQ-GER-003 (painel 3D no senoidal).





## Revisão – v1.24.1 – 2026-11-22 16:02
- Requisitos: 67 | APROVADO 54 | ATENÇÃO 6 | REPROVADO 7
- Projetos conferidos: BCD-FD8,16-400kvar-415V_Schneider_20261122_1600
- Mudanças: nenhuma
- Críticos que diziam ATENDIDO e falharam (bloqueiam): nenhum | regredidos: nenhum
- Críticos pendentes conhecidos (prioridade): REQ-GER-003, REQ-REA-002, REQ-PNL-002, REQ-REF-001
- Decisão: pode publicar
- Análise v1.24.1: projeto completo gerado com o código novo – painel 3D com 6 folhas e todos os requisitos marcados como
  atendidos passaram. Pendentes críticos (prioridade): REQ-REA-002 (reator × Cootrans – causa achada), REQ-GER-003 (painel 3D
  no senoidal), REQ-PNL-002 (3 componentes sem medida de catálogo), REQ-REF-001 (PLASBIL, Panatlântica histórico, ALCAST e
  Google Fotos ainda não usados). Aguardando o engenheiro aprovar as folhas do painel.

## Revisão – v1.24.2 – 2026-11-22 16:23
- Requisitos: 76 | APROVADO 56 | ATENÇÃO 11 | REPROVADO 9
- Projetos conferidos: BCD-FD8,16-400kvar-415V_Schneider_20261122_1621
- Mudanças: nenhuma
- Críticos que diziam ATENDIDO e falharam (bloqueiam): nenhum | regredidos: nenhum
- Críticos pendentes conhecidos (prioridade): REQ-GER-003, REQ-REA-002, REQ-PNL-002, REQ-REF-001, REQ-SEG-007
- Decisão: pode publicar
- Análise v1.24.2: projeto completo da Panatlântica gerado com o arranjo novo – nenhuma verificação de montagem reprovada,
  consolidado sem "NÃO INCLUÍDO". Pendentes críticos: REA-002 (reator), GER-003 (3D no senoidal), PNL-002 (3 medidas),
  REF-001 (referências não usadas), SEG-007 (energia incidente – em desenvolvimento, módulo IEEE 1584 da Plataforma de Estudos
  identificado em GeradorProtecao/terceiros/arcflash, licença MIT).

## Revisão – v1.24.3 – 2026-11-22 16:57
- Requisitos: 91 | APROVADO 57 | ATENÇÃO 16 | REPROVADO 18
- Projetos conferidos: BCD-FD8,16-400kvar-415V_Schneider_20261122_1652
- Mudanças: REQ-REA-002 MELHOROU (REPROVADO→ATENÇÃO)
- Críticos que diziam ATENDIDO e falharam (bloqueiam): nenhum | regredidos: nenhum
- Críticos pendentes conhecidos (prioridade): REQ-GER-003, REQ-PNL-002, REQ-REF-001, REQ-SEG-007, REQ-PNL-015, REQ-SEG-009, REQ-PNL-016, REQ-PNL-017, REQ-PNL-018, REQ-SEG-010, REQ-SEG-011, REQ-SEG-012, REQ-PNL-020, REQ-PNL-021
- Decisão: pode publicar
- Análise v1.24.3: rodada completa da Panatlântica (191 páginas no consolidado, todos os arquivos incluídos). Segurança: DJ geral,
  barra única, NR-10 2026 e energia incidente atendidos; cabos e trafo de comando calculados. Próximo bloco (REQ-PNL-021/022,
  REQ-GER-010): banco de componentes completo por marca (ABB/Schneider/padrão Panatlântica) até parafuso, terminal e torque,
  e modelos 3D reais dos fabricantes.

## Revisão – v1.24.3 – 2026-11-22 16:58
- Requisitos: 91 | APROVADO 60 | ATENÇÃO 20 | REPROVADO 11
- Projetos conferidos: BCD-FD8,16-400kvar-415V_Schneider_20261122_1652
- Mudanças: REQ-SEG-007 MELHOROU (REPROVADO→APROVADO); REQ-SEG-009 MELHOROU (REPROVADO→ATENÇÃO); REQ-PNL-017 MELHOROU (REPROVADO→ATENÇÃO); REQ-PNL-018 MELHOROU (REPROVADO→APROVADO); REQ-SEG-010 MELHOROU (REPROVADO→APROVADO); REQ-SEG-012 MELHOROU (REPROVADO→ATENÇÃO); REQ-PNL-020 MELHOROU (REPROVADO→ATENÇÃO)
- Críticos que diziam ATENDIDO e falharam (bloqueiam): nenhum | regredidos: nenhum
- Críticos pendentes conhecidos (prioridade): REQ-GER-003, REQ-PNL-002, REQ-REF-001, REQ-PNL-015, REQ-PNL-016, REQ-SEG-011, REQ-PNL-021
- Decisão: pode publicar

## Revisão – v1.25.0 – 2026-11-22 17:31
- Requisitos: 95 | APROVADO 60 | ATENÇÃO 22 | REPROVADO 13
- Projetos conferidos: BCD-FD8,16-400kvar-415V_Schneider_20261122_1727
- Mudanças: nenhuma
- Críticos que diziam ATENDIDO e falharam (bloqueiam): nenhum | regredidos: nenhum
- Críticos pendentes conhecidos (prioridade): REQ-GER-003, REQ-PNL-002, REQ-REF-001, REQ-PNL-015, REQ-PNL-016, REQ-SEG-011, REQ-PNL-021, REQ-PNL-023
- Decisão: pode publicar

## Revisão – v1.25.1 – 2026-11-22 18:04
- Requisitos: 99 | APROVADO 64 | ATENÇÃO 22 | REPROVADO 13
- Projetos conferidos: BCD-FD8,16-400kvar-415V_Schneider_20261122_1800, BCD-FD8,16-400kvar-415V_ABB_20261122_1800
- Mudanças: nenhuma
- Críticos que diziam ATENDIDO e falharam (bloqueiam): nenhum | regredidos: nenhum
- Críticos pendentes conhecidos (prioridade): REQ-GER-003, REQ-PNL-002, REQ-REF-001, REQ-PNL-015, REQ-PNL-016, REQ-SEG-011, REQ-PNL-021, REQ-PNL-023
- Decisão: pode publicar

## Revisão – v1.25.1 – 2026-11-22 18:07
- Requisitos: 99 | APROVADO 64 | ATENÇÃO 22 | REPROVADO 13
- Projetos conferidos: BCD-FD8,16-400kvar-415V_Schneider_20261122_1804, BCD-FD8,16-400kvar-415V_ABB_20261122_1804
- Mudanças: nenhuma
- Críticos que diziam ATENDIDO e falharam (bloqueiam): nenhum | regredidos: nenhum
- Críticos pendentes conhecidos (prioridade): REQ-GER-003, REQ-PNL-002, REQ-REF-001, REQ-PNL-015, REQ-PNL-016, REQ-SEG-011, REQ-PNL-021, REQ-PNL-023
- Decisão: pode publicar

## Revisão – v1.25.2 – 2026-11-22 19:48
- Requisitos: 108 | APROVADO 70 | ATENÇÃO 24 | REPROVADO 14
- Projetos conferidos: BCD-FD8,16-400kvar-415V_Schneider_20261122_1939, BCD-FD8,16-400kvar-415V_ABB_20261122_1939
- Mudanças: nenhuma
- Críticos que diziam ATENDIDO e falharam (bloqueiam): nenhum | regredidos: nenhum
- Críticos pendentes conhecidos (prioridade): REQ-GER-003, REQ-PNL-002, REQ-REF-001, REQ-PNL-015, REQ-PNL-016, REQ-SEG-011, REQ-PNL-021, REQ-PNL-023
- Decisão: pode publicar

## Revisão – v1.25.3 – 2026-11-22 20:19
- Requisitos: 110 | APROVADO 70 | ATENÇÃO 24 | REPROVADO 16
- Projetos conferidos: BCD-FD8,16-400kvar-415V_Schneider_20261122_2010, BCD-FD8,16-400kvar-415V_ABB_20261122_2010
- Mudanças: nenhuma
- Críticos que diziam ATENDIDO e falharam (bloqueiam): nenhum | regredidos: nenhum
- Críticos pendentes conhecidos (prioridade): REQ-GER-003, REQ-PNL-002, REQ-REF-001, REQ-CMP-004, REQ-CMP-005, REQ-PNL-015, REQ-PNL-016, REQ-SEG-011, REQ-PNL-021, REQ-PNL-023
- Decisão: pode publicar

## Revisão – v1.25.3 – 2026-11-22 20:20
- Requisitos: 110 | APROVADO 71 | ATENÇÃO 25 | REPROVADO 14
- Projetos conferidos: BCD-FD8,16-400kvar-415V_Schneider_20261122_2010, BCD-FD8,16-400kvar-415V_ABB_20261122_2010
- Mudanças: REQ-CMP-004 MELHOROU (REPROVADO→APROVADO); REQ-CMP-005 MELHOROU (REPROVADO→ATENÇÃO)
- Críticos que diziam ATENDIDO e falharam (bloqueiam): nenhum | regredidos: nenhum
- Críticos pendentes conhecidos (prioridade): REQ-GER-003, REQ-PNL-002, REQ-REF-001, REQ-PNL-015, REQ-PNL-016, REQ-SEG-011, REQ-PNL-021, REQ-PNL-023
- Decisão: pode publicar

## Revisão – v1.26.0 – 2026-11-22 21:25
- Requisitos: 115 | APROVADO 75 | ATENÇÃO 26 | REPROVADO 14
- Projetos conferidos: BCD-FD8,16-400kvar-415V_Schneider_20261122_2116, BCD-FD8,16-400kvar-415V_ABB_20261122_2116
- Mudanças: nenhuma
- Críticos que diziam ATENDIDO e falharam (bloqueiam): nenhum | regredidos: nenhum
- Críticos pendentes conhecidos (prioridade): REQ-GER-003, REQ-PNL-002, REQ-REF-001, REQ-PNL-015, REQ-PNL-016, REQ-SEG-011, REQ-PNL-021, REQ-PNL-023
- Decisão: pode publicar

## Revisão – v1.26.0 – 2026-11-22 23:00
- Requisitos: 126 | APROVADO 78 | ATENÇÃO 29 | REPROVADO 19
- Projetos conferidos: BCD-FD8,16-400kvar-415V_Schneider_20261122_2251
- Mudanças: nenhuma
- Críticos que diziam ATENDIDO e falharam (bloqueiam): nenhum | regredidos: nenhum
- Críticos pendentes conhecidos (prioridade): REQ-GER-003, REQ-PNL-002, REQ-REF-001, REQ-REA-012, REQ-REA-013, REQ-REA-014, REQ-PNL-015, REQ-PNL-016, REQ-SEG-011, REQ-PNL-021, REQ-PNL-023
- Decisão: pode publicar

## Revisão – v1.26.0 – 2026-11-22 23:44
- Requisitos: 127 | APROVADO 78 | ATENÇÃO 31 | REPROVADO 18
- Projetos conferidos: BCD-FD8,16-400kvar-415V_Schneider_20261122_2335
- Mudanças: REQ-REA-013 MELHOROU (REPROVADO→ATENÇÃO)
- Críticos que diziam ATENDIDO e falharam (bloqueiam): nenhum | regredidos: nenhum
- Críticos pendentes conhecidos (prioridade): REQ-GER-003, REQ-PNL-002, REQ-REF-001, REQ-REA-012, REQ-REA-014, REQ-PNL-015, REQ-PNL-016, REQ-SEG-011, REQ-PNL-021, REQ-PNL-023
- Decisão: pode publicar

## Revisão – v1.26.1 – 2026-11-22 23:45
- Requisitos: 127 | APROVADO 78 | ATENÇÃO 31 | REPROVADO 18
- Projetos conferidos: BCD-FD8,16-400kvar-415V_Schneider_20261122_2335
- Mudanças: nenhuma
- Críticos que diziam ATENDIDO e falharam (bloqueiam): nenhum | regredidos: nenhum
- Críticos pendentes conhecidos (prioridade): REQ-GER-003, REQ-PNL-002, REQ-REF-001, REQ-REA-012, REQ-REA-014, REQ-PNL-015, REQ-PNL-016, REQ-SEG-011, REQ-PNL-021, REQ-PNL-023
- Decisão: pode publicar

## Revisão – v1.26.1 – 2026-11-23 00:44
- Requisitos: 128 | APROVADO 78 | ATENÇÃO 32 | REPROVADO 18
- Projetos conferidos: BCD-FD8,16-400kvar-415V_Schneider_20261123_0035
- Mudanças: nenhuma
- Críticos que diziam ATENDIDO e falharam (bloqueiam): nenhum | regredidos: nenhum
- Críticos pendentes conhecidos (prioridade): REQ-GER-003, REQ-PNL-002, REQ-REF-001, REQ-REA-012, REQ-REA-014, REQ-PNL-015, REQ-PNL-016, REQ-SEG-011, REQ-PNL-021, REQ-PNL-023
- Decisão: pode publicar

## Revisão – v1.26.2 – 2026-11-23 00:44
- Requisitos: 128 | APROVADO 79 | ATENÇÃO 31 | REPROVADO 18
- Projetos conferidos: BCD-FD8,16-400kvar-415V_Schneider_20261123_0035
- Mudanças: REQ-REL-009 MELHOROU (ATENÇÃO→APROVADO)
- Críticos que diziam ATENDIDO e falharam (bloqueiam): nenhum | regredidos: nenhum
- Críticos pendentes conhecidos (prioridade): REQ-GER-003, REQ-PNL-002, REQ-REF-001, REQ-REA-012, REQ-REA-014, REQ-PNL-015, REQ-PNL-016, REQ-SEG-011, REQ-PNL-021, REQ-PNL-023
- Decisão: pode publicar

## Revisão – v1.26.2 – 2026-11-23 07:08
- Requisitos: 130 | APROVADO 80 | ATENÇÃO 33 | REPROVADO 17
- Projetos conferidos: BCD-FD8,16-400kvar-415V_Schneider_20261123_0701
- Mudanças: REQ-REA-012 MELHOROU (REPROVADO→ATENÇÃO); REQ-REA-014 MELHOROU (REPROVADO→ATENÇÃO)
- Críticos que diziam ATENDIDO e falharam (bloqueiam): nenhum | regredidos: nenhum
- Críticos pendentes conhecidos (prioridade): REQ-GER-003, REQ-PNL-002, REQ-REF-001, REQ-PNL-015, REQ-PNL-016, REQ-SEG-011, REQ-PNL-021, REQ-PNL-023
- Decisão: pode publicar

## Revisão – v1.26.3 – 2026-11-23 07:08
- Requisitos: 130 | APROVADO 80 | ATENÇÃO 33 | REPROVADO 17
- Projetos conferidos: BCD-FD8,16-400kvar-415V_Schneider_20261123_0701
- Mudanças: nenhuma
- Críticos que diziam ATENDIDO e falharam (bloqueiam): nenhum | regredidos: nenhum
- Críticos pendentes conhecidos (prioridade): REQ-GER-003, REQ-PNL-002, REQ-REF-001, REQ-PNL-015, REQ-PNL-016, REQ-SEG-011, REQ-PNL-021, REQ-PNL-023
- Decisão: pode publicar

## Revisão – v1.26.3 – 2026-11-23 07:08
- Requisitos: 130 | APROVADO 78 | ATENÇÃO 32 | REPROVADO 20
- Projetos conferidos: BCD-FD8,16-400kvar-415V_ABB_20261123_0635
- Mudanças: REQ-BCO-004 REGREDIU (ATENÇÃO→REPROVADO); REQ-GER-011 REGREDIU (APROVADO→REPROVADO); REQ-PNL-028 REGREDIU (APROVADO→REPROVADO)
- Críticos que diziam ATENDIDO e falharam (bloqueiam): REQ-GER-011, REQ-PNL-028 | regredidos: REQ-BCO-004, REQ-GER-011, REQ-PNL-028
- Críticos pendentes conhecidos (prioridade): REQ-GER-003, REQ-PNL-002, REQ-REF-001, REQ-BCO-004, REQ-PNL-015, REQ-PNL-016, REQ-SEG-011, REQ-PNL-021, REQ-PNL-023
- Decisão: NÃO PUBLICAR

## Revisão – v1.26.3 – 2026-11-23 07:08
- Requisitos: 130 | APROVADO 80 | ATENÇÃO 33 | REPROVADO 17
- Projetos conferidos: BCD-FD8,16-400kvar-415V_Schneider_20261123_0701
- Mudanças: REQ-BCO-004 MELHOROU (REPROVADO→ATENÇÃO); REQ-GER-011 MELHOROU (REPROVADO→APROVADO); REQ-PNL-028 MELHOROU (REPROVADO→APROVADO)
- Críticos que diziam ATENDIDO e falharam (bloqueiam): nenhum | regredidos: nenhum
- Críticos pendentes conhecidos (prioridade): REQ-GER-003, REQ-PNL-002, REQ-REF-001, REQ-PNL-015, REQ-PNL-016, REQ-SEG-011, REQ-PNL-021, REQ-PNL-023
- Decisão: pode publicar

## Revisão – v1.26.3 – 2026-11-23 07:18
- Requisitos: 130 | APROVADO 80 | ATENÇÃO 33 | REPROVADO 17
- Projetos conferidos: BCD-FD8,16-400kvar-415V_ABB_20261123_0709
- Mudanças: nenhuma
- Críticos que diziam ATENDIDO e falharam (bloqueiam): nenhum | regredidos: nenhum
- Críticos pendentes conhecidos (prioridade): REQ-GER-003, REQ-PNL-002, REQ-REF-001, REQ-PNL-015, REQ-PNL-016, REQ-SEG-011, REQ-PNL-021, REQ-PNL-023
- Decisão: pode publicar

## Revisão – v1.26.4 – 2026-11-23 10:25
- Requisitos: 137 | APROVADO 84 | ATENÇÃO 34 | REPROVADO 19
- Projetos conferidos: BCD-FD8,16-400kvar-415V_ABB_20261123_1007
- Mudanças: nenhuma
- Críticos que diziam ATENDIDO e falharam (bloqueiam): nenhum | regredidos: nenhum
- Críticos pendentes conhecidos (prioridade): REQ-GER-003, REQ-PNL-002, REQ-REF-001, REQ-PNL-015, REQ-PNL-016, REQ-SEG-011, REQ-PNL-021, REQ-PNL-023
- Decisão: pode publicar

## Revisão – v1.26.4 – 2026-11-23 10:32
- Requisitos: 138 | APROVADO 79 | ATENÇÃO 30 | REPROVADO 29
- Projetos conferidos: BCD-FD8,16-400kvar-415V_ABB_20261123_1007, 2026-11-23_FSEN-LC-269A-440V
- Mudanças: REQ-PNL-001 REGREDIU (ATENÇÃO→REPROVADO); REQ-PNL-003 REGREDIU (APROVADO→REPROVADO); REQ-PNL-004 REGREDIU (APROVADO→REPROVADO); REQ-PNL-005 REGREDIU (APROVADO→REPROVADO); REQ-BCO-004 REGREDIU (ATENÇÃO→REPROVADO); REQ-PNL-012 REGREDIU (ATENÇÃO→REPROVADO); REQ-PNL-013 REGREDIU (ATENÇÃO→REPROVADO); REQ-GER-011 REGREDIU (APROVADO→REPROVADO); REQ-PNL-028 REGREDIU (APROVADO→REPROVADO)
- Críticos que diziam ATENDIDO e falharam (bloqueiam): REQ-PNL-003, REQ-PNL-004, REQ-PNL-005, REQ-GER-011, REQ-PNL-028 | regredidos: REQ-PNL-001, REQ-PNL-003, REQ-PNL-004, REQ-PNL-005, REQ-BCO-004, REQ-PNL-012, REQ-PNL-013, REQ-GER-011, REQ-PNL-028
- Críticos pendentes conhecidos (prioridade): REQ-GER-003, REQ-PNL-001, REQ-PNL-002, REQ-REF-001, REQ-BCO-004, REQ-PNL-012, REQ-PNL-013, REQ-PNL-015, REQ-PNL-016, REQ-SEG-011, REQ-PNL-021, REQ-PNL-023
- Decisão: NÃO PUBLICAR

## Revisão – v1.26.4 – 2026-11-23 10:33
- Requisitos: 138 | APROVADO 84 | ATENÇÃO 34 | REPROVADO 20
- Projetos conferidos: BCD-FD8,16-400kvar-415V_ABB_20261123_1007
- Mudanças: nenhuma
- Críticos que diziam ATENDIDO e falharam (bloqueiam): nenhum | regredidos: nenhum
- Críticos pendentes conhecidos (prioridade): REQ-GER-003, REQ-PNL-002, REQ-REF-001, REQ-PNL-015, REQ-PNL-016, REQ-SEG-011, REQ-PNL-021, REQ-PNL-023
- Decisão: pode publicar

### Análise da revisão v1.26.4 (23/11/2026) – correções da auditoria independente (DeepSeek, lote 2)
- Verificador: com o projeto de teste do BANCO (BCD-FD8,16-400kvar-415V_ABB_20261123_1007) → "pode publicar", nenhum crítico regredido.
- A linha "NÃO PUBLICAR" das 10:32 acima NÃO vale como bloqueio: nela foi passado também o projeto do filtro SENOIDAL (A&W), e os testes
  automáticos do verificador são específicos de banco (folha de normas do banco, painel, "Plataforma = ATP n/n") – num projeto senoidal eles
  reprovam por construção. Pendência registrada: o verificador precisa de testes próprios para o filtro senoidal.
- Banco Panatlântica (teste): térmica do reator de 50 kvar 164 °C → refeito sozinho → 132 °C (folga 23 K); status geral "NÃO LIBERAR" com 2
  reprovados reais (borne da contatora AF52 × cabo 70 mm²; arco elétrico 19,79 cal/cm² nos terminais de entrada com a premissa de 500 ms).
- A&W (teste): Status REPROVADO – ponto quente do indutor 165,9 °C no painel (com as perdas no limite contratual e o ar no topo do indutor)
  contra 155 °C da classe F pedida; pelo pior método do indutor isolado 153–154 °C (folga 1–2 K). Sem solução com 10 K de folga com barra
  única nem com paralelos. Antes saía APROVADO. Decisão do engenheiro pendente: classe H com o cliente, indutor maior ou outra construção.
- Em aberto: os modelos térmicos do indutor divergem (projeto 89 °C × avançado 153 °C na A&W; 120 × 132 °C no reator de 50 kvar) – calibrar
  com termografia/ensaio; composição da corrente de projeto do reator (espectro do local × k) e folga de 10 K a confirmar com o engenheiro.

## Revisão – v1.27.0 – 2026-11-23 10:54
- Requisitos: 138 | APROVADO 84 | ATENÇÃO 35 | REPROVADO 19
- Projetos conferidos: BCD-FD8,16-400kvar-415V_ABB_20261123_1039
- Mudanças: REQ-GER-016 MELHOROU (REPROVADO→ATENÇÃO)
- Críticos que diziam ATENDIDO e falharam (bloqueiam): nenhum | regredidos: nenhum
- Críticos pendentes conhecidos (prioridade): REQ-GER-003, REQ-PNL-002, REQ-REF-001, REQ-PNL-015, REQ-PNL-016, REQ-SEG-011, REQ-PNL-021, REQ-PNL-023
- Decisão: pode publicar

### Análise da revisão v1.27.0 (23/11/2026) – nível de maturidade dos projetos (REQ-GER-016)
- Verificador com o projeto de teste do banco (BCD-FD8,16-400kvar-415V_ABB_20261123_1039): "pode publicar", nenhum crítico regredido.
- O teste saiu no nível 1 (2 reprovados reais: borne da contatora × cabo, arco elétrico) – comportamento esperado; pasta 06_Evidencias,
  maturidade.json e bloco no RESUMO gerados. A tela da Biblioteca (lista + perguntas) só foi conferida por sintaxe aqui – testar no notebook.

## Revisão – v1.27.1 – 2026-11-23 14:05
- Requisitos: 139 | APROVADO 85 | ATENÇÃO 35 | REPROVADO 19
- Projetos conferidos: BCD-FD8,16-400kvar-415V_ABB_20261123_1039
- Mudanças: nenhuma
- Críticos que diziam ATENDIDO e falharam (bloqueiam): nenhum | regredidos: nenhum
- Críticos pendentes conhecidos (prioridade): REQ-GER-003, REQ-PNL-002, REQ-REF-001, REQ-PNL-015, REQ-PNL-016, REQ-SEG-011, REQ-PNL-021, REQ-PNL-023
- Decisão: pode publicar

### Análise da revisão v1.27.1 (23/11/2026) – filtro senoidal sempre em classe H (REQ-SEN-021)
- Verificador com o projeto do banco: "pode publicar". Teste da A&W na nuvem (sem ATP): Status APROVADO; o 1º indutor deu 178 °C pelo pior
  método (limite 180 °C), a plataforma refez e fechou em 124 °C; no painel 131 °C. Painel 258 kg, 863 W, 1 ventilador; maturidade nível 2.
- Testes no notebook pela v1.27.0 (antes desta mudança): A&W REPROVADO pela classe F (165,9 °C); Panatlântica NÃO LIBERAR (borne AF52 × cabo, arco).

## Revisão – v1.28.0 – 2026-11-25 20:43
- Requisitos: 141 | APROVADO 80 | ATENÇÃO 42 | REPROVADO 19
- Projetos conferidos: nenhum
- Mudanças: REQ-PUB-002 REGREDIU (APROVADO→ATENÇÃO); REQ-REL-001 REGREDIU (APROVADO→ATENÇÃO); REQ-REL-002 REGREDIU (APROVADO→ATENÇÃO); REQ-REL-005 REGREDIU (APROVADO→ATENÇÃO); REQ-SIM-001 REGREDIU (APROVADO→ATENÇÃO); REQ-GER-011 REGREDIU (APROVADO→ATENÇÃO); REQ-PNL-028 REGREDIU (APROVADO→ATENÇÃO)
- Críticos que diziam ATENDIDO e falharam (bloqueiam): nenhum | regredidos: REQ-PUB-002, REQ-REL-001, REQ-REL-002, REQ-REL-005, REQ-SIM-001, REQ-GER-011, REQ-PNL-028
- Críticos pendentes conhecidos (prioridade): REQ-GER-003, REQ-PNL-002, REQ-REF-001, REQ-PNL-015, REQ-PNL-016, REQ-SEG-011, REQ-PNL-021, REQ-PNL-023
- Decisão: NÃO PUBLICAR

## Revisão – v1.28.0 – 2026-11-25 20:44
- Requisitos: 141 | APROVADO 87 | ATENÇÃO 35 | REPROVADO 19
- Projetos conferidos: BCD-FD8,16-400kvar-415V_ABB_20261125_2029
- Mudanças: REQ-PUB-002 MELHOROU (ATENÇÃO→APROVADO); REQ-REL-001 MELHOROU (ATENÇÃO→APROVADO); REQ-REL-002 MELHOROU (ATENÇÃO→APROVADO); REQ-REL-005 MELHOROU (ATENÇÃO→APROVADO); REQ-SIM-001 MELHOROU (ATENÇÃO→APROVADO); REQ-GER-011 MELHOROU (ATENÇÃO→APROVADO); REQ-PNL-028 MELHOROU (ATENÇÃO→APROVADO)
- Críticos que diziam ATENDIDO e falharam (bloqueiam): nenhum | regredidos: nenhum
- Críticos pendentes conhecidos (prioridade): REQ-GER-003, REQ-PNL-002, REQ-REF-001, REQ-PNL-015, REQ-PNL-016, REQ-SEG-011, REQ-PNL-021, REQ-PNL-023
- Decisão: pode publicar

### Análise da revisão v1.28.0 (25/11/2026) – filtro senoidal: correções gerais da auditoria do A&W (REQ-SEN-022) e cotação (REQ-SEN-023)
- Verificador com o projeto de teste do banco (BCD-FD8,16-400kvar-415V_ABB_20261125_2029): "pode publicar", nenhum crítico regredido.
  (A primeira execução, logo depois de o projeto terminar, mostrou 7 itens em ATENÇÃO porque os arquivos ainda estavam sendo
  gravados; repetida com a pasta completa, todos APROVADOS.) Com projeto senoidal o verificador continua reprovando os testes de
  painel de banco – pendência conhecida: testes próprios para o filtro senoidal.
- A&W com o pedido do dossiê auditado (cabo não blindado), na nuvem: Status APROVADO, 150 µH, 6 × 30 µF; 1º indutor 192 °C pela regra
  nova (média + 15 K) → refeito → 124 °C; NGSolve 3D 142,9/140,1/145,4 µH → entreferro ajustado (central 7,31 mm/peça) → previsto
  149,0/150,3/151,6 µH, desequilíbrio 3,7 → 1,7 %; THD com metade do amortecimento 9,35 % (ATENÇÃO, ressonância carregada ≈ 1,13 kHz).
- E-mails de cotação com a lista do que a proposta deve trazer e as planilhas de resposta (indutor e capacitor) conferidos no teste.

## Revisão – v1.28.1 – 2026-11-25 21:09
- Requisitos: 143 | APROVADO 87 | ATENÇÃO 37 | REPROVADO 19
- Projetos conferidos: BCD-FD8,16-400kvar-415V_ABB_20261125_2056
- Mudanças: nenhuma
- Críticos que diziam ATENDIDO e falharam (bloqueiam): nenhum | regredidos: nenhum
- Críticos pendentes conhecidos (prioridade): REQ-GER-003, REQ-PNL-002, REQ-REF-001, REQ-PNL-015, REQ-PNL-016, REQ-SEG-011, REQ-PNL-021, REQ-PNL-023
- Decisão: pode publicar

## Revisão – v1.29.0 – 2026-11-25 22:16
- Requisitos: 147 | APROVADO 91 | ATENÇÃO 37 | REPROVADO 19
- Projetos conferidos: BCD-FD8,16-400kvar-415V_ABB_20261125_2155
- Mudanças: REQ-PNL-032 MELHOROU (REPROVADO→APROVADO)
- Críticos que diziam ATENDIDO e falharam (bloqueiam): nenhum | regredidos: nenhum
- Críticos pendentes conhecidos (prioridade): REQ-GER-003, REQ-PNL-002, REQ-REF-001, REQ-PNL-015, REQ-PNL-016, REQ-SEG-011, REQ-PNL-021, REQ-PNL-023
- Decisão: pode publicar

## Revisão – v1.30.0 – 2026-11-26 00:08
- Requisitos: 149 | APROVADO 91 | ATENÇÃO 38 | REPROVADO 20
- Projetos conferidos: BCD-FD8,16-400kvar-415V_ABB_20261125_2155
- Mudanças: REQ-PNL-032 MELHOROU (REPROVADO→APROVADO)
- Críticos que diziam ATENDIDO e falharam (bloqueiam): nenhum | regredidos: nenhum
- Críticos pendentes conhecidos (prioridade): REQ-GER-003, REQ-PNL-002, REQ-REF-001, REQ-PNL-015, REQ-PNL-016, REQ-SEG-011, REQ-PNL-021, REQ-PNL-023
- Decisão: pode publicar

## Revisão – v1.31.0 – 2026-11-26 10:34
- Requisitos: 150 | APROVADO 91 | ATENÇÃO 38 | REPROVADO 21
- Projetos conferidos: BCD-FD8,16-400kvar-415V_ABB_20261126_0949
- Mudanças: REQ-PNL-032 MELHOROU (REPROVADO→APROVADO)
- Críticos que diziam ATENDIDO e falharam (bloqueiam): nenhum | regredidos: nenhum
- Críticos pendentes conhecidos (prioridade): REQ-GER-003, REQ-PNL-002, REQ-REF-001, REQ-PNL-015, REQ-PNL-016, REQ-SEG-011, REQ-PNL-021, REQ-PNL-023
- Decisão: pode publicar

## Revisão – v1.31.1 – 2026-11-26 10:50
- Requisitos: 151 | APROVADO 93 | ATENÇÃO 38 | REPROVADO 20
- Projetos conferidos: BCD-FD8,16-400kvar-415V_ABB_20261126_0949
- Mudanças: REQ-PNL-032 MELHOROU (REPROVADO→APROVADO); REQ-DOC-020 MELHOROU (REPROVADO→APROVADO)
- Críticos que diziam ATENDIDO e falharam (bloqueiam): nenhum | regredidos: nenhum
- Críticos pendentes conhecidos (prioridade): REQ-GER-003, REQ-PNL-002, REQ-REF-001, REQ-PNL-015, REQ-PNL-016, REQ-SEG-011, REQ-PNL-021, REQ-PNL-023
- Decisão: pode publicar
