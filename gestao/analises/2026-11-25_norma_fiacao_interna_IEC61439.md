# Fiação interna dos painéis (banco dessintonizado, sintonizado e filtro senoidal) – qual norma vale

Pesquisa 25/11/2026 (REQ-PNL-031/032), a pedido do engenheiro.

## Conclusão
- O painel é um CONJUNTO de manobra e comando: ABNT NBR IEC 61439-1 (2016, obrigatória no Brasil desde dez/2021) + NBR IEC 61439-2 (conjunto PSC).
- Banco de capacitores (com ou sem reator de dessintonia): IEC 61921:2017 (EN IEC 61921:2025), que manda atender "where applicable" a IEC 61439-1 e -2; 6.2.2: chaves e conexões para 1,3 × In senoidal; Anexo A: seções mínimas/máximas de condutores de cobre para conexões.
- Filtro sintonizado: o mesmo conjunto (IEC 61439-1/-2); aplicação de filtros: IEC 61642 (guia); capacitor IEC 60831; reator IEC 60076-6.
- Filtro senoidal: o painel é conjunto IEC 61439-1/-2; o indutor e o filtro como produto: fabricantes declaram EN/IEC 61558 (Danfoss MCC 101) e IEC 61800-5-1 para grau de poluição/categoria de sobretensão (sistema de acionamento).
- NBR 5410 §1.4: considera componentes e conjuntos "apenas no que concerne à sua seleção e condições de instalação"; conjuntos seguem as normas a eles aplicáveis. NBR 5410 vale para os cabos do cliente até o painel, não para a fiação interna.

## Como a IEC 61439-1 dimensiona os condutores internos
- §10.10.4.2.1 f) e §10.10.4.3.1 f) (verificação da elevação de temperatura por cálculo – o nosso caso, IEC 60890, até 1600 A): seção mínima para 125 % da corrente do circuito; cabos escolhidos pela IEC 60364-5-52 com o exemplo de adaptação do Anexo H; barras como ensaiadas ou pelo Anexo N; se o fabricante do dispositivo pedir seção maior, usar a maior.
- §10.10.4.x c): corrente do circuito ≤ 80 % da corrente térmica convencional ao ar livre (Ith) ou In do dispositivo (contatora: AC-1).
- Anexo H: Imax = I30 × k1 × k2. I30 da IEC 60364-5-52 para o método de instalação; k1 = Tabela H.2 (condutor a 70 °C – o borne dos dispositivos é ensaiado com condutor a 70 °C), em função do ar DENTRO do painel (20 °C 1,12 · 30 °C 1,00 · 40 °C 0,87 · 45 °C 0,79 · 50 °C 0,71 · 55 °C 0,61 · 60 °C 0,50); k2 = agrupamento (0,8 canaleta, 0,88 encostados, 1,0 espaçados ≥ 1 diâmetro; Tabela H.1 com 2 circuitos – mais circuitos: fatores da IEC 60364-5-52).
- Tabela H.1 (55 °C, 70 °C): 35 mm² 54/76/110 A; 50 mm² 65/93/134 A; 70 mm² 83/120/171 A (canaleta / encostados / espaçados).
- Perdas: Pv = I² · R20 · [1 + 0,004 (Tc − 20)] – entram na térmica do painel.

## Consequência para a Panatlântica (estágio 50 kvar 415 V, In 92 A → 125 % = 115 A)
- Espaçados ao ar: 35 mm² (ar interno 50 °C: 128 A) ou 50 mm² (55 °C: 134 A) atendem – coerente com a prática Electric (35/50 mm²).
- Em canaleta fechada com 4 circuitos: nem 70 mm² atende – a montagem tem que ser espaçada (cabos de força fora da canaleta, presos na placa com espaçadores).
- Contatora: AC-1 ≥ 92/0,8 = 115 A → AF80 (125 A) com borne 50 mm²; AF52 (100 A) não atende o §10.10.4 c).

## Fontes
- IEC 61439-1:2011 (texto: catvanloi.com/.../IEC-61439-1-2011.pdf) e Anexo H ed. 3 (arielsegal.co.il/.../ANNEX-H-ed3.pdf)
- IEC 61921:2017 prévia (cdn.standards.iteh.ai/samples/23601/...)
- NBR 5410:2004 §1.4 (ipaam.am.gov.br/.../NBR-05410-05...)
- O Setor Elétrico – vigência da ABNT NBR IEC 61439-1:2016
- Schneider PFC Cubicles Guide 2015; WEG catálogo de painéis (NBR IEC 61439); Danfoss MCC 101 (EN 61558)
