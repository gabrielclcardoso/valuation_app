#!/usr/bin/env python3
"""Helper script para Valuation de Holdings (ex: Itaúsa - ITSA4)
utilizando SOTP (Sum of the Parts / Soma das Partes) a Valor Intrínseco e a Valor de Mercado,
dedução de dívida própria da holding e aplicação de Desconto Estrutural de Holding.
"""

import argparse
import json
import sys
from pathlib import Path


def find_project_root() -> Path:
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "valuation_engine").exists() or (parent / "pyproject.toml").exists():
            return parent
    return Path.cwd()


PROJECT_ROOT = find_project_root()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from valuation_engine.sotp import calculate_sotp_holding
from valuation_engine.export import save_valuation_json, print_dossier_summary


def main():
    parser = argparse.ArgumentParser(
        description="Calcular Valuation SOTP (Soma das Partes) para Holdings"
    )
    parser.add_argument("--ticker", default="ITSA4", help="Ticker da holding (padrão: ITSA4)")
    parser.add_argument("--divida-holding", type=float, required=True, help="Dívida Líquida exclusiva da Holding em R$ Mi")
    parser.add_argument("--num-acoes", type=float, required=True, help="Total de ações emitidas pela Holding em Milhões")
    parser.add_argument("--desconto", type=float, default=20.0, help="Desconto de Holding adotado em %% (padrão: 20)")
    parser.add_argument("--margem", type=float, default=20.0, help="Margem de segurança desejada em %% (padrão: 20)")
    parser.add_argument("--dpa", type=float, default=None, help="DPA anual projetado da própria holding (opcional)")
    parser.add_argument("--despesas-adm", type=float, default=150.0, help="Despesas operacionais da holding em R$ Mi (padrão: 150)")
    parser.add_argument("--participacoes-json", help="Caminho de arquivo JSON contendo lista detalhada de participações")

    # Atalhos para Itaúsa / Holdings com participação âncora
    parser.add_argument("--itub-acoes", type=float, default=0.0, help="Quantidade de ações ITUB detidas pela Itaúsa (em Milhões)")
    parser.add_argument("--itub-preco-mercado", type=float, default=0.0, help="Cotação de mercado atual de ITUB na B3 (R$)")
    parser.add_argument("--itub-preco-justo", type=float, default=0.0, help="Preço justo fundamentalista de ITUB via Gordon/DDM (R$)")
    parser.add_argument("--itub-dpa", type=float, default=0.0, help="DPA esperado de ITUB repassado à Itaúsa (R$)")
    parser.add_argument("--outros-ativos-mercado", type=float, default=0.0, help="Valor de mercado das outras investidas (CCR, Aegea, Dexco, Copa) em R$ Mi")
    parser.add_argument("--outros-ativos-justo", type=float, default=0.0, help="Valor justo intrínseco das outras investidas em R$ Mi")
    parser.add_argument("--outros-ativos-dpa", type=float, default=0.0, help="Proventos anuais recebidos das outras investidas em R$ Mi")

    parser.add_argument("--empresa", default="Itaúsa", help="Nome da empresa")
    parser.add_argument("--setor", default="Holding Financeira", help="Setor")
    parser.add_argument("--justificativa", default="", help="Resumo das premissas")
    parser.add_argument("--out", help="Caminho do arquivo JSON de saída (padrão: valuations/<ticker>_valuation.json)")

    args = parser.parse_args()

    participacoes = []
    if args.participacoes_json:
        with open(args.participacoes_json, "r", encoding="utf-8") as f:
            participacoes = json.load(f)
    else:
        # Se usou os atalhos de ITUB + Outros
        if args.itub_acoes > 0:
            participacoes.append({
                "nome": "Itaú Unibanco",
                "ticker": "ITUB4",
                "quantidade_acoes": args.itub_acoes,
                "preco_mercado": args.itub_preco_mercado,
                "preco_justo_intrinseco": args.itub_preco_justo if args.itub_preco_justo > 0 else args.itub_preco_mercado,
                "dpa_esperado": args.itub_dpa,
            })
        if args.outros_ativos_mercado > 0 or args.outros_ativos_justo > 0:
            participacoes.append({
                "nome": "Demais Controladas (CCR, Aegea, Dexco, Copa Energia)",
                "ticker": "OUTRAS",
                "quantidade_acoes": 1.0,
                "preco_mercado": args.outros_ativos_mercado,
                "preco_justo_intrinseco": args.outros_ativos_justo if args.outros_ativos_justo > 0 else args.outros_ativos_mercado,
                "dpa_esperado": args.outros_ativos_dpa,
            })

    if not participacoes:
        parser.error("Informe as participações via --participacoes-json ou via flags (--itub-acoes, etc.)")

    meta = {}
    if args.justificativa:
        meta["justificativa"] = args.justificativa

    resultado = calculate_sotp_holding(
        ticker=args.ticker,
        participacoes=participacoes,
        divida_liquida_holding=args.divida_holding,
        num_acoes_holding=args.num_acoes,
        desconto_holding_adotado_pct=args.desconto,
        margem_seguranca=args.margem,
        dpa_projetado_holding=args.dpa,
        despesas_adm_holding=args.despesas_adm,
        empresa=args.empresa,
        setor=args.setor,
        metadata=meta,
    )

    out_file = save_valuation_json(resultado, args.out)
    print_dossier_summary(resultado, out_file)


if __name__ == "__main__":
    main()
