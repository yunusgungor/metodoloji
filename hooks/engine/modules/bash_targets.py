"""Bash command target extraction for BMAD hooks engine."""

import os
import pathlib
import re
import shlex

from .archive import targets_from_tar, targets_from_unzip
from .config import CODE_BASENAMES, CODE_DIRS, TAR_ARG_OPTS
from .utils import is_code_target, norm_path


def _space_out_redirects(command: str) -> str:
    """Separate redirect operators without spaces."""
    out: list[str] = []
    in_s = in_d = False
    i, n = 0, len(command)
    while i < n:
        c = command[i]
        if c == "'" and not in_d:
            in_s = not in_s
            out.append(c)
            i += 1
        elif c == '"' and not in_s:
            in_d = not in_d
            out.append(c)
            i += 1
        elif c == "\\" and not in_s and not in_d:
            out.append(c)
            if i + 1 < n:
                out.append(command[i + 1])
                i += 2
            else:
                i += 1
        elif c == ">" and not in_s and not in_d:
            out.append(" > ")
            i += 1
        else:
            out.append(c)
            i += 1
    return "".join(out)


def _read_patch_targets(path: str, prefix: str = "") -> list[str]:
    """Extract target paths from patch/diff file."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            content = fh.read()
    except OSError:
        return []
    out: list[str] = []
    for m in re.finditer(r"(?m)^diff --git a/[^\t]+ b/(.+?)(?:[\t ]|$)", content):
        out.append(prefix + m.group(1))
    for m in re.finditer(r"(?m)^\+\+\+ (?:b/)?(.+?)(?:[\t ]|$)", content):
        out.append(prefix + m.group(1))
    return out


def extract_bash_targets(command: str) -> list[str]:
    """Return file paths the command may write to.

    Unexpanded shell variables ($var, ${var}) are caller-resolved or skipped:
    a literal "$spool_file" is never a real path, so it is dropped here
    rather than leaking into guard/stop decisions.
    """
    if not command:
        return []
    if "$" in command:
        return []
    targets: list[str] = []
    command = _space_out_redirects(command)
    try:
        tokens = shlex.split(command, posix=True)
    except ValueError:
        return []

    # Split command on && / ; / |
    seg_tokens: list[list[str]] = []
    _cur: list[str] = []
    for _t in tokens:
        if _t in ("&&", "||", ";", "|"):
            if _cur:
                seg_tokens.append(_cur)
                _cur = []
        else:
            _cur.append(_t)
    if _cur:
        seg_tokens.append(_cur)

    for i, tok in enumerate(tokens):
        if tok in (">", ">>"):
            if i + 1 < len(tokens) and not tokens[i + 1].startswith("&"):
                targets.append(tokens[i + 1])
        elif tok == "tee":
            for j in range(i + 1, len(tokens)):
                if not tokens[j].startswith("-"):
                    targets.append(tokens[j])
                    break
        elif tok == "sed":
            has_i = any(t.startswith("-i") for t in tokens[i + 1 : i + 3])
            if has_i:
                tail = [t for t in tokens[i + 1 :] if not t.startswith("-") and t != "-e"]
                if len(tail) >= 2:
                    targets.extend(tail[1:])
                elif tail:
                    targets.append(tail[-1])
        elif tok in ("cp", "mv", "install"):
            for st in seg_tokens:
                if st and st[0] == tok:
                    nonflag = [t for t in st[1:] if not t.startswith("-")]
                    if nonflag:
                        targets.append(nonflag[-1])
                    break
        elif tok in ("curl", "wget"):
            if "-o" in tokens[i + 1 : i + 3]:
                idx = tokens.index("-o", i + 1)
                if idx + 1 < len(tokens):
                    targets.append(tokens[idx + 1])
        elif tok.startswith("of="):  # dd of=/path
            targets.append(tok[3:])
        elif tok == "git":
            rest = tokens[i + 1 :]
            if rest and rest[0] in ("apply", "am"):
                args_after = rest[1:]
                prefix = ""
                for t in args_after:
                    m2 = re.match(r"--directory=(.+)$", t)
                    if m2:
                        prefix = m2.group(1).rstrip("/") + "/"
                patch_path = next((t for t in args_after if not t.startswith("-")), None)
                if patch_path:
                    targets.extend(_read_patch_targets(patch_path, prefix))
            elif rest and rest[0] == "checkout" and "--" in rest:
                targets.extend(
                    t
                    for t in rest[rest.index("--") + 1 :]
                    if t and not t.startswith("-")
                )
        elif tok == "patch":
            rest = tokens[i + 1 :]
            nonflags = [t for t in rest if not t.startswith("-")]
            if "<" in rest:
                j = rest.index("<")
                if j + 1 < len(rest):
                    targets.extend(_read_patch_targets(rest[j + 1]))
            elif len(nonflags) == 1:
                targets.extend(_read_patch_targets(nonflags[0]))
            elif len(nonflags) >= 2:
                targets.append(nonflags[0])
                targets.extend(_read_patch_targets(nonflags[1]))
        elif tok == "tar":
            args_after = tokens[i + 1 :]
            _extract = False
            _skip_next = False
            _n = 0
            for t in args_after:
                _n += 1
                if _n > 32:
                    break
                if _skip_next:
                    _skip_next = False
                    continue
                if t in TAR_ARG_OPTS:
                    _skip_next = True
                    continue
                if t.startswith("-"):
                    if t.startswith("--extract") or t.startswith("-x"):
                        _extract = True
                    continue
                if t.startswith("x"):
                    _extract = True
                break
            if _extract:
                targets.extend(targets_from_tar(args_after))
        elif tok == "unzip":
            targets.extend(targets_from_unzip(tokens[i + 1 :]))
        elif tok.startswith("python"):
            for m in re.finditer(
                r"""\bopen\(\s*['"]([^'"]+)['"]\s*,\s*['"](?:w|a|w\+|a\+)['"]\s*\)""",
                command,
            ):
                targets.append(m.group(1))
            for m in re.finditer(
                r"""\b(?:write_text|write_bytes|touch)\(\s*['"]([^'"]+)['"]""",
                command,
            ):
                targets.append(m.group(1))
            for m in re.finditer(
                r"""\b(?:copy|copyfile|copy2|move|rename|replace)\s*\([^,]+,\s*['"]([^'"]+)['"]""",
                command,
            ):
                targets.append(m.group(1))
        elif re.search(
            r"(?i)\b(python\d*|node|nodejs|perl|ruby|php|deno|bun|lua|Rscript)\b",
            command,
        ) and re.search(r"(?<![A-Za-z0-9])-([a-zA-Z]*[cEer])\b", command):
            for m in re.finditer(r"""['"]([^'"]+\.[A-Za-z0-9]+)['"]""", command):
                if is_code_target(m.group(1)):
                    targets.append(m.group(1))
            for m in re.finditer(r"""['"](?=([^'"]*)['"])""", command):
                s = m.group(1)
                if not s or re.search(r"\.[A-Za-z0-9]+$", s):
                    continue
                base = pathlib.PurePosixPath(s).name.lower()
                first = s.split("/", 1)[0].lstrip(".")
                if (first in CODE_DIRS and ("/" in s or "\\" in s)) or base in CODE_BASENAMES:
                    if is_code_target(s):
                        targets.append(s)
    return targets
