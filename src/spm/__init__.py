"""Pacote do projeto de Sequential Pattern Mining (SPM) sobre logs do Moodle.

Reune a configuracao compartilhada (cenarios, parametros) e os helpers de
caminho usados pelos scripts em ``scripts/``.
"""

from . import config, paths

__all__ = ["config", "paths"]
