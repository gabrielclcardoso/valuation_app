"""Testes unitários automatizados para o Valuation Engine da B3 usando unittest padrão.
Garante a integridade matemática, estabilidade e facilidade de manutenção futura sem depender de pacotes externos.
"""
import unittest
from valuation_engine import (
    calculate_bazin,
    calculate_dcf,
    calculate_financials_ddm,
    calculate_sotp_holding,
    calculate_operadora_saude,
    route_company,
)


class TestValuationEngine(unittest.TestCase):
    def test_bazin_metrics(self):
        # DPA de R$ 0.60 com preço teto do modelo a R$ 8.00
        res = calculate_bazin(dpa=0.60, preco_teto_modelo=8.00)
        self.assertIsNotNone(res)
        self.assertEqual(res["dpa_projetado"], 0.60)
        self.assertEqual(res["preco_teto_bazin_6pct"], 10.00)  # 0.60 / 0.06
        self.assertEqual(res["preco_teto_bazin_8pct"], 7.50)   # 0.60 / 0.08
        self.assertEqual(res["yield_on_cost_no_preco_teto_modelo"], 7.50)  # (0.60 / 8.00) * 100

        # DPA nulo ou negativo deve retornar None
        self.assertIsNone(calculate_bazin(dpa=0.0, preco_teto_modelo=10.0))
        self.assertIsNone(calculate_bazin(dpa=-1.0, preco_teto_modelo=10.0))

    def test_dcf_with_quasi_debt_scenarios(self):
        res = calculate_dcf(
            ticker="SAPR4",
            fclf_inicial=600.0,
            taxas_crescimento=[6.0, 5.0, 4.0],
            wacc=12.0,
            cresc_perp=3.0,
            divida_liquida=2000.0,
            outros_passivos=1000.0,
            num_acoes=1000.0,
            margem_seguranca=20.0,
            dpa_projetado=0.50,
        )
        self.assertEqual(res["ticker"], "SAPR4")
        self.assertEqual(res["modelo"], "dcf_fcff")
        self.assertEqual(res["dividaLiquida"], 3000.0)  # 2000 fin + 1000 regulatorio
        self.assertGreater(res["precoJusto"], 0)
        self.assertLess(res["precoTeto"], res["precoJusto"])

        # Cenários
        cenarios = res["detalhes"]["cenarios"]
        self.assertGreater(
            cenarios["cenario_base"]["preco_justo"],
            cenarios["cenario_ajustado"]["preco_justo"],
        )
        self.assertEqual(res["precoJusto"], cenarios["cenario_ajustado"]["preco_justo"])

    def test_dcf_invalid_wacc(self):
        with self.assertRaises(ValueError):
            calculate_dcf(
                ticker="TEST",
                fclf_inicial=100.0,
                taxas_crescimento=[5.0],
                wacc=3.0,
                cresc_perp=3.0,
                divida_liquida=0.0,
                num_acoes=10.0,
            )

    def test_financials_ddm_bank(self):
        res = calculate_financials_ddm(
            ticker="ITUB4",
            vpa=20.0,
            roe=20.0,
            ke=13.0,
            cresc_perp=4.0,
            payout=50.0,
            num_acoes=9000.0,
            margem_seguranca=20.0,
        )
        self.assertEqual(res["ticker"], "ITUB4")
        self.assertEqual(res["modelo"], "gordon_ddm")
        self.assertEqual(res["dividaLiquida"], 0.0)  # Dívida bancária não é deduzida do Equity
        self.assertGreater(res["precoJusto"], 0)
        self.assertEqual(res["precoTeto"], round(res["precoJusto"] * 0.8, 2))
        # Gordon P/VP = (20 - 4) / (13 - 4) = 16 / 9 = 1.778
        p_vp = res["detalhes"]["p_vp_justo_gordon"]
        self.assertEqual(round(p_vp, 2), 1.78)

    def test_sotp_holding_protects_against_overvalued_subsidiary(self):
        # Cenário: Itaú na bolsa está inflado (R$ 40), mas seu valor intrínseco real é R$ 25
        participacoes = [
            {
                "nome": "Itaú Unibanco",
                "ticker": "ITUB4",
                "quantidade_acoes": 1000.0,
                "preco_mercado": 40.0,
                "preco_justo_intrinseco": 25.0,
                "dpa_esperado": 2.0,
            }
        ]
        res = calculate_sotp_holding(
            ticker="ITSA4",
            participacoes=participacoes,
            divida_liquida_holding=2000.0,
            num_acoes_holding=2000.0,
            desconto_holding_adotado_pct=20.0,
            margem_seguranca=20.0,
        )
        cenarios = res["detalhes"]["cenarios"]
        preco_mercado = cenarios["sotp_mercado"]["preco_com_desconto"]
        preco_intrinseco = cenarios["sotp_intrinseco"]["preco_com_desconto"]

        # O preço justo oficial adotado pelo modelo DEVE ser o intrínseco conservador,
        # impedindo que o investidor compre a holding pelo preço inflado da investida!
        self.assertLess(preco_intrinseco, preco_mercado)
        self.assertEqual(res["precoJusto"], preco_intrinseco)

    def test_operadora_saude_ans(self):
        res = calculate_operadora_saude(
            ticker="SAUD3",
            receita_liquida=1000.0,
            sinistralidade_mlr_pct=80.0,
            despesas_adm_comerciais_pct=10.0,
            resultado_financeiro=30.0,
            ke=13.0,
            cresc_perp=3.5,
            num_acoes=100.0,
        )
        self.assertEqual(res["ticker"], "SAUD3")
        self.assertEqual(res["modelo"], "saude_ans")
        self.assertGreater(res["precoJusto"], 0)
        self.assertGreater(res["detalhes"]["retencao_reserva_solvencia_ans_mi"], 0)

    def test_router_coverage(self):
        self.assertEqual(route_company("ITUB4")["modelo_recomendado"], "financials")
        self.assertEqual(route_company("BBSE3")["modelo_recomendado"], "financials")
        self.assertEqual(route_company("ITSA4")["modelo_recomendado"], "holding")
        self.assertEqual(route_company("SAUD3")["modelo_recomendado"], "saude")
        self.assertEqual(route_company("SAPR4")["modelo_recomendado"], "dcf")
        self.assertEqual(route_company("WEGE3")["modelo_recomendado"], "dcf")


if __name__ == "__main__":
    unittest.main()
