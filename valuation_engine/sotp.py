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
    ke_holding: float = 12.0,
    pct_jcp: float = 0.0,
    empresa: str = "Itaúsa",
    setor: str = "Holding Financeira / Conglomerado",
    metadata: Optional[Dict[str, Any]] = None,
    ntnb: float = 6.0,
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
        ke_holding: Taxa de desconto para capitalizar despesas administrativas da holding (% a.a.)
        pct_jcp: Percentual dos proventos pagos sob a forma de JCP bruto (%)
        empresa: Nome corporativo
        setor: Setor
        metadata: Premissas e justificativas adicionais
        ntnb: Taxa da NTN-B para ancoragem de risco (Custo de Capital)
    """
    ke_holding = max(float(ke_holding), float(ntnb) + 5.0)

    if num_acoes_holding <= 0:
        raise ValueError("O número de ações da holding deve ser maior que zero.")
    if not participacoes:
        raise ValueError("A holding deve possuir ao menos uma participação societária/investida no SOTP.")

    total_mercado_bruto = 0.0
    total_intrinseco_bruto = 0.0
    total_proventos_recebidos = 0.0
    detalhes_participacoes = []
    avisos = []

    for part in participacoes:
        nome = part.get("nome", "Ativo")
        tick = part.get("ticker", "").upper()
        qtd = float(part.get("quantidade_acoes", 0.0))
        p_mercado = float(part.get("preco_mercado", 0.0))
        p_intrinseco_val = part.get("preco_justo_intrinseco")

        # Validação do preço justo intrínseco das investidas:
        # Se omitido, alerta explicitamente que foi usado fallback para preço de mercado
        if p_intrinseco_val is not None and float(p_intrinseco_val) > 0:
            p_intrinseco = float(p_intrinseco_val)
            usou_fallback = False
            fonte = "intrinseco_calculado"
        else:
            raise ValueError(
                f"SOTP Violado: A investida '{nome}' não possui preço justo intrínseco informado. "
                "O uso de cotação de mercado como fallback para investidas principais é proibido."
            )

        val_mercado = qtd * p_mercado
        val_intrinseco = qtd * p_intrinseco
        dpa_investida = float(part.get("dpa_esperado", 0.0))
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
                "usou_fallback_mercado": usou_fallback,
                "fonte_preco_intrinseco": fonte,
                "valor_mercado_bruto_mi": round(val_mercado, 2),
                "valor_intrinseco_bruto_mi": round(val_intrinseco, 2),
                "dpa_recebido_pela_holding": round(dpa_investida, 4),
                "proventos_totais_mi": round(proventos, 2),
            }
        )

    # Dívida Líquida e Despesas Administrativas da Holding deduzidas a Valor Presente do NAV
    div_holding = float(divida_liquida_holding)
    desp_adm = float(despesas_adm_holding)
    ke_h_dec = float(ke_holding) / 100.0

    g_inflacao = 0.035
    if desp_adm > 0 and ke_h_dec > g_inflacao:
        vp_despesas_adm = desp_adm / (ke_h_dec - g_inflacao)
    else:
        vp_despesas_adm = 0.0

    desconto_dec = float(desconto_holding_adotado_pct) / 100.0

    # 1. NAV a Valor de Mercado (Bolsa) deduzindo dívida e VP das despesas
    nav_mercado_liquido = total_mercado_bruto - div_holding - vp_despesas_adm
    preco_mercado_sem_desconto = max(0.0, nav_mercado_liquido / float(num_acoes_holding))
    preco_mercado_com_desconto = preco_mercado_sem_desconto * (1.0 - desconto_dec)

    # 2. NAV a Valor Intrínseco (Fundamentalista) deduzindo dívida e VP das despesas
    nav_intrinseco_liquido = total_intrinseco_bruto - div_holding - vp_despesas_adm
    preco_intrinseco_sem_desconto = max(0.0, nav_intrinseco_liquido / float(num_acoes_holding))
    preco_justo_intrinseco_com_desconto = preco_intrinseco_sem_desconto * (1.0 - desconto_dec)

    # Preço Justo Adotado = SOTP Intrínseco com Desconto
    preco_justo_final = preco_justo_intrinseco_com_desconto
    preco_teto_final = preco_justo_final * (1.0 - (float(margem_seguranca) / 100.0))

    # Estimativa de DPA da Holding (se não informado, calcula via proventos recebidos menos despesas)
    if dpa_projetado_holding is not None and dpa_projetado_holding > 0:
        dpa_holding = float(dpa_projetado_holding)
    else:
        fluxo_liquido_holding = max(0.0, total_proventos_recebidos - desp_adm)
        dpa_holding = fluxo_liquido_holding / float(num_acoes_holding)

    # Métrica Bazin
    metrica_bazin = calculate_bazin(
        dpa=dpa_holding,
        preco_teto_modelo=preco_teto_final,
        pct_jcp=pct_jcp,
    )

    meta = metadata.copy() if metadata else {}
    if empresa:
        meta["empresa"] = empresa
    if setor:
        meta["setor"] = setor

    return {
        "ticker": ticker.upper(),
        "modelo": "sotp_holding",
        "fclf": round(total_proventos_recebidos, 2),
        "anosProjecao": 5,
        "taxasCrescimento": [5.0, 5.0, 5.0, 5.0, 5.0],
        "wacc": round(float(ke_holding), 2),
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
            "despesas_adm_holding_anual_mi": round(desp_adm, 2),
            "vp_despesas_adm_holding_mi": round(vp_despesas_adm, 2),
            "taxa_desconto_holding_ke_pct": round(float(ke_holding), 2),
            "nav_mercado_liquido_mi": round(nav_mercado_liquido, 2),
            "nav_intrinseco_liquido_mi": round(nav_intrinseco_liquido, 2),
            "desconto_holding_adotado_pct": round(float(desconto_holding_adotado_pct), 2),
            "dpa_holding_projetado": round(dpa_holding, 4),
            "avisos": avisos,
            "possui_fallback_mercado": len(avisos) > 0,
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
