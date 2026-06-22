# SPM Torres — Sequential Pattern Mining sobre logs do Moodle

Projeto de pesquisa que minera sequências frequentes de eventos a partir de
traços de atividade de estudantes (logs do Moodle LMS) e calcula métricas
(suporte, notas, time spans, diversidade de Jaccard) em diferentes cenários.

Dois cursos foram estudados no mestrado (**2060** e **2065**), mas o código é
genérico: cada curso tem várias atividades (inteiros) e 24 cenários nomeados
(`0-zero` … `23-twenty_third`).

O projeto é uma **biblioteca instalável** (`spm`), usável de duas formas:

1. **Importando funções** em Python — inclusive operando sobre os próprios dados
   em memória (`simplify` → `mine` → `metrics`).
2. **Pela CLI** `spm` (subcomandos `simplify` / `mine` / `metrics` / `pipeline`).

> O pipeline recebe **todos os parâmetros por argumentos** (nada de hardcode); a
> matriz de 24 cenários vive numa fonte única (`src/spm/sceneries.py`); e há
> separação entre dados de entrada (`data/raw/`), código (`src/spm/`) e saídas
> geradas (`outputs/`, fora do versionamento).

## Estrutura

```
.
├── src/spm/              # a biblioteca
│   ├── __init__.py       # API pública (simplify, mine, metrics, run_*)
│   ├── simplification.py # NÚCLEO: transforms + simplify() (pré-processamento)
│   ├── mining.py         # NÚCLEO: mine() (PrefixSpan)
│   ├── metrics.py        # NÚCLEO: metrics() (Jaccard, suportes, notas)
│   ├── io.py             # leitura/escrita JSON/CSV e relatórios consolidados
│   ├── pipeline.py       # orquestradores file-based: run_simplification/mining/metrics + run_pipeline
│   ├── cli.py            # comando `spm` (argparse, subcomandos)
│   ├── sceneries.py      # FONTE ÚNICA: matriz dos 24 cenários (SCENERY_DEFINITIONS)
│   ├── config.py         # legado: knobs usados só por scripts/mining.py e viz/*
│   └── paths.py          # esquema de diretórios (data/raw, outputs/)
├── scripts/              # scripts legados (NÃO fazem parte da lib)
│   ├── mining.py, order.py, scenario_metrics.py, support_percentage.py
│   └── viz/              # gráficos (analysis, plot_patterns, comparison_boxplots)
├── configs/              # parâmetros por experimento (course_2060.yaml, course_2065.yaml)
├── data/raw/{course}/    # CSVs crus do Moodle (NÃO versionados — ver data/README.md)
├── outputs/              # tudo gerado (no .gitignore)
│   ├── sceneries/{course}/{activity}/
│   ├── mining_results/{course}/{activity}/
│   ├── results/{course}/{activity}/{json,csv}/
│   └── figures/
├── notebooks/            # exploração (.ipynb, no .gitignore)
├── docs/                 # CODE_ORGANIZATION, JACCARD_METRICS, OPTIMIZATIONS (no .gitignore)
├── pyproject.toml        # empacotamento + entry point `spm`
└── requirements.txt
```

## Instalação

```bash
pip install -e .            # instala a lib + o comando `spm`
pip install -e ".[viz]"     # opcional: extras p/ os scripts de gráficos legados
pip install -e ".[gsp]"     # opcional: algoritmo GSP (spm.mining.gsp_mining)
```

Dependências de runtime: `pandas`, `numpy`, `prefixspan`. `matplotlib`/`seaborn`
(extra `viz`) e `gsppy` (extra `gsp`) são opcionais.

## Uso como biblioteca (Python)

A API de **núcleo** opera em memória — você passa os próprios dados e recebe os
resultados de volta, encadeando as etapas:

```python
import pandas as pd
from spm import simplify, mine, metrics, SCENERY_DEFINITIONS

logs    = pd.read_csv("data/raw/2060/see_course2060_logs_filtered.csv", index_col="id")
mapping = pd.read_csv("data/raw/2060/event_mapping.csv")
grades  = pd.read_csv("data/raw/2060/see_course2060_quiz_grades.csv")

scenario = SCENERY_DEFINITIONS[1]                       # flags do cenário "1-first"
seqs = simplify(logs, mapping, scenario,                # -> sequências por usuário
                assignment_id=12842,
                initial_date=1574132400, final_date=1574823300,
                grades_df=grades)
patterns       = mine(seqs, minsup=0.08)                # -> padrões frequentes
final, general = metrics(patterns, seqs, minsup=0.08)   # -> métricas do cenário
```

> As datas (`t_open`/`t_close`) podem ser derivadas do quiz CSV com
> `spm.simplification.get_dates(quiz_df, assignment_id)`.

Para reproduzir o experimento completo a partir dos arquivos (lê `data/raw/`,
escreve `outputs/`), use os **orquestradores**:

```python
from spm import run_pipeline   # ou run_simplification / run_mining / run_metrics
run_pipeline(course=2060, activity=2, total_sequences=11974)
```

## Uso pela CLI (`spm`)

O comando `spm` assume a **raiz do repositório** como diretório de trabalho
(os caminhos de entrada/saída são relativos a ela). O `assignment_id` é derivado
de `(curso, atividade)`; sobrescreva com `--assignment-id` se precisar.

```bash
# Pipeline completo (as 3 etapas em sequência)
spm pipeline --course 2060 --activity 2 --total-sequences 11974

# Ou etapa por etapa:
spm simplify --course 2060 --activity 2 --assignment-id 12842
spm mine     --course 2060 --activity 2 --minsup 0.08
spm metrics  --course 2060 --activity 2 --minsup 0.08 --total-sequences 11974
```

Flags úteis: `--minsup`, `--use-split` (variantes `_high`/`_low` por nota) e
`--*-dir` para mudar as raízes de entrada/saída. Veja `spm <subcomando> --help`.

## Configuração

- A **matriz dos 24 cenários** (combinações de `multilevel`/`spell`/
  `coalescing_repeating`/`coalescing_hidden`/`tf`) é definição fixa do
  experimento e vive numa fonte única: `src/spm/sceneries.py`
  (`SCENERY_DEFINITIONS`). Edite ali apenas se quiser mudar os cenários em si.
- O mapa `(curso, atividade) -> assignment_id` fica em
  `spm.pipeline.ASSIGNMENT_IDS`.
- `src/spm/config.py` permanece apenas como **legado** para os scripts fora da
  biblioteca (`scripts/mining.py`, `scripts/viz/*`), que ainda o importam.
- Os YAMLs em `configs/` documentam os parâmetros de cada execução.

## Dados

Os CSVs crus não são versionados (podem conter dados de estudantes). Veja
`data/README.md` para onde colocá-los.
