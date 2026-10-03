#!/usr/bin/env python3
"""Wrapper leve para cálculo de Operadoras de Saúde ANS delegando ao CLI unificado valuation_cli.py (DRY).
Mantém total compatibilidade de flags com a skill dcf-valuation.
"""
import sys
from pathlib import Path


def find_project_root() -> Path:
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "valuation_cli.py").exists() or (parent / "pyproject.toml").exists():
            return parent
    return Path.cwd()


PROJECT_ROOT = find_project_root()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import valuation_cli

if __name__ == "__main__":
    sys.argv.insert(1, "saude")
    valuation_cli.main()
