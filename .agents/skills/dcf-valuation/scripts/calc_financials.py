#!/usr/bin/env python3
"""Helper script para Valuation de Instituições Financeiras (Bancos e Seguradoras na B3)
utilizando Gordon Growth (ROE vs Ke / P/VP Justo) e DDM (Dividend Discount Model).
Exemplos: ITUB4, BBAS3, BBDC4, SANB11, BBSE3, CXSE3.
"""

import argparse
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

from valuation_engine.ddm import calculate_financials_ddm
from valuation_engine.export import save_valuation_json, print_dossier_summary


def main():
    parser = argparse.ArgumentParser(
        description="Calcular Valuation de Bancos e Seguradoras via Gordon e DDM"
    )
    parser.add_argument("--ticker", required=True, help="Ticker da ação (ex: ITUB4, BBAS3, CXSE3)")
    parser.add_argument("--vpa", type=float, required=True, help="Valor Patrimonial por Ação em R$")
    parser.add_argument("--roe", type=float, required=True, help="ROE sustentável estimado em %% (ex: 20.0)")
    parser.add_argument("--ke", type=float, required=True, help="Custo de Capital Próprio Ke em %% (ex: 13.5)")
    parser.add_argument("--cresc-perp", type=float, required=True, help="Crescimento na perpetuidade em %% (ex: 4.5)")
    parser.add_argument("--payout", type=float, default=50.0, help="Payout médio sustentável em %% (padrão: 50)")
    parser.add_argument("--dpa", type=float, default=None, help="DPA anual projetado em R$ (opcional, calculado via VPA*ROE*Payout se omitido)")
    parser.add_argument("--taxas", type=float, nargs="*", default=None, help="Trajetória de crescimento do dividendo em %% (ex: 7.0 6.0 5.0)")
    parser.add_argument("--num-acoes", type=float, required=True, help="Total de ações em Milhões")
    parser.add_argument("--margem", type=float, default=20.0, help="Margem de segurança desejada em %% (padrão: 20)")
    parser.add_argument("--tipo", choices=["banco", "seguradora"], default="banco", help="Tipo de instituição (padrão: banco)")
    parser.add_argument("--empresa", default="", help="Nome da instituição")
    parser.add_argument("--setor", default="", help="Setor")
    parser.add_argument("--justificativa", default="", help="Resumo das premissas")
    parser.add_argument("--out", help="Caminho do arquivo JSON de saída (padrão: valuations/<ticker>_valuation.json)")

    args = parser.parse_args()

    meta = {}
    if args.justificativa:
        meta["justificativa"] = args.justificativa

    resultado = calculate_financials_ddm(
        ticker=args.ticker,
        vpa=args.vpa,
        roe=args.roe,
        ke=args.ke,
        cresc_perp=args.cresc_perp,
        payout=args.payout,
        dpa_projetado=args.dpa,
        taxas_crescimento_dpa=args.taxas,
        num_acoes=args.num_acoes,
        margem_seguranca=args.margem,
        tipo=args.tipo,
        empresa=args.empresa,
        setor=args.setor,
        metadata=meta,
    )

    out_file = save_valuation_json(resultado, args.out)
    print_dossier_summary(resultado, out_file)


if __name__ == "__main__":
    main()
