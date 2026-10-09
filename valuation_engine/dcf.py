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


def calculate_cagr(valor_inicial: float, valor_final: float, periodos: int) -> float:
    """Calcula a taxa de crescimento anual composta (CAGR) em porcentagem.
    Retorna 0.0 se valores forem inválidos ou períodos <= 0.
    """
    if valor_inicial <= 0 or valor_final <= 0 or periodos <= 0:
        return 0.0
    return round(((valor_final / valor_inicial) ** (1.0 / periodos) - 1.0) * 100.0, 2)


def validate_growth_and_market_share(
    fclf_inicial: float,
    taxas_crescimento: List[float],
    cresc_perp: float,
    historico_fcf: Optional[List[float]] = None,
    cagr_historico: Optional[float] = None,
    market_share_dinamica: Optional[str] = None,
    decomposicao_g1: Optional[List[float]] = None,
    analise_competitiva: str = "",
) -> Dict[str, Any]:
    """Analisa a consistência do crescimento projetado frente ao histórico e dinâmica concorrencial.
    
    Args:
        fclf_inicial: Fluxo de caixa do ano base adotado (R$ Milhões).
        taxas_crescimento: Taxas de crescimento projetadas dos fluxos explícitos (%).
        cresc_perp: Taxa de crescimento perpétuo (%).
        historico_fcf: Lista de fluxos realizados dos últimos anos (ex: [3700, 4600, 5300]).
        cagr_historico: CAGR histórico de referência informado (%).
        market_share_dinamica: 'estavel', 'ganho', 'perda' ou 'monopolio_regulado'.
        decomposicao_g1: Lista [ipca, volume_setor, pricing_or_share] para decompor a taxa g1.
        analise_competitiva: Racional qualitativo de vantagem competitiva / market share.
    """
    cagr_apurado = None
    media_historica = None
    desvio_base_pct = None

    if historico_fcf and len(historico_fcf) >= 2:
        periodos = len(historico_fcf) - 1
        cagr_apurado = calculate_cagr(historico_fcf[0], historico_fcf[-1], periodos)
        media_historica = sum(historico_fcf) / len(historico_fcf)
        if media_historica > 0:
            desvio_base_pct = round(((fclf_inicial - media_historica) / media_historica) * 100.0, 2)
    elif cagr_historico is not None:
        cagr_apurado = round(float(cagr_historico), 2)

    # Verificação de convergência em direção à perpetuidade (decaimento monotônico e proximidade a g_perp)
    is_descending_or_stable = all(
        taxas_crescimento[i] >= taxas_crescimento[i + 1] for i in range(len(taxas_crescimento) - 1)
    )
    converge_proximo_perp = abs(taxas_crescimento[-1] - cresc_perp) <= 1.5
    convergencia_perpetuidade = is_descending_or_stable and converge_proximo_perp

    # Avaliação de coerência frente ao histórico
    status_coerencia = "nao_informado"
    mensagem_coerencia = None
    if cagr_apurado is not None and taxas_crescimento:
        g1 = taxas_crescimento[0]
        if g1 > cagr_apurado + 3.0:
            status_coerencia = "alerta_aceleracao"
            mensagem_coerencia = (
                f"Taxa g1 ({g1:.1f}%) projeta aceleração frente ao CAGR histórico ({cagr_apurado:.1f}%). "
                f"Exige gatilho de investimento (CapEx) ou ganho comprovado de market share."
            )
        else:
            status_coerencia = "coerente"
            mensagem_coerencia = (
                f"Taxa g1 ({g1:.1f}%) compatível com a capacidade histórica demonstrada ({cagr_apurado:.1f}% a.a.)."
            )

    alerta_base = None
    if desvio_base_pct is not None and abs(desvio_base_pct) > 25.0:
        alerta_base = (
            f"O FCFF inicial (R$ {fclf_inicial:,.2f} Mi) desvia {desvio_base_pct:+.1f}% da média histórica "
            f"(R$ {media_historica:,.2f} Mi). Verifique se o ano-base inclui efeitos não recorrentes ou NCG atípico."
        )

    decomposicao = None
    if decomposicao_g1 and len(decomposicao_g1) == 3 and taxas_crescimento:
        ipca, volume, share_pricing = [round(float(v), 2) for v in decomposicao_g1]
        soma = round(ipca + volume + share_pricing, 2)
        decomposicao = {
            "ipca": ipca,
            "volume_setor": volume,
            "market_share_pricing": share_pricing,
            "soma": soma,
            "g1_adotado": round(taxas_crescimento[0], 2),
            "diferenca": round(soma - taxas_crescimento[0], 2),
        }

    return {
        "cagr_historico_pct": cagr_apurado,
        "historico_fcf": [round(float(v), 2) for v in historico_fcf] if historico_fcf else None,
        "media_historica_fcf": round(media_historica, 2) if media_historica is not None else None,
        "desvio_ano_base_pct": desvio_base_pct,
        "market_share_dinamica": market_share_dinamica,
        "analise_competitiva": analise_competitiva,
        "decomposicao_g1": decomposicao,
        "convergencia_perpetuidade": convergencia_perpetuidade,
        "status_coerencia": status_coerencia,
        "mensagem_coerencia": mensagem_coerencia,
        "alerta_base": alerta_base,
    }


def calculate_dcf(
    ticker: str,
    *,
    fclf_inicial: Optional[float] = None,
    taxas_crescimento: List[float],
    wacc: float,
    cresc_perp: float,
    divida_liquida: float,
    num_acoes: float,
    outros_passivos: float = 0.0,
    passivos_contingentes: float = 0.0,
    passivos_regulatorios: Optional[float] = None,
    aliquota_ir_csll: float = 34.0,
    quase_divida_dedutivel: bool = False,
    margem_seguranca: float = 20.0,
    dpa_projetado: float = 0.0,
    pct_jcp: float = 0.0,
    historico_fcf: Optional[List[float]] = None,
    cagr_historico: Optional[float] = None,
    market_share_dinamica: Optional[str] = None,
    decomposicao_g1: Optional[List[float]] = None,
    analise_competitiva: str = "",
    empresa: str = "",
    setor: str = "",
    metadata: Optional[Dict[str, Any]] = None,
    capex_minimo_historico: Optional[float] = None,
    ifrs16_expurgado: bool = False,
    teto_crescimento_oligopolio: Optional[float] = None,
    ebitda_al: Optional[float] = None,
    capex_projetado: Optional[float] = None,
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
        outros_passivos: Quase-dívidas consolidadas em R$ Milhões
        passivos_contingentes: Passivos contingentes e atuariais dedutíveis para IRPJ/CSLL (R$ Mi)
        passivos_regulatorios: Passivos regulatórios (R$ Mi). Se negativo, tratado como ativo regulatório.
        aliquota_ir_csll: Alíquota de IRPJ/CSLL para cálculo do benefício fiscal (padrão 34.0%)
        quase_divida_dedutivel: Se True, aplica benefício fiscal de 34% a 'outros_passivos'
        margem_seguranca: Margem de segurança aplicada ao Preço Justo (%)
        dpa_projetado: DPA sustentável esperado para métrica Bazin (R$)
        pct_jcp: Percentual dos proventos pagos sob a forma de JCP bruto (%)
        historico_fcf: Lista de FCF dos últimos exercícios fechados (R$ Mi)
        cagr_historico: CAGR histórico de referência para teste de coerência (%)
        market_share_dinamica: 'estavel', 'ganho', 'perda' ou 'monopolio_regulado'
        decomposicao_g1: [ipca, volume_setor, pricing_or_share] para justificar g1
        analise_competitiva: Racional de market share ou moats da empresa
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

    if fclf_inicial is None:
        if ebitda_al is None or capex_projetado is None:
            raise ValueError("É necessário informar fclf_inicial ou (ebitda_al e capex_projetado).")
        fclf_inicial = float(ebitda_al) - float(capex_projetado)

    # Validação contra projeção infinita de fluxos negativos
    if fclf_inicial < 0:
        raise ValueError(f"O FCFF do ano-base não pode ser negativo (R$ {fclf_inicial} Mi) para projeção da taxa de crescimento 'g'. A normalização prévia do fluxo inicial é obrigatória.")

    # Telecom Safety Parameters: Teto de Crescimento
    if teto_crescimento_oligopolio is not None and market_share_dinamica == 'estavel':
        if taxas_crescimento and taxas_crescimento[0] > teto_crescimento_oligopolio:
            raise ValueError(
                f"Taxa de crescimento inicial (g1={taxas_crescimento[0]}%) supera o teto de oligopólio ({teto_crescimento_oligopolio}%). "
                "Crescimento em Telecom (oligopólio maduro) exige ganho agressivo e documentado de ARPU. "
                "Reduza a taxa G1 ou altere o teto."
            )

    # Telecom Safety Parameters: Tratamento de Arrendamentos IFRS 16
    is_telecom = setor.lower() in ['telecom', 'telecomunicações', 'telecomunicacoes'] or ticker.upper().startswith(('VIVT', 'TIMS', 'OIBR'))
    if is_telecom and not ifrs16_expurgado:
        raise ValueError(
            "Para empresas de Telecomunicações, é obrigatório confirmar o expurgo do IFRS 16 da Dívida Financeira "
            "passando a flag --ifrs16-expurgado. Isso evita dupla penalização (considerando passivo de arrendamento "
            "como dívida ao mesmo tempo em que já reduz o FCF via EBITDA-AL)."
        )

    # Telecom Safety Parameters: Risco de CapEx
    deficit_capex = 0.0
    provisao_queima_caixa = 0.0
    if capex_minimo_historico is not None:
        if capex_projetado is None:
            raise ValueError("Para usar capex_minimo_historico, é necessário informar capex_projetado (e ebitda_al).")
        deficit_capex = max(0.0, float(capex_minimo_historico) - float(capex_projetado))
        provisao_queima_caixa = deficit_capex * 5.0

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
    enterprise_value_bruto = soma_pv + vp_terminal
    enterprise_value = enterprise_value_bruto - provisao_queima_caixa

    # 4. Estrutura de Dívida e Quase-Dívidas com Benefício Fiscal
    divida_fin_liq = float(divida_liquida)
    tax_rate = float(aliquota_ir_csll) / 100.0

    # Segregação e tratamento tributário:
    # Passivos regulatórios: restituições tarifárias (não geram benefício fiscal direto de IR)
    if passivos_regulatorios is not None:
        regulatorio = float(passivos_regulatorios)
    else:
        regulatorio = float(outros_passivos) if not quase_divida_dedutivel else 0.0

    # Passivos contingentes e atuariais (previdência/processos cíveis/trabalhistas/tributários dedutíveis)
    if passivos_contingentes > 0:
        contingentes_bruto = float(passivos_contingentes)
    elif quase_divida_dedutivel and outros_passivos != 0.0:
        contingentes_bruto = float(outros_passivos)
    else:
        contingentes_bruto = 0.0

    # Quase-dívidas contingentes deduzidas líquidas de impostos (34% IRPJ/CSLL)
    contingentes_liquidos = contingentes_bruto * (1.0 - tax_rate)
    beneficio_fiscal_quase_divida = contingentes_bruto - contingentes_liquidos

    # Passivo regulatório negativo é tratado como ATIVO regulatório (adiciona ao valor ou reduz dívida)
    divida_total_ajustada = divida_fin_liq + contingentes_liquidos + regulatorio
    quase_dividas_total_liquidas = contingentes_liquidos + regulatorio

    # Cenário Base: Apenas dívida financeira líquida
    equity_value_base = enterprise_value - divida_fin_liq
    preco_justo_base = max(0.0, equity_value_base / float(num_acoes))
    preco_teto_base = preco_justo_base * (1.0 - (float(margem_seguranca) / 100.0))

    # Cenário Ajustado: Deduzindo passivos regulatórios, contingências e déficits atuariais líquidos
    equity_value_ajustado = enterprise_value - divida_total_ajustada
    preco_justo_ajustado = max(0.0, equity_value_ajustado / float(num_acoes))
    preco_teto_ajustado = preco_justo_ajustado * (1.0 - (float(margem_seguranca) / 100.0))

    # Se quase-dívidas/passivos regulatórios foram informados, o preço oficial adotado é o ajustado
    if contingentes_bruto > 0 or regulatorio != 0.0 or outros_passivos != 0.0:
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
    metrica_bazin = calculate_bazin(
        dpa=dpa_projetado,
        preco_teto_modelo=preco_teto_final,
        pct_jcp=pct_jcp,
    )

    # Validação do triângulo de crescimento (Histórico, Mercado e Reinvestimento)
    validacao_crescimento = validate_growth_and_market_share(
        fclf_inicial=fclf_inicial,
        taxas_crescimento=taxas_crescimento,
        cresc_perp=cresc_perp,
        historico_fcf=historico_fcf,
        cagr_historico=cagr_historico,
        market_share_dinamica=market_share_dinamica,
        decomposicao_g1=decomposicao_g1,
        analise_competitiva=analise_competitiva,
    )

    meta = metadata.copy() if metadata else {}
    if empresa:
        meta["empresa"] = empresa
    if setor:
        meta["setor"] = setor
    if ifrs16_expurgado:
        meta["ifrs16_expurgado"] = True
    if capex_minimo_historico is not None:
        meta["capex_minimo_historico_penalidade_aplicada"] = True
    if teto_crescimento_oligopolio is not None:
        meta["teto_crescimento_oligopolio_aplicado"] = teto_crescimento_oligopolio

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
            "deficit_capex": round(deficit_capex, 2),
            "provisao_queima_caixa": round(provisao_queima_caixa, 2),
            "enterprise_value_bruto": round(enterprise_value_bruto, 2),
            "enterprise_value": round(enterprise_value, 2),
            "equity_value": round(equity_value_final, 2),
            "divida_financeira_liquida": round(divida_fin_liq, 2),
            "passivos_contingentes_bruto": round(contingentes_bruto, 2),
            "passivos_contingentes_liquidos": round(contingentes_liquidos, 2),
            "beneficio_fiscal_quase_divida_mi": round(beneficio_fiscal_quase_divida, 2),
            "passivos_regulatorios": round(regulatorio, 2),
            "ativo_regulatorio_mi": round(abs(regulatorio), 2) if regulatorio < 0 else 0.0,
            "outros_passivos_deduzidos": round(quase_dividas_total_liquidas, 2),
            "divida_total_ajustada": round(divida_total_ajustada, 2),
            "cenarios": {
                "cenario_base": {
                    "descricao": "DCF Econômico sem dedução de passivos contingentes/regulatórios",
                    "equity_value": round(equity_value_base, 2),
                    "preco_justo": round(preco_justo_base, 2),
                    "preco_teto": round(preco_teto_base, 2),
                },
                "cenario_ajustado": {
                    "descricao": "DCF Ajustado deduzindo passivos regulatórios e quase-dívidas líquidas de impostos",
                    "equity_value": round(equity_value_ajustado, 2),
                    "preco_justo": round(preco_justo_ajustado, 2),
                    "preco_teto": round(preco_teto_ajustado, 2),
                },
            },
            "metrica_bazin": metrica_bazin,
            "projecoes": projecoes,
            "validacao_crescimento": validacao_crescimento,
            "metadata": meta,
        },
    }
