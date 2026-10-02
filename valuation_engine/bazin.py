"""Módulo centralizado para cálculo de métricas previdenciárias de Décio Bazin.
Utilizado transversalmente por todos os modelos de valuation (DCF, DDM, SOTP, Saúde).
"""
from typing import Dict, Any, Optional


def calculate_bazin(
    dpa: float,
    preco_teto_modelo: float,
    taxa_padrao: float = 0.06,
    taxa_exigente: float = 0.08,
) -> Optional[Dict[str, Any]]:
    """Calcula os Preços Tetos de Bazin e o Yield-on-Cost resultante no Preço Teto do modelo.
    
    Args:
        dpa: Dividendo por Ação anual projetado em regime sustentável (R$)
        preco_teto_modelo: Preço Teto calculado pelo modelo de valuation (DCF, DDM, SOTP)
        taxa_padrao: Taxa padrão de Décio Bazin (padrão 6% a.a.)
        taxa_exigente: Taxa exigente para ambientes de juros altos (padrão 8% a.a.)
        
    Returns:
        Dicionário com as métricas de Bazin ou None se dpa <= 0
    """
    if dpa is None or dpa <= 0:
        return None

    dpa_val = float(dpa)
    teto_padrao = dpa_val / taxa_padrao if taxa_padrao > 0 else 0.0
    teto_exigente = dpa_val / taxa_exigente if taxa_exigente > 0 else 0.0
    
    # Yield-on-Cost que o investidor terá comprando exatamente no Preço Teto do valuation
    yoc_no_teto = (dpa_val / preco_teto_modelo * 100.0) if preco_teto_modelo > 0 else 0.0

    return {
        "dpa_projetado": round(dpa_val, 4),
        "taxa_padrao_pct": round(taxa_padrao * 100.0, 1),
        "taxa_exigente_pct": round(taxa_exigente * 100.0, 1),
        f"preco_teto_bazin_{int(taxa_padrao*100)}pct": round(teto_padrao, 2),
        f"preco_teto_bazin_{int(taxa_exigente*100)}pct": round(teto_exigente, 2),
        "yield_on_cost_no_preco_teto_modelo": round(yoc_no_teto, 2),
    }
