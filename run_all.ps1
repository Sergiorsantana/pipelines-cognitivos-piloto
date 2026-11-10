# Executa o piloto, a verificação, a análise estatística e as figuras (Windows PowerShell).
# Uso, a partir da raiz do repositório, com o ambiente virtual ativo:  .\run_all.ps1
$ErrorActionPreference = "Stop"
python src\run_experiment.py --saida results\novo
python src\verificar_reproducao.py results\resultados_brutos.csv results\novo\resultados_brutos.csv
python analysis\analise_piloto.py results\novo\resultados_brutos.csv results\novo\tabelas
python analysis\graficos.py results\novo\resultados_brutos.csv results\novo\figuras
Write-Host "Concluído. Veja results\novo\"
