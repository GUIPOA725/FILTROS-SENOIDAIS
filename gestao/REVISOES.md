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




## Revisão – v1.24.1 – 2026-11-22 15:59
- Requisitos: 67 | APROVADO 51 | ATENÇÃO 5 | REPROVADO 11
- Projetos conferidos: fogo, BCD-FD8,16-400kvar-415V_Schneider_20261122_1530
- Mudanças: nenhuma
- Críticos que diziam ATENDIDO e falharam (bloqueiam): REQ-PNL-003, REQ-PNL-004, REQ-PNL-005 | regredidos: nenhum
- Críticos pendentes conhecidos (prioridade): REQ-GER-003, REQ-REA-002, REQ-PNL-001, REQ-PNL-002, REQ-REF-001
- Decisão: NÃO PUBLICAR
