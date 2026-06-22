"""Configuracao legada do projeto.

Os scripts do pipeline principal (``simplification.py``, ``process_mining.py``,
``metrics_calculation.py``) NAO usam mais este modulo: eles recebem todos os
parametros de execucao por flags de linha de comando (ver ``--help`` de cada um
ou ``scripts/run_pipeline.py``).

Os valores abaixo permanecem apenas para os scripts ainda nao migrados
(``mining.py``, ``scripts/viz/*``). A matriz de cenarios e importada de
``spm.sceneries`` (fonte unica) — nao a duplique aqui.
"""

from spm.sceneries import SCENERIES_NAMES  # noqa: F401  (re-export p/ scripts legados)

# ---------------------------------------------------------------------------
# Parametros de execucao — LEGADO (apenas mining.py / viz/*)
# Os scripts do pipeline principal recebem isto por flags.
# ---------------------------------------------------------------------------
COURSE = 2060          # 2060 ou 2065
ACTIVITY = 2           # numero da atividade (inteiro)
USE_SPLIT = False      # se True, gera variantes _high/_low por nota
MINSUP = 0.08          # suporte minimo do PrefixSpan
TOTAL_SEQUENCES = 11974  # total de referencia para normalizacao de %
