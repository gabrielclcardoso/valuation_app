---
name: dcf-valuation
description: Analyzes Brazilian public companies (B3) using specialized fundamentalist valuation models (DCF por FCFF para Concessões/Infra, Gordon & DDM para Bancos/Seguradoras, SOTP Intrínseco para Holdings, e DDM Regulatório para Operadoras de Saúde), following a strict 4-phase blind methodology, and outputs a ready-to-use JSON file for the valuation app.
---

# Valuation Fundamentalista para Ações Brasileiras (B3)

Esta skill guia o agente Antigravity na execução completa do processo de Valuation para empresas listadas na B3, com foco especial em **empresas de infraestrutura, dividendos e previdenciárias**, garantindo rigor contábil, cálculos exatos via Python, proteção contra viés de ancoragem e exportação padronizada em JSON para a Calculadora Web.

---

## 🧭 Fase 0: Roteamento Inteligente de Metodologia

Antes de iniciar qualquer coleta, identifique a natureza contábil e societária da empresa para acionar o motor de valuation correto:

```mermaid
flowchart TD
    Inicio["Identificação do Ativo (Ticker / Setor)"] --> Roteador{"Tipo de Empresa"}
    
    Roteador -->|"Concessões, Saneamento, Energia, Telecom, Indústria, Hospitais"| FluxoA["Fluxo A: DCF por FCFF (WACC)<br/>CLI: valuation_cli.py dcf"]
    Roteador -->|"Bancos e Seguradoras / Corretoras (ITUB, BBAS, BBDC, BBSE, CXSE)"| FluxoB["Fluxo B: Gordon & DDM (Ke)<br/>CLI: valuation_cli.py financials"]
    Roteador -->|"Holdings Puras e Mistas (ITSA4, BRAP4)"| FluxoC["Fluxo C: SOTP Intrínseco<br/>CLI: valuation_cli.py holding"]
    Roteador -->|"Operadoras de Saúde ANS Puras (BradSaúde/SAUD3, ODPV3)"| FluxoD["Fluxo D: Saúde Suplementar ANS<br/>CLI: valuation_cli.py saude"]
```

> [!TIP]
> Você pode executar a triagem automática via terminal executando:
> `python valuation_cli.py route --ticker <TICKER>`

* **Fluxo A — DCF por FCFF / WACC (`valuation_cli.py dcf`):**
  * Saneamento (SAPR4, SBSP3, CSMG3), Energia Elétrica (ALUP11, CPFE3, EGIE3, TAEE11), Telecom (TIMS3, VIVT3), Rodovias/Logística (CCRO3, ECOR3, STBP3), Indústria (WEGE3, TUPY3), Hospitais e Redes de Diagnóstico (RDOR3, FLRY3).
* **Fluxo B — Gordon Growth & DDM (`valuation_cli.py financials`):**
  * Bancos (ITUB4, BBAS3, BBDC4, SANB11) e Seguradoras/Bancassurance (BBSE3, CXSE3).
  * *Fundamento:* A dívida/depósitos faz parte da operação e o caixa livre que chega ao acionista é limitado pelo Índice de Basileia ou Margem de Solvência da Susep. Usa-se $K_e$ (Custo do Capital Próprio) em vez de WACC.
* **Fluxo C — SOTP a Valor Intrínseco (`valuation_cli.py holding`):**
  * Holdings (ITSA4, BRAP4, SIMH3).
  * *Fundamento Anti-Bolha:* Para evitar herdar eventuais cotações de mercado infladas das controladas (ex: se Itaú estiver caro na bolsa), o modelo calcula tanto o **SOTP a Valor de Mercado** quanto o **SOTP a Valor Intrínseco** (utilizando o Preço Justo fundamentalista calculado para a investida).
* **Fluxo D — DDM Regulatório ANS (`valuation_cli.py saude`):**
  * Operadoras de Planos de Saúde puras com provisões técnicas (BradSaúde/SAUD3, ODPV3).
  * *Atenção:* Operadoras verticalizadas (com hospitais próprios, ex: HAPV3) são PROIBIDAS de usar o Fluxo D. Elas devem obrigatoriamente usar o Fluxo A (DCF por FCFF) para capturar o impacto real do CapEx físico e da depreciação no fluxo de caixa.
  * *Fundamento:* Calibra a Sinistralidade Médica (MLR), o rendimento do *float* das provisões técnicas e a retenção de lucros exigida pela Margem de Solvência da ANS.

---

## 📋 As 4 Fases de Execução (Rigor Metodológico)

### Fase 1: Coleta Bruta e Pre-Flight Checklist (Isolando Fatos)

> [!WARNING]
> **REGRA DE ATUALIDADE TEMPORAL E CHECKLIST OBRIGATÓRIO (ANTI-DESATUALIZAÇÃO):**
> * **Verifique o ano civil atual antes de pesquisar:** Execute `date` ou leia a metadata do sistema.
> * **NUNCA chumbe anos passados nas buscas iniciais** (ex: NUNCA pesquise termos fixos como `"DFP 2024"` ou `"4T24"` antes de saber o ano corrente).
> * **Acesse primeiro a Central de Resultados oficial:**
>   Faça buscas como `site:ri.<empresa>.com.br "Central de Resultados"` ou `site:cvm.gov.br "<empresa>" "DFP"`.
> * **Posição Patrimonial Recente:** Para Caixa e Dívida, utilize o último balanço trimestral (ITR) disponível.
> * **Prioridade da pasta `reports/`:** Se o usuário colocar um relatório na pasta `reports/`, utilize esse documento como fonte primária da verdade.
> * **[OBRIGATÓRIO] PRE-FLIGHT CHECKLIST DE EVIDÊNCIA:** Antes de executar qualquer script Python da CLI, você DEVE imprimir no chat um bloco chamado "Evidência de Recência", listando: a URL ou o número do protocolo da CVM consultado, o Ano Base do FCFF, e o Trimestre do ITR utilizado. O script exigirá esses dados via `--ano-base` e `--trimestre-itr`.

> [!CAUTION]
> **[HARD STOP] PROTOCOLO DE FALLBACK (ANTI-ALUCINAÇÃO EXTREMA):** Se após a busca inicial (CVM e site de RI) você NÃO conseguir baixar ou acessar os PDFs originais do DFP/ITR mais recentes da empresa:
> 1. **PARE IMEDIATAMENTE.**
> 2. NÃO adivinhe números, NÃO interpole, e NÃO use dados de portais secundários ou agregadores (ex: StatusInvest, Fundamentus, Yahoo Finance).
> 3. Avise o usuário **ESPECIFICANDO EXATAMENTE** qual período ele deve baixar (ex: ITR 2T26 ou DFP 2025): *"Não consegui acessar os documentos primários necessários. Por favor, baixe os PDFs do [ESPECIFIQUE O DOCUMENTO E PERÍODO, ex: ITR 2T26], coloque-os na pasta `reports/` e me avise quando estiverem prontos."*
> 4. Aguarde a confirmação explícita do usuário antes de retomar a coleta ou passar para a Fase 2.

#### 1.1 Levantamento Histórico Obrigatório (3 a 5 Anos - Anti-Distorção de Base):
* Colete a série histórica de **Receita Líquida, EBITDA e Fluxo de Caixa Livre da Firma (FCFF)** dos últimos 3 exercícios fechados.
* **[ATENÇÃO - REGRA DO FCFF]:** A fórmula matemática para calcular o FCFF requer somar o benefício fiscal da dívida de volta ao FCO antes de deduzir o CapEx. O Motor Python fará essa conta automaticamente para você de forma livre de erros: basta inserir o FCO bruto, as Despesas Financeiras Pagas (Juros) e o CapEx nos parâmetros da CLI (`--fco`, `--juros-pagos` e `--capex-projetado`). NUNCA calcule o FCFF mentalmente usando apenas "FCO - CapEx" ou correremos o risco de dupla penalização da dívida. *(Ressalva CPC 03 / IAS 7: Caso as demonstrações contábeis da empresa classifiquem os Juros Pagos no Fluxo de Financiamento em vez do Fluxo Operacional, o FCO já se encontra antes dos juros; nesse caso, utilize `--sem-juros-no-fco` na CLI para evitar dupla contagem).*
* Calcule a média histórica do FCFF e o CAGR histórico de 3 anos.
* Identifique distorções não recorrentes: créditos tributários extraordinários, descompassos temporários de capital de giro (NCG) ou M&A inorgânico (ex: compra da Oi Móvel).

#### 1.2 Diagnóstico da Dinâmica Concorrencial & Market Share:
Antes de arbitrar o crescimento, classifique a empresa em um dos 3 regimes de mercado:
1. **Oligopólios Racionais (ex: Telecomunicações — TIMS3, VIVT3; Grandes Bancos):**
   * Fatia de mercado (*Volume Share*) cristalizada. Guerras predatórias de preços destroem margem.
   * Premissa de mercado: **Market share em volume estável** (acompanha crescimento demográfico/PIB). O ganho real vem de **ARPU / Value Share** (migração de planos, 5G, valor agregado).
2. **Monopólios Naturais / Concessões Reguladas (ex: Saneamento, Transmissão Elétrica — SAPR4, SBSP3, TAEE11):**
   * Área de atendimento exclusiva contratual (sem concorrência de varejo).
   * O crescimento vem da **expansão da Base de Ativos Regulatórios (RAB)**, metas contratuais do marco legal e reajuste inflacionário das tarifas.
3. **Setores Concorrenciais Abertos / Indústria (ex: WEGE3, TUPY3):**
   * Empresas com fortes vantagens competitivas (*moats*) podem sustentar taxas acima do PIB através de ganho contínuo de market share doméstico e internacional.

#### 1.3 Levantamento Patrimonial e Quase-Dívidas Obrigatório:
* **Dívida Financeira e Caixa:** Colete a dívida bancária bruta e disponibilidades no último balanço. Em empresas de telecom e logística, isole a dívida estritamente financeira dos arrendamentos IFRS 16 (que já reduzem o EBITDA-AL).
* **Varredura de Contingências (CPC 25 / IAS 37):** Acesse a nota explicativa de Provisões. Identifique o saldo total de contingências com probabilidade de perda provável (cíveis, fiscais, trabalhistas e regulatórias) para alimentar obrigatoriamente `--passivos-contingentes`.

---

### Fase 2: Coleta de Variáveis Conforme o Fluxo

> [!CAUTION]
> **REGRA DE ANUALIZAÇÃO OBRIGATÓRIA (ANTI-ESMAGAMENTO):** Todos os inputs financeiros (FCFF, Lucro) e taxas de rentabilidade (ROE, ROIC) fornecidos à CLI **DEVEM estar em base ANUAL (12 meses / TTM)**. Se você extrair o lucro ou fluxo de caixa de apenas um trimestre ou semestre (ex: 1S26), você é OBRIGADO a anualizá-lo antes de rodar os scripts. Inserir um ROE trimestral (ex: 5%) contra um Custo de Capital anual (ex: 15%) vai esmagar o Preço Justo e destruir a matemática do Valuation.

#### Para Fluxo A (DCF Concessões e Indústria):
1. **FCO Bruto e CapEx:** Segregar CapEx de Sustentação, Expansão Remunerada (RAB) e CapEx Não Oneroso (obrigações compulsórias sem remuneração tarifária).
2. **Dívida Financeira Líquida:** Dívida Bruta menos Caixa e Aplicações do último ITR (isolando passivos de arrendamento operacional IFRS 16 quando o fluxo já é deduzido de leasing).
3. **Quase-Dívidas / Passivos Contingentes (Checklist Mandatório):**
   * É **OBRIGATÓRIO** pesquisar nas Notas Explicativas do DFP/ITR a linha de *Provisões para Processos Judiciais e Administrativos (Cíveis, Trabalhistas, Fiscais e Regulatórios)* com risco de perda provável.
   * O parâmetro `--passivos-contingentes` NUNCA deve ser deixado em zero sem que o agente declare explicitamente na justificativa que consultou as demonstrações e a empresa não possui processos judiciais provisionados relevantes.
   * O motor Python aplica automaticamente o benefício fiscal de dedutibilidade de 34% (IRPJ/CSLL) sobre essas contingências, garantindo que o **Cenário Ajustado por Quase-Dívidas** reflita o passivo líquido real que o acionista terá que honrar.
4. **Base Acionária:** Total de ações emitidas líquidas de tesouraria (Milhões).
5. **DPA Projetado:** Dividendo por ação esperado e percentual em JCP para métricas de Décio Bazin (6% e 8%).
6. **Parâmetros de Concessão e Estrutura de Capital:** Para concessões com prazo finito (rodovias, distribuição, saneamento contratual), colete o prazo contratual remanescente (em anos a partir do ano-base, `--prazo-concessao-anos`) e o saldo da Base de Ativos Regulatórios (RAB) indenizável ao final do contrato (`--rab-indenizavel-mi`), além da alavancagem ótima setorial (`--alavancagem-otima-pct`, `Dívida / (Dívida + Equity)`).

#### 🧭 Subfase 2.1: Triângulo de Validação do Crescimento ($g$) e Base ($FCFF_0$)
Para evitar arbitrariedade nas taxas projetadas ($g_1 \dots g_5$), aplique o triângulo fundamentalista:
* **Âncora 1: Normalização do Ano-Base ($FCFF_0$):**
  Compare o FCFF recente com a média dos últimos 3 anos. Se o desvio for superior a 25%, justifique se o ano recente reflete um novo patamar estrutural ou se requer normalização.
* **Âncora 2: Teste de Coerência Histórica (CAGR 3A):**
  A taxa inicial $g_1$ não deve superar o CAGR histórico sem que haja um gatilho comprovado (ex: entrada em operação de grandes obras de CapEx, novo contrato ou ganho medido de share).
* **Âncora 3: Decomposição Vetorial da Taxa Inicial ($g_1$):**
  A taxa $g_1$ deve ser explicitada como a soma de três vetores econômicos:
  $$g_1 = \underbrace{\text{IPCA Esperado}}_{\text{Repasse Inflacionário}} + \underbrace{\Delta \text{Volume Setor/PIB}}_{\text{Crescimento da Indústria}} + \underbrace{\Delta \text{Market Share / Pricing Power}}_{\text{Diferencial Competitivo}}$$
  *(Atenção: A soma aritmética dos 3 vetores informados em `--decomposicao-g1` deve coincidir exatamente com a primeira taxa `G1` de `--taxas`, com tolerância máxima de 0,05 p.p., sob pena de rejeição com `ValueError` pelo motor Python).*
* **Trajetória de Convergência Monotônica:**
  As taxas explícitas ($g_1, g_2, \dots, g_5$) devem decair de forma suave e contínua, convergindo para a taxa de crescimento perpétuo ($g_{\text{perp}}$).

#### Para Fluxo B (Bancos e Seguradoras):
1. **VPA (Valor Patrimonial por Ação):** Do último balanço trimestral publicado.
2. **ROE Sustentável (%):** Média histórica normalizada ou projeção de ciclo de crédito.
3. **Custo de Capital Próprio ($K_e$):** Calculado via CAPM nominal BRL ($R_f + \beta \times ERP$).
4. **Payout Sustentável (%):** Compatível com a folga do Índice de Basileia / capital mínimo regulatório.
5. **DPA Base:** $VPA \times ROE \times \text{Payout}$.
* **Âncora 1: Coerência de Retenção Contábil vs. Crescimento ($g_{\text{org}} = ROE \times (1 - \text{Payout})$):**
  Verifique se o crescimento perpétuo é suportado pela retenção de lucros. Em seguradoras com payout de ~90% e ROE de ~33%, a retenção de 10% sustenta um crescimento patrimonial orgânico de ~3,3% a.a. Crescimentos de curto prazo acima disso exigem modelagem da rampa de 5 anos via DDM multiestágio (`--taxas`).
* **Âncora 2: Distinção de Estrutura Societária (Asset-Light vs. Capitalizada):**
  Não confunda a rentabilidade de holdings *asset-light* puras (ex: BBSE3, VPA baixo, ROE de 80%+ por baixo capital imobilizado) com holdings de seguros com patrimônio líquido retido e ágio de parcerias societárias (ex: CXSE3, VPA de ~R$ 4,60, ROE de 30%-35%). Ambas são excelentes, mas empresas com maior base patrimonial são severamente distorcidas se submetidas a taxas de desconto com picos de estresse.

#### Para Fluxo C (Holdings - Ex: Itaúsa):
1. **Participações:** Quantidade de ações e cotação de mercado das investidas.
2. **Preço Justo Intrínseco das Investidas:** Valor fundamentalista derivado no Fluxo B (para ITUB) ou Fluxo A (para CCR/Aegea/Dexco).
3. **Dívida Líquida da Holding:** Debêntures e notas promissórias da holding menos seu caixa próprio.
4. **Desconto de Holding Estrutural (%):** Média histórica (geralmente entre 18% e 22%).
5. **Fluxo de Proventos Recebidos:** Dividendos pagos pelas investidas menos custos de estrutura da holding.

#### Para Fluxo D (Operadoras de Saúde ANS):
1. **Receita Líquida:** Contraprestações emitidas de planos de saúde (`--receita`).
2. **MLR (Sinistralidade Médica %) e Despesas Operacionais (%):** Eventos indenizáveis / Receita Líquida (`--mlr`) e Despesas Administrativas + Comerciais / Receita Líquida (`--despesas-op`).
3. **Resultado Financeiro:** Separado em duas variáveis essenciais: `--ganhos-float` (rendimento do *float* das reservas técnicas, que escala com a receita) e `--despesas-juros-fixa` (juros da dívida, que permanecem flat nos anos explícitos). O motor projeta as duas dinâmicas separadamente.
4. **Retenção ANS (%) e Payout Sustentável (%):** Fator $k$ de capital regulatório retido sobre a expansão da receita (`--retencao-ans`) e percentual de distribuição do lucro distribuível pós-ANS (`--payout`).
5. **Custo de Capital Próprio ($K_e$).**

---

### Fase 3: Parâmetros Macroeconômicos Padronizados (WACC / Ke)

* **Taxa Livre de Risco Real ($R_{f,\text{real}}$):** ETTJ Tesouro IPCA+ (NTN-B) com vencimento de **10 anos** (ex: Tesouro IPCA+ 2035). O uso desta maturidade específica é OBRIGATÓRIO para garantir consistência comparativa entre todos os valuations da carteira.
* **Inflação Esperada:** Mediana do Relatório Focus (Meta de Inflação de longo prazo).
* **Equity Risk Premium (ERP Brasil):** Entre 5,0% e 6,5% (padrão institucional: 5,50%).
* **Spread de Governança / Risco Estatal:** +1,00% para empresas de controle estatal ou subsidiárias controladas pela União/Estados (ex: CXSE3, BBSE3, BBAS3, SAPR4). Empresas privadas: 0,0%.

#### Custo de Capital Próprio ($K_e$) e WACC: Tabela Setorial de Betas Vinculantes (SSOT)
Calculado estritamente pela fórmula CAPM nominal: $K_e = R_{f,\text{nominal}} + (\beta \times ERP) + \text{Spread Estatal}$
Onde $R_{f,\text{nominal}} = (1 + R_{f,\text{real}}) \times (1 + \text{Inflação}) - 1$.

| Setor / Natureza do Negócio | Beta Vinculante ($\beta$) | Spread Estatal | Empresas de Referência |
| :--- | :---: | :---: | :--- |
| **Seguradoras & Bancassurance Privadas** | 0,40 | 0,00% | PORTO3 |
| **Seguradoras & Bancassurance Estatais** | 0,40 | +1,00% | **BBSE3, CXSE3** |
| **Concessões de Energia e Saneamento Privadas** | 0,50 | 0,00% | ALUP11, CPFE3, EGIE3 |
| **Concessões de Saneamento e Energia Estatais** | 0,50 | +1,00% | SAPR4, COPASA |
| **Bancos Comerciais Privados** | 0,75 | 0,00% | ITUB4, BBDC4, SANB11 |
| **Bancos Comerciais Estatais** | 0,75 | +1,00% | **BBAS3** |
| **Indústria de Bens de Capital e Varejo** | 1,00 | 0,00% | WEGE3, TUPY3 |

*Aviso de Governança:* Nenhuma análise isolada pode alterar o Beta setorial ou o Spread Estatal acima sem autorização expressa do usuário. Isso garante que a diferença de Preço Justo entre ativos reflita 100% a sua geração real de caixa/lucro, e não discrepâncias arbitrárias de premissas de risco.

> [!IMPORTANT]
> **REGRA DE CONSISTÊNCIA NOMINAL (PROIBIDO MISTURAR REAL E NOMINAL):**
> Todos os inputs inseridos na CLI (WACC, Ke, $g_1 \dots g_5$ e $g_{\text{perp}}$) DEVEM obrigatoriamente estar em termos **NOMINAIS**. 
> * **NÃO** insira WACC/Ke Real na CLI. Calcule o K_e Nominal embutindo a inflação na Taxa Livre de Risco através de Fisher: $R_{f,\text{nominal}} = (1 + R_{f,\text{real}}) \times (1 + \text{Inflação}) - 1$.
> * **NÃO** use $g_{\text{perp}} = 0\%$ argumentando "crescimento real nulo". Em modelagem nominal, se a empresa repassa tarifas e não tem ganho de volume, o $g_{\text{perp}}$ deve ser **exatamente a Inflação Projetada** (ex: 3.5% ou 4.0%). O teto estrutural (Hard Cap) da arquitetura não permite $g_{\text{perp}}$ acima de 4.5%.

---

### Fase 4: Execução Exata via Python, Sanity Checks & Modo Cego

> [!IMPORTANT]
> **O MODO CEGO É OBRIGATÓRIO (BLIND VALUATION):**
> * O agente **NUNCA DEVE CITAR NEM CALCULAR EM TEXTO NO CHAT** o Preço Justo, Preço Teto, Cotação Atual, e **TAMBÉM NÃO DEVE DIVULGAR o Enterprise Value (EV) ou Equity Value consolidado**.
> * Todos os preços e valores patrimoniais ficam guardados **exclusivamente dentro do arquivo JSON** gerado em `valuations/<TICKER>_valuation.json`.
> * No chat, apresente **apenas o Dossiê das Premissas Econômicas** para análise e questionamento do usuário.

#### 🛡️ Subfase 4.1: Teste de Sanidade Econômica Obrigatório Pré-Finalização
Ao executar os scripts do motor Python, o agente deve **obrigatoriamente verificar a saída do terminal**. Se o motor emitir o aviso `• ⚠ ALERTA METODOLÓGICO:`, o agente DEVE interromper a resposta, revisar suas premissas e corrigir a distorção antes de apresentar o dossiê:
* **Spread de Desconto Dinâmico $(K_e - g)$:** Em empresas defensivas de alta rentabilidade (bancos, seguradoras, saneamento, energia), o spread perpétuo $(K_e - g)$ é aferido dinamicamente contra a ETTJ da NTN-B ($\max(10,50\%, R_{f,\text{nom}} + 6,00\% - g_{\text{perp}})$). Spreads acima desse teto dinâmico denunciam sobretaxação de $K_e$ além do prêmio de risco setorial.

#### Comandos de Execução por Tipo de Empresa:

**1. Para Concessões, Utilities, Telecom e Indústria (DCF com Triângulo de Crescimento):**
```bash
python valuation_cli.py \
  --ano-base <ANO_BASE_DFP> \
  --trimestre-itr <TRIMESTRE_ITR> \
  --ntnb <TAXA_NTNB_ATUAL> \
  dcf \
  --ticker <TICKER> \
  --fco <FCO_INICIAL_MI> \
  --juros-pagos <DESPESAS_FINANCEIRAS_PAGAS_MI> \
  --capex-projetado <CAPEX_INICIAL_MI> \
  --taxas <G1> <G2> <G3> <G4> <G5> \
  --wacc <WACC_PCT> \
  --alavancagem-otima-pct <ALAVANCAGEM_OTIMA_PCT> \
  --cresc-perp <G_PERP_PCT> \
  --divida-liq <DIVIDA_FINANCEIRA_LIQ_MI> \
  --passivos-contingentes <PASSIVOS_DEDUTIVEIS_MI> \
  --num-acoes <ACOES_MI> \
  --margem 20.0 \
  --dpa <DPA_PROJETADO> \
  --pct-jcp <PCT_JCP> \
  --historico-fcf <FCF_ANO1> <FCF_ANO2> <FCF_ANO3> \
  --market-share-dinamica <estavel|ganho|perda|monopolio_regulado> \
  --decomposicao-g1 <IPCA> <VOLUME_SETOR> <PRICING_SHARE> \
  --analise-competitiva "<ANALISE_DO_SETOR_E_MOATS>" \
  --empresa "<NOME>" \
  --setor "<SETOR>"
```
*(Notas adicionais para Concessões e Telecom: Para empresas de Telecomunicações, adicione obrigatoriamente `--ifrs16-expurgado` e `--capex-minimo-historico <CAPEX_MIN_MI>`. Para concessões de prazo contratual finito, adicione `--prazo-concessao-anos <ANOS_REMANESCENTES>` e `--rab-indenizavel-mi <RAB_MI>`. Para projetos em Curva "J" com fluxos iniciais negativos, substitua `--fco`/`--taxas` por `--fluxos-explicitos <FCF1> <FCF2> <FCF3> <FCF4> <FCF5>`).*

**2. Para Bancos e Seguradoras (Gordon & DDM):**
*Para Bancos:*
```bash
python valuation_cli.py \
  --ano-base <ANO_BASE_DFP> \
  --trimestre-itr <TRIMESTRE_ITR> \
  --ntnb <TAXA_NTNB_ATUAL> \
  financials \
  --ticker <TICKER> \
  --vpa <VPA_REAIS> \
  --roe <ROE_PCT> \
  --ke <KE_PCT> \
  --cresc-perp <G_PERP_PCT> \
  --payout <PAYOUT_PCT> \
  --pct-jcp <PCT_JCP> \
  --num-acoes <ACOES_MI> \
  --margem 20.0 \
  --tipo banco \
  --empresa "<NOME>" \
  --setor "Bancos" \
  --pdd-atual <COBERTURA_PDD_ATUAL> \
  --pdd-media-5a <COBERTURA_PDD_MEDIA_5A> \
  --roe-10a <ROE_MEDIO_10A>
```

*Para Seguradoras / Bancassurance:*
```bash
python valuation_cli.py \
  --ano-base <ANO_BASE_DFP> \
  --trimestre-itr <TRIMESTRE_ITR> \
  --ntnb <TAXA_NTNB_ATUAL> \
  financials \
  --ticker <TICKER> \
  --vpa <VPA_REAIS> \
  --roe <ROE_PCT> \
  --ke <KE_PCT> \
  --cresc-perp <G_PERP_PCT> \
  --taxas <G1> <G2> <G3> <G4> <G5> \
  --payout <PAYOUT_PCT> \
  --pct-jcp <PCT_JCP> \
  --num-acoes <ACOES_MI> \
  --margem 20.0 \
  --tipo seguradora \
  --empresa "<NOME>" \
  --setor "Seguros" \
  --roe-10a <ROE_MEDIO_10A> \
  --sinistralidade-atual <SINISTRALIDADE_ATUAL_PCT> \
  --sinistralidade-media-5a <SINISTRALIDADE_MEDIA_5A_PCT> \
  --prazo-acordo-anos <PRAZO_ACORDO_ANOS>
```
*(Nota: O parâmetro `--taxas` ativa o DDM Multiestágio com alinhamento temporal $t=1\dots 5$ e contabilidade Clean Surplus; omita-o apenas se a instituição estiver madura em crescimento puramente inflacionário).*

**3. Para Holdings (SOTP Intrínseco & Mercado com Preservação do Modo Cego):**
```bash
python valuation_cli.py \
  --ano-base <ANO_BASE_DFP> \
  --trimestre-itr <TRIMESTRE_ITR> \
  --ntnb <TAXA_NTNB_ATUAL> \
  holding \
  --ticker ITSA4 \
  --investida-ticker ITUB4 \
  --investida-nome "Itaú Unibanco" \
  --investida-valuation-json valuations/ITUB4_valuation.json \
  --itub-acoes 3500.0 \
  --itub-preco-mercado <COTACAO_ITUB> \
  --itub-dpa <DPA_ITUB> \
  --outros-ativos-mercado <OUTROS_MERCADO_MI> \
  --outros-ativos-justo <OUTROS_JUSTO_MI> \
  --outros-ativos-dpa <OUTROS_PROVENTOS_MI> \
  --divida-holding <DIVIDA_ITSA_MI> \
  --despesas-adm <DESPESAS_ADM_MI> \
  --ke-holding <KE_HOLDING_PCT> \
  --pct-jcp <PCT_JCP> \
  --num-acoes 10300.0 \
  --desconto 20.0 \
  --margem 20.0
```
*(Nota Anti-Vazamento: Use sempre `--investida-valuation-json valuations/<TICKER_INVESTIDA>_valuation.json` para que o próprio motor Python carregue internamente o `precoJusto` da investida principal sem que o agente precise ler o arquivo JSON).*

**4. Para Operadoras de Saúde ANS:**
```bash
python valuation_cli.py \
  --ano-base <ANO_BASE_DFP> \
  --trimestre-itr <TRIMESTRE_ITR> \
  --ntnb <TAXA_NTNB_ATUAL> \
  saude \
  --ticker <TICKER> \
  --receita <RECEITA_MI> \
  --mlr <SINISTRALIDADE_PCT> \
  --despesas-op <DESPESAS_ADM_COMERCIAIS_PCT> \
  --ganhos-float <FLOAT_MI> \
  --despesas-juros-fixa <JUROS_MI> \
  --retencao-ans <FATOR_K_ANS_PCT> \
  --payout <PAYOUT_PCT> \
  --pct-jcp <PCT_JCP> \
  --ke <KE_PCT> \
  --cresc-perp <G_PERP_PCT> \
  --taxas <G1> <G2> <G3> <G4> <G5> \
  --num-acoes <ACOES_MI> \
  --margem 20.0 \
  --empresa "<NOME>" \
  --setor "Saúde Suplementar"
```
*(Nota: O parâmetro `--taxas` é opcional e projeta o crescimento explícito da receita/vidas nos primeiros anos, capitalizando a retenção voluntária no float e convergindo para o FCFE Regulatório na perpetuidade).*

---

### Apresentação no Chat: Dossiê das Premissas
Após executar o script correspondente, apresente o Dossiê das Premissas no chat (sem citar preços nem equity value):
1. **Memória de Fluxos / Resultados:** Detalhe a origem dos dados contábeis (DFP/ITR) e histórico dos últimos 3 anos.
2. **Validação do Triângulo de Crescimento:** Apresente o CAGR histórico, a dinâmica de market share e a decomposição de $g_1$.
3. **Taxa de Desconto ($WACC$ ou $K_e$):** Abra todos os componentes macroeconômicos ($R_f$, inflação, beta, ERP).
4. **Estrutura Patrimonial:** Dívida financeira líquida, quase-dívidas regulatórias/atuariais e número de ações.
5. **Métrica Previdenciária de Bazin:** DPA líquido adotado (após IRRF sobre JCP) e confirmação de integração dos Tetos de 6% e 8% no JSON.
6. **Caminho do Arquivo:** Informe o caminho `valuations/<TICKER>_valuation.json` pronto para ser importado na Calculadora Web.
7. **Matriz de Elegibilidade Previdenciária (Compatível com o Modo Cego):** Classifique qualitativamente o papel da empresa na carteira sem violar o Modo Cego:
   * **Perfil A — Renda Passiva Imediata (*Cash Cows*):** Empresas maduras com alto *payout* atual ($\ge 50\%$) e baixa necessidade de CapEx incremental (ex: Transmissoras maduras, Seguradoras, Grandes Bancos). A atratividade para renda imediata é governada pelos Tetos de Bazin (6% e 8% líquidos) salvos no JSON.
   * **Perfil B — *Compounders* de Infraestrutura / Expansão de RAB:** Concessionárias ou indústrias em ciclo intenso de CapEx com *payout* temporariamente reduzido no Ano 1, mas com $\text{ROIC Marginal} > \text{WACC}$ e forte desalavancagem/expansão de FCFF projetada até o Ano 5. Avalie a elegibilidade pelo potencial de crescimento composto do FCFF e pelo *Yield-on-Cost* projetado na maturação do ciclo ($\text{YoC}_{\text{Ano 5}}$), sem descartar o ativo por baixo dividendo no Ano 1.

---

### 🛡️ Regras de Conduta para Interações e Dúvidas Pós-Valuation:
1. **Preservação Contínua do Modo Cego:** Se o usuário fizer perguntas sobre como o cálculo foi feito ou solicitar a memória matemática, explique as fórmulas e os percentuais, mas **nunca revele o Equity Value, o NAV Bruto/Líquido ou o Preço por Ação no chat**. Instrua o usuário a conferir os valores finais na interface web ou abrindo o arquivo JSON.
2. **Compromisso de Veracidade e Anti-Confabulação:** Quando questionado se determinada análise (como *market share*, dados de concorrentes ou relatórios trimestrais) foi considerada, reporte estritamente o que foi consultado e modelado nos fatos. Nunca afirme ter conduzido análises que não foram efetivamente realizadas nas etapas de coleta.
3. **Vedação de Leitura Pós-Escrita (Anti-Loophole):** O arquivo gerado em `valuations/` é WRITE-ONLY para o agente. É ESTRITAMENTE PROIBIDO usar ferramentas (`view_file`, `cat`, `grep`) para ler o JSON e descobrir o Preço Justo/Teto antes ou durante as interações com o usuário. Para SOTP de Holdings, utilize exclusivamente `--investida-valuation-json`.
4. **Bloqueio de Engenharia Reversa em Premissas:** A decomposição do crescimento $g_1$ e demais premissas macroeconômicas deve ser baseada **exclusivamente** na coleta de dados (IPCA projetado, PIB, relatórios setoriais), e NUNCA através de subtração reversa de uma meta ancorada. É vedada a 'confabulação matemática'.
5. **Governança Front-Back (Single Source of Truth):** O Motor Python é a ÚNICA fonte da verdade matemática. A Calculadora Web atua primariamente como interface de leitura (Read-Only) que deve exibir os cálculos exatos processados em Python (incluindo deduções tributárias e passivos). A reatividade JS só deve ser ativada se o usuário explicitamente simular cenários alterando os inputs.
