"""Módulo de exportação padronizada de resultados em JSON e exibição de dossiê no terminal.
Garante rigorosamente a regra do Modo Cego (Blind Valuation):
Preços Justos, Preços Tetos e Tetos Bazin NUNCA são impressos no terminal ou chat,
ficando restritos ao arquivo JSON para revelação exclusivamente na Calculadora Web.
"""
import json
from pathlib import Path
from typing import Dict, Any, Optional


def save_valuation_json(resultado: Dict[str, Any], output_path: Optional[str] = None) -> Path:
    """Salva o dicionário de valuation padronizado na pasta valuations/<ticker>_valuation.json."""
    ticker = resultado.get("ticker", "VALUATION").upper()
    if output_path:
        out_file = Path(output_path)
    else:
        val_dir = Path("valuations")
        val_dir.mkdir(parents=True, exist_ok=True)
        out_file = val_dir / f"{ticker}_valuation.json"

    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(resultado, f, indent=2, ensure_ascii=False)

    return out_file


def print_dossier_summary(resultado: Dict[str, Any], output_path: Path):
    """Exibe o Dossiê dos Parâmetros Registrados no terminal preservando o Modo Cego."""
    ticker = resultado.get("ticker", "").upper()
    modelo = resultado.get("modelo", "dcf_fcff")
    detalhes = resultado.get("detalhes", {})
    modelo_nome = detalhes.get("modelo_utilizado", "Valuation Fundamentalista")

    print("\n" + "=" * 65)
    print(f" VALUATION REGISTRADO: {ticker} ({modelo_nome})")
    print("=" * 65)

    if modelo == "dcf_fcff":
        print(f"• Fluxo Livre Inicial (FCFF): R$ {resultado['fclf']:,.2f} Mi")
        print(f"• WACC Nominal: {resultado['wacc']:.2f}% a.a.")
        print(f"• Trajetória de Crescimento (5 anos): {resultado['taxasCrescimento']}")
        print(f"• Crescimento Perpétuo (g_perp): {resultado['crescPerp']:.2f}% a.a.")
        print(f"• Dívida Financeira Líquida: R$ {detalhes.get('divida_financeira_liquida', 0):,.2f} Mi")
        contingentes_bruto = detalhes.get("passivos_contingentes_bruto", 0)
        regulatorio = detalhes.get("passivos_regulatorios", 0)
        outros_deduzidos = detalhes.get("outros_passivos_deduzidos", 0)
        if contingentes_bruto > 0 or regulatorio != 0 or outros_deduzidos != 0:
            if contingentes_bruto > 0:
                print(f"• Passivos Contingentes (Bruto): R$ {contingentes_bruto:,.2f} Mi (Líquido IR/CSLL 34%: R$ {detalhes.get('passivos_contingentes_liquidos', 0):,.2f} Mi)")
            if regulatorio != 0:
                if regulatorio < 0:
                    print(f"• Ativo Regulatório Líquido: R$ {abs(regulatorio):,.2f} Mi")
                else:
                    print(f"• Passivo Regulatório: R$ {regulatorio:,.2f} Mi")
            print(f"• Dívida Total Ajustada: R$ {detalhes['divida_total_ajustada']:,.2f} Mi")

    elif modelo == "gordon_ddm":
        print(f"• VPA (Valor Patrimonial por Ação): R$ {detalhes.get('vpa', 0):,.2f}")
        print(f"• ROE Sustentável Adotado: {detalhes.get('roe_adotado_pct', 0):.2f}% a.a.")
        print(f"• Custo do Capital Próprio (Ke): {detalhes.get('ke_adotado_pct', 0):.2f}% a.a.")
        print(f"• Crescimento Perpétuo (g_perp): {resultado['crescPerp']:.2f}% a.a.")
        print("• P/VP Justo Teórico derivado: [Preservado no JSON para Modo Cego]")
        print(f"• Payout Sustentável: {detalhes.get('payout_sustentavel_pct', 0):.1f}%")
        print(f"• DPA Base Projetado: R$ {detalhes.get('dpa_ano_base', 0):.4f}")

    elif modelo == "sotp_holding":
        print(f"• Soma das Partes (NAV Bruto Mercado): R$ {detalhes.get('total_mercado_bruto_mi', 0):,.2f} Mi")
        print(f"• Soma das Partes (NAV Bruto Intrínseco): R$ {detalhes.get('total_intrinseco_bruto_mi', 0):,.2f} Mi")
        print(f"• Dívida Líquida Própria da Holding: R$ {detalhes.get('divida_liquida_holding_mi', 0):,.2f} Mi")
        if detalhes.get("vp_despesas_adm_holding_mi", 0) > 0:
            print(f"• VP Despesas Administrativas da Holding: R$ {detalhes['vp_despesas_adm_holding_mi']:,.2f} Mi")
        print(f"• Desconto de Holding Adotado: {detalhes.get('desconto_holding_adotado_pct', 0):.1f}%")
        print(f"• DPA Estimado da Holding: R$ {detalhes.get('dpa_holding_projetado', 0):.4f}")

    elif modelo == "saude_ans":
        print(f"• Receita Líquida (Contraprestações): R$ {detalhes.get('receita_liquida_mi', 0):,.2f} Mi")
        print(f"• Sinistralidade Médica (MLR): {detalhes.get('sinistralidade_mlr_pct', 0):.2f}%")
        print(f"• Custo do Capital Próprio (Ke): {resultado['wacc']:.2f}% a.a.")
        print(f"• Retenção para Margem de Solvência ANS: R$ {detalhes.get('retencao_reserva_solvencia_ans_mi', 0):,.2f} Mi")
        print(f"• DPA Base Projetado: R$ {detalhes.get('dpa_ano_base', 0):.4f}")

    print(f"• Base Acionária: {resultado['numAcoes']:,.2f} Mi ações/Units")
    print(f"• Margem de Segurança Aplicada: {resultado['margemSeguranca']:.1f}%")

    if detalhes.get("metrica_bazin"):
        bazin = detalhes["metrica_bazin"]
        print(f"• Métrica Bazin: DPA projetado de R$ {bazin['dpa_projetado']:.2f} (Tetos Bazin 6% e 8% no JSON)")

    print(f"• Arquivo JSON salvo com sucesso em: {output_path}")
    print("  [Preço Justo, Preço Teto e Tetos Bazin preservados no JSON para revelação na Calculadora]")
    print("=" * 65 + "\n")
