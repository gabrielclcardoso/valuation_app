"""Motor de Valuation para Instituições Financeiras (Bancos e Seguradoras).
Metodologia: Dividend Discount Model (DDM) e Modelo de Gordon via ROE vs Ke (P/VP Justo).
Ideal para: Itaú (ITUB4), Banco do Brasil (BBAS3), Bradesco (BBDC4), Santander (SANB11),
BB Seguridade (BBSE3), Caixa Seguridade (CXSE3).
"""
from typing import List, Dict, Any, Optional
from valuation_engine.bazin import calculate_bazin


def calculate_financials_ddm(
    ticker: str,
    vpa: float,
    roe: float,
    ke: float,
    cresc_perp: float,
    payout: float = 50.0,
    dpa_projetado: Optional[float] = None,
    taxas_crescimento_dpa: Optional[List[float]] = None,
    num_acoes: float = 1.0,
    margem_seguranca: float = 20.0,
    tipo: str = "banco",
    empresa: str = "",
    setor: str = "",
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Calcula o Preço Justo e Preço Teto para Bancos e Seguradoras via Gordon e DDM.
    
    Args:
        ticker: Ticker do ativo (ex: ITUB4, BBAS3, CXSE3)
        vpa: Valor Patrimonial por Ação do último ITR/DFP (R$)
        roe: Retorno sobre o Patrimônio Líquido sustentável (%)
        ke: Custo do Capital Próprio via CAPM (% a.a.)
        cresc_perp: Taxa de crescimento do lucro/dividendo na perpetuidade (% a.a.)
        payout: Percentual do lucro distribuído como proventos (% - padrão 50%)
        dpa_projetado: DPA sustentável projetado (R$); se omitido, calcula via VPA * ROE * Payout
        taxas_crescimento_dpa: Trajetória de crescimento do dividendo nos anos explícitos (%)
        num_acoes: Total de ações emitidas (Milhões)
        margem_seguranca: Margem de segurança aplicada ao Preço Justo (%)
        tipo: 'banco' ou 'seguradora'
        empresa: Nome da instituição
        setor: Setor de atuação
        metadata: Informações e premissas complementares
    """
    ke_dec = float(ke) / 100.0
    g_perp_dec = float(cresc_perp) / 100.0
    roe_dec = float(roe) / 100.0
    vpa_val = float(vpa)
    payout_dec = float(payout) / 100.0

    if ke_dec <= g_perp_dec:
        raise ValueError(
            f"O Custo de Capital Próprio Ke ({ke}%) deve ser estritamente maior que o Crescimento Perpétuo ({cresc_perp}%)."
        )
    if vpa_val <= 0:
        raise ValueError("O VPA (Valor Patrimonial por Ação) deve ser maior que zero.")

    # 1. Modelo de Gordon Fundamentalista via P/VP Justo:
    # P/VP Justo = (ROE - g) / (Ke - g)
    p_vp_justo = max(0.0, (roe_dec - g_perp_dec) / (ke_dec - g_perp_dec))
    preco_justo_gordon = p_vp_justo * vpa_val

    # 2. Definição do DPA base
    # Se DPA não foi fixado manualmente, calcula com base no lucro por ação teórico: LPA = VPA * ROE
    lpa_teorico = vpa_val * roe_dec
    if dpa_projetado is not None and dpa_projetado > 0:
        dpa_base = float(dpa_projetado)
    else:
        dpa_base = lpa_teorico * payout_dec

    # 3. DDM Multiestágio (se fornecido) ou Perpetuidade Direta
    taxas = taxas_crescimento_dpa if taxas_crescimento_dpa else [float(cresc_perp)] * 5
    dpa_atual = dpa_base
    soma_pv_dpa = 0.0
    projecoes = []

    for t, taxa in enumerate(taxas, start=1):
        g_dec = float(taxa) / 100.0
        dpa_atual = dpa_atual * (1.0 + g_dec)
        pv = dpa_atual / ((1.0 + ke_dec) ** t)
        soma_pv_dpa += pv
        projecoes.append(
            {
                "ano": t,
                "crescimento_pct": round(float(taxa), 2),
                "dpa_projetado": round(dpa_atual, 4),
                "valor_presente": round(pv, 4),
            }
        )

    # Valor Terminal dos Dividendos
    dpa_terminal = dpa_atual * (1.0 + g_perp_dec)
    valor_terminal_dpa = dpa_terminal / (ke_dec - g_perp_dec)
    vp_terminal_dpa = valor_terminal_dpa / ((1.0 + ke_dec) ** len(taxas))

    preco_justo_ddm = soma_pv_dpa + vp_terminal_dpa

    # Preço Justo Final Ponderado ou Conservador:
    # Para bancos e seguradoras, adotamos o menor entre Gordon e DDM como preço conservador
    preco_justo_adotado = min(preco_justo_gordon, preco_justo_ddm)
    preco_teto_adotado = preco_justo_adotado * (1.0 - (float(margem_seguranca) / 100.0))

    # Métrica Bazin
    metrica_bazin = calculate_bazin(dpa=dpa_base, preco_teto_modelo=preco_teto_adotado)

    # Total de dividendos pagos (para compatibilidade com campos do App: FCLF do Acionista = DPA * Ações)
    total_proventos_ano = round(dpa_base * float(num_acoes), 2)

    meta = metadata.copy() if metadata else {}
    if empresa:
        meta["empresa"] = empresa
    if setor:
        meta["setor"] = setor
    meta["tipo_instituicao"] = tipo

    return {
        "ticker": ticker.upper(),
        "modelo": "gordon_ddm",
        "fclf": total_proventos_ano,  # No caso financeiro, o fluxo livre é o fluxo de dividendos
        "anosProjecao": len(taxas),
        "taxasCrescimento": [round(float(t), 2) for t in taxas],
        "wacc": round(float(ke), 2),  # Ke substitui WACC
        "crescPerp": round(float(cresc_perp), 2),
        "dividaLiquida": 0.0,  # Em bancos e seguradoras, dívida operacional já está precificada
        "numAcoes": round(float(num_acoes), 2),
        "margemSeguranca": round(float(margem_seguranca), 2),
        "precoJusto": round(preco_justo_adotado, 2),
        "precoTeto": round(preco_teto_adotado, 2),
        "detalhes": {
            "modelo_utilizado": f"Financeiro ({tipo.capitalize()}): Gordon Growth (ROE vs Ke) & DDM",
            "vpa": round(vpa_val, 2),
            "roe_adotado_pct": round(float(roe), 2),
            "ke_adotado_pct": round(float(ke), 2),
            "p_vp_justo_gordon": round(p_vp_justo, 3),
            "payout_sustentavel_pct": round(float(payout), 2),
            "lpa_projetado": round(lpa_teorico, 2),
            "dpa_ano_base": round(dpa_base, 4),
            "cenarios": {
                "modelo_gordon": {
                    "descricao": "Avaliação Patrimonial por ROE vs Custo de Capital (P/VP Justo)",
                    "p_vp_justo": round(p_vp_justo, 3),
                    "preco_justo": round(preco_justo_gordon, 2),
                    "preco_teto": round(preco_justo_gordon * (1.0 - float(margem_seguranca) / 100.0), 2),
                },
                "modelo_ddm": {
                    "descricao": "Desconto dos Fluxos de Proventos Futuros (DDM Multiestágio)",
                    "preco_justo": round(preco_justo_ddm, 2),
                    "preco_teto": round(preco_justo_ddm * (1.0 - float(margem_seguranca) / 100.0), 2),
                },
            },
            "metrica_bazin": metrica_bazin,
            "projecoes_dpa": projecoes,
            "metadata": meta,
        },
    }
