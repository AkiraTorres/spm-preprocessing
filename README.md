# SPM Torres — Sequential Pattern Mining sobre logs do Moodle

Projeto de pesquisa que minera sequências frequentes de eventos a partir de
traços de atividade de estudantes (logs do Moodle LMS) e calcula métricas
(suporte, notas, time spans, diversidade de Jaccard) em diferentes cenários.

Dois cursos são estudados: **2060** e **2065**, cada um com várias atividades
(inteiros) e até 24 cenários nomeados (`0-zero` … `23-twenty_third`).

> Esta é a versão **reorganizada** do projeto. O código é o mesmo dos scripts
> originais, com duas mudanças estruturais: (1) configuração centralizada em
> `src/spm/config.py` e (2) separação entre dados de entrada (`data/raw/`),
> código (`src/`, `scripts/`) e saídas geradas (`outputs/`, fora do versionamento).

## Estrutura

```
.
├── src/spm/              # pacote compartilhado
│   ├── config.py         # FONTE ÚNICA: cenários + COURSE/ACTIVITY/USE_SPLIT/MINSUP
│   └── paths.py          # esquema de diretórios (data/raw, outputs/)
├── scripts/              # scripts executáveis do pipeline (rodar da raiz)
│   ├── simplification.py
│   ├── process_mining.py
│   ├── mining.py
│   ├── metrics_calculation.py
│   ├── order.py
│   ├── support_percentage.py / percentagesupport.py
│   ├── scenario_metrics.py
│   └── viz/              # gráficos (analysis, plot_patterns, comparison_boxplots)
├── configs/              # parâmetros por experimento (course_2060.yaml, course_2065.yaml)
├── data/raw/{course}/    # CSVs crus do Moodle (NÃO versionados — ver data/README.md)
├── outputs/              # tudo gerado (no .gitignore)
│   ├── sceneries/{course}/{activity}/
│   ├── mining_results/{course}/{activity}/
│   ├── results/{course}/{activity}/{json,csv}/
│   └── figures/
├── notebooks/            # exploração (.ipynb)
├── docs/                 # CODE_ORGANIZATION, JACCARD_METRICS, OPTIMIZATIONS
├── tests/
├── pyproject.toml
└── requirements.txt
```

## Configuração

Antes, a lista de cenários e os parâmetros estavam duplicados no topo de cada
script. Agora edite **um único arquivo**: `src/spm/config.py`
(`COURSE`, `ACTIVITY`, `USE_SPLIT`, `MINSUP`, `SCENERIES_NAMES`). Os YAMLs em
`configs/` documentam os parâmetros de cada execução.

## Instalação

```bash
pip install -r requirements.txt
# ou, para usar o pacote instalável:
pip install -e .
```

## Como rodar

Os scripts assumem a **raiz do repositório** como diretório de trabalho
(os caminhos de entrada/saída são relativos a ela).

```bash
# 1. Pré-processa logs crus -> outputs/sceneries/{course}/{activity}/
python scripts/simplification.py

# 2a. Mineração apenas -> outputs/mining_results/{course}/{activity}/
python scripts/process_mining.py
# 2b. Mineração + métricas completas -> outputs/results/{course}/{activity}/
python scripts/mining.py

# 3. Métricas de Jaccard a partir dos resultados minerados
python scripts/metrics_calculation.py

# Utilitário: estatísticas de comprimento de sequência
python scripts/scenario_metrics.py ./outputs/sceneries/2060/1/

# Visualizações
python scripts/viz/analysis.py
python scripts/viz/plot_patterns.py
```

## Dados

Os CSVs crus não são versionados (podem conter dados de estudantes). Veja
`data/README.md` para onde colocá-los.
