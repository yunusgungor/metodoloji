#!/usr/bin/env python3
"""bmad-hooks.py — BMAD metodolojisi hook motoru (PreToolUse/Stop/PostToolUse).

Kabuk hook'larına ince sarmalayıcı olarak bakılan bu betik, tüm karar mantığını
Python'da taşır:
  guard  — PreToolUse (Write|Edit|Bash|MultiEdit|NotebookEdit):
           kapı anahtarı + 'Kod kapsamı' eşleşmesi olmadan kod yazımını engeller.
  stop   — Stop: FORGED / ADVISORY-BLOCK kayıt ya da kapsam dışı kod varken
           doğrulanmış onay yoksa bitişi engeller.
  audit  — PostToolUse: denetim izine tam satırı JSON olarak yazar (tırnak kesmesi yok).

'guard' kararı için kapı betiğini (run_experiment.py) içe aktarır — tek doğruluk
kaynağı odur; buradaki mantık kapıyı kopyalamaz.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import pathlib
import re
import shlex
import subprocess
import sys
import tarfile
import time
import zipfile

_HERE = pathlib.Path(__file__).resolve().parent


def _first_existing(cands: list[pathlib.Path]) -> pathlib.Path | None:
    for c in cands:
        if c.exists():
            return c
    return None


# Kapı betiğinin bulunduğu dizin — iki yerleşim desteklenir:
#  claude:   .claude/helpers/ -> .claude/skills/bmad-research-experiment/scripts
#  plugin:   {plugin}/hooks/engine/ -> {plugin}/skills/bmad-research-experiment/scripts
_GATE_DIR = _first_existing([
    _HERE.parent / "skills" / "bmad-research-experiment" / "scripts",
    _HERE.parent.parent / "skills" / "bmad-research-experiment" / "scripts",
])
if _GATE_DIR is None:
    sys.stderr.write("bmad-hooks: kapı (run_experiment.py) bulunamadı — fail-closed\n")
    sys.exit(2)
if str(_GATE_DIR) not in sys.path:
    sys.path.insert(0, str(_GATE_DIR))
import run_experiment as gate  # noqa: E402

# Çıkış profili: 'claude' (hookSpecificOutput.permissionDecision) veya 'openhands'
# ({"decision": ...}; deny exit 2). main() --runtime argümanıyla da değiştirebilir.
_RUNTIME = os.environ.get("METODOLOJI_RUNTIME", "claude")

# --- Kod hedefi tanımı (BEYAZ-LİSTE: serbest bölge dışında her şey kod) ---
# Uzantı kara-listesi (CODE_EXTS) listelenmeyen dille (r, jl, dart, zig...) baypas
# edilirdi. Yalnızca veri/markup/asset & dosya-adı muafiyeti (NON_CODE_*) tanınır;
# kalan HER dosya kod sayılır. CODE_DIRS üyeleri her durumda koddur.
NON_CODE_EXTS = {
    ".md", ".markdown", ".txt", ".rst", ".json", ".jsonc", ".toml", ".yaml", ".yml",
    ".csv", ".tsv", ".log", ".lock",
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".ico", ".bmp", ".avif",
    ".woff", ".woff2", ".ttf", ".eot", ".otf",
    ".pdf", ".zip", ".gz", ".tar", ".bz2", ".xz", ".7z", ".rar",
    ".sqlite", ".db", ".sqlite3", ".parquet", ".arrow", ".npy", ".npz", ".h5",
    ".hdf5", ".pkl", ".pickle", ".feather",
}
NON_CODE_BASENAMES = {".gitignore", ".gitattributes", ".gitkeep", ".ignore",
                      ".dockerignore", ".editorconfig", ".npmrc", "license", "copying",
                      "readme", "authors", "notice"}
CODE_BASENAMES = {"makefile", "dockerfile", "cmakelists.txt", "rakefile", "justfile",
                  "taskfile.yml", "taskfile.yaml"}
CODE_DIRS = {"lib", "src", "tools", "bin", "core", "app"}
# Yürütülebilir config: uzantısı 'veri' (yml/yaml/json) olsa bile davranış taşır —
# CI workflow'ları, docker-compose, kök package.json (scripts). Beyaz-listenin gerçek
# açığı bunlardı (madde 3): onaysız yazılıp onaydan bağımsız kod çalıştırırdı.
EXEC_CONFIG_NAME = re.compile(
    r"(?i)(?:^|/)(?:\.github/workflows/|\.gitlab-ci\.yml$|azure-pipelines\.yml$|"
    r"(?:docker-compose|compose)[^/]*\.ya?ml$|package\.json$)")
# Serbest bölgeler: burada kod yazımı onaysız serbesttir (keşif/metadata/araç kodları).
# scripts/ ve skills/ BİLEREK DAHİL DEĞİLDİR — üretim kodu buraya yazılarak kapı atlanmaz;
# yalnızca metodolojinin KENDİ altyapı dosyaları için dar istisna (INFRA_FILES) tanınır.
# openhands/ OpenHands plugin iskeletidir (motor kopyası, skill kaynakları) —
# metodolojinin kendi altyapısı olarak .claude/ ile aynı muafiyete sahiptir.
# .metodoloji/ plugin'in workspace'içi önbelleğidir (bootstrap senkronu + audit log);
# içerik bizim altyapımız, hedef projenin kodu değildir.
FREE_PREFIXES = (".claude/", "_bmad/", "scratch/", "graft/", ".git/", "tmp/", "temp/",
                 "openhands/", ".metodoloji/")
INFRA_FILES = {"scripts/check-methodology.sh", "scripts/run_experiment.py"}
# docs/ yalnızca .md ve raw/ altında serbest; docs/evil.py gibi kod dosyaları korunur.
FREE_DOC_MD = re.compile(r"(?i)^docs/.*\.md$")
FREE_DOC_RAW = re.compile(r"(?i)^docs/.*/raw(/|$)")

# Denetim izi konumu runtime'a göre: Claude'da .claude/logs, OpenHands'te .metodoloji/logs.
def _log_file() -> str:
    if _RUNTIME == "openhands":
        return ".metodoloji/logs/hook-audit.log"
    return ".claude/logs/hook-audit.log"



def norm_path(p: str) -> str:
    """Windows/Unix karışık yolları proje-göreli, ters-bölüsüz, './'siz forma indir."""
    p = (p or "").replace("\\", "/")
    p = re.sub(r"^[a-zA-Z]:", "", p)  # sürücü önekini soy (c:/... -> /...)
    while p.startswith("./"):
        p = p[2:]
    return p


def is_free(path: str) -> bool:
    """True if the project-relative path is inside a free zone (no approval needed)."""
    p = norm_path(path).lstrip("/")
    if not p:
        return True
    if FREE_DOC_MD.match(p) or FREE_DOC_RAW.match(p):
        return True
    if p in INFRA_FILES:
        return True
    if p.startswith("explore_"):
        return True
    return any(p.startswith(prefix) for prefix in FREE_PREFIXES)


def is_code_target(path: str) -> bool:
    """True if the path is a code target (beyaz-liste: veri/markup/asset dışı her şey)."""
    p = norm_path(path).lstrip("/")
    base = pathlib.PurePosixPath(p).name
    first = p.split("/", 1)[0]
    ext = pathlib.PurePosixPath(base).suffix.lower()
    if p == "dev/null" or p.startswith("dev/null/"):
        return False  # aygıt/discard — proje kodu değil (env > /dev/null vb. serbest)
    if base.lower() in CODE_BASENAMES or first in CODE_DIRS:
        return True
    if EXEC_CONFIG_NAME.search(p):
        return True  # yürütülebilir config (workflow/compose/package.json) kod sayılır
    if ext in NON_CODE_EXTS or base.lower() in NON_CODE_BASENAMES:
        return False
    return True  # beyaz liste: bilinen veri/markup/asset dışındaki her dosya kod sayılır


def repo_root(json_in: dict) -> str:
    root = (os.environ.get("CLAUDE_PROJECT_DIR")
            or os.environ.get("OPENHANDS_PROJECT_DIR")
            or json_in.get("cwd") or json_in.get("working_dir")
            or os.getcwd())
    return os.path.abspath(root)


def rel_to_root(root: str, p: str, cwd: str | None = None) -> str:
    """Resolve a possibly-relative path against cwd (or root) and relativize to root."""
    if not p:
        return ""
    p = p.strip().strip("\"'")
    base = cwd or root
    full = p if os.path.isabs(p) or re.match(r"^[a-zA-Z]:[/\\]", p) \
        else os.path.join(base, p)
    r = norm_path(root)
    f = norm_path(full)
    if r and (f.startswith(r.rstrip("/") + "/") or f.startswith(r)):
        f = f[len(r.rstrip("/")):].lstrip("/")
    return f


# --- Bash yazma-hedefi tespiti (Python; shlex tırnak-dengeli, eski sed kesmesi yok) ---


def _space_out_redirects(command: str) -> str:
    """Boşluksuz yönlendirme operatörlerini (> hedef, >>hedef, 2>hedef, x>hedef) ayırır.

    shlex '>' öğesini ayraç saymaz; 'echo x>src/evil.py' tek token'a dönüşürdü.
    Tırnak içlerine ve ters-bölü kaçışlarına dokunulmaz; 2>&1 gibi fd-yineleme
    hedefi '&...' olduğu için ayrım aşağıda ayrıca yapılır.
    """
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
    """Patch/diff dosyasından değiştirilecek hedef yolları çıkar.

    git apply/am ve patch (<) için ortaktır: 'diff --git a/x b/y' ve '+++ b/y'
    başlıkları hedefin kendisidir (yalnızca git: a/ → b/ kopyası değil, yazılan taraf).
    Dosya okunamazsa [] döner (Stop arka planı devreye girer; guard sessiz geçer).
    """
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            content = fh.read()
    except OSError:
        return []
    out: list[str] = []
    for m in re.finditer(r"(?m)^diff --git a/[^ \t]+ b/(.+?)(?:[\t ]|$)", content):
        out.append(prefix + m.group(1))
    for m in re.finditer(r"(?m)^\+\+\+ (?:b/)?(.+?)(?:[\t ]|$)", content):
        out.append(prefix + m.group(1))
    return out


# Tur 6/madde 1: arşiv ayrıştırma tavanları — ajan-kontrollü arşiv-bombası guard'ı
# (PreToolUse) sınırsız CPU/bellek harcamaya zorlayamaz. Tavan aşılınca arşiv
# "okunamaz" sayılır → konservatif hedef-dizini (fail-closed kod bölgesi).
_ARCHIVE_MAX_FILE = 512 * 1024 * 1024          # diskteki arşiv boyutu tavanı
_ARCHIVE_MAX_COMPRESSED = 64 * 1024 * 1024     # açılan (sıkıştırılmış) bayt tavanı
_ARCHIVE_MAX_MEMBERS = 200_000                  # üye sayısı tavanı
_ARCHIVE_MAX_UNCOMPRESSED = 2 * 1024 * 1024 * 1024  # üye boyutları toplamı tavanı

# Tur 6 (kalıntı): tar'da bağımsız argüman alan seçenekler — tespit döngüsü bunların
# argümanlarını "komut jetonu" sanmamak için atlar (ör. 'tar --exclude PAT xf a.tgz').
_TAR_ARG_OPTS = frozenset({
    "-C", "--directory", "-f", "--file", "--exclude", "--owner", "--group",
    "--transform", "--to-command", "--strip-components", "--index-file",
    "--record-size", "--blocking-factor", "--use-compress-program",
    "--newer", "--newer-mtime", "--listed-incremental", "--files-from",
    "--checkpoint", "--checkpoint-action", "--warning", "--level",
})


class _ArchiveLimitError(OSError):
    """Arşiv bir tavanı aştı — konservatif davranışa düş (fail-closed)."""


class _LimitReader(io.RawIOBase):
    """Belirli sayıda baytın ötesini okumayı reddeden sınırlı okuyucu.

    Tarfile sıkıştırılmış akışta sıralı okur; bu sarmalayıcı tüm okumaları geçirir
    ve tavan aşıldığında _ArchiveLimitError yükseltir — bir gzip-bombası sınırlı
    sıkıştırılmış veriye dek açılır, sınırsız işe dönüşmez.
    """

    def __init__(self, raw: io.RawIOBase, limit: int):
        super().__init__()
        self._raw = raw
        self._left = limit

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return True

    def tell(self) -> int:
        return self._raw.tell()

    def seek(self, offset: int, whence: int = 0) -> int:
        # Tur 6/madde 1 (kalıntı): ileri-seek de "dokunulan bayt" sayılır ve tavan
        # bütçesinden düşülür — okuyucu değişmezi: temel akıştan okunan + ileri
        # atlanan toplam bayt asla _left'i aşamaz. Geriye-seek tavan harcamaz
        # (iş yapmaz; tarfile açılış probe'unda seek(0) bu yüzden serbesttir).
        cur = self._raw.tell()
        if whence == 0:
            target = offset
        elif whence == 1:
            target = cur + offset
        else:
            target = self._raw.seek(0, 2)
            self._raw.seek(cur, 0)
            target += offset
        if target > cur:
            if target - cur > self._left:
                raise _ArchiveLimitError("arşiv ileri-seek tavanı aşıldı")
            self._left -= target - cur
        self._raw.seek(offset, whence)
        return self._raw.tell()

    def readinto(self, b) -> int:
        if self._left <= 0:
            raise _ArchiveLimitError("arşiv okuma tavanı aşıldı")
        view = memoryview(b)
        chunk = view[:self._left]
        m = self._raw.readinto(chunk)
        self._left -= m
        return m

    def read(self, n: int = -1) -> bytes:
        if self._left <= 0:
            raise _ArchiveLimitError("arşiv okuma tavanı aşıldı")
        if n < 0 or n > self._left:
            n = self._left
        data = self._raw.read(n)
        self._left -= len(data)
        return data

    def close(self) -> None:
        if not self.closed:
            try:
                self._raw.close()
            finally:
                super().close()


def _conservative_dest(dest: str) -> list[str]:
    """Okunamaz/tavan-aşan arşivin konservatif hedefi — DİZİN, sonda / ile."""
    if dest:
        return [dest.rstrip("/\\") + "/"]
    return []


def _archive_fileobj(path: str) -> io.RawIOBase:
    """Diskteki arşivi aç; çok büyükse reddet, okumaları sınırla (Tur 6/madde 1)."""
    if os.path.getsize(path) > _ARCHIVE_MAX_FILE:
        raise _ArchiveLimitError("arşiv dosyası çok büyük")
    return _LimitReader(open(path, "rb"), _ARCHIVE_MAX_COMPRESSED)


def _targets_from_tar(args: list[str]) -> list[str]:
    """tar -x[f...] <arşiv> [-C <dir>] — yazılacak yolları SAF Python ile çıkar.

    Tur 5/madde 2: guard harici komut ÇALIŞTIRMAZ (tar -tf yerine stdlib tarfile ile
    arşiv listelenir) — ajan-kontrollü yolda süreç başlatma / tar CVE yüzeyi yoktur;
    guard yeniden yan-etkisiz metin analizidir.
    Tur 6/madde 1: listeleme SINIRLI iştir — okuma/sıkıştırılmış-bayt, üye sayısı ve
    toplam boyut tavanları vardır; tavan aşılınca arşiv okunamaz sayılır.
    Arşiv guard anında diskte değilse (curl -o x.tgz && tar -xf x.tgz zinciri) ve -C
    hedefi varsa, konservatif olarak hedef DİZİN döner (kod bölgesine çıkarma deny);
    -C yoksa [] döner (madde 3'ün kabul edilen artığı — yazım Stop'ta yakalanır).
    """
    archive = None
    dest = ""
    i = 0
    seen_bare = False
    while i < len(args):
        t = args[i]
        if t.startswith("-"):
            if t == "-C" and i + 1 < len(args):
                dest = args[i + 1]
                i += 2
                continue
            if t.startswith("-C"):
                dest = t[2:]
                i += 1
                continue
            if t == "--directory" and i + 1 < len(args):
                dest = args[i + 1]
                i += 2
                continue
            if t.startswith("--directory="):
                dest = t[len("--directory="):]
                i += 1
                continue
            # Tur 6 (kalıntı): arg-alan seçeneklerin argümanlarını arşiv sanma
            # (ör. 'tar --exclude PAT xf a.tgz' — PAT arşiv değildir). -f/--file
            # hariç: onların argümanı arşivin kendisidir.
            if t in _TAR_ARG_OPTS and t not in ("-f", "--file") and i + 1 < len(args):
                i += 2
                continue
            i += 1
            continue
        # Tur 6/madde 2: tiresiz komut jetonu ('xf', 'xzf'...) arşiv DEĞİLDİR —
        # yalnızca harflerden oluşuyorsa ve ilk bare token ise (dosya adı değil).
        if not seen_bare and re.match(r"^x[a-z]*$", t):
            i += 1
            continue
        seen_bare = True
        if archive is None:
            archive = t
        i += 1
    if not archive:
        return []
    out: list[str] = []
    total = 0
    try:
        with tarfile.open(fileobj=_archive_fileobj(archive), mode="r:*") as tf:
            for i, member in enumerate(tf):
                if i >= _ARCHIVE_MAX_MEMBERS:
                    raise _ArchiveLimitError("üye tavanı aşıldı")
                if member.isfile():
                    total += member.size
                    if total > _ARCHIVE_MAX_UNCOMPRESSED:
                        raise _ArchiveLimitError("toplam boyut tavanı aşıldı")
                    out.append(dest.rstrip("/\\") + "/" + member.name if dest
                               else member.name)
    except (OSError, tarfile.TarError, ValueError):
        # Konservatif: hedef DİZİN (sondaki / serbest-bölge eşleşmesini sağlar).
        return _conservative_dest(dest)
    return out


def _targets_from_unzip(args: list[str]) -> list[str]:
    """unzip <arşiv> [hedefler...]  |  unzip -d <dir> <arşiv> — yazılacak yollar.

    Tur 5/madde 2: harici unzip yerine stdlib zipfile; -d hedefi DOĞRU ayrıştırılır
    (önceki sürüm 'unzip -d src x.zip' sırasında src'yi arşiv sanıyordu — baypas).
    Tur 6/madde 1: üye sayısı ve toplam boyut tavanları; tavan aşılınca konservatif.
    Arşiv yoksa ve -d hedefi varsa konservatif hedef-dizini döner; yoksa [] (Stop).
    """
    dest = ""
    rest: list[str] = []
    i = 0
    while i < len(args):
        t = args[i]
        if t == "-d" and i + 1 < len(args):
            dest = args[i + 1]
            i += 2
            continue
        if t.startswith("-d"):
            dest = t[2:]
            i += 1
            continue
        rest.append(t)
        i += 1
    nonflag = [t for t in rest if not t.startswith("-")]
    if not nonflag:
        return []
    archive, files = nonflag[0], nonflag[1:]
    if files:
        return [dest.rstrip("/\\") + "/" + f if dest else f for f in files]
    out: list[str] = []
    try:
        if os.path.getsize(archive) > _ARCHIVE_MAX_FILE:
            raise _ArchiveLimitError("arşiv dosyası çok büyük")
        with zipfile.ZipFile(archive) as zf:
            infos = zf.infolist()
            if len(infos) > _ARCHIVE_MAX_MEMBERS:
                raise _ArchiveLimitError("üye tavanı aşıldı")
            total = 0
            for info in infos:
                if info.is_dir():
                    continue
                total += info.file_size
                if total > _ARCHIVE_MAX_UNCOMPRESSED:
                    raise _ArchiveLimitError("toplam boyut tavanı aşıldı")
                out.append(dest.rstrip("/\\") + "/" + info.filename if dest
                           else info.filename)
    except (OSError, zipfile.BadZipFile, NotImplementedError):
        # Konservatif: hedef DİZİN (sondaki / serbest-bölge eşleşmesini sağlar).
        return _conservative_dest(dest)
    return out


def extract_bash_targets(command: str) -> list[str]:
    """Return file paths the command may write to (only those that matter to the guard)."""
    if not command:
        return []
    targets: list[str] = []
    command = _space_out_redirects(command)
    try:
        tokens = shlex.split(command, posix=True)
    except ValueError:
        return []
    # Komutu && / ; / | üzerinde parçala (TOKEN bazlı: tırnak içindeki ';' güvenlidir);
    # her parçanın son non-flag token'ı cp/mv/install hedefidir.
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
            # & ile başlayan hedef (2>&1) fd-yinelemedir, dosya değildir.
            if i + 1 < len(tokens) and not tokens[i + 1].startswith("&"):
                targets.append(tokens[i + 1])
        elif tok == "tee":
            for j in range(i + 1, len(tokens)):
                if not tokens[j].startswith("-"):
                    targets.append(tokens[j])
                    break
        elif tok == "sed":
            has_i = any(t.startswith("-i") for t in tokens[i + 1:i + 3])
            if has_i:
                tail = [t for t in tokens[i + 1:] if not t.startswith("-") and t != "-e"]
                if len(tail) >= 2:  # ilk non-flag token betiktir; gerisi dosyalar
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
        elif tok == "curl" or tok == "wget":
            if "-o" in tokens[i + 1:i + 3]:
                idx = tokens.index("-o", i + 1)
                if idx + 1 < len(tokens):
                    targets.append(tokens[idx + 1])
        elif tok.startswith("of="):  # dd of=/path
            targets.append(tok[3:])
        elif tok == "git":
            # Tur 4/madde 2: guard'ı atlatan yazma araçları — git apply/am (patch)
            # ve git checkout -- <paths> (indeks/HEAD'ten geri yazma).
            rest = tokens[i + 1:]
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
                targets.extend(t for t in rest[rest.index("--") + 1:]
                               if t and not t.startswith("-"))
        elif tok == "patch":
            # patch [-pN] < d.diff   |   patch [-pN] hedef [d.diff]   |   patch [-pN] d.diff
            # Tur 6/madde 3: diff dosyası GİRDİDİR, yazma hedefi değildir — yazma
            # hedefleri diff içeriğindeki hedef dosyalardır (ve iki-argüman formunda
            # ilk argümanın kendisi). Tek argümanlı formda da diff okunur.
            rest = tokens[i + 1:]
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
            # Tur 6/madde 2: tar ekstraksiyonu tiresiz formu da tanır (GNU/BSD
            # 'tar xf a.tgz', 'tar xzf a.tgz', '-C src' argümanlı 'tar -C src xf').
            # Tur 6 (kalıntı): seçenek SIRASINDAN bağımsız — seçeneklerde break
            # edilmez, arg-alan seçeneklerin argümanları atlanır; böylece
            # 'tar --exclude=* --owner=u xf a.tgz' gibi uzun seçenek zincirlerinde
            # bile komut jetonu pencerenin dışına düşüp tespiti kaçırmaz.
            args_after = tokens[i + 1:]
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
                if t in _TAR_ARG_OPTS:
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
                targets.extend(_targets_from_tar(args_after))
        elif tok == "unzip":
            targets.extend(_targets_from_unzip(tokens[i + 1:]))
        elif tok.startswith("python"):
            for m in re.finditer(
                    r"\bopen\(\s*[\"']([^\"']+)[\"']\s*,\s*[\"'](?:w|a|w\+|a\+)[\"']\s*\)",
                    command):
                targets.append(m.group(1))
            # open('w') dışındaki python yazımları: pathlib, shutil, os.*
            for m in re.finditer(
                    r"\b(?:write_text|write_bytes|touch)\(\s*[\"']([^\"']+)[\"']",
                    command):
                targets.append(m.group(1))
            for m in re.finditer(
                    r"\b(?:copy|copyfile|copy2|move|rename|replace)\s*\([^,]+,\s*"
                    r"[\"']([^\"']+)[\"']",
                    command):
                targets.append(m.group(1))
        elif re.search(r"(?i)\b(python\d*|node|nodejs|perl|ruby|php|deno|bun|lua|Rscript)\b",
                       command) and \
                re.search(r"(?<![A-Za-z0-9])-([a-zA-Z]*[cEer])\b", command):
            # Satır içi yorumlayıcı (node -e, perl -e, ruby -e, php -r...) — desen sayısı
            # sınırsız olduğundan genel yaklaşım: tırnaklı kod-uzantılı yolları hedef say.
            # (sed -e gibi yorumlayıcısız komutlar buraya girmez.) Gerçek güvence Stop'ta
            # kapsam-eşleşmesidir; bu yalnızca erken yakalama katmanıdır.
            for m in re.finditer(r"[\"']([^\"']+\.[A-Za-z0-9]+)[\"']", command):
                if is_code_target(m.group(1)):
                    targets.append(m.group(1))
            # Tur 4/madde 4: uzantısız ama kod-sayılan tırnaklı yollar — CODE_DIR üyesi
            # (bin/tool, src/gizli) ya da yapı-dosyası adı (Makefile, Dockerfile...).
            # require('./src/utils') gibi import-yanlış-pozitifi kabul edilir (fail-closed).
            # Lookahead: yalnızca açıcı tırnak tüketilir — tırnak çiftleri birbirini
            # yutmadığından ('bin/tool' gibi) her tırnaklı yol ayrı görülür.
            for m in re.finditer(r"[\"'](?=([^\"']*)[\"'])", command):
                s = m.group(1)
                if not s or re.search(r"\.[A-Za-z0-9]+$", s):
                    continue  # boş ya da uzantılı — yukarıda ele alındı
                base = pathlib.PurePosixPath(s).name.lower()
                first = s.split("/", 1)[0].lstrip(".")
                if (first in CODE_DIRS and ("/" in s or "\\" in s)) \
                        or base in CODE_BASENAMES:
                    if is_code_target(s):
                        targets.append(s)
    return targets


# --- Kapı ile doğrulama (sessiz) ---
def verify_record(rec: str) -> tuple[int, str]:
    """Run gate verify on a record; return (rc, scope). rc=3 means key not configured."""
    try:
        with contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(io.StringIO()):
            rc = gate.verify(rec)
        return rc, gate.record_scope(rec)
    except Exception:
        return 1, ""


def find_approved(target: str, recs_dir: str | None = None) -> tuple[bool, str]:
    """Find a VERIFIED record whose 'Kod kapsamı' matches target.
    Returns (approved, detail). rc=3 (key missing) records are treated as not verifiable.
    """
    target_rel = norm_path(target).lstrip("/")
    recs_dir = recs_dir or "docs/experiments"
    base = pathlib.Path(recs_dir)
    if not base.is_dir():
        return False, "docs/experiments/ yok"
    key_missing = False
    best = None
    for rec in sorted(base.glob("*.md")):
        if rec.name == "_template.md":
            continue
        rc, scope = verify_record(str(rec))
        if rc == 3:
            key_missing = True
            continue
        if rc != 0:
            continue  # FORGED / ADVISORY-BLOCK / undecided — kod açmaz
        if gate.scope_matches(scope, target_rel):
            return True, f"kayıt {rec} (kapsam eşleşti)"
        if best is None:
            best = f"kayıt {rec} kapsam eşleşmedi"
    if key_missing:
        return False, "kapı anahtarı kurulmamış (python3 run_experiment.py --init-secret)"
    return False, best or "onaylı deney kaydı yok"


# --- PreToolUse: guard ---
# Kapı anahtarı sızıntı işaretleri: anahtarın bulunduğu dizin/anahtar adı/env adı.
# Tur 4/madde 5: '.bmad' artık YALNIZCA bir yol parçası olarak (foo.bmad DEĞİL) yakalanır;
# yanlış-pozitifler (legit .bmad dosyaları, dokümanlardaki 'bmad' sözleri) azalır.
# Wildcard sızma (~/.b?ad/*) string yaklaşımının sınırıdır — madde 1 (belgelenmiş güven sınırı).
_BMD_DIR = re.compile(r"(?i)(?:^|[\\/~\s\"'=])\.bmad(?=[\\/\s\"'*?\[\]]|$)")


def _secret_ref(s: str) -> bool:
    """True if s, bir anahtar sızma işareti taşıyor: gate-key adı, env adı ya da
    yol-parçası olarak .bmad dizini. Substring-eşleme yerine kesin eşleşme."""
    low = s.lower()
    if "gate-key" in low or "bmad_gate_key" in low:
        return True
    return bool(_BMD_DIR.search(s))


# Tur-7/madde 1: anahtar koruması yalnızca komut METNİNİ tarıyordu — ajan, serbest
# bölgeye (scratch/) anahtar-okuyucu betik yazıp `python3 scratch/read.py` ile
# çalıştırabilirdi (komut metni temiz). Kapanış: AJAN serbest yazım bölgelerine
# (scratch/tmp/temp) yazılan KOD dosyalarının İÇERİĞİ anahtar erişim deseni taşıyorsa
# yazım engellenir. Sistem bölgeleri (.claude/, _bmad/) taranmaz — zaten load_secret
# içerirler. Obfuscation/base64 hâlâ kırılamaz; bu belgelenmiş güven sınırıdır.
_AGENT_ZONES = ("scratch/", "tmp/", "temp/")
_KEY_ACCESS_IN_CONTENT = re.compile(
    r"(?i)(?:\.bmad|gate-key|bmad_gate_key|load_secret|gate_token|secret_file|secret_env)")


def _notebook_content_to_text(content) -> str:
    """NotebookEdit içeriğini (hücre listesi, satır listeleri vb.) tarama için
    düz metne normalleştirir; sağlanan yapı ne olursa olsun string döner."""
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return str(content or "")
    parts: list[str] = []
    for cell in content:
        if isinstance(cell, dict):
            src = cell.get("source")
            if src is None:
                src = cell.get("content") or ""
        else:
            src = cell
        if isinstance(src, list):
            src = "".join(str(line) for line in src)
        parts.append(str(src))
    return "\n".join(parts)


def _env_dump_to_file(cmd: str) -> bool:
    """True if cmd bare 'env'/printenv'ü bir DOSYAYA yönlendiriyor (BMAD_GATE_KEY
    sızıntı vektörü). stdout'a döküm serbesttir (diagnostics; konsol sızıntısı
    belgelenmiş sınırdır); dosyaya kopya yasak."""
    try:
        toks = shlex.split(cmd, posix=True)
    except ValueError:
        return False
    if not any(t in ("env", "printenv") for t in toks):
        return False
    for i, t in enumerate(toks):
        if t in (">", ">>") and i + 1 < len(toks) and toks[i + 1] != "/dev/null":
            return True
    return False


INIT_SECRET_CHAIN = re.compile(r"[;&|`$()\n]")  # zincirleme/metashell — erken-allow yok


def is_init_secret_cmd(cmd: str) -> bool:
    """True yalnızca TEK BAŞINA 'python3 <run_experiment.py> --init-secret' komutu için.

    Zincirlenmiş (&&/;/|/newline/$(...)) veya run_experiment.py yerine başka bir betiği
    çağıran hiçbir komut bu kısayola girmez — aksi halde tek satırda bir yazma işlemi
    (ör. 'python3 x.py --init-secret && cat > src/evil.py') onaysız geçerdi.
    """
    if not cmd or not cmd.strip():
        return False
    if INIT_SECRET_CHAIN.search(cmd):
        return False
    try:
        toks = shlex.split(cmd, posix=True)
    except ValueError:
        return False
    if not toks:
        return False
    if toks[0].lower() not in ("python", "python3", "py"):
        return False
    if "--init-secret" not in toks:
        return False
    return any(t.endswith("run_experiment.py") for t in toks)


def cmd_guard(json_in: dict) -> int:
    tool = json_in.get("tool_name", "")
    ti = json_in.get("tool_input", {}) or {}
    root = repo_root(json_in)
    cwd = json_in.get("cwd") or json_in.get("working_dir") or root

    paths: list[str] = []
    cmd = ""
    content = ""
    read_only = False
    if tool in ("Bash", "terminal"):  # OpenHands terminal ≙ Bash
        cmd = ti.get("command") or ""
        content = cmd  # heredoc/inline yazımlar komut metnindedir
    elif tool == "NotebookEdit":
        paths = [ti.get("notebook_path") or ""]
        content = _notebook_content_to_text(ti.get("content"))
    elif tool == "file_editor":  # OpenHands
        sub = ti.get("command") or "view"
        paths = [ti.get("path") or ""]
        read_only = sub == "view"
        if sub == "create":
            content = ti.get("file_text") or ""
        elif sub in ("str_replace", "insert"):
            content = ti.get("new_str") or ""
    elif tool in ("Read", "Write", "Edit", "MultiEdit"):
        read_only = tool == "Read"
        paths = [ti.get("file_path") or ""]
        if tool == "Write":
            content = ti.get("content") or ""
        elif tool == "Edit":
            content = ti.get("new_string") or ""
        elif tool == "MultiEdit":
            content = "\n".join(e.get("new_string") or "" for e in (ti.get("edits") or []))
    elif tool not in ("Read", "Write", "Edit", "MultiEdit", "Bash", "terminal",
                      "NotebookEdit", "file_editor"):
        # Bilinmeyen araç: path alanı taşıyorsa yazma hedefi olarak ele al (fail-temkinli).
        # Okuma araçları (browser_*, think...) path taşımadığından serbest akar.
        unknown_path = ti.get("path") or ti.get("file_path") or ""
        if unknown_path:
            paths = [unknown_path]

    # MultiEdit bazen path'i edits içinde taşır; file_path boşsa ilk düzenin dosyası.
    if not paths and tool == "MultiEdit":
        edits = ti.get("edits") or []
        if edits:
            paths = [edits[0].get("file_path") or ""]

    # --- Kapı anahtarı koruması: anahtar hiçbir araçtan okunamaz ---
    # Bash/terminal: yalnızca tek başına --init-secret kurulumu serbest; anahtar izi
    # taşıyan her komut (cat ~/.bmad/*, g?te-key wildcard'ı dahil) engellenir.
    if tool in ("Bash", "terminal") and cmd:
        if is_init_secret_cmd(cmd):
            return allow()  # anahtar kurulumu serbest
        if _secret_ref(cmd):
            return deny("Kapı anahtarı (gate-key/.bmad/BMAD_GATE_KEY) komut satırında "
                        "okunamaz/kullanılamaz; anahtarı ele geçirmek yasaktır. Kurulum "
                        "için python3 run_experiment.py --init-secret kullan.")
        if _env_dump_to_file(cmd):
            return deny("env/printenv dökümü dosyaya yazılamaz — BMAD_GATE_KEY sızıntı "
                        "vektörü kapatıldı. Ortam dökümü yalnızca ekrana (stdout) serbesttir.")
    for p in paths:
        if _secret_ref(norm_path(p)):
            return deny("Kapı anahtarı konumuna (.bmad/gate-key) erişim yasaktır; "
                        "anahtarı ele geçirmek yasaktır.")

    # Okuma araçları (Read, file_editor view) yalnızca anahtar engelinden geçer;
    # onay mekanizması yazma araçları içindir.
    if read_only:
        return allow()

    if cmd:
        paths += extract_bash_targets(cmd)

    # Tur-7/madde 1: ajan serbest yazım bölgelerine (scratch/, tmp/, temp/) yazılan
    # KOD dosyaları, içerikte anahtar erişim deseni taşıyorsa yasaklanır. Sistem
    # bölgeleri (.claude/, _bmad/) içeriği zaten anahtar kodu içerdiğinden taranmaz.
    if content:
        for p in paths:
            rel = rel_to_root(root, p, cwd)
            if not rel or not rel.startswith(_AGENT_ZONES):
                continue
            if is_code_target(rel) and _KEY_ACCESS_IN_CONTENT.search(content):
                return deny("scratch/tmp/temp bölgesine anahtar erişim kodu (.bmad, "
                            "gate-key, load_secret, gate_token...) yazılamaz — kapı "
                            "anahtarı dolaylaması yasaktır.")

    # Yalnızca KOD hedefleri önemlidir; hedef yoksa veya serbest bölgedeyse geç.
    code_targets = []
    for p in paths:
        rel = rel_to_root(root, p, cwd)
        if rel and is_code_target(rel) and not is_free(rel):
            code_targets.append(rel)

    if not code_targets:
        return allow()

    for t in sorted(set(code_targets)):
        ok, detail = find_approved(t, recs_dir=os.path.join(root, "docs", "experiments"))
        if not ok:
            return deny(_block_reason(t, detail))
    return allow()


def _block_reason(target: str, detail: str) -> str:
    return (f"Metodoloji: {target} yazımı için kapsamı eşleşen ONAYLI (VERIFIED) deney "
            f"kaydı yok ({detail}). Önce bir hipotez kur, ölçüm al, "
            f"run_experiment.py --record docs/experiments/E-XXX.md --run <komut> ile "
            f"ONAYLANDI al ve 'Kod kapsamı' alanına bu dosyayı kapsayan glob yaz. "
            f"Keşif kodu için scratch/ altında yazabilirsin.")


# --- Stop: stop ---
GENERATED_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build",
                  "target", ".next", ".cache", "coverage", ".pytest_cache", ".mypy_cache",
                  ".ruff_cache", ".tox", "out", "vendor"}


def code_outside_free_zones(root: str) -> tuple[list[str], set[str]]:
    """Kapsam dışı kod dosyalarını tara (guard'ın koruduğu bölgeyle aynı tanım).

    Tur 4/madde 3: üretilmiş dizinler (node_modules, vendor, __pycache__...) yürüme
    sırasında BUDANIR ama yolları (gen_dirs) döndürülür; cmd_stop, bu dizinlerin
    yalnızca 'gerçek' (git'te izlenen ya da ignore EDİLMEYEN) dosyalarını geri ekler.
    Böylece vendor/evil.py Stop'un gözünden kaçamaz; node_modules/* ise gürültü sayılmaz.
    """
    found: list[str] = []
    gen_dirs: set[str] = set()
    for dirpath, dirnames, filenames in os.walk(root):
        rel_dir = os.path.relpath(dirpath, root).replace("\\", "/")
        if rel_dir == ".":
            rel_dir = ""
        pruned = [d for d in dirnames if d in GENERATED_DIRS]
        if pruned:
            gen_dirs.update((rel_dir + "/" + d) if rel_dir else d for d in pruned)
            dirnames[:] = [d for d in dirnames if d not in GENERATED_DIRS]
        for fn in filenames:
            rel = f"{rel_dir}/{fn}" if rel_dir else fn
            if is_free(rel):
                continue
            if is_code_target(rel):
                found.append(rel)
    return found, gen_dirs


def _generated_real_files(root: str, gen_dirs: set[str]) -> set[str]:
    """Budanmış üretilmiş dizinlerin altında 'repo'ya ait' dosyalar.

    İzlenen (git ls-files) ya da untracked ama ignore EDİLMEYEN (--others
    --exclude-standard) dosyalar gerçek yazımlardır ve Stop'ta görülmelidir;
    git tarafından ignore edilenler (node_modules/*, *.pyc...) üretim gürültüsüdür.
    Tur 5/madde 5: tüm üretilmiş dizinler TEK pathspec listesiyle sorgulanır
    (2 subprocess, dizin başına değil); git yoksa/başarısızsa konservatif davran:
    o dizindeki HER dosyayı gör.
    """
    if not gen_dirs:
        return set()
    dirs = sorted(gen_dirs)
    real: set[str] = set()
    try:
        for extra in ([], ["--others", "--exclude-standard"]):
            r = subprocess.run(
                ["git", "-C", root, "ls-files", "-z"] + extra + ["--"] + dirs,
                capture_output=True, text=True, encoding="utf-8", timeout=60)
            if r.returncode == 0 and r.stdout:
                real.update(x for x in r.stdout.split("\0") if x)
    except (OSError, subprocess.SubprocessError):
        for gd in dirs:
            d = pathlib.Path(root) / gd
            if d.is_dir():
                for dirpath, dirnames, filenames in os.walk(d):
                    for fn in filenames:
                        rel = os.path.relpath(os.path.join(dirpath, fn),
                                              root).replace("\\", "/")
                        real.add(rel)
    return real


def _audit_write(root: str, entry: dict) -> None:
    """Denetim izine JSON satırı ekle (sessiz; OSError yutulur)."""
    log = pathlib.Path(root) / _log_file()
    try:
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        pass


def _uncovered_code(root: str) -> list[str]:
    """Kapsam dışı (korunan bölgedeki) kod dosyaları — üretilmiş dizin gerçekleri dahil."""
    found, gen_dirs = code_outside_free_zones(root)
    code = list(found)
    for c in sorted(_generated_real_files(root, gen_dirs)):
        if is_code_target(c) and not is_free(c) and c not in code:
            code.append(c)
    return code


def _stop_at_cap(json_in: dict) -> int:
    """8-blok tavanı aşılınca bloklayamayız; kapsam dışı kod varsa kanıt bırak (madde 6)."""
    root = repo_root(json_in)
    code = _uncovered_code(root)
    if code:
        shown = ", ".join(sorted(code)[:6])
        more = " ..." if len(code) > 6 else ""
        msg = (f"Stop 8-blok tavanı aşıldı; kapsam dışı kod varken oturum sonlandı: "
               f"{shown}{more}. Koruma guard'a ve denetim izine dayanır.")
        sys.stderr.write("UYARI: " + msg + "\n")
        _audit_write(root, {
            "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
            "tool": "Stop",
            "event": "stop-at-cap",
            "file": "",
            "cmd": "KAPSAM-DIŞI: " + "; ".join(sorted(code)),
            "note": msg,
        })
    return 0


def cmd_stop(json_in: dict) -> int:
    if json_in.get("stop_hook_active"):
        # 8-block cap'a saygı: artık bloklayamayız. Ama kapsam dışı kod varsa izsiz
        # kaybolmaz — uyarı + hook-audit.log'a kanıt satırı (madde 6).
        return _stop_at_cap(json_in)
    root = repo_root(json_in)
    code = _uncovered_code(root)
    if not code:
        return 0  # guard'ın koruduğu bölgede kod yok — sorun yok

    recs_dir = pathlib.Path(root) / "docs" / "experiments"
    forged = advisory = 0
    verified_scopes: list[tuple[str, str]] = []  # (kayıt, Kod kapsamı)
    if recs_dir.is_dir():
        for rec in sorted(recs_dir.glob("*.md")):
            if rec.name == "_template.md":
                continue
            rc, scope = verify_record(str(rec))
            if rc == 1:
                forged += 1
            elif rc == 2:
                advisory += 1
            elif rc == 0:
                verified_scopes.append((str(rec), scope))

    if forged:
        sys.stderr.write(
            "UYARI: FORGED onay kaydı var (sahte/bozuk jeton). Kapsam dışı kod varken "
            "bu bitişi geçersiz kılar. Kayıtları run_experiment.py --verify ile netleştir.\n")
        return 2
    if not verified_scopes:
        sys.stderr.write(
            "UYARI: kapsam dışı kod var ama doğrulanmış (VERIFIED) deney kaydı yok. "
            "Metodoloji: her kod iddiası ölçümle onaylanmalı. Önce run_experiment.py "
            "ile ONAYLANDI al (docs/experiments/).\n")
        return 2

    # KAPSAM EŞLEŞMESİ: her kapsam dışı kod dosyası, bir VERIFIED onayın 'Kod kapsamı'
    # glob'una girmeli. Guard dosya-başına bunu uygular; Stop da uygulamazsa, guard'ı
    # atlatan yazımlar (inline yorumlayıcı, beyaz-liste kuralı değişikliği) tek bir
    # VERIFIED kayıt varken temiz görünürdü (eski kapsam-körlüğü).
    uncovered = [c for c in code
                 if not any(gate.scope_matches(scope, c) for _, scope in verified_scopes)]
    if uncovered:
        shown = ", ".join(sorted(uncovered)[:6])
        more = " ..." if len(uncovered) > 6 else ""
        sys.stderr.write(
            "UYARI: kapsam dışı kod hiçbir VERIFIED onay kapsamına girmiyor: "
            f"{shown}{more}. Her kod dosyası için 'Kod kapsamı' glob'u eşleşen bir "
            "ONAYLANDI (VERIFIED) kaydı gerekir; guard'ı atlatan yazımlar (inline "
            "yorumlayıcı, kayıt dışı dosyalar) böyle yakalanır.\n")
        return 2

    if advisory:
        sys.stderr.write(
            "NOT: bazı onay kayıtları ADVISORY-BLOCK durumunda (örneklem küçük / metrik "
            "uyuşmazlığı); bu onaylar kod AÇMAZ. Mevcut kod VERIFIED onaylarla "
            "kapsandığı için engel değildir.\n")
    return 0


# --- PostToolUse: audit ---
def cmd_audit(json_in: dict) -> int:
    tool = json_in.get("tool_name", "")
    ti = json_in.get("tool_input", {}) or {}
    root = repo_root(json_in)
    path = ti.get("file_path") or ti.get("notebook_path") or ti.get("path") or ""
    cmd = ti.get("command") or ""
    entry = {
        "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
        "tool": tool,
        "file": norm_path(rel_to_root(root, path, root)),
        "cmd": cmd,
    }
    # Anahtar erişim deseni taşıyan ama guard'dan geçen (dolaylı) komutlar izlenir
    # (madde 1/kanıt katmanı): load_secret/gate_token import'ları gibi string-kaçışlar.
    if cmd and _KEY_ACCESS_IN_CONTENT.search(cmd):
        entry["leak"] = "key-access"
    _audit_write(root, entry)
    return 0


def _emit(decision: str, reason: str = "", additional_context: str = "") -> int:
    """Tek çıkış noktası — _RUNTIME profiline göre karar JSON'u basar.

    decision: 'allow' | 'deny' | 'ask'. OpenHands profilinde 'ask' yoktur;
    soft mod _emit_soft() üzerinden allow+uyarıya çevrilir (aşağıda).
    Dönen exit kodu: deny OpenHands'te 2, Claude'da 0; allow/ask her zaman 0.
    """
    if _RUNTIME == "openhands":
        if decision == "ask":
            decision = "allow"
        out = {"decision": decision}
        if reason:
            out["reason"] = reason
        if additional_context:
            out["additionalContext"] = additional_context
        sys.stdout.write(json.dumps(out, ensure_ascii=False) + "\n")
        return 2 if decision == "deny" else 0
    perm = {"allow": "allow", "deny": "deny", "ask": "ask"}[decision]
    out = {"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                  "permissionDecision": perm,
                                  "permissionDecisionReason": reason or None}}
    if not reason:
        out["hookSpecificOutput"].pop("permissionDecisionReason")
    sys.stdout.write(json.dumps(out, ensure_ascii=False) + "\n")
    return 0


def _emit_soft(reason: str, detail: str = "") -> int:
    """Soft enforcement: Claude'da 'ask' (kullanıcıya sor); OpenHands'te
    'ask' kararı olmadığından allow + görünür uyarı (additionalContext)."""
    full = f"{reason}\n{detail}" if detail else reason
    if _RUNTIME == "openhands":
        return _emit("allow", reason=reason,
                     additional_context=f"METODOLOJI UYARISI (soft gate): {full}")
    return _emit("ask", reason=full)


def allow() -> int:
    return _emit("allow")


def deny(reason: str) -> int:
    return _emit("deny", reason=reason)


# --- Testler ---
def _selfcheck() -> None:
    import os as _os
    import tempfile

    # Bu fonksiyonun gövdesi claude profili sözleşmesiyle yazıldı (deny = rc 0 +
    # stdout'ta '"deny"'). CLI --runtime=openhands ile çağrılırsa _RUNTIME global'i
    # openhands kalır ve deny rc 2 döner — aşağıdaki assert'ler yanlış patlar.
    # Gövdeyi claude'a sabitle; OpenHands profili kendi bölümünde geçiş yapar.
    global _RUNTIME
    _selfcheck_rt = _RUNTIME
    _RUNTIME = "claude"

    def _guard_denies(payload: dict) -> bool:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = cmd_guard(payload)
        return rc == 0 and '"deny"' in buf.getvalue()

    def _guard_allows(payload: dict) -> bool:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = cmd_guard(payload)
        return rc == 0 and '"deny"' not in buf.getvalue()

    # Bölge / hedef tespiti.
    assert is_free("docs/experiments/E-001.md")
    assert is_free("docs/notes/raw/x.png")
    assert not is_free("docs/evil.py")
    assert is_free(".claude/hooks/guard-code.sh")
    assert is_free("scratch/foo.py")
    assert is_free("graft/index.json")
    assert not is_free("src/foo.py")
    assert not is_free("scripts/deploy.py")        # scripts/ geniş muafiyet DEĞİL
    assert not is_free("skills/foo.py")
    assert is_free("scripts/check-methodology.sh")  # yalnızca metodolojinin kendi altyapısı
    assert is_free("scripts/run_experiment.py")
    assert not is_free("src/main.py")
    assert is_code_target("src/foo.py")
    assert is_code_target("src/whatever.txt")      # CODE_DIR üyesi
    assert is_code_target("lib/x.js")
    assert is_code_target("Makefile")
    assert is_code_target("docs/evil.py")           # uzantı kod sayar
    assert not is_code_target("docs/notes/raw/x.png")
    assert not is_code_target("README.md")
    # Beyaz-liste: listelenmeyen diller/uzantılar da koddur; yalnızca veri/markup muaf.
    assert is_code_target("analysis.jl")
    assert is_code_target("data/model.zig")
    assert is_code_target("lib/f.erl")
    assert is_code_target("config.r")
    assert is_code_target("root/script.rs")
    assert not is_code_target("data.csv")
    assert not is_code_target("config.json")
    assert not is_code_target("Cargo.toml")
    assert not is_code_target(".gitignore")
    # Yürütülebilir config (madde 3): workflow/compose/package.json kod sayılır;
    # saf veri JSON/Toml değil.
    assert is_code_target(".github/workflows/ci.yml")
    assert is_code_target(".github/workflows/deploy.yaml")
    assert is_code_target(".gitlab-ci.yml")
    assert is_code_target("azure-pipelines.yml")
    assert is_code_target("docker-compose.yml")
    assert is_code_target("docker-compose.prod.yml")
    assert is_code_target("compose.yaml")
    assert is_code_target("sub/docker-compose.yml")
    assert is_code_target("package.json")
    assert is_code_target("sub/package.json")
    assert is_code_target("scripts/package.json")
    assert not is_code_target("package-lock.json")
    assert not is_code_target("docs/notes/config.yaml")
    assert not is_code_target(".github/ISSUE_TEMPLATE/bug.md")

    # Root kapı şim'i (drift muhafızı — madde 5): scripts/run_experiment.py bir
    # delegasyon şim'i olmalı, ikinci kopya DEĞİL.
    _shim = _HERE.parent.parent / "scripts" / "run_experiment.py"
    if _shim.is_file():
        _stxt = _shim.read_text(encoding="utf-8")
        assert "runpy.run_path" in _stxt, "scripts/run_experiment.py shim değil!"
        assert "bmad-research-experiment/scripts/run_experiment.py" in _stxt, \
            "shim tek doğruluk kaynağına işaret etmiyor!"

    # Bash yazma hedefi tespiti.
    assert "src/x.py" in extract_bash_targets("cat > src/x.py <<EOF\nhi\nEOF")
    assert "src/x.py" in extract_bash_targets("echo hi > src/x.py")
    assert "src/x.py" in extract_bash_targets("echo hi >> src/x.py")
    assert "src/x.py" in extract_bash_targets('python -c "open(\'src/x.py\',\'w\').write(\'x\')"')
    assert "src/x.py" in extract_bash_targets("tee src/x.py <<EOF")
    assert "src/x.py" in extract_bash_targets("sed -i s/a/b/g src/x.py")
    assert "src/x.py" in extract_bash_targets("cp tpl.py src/x.py")
    assert "src/x.py" in extract_bash_targets("mv tpl.py src/x.py")
    assert "src/x.py" in extract_bash_targets("install -m 644 tpl.py src/x.py")
    assert "src/x.py" in extract_bash_targets("curl -o src/x.py http://x")
    assert "src/x.py" in extract_bash_targets("dd if=/dev/zero of=src/x.py")
    # Yorumlayıcı içi yazımlar (guard'ı atlatan inline kod) — erken yakalama katmanı.
    assert "src/x.py" in extract_bash_targets(
        "python -c \"from pathlib import Path; Path('src/x.py').write_text('x')\"")
    assert "src/x.py" in extract_bash_targets(
        "python -c \"import shutil; shutil.copy('a.py','src/x.py')\"")
    assert "src/x.js" in extract_bash_targets(
        "node -e \"require('fs').writeFileSync('src/x.js','x')\"")
    assert "src/x.pl" in extract_bash_targets(
        "perl -e 'open(F,\">\",\"src/x.pl\")'")
    assert "src/x.php" in extract_bash_targets(
        "php -r \"file_put_contents('src/x.php','x')\"")
    assert not extract_bash_targets("node -e \"console.log(1)\"")   # yazma yok
    assert not extract_bash_targets("perl -e 'print 1'")
    assert not extract_bash_targets("sed -e 's/a/b/' src/x.py")     # yorumlayıcı değil
    assert not extract_bash_targets("grep -E 'src/x.py' a.txt")     # okuma/yorumlayıcı yok
    assert not extract_bash_targets("python -c \"print(1)\"")           # yazma yok
    assert "out.txt" in extract_bash_targets("ls > out.txt")
    assert not extract_bash_targets("ls 2>&1 && grep x a | sort")       # stderr yönlendirmesi
    assert "x.py" not in extract_bash_targets("cat a.py")               # okuma

# Tur 4/madde 2: guard'ı atlatan yazma araçları — git apply/checkout, patch, tar, unzip.
    with tempfile.TemporaryDirectory() as _td:
        _pf = _os.path.join(_td, "fix.patch").replace("\\", "/")
        with open(_pf, "w", encoding="utf-8") as fh:
            fh.write("diff --git a/src/x.py b/src/x.py\n"
                     "index 000..111\n"
                     "--- a/src/x.py\n"
                     "+++ b/src/x.py\n"
                     "@@ -0,0 +1 @@\n"
                     "+x\n")
        assert "src/x.py" in extract_bash_targets(f"git apply {_pf}")
        assert "sub/src/x.py" in extract_bash_targets(
            f"git apply --directory=sub {_pf}")
        assert "sub/src/x.py" in _read_patch_targets(_pf, "sub/")
        assert "src/x.py" in extract_bash_targets(f"patch -p1 < {_pf}")
    assert "src/x.py" in extract_bash_targets("git checkout -- src/x.py")
    assert "src/x.py" in extract_bash_targets("git checkout -- src/x.py src/y.py")
    assert "src/y.py" in extract_bash_targets("git checkout -- src/x.py src/y.py")
    assert not extract_bash_targets("git status")
    # Tur 5/madde 2: guard harici komut ÇALIŞTIRMAZ — arşivler saf Python ile listelenir.
    with tempfile.TemporaryDirectory() as _td:
        _td = _td.replace("\\", "/")
        _src = _os.path.join(_td, "src").replace("\\", "/")
        _os.makedirs(_src, exist_ok=True)
        with open(_os.path.join(_src, "x.py").replace("\\", "/"),
                  "w", encoding="utf-8") as fh:
            fh.write("# x\n")
        _tar = _os.path.join(_td, "a.tar").replace("\\", "/")
        with tarfile.open(_tar, "w") as _tf:
            _tf.add(_src, arcname="src")
        assert "src/x.py" in extract_bash_targets(f"tar -xf {_tar}")
        assert "dest/src/x.py" in extract_bash_targets(f"tar -xvf {_tar} -C dest")
        assert "dest/src/x.py" in extract_bash_targets(f"tar -xzf {_tar} -C dest")
        # Tur 5/madde 3: arşiv yoksa ama -C hedefi varsa konservatif hedef-dizini döner
        # (sondaki / dizin işaretidir — serbest-bölge eşleşmesi için).
        assert "src/" in extract_bash_targets("tar -xf nope.tgz -C src")
        assert "scratch/" in extract_bash_targets("tar -xf nope.tgz -C scratch")
        assert not extract_bash_targets("tar -xf nope.tgz")
        _zip = _os.path.join(_td, "a.zip").replace("\\", "/")
        with zipfile.ZipFile(_zip, "w") as _zf:
            _zf.write(_os.path.join(_src, "x.py").replace("\\", "/"), arcname="x.py")
        assert "src/x.py" in extract_bash_targets(f"unzip -d src {_zip}")
        assert "x.py" in extract_bash_targets(f"unzip {_zip}")
        # Tur 5: -d sıralamasından bağımsız (önceki sürüm 'unzip -d src x.zip' baypası).
        assert "src/x.py" in extract_bash_targets(f"unzip {_zip} -d src")
        assert "src/" in extract_bash_targets("unzip -d src nope.zip")  # konservatif
        assert not extract_bash_targets("unzip nope.zip")              # hedef yok -> []
        # Tur 6/madde 2: tiresiz (GNU/BSD) tar ekstraksiyon formları da algılanır.
        assert "src/x.py" in extract_bash_targets(f"tar xf {_tar}")
        assert "dest/src/x.py" in extract_bash_targets(f"tar xzf {_tar} -C dest")
        assert "dest/src/x.py" in extract_bash_targets(f"tar -C dest xf {_tar}")
        assert "dest/src/x.py" in extract_bash_targets(f"tar --extract -C dest {_tar}")
        assert not extract_bash_targets(f"tar tf {_tar}")              # listeleme, yazma yok
        assert not extract_bash_targets(f"tar cf {_tar} src")          # oluşturma, yazma hedefi değil
        # Tur 6 (kalıntı): seçenek sırasından bağımsız + arg-alan seçenekler.
        assert "src/x.py" in extract_bash_targets(f"tar --exclude=x --owner=u xf {_tar}")
        assert "dest/src/x.py" in extract_bash_targets(
            f"tar --exclude PAT xf {_tar} -C dest")   # ayrı-argümanlı --exclude
        assert "dest/src/x.py" in extract_bash_targets(
            f"tar --directory dest xf {_tar}")        # uzun --directory formu
        assert "d2/src/x.py" in extract_bash_targets(f"tar -C d1 -C d2 xf {_tar}")
        # Tur 6/madde 3: patch diff dosyası GİRDİdir — tek argümanlı formda yazma
        # hedefleri diff içeriğinden gelir, diff dosyasının kendisi hedef DEĞİLDİR.
        _dpat = _os.path.join(_td, "d.patch").replace("\\", "/")
        with open(_dpat, "w", encoding="utf-8") as fh:
            fh.write("--- a/src/evil.py\n"
                     "+++ b/src/evil.py\n"
                     "@@ -0,0 +1 @@\n"
                     "+x\n")
        assert "src/evil.py" in extract_bash_targets(f"patch -p1 {_dpat}")
        assert _dpat not in extract_bash_targets(f"patch -p1 {_dpat}")
        assert "src/x.py" in extract_bash_targets(
            f"patch -p1 src/x.py {_dpat}")   # iki argüman: hedef dosya + diff
        assert _dpat not in extract_bash_targets(f"patch -p1 src/x.py {_dpat}")
        # Tur 6/madde 1: arşiv tavanları — üye/boyut tavanı aşılınca konservatif hedef.
        _saved_limits = (globals()["_ARCHIVE_MAX_MEMBERS"],
                         globals()["_ARCHIVE_MAX_UNCOMPRESSED"],
                         globals()["_ARCHIVE_MAX_FILE"])
        globals()["_ARCHIVE_MAX_MEMBERS"] = 2
        globals()["_ARCHIVE_MAX_UNCOMPRESSED"] = 1 << 62
        globals()["_ARCHIVE_MAX_FILE"] = 1 << 62
        _many = _os.path.join(_td, "many.tar").replace("\\", "/")
        with tarfile.open(_many, "w") as _tf:
            for _k in range(3):
                _ti = tarfile.TarInfo(f"m{_k}.py")
                _ti.size = len(b"x\n")
                _tf.addfile(_ti, io.BytesIO(b"x\n"))
        assert "src/" in extract_bash_targets(f"tar -xf {_many} -C src")  # tavan -> konservatif
        _manyz = _os.path.join(_td, "many.zip").replace("\\", "/")
        with zipfile.ZipFile(_manyz, "w") as _zf:
            for _k in range(3):
                _zf.writestr(f"m{_k}.py", b"x\n")
        assert "src/" in extract_bash_targets(f"unzip -d src {_manyz}")  # tavan -> konservatif
        (globals()["_ARCHIVE_MAX_MEMBERS"], globals()["_ARCHIVE_MAX_UNCOMPRESSED"],
         globals()["_ARCHIVE_MAX_FILE"]) = _saved_limits

    # Tur 4/madde 4: inline yorumlayıcı uzantısız ama kod-sayılan yolları da hedef sayar.
    assert "bin/tool" in extract_bash_targets(
        "node -e \"require('fs').writeFileSync('bin/tool','x')\"")
    assert "Makefile" in extract_bash_targets(
        "node -e \"require('fs').writeFileSync('Makefile','x')\"")
    assert not extract_bash_targets("node -e \"import('fs/promises')\"")

    # Boşluksuz yönlendirme (>hedef, >>hedef, 2>hedef) ayrı token olarak yakalanır.
    assert "src/evil.py" in extract_bash_targets("echo x >src/evil.py")
    assert "src/evil.py" in extract_bash_targets("echo x>>src/evil.py")
    assert "out.txt" in extract_bash_targets("ls >out.txt")
    assert "err.log" in extract_bash_targets("cmd 2>err.log")
    assert "src/evil.py" in extract_bash_targets("echo x 2>&1 && cat >src/evil.py")
    # sed çoklu dosya: ilk non-flag token betiktir; gerisi hedefler.
    assert "f1.py" in extract_bash_targets("sed -i 's/a/b/' f1.py f2.py")
    assert "f2.py" in extract_bash_targets("sed -i 's/a/b/' f1.py f2.py")
    assert "f.py" in extract_bash_targets("sed -i -e 's/a/b/' f.py")
    assert "f.py" in extract_bash_targets("sed -i.bak 's/a/b/' f.py")

    # Guard: serbest bölge ve doküman yazımı serbest; kod hedefi deny.
    assert cmd_guard({"tool_name": "Write", "tool_input": {"file_path": "docs/experiments/E-1.md"}}) == 0
    assert cmd_guard({"tool_name": "Write", "tool_input": {"file_path": "scratch/t.py"}}) == 0
    assert cmd_guard({"tool_name": "Write", "tool_input": {"file_path": ".claude/hooks/x.sh"}}) == 0
    assert _guard_denies({"tool_name": "Write", "tool_input": {"file_path": "src/foo.py"}})
    assert _guard_denies({"tool_name": "Bash",
                          "tool_input": {"command": "cat > src/x.py <<EOF\nx\nEOF"}})
    assert _guard_denies({"tool_name": "Bash",
                          "tool_input": {"command": 'python -c "open(\'src/x.py\',\'w\')" '}})
    assert _guard_denies({"tool_name": "Edit", "tool_input": {"file_path": "src/main.py"}})
    assert _guard_denies({"tool_name": "MultiEdit", "tool_input": {"file_path": "src/main.py"}})
    # scripts/ geniş muafiyet kalktı: üretim kodu buraya yazılamaz; yalnızca INFRA_FILES serbest.
    assert _guard_denies({"tool_name": "Write", "tool_input": {"file_path": "scripts/deploy.py"}})
    assert cmd_guard({"tool_name": "Write",
                      "tool_input": {"file_path": "scripts/check-methodology.sh"}}) == 0

    # Kapı anahtarı koruması: anahtar içeren komutlar deny (wildcard dahil).
    assert _guard_denies({"tool_name": "Bash", "tool_input": {"command": "cat ~/.bmad/gate-key"}})
    assert _guard_denies({"tool_name": "Bash", "tool_input": {"command": "echo $BMAD_GATE_KEY"}})
    assert _guard_denies({"tool_name": "Bash", "tool_input": {"command": "cat ~/.bmad/*"}})
    assert _guard_denies({"tool_name": "Bash", "tool_input": {"command": "cat ~/.bmad/g?te-key"}})
    assert _guard_denies({"tool_name": "Bash", "tool_input": {"command": "ls C:/Users/x/.bmad"}})
    # Tur 4/madde 5: '.bmad' yalnızca YOL PARÇASI olarak yakalanır; foo.bmad dosyası
    # ve 'bmad' sözü içeren normal komutlar anahtar-yüzünden ENGEL YEMEZ.
    assert _secret_ref("cat ~/.bmad/gate-key")
    assert _secret_ref("echo $BMAD_GATE_KEY")
    assert _secret_ref("cat ~/.bmad/*")
    assert _secret_ref("ls C:/Users/x/.bmad")
    assert not _secret_ref("cat foo.bmad")
    assert not _secret_ref("cat notes.bmad")
    assert not _secret_ref("docs/bmad/research-methodology.md")
    assert not _secret_ref("echo $MY_VAR")
    assert cmd_guard({"tool_name": "Bash", "tool_input": {"command": "cat foo.bmad"}}) == 0
    # Read aracıyla da anahtar dosyası okunamaz; normal dosya okuması serbest.
    assert _guard_denies({"tool_name": "Read", "tool_input": {"file_path": "/home/user/.bmad/gate-key"}})
    assert _guard_denies({"tool_name": "Read", "tool_input": {"file_path": "~/.bmad/gate-key"}})
    assert cmd_guard({"tool_name": "Read",
                      "tool_input": {"file_path": "docs/bmad/usage-guide.md"}}) == 0
    # Anahtar kurulum komutu yalnızca TEK BAŞINA serbest; zincirlenmiş komut allow almaz.
    assert cmd_guard({"tool_name": "Bash",
                      "tool_input": {"command": "python3 .claude/skills/bmad-research-experiment/"
                                                "scripts/run_experiment.py --init-secret"}}) == 0
    assert cmd_guard({"tool_name": "Bash",
                      "tool_input": {"command": "python3 run_experiment.py --init-secret"}}) == 0
    assert cmd_guard({"tool_name": "Bash",
                      "tool_input": {"command": "python3 x.py --init-secret"}}) == 0
    assert _guard_denies({"tool_name": "Bash",
                          "tool_input": {"command": "python3 run_experiment.py --init-secret && "
                                                    "cat > src/evil.py <<EOF\nx\nEOF"}})
    assert _guard_denies({"tool_name": "Bash",
                          "tool_input": {"command": "python3 run_experiment.py --init-secret; "
                                                    "echo x > src/evil.py"}})
    assert _guard_denies({"tool_name": "Bash",
                          "tool_input": {"command": "bash -c 'python3 run_experiment.py "
                                                    "--init-secret'; cat > src/evil.py"}})
    # deny() JSON çıktısı bozuk karakterlerle bile geçerli JSON üretir.
    _buf = io.StringIO()
    with contextlib.redirect_stdout(_buf):
        deny("satır1\nsatır2\t\"tırnak\" \\ ters")
    import json as _json
    _json.loads(_buf.getvalue())

    # Tur-7/madde 1: ajan serbest bölgesine (scratch/tmp/temp) anahtar-okuyucu KOD
    # yazımı deny; temiz kod scratch'te serbest kalır; sistem bölgesi taranmaz.
    assert _guard_denies({"tool_name": "Write",
                          "tool_input": {"file_path": "scratch/read.py",
                                         "content": "import run_experiment as g\n"
                                                    "print(g.load_secret())"}})
    assert _guard_denies({"tool_name": "Write",
                          "tool_input": {"file_path": "scratch/read.py",
                                         "content": "open(os.path.expanduser('~/.bmad/"
                                                    "gate-key')).read()"}})
    assert _guard_denies({"tool_name": "Edit",
                          "tool_input": {"file_path": "scratch/read.py",
                                         "new_string": "tok = gate_token(...)"}})
    assert _guard_denies({"tool_name": "Bash",
                          "tool_input": {"command": "cat > scratch/read.py <<EOF\n"
                                                    "import run_experiment as g\n"
                                                    "print(g.load_secret())\nEOF"}})
    assert _guard_allows({"tool_name": "Write",
                          "tool_input": {"file_path": "scratch/t.py", "content": "print('x')"}})
    assert _guard_allows({"tool_name": "Write",
                          "tool_input": {"file_path": "scratch/notes.md",
                                         "content": "gate-key hakkında not"}})  # kod değil
    assert _guard_allows({"tool_name": "Write",
                          "tool_input": {"file_path": ".claude/helpers/x.py",
                                         "content": "load_secret()"}})  # sistem bölgesi
    # NotebookEdit içeriği hücre LİSTESİ'dir (string değil) — normalize edilip taranmalı.
    assert _guard_denies({"tool_name": "NotebookEdit",
                          "tool_input": {"notebook_path": "scratch/nb.ipynb",
                                         "content": [{"cell_type": "code",
                                                      "source": ["import run_experiment as g",
                                                                 "print(g.load_secret())"]}]}})
    assert _guard_denies({"tool_name": "NotebookEdit",
                          "tool_input": {"notebook_path": "scratch/nb.ipynb",
                                         "content": [{"cell_type": "markdown",
                                                      "content": "anahtar: .bmad/gate-key"}]}})
    assert _guard_allows({"tool_name": "NotebookEdit",
                          "tool_input": {"notebook_path": "scratch/nb.ipynb",
                                         "content": [{"cell_type": "code",
                                                      "source": ["print('temiz')"]}]}})
    # env-dump dosyaya yazılamaz; stdout dökümü /dev/null serbesttir.
    assert _guard_denies({"tool_name": "Bash",
                          "tool_input": {"command": "env > scratch/e.txt"}})
    assert _guard_denies({"tool_name": "Bash",
                          "tool_input": {"command": "printenv | grep -i bmad > tmp/e.txt"}})
    assert _guard_allows({"tool_name": "Bash", "tool_input": {"command": "env"}})
    assert _guard_allows({"tool_name": "Bash",
                          "tool_input": {"command": "env | grep -i bmad"}})
    assert _guard_allows({"tool_name": "Bash",
                          "tool_input": {"command": "env > /dev/null"}})
    # aygıt hedefi /dev/null kod sayılmaz (whitelist yanlış-pozitif) ama düz kod hedefleri sayılır.
    assert not is_code_target("/dev/null")
    assert is_code_target("dev/bench.py")
    assert is_code_target("scripts/bench.py")

    # Onaylı kayıt: 'Kod kapsamı' eşleşen hedefe yazım serbest; eşleşmeyene deny.
    _old_env = _os.environ.get(gate.SECRET_ENV)
    _os.environ[gate.SECRET_ENV] = "hooks-selfcheck-test-key"
    try:
        with tempfile.TemporaryDirectory() as td:
            rec = _os.path.join(td, "E-900.md")
            tok = gate.gate_token("accuracy >= 0.90", 1.0, "E-900",
                                  gate.load_secret() or b"")
            with open(rec, "w", encoding="utf-8") as fh:
                fh.write("\n".join([
                    "## Deney: E-900 — hooks selfcheck",
                    "- **Tarih:** 13.08.2026",
                    "- **Durum:** tamamlandı",
                    "- **Teori:** t",
                    '- **Hipotez:** H-001: "accuracy >= 0.90"',
                    "- **Ölçüm metrikleri:** accuracy >= 0.90",
                    "- **Deney tasarımı:** birim test",
                    "- **Kod kapsamı:** src/**",
                    "- **Ham sonuçlar:** measured=1.0; n=40",
                    "- **Belirsizlik:** yok",
                    "- **Metrik:** uyumlu",
                    "- **Karar:** ONAYLANDI — H-001: measured=1.0 >= threshold=0.9",
                    f'- **Kapı kanıtı:** measured=1.0 claim="accuracy >= 0.90" {tok}',
                    "- **Sonraki adım:** Kod'a geç",
                    ""]))
            with contextlib.redirect_stdout(io.StringIO()), \
                    contextlib.redirect_stderr(io.StringIO()):
                assert gate.verify(rec) == 0  # kayıt gerçekten VERIFIED
            ok, detail = find_approved("src/foo.py", recs_dir=td)
            assert ok, detail
            ok, detail = find_approved("src/engine/core/x.py", recs_dir=td)
            assert ok, detail
            ok, detail = find_approved("tests/x.py", recs_dir=td)
            assert not ok, detail
            ok, detail = find_approved("src2/x.py", recs_dir=td)
            assert not ok, detail

            # Stop kapsam eşleşmesi: VERIFIED onayın kapsamına giren kod temiz;
            # girmeyen dosya bitişi engeller (kapsam-körlüğü yok).
            _p_root = pathlib.Path(td)
            (_p_root / "docs" / "experiments").mkdir(parents=True, exist_ok=True)
            _tok2 = gate.gate_token("accuracy >= 0.90", 1.0, "E-901",
                                    gate.load_secret() or b"")
            (_p_root / "docs" / "experiments" / "E-901.md").write_text(
                "\n".join([
                    "## Deney: E-901 — hooks selfcheck",
                    "- **Tarih:** 14.08.2026",
                    "- **Durum:** tamamlandı",
                    "- **Teori:** t",
                    '- **Hipotez:** H-001: "accuracy >= 0.90"',
                    "- **Ölçüm metrikleri:** accuracy >= 0.90",
                    "- **Deney tasarımı:** birim test",
                    "- **Kod kapsamı:** src/**",
                    "- **Ham sonuçlar:** measured=1.0; n=40",
                    "- **Belirsizlik:** yok",
                    "- **Metrik:** uyumlu",
                    "- **Karar:** ONAYLANDI — H-001: measured=1.0 >= threshold=0.9",
                    f'- **Kapı kanıtı:** measured=1.0 claim="accuracy >= 0.90" {_tok2}',
                    "- **Sonraki adım:** Kod'a geç",
                    ""]), encoding="utf-8")
            (_p_root / "src" / "engine" / "core").mkdir(parents=True, exist_ok=True)
            (_p_root / "src2").mkdir(parents=True, exist_ok=True)
            (_p_root / "src" / "engine" / "core" / "x.py").write_text("# x", encoding="utf-8")
            (_p_root / ".gitignore").write_text("*.log", encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()), \
                    contextlib.redirect_stderr(io.StringIO()):
                rc_covered = cmd_stop({"cwd": td, "stop_hook_active": False})
            assert rc_covered == 0, f"kapsanan kod stop'u engellememeli, rc={rc_covered}"
            (_p_root / "src2" / "x.py").write_text("# x", encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()), \
                    contextlib.redirect_stderr(io.StringIO()):
                rc_uncovered = cmd_stop({"cwd": td, "stop_hook_active": False})
            assert rc_uncovered == 2, f"kapsam dışı kod stop'u engellemeli, rc={rc_uncovered}"

            # Tur 4/madde 3: GENERATED_DIRS körlüğü — vendor/evil.py (git-ignore EDİLMEYEN)
            # Stop'un gözünden kaçamaz; git-ignore edilen node_modules/* ise üretim
            # gürültüsü sayılıp düşer (SAĞLIKLI selfcheck'in göstermediği senaryo).
            with tempfile.TemporaryDirectory() as td2:
                _p2 = pathlib.Path(td2)
                try:
                    subprocess.run(["git", "-C", td2, "init", "-q"], check=True,
                                   capture_output=True)
                except (OSError, subprocess.SubprocessError):
                    pass
                (_p2 / "docs" / "experiments").mkdir(parents=True, exist_ok=True)
                _tok3 = gate.gate_token("accuracy >= 0.90", 1.0, "E-902",
                                        gate.load_secret() or b"")
                (_p2 / "docs" / "experiments" / "E-902.md").write_text(
                    "\n".join([
                        "## Deney: E-902 — hooks selfcheck",
                        "- **Tarih:** 14.08.2026",
                        "- **Durum:** tamamlandı",
                        "- **Teori:** t",
                        '- **Hipotez:** H-001: "accuracy >= 0.90"',
                        "- **Ölçüm metrikleri:** accuracy >= 0.90",
                        "- **Deney tasarımı:** birim test",
                        "- **Kod kapsamı:** src/**",
                        "- **Ham sonuçlar:** measured=1.0; n=40",
                        "- **Belirsizlik:** yok",
                        "- **Metrik:** uyumlu",
                        "- **Karar:** ONAYLANDI — H-001: measured=1.0 >= threshold=0.9",
                        f'- **Kapı kanıtı:** measured=1.0 claim="accuracy >= 0.90" {_tok3}',
                        "- **Sonraki adım:** Kod'a geç",
                        ""]), encoding="utf-8")
                (_p2 / ".gitignore").write_text("node_modules/\n", encoding="utf-8")
                (_p2 / "node_modules" / "dep").mkdir(parents=True, exist_ok=True)
                (_p2 / "node_modules" / "dep" / "ignored.py").write_text(
                    "# üretilmiş", encoding="utf-8")
                (_p2 / "vendor").mkdir(parents=True, exist_ok=True)
                (_p2 / "vendor" / "evil.py").write_text("# baypas", encoding="utf-8")
                with contextlib.redirect_stdout(io.StringIO()), \
                        contextlib.redirect_stderr(io.StringIO()):
                    rc_gen = cmd_stop({"cwd": td2, "stop_hook_active": False})
                assert rc_gen == 2, \
                    f"ignore-edilmeyen vendor/evil.py stop'u engellemeli, rc={rc_gen}"
                (_p2 / "vendor" / "evil.py").unlink()
                with contextlib.redirect_stdout(io.StringIO()), \
                        contextlib.redirect_stderr(io.StringIO()):
                    rc_clean = cmd_stop({"cwd": td2, "stop_hook_active": False})
                assert rc_clean == 0, \
                    f"yalnızca üretilmiş (ignore) dosya stop'u engellememeli, rc={rc_clean}"
    finally:
        if _old_env is None:
            _os.environ.pop(gate.SECRET_ENV, None)
        else:
            _os.environ[gate.SECRET_ENV] = _old_env

    # Stop: korumalı bölgede kod yok -> temiz. (cwd = repo kökü)
    # Yalnızca repo yerleşiminde anlamlı (plugin kopyasında plugin kökü kendi
    # belgeleri olmayan bir "proje" olur; bu denetim oraya ait değildir).
    if (_HERE.parent.parent / ".claude").is_dir() or (_HERE.parent.parent / "_bmad").is_dir():
        assert cmd_stop({"cwd": str(_HERE.parent.parent), "stop_hook_active": False}) == 0

    # Kalite kapısı + deploy guard: payload ayıklaması tool_input.command'dan.
    # Gerçek Claude Code payload'ında komut tool_input içindedir; top-level
    # 'command' okuyan eski sürüm her zaman allow dönerdi (dead code).
    def _qg_decision(payload: dict, fn) -> str:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            fn(payload)
        for line in buf.getvalue().splitlines():
            try:
                return _json.loads(line)["hookSpecificOutput"]["permissionDecision"]
            except (ValueError, KeyError, TypeError):
                continue
        return ""
    with tempfile.TemporaryDirectory() as _qtd:
        _qdd = _os.path.join(_qtd, "docs", "development")
        _os.makedirs(_qdd)
        _qrec = _os.path.join(_qdd, "QR-902.md")
        with open(_qrec, "w", encoding="utf-8") as _fh:
            _fh.write("# QR-902\n- **Tarih:** 2026-08-02\n- **Karar:** REDDEDİLDİ | ONAYLANDI | REVİZE\n")
        assert _qg_decision(
            {"tool_input": {"command": "git commit -m t"}, "cwd": _qtd},
            cmd_quality_gate) == "ask", "REDDEDİLDİ QR ile git commit ask dönmeli"
        assert _qg_decision(
            {"tool_input": {"command": "ls"}, "cwd": _qtd},
            cmd_quality_gate) == "allow", "git dışı komut pas geçmeli"
        _prec = _os.path.join(_qdd, "PR-902.md")
        with open(_prec, "w", encoding="utf-8") as _fh:
            _fh.write("# PR-902\n- **Tarih:** 2026-08-02\n- **Karar:** HAZIR | BEKLİYOR\n")
        assert _qg_decision(
            {"tool_input": {"command": "terraform apply"}, "cwd": _qtd},
            cmd_deploy_guard) == "ask", "rollback'siz PR ile deploy ask dönmeli"
        assert _qg_decision(
            {"tool_input": {"command": "echo hi"}, "cwd": _qtd},
            cmd_deploy_guard) == "allow", "deploy dışı komut pas geçmeli"
    # Hard gate modu: config hard iken deny dönmeli. _load_hook_enforcement'u
    # geçici hard yap, test et, sonra soft'a geri getir (temizlik).
    _cfg_path = _first_existing([
        _HERE.parent.parent / "_bmad" / "custom" / "config.toml",      # claude
        _HERE.parent.parent / "custom" / "config.toml",                # plugin
    ]) or (_HERE.parent.parent / "_bmad" / "custom" / "config.toml")
    _cfg_orig = _cfg_path.read_text(encoding="utf-8") if _cfg_path.is_file() else ""
    try:
        _cfg_path.parent.mkdir(parents=True, exist_ok=True)
        _cfg_path.write_text('[hooks]\nquality_gate = "hard"\ndeploy_guard = "hard"\n',
                             encoding="utf-8")
        with tempfile.TemporaryDirectory() as _htd:
            _hdd = _os.path.join(_htd, "docs", "development")
            _os.makedirs(_hdd)
            with open(_os.path.join(_hdd, "QR-902.md"), "w", encoding="utf-8") as _fh:
                _fh.write("# QR-902\n- **Tarih:** 2026-08-02\n"
                          "- **Karar:** REDDEDİLDİ | ONAYLANDI | REVİZE\n")
            assert _qg_decision(
                {"tool_input": {"command": "git commit -m t"}, "cwd": _htd},
                cmd_quality_gate) == "deny", "hard modda REDDEDİLDİ QR ile git commit deny dönmeli"
            assert _qg_decision(
                {"tool_input": {"command": "ls"}, "cwd": _htd},
                cmd_quality_gate) == "allow", "hard modda bile git dışı komut allow"
            with open(_os.path.join(_hdd, "PR-902.md"), "w", encoding="utf-8") as _fh:
                _fh.write("# PR-902\n- **Tarih:** 2026-08-02\n"
                          "- **Karar:** HAZIR | BEKLİYOR\n")
            assert _qg_decision(
                {"tool_input": {"command": "terraform apply"}, "cwd": _htd},
                cmd_deploy_guard) == "deny", "hard modda rollback'siz PR ile deploy deny dönmeli"
            assert _qg_decision(
                {"tool_input": {"command": "echo hi"}, "cwd": _htd},
                cmd_deploy_guard) == "allow", "hard modda bile deploy dışı komut allow"
    finally:
        if _cfg_orig:
            _cfg_path.write_text(_cfg_orig, encoding="utf-8")
        elif _cfg_path.is_file():
            _cfg_path.unlink()
    # Config yoksa güvenli varsayılan soft'tur (deny değil).
    with tempfile.TemporaryDirectory() as _etd:
        _edd = _os.path.join(_etd, "docs", "development")
        _os.makedirs(_edd)
        with open(_os.path.join(_edd, "QR-902.md"), "w", encoding="utf-8") as _fh:
            _fh.write("# QR-902\n- **Tarih:** 2026-08-02\n"
                      "- **Karar:** REDDEDİLDİ | ONAYLANDI | REVİZE\n")
        _saved_cfg = _cfg_path.read_text(encoding="utf-8") if _cfg_path.is_file() else ""
        try:
            if _cfg_path.is_file():
                _cfg_path.unlink()
            assert _load_hook_enforcement("quality_gate") == "soft", \
                "config yoksa güvenli varsayılan soft olmalı"
            assert _qg_decision(
                {"tool_input": {"command": "git commit -m t"}, "cwd": _etd},
                cmd_quality_gate) == "ask", "config yoksa soft (ask) dönmeli"
        finally:
            if _saved_cfg:
                _cfg_path.write_text(_saved_cfg, encoding="utf-8")
    # --- OpenHands profili (exit kodu + {"decision"} formatı) ---
    _saved_rt = _RUNTIME
    def _oh_decision(payload, fn):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            rc = fn(payload)
        for line in buf.getvalue().splitlines():
            try:
                d = json.loads(line)
            except ValueError:
                continue
            if isinstance(d, dict) and "decision" in d:
                return d["decision"], rc
        return "", rc
    try:
        _RUNTIME = "openhands"
        # emit katmanı: deny -> exit 2 + JSON decision
        _b = io.StringIO()
        with contextlib.redirect_stdout(_b):
            _rc = _emit("deny", reason="t")
        assert _rc == 2 and json.loads(_b.getvalue())["decision"] == "deny", \
            "OpenHands'de deny exit 2 + decision JSON dönmeli"
        # soft gate: ask -> allow + additionalContext uyarı
        _b = io.StringIO()
        with contextlib.redirect_stdout(_b):
            _rc = _emit_soft("sebep", "detay")
        _j = json.loads(_b.getvalue())
        assert _rc == 0 and _j["decision"] == "allow" and "additionalContext" in _j, \
            "OpenHands soft: allow + additionalContext uyarısı"
        # guard: file_editor create kod hedefine (onaysız) -> deny/exit2
        with tempfile.TemporaryDirectory() as _ohtd:
            assert _oh_decision(
                {"tool_name": "file_editor",
                 "tool_input": {"command": "create", "path": "src/x.py",
                                "file_text": "x=1"},
                 "working_dir": _ohtd},
                cmd_guard)[0] == "deny", "file_editor create (kod) deny dönmeli"
            assert _oh_decision(
                {"tool_name": "file_editor",
                 "tool_input": {"command": "view", "path": "src/x.py"},
                 "working_dir": _ohtd},
                cmd_guard)[0] == "allow", "file_editor view (okuma) allow dönmeli"
            assert _oh_decision(
                {"tool_name": "terminal",
                 "tool_input": {"command": "mkdir -p src && cd src && echo x > y.py"},
                 "working_dir": _ohtd},
                cmd_guard)[0] == "deny", "terminal kod yazımı deny dönmeli"
            d, rc = _oh_decision(
                {"tool_name": "file_editor",
                 "tool_input": {"command": "create", "path": "scratch/x.py",
                                "file_text": "x=1"},
                 "working_dir": _ohtd},
                cmd_guard)
            assert (d, rc) == ("allow", 0), "serbest bölge (scratch) allow"
            # bilinmeyen araç path taşırsa deny; taşımazsa allow
            d, rc = _oh_decision(
                {"tool_name": "browser_navigate", "tool_input": {"url": "http://x"},
                 "working_dir": _ohtd}, cmd_guard)
            assert d == "allow", "browser_* (pathsiz) allow"
            d, rc = _oh_decision(
                {"tool_name": "unknown_tool",
                 "tool_input": {"path": "src/y.py"}, "working_dir": _ohtd}, cmd_guard)
            assert d == "deny", "bilinmeyen araç path taşırsa deny (fail-temkinli)"
    finally:
        _RUNTIME = _saved_rt
    _RUNTIME = _selfcheck_rt
    print("hooks selfcheck OK")


# --- Geliştirme Kanadı Fonksiyonları ---

def cmd_quality_gate(payload: dict) -> int:
    """Quality Gate hook (PreToolUse - Bash).
    
    Git merge/commit/push komutlarını yakalar ve QR kontrolü yapar.
    SOFT ENFORCEMENT: Kontrol eder, sorun varsa 'ask' döner (kullanıcı devam edebilir).
    """
    command = (payload.get("tool_input", {}) or {}).get("command") or ""
    cwd = pathlib.Path(payload.get("cwd") or repo_root(payload)).resolve()
    
    # Git merge/commit/push komutlarını yakala (push main/master dahil)
    git_patterns = [
        r"\bgit\s+(commit|push|merge)\b",
    ]
    
    is_git_action = any(re.search(pat, command, re.IGNORECASE) for pat in git_patterns)
    
    if not is_git_action:
        # Git aksiyonu değilse geç
        return _respond_allow()
    
    # QR kayıtlarını ara
    qr_dir = cwd / "docs" / "development"
    if not qr_dir.exists():
        # Geliştirme klasörü yoksa bilgilendirme
        return _respond_gate("quality_gate",
            "Quality Review kaydı bulunamadı. QR-xxx.md oluşturmak ister misin?",
            "QR klasörü (docs/development) mevcut değil."
        )
    
    qr_files = list(qr_dir.glob("QR-*.md"))
    
    if not qr_files:
        # QR kaydı yoksa uyar
        return _respond_gate("quality_gate",
            "Quality Review kaydı yok. Devam edilsin mi?",
            "Git commit/push öncesi QR kaydı önerilir (test coverage, code review, security scan)."
        )
    
    # En son QR'ı oku
    latest_qr = max(qr_files, key=lambda p: p.stat().st_mtime)
    content = latest_qr.read_text(encoding="utf-8", errors="ignore")
    
    # ONAYLANDI kontrolü (Karar satırına bağlı; enum içinde geçme değil)
    if not _has_decision(content, "ONAYLANDI"):
        return _respond_gate("quality_gate",
            f"{latest_qr.name} henüz ONAYLANDI değil. Devam edilsin mi?",
            "QR kaydı tamamlanmalı ve ONAYLANDI durumuna getirilmelidir."
        )
    
    # Başarılı - geç
    return _respond_allow()


def cmd_deploy_guard(payload: dict) -> int:
    """Deploy Guard hook (PreToolUse - Bash).
    
    Production deploy komutlarını yakalar ve PR kontrolü yapar.
    SOFT ENFORCEMENT: Kontrol eder, sorun varsa 'ask' döner (kullanıcı devam edebilir).
    """
    command = (payload.get("tool_input", {}) or {}).get("command") or ""
    cwd = pathlib.Path(payload.get("cwd") or repo_root(payload)).resolve()
    
    # Deploy komut desenlerini yakala
    deploy_patterns = [
        r"\bkubectl\s+apply\b",
        r"\bhelm\s+(install|upgrade)\b",
        r"\bgit\s+push.*production\b",
        r"\bgit\s+push.*prod\b",
        r"\bdocker\s+push.*:production\b",
        r"\bdocker\s+push.*:prod\b",
        r"\bterraform\s+apply\b",
        r"\bvercel\s+--prod\b",
        r"\bnpm\s+run\s+deploy\b",
        r"\byarn\s+deploy\b",
        r"\bpnpm\s+deploy\b",
    ]
    
    is_deploy = any(re.search(pat, command, re.IGNORECASE) for pat in deploy_patterns)
    
    if not is_deploy:
        # Deploy komutu değilse geç
        return _respond_allow()
    
    # PR kayıtlarını ara
    pr_dir = cwd / "docs" / "development"
    if not pr_dir.exists():
        # Geliştirme klasörü yoksa ciddi uyar
        return _respond_gate("deploy_guard",
            "🚨 Production deploy algılandı ama PR kaydı bulunamadı!",
            "Production Readiness (PR-xxx.md) kaydı ZORUNLUDUR. Rollback planı, monitoring, runbook hazır olmalı."
        )
    
    pr_files = list(pr_dir.glob("PR-*.md"))
    
    if not pr_files:
        # PR kaydı yoksa engellemeye yakın uyar
        return _respond_gate("deploy_guard",
            "🚨 Production deploy için PR kaydı YOK! Devam edilsin mi?",
            "Production Readiness kontrolleri: rollback planı, monitoring, staging test, runbook. PR-xxx.md oluşturulmalıdır."
        )
    
    # En son PR'ı oku
    latest_pr = max(pr_files, key=lambda p: p.stat().st_mtime)
    content = latest_pr.read_text(encoding="utf-8", errors="ignore")
    
    # HAZIR kontrolü (Karar satırına bağlı; bold '**Karar:**' eşleşme sorunu yok)
    if not _has_decision(content, "HAZIR"):
        return _respond_gate("deploy_guard",
            f"🚨 {latest_pr.name} henüz HAZIR değil! Devam edilsin mi?",
            "Production Readiness Kapı 4 kontrollerini tamamla: staging test, rollback planı, monitoring."
        )
    
    # Rollback planı kontrolü (template bölüm başlığı + yöntem alanı)
    if "## Rollback Planı" not in content or "Rollback yöntemi:" not in content:
        return _respond_gate("deploy_guard",
            f"⚠️ {latest_pr.name}'de rollback planı eksik görünüyor. Devam edilsin mi?",
            "Her production deploy için rollback planı ZORUNLUDUR."
        )
    
    # Başarılı - ama yine de bilgilendir
    print(f"\n✅ Production Readiness: {latest_pr.name} HAZIR\n", file=sys.stderr)
    return _respond_allow()


def _has_decision(content: str, expected: str) -> bool:
    """Kayıttaki Karar satırının expected ile başladığını kontrol eder.

    Format: `- **Karar:** <değer> | ...`. Template enum'larında ilk seçenek
    aktif karardır. Kalın işaretli `**Karar:**` yüzünden "Karar: HAZIR" gibi
    bitişik substring'ler hiç eşleşmediği için regex ile alana bakılır.
    """
    pattern = r"- \*\*Karar:\*\*\s*" + re.escape(expected) + r"(?:\||\s|$)"
    return re.search(pattern, content) is not None


def _respond_allow() -> int:
    """Hook'un 'allow' kararını döndür."""
    return _emit("allow")


def _respond_ask(reason: str, detail: str = "") -> int:
    """Hook'un 'ask' kararını döndür (kullanıcıya sor, soft enforcement)."""
    return _emit_soft(reason, detail)


def _load_hook_enforcement(gate: str) -> str:
    """Hook enforcement modunu oku: 'soft' (varsayılan) veya 'hard'.

    Kaynak: _bmad/custom/config.toml [hooks] tablosu (plugin yerleşiminde
    {plugin}/custom/config.toml). gate 'quality_gate' veya 'deploy_guard'.
    Dosya yoksa veya anahtar yoksa 'soft' döner — güvenli varsayılan.
    """
    import tomllib as _tl
    cfg = _first_existing([
        _HERE.parent.parent / "_bmad" / "custom" / "config.toml",      # claude
        _HERE.parent.parent / "custom" / "config.toml",                # plugin
    ])
    if cfg is None or not cfg.is_file():
        return "soft"
    try:
        data = _tl.load(cfg.open("rb"))
    except Exception:
        return "soft"
    val = (data.get("hooks", {}) or {}).get(gate, "soft")
    return "hard" if str(val).strip().lower() == "hard" else "soft"


def _respond_gate(gate: str, reason: str, detail: str = "") -> int:
    """Config'e göre soft (ask / allow+uyarı) veya hard (deny) döndür.

    gate: 'quality_gate' veya 'deploy_guard'. config.toml [hooks] tablosundaki
    değere bakar. 'hard' ise deny (mekanik engel), 'soft' ise ask/uyarı.
    """
    if _load_hook_enforcement(gate) == "hard":
        full_reason = f"{reason}\n{detail}" if detail else reason
        return _emit("deny", reason=full_reason)
    return _respond_ask(reason, detail)


def _parse_runtime() -> None:
    """--runtime=claude|openhands argümanını yakalayın ve listeden çıkar."""
    global _RUNTIME
    for a in list(sys.argv):
        m = re.match(r"--runtime=(claude|openhands)$", a)
        if m:
            _RUNTIME = m.group(1)
            sys.argv.remove(a)


if __name__ == "__main__":
    _parse_runtime()
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    if "--selfcheck" in sys.argv:
        _selfcheck()
        sys.exit(0)
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    if mode == "guard":
        sys.exit(cmd_guard(payload))
    elif mode == "stop":
        sys.exit(cmd_stop(payload))
    elif mode == "audit":
        sys.exit(cmd_audit(payload))
    elif mode == "quality-gate":
        sys.exit(cmd_quality_gate(payload))
    elif mode == "deploy-guard":
        sys.exit(cmd_deploy_guard(payload))
    sys.exit(0)
