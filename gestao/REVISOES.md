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
