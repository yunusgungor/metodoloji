"""Tests for hooks/engine/modules/utils.py — path classification helpers."""

import importlib.util
import sys
from pathlib import Path

_HOOKS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_HOOKS))

from modules.utils import is_free, is_code_target, norm_path, rel_to_root, repo_root  # noqa: E402


def test_norm_path_forward_slashes():
    assert norm_path("src\\foo.py") == "src/foo.py"
    assert norm_path("./src/foo.py") == "src/foo.py"
    assert norm_path("C:/x/src.py") == "/x/src.py"  # drive stripped, leading slash kept


def test_is_free_free_zones():
    assert is_free("scratch/explore.py")
    assert is_free("tmp/t.txt")
    assert is_free("docs/README.md")
    assert is_free(".metodoloji/logs/hook-audit.log")
    assert is_free("_bmad/foo.py")
    assert is_free("explore_x.py")


def test_is_free_not_free():
    assert not is_free("src/main.py")
    assert not is_free("lib/engine/core.py")


def test_is_code_target_classification():
    # Code: unknown/executable extensions are code
    assert is_code_target("src/foo.py")
    assert is_code_target("lib/engine.py")
    assert is_code_target("Makefile")
    assert is_code_target("Dockerfile")
    assert is_code_target(".github/workflows/ci.yml")
    # Non-code: data/markup/assets
    assert not is_code_target("README.md")
    assert not is_code_target("data.json")
    assert not is_code_target("config.yaml")
    assert not is_code_target("image.png")
    assert not is_code_target(".gitignore")


def test_rel_to_root():
    assert rel_to_root("C:/proj", "C:/proj/src/x.py") == "src/x.py"
    assert rel_to_root("C:/proj", "src/x.py", "C:/proj") == "src/x.py"


def test_repo_root_env_priority():
    import os
    old = os.environ.pop("CLAUDE_PROJECT_DIR", None)
    os.environ["OPENHANDS_PROJECT_DIR"] = "C:/envroot"
    try:
        assert repo_root({}) == "C:\\envroot"
    finally:
        if old:
            os.environ["CLAUDE_PROJECT_DIR"] = old
        os.environ.pop("OPENHANDS_PROJECT_DIR", None)
