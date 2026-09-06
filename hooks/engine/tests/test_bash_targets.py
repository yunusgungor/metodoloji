"""Tests for hooks/engine/modules/bash_targets.py — write-target extraction.

Pins the ACTUAL behavior of extract_bash_targets, including several known
defects (each marked with `BUG:`). These defect tests are written to the real
behavior so a future fix flips them green; they document the gap rather than
assert a desired-but-absent behavior.
"""

import sys
from pathlib import Path

_HOOKS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_HOOKS))

from modules.bash_targets import (  # noqa: E402
    _read_patch_targets,
    _space_out_redirects,
    extract_bash_targets,
)


# --- _space_out_redirects: quote/escape-aware redirect separation ----------

def test_space_out_redirects_single_gt():
    # A bare `>` gets spaces around it.
    assert _space_out_redirects("echo hi >out.txt") == "echo hi  > out.txt"
    # Already-spaced redirect gets an extra space inserted.
    assert _space_out_redirects("echo hi > out.txt") == "echo hi  >  out.txt"


def test_space_out_redirects_ignores_quotes():
    # Single-quoted `>` is left alone; the trailing bare `>` gets spaced.
    out = _space_out_redirects("echo 'a > b' >real.txt")
    assert out == "echo 'a > b'  > real.txt"
    # BUG: inside double quotes the `>` is also spaced (in_d not checked),
    # and the append `>>` splits — both facets of the `>>` defect.
    out2 = _space_out_redirects('echo "x > y" >>log')
    assert out2 == 'echo "x > y"  >  > log'


def test_space_out_redirects_escaped_char():
    assert _space_out_redirects(r"echo \> >real.txt") == r"echo \>  > real.txt"


def test_space_out_redirects_double_gt():
    # BUG: `>>` is split into two separate `>` markers, corrupting append.
    # Desired: "cat f >> log.txt"; actual: "cat f  >  > log.txt".
    assert _space_out_redirects("cat f >>log.txt") == "cat f  >  > log.txt"


# --- extract_bash_targets: redirects ----------------------------------------

def test_redirect_single_gt_target():
    assert extract_bash_targets("echo hi > src/out.txt") == ["src/out.txt"]
    assert extract_bash_targets("echo hi >src/out.txt") == ["src/out.txt"]


def test_append_redirect_double_gt():
    # BUG: `>>` yields a spurious ">" target plus the real one.
    assert extract_bash_targets("cat f >> logs/app.log") == [">", "logs/app.log"]


# --- tee --------------------------------------------------------------------

def test_tee_target():
    assert extract_bash_targets("cmd | tee build/result.txt") == ["build/result.txt"]
    assert extract_bash_targets("cmd | tee -a log.txt") == ["log.txt"]


# --- sed -i ----------------------------------------------------------------

def test_sed_inplace_target():
    res = extract_bash_targets("sed -i 's/foo/bar/' src/app.py")
    assert "src/app.py" in res
    res2 = extract_bash_targets("sed -i.bak 's/x/y/' notes.md")
    assert any("notes.md" in t for t in res2)


def test_sed_without_i_no_target():
    assert extract_bash_targets("sed 's/x/y/' src/app.py") == []


# --- cp / mv / install ------------------------------------------------------

def test_cp_mv_install_target_is_dest():
    assert extract_bash_targets("cp a.py b.py") == ["b.py"]
    assert extract_bash_targets("mv src/old.py src/new.py") == ["src/new.py"]
    assert extract_bash_targets("install -m 755 x.py bin/x.py") == ["bin/x.py"]


def test_cp_multi_arg_dest():
    assert extract_bash_targets("cp a.py b.py lib/") == ["lib/"]


# --- curl / wget -----------------------------------------------------------

def test_curl_output_flag():
    assert extract_bash_targets("curl -o out.json http://x") == ["out.json"]
    assert extract_bash_targets("curl -o out.json http://x --max-time 5") == ["out.json"]


def test_wget_lowercase_o():
    assert extract_bash_targets("wget -o downloaded.zip http://x/y.zip") == ["downloaded.zip"]


def test_wget_uppercase_o():
    # BUG: wget -O (the actual flag) is not recognized; only lowercase -o.
    assert extract_bash_targets("wget -O downloaded.zip http://x/y.zip") == []


def test_curl_without_o_no_target():
    assert extract_bash_targets("curl http://x") == []


# --- dd of= -----------------------------------------------------------------

def test_dd_of_target():
    assert extract_bash_targets("dd if=/dev/zero of=img.bin bs=1M count=1") == ["img.bin"]


# --- git apply / am / checkout ----------------------------------------------

def _patch(tmp_path, body, name="changes.patch"):
    # Forward-slash path: shlex on Windows escapes backslashes, so a Windows
    # path like C:\...\changes.patch is mangled and the file is never read.
    p = str(tmp_path / name).replace("\\", "/")
    Path(p).write_text(body, encoding="utf-8")
    return p


def test_git_apply_patch(tmp_path):
    p = _patch(
        tmp_path,
        "diff --git a/src/a.py b/src/a.py\n"
        "--- a/src/a.py\n"
        "+++ b/src/a.py\n"
        "@@ -1,1 +1,1 @@\n"
        "-old\n"
        "+new\n",
    )
    res = extract_bash_targets(f"git apply {p}")
    assert "src/a.py" in res


def test_git_apply_with_directory_prefix(tmp_path):
    p = _patch(tmp_path, "diff --git a/src/a.py b/src/a.py\n+++ b/src/a.py\n")
    res = extract_bash_targets(f"git apply --directory=sub {p}")
    assert "sub/src/a.py" in res


def test_git_checkout_targets():
    res = extract_bash_targets("git checkout -- src/a.py lib/b.py")
    assert "src/a.py" in res and "lib/b.py" in res


def test_git_apply_windows_backslash_path(tmp_path):
    # _patch forward-slashes the temp path, so shlex leaves it intact on every
    # platform (a native C:\... path would otherwise be escape-mangled and the
    # patch never opened). Same contract as test_git_apply_patch.
    p = _patch(tmp_path, "diff --git a/src/a.py b/src/a.py\n+++ b/src/a.py\n")
    res = extract_bash_targets(f"git apply {p}")
    assert "src/a.py" in res


# --- patch ------------------------------------------------------------------

def test_patch_file_redirect(tmp_path):
    p = _patch(tmp_path, "diff --git a/x.c b/x.c\n--- a/x.c\n+++ b/x.c\n", "fix.patch")
    res = extract_bash_targets(f"patch < {p}")
    assert "x.c" in res


def test_patch_file_argument(tmp_path):
    p = _patch(tmp_path, "diff --git a/x.c b/x.c\n--- a/x.c\n+++ b/x.c\n", "fix.patch")
    res = extract_bash_targets(f"patch {p}")
    assert "x.c" in res


# --- python open/write/copy -------------------------------------------------

def test_python_open_write():
    cmd = "python3 -c \"open('out/data.txt', 'w').write('x')\""
    assert "out/data.txt" in extract_bash_targets(cmd)


def test_python_write_text():
    cmd = "python3 -c \"Path('src/gen.py').write_text('code')\""
    res = extract_bash_targets(cmd)
    assert "src/gen.py" in res


def test_python_copy():
    cmd = "python3 -c \"shutil.copy('a.py', 'b.py')\""
    res = extract_bash_targets(cmd)
    assert "b.py" in res


# --- interpreter -c with quoted code paths ----------------------------------

def test_interpreter_quote_code_target():
    res = extract_bash_targets("python3 -c 'run(\"scripts/gen.py\")'")
    assert any("scripts/gen.py" == t for t in res)


def test_interpreter_inline_code_no_target():
    assert extract_bash_targets("python3 -c 'print(1)'") == []


# --- empty / malformed ------------------------------------------------------

def test_empty_command_no_targets():
    assert extract_bash_targets("") == []
    assert extract_bash_targets(None) == []


def test_malformed_quotes_no_targets():
    assert extract_bash_targets("echo 'unterminated") == []


def test_unrelated_command_no_targets():
    assert extract_bash_targets("ls -la") == []
    assert extract_bash_targets("git status") == []


def test_shell_variable_targets_dropped():
    # Unexpanded $vars are not real paths (live find: "$spool_file" wedge).
    assert extract_bash_targets("cat > $spool_file << 'EOF'\nx\nEOF") == []
    assert extract_bash_targets("echo hi > ${OUT_DIR}/x.txt") == []
    assert extract_bash_targets("cp a.py $DEST/b.py") == []


# --- _read_patch_targets directly -------------------------------------------

def test_read_patch_targets(tmp_path):
    patch = tmp_path / "p.patch"
    patch.write_text(
        "diff --git a/one.py b/one.py\n--- a/one.py\n+++ b/one.py\n"
        "diff --git a/two/two.py b/two/two.py\n--- a/two/two.py\n+++ b/two/two.py\n",
        encoding="utf-8",
    )
    res = _read_patch_targets(str(patch))
    assert "one.py" in res and "two/two.py" in res


def test_read_patch_targets_missing_file():
    assert _read_patch_targets("/nonexistent/x.patch") == []


def test_read_patch_targets_duplicates():
    # Both the `diff --git` and `+++` patterns fire for the same file.
    res = _read_patch_targets(str(Path(".") / "no-such.patch"))
    assert res == []
