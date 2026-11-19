# Lista de melhorias (motor de melhorias)

Marque [x] quando concluído. A plataforma lê e grava este arquivo (menu "Melhorias / atualizações").

## Prioridade alta
- [ ] Preencher datasheet real do PEC 20 µF 480 V: Imax, ESR, Rth, categoria de temperatura (define se Δ é possível).
- [ ] Validar estudo térmico com medição (termopares) em um filtro em operação: ar de saída, indutor, capacitor mais alto.
- [ ] Pedir à Cootrans perdas reais (60 Hz e com ondulação em 4 kHz) e área de troca do indutor para calibrar o modelo térmico.
- [ ] Testar Ollama local (offline) com um modelo de 7–14B para leitura dos pedidos sem internet.
- [ ] Cadastrar capacitor de filtro IEC 61071 (TDK MKP AC filter) com Imax do datasheet – deve reduzir para ~6 capacitores e caixa menor.
- [ ] Oferecer versão IP00 (filtro aberto) como opção na proposta: ≈ −30 % de custo.
- [ ] Revisar arranjo da caixa com as caixas reais que você usa (alturas/zonas) – hoje a caixa é ~30 % do custo.
- [ ] Paralelizar a otimização (multiprocessamento) para cair de ~70 s para ~15 s.
- [ ] Importar as pastas "6 - FILTRO SENOIDAL LC" e "7 - FILTRO SENOIDAL LCL" (conta electricservice) para o histórico de clientes.
- [ ] Preencher catálogo com P/N reais e preços: capacitor TDK PEC 20 µF 480 V (Imax do datasheet), WEG UCW, caixas usadas recentemente.
- [ ] Registrar 2+ cotações reais da Cootrans para calibrar o custo do indutor (comando `cotacao-indutor`).
- [ ] Validar simulação com medição de um filtro já entregue (THD, corrente nos capacitores, temperatura).
- [ ] Confirmar fs padrão por modelo de inversor (ACS580 frame R8 a 4 kHz: derating) e cadastrar WEG CFW, Danfoss, Siemens.

## Prioridade média
- [ ] Amortecimento RC paralelo (Rd + Cd) como alternativa ao resistor série – menos perdas.
- [ ] FEA do indutor (núcleo/entreferro/térmica) quando a Cootrans enviar a geometria.
- [ ] Indutor: estimativa de núcleo/enrolamento (área de janela, nº de espiras, perdas Steinmetz) para conversar tecnicamente com a Cootrans.
- [ ] Modelo de cabo longo (reflexão de onda) para filtros dv/dt e LCL com cabos > 150 m.
- [ ] Exportar desenhos em DXF para a montadora/caixa.
- [ ] Enviar ETs aos fornecedores direto pelo Gmail (rascunhos) a partir da interface.
- [ ] Gerar PDF dos documentos (proposta e folha de dados) junto com o .docx.

## Ideias
- [ ] Painel de acompanhamento: status (cotado, enviado, ganho, perdido, em montagem, entregue).
- [ ] Comparativo automático com catálogo Schaffner/ABB/Danfoss para o cliente.

## Próximas (pedido de 19/11/2026)
- [ ] **Dupla checagem no ATP.** A plataforma gera o deck .atp da mesma rede (inversor, L, C, cabo, motor e terra), executa o ATP instalado no PC, lê o .pl4 e compara com a simulação Python. A comparação cobre THD, I e Vpk dos capacitores, fr e corrente de terra, com tolerância e alerta de divergência. Usar como modelo o deck PWMMOTOR_Jul_2023_filtro_LCL.atp (SENAI).
- [ ] **Modelo do inversor por fabricante:**
  - modulação SPWM, SVPWM, DPWM/60° e sobremodulação;
  - amostragem regular/assimétrica, tempo morto e pulso mínimo;
  - fs fixa ou aleatória/wobbling;
  - DTC × escalar (ABB) e os parâmetros obrigatórios com filtro senoidal.
- [ ] Verificador temporal independente em Python (integração passo a passo com chaves) para conferir o método harmônico.

- [x] Pedido automático de dados faltantes ao cliente com análise de sensibilidade (v1.7.0)
- [ ] Indutor classe H como opção automática quando o ponto quente classe F ficar com margem < 5 K
