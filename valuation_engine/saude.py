"""Motor de Valuation para o Setor de Saúde (B3).
Distingue com rigor:
1. Operadoras de Planos de Saúde (BradSaúde/SAUD3, Hapvida, Odontoprev):
   Reguladas pela ANS, sujeitas a Capital Baseado em Risco (CBR), Provisões Técnicas e Sinistralidade (MLR).
   Avaliadas via FCFE Regulatório ou DDM com taxa Ke.
2. Hospitais e Diagnósticos (Rede D'Or, Fleury):
   Operações intensivas em ativos reais (leitos/equipamentos). Avaliadas via DCF FCFF tradicional.
"""
from typing import List, Dict, Any, Optional
from valuation_engine.bazin import calculate_bazin
from valuation_engine.dcf import calculate_dcf


def calculate_operadora_saude(
    ticker: str,
    receita_liquida: float,
    sinistralidade_mlr_pct: float,
    despesas_adm_comerciais_pct: float,
    resultado_financeiro: float,
    aliquota_ir_csll_pct: float = 34.0,
    exigencia_capital_ans_pct: float = 10.0,
    payout_sustentavel_pct: float = 60.0,
    ke: float = 13.0,
    cresc_perp: float = 3.5,
    num_acoes: float = 1.0,
    margem_seguranca: float = 20.0,
    taxas_crescimento_receita: Optional[List[float]] = None,
    empresa: str = "BradSaúde",
    setor: str = "Saúde Suplementar / Operadora ANS",
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Calcula o Valuation para Operadoras de Planos de Saúde considerando regulação da ANS.
    
    Args:
        ticker: Ticker do ativo (ex: SAUD3, HAPV3, ODPV3)
        receita_liquida: Receita Líquida anual (contraprestações dos beneficiários) em R$ Mi
        sinistralidade_mlr_pct: Índice de sinistralidade médica (Eventos / Receita Líquida %)
        despesas_adm_comerciais_pct: Despesas administrativas e comerciais sobre a receita (%)
        resultado_financeiro: Resultado financeiro líquido gerado pelo float das reservas técnicas (R$ Mi)
        aliquota_ir_csll_pct: Alíquota efetiva de tributação (%)
        exigencia_capital_ans_pct: Retenção de capital necessária para suprir Margem de Solvência da ANS (%)
        payout_sustentavel_pct: Payout dos lucros distribuíveis após recompor exigência da ANS (%)
        ke: Custo de Capital Próprio via CAPM (% a.a.)
        cresc_perp: Crescimento perpétuo (% a.a.)
        num_acoes: Total de ações em Milhões
        margem_seguranca: Margem de segurança (%)
        taxas_crescimento_receita: Trajetória de crescimento da base de vidas/receita (%)
        empresa: Nome da empresa
        setor: Setor
        metadata: Premissas complementares
    """
    ke_dec = float(ke) / 100.0
    g_perp_dec = float(cresc_perp) / 100.0

    if ke_dec <= g_perp_dec:
        raise ValueError(f"Ke ({ke}%) deve ser maior que o Crescimento Perpétuo ({cresc_perp}%).")
    if num_acoes <= 0:
        raise ValueError("O número de ações deve ser maior que zero.")

    # 1. Demonstração de Resultado Normalizada da Operadora
    rec = float(receita_liquida)
    eventos_assistenciais = rec * (float(sinistralidade_mlr_pct) / 100.0)
    despesas_op = rec * (float(despesas_adm_comerciais_pct) / 100.0)
    ebit_operadora = rec - eventos_assistenciais - despesas_op
    lair = ebit_operadora + float(resultado_financeiro)
    ir_csll = max(0.0, lair * (float(aliquota_ir_csll_pct) / 100.0))
    lucro_liquido_base = lair - ir_csll

    # Retenção obrigatória para atendimento da Margem de Solvência da ANS (CBR)
    retencao_ans = lucro_liquido_base * (float(exigencia_capital_ans_pct) / 100.0)
    lucro_distribuivel = max(0.0, lucro_liquido_base - retencao_ans)
    total_proventos_base = lucro_distribuivel * (float(payout_sustentavel_pct) / 100.0)
    dpa_base = total_proventos_base / float(num_acoes)

    # 2. DDM Multiestágio dos Fluxos Distribuíveis aos Acionistas
    taxas = taxas_crescimento_receita if taxas_crescimento_receita else [float(cresc_perp)] * 5
    dpa_atual = dpa_base
    soma_pv = 0.0
    projecoes = []

    for t, taxa in enumerate(taxas, start=1):
        g_dec = float(taxa) / 100.0
        dpa_atual = dpa_atual * (1.0 + g_dec)
        pv = dpa_atual / ((1.0 + ke_dec) ** t)
        soma_pv += pv
        projecoes.append(
            {
                "ano": t,
                "crescimento_pct": round(float(taxa), 2),
                "dpa_projetado": round(dpa_atual, 4),
                "valor_presente": round(pv, 4),
            }
        )

    # Valor Terminal
    dpa_terminal = dpa_atual * (1.0 + g_perp_dec)
    valor_terminal = dpa_terminal / (ke_dec - g_perp_dec)
    vp_terminal = valor_terminal / ((1.0 + ke_dec) ** len(taxas))

    preco_justo = max(0.0, soma_pv + vp_terminal)
    preco_teto = preco_justo * (1.0 - (float(margem_seguranca) / 100.0))

    # Métrica Bazin
    metrica_bazin = calculate_bazin(dpa=dpa_base, preco_teto_modelo=preco_teto)

    meta = metadata.copy() if metadata else {}
    if empresa:
        meta["empresa"] = empresa
    if setor:
        meta["setor"] = setor

    return {
        "ticker": ticker.upper(),
        "modelo": "saude_ans",
        "fclf": round(total_proventos_base, 2),
        "anosProjecao": len(taxas),
        "taxasCrescimento": [round(float(t), 2) for t in taxas],
        "wacc": round(float(ke), 2),
        "crescPerp": round(float(cresc_perp), 2),
        "dividaLiquida": 0.0,
        "numAcoes": round(float(num_acoes), 2),
        "margemSeguranca": round(float(margem_seguranca), 2),
        "precoJusto": round(preco_justo, 2),
        "precoTeto": round(preco_teto, 2),
        "detalhes": {
            "modelo_utilizado": "Operadora de Saúde: DDM Regulatório com Restrição de Solvência ANS",
            "receita_liquida_mi": round(rec, 2),
            "sinistralidade_mlr_pct": round(float(sinistralidade_mlr_pct), 2),
            "despesas_adm_comerciais_pct": round(float(despesas_adm_comerciais_pct), 2),
            "resultado_financeiro_float_mi": round(float(resultado_financeiro), 2),
            "lucro_liquido_projetado_mi": round(lucro_liquido_base, 2),
            "retencao_reserva_solvencia_ans_mi": round(retencao_ans, 2),
            "lucro_distribuivel_mi": round(lucro_distribuivel, 2),
            "dpa_ano_base": round(dpa_base, 4),
            "metrica_bazin": metrica_bazin,
            "projecoes_dpa": projecoes,
            "metadata": meta,
        },
    }
