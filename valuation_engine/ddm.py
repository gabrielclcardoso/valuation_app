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
    payout: Optional[float] = 50.0,
    dpa_projetado: Optional[float] = None,
    taxas_crescimento_dpa: Optional[List[float]] = None,
    num_acoes: float = 1.0,
    margem_seguranca: float = 20.0,
    pct_jcp: float = 0.0,
    tipo: str = "banco",
    empresa: str = "",
    setor: str = "",
    metadata: Optional[Dict[str, Any]] = None,
    ntnb: Optional[float] = None,
    pdd_atual: Optional[float] = None,
    pdd_media_5a: Optional[float] = None,
    roe_10a: Optional[float] = None,
    sinistralidade_atual: Optional[float] = None,
    sinistralidade_media_5a: Optional[float] = None,
    prazo_acordo_anos: Optional[float] = None,
    modo_penalizacao: str = "gradual",
    alinhar_dpa_base_ano1: bool = True,
) -> Dict[str, Any]:
    """Calcula o Preço Justo e Preço Teto para Bancos e Seguradoras via Gordon e DDM.
    Garante a coerência entre Payout sustentável e crescimento perpétuo (g = ROE * (1 - Payout)),
    alinhamento temporal t=1..T no DDM multiestágio (Clean Surplus) e penalização gradual sem efeito penhasco.
    """
    if metadata is None:
        metadata = {}

    roe_original = float(roe)
    roe_truncado_por_ciclo = False
    if roe_10a is not None:
        if roe_original > float(roe_10a):
            roe_truncado_por_ciclo = (roe_original - float(roe_10a)) >= 2.0
        roe = min(roe_original, float(roe_10a))

    ipca_ref = 0.035
    rf_nominal_pct = None
    if ntnb is not None:
        rf_nominal_pct = ((1.0 + float(ntnb) / 100.0) * (1.0 + ipca_ref) - 1.0) * 100.0
        spread_min = 2.0 if tipo == "seguradora" else 3.5
        ke = max(float(ke), rf_nominal_pct + spread_min)

    if pdd_atual is not None and pdd_media_5a is not None:
        if float(pdd_atual) < float(pdd_media_5a):
            if modo_penalizacao == "estrito":
                margem_seguranca = max(float(margem_seguranca), 35.0)
            else:
                desvio_pdd = (
                    (float(pdd_media_5a) - float(pdd_atual)) / float(pdd_media_5a)
                    if float(pdd_media_5a) > 0
                    else 1.0
                )
                if roe_truncado_por_ciclo:
                    # Ciclo de crédito já foi absorvido pelo corte de ROE via roe_10a; evita dupla/tripla punição
                    alvo_pdd = 25.0
                else:
                    alvo_pdd = 25.0 if desvio_pdd <= 0.15 else 35.0
                margem_seguranca = max(float(margem_seguranca), alvo_pdd)
            metadata["alerta_npl"] = (
                f"Margem de segurança ajustada para >={margem_seguranca:.1f}% devido à cobertura de PDD abaixo da média de 5 anos."
            )

    if tipo == "seguradora":
        if sinistralidade_atual is not None and sinistralidade_media_5a is not None:
            if float(sinistralidade_atual) < 0 or float(sinistralidade_media_5a) < 0:
                raise ValueError("A sinistralidade não pode ser negativa.")
            if float(sinistralidade_atual) > float(sinistralidade_media_5a):
                if modo_penalizacao == "estrito":
                    margem_seguranca = max(float(margem_seguranca), 35.0)
                else:
                    excesso_sinist = float(sinistralidade_atual) - float(sinistralidade_media_5a)
                    alvo_sinist = 25.0 if roe_truncado_por_ciclo else min(35.0, 20.0 + excesso_sinist * 1.5)
                    margem_seguranca = max(float(margem_seguranca), round(alvo_sinist, 2))
                metadata["alerta_sinistralidade"] = (
                    f"Margem de segurança ajustada para >={margem_seguranca:.1f}% devido à sinistralidade atual acima da média de 5 anos."
                )

        if prazo_acordo_anos is not None:
            if float(prazo_acordo_anos) < 0:
                raise ValueError("O prazo do acordo não pode ser negativo.")
            if float(prazo_acordo_anos) < 10.0:
                if modo_penalizacao == "estrito":
                    margem_seguranca = max(float(margem_seguranca), 40.0)
                else:
                    margem_acordo = 20.0 + 2.0 * max(0.0, 10.0 - float(prazo_acordo_anos))
                    margem_seguranca = max(float(margem_seguranca), round(margem_acordo, 2))
                metadata["alerta_prazo_acordo"] = (
                    f"Margem de segurança ajustada para >={margem_seguranca:.1f}% devido ao prazo do acordo de balcão < 10 anos."
                )

    cresc_perp = min(float(cresc_perp), 4.5)

    ke_dec = float(ke) / 100.0
    g_perp_dec = float(cresc_perp) / 100.0
    roe_dec = float(roe) / 100.0
    vpa_val = float(vpa)
    payout_dec = (float(payout) / 100.0) if payout is not None else None

    if ke_dec <= g_perp_dec:
        raise ValueError(
            f"O Custo de Capital Próprio Ke ({ke}%) deve ser estritamente maior que o Crescimento Perpétuo ({cresc_perp}%)."
        )
    if vpa_val <= 0:
        raise ValueError("O VPA (Valor Patrimonial por Ação) deve ser maior que zero.")
    if num_acoes <= 0:
        raise ValueError("O número de ações deve ser maior que zero.")

    # 1. Coerência Fundamental entre Crescimento Perpétuo e Payout Sustentável:
    # Na perpetuidade, a taxa de retenção necessária para sustentar g é b = g / ROE.
    # Logo, o Payout sustentável na perpetuidade é Payout_sust = 1 - (g / ROE).
    payout_sustentavel_perp = max(0.0, min(1.0, 1.0 - (g_perp_dec / roe_dec))) if roe_dec > 0 else 0.0
    payout_ref_dec = payout_dec if payout_dec is not None else payout_sustentavel_perp
    g_sustentavel_do_payout = (roe_dec * (1.0 - payout_ref_dec)) * 100.0

    # 2. Modelo de Gordon Fundamentalista via P/VP Justo:
    # P/VP Justo = (ROE - g) / (Ke - g)
    p_vp_justo = max(0.0, (roe_dec - g_perp_dec) / (ke_dec - g_perp_dec))
    preco_justo_gordon = p_vp_justo * vpa_val

    # 3. Definição do DPA Efetivo de Ano 1 (para Bazin e ancoragem de Ano 1 no DDM):
    # LPA_1 = VPA_0 * ROE
    lpa_teorico = vpa_val * roe_dec
    if dpa_projetado is not None and dpa_projetado > 0:
        dpa_base = float(dpa_projetado)
        payout_efetivo = (dpa_base / lpa_teorico * 100.0) if lpa_teorico > 0 else (payout_sustentavel_perp * 100.0)
    elif payout is not None:
        # Usa o payout efetivo informado para refletir o dividendo real do Ano 1 na métrica Bazin
        dpa_base = lpa_teorico * payout_dec
        payout_efetivo = float(payout)
    else:
        # Se payout não foi explicitamente informado, usa o payout sustentável perpétuo
        dpa_base = lpa_teorico * payout_sustentavel_perp
        payout_efetivo = payout_sustentavel_perp * 100.0

    # 4. DDM Multiestágio (com Alinhamento Temporal t=1..T e Clean Surplus) ou Gordon Direto
    if taxas_crescimento_dpa:
        taxas = [float(t) for t in taxas_crescimento_dpa]
        g1_dec = taxas[0] / 100.0
        if alinhar_dpa_base_ano1 and (1.0 + g1_dec) > 0.0:
            dpa_atual = dpa_base / (1.0 + g1_dec)
            lpa_atual = lpa_teorico / (1.0 + g1_dec)
        else:
            dpa_atual = dpa_base
            lpa_atual = lpa_teorico

        vpa_atual = vpa_val
        soma_pv_dpa = 0.0
        projecoes = []

        for t, taxa in enumerate(taxas, start=1):
            g_dec = float(taxa) / 100.0
            dpa_atual = dpa_atual * (1.0 + g_dec)
            lpa_atual = lpa_atual * (1.0 + g_dec)
            vpa_atual = vpa_atual + lpa_atual - dpa_atual
            pv = dpa_atual / ((1.0 + ke_dec) ** t)
            soma_pv_dpa += pv
            projecoes.append(
                {
                    "ano": t,
                    "crescimento_pct": round(float(taxa), 2),
                    "lpa_projetado": round(lpa_atual, 4),
                    "dpa_projetado": round(dpa_atual, 4),
                    "vpa_projetado": round(vpa_atual, 4),
                    "valor_presente": round(pv, 4),
                }
            )

        # Valor Terminal: na perpetuidade, o lucro cresce a g_perp e o payout
        # converge para o nível sustentável teórico (1 - g_perp / ROE)
        lpa_terminal = lpa_atual * (1.0 + g_perp_dec)
        dpa_terminal = lpa_terminal * payout_sustentavel_perp
        valor_terminal_dpa = dpa_terminal / (ke_dec - g_perp_dec)
        vp_terminal_dpa = valor_terminal_dpa / ((1.0 + ke_dec) ** len(taxas))
        preco_justo_ddm = soma_pv_dpa + vp_terminal_dpa

        # Quando fornecida trajetória multiestágio explícita, adota-se o DDM multiestágio
        preco_justo_adotado = preco_justo_ddm
    else:
        # Sem trajetória multiestágio explícita: Gordon e DDM convergem exatamente pela coerência de payout!
        preco_justo_ddm = preco_justo_gordon
        preco_justo_adotado = preco_justo_gordon
        projecoes = []

    preco_justo_final = round(preco_justo_adotado, 2)
    preco_teto_adotado = round(preco_justo_final * (1.0 - (float(margem_seguranca) / 100.0)), 2)

    # Métrica Bazin (ancorada no DPA efetivo de Ano 1)
    metrica_bazin = calculate_bazin(
        dpa=dpa_base,
        preco_teto_modelo=preco_teto_adotado,
        pct_jcp=pct_jcp,
    )

    total_proventos_ano = round(dpa_base * float(num_acoes), 2)

    # Métricas de Sanidade Econômica (ajustadas dinamicamente pela ETTJ da NTN-B para evitar deadlock)
    p_l_justo = round(preco_justo_final / lpa_teorico, 2) if lpa_teorico > 0 else None
    yield_justo = round((dpa_base / preco_justo_final) * 100.0, 2) if preco_justo_final > 0 else None
    spread_ke_g = round(float(ke) - float(cresc_perp), 2)

    if rf_nominal_pct is not None and ntnb is not None:
        limite_spread_nominal = max(
            round(10.5 + max(0.0, float(ntnb) - 6.0), 2),
            round(rf_nominal_pct + 6.0 - float(cresc_perp), 2),
        )
    else:
        limite_spread_nominal = 10.5

    avisos_metodologicos = []
    if spread_ke_g > limite_spread_nominal:
        avisos_metodologicos.append(
            f"Spread (Ke - g) de {spread_ke_g:.2f}% é excessivo para perpetuidade (limite dinâmico de {limite_spread_nominal:.2f}%), "
            "indicando provável sobretaxação de Ke."
        )

    meta = metadata.copy() if metadata else {}
    if empresa:
        meta["empresa"] = empresa
    if setor:
        meta["setor"] = setor
    meta["tipo_instituicao"] = tipo
    meta["modo_penalizacao"] = modo_penalizacao

    return {
        "ticker": ticker.upper(),
        "modelo": "gordon_ddm",
        "fclf": total_proventos_ano,
        "anosProjecao": len(projecoes) if projecoes else 5,
        "taxasCrescimento": [p["crescimento_pct"] for p in projecoes] if projecoes else [round(float(cresc_perp), 2)] * 5,
        "wacc": round(float(ke), 2),  # Ke substitui WACC
        "crescPerp": round(float(cresc_perp), 2),
        "dividaLiquida": 0.0,
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
            "p_l_justo_implicito": p_l_justo,
            "dividend_yield_justo_pct": yield_justo,
            "spread_ke_g_pct": spread_ke_g,
            "limite_spread_ke_g_pct": round(limite_spread_nominal, 2),
            "avisos_metodologicos": avisos_metodologicos,
            "payout_sustentavel_pct": round(payout_efetivo, 2),
            "payout_sustentavel_teorico_pct": round(payout_sustentavel_perp * 100.0, 2),
            "crescimento_sustentavel_payout_adotado_pct": round(g_sustentavel_do_payout, 2),
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
                    "descricao": "Desconto dos Fluxos de Proventos Futuros (DDM)",
                    "preco_justo": round(preco_justo_ddm, 2),
                    "preco_teto": round(preco_justo_ddm * (1.0 - float(margem_seguranca) / 100.0), 2),
                },
            },
            "metrica_bazin": metrica_bazin,
            "projecoes_dpa": projecoes,
            "metadata": meta,
        },
    }
