#!/usr/bin/env python3
"""CLI Unificado para Valuation Fundamentalista de Ações Brasileiras (B3).
Suporta:
- route: Triagem e recomendação de metodologia para qualquer ação
- dcf: DCF por FCFF (Concessões, Saneamento, Energia, Indústria, Hospitais)
- financials: Gordon Growth & DDM (Bancos e Seguradoras)
- holding: SOTP a Valor Intrínseco & Mercado (Holdings)
- saude: DDM Regulatório ANS (Operadoras de Saúde)
"""

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from valuation_engine import (
    calculate_dcf,
    calculate_financials_ddm,
    calculate_sotp_holding,
    calculate_operadora_saude,
    route_company,
    save_valuation_json,
    print_dossier_summary,
)


def main():
    parser = argparse.ArgumentParser(description="Valuation Engine B3 - CLI Unificado")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # 1. ROUTE
    route_p = subparsers.add_parser("route", help="Identificar metodologia adequada para o ticker ou setor")
    route_p.add_argument("--ticker", required=True, help="Ticker da ação (ex: SAPR4, ITUB4, ITSA4, SAUD3)")
    route_p.add_argument("--setor", default="", help="Setor da empresa (opcional)")

    # 2. DCF
    dcf_p = subparsers.add_parser("dcf", help="Valuation DCF por FCFF / WACC")
    dcf_p.add_argument("--ticker", required=True)
    dcf_p.add_argument("--fclf", type=float, default=None)
    dcf_p.add_argument("--ebitda-al", type=float, default=None)
    dcf_p.add_argument("--capex-projetado", type=float, default=None)
    dcf_p.add_argument("--taxas", type=float, nargs="+", required=True)
    dcf_p.add_argument("--wacc", type=float, required=True)
    dcf_p.add_argument("--cresc-perp", type=float, required=True)
    dcf_p.add_argument("--divida-liq", type=float, required=True)
    dcf_p.add_argument("--outros-passivos", type=float, default=0.0)
    dcf_p.add_argument("--passivos-contingentes", type=float, default=0.0)
    dcf_p.add_argument("--passivos-regulatorios", type=float, default=None)
    dcf_p.add_argument("--aliquota-ir", type=float, default=34.0)
    dcf_p.add_argument("--quase-divida-dedutivel", action="store_true", default=False)
    dcf_p.add_argument("--num-acoes", type=float, required=True)
    dcf_p.add_argument("--margem", type=float, default=20.0)
    dcf_p.add_argument("--dpa", type=float, default=0.0)
    dcf_p.add_argument("--pct-jcp", type=float, default=0.0)
    dcf_p.add_argument("--empresa", default="")
    dcf_p.add_argument("--setor", default="")
    dcf_p.add_argument("--historico-fcf", type=float, nargs="+", default=None, help="Histórico de FCF dos últimos anos (ex: 3700 4600 5300)")
    dcf_p.add_argument("--cagr-historico", type=float, default=None, help="CAGR histórico de referência para teste de coerência (%%)")
    dcf_p.add_argument("--market-share-dinamica", choices=["estavel", "ganho", "perda", "monopolio_regulado"], default=None, help="Dinâmica esperada de market share")
    dcf_p.add_argument("--decomposicao-g1", type=float, nargs=3, metavar=("IPCA", "VOLUME", "PRICING"), default=None, help="Decomposição da taxa g1 em 3 vetores: IPCA Volume Share/Pricing")
    dcf_p.add_argument("--analise-competitiva", default="", help="Racional competitivo ou tese de mercado")
    dcf_p.add_argument("--justificativa", default="")
    dcf_p.add_argument("--capex-minimo-historico", type=float, default=None, help="Parâmetro Telecom: Força queda do preço-teto (aumentando margem de segurança) caso o risco de queima de caixa seja muito alto")
    dcf_p.add_argument("--ifrs16-expurgado", action="store_true", default=False, help="Parâmetro Telecom: Confirma que o passivo de arrendamento IFRS 16 foi expurgado da dívida para não penalizar em duplicidade")
    dcf_p.add_argument("--teto-crescimento-oligopolio", type=float, default=None, help="Parâmetro Telecom: Força teto máximo para a taxa inicial G1 em mercados oligopolizados")
    dcf_p.add_argument("--out")

    # 3. FINANCIALS
    fin_p = subparsers.add_parser("financials", help="Valuation de Bancos e Seguradoras via Gordon e DDM")
    fin_p.add_argument("--ticker", required=True)
    fin_p.add_argument("--vpa", type=float, required=True)
    fin_p.add_argument("--roe", type=float, required=True)
    fin_p.add_argument("--ke", type=float, required=True)
    fin_p.add_argument("--cresc-perp", type=float, required=True)
    fin_p.add_argument("--payout", type=float, default=50.0)
    fin_p.add_argument("--dpa", type=float, default=None)
    fin_p.add_argument("--taxas", type=float, nargs="*", default=None)
    fin_p.add_argument("--num-acoes", type=float, required=True)
    fin_p.add_argument("--margem", type=float, default=20.0)
    fin_p.add_argument("--pct-jcp", type=float, default=0.0)
    fin_p.add_argument("--tipo", choices=["banco", "seguradora"], default="banco")
    fin_p.add_argument("--empresa", default="")
    fin_p.add_argument("--setor", default="")
    fin_p.add_argument("--justificativa", default="")
    fin_p.add_argument("--out")
    fin_p.add_argument("--ntnb", type=float, default=None, help="Taxa da NTN-B para Ke Floor")
    fin_p.add_argument("--pdd-atual", type=float, default=None, help="Índice de Cobertura de PDD / NPL Atual")
    fin_p.add_argument("--pdd-media-5a", type=float, default=None, help="Índice de Cobertura de PDD / NPL Média 5 anos")
    fin_p.add_argument("--roe-10a", type=float, default=None, help="ROE médio histórico de 10 anos para Cap")
    fin_p.add_argument("--sinistralidade-atual", type=float, default=None, help="Sinistralidade atual (Apenas Seguradoras)")
    fin_p.add_argument("--sinistralidade-media-5a", type=float, default=None, help="Sinistralidade média de 5 anos (Apenas Seguradoras)")
    fin_p.add_argument("--prazo-acordo-anos", type=float, default=None, help="Prazo restante do acordo de balcão bancassurance em anos (Apenas Seguradoras)")

    # 4. HOLDING
    hld_p = subparsers.add_parser("holding", help="Valuation SOTP para Holdings (ex: Itaúsa)")
    hld_p.add_argument("--ticker", default="ITSA4")
    hld_p.add_argument("--divida-holding", type=float, required=True)
    hld_p.add_argument("--num-acoes", type=float, required=True)
    hld_p.add_argument("--desconto", type=float, default=20.0)
    hld_p.add_argument("--margem", type=float, default=20.0)
    hld_p.add_argument("--dpa", type=float, default=None)
    hld_p.add_argument("--despesas-adm", type=float, default=0.0)
    hld_p.add_argument("--ke-holding", type=float, default=12.0)
    hld_p.add_argument("--pct-jcp", type=float, default=0.0)
    hld_p.add_argument("--participacoes-json")
    hld_p.add_argument("--itub-acoes", type=float, default=0.0)
    hld_p.add_argument("--itub-preco-mercado", type=float, default=0.0)
    hld_p.add_argument("--itub-preco-justo", type=float, default=0.0)
    hld_p.add_argument("--itub-dpa", type=float, default=0.0)
    hld_p.add_argument("--outros-ativos-mercado", type=float, default=0.0)
    hld_p.add_argument("--outros-ativos-justo", type=float, default=0.0)
    hld_p.add_argument("--outros-ativos-dpa", type=float, default=0.0)
    hld_p.add_argument("--empresa", default="Itaúsa")
    hld_p.add_argument("--setor", default="Holding")
    hld_p.add_argument("--justificativa", default="")
    hld_p.add_argument("--out")

    # 5. SAUDE
    sau_p = subparsers.add_parser("saude", help="Valuation de Operadoras de Saúde ANS")
    sau_p.add_argument("--ticker", required=True)
    sau_p.add_argument("--receita", type=float, required=True)
    sau_p.add_argument("--mlr", type=float, required=True)
    sau_p.add_argument("--despesas-op", type=float, default=12.0)
    sau_p.add_argument("--res-financeiro", type=float, default=0.0)
    sau_p.add_argument("--aliquota-ir", type=float, default=34.0)
    sau_p.add_argument("--retencao-ans", type=float, default=10.0)
    sau_p.add_argument("--payout", type=float, default=60.0)
    sau_p.add_argument("--ke", type=float, required=True)
    sau_p.add_argument("--cresc-perp", type=float, required=True)
    sau_p.add_argument("--taxas", type=float, nargs="*", default=None)
    sau_p.add_argument("--num-acoes", type=float, required=True)
    sau_p.add_argument("--divida-liq", type=float, default=0.0)
    sau_p.add_argument("--margem", type=float, default=20.0)
    sau_p.add_argument("--pct-jcp", type=float, default=0.0)
    sau_p.add_argument("--empresa", default="")
    sau_p.add_argument("--setor", default="Saúde Suplementar")
    sau_p.add_argument("--justificativa", default="")
    sau_p.add_argument("--out")

    args = parser.parse_args()

    if args.command == "route":
        res = route_company(ticker=args.ticker, setor=args.setor)
        print("\n" + "=" * 60)
        print(f" TRIAGEM METODOLÓGICA: {res['ticker']}")
        print("=" * 60)
        print(f"• Modelo Recomendado: {res['modelo_recomendado'].upper()}")
        print(f"• Metodologia: {res['metodologia']}")
        print(f"• Script Dedicado: .agents/skills/dcf-valuation/scripts/{res['script']}")
        print(f"• Fundamento: {res['justificativa']}")
        print("=" * 60 + "\n")
        return

    meta = {}
    if getattr(args, "justificativa", None):
        meta["justificativa"] = args.justificativa

    if args.command == "dcf":
        if args.fclf is None and (args.ebitda_al is None or args.capex_projetado is None):
            parser.error("É necessário informar --fclf OU (--ebitda-al E --capex-projetado) no modelo DCF.")
        if args.fclf is not None and (args.ebitda_al is not None or args.capex_projetado is not None):
            parser.error("Informe --fclf OU (--ebitda-al E --capex-projetado), não ambos.")

        resultado = calculate_dcf(
            ticker=args.ticker,
            fclf_inicial=args.fclf,
            taxas_crescimento=args.taxas,
            wacc=args.wacc,
            cresc_perp=args.cresc_perp,
            divida_liquida=args.divida_liq,
            num_acoes=args.num_acoes,
            outros_passivos=args.outros_passivos,
            passivos_contingentes=args.passivos_contingentes,
            passivos_regulatorios=args.passivos_regulatorios,
            aliquota_ir_csll=args.aliquota_ir,
            quase_divida_dedutivel=args.quase_divida_dedutivel,
            margem_seguranca=args.margem,
            dpa_projetado=args.dpa,
            pct_jcp=args.pct_jcp,
            historico_fcf=args.historico_fcf,
            cagr_historico=args.cagr_historico,
            market_share_dinamica=args.market_share_dinamica,
            decomposicao_g1=args.decomposicao_g1,
            analise_competitiva=args.analise_competitiva,
            empresa=args.empresa,
            setor=args.setor,
            metadata=meta,
            capex_minimo_historico=args.capex_minimo_historico,
            ifrs16_expurgado=args.ifrs16_expurgado,
            teto_crescimento_oligopolio=args.teto_crescimento_oligopolio,
            ebitda_al=args.ebitda_al,
            capex_projetado=args.capex_projetado,
        )
    elif args.command == "financials":
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
            pct_jcp=args.pct_jcp,
            tipo=args.tipo,
            empresa=args.empresa,
            setor=args.setor,
            metadata=meta,
            ntnb=args.ntnb,
            pdd_atual=args.pdd_atual,
            pdd_media_5a=args.pdd_media_5a,
            roe_10a=args.roe_10a,
            sinistralidade_atual=args.sinistralidade_atual,
            sinistralidade_media_5a=args.sinistralidade_media_5a,
            prazo_acordo_anos=args.prazo_acordo_anos,
        )
    elif args.command == "holding":
        import json

        participacoes = []
        if args.participacoes_json:
            with open(args.participacoes_json, "r", encoding="utf-8") as f:
                participacoes = json.load(f)
        else:
            if args.itub_acoes > 0:
                participacoes.append({
                    "nome": "Itaú Unibanco",
                    "ticker": "ITUB4",
                    "quantidade_acoes": args.itub_acoes,
                    "preco_mercado": args.itub_preco_mercado,
                    "preco_justo_intrinseco": args.itub_preco_justo if args.itub_preco_justo > 0 else None,
                    "dpa_esperado": args.itub_dpa,
                })
            if args.outros_ativos_mercado > 0 or args.outros_ativos_justo > 0:
                participacoes.append({
                    "nome": "Demais Controladas (CCR, Aegea, Dexco, Copa Energia)",
                    "ticker": "OUTRAS",
                    "quantidade_acoes": 1.0,
                    "preco_mercado": args.outros_ativos_mercado,
                    "preco_justo_intrinseco": args.outros_ativos_justo if args.outros_ativos_justo > 0 else None,
                    "dpa_esperado": args.outros_ativos_dpa,
                })
        resultado = calculate_sotp_holding(
            ticker=args.ticker,
            participacoes=participacoes,
            divida_liquida_holding=args.divida_holding,
            num_acoes_holding=args.num_acoes,
            desconto_holding_adotado_pct=args.desconto,
            margem_seguranca=args.margem,
            dpa_projetado_holding=args.dpa,
            despesas_adm_holding=args.despesas_adm,
            ke_holding=args.ke_holding,
            pct_jcp=args.pct_jcp,
            empresa=args.empresa,
            setor=args.setor,
            metadata=meta,
        )
    elif args.command == "saude":
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
            divida_liquida=args.divida_liq,
            margem_seguranca=args.margem,
            taxas_crescimento_receita=args.taxas,
            pct_jcp=args.pct_jcp,
            empresa=args.empresa,
            setor=args.setor,
            metadata=meta,
        )

    out_file = save_valuation_json(resultado, args.out)
    print_dossier_summary(resultado, out_file)


if __name__ == "__main__":
    main()
