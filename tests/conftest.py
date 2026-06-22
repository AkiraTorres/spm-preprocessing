"""Fixtures compartilhadas: dados sintéticos pequenos e determinísticos.

Os testes de núcleo não dependem de `data/raw/` (que não é versionado): usam
estes dados em memória. Há também um marcador para testes de integração que só
rodam quando os CSVs reais estão presentes.
"""
import pandas as pd
import pytest


@pytest.fixture
def mapping_df():
    """Mapeamento mínimo (component, action, target) -> class."""
    return pd.DataFrame(
        [
            {"component": "mod_quiz", "action": "viewed", "target": "course_module", "class": "assignment_vis"},
            {"component": "mod_quiz", "action": "started", "target": "attempt", "class": "assignment_try"},
            {"component": "mod_quiz", "action": "submitted", "target": "attempt", "class": "assignment_sub"},
            {"component": "core", "action": "viewed", "target": "course", "class": "course_vis"},
        ]
    )


@pytest.fixture
def quiz_df():
    """Catálogo de atividades mínimo (datas por assignment_id)."""
    return pd.DataFrame(
        [
            {"id": 999, "course_id": 1, "name": "Atividade X", "t_open": 1000, "t_close": 9000},
        ]
    )


@pytest.fixture
def sequences():
    """Lista de sequências por usuário (formato `events_by_user`).

    Quatro usuários; o padrão ["a", "b"] aparece em três deles.
    """
    def user(key, names):
        events = [{"event": n, "time": i + 1} for i, n in enumerate(names)]
        return {
            "key": key,
            "temporal_folding": False,
            "grade": 2.0,
            "max_grade": 2.0,
            "events": [events],
        }

    return [
        user("1", ["a", "b", "c"]),
        user("2", ["a", "b"]),
        user("3", ["a", "b", "d"]),
        user("4", ["x", "y"]),
    ]
