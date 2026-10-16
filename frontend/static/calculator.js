function parseNum(val, def = 0) {
  if (val === undefined || val === null || val === "") return def;
  const num = parseFloat(val);
  return isNaN(num) ? def : num;
}

document.addEventListener("alpine:init", () => {
  Alpine.data("valuationApp", () => ({
    // Estado das Abas e Histórico
    abaAtual: "calculadora",
    salvando: false,
    historico: [],
    filtroApenasRecentes: true,

    // Variáveis da Calculadora
    tickersList: [{ ticker: "VALE3", precoAtual: 62.5 }],
    fclf: 25000,
    anosProjecao: 5,
    taxasCrescimento: [5.0, 5.0, 4.0, 4.0, 3.0],
    wacc: 12.0,
    crescPerp: 2.5,
    dividaLiquida: 35000,
    numAcoes: 4500,
    margemSeguranca: 20,
    ocultarResultados: false,
    precosTempoReal: {},
    modalImportarAberto: false,
    jsonParaImportar: "",
    detalhesValuation: null,
    modeloAtual: "dcf_fcff",
    importedPrecoJusto: null,
    importedPrecoTeto: null,
    parametrosModificados: false,

    // Variáveis Específicas dos Modelos para Reatividade em Tempo Real
    // 1. Gordon & DDM (Bancos e Seguradoras)
    vpa: 20.0,
    roe: 18.0,
    payoutBanco: 50.0,

    // 2. SOTP Holding
    descontoHolding: 20.0,
    despesasAdmHolding: 0.0,
    participacoes: [],

    // 3. Saúde Suplementar ANS
    receitaLiquida: 0.0,
    sinistralidadeMlr: 80.0,
    despesasOpSaude: 10.0,
    retencaoAns: 10.0,
    resultadoFinanceiro: 0.0,
    payoutSaude: 60.0,

    resetarParametrosModelos() {
      this.vpa = 20.0;
      this.roe = 18.0;
      this.payoutBanco = 50.0;
      this.descontoHolding = 20.0;
      this.despesasAdmHolding = 0.0;
      this.participacoes = [];
      this.receitaLiquida = 0.0;
      this.sinistralidadeMlr = 80.0;
      this.despesasOpSaude = 10.0;
      this.retencaoAns = 10.0;
      this.resultadoFinanceiro = 0.0;
      this.payoutSaude = 60.0;
      this.detalhesValuation = null;
      this.importedPrecoJusto = null;
      this.importedPrecoTeto = null;
    },

    mudarModelo(novo) {
      if (novo === this.modeloAtual) return;
      this.modeloAtual = novo;
      // Limpeza de preços congelados e detalhes prévios ao trocar de modelo
      this.importedPrecoJusto = null;
      this.importedPrecoTeto = null;
      this.detalhesValuation = null;
      this.participacoes = [];

      if (novo === "gordon_ddm") {
        this.dividaLiquida = 0;
        if (!this.vpa || this.vpa <= 0) this.vpa = 20.0;
        if (!this.roe || this.roe <= 0) this.roe = 18.0;
        if (this.wacc <= this.crescPerp) this.wacc = 13.0;
      } else if (novo === "sotp_holding") {
        if (this.descontoHolding === undefined || this.descontoHolding === "") this.descontoHolding = 20.0;
      } else if (novo === "saude_ans") {
        if (!this.sinistralidadeMlr) this.sinistralidadeMlr = 80.0;
        if (!this.retencaoAns) this.retencaoAns = 10.0;
        if (this.wacc <= this.crescPerp) this.wacc = 13.0;
      }
    },

    adicionarParticipacao() {
      this.participacoes.push({
        nome: "Nova Investida",
        ticker: "",
        quantidade_acoes_mi: 100.0,
        preco_mercado: 10.0,
        preco_justo_intrinseco: 12.0,
        dpa_esperado: 0.5,
      });
    },

    removerParticipacao(index) {
      if (this.participacoes.length > 0) {
        this.participacoes.splice(index, 1);
      }
    },

    restaurarParametrosDoModelo(det) {
      if (!det) return;
      // Gordon & DDM
      if (det.vpa !== undefined) this.vpa = parseNum(det.vpa, 20);
      if (det.roe_adotado_pct !== undefined) this.roe = parseNum(det.roe_adotado_pct, 18);
      if (det.payout_sustentavel_pct !== undefined) this.payoutBanco = parseNum(det.payout_sustentavel_pct, 50);

      // SOTP Holding
      if (det.desconto_holding_adotado_pct !== undefined) this.descontoHolding = parseNum(det.desconto_holding_adotado_pct, 20);
      if (det.despesas_adm_holding_anual_mi !== undefined) this.despesasAdmHolding = parseNum(det.despesas_adm_holding_anual_mi, 0);
      if (det.participacoes && Array.isArray(det.participacoes)) {
        this.participacoes = JSON.parse(JSON.stringify(det.participacoes));
      }

      // Saúde Suplementar ANS
      if (det.receita_liquida_mi !== undefined) this.receitaLiquida = parseNum(det.receita_liquida_mi, 0);
      if (det.sinistralidade_mlr_pct !== undefined) this.sinistralidadeMlr = parseNum(det.sinistralidade_mlr_pct, 80);
      if (det.despesas_adm_comerciais_pct !== undefined) this.despesasOpSaude = parseNum(det.despesas_adm_comerciais_pct, 10);
      if (det.fator_capital_ans_k_pct !== undefined) this.retencaoAns = parseNum(det.fator_capital_ans_k_pct, 10);
      else if (det.exigencia_capital_ans_pct !== undefined) this.retencaoAns = parseNum(det.exigencia_capital_ans_pct, 10);
      const rfImportado = det.resultado_financeiro_liquido_mi ?? det.resultado_financeiro_float_mi;
      if (rfImportado !== undefined) this.resultadoFinanceiro = parseNum(rfImportado, 0);
      if (det.payout_sustentavel_pct !== undefined && this.modeloAtual === "saude_ans") {
        this.payoutSaude = parseNum(det.payout_sustentavel_pct, 60);
      }
    },

    gerarDetalhesParaSalvar() {
      const base = this.detalhesValuation ? JSON.parse(JSON.stringify(this.detalhesValuation)) : {};
      base.modelo_utilizado = this.modeloAtual;
      const r = parseNum(this.wacc, 12) / 100;
      const g = parseNum(this.crescPerp, 2.5) / 100;

      if (this.modeloAtual === "gordon_ddm") {
        base.vpa = parseNum(this.vpa, 20);
        base.roe_adotado_pct = parseNum(this.roe, 18);
        base.ke_adotado_pct = parseNum(this.wacc, 12);
        base.payout_sustentavel_pct = parseNum(this.payoutBanco, 50);
        const roeDec = base.roe_adotado_pct / 100;
        base.p_vp_justo_gordon = r > g ? parseFloat(Math.max(0, (roeDec - g) / (r - g)).toFixed(3)) : 0;
      } else if (this.modeloAtual === "sotp_holding") {
        base.desconto_holding_adotado_pct = parseNum(this.descontoHolding, 20);
        base.despesas_adm_holding_anual_mi = parseNum(this.despesasAdmHolding, 0);
        base.divida_liquida_holding_mi = parseNum(this.dividaLiquida, 0);
        base.total_intrinseco_bruto_mi = this.resultados.navIntrinsecoBruto;
        base.total_mercado_bruto_mi = this.resultados.navMercadoBruto;
        base.vp_despesas_adm_holding_mi = this.resultados.vpDespesasAdm;
        if (this.participacoes && this.participacoes.length > 0) {
          base.participacoes = this.participacoes;
        }
      } else if (this.modeloAtual === "saude_ans") {
        base.receita_liquida_mi = parseNum(this.receitaLiquida, 0);
        base.sinistralidade_mlr_pct = parseNum(this.sinistralidadeMlr, 80);
        base.despesas_adm_comerciais_pct = parseNum(this.despesasOpSaude, 10);
        base.fator_capital_ans_k_pct = parseNum(this.retencaoAns, 10);
        base.resultado_financeiro_liquido_mi = parseNum(this.resultadoFinanceiro, 0);
        base.resultado_financeiro_float_mi = parseNum(this.resultadoFinanceiro, 0);
        base.retencao_reserva_solvencia_ans_mi = this.resultados.retencaoSolvenciaAns;
        base.divida_liquida_deduzida_mi = 0.0;
      }
      return base;
    },

    importarJSON() {
      try {
        const raw = this.jsonParaImportar.trim();
        if (!raw) {
          alert("Por favor, cole o JSON no campo antes de importar.");
          return;
        }
        const data = JSON.parse(raw);
        this.resetarParametrosModelos();

        if (data.ticker) {
          const preco = data.precoAtual || data.preco_atual || (this.tickersList[0] ? this.tickersList[0].precoAtual : 0);
          this.tickersList = [{ ticker: data.ticker, precoAtual: preco }];
        }
        const fclf = data.fclf !== undefined ? data.fclf : data.fclf_inicial;
        if (fclf !== undefined) this.fclf = parseNum(fclf);

        const anos = data.anosProjecao !== undefined ? data.anosProjecao : data.anos_projecao;
        if (anos !== undefined) this.anosProjecao = parseInt(anos);

        const taxas = data.taxasCrescimento || data.taxas_crescimento;
        if (Array.isArray(taxas)) this.taxasCrescimento = taxas.map(Number);

        if (data.wacc !== undefined) this.wacc = parseNum(data.wacc);

        const crescPerp = data.crescPerp !== undefined ? data.crescPerp : data.cresc_perp;
        if (crescPerp !== undefined) this.crescPerp = parseNum(crescPerp);

        const divida = data.dividaLiquida !== undefined ? data.dividaLiquida : data.divida_liquida;
        if (divida !== undefined) this.dividaLiquida = parseNum(divida);

        const acoes = data.numAcoes !== undefined ? data.numAcoes : data.num_acoes;
        if (acoes !== undefined) this.numAcoes = parseNum(acoes);

        const margem = data.margemSeguranca !== undefined ? data.margemSeguranca : data.margem_seguranca;
        if (margem !== undefined) this.margemSeguranca = parseNum(margem);

        if (data.modelo) {
          this.modeloAtual = data.modelo;
        } else if (data.detalhes?.modelo_utilizado) {
          const mod = data.detalhes.modelo_utilizado.toLowerCase();
          if (mod.includes("gordon") || mod.includes("financeiro")) this.modeloAtual = "gordon_ddm";
          else if (mod.includes("sotp") || mod.includes("holding")) this.modeloAtual = "sotp_holding";
          else if (mod.includes("saúde") || mod.includes("ans")) this.modeloAtual = "saude_ans";
          else this.modeloAtual = "dcf_fcff";
        } else {
          this.modeloAtual = "dcf_fcff";
        }

        this.detalhesValuation = data.detalhes || null;
        if (this.detalhesValuation) {
          this.restaurarParametrosDoModelo(this.detalhesValuation);
        }

        // SSOT: Congelar o resultado rigoroso do Motor Python
        this.importedPrecoJusto = data.precoJusto !== undefined ? parseNum(data.precoJusto) : parseNum(data.preco_justo);
        this.importedPrecoTeto = data.precoTeto !== undefined ? parseNum(data.precoTeto) : parseNum(data.preco_teto);
        this.parametrosModificados = false; 

        this.modalImportarAberto = false;
        this.jsonParaImportar = "";
        if (data.ticker) {
          this.buscarPrecoNaBrapi(0);
        }
      } catch (err) {
        alert("Erro ao ler JSON: " + err.message);
      }
    },

    adicionarTicker() {
      this.tickersList.push({ ticker: "", precoAtual: 0 });
    },

    removerTicker(index) {
      if (this.tickersList.length > 1) this.tickersList.splice(index, 1);
    },

    init() {
      document.addEventListener('input', (e) => {
        this.parametrosModificados = true;
      });
      this.$watch("anosProjecao", (val) => {
        let num = parseInt(val) || 1;
        if (num > 20) num = 20;
        if (num < 1) num = 1;

        const newArray = [...this.taxasCrescimento];
        if (num > newArray.length) {
          const lastRate =
            newArray.length > 0 ? newArray[newArray.length - 1] : 0;
          for (let i = newArray.length; i < num; i++) newArray.push(lastRate);
        } else if (num < newArray.length) {
          newArray.length = num;
        }
        this.taxasCrescimento = newArray;
      });
    },

    mudarAba(aba) {
      this.abaAtual = aba;
      if (aba === "historico") {
        this.carregarHistorico();
      }
    },

    async salvarValuation() {
      if (this.resultados.erro) {
        alert("Corrija os erros matemáticos antes de salvar.");
        return;
      }

      this.salvando = true;
      try {
        const payloadDetalhes = this.gerarDetalhesParaSalvar();
        const saves = this.tickersList.map((t) => {
          const payload = {
            ticker: t.ticker,
            preco_atual: t.precoAtual,
            fclf_inicial: this.fclf,
            anos_projecao: this.anosProjecao,
            taxas_crescimento: this.taxasCrescimento,
            wacc: this.wacc,
            cresc_perp: this.crescPerp,
            divida_liquida: this.dividaLiquida,
            num_acoes: this.numAcoes,
            margem_seguranca: this.margemSeguranca,
            preco_justo: this.resultados.precoJusto,
            preco_teto: this.resultados.precoTeto,
            modelo: this.modeloAtual,
            detalhes: payloadDetalhes,
          };
          return fetch("/valuations", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
          }).then((res) => {
            if (!res.ok) throw new Error(`Erro ao salvar ${t.ticker}`);
          });
        });

        await Promise.all(saves);
        alert(`${this.tickersList.length} valuation(s) salvo(s) com sucesso!`);
      } catch (e) {
        alert(e.message);
      } finally {
        this.salvando = false;
      }
    },

    async carregarHistorico() {
      try {
        const res = await fetch("/valuations");
        if (!res.ok) throw new Error("Erro ao buscar histórico");
        this.historico = await res.json();
        this.historico.reverse(); // Os mais novos ficam no topo
        await this.atualizarPrecosHistorico();
      } catch (e) {
        console.error(e);
      }
    },

    // Função chamada quando o usuário clica na aba de histórico
    async atualizarPrecosHistorico() {
      if (!this.historico || this.historico.length === 0) return;

      const tickersUnicos = [
        ...new Set(this.historico.map((item) => item.ticker)),
      ];

      await Promise.all(
        tickersUnicos.map(async (ticker) => {
          try {
            const resposta = await fetch(`/api/quote/${ticker}`);
            if (resposta.ok) {
              const dados = await resposta.json();
              if (dados.results && dados.results[0]) {
                this.precosTempoReal[ticker] =
                  dados.results[0].regularMarketPrice;
              }
            }
          } catch (erro) {
            console.error(`Erro ao atualizar preço de ${ticker}:`, erro);
          }
        }),
      );
    },

    async excluirValuation(id) {
      if (
        !confirm(
          "Tem certeza que deseja excluir este valuation permanentemente?",
        )
      )
        return;
      try {
        const res = await fetch(`/valuations/${id}`, { method: "DELETE" });
        if (!res.ok) throw new Error("Erro ao excluir o registro.");
        await this.carregarHistorico();
      } catch (e) {
        alert(e.message);
      }
    },

    // Carrega os dados da tabela para o formulário com limpeza de estado completo
    carregarValuationFormulario(item) {
      // Limpeza de estado prévio completo para evitar contaminação
      this.resetarParametrosModelos();

      this.tickersList = [
        { ticker: item.ticker, precoAtual: item.preco_atual },
      ];
      this.fclf = item.fclf_inicial;
      this.anosProjecao = item.anos_projecao;
      this.taxasCrescimento = Array.isArray(item.taxas_crescimento) ? [...item.taxas_crescimento] : [];
      this.wacc = item.wacc;
      this.crescPerp = item.cresc_perp;
      this.dividaLiquida = item.divida_liquida;
      this.numAcoes = item.num_acoes;
      this.margemSeguranca = item.margem_seguranca;
      this.modeloAtual = item.modelo || "dcf_fcff";

      let det = item.detalhes;
      if (typeof det === "string") {
        try { det = JSON.parse(det); } catch (e) { det = null; }
      }
      this.detalhesValuation = det || null;
      if (this.detalhesValuation) {
        this.restaurarParametrosDoModelo(this.detalhesValuation);
      }

      this.importedPrecoJusto = item.preco_justo !== undefined ? parseNum(item.preco_justo) : (item.precoJusto !== undefined ? parseNum(item.precoJusto) : null);
      this.importedPrecoTeto = item.preco_teto !== undefined ? parseNum(item.preco_teto) : (item.precoTeto !== undefined ? parseNum(item.precoTeto) : null);
      this.parametrosModificados = false;

      this.ocultarResultados = false;
      this.mudarAba("calculadora");
    },

    get historicoFiltrado() {
      if (!this.filtroApenasRecentes) return this.historico;

      const tickersVistos = new Set();
      return this.historico.filter((item) => {
        if (tickersVistos.has(item.ticker)) return false;
        tickersVistos.add(item.ticker);
        return true;
      });
    },

    calcularDiferencaTeto(atual, teto) {
      if (!teto || teto === 0) return { texto: "-", cor: "text-slate-500" };
      const diff = atual / teto - 1;
      const percentual = Math.abs(diff * 100).toFixed(2) + "%";
      if (diff < 0) {
        return {
          texto: `${percentual} Abaixo do Teto`,
          cor: "text-emerald-400 font-bold",
        };
      } else {
        return {
          texto: `${percentual} Acima do Teto`,
          cor: "text-red-400 font-bold",
        };
      }
    },

    fazerLogout() {
      fetch("/logout", { method: "POST" }).then(() => {
        window.location.href = "/";
      });
    },

    buscarPrecoNaBrapi(index) {
      const t = this.tickersList[index];
      if (!t || !t.ticker) return;
      fetch(`/api/quote/${t.ticker}`)
        .then((res) => res.json())
        .then((data) => {
          if (
            data.results &&
            data.results.length > 0 &&
            data.results[0].regularMarketPrice
          ) {
            t.precoAtual = data.results[0].regularMarketPrice;
          }
        })
        .catch(() => alert("Erro ao buscar cotação. Verifique o ticker."));
    },

    get resultados() {
      const r = parseNum(this.wacc, 12) / 100;
      const gPerp = parseNum(this.crescPerp, 2.5) / 100;
      const mSeguranca = parseNum(this.margemSeguranca, 20);
      const nAcoes = parseNum(this.numAcoes, 1);
      const dLiquida = parseNum(this.dividaLiquida, 0);

      let erro = null;
      if (r <= gPerp) {
        erro = (this.modeloAtual === "gordon_ddm" || this.modeloAtual === "saude_ans")
          ? "Custo do Capital (Ke) deve ser maior que a Perpetuidade."
          : "WACC deve ser maior que a Perpetuidade.";
      }
      if (nAcoes <= 0) {
        erro = "Número de ações deve ser maior que zero.";
      }

      // Projeções básicas de fluxo (DCF: taxa de crescimento ou Curva J explícita)
      let fluxoAtual = parseNum(this.fclf, 0);
      let somaPV = 0;
      let projecoes = [];

      const hasExplicitJCurve =
        this.modeloAtual === "dcf_fcff" &&
        fluxoAtual <= 0 &&
        Array.isArray(this.detalhesValuation?.projecoes) &&
        this.detalhesValuation.projecoes.length > 0;

      if (hasExplicitJCurve) {
        const expProjs = this.detalhesValuation.projecoes;
        for (let i = 0; i < expProjs.length; i++) {
          const t = i + 1;
          const fcfT = parseNum(expProjs[i].fclf_projetado, 0);
          const gPct = parseNum(expProjs[i].crescimento_pct, 0);
          const pv = r > -1 ? fcfT / Math.pow(1 + r, t) : 0;
          somaPV += pv;
          fluxoAtual = fcfT;
          projecoes.push({
            ano: t,
            g: gPct.toFixed(2),
            fcf: fcfT,
            vp: pv,
          });
        }
      } else {
        for (let i = 1; i <= this.anosProjecao; i++) {
          const g = parseNum(this.taxasCrescimento[i - 1], 0) / 100;
          fluxoAtual = fluxoAtual * (1 + g);
          const pv = r > -1 ? fluxoAtual / Math.pow(1 + r, i) : 0;
          somaPV += pv;
          projecoes.push({
            ano: i,
            g: (g * 100).toFixed(2),
            fcf: fluxoAtual,
            vp: pv,
          });
        }
      }

      const periodoExplicito = projecoes.length || this.anosProjecao;
      let fcfAnoSeguinte = fluxoAtual * (1 + gPerp);
      let valorTerminal = 0;
      const prazoConcessao = this.detalhesValuation?.metadata?.prazo_concessao_anos;
      if (this.modeloAtual === "dcf_fcff" && prazoConcessao !== undefined && prazoConcessao !== null && r > gPerp) {
        const anosRem = Math.max(0, parseInt(prazoConcessao) - periodoExplicito);
        const fatorAnuidade = anosRem > 0 ? (1 - Math.pow((1 + gPerp) / (1 + r), anosRem)) : 0;
        const vtAnuidade = anosRem > 0 ? (fcfAnoSeguinte / (r - gPerp)) * fatorAnuidade : 0;
        const rabMi = parseNum(this.detalhesValuation?.metadata?.rab_indenizavel_mi, 0);
        const vpRabEmT = rabMi > 0 ? rabMi / Math.pow(1 + r, anosRem) : 0;
        valorTerminal = vtAnuidade + vpRabEmT;
      } else {
        valorTerminal = r > gPerp ? fcfAnoSeguinte / (r - gPerp) : 0;
      }
      let vpTerminal = r > -1 ? valorTerminal / Math.pow(1 + r, periodoExplicito) : 0;
      let ev = somaPV + vpTerminal;
      let equity = ev - dLiquida;

      let precoJusto = 0;
      let precoTeto = 0;
      let pVp = 0;
      let navIntrinsecoBruto = 0;
      let navMercadoBruto = 0;
      let vpDesp = 0;
      let retAnsBase = 0;
      let dpaReativo = 0;

      // CÁLCULO REATIVO EM TEMPO REAL CONFORME O MODELO ATUAL
      if (this.modeloAtual === "gordon_ddm") {
        const vpaVal = parseNum(this.vpa, 20);
        const roeVal = parseNum(this.roe, 18) / 100;
        const payoutEfetivo = parseNum(this.payoutBanco, 0) / 100;

        if (vpaVal > 0 && roeVal > 0 && r > gPerp) {
          pVp = Math.max(0, (roeVal - gPerp) / (r - gPerp));
          const precoGordon = pVp * vpaVal;
          // Payout sustentável perpétuo = 1 - g/ROE
          const payoutSust = Math.max(0, Math.min(1, 1 - (gPerp / roeVal)));
          const payoutUsado = payoutEfetivo > 0 ? payoutEfetivo : payoutSust;
          const lpaTeorico = vpaVal * roeVal;
          dpaReativo = lpaTeorico * payoutUsado;

          const hasMultistage = Array.isArray(this.detalhesValuation?.projecoes_dpa) && this.detalhesValuation.projecoes_dpa.length > 0;
          if (hasMultistage && this.anosProjecao > 0) {
            const g1Dec = parseNum(this.taxasCrescimento[0], 0) / 100;
            let dpaAtual = (1 + g1Dec) > 0 ? (dpaReativo / (1 + g1Dec)) : dpaReativo;
            let lpaAtual = (1 + g1Dec) > 0 ? (lpaTeorico / (1 + g1Dec)) : lpaTeorico;
            let somaPvDpa = 0;
            const projecoesDdm = [];
            for (let i = 1; i <= this.anosProjecao; i++) {
              const g = parseNum(this.taxasCrescimento[i - 1], 0) / 100;
              dpaAtual = dpaAtual * (1 + g);
              lpaAtual = lpaAtual * (1 + g);
              const pv = dpaAtual / Math.pow(1 + r, i);
              somaPvDpa += pv;
              projecoesDdm.push({
                ano: i,
                g: (g * 100).toFixed(2),
                fcf: dpaAtual * nAcoes,
                vp: pv * nAcoes,
              });
            }
            const lpaTerm = lpaAtual * (1 + gPerp);
            const dpaTerm = lpaTerm * payoutSust;
            const vtDpa = ( dpaTerm / (r - gPerp) ) / Math.pow(1 + r, this.anosProjecao);
            precoJusto = Math.max(0, somaPvDpa + vtDpa);
            projecoes = projecoesDdm;
          } else {
            precoJusto = precoGordon;
          }
        } else if (nAcoes > 0 && r > gPerp) {
          precoJusto = Math.max(0, ev / nAcoes);
        }
        precoTeto = precoJusto * (1 - mSeguranca / 100);

      } else if (this.modeloAtual === "sotp_holding") {
        const desconto = parseNum(this.descontoHolding, 20) / 100;
        const despAdm = parseNum(this.despesasAdmHolding, 0);
        const tHolding = parseNum(this.detalhesValuation?.aliquota_ir_holding_pct, 0) / 100;
        vpDesp = r > 0.035 ? ((despAdm * (1 - tHolding)) / (r - 0.035)) : 0;

        if (this.participacoes && this.participacoes.length > 0) {
          let proventosCalc = 0;
          this.participacoes.forEach((p) => {
            const qtd = parseNum(p.quantidade_acoes_mi !== undefined ? p.quantidade_acoes_mi : p.quantidade_acoes, 0);
            const pIntr = parseNum(p.preco_justo_intrinseco !== undefined && p.preco_justo_intrinseco !== null && p.preco_justo_intrinseco !== "" ? p.preco_justo_intrinseco : p.preco_mercado, 0);
            const pMerc = parseNum(p.preco_mercado, 0);
            const dpaPart = parseNum(p.dpa_recebido_pela_holding ?? p.dpa_esperado, 0);
            navIntrinsecoBruto += qtd * pIntr;
            navMercadoBruto += qtd * pMerc;
            proventosCalc += qtd * dpaPart;
          });

          const navPreDesp = navIntrinsecoBruto - dLiquida;
          const navIntrinsecoLiquido = navPreDesp - vpDesp;
          const pesoAdm = navPreDesp > 0 ? (vpDesp / navPreDesp) : 0;
          const descontoResidual = Math.max(0, desconto - pesoAdm);
          const precoSemDesconto = nAcoes > 0 ? Math.max(0, navIntrinsecoLiquido / nAcoes) : 0;
          precoJusto = precoSemDesconto * (1 - descontoResidual);

          const proventosBrutos = parseNum(this.fclf, 0) > 0 ? parseNum(this.fclf, 0) : proventosCalc;
          if (proventosBrutos > 0 && nAcoes > 0) {
            const pctJcpHold = parseNum(this.detalhesValuation?.metrica_bazin?.pct_jcp, 0);
            const vazamentoPisCofins = proventosBrutos * (pctJcpHold / 100) * 0.0925;
            const fluxoLiqHolding = Math.max(0, proventosBrutos - despAdm - vazamentoPisCofins);
            dpaReativo = fluxoLiqHolding / nAcoes;
          }
        } else if (nAcoes > 0 && r > gPerp) {
          const navLiq = ev - dLiquida - vpDesp;
          precoJusto = Math.max(0, (navLiq / nAcoes) * (1 - desconto));
        }
        precoTeto = precoJusto * (1 - mSeguranca / 100);

      } else if (this.modeloAtual === "saude_ans") {
        const recBase = parseNum(this.receitaLiquida, 0);
        const mlr = parseNum(this.sinistralidadeMlr, 80) / 100;
        const despOp = parseNum(this.despesasOpSaude, 10) / 100;
        const margemOp = 1.0 - mlr - despOp;
        const rf = parseNum(this.resultadoFinanceiro, 0);
        const kAns = parseNum(this.retencaoAns, 10) / 100;
        const payout = parseNum(this.payoutSaude, 60) / 100;

        if (recBase > 0 && r > gPerp && nAcoes > 0) {
          let recAnt = recBase;
          let somaPvSaude = 0;
          let reservaLivreAcumulada = 0;
          const projecoesSaude = [];

          const rfImportado = parseNum(
            this.detalhesValuation?.resultado_financeiro_liquido_mi ?? this.detalhesValuation?.resultado_financeiro_float_mi,
            rf
          );
          const deltaRf = rf - rfImportado;
          const ganhosFloatBase = this.detalhesValuation?.ganhos_float_mi !== undefined
            ? parseNum(this.detalhesValuation.ganhos_float_mi, 0) + deltaRf
            : rf;
          const jurosBase = this.detalhesValuation?.despesas_juros_fixa_mi !== undefined
            ? parseNum(this.detalhesValuation.despesas_juros_fixa_mi, 0)
            : 0;
          const rfNominalDec = this.detalhesValuation?.rf_nominal_pct !== undefined
            ? parseNum(this.detalhesValuation.rf_nominal_pct, 0) / 100
            : Math.max(0, r - 0.02);

          const gBase = (this.taxasCrescimento && this.taxasCrescimento.length > 0 ? parseNum(this.taxasCrescimento[0], 0) : gPerp * 100) / 100;
          retAnsBase = (1 + gBase) > 0 ? Math.max(0, recBase * (gBase / (1 + gBase))) * kAns : 0;

          for (let i = 1; i <= this.anosProjecao; i++) {
            const g = parseNum(this.taxasCrescimento[i - 1], 0) / 100;
            const recT = recAnt * (1 + g);
            const deltaRecT = Math.max(0, recT - recAnt);
            const retAnsT = deltaRecT * kAns;
            const ganhosFloatOpT = recBase > 0 ? ganhosFloatBase * (recT / recBase) : ganhosFloatBase;
            const rendimentoReservaT = reservaLivreAcumulada * rfNominalDec;
            const rfT = ganhosFloatOpT + rendimentoReservaT - jurosBase;
            const lairT = (recT * margemOp) + rfT;
            const irT = Math.max(0, lairT * 0.34);
            const lucroT = lairT - irT;
            const lucroDistT = Math.max(0, lucroT - retAnsT);
            const provT = lucroDistT * payout;
            reservaLivreAcumulada += lucroDistT * (1 - payout);
            const dpaT = provT / nAcoes;
            const pv = dpaT / Math.pow(1 + r, i);
            somaPvSaude += pv;
            projecoesSaude.push({
              ano: i,
              g: (g * 100).toFixed(2),
              fcf: provT,
              vp: pv * nAcoes,
            });
            recAnt = recT;
          }

          const recTerm = recAnt * (1 + gPerp);
          const deltaRecTerm = Math.max(0, recAnt * gPerp);
          const retAnsTerm = deltaRecTerm * kAns;
          const ganhosFloatOpTerm = recBase > 0 ? ganhosFloatBase * (recTerm / recBase) : ganhosFloatBase;
          const rendimentoReservaTerm = reservaLivreAcumulada * rfNominalDec;
          const jurosTerm = jurosBase * (1 + gPerp);
          const rfTerm = ganhosFloatOpTerm + rendimentoReservaTerm - jurosTerm;
          const lairTerm = (recTerm * margemOp) + rfTerm;
          const irTerm = Math.max(0, lairTerm * 0.34);
          const lucroDistTerm = Math.max(0, lairTerm - irTerm - retAnsTerm);
          const provTerm = lucroDistTerm;
          const dpaTerm = provTerm / nAcoes;
          const valTermDpa = dpaTerm / (r - gPerp);
          const vpTermDpa = valTermDpa / Math.pow(1 + r, this.anosProjecao);

          const equityPerShare = somaPvSaude + vpTermDpa;
          precoJusto = Math.max(0, equityPerShare);
          projecoes = projecoesSaude;

          // DPA sustentável ano base para Bazin
          const lairBase = (recBase * margemOp) + rf;
          const irBase = Math.max(0, lairBase * 0.34);
          const lucroLiqBase = lairBase - irBase;
          const lucroDistBase = Math.max(0, lucroLiqBase - retAnsBase);
          dpaReativo = (lucroDistBase * payout) / nAcoes;
        } else if (nAcoes > 0) {
          precoJusto = Math.max(0, equity / nAcoes);
        }
        precoTeto = precoJusto * (1 - mSeguranca / 100);

      } else {
        // Padrão DCF por FCFF
        precoJusto = nAcoes > 0 ? Math.max(0, equity / nAcoes) : 0;
        precoTeto = precoJusto * (1 - mSeguranca / 100);
      }

      // Preço Teto Bazin e YoC reativo (com retenção de 15% de IRRF sobre JCP)
      const pctJcp = parseNum(this.detalhesValuation?.metrica_bazin?.pct_jcp, 0);
      const aliquotaIrrf = parseNum(this.detalhesValuation?.metrica_bazin?.aliquota_irrf_jcp, 15);
      const fatorLiquidoJcp = 1 - (aliquotaIrrf / 100) * (pctJcp / 100);
      const dpaBazinLiquido = dpaReativo * fatorLiquidoJcp;
      let dpaBazin = dpaBazinLiquido > 0
        ? dpaBazinLiquido
        : parseNum(this.detalhesValuation?.metrica_bazin?.dpa_liquido ?? this.detalhesValuation?.metrica_bazin?.dpa_projetado, 0);
      let yocNoTeto = (dpaBazin > 0 && precoTeto > 0) ? (dpaBazin / precoTeto * 100) : 0;
      let tetoBazin6 = dpaBazin > 0 ? (dpaBazin / 0.06) : 0;
      let tetoBazin8 = dpaBazin > 0 ? (dpaBazin / 0.08) : 0;

      // SSOT DO BACKEND: Sobrescreve a simulação rasa do JS com os cálculos exatos em Python
      // (que incluem tributação JCP, passivos contingentes, Curva J e concessões finitas)
      if (this.parametrosModificados === false && this.importedPrecoJusto !== null) {
        precoJusto = this.importedPrecoJusto;
        precoTeto = this.importedPrecoTeto;
        const det = this.detalhesValuation;
        if (det) {
          if (det.soma_pv_fluxos !== undefined) somaPV = parseNum(det.soma_pv_fluxos, somaPV);
          if (det.fcf_ano_terminal !== undefined) fcfAnoSeguinte = parseNum(det.fcf_ano_terminal, fcfAnoSeguinte);
          if (det.valor_terminal_bruto !== undefined) valorTerminal = parseNum(det.valor_terminal_bruto, valorTerminal);
          if (det.vp_terminal !== undefined) vpTerminal = parseNum(det.vp_terminal, vpTerminal);
          if (det.enterprise_value !== undefined) ev = parseNum(det.enterprise_value, ev);
          if (det.equity_value !== undefined) equity = parseNum(det.equity_value, equity);
          if (det.p_vp_justo_gordon !== undefined) pVp = parseNum(det.p_vp_justo_gordon, pVp);
          if (det.total_intrinseco_bruto_mi !== undefined) navIntrinsecoBruto = parseNum(det.total_intrinseco_bruto_mi, navIntrinsecoBruto);
          if (det.total_mercado_bruto_mi !== undefined) navMercadoBruto = parseNum(det.total_mercado_bruto_mi, navMercadoBruto);
          if (det.vp_despesas_adm_holding_mi !== undefined) vpDesp = parseNum(det.vp_despesas_adm_holding_mi, vpDesp);
          if (det.retencao_reserva_solvencia_ans_mi !== undefined) retAnsBase = parseNum(det.retencao_reserva_solvencia_ans_mi, retAnsBase);
          if (Array.isArray(det.projecoes) && det.projecoes.length > 0) {
            projecoes = det.projecoes.map((p) => ({
              ano: p.ano,
              g: parseNum(p.crescimento_pct, 0).toFixed(2),
              fcf: parseNum(p.fclf_projetado, 0),
              vp: parseNum(p.valor_presente, 0),
            }));
          }
          if (det.metrica_bazin) {
            const mb = det.metrica_bazin;
            dpaBazin = mb.dpa_liquido ?? mb.dpa_projetado ?? dpaBazin;
            tetoBazin6 = mb.preco_teto_bazin_6pct ?? mb.teto_bazin_6pct ?? tetoBazin6;
            tetoBazin8 = mb.preco_teto_bazin_8pct ?? mb.teto_bazin_8pct ?? tetoBazin8;
            yocNoTeto = mb.yield_on_cost_no_preco_teto_modelo ?? mb.yoc_no_teto_modelo_pct ?? yocNoTeto;
          }
        }
      }

      return {
        erro,
        somaPV,
        fcfAnoSeguinte,
        valorTerminal,
        vpTerminal,
        ev,
        equity,
        precoJusto,
        precoTeto,
        projecoes,
        pVpJusto: pVp,
        navIntrinsecoBruto,
        navMercadoBruto,
        vpDespesasAdm: vpDesp,
        retencaoSolvenciaAns: retAnsBase,
        dpaBazin,
        yocNoTeto,
        tetoBazin6,
        tetoBazin8,
      };
    },

    get resultadosList() {
      const base = this.resultados;
      return this.tickersList.map((t) => {
        const precoA = parseNum(t.precoAtual, 0);
        const { precoJusto, precoTeto, erro } = base;

        const margemReal =
          precoTeto > 0 ? ((precoA - precoTeto) / precoTeto) * 100 : 0;

        let status;
        if (precoJusto === 0 || erro) {
          status = {
            texto: "INVIÁVEL",
            cor: "text-red-400",
            bg: "bg-red-900/20",
            border: "border-red-700/50",
          };
        } else if (precoA <= precoTeto) {
          status = {
            texto: "COMPRAR (Abaixo do Teto)",
            cor: "text-emerald-400",
            bg: "bg-emerald-900/20",
            border: "border-emerald-700/50",
          };
        } else if (precoA < precoJusto) {
          status = {
            texto: "COMPRAR (Sem Margem)",
            cor: "text-blue-400",
            bg: "bg-blue-900/20",
            border: "border-blue-700/50",
          };
        } else {
          status = {
            texto: "NÃO COMPRAR (Cara)",
            cor: "text-red-400",
            bg: "bg-red-900/20",
            border: "border-red-700/50",
          };
        }

        return {
          ticker: t.ticker,
          precoAtual: precoA,
          margemReal,
          status,
          precoJusto,
          precoTeto,
          somaPV: base.somaPV,
          valorTerminal: base.valorTerminal,
          vpTerminal: base.vpTerminal,
          ev: base.ev,
          projecoes: base.projecoes,
          erro,
        };
      });
    },

    formatMoney(val) {
      return new Intl.NumberFormat("pt-BR", {
        style: "currency",
        currency: "BRL",
      }).format(val || 0);
    },
    formatNum(val) {
      return new Intl.NumberFormat("pt-BR", {
        maximumFractionDigits: 0,
      }).format(val || 0);
    },
    formatData(isoString) {
      const d = new Date(isoString);
      return (
        d.toLocaleDateString("pt-BR") +
        " " +
        d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })
      );
    },
  }));
});
