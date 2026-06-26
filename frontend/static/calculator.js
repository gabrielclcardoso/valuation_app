// frontend/static/calculator.js

document.addEventListener("alpine:init", () => {
  Alpine.data("valuationApp", () => ({
    // Estado das Abas e Histórico
    abaAtual: "calculadora",
    salvando: false,
    historico: [],
    filtroApenasRecentes: true, // Novo: Controla o filtro da tabela (Padrão: Mostra o último de cada)

    // Variáveis da Calculadora
    ticker: "VALE3",
    precoAtual: 62.5,
    fclf: 25000,
    anosProjecao: 5,
    taxasCrescimento: [5.0, 5.0, 4.0, 4.0, 3.0],
    wacc: 12.0,
    crescPerp: 2.5,
    dividaLiquida: 35000,
    numAcoes: 4500,
    margemSeguranca: 20,
    ocultarResultados: false,

    init() {
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
        const payload = {
          ticker: this.ticker,
          preco_atual: this.precoAtual,
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
        };

        const res = await fetch("/valuations", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });

        if (!res.ok) throw new Error("Erro ao salvar no banco de dados");

        alert("Valuation salvo com sucesso!");
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
      } catch (e) {
        console.error(e);
      }
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

    // NOVA FUNÇÃO: Carrega os dados da tabela para o formulário
    carregarValuationFormulario(item) {
      this.ticker = item.ticker;
      this.precoAtual = item.preco_atual;
      this.fclf = item.fclf_inicial;
      this.anosProjecao = item.anos_projecao;
      this.taxasCrescimento = [...item.taxas_crescimento]; // Usa espalhamento para clonar o array
      this.wacc = item.wacc;
      this.crescPerp = item.cresc_perp;
      this.dividaLiquida = item.divida_liquida;
      this.numAcoes = item.num_acoes;
      this.margemSeguranca = item.margem_seguranca;

      this.ocultarResultados = false; // Garante que você verá o resultado
      this.mudarAba("calculadora"); // Troca a tela
    },

    // NOVO GETTER: Filtra a tabela inteligentemente
    get historicoFiltrado() {
      if (!this.filtroApenasRecentes) return this.historico;

      // Como o histórico já está invertido (do mais novo pro mais velho),
      // se guardarmos os Tickers que já vimos num "Set", só o mais recente passa.
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

    buscarPrecoNaBrapi() {
      if (!this.ticker) return;
      fetch(`/api/quote/${this.ticker}`)
        .then((res) => res.json())
        .then((data) => {
          if (
            data.results &&
            data.results.length > 0 &&
            data.results[0].regularMarketPrice
          ) {
            this.precoAtual = data.results[0].regularMarketPrice;
          }
        })
        .catch((err) => alert("Erro ao buscar cotação. Verifique o ticker."));
    },

    get resultados() {
      const r = (parseFloat(this.wacc) || 0) / 100;
      const gPerp = (parseFloat(this.crescPerp) || 0) / 100;

      let erro = null;
      if (r <= gPerp) erro = "WACC deve ser maior que a Perpetuidade.";

      let fluxoAtual = parseFloat(this.fclf) || 0;
      let somaPV = 0;
      let projecoes = [];

      for (let i = 1; i <= this.anosProjecao; i++) {
        const g = (parseFloat(this.taxasCrescimento[i - 1]) || 0) / 100;
        fluxoAtual = fluxoAtual * (1 + g);
        const pv = fluxoAtual / Math.pow(1 + r, i);
        somaPV += pv;
        projecoes.push({
          ano: i,
          g: (g * 100).toFixed(2),
          fcf: fluxoAtual,
          vp: pv,
        });
      }

      const fcfAnoSeguinte = fluxoAtual * (1 + gPerp);
      const valorTerminal = r > gPerp ? fcfAnoSeguinte / (r - gPerp) : 0;
      const vpTerminal = valorTerminal / Math.pow(1 + r, this.anosProjecao);

      const ev = somaPV + vpTerminal;
      const dLiquida = parseFloat(this.dividaLiquida) || 0;
      const nAcoes = parseFloat(this.numAcoes) || 0;
      const equity = ev - dLiquida;

      const precoJusto = nAcoes > 0 ? Math.max(0, equity / nAcoes) : 0;
      const mSeguranca = parseFloat(this.margemSeguranca) || 0;
      const precoTeto = precoJusto * (1 - mSeguranca / 100);

      let status = {
        texto: "AGUARDAR",
        cor: "text-amber-400",
        bg: "bg-amber-900/20",
        border: "border-amber-700/50",
      };
      const precoA = parseFloat(this.precoAtual) || 0;

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
        status,
      };
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
