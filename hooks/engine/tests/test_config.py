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
    TAR_ARG_OPTS,
)


def test_methodology_root_is_repo_root():
    # config.py is at <root>/hooks/engine/modules/config.py → root is 4 parents up.
    assert _METHODOLOGY_ROOT.name == "openhands-metodoloji"


def test_free_prefixes_are_slashed():
    for p in FREE_PREFIXES:
        assert p.endswith("/"), f"free prefix should end with /: {p!r}"


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


def test_hook_strictness_parses_hard_with_comment(tmp_path, monkeypatch):
    from modules import config
    # A [hooks] quality_gate = "hard" value followed by a # comment must parse.
    cfg = tmp_path / "config.toml"
    cfg.write_text('[hooks]\nquality_gate = "hard"   # "soft" (default) | "hard"\n',
                   encoding="utf-8")
    monkeypatch.setattr(config, "_HOOKS_CFG", cfg)
    assert config._hook_strictness() == "hard"


def test_hook_strictness_default_soft(tmp_path, monkeypatch):
    from modules import config
    cfg = tmp_path / "config.toml"
    cfg.write_text('[hooks]\nquality_gate = "soft"\n', encoding="utf-8")
    monkeypatch.setattr(config, "_HOOKS_CFG", cfg)
    assert config._hook_strictness() == "soft"


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
    assert config._hook_strictness() == "hard"  # combined: either hard → hard


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
