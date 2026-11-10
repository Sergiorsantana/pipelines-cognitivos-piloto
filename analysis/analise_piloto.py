#!/usr/bin/env python3
"""Análise estatística do estudo piloto (Seção 5.2).

Entrada: CSV em formato longo, uma linha por rodada e arquitetura, com as colunas
  rodada, arquitetura, tempo_s, latencia_ms, throughput, cpu_pct, mem_mb, sucesso_pct, precisao_pct
Os valores de "arquitetura" devem ser exatamente: ETL, ELT, Cognitivo.

Uso:  python analysis/analise_piloto.py results/resultados_brutos.csv results/tabelas
(aceita tanto o CSV bruto do experimento quanto o formato longo descrito acima)

Saídas (CSV, com decimal em ponto): tabela_5_3_descritiva.csv, tabela_5_4_pareados.csv,
tabela_5_5_severidade.csv, friedman.csv
"""
import sys, itertools, os
import numpy as np, pandas as pd
from scipy import stats

METRICAS = {
    'tempo_s': 'Tempo médio (s)', 'latencia_ms': 'Latência (ms)', 'throughput': 'Throughput (registros/s)',
    'cpu_pct': 'CPU (%)', 'mem_mb': 'Memória (MB)', 'sucesso_pct': 'Taxa de sucesso das integrações (%)',
    'precisao_pct': 'Precisão do mapeamento (%)'}
ARQ = ['ETL', 'ELT', 'Cognitivo']
SEED = 20260808
N_BOOT = 10000
ALFA = 0.05

def holm(p):
    """Correção de Holm-Bonferroni. Retorna p ajustados na ordem original."""
    p = np.asarray(p, float); m = len(p); ordem = np.argsort(p)
    aj = np.empty(m); correntes = 0.0
    for i, idx in enumerate(ordem):
        correntes = max(correntes, (m - i) * p[idx]); aj[idx] = min(1.0, correntes)
    return aj

def ic_boot(d, rng):
    """IC95% percentil da mediana das diferenças pareadas."""
    d = np.asarray(d, float)
    meds = np.median(rng.choice(d, size=(N_BOOT, len(d)), replace=True), axis=1)
    return np.percentile(meds, [2.5, 97.5])

def rank_biserial(d):
    """Correlação rank-biserial para pares (Kerby, 2014): (T+ - T-) / (T+ + T-)."""
    d = np.asarray(d, float); d = d[d != 0]
    if len(d) == 0: return np.nan
    r = stats.rankdata(np.abs(d)); tp = r[d > 0].sum(); tm = r[d < 0].sum()
    return (tp - tm) / (tp + tm)

def main(caminho, saida):
    os.makedirs(saida, exist_ok=True)
    df = pd.read_csv(caminho)
    # aceita diretamente o CSV gerado por src/run_experiment.py
    df = df.rename(columns={'run_id': 'rodada', 'tempo_execucao_s': 'tempo_s', 'throughput_rps': 'throughput',
                            'cpu_medio_pct': 'cpu_pct', 'memoria_pico_mb': 'mem_mb',
                            'taxa_sucesso_pct': 'sucesso_pct', 'precisao_mapeamento_pct': 'precisao_pct'})
    faltam = {'rodada', 'arquitetura', *METRICAS} - set(df.columns)
    if faltam: sys.exit(f'Colunas ausentes: {sorted(faltam)}')
    ape = {m: df.pivot(index='rodada', columns='arquitetura', values=m)[ARQ].sort_index() for m in METRICAS}
    n = len(ape['tempo_s'])
    if ape['tempo_s'].isna().any().any(): sys.exit('Há valores ausentes: o desenho pareado exige as três arquiteturas em todas as rodadas.')
    rng = np.random.default_rng(SEED)

    # Tabela 5.3: estatística descritiva (média, desvio-padrão, mediana)
    linhas = []
    for m, nome in METRICAS.items():
        for a in ARQ:
            x = ape[m][a]
            linhas.append(dict(metrica=nome, arquitetura=a, media=x.mean(), desvio_padrao=x.std(ddof=1), mediana=x.median(), n=n))
    pd.DataFrame(linhas).to_csv(f'{saida}/tabela_5_3_descritiva.csv', index=False)

    # Friedman por métrica (três grupos, rodadas como blocos)
    fr = []
    for m, nome in METRICAS.items():
        x = [ape[m][a].values for a in ARQ]
        if all(np.allclose(x[0], v) for v in x[1:]):
            fr.append(dict(metrica=nome, chi2=np.nan, gl=2, p=np.nan, observacao='três arquiteturas idênticas em todas as rodadas')); continue
        chi2, p = stats.friedmanchisquare(*x)
        fr.append(dict(metrica=nome, chi2=chi2, gl=2, p=p, observacao=''))
    pd.DataFrame(fr).to_csv(f'{saida}/friedman.csv', index=False)

    # Comparações pareadas: Wilcoxon signed-rank, Holm dentro de cada métrica
    pares = list(itertools.combinations(ARQ, 2))
    out = []
    for m, nome in METRICAS.items():
        brutos, linhas_m = [], []
        for a, b in pares:
            d = (ape[m][a] - ape[m][b]).values
            if np.allclose(d, 0):
                linhas_m.append(dict(metrica=nome, comparacao=f'{a} − {b}', dif_mediana=0.0, ic_inf=0.0, ic_sup=0.0,
                                     rbc=np.nan, p_bruto=np.nan, observacao='idênticos em todas as rodadas (mesma regra de mapeamento)'))
                continue
            w = stats.wilcoxon(d, zero_method='wilcox', alternative='two-sided', method='auto')
            lo, hi = ic_boot(d, rng)
            linhas_m.append(dict(metrica=nome, comparacao=f'{a} − {b}', dif_mediana=float(np.median(d)), ic_inf=lo, ic_sup=hi,
                                 rbc=rank_biserial(d), p_bruto=w.pvalue, observacao=''))
            brutos.append(len(linhas_m) - 1)
        if brutos:
            aj = holm([linhas_m[i]['p_bruto'] for i in brutos])
            for i, pa in zip(brutos, aj): linhas_m[i]['p_holm'] = pa
        out += linhas_m
    t = pd.DataFrame(out)
    t['significativo_holm'] = t['p_holm'] < ALFA
    t.to_csv(f'{saida}/tabela_5_4_pareados.csv', index=False)

    # Efeito da severidade: Spearman entre o índice da rodada e a métrica, por arquitetura
    sev = []
    idx = ape['tempo_s'].index.values
    for m, nome in METRICAS.items():
        brutos, linhas_m = [], []
        for a in ARQ:
            y = ape[m][a].values
            if np.allclose(y, y[0]):
                linhas_m.append(dict(metrica=nome, arquitetura=a, rho=np.nan, p_bruto=np.nan, observacao='constante')); continue
            r, p = stats.spearmanr(idx, y)
            linhas_m.append(dict(metrica=nome, arquitetura=a, rho=r, p_bruto=p, observacao='')); brutos.append(len(linhas_m) - 1)
        if brutos:
            aj = holm([linhas_m[i]['p_bruto'] for i in brutos])
            for i, pa in zip(brutos, aj): linhas_m[i]['p_holm'] = pa
        sev += linhas_m
    pd.DataFrame(sev).to_csv(f'{saida}/tabela_5_5_severidade.csv', index=False)
    print('Arquivos gravados em', saida)

if __name__ == '__main__':
    if len(sys.argv) != 3: sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
