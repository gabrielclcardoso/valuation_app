"""Roteador inteligente de elegibilidade e seleção de metodologia de valuation para a B3.
"""
from typing import Dict, Any

MAPA_TICKERS_CONHECIDOS = {
    # Bancos
    "ITUB3": "financials", "ITUB4": "financials",
    "BBAS3": "financials",
    "BBDC3": "financials", "BBDC4": "financials",
    "SANB3": "financials", "SANB4": "financials", "SANB11": "financials",
    "BPAC11": "financials", "ABCB4": "financials",
    
    # Seguradoras & Corretoras
    "BBSE3": "financials", "CXSE3": "financials", "PSSA3": "financials",

    # Holdings
    "ITSA3": "holding", "ITSA4": "holding",
    "BRAP3": "holding", "BRAP4": "holding",
    "SIMH3": "holding",

    # Operadoras de Saúde (ANS)
    "SAUD3": "saude", "HAPV3": "saude", "ODPV3": "saude",

    # Infraestrutura / Utilities / Indústria (DCF)
    "SAPR3": "dcf", "SAPR4": "dcf", "SAPR11": "dcf",
    "SBSP3": "dcf", "CSMG3": "dcf",
    "ALUP3": "dcf", "ALUP4": "dcf", "ALUP11": "dcf",
    "TAEE3": "dcf", "TAEE4": "dcf", "TAEE11": "dcf",
    "CPFE3": "dcf", "EGIE3": "dcf", "EQTL3": "dcf",
    "TIMS3": "dcf", "VIVT3": "dcf",
    "WEGE3": "dcf", "TUPY3": "dcf",
    "CCRO3": "dcf", "ECOR3": "dcf", "STBP3": "dcf",
    "RDOR3": "dcf", "FLRY3": "dcf",
}


def route_company(ticker: str, setor: str = "") -> Dict[str, Any]:
    """Retorna o modelo de valuation recomendado para o ticker ou setor informado."""
    tick = ticker.strip().upper()
    setor_lower = setor.strip().lower()

    if tick in MAPA_TICKERS_CONHECIDOS:
        modelo = MAPA_TICKERS_CONHECIDOS[tick]
    elif any(s in setor_lower for s in ["banco", "bancário", "financeiro"]):
        modelo = "financials"
    elif any(s in setor_lower for s in ["segur", "previdência", "corretora"]):
        modelo = "financials"
    elif "holding" in setor_lower:
        modelo = "holding"
    elif any(s in setor_lower for s in ["operadora de saúde", "plano de saúde", "saúde suplementar"]):
        modelo = "saude"
    else:
        # Default para concessões, utilities e indústrias
        modelo = "dcf"

    descricoes = {
        "dcf": {
            "metodologia": "DCF por FCFF (Fluxo Livre da Firma descontado por WACC)",
            "script": "calc_dcf.py",
            "justificativa": "Empresa intensiva em capital, concessão ou indústria com geração operacional e dívida financeira estruturada.",
        },
        "financials": {
            "metodologia": "Gordon Growth (ROE vs Ke) & DDM de Dividendos",
            "script": "calc_financials.py",
            "justificativa": "Instituição financeira ou seguradora onde dívida/depósitos são operacionais e a geração livre ao acionista é o dividendo regulatório.",
        },
        "holding": {
            "metodologia": "SOTP (Soma das Partes a Valor Intrínseco) & Desconto de Holding",
            "script": "calc_holding.py",
            "justificativa": "Holding pura ou mista com receitas de equivalência patrimonial e participações em empresas investidas.",
        },
        "saude": {
            "metodologia": "DDM / FCFE Regulatório com Restrição de Solvência da ANS",
            "script": "calc_saude.py",
            "justificativa": "Operadora de planos de saúde sujeita a provisões técnicas e exigências de capital mínimo da ANS.",
        },
    }

    return {
        "ticker": tick,
        "modelo_recomendado": modelo,
        **descricoes[modelo],
    }
