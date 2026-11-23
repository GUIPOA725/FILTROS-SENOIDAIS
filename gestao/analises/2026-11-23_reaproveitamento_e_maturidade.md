# Reaproveitar projetos antigos e níveis de maturidade – pesquisa e decisão (23/11/2026)

Pedido do engenheiro (voz, 23/11): pesquisar como as empresas de engenharia reaproveitam projetos antigos nos novos, analisar se com
a IA vale reaproveitar tudo ou só o mínimo, e criar um nível de pontuação (salvo → calculado → vendido → TAF → campo) que funcione
sozinho ("eu posso esquecer"). Combinado: se a pesquisa convergir com a proposta, aplicar e gerar versão.

## O que foi consultado nesta sessão (texto)
1. **Revisão sistemática – reuso de projeto em engenharia sob encomenda (ETO)**, Universidade de Tampere:
   https://researchportal.tuni.fi/en/publications/supporting-design-reuse-in-engineer-to-order-context-a-systematic/
   – o problema descrito é o mesmo: cada entrega começa do zero e falta reuso na cotação e na engenharia; o remédio apontado é
   modularização/plataforma (passar de produto projetado individualmente para reuso de módulos). A revisão NÃO achou um método pronto.
2. **Estados de ciclo de vida de peças em PLM (PTC Windchill, relatos de empresas)**:
   https://community.ptc.com/windchill-10/life-cycle-state-business-definitions-101056
   – as empresas usam estados de maturidade da peça: conceito/projeto → protótipo → pré-série → série/liberado → fora de linha
   (obsoleto ativo/inativo). "Protótipo" é citado como a maturidade mínima para gastar dinheiro em fabricação.
3. **Escala TRL (NASA)** – a página oficial não abriu nesta sessão; o que uso dela vem do conhecimento geral: 9 níveis, e o topo só
   é atingido com operação real comprovada. NÃO conferido na fonte hoje.
4. As citações da EPLAN e da Rittal feitas na conversa por voz NÃO foram reconferidas aqui – não entram como base.

## Converge com o que foi combinado?
Sim, nos três pontos que importam:
- reaproveitar **módulos validados**, não o projeto antigo inteiro copiado (a literatura de ETO aponta modularização);
- **maturidade em degraus**, com estado de "não usar em projeto novo" (prática de PLM);
- o degrau mais alto só com **prova do mundo real** (PLM: série; TRL: operação).
Limite da pesquisa: 2 fontes lidas de fato; é suficiente para a direção, não é um levantamento completo.

## Análise – vale reaproveitar tudo, com a IA?
- Recalcular ficou barato (um banco completo roda em ~10–20 min). O que continua caro é **validar** (ensaio, TAF, campo) e **decidir**.
- Copiar o projeto antigo traz os erros dele junto (a auditoria de 23/11 mostrou projetos "APROVADOS" com reprovação interna).
- Portanto: reaproveitar só o que custou validação – reator/módulo de estágio com nível alto, componente conferido, preço cotado,
  lição de campo – e **recalcular sempre** o que depende da rede do cliente (harmônicas, ressonância, curto, arco, disjuntor geral,
  transitórios), além de reconferir o módulo contra as correntes do local.

## O que foi aplicado na v1.27.0
- `fsen/maturidade.py`: níveis 0–5; 1 e 2 automáticos ao rodar; 3–5 por evidência em `06_Evidencias` (3_Vendido_Fabricado, 4_TAF,
  5_Campo); bloco no RESUMO; `maturidade.json` na pasta do projeto.
- Página Biblioteca › Maturidade dos projetos: lista com nível e evidências; projetos há mais de 14 dias sem evidência e sem
  resposta viram pergunta (o engenheiro não precisa lembrar).
- Biblioteca de reatores: guarda a pasta de origem; entre os aprovados que cobrem o caso usa o de maior maturidade.

## O que NÃO foi feito (fica registrado)
- Módulo de estágio padrão completo (reator + capacitor + proteção + desenhos + coluna do painel) – REQ-GER-015.
- Detecção automática de evidência fora da pasta 06_Evidencias (ex.: achar a ordem de compra em outra pasta do cliente).
- Nível de maturidade por componente e conferência na internet se ainda é vendido – REQ-CMP-008.
