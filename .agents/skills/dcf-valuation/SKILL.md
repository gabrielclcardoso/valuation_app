---
name: dcf-valuation
description: Analyzes Brazilian public companies (B3) using Discounted Free Cash Flow to Firm (FCFF / FCLF), following a strict 4-phase blind methodology, and outputs a ready-to-use JSON file for the valuation app.
---

# Valuation por Fluxo de Caixa Descontado (DCF / FCD) para Ações Brasileiras (B3)

Esta skill guia o agente Antigravity na execução completa do processo de Valuation por FCD (9 Passos) para empresas listadas na B3, garantindo rigor contábil, cálculos exatos via Python, proteção contra viés de ancoragem e exportação padronizada em JSON.

---

## 🛑 Fase 0: Triagem de Elegibilidade do Setor

Antes de iniciar qualquer análise, verifique se o modelo FCD (FCFF/WACC) é aplicável:

* **NÃO APLICÁVEL (Rejeitar ou alertar o usuário):**
  * **Setor Financeiro:** Bancos (ITUB, BBDC, BBAS, SANB), Seguradoras/Planos de Saúde (BBSE, CXSE, Bradesco Saúde, PSSA), Corretoras/B3 (B3SA3). *Motivo: A dívida/depósitos/reservas técnicas é a matéria-prima do negócio. Use DDM (Gordon) ou P/VP.*
  * **Eventos Binários:** Biotecnologia pré-clínica, mineradoras/petroleiras juniores em sondagem. *Use Opções Reais.*
  * **Empresas Pré-Lucro / Startups de Queima Acelerada:** SaaS ou e-commerce com FCLF negativo crônico. *Use Múltiplos EV/Sales.*
  * **Holdings Puras:** Itaúsa (ITSA4). *Use Soma das Partes (SOTP).*
  * **Recuperação Judicial Severa:** *Use Liquidação / Net Asset Value.*

* **IDEAL PARA FCD:**
  * Utilidades Públicas (Alupar, Sanepar, CPFL, Engie, Taesa, Sabesp).
  * Telecomunicações (TIM, Telefônica Brasil/Vivo).
  * Indústria e Bens de Capital (WEG, Tupy, Iochpe-Maxion).
  * Logística e Infraestrutura (CCR, Ecorodovias, Santos Brasil, Rumo).
  * Saúde Operacional / Hospitais / Diagnósticos (Rede D'Or, Fleury, Mater Dei).
  * Varejo maduro e Consumo (M. Dias Branco, Ambev, Lojas Renner).

---

## 📋 As 4 Fases de Execução

### Fase 1: Coleta Bruta (Isolando Fatos)

> [!WARNING]
> **REGRA DE ATUALIDADE TEMPORAL (ANTI-DESATUALIZAÇÃO):**
> * **NUNCA chumbe anos passados nas buscas** (ex: NUNCA pesquise termos fixos como `"DFP 2024"` ou `"4T24"`). Modelos de IA possuem forte viés de ancoragem em anos anteriores.
> * **Verifique o ano civil corrente:** Sempre identifique o ano atual antes de pesquisar.
> * **Acesse primeiro a Central de Resultados oficial:**
>   Faça buscas como `site:ri.<empresa>.com.br "Central de Resultados"` ou `site:cvm.gov.br "<empresa>" "DFP"`.
> * **Identifique a última DFP fechada e o último ITR trimestral:**
>   Utilize a DFP do último ano calendário completo publicado (ex: em 2026, use a DFP de 2025). Para **Caixa e Dívida Bruta**, utilize preferencialmente o último balanço trimestral (ITR) disponível para capturar a posição patrimonial mais recente, pois dívidas e caixas sofrem grandes oscilações ao longo do ano.
> * **Prioridade da pasta `reports/`:** Se o usuário colocar um PDF recente na pasta `reports/`, utilize esse documento como fonte primária da verdade.

1. **Documentos Oficiais (DFP / ITR):**
   * Procure por relatórios oficiais na pasta `reports/` ou PDFs baixados do RI da empresa.
   * Extraia via script ou leitura literal (sem estimativas):
     * **Caixa e Equivalentes + Aplicações Financeiras** (posição do trimestre mais recente disponível).
     * **Dívida Bruta Total** (Empréstimos de Curto e Longo Prazo, Debêntures, Financiamentos do último trimestre).
     * **Dívida Líquida** = Dívida Bruta - Caixa *(se Caixa > Dívida, o valor é NEGATIVO)*.
     * **Número Total de Ações / Units emitidas** (em Milhões): Verifique se houve bonificação recente de ações, desdobramento (split) ou cancelamento de ações em tesouraria após a data da última DFP.
     * **FCO (Fluxo de Caixa Operacional)** anual normalizado.
     * **CAPEX** (Adições ao Imobilizado e Intangível). *Atenção: Diferencie CapEx de Manutenção de CapEx de Expansão quando divulgado.*

2. **Parâmetros Macroeconômicos e Financeiros Atuais (Tempo Real):**
   * Taxa do **Tesouro IPCA+ longo** (ex: NTN-B 2035 ou 2045) $\to R_{f,\text{real}}$ (geralmente entre 6.0% e 6.8%).
   * **Expectativa de Inflação IPCA** de longo prazo (meta CMN + Focus, tipicamente 3.5% a 4.0%).
   * **Prêmio de Risco de Mercado (ERP)** para o Brasil (Damodaran atualizado, tipicamente 5.5% a 6.5%).
   * **Beta do Setor / Empresa** ($\beta$) desalavancado e realavancado.
   * **Custo da Dívida ($K_d$ bruto):** Quase toda dívida de empresas brasileiras é pós-fixada (CDI + spread ou IPCA + spread). Calibre o $K_d$ com a taxa Selic/CDI **vigente no momento da análise**, somada ao spread médio de captação reportado no balanço mais recente da empresa. Não use taxas de juros de anos em que a Selic estava em outro patamar de ciclo.

---

### Fase 2: O Presente e o Risco (Isolando a Matemática)
Nunca realize cálculos de WACC ou juros compostos em texto livre. Utilize sempre o script de cálculo embutido.

1. **FCLF Inicial ($FCFF_0$):**
   $$\text{FCLF}_0 = \text{FCO} - \text{CAPEX}_{\text{manutenção}}$$
   *Se o FCLF do último ano foi distorcido por variação pontual de capital de giro, normalize pela média dos últimos 3 anos.*

2. **Estrutura de Capital e WACC (em termos nominais BRL):**
   * $R_{f,\text{nominal}} = (1 + R_{f,\text{real}}) \times (1 + \text{IPCA}) - 1$
   * $K_e = R_{f,\text{nominal}} + \beta \times \text{ERP}$
   * $K_d(\text{líquido}) = K_d \times (1 - T)$, onde $T \approx 34\%$ (alíquota efetiva).
   * $\text{WACC} = \left(\frac{E}{D+E}\right) K_e + \left(\frac{D}{D+E}\right) K_d(\text{líquido})$

---

### Fase 3: O Futuro (Isolando a Narrativa)

> [!IMPORTANT]
> **ÂNCORA TEMPORAL DA PROJEÇÃO ($t=0$ e $t=1$):**
> * **$t=0$ (Ano Base):** É o exercício mais recente já encerrado (última DFP publicada ou LTM).
> * **$t=1$ (Ano 1 da Projeção):** DEVE ser obrigatoriamente o próximo ano fiscal ainda não encerrado. **NUNCA projete como 'Ano 1' um ano que já passou**.
>   * *Exemplo:* Se o valuation ocorre em 2026 com base na DFP de 2025, o **Ano 1 é 2026**, o **Ano 2 é 2027**, etc.
>   * Documente explicitamente na justificativa quais anos civis correspondem aos Anos 1 a 5.

1. **Anos de Projeção:**
   * Padrão: 5 anos de projeção explícita ($t=1 \dots t=5$).
2. **Taxas de Crescimento Anual ($g_1 \dots g_5$):**
   * Baseie-se no cronograma de CAPEX mais recente, novas concessões e revisões tarifárias periódicas definitivas (ex: AGEPAR, ANEEL, ANTT).
   * Crie uma trajetória de desaceleração gradual em direção ao crescimento perpétuo.
3. **Crescimento Perpétuo ($g_{\text{perp}}$):**
   * Deve ser estritamente menor que o WACC ($g_{\text{perp}} < \text{WACC}$).
   * No Brasil (nominal), costuma ficar entre **2.5% e 4.0%** (alinhado ao PIB de longo prazo + inflação).

---

### Fase 4: O Veredito Cego (Blind Valuation) e Dossiê de Premissas

> [!IMPORTANT]
> **REGRA DE OURO (BLIND TOTAL — NUNCA REVELE OU PESQUISE PREÇOS NO CHAT):**
> * O agente **NÃO DEVE** pesquisar ou mencionar a cotação atual de mercado da ação.
> * O agente **NÃO DEVE** divulgar no chat o Preço Justo calculado, o Preço Teto ou qualquer veredito de compra/venda (ex: 'COMPRAR', 'BARATA').
> * **Objetivo:** Permitir que o usuário analise, questione e valide as premissas econômicas (WACC, FCLF, Crescimento, Dívida) de forma 100% isenta, sem qualquer viés de ancoragem no preço final ou na cotação de mercado.
> * **Onde fica o preço?** O Preço Justo e Preço Teto calculados ficam salvos **estritamente dentro do arquivo JSON** gerado em `valuations/<TICKER>_valuation.json`, para serem revelados na Calculadora Web apenas quando o usuário importar o arquivo.

1. **Executar o Script de Cálculo:**
   Execute o script `.agents/skills/dcf-valuation/scripts/calc_dcf.py` passando os parâmetros coletados:
   ```bash
   python3 .agents/skills/dcf-valuation/scripts/calc_dcf.py \
     --ticker <TICKER> \
     --fclf <VALOR_MI> \
     --taxas <G1> <G2> <G3> <G4> <G5> \
     --wacc <WACC_PCT> \
     --cresc-perp <G_PERP_PCT> \
     --divida-liq <DIVIDA_LIQ_MI> \
     --num-acoes <ACOES_MI> \
     --margem <MARGEM_SEGURANCA_PCT> \
     --empresa "<NOME_EMPRESA>" \
     --setor "<SETOR>" \
     --justificativa "<RESUMO_DAS_PREMISSAS>"
   ```

2. **Formato do JSON Gerado:**
   O script salvará o arquivo em `valuations/<TICKER>_valuation.json`, pronto para ser utilizado ou importado na aplicação:
   ```json
   {
     "ticker": "SAPR4",
     "fclf": 1850.5,
     "anosProjecao": 5,
     "taxasCrescimento": [6.0, 5.5, 5.0, 4.5, 4.0],
     "wacc": 11.8,
     "crescPerp": 3.0,
     "dividaLiquida": 1784.6,
     "numAcoes": 1511.21,
     "margemSeguranca": 20.0,
     "precoJusto": 14.42,
     "precoTeto": 11.54,
     "detalhes": {
       "soma_pv_fluxos": 7770.47,
       "enterprise_value": 23595.04,
       "equity_value": 19095.04,
       "projecoes": [ ... ],
       "metadata": { ... }
     }
   }
   ```

3. **Apresentação Obrigatória no Chat (Dossiê das Premissas para Análise do Usuário):**
   Ao finalizar a execução, o agente deve apresentar **exclusivamente o Dossiê das Premissas e seus fundamentos**, convidando o usuário a questioná-las antes de importar:
   * **1. Fluxo de Caixa Livre Inicial ($FCFF_0$):** Apresentar o valor adotado (em R$ Mi) e detalhar a memória contábil (FCO bruto menos CapEx de manutenção, explicando se houve ajuste por universalização/expansão ou normalização de capital de giro).
   * **2. Dívida Líquida e Caixa:** Informar o valor líquido adotado (em R$ Mi), detalhando a data-base do balanço (trimestre/ano), Caixa bruto e Dívida bruta.
   * **3. Base Acionária:** Número de ações/Units consideradas e se houve evento societário recente (bonificação/desdobramento).
   * **4. Custo de Capital (WACC Nominal):** Detalhar todos os blocos: taxa livre de risco ($R_{f,\text{real}}$ e nominal), inflação esperada, Beta adotado, ERP Brasil, custo da dívida ($K_d$ bruto e líquido pós-IR) e a proporção de capital próprio vs. terceiros.
   * **5. Trajetória de Crescimento ($g_1 \dots g_5$ e $g_{\text{perp}}$):** Justificar os percentuais ano a ano com base no plano de investimentos, concessões, expansão e capacidade operacional da empresa.
   * **Conclusão:** Informar o caminho do arquivo JSON gerado (`valuations/<TICKER>_valuation.json`) para que o usuário possa importá-lo na Calculadora Web assim que aprovar as premissas.

---

## 🎯 Regras Específicas do Mercado Brasileiro (B3)

1. **Ações do Tipo "UNIT" (ex: ALUP11, SAPR11, KLBN11, TAEE11):**
   * Units são pacotes de ações (ex: SAPR11 = 1 ON + 4 PN).
   * Certifique-se de que o campo `numAcoes` reflita o **total de Units equivalentes**, e não a soma bruta de ONs e PNs individuais, para que o Preço Justo coincida diretamente com a cotação da Unit negociada.
2. **Caixa Líquido (Dívida Líquida Negativa):**
   * Se a empresa tiver mais caixa que dívida (ex: WEG, Odontoprev), informe `--divida-liq` com valor negativo (ex: `-1500.0`).
3. **Moeda e Inflação:**
   * Mantenha WACC e Crescimento na mesma base: ambos **nominais** ou ambos **reais**. O padrão da ferramenta é **Nominal BRL**.
4. **Atualização da Posição de Dívida Líquida (Último Trimestre / ITR):**
   * Enquanto os fluxos de caixa (FCO, CapEx, D&A) e receita devem ser analisados em base anual completa (DFP ou LTM 12 meses acumulados), a **Dívida Líquida (Caixa e Dívida Bruta)** deve refletir a foto mais recente possível (do último ITR trimestral publicado), evitando carregar dívidas quitadas ou desatualizadas de exercícios passados.
5. **Checklist Obrigatório de Recência Pré-Cálculo:**
   Antes de executar o `calc_dcf.py`, o agente deve verificar se todos os pontos abaixo foram atendidos:
   * [x] **Data Corrente Identificada:** O ano civil atual foi considerado; nenhuma busca com anos passados fixos foi executada.
   * [x] **Dívida & Caixa Recentes:** A Dívida Líquida reflete o balanço mais recente publicado (último ITR ou DFP).
   * [x] **Horizonte de Projeção ($t=1$):** O Ano 1 é um ano futuro/vigente; nenhum ano que já se encerrou foi projetado.
   * [x] **Custo da Dívida ($K_d$):** Foi calibrado com a taxa Selic/CDI vigente no mercado atual.
   * [x] **Base Acionária Atual:** Foi verificado se ocorreram desdobramentos, bonificações ou cancelamento de ações recentes.
