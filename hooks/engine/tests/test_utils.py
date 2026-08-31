"""Tests for hooks/engine/modules/utils.py — path classification helpers."""

import importlib.util
import sys
from pathlib import Path

_HOOKS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_HOOKS))

from modules.utils import (  # noqa: E402
    extract_story_key_from_content,
    is_code_target,
    is_free,
    norm_path,
    rel_to_root,
    repo_root,
)


def test_norm_path_forward_slashes():
    assert norm_path("src\\foo.py") == "src/foo.py"
    assert norm_path("./src/foo.py") == "src/foo.py"
    assert norm_path("C:/x/src.py") == "/x/src.py"  # drive stripped, leading slash kept


def test_norm_path_repeated_dots():
    assert norm_path("././src/x.py") == "src/x.py"
    assert norm_path("") == ""


def test_norm_path_drive_variants():
    assert norm_path("c:/x.py") == "/x.py"
    assert norm_path("C:\\x\\y.py") == "/x/y.py"


def test_is_free_free_zones():
    assert is_free("scratch/explore.py")
    assert is_free("tmp/t.txt")
    assert is_free("docs/README.md")
    assert is_free(".metodoloji/logs/hook-audit.log")
    assert is_free("_bmad/foo.py")
    assert is_free("explore_x.py")


def test_is_free_docs_raw():
    assert is_free("docs/code-docs/decisions/D-001-x.md")
    assert is_free("docs/foo/raw/data.json")


def test_is_free_infra_files():
    assert is_free("scripts/check-methodology.sh")
    assert is_free("skills/bmad-research-experiment/scripts/run_experiment.py")


def test_is_free_empty():
    assert is_free("") is True
    assert is_free("/") is True


def test_is_free_not_free():
    assert not is_free("src/main.py")
    assert not is_free("lib/engine/core.py")
    # Anything starting with explore_ is free (even a plain name).
    assert is_free("explore_main.py")


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


def test_is_code_target_code_dirs():
    assert is_code_target("src/deep/file.py")
    assert is_code_target("lib/helper.ts")
    assert is_code_target("tools/build.py")
    assert is_code_target("core/x.go")
    assert is_code_target("app/main.py")


def test_is_code_target_dev_null():
    assert not is_code_target("dev/null")
    assert not is_code_target("dev/null/x")


def test_is_code_target_exec_config():
    assert is_code_target(".github/workflows/ci.yml")
    assert is_code_target("docker-compose.yml")
    assert is_code_target("package.json")


def test_rel_to_root():
    assert rel_to_root("C:/proj", "C:/proj/src/x.py") == "src/x.py"
    assert rel_to_root("C:/proj", "src/x.py", "C:/proj") == "src/x.py"


def test_rel_to_root_outside_root_kept_abs():
    # A path outside the root stays as-is (normalized, not truncated).
    assert rel_to_root("C:/proj", "C:/other/x.py") == "/other/x.py"


def test_rel_to_root_empty():
    assert rel_to_root("C:/proj", "") == ""
    assert rel_to_root("C:/proj", None) == ""


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


def test_repo_root_json_cwd_fallback():
    import os
    old_c = os.environ.pop("CLAUDE_PROJECT_DIR", None)
    old_o = os.environ.pop("OPENHANDS_PROJECT_DIR", None)
    try:
        assert repo_root({"cwd": "C:/from-json"}) == "C:\\from-json"
    finally:
        if old_c:
            os.environ["CLAUDE_PROJECT_DIR"] = old_c
        if old_o:
            os.environ["OPENHANDS_PROJECT_DIR"] = old_o


def test_extract_story_key_colon():
    assert extract_story_key_from_content("# Story: S-001\n") == "S-001"


def test_extract_story_key_space():
    assert extract_story_key_from_content("# Story S-001\n") == "S-001"


def test_extract_story_key_no_match():
    assert extract_story_key_from_content("## Title\nbody") == ""
