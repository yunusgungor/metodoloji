"""Configuration constants for BMAD hooks engine."""

import os
import pathlib
import re

# Runtime detection. Module-level constant kept for backward compatibility,
# but main.py sets METODOLOJI_RUNTIME from --runtime= AFTER imports, so live
# code must call runtime() instead of reading RUNTIME.
RUNTIME = os.environ.get("METODOLOJI_RUNTIME", "claude")


def runtime() -> str:
    """Live runtime value (main.py may set it after import)."""
    return os.environ.get("METODOLOJI_RUNTIME", "claude")

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
# custom/config.toml [hooks]: quality_gate / deploy_guard / code_guard /
# stop_guard (soft|hard). quality/deploy default soft (warn-only); code/stop
# default hard (fail-closed — code writes and session close stay mechanical
# unless a project explicitly relaxes them, e.g. brownfield adoption).
# Read live per-call so config edits apply without a reload. Each key is
# read independently.
_HOOKS_CFG = _METHODOLOGY_ROOT / "custom" / "config.toml"

def _hook_gate_value(gate_key: str, *args) -> str:
    """Return the value of a [hooks] gate key: 'hard'/'soft' when set, else default.

    Default comes from _GATE_DEFAULTS (soft for quality_gate/deploy_guard,
    hard for code_guard/stop_guard). A positional default may be passed for
    backward compatibility with single-arg mocks in tests; the table wins
    when no override is given. Only the named key is read, so gates stay
    independent.
    """
    default = args[0] if args else _GATE_DEFAULTS.get(gate_key, "soft")
    try:
        text = _HOOKS_CFG.read_text(encoding="utf-8")
    except OSError:
        return default
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
            if key == gate_key and val in ("hard", "soft"):
                return val
    return default

# Per-key defaults: commit/deploy gates are warn-only unless opted into hard;
# code/stop gates stay mechanical unless a project explicitly relaxes them.
_GATE_DEFAULTS = {
    "quality_gate": "soft",
    "deploy_guard": "soft",
    "code_guard": "hard",
    "stop_guard": "hard",
}

def hook_gate_mode(gate_key: str) -> str:
    """Public per-call accessor for one [hooks] gate mode: 'soft' | 'hard'.

    Each gate key is read INDEPENDENTLY and live from custom/config.toml —
    an import-time constant would go stale, and one gate's mode must never
    leak into the other's semantics.
    """
    return _hook_gate_value(gate_key)

# Code classification
NON_CODE_EXTS = {
    ".md", ".markdown", ".txt", ".rst", ".json", ".jsonc", ".toml", ".yaml", ".yml",
    ".csv", ".tsv", ".log", ".lock",
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".ico", ".bmp", ".avif",
    ".woff", ".woff2", ".ttf", ".eot", ".otf",
    ".pdf", ".zip", ".gz", ".tar", ".bz2", ".xz", ".7z", ".rar",
    ".sqlite", ".db", ".sqlite3", ".parquet", ".arrow", ".npy", ".npz", ".h5",
    ".hdf5", ".pkl", ".pickle", ".feather",
    # Toolchain config: real code lives elsewhere; gating these files only
    # produces brownfield false-blocks (e.g. prisma.config.ts).
    ".config.js", ".config.ts", ".config.mjs", ".config.cjs",
}

# Basename-level toolchain config (matched against the full relative path):
# bundler/linter/formatter/ORM configs are not application code.
NON_CODE_CONFIG_RES = (
    re.compile(r"(?i)(?:^|/)(?:prisma|vite|vitest|webpack|rollup|esbuild|babel|eslint|prettier|"
               r"postcss|tailwind|jest|playwright|cypress|next|nuxt|astro)\.config\.[a-z0-9]+$"),
    re.compile(r"(?i)(?:^|/)(?:tsconfig(?:\..*)?|jsconfig(?:\..*)?|package-lock\.json|"
               r"yarn\.lock|pnpm-lock\.yaml|bun\.lockb?)$"),
)

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
# Per-member cap: without it a single 2GB member passes the total check.
ARCHIVE_MAX_MEMBER = 256 * 1024 * 1024

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
# Secret access needs an access context (assignment, env read, file open),
# not a bare substring — "secret_env" alone appears in ordinary prose.
_KEY_ACCESS_IN_CONTENT = re.compile(
    r"(?i)(?:"
    r"\.bmad(?=[\\/\s\"'*?\[\]]|$)|"  # .bmad dir reference (path boundary)
    r"gate-key|"                       # key filename — specific enough bare
    r"bmad_gate_key|gate_token|"        # exact key/token identifiers
    r"(?:load_secret|secret_file|secret_env)\s*[(=:\[]"  # call/assign/open context
    r")"
)
