"""Motor de Valuation por Fluxo de Caixa Descontado da Firma (FCFF / FCLF).
Ideal para: Concessões, Saneamento, Energia (Geração/Transmissão/Distribuição), Telecomunicações,
Logística, Indústria de Bens de Capital e Hospitais/Laboratórios.
"""
from typing import List, Dict, Any, Optional
from valuation_engine.bazin import calculate_bazin


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
    validar_soma_g1: bool = True,
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
        validar_soma_g1: Se True (padrão), exige que soma(decomposicao_g1) == taxas_crescimento[0].
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
    if taxas_crescimento:
        is_descending_or_stable = all(
            taxas_crescimento[i] >= taxas_crescimento[i + 1] for i in range(len(taxas_crescimento) - 1)
        )
        converge_proximo_perp = abs(taxas_crescimento[-1] - cresc_perp) <= 1.5
        convergencia_perpetuidade = is_descending_or_stable and converge_proximo_perp
    else:
        convergencia_perpetuidade = False

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
    if decomposicao_g1 and len(decomposicao_g1) == 3:
        ipca, volume, share_pricing = [round(float(v), 2) for v in decomposicao_g1]
        soma = round(ipca + volume + share_pricing, 2)
        g1_adotado = round(float(taxas_crescimento[0]), 2) if (taxas_crescimento and validar_soma_g1) else soma
        diferenca = round(soma - g1_adotado, 2)
        if validar_soma_g1 and abs(diferenca) > 0.05:
            raise ValueError(
                f"Inconsistência na decomposição de g1: a soma dos vetores ({soma:.2f}%) "
                f"difere da taxa g1 informada ({g1_adotado:.2f}%) em {diferenca:+.2f} p.p. "
                "(tolerância máxima: 0.05 p.p.)."
            )
        decomposicao = {
            "ipca": ipca,
            "volume_setor": volume,
            "market_share_pricing": share_pricing,
            "soma": soma,
            "g1_adotado": g1_adotado,
            "diferenca": diferenca,
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
    taxas_crescimento: Optional[List[float]] = None,
    wacc: float,
    cresc_perp: float,
    divida_liquida: float,
    num_acoes: float,
    outros_passivos: float = 0.0,
    passivos_contingentes: float = 0.0,
    passivos_regulatorios: Optional[float] = None,
    aliquota_ir_csll: float = 34.0,
    pct_contingencia_dedutivel: Optional[float] = None,
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
    fco: Optional[float] = None,
    juros_pagos: Optional[float] = None,
    capex_projetado: Optional[float] = None,
    ntnb: float = 6.0,
    alavancagem_otima_pct: Optional[float] = None,
    prazo_concessao_anos: Optional[int] = None,
    rab_indenizavel_mi: float = 0.0,
    fluxos_explicitos: Optional[List[float]] = None,
    juros_pagos_no_fco: bool = True,
    normalizar_capex_fluxo: bool = True,
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
        outros_passivos: Quase-dívidas consolidadas não-dedutíveis em R$ Milhões
        passivos_contingentes: Passivos contingentes e atuariais dedutíveis para IRPJ/CSLL (R$ Mi)
        passivos_regulatorios: Passivos regulatórios (R$ Mi). Se negativo, tratado como ativo regulatório.
        aliquota_ir_csll: Alíquota de IRPJ/CSLL para cálculo do benefício fiscal (padrão 34.0%)
        pct_contingencia_dedutivel: Percentual de dedutibilidade fiscal sobre contingências (default 100% se passivos_contingentes > 0)
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
        alavancagem_otima_pct: Alavancagem ótima D/(D+E) em % para piso de WACC com escudo fiscal
        prazo_concessao_anos: Prazo total remanescente da concessão em anos (ativa VT por anuidade finita)
        rab_indenizavel_mi: Base de Ativos Regulatórios (RAB) indenizável ao final da concessão (R$ Mi)
        fluxos_explicitos: Lista explícita de FCFF projetados [FCFF_1, ..., FCFF_T] para projetos em Curva J
        juros_pagos_no_fco: Se True (padrão), soma juros_pagos * (1 - T) de volta ao FCO
        normalizar_capex_fluxo: Se True (padrão), deduz deficit_capex diretamente no FCFF inicial
    """
    if taxas_crescimento is None:
        taxas_crescimento = []

    if decomposicao_g1 and len(decomposicao_g1) == 3:
        ipca_informado_pct = float(decomposicao_g1[0])
        ipca_ref = ipca_informado_pct / 100.0
        teto_g_perp = max(4.5, ipca_informado_pct + 1.0)
    else:
        ipca_ref = 0.035
        teto_g_perp = 4.5

    tax_rate = float(aliquota_ir_csll) / 100.0
    rf_nominal_pct = ((1.0 + float(ntnb) / 100.0) * (1.0 + ipca_ref) - 1.0) * 100.0

    if alavancagem_otima_pct is not None and 0.0 < float(alavancagem_otima_pct) < 100.0:
        alpha = float(alavancagem_otima_pct) / 100.0
        wacc_floor = (1.0 - alpha) * (rf_nominal_pct + 2.5) + alpha * (rf_nominal_pct + 1.0) * (1.0 - tax_rate)
    else:
        wacc_floor = rf_nominal_pct + 1.5

    wacc = max(float(wacc), wacc_floor)
    cresc_perp = min(float(cresc_perp), teto_g_perp)

    wacc_dec = float(wacc) / 100.0
    g_perp_dec = float(cresc_perp) / 100.0

    if wacc_dec <= g_perp_dec:
        raise ValueError(
            f"WACC ({wacc}%) deve ser estritamente maior que o Crescimento Perpétuo ({cresc_perp}%)."
        )
    if num_acoes <= 0:
        raise ValueError("O número de ações deve ser maior que zero.")

    if prazo_concessao_anos is not None and int(prazo_concessao_anos) <= 0:
        raise ValueError("O prazo da concessão (prazo_concessao_anos) deve ser maior que zero.")

    # Telecom Safety Parameters: Risco de CapEx
    deficit_capex = 0.0
    provisao_queima_caixa = 0.0
    if capex_minimo_historico is not None:
        if capex_projetado is None:
            raise ValueError("Para usar capex_minimo_historico, é necessário informar capex_projetado.")
        deficit_capex = max(0.0, float(capex_minimo_historico) - abs(float(capex_projetado)))
        if not normalizar_capex_fluxo:
            provisao_queima_caixa = deficit_capex * 5.0

    if fluxos_explicitos is not None and len(fluxos_explicitos) > 0:
        fluxos_efetivos = [
            float(f) - (deficit_capex if normalizar_capex_fluxo else 0.0)
            for f in fluxos_explicitos
        ]
        if prazo_concessao_anos is not None and int(prazo_concessao_anos) < len(fluxos_efetivos):
            fluxos_efetivos = fluxos_efetivos[: int(prazo_concessao_anos)]
        if float(fluxos_efetivos[-1]) <= 0:
            raise ValueError(
                f"O último fluxo explícito da Curva J (FCFF_T = R$ {fluxos_efetivos[-1]} Mi) "
                "deve ser estritamente positivo para ancorar o Valor Terminal."
            )
        if fclf_inicial is None:
            fclf_inicial = float(fluxos_efetivos[0])
    else:
        fluxos_efetivos = None
        if fclf_inicial is None:
            if fco is not None and capex_projetado is not None and (juros_pagos is not None or not juros_pagos_no_fco):
                parcela_juros = (
                    abs(float(juros_pagos)) * (1.0 - tax_rate)
                    if (juros_pagos_no_fco and juros_pagos is not None)
                    else 0.0
                )
                fclf_inicial = float(fco) + parcela_juros - abs(float(capex_projetado))
            else:
                raise ValueError("É necessário informar fclf_inicial OU (fco, juros_pagos e capex_projetado).")

        if normalizar_capex_fluxo and deficit_capex > 0.0:
            fclf_inicial = float(fclf_inicial) - deficit_capex

        # Validação contra projeção de fluxos nulos ou negativos no modo taxa de crescimento
        if fclf_inicial <= 0:
            raise ValueError(
                f"O FCFF do ano-base deve ser estritamente positivo (R$ {fclf_inicial} Mi) para projeção "
                "por taxa de crescimento 'g'. Para projetos em Curva J com anos iniciais negativos, "
                "utilize fluxos_explicitos."
            )
        if not taxas_crescimento:
            raise ValueError("É necessário informar taxas_crescimento ou fluxos_explicitos.")
        if prazo_concessao_anos is not None and int(prazo_concessao_anos) < len(taxas_crescimento):
            taxas_crescimento = list(taxas_crescimento[: int(prazo_concessao_anos)])

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

    # 1. Projeção dos fluxos explícitos (por taxas de crescimento ou vetor explícito em Curva J)
    soma_pv = 0.0
    projecoes = []

    if fluxos_efetivos is not None:
        fcf_atual = float(fluxos_efetivos[-1])
        for t, fcf_val in enumerate(fluxos_efetivos, start=1):
            fcf_t = float(fcf_val)
            if t == 1:
                g_pct = 0.0
            else:
                prev_fcf = float(fluxos_efetivos[t - 2])
                g_pct = round(((fcf_t / prev_fcf) - 1.0) * 100.0, 2) if prev_fcf > 0 else 0.0
            pv = fcf_t / ((1.0 + wacc_dec) ** t)
            soma_pv += pv
            projecoes.append(
                {
                    "ano": t,
                    "crescimento_pct": g_pct,
                    "fclf_projetado": round(fcf_t, 2),
                    "valor_presente": round(pv, 2),
                }
            )
        periodo_explicito = len(fluxos_efetivos)
    else:
        fcf_atual = float(fclf_inicial)
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
        periodo_explicito = len(taxas_crescimento)

    # 2. Valor Terminal (Perpetuidade de Gordon ou Anuidade Crescente Finita + Indenização de RAB)
    fcf_terminal = fcf_atual * (1.0 + g_perp_dec)
    fator_anuidade = None
    vp_rab_em_t = 0.0

    if prazo_concessao_anos is not None:
        anos_remanescentes = max(0, int(prazo_concessao_anos) - periodo_explicito)
        if anos_remanescentes > 0:
            fator_anuidade = 1.0 - (((1.0 + g_perp_dec) / (1.0 + wacc_dec)) ** anos_remanescentes)
            vt_anuidade = (fcf_terminal / (wacc_dec - g_perp_dec)) * fator_anuidade
        else:
            fator_anuidade = 0.0
            vt_anuidade = 0.0
        vp_rab_em_t = float(rab_indenizavel_mi) / ((1.0 + wacc_dec) ** anos_remanescentes) if rab_indenizavel_mi > 0 else 0.0
        valor_terminal = vt_anuidade + vp_rab_em_t
    else:
        valor_terminal = fcf_terminal / (wacc_dec - g_perp_dec)

    vp_terminal = valor_terminal / ((1.0 + wacc_dec) ** periodo_explicito)

    # 3. Enterprise Value
    enterprise_value_bruto = soma_pv + vp_terminal
    enterprise_value = enterprise_value_bruto - provisao_queima_caixa

    # 4. Estrutura de Dívida e Quase-Dívidas com Benefício Fiscal (Segregação Ortogonal)
    divida_fin_liq = float(divida_liquida)

    if pct_contingencia_dedutivel is None:
        pct_ded_val = 100.0 if float(passivos_contingentes) > 0 else 0.0
    else:
        pct_ded_val = float(pct_contingencia_dedutivel)

    # Passivos regulatórios: restituições tarifárias (não geram benefício fiscal direto de IR)
    regulatorio = float(passivos_regulatorios) if passivos_regulatorios is not None else 0.0

    # Passivos contingentes e atuariais (previdência/processos cíveis/trabalhistas/tributários dedutíveis)
    if float(passivos_contingentes) > 0:
        contingentes_bruto = float(passivos_contingentes)
        outros_nao_dedutiveis = float(outros_passivos)
    elif pct_ded_val > 0.0 and float(outros_passivos) != 0.0:
        contingentes_bruto = float(outros_passivos)
        outros_nao_dedutiveis = 0.0
    else:
        contingentes_bruto = 0.0
        outros_nao_dedutiveis = float(outros_passivos)

    # Benefício fiscal sobre contingências: incide apenas sobre a parcela dedutível
    pct_dedutivel = pct_ded_val / 100.0
    contingentes_dedutiveis = contingentes_bruto * pct_dedutivel
    contingentes_nao_dedutiveis = contingentes_bruto - contingentes_dedutiveis

    contingentes_liquidos_dedutiveis = contingentes_dedutiveis * (1.0 - tax_rate)
    contingentes_liquidos = contingentes_liquidos_dedutiveis + contingentes_nao_dedutiveis
    beneficio_fiscal_quase_divida = contingentes_dedutiveis - contingentes_liquidos_dedutiveis

    # Passivo regulatório negativo é tratado como ATIVO regulatório (adiciona ao valor ou reduz dívida)
    quase_dividas_total_liquidas = contingentes_liquidos + regulatorio + outros_nao_dedutiveis
    divida_total_ajustada = divida_fin_liq + quase_dividas_total_liquidas

    # Cenário Base: Apenas dívida financeira líquida
    equity_value_base = enterprise_value - divida_fin_liq
    preco_justo_base = max(0.0, equity_value_base / float(num_acoes))
    preco_teto_base = preco_justo_base * (1.0 - (float(margem_seguranca) / 100.0))

    # Cenário Ajustado: Deduzindo passivos regulatórios, contingências e déficits atuariais líquidos
    equity_value_ajustado = enterprise_value - divida_total_ajustada
    preco_justo_ajustado = max(0.0, equity_value_ajustado / float(num_acoes))
    preco_teto_ajustado = preco_justo_ajustado * (1.0 - (float(margem_seguranca) / 100.0))

    # Se quase-dívidas/passivos regulatórios foram informados, o preço oficial adotado é o ajustado
    if contingentes_bruto > 0 or regulatorio != 0.0 or outros_nao_dedutiveis != 0.0:
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
    taxas_para_validacao = taxas_crescimento if taxas_crescimento else [p["crescimento_pct"] for p in projecoes]
    validacao_crescimento = validate_growth_and_market_share(
        fclf_inicial=fclf_inicial,
        taxas_crescimento=taxas_para_validacao,
        cresc_perp=cresc_perp,
        historico_fcf=historico_fcf,
        cagr_historico=cagr_historico,
        market_share_dinamica=market_share_dinamica,
        decomposicao_g1=decomposicao_g1,
        analise_competitiva=analise_competitiva,
        validar_soma_g1=bool(taxas_crescimento),
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
        meta["normalizar_capex_fluxo"] = normalizar_capex_fluxo
    if teto_crescimento_oligopolio is not None:
        meta["teto_crescimento_oligopolio_aplicado"] = teto_crescimento_oligopolio
    if prazo_concessao_anos is not None:
        meta["prazo_concessao_anos"] = prazo_concessao_anos
        meta["rab_indenizavel_mi"] = round(float(rab_indenizavel_mi), 2)

    detalhes_dict = {
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
        "outros_passivos_nao_dedutiveis": round(outros_nao_dedutiveis, 2),
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
    }
    if fator_anuidade is not None:
        detalhes_dict["fator_anuidade_finita"] = round(fator_anuidade, 6)
        detalhes_dict["vp_rab_indenizavel_em_t_mi"] = round(vp_rab_em_t, 2)

    return {
        "ticker": ticker.upper(),
        "modelo": "dcf_fcff",
        "fclf": round(float(fclf_inicial), 2),
        "anosProjecao": periodo_explicito,
        "taxasCrescimento": [round(float(t), 2) for t in taxas_para_validacao],
        "wacc": round(float(wacc), 2),
        "crescPerp": round(float(cresc_perp), 2),
        "dividaLiquida": round(divida_final, 2),
        "numAcoes": round(float(num_acoes), 2),
        "margemSeguranca": round(float(margem_seguranca), 2),
        "precoJusto": round(preco_justo_final, 2),
        "precoTeto": round(preco_teto_final, 2),
        "detalhes": detalhes_dict,
    }
