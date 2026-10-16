"""Testes unitários automatizados para o Valuation Engine da B3 usando unittest padrão.
Garante a integridade matemática, estabilidade, tratamento de edge cases e blind mode.
"""
import io
import sys
import unittest
from sqlalchemy import create_engine
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
                ntnb=-2.5,
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
        # Quando capex_minimo_historico é fornecido e capex_projetado também (com normalização direta no fluxo por padrão)
        res = calculate_dcf(
            ticker="VIVT3",
            fclf_inicial=1500.0 - 800.0,
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
        self.assertEqual(res["fclf"], 500.0)  # 700 - 200 deduzido diretamente no fluxo
        self.assertEqual(detalhes["provisao_queima_caixa"], 0.0)
        self.assertAlmostEqual(
            detalhes["enterprise_value"],
            detalhes["enterprise_value_bruto"],
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

    def test_financials_ddm_sanity_checks(self):
        # Cenário com Ke excessivo gerando spread > 10.5% e P/L baixo
        res = calculate_financials_ddm(
            ticker="CXSE3",
            vpa=4.60,
            roe=32.8,
            ke=17.1,
            cresc_perp=4.0,
            payout=90.0,
            num_acoes=3000.0,
        )
        detalhes = res["detalhes"]
        self.assertEqual(detalhes["spread_ke_g_pct"], 13.1)
        self.assertIsNotNone(detalhes["p_l_justo_implicito"])
        self.assertGreater(len(detalhes["avisos_metodologicos"]), 0)
        # Deve conter aviso sobre spread excessivo
        self.assertTrue(any("Spread (Ke - g)" in av for av in detalhes["avisos_metodologicos"]))

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
        # Test improvements added: ntnb, pdd, roe_10a (modo gradual padrão evita dupla penalização com roe_10a)
        res = calculate_financials_ddm(
            ticker="TESTA",
            vpa=10.0,
            roe=25.0,  # capped to 20.0 (corte de 5 p.p. já absorve ciclo de crédito)
            ke=10.0,   # floored via Fisher formula (8.675 + 3.5 = 12.17)
            cresc_perp=5.0,
            num_acoes=100.0,
            margem_seguranca=20.0,  # ajusta gradualmente para 25.0 sem tripla contagem
            ntnb=5.0,
            pdd_atual=50.0,
            pdd_media_5a=100.0,
            roe_10a=20.0
        )
        self.assertEqual(res["wacc"], 12.17)
        self.assertEqual(res["margemSeguranca"], 25.0)
        self.assertEqual(res["detalhes"]["roe_adotado_pct"], 20.0)
        self.assertIn("alerta_npl", res["detalhes"]["metadata"])

    def test_financials_ddm_seguradora_constraints(self):
        # Triggering both sinistralidade and prazo_acordo_anos rules (modo gradual padrão)
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
        self.assertEqual(res["margemSeguranca"], 35.0)
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
        # Despesas administrativas de R$ 120 Mi capitalizadas a Ke de 12% e inflação 3.5% = VP de R$ 1411.76 Mi deduzido do NAV
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
        # Sem despesas (desconto 0% para isolar o efeito puro do VP das despesas no NAV)
        res_sem = calculate_sotp_holding(
            ticker="HOLD3",
            participacoes=participacoes,
            divida_liquida_holding=1000.0,
            num_acoes_holding=100.0,
            despesas_adm_holding=0.0,
            desconto_holding_adotado_pct=0.0,
        )
        # Com despesas
        res_com = calculate_sotp_holding(
            ticker="HOLD3",
            participacoes=participacoes,
            divida_liquida_holding=1000.0,
            num_acoes_holding=100.0,
            despesas_adm_holding=120.0,
            ke_holding=12.0,
            desconto_holding_adotado_pct=0.0,
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

        # Quando a receita cresce a 10% com k=15%:
        # Ano Base: ΔRec_0 = 1000 * (0.10 / 1.10) = 90.91 -> Retenção_0 = 13.64 Mi
        # Ano 1 Projetado: ΔRec_1 = 100 Mi -> Retenção_1 = 15.0 Mi
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
        self.assertEqual(res_growth["detalhes"]["retencao_reserva_solvencia_ans_mi"], 13.64)
        self.assertEqual(res_growth["detalhes"]["projecoes_dpa"][0]["retencao_solvencia_ans_mi"], 15.0)

    def test_operadora_saude_net_debt_ignored(self):
        # Operadora alavancada: dívida líquida NÃO deve ser deduzida no DDM
        res_desalav = calculate_operadora_saude(
            ticker="ODPV3",
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
            ticker="ODPV3",
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
        self.assertEqual(route_company("HAPV3")["modelo_recomendado"], "dcf")

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
        self.assertEqual(res["precoJusto"], 6.45)

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

    # ── Testes das Correções Metodológicas Refinadas ─────────────────────────
    def test_fisher_floors_all_models(self):
        # NTN-B = 6.0%, IPCA = 3.5% -> Rf_nominal = ((1.06 * 1.035) - 1) * 100 = 9.71%
        # DCF: floor = Rf_nominal + 1.5% = 11.21%
        res_dcf = calculate_dcf(
            ticker="SAPR4", fclf_inicial=500.0, taxas_crescimento=[4.0],
            wacc=10.0, cresc_perp=3.5, divida_liquida=1000.0, num_acoes=100.0, ntnb=6.0
        )
        self.assertEqual(res_dcf["wacc"], 11.21)

        # DDM Seguradora: floor = Rf_nominal + 2.0% = 11.71%
        res_seg = calculate_financials_ddm(
            ticker="BBSE3", vpa=10.0, roe=20.0, ke=10.0, cresc_perp=3.5,
            num_acoes=100.0, ntnb=6.0, tipo="seguradora"
        )
        self.assertEqual(res_seg["wacc"], 11.71)

        # DDM Banco: floor = Rf_nominal + 3.5% = 13.21%
        res_banco = calculate_financials_ddm(
            ticker="ITUB4", vpa=10.0, roe=20.0, ke=10.0, cresc_perp=3.5,
            num_acoes=100.0, ntnb=6.0, tipo="banco"
        )
        self.assertEqual(res_banco["wacc"], 13.21)

        # Saúde: floor = Rf_nominal + 2.0% = 11.71%
        res_saude = calculate_operadora_saude(
            ticker="ODPV3", receita_liquida=1000.0, sinistralidade_mlr_pct=75.0,
            despesas_adm_comerciais_pct=10.0, ganhos_float=20.0, despesas_juros_fixa=0.0,
            ntnb=6.0, ke=10.0, cresc_perp=3.5, num_acoes=100.0
        )
        self.assertEqual(res_saude["wacc"], 11.71)

        # SOTP: floor = Rf_nominal + 2.0% = 11.71%
        res_sotp = calculate_sotp_holding(
            ticker="ITSA4",
            participacoes=[{
                "nome": "Itaú",
                "ticker": "ITUB4",
                "quantidade_acoes": 100.0,
                "preco_mercado": 30.0,
                "preco_justo_intrinseco": 32.0,
            }],
            divida_liquida_holding=0.0, num_acoes_holding=100.0, ke_holding=10.0, ntnb=6.0
        )
        self.assertEqual(res_sotp["wacc"], 11.71)

    def test_ddm_multistage_payout_convergence(self):
        # ROE = 20%, g_perp = 4.0% -> payout sustentável perpétuo = 1 - (4/20) = 80%
        # Com payout inicial = 40% e crescimento zero nos anos 1 a 3:
        # DPA anual = 10 * 0.20 * 0.40 = 0.80
        # No ano terminal: LPA terminal = 2.0 * (1.04) = 2.08
        # DPA terminal = 2.08 * 0.80 = 1.664 (refletindo convergência para payout sustentável)
        res = calculate_financials_ddm(
            ticker="SANB11", vpa=10.0, roe=20.0, ke=14.0, cresc_perp=4.0,
            payout=40.0, taxas_crescimento_dpa=[0.0, 0.0, 0.0], num_acoes=100.0
        )
        # O DPA dos anos explícitos é 0.80
        self.assertEqual(res["detalhes"]["projecoes_dpa"][0]["dpa_projetado"], 0.8)
        # Se não houvesse ajuste de payout no terminal, DPA terminal seria 0.80 * 1.04 = 0.832
        # Com a convergência, DPA terminal é 2.08 * 0.80 = 1.664, dobrando o VP terminal
        # VP terminal = (1.664 / (0.14 - 0.04)) / (1.14 ** 3) = 16.64 / 1.481544 = 11.2315
        self.assertGreater(res["precoJusto"], 12.0)

    def test_operadora_saude_terminal_debt_interest(self):
        # Verifica que juros de dívida escalam suavemente por (1 + g_perp) no terminal
        res_sem_juros = calculate_operadora_saude(
            ticker="ODPV3", receita_liquida=1000.0, sinistralidade_mlr_pct=75.0,
            despesas_adm_comerciais_pct=10.0, ganhos_float=50.0, despesas_juros_fixa=0.0,
            ntnb=6.0, ke=13.0, cresc_perp=4.0, num_acoes=100.0
        )
        res_com_juros = calculate_operadora_saude(
            ticker="ODPV3", receita_liquida=1000.0, sinistralidade_mlr_pct=75.0,
            despesas_adm_comerciais_pct=10.0, ganhos_float=50.0, despesas_juros_fixa=10.0,
            ntnb=6.0, ke=13.0, cresc_perp=4.0, num_acoes=100.0
        )
        self.assertLess(res_com_juros["precoJusto"], res_sem_juros["precoJusto"])
        self.assertGreater(res_com_juros["precoJusto"], 0.0)

    # ── Fase 5: 18 Novos Testes Unitários da Refatoração Quantitativa ────────

    # 1. Default de 100% de dedutibilidade fiscal sobre passivos contingentes
    def test_dcf_default_contingent_tax_shield_100pct(self):
        res = calculate_dcf(
            ticker="CPFE3",
            fclf_inicial=2000.0,
            taxas_crescimento=[5.0, 4.0, 3.5],
            wacc=12.0,
            cresc_perp=3.5,
            divida_liquida=10000.0,
            passivos_contingentes=1000.0,
            num_acoes=1000.0,
        )
        self.assertEqual(res["detalhes"]["passivos_contingentes_bruto"], 1000.0)
        self.assertEqual(res["detalhes"]["passivos_contingentes_liquidos"], 660.0)
        self.assertEqual(res["detalhes"]["beneficio_fiscal_quase_divida_mi"], 340.0)
        self.assertEqual(res["dividaLiquida"], 10660.0)

    # 2. Preservação ortogonal de outros_passivos junto com passivos_contingentes
    def test_dcf_preserves_outros_passivos_with_contingencies(self):
        res = calculate_dcf(
            ticker="SAPR4",
            fclf_inicial=1000.0,
            taxas_crescimento=[5.0, 4.0, 3.5],
            wacc=12.0,
            cresc_perp=3.5,
            divida_liquida=2000.0,
            passivos_contingentes=1000.0,
            outros_passivos=500.0,
            pct_contingencia_dedutivel=100.0,
            num_acoes=1000.0,
        )
        # Dívida total ajustada = 2000 (dívida fin) + 660 (contingentes líq) + 500 (outros não-dedutíveis) = 3160
        self.assertEqual(res["detalhes"]["passivos_contingentes_liquidos"], 660.0)
        self.assertEqual(res["detalhes"]["outros_passivos_nao_dedutiveis"], 500.0)
        self.assertEqual(res["detalhes"]["divida_total_ajustada"], 3160.0)
        self.assertEqual(res["dividaLiquida"], 3160.0)

    # 3. Bloqueio de fclf_inicial == 0.0 no modo taxa de crescimento
    def test_dcf_zero_fclf_raises_value_error(self):
        with self.assertRaises(ValueError):
            calculate_dcf(
                ticker="TEST3",
                fclf_inicial=0.0,
                taxas_crescimento=[5.0, 4.0, 3.5],
                wacc=12.0,
                cresc_perp=3.5,
                divida_liquida=500.0,
                num_acoes=100.0,
            )

    # 4. Validação estrita da decomposição vetorial de g1
    def test_dcf_decomposicao_g1_mismatch_raises_error(self):
        with self.assertRaises(ValueError):
            calculate_dcf(
                ticker="WEGE3",
                fclf_inicial=1000.0,
                taxas_crescimento=[8.0, 6.0, 4.5],
                wacc=12.0,
                cresc_perp=3.5,
                divida_liquida=0.0,
                num_acoes=1000.0,
                decomposicao_g1=[3.5, 1.0, 0.5],  # soma = 5.0 != 8.0
            )

    # 5. Flag juros_pagos_no_fco contra dupla contagem no CPC 03
    def test_dcf_juros_pagos_no_fco_flag(self):
        res_com_juros = calculate_dcf(
            ticker="INFRA3",
            fco=1000.0,
            juros_pagos=200.0,
            capex_projetado=400.0,
            juros_pagos_no_fco=True,
            taxas_crescimento=[4.0, 3.5],
            wacc=12.0,
            cresc_perp=3.5,
            divida_liquida=1000.0,
            num_acoes=100.0,
        )
        res_sem_juros = calculate_dcf(
            ticker="INFRA3",
            fco=1000.0,
            juros_pagos=200.0,
            capex_projetado=400.0,
            juros_pagos_no_fco=False,
            taxas_crescimento=[4.0, 3.5],
            wacc=12.0,
            cresc_perp=3.5,
            divida_liquida=1000.0,
            num_acoes=100.0,
        )
        # Com juros no FCO: 1000 + 200 * 0.66 - 400 = 732.0
        self.assertEqual(res_com_juros["fclf"], 732.0)
        # Sem juros no FCO: 1000 - 400 = 600.0
        self.assertEqual(res_sem_juros["fclf"], 600.0)

    # 6. Valor Terminal por Anuidade Crescente Finita + Indenização de RAB
    def test_dcf_finite_concession_terminal_value(self):
        # Perpetuidade pura
        res_perp = calculate_dcf(
            ticker="CCRO3",
            fclf_inicial=1000.0,
            taxas_crescimento=[4.0, 4.0, 4.0, 4.0, 4.0],
            wacc=11.5,
            cresc_perp=3.5,
            divida_liquida=2000.0,
            num_acoes=1000.0,
            ntnb=6.0,
        )
        # Concessão de 20 anos (N = 15 anos após 5 explícitos) + RAB indenizável de R$ 1000 Mi
        res_finita = calculate_dcf(
            ticker="CCRO3",
            fclf_inicial=1000.0,
            taxas_crescimento=[4.0, 4.0, 4.0, 4.0, 4.0],
            wacc=11.5,
            cresc_perp=3.5,
            divida_liquida=2000.0,
            num_acoes=1000.0,
            ntnb=6.0,
            prazo_concessao_anos=20,
            rab_indenizavel_mi=1000.0,
        )
        fator_esperado = 1.0 - ((1.035 / 1.115) ** 15)
        vp_rab_esperado = 1000.0 / (1.115 ** 15)
        self.assertAlmostEqual(res_finita["detalhes"]["fator_anuidade_finita"], fator_esperado, places=6)
        self.assertAlmostEqual(res_finita["detalhes"]["vp_rab_indenizavel_em_t_mi"], round(vp_rab_esperado, 2), places=2)
        vt_esperado = res_perp["detalhes"]["valor_terminal_bruto"] * fator_esperado + vp_rab_esperado
        self.assertAlmostEqual(res_finita["detalhes"]["valor_terminal_bruto"], round(vt_esperado, 2), places=1)
        self.assertLess(res_finita["precoJusto"], res_perp["precoJusto"])

    # 7. Suporte a Curva "J" via fluxos_explicitos
    def test_dcf_j_curve_explicit_cash_flows(self):
        res = calculate_dcf(
            ticker="SBSP3",
            fluxos_explicitos=[-500.0, -200.0, 300.0, 800.0, 1200.0],
            wacc=11.5,
            cresc_perp=3.5,
            divida_liquida=3000.0,
            num_acoes=683.5,
            ntnb=6.0,
        )
        self.assertEqual(res["anosProjecao"], 5)
        self.assertEqual(res["detalhes"]["projecoes"][0]["fclf_projetado"], -500.0)
        self.assertEqual(res["detalhes"]["projecoes"][4]["fclf_projetado"], 1200.0)
        # fcf_ano_terminal deve ser ancorado em FCFF_5 = 1200 * 1.035 = 1242.0
        self.assertEqual(res["detalhes"]["fcf_ano_terminal"], 1242.0)
        self.assertGreater(res["precoJusto"], 0.0)

    # 8. Normalização econômica direta do CapEx no fluxo em Telecom
    def test_dcf_telecom_normalized_capex_in_flow(self):
        res = calculate_dcf(
            ticker="TIMS3",
            fco=10000.0,
            juros_pagos=1000.0,
            capex_projetado=4000.0,
            capex_minimo_historico=4500.0,
            normalizar_capex_fluxo=True,
            ifrs16_expurgado=True,
            setor="Telecomunicações",
            taxas_crescimento=[4.5, 4.0, 3.5],
            wacc=12.0,
            cresc_perp=3.5,
            divida_liquida=2000.0,
            num_acoes=2400.0,
        )
        # FCFF antes do deficit = 10000 + 660 - 4000 = 6660. Deficit = 500 -> FCFF normalizado = 6160.0
        self.assertEqual(res["detalhes"]["deficit_capex"], 500.0)
        self.assertEqual(res["detalhes"]["provisao_queima_caixa"], 0.0)
        self.assertEqual(res["fclf"], 6160.0)

    # 9. Separação entre Dividendo Efetivo de Ano 1 (Bazin) e Payout Sustentável Perpétuo (Gordon)
    def test_ddm_single_stage_bazin_uses_effective_payout(self):
        res = calculate_financials_ddm(
            ticker="BBAS3",
            vpa=30.0,
            roe=20.0,
            ke=14.0,
            cresc_perp=4.0,
            payout=40.0,
            num_acoes=2800.0,
        )
        # Gordon usa Payout_sust = 1 - 4/20 = 80% -> P/VP = 1.6 -> Preço Justo = 48.00
        self.assertEqual(res["precoJusto"], 48.0)
        # Bazin usa o dividendo efetivo de Ano 1 (30 * 20% * 40% = R$ 2,40) e não R$ 4,80
        self.assertEqual(res["detalhes"]["dpa_ano_base"], 2.40)
        self.assertEqual(res["detalhes"]["metrica_bazin"]["dpa_bruto"], 2.40)

    # 10. Convergência exata do DDM Multiestágio em estado estacionário para o Modelo de Gordon
    def test_ddm_multistage_steady_state_converges_to_gordon(self):
        res = calculate_financials_ddm(
            ticker="ITUB4",
            vpa=30.0,
            roe=20.0,
            ke=14.0,
            cresc_perp=4.0,
            payout=80.0,
            taxas_crescimento_dpa=[4.0, 4.0, 4.0, 4.0, 4.0],
            num_acoes=9800.0,
            alinhar_dpa_base_ano1=True,
        )
        preco_gordon = res["detalhes"]["cenarios"]["modelo_gordon"]["preco_justo"]
        preco_ddm = res["detalhes"]["cenarios"]["modelo_ddm"]["preco_justo"]
        self.assertEqual(preco_gordon, 48.00)
        self.assertEqual(preco_ddm, 48.00)
        self.assertEqual(res["precoJusto"], 48.00)
        # Verifica evolução Clean Surplus do VPA: VPA_1 = 30 + 6.0 - 4.8 = 31.20 (30 * 1.04)
        self.assertEqual(res["detalhes"]["projecoes_dpa"][0]["vpa_projetado"], 31.20)

    # 11. Penalização gradual sem efeito penhasco nem tripla contagem
    def test_ddm_gradual_penalty_avoids_cliff_effect(self):
        # Seguradora com acordo de balcão de 8.5 anos: margem = 20% + 2% * (10 - 8.5) = 23.0%
        res_seg = calculate_financials_ddm(
            ticker="CXSE3",
            vpa=4.60,
            roe=32.0,
            ke=13.5,
            cresc_perp=3.5,
            num_acoes=3000.0,
            tipo="seguradora",
            prazo_acordo_anos=8.5,
            modo_penalizacao="gradual",
        )
        self.assertEqual(res_seg["margemSeguranca"], 23.0)

        # Banco com ROE já truncado por roe_10a (24% -> 19%) e cobertura de PDD levemente abaixo da média:
        # margem sobe apenas para 25.0% em vez de saltar para 35.0%
        res_banco = calculate_financials_ddm(
            ticker="BBDC4",
            vpa=15.0,
            roe=24.0,
            roe_10a=19.0,
            ke=14.0,
            cresc_perp=3.5,
            num_acoes=10600.0,
            pdd_atual=180.0,
            pdd_media_5a=200.0,
            modo_penalizacao="gradual",
        )
        self.assertEqual(res_banco["detalhes"]["roe_adotado_pct"], 19.0)
        self.assertEqual(res_banco["margemSeguranca"], 25.0)

    # 12. Teste de sanidade do spread (Ke - g) ajustado pela ETTJ da NTN-B sem deadlock
    def test_ddm_high_ntnb_sanity_check_no_deadlock(self):
        res = calculate_financials_ddm(
            ticker="BBAS3",
            vpa=30.0,
            roe=21.0,
            ke=16.62,
            cresc_perp=4.5,
            payout=40.0,
            num_acoes=5700.0,
            ntnb=7.2,
        )
        # Com NTN-B = 7.2% (Rf_nom = 10.95%), o limite dinâmico é 10.95 + 6.0 - 4.5 = 12.45% > 12.12%
        self.assertEqual(res["detalhes"]["spread_ke_g_pct"], 12.12)
        self.assertEqual(len(res["detalhes"]["avisos_metodologicos"]), 0)

    # 13. Fim da dupla retenção ANS no Ano Base e fim da Retenção Fantasma na Saúde
    def test_saude_no_double_ans_retention_in_base_year(self):
        res_com_reinv = calculate_operadora_saude(
            ticker="ODPV3",
            receita_liquida=2000.0,
            sinistralidade_mlr_pct=70.0,
            despesas_adm_comerciais_pct=12.0,
            ganhos_float=40.0,
            despesas_juros_fixa=0.0,
            exigencia_capital_ans_pct=10.0,
            payout_sustentavel_pct=60.0,
            ke=13.0,
            cresc_perp=3.5,
            taxas_crescimento_receita=[10.0, 8.0, 6.0, 5.0, 4.0],
            num_acoes=500.0,
            ntnb=6.0,
            reinvestir_retencao_voluntaria_no_float=True,
        )
        res_sem_reinv = calculate_operadora_saude(
            ticker="ODPV3",
            receita_liquida=2000.0,
            sinistralidade_mlr_pct=70.0,
            despesas_adm_comerciais_pct=12.0,
            ganhos_float=40.0,
            despesas_juros_fixa=0.0,
            exigencia_capital_ans_pct=10.0,
            payout_sustentavel_pct=60.0,
            ke=13.0,
            cresc_perp=3.5,
            taxas_crescimento_receita=[10.0, 8.0, 6.0, 5.0, 4.0],
            num_acoes=500.0,
            ntnb=6.0,
            reinvestir_retencao_voluntaria_no_float=False,
        )
        # Retenção do Ano Base = 2000 * (0.10 / 1.10) * 0.10 = 18.18 Mi (e não 20.0 Mi)
        self.assertEqual(res_com_reinv["detalhes"]["retencao_reserva_solvencia_ans_mi"], 18.18)
        self.assertGreater(res_com_reinv["detalhes"]["reserva_livre_acumulada_mi"], 0.0)
        self.assertGreater(res_com_reinv["precoJusto"], res_sem_reinv["precoJusto"])

    # 14. Eliminação da dupla penalização de despesas adm e dedução de PIS/COFINS sobre JCP no SOTP
    def test_sotp_avoid_double_penalty_admin_expenses_and_pis_cofins(self):
        participacoes = [
            {
                "nome": "Itaú Unibanco",
                "ticker": "ITUB4",
                "quantidade_acoes": 100.0,
                "preco_mercado": 100.0,
                "preco_justo_intrinseco": 100.0,
                "dpa_esperado": 10.0,  # Proventos totais = 1000 Mi
            }
        ]
        res_abatido = calculate_sotp_holding(
            ticker="ITSA4",
            participacoes=participacoes,
            divida_liquida_holding=1000.0,
            num_acoes_holding=100.0,
            desconto_holding_adotado_pct=20.0,
            despesas_adm_holding=120.0,
            ke_holding=12.0,
            pct_jcp=50.0,
            deduzir_despesas_do_desconto=True,
        )
        res_duplo = calculate_sotp_holding(
            ticker="ITSA4",
            participacoes=participacoes,
            divida_liquida_holding=1000.0,
            num_acoes_holding=100.0,
            desconto_holding_adotado_pct=20.0,
            despesas_adm_holding=120.0,
            ke_holding=12.0,
            pct_jcp=50.0,
            deduzir_despesas_do_desconto=False,
        )
        # VP despesas = 1411.76 Mi; peso sobre (10000 - 1000) = 15.69% -> desconto residual = 4.31%
        self.assertEqual(res_abatido["detalhes"]["desconto_holding_residual_intrinseco_pct"], 4.31)
        self.assertGreater(res_abatido["precoJusto"], res_duplo["precoJusto"])
        # Vazamento PIS/COFINS sobre JCP: 1000 * 50% * 9.25% = 46.25 Mi
        # Fluxo líquido = 1000 - 120 - 46.25 = 833.75 Mi -> DPA = 8.3375
        self.assertEqual(res_abatido["detalhes"]["vazamento_pis_cofins_jcp_mi"], 46.25)
        self.assertEqual(res_abatido["detalhes"]["dpa_holding_projetado"], 8.3375)

    # 15. CLI holding repassa ntnb e carrega precoJusto diretamente do JSON da investida
    def test_cli_holding_passes_ntnb_and_reads_subsidiary_json(self):
        import json
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        import valuation_cli

        with tempfile.TemporaryDirectory() as tmpdir:
            inv_json_path = Path(tmpdir) / "ITUB4_valuation.json"
            out_json_path = Path(tmpdir) / "ITSA4_valuation.json"
            with open(inv_json_path, "w", encoding="utf-8") as f:
                json.dump({"ticker": "ITUB4", "precoJusto": 42.50, "precoTeto": 34.00}, f)

            test_args = [
                "valuation_cli.py",
                "--ano-base", "2026",
                "--trimestre-itr", "2",
                "--ntnb", "7.0",
                "holding",
                "--ticker", "ITSA4",
                "--investida-ticker", "ITUB4",
                "--investida-nome", "Itaú Unibanco",
                "--investida-valuation-json", str(inv_json_path),
                "--itub-acoes", "3500.0",
                "--itub-preco-mercado", "35.0",
                "--itub-dpa", "2.50",
                "--divida-holding", "3000.0",
                "--num-acoes", "10300.0",
                "--ke-holding", "10.0",
                "--out", str(out_json_path),
            ]
            captured = io.StringIO()
            with patch.object(sys, "argv", test_args), patch("sys.stdout", captured):
                valuation_cli.main()

            with open(out_json_path, "r", encoding="utf-8") as f_out:
                saved_data = json.load(f_out)

            # NTN-B = 7.0% -> Rf_nom = ((1.07 * 1.035) - 1) * 100 = 10.745% -> Ke_holding floor = 12.75%
            self.assertEqual(saved_data["wacc"], 12.75)
            self.assertEqual(saved_data["detalhes"]["participacoes"][0]["preco_justo_intrinseco"], 42.50)

    # 16. Blindagem estrita do Modo Cego em export.py (sem vazamento de yield_justo nem NAV bruto)
    def test_export_blind_mode_no_yield_or_nav_leak(self):
        # 1. Gordon/DDM com spread elevado: não deve vazar o yield_justo no aviso metodológico
        res_ddm = calculate_financials_ddm(
            ticker="CXSE3",
            vpa=4.60,
            roe=32.8,
            ke=17.1,
            cresc_perp=4.0,
            payout=90.0,
            num_acoes=3000.0,
        )
        yield_str = f"{res_ddm['detalhes']['dividend_yield_justo_pct']:.1f}%"
        buf_ddm = io.StringIO()
        old_stdout = sys.stdout
        try:
            sys.stdout = buf_ddm
            print_dossier_summary(res_ddm, "dummy_ddm.json")
        finally:
            sys.stdout = old_stdout
        out_ddm = buf_ddm.getvalue()
        self.assertNotIn(yield_str, out_ddm)

        # 2. SOTP Holding: não deve vazar total_intrinseco_bruto_mi nem total_mercado_bruto_mi
        res_sotp = calculate_sotp_holding(
            ticker="ITSA4",
            participacoes=[{
                "nome": "Itaú Unibanco",
                "ticker": "ITUB4",
                "quantidade_acoes": 3500.0,
                "preco_mercado": 34.0,
                "preco_justo_intrinseco": 41.23,
                "dpa_esperado": 2.40,
            }],
            divida_liquida_holding=3200.0,
            num_acoes_holding=10300.0,
        )
        buf_sotp = io.StringIO()
        try:
            sys.stdout = buf_sotp
            print_dossier_summary(res_sotp, "dummy_sotp.json")
        finally:
            sys.stdout = old_stdout
        out_sotp = buf_sotp.getvalue()
        self.assertIn("[Preservado no JSON para Modo Cego]", out_sotp)
        self.assertNotIn("144,305.00", out_sotp)
        self.assertNotIn("119,000.00", out_sotp)

    # 17. Roteador sem falsos positivos por substring em Segurança Eletrônica ou Holding Elétrica
    def test_router_no_false_positives_security_or_electric_holding(self):
        self.assertEqual(route_company("INTB3", "Segurança Eletrônica")["modelo_recomendado"], "dcf")
        self.assertEqual(route_company("B3SA3", "Serviços Financeiros")["modelo_recomendado"], "dcf")
        self.assertEqual(route_company("NEOE3", "Holding do Setor Elétrico")["modelo_recomendado"], "dcf")
        self.assertEqual(route_company("NOVO3", "Equipamentos de Segurança Patrimonial")["modelo_recomendado"], "dcf")
        self.assertEqual(route_company("ELEC3", "Holding de Energia Elétrica")["modelo_recomendado"], "dcf")

    # 18. Piso de WACC consciente do escudo fiscal da dívida (alavancagem ótima)
    def test_wacc_floor_with_debt_tax_shield(self):
        # NTN-B = 7.0%, IPCA = 3.5% -> Rf_nom = 10.745%
        # Sem alavancagem ótima: piso = 10.745 + 1.5 = 12.25%
        # Com alavancagem_otima_pct = 50% e T = 34%:
        # Ke_floor = 13.245%, Kd_liq_floor = 11.745 * 0.66 = 7.7517% -> WACC_floor = 10.50%
        res_com_escudo = calculate_dcf(
            ticker="TAEE11",
            fclf_inicial=1500.0,
            taxas_crescimento=[4.0, 3.5, 3.5],
            wacc=11.0,
            cresc_perp=3.5,
            divida_liquida=8000.0,
            num_acoes=344.5,
            ntnb=7.0,
            alavancagem_otima_pct=50.0,
        )
        self.assertEqual(res_com_escudo["wacc"], 11.0)

    def test_dcf_concession_and_j_curve_edge_cases(self):
        # 1. Curva J com decomposicao_g1 informada não deve lançar falso erro contra g1=0.0%
        res_j = calculate_dcf(
            ticker="SBSP3",
            fluxos_explicitos=[-500.0, -200.0, 300.0, 800.0, 1200.0],
            wacc=11.5,
            cresc_perp=3.5,
            divida_liquida=3000.0,
            num_acoes=683.5,
            ntnb=6.0,
            decomposicao_g1=[3.5, 1.5, 1.0],
        )
        self.assertGreater(res_j["precoJusto"], 0.0)
        self.assertEqual(res_j["detalhes"]["validacao_crescimento"]["decomposicao_g1"]["soma"], 6.0)

        # 2. Concessão com prazo remanescente menor que len(taxas_crescimento) trunca os anos explícitos
        res_3_from_5 = calculate_dcf(
            ticker="CCRO3",
            fclf_inicial=1000.0,
            taxas_crescimento=[4.0, 4.0, 4.0, 4.0, 4.0],
            wacc=11.5,
            cresc_perp=3.5,
            divida_liquida=0.0,
            num_acoes=1000.0,
            prazo_concessao_anos=3,
            rab_indenizavel_mi=1000.0,
        )
        res_3_exact = calculate_dcf(
            ticker="CCRO3",
            fclf_inicial=1000.0,
            taxas_crescimento=[4.0, 4.0, 4.0],
            wacc=11.5,
            cresc_perp=3.5,
            divida_liquida=0.0,
            num_acoes=1000.0,
            prazo_concessao_anos=3,
            rab_indenizavel_mi=1000.0,
        )
        self.assertEqual(res_3_from_5["anosProjecao"], 3)
        self.assertEqual(res_3_from_5["precoJusto"], res_3_exact["precoJusto"])
        self.assertEqual(res_3_from_5["detalhes"]["vp_terminal"], res_3_exact["detalhes"]["vp_terminal"])

        # 3. Prazo de concessão <= 0 deve lançar ValueError
        with self.assertRaises(ValueError):
            calculate_dcf(
                ticker="CCRO3",
                fclf_inicial=1000.0,
                taxas_crescimento=[4.0, 4.0],
                wacc=11.5,
                cresc_perp=3.5,
                divida_liquida=0.0,
                num_acoes=1000.0,
                prazo_concessao_anos=0,
            )

        # 4. validate_growth_and_market_share com lista vazia não deve lançar IndexError
        val_empty = validate_growth_and_market_share(fclf_inicial=100.0, taxas_crescimento=[], cresc_perp=3.5)
        self.assertFalse(val_empty["convergencia_perpetuidade"])

    def test_frontend_calculator_js_parity_all_models(self):
        import json
        import shutil
        import subprocess
        from pathlib import Path

        if not shutil.which("node"):
            self.skipTest("Node.js não disponível no ambiente")

        res_ddm = calculate_financials_ddm(
            ticker="BBAS3",
            vpa=30.0,
            roe=20.0,
            ke=14.0,
            cresc_perp=4.0,
            payout=40.0,
            num_acoes=2800.0,
        )
        res_j = calculate_dcf(
            ticker="SBSP3",
            fluxos_explicitos=[-500.0, -200.0, 300.0, 800.0, 1200.0],
            wacc=11.5,
            cresc_perp=3.5,
            divida_liquida=3000.0,
            num_acoes=683.5,
            ntnb=6.0,
        )
        res_saude = calculate_operadora_saude(
            ticker="ODPV3",
            receita_liquida=2000.0,
            sinistralidade_mlr_pct=70.0,
            despesas_adm_comerciais_pct=12.0,
            ganhos_float=40.0,
            despesas_juros_fixa=10.0,
            exigencia_capital_ans_pct=10.0,
            payout_sustentavel_pct=60.0,
            ke=13.0,
            cresc_perp=3.5,
            taxas_crescimento_receita=[10.0, 8.0, 6.0, 5.0, 4.0],
            num_acoes=500.0,
            ntnb=6.0,
            pct_jcp=30.0,
        )
        res_sotp = calculate_sotp_holding(
            ticker="ITSA4",
            participacoes=[{
                "nome": "Itaú Unibanco",
                "ticker": "ITUB4",
                "quantidade_acoes": 100.0,
                "preco_mercado": 100.0,
                "preco_justo_intrinseco": 100.0,
                "dpa_esperado": 10.0,
            }],
            divida_liquida_holding=1000.0,
            num_acoes_holding=100.0,
            desconto_holding_adotado_pct=20.0,
            despesas_adm_holding=120.0,
            ke_holding=12.0,
            pct_jcp=50.0,
        )

        js_path = Path(__file__).resolve().parent.parent / "frontend" / "static" / "calculator.js"
        node_script = """
const fs = require("fs");
let registeredFactory = null;
global.document = { addEventListener: (ev, cb) => { if (ev === "alpine:init") cb(); } };
global.Alpine = { data: (name, fn) => { registeredFactory = fn; } };
global.alert = (msg) => { throw new Error("Alert: " + msg); };
eval(fs.readFileSync(process.argv[1], "utf8"));

function evaluateModel(data) {
  const app = registeredFactory();
  app.buscarPrecoNaBrapi = () => {};
  app.jsonParaImportar = JSON.stringify(data);
  app.importarJSON();
  const ro = app.resultados;
  app.parametrosModificados = true;
  const rx = app.resultados;
  return {
    ro_precoJusto: Number(ro.precoJusto.toFixed(2)),
    rx_precoJusto: Number(rx.precoJusto.toFixed(2)),
    ro_somaPV: ro.somaPV ? Number(ro.somaPV.toFixed(2)) : 0,
    rx_somaPV: rx.somaPV ? Number(rx.somaPV.toFixed(2)) : 0,
    ro_dpaBazin: Number(ro.dpaBazin.toFixed(4)),
    rx_dpaBazin: Number(rx.dpaBazin.toFixed(4)),
    ro_tetoBazin6: Number(ro.tetoBazin6.toFixed(2)),
    rx_tetoBazin6: Number(rx.tetoBazin6.toFixed(2)),
  };
}
const payloads = JSON.parse(process.argv[2]);
const out = {};
for (const [k, v] of Object.entries(payloads)) {
  out[k] = evaluateModel(v);
}
console.log(JSON.stringify(out));
"""
        proc = subprocess.run(
            ["node", "-e", node_script, str(js_path), json.dumps({"ddm": res_ddm, "j": res_j, "saude": res_saude, "sotp": res_sotp})],
            capture_output=True,
            text=True,
            check=True,
        )
        js_out = json.loads(proc.stdout.strip())

        # Gordon DDM parity (effective payout 40% -> DPA 2.40, Teto Bazin 6% = 40.00, Preço Justo = 48.00)
        self.assertEqual(js_out["ddm"]["ro_precoJusto"], res_ddm["precoJusto"])
        self.assertEqual(js_out["ddm"]["rx_precoJusto"], res_ddm["precoJusto"])
        self.assertEqual(js_out["ddm"]["ro_dpaBazin"], 2.40)
        self.assertEqual(js_out["ddm"]["rx_dpaBazin"], 2.40)
        self.assertEqual(js_out["ddm"]["ro_tetoBazin6"], 40.00)
        self.assertEqual(js_out["ddm"]["rx_tetoBazin6"], 40.00)

        # J-Curve DCF parity
        self.assertEqual(js_out["j"]["ro_precoJusto"], res_j["precoJusto"])
        self.assertEqual(js_out["j"]["rx_precoJusto"], res_j["precoJusto"])
        self.assertEqual(js_out["j"]["ro_somaPV"], res_j["detalhes"]["soma_pv_fluxos"])
        self.assertEqual(js_out["j"]["rx_somaPV"], res_j["detalhes"]["soma_pv_fluxos"])

        # Saúde ANS parity (with voluntary retention reinvestment in float)
        self.assertEqual(js_out["saude"]["ro_precoJusto"], res_saude["precoJusto"])
        self.assertEqual(js_out["saude"]["rx_precoJusto"], res_saude["precoJusto"])
        self.assertEqual(js_out["saude"]["ro_dpaBazin"], res_saude["detalhes"]["metrica_bazin"]["dpa_liquido"])
        self.assertEqual(js_out["saude"]["rx_dpaBazin"], res_saude["detalhes"]["metrica_bazin"]["dpa_liquido"])

        # SOTP Holding parity
        self.assertEqual(js_out["sotp"]["ro_precoJusto"], res_sotp["precoJusto"])
        self.assertEqual(js_out["sotp"]["rx_precoJusto"], res_sotp["precoJusto"])
        self.assertEqual(js_out["sotp"]["ro_dpaBazin"], res_sotp["detalhes"]["metrica_bazin"]["dpa_liquido"])
        self.assertEqual(js_out["sotp"]["rx_dpaBazin"], res_sotp["detalhes"]["metrica_bazin"]["dpa_liquido"])


if __name__ == "__main__":
    unittest.main()

