"""BMAD hooks engine modules."""

from .config import RUNTIME, GATE_DIR, log_file, CODE_DOCS_DIR, CODE_DOCS_TYPES
from .utils import norm_path, is_free, is_code_target, repo_root, rel_to_root
from .archive import ArchiveLimitError, targets_from_tar, targets_from_unzip
from .bash_targets import extract_bash_targets
from .guard import guard, quality, deploy, find_approved, verify_record
from .audit import audit, session_start
from .stop import stop
from .code_docs import (
    build_learning_doc, build_decision_doc, build_troubleshooting_doc,
    build_pattern_doc, build_api_doc, build_pending_doc,
    create_learning, create_decision, create_troubleshooting,
    create_pattern, create_api, create_pending,
    recall_by_tag, recall_by_experiment, recall_by_type, recall_all,
    load_context_for_task, load_recent_docs, load_pending_docs,
)

__all__ = [
    "RUNTIME",
    "GATE_DIR",
    "log_file",
    "CODE_DOCS_DIR",
    "CODE_DOCS_TYPES",
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
    "quality",
    "deploy",
    "find_approved",
    "verify_record",
    "audit",
    "session_start",
    "stop",
    "build_learning_doc",
    "build_decision_doc",
    "build_troubleshooting_doc",
    "build_pattern_doc",
    "build_api_doc",
    "build_pending_doc",
    "create_learning",
    "create_decision",
    "create_troubleshooting",
    "create_pattern",
    "create_api",
    "create_pending",
    "recall_by_tag",
    "recall_by_experiment",
    "recall_by_type",
    "recall_all",
    "load_context_for_task",
    "load_recent_docs",
    "load_pending_docs",
]
