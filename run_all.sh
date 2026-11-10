#!/usr/bin/env bash
# Mesma sequência de run_all.ps1 para Linux e macOS.
set -euo pipefail
python src/run_experiment.py --saida results/novo
python src/verificar_reproducao.py results/resultados_brutos.csv results/novo/resultados_brutos.csv
python analysis/analise_piloto.py results/novo/resultados_brutos.csv results/novo/tabelas
python analysis/graficos.py results/novo/resultados_brutos.csv results/novo/figuras
echo "Concluído. Veja results/novo/"
