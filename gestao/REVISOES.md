# Revisões e análise – Plataforma FSEN

Registro de cada versão contra o REGISTRO DE REQUISITOS do engenheiro (gestao/REQUISITOS.yaml).
As linhas "Revisão – vX" são geradas por `python gestao/verificar_requisitos.py <projetos>`; a análise é escrita à mão abaixo de cada uma.

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
