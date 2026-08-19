"""BMAD hooks engine modules."""

from .config import RUNTIME, GATE_DIR, log_file
from .utils import norm_path, is_free, is_code_target, repo_root, rel_to_root
from .archive import ArchiveLimitError, targets_from_tar, targets_from_unzip
from .bash_targets import extract_bash_targets
from .guard import guard, find_approved, verify_record
from .audit import audit
from .stop import stop

__all__ = [
    "RUNTIME",
    "GATE_DIR",
    "log_file",
    "norm_path",
    "is_free",
    "is_code_target",
    "repo_root",
    "rel_to_root",
    "ArchiveLimitError",
    "targets_from_tar",
    "targets_from_unzip",
    "extract_bash_targets",
    "guard",
    "find_approved",
    "verify_record",
    "audit",
    "stop",
]
