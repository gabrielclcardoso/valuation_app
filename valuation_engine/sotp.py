"""Motor de Valuation para Holdings (ex: Itaúsa - ITSA4).
Metodologia: SOTP (Sum of the Parts / Soma das Partes) a Valor Intrínseco e a Valor de Mercado,
dedução de dívida própria da holding e aplicação do Desconto Estrutural de Holding.
"""
from typing import List, Dict, Any, Optional
from valuation_engine.bazin import calculate_bazin


def calculate_sotp_holding(
    ticker: str,
    participacoes: List[Dict[str, Any]],
    divida_liquida_holding: float,
    num_acoes_holding: float,
    desconto_holding_adotado_pct: float = 20.0,
    margem_seguranca: float = 20.0,
    dpa_projetado_holding: Optional[float] = None,
    despesas_adm_holding: float = 0.0,
    empresa: str = "Itaúsa",
    setor: str = "Holding Financeira / Conglomerado",
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Calcula o Valuation SOTP Intrínseco e de Mercado para Holdings.
    
    Args:
        ticker: Ticker da holding (ex: ITSA4)
        participacoes: Lista de participações, onde cada item contém:
            - 'nome': Nome da empresa investida (ex: 'Itaú Unibanco')
            - 'ticker': Ticker da investida (ex: 'ITUB4')
            - 'quantidade_acoes': Quantidade de ações que a holding detém (em Milhões)
            - 'preco_mercado': Cotação atual de tela na B3 (R$)
            - 'preco_justo_intrinseco': Preço justo calculado da investida via Gordon/DCF (R$)
            - 'dpa_esperado': Dividendo por ação pago pela investida à holding (R$)
        divida_liquida_holding: Dívida líquida exclusiva da holding (R$ Milhões)
        num_acoes_holding: Total de ações emitidas pela holding (Milhões)
        desconto_holding_adotado_pct: Desconto de holding considerado justo/estrutural (%)
        margem_seguranca: Margem de segurança aplicada ao Preço Justo (%)
        dpa_projetado_holding: DPA projetado da própria holding para métrica Bazin (R$)
        despesas_adm_holding: Despesas operacionais anuais da holding (R$ Milhões)
        empresa: Nome corporativo
        setor: Setor
        metadata: Premissas e justificativas adicionais
    """
    if num_acoes_holding <= 0:
        raise ValueError("O número de ações da holding deve ser maior que zero.")

    total_mercado_bruto = 0.0
    total_intrinseco_bruto = 0.0
    total_proventos_recebidos = 0.0
    detalhes_participacoes = []

    for part in participacoes:
        nome = part.get("nome", "Ativo")
        tick = part.get("ticker", "").upper()
        qtd = float(part.get("quantidade_acoes", 0.0))
        p_mercado = float(part.get("preco_mercado", 0.0))
        p_intrinseco = float(part.get("preco_justo_intrinseco", p_mercado))
        dpa_investida = float(part.get("dpa_esperado", 0.0))

        val_mercado = qtd * p_mercado
        val_intrinseco = qtd * p_intrinseco
        proventos = qtd * dpa_investida

        total_mercado_bruto += val_mercado
        total_intrinseco_bruto += val_intrinseco
        total_proventos_recebidos += proventos

        detalhes_participacoes.append(
            {
                "nome": nome,
                "ticker": tick,
                "quantidade_acoes_mi": round(qtd, 2),
                "preco_mercado": round(p_mercado, 2),
                "preco_justo_intrinseco": round(p_intrinseco, 2),
                "valor_mercado_bruto_mi": round(val_mercado, 2),
                "valor_intrinseco_bruto_mi": round(val_intrinseco, 2),
                "dpa_recebido_pela_holding": round(dpa_investida, 4),
                "proventos_totais_mi": round(proventos, 2),
            }
        )

    # Dívida Líquida da Holding
    div_holding = float(divida_liquida_holding)
    desconto_dec = float(desconto_holding_adotado_pct) / 100.0

    # 1. NAV a Valor de Mercado (Bolsa)
    nav_mercado_liquido = total_mercado_bruto - div_holding
    preco_mercado_sem_desconto = max(0.0, nav_mercado_liquido / float(num_acoes_holding))
    preco_mercado_com_desconto = preco_mercado_sem_desconto * (1.0 - desconto_dec)

    # 2. NAV a Valor Intrínseco (Fundamentalista - Proteção contra bolsas esticadas)
    nav_intrinseco_liquido = total_intrinseco_bruto - div_holding
    preco_intrinseco_sem_desconto = max(0.0, nav_intrinseco_liquido / float(num_acoes_holding))
    preco_justo_intrinseco_com_desconto = preco_intrinseco_sem_desconto * (1.0 - desconto_dec)

    # Preço Justo Adotado = SOTP Intrínseco com Desconto
    preco_justo_final = preco_justo_intrinseco_com_desconto
    preco_teto_final = preco_justo_final * (1.0 - (float(margem_seguranca) / 100.0))

    # Estimativa de DPA da Holding (se não informado, calcula via proventos recebidos menos custos da holding)
    if dpa_projetado_holding is not None and dpa_projetado_holding > 0:
        dpa_holding = float(dpa_projetado_holding)
    else:
        fluxo_liquido_holding = max(0.0, total_proventos_recebidos - float(despesas_adm_holding))
        dpa_holding = fluxo_liquido_holding / float(num_acoes_holding)

    # Métrica Bazin
    metrica_bazin = calculate_bazin(dpa=dpa_holding, preco_teto_modelo=preco_teto_final)

    meta = metadata.copy() if metadata else {}
    if empresa:
        meta["empresa"] = empresa
    if setor:
        meta["setor"] = setor

    return {
        "ticker": ticker.upper(),
        "modelo": "sotp_holding",
        "fclf": round(total_proventos_recebidos, 2),  # Proventos totais gerados pelas investidas
        "anosProjecao": 5,
        "taxasCrescimento": [5.0, 5.0, 5.0, 5.0, 5.0],
        "wacc": 12.0,
        "crescPerp": 3.0,
        "dividaLiquida": round(div_holding, 2),
        "numAcoes": round(float(num_acoes_holding), 2),
        "margemSeguranca": round(float(margem_seguranca), 2),
        "precoJusto": round(preco_justo_final, 2),
        "precoTeto": round(preco_teto_final, 2),
        "detalhes": {
            "modelo_utilizado": "SOTP (Soma das Partes) a Valor Intrínseco com Desconto de Holding",
            "total_mercado_bruto_mi": round(total_mercado_bruto, 2),
            "total_intrinseco_bruto_mi": round(total_intrinseco_bruto, 2),
            "divida_liquida_holding_mi": round(div_holding, 2),
            "nav_mercado_liquido_mi": round(nav_mercado_liquido, 2),
            "nav_intrinseco_liquido_mi": round(nav_intrinseco_liquido, 2),
            "desconto_holding_adotado_pct": round(float(desconto_holding_adotado_pct), 2),
            "dpa_holding_projetado": round(dpa_holding, 4),
            "participacoes": detalhes_participacoes,
            "cenarios": {
                "sotp_mercado": {
                    "descricao": "SOTP baseado na cotação de mercado atual das investidas na B3",
                    "nav_liquido_mi": round(nav_mercado_liquido, 2),
                    "preco_sem_desconto": round(preco_mercado_sem_desconto, 2),
                    "preco_com_desconto": round(preco_mercado_com_desconto, 2),
                    "preco_teto": round(preco_mercado_com_desconto * (1.0 - float(margem_seguranca) / 100.0), 2),
                },
                "sotp_intrinseco": {
                    "descricao": "SOTP fundamentalista usando o Valor Justo intrínseco das investidas",
                    "nav_liquido_mi": round(nav_intrinseco_liquido, 2),
                    "preco_sem_desconto": round(preco_intrinseco_sem_desconto, 2),
                    "preco_com_desconto": round(preco_justo_intrinseco_com_desconto, 2),
                    "preco_teto": round(preco_teto_final, 2),
                },
            },
            "metrica_bazin": metrica_bazin,
            "metadata": meta,
        },
    }
