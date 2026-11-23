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
