#!/usr/bin/env python3
"""
Helper script to calculate DCF (Fluxo de Caixa Descontado) for Brazilian stocks
and output the standardized JSON for the valuation app.
"""

import argparse
import json
import os
import sys


def calculate_wacc(rf_real, ipca, beta, erp, kd_bruto, alíquota_ir, equity_ratio):
    """
    Calcula o WACC nominal em BRL.
    rf_nominal = (1 + rf_real) * (1 + ipca) - 1
    ke = rf_nominal + beta * erp
    kd_liquido = kd_bruto * (1 - alíquota_ir)
    wacc = ke * equity_ratio + kd_liquido * (1 - equity_ratio)
    """
    rf_nom = ((1 + rf_real / 100) * (1 + ipca / 100) - 1) * 100
    ke = rf_nom + (beta * erp)
    kd_liq = kd_bruto * (1 - alíquota_ir / 100)
    debt_ratio = 1.0 - equity_ratio
    wacc = (ke * equity_ratio) + (kd_liq * debt_ratio)
    return {
        "rf_real": rf_real,
        "ipca_esperado": ipca,
        "rf_nominal": round(rf_nom, 2),
        "beta": round(beta, 2),
        "erp": round(erp, 2),
        "ke": round(ke, 2),
        "kd_bruto": round(kd_bruto, 2),
        "aliquota_ir": round(alíquota_ir, 2),
        "kd_liquido": round(kd_liq, 2),
        "equity_ratio": round(equity_ratio, 2),
        "debt_ratio": round(debt_ratio, 2),
        "wacc": round(wacc, 2),
    }


def calculate_dcf(
    ticker: str,
    fclf_inicial: float,
    taxas_crescimento: list,
    wacc: float,
    cresc_perp: float,
    divida_liquida: float,
    num_acoes: float,
    margem_seguranca: float = 20.0,
    metadata: dict = None,
    output_path: str = None,
):
    r = wacc / 100.0
    g_perp = cresc_perp / 100.0

    if r <= g_perp:
        raise ValueError(
            f"Erro Matemático: WACC ({wacc}%) deve ser estritamente maior que o Crescimento Perpétuo ({cresc_perp}%)."
        )

    if num_acoes <= 0:
        raise ValueError("Número de ações deve ser maior que zero.")

    fluxo_atual = float(fclf_inicial)
    soma_pv = 0.0
    projecoes = []

    for i, taxa in enumerate(taxas_crescimento, start=1):
        g = float(taxa) / 100.0
        fluxo_atual = fluxo_atual * (1.0 + g)
        pv = fluxo_atual / ((1.0 + r) ** i)
        soma_pv += pv
        projecoes.append(
            {
                "ano": i,
                "crescimento_pct": round(taxa, 2),
                "fclf_projetado": round(fluxo_atual, 2),
                "valor_presente": round(pv, 2),
            }
        )

    fcf_terminal = fluxo_atual * (1.0 + g_perp)
    valor_terminal = fcf_terminal / (r - g_perp)
    anos_projecao = len(taxas_crescimento)
    vp_terminal = valor_terminal / ((1.0 + r) ** anos_projecao)

    enterprise_value = soma_pv + vp_terminal
    equity_value = enterprise_value - float(divida_liquida)

    preco_justo = max(0.0, equity_value / float(num_acoes))
    preco_teto = preco_justo * (1.0 - (float(margem_seguranca) / 100.0))

    resultado = {
        "ticker": ticker.upper(),
        "fclf": round(float(fclf_inicial), 2),
        "anosProjecao": anos_projecao,
        "taxasCrescimento": [round(float(t), 2) for t in taxas_crescimento],
        "wacc": round(float(wacc), 2),
        "crescPerp": round(float(cresc_perp), 2),
        "dividaLiquida": round(float(divida_liquida), 2),
        "numAcoes": round(float(num_acoes), 2),
        "margemSeguranca": round(float(margem_seguranca), 2),
        "precoJusto": round(preco_justo, 2),
        "precoTeto": round(preco_teto, 2),
        "detalhes": {
            "soma_pv_fluxos": round(soma_pv, 2),
            "fcf_ano_terminal": round(fcf_terminal, 2),
            "valor_terminal_bruto": round(valor_terminal, 2),
            "vp_terminal": round(vp_terminal, 2),
            "enterprise_value": round(enterprise_value, 2),
            "equity_value": round(equity_value, 2),
            "projecoes": projecoes,
            "metadata": metadata or {},
        },
    }

    if not output_path:
        os.makedirs("valuations", exist_ok=True)
        output_path = f"valuations/{ticker.upper()}_valuation.json"

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(resultado, f, indent=2, ensure_ascii=False)

    return resultado, output_path


def main():
    parser = argparse.ArgumentParser(description="Calcular Valuation DCF e gerar JSON para o App")
    parser.add_argument("--ticker", required=True, help="Ticker da ação (ex: SAPR11, CPFE3)")
    parser.add_argument("--fclf", type=float, required=True, help="FCLF inicial em R$ Milhões")
    parser.add_argument(
        "--taxas",
        type=float,
        nargs="+",
        required=True,
        help="Taxas de crescimento anual em percentual (ex: 6.0 5.5 5.0 4.5 4.0)",
    )
    parser.add_argument("--wacc", type=float, required=True, help="Taxa WACC em percentual (ex: 11.5)")
    parser.add_argument("--cresc-perp", type=float, required=True, help="Crescimento na perpetuidade (ex: 3.0)")
    parser.add_argument("--divida-liq", type=float, required=True, help="Dívida Líquida em R$ Milhões (negativo se caixa líquido)")
    parser.add_argument("--num-acoes", type=float, required=True, help="Total de ações em Milhões (ou total de Units)")
    parser.add_argument("--margem", type=float, default=20.0, help="Margem de segurança desejada em %% (padrão: 20)")
    parser.add_argument("--out", help="Caminho do arquivo JSON de saída (padrão: valuations/<ticker>_valuation.json)")
    parser.add_argument("--empresa", default="", help="Nome da empresa")
    parser.add_argument("--setor", default="", help="Setor de atuação")
    parser.add_argument("--justificativa", default="", help="Justificativa das premissas")

    args = parser.parse_args()

    meta = {
        "empresa": args.empresa,
        "setor": args.setor,
        "justificativa": args.justificativa,
    }

    resultado, path = calculate_dcf(
        ticker=args.ticker,
        fclf_inicial=args.fclf,
        taxas_crescimento=args.taxas,
        wacc=args.wacc,
        cresc_perp=args.cresc_perp,
        divida_liquida=args.divida_liq,
        num_acoes=args.num_acoes,
        margem_seguranca=args.margem,
        metadata=meta,
        output_path=args.out,
    )

    print(f"\n=======================================================")
    print(f" VALUATION DCF: PARÂMETROS REGISTRADOS: {resultado['ticker']}")
    print(f"=======================================================")
    print(f"• FCLF Inicial: R$ {resultado['fclf']:,.2f} Mi")
    print(f"• WACC Nominal: {resultado['wacc']:.2f}% a.a.")
    print(f"• Trajetória de Crescimento (5 anos): {resultado['taxasCrescimento']}")
    print(f"• Crescimento Perpétuo (g_perp): {resultado['crescPerp']:.2f}% a.a.")
    print(f"• Dívida Líquida Adotada: R$ {resultado['dividaLiquida']:,.2f} Mi")
    print(f"• Base Acionária: {resultado['numAcoes']:,.2f} Mi ações/Units")
    print(f"• Margem de Segurança: {resultado['margemSeguranca']:.1f}%")
    print(f"• Arquivo JSON salvo com sucesso em: {path}")
    print(f"  [Preço Justo e Preço Teto preservados no JSON para revelação na Calculadora]")
    print(f"=======================================================\n")


if __name__ == "__main__":
    main()
