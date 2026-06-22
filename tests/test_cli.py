"""Testes do parser da CLI e da resolução de parâmetros do pipeline."""
import pytest

from spm.cli import build_parser
from spm.pipeline import _expand_sceneries, resolve_assignment_id
from spm.sceneries import SCENERIES_NAMES


def test_parser_pipeline_defaults():
    args = build_parser().parse_args(["pipeline", "--course", "2060", "--activity", "2"])
    assert args.command == "pipeline"
    assert args.course == 2060
    assert args.activity == 2
    assert args.minsup == 0.08
    assert args.total_sequences == 11974.0
    assert args.use_split is False
    assert args.assignment_id is None


def test_parser_subcommands_exist():
    for cmd in ("simplify", "mine", "metrics", "pipeline"):
        args = build_parser().parse_args([cmd, "-co", "2065", "-act", "1"])
        assert args.command == cmd


def test_parser_requires_subcommand():
    with pytest.raises(SystemExit):
        build_parser().parse_args([])


def test_resolve_assignment_id_from_map():
    assert resolve_assignment_id(2060, 1) == 12841
    assert resolve_assignment_id(2060, 2) == 12842
    assert resolve_assignment_id(2065, 1) == 12874


def test_resolve_assignment_id_explicit_override():
    assert resolve_assignment_id(2060, 2, 55555) == 55555


def test_resolve_assignment_id_unknown_course_raises():
    with pytest.raises(ValueError):
        resolve_assignment_id(1234, 1)


def test_resolve_assignment_id_out_of_range_raises():
    with pytest.raises(ValueError):
        resolve_assignment_id(2060, 99)


def test_expand_sceneries():
    assert _expand_sceneries(False) == list(SCENERIES_NAMES)
    split = _expand_sceneries(True)
    assert len(split) == 2 * len(SCENERIES_NAMES)
    assert split[0].endswith("_high")
    assert split[1].endswith("_low")
