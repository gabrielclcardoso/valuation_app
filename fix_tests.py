import re

with open("tests/test_valuation_engine.py", "r") as f:
    content = f.read()

# Fix calculate_dcf calls that lack fclf_inicial
content = re.sub(
    r'ebitda_al=(\d+\.\d+),\s*capex_projetado=(\d+\.\d+),',
    r'fclf_inicial=\g<1> - \g<2>,\n            ebitda_al=\g<1>,\n            capex_projetado=\g<2>,',
    content
)

# Replace quase_divida_dedutivel=True with pct_contingencia_dedutivel=100.0
content = content.replace("quase_divida_dedutivel=True", "pct_contingencia_dedutivel=100.0")

# Replace resultado_financeiro with ganhos_float and despesas_juros_fixa
content = re.sub(
    r'resultado_financeiro=([\d\.]+),',
    r'ganhos_float=\g<1>,\n            despesas_juros_fixa=0.0,\n            ntnb=6.0,',
    content
)

with open("tests/test_valuation_engine.py", "w") as f:
    f.write(content)
