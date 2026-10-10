"""Testes unitários automatizados para o Valuation Engine da B3 usando unittest padrão.
Garante a integridade matemática, estabilidade, tratamento de edge cases e blind mode.
"""
import io
import json
import sys
import unittest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from database import Base
from models import ValuationDB, UserDB
from schemas import ValuationCreate
from routers.valuations import save_valuation, list_valuations, delete_valuation
from valuation_engine import (
    calculate_bazin,
    calculate_dcf,
    calculate_cagr,
    validate_growth_and_market_share,
    calculate_financials_ddm,
    calculate_sotp_holding,
    calculate_operadora_saude,
    route_company,
    print_dossier_summary,
)


class TestValuationEngine(unittest.TestCase):
    # ── Módulo Décio Bazin ───────────────────────────────────────────────────
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

    def test_bazin_jcp_retention(self):
        # 100% dos proventos em JCP com 15% IRRF: DPA bruto 1.00 -> líquido 0.85
        res_100 = calculate_bazin(dpa=1.00, preco_teto_modelo=10.00, pct_jcp=100.0, aliquota_irrf_jcp=15.0)
        self.assertEqual(res_100["dpa_bruto"], 1.00)
        self.assertEqual(res_100["dpa_liquido"], 0.85)
        self.assertEqual(res_100["preco_teto_bazin_6pct"], round(0.85 / 0.06, 2))  # 14.17
        self.assertEqual(res_100["preco_teto_bazin_8pct"], round(0.85 / 0.08, 2))  # 10.62

        # 50% dos proventos em JCP com 15% IRRF: DPA bruto 1.00 -> líquido 0.50 + 0.50*0.85 = 0.925
        res_50 = calculate_bazin(dpa=1.00, preco_teto_modelo=10.00, pct_jcp=50.0, aliquota_irrf_jcp=15.0)
        self.assertEqual(res_50["dpa_bruto"], 1.00)
        self.assertEqual(res_50["dpa_liquido"], 0.925)
        self.assertEqual(res_50["preco_teto_bazin_6pct"], round(0.925 / 0.06, 2))  # 15.42
        self.assertEqual(res_50["preco_teto_bazin_8pct"], round(0.925 / 0.08, 2))  # 11.56

    def test_bazin_edge_cases(self):
        # Preço teto zerado ou negativo não deve gerar ZeroDivisionError
        res = calculate_bazin(dpa=1.00, preco_teto_modelo=0.0)
        self.assertEqual(res["yield_on_cost_no_preco_teto_modelo"], 0.0)
        res_neg = calculate_bazin(dpa=1.00, preco_teto_modelo=-5.0)
        self.assertEqual(res_neg["yield_on_cost_no_preco_teto_modelo"], 0.0)

    # ── Módulo DCF FCFF ──────────────────────────────────────────────────────
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
            ntnb=6.0,
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

    def test_dcf_tax_benefit_contingent_liabilities(self):
        # Passivos contingentes dedutíveis com benefício fiscal de 34% (IRPJ/CSLL)
        res = calculate_dcf(
            ticker="CPFE3",
            fclf_inicial=2000.0,
            taxas_crescimento=[5.0, 4.0, 3.0],
            wacc=12.0,
            cresc_perp=3.0,
            divida_liquida=10000.0,
            passivos_contingentes=1000.0,  # 1000 bruto -> líquido = 660 (economia fiscal de 340)
            aliquota_ir_csll=34.0,
            pct_contingencia_dedutivel=100.0,
            num_acoes=1150.0,
        )
        self.assertEqual(res["detalhes"]["passivos_contingentes_bruto"], 1000.0)
        self.assertEqual(res["detalhes"]["passivos_contingentes_liquidos"], 660.0)
        self.assertEqual(res["detalhes"]["beneficio_fiscal_quase_divida_mi"], 340.0)
        self.assertEqual(res["dividaLiquida"], 10660.0)

    def test_dcf_negative_regulatory_liability_as_asset(self):
        # Passivo regulatório negativo (-500 Mi) tratado como ATIVO regulatório (adiciona ao valor)
        res = calculate_dcf(
            ticker="TAEE11",
            fclf_inicial=1000.0,
            taxas_crescimento=[4.0, 3.5, 3.0],
            wacc=11.5,
            cresc_perp=3.0,
            divida_liquida=5000.0,
            passivos_regulatorios=-500.0,  # Ativo regulatório a receber
            num_acoes=1000.0,
        )
        self.assertEqual(res["detalhes"]["ativo_regulatorio_mi"], 500.0)
        # Dívida total ajustada deve ser menor que a dívida financeira líquida (5000 - 500 = 4500)
        self.assertEqual(res["dividaLiquida"], 4500.0)
        cenarios = res["detalhes"]["cenarios"]
        self.assertGreater(
            cenarios["cenario_ajustado"]["equity_value"],
            cenarios["cenario_base"]["equity_value"],
        )

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
                ntnb=-1.0,
            )

    def test_calculate_cagr(self):
        # 100 crescendo para 133.1 em 3 anos = 10% a.a.
        cagr = calculate_cagr(100.0, 133.1, 3)
        self.assertEqual(cagr, 10.0)

        # Casos inválidos retornam 0.0
        self.assertEqual(calculate_cagr(0.0, 100.0, 3), 0.0)
        self.assertEqual(calculate_cagr(-50.0, 100.0, 3), 0.0)
        self.assertEqual(calculate_cagr(100.0, 100.0, 0), 0.0)

    def test_validate_growth_and_market_share(self):
        # Histórico de 3 anos: 3700, 4600, 5300 (CAGR = 19.68%)
        res = validate_growth_and_market_share(
            fclf_inicial=5300.0,
            taxas_crescimento=[5.0, 4.5, 4.0, 3.5, 3.0],
            cresc_perp=3.0,
            historico_fcf=[3700.0, 4600.0, 5300.0],
            market_share_dinamica="estavel",
            decomposicao_g1=[3.8, 0.5, 0.7],
            analise_competitiva="Triopólio de telecom com disciplina de preços",
        )
        self.assertIsNotNone(res["cagr_historico_pct"])
        self.assertAlmostEqual(res["cagr_historico_pct"], 19.68, places=1)
        self.assertEqual(res["status_coerencia"], "coerente")
        self.assertTrue(res["convergencia_perpetuidade"])
        self.assertEqual(res["market_share_dinamica"], "estavel")
        self.assertIsNotNone(res["decomposicao_g1"])
        self.assertEqual(res["decomposicao_g1"]["soma"], 5.0)
        self.assertEqual(res["decomposicao_g1"]["g1_adotado"], 5.0)

        # Caso com alerta de aceleração (g1 > cagr + 3%)
        res_alerta = validate_growth_and_market_share(
            fclf_inicial=100.0,
            taxas_crescimento=[10.0, 8.0, 6.0],
            cresc_perp=3.0,
            cagr_historico=2.0,
        )
        self.assertEqual(res_alerta["status_coerencia"], "alerta_aceleracao")
        self.assertIn("alerta_aceleracao", res_alerta["status_coerencia"])

    def test_dcf_with_growth_and_market_share_validation(self):
        res = calculate_dcf(
            ticker="TIMS3",
            fclf_inicial=5300.0,
            taxas_crescimento=[5.0, 4.5, 4.0, 3.5, 3.0],
            wacc=12.37,
            cresc_perp=3.5,
            divida_liquida=1800.0,
            passivos_contingentes=2100.0,
            num_acoes=2378.93,
            margem_seguranca=20.0,
            dpa_projetado=1.50,
            pct_jcp=35.0,
            historico_fcf=[3700.0, 4600.0, 5300.0],
            market_share_dinamica="estavel",
            decomposicao_g1=[3.8, 0.5, 0.7],
            analise_competitiva="Triopólio de telecomunicações; ARPU em expansão",
            empresa="TIM S.A.",
            setor="Telecomunicações",
            ifrs16_expurgado=True,
        )
        detalhes = res["detalhes"]
        self.assertIn("validacao_crescimento", detalhes)
        val = detalhes["validacao_crescimento"]
        self.assertEqual(val["market_share_dinamica"], "estavel")
        self.assertEqual(val["cagr_historico_pct"], 19.68)
        self.assertEqual(val["decomposicao_g1"]["g1_adotado"], 5.0)
        self.assertEqual(val["decomposicao_g1"]["soma"], 5.0)

    def test_dcf_capex_minimo_historico(self):
        # Quando capex_minimo_historico é fornecido e capex_projetado também
        res = calculate_dcf(
            ticker="VIVT3",
            fclf_inicial=1000.0 - 800.0,
            ebitda_al=1000.0,
            capex_projetado=800.0,
            capex_minimo_historico=1000.0,
            taxas_crescimento=[4.0, 3.0],
            wacc=12.0,
            cresc_perp=3.0,
            divida_liquida=2000.0,
            num_acoes=1000.0,
            setor="Telecomunicações",
            ifrs16_expurgado=True,
        )
        detalhes = res["detalhes"]
        self.assertEqual(detalhes["deficit_capex"], 200.0)  # 1000 - 800
        self.assertEqual(detalhes["provisao_queima_caixa"], 1000.0)  # 200 * 5
        self.assertAlmostEqual(
            detalhes["enterprise_value"],
            detalhes["enterprise_value_bruto"] - 1000.0,
            places=2
        )
        
        # Testar ValueError se capex_projetado não é fornecido
        with self.assertRaisesRegex(ValueError, "Para usar capex_minimo_historico, é necessário informar capex_projetado"):
            calculate_dcf(
                ticker="VIVT3",
                fclf_inicial=200.0,
                capex_minimo_historico=1000.0,
                taxas_crescimento=[4.0, 3.0],
                wacc=12.0,
                cresc_perp=3.0,
                divida_liquida=2000.0,
                num_acoes=1000.0,
                setor="Telecomunicações",
                ifrs16_expurgado=True,
            )

    def test_dcf_invalid_shares(self):
        with self.assertRaises(ValueError):
            calculate_dcf(
                ticker="TEST",
                fclf_inicial=100.0,
                taxas_crescimento=[5.0],
                wacc=12.0,
                cresc_perp=3.0,
                divida_liquida=0.0,
                num_acoes=0.0,
            )

    # ── Módulo Gordon & DDM (Bancos e Seguradoras) ───────────────────────────
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
        self.assertEqual(res["dividaLiquida"], 0.0)
        self.assertGreater(res["precoJusto"], 0)
        self.assertEqual(res["precoTeto"], round(res["precoJusto"] * 0.8, 2))
        # Gordon P/VP = (20 - 4) / (13 - 4) = 16 / 9 = 1.778
        p_vp = res["detalhes"]["p_vp_justo_gordon"]
        self.assertEqual(round(p_vp, 2), 1.78)

    def test_financials_ddm_sustainable_payout_coherence(self):
        # Teste de coerência: Payout sustentável = 1 - g/ROE
        # Para ROE = 20% e g = 4%, o Payout sustentável é 1 - (4/20) = 80%.
        # Com a remoção do min() arbitrário, o banco não é artificialmente penalizado.
        res = calculate_financials_ddm(
            ticker="BBAS3",
            vpa=30.0,
            roe=20.0,
            ke=14.0,
            cresc_perp=4.0,
            payout=40.0,  # Payout informado inferior ao potencial
            num_acoes=2800.0,
        )
        self.assertEqual(res["detalhes"]["payout_sustentavel_teorico_pct"], 80.0)
        # Gordon P/VP = (20 - 4) / (14 - 4) = 16 / 10 = 1.60
        self.assertEqual(res["detalhes"]["p_vp_justo_gordon"], 1.6)
        self.assertEqual(res["precoJusto"], 48.0)  # 30 * 1.6

    def test_financials_ddm_multistage(self):
        # DDM multiestágio explícito
        res = calculate_financials_ddm(
            ticker="SANB11",
            vpa=25.0,
            roe=16.0,
            ke=13.0,
            cresc_perp=3.5,
            payout=50.0,
            taxas_crescimento_dpa=[8.0, 7.0, 5.0],
            num_acoes=3700.0,
        )
        self.assertEqual(res["anosProjecao"], 3)
        self.assertEqual(len(res["detalhes"]["projecoes_dpa"]), 3)
        self.assertGreater(res["precoJusto"], 0)

    def test_financials_ddm_edge_cases(self):
        # VPA <= 0
        with self.assertRaises(ValueError):
            calculate_financials_ddm(ticker="TEST", vpa=0.0, roe=15.0, ke=12.0, cresc_perp=3.0, num_acoes=100.0)
        # Ke <= g
        with self.assertRaises(ValueError):
            calculate_financials_ddm(ticker="TEST", vpa=10.0, roe=15.0, ke=3.0, cresc_perp=3.0, num_acoes=100.0)
        # Ações <= 0
        with self.assertRaises(ValueError):
            calculate_financials_ddm(ticker="TEST", vpa=10.0, roe=15.0, ke=12.0, cresc_perp=3.0, num_acoes=0.0)
        # ROE <= g deve zerar P/VP sem lançar exceção
        res_zero = calculate_financials_ddm(ticker="TEST", vpa=10.0, roe=3.0, ke=12.0, cresc_perp=3.0, num_acoes=100.0, payout=100.0)
        self.assertEqual(res_zero["precoJusto"], 0.0)

    def test_financials_ddm_auditoria(self):
        # Test improvements added: ntnb, pdd, roe_10a
        res = calculate_financials_ddm(
            ticker="TESTA",
            vpa=10.0,
            roe=25.0,  # should be capped to 20.0
            ke=10.0,   # should be floored to 5.0 + 6.0 = 11.0
            cresc_perp=5.0,
            num_acoes=100.0,
            margem_seguranca=20.0, # should adjust to 35.0
            ntnb=5.0,
            pdd_atual=50.0,
            pdd_media_5a=100.0,
            roe_10a=20.0
        )
        self.assertEqual(res["wacc"], 11.0)
        self.assertEqual(res["margemSeguranca"], 35.0)
        self.assertEqual(res["detalhes"]["roe_adotado_pct"], 20.0)
        self.assertIn("alerta_npl", res["detalhes"]["metadata"])

    def test_financials_ddm_seguradora_constraints(self):
        # Triggering both sinistralidade and prazo_acordo_anos rules
        res = calculate_financials_ddm(
            ticker="BBSE3",
            vpa=10.0,
            roe=20.0,
            ke=12.0,
            cresc_perp=4.0,
            num_acoes=100.0,
            margem_seguranca=20.0,
            tipo="seguradora",
            sinistralidade_atual=80.0,
            sinistralidade_media_5a=70.0,
            prazo_acordo_anos=5.0
        )
        self.assertEqual(res["margemSeguranca"], 40.0)
        self.assertIn("alerta_sinistralidade", res["detalhes"]["metadata"])
        self.assertIn("alerta_prazo_acordo", res["detalhes"]["metadata"])
        
        # Test negative inputs validation
        with self.assertRaisesRegex(ValueError, "sinistralidade não pode ser negativa"):
            calculate_financials_ddm(
                ticker="BBSE3", vpa=10.0, roe=20.0, ke=12.0, cresc_perp=4.0, num_acoes=100.0,
                tipo="seguradora", sinistralidade_atual=-5.0, sinistralidade_media_5a=70.0
            )
        
        with self.assertRaisesRegex(ValueError, "prazo do acordo não pode ser negativo"):
            calculate_financials_ddm(
                ticker="BBSE3", vpa=10.0, roe=20.0, ke=12.0, cresc_perp=4.0, num_acoes=100.0,
                tipo="seguradora", prazo_acordo_anos=-2.0
            )

    # ── Módulo SOTP Holdings ─────────────────────────────────────────────────
    def test_sotp_holding_protects_against_overvalued_subsidiary(self):
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
        self.assertLess(preco_intrinseco, preco_mercado)
        self.assertEqual(res["precoJusto"], preco_intrinseco)

    def test_sotp_holding_admin_expenses_present_value(self):
        # Despesas administrativas de R$ 120 Mi capitalizadas a Ke de 12% = VP de R$ 1000 Mi deduzido do NAV
        participacoes = [
            {
                "nome": "Controlada",
                "ticker": "CTRL3",
                "quantidade_acoes": 100.0,
                "preco_mercado": 100.0,
                "preco_justo_intrinseco": 100.0,
                "dpa_esperado": 5.0,
            }
        ]
        # Sem despesas
        res_sem = calculate_sotp_holding(
            ticker="HOLD3",
            participacoes=participacoes,
            divida_liquida_holding=1000.0,
            num_acoes_holding=100.0,
            despesas_adm_holding=0.0,
        )
        # Com despesas
        res_com = calculate_sotp_holding(
            ticker="HOLD3",
            participacoes=participacoes,
            divida_liquida_holding=1000.0,
            num_acoes_holding=100.0,
            despesas_adm_holding=120.0,
            ke_holding=12.0,
        )
        self.assertEqual(res_com["detalhes"]["vp_despesas_adm_holding_mi"], 1411.76)
        self.assertLess(res_com["precoJusto"], res_sem["precoJusto"])
        # Diferença de NAV líquido deve ser exatamente 1411.76 Mi
        diff_nav = res_sem["detalhes"]["nav_intrinseco_liquido_mi"] - res_com["detalhes"]["nav_intrinseco_liquido_mi"]
        self.assertEqual(round(diff_nav, 2), 1411.76)

    def test_sotp_holding_fallback_warning(self):
        # Investida sem preco_justo_intrinseco informado emite ValueError
        participacoes = [
            {
                "nome": "Investida Bolsa",
                "ticker": "BLSA3",
                "quantidade_acoes": 50.0,
                "preco_mercado": 20.0,
            }
        ]
        with self.assertRaises(ValueError):
            calculate_sotp_holding(
                ticker="HOLD3",
                participacoes=participacoes,
                divida_liquida_holding=100.0,
                num_acoes_holding=50.0,
            )

    def test_sotp_holding_edge_cases(self):
        with self.assertRaises(ValueError):
            calculate_sotp_holding(ticker="HOLD3", participacoes=[], divida_liquida_holding=0.0, num_acoes_holding=0.0)
        # Investida com ambos os preços zerados
        with self.assertRaises(ValueError):
            calculate_sotp_holding(
                ticker="HOLD3",
                participacoes=[{"nome": "Vazia", "ticker": "VAZ3", "quantidade_acoes": 10.0, "preco_mercado": 0.0}],
                divida_liquida_holding=0.0,
                num_acoes_holding=10.0,
            )

    # ── Módulo Saúde Suplementar (ANS RN 569/2022) ───────────────────────────
    def test_operadora_saude_ans(self):
        res = calculate_operadora_saude(
            ticker="SAUD3",
            receita_liquida=1000.0,
            sinistralidade_mlr_pct=80.0,
            despesas_adm_comerciais_pct=10.0,
            ganhos_float=30.0,
            despesas_juros_fixa=0.0,
            ntnb=6.0,
            ke=13.0,
            cresc_perp=3.5,
            num_acoes=100.0,
        )
        self.assertEqual(res["ticker"], "SAUD3")
        self.assertEqual(res["modelo"], "saude_ans")
        self.assertGreater(res["precoJusto"], 0)
        self.assertGreater(res["detalhes"]["retencao_reserva_solvencia_ans_mi"], 0)

    def test_operadora_saude_rn569_expansion_retention(self):
        # RN 569/2022: Retenção vinculada à variação da receita (ΔReceita * k)
        # Quando a receita NÃO cresce (g = 0%), retenção regulatória é ZERO
        res_flat = calculate_operadora_saude(
            ticker="SAUD3",
            receita_liquida=1000.0,
            sinistralidade_mlr_pct=80.0,
            despesas_adm_comerciais_pct=10.0,
            ganhos_float=0.0,
            despesas_juros_fixa=0.0,
            ntnb=6.0,
            ke=13.0,
            cresc_perp=3.0,
            taxas_crescimento_receita=[0.0, 0.0],
            num_acoes=100.0,
        )
        self.assertEqual(res_flat["detalhes"]["retencao_reserva_solvencia_ans_mi"], 0.0)

        # Quando a receita cresce a 10% com k=15%: ΔReceita = 100 Mi, Retenção = 15 Mi
        res_growth = calculate_operadora_saude(
            ticker="SAUD3",
            receita_liquida=1000.0,
            sinistralidade_mlr_pct=80.0,
            despesas_adm_comerciais_pct=10.0,
            ganhos_float=0.0,
            despesas_juros_fixa=0.0,
            ntnb=6.0,
            exigencia_capital_ans_pct=15.0,
            ke=13.0,
            cresc_perp=3.0,
            taxas_crescimento_receita=[10.0],
            num_acoes=100.0,
        )
        self.assertEqual(res_growth["detalhes"]["retencao_reserva_solvencia_ans_mi"], 15.0)

    def test_operadora_saude_net_debt_ignored(self):
        # Operadora alavancada: dívida líquida NÃO deve ser deduzida no DDM
        res_desalav = calculate_operadora_saude(
            ticker="HAPV3",
            receita_liquida=5000.0,
            sinistralidade_mlr_pct=75.0,
            despesas_adm_comerciais_pct=12.0,
            ganhos_float=50.0,
            despesas_juros_fixa=0.0,
            ntnb=6.0,
            divida_liquida=0.0,
            num_acoes=1000.0,
            ke=13.5,
            cresc_perp=3.5,
        )
        res_alav = calculate_operadora_saude(
            ticker="HAPV3",
            receita_liquida=5000.0,
            sinistralidade_mlr_pct=75.0,
            despesas_adm_comerciais_pct=12.0,
            ganhos_float=50.0,
            despesas_juros_fixa=0.0,
            ntnb=6.0,
            divida_liquida=2000.0,  # Dívida não deve abater o Equity Value
            num_acoes=1000.0,
            ke=13.5,
            cresc_perp=3.5,
        )
        diff_preco = res_desalav["precoJusto"] - res_alav["precoJusto"]
        self.assertEqual(round(diff_preco, 2), 0.00)

    def test_operadora_saude_edge_cases(self):
        with self.assertRaises(ValueError):
            calculate_operadora_saude(
                ticker="TEST", receita_liquida=100.0, sinistralidade_mlr_pct=80.0,
                despesas_adm_comerciais_pct=10.0, ganhos_float=0.0,
            despesas_juros_fixa=0.0,
            ntnb=-5.0, ke=3.0, cresc_perp=3.0, num_acoes=10.0
            )
        with self.assertRaises(ValueError):
            calculate_operadora_saude(
                ticker="TEST", receita_liquida=100.0, sinistralidade_mlr_pct=80.0,
                despesas_adm_comerciais_pct=10.0, ganhos_float=0.0,
            despesas_juros_fixa=0.0,
            ntnb=6.0, ke=12.0, cresc_perp=3.0, num_acoes=0.0
            )

    # ── Blind Mode & Exportação ──────────────────────────────────────────────
    def test_export_blind_mode_no_pvp_leak(self):
        # Garante que o dossiê do terminal NÃO imprime o multiplicador P/VP derivado
        resultado = calculate_financials_ddm(
            ticker="ITUB4",
            vpa=20.0,
            roe=20.0,
            ke=13.0,
            cresc_perp=4.0,
            payout=50.0,
            num_acoes=9000.0,
        )
        captured_output = io.StringIO()
        old_stdout = sys.stdout
        try:
            sys.stdout = captured_output
            print_dossier_summary(resultado, "dummy.json")
        finally:
            sys.stdout = old_stdout

        out = captured_output.getvalue()
        self.assertIn("Preservado no JSON para Modo Cego", out)
        # O número 1.778x não deve aparecer no terminal
        self.assertNotIn("1.778", out)
        self.assertNotIn("1.78x", out)

    # ── Roteador ─────────────────────────────────────────────────────────────
    def test_router_coverage(self):
        self.assertEqual(route_company("ITUB4")["modelo_recomendado"], "financials")
        self.assertEqual(route_company("BBSE3")["modelo_recomendado"], "financials")
        self.assertEqual(route_company("ITSA4")["modelo_recomendado"], "holding")
        self.assertEqual(route_company("SAUD3")["modelo_recomendado"], "saude")
        self.assertEqual(route_company("SAPR4")["modelo_recomendado"], "dcf")
        self.assertEqual(route_company("WEGE3")["modelo_recomendado"], "dcf")

    # ── Testes de Robustez Adicionais e Cobertura Completa ────────────────────
    def test_sotp_holding_empty_participacoes_raises_error(self):
        # SOTP sem participações informadas deve lançar ValueError explícito
        with self.assertRaises(ValueError):
            calculate_sotp_holding(
                ticker="HOLD3",
                participacoes=[],
                divida_liquida_holding=0.0,
                num_acoes_holding=100.0,
            )

    def test_sotp_holding_zero_discount(self):
        # Desconto de holding igual a 0% não deve sofrer fallback arbitrário para 20%
        participacoes = [
            {
                "nome": "Ativo Integral",
                "ticker": "INTG3",
                "quantidade_acoes": 100.0,
                "preco_mercado": 50.0,
                "preco_justo_intrinseco": 50.0,
            }
        ]
        res = calculate_sotp_holding(
            ticker="HOLD3",
            participacoes=participacoes,
            divida_liquida_holding=0.0,
            num_acoes_holding=100.0,
            desconto_holding_adotado_pct=0.0,
            margem_seguranca=20.0,
        )
        self.assertEqual(res["precoJusto"], 50.00)
        self.assertEqual(res["precoTeto"], 40.00)

    def test_operadora_saude_flat_or_negative_growth_zero_retention(self):
        # Operadora com receita estável ou em contração: retenção de solvência ANS deve ser zero
        res_flat = calculate_operadora_saude(
            ticker="FLAT3",
            receita_liquida=1000.0,
            sinistralidade_mlr_pct=75.0,
            despesas_adm_comerciais_pct=10.0,
            ganhos_float=0.0,
            despesas_juros_fixa=0.0,
            ntnb=6.0,
            exigencia_capital_ans_pct=10.0,
            taxas_crescimento_receita=[0.0],
            cresc_perp=2.0,
            num_acoes=100.0,
        )
        self.assertEqual(res_flat["detalhes"]["retencao_reserva_solvencia_ans_mi"], 0.0)

    def test_operadora_saude_excessive_debt_ignored(self):
        # Dívida líquida muito superior ao VP dos dividendos não afeta o Preço Justo no modelo DDM
        res = calculate_operadora_saude(
            ticker="DEBT3",
            receita_liquida=100.0,
            sinistralidade_mlr_pct=80.0,
            despesas_adm_comerciais_pct=10.0,
            ganhos_float=0.0,
            despesas_juros_fixa=0.0,
            ntnb=6.0,
            divida_liquida=50000.0,
            num_acoes=10.0,
        )
        self.assertGreater(res["precoJusto"], 0.0)
        self.assertEqual(res["precoJusto"], 4.09)

    def test_bazin_custom_irrf_and_100pct_jcp(self):
        # Proventos com 50% dividendos e 50% JCP retido a 20% de IRRF
        res = calculate_bazin(
            dpa=2.00,
            preco_teto_modelo=20.00,
            pct_jcp=50.0,
            aliquota_irrf_jcp=20.0,
        )
        # Líquido = 2.00 * (0.50 + 0.50 * 0.80) = 2.00 * 0.90 = 1.80
        self.assertEqual(res["dpa_liquido"], 1.80)
        self.assertEqual(res["yield_on_cost_no_preco_teto_modelo"], 9.0)  # 1.80 / 20 * 100

    def test_export_dossier_dcf_regulatory_asset_and_contingent_debt(self):
        # Testa exibição de ativos regulatórios líquidos e quase-dívidas no dossiê
        resultado = calculate_dcf(
            ticker="REG3",
            fclf_inicial=100.0,
            taxas_crescimento=[5.0],
            wacc=12.0,
            cresc_perp=3.0,
            divida_liquida=200.0,
            passivos_contingentes=100.0,
            passivos_regulatorios=-50.0,
            num_acoes=50.0,
        )
        captured = io.StringIO()
        old_stdout = sys.stdout
        try:
            sys.stdout = captured
            print_dossier_summary(resultado, "dummy_reg.json")
        finally:
            sys.stdout = old_stdout

        out = captured.getvalue()
        self.assertIn("Passivos Contingentes (Bruto): R$ 100.00 Mi", out)
        self.assertIn("Ativo Regulatório Líquido: R$ 50.00 Mi", out)
        self.assertIn("Dívida Total Ajustada", out)

    # ── Banco de Dados SQLite, Migração e CRUD de Valuations ──────────────────
    def test_database_migration_and_valuation_crud(self):
        test_engine = create_engine("sqlite:///:memory:")
        TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
        Base.metadata.create_all(bind=test_engine)

        db = TestingSessionLocal()
        try:
            # 1. Cria usuário de teste
            user = UserDB(nome="Usuário Auditoria", username="auditor", senha_hash="hash123")
            db.add(user)
            db.commit()
            db.refresh(user)

            # 2. Salva valuation com modelo Gordon e detalhes estruturados
            detalhes_input = {
                "vpa": 25.5,
                "roe_adotado_pct": 20.0,
                "p_vp_justo_gordon": 1.778,
            }
            val_input = ValuationCreate(
                ticker="BBAS3",
                preco_atual=27.50,
                fclf_inicial=15000.0,
                anos_projecao=5,
                taxas_crescimento=[4.0, 4.0, 4.0, 4.0, 4.0],
                wacc=13.0,
                cresc_perp=4.0,
                divida_liquida=0.0,
                num_acoes=2850.0,
                margem_seguranca=20.0,
                preco_justo=35.00,
                preco_teto=28.00,
                modelo="gordon_ddm",
                detalhes=detalhes_input,
            )
            saved = save_valuation(val_input, db=db, user_id=user.id)
            self.assertEqual(saved["ticker"], "BBAS3")
            self.assertEqual(saved["modelo"], "gordon_ddm")
            self.assertEqual(saved["detalhes"]["vpa"], 25.5)
            self.assertNotIn("_sa_instance_state", saved)

            # 3. Lista valuations e verifica integridade
            listed = list_valuations(db=db, user_id=user.id)
            self.assertEqual(len(listed), 1)
            self.assertEqual(listed[0]["ticker"], "BBAS3")
            self.assertEqual(listed[0]["modelo"], "gordon_ddm")
            self.assertIsInstance(listed[0]["detalhes"], dict)
            self.assertNotIn("_sa_instance_state", listed[0])

            # 4. Deleta valuation
            del_resp = delete_valuation(saved["id"], db=db, user_id=user.id)
            self.assertIn("eliminado", del_resp["message"].lower())
            listed_after = list_valuations(db=db, user_id=user.id)
            self.assertEqual(len(listed_after), 0)
        finally:
            db.close()

    def test_database_legacy_null_columns_fallback(self):
        # Valuations legados sem modelo ou detalhes devem ter fallback seguro
        test_engine = create_engine("sqlite:///:memory:")
        TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
        Base.metadata.create_all(bind=test_engine)

        db = TestingSessionLocal()
        try:
            user = UserDB(nome="Usuário Legado", username="legado", senha_hash="hash")
            db.add(user)
            db.commit()
            db.refresh(user)

            # Insere registro simulando base SQLite pré-migração
            legacy_item = ValuationDB(
                usuario_id=user.id,
                ticker="VALE3",
                preco_atual=60.0,
                fclf_inicial=20000.0,
                anos_projecao=5,
                taxas_crescimento="[5.0, 5.0, 5.0, 5.0, 5.0]",
                wacc=12.0,
                cresc_perp=2.5,
                divida_liquida=30000.0,
                num_acoes=4500.0,
                margem_seguranca=20.0,
                preco_justo=80.0,
                preco_teto=64.0,
                modelo="dcf_fcff",
                detalhes=None,
            )
            db.add(legacy_item)
            db.commit()

            listed = list_valuations(db=db, user_id=user.id)
            self.assertEqual(len(listed), 1)
            self.assertEqual(listed[0]["modelo"], "dcf_fcff")
            self.assertIsNone(listed[0]["detalhes"])
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()

