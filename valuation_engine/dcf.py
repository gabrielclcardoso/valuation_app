"""Motor de Valuation por Fluxo de Caixa Descontado da Firma (FCFF / FCLF).
Ideal para: Concessões, Saneamento, Energia (Geração/Transmissão/Distribuição), Telecomunicações,
Logística, Indústria de Bens de Capital e Hospitais/Laboratórios.
"""
from typing import List, Dict, Any, Optional
from valuation_engine.bazin import calculate_bazin


def calculate_wacc(
    rf_real: float,
    ipca: float,
    beta: float,
    erp: float,
    kd_bruto: float,
    aliquota_ir: float,
    equity_ratio: float,
    spread_governanca: float = 0.0,
) -> Dict[str, Any]:
    """Calcula o WACC nominal em BRL.
    rf_nominal = (1 + rf_real) * (1 + ipca) - 1
    ke = rf_nominal + beta * erp + spread_governanca
    kd_liquido = kd_bruto * (1 - aliquota_ir)
    wacc = ke * equity_ratio + kd_liquido * (1 - equity_ratio)
    """
    rf_nom = ((1.0 + rf_real / 100.0) * (1.0 + ipca / 100.0) - 1.0) * 100.0
    ke = rf_nom + (beta * erp) + spread_governanca
    kd_liq = kd_bruto * (1.0 - aliquota_ir / 100.0)
    debt_ratio = 1.0 - equity_ratio
    wacc = (ke * equity_ratio) + (kd_liq * debt_ratio)
    return {
        "rf_real": rf_real,
        "ipca_esperado": ipca,
        "rf_nominal": round(rf_nom, 2),
        "beta": round(beta, 2),
        "erp": round(erp, 2),
        "spread_governanca": round(spread_governanca, 2),
        "ke": round(ke, 2),
        "kd_bruto": round(kd_bruto, 2),
        "aliquota_ir": round(aliquota_ir, 2),
        "kd_liquido": round(kd_liq, 2),
        "equity_ratio": round(equity_ratio, 2),
        "debt_ratio": round(debt_ratio, 2),
        "wacc": round(wacc, 2),
    }


def calculate_dcf(
    ticker: str,
    fclf_inicial: float,
    taxas_crescimento: List[float],
    wacc: float,
    cresc_perp: float,
    divida_liquida: float,
    num_acoes: float,
    outros_passivos: float = 0.0,
    margem_seguranca: float = 20.0,
    dpa_projetado: float = 0.0,
    empresa: str = "",
    setor: str = "",
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Calcula o Valuation DCF por FCFF com cenários (Base e Ajustado por Quase-Dívidas).
    
    Args:
        ticker: Ticker do ativo (ex: SAPR4, CPFE3, TIMS3)
        fclf_inicial: Fluxo de Caixa Livre da Firma no ano base (R$ Milhões)
        taxas_crescimento: Lista com taxas de crescimento dos anos projetados (%)
        wacc: Taxa de desconto WACC nominal (% a.a.)
        cresc_perp: Taxa de crescimento na perpetuidade (% a.a.)
        divida_liquida: Dívida Financeira Líquida do último ITR/DFP (R$ Milhões)
        num_acoes: Total de ações ou Units equivalentes (Milhões)
        outros_passivos: Quase-dívidas (passivos regulatórios, déficits atuariais, contingências)
        margem_seguranca: Margem de segurança aplicada ao Preço Justo (%)
        dpa_projetado: DPA sustentável esperado para métrica Bazin (R$)
        empresa: Nome corporativo da empresa
        setor: Setor de atuação
        metadata: Dicionário adicional com memórias de cálculo e justificativas
    """
    wacc_dec = float(wacc) / 100.0
    g_perp_dec = float(cresc_perp) / 100.0

    if wacc_dec <= g_perp_dec:
        raise ValueError(
            f"WACC ({wacc}%) deve ser estritamente maior que o Crescimento Perpétuo ({cresc_perp}%)."
        )
    if num_acoes <= 0:
        raise ValueError("O número de ações deve ser maior que zero.")

    # 1. Projeção dos fluxos explícitos
    fcf_atual = float(fclf_inicial)
    soma_pv = 0.0
    projecoes = []

    for t, taxa in enumerate(taxas_crescimento, start=1):
        g_dec = float(taxa) / 100.0
        fcf_atual = fcf_atual * (1.0 + g_dec)
        pv = fcf_atual / ((1.0 + wacc_dec) ** t)
        soma_pv += pv
        projecoes.append(
            {
                "ano": t,
                "crescimento_pct": round(float(taxa), 2),
                "fclf_projetado": round(fcf_atual, 2),
                "valor_presente": round(pv, 2),
            }
        )

    # 2. Valor Terminal (Gordon na Perpetuidade)
    fcf_terminal = fcf_atual * (1.0 + g_perp_dec)
    valor_terminal = fcf_terminal / (wacc_dec - g_perp_dec)
    vp_terminal = valor_terminal / ((1.0 + wacc_dec) ** len(taxas_crescimento))

    # 3. Enterprise Value
    enterprise_value = soma_pv + vp_terminal

    # 4. Estrutura de Dívida e Quase-Dívidas
    divida_fin_liq = float(divida_liquida)
    outros_pass = float(outros_passivos)
    divida_total_ajustada = divida_fin_liq + outros_pass

    # Cenário Base: Apenas dívida financeira líquida
    equity_value_base = enterprise_value - divida_fin_liq
    preco_justo_base = max(0.0, equity_value_base / float(num_acoes))
    preco_teto_base = preco_justo_base * (1.0 - (float(margem_seguranca) / 100.0))

    # Cenário Ajustado: Deduzindo passivos regulatórios, contingências e déficits atuariais
    equity_value_ajustado = enterprise_value - divida_total_ajustada
    preco_justo_ajustado = max(0.0, equity_value_ajustado / float(num_acoes))
    preco_teto_ajustado = preco_justo_ajustado * (1.0 - (float(margem_seguranca) / 100.0))

    # Se outros passivos foram informados, o preço conservador oficial adotado é o ajustado
    if outros_pass > 0:
        preco_justo_final = preco_justo_ajustado
        preco_teto_final = preco_teto_ajustado
        equity_value_final = equity_value_ajustado
        divida_final = divida_total_ajustada
    else:
        preco_justo_final = preco_justo_base
        preco_teto_final = preco_teto_base
        equity_value_final = equity_value_base
        divida_final = divida_fin_liq

    # Métrica Bazin centralizada
    metrica_bazin = calculate_bazin(dpa=dpa_projetado, preco_teto_modelo=preco_teto_final)

    meta = metadata.copy() if metadata else {}
    if empresa:
        meta["empresa"] = empresa
    if setor:
        meta["setor"] = setor

    return {
        "ticker": ticker.upper(),
        "modelo": "dcf_fcff",
        "fclf": round(float(fclf_inicial), 2),
        "anosProjecao": len(taxas_crescimento),
        "taxasCrescimento": [round(float(t), 2) for t in taxas_crescimento],
        "wacc": round(float(wacc), 2),
        "crescPerp": round(float(cresc_perp), 2),
        "dividaLiquida": round(divida_final, 2),
        "numAcoes": round(float(num_acoes), 2),
        "margemSeguranca": round(float(margem_seguranca), 2),
        "precoJusto": round(preco_justo_final, 2),
        "precoTeto": round(preco_teto_final, 2),
        "detalhes": {
            "modelo_utilizado": "DCF por FCFF (Enterprise Value)",
            "soma_pv_fluxos": round(soma_pv, 2),
            "fcf_ano_terminal": round(fcf_terminal, 2),
            "valor_terminal_bruto": round(valor_terminal, 2),
            "vp_terminal": round(vp_terminal, 2),
            "enterprise_value": round(enterprise_value, 2),
            "equity_value": round(equity_value_final, 2),
            "divida_financeira_liquida": round(divida_fin_liq, 2),
            "outros_passivos_deduzidos": round(outros_pass, 2),
            "divida_total_ajustada": round(divida_total_ajustada, 2),
            "cenarios": {
                "cenario_base": {
                    "descricao": "DCF Econômico sem dedução de passivos contingentes/regulatórios",
                    "equity_value": round(equity_value_base, 2),
                    "preco_justo": round(preco_justo_base, 2),
                    "preco_teto": round(preco_teto_base, 2),
                },
                "cenario_ajustado": {
                    "descricao": "DCF Ajustado deduzindo passivos regulatórios, contingências e quase-dívidas",
                    "equity_value": round(equity_value_ajustado, 2),
                    "preco_justo": round(preco_justo_ajustado, 2),
                    "preco_teto": round(preco_teto_ajustado, 2),
                },
            },
            "metrica_bazin": metrica_bazin,
            "projecoes": projecoes,
            "metadata": meta,
        },
    }
