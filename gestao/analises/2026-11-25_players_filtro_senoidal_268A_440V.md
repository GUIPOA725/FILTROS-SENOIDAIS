# Filtro senoidal A&W (268 A, 440 V) × players mundiais – 25/11/2026 (REQ-SEN-024)

Critérios (normalizados): L por fase; C equivalente em estrela (Δ × 3); fr = 1/(2π√(L·Cy)); uk = 2π·60·L·I/(V/√3);
perdas por ampère; massa; fs mínima; classe de isolação. Só dados de datasheet oficial (links abaixo).

| Filtro | I (A) | L (µH) | Cy (µF) | fr (Hz) | uk 60 Hz | Perdas (W) | W/A | Massa (kg) | fs mín |
|---|---|---|---|---|---|---|---|---|---|
| Electric A&W v1.29.0 | 268 | 210 | 90 (3×30 µF Δ) | 1158 | 8,4 % | 843 (painel) | 3,15 | ≈225 (com caixa) | 4 kHz fixa |
| Schaffner FN5040-260-99 | 260 | 200 | 141 (47 µF Δ) | 948 | 7,7 % | 880 | 3,38 | 125 | 3 kHz |
| TDK B84143V0250R227 | 250 | 320 | 102 (Y) | 881 | 11,9 % | 560 | 2,24 | 91 | 2,4 kHz |
| TDK B84143V0320R227 | 320 | 250 | 167 (Y) | 779 | 11,9 % | 750 | 2,34 | 145 | 2,4 kHz |
| Danfoss MCC 101 260 A (130B3184) | 260 | 340 | 25 (Y equiv.) | 1726 (conferir C) | 13,1 % | 850 | 3,27 | 197 (IP00) | 3 kHz |
| Block SFB 400/250 | 250 | 350 | 67,5 (22,5 µF Δ) | 1035 | 13,0 % | 810 | 3,24 | 157,5 | 3 kHz |
| MTE SWG 305 A (480 V) | 305 | n/p | n/p | n/p | queda ≤ 6 % | 945 | 3,10 | 118 (aberto) | 2 kHz |

Leitura: C e fr dentro da faixa do mercado (Cy 67–167 µF; fr 780–1160 Hz; fr/fs 0,29 dentro de 0,20–0,35). L igual ao Schaffner e
abaixo de TDK/Danfoss/Block (uk 12–13 %, queda ~11 %): escolha deliberada de queda menor (6,7 %) para o motor receber o V/f; o preço é
mais ondulação (perda AF no indutor e corrente no capacitor), já verificados. Perdas/A dentro da faixa (2,2–3,4 W/A). Block declara
classe H (180 °C) – coerente com REQ-SEN-021.

Fontes: Schaffner FN5040/45 datasheet (mouser.com/ds/2/355/DS_FN5040_45_web-7503.pdf); TDK B84143V*R227
(tdk-electronics.tdk.com/inf/30/db/emc_2014/B84143V_R227.pdf); Danfoss Output Filters Design Guide
(assets.danfoss.com/documents/latest/277639/AJ361178726334en-000501.pdf, tab. 4.4); Block SFB technical information
(foxdrives.de/mediafiles/Sonstiges/anhang/SFB_Technische_Informationen.pdf); MTE SWG TRM (mtecorp.com/wp-content/uploads/SWG-TRM-E.pdf).
