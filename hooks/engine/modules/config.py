"""Configuration constants for BMAD hooks engine."""

import os
import pathlib
import re

# NEW: Error code registry (CRITICAL #24 / ISSUE #69)
# Centralized error codes for consistent diagnostics across modules
ERROR_CODE_REGISTRY = {
    # Verification return codes (verify_record)
    "VERIFY_OK": {
        "rc": 0,
        "level": "info",
        "message": "Record passed HMAC verification",
        "recovery": "Record is approved for use"
    },
    "VERIFY_FAILED": {
        "rc": 1,
        "level": "error",
        "message": "Record verification failed (HMAC mismatch, not found, or gate error)",
        "recovery": "Check record file exists, token valid, or re-generate record"
    },
    "ADVISORY_BLOCKED": {
        "rc": 2,
        "level": "warning",
        "message": "Record has valid token but is restricted (small sample, metric missing, or locked)",
        "recovery": "Increase experiment sample size, collect metrics, or wait for lock release"
    },
    "KEY_MISSING": {
        "rc": 3,
        "level": "error",
        "message": "Gate secret key not configured",
        "recovery": "Run: python3 scripts/run_experiment.py --init-secret"
    },
    
    # Story validation errors
    "INVALID_AC_METADATA": {
        "status": "deny",
        "level": "error",
        "message": "AC missing required fields (Type, Measured, Verify, or Experiment)",
        "recovery": "Complete all required AC metadata fields"
    },
    "EXPERIMENT_NOT_FOUND": {
        "status": "deny",
        "level": "error",
        "message": "Referenced experiment record E-NNN not found in docs/experiments/",
        "recovery": "Create experiment record or correct the E-NNN reference"
    },
    "INVALID_STATUS": {
        "status": "deny",
        "level": "error",
        "message": "Story status invalid (must be: backlog, ready-for-dev, in-progress, review, done, blocked)",
        "recovery": "Set status to one of the valid states"
    },
    "DUPLICATE_RECORD_ID": {
        "status": "deny",
        "level": "error",
        "message": "Duplicate record ID (e.g., two S-001.md files)",
        "recovery": "Use unique record IDs within each type, or rename existing record"
    },
    "ORPHANED_STORY": {
        "status": "deny",
        "level": "error",
        "message": "Story references missing IR/SP (broken methodology chain)",
        "recovery": "Ensure S→SP→IR→E chain is complete before writing story"
    },
    
    # Hook validation errors
    "HOOK_SEQUENCE_VIOLATION": {
        "status": "warning",
        "level": "error",
        "message": "Hook event sequence invalid (not SessionStart→PreToolUse→PostToolUse→Stop)",
        "recovery": "Check agent hook execution order and trigger sequence"
    },
    "INVALID_HOOKS_CONFIG": {
        "level": "warning",
        "message": "Invalid [hooks] section key in config.toml",
        "recovery": "Use valid keys: quality_gate, deploy_guard, code_guard, stop_guard, blackboard"
    },
    
    # Blackboard errors
    "EVENT_LOG_CORRUPTION": {
        "code": "E001",
        "level": "error",
        "message": "Event log contains malformed JSON (truncated or incomplete line)",
        "recovery": "Rotate event log: python3 bmad/scripts/blackboard.py --rotate"
    },
    "FILE_LOCK_TIMEOUT": {
        "code": "E002",
        "level": "error",
        "message": "Snapshot file lock timeout (high contention or crashed process)",
        "recovery": "Wait for other processes to complete, or kill crashed processes in .metodoloji/"
    },
    "STALE_SESSION": {
        "code": "E004",
        "level": "error",
        "message": "Session started >1h ago without Stop marker (hung session)",
        "recovery": "Kill hung process: ps aux | grep hooks; kill -9 <pid>"
    },
    "CASCADE_INVALIDATION": {
        "code": "E005",
        "level": "warning",
        "message": "Referenced experiment modified recently; downstream records may be stale",
        "recovery": "Review experiment changes and re-validate affected records"
    },
    "SESSION_ISOLATION_FAILURE": {
        "level": "error",
        "message": "Session ID context lost (concurrent session interference)",
        "recovery": "Ensure sessions are not overlapping; check for agent crashes"
    },
    "GATE_VERIFY_TIMEOUT": {
        "level": "error",
        "message": f"Gate verification timeout after {30}s (record verification hung)",
        "recovery": "Check for corrupted record files, or increase GATE_VERIFY_TIMEOUT_SECONDS"
    },
}

# Runtime detection. main.py sets METODOLOJI_RUNTIME from --runtime= AFTER
# imports, so this must stay a function: a module-level constant would freeze
# the pre-flag value. (The old RUNTIME constant was removed — zero readers.)
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
_DONE_RE = re.compile(r"^(?:[-*]\s+)?\*?\*?Status\s*:\s*\*?\*?\s*(done)", re.IGNORECASE | re.MULTILINE)

# Log file location
def log_file() -> str:
    # OpenHands plugin olarak her zaman .metodoloji/logs/ kullan
    return ".metodoloji/logs/hook-audit.log"


# --- Validation Bounds (MEDIUM #11 / ISSUE #70) --------------------------------
# Prevent quadratic validation loops by bounding collection sizes
MAX_STORY_COUNT = 1000            # Max stories to validate in single check
MAX_AC_PER_STORY = 100             # Max acceptance criteria per story
MAX_EXPERIMENTS_TO_CHECK = 50      # Max experiment references to validate per chain
MAX_CHAIN_DEPTH = 10               # Max steps in methodology chain (S→SP→IR→E→QR→PR)
MAX_DUPLICATE_CHECK_RECORDS = 5000 # Max record files to scan for duplicate IDs
MAX_VALIDATION_LOOP_ITERATIONS = 10000  # Hard cap on any validation loop

# --- Timeout Values (MEDIUM #14 / ISSUE #73) --------------------------------
# Prevent indefinite hangs on corrupted files or locked resources
GATE_VERIFY_TIMEOUT_SECONDS = 30      # Max time for gate.verify() to complete
BLACKBOARD_READ_TIMEOUT_SECONDS = 5   # Max time to read blackboard state
BLACKBOARD_WRITE_TIMEOUT_SECONDS = 5  # Max time to write blackboard state
LOCK_ACQUIRE_TIMEOUT_SECONDS = 10     # Max time to acquire advisory lock (fail-open after)
FILE_OPERATION_TIMEOUT_SECONDS = 10   # Max time for file I/O operations

# --- Gate strictness ---------------------------------------------------------
# custom/config.toml [hooks]: quality_gate / deploy_guard / code_guard /
# stop_guard (soft|hard). quality/deploy default soft (warn-only); code/stop
# default hard (fail-closed — code writes and session close stay mechanical
# unless a project explicitly relaxes them, e.g. brownfield adoption).
# Read live per-call so config edits apply without a reload. Each key is
# read independently.
#
# NOTE (deliberate): this reads the plugin's own custom/config.toml, NOT the
# bmad resolve_config.py merge (four plugin layers + four {project-root}
# layers, plus the legacy per-module config.yaml bridge — see
# bmad/scripts/resolve_config.py). Hook enforcement is plugin policy, not
# project configuration: the layers above let a PROJECT override its own
# behavior, but a target project must never be able to silently relax the
# guard that watches it. Personal
# preference layers (config.user.toml) are opt-in via the brownfield keys.
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

# NEW: Valid [hooks] config keys (MEDIUM #9 / ISSUE #68)
_VALID_HOOKS_KEYS = frozenset({
    "quality_gate",
    "deploy_guard",
    "code_guard",
    "stop_guard",
    "blackboard",
})


def _validate_hooks_config() -> tuple[bool, str]:
    """Validate [hooks] section in custom/config.toml (MEDIUM #9 / ISSUE #68).
    
    Checks that all keys in [hooks] are recognized. Invalid keys raise error.
    Returns (is_valid, error_message).
    """
    try:
        text = _HOOKS_CFG.read_text(encoding="utf-8")
    except OSError:
        return True, ""  # Config file doesn't exist yet
    
    in_hooks = False
    invalid_keys = []
    line_no = 0
    
    for line in text.splitlines():
        line_no += 1
        stripped = line.strip()
        
        # Skip empty lines and comments
        if not stripped or stripped.startswith("#"):
            continue
        
        # Check for [hooks] section start
        if stripped.startswith("[hooks]"):
            in_hooks = True
            continue
        
        # Check for other sections
        if stripped.startswith("[") and not stripped.startswith("[hooks]"):
            in_hooks = False
            continue
        
        # Validate keys in [hooks] section
        if in_hooks and "=" in stripped:
            key, _, _ = stripped.partition("=")
            key = key.strip()
            
            if key not in _VALID_HOOKS_KEYS:
                invalid_keys.append((line_no, key))
    
    if invalid_keys:
        error_msg = f"Invalid [hooks] keys in {_HOOKS_CFG}: "
        error_parts = [f"line {line}: '{key}' (valid: {', '.join(sorted(_VALID_HOOKS_KEYS))})"
                      for line, key in invalid_keys[:3]]
        error_msg += "; ".join(error_parts)
        return False, error_msg
    
    return True, ""


def blackboard_enabled() -> bool:
    """[hooks] blackboard = on|off (default on). Read live per-call.

    off → every engine blackboard integration becomes a no-op; the CLI keeps
    working (fail-open) because skills own their writes.
    """
    try:
        text = _HOOKS_CFG.read_text(encoding="utf-8")
    except OSError:
        return True
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
            val = val.split("#", 1)[0].strip().strip('"').strip("'")
            if key == "blackboard":
                return val != "off"
    return True

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
# NOTE: hooks/, scripts/ and skills/ are deliberately NOT here.
# Those are plugin source trees and stay protected by the experiment gate in any
# ordinary project; see PLUGIN_FREE_PREFIXES for the self-modification exemption.
FREE_PREFIXES = (
    "_bmad/", "scratch/", "graft/", ".git/", "tmp/", "temp/",
    "openhands/", ".metodoloji/",
)

# Plugin source trees that are free ONLY when the plugin root resolves to the
# methodology root (i.e. this repository running as its own project). Resolved
# per-call in utils.is_free(); under test it is monkeypatched via config._METHODOLOGY_ROOT.
PLUGIN_FREE_PREFIXES = ("hooks/", "scripts/", "skills/", "custom/")

INFRA_FILES = {"scripts/check-methodology.sh", "skills/bmad-research-experiment/scripts/run_experiment.py"}

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


# NEW: Validate config on module load (MEDIUM #9 / ISSUE #68)
# Checks [hooks] section for invalid keys at import time
_config_valid, _config_error = _validate_hooks_config()
if not _config_valid:
    import sys
    sys.stderr.write(f"metodoloji: config error: {_config_error}\n")
    # Note: We don't raise here (fail-open) but log the error so deployment tools can catch it
