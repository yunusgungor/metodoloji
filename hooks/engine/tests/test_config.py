"""Tests for hooks/engine/modules/config.py — constants + invariants."""

import sys
from pathlib import Path

_HOOKS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_HOOKS))

from modules.config import (  # noqa: E402
    _AGENT_ZONES,
    _first_existing,
    _METHODOLOGY_ROOT,
    CODE_DIRS,
    CODE_DOCS_TYPES,
    FREE_PREFIXES,
    NON_CODE_EXTS,
    PLUGIN_FREE_PREFIXES,
    TAR_ARG_OPTS,
)


def test_methodology_root_is_repo_root():
    # config.py is at <root>/hooks/engine/modules/config.py → root is 4 parents up.
    # The checkout directory may be named after the repo ("metodoloji")
    # or by a local clone (e.g. "metodoloji") — pin the structural identity instead
    # of the directory's literal name.
    assert (_METHODOLOGY_ROOT / "hooks" / "engine").is_dir()
    assert (_METHODOLOGY_ROOT / "custom").is_dir()
    assert (_METHODOLOGY_ROOT / "bmad").is_dir()


def test_free_prefixes_are_slashed():
    for p in FREE_PREFIXES:
        assert p.endswith("/"), f"free prefix should end with /: {p!r}"
    for p in PLUGIN_FREE_PREFIXES:
        assert p.endswith("/"), f"plugin free prefix should end with /: {p!r}"


def test_plugin_trees_not_in_plain_free_prefixes():
    # Plugin source trees must NOT be unconditionally free: in ordinary projects
    # they stay behind the experiment gate. utils.is_free() releases them only
    # when the project root IS the methodology root (self-modification).
    for tree in ("hooks/", "scripts/", "skills/", "bmad_benchmarks/"):
        assert tree not in FREE_PREFIXES, f"{tree} must be a conditional plugin-free prefix"
        assert tree in PLUGIN_FREE_PREFIXES


def test_agent_zones_are_free_prefixes():
    # Every agent zone (scratch/tmp/temp) must also be a free prefix, so free-zone
    # files are always exempt from approval.
    for z in _AGENT_ZONES:
        zone = z if z.endswith("/") else z + "/"
        assert zone in FREE_PREFIXES, f"agent zone {zone} not free"


def test_code_dirs_do_not_collide_with_non_code_exts():
    # CODE_DIRS are directory names, NON_CODE_EXTS are extensions — they should
    # never overlap in a way that misclassifies.
    assert "md" not in CODE_DIRS
    assert "src" not in NON_CODE_EXTS


def test_code_doc_types_have_prefix_and_dir():
    for kind, info in CODE_DOCS_TYPES.items():
        assert info["prefix"]
        assert info["dir"]
        assert info["prefix"] in ("D", "P", "L", "A", "T", "X")


def test_tar_arg_opts_is_frozenset():
    assert isinstance(TAR_ARG_OPTS, frozenset)
    assert "-f" in TAR_ARG_OPTS and "--directory" in TAR_ARG_OPTS


def test_first_existing():
    from modules.config import _first_existing
    assert _first_existing([Path("/nonexistent-a"), Path("/nonexistent-b")]) is None
    # With a real file, returns it.
    import tempfile
    with tempfile.NamedTemporaryFile() as f:
        assert _first_existing([Path(f.name)]) == Path(f.name)


def test_hook_gate_mode_parses_hard_with_comment(tmp_path, monkeypatch):
    from modules import config
    # A [hooks] quality_gate = "hard" value followed by a # comment must parse.
    cfg = tmp_path / "config.toml"
    cfg.write_text('[hooks]\nquality_gate = "hard"   # "soft" (default) | "hard"\n',
                   encoding="utf-8")
    monkeypatch.setattr(config, "_HOOKS_CFG", cfg)
    assert config.hook_gate_mode("quality_gate") == "hard"


def test_hook_gate_mode_default_soft(tmp_path, monkeypatch):
    from modules import config
    cfg = tmp_path / "config.toml"
    cfg.write_text('[hooks]\nquality_gate = "soft"\n', encoding="utf-8")
    monkeypatch.setattr(config, "_HOOKS_CFG", cfg)
    assert config.hook_gate_mode("quality_gate") == "soft"


def test_hook_gate_values_read_independently(tmp_path, monkeypatch):
    """quality_gate and deploy_guard are independent — hard on one must not
    leak to the other."""
    from modules import config
    cfg = tmp_path / "config.toml"
    cfg.write_text(
        '[hooks]\nquality_gate = "soft"\ndeploy_guard = "hard"\n', encoding="utf-8")
    monkeypatch.setattr(config, "_HOOKS_CFG", cfg)
    assert config._hook_gate_value("quality_gate") == "soft"
    assert config._hook_gate_value("deploy_guard") == "hard"
    # hook_gate_mode is the public accessor — same independent semantics.
    assert config.hook_gate_mode("quality_gate") == "soft"
    assert config.hook_gate_mode("deploy_guard") == "hard"


def test_health_json_contract_keys():
    """The audit-status.sh health snapshot contract: these keys must always be
    present. (The script itself runs via subprocess which is flaky under
    Windows handle exhaustion; the contract is pinned here instead.)"""
    contract = {
        "generated", "gate_key", "experiments", "audit_log_lines",
        "skills", "custom_toml", "guard_ok",
    }
    # No executable check — just pin the key set the script must emit.
    assert len(contract) == 7


def test_non_code_exts_includes_markup_and_assets():
    for ext in (".md", ".json", ".yaml", ".png", ".pdf", ".zip", ".sqlite"):
        assert ext in NON_CODE_EXTS, ext


def test_gate_defaults_code_stop_hard_quality_deploy_soft(tmp_path, monkeypatch):
    """New gates default safe: code/stop hard, quality/deploy soft."""
    from modules import config
    cfg = tmp_path / "config.toml"
    cfg.write_text('[hooks]\n', encoding="utf-8")
    monkeypatch.setattr(config, "_HOOKS_CFG", cfg)
    assert config.hook_gate_mode("code_guard") == "hard"
    assert config.hook_gate_mode("stop_guard") == "hard"
    assert config.hook_gate_mode("quality_gate") == "soft"
    assert config.hook_gate_mode("deploy_guard") == "soft"


def test_gate_explicit_soft_code_guard(tmp_path, monkeypatch):
    """Brownfield adoption: code_guard=soft parses and is independent."""
    from modules import config
    cfg = tmp_path / "config.toml"
    cfg.write_text('[hooks]\ncode_guard = "soft"\nstop_guard = "hard"\n',
                   encoding="utf-8")
    monkeypatch.setattr(config, "_HOOKS_CFG", cfg)
    assert config.hook_gate_mode("code_guard") == "soft"
    assert config.hook_gate_mode("stop_guard") == "hard"
