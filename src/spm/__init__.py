"""Sequential Pattern Mining (SPM) sobre logs do Moodle.

Biblioteca para minerar sequências frequentes de eventos a partir de traços de
atividade de estudantes e calcular métricas (suporte, notas, time spans,
diversidade de Jaccard) em diferentes cenários de simplificação.

Uso em memória (compõe as etapas com os próprios dados)::

    import pandas as pd
    from spm import simplify, mine, metrics, SCENERY_DEFINITIONS

    seqs = simplify(logs_df, mapping_df, SCENERY_DEFINITIONS[1],
                    assignment_id=12842, initial_date=..., final_date=...)
    pats = mine(seqs, minsup=0.08)
    final, info = metrics(pats, seqs, minsup=0.08)

Uso baseado em arquivos (equivalente à CLI ``spm``)::

    from spm import run_pipeline
    run_pipeline(course=2060, activity=2, total_sequences=11974)
"""
from . import config, paths
from .metrics import metrics
from .mining import mine
from .pipeline import run_metrics, run_mining, run_pipeline, run_simplification
from .sceneries import SCENERY_DEFINITIONS, SCENERIES_NAMES
from .simplification import simplify

__all__ = [
    # núcleo em memória
    "simplify",
    "mine",
    "metrics",
    # orquestradores baseados em arquivos
    "run_simplification",
    "run_mining",
    "run_metrics",
    "run_pipeline",
    # matriz de cenários
    "SCENERY_DEFINITIONS",
    "SCENERIES_NAMES",
    # submódulos legados
    "config",
    "paths",
]
