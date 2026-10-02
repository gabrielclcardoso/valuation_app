#!/usr/bin/env python3
"""Helper script to calculate DCF (Fluxo de Caixa Descontado) for Brazilian stocks
and output the standardized JSON for the valuation app, supporting pension/dividend
investor metrics (Bazin, regulatory debt adjustments, and scenario analysis).
Delegates core calculations to valuation_engine.dcf for clean maintainability.
"""

import argparse
import sys
from pathlib import Path

# Adiciona a raiz do projeto ao sys.path para importação do valuation_engine
def find_project_root() -> Path:
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "valuation_engine").exists() or (parent / "pyproject.toml").exists():
            return parent
    return Path.cwd()

PROJECT_ROOT = find_project_root()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from valuation_engine.dcf import calculate_dcf, calculate_wacc
from valuation_engine.export import save_valuation_json, print_dossier_summary


def main():
    parser = argparse.ArgumentParser(description="Calcular Valuation DCF e Métricas Previdenciárias para o App")
    parser.add_argument("--ticker", required=True, help="Ticker da ação (ex: SAPR4, CPFE3, TIMS3)")
    parser.add_argument("--fclf", type=float, required=True, help="FCLF inicial em R$ Milhões")
    parser.add_argument(
        "--taxas",
        type=float,
        nargs="+",
        required=True,
        help="Taxas de crescimento anual em percentual (ex: 6.0 5.5 5.0 4.5 4.0)",
    )
    parser.add_argument("--wacc", type=float, required=True, help="Taxa WACC em percentual (ex: 11.8)")
    parser.add_argument("--cresc-perp", type=float, required=True, help="Crescimento na perpetuidade (ex: 3.0)")
    parser.add_argument("--divida-liq", type=float, required=True, help="Dívida Líquida Financeira em R$ Milhões")
    parser.add_argument(
        "--outros-passivos",
        type=float,
        default=0.0,
        help="Outros passivos/quase-dívidas em R$ Milhões (passivos regulatórios, déficits atuariais, contingências prováveis)",
    )
    parser.add_argument("--num-acoes", type=float, required=True, help="Total de ações em Milhões (ou total de Units)")
    parser.add_argument("--margem", type=float, default=20.0, help="Margem de segurança desejada em %% (padrão: 20)")
    parser.add_argument(
        "--dpa",
        type=float,
        default=0.0,
        help="Dividendo por Ação anual esperado em regime permanente (para cálculo do Preço Teto Bazin)",
    )
    parser.add_argument("--out", help="Caminho do arquivo JSON de saída (padrão: valuations/<ticker>_valuation.json)")
    parser.add_argument("--empresa", default="", help="Nome da empresa")
    parser.add_argument("--setor", default="", help="Setor de atuação")
    parser.add_argument("--justificativa", default="", help="Resumo das premissas")

    args = parser.parse_args()

    meta = {}
    if args.justificativa:
        meta["justificativa"] = args.justificativa

    resultado = calculate_dcf(
        ticker=args.ticker,
        fclf_inicial=args.fclf,
        taxas_crescimento=args.taxas,
        wacc=args.wacc,
        cresc_perp=args.cresc_perp,
        divida_liquida=args.divida_liq,
        num_acoes=args.num_acoes,
        outros_passivos=args.outros_passivos,
        margem_seguranca=args.margem,
        dpa_projetado=args.dpa,
        empresa=args.empresa,
        setor=args.setor,
        metadata=meta,
    )

    out_file = save_valuation_json(resultado, args.out)
    print_dossier_summary(resultado, out_file)


if __name__ == "__main__":
    main()
