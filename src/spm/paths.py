"""Helpers de caminho do projeto.

Centraliza o esquema de diretorios. Entradas (CSVs crus) ficam em ``data/raw/``
e tudo que e gerado vai para ``outputs/`` (que esta no .gitignore).

Os caminhos sao relativos a raiz do repositorio — os scripts continuam sendo
executados a partir da raiz, como na versao original.

Esquema:
    data/raw/{course}/                       <- CSVs crus do Moodle
    outputs/sceneries/{course}/{activity}/   <- JSONs por cenario (pre-processado)
    outputs/mining_results/{course}/{activity}/
    outputs/results/{course}/{activity}/     <- metricas (json/ e csv/)
    outputs/figures/                         <- PNGs, boxplots, PDFs
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

DATA_DIR = ROOT / "data" / "raw"
OUTPUTS_DIR = ROOT / "outputs"


def raw(course) -> str:
    return f"data/raw/{course}"


def sceneries(course, activity) -> str:
    return f"outputs/sceneries/{course}/{activity}"


def mining(course, activity) -> str:
    return f"outputs/mining_results/{course}/{activity}"


def results(course, activity) -> str:
    return f"outputs/results/{course}/{activity}"


def figures() -> str:
    return "outputs/figures"
