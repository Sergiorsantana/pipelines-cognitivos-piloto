# -*- coding: utf-8 -*-
"""Compara uma nova execução com os resultados publicados no repositório.

Taxa de sucesso e precisão do mapeamento são determinísticas (semente fixa por rodada)
e devem coincidir. Tempo, latência, throughput, CPU e memória dependem da máquina e
variam entre execuções, então são apenas resumidos.

Uso: python src/verificar_reproducao.py results/resultados_brutos.csv results/novo/resultados_brutos.csv
"""
import sys
import numpy as np
import pandas as pd

ref = pd.read_csv(sys.argv[1]).sort_values(["run_id", "arquitetura"]).reset_index(drop=True)
novo = pd.read_csv(sys.argv[2]).sort_values(["run_id", "arquitetura"]).reset_index(drop=True)
ok = True
for col in ("taxa_sucesso_pct", "precisao_mapeamento_pct"):
    igual = np.allclose(ref[col], novo[col], atol=1e-9)
    ok &= igual
    print(f"{col}: {'IGUAL' if igual else 'DIFERENTE'} em todas as {len(ref)} linhas" if igual
          else f"{col}: DIFERENTE (maior diferença {np.abs(ref[col]-novo[col]).max():.4f})")
print("\nMétricas dependentes da máquina (média por arquitetura, publicado -> novo):")
for col in ("tempo_execucao_s", "latencia_ms", "throughput_rps", "cpu_medio_pct", "memoria_pico_mb"):
    a = ref.groupby("arquitetura")[col].mean(); b = novo.groupby("arquitetura")[col].mean()
    print(" ", col, {k: f"{a[k]:.3f} -> {b[k]:.3f}" for k in ("ETL", "ELT", "Cognitivo")})
sys.exit(0 if ok else 1)
