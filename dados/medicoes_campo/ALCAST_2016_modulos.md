# ALCAST – módulos de correção (Francisco Beltrão) – medições de campo 08–10/11/2016

Fonte: álbum Google Fotos "ALCAST MODULOS" (guilando@gmail.com, compartilhado pelo Guilherme em 22/11/2026),
31 fotos: 5 folhas de anotação manuscrita, 3 placas, 22 telas do Fluke 43 (harmônicos e osciloscópio), 1 painel Epcos.
Complementa: Engenharia_Backup\0 - CLIENTES\ALCAST\CORREÇÃO FP ALCAST\FRANCISCO BELTRÃO\LAMINAÇÃO\MEDIÇÕES COMPROBATORIAS
(indt mod 50kvar 520V.xls: tensão na bobina 24,6 V @60 Hz, 27,5 V @300 Hz, 8,6 V @660 Hz; reator Cootrans 1,289 mH / 72 A / 520 V; DHTi 26 %).

## Leituras do Fluke 43 (lidas das fotos – conferir no original)
| Foto | Tela | Leitura |
|---|---|---|
| 9–10 | Harmônicos – AMPS, h1 | THD 21,3–21,4 %f, 53,6 A rms, h1 52,5 A (100 %f, 0°), 59,97 Hz, KF 2,2 |
| 12 | AMPS, h7 | 419,8 Hz, 0,6 A (1,2 %f), −72° |
| 13–16 | AMPS, h11 | THD 21,5–21,6 %, 53,9 A rms, 659,7 Hz, 1,7 A (3,2 %f), 43°, KF 2,3 |
| 17 | VOLTS, h1 | THD 3,9 %f, 0,582 kV rms, 59,97 Hz |
| 18–22 | VOLTS, h3 | THD 3,9 %, 0,582–0,584 kV, 179,9 Hz, 0,003–0,004 kV (0,5–0,8 %f), 73–81° |
| 26 | VOLTS, h5 | THD 4,0 %, 0,590 kV, 299,9 Hz, 0,023 kV (4,0 %f), 170° |
| 27–28 | VOLTS, h5 | THD 4,1 % (foto girada) |
| 30 | OSCILOSCÓPIO 500 V/div, 2 ms/div | senoide com **6 notches/spikes por ciclo** (ponte de 6 pulsos), spikes ≈ ±0,5 div (~250 V) sobre a onda |
| 31 | OSCILOSCÓPIO 500 V/div, 5 ms/div | 0,563 kV rms, senoide limpa (outro ponto/condição) |

Folhas manuscritas (fotos 2–5): tensões VAB/VBC/VCA ≈ 378–381 V (entrada) e 413 V (capacitor), correntes ≈ 73–74 A,
cálculo de XL por fase (0,265–0,276 Ω) para indutor de 100 A e (0,53–0,55 Ω) para 50 A, "SOLDAR 380 V".

## Uso na plataforma (motor de melhoria contínua)
- Caso S2 (tensão nas bobinas com notches da rede) – validar: profundidade/largura dos notches (foto 30),
  DHTv 3,9–4,1 % com h5 4 %, e o espectro da tensão na bobina (24,6 / 27,5 / 8,6 V).
- O ponto de medição da foto 30 (barra × bobina) não está identificado na foto – confirmar com o Guilherme.
- Física: a tensão de alta frequência (notches) cai quase toda no reator, porque o capacitor é baixa impedância em HF.
  Volt-segundo do notch é pequeno (pouco fluxo), mas a perda por correntes parasitas cresce com V_h² e o dv/dt estressa a isolação entre espiras.
