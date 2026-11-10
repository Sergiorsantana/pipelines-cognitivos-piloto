# -*- coding: utf-8 -*-
"""Executa o estudo piloto da Seção 5.2: 25 rodadas, 8.000 registros por rodada,
três pipelines (ETL, ELT e mapeador cognitivo lexical) sobre os mesmos dados.

As métricas emergem da execução real dos pipelines (E/S em SQLite, psutil para
CPU e memória, time.perf_counter para tempo e latência).

Uso (a partir da raiz do repositório):
    python src/run_experiment.py --saida results/novo
"""
import argparse
import os
import sqlite3
import sys
import tempfile

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from data_generator import generate_source_dataset  # noqa: E402
from pipelines import run_etl, run_elt, run_cognitive  # noqa: E402
from resource_monitor import run_with_monitoring  # noqa: E402


def main(n_runs, n_records, saida):
    os.makedirs(saida, exist_ok=True)
    tmpdir = tempfile.mkdtemp(prefix="piloto_")
    conn = sqlite3.connect(os.path.join(tmpdir, "experiment.db"), check_same_thread=False)
    results = []

    for run_id in range(1, n_runs + 1):
        frac = (run_id - 1) / (n_runs - 1)
        drift_prob = 0.15 + 0.5 * frac        # 0,15 -> 0,65
        malformed_prob = 0.10 + 0.4 * frac    # 0,10 -> 0,50

        rows, column_map_truth, used_names = generate_source_dataset(
            n_records, drift_prob, malformed_prob, seed=1000 + run_id)

        for arch_name, func in (("ETL", run_etl), ("ELT", run_elt), ("Cognitivo", run_cognitive)):
            m = run_with_monitoring(func, rows, column_map_truth, conn)
            throughput = m["n_records"] / m["exec_time_s"]
            results.append({
                "run_id": run_id,
                "arquitetura": arch_name,
                "drift_prob": round(drift_prob, 3),
                "malformed_prob": round(malformed_prob, 3),
                "n_records": m["n_records"],
                "tempo_execucao_s": m["exec_time_s"],
                "latencia_ms": m["latency_ms"],
                "throughput_rps": throughput,
                "cpu_medio_pct": m["cpu_avg_pct"],
                "memoria_pico_mb": m["mem_peak_mb"],
                "taxa_sucesso_pct": m["success_rate_pct"],
                "precisao_mapeamento_pct": m["mapping_precision_pct"],
            })
            print(f"run={run_id:02d} arch={arch_name:10s} t={m['exec_time_s']:.3f}s "
                  f"lat={m['latency_ms']:.1f}ms thr={throughput:.0f}rec/s cpu={m['cpu_avg_pct']:.1f}% "
                  f"mem={m['mem_peak_mb']:.1f}MB sucesso={m['success_rate_pct']:.1f}% "
                  f"map={m['mapping_precision_pct']:.1f}%")

    conn.close()
    destino = os.path.join(saida, "resultados_brutos.csv")
    pd.DataFrame(results).to_csv(destino, index=False)
    print("\nSalvo em", destino)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rodadas", type=int, default=25)
    ap.add_argument("--registros", type=int, default=8000)
    ap.add_argument("--saida", default="results/novo")
    a = ap.parse_args()
    main(a.rodadas, a.registros, a.saida)
