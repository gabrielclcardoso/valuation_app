"""Módulo centralizado para cálculo de métricas previdenciárias de Décio Bazin.
Utilizado transversalmente por todos os modelos de valuation (DCF, DDM, SOTP, Saúde).
"""
from typing import Dict, Any, Optional


def calculate_bazin(
    dpa: float,
    preco_teto_modelo: float,
    taxa_padrao: float = 0.06,
    taxa_exigente: float = 0.08,
    pct_jcp: float = 0.0,
    aliquota_irrf_jcp: float = 15.0,
) -> Optional[Dict[str, Any]]:
    """Calcula os Preços Tetos de Bazin e o Yield-on-Cost resultante no Preço Teto do modelo,
    suportando retenção de IRRF sobre JCP (15% na fonte para investidor pessoa física).
    
    Args:
        dpa: Proventos Totais por Ação anuais projetados em regime sustentável (R$)
        preco_teto_modelo: Preço Teto calculado pelo modelo de valuation (DCF, DDM, SOTP)
        taxa_padrao: Taxa padrão de Décio Bazin (padrão 6% a.a.)
        taxa_exigente: Taxa exigente para ambientes de juros altos (padrão 8% a.a.)
        pct_jcp: Percentual dos proventos totais pagos sob a forma de JCP bruto (0% a 100%)
        aliquota_irrf_jcp: Alíquota de IRRF retido na fonte sobre JCP (padrão 15.0%)
        
    Returns:
        Dicionário com as métricas de Bazin calculadas sobre proventos líquidos ou None se dpa <= 0
    """
    if dpa is None or dpa <= 0:
        return None

    dpa_bruto = float(dpa)
    jcp_ratio = max(0.0, min(1.0, float(pct_jcp) / 100.0))
    irrf_rate = max(0.0, float(aliquota_irrf_jcp) / 100.0)

    # Proventos líquidos de IRRF: Dividendos são isentos, JCP sofre retenção de 15% na fonte
    # dpa_liquido = dpa_bruto * [(1 - jcp_ratio) + jcp_ratio * (1 - irrf_rate)]
    fator_liquido = (1.0 - jcp_ratio) + (jcp_ratio * (1.0 - irrf_rate))
    dpa_liquido = dpa_bruto * fator_liquido

    teto_padrao = dpa_liquido / taxa_padrao if taxa_padrao > 0 else 0.0
    teto_exigente = dpa_liquido / taxa_exigente if taxa_exigente > 0 else 0.0
    
    # Yield-on-Cost líquido que o investidor terá comprando exatamente no Preço Teto do valuation
    yoc_no_teto = (dpa_liquido / preco_teto_modelo * 100.0) if preco_teto_modelo > 0 else 0.0

    return {
        "dpa_projetado": round(dpa_liquido, 4),
        "dpa_bruto": round(dpa_bruto, 4),
        "dpa_liquido": round(dpa_liquido, 4),
        "pct_jcp": round(float(pct_jcp), 1),
        "aliquota_irrf_jcp": round(float(aliquota_irrf_jcp), 1),
        "taxa_padrao_pct": round(taxa_padrao * 100.0, 1),
        "taxa_exigente_pct": round(taxa_exigente * 100.0, 1),
        f"preco_teto_bazin_{int(taxa_padrao*100)}pct": round(teto_padrao, 2),
        f"preco_teto_bazin_{int(taxa_exigente*100)}pct": round(teto_exigente, 2),
        "yield_on_cost_no_preco_teto_modelo": round(yoc_no_teto, 2),
    }
