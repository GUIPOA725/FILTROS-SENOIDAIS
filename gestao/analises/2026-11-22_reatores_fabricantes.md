# Reator de filtro dessintonizado / sintonizado – o que dizem os fabricantes × o que a plataforma faz

Pedido do engenheiro (22/11/2026 22:36 e 22:41, REQ-REF-008): analisar a fundo o material em inglês do Drive pessoal
(guilando@gmail.com) e conferir nos sites dos FABRICANTES de reator – a NEPSI monta filtros, não fabrica indutor.

## Fontes lidas (22/11/2026)
Drive pessoal: `nepsi reator.pdf` (LV-AFB 1999), `Reatores.docx` (Polylux + NEPSI + ferro × ar), `Iron.docx`, `filtspec.docx`
(guia de especificação NEPSI MT), `Harmonic Filter Bank Tuning.docx`, `Differences Between Medium and Low Voltage Filter
Design.docx` (P. Steciuk), `Harmonic Filter Bank.docx` (proteção), `HvM_Ironcore_Reactors_Catalogue_2011_ENG.pdf` (Mangoldt),
`Understanding-Medium-Voltage-Harmonic-Filter-Reactors` e blog "Docta Reacta" (Power Magnetics).
Internet: folha de dados TDK/Epcos B44066D5050M441 (50 kvar 440 V 60 Hz 5,67 %), Schneider LVR14125A40T, manual PSF com
reatores Mangoldt PolyGap (vfds.com), Estel DTFR (IEC 60076-6), apresentação "Harmonic Filter Design" da NEPSI.
NÃO lidos ainda: IEEE 1531-2003, IEC 60076-6 (norma), McLyman, "dimensionamento cabos filtros harmonicas nepsi.pdf",
"Steps and Stage Size", "Actual Kvar Output Versus Installed Kvar", catálogos Schneider PB Guide/ABB, sites Trench/Hammond/Trafox.

## 1. Saturação / linearidade do núcleo (o ponto do "quantos tesla")
| Fonte | Tipo | Critério |
|---|---|---|
| NEPSI (monta filtros; especifica o reator) | filtro BT e MT | não saturar abaixo de 250 % da corrente fundamental do estágio; pico de indução < 1,2–1,4 T com picos das harmônicas 100 % coincidentes; "saturação" = perda de 10 % de L; espectro mínimo I1 = 1,21·In e I(sintonia) = 0,5·In |
| Power Magnetics (fabricante) | reator de filtro MT | pico = soma ARITMÉTICA de fundamental + harmônicas; saturação começa em 15–16 kG (1,5–1,6 T); aquecimento pela soma RSS; vários entreferros pequenos; alumínio com confiabilidade similar ao cobre (cobre 15–25 % mais caro) |
| Mangoldt (fabricante) | dessintonia BT | L ±3 %; I1 = 1,10·Icn; U3 0,5 / U5 6 / U7 5 / U11 3,5 / U13 3,5 % (THD 8 %); I_lin = k·Icn, k função do FD (critério antigo: 1,20·(I1+…+I7), soma aritmética); ambiente 50 °C |
| TDK/Epcos (fabricante) B44066D5050M441 | 50 kvar 440 V 60 Hz 5,67 % | Ief 83,5 A; "linear até 155 A" (≈ 2,36 × a corrente nominal do capacitor de 65,6 A); U 0,5/6/5/3,5/3 %; 300 W; 34 kg; classe H, 40 °C; termostato NF só de alarme |
| Estel DTFR (fabricante) | dessintonia | L ≥ 0,95·Ln em 1,3·Ief; L ±3 %; classe F; 50 °C; IEC 60076-6 |
| Schneider LVR (fabricante) | dessintonia | L ±5 %; Imp = 1,12·I1; classe H; convecção forçada; 55 °C |
| Polylux (fabricante, no Reatores.docx) | 7 % 400 V | classe F, elevação < 85 K, 45 °C, I3 8 % / I5 31 % / I7 13 %, sobrecorrente 6 %, L ±3 % |
| **Plataforma FSEN (hoje)** | BT | Isat = max(√2·1,5·I_projeto·0,97 ; pico da soma aritmética) com L ≥ 90 %; núcleo dimensionado para 1,45 T em Isat; espectro padrão 0,5/6/5/3,5/3 % (igual TDK/Mangoldt); I_projeto = max(1,3·I60, física) |

Leitura: o MÉTODO da plataforma (soma aritmética, perda de 10 % de L) é o mesmo da NEPSI e da Power Magnetics, e o espectro
padrão é o da TDK/Mangoldt. A MARGEM é que é menor: na Panatlântica 50 kvar a plataforma garante linearidade até ≈ 2,0 × a
fundamental (193 A de pico), contra 2,36 × da TDK e 2,5 × da NEPSI; e a indução de projeto (1,45 T) está acima da faixa NEPSI
(1,2–1,4 T) e logo abaixo de onde a Power Magnetics diz que a saturação começa (1,5–1,6 T).

## 2. Peso e perdas – comparação com o reator real
TDK 50 kvar 440 V 60 Hz 5,67 %: 0,618 mH, 34 kg, 300 W (classe H). Cootrans Panatlântica (8,16 %, 796 µH, 95 A): ~55 kg,
alumínio, classe F. Plataforma (8,16 %, 829 µH): 53–56 kg, 265 W, alumínio, classe F, elevação 42 K. A plataforma está no
peso do Cootrans; a TDK é mais leve porque tem L 25 % menor (5,67 %), cobre e classe H (elevação maior).

## 3. Construção
- Vários entreferros pequenos e colados (PolyGap, "wind-on-leg", "distributed and cemented"): menos espraiamento, menos
  aquecimento local e ruído. A plataforma usa 2 entreferros por coluna na Panatlântica – revisar o critério para mais divisões.
- Impregnação a vácuo (VPI), isolação Nomex 220 °C (NEPSI/PMI) ou classe H (TDK, Mangoldt, Schneider). A ET Electric usa classe F.
- Sintonizado: fabricantes preferem 3 monofásicos de 2 bobinas (confirma Pirelli); trifásico é o usual na dessintonia BT.
- Taps: comuns em MT, não usuais em BT.
- Termostato: na bobina central, NF em série (Mangoldt); a TDK avisa que o NF é só alarme – o desligamento é pelo comando
  (a plataforma já liga em série com a bobina da contatora).
- Montagem (manual PSF/Mangoldt): ≥ 12 mm entre reator e outros componentes/paredes; eixo das bobinas vertical; ar forçado
  paralelo ao eixo; torques M8 16 N·m / M10 32 N·m / M12 56 N·m na fixação e 25/49/86 N·m nas barras; ar interno ≤ 45–50 °C.

## 4. Sintonia e proteção (NEPSI)
- Dessintonizado 4,0–4,4 (só FP, cuidar da anti-ressonância perto da 3ª); parcialmente sintonizado 4,4–4,8; sintonizado
  4,8–5,0 (maior risco, exige estudo). FD 8,16 % = Nr 3,5 fica ABAIXO da faixa "4,0–4,4": absorve ainda menos 5ª – coerente com
  a regra do engenheiro de usar 14 % se houver 3ª relevante.
- Capacitor: picos coincidentes, +5 % de tensão, distorção no limite da IEEE 519; BT metalizado perde capacitância com o tempo
  → a sintonia sobe (por isso BT sintoniza em 4,7 e não 5,0).
- Reator: relé de sobrecarga térmica (49) sensível a rms + termostato de reserva (também cobre falha do ventilador); fusíveis
  limitadores a montante (reator saturado numa falta cai para a reatância de núcleo de ar).

## 5. Propostas para a plataforma (a aprovar pelo engenheiro)
1. Verificação nova no relatório do reator, com Check: indução de pico na COLUNA com soma aritmética × faixa 1,2–1,4 T (NEPSI)
   e ≤ 1,5 T (PMI); linearidade L ≥ 90 % até 2,5 × I fundamental (NEPSI) e L ≥ 95 % até 2,36 × Icn (TDK) como referência.
2. Decidir a margem padrão Electric: manter 1,5 × I_projeto ou subir para 2,5 × I60 (reator mais pesado – estimar o custo).
3. Indução conferida no NGSolve não-linear (REQ-REA-012).
4. Mais entreferros por coluna (critério PolyGap) – medir o efeito nas perdas por espraiamento.
5. Folgas e torques de montagem do reator (12 mm, torques) no catálogo de montagem (REQ-CMP-003) junto com as distâncias do campo.
6. Sintonizado: espectro mínimo NEPSI (I1 = 1,21·In; I sintonia = 0,5·In) como piso, comparado ao padrão Electric (1,1/0,55/0,44·I1).
