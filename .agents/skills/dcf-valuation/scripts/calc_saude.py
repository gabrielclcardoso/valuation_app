#!/usr/bin/env python3
"""Helper script para Valuation de Operadoras de Planos de Saúde (ex: BradSaúde/SAUD3, Hapvida, Odontoprev)
sujeitas à regulação da ANS, com Provisões Técnicas, Sinistralidade (MLR) e Margem de Solvência.
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

from valuation_engine.saude import calculate_operadora_saude
from valuation_engine.export import save_valuation_json, print_dossier_summary


def main():
    parser = argparse.ArgumentParser(
        description="Calcular Valuation para Operadoras de Planos de Saúde (ANS)"
    )
    parser.add_argument("--ticker", required=True, help="Ticker da operadora (ex: SAUD3, HAPV3, ODPV3)")
    parser.add_argument("--receita", type=float, required=True, help="Receita Líquida anual (contraprestações) em R$ Mi")
    parser.add_argument("--mlr", type=float, required=True, help="Sinistralidade médica (Eventos / Receita Líquida) em %% (ex: 80.0)")
    parser.add_argument("--despesas-op", type=float, default=12.0, help="Despesas administrativas e comerciais sobre receita em %% (padrão: 12.0)")
    parser.add_argument("--res-financeiro", type=float, default=0.0, help="Resultado financeiro das reservas técnicas / float em R$ Mi")
    parser.add_argument("--aliquota-ir", type=float, default=34.0, help="Alíquota efetiva de IR/CSLL em %% (padrão: 34.0)")
    parser.add_argument("--retencao-ans", type=float, default=10.0, help="Retenção de lucro para margem de solvência ANS em %% (padrão: 10.0)")
    parser.add_argument("--payout", type=float, default=60.0, help="Payout dos lucros distribuíveis em %% (padrão: 60.0)")
    parser.add_argument("--ke", type=float, required=True, help="Custo de Capital Próprio Ke em %% (ex: 13.5)")
    parser.add_argument("--cresc-perp", type=float, required=True, help="Crescimento na perpetuidade em %% (ex: 3.5)")
    parser.add_argument("--taxas", type=float, nargs="*", default=None, help="Trajetória de crescimento anual da receita em %% (ex: 6.0 5.5 5.0)")
    parser.add_argument("--num-acoes", type=float, required=True, help="Total de ações em Milhões")
    parser.add_argument("--margem", type=float, default=20.0, help="Margem de segurança desejada em %% (padrão: 20)")
    parser.add_argument("--empresa", default="", help="Nome da operadora")
    parser.add_argument("--setor", default="Saúde Suplementar", help="Setor")
    parser.add_argument("--justificativa", default="", help="Resumo das premissas")
    parser.add_argument("--out", help="Caminho do arquivo JSON de saída (padrão: valuations/<ticker>_valuation.json)")

    args = parser.parse_args()

    meta = {}
    if args.justificativa:
        meta["justificativa"] = args.justificativa

    resultado = calculate_operadora_saude(
        ticker=args.ticker,
        receita_liquida=args.receita,
        sinistralidade_mlr_pct=args.mlr,
        despesas_adm_comerciais_pct=args.despesas_op,
        resultado_financeiro=args.res_financeiro,
        aliquota_ir_csll_pct=args.aliquota_ir,
        exigencia_capital_ans_pct=args.retencao_ans,
        payout_sustentavel_pct=args.payout,
        ke=args.ke,
        cresc_perp=args.cresc_perp,
        num_acoes=args.num_acoes,
        margem_seguranca=args.margem,
        taxas_crescimento_receita=args.taxas,
        empresa=args.empresa,
        setor=args.setor,
        metadata=meta,
    )

    out_file = save_valuation_json(resultado, args.out)
    print_dossier_summary(resultado, out_file)


if __name__ == "__main__":
    main()
