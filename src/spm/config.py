"""Configuracao legada.

Mantido apenas para os scripts ainda nao migrados (``scripts/mining.py``,
``scripts/viz/*``). A biblioteca recebe estes parametros por argumento; a matriz
de cenarios e importada de ``spm.sceneries``.
"""

from spm.sceneries import SCENERIES_NAMES  # noqa: F401  (re-export p/ scripts legados)

COURSE = 2060
ACTIVITY = 2
USE_SPLIT = False
MINSUP = 0.08
TOTAL_SEQUENCES = 11974
