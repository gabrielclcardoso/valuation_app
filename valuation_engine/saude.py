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
    divida_liquida: float = 0.0,
    margem_seguranca: float = 20.0,
    taxas_crescimento_receita: Optional[List[float]] = None,
    pct_jcp: float = 0.0,
    empresa: str = "BradSaúde",
    setor: str = "Saúde Suplementar / Operadora ANS",
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Calcula o Valuation para Operadoras de Planos de Saúde considerando regulação da ANS (RN 569/2022).
    A retenção de capital é estritamente vinculada à variação do capital regulatório exigido
    pela expansão da receita/operações (ΔReceita * k), e suporta dedução de dívida líquida para
    operadoras alavancadas.
    
    Args:
        ticker: Ticker do ativo (ex: SAUD3, HAPV3, ODPV3)
        receita_liquida: Receita Líquida anual (contraprestações dos beneficiários) em R$ Mi
        sinistralidade_mlr_pct: Índice de sinistralidade médica (Eventos / Receita Líquida %)
        despesas_adm_comerciais_pct: Despesas administrativas e comerciais sobre a receita (%)
        resultado_financeiro: Resultado financeiro líquido gerado pelo float das reservas técnicas (R$ Mi)
        aliquota_ir_csll_pct: Alíquota efetiva de tributação (%)
        exigencia_capital_ans_pct: Fator de capital regulatório requerido pela expansão da operação k (RN 569/2022) (%)
        payout_sustentavel_pct: Payout dos lucros distribuíveis após recompor exigência da ANS (%)
        ke: Custo de Capital Próprio via CAPM (% a.a.)
        cresc_perp: Crescimento perpétuo (% a.a.)
        num_acoes: Total de ações em Milhões
        divida_liquida: Dívida líquida financeira da operadora/holding em R$ Mi (0 se operadora desalavancada)
        margem_seguranca: Margem de segurança (%)
        taxas_crescimento_receita: Trajetória de crescimento da base de vidas/receita (%)
        pct_jcp: Percentual dos proventos sob forma de JCP bruto (%)
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

    rec_base = float(receita_liquida)
    mlr_dec = float(sinistralidade_mlr_pct) / 100.0
    desp_dec = float(despesas_adm_comerciais_pct) / 100.0
    margem_op_dec = 1.0 - mlr_dec - desp_dec
    rf_base = float(resultado_financeiro)
    ir_dec = float(aliquota_ir_csll_pct) / 100.0
    k_ans_dec = float(exigencia_capital_ans_pct) / 100.0
    payout_dec = float(payout_sustentavel_pct) / 100.0

    taxas = [float(t) for t in taxas_crescimento_receita] if taxas_crescimento_receita else [float(cresc_perp)] * 5

    # 1. Demonstração de Resultado Normalizada da Operadora (Ano Base)
    g_base_dec = float(taxas[0]) / 100.0 if taxas else g_perp_dec
    delta_rec_base = max(0.0, rec_base * g_base_dec)
    # Retenção regulatória vinculada à variação do capital regulatório exigido (ΔReceita * k - RN 569/2022)
    retencao_ans_base = delta_rec_base * k_ans_dec

    ebit_base = rec_base * margem_op_dec
    lair_base = ebit_base + rf_base
    ir_base = max(0.0, lair_base * ir_dec)
    lucro_liq_base = lair_base - ir_base
    lucro_dist_base = max(0.0, lucro_liq_base - retencao_ans_base)
    proventos_base = lucro_dist_base * payout_dec
    dpa_base = proventos_base / float(num_acoes)

    # 2. DDM Multiestágio com Dinâmica de Solvência ANS ano a ano
    rec_ant = rec_base
    soma_pv = 0.0
    projecoes = []

    for t, taxa in enumerate(taxas, start=1):
        g_dec = float(taxa) / 100.0
        rec_t = rec_ant * (1.0 + g_dec)
        delta_rec_t = max(0.0, rec_t - rec_ant)
        retencao_ans_t = delta_rec_t * k_ans_dec

        ebit_t = rec_t * margem_op_dec
        rf_t = rf_base * (rec_t / rec_base) if rec_base > 0 else rf_base
        lair_t = ebit_t + rf_t
        ir_t = max(0.0, lair_t * ir_dec)
        lucro_t = lair_t - ir_t
        lucro_dist_t = max(0.0, lucro_t - retencao_ans_t)
        proventos_t = lucro_dist_t * payout_dec
        dpa_t = proventos_t / float(num_acoes)
        pv = dpa_t / ((1.0 + ke_dec) ** t)
        soma_pv += pv

        projecoes.append(
            {
                "ano": t,
                "crescimento_pct": round(float(taxa), 2),
                "receita_projetada_mi": round(rec_t, 2),
                "delta_receita_mi": round(delta_rec_t, 2),
                "retencao_solvencia_ans_mi": round(retencao_ans_t, 2),
                "lucro_distribuivel_mi": round(lucro_dist_t, 2),
                "dpa_projetado": round(dpa_t, 4),
                "valor_presente": round(pv, 4),
            }
        )
        rec_ant = rec_t

    # 3. Valor Terminal Perpétuo
    rec_term = rec_ant * (1.0 + g_perp_dec)
    delta_rec_term = max(0.0, rec_ant * g_perp_dec)
    retencao_ans_term = delta_rec_term * k_ans_dec

    ebit_term = rec_term * margem_op_dec
    rf_term = rf_base * (rec_term / rec_base) if rec_base > 0 else rf_base
    lair_term = ebit_term + rf_term
    ir_term = max(0.0, lair_term * ir_dec)
    lucro_term = lair_term - ir_term
    lucro_dist_term = max(0.0, lucro_term - retencao_ans_term)
    proventos_term = lucro_dist_term * payout_dec
    dpa_terminal = proventos_term / float(num_acoes)

    valor_terminal_dpa = dpa_terminal / (ke_dec - g_perp_dec)
    vp_terminal = valor_terminal_dpa / ((1.0 + ke_dec) ** len(taxas))

    # 4. Preço Justo e Preço Teto
    # CORREÇÃO: No DDM, o VP dos dividendos JÁ É o Equity Value.
    # Subtrair Dívida Líquida configuraria dupla penalização.
    div_liq = float(divida_liquida)
    equity_per_share = soma_pv + vp_terminal
    preco_justo = max(0.0, equity_per_share)
    preco_teto = preco_justo * (1.0 - (float(margem_seguranca) / 100.0))

    # Métrica Bazin
    metrica_bazin = calculate_bazin(
        dpa=dpa_base,
        preco_teto_modelo=preco_teto,
        pct_jcp=pct_jcp,
    )

    meta = metadata.copy() if metadata else {}
    if empresa:
        meta["empresa"] = empresa
    if setor:
        meta["setor"] = setor

    return {
        "ticker": ticker.upper(),
        "modelo": "saude_ans",
        "fclf": round(proventos_base, 2),
        "anosProjecao": len(taxas),
        "taxasCrescimento": [round(float(t), 2) for t in taxas],
        "wacc": round(float(ke), 2),
        "crescPerp": round(float(cresc_perp), 2),
        "dividaLiquida": round(div_liq, 2),
        "numAcoes": round(float(num_acoes), 2),
        "margemSeguranca": round(float(margem_seguranca), 2),
        "precoJusto": round(preco_justo, 2),
        "precoTeto": round(preco_teto, 2),
        "detalhes": {
            "modelo_utilizado": "Operadora de Saúde: DDM Regulatório com Restrição de Solvência ANS (RN 569/2022)",
            "receita_liquida_mi": round(rec_base, 2),
            "sinistralidade_mlr_pct": round(float(sinistralidade_mlr_pct), 2),
            "despesas_adm_comerciais_pct": round(float(despesas_adm_comerciais_pct), 2),
            "fator_capital_ans_k_pct": round(float(exigencia_capital_ans_pct), 2),
            "resultado_financeiro_float_mi": round(rf_base, 2),
            "lucro_liquido_projetado_mi": round(lucro_liq_base, 2),
            "retencao_reserva_solvencia_ans_mi": round(retencao_ans_base, 2),
            "lucro_distribuivel_mi": round(lucro_dist_base, 2),
            "payout_sustentavel_pct": round(float(payout_sustentavel_pct), 2),
            "divida_liquida_deduzida_mi": 0.0, # Zerado, Dívida não deve mais ser deduzida no DDM
            "dpa_ano_base": round(dpa_base, 4),
            "metrica_bazin": metrica_bazin,
            "projecoes_dpa": projecoes,
            "metadata": meta,
        },
    }
