"""Tests for bmad/scripts/resolve_config.py.

Run standalone: python3 -m pytest bmad/tests/test_resolve_config.py -q
Also registered under scripts/tests in pyproject.toml via this sibling path.
"""

import importlib.util
import json
import shutil
import sys
from pathlib import Path

import pytest

_SCRIPT = (
    Path(__file__).resolve().parent.parent.parent
    / "bmad" / "scripts" / "resolve_config.py"
)
_spec = importlib.util.spec_from_file_location("resolve_config", _SCRIPT)
rc = importlib.util.module_from_spec(_spec)
sys.modules.setdefault("resolve_config", rc)
_spec.loader.exec_module(rc)


def _write_toml(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_yaml(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


@pytest.fixture
def plugin(tmp_path):
    """A minimal fake plugin root with the required base config."""
    root = tmp_path / "plugin"
    _write_toml(
        root / "bmad" / "config.toml",
        """
[core]
project_name = "base-project"
output_folder = "{project-root}/bmad-output"
document_output_language = "English"

[modules.tea]
risk_threshold = "p1"
test_stack_type = "auto"

[agents]
""",
    )
    # The resolver locates the plugin layers relative to its own path — copy it in.
    dest = root / "bmad" / "scripts"
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copy(_SCRIPT, dest / "resolve_config.py")
    return root


def _make_project(tmp_path: Path) -> Path:
    return tmp_path / "project"


def _run(plugin_root: Path, project_root: Path, *extra: str) -> dict:
    import subprocess

    cmd = [
        sys.executable, str(plugin_root / "bmad" / "scripts" / "resolve_config.py"),
        "--project-root", str(project_root), *extra,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


# ── Legacy YAML parser ───────────────────────────────────────────────

def test_parse_legacy_yaml_scalars_and_lists(tmp_path):
    f = tmp_path / "config.yaml"
    _write_yaml(f, """
# comment
test_artifacts: "{project-root}/bmad-output/test-artifacts"
tea_use_playwright_utils: true
tea_use_pactjs_utils: false
risk_threshold: p1
count: 3
ratio: 1.5
product_languages:
  - en
  - tr
empty_list:
""")
    data = rc.load_legacy_yaml(f)
    assert data["test_artifacts"] == "{project-root}/bmad-output/test-artifacts"
    assert data["tea_use_playwright_utils"] is True
    assert data["tea_use_pactjs_utils"] is False
    assert data["risk_threshold"] == "p1"
    assert data["count"] == 3
    assert data["ratio"] == 1.5
    assert data["product_languages"] == ["en", "tr"]
    assert data["empty_list"] == []


def test_parse_legacy_yaml_with_bom(tmp_path):
    f = tmp_path / "config.yaml"
    _write_yaml(f, "\ufeffuser_name: BOMUser\nrisk_threshold: p2\n")
    data = rc.load_legacy_yaml(f)
    assert data == {"user_name": "BOMUser", "risk_threshold": "p2"}


def test_split_legacy_core():
    data = {
        "user_name": "Yunus",
        "output_folder": "{project-root}/bmad-output",
        "risk_threshold": "p1",
    }
    core, module = rc._split_legacy_core(data)
    assert core == {"user_name": "Yunus", "output_folder": "{project-root}/bmad-output"}
    assert module == {"risk_threshold": "p1"}


# ── Legacy bridge behavior ───────────────────────────────────────────

def test_legacy_yaml_overrides_plugin_default(plugin, tmp_path):
    project = _make_project(tmp_path)
    # A project-root legacy config.yaml is a PROJECT setting: it must beat the
    # plugin's installer defaults even though it is YAML and they are TOML.
    _write_yaml(
        project / "bmad" / "tea" / "config.yaml",
        "risk_threshold: p0\ntest_stack_type: playwright\n",
    )
    out = _run(plugin, project, "--key", "modules.tea.risk_threshold")
    assert out == {"modules.tea.risk_threshold": "p0"}


def test_project_toml_beats_legacy_yaml(plugin, tmp_path):
    project = _make_project(tmp_path)
    _write_yaml(project / "bmad" / "tea" / "config.yaml", "risk_threshold: p0\n")
    _write_toml(project / "bmad" / "config.toml", '[modules.tea]\nrisk_threshold = "p2"\n')
    out = _run(plugin, project, "--key", "modules.tea.risk_threshold")
    assert out == {"modules.tea.risk_threshold": "p2"}


def test_legacy_yaml_and_plugin_toml_deep_merge(plugin, tmp_path):
    project = _make_project(tmp_path)
    # YAML overrides one key; the other plugin key survives.
    _write_yaml(project / "bmad" / "tea" / "config.yaml", "risk_threshold: p0\n")
    out = _run(plugin, project, "--key", "modules.tea")
    assert out["modules.tea"]["risk_threshold"] == "p0"
    assert out["modules.tea"]["test_stack_type"] == "auto"


def test_legacy_yaml_fills_missing_module_section(plugin, tmp_path):
    project = _make_project(tmp_path)
    _write_yaml(
        project / "bmad" / "gds" / "config.yaml",
        """
game_dev_experience: intermediate
user_name: Yunus
output_folder: "{project-root}/bmad-output"
""",
    )
    out = _run(plugin, project, "--key", "modules.gds", "--key", "core.user_name")
    assert out["modules.gds"]["game_dev_experience"] == "intermediate"
    # Core keys stamped by the legacy installer are routed to the CORE merge,
    # NOT kept in the module section — stale stamps must never shadow live core.
    assert "user_name" not in out["modules.gds"]
    assert out["core.user_name"] == "Yunus"


def test_legacy_core_fills_missing_core_section(plugin, tmp_path):
    project = _make_project(tmp_path)
    _write_yaml(
        project / "bmad" / "core" / "config.yaml",
        "user_name: Legacy\ncommunication_language: Turkish\n",
    )
    out = _run(plugin, project, "--key", "core")
    assert out["core"]["user_name"] == "Legacy"


def test_core_only_legacy_file_still_registers_module(plugin, tmp_path):
    project = _make_project(tmp_path)
    # bmad-loop-style legacy file: ONLY core stamps, no module-specific keys.
    # The module must still resolve (flat = core keys), not error.
    _write_yaml(
        project / "bmad" / "bmad-loop" / "config.yaml",
        'user_name: Yunus\noutput_folder: "{project-root}/bmad-output"\n',
    )
    out = _run(plugin, project, "--module", "bmad-loop")
    assert out["bmad-loop"]["user_name"] == "Yunus"
    assert out["bmad-loop"]["output_folder"] == "{project-root}/bmad-output"


def test_legacy_core_yaml_authority_over_module_stamps(plugin, tmp_path):
    project = _make_project(tmp_path)
    # Conflicting stamps: core/config.yaml is the authority for core keys;
    # per-module stamps only fill gaps.
    _write_yaml(project / "bmad" / "core" / "config.yaml", "user_name: CoreAuthority\n")
    _write_yaml(project / "bmad" / "tea" / "config.yaml", "user_name: StaleStamp\n")
    out = _run(plugin, project, "--key", "core.user_name")
    assert out == {"core.user_name": "CoreAuthority"}


def test_module_stamp_fills_gap_when_core_yaml_missing(plugin, tmp_path):
    project = _make_project(tmp_path)
    # No core/config.yaml — the module file's core stamp fills the gap in the
    # flat --module output (the realistic legacy skill query).
    _write_yaml(project / "bmad" / "tea" / "config.yaml", "user_name: FromStamp\n")
    out = _run(plugin, project, "--module", "tea")
    assert out["tea"]["user_name"] == "FromStamp"


def test_project_user_toml_beats_legacy_core(plugin, tmp_path):
    project = _make_project(tmp_path)
    _write_yaml(project / "bmad" / "core" / "config.yaml", "user_name: Legacy\n")
    _write_toml(project / "bmad" / "config.user.toml", '[core]\nuser_name = "Me"\n')
    out = _run(plugin, project, "--key", "core.user_name")
    assert out == {"core.user_name": "Me"}


# ── Project-root layers ──────────────────────────────────────────────

def test_project_bmad_toml_overrides_plugin_and_legacy(plugin, tmp_path):
    project = _make_project(tmp_path)
    _write_toml(
        project / "bmad" / "config.toml",
        '[modules.tea]\nrisk_threshold = "p0"\n',
    )
    out = _run(plugin, project, "--key", "modules.tea.risk_threshold")
    assert out == {"modules.tea.risk_threshold": "p0"}


def test_project_config_user_toml_overrides_project_team(plugin, tmp_path):
    project = _make_project(tmp_path)
    _write_toml(project / "bmad" / "config.toml", '[core]\nuser_name = "Team"\n')
    _write_toml(project / "bmad" / "config.user.toml", '[core]\nuser_name = "Me"\n')
    out = _run(plugin, project, "--key", "core.user_name")
    assert out == {"core.user_name": "Me"}


def test_bmad_output_layer_wins_over_project_bmad(plugin, tmp_path):
    project = _make_project(tmp_path)
    _write_toml(project / "bmad" / "config.toml", '[core]\noutput_folder = "a"\n')
    _write_toml(project / "bmad-output" / "config.toml", '[core]\noutput_folder = "b"\n')
    out = _run(plugin, project, "--key", "core.output_folder")
    assert out == {"core.output_folder": "b"}


def test_project_user_output_beats_everything(plugin, tmp_path):
    project = _make_project(tmp_path)
    _write_toml(project / "bmad" / "config.toml", '[core]\nlanguage = "en"\n')
    _write_toml(project / "bmad-output" / "config.toml", '[core]\nlanguage = "tr"\n')
    _write_toml(project / "bmad-output" / "config.user.toml", '[core]\nlanguage = "de"\n')
    out = _run(plugin, project, "--key", "core.language")
    assert out == {"core.language": "de"}


def test_project_layers_absent_is_fine(plugin, tmp_path):
    project = _make_project(tmp_path)  # no project files at all
    out = _run(plugin, project, "--key", "modules.tea.risk_threshold")
    assert out == {"modules.tea.risk_threshold": "p1"}


# ── --module flat output ─────────────────────────────────────────────

def test_module_flat_output_merges_core(plugin, tmp_path):
    project = _make_project(tmp_path)
    _write_toml(
        project / "bmad" / "config.toml",
        '[modules.wds]\nproject_type = "digital_product"\n',
    )
    out = _run(plugin, project, "--module", "wds")
    flat = out["wds"]
    assert flat["project_type"] == "digital_product"
    # core keys included (from plugin base)
    assert flat["output_folder"] == "{project-root}/bmad-output"
    assert flat["project_name"] == "base-project"


def test_module_output_project_override_applies(plugin, tmp_path):
    project = _make_project(tmp_path)
    _write_toml(
        project / "bmad" / "config.toml",
        '[modules.tea]\nrisk_threshold = "p0"\n',
    )
    out = _run(plugin, project, "--module", "tea")
    assert out["tea"]["risk_threshold"] == "p0"


def test_module_unknown_module_errors(plugin, tmp_path):
    project = _make_project(tmp_path)
    import subprocess

    cmd = [
        sys.executable,
        str(plugin / "bmad" / "scripts" / "resolve_config.py"),
        "--project-root", str(project), "--module", "nope",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    assert proc.returncode == 1
    assert "unknown module" in proc.stderr


def test_module_via_legacy_yaml(plugin, tmp_path):
    project = _make_project(tmp_path)
    _write_yaml(
        project / "bmad" / "tea" / "config.yaml",
        "risk_threshold: p0\nuser_name: Yunus\n",
    )
    out = _run(plugin, project, "--module", "tea")
    assert out["tea"]["risk_threshold"] == "p0"
    assert out["tea"]["user_name"] == "Yunus"


# ── deep_merge sanity (unchanged semantics) ──────────────────────────

def test_deep_merge_tables_and_scalars():
    base = {"a": {"b": 1, "c": 2}, "list": [1, 2]}
    over = {"a": {"b": 10}, "list": [3]}
    assert rc.deep_merge(base, over) == {"a": {"b": 10, "c": 2}, "list": [1, 2, 3]}


def test_keyed_array_merge_by_code():
    base = {"agents": [{"code": "x", "name": "A"}, {"code": "y", "name": "B"}]}
    over = {"agents": [{"code": "y", "name": "B2"}]}
    merged = rc.deep_merge(base, over)
    assert merged["agents"] == [
        {"code": "x", "name": "A"},
        {"code": "y", "name": "B2"},
    ]


def test_modules_from_key_paths():
    assert rc._modules_from_key_paths(["modules.tea.risk_threshold", "core"]) == ["tea"]
    assert rc._modules_from_key_paths([]) == []
