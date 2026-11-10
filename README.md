# Pipelines Cognitivos: estudo piloto (Seção 5.2)

Código, dados e resultados do estudo piloto da proposta de qualificação de doutorado
"Pipelines Cognitivos: Integração de Dados Baseada em LLMs com Autonomia Supervisionada e Mensurável"
(Centro de Informática, UFPE). O piloto compara três pipelines sobre dados sintéticos com
variação de nomenclatura (schema drift) e ruído de formato crescentes:

| Pipeline | O que faz |
|---|---|
| ETL | Mapeamento de esquema fixo, transformação antes da carga |
| ELT | Mapeamento de esquema fixo, carga do dado bruto e transformação depois |
| Cognitivo | Mapeador lexical (TF-IDF com cosseno e similaridade de strings), com leitura de várias formas de data e de valor monetário |

**Limites que o leitor deve conhecer.** O mapeador do piloto não usa LLM, RAG, banco vetorial nem
verificador determinístico. Ele é um substituto determinístico e offline do agente da tese e serve de
linha de base lexical para a QP1. O piloto não mede intervenção humana nem registros incorretos no
destino e, portanto, não testa a hipótese H1. As limitações completas estão na Seção 6.3 da proposta.

## Estrutura

```
src/
  data_generator.py        gerador de dados sintéticos (7 campos canônicos, drift e ruído)
  pipelines.py             run_etl, run_elt e run_cognitive
  resource_monitor.py      CPU e memória do processo (psutil, amostragem a cada 10 ms)
  run_experiment.py        executa as 25 rodadas e grava o CSV bruto
  verificar_reproducao.py  compara uma nova execução com os resultados publicados
analysis/
  analise_piloto.py        Friedman, Wilcoxon com Holm, bootstrap, rank-biserial e Spearman
  graficos.py              Figuras 5.3 a 5.7
results/
  resultados_brutos.csv    execução publicada na proposta (novembro de 2026, Windows 11, Intel Core i5-14450HX, Python 3.14)
  tabelas/                 Tabelas 5.3, 5.4 e 5.5 e testes de Friedman
figures/                   Figuras 5.3 a 5.7
```

## Como executar

Requisitos: Python 3.10 ou superior.

Windows (PowerShell), a partir da pasta do repositório:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
.\run_all.ps1
```

Se o PowerShell bloquear a ativação do ambiente, rode uma vez
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` e repita.

Linux e macOS:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
./run_all.sh
```

A execução completa leva menos de um minuto. Cada etapa também pode ser rodada separadamente:

```
python src/run_experiment.py --saida results/novo
python src/verificar_reproducao.py results/resultados_brutos.csv results/novo/resultados_brutos.csv
python analysis/analise_piloto.py results/novo/resultados_brutos.csv results/novo/tabelas
python analysis/graficos.py results/novo/resultados_brutos.csv results/novo/figuras
```

## O que deve e o que não deve coincidir

As sementes são fixas (`1000 + rodada` para os dados, `20260808` para o bootstrap).

| Métrica | Reproduz exatamente? |
|---|---|
| Taxa de sucesso e precisão do mapeamento | Sim, em qualquer máquina |
| Tempo, latência, throughput, CPU | Não, dependem do hardware. A ordem entre as arquiteturas tende a se manter |
| Memória | Não. É o pico de memória residente do processo e satura, então não discrimina as arquiteturas |
| IC95% por bootstrap das métricas de sucesso e precisão | Sim, pois partem de valores determinísticos e de semente fixa |

Para regerar as tabelas da proposta a partir do CSV publicado:

```
python analysis/analise_piloto.py results/resultados_brutos.csv results/tabelas
```

## Correspondência com a proposta

| Arquivo | Conteúdo na proposta |
|---|---|
| `results/tabelas/tabela_5_3_descritiva.csv` | Tabela 5.3 (média, desvio-padrão e mediana por arquitetura) |
| `results/tabelas/friedman.csv` | Teste de Friedman por métrica (Seção 5.2.3) |
| `results/tabelas/tabela_5_4_pareados.csv` | Tabela 5.4 (Wilcoxon com Holm, diferença mediana, IC95%, rank-biserial) |
| `results/tabelas/tabela_5_5_severidade.csv` | Tabela 5.5 (Spearman entre índice da rodada e métrica) |
| `figures/Figura_5.3_desempenho.png` a `Figura_5.7_evolucao.png` | Figuras 5.3 a 5.7 |

## Licença e citação

Código sob licença MIT (ver `LICENSE`). A citação sugerida está em `CITATION.cff`.
