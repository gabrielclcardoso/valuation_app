"""Valuation Engine - Biblioteca de Valuation Fundamentalista para a B3.
Engloba:
- DCF por FCFF (Concessões, Saneamento, Energia, Indústria, Hospitais)
- DDM & Gordon Growth (Bancos, Seguradoras e Bancassurance)
- SOTP a Valor Intrínseco & Mercado (Holdings)
- DDM Regulatório ANS (Operadoras de Saúde)
- Métricas Previdenciárias de Décio Bazin (6% e 8% Yield-on-Cost)
"""
from valuation_engine.bazin import calculate_bazin
from valuation_engine.dcf import calculate_dcf, calculate_cagr, validate_growth_and_market_share
from valuation_engine.ddm import calculate_financials_ddm
from valuation_engine.sotp import calculate_sotp_holding
from valuation_engine.saude import calculate_operadora_saude
from valuation_engine.router import route_company
from valuation_engine.export import save_valuation_json, print_dossier_summary

__all__ = [
    "calculate_bazin",
    "calculate_dcf",
    "calculate_cagr",
    "validate_growth_and_market_share",
    "calculate_financials_ddm",
    "calculate_sotp_holding",
    "calculate_operadora_saude",
    "route_company",
    "save_valuation_json",
    "print_dossier_summary",
]
