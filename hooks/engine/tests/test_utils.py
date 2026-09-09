"""Tests for hooks/engine/modules/utils.py — path classification helpers."""

import importlib.util
import sys
from pathlib import Path

_HOOKS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_HOOKS))

from modules.utils import (  # noqa: E402
    rel_to_root,
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


def test_plugin_trees_protected_in_ordinary_project(monkeypatch, tmp_path):
    """hooks/, scripts/, skills/, bmad_benchmarks/ are plugin source trees.
    When the project root is NOT the methodology root, they are NOT free —
    the experiment gate applies."""
    from modules import config, utils
    monkeypatch.setattr(config, "_METHODOLOGY_ROOT", tmp_path)
    monkeypatch.setattr(utils, "repo_root", lambda json_in: str(tmp_path / "user-project"))
    assert not is_free("scripts/tool.py")
    assert not is_free("hooks/engine/main.py")
    assert not is_free("skills/bmad-dev-story/SKILL.md")
    assert not is_free("bmad_benchmarks/envs/x/adapter.py")


def test_plugin_trees_free_when_project_is_methodology_root(monkeypatch, tmp_path):
    """Self-modification: when the project root IS the methodology root,
    plugin source trees are released without experiment approval."""
    from modules import config, utils
    monkeypatch.setattr(config, "_METHODOLOGY_ROOT", tmp_path)
    monkeypatch.setattr(utils, "repo_root", lambda json_in: str(tmp_path))
    assert is_free("scripts/tool.py")
    assert is_free("hooks/engine/main.py")
    assert is_free("skills/bmad-dev-story/SKILL.md")
    assert is_free("bmad_benchmarks/envs/x/adapter.py")
    assert is_free("custom/bmad-dev-story.toml")


def test_plugin_trees_protected_when_no_project_env(monkeypatch, tmp_path):
    """Fail-closed default: with no project-root env, plugin trees stay protected
    (the check must not silently release them)."""
    from modules import config, utils
    monkeypatch.setattr(config, "_METHODOLOGY_ROOT", tmp_path)
    # repo_root falls back to os.getcwd() — pin it away from the methodology root.
    monkeypatch.setattr(utils, "repo_root", lambda json_in: "/somewhere/else")
    assert not is_free("scripts/tool.py")
    assert not is_free("skills/anything.py")


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


def test_norm_path_dotdot_and_slashes():
    assert norm_path("src//a.py") == "src/a.py"
    assert norm_path("scratch/../src/x.py") == "src/x.py"
    assert norm_path("  src/x.py  ") == "src/x.py"
    assert norm_path("C:\\x\\y.py") == "/x/y.py"


def test_rel_to_root_sibling_prefix_not_stripped():
    # /repo-evil/x under root /repo must NOT rebase as repo-internal.
    assert rel_to_root("/repo", "/repo-evil/x.py") == "/repo-evil/x.py"
    assert rel_to_root("/repo", "/repo/src/x.py") == "src/x.py"


def test_normalize_notebook_edit():
    from modules.utils import normalize_hook_input
    norm = normalize_hook_input({"tool_name": "NotebookEdit",
                                 "tool_input": {"file_path": "nb/x.ipynb"}})
    assert norm["tool_name"] == "notebook_editor"
    assert norm["tool_input"]["path"] == "nb/x.ipynb"


def test_normalize_unknown_tool_flagged():
    from modules.utils import normalize_hook_input
    norm = normalize_hook_input({"tool_name": "FutureTool",
                                 "tool_input": {}})
    assert norm["tool_name"] == "unknown"
    assert norm["raw_tool_name"] == "FutureTool"


def test_is_code_target_src_md_not_code():
    # CODE_DIRS shortcut must not promote data files: src/*.md is docs.
    assert not is_code_target("src/README.md")
    assert not is_code_target("SRC/notes.md")
    assert not is_code_target("Src/data.json")


def test_is_code_target_toolchain_config_not_code():
    # Brownfield false-block class: bundler/ORM/TS configs are not app code.
    assert not is_code_target("prisma.config.ts")
    assert not is_code_target("backend/prisma.config.ts")
    assert not is_code_target("vite.config.ts")
    assert not is_code_target("tsconfig.json")
    assert not is_code_target("tsconfig.node.json")
    assert not is_code_target("package-lock.json")
    # Real code still gated, even next to configs.
    assert is_code_target("src/main.py")
    assert is_code_target("prisma/schema-helper.py")


def test_rel_to_root():
    assert rel_to_root("C:/proj", "C:/proj/src/x.py") == "src/x.py"
    assert rel_to_root("C:/proj", "src/x.py", "C:/proj") == "src/x.py"


def test_rel_to_root_outside_root_kept_abs():
    # A path outside the root stays as-is (normalized, not truncated).
    assert rel_to_root("C:/proj", "C:/other/x.py") == "/other/x.py"


def test_rel_to_root_empty():
    assert rel_to_root("C:/proj", "") == ""
    assert rel_to_root("C:/proj", None) == ""


def test_repo_root_env_priority(tmp_path):
    import os
    old = os.environ.pop("CLAUDE_PROJECT_DIR", None)
    envroot = str(tmp_path / "envroot")  # absolute on this platform
    os.environ["OPENHANDS_PROJECT_DIR"] = envroot
    try:
        assert repo_root({}) == os.path.abspath(envroot)
    finally:
        if old:
            os.environ["CLAUDE_PROJECT_DIR"] = old
        os.environ.pop("OPENHANDS_PROJECT_DIR", None)


def test_repo_root_json_cwd_fallback(tmp_path):
    import os
    old_c = os.environ.pop("CLAUDE_PROJECT_DIR", None)
    old_o = os.environ.pop("OPENHANDS_PROJECT_DIR", None)
    try:
        cwd = str(tmp_path / "from-json")  # absolute on this platform
        assert repo_root({"cwd": cwd}) == os.path.abspath(cwd)
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


# END — intent bridge tests removed
