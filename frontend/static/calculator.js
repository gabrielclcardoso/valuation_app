// frontend/calculadora.js

document.addEventListener('alpine:init', () => {
	Alpine.data('valuationApp', () => ({
		ticker: 'VALE3',
		precoAtual: 62.50,
		fclf: 25000,
		anosProjecao: 5,
		taxasCrescimento: [5.0, 5.0, 4.0, 4.0, 3.0],
		wacc: 12.0,
		crescPerp: 2.5,
		dividaLiquida: 35000,
		numAcoes: 4500,
		margemSeguranca: 20,
		ocultarResultados: false,
		brapiToken: '',

		init() {
			this.$watch('anosProjecao', (val) => {
				let num = parseInt(val) || 1;
				if (num > 20) num = 20;
				if (num < 1) num = 1;

				const newArray = [...this.taxasCrescimento];
				if (num > newArray.length) {
					const lastRate = newArray.length > 0 ? newArray[newArray.length - 1] : 0;
					for (let i = newArray.length; i < num; i++) newArray.push(lastRate);
				} else if (num < newArray.length) {
					newArray.length = num;
				}
				this.taxasCrescimento = newArray;
			});
		},

		fazerLogout() {
			fetch('/logout', { method: 'POST' }).then(() => {
				window.location.href = '/';
			});
		},

		buscarPrecoNaBrapi() {
			if (!this.brapiToken || !this.ticker) return;
			fetch(`https://brapi.dev/api/quote/${this.ticker}?token=${this.brapiToken}`)
				.then(res => res.json())
				.then(data => {
					if (data.results && data.results.length > 0 && data.results[0].regularMarketPrice) {
						this.precoAtual = data.results[0].regularMarketPrice;
					}
				});
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
				projecoes.push({ ano: i, g: (g * 100).toFixed(2), fcf: fluxoAtual, vp: pv });
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
			const precoTeto = precoJusto * (1 - (mSeguranca / 100));

			let status = { texto: 'AGUARDAR', cor: 'text-amber-400', bg: 'bg-amber-900/20', border: 'border-amber-700/50' };
			const precoA = parseFloat(this.precoAtual) || 0;

			if (precoJusto === 0 || erro) {
				status = { texto: 'INVIÁVEL', cor: 'text-red-400', bg: 'bg-red-900/20', border: 'border-red-700/50' };
			} else if (precoA <= precoTeto) {
				status = { texto: 'COMPRAR (Abaixo do Teto)', cor: 'text-emerald-400', bg: 'bg-emerald-900/20', border: 'border-emerald-700/50' };
			} else if (precoA < precoJusto) {
				status = { texto: 'COMPRAR (Sem Margem)', cor: 'text-blue-400', bg: 'bg-blue-900/20', border: 'border-blue-700/50' };
			} else {
				status = { texto: 'NÃO COMPRAR (Cara)', cor: 'text-red-400', bg: 'bg-red-900/20', border: 'border-red-700/50' };
			}

			return { erro, somaPV, fcfAnoSeguinte, valorTerminal, vpTerminal, ev, equity, precoJusto, precoTeto, projecoes, status };
		},

		formatMoney(val) { return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(val || 0); },
		formatNum(val) { return new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 0 }).format(val || 0); }
	}));
});
