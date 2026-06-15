"""Configuracao central do projeto.

Antes da reorganizacao, a lista ``sceneries_names`` e os parametros
``COURSE`` / ``activity`` / ``use_split`` / ``minsup`` estavam duplicados no
topo de cada script. Agora existe uma unica fonte de verdade: edite os valores
aqui (ou via os YAMLs em ``configs/``) em vez de editar cada arquivo.

Os scripts importam estes nomes, por exemplo::

    from spm.config import SCENERIES_NAMES, COURSE, ACTIVITY, USE_SPLIT, MINSUP
"""

# ---------------------------------------------------------------------------
# Cenarios (fonte unica — antes copiada em 5 arquivos)
# ---------------------------------------------------------------------------
SCENERIES_NAMES = [
    "0-zero",
    "1-first",
    "2-second",
    "3-third",
    "4-fourth",
    "5-fifth",
    "6-sixth",
    "7-seventh",
    "8-eighth",
    "9-ninth",
    "10-tenth",
    "11-eleventh",
    "12-twelfth",
    "13-thirteenth",
    "14-fourteenth",
    "15-fifteenth",
    "16-sixteenth",
    "17-seventeenth",
    "18-eighteenth",
    "19-nineteenth",
    "20-twentieth",
    "21-twenty_first",
    "22-twenty_second",
    "23-twenty_third",
    # "24-twenty_fourth",
]

# ---------------------------------------------------------------------------
# Parametros do experimento (knobs por execucao)
# ---------------------------------------------------------------------------
COURSE = 2060          # 2060 ou 2065
ACTIVITY = 2           # numero da atividade (inteiro)
USE_SPLIT = False      # se True, gera variantes _high/_low por nota
MINSUP = 0.08          # suporte minimo do PrefixSpan
TOTAL_SEQUENCES = 11974  # total de referencia para normalizacao de %
