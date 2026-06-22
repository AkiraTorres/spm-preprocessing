"""Teste de integração com dados reais.

Só roda quando os CSVs do curso 2060 estão presentes em `data/raw/2060/`
(não versionados). Caso contrário é pulado — assim a suíte de núcleo continua
verde em qualquer clone.
"""
from pathlib import Path

import pandas as pd
import pytest

from spm import metrics, mine, simplify
from spm.sceneries import SCENERY_DEFINITIONS
from spm.simplification import get_dates

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "raw" / "2060"
REQUIRED = [
    "event_mapping.csv",
    "see_course2060_logs_filtered.csv",
    "see_course2060_quiz_list.csv",
    "see_course2060_quiz_grades.csv",
]

pytestmark = pytest.mark.skipif(
    not all((DATA / f).exists() for f in REQUIRED),
    reason="CSVs reais de data/raw/2060 ausentes (dados não versionados)",
)


def test_in_memory_pipeline_on_real_data():
    logs = pd.read_csv(DATA / "see_course2060_logs_filtered.csv", index_col="id")
    mapping = pd.read_csv(DATA / "event_mapping.csv")
    grades = pd.read_csv(DATA / "see_course2060_quiz_grades.csv")
    quiz = pd.read_csv(DATA / "see_course2060_quiz_list.csv")

    assignment_id = 12842   # Atividade 2
    initial_date, final_date = get_dates(quiz, assignment_id)
    scenario = SCENERY_DEFINITIONS[12]   # cenário rápido (temporal folding)

    seqs = simplify(logs, mapping, scenario, assignment_id=assignment_id,
                    initial_date=initial_date, final_date=final_date, grades_df=grades)
    assert seqs, "simplify não produziu sequências"

    patterns = mine(seqs, minsup=0.08)
    final, general = metrics(patterns, seqs, scenery=scenario["path"], minsup=0.08)

    assert final is not None and general is not None
    assert general["scenery"] == "12"
    assert general["total_sequences"] > 0
    # diversidade de Jaccard é uma porcentagem válida
    assert 0.0 <= float(general["jaccard_diversity"]) <= 100.0
