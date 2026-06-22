# SPM Torres — Sequential Pattern Mining sobre logs do Moodle

Projeto de pesquisa que minera sequências frequentes de eventos a partir de
traços de atividade de estudantes (logs do Moodle LMS) e calcula métricas
(suporte, notas, time spans, diversidade de Jaccard) em diferentes cenários.

Dois cursos são estudados: **2060** e **2065**, cada um com várias atividades
(inteiros) e até 24 cenários nomeados (`0-zero` … `23-twenty_third`).

> Esta é a versão **reorganizada** do projeto. O código é o mesmo dos scripts
> originais, com três mudanças estruturais: (1) o pipeline principal recebe
> **todos os parâmetros por flags de CLI** (nada de hardcode); (2) a matriz de
> 24 cenários vive numa fonte única, `src/spm/sceneries.py`; e (3) separação
> entre dados de entrada (`data/raw/`), código (`src/`, `scripts/`) e saídas
> geradas (`outputs/`, fora do versionamento).

## Estrutura

```
.
├── src/spm/              # pacote compartilhado
│   ├── sceneries.py      # FONTE ÚNICA: matriz dos 24 cenários (SCENERY_DEFINITIONS)
│   ├── config.py         # legado: knobs usados só por mining.py e viz/*
│   └── paths.py          # esquema de diretórios (data/raw, outputs/)
├── scripts/              # scripts executáveis do pipeline (rodar da raiz)
│   ├── run_pipeline.py   # driver: roda e valida as 3 etapas via flags (fail-fast)
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
├── notebooks/            # exploração (.ipynb, no .gitignore)
├── docs/                 # CODE_ORGANIZATION, JACCARD_METRICS, OPTIMIZATIONS (no .gitignore)
├── pyproject.toml
└── requirements.txt
```

## Configuração

O pipeline principal **não tem mais nada hardcoded**: curso, atividade,
`assignment_id`, `minsup`, `total_sequences` e caminhos são passados por **flags
de CLI** (veja `--help` de cada script). Não é preciso editar nenhum arquivo
para trocar de curso/atividade.

- A **matriz dos 24 cenários** (combinações de `multilevel`/`spell`/
  `coalescing_repeating`/`coalescing_hidden`/`tf`) é definição fixa do
  experimento e vive numa fonte única: `src/spm/sceneries.py`
  (`SCENERY_DEFINITIONS`). Edite ali apenas se quiser mudar os cenários em si.
- As **datas** de cada atividade (`t_open`/`t_close`) são derivadas
  automaticamente do CSV de quizzes a partir do `assignment_id` — não são mais
  digitadas.
- `src/spm/config.py` permanece apenas como **legado** para os scripts fora do
  pipeline principal (`mining.py`, `viz/*`), que ainda o importam.
- Os YAMLs em `configs/` documentam os parâmetros de cada execução.

## Instalação

```bash
pip install -r requirements.txt
# ou, para usar o pacote instalável:
pip install -e .
```

## Como rodar

Os scripts assumem a **raiz do repositório** como diretório de trabalho
(os caminhos de entrada/saída são relativos a ela).

### Pipeline completo (recomendado)

`scripts/run_pipeline.py` roda as 3 etapas em sequência, passando tudo por flags
e validando a saída de cada etapa antes da próxima (fail-fast). O `assignment_id`
é derivado de `(curso, atividade)` por um mapa interno; sobrescreva com
`--assignment-id` se precisar.

```bash
# Curso 2060, atividade 2 (assignment_id derivado automaticamente)
python scripts/run_pipeline.py --course 2060 --activity 2 --total-sequences 11974

# Outras flags: --minsup 0.1, --use-split, --assignment-id 12842,
#               --python /caminho/para/python
```

### Etapas individuais

Cada etapa também roda sozinha (veja `--help`):

```bash
# 1. Pré-processa logs crus -> outputs/sceneries/{course}/{activity}/
python scripts/simplification.py --course 2060 --activity 2 --assignment-id 12842

# 2. Mineração PrefixSpan -> outputs/mining_results/{course}/{activity}/
python scripts/process_mining.py --course 2060 --activity 2 --minsup 0.08

# 3. Métricas (Jaccard, suportes, notas) -> outputs/results/{course}/{activity}/
python scripts/metrics_calculation.py --course 2060 --activity 2 \
    --minsup 0.08 --total-sequences 11974

# Utilitário: estatísticas de comprimento de sequência
python scripts/scenario_metrics.py ./outputs/sceneries/2060/2/

# Visualizações (scripts legados — ainda usam src/spm/config.py)
python scripts/viz/analysis.py
python scripts/viz/plot_patterns.py
```

## Dados

Os CSVs crus não são versionados (podem conter dados de estudantes). Veja
`data/README.md` para onde colocá-los.
