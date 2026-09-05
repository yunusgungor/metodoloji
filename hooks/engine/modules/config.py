"""Configuration constants for BMAD hooks engine."""

import os
import pathlib
import re

# Runtime detection
RUNTIME = os.environ.get("METODOLOJI_RUNTIME", "claude")

# Gate script location — resolved inside the methodology root.
# config.py lives at <methodology-root>/hooks/engine/modules/config.py:
#   parent1 = modules/
#   parent2 = engine/
#   parent3 = hooks/
#   parent4 = <methodology-root>
_METHODOLOGY_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent.parent

def _first_existing(cands: list[pathlib.Path]) -> pathlib.Path | None:
    for c in cands:
        if c.exists():
            return c
    return None

GATE_DIR = _first_existing([
    _METHODOLOGY_ROOT / "skills" / "bmad-research-experiment" / "scripts",
])

# Shared story status regex (DRY: used by guard, stop, audit)
_DONE_RE = re.compile(r"[-*]?\s*\*?\*?Status\s*:\s*\*?\*?\s*(done)", re.IGNORECASE | re.MULTILINE)

# Log file location
def log_file() -> str:
    # OpenHands plugin olarak her zaman .metodoloji/logs/ kullan
    return ".metodoloji/logs/hook-audit.log"


# --- Gate strictness ---------------------------------------------------------
# custom/config.toml [hooks] quality_gate / deploy_guard (soft|hard). Default
# soft: commit/deploy gates warn (allow + methodology_warnings) instead of
# blocking; "hard" opts into denial. Read live per-call so config edits apply
# without a reload. Each key is read independently.
_HOOKS_CFG = _METHODOLOGY_ROOT / "custom" / "config.toml"

def _hook_gate_value(gate_key: str) -> str:
    """Return the value of a [hooks] gate key: 'hard' when set, else 'soft'.

    A malformed/missing config fails soft (permissive). Only the named key is
    read, so quality_gate and deploy_guard stay independent.
    """
    try:
        text = _HOOKS_CFG.read_text(encoding="utf-8")
    except OSError:
        return "soft"
    in_hooks = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("[hooks]"):
            in_hooks = True
            continue
        if in_hooks and stripped.startswith("[") and not stripped.startswith("[hooks]"):
            break
        if in_hooks and "=" in stripped:
            key, _, val = stripped.partition("=")
            key = key.strip()
            # Strip a trailing # comment and surrounding quotes.
            val = val.split("#", 1)[0].strip().strip('"').strip("'")
            if key == gate_key and val == "hard":
                return "hard"
    return "soft"

def _hook_strictness() -> str:
    """Backward-compatible combined strictness: 'hard' if EITHER gate is hard.

    Used by guard()'s story-metadata path, which predates the split gate keys.
    """
    if _hook_gate_value("quality_gate") == "hard" or _hook_gate_value("deploy_guard") == "hard":
        return "hard"
    return "soft"


def hook_gate_mode(gate_key: str) -> str:
    """Public per-call accessor for a [hooks] gate mode: 'soft' | 'hard'.

    Always reads live from custom/config.toml — an import-time constant would
    go stale the moment config.toml changes after the engine process starts.
    """
    return _hook_gate_value(gate_key)


def QUALITY_GATE_HARD() -> bool:
    """Deprecated shim: use hook_gate_mode() for per-call reads.

    Kept as a function because the value cannot be snapshotted at import time:
    config.toml may change (or not exist yet) after this module is imported.
    """
    return _hook_strictness() == "hard"

# Code classification
NON_CODE_EXTS = {
    ".md", ".markdown", ".txt", ".rst", ".json", ".jsonc", ".toml", ".yaml", ".yml",
    ".csv", ".tsv", ".log", ".lock",
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".ico", ".bmp", ".avif",
    ".woff", ".woff2", ".ttf", ".eot", ".otf",
    ".pdf", ".zip", ".gz", ".tar", ".bz2", ".xz", ".7z", ".rar",
    ".sqlite", ".db", ".sqlite3", ".parquet", ".arrow", ".npy", ".npz", ".h5",
    ".hdf5", ".pkl", ".pickle", ".feather",
}

NON_CODE_BASENAMES = {
    ".gitignore", ".gitattributes", ".gitkeep", ".ignore",
    ".dockerignore", ".editorconfig", ".npmrc", "license", "copying",
    "readme", "authors", "notice"
}

CODE_BASENAMES = {
    "makefile", "dockerfile", "cmakelists.txt", "rakefile", "justfile",
    "taskfile.yml", "taskfile.yaml"
}

CODE_DIRS = {"lib", "src", "tools", "bin", "core", "app"}

EXEC_CONFIG_NAME = re.compile(
    r"(?i)(?:^|/)(?:\.github/workflows/|\.gitlab-ci\.yml$|azure-pipelines\.yml$|"
    r"(?:docker-compose|compose)[^/]*\.ya?ml$|package\.json$)"
)

# Free zones — project-relative prefixes that never need experiment approval.
# NOTE: hooks/, scripts/, skills/ and bmad_benchmarks/ are deliberately NOT here.
# Those are plugin source trees and stay protected by the experiment gate in any
# ordinary project; see PLUGIN_FREE_PREFIXES for the self-modification exemption.
FREE_PREFIXES = (
    "_bmad/", "scratch/", "graft/", ".git/", "tmp/", "temp/",
    "openhands/", ".metodoloji/", "docs/code-docs/",
)

# Plugin source trees that are free ONLY when the plugin root resolves to the
# methodology root (i.e. this repository running as its own project). Resolved
# per-call in utils.is_free(); under test it is monkeypatched via config._METHODOLOGY_ROOT.
PLUGIN_FREE_PREFIXES = ("hooks/", "scripts/", "skills/", "bmad_benchmarks/", "custom/")

INFRA_FILES = {"scripts/check-methodology.sh", "skills/bmad-research-experiment/scripts/run_experiment.py"}

# Code docs paths
CODE_DOCS_DIR = "docs/code-docs"
CODE_DOCS_TYPES = {
    "decision": {"prefix": "D", "dir": "decisions"},
    "pattern": {"prefix": "P", "dir": "patterns"},
    "learning": {"prefix": "L", "dir": "learnings"},
    "api": {"prefix": "A", "dir": "api"},
    "troubleshooting": {"prefix": "T", "dir": "troubleshooting"},
    "pending": {"prefix": "X", "dir": "pending"},
}

FREE_DOC_MD = re.compile(r"(?i)^docs/.*\.md$")
FREE_DOC_RAW = re.compile(r"(?i)^docs/.*/raw(/|$)")

# Archive limits
ARCHIVE_MAX_FILE = 512 * 1024 * 1024
ARCHIVE_MAX_COMPRESSED = 64 * 1024 * 1024
ARCHIVE_MAX_MEMBERS = 200_000
ARCHIVE_MAX_UNCOMPRESSED = 2 * 1024 * 1024 * 1024

TAR_ARG_OPTS = frozenset({
    "-C", "--directory", "-f", "--file", "--exclude", "--owner", "--group",
    "--transform", "--to-command", "--strip-components", "--index-file",
    "--record-size", "--blocking-factor", "--use-compress-program",
    "--newer", "--newer-mtime", "--listed-incremental", "--files-from",
    "--checkpoint", "--checkpoint-action", "--warning", "--level",
})

# Secret protection
_BMD_DIR = re.compile(r"(?i)(?:^|[\\/~\s\"'=])\.bmad(?=[\\/\s\"'*?\[\]]|$)")
_AGENT_ZONES = ("scratch/", "tmp/", "temp/")
_KEY_ACCESS_IN_CONTENT = re.compile(
    r"(?i)(?:\.bmad|gate-key|bmad_gate_key|load_secret|gate_token|secret_file|secret_env)"
)
