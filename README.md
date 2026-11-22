# FSEN – Plataforma de Filtros Senoidais LC/LCL

Substitui as planilhas manuais de dimensionamento. A partir do e-mail do cliente, gera em segundos:
dimensionamento otimizado, simulação PWM, verificações por norma, especificação dos componentes reais,
desenhos da caixa (vistas, cortes, 3D, diagrama elétrico), lista de material, custo, preço, proposta ao cliente,
ET + e-mail para cada fornecedor e pacote completo para a montadora terceirizada.

## Onde fica no Drive
Drive da Electric Service (guilherme@electricservice.com.br):
`G:\Drives compartilhados\Engenharia\15 - TEMPLATES-PLANILHA ESTUDOS\PLATAFORMA FILTROS SENOIDAIS`
- PROGRAMAS – zip da versão oficial
- PROJETOS – um pasta por pedido (gerada automaticamente pela plataforma)
- BIBLIOTECA – catálogo (capacitores, caixas, preços, critérios, fornecedores)
- ATUALIZACOES-MELHORIAS – registro de versões, lista de melhorias e estudos

O programa roda no computador de cada um (copie o zip para o disco local, não rode de dentro do Drive).

## Instalação (Windows)
1. Copie a pasta `fsen_plataforma` para o computador (ou para o Google Drive).
2. Execute `INSTALAR.bat` (usa o Python/Anaconda já instalado).
3. Edite `INICIAR.bat`: pasta de saída do Google Drive e, se quiser IA, `ANTHROPIC_API_KEY`.
4. Execute `INICIAR.bat` → abre no navegador.

## Uso diário
- **Ajuste manual:** depois do cálculo automático, menu *Ajuste manual e ressimulação* → mude uk/µH, fs, capacitor (ou um personalizado), Δ/Y, quantidade ou fr desejada, resistor → **Ressimular** → compare com o automático → **Gerar pacote**.
- **Critérios:** menu *Critérios de projeto* para mudar limites e pesos da otimização.
- **Interface:** cole o e-mail, anexe o PDF do cliente → "Ler solicitação" → confira → "Dimensionar…" → baixe/abra o pacote.
- **Automático:** `MONITOR_EMAIL.bat` verifica a caixa a cada 5 min, gera tudo na pasta do Drive e deixa um **rascunho de resposta** com a proposta anexada. Você só revisa e envia.
- **Linha de comando:** `python -m fsen processar email.txt --anexo cotacao.pdf`

## O que sai para cada pedido (pasta `AAAA-MM-DD_Cliente_FSEN-LC-293A-440V`)
| Pasta | Conteúdo |
|---|---|
| `01_Engenharia` | Memorial de cálculo e simulação (.docx), planilha BOM/custos/preço (.xlsx, fórmulas vivas), projeto.json |
| `02_Cliente` | Proposta técnico-comercial, folha de dados, e-mail de resposta |
| `03_Fornecedores` | ET + e-mail: indutor (Cootrans), capacitores (TDK/WEG), resistores, caixa, cabos/miscelânea |
| `04_Montadora` | Pedido de orçamento de montagem, caderno de montagem (após fechar), desenhos |
| `05_Desenhos` | PDF A3: vistas cotadas, cortes, 3D, vista externa, diagrama trifilar, lista de cabos |
| `graficos` | Formas de onda, espectro, Bode, impedância, ressonância, fluxo de correntes |
| `RESUMO.md` | Resumo de 1 página com status e preço |

## Método de cálculo (resumo)
- Candidatos: uk 4–10 % (L), fr entre 10·f_saída,máx e fs/2, arranjos reais de capacitores (Δ/Y, n por ramo) e amortecimento opcional (Rd = Z0/Q).
- Pré-filtro analítico (THD ≈ 1,6·(fr/fs)²/(1−(fr/fs)²), ondulação ≈ 0,19·Vcc/(L·fs)) e simulação PWM SVPWM em regime permanente exato para cada candidato; escolhe o de menor custo que atende a todos os critérios críticos.
- Critérios e normas: IEC 61800-2/-5-1, IEC TS 60034-25, NEMA MG1 Pt30/31, IEC 60076-6, IEC 60831/61071, IEC 61000-2-4/IEEE 519, IEC 61439, NBR 5410; prática Schaffner FN5040/5045, ABB, Danfoss.
- Tudo configurável em `dados/catalogo.yaml` (ou menu "Catálogo e preços").

## Histórico e clientes
- Cada projeto é registrado em `dados/historico.db`. Projetos semelhantes aparecem ao abrir um novo pedido.
- Importar pastas antigas: `python -m fsen importar "G:/…/6 - FILTRO SENOIDAL LC" "G:/…/7 - FILTRO SENOIDAL LCL"`
- Planilha de clientes fornecidos: `python -m fsen clientes Clientes_Fornecidos.xlsx`
- Cotações reais de indutor recalibram o modelo de custo: `python -m fsen cotacao-indutor Cootrans 47.4 8200`

## Limitações conhecidas (v1.0)
Dimensões/massa de indutor e preços são estimativas até chegarem desenhos e cotações reais; Imax dos capacitores
usa 1,3·In (IEC 60831) até ser preenchido com o datasheet. Ver `MELHORIAS.md`.


## Regra para TODA versão nova (desde a v1.18.0)
1. Todo campo/botão novo nasce com dica: `help=` no widget **ou** entrada em `fsen/ajuda.py` (DICAS). Tela nova ganha seu roteiro em `GUIAS`.
2. Antes de publicar: `python validacao/verificar_ajuda.py` precisa dar **0 campo(s) sem dica** (senão não publica).
3. O CHANGELOG é escrito para o usuário (o que mudou e como usar) – a primeira seção aparece em "Novidades desta versão" na ajuda e alimenta o assistente.
4. Publicação: commit + push, zip em PROGRAMAS, arquivos alterados no FSEN_v1.7.1, CHANGELOG em ATUALIZACOES-MELHORIAS. Os colegas atualizam fechando a janela preta e abrindo o ABRIR_FSEN.bat de novo.
