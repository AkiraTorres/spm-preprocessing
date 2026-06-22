"""Matriz de cenarios do experimento.

Cada cenario e uma combinacao fixa das etapas de simplificacao (multilevel,
spell, coalescing_repeating, coalescing_hidden, temporal folding). Como e a
definicao do experimento em si, vive aqui como dado importavel. Os parametros
que mudam a cada execucao (curso, atividade, assignment_id, minsup) vem por flags.
"""

# A ordem importa: o indice define o numero do cenario.
SCENERY_DEFINITIONS = [
    {"path": "0-zero", "multilevel": False, "spell": False, "coalescing_repeating": False, "coalescing_hidden": False, "tf": False},
    {"path": "1-first", "multilevel": True, "spell": False, "coalescing_repeating": True, "coalescing_hidden": True, "tf": False},
    {"path": "2-second", "multilevel": True, "spell": False, "coalescing_repeating": True, "coalescing_hidden": False, "tf": False},
    {"path": "3-third", "multilevel": True, "spell": False, "coalescing_repeating": False, "coalescing_hidden": True, "tf": False},

    {"path": "4-fourth", "multilevel": True, "spell": False, "coalescing_repeating": False, "coalescing_hidden": False, "tf": False},
    {"path": "5-fifth", "multilevel": False, "spell": False, "coalescing_repeating": True, "coalescing_hidden": True, "tf": False},
    {"path": "6-sixth", "multilevel": False, "spell": False, "coalescing_repeating": True, "coalescing_hidden": False, "tf": False},
    {"path": "7-seventh", "multilevel": False, "spell": False, "coalescing_repeating": False, "coalescing_hidden": True, "tf": False},

    {"path": "8-eighth", "multilevel": True, "spell": True, "coalescing_hidden": True, "coalescing_repeating": False, "tf": False},
    {"path": "9-ninth", "multilevel": True, "spell": True, "coalescing_hidden": False, "coalescing_repeating": False, "tf": False},
    {"path": "10-tenth", "multilevel": False, "spell": True, "coalescing_hidden": True, "coalescing_repeating": False, "tf": False},
    {"path": "11-eleventh", "multilevel": False, "spell": True, "coalescing_hidden": False, "coalescing_repeating": False, "tf": False},

    {"path": "12-twelfth", "multilevel": True, "spell": False, "coalescing_repeating": True, "coalescing_hidden": True, "tf": True},
    {"path": "13-thirteenth", "multilevel": True, "spell": False, "coalescing_repeating": True, "coalescing_hidden": False, "tf": True},
    {"path": "14-fourteenth", "multilevel": True, "spell": False, "coalescing_repeating": False, "coalescing_hidden": True, "tf": True},
    {"path": "15-fifteenth", "multilevel": True, "spell": False, "coalescing_repeating": False, "coalescing_hidden": False, "tf": True},

    {"path": "16-sixteenth", "multilevel": False, "spell": False, "coalescing_repeating": True, "coalescing_hidden": True, "tf": True},
    {"path": "17-seventeenth", "multilevel": False, "spell": False, "coalescing_repeating": True, "coalescing_hidden": False, "tf": True},
    {"path": "18-eighteenth", "multilevel": False, "spell": False, "coalescing_repeating": False, "coalescing_hidden": True, "tf": True},
    {"path": "19-nineteenth", "multilevel": False, "spell": False, "coalescing_repeating": False, "coalescing_hidden": False, "tf": True},

    {"path": "20-twentieth", "multilevel": True, "spell": True, "coalescing_hidden": True, "coalescing_repeating": False, "tf": True},
    {"path": "21-twenty_first", "multilevel": True, "spell": True, "coalescing_hidden": False, "coalescing_repeating": False, "tf": True},
    {"path": "22-twenty_second", "multilevel": False, "spell": True, "coalescing_hidden": True, "coalescing_repeating": False, "tf": True},
    {"path": "23-twenty_third", "multilevel": False, "spell": True, "coalescing_hidden": False, "coalescing_repeating": False, "tf": True},
]

SCENERIES_NAMES = [s["path"] for s in SCENERY_DEFINITIONS]
