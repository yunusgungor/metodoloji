#!/usr/bin/env python3
"""Record-bound mechanical approval gate for the research methodology.

The gate reads the hypothesis threshold FROM the experiment record file, so
the threshold cannot be silently changed at the command line. It is the ONLY
writer of the decision: a record that says ONAYLANDI without a valid GATE-OK
token is forged (detected by --verify).

Flow:
  draft record written (Teori/Hipotez/Ölçüm metrikleri/Deney tasarımı, durum: planlandı)
  -> experiment runs, value measured MECHANICALLY by the gate
  -> run_experiment.py --record <rec> --run "<cmd>" [--raw "<note>"]
        gate executes <cmd>, parses the measured value from its stdout (it never
        trusts an operator-supplied value), compares to the claim, writes
        Ham sonuçlar / Karar / Kapı kanıtı / Sonraki adım / Durum
  -> later: run_experiment.py --verify <rec>   (confirms the decision is genuine)

One measurement, one decision per record. A decided record refuses a re-run;
a new measurement requires a new experiment record.

`--dry-run` previews a decision (parsed claim/threshold, measured value,
PASS/FAIL, Wilson bound, the lines that would be written, and the would-be
GATE-OK token) WITHOUT writing anything to the record. Every format/draft
check must use --dry-run: a gate run without it WRITES a real decision into
the record (E-189 lesson).

Usage:
  run_experiment.py --record docs/experiments/E-001.md --run "<cmd>"
  run_experiment.py --record docs/experiments/E-001.md --run "<cmd>" --dry-run
  run_experiment.py --verify  docs/experiments/E-001.md
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import math
import os
import pathlib
import re
import secrets as _secrets
import shlex
import subprocess
import sys

OPS = {">=": lambda a, b: a >= b, "<=": lambda a, b: a <= b, "==": lambda a, b: a == b,
       ">": lambda a, b: a > b, "<": lambda a, b: a < b}
OP_RE = re.compile(r">=|<=|==|>|<")
QUOTED_CLAIM = re.compile(r'"([^"]+)"')
# A measured value line from a bench script: `metric_accuracy=0.93 (14/15)` or
# `metric_score=0.80`. The gate only trusts a number it parsed from the run's own output.
# group 2 = value; groups 3/4 = optional `(x/y)` sample-size fraction.
MEASURED_RE = re.compile(
    r"(?i)(?:^|\s)([A-Za-z_][\w]*)_(?:accuracy|validity|precision|score|rate|quality)"
    r"\s*=\s*(-?\d+(?:\.\d+)?)(?:\s*\(\s*(\d+)\s*/\s*(\d+)\s*\))?")

# --- GATE-OK jetonu: HMAC-SHA256(anahtar, did|claim|measured). Anahtar repo DIŞINDADIR:
# ~/.bmad/gate-key dosyası veya BMAD_GATE_KEY ortam değişkeni. Anahtar olmadan jeton
# üretilemez; açık kaynaklı betikle elle hesaplanıp sahte kayıt üretme yolu böylece kapanır. ---
SECRET_ENV = "BMAD_GATE_KEY"
SECRET_FILE = str(pathlib.Path.home() / ".bmad" / "gate-key")


class GateError(Exception):
    pass


def load_secret() -> bytes | None:
    """Return the gate key (env overrides file), or None if not configured."""
    env = os.environ.get(SECRET_ENV)
    if env and env.strip():
        return env.strip().encode("utf-8")
    try:
        data = pathlib.Path(SECRET_FILE).read_text(encoding="utf-8").strip()
        if data:
            return data.encode("utf-8")
    except OSError:
        pass
    return None


def require_secret() -> bytes:
    secret = load_secret()
    if secret is None:
        raise GateError(
            "kapı anahtarı yok. Önce çalıştır: python3 run_experiment.py --init-secret "
            f"(yazılır: {SECRET_FILE}) veya {SECRET_ENV} ortam değişkenini kullan.")
    return secret


def init_secret() -> int:
    """Generate a fresh gate key outside the repo. Call once per machine."""
    key = _secrets.token_hex(32)
    path = pathlib.Path(SECRET_FILE)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(key + "\n", encoding="utf-8")
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass  # Windows'ta chmod kısıtlı; içerik dışı repo koruması yeterli
        print(f"GATE-OK anahtarı yazıldı: {path}")
        print("Anahtar repo DIŞINDA tutulur (git'e girmez). Kaybedersen mevcut onaylar")
        print("doğrulanamaz — yeni anahtarla yeni onaylar üretmen gerekir.")
        return 0
    except OSError as exc:
        print(f"HATA: anahtar yazılamadı: {exc}", file=sys.stderr)
        return 2


def check_secret() -> int:
    if load_secret() is not None:
        print(f"[OK] kapı anahtarı mevcut ({SECRET_FILE} veya {SECRET_ENV})")
        return 0
    print(f"[HATA] kapı anahtarı yok. Çalıştır: python3 run_experiment.py --init-secret",
          file=sys.stderr)
    return 1

# Records use the manifesto's Turkish field labels. The gate parses exactly these
# labels; an English-labeled record will be rejected as an incomplete draft. This is
# intentional and matches document_output_language = "Türkçe".
# 'Kod kapsamı' zorunludur: onayın hangi kod dosyalarını açtığını glob'lar söyler.
# guard-code.sh yalnızca kapsamı eşleşen dosyalara yazım izni verir.
REQUIRED_DRAFT = ("Teori", "Hipotez", "Ölçüm metrikleri", "Deney tasarımı", "Kod kapsamı")


def parse_scope(scope: str) -> list[str]:
    """Split a 'Kod kapsamı' value into patterns (comma/whitespace separated)."""
    if not scope:
        return []
    return [p for p in re.split(r"[,\s]+", scope) if p]


def glob_to_regex(pattern: str) -> str:
    """Convert a scope glob to a regex. Semantics:
      '*'  -> one path segment, '**' -> any depth (incl. zero), '?' -> one char.
    Backslashes are normalized to forward slashes first.
    """
    pat = pattern.replace("\\", "/")
    out = ["^"]
    i, n = 0, len(pat)
    while i < n:
        c = pat[i]
        if c == "*":
            if i + 1 < n and pat[i + 1] == "*":
                if i + 2 < n and pat[i + 2] == "/":
                    out.append("(?:[^/]*/)*")
                    i += 3
                else:
                    out.append(".*")
                    i += 2
            else:
                out.append("[^/]*")
                i += 1
            continue
        if c == "?":
            out.append("[^/]")
            i += 1
            continue
        out.append(re.escape(c))
        i += 1
    out.append("$")
    return "".join(out)


def scope_matches(scope: str, target: str) -> bool:
    """True if the record's 'Kod kapsamı' covers the target file path (project-relative)."""
    if not scope or not target:
        return False
    target = target.replace("\\", "/").lstrip("./")
    for pat in parse_scope(scope):
        if re.fullmatch(glob_to_regex(pat), target, re.IGNORECASE):
            return True
    return False


def record_scope(record_path: str) -> str:
    """Return the 'Kod kapsamı' field of a record ('' when missing)."""
    try:
        text = open(record_path, encoding="utf-8").read()
    except OSError:
        return ""
    return record_fields(text).get("Kod kapsamı", "").strip()


# --- Belgesel mod (B/C/D) kayıt doğrulayıcı. Sayısal kapıdan ayrı: mekanik değil,
# ama kayıt EKSİKSİZ ve dürüstlük alanları dolu mu mekanik olarak kontrol eder. ---
DOC_FIELDS = {
    "Bulgu": ("Tarih", "Durum", "Araştırma sorusu", "Bağlam", "Yöntem", "Bulgu",
              "Kanıt", "Karşıt kanıt", "Yorum", "Belirsizlik", "Karar", "Sonraki adım"),
    "Tasarım": ("Tarih", "Durum", "Tasarım sorusu", "Kullanıcı / ihtiyaç", "Senaryo",
                "Tasarım fikri", "Prototip", "Geri bildirim", "Belirsizlik", "Karar",
                "Sonraki adım"),
    "Alan": ("Tarih", "Durum", "Alan sorunu", "Kapsam / bağlam", "Paydaşlar",
             "Koşullar / kısıtlar", "Sistem dinamikleri", "Kanıt", "Belirsizlik",
             "Karar", "Sonraki adım"),
}
# Dürüstlük alanları: boş bırakılamaz (karşıt kanıt, belirsizlik itirafı, kaynak).
HONESTY_FIELDS = {
    "Bulgu": ("Kanıt", "Karşıt kanıt", "Belirsizlik"),
    "Tasarım": ("Geri bildirim", "Belirsizlik"),
    "Alan": ("Kanıt", "Belirsizlik"),
}
DECISION_RE = re.compile(r"^(ONAYLANDI|REDDEDİLDİ|REVİZE|ERTELENDİ)")


def validate_doc(path: str) -> int:
    """Validate a Mod B/C/D record for completeness and honesty. 0=OK, 1=issues, 2=not a doc."""
    try:
        text = open(path, encoding="utf-8").read()
    except OSError as exc:
        print(f"HATA: okunamadı: {path}: {exc}", file=sys.stderr)
        return 2
    fields = record_fields(text)
    if re.search(r"##\s+Deney:", text):
        print("Bu bir Mod A kaydı (E-id) — --validate Mod B/C/D içindir; Mod A için --verify kullan.",
              file=sys.stderr)
        return 2
    kind = None
    for k in ("Bulgu", "Tasarım", "Alan"):
        if re.search(rf"##\s+{k}:", text):
            kind = k
            break
    if kind is None:
        print(f"Tanınmayan kayıt başlığı: {path}", file=sys.stderr)
        return 2

    problems = []
    for f in DOC_FIELDS[kind]:
        val = fields.get(f, "").strip()
        if not val or re.fullmatch(r"<.*>", val):
            problems.append(f"eksik/boş '{f}'")
    karar = fields.get("Karar", "").strip()
    if karar and not re.fullmatch(r"<.*>", karar) and not DECISION_RE.search(karar):
        problems.append(f"Karar biçimi geçersiz: '{karar[:40]}'")
    for f in HONESTY_FIELDS[kind]:
        val = fields.get(f, "").strip()
        if not val or re.fullmatch(r"<.*>", val):
            problems.append(f"dürüstlük alanı '{f}' boş")

    for p in problems:
        print(f"  {path}: {p}")
    if problems:
        print(f"[UYARI] {kind} kaydı eksik: {len(problems)} sorun")
        return 1
    print(f"[OK] {path} — {kind} kaydı eksiksiz ve dürüstlük alanları dolu.")
    return 0


def parse_claim(claim: str) -> tuple[float, str]:
    """From '<metric> <op> <threshold>' -> (threshold, op)."""
    m = OP_RE.search(claim)
    if not m:
        raise ValueError(f"'{claim}' has no supported operator (>, >=, ==, <=, <)")
    op = m.group(0)
    try:
        threshold = float(claim[m.end():].strip())
    except ValueError as exc:
        raise ValueError(f"threshold in '{claim}' is not a number") from exc
    return threshold, op


def evaluate(claim: str, measured: float) -> tuple[bool, str]:
    """Return (passed, human-readable summary). Raises ValueError on bad claim."""
    threshold, op = parse_claim(claim)
    passed = OPS[op](measured, threshold)
    return passed, f"measured={measured} {op} threshold={threshold}"


def record_fields(text: str) -> dict:
    """Extract '- **Field:** value' lines into a dict."""
    out = {}
    for line in text.splitlines():
        m = re.match(r"^\s*-\s*\*\*([^*]+):\*\*\s*(.*)$", line)
        if m:
            out[m.group(1).strip()] = m.group(2).strip()
    return out


def deney_id(text: str) -> str:
    m = re.search(r"##\s+Deney:\s*([\w.\-]+)", text)
    return m.group(1) if m else "E-?"


def hypothesis_claim(hipotez: str) -> tuple[str, str]:
    """From 'H-001: \"accuracy >= 0.90\"' -> (id, claim)."""
    hm = re.search(r"(H-\d+)[:\s]", hipotez)
    hid = hm.group(1) if hm else "H-?"
    m = QUOTED_CLAIM.search(hipotez)
    if m:
        return hid, m.group(1)
    tail = re.search(r"[:\s]+(.+)$", hipotez)
    if tail:
        return hid, tail.group(1).strip()
    raise ValueError("record 'Hipotez' line must look like 'H-001: \"metric >= 0.90\"'")


def gate_token(claim: str, measured: float, did: str, secret: bytes,
               cmd: str | None = None) -> str:
    """GATE-OK token: HMAC-SHA256(secret, 'GATE-OK|did|claim|measured[|cmd_sha256]').

    Secret-gated: without the key the token cannot be reproduced, so a forged
    ONAYLANDI record cannot pass --verify (unlike the old sha1(claim|measured)
    scheme, which anyone with the open-source script could compute).
    cmd: the measurement command. When given, the token binds to the EXACT
    measurement (new-style); editing 'Ölçüm komutu' after approval breaks the
    token. Legacy tokens (cmd=None) keep verifying — tur-7 geriye uyumlu kapanış.
    """
    payload = f"GATE-OK|{did}|{claim}|{measured}"
    if cmd is not None:
        payload += "|" + hashlib.sha256(cmd.encode("utf-8")).hexdigest()
    mac = hmac.new(secret, payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"GATE-OK-{did}-{mac[:32]}"


def wilson_lower(x: int, n: int, z: float = 1.96) -> float:
    """95% Wilson score lower bound for observed x/n successes. 0.0 when n <= 0."""
    if n <= 0:
        return 0.0
    p = x / n
    z2 = z * z
    denom = 1 + z2 / n
    center = (p + z2 / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n)) / denom
    return max(0.0, center - half)


METRIC_SUFFIXES = ("_accuracy", "_validity", "_precision", "_score", "_rate", "_quality")


def metric_stem(name: str) -> str:
    """Strip a known metric suffix: 'llm_overnight_accuracy' -> 'llm_overnight'."""
    for s in METRIC_SUFFIXES:
        if name.endswith(s):
            return name[: -len(s)]
    return name


def claim_metric_name(claim: str) -> str:
    """Metric name before the operator, stemmed: 'llm_overnight_accuracy >= 0.90' -> 'llm_overnight'."""
    m = OP_RE.search(claim)
    if not m:
        return ""
    return metric_stem(claim[: m.start()].strip())


def uncertainty_note(x: int | None, n: int | None, value: float, threshold: float,
                     op: str) -> str:
    """Mechanical rule-4 confession: return the 'Belirsizlik' line content.

    n is advisory, never a rejection. Returns 'yok' when the sample is large enough
    for the threshold, an explanation when it is too small, or 'n bilinmiyor'.
    """
    if n is None or x is None:
        return "n bilinmiyor (örneklem büyüklüğü ayrıştırılamadı)"
    # The count only matters for upper-bound claims: a small sample inflates
    # confidence that the rate >= threshold.
    if op not in (">=", ">"):
        return "yok (alt-sınır claim: örneklem küçüklüğü riski yok)"
    if abs(x / n - value) > 0.02:
        return f"n bilinmiyor (x/y={x}/{n} değer {value} ile tutarsız)"
    lower = wilson_lower(x, n)
    if lower >= threshold:
        return f"yok (n={n}, 95% Wilson alt sınır {lower:.2f} >= eşik {threshold:g})"
    return (f"n={n} (örneklem küçük: 95% Wilson alt sınır {lower:.2f} < eşik {threshold:g})")


def run_and_measure(cmd: str) -> tuple[float, int | None, int | None, str | None]:
    """Run the measurement script; return (value, x, y, metric_stem) from its stdout."""
    try:
        proc = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=600)
    except subprocess.TimeoutExpired as exc:
        raise ValueError(f"measurement run timed out after 600s: {cmd}") from exc
    if proc.returncode != 0:
        raise ValueError(
            f"measurement run exited {proc.returncode}: {cmd}\n{proc.stdout}\n{proc.stderr}")
    m = MEASURED_RE.search(proc.stdout)
    if not m:
        raise ValueError(
            f"could not parse a measured value from the run output: {cmd}\n{proc.stdout}")
    x = int(m.group(3)) if m.group(3) else None
    y = int(m.group(4)) if m.group(4) else None
    # --run mode requires the sample-size denominator: without (x/y) the gate cannot
    # enforce rule 4, and 'n bilinmiyor' would be a bypass of ADVISORY-BLOCK.
    if y is None:
        raise ValueError(
            f"no sample-size denominator '(x/y)' in the run output: {cmd}\n{proc.stdout}")
    return float(m.group(2)), x, y, metric_stem(m.group(1))


# --- Tur-7/madde 2: ölçüm betiği serbest bölgede yaşayamaz ---
# Kapı, ölçümün KENDİSİNİN de metodoloji korumasında olmasını ister. scratch/tmp/temp
# serbest bölgelerdir; oraya yazılan bench ajan tarafından serbestçe uydurulabilirdi.
# Korumalı bölgede yaşayan bench'in kendisi onaylanmış artefakt olur (her değişiklik
# kapıdan geçer). Konsola (stdout) sızıntı ve base64 obfuscation belgelenmiş sınırdır.
_AGENT_BENCH_ZONE = re.compile(r"(?i)(?:^|[/\\])(?:scratch|tmp|temp)(?:[/\\]|$)")
_KNOWN_INTERP = {"python", "python3", "py", "sh", "bash", "zsh", "node", "nodejs",
                 "deno", "bun", "perl", "ruby", "php", "rscript", "uv"}


def _bench_target(cmd: str) -> str | None:
    """Ölçüm komutunun ÇALIŞTIRDIĞI ilk betik/dosya yolu (hedef kontrolü için).

    'python3 src/bench.py data.csv' -> 'src/bench.py' (veri argümanları değil);
    'sh scripts/bench.sh' -> 'scripts/bench.sh'; './bench' -> './bench';
    inline (-c/-m) -> None (dosya hedefi yok).
    """
    try:
        toks = shlex.split(cmd)
    except ValueError:
        return None
    if not toks:
        return None
    i = 0
    base0 = toks[0].replace("\\", "/").split("/")[-1].lower()
    for suf in (".exe", ".sh", ".cmd", ".bat"):
        if base0.endswith(suf):
            base0 = base0[: -len(suf)]
            break
    if base0 in _KNOWN_INTERP:
        i = 1
        if i >= len(toks) or toks[i].startswith("-"):
            return None  # -c / -m / inline — dosya hedefi yok
    return toks[i]


def bench_in_free_zone(cmd: str) -> bool:
    """True if the run command executes a script inside a free zone (scratch/tmp/temp)."""
    bench = _bench_target(cmd)
    return bool(bench and _AGENT_BENCH_ZONE.search(bench.replace("\\", "/")))


def upsert(lines: list[str], prefix: str, value: str) -> list[str]:
    """Replace the first line starting with prefix, or append it. Returns new lines."""
    for i, l in enumerate(lines):
        if l.strip().startswith(prefix):
            lines[i] = f"{prefix} {value}"
            return lines
    lines.append(f"{prefix} {value}")
    return lines


def main() -> int:
    ap = argparse.ArgumentParser(description="Record-bound mechanical approval gate.")
    ap.add_argument("--record", help="path to the experiment record .md")
    ap.add_argument("--run", help="measurement command to execute; the gate parses the "
                                  "measured value from its output (tek mekanik yol)")
    ap.add_argument("--raw", default="", help="extra raw-result note (optional)")
    ap.add_argument("--dry-run", action="store_true",
                    help="preview the decision (measured vs threshold, Wilson bound, "
                         "would-be GATE-OK token) WITHOUT writing to the record")
    ap.add_argument("--verify", action="store_true", help="verify an existing decision")
    ap.add_argument("--init-secret", action="store_true",
                    help="generate the gate key (HMAC secret) outside the repo, once per machine")
    ap.add_argument("--check-secret", action="store_true",
                    help="report whether the gate key is configured")
    ap.add_argument("--validate", metavar="PATH",
                    help="validate a Mod B/C/D (belgesel) record for completeness/honesty")
    args = ap.parse_args()

    if args.init_secret:
        return init_secret()
    if args.check_secret:
        return check_secret()
    if args.validate:
        return validate_doc(args.validate)
    if args.verify:
        if not args.record:
            ap.error("--verify requires --record")
        return verify(args.record)
    if not args.record:
        ap.error("need --record")
    if not args.run:
        ap.error("need --run <measurement command> — kapı ölçümü kendisi çalıştırır; "
                 "operatör beyanlı değer kabul edilmez")

    with open(args.record, encoding="utf-8") as fh:
        text = fh.read()
    fields = record_fields(text)
    for need in REQUIRED_DRAFT:
        if not fields.get(need):
            print(f"ERROR: record missing '{need}' — finish the design draft before measuring.",
                  file=sys.stderr)
            return 2

    did = deney_id(text)
    hid, claim = hypothesis_claim(fields.get("Hipotez", ""))

    # Tur-7/madde 2: ölçüm betiği serbest bölgede (scratch/tmp/temp) yaşayamaz. Kapı,
    # ölçümün KENDİSİNİN de metodoloji korumasında olmasını ister; aksi halde ajan,
    # uydurma bir scratch bench'i ile onay üretebilirdi. (Çalıştırma öncesi reddet.)
    if bench_in_free_zone(args.run):
        print("ERROR: ölçüm betiği serbest bölgede (scratch/tmp/temp) çalıştırılamaz — "
              "kapı, ölçümün kendisinin de metodoloji korumasında olmasını ister. Ölçüm "
              "betiğini korumalı bir dizine (ör. scripts/bench/) taşı; her bench "
              "değişikliği onay kapısından geçer.", file=sys.stderr)
        return 2

    # Şablon yer tutucusu ('<...>') karar DEĞİLDİR — kapı henüz yazmadı. Yalnızca gerçek
    # ONAYLANDI/REDDEDİLDİ değeri "karar verilmiş" sayılır; aksi halde şablon kopyası
    # "already decided" ile reddedilirdi (kayıt-formatı tuzağı).
    karar_val = fields.get("Karar", "").strip()
    if karar_val and not re.fullmatch(r"<.*>", karar_val):
        print(f"ERROR: record already decided ('{karar_val[:60]}'). "
              "Open a new experiment record for a new measurement.", file=sys.stderr)
        return 2

    # Jeton (GATE-OK) HMAC-SHA256(anahtar, ...) ile üretilir — anahtar repo dışında.
    # Karar ancak anahtar kuruluysa yazılır (sahte kayıt üretimi kapanır).
    try:
        secret = require_secret()
    except GateError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    # Ölçüm: kapı komutu KENDİSİ çalıştırır ve değeri çıktıdan ayrıştırır. Operatörün
    # sayı beyan etmesi yoktur — gerçeklik mekaniktir (manifesto: --run kanonik yoldur).
    try:
        val, x, y, run_metric = run_and_measure(args.run)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    try:
        threshold, op = parse_claim(claim)
        passed, summary = evaluate(claim, val)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    # Metric-name cross-check (Kural 1): ölçülen metrik adı (çıktıdan ayrıştırılan)
    # hipotez claim'indeki metrik adıyla karşılaştırılır.
    claim_metric = claim_metric_name(claim)
    measured_metric = run_metric
    metric_mismatch = measured_metric is not None and measured_metric != claim_metric
    if metric_mismatch:
        fate = "would write warning into record (dry-run)" if args.dry_run \
            else "writing warning into record"
        print(f"WARNING: run measured '{measured_metric}', claim names '{claim_metric}'. "
              f"Metric redefinition — {fate}.", file=sys.stderr)

    # Örneklem büyüklüğü: --run modunda payda (x/y) kapı tarafından ayrıştırılır ve
    # zorunludur; 'n bilinmiyor' karar yolu yoktur (ADVISORY-BLOCK baypası kapalı).
    n = y
    if x is None:
        x = int(round(n * val))  # n var ama x yoksa değerden türet (Wilson için)

    belirsizlik = uncertainty_note(x, n, val, threshold, op)

    # Metric cross-check note: 'uyumlu' when the measured metric equals the claimed one,
    # 'UYUMSUZ' on a redefinition (rule-1 spirit, advisory).
    if measured_metric is not None:
        if not metric_mismatch:
            metrik_note = f"uyumlu (ölçülen {measured_metric} == iddia edilen {claim_metric})"
        else:
            metrik_note = (f"UYUMSUZ — ölçülen {measured_metric}, iddia edilen {claim_metric}: "
                           "farklı bir şey ölçüldü (metrik yeniden tanımı)")
    else:
        metrik_note = "n/a"

    # Dry-run: preview the full decision but write NOTHING. This is the only safe
    # way to check a record/format without deciding it — a gate run without --dry-run
    # writes a REAL decision (E-189 lesson).
    if args.dry_run:
        # Mirror the exact lines a real run would write (proper Turkish, verbatim)
        # so the operator sees precisely what will land in the record.
        print(f"[DRY-RUN] {hid}: {summary} -> {'PASS' if passed else 'FAIL'}")
        print(f"[DRY-RUN]   Belirsizlik yazılacak: {belirsizlik}")
        print(f"[DRY-RUN]   Metrik yazılacak: {metrik_note}")
        print(f"[DRY-RUN]   Ölçüm komutu yazılacak: {args.run}")
        if passed:
            tok = gate_token(claim, val, did, secret, args.run)
            print(f"[DRY-RUN]   Karar yazılacak: ONAYLANDI — {hid}: {summary}")
            print(f'[DRY-RUN]   Kapı kanıtı yazılacak: measured={val} claim="{claim}" {tok}')
            print("[DRY-RUN]   Sonraki adım yazılacak: Kod'a geç; "
                  "Durum yazılacak: tamamlandı")
        else:
            print(f"[DRY-RUN]   Karar yazılacak: REDDEDİLDİ — {hid}: {summary} (kapı FAIL)")
            print("[DRY-RUN]   Sonraki adım yazılacak: Teori'ye dön; yeni hipotez için yeni "
                  "deney aç; Durum yazılacak: REDDEDİLDİ")
        print(f"[DRY-RUN] HİÇBİR DEĞİŞİKLİK YAZILMADI — {args.record} dokunulmadı.")
        return 0

    lines = text.splitlines(keepends=False)
    raw_val = f"measured={val}" + (f"; n={n}" if n is not None else "") \
              + (f"; {args.raw}" if args.raw else "")
    lines = upsert(lines, "- **Ham sonuçlar:**", raw_val)
    lines = upsert(lines, "- **Belirsizlik:**", belirsizlik)
    lines = upsert(lines, "- **Metrik:**", metrik_note)
    # Tur-7/madde 2: ölçüm komutu kayda yazılır; yeni-stil jeton bu komuta bağlanır,
    # böylece onay sonrası komutu değiştirmek jetonu kırar (verify reddeder).
    lines = upsert(lines, "- **Ölçüm komutu:**", args.run)

    if passed:
        tok = gate_token(claim, val, did, secret, args.run)
        lines = upsert(lines, "- **Karar:**", f"ONAYLANDI — {hid}: {summary}")
        lines = upsert(lines, "- **Kapı kanıtı:**", f'measured={val} claim="{claim}" {tok}')
        lines = upsert(lines, "- **Sonraki adım:**", "Kod'a geç")
        lines = upsert(lines, "- **Durum:**", "tamamlandı")
        open(args.record, "w", encoding="utf-8").write("\n".join(lines) + "\n")
        print(f"[{hid}] {summary} -> PASS")
        print(f"DECISION: ONAYLANDI  token={tok}")
        print(f"Record updated: {args.record}")
        return 0

    lines = upsert(lines, "- **Karar:**", f"REDDEDİLDİ — {hid}: {summary} (kapı FAIL)")
    lines = upsert(lines, "- **Sonraki adım:**", "Teori'ye dön; yeni hipotez için yeni deney aç")
    lines = upsert(lines, "- **Durum:**", "REDDEDİLDİ")
    open(args.record, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print(f"[{hid}] {summary} -> FAIL")
    print("DECISION: REDDEDİLDİ")
    print(f"Record updated: {args.record}")
    return 1


def verify(path: str) -> int:
    """Return 0 if the record's ONAYLANDI is backed by a genuine gate token, else:
    1 = FORGED / undecided / rejected, 2 = ADVISORY-BLOCK (genuine but no code),
    3 = gate key missing (cannot verify).
    """
    try:
        secret = require_secret()
    except GateError as exc:
        print(f"SECRET-MISSING: {path} — {exc}", file=sys.stderr)
        return 3
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    fields = record_fields(text)
    karar = fields.get("Karar", "").strip()
    kanit = fields.get("Kapı kanıtı", "")

    # Şablon yer tutucusu ('<...>') karar değildir — 'ONAYLANDI' içerse bile (format
    # örneği `<kapı yazar: ONAYLANDI | REDDEDİLDİ — gerekçe>`) FORGED damgası YEMEMELİ;
    # kapı henüz yazmadığı için "undecided" sayılır.
    if re.fullmatch(r"<.*>", karar):
        karar = ""

    if "ONAYLANDI" in karar:
        m = re.search(r'measured=(-?[\d.]+)\s+claim="([^"]+)"\s+(GATE-OK-[\w\-]+)', kanit)
        if not m:
            print(f"FORGED: {path} says ONAYLANDI but has no valid gate evidence.")
            return 1
        measured, claim, tok = float(m.group(1)), m.group(2), m.group(3)
        # Cross-check: the hypothesis claim recorded in the Hipotez field must match
        # the claim the gate actually evaluated. Editing the threshold after approval
        # (then keeping the token) is a forged outcome.
        try:
            _, recorded_claim = hypothesis_claim(fields.get("Hipotez", ""))
        except ValueError as exc:
            print(f"FORGED: record Hipotez cannot be parsed ({exc}).")
            return 1
        if recorded_claim.strip() != claim:
            print(f"FORGED: recorded Hipotez claim '{recorded_claim}' != gate claim '{claim}'.")
            return 1
        # Tur-7/madde 2: jeton, kayıttaki 'Ölçüm komutu'na bağlanır (yeni-stil).
        # Alanı OLAN kayıtta YALNIZCA yeni-stil jeton geçer — alan değiştirilip eski
        # (komut-bağlanmamış) jetonla sürdürmek ya da alanı silip ESKİ jetonu korumak
        # FORGED olur (indirgeme). Alanı OLMAYAN kayıtlar ön-tur-7 kayıtlardır ve eski
        # stil jetonla doğrulanır. (Alan silinip jeton da ANAHTARLA yeniden üretilirse
        # doğrulanır — ama o, anahtarı ele geçirmiş demektir; belgelenmiş güven sınırıdır.)
        cmd_field = fields.get("Ölçüm komutu", "").strip()
        new_tok = gate_token(claim, measured, deney_id(text), secret, cmd_field) if cmd_field \
            else None
        legacy_ok = tok == gate_token(claim, measured, deney_id(text), secret)
        if new_tok is not None and tok == new_tok:
            ok = True
        elif cmd_field:
            ok = False  # alan varken yeni-stil jetonla uyuşmuyor => sahte/indirgeme
        else:
            ok = legacy_ok
        if ok:
            # The token is genuine, but rule 4 (sample size) and rule 1 (metric
            # identity) are mechanically enforced here: a record that confesses a
            # small sample, an unknown sample ('n bilinmiyor'), or a metric mismatch
            # does NOT unlock code.
            belirsizlik = fields.get("Belirsizlik", "").strip()
            metrik = fields.get("Metrik", "").strip()
            blocks = []
            # 'n bilinmiyor' BLOKLAR: örneklem paydası kapı tarafından ayrıştırılır (--run);
            # karar sonrası n'yi sökmek onayı geçersiz kılar. Eski (ön-kural) kayıtlar
            # için güvenli davranış kod önünü açmamaktır.
            if "örneklem küçük" in belirsizlik or "n bilinmiyor" in belirsizlik:
                blocks.append(f"örneklem belirsizliği ({belirsizlik})")
            if metrik and metrik.startswith("UYUMSUZ"):
                blocks.append(f"metrik uyuşmazlığı ({metrik})")
            if blocks:
                print(f"ADVISORY-BLOCK: {path} — ONAYLANDI genuine (token {tok}), "
                      f"but {'; '.join(blocks)}. Fix the experiment before code.")
                return 2
            print(f"VERIFIED: {path} — ONAYLANDI genuine (token {tok}). Code may proceed.")
            return 0
        print(f"FORGED: token {tok} does not match the record's claim/measured/cmd.")
        return 1
    if "REDDEDİLDİ" in karar:
        print(f"{path} — REDDEDİLDİ (no code). Reason: {karar}")
        return 1
    print(f"{path} — undecided (no Karar). Run the gate with --record and --run.")
    return 1


def _selfcheck() -> None:
    import os
    import tempfile

    # Selfcheck sabit bir test anahtarı kullanır (ortam değişkeni yoluyla; dosya
    # yoluna dokunmaz). Sonunda geri alınır.
    _old_env = os.environ.get(SECRET_ENV)
    os.environ[SECRET_ENV] = "selfcheck-test-key"

    assert evaluate("accuracy >= 0.90", 0.93)[0]
    assert not evaluate("accuracy >= 0.90", 0.87)[0]

    # Sample-size helpers.
    assert wilson_lower(35, 35) >= 0.90   # n=35 perfect at >=0.90 clears
    assert wilson_lower(4, 4) < 0.90      # n=4 perfect at >=0.90 does NOT clear
    assert wilson_lower(0, 0) == 0.0      # n<=0 -> 0.0
    m = MEASURED_RE.search("metric_accuracy=0.93 (14/15)")
    assert (m.group(2), m.group(3), m.group(4)) == ("0.93", "14", "15")
    m = MEASURED_RE.search("metric_score=0.80")
    assert (m.group(2), m.group(3), m.group(4)) == ("0.80", None, None)

    # 'Kod kapsamı' glob eşleştirme: '**' her derinlik, '*' tek segment, '?' tek karakter.
    assert scope_matches("src/**", "src/foo.py")
    assert scope_matches("src/**", "src/engine/foo.py")
    assert not scope_matches("src/**", "tests/foo.py")
    assert scope_matches("src/engine/**", "src/engine/core/x.py")
    assert scope_matches("src/*.py", "src/foo.py")
    assert not scope_matches("src/*.py", "src/foo/bar.py")
    assert scope_matches("src/**", "src\\engine\\foo.py")   # Windows ayraçları normalize
    assert scope_matches("lib/**,tools/*", "tools/build.py")
    assert scope_matches("src/engine/**", "src/engine/core/x.py")
    assert not scope_matches("", "src/foo.py")
    assert scope_matches("src/**", "src/foo.py")
    assert glob_to_regex("**").endswith(".*$")

    # Tur-7/madde 2: serbest bölge bench'i reddedilir; korumalı bench serbesttir;
    # jeton ölçüm komutuna bağlanır (cmd param) — komut değişince jeton değişir.
    assert bench_in_free_zone("python3 scratch/bench.py") is True
    assert bench_in_free_zone("python3 tmp/bench.py") is True
    assert bench_in_free_zone("sh scripts/bench.sh") is False
    assert bench_in_free_zone("python3 src/bench.py data.csv") is False
    assert bench_in_free_zone("python3 -c 'print(1)'") is False
    assert bench_in_free_zone(f'"{sys.executable}" "scripts/fake_bench.py"') is False
    assert _bench_target("python3 src/bench.py data.csv") == "src/bench.py"
    assert _bench_target("sh scripts/bench.sh") == "scripts/bench.sh"
    assert _bench_target("python3 -m timeit 'x'") is None
    _tok_a = gate_token("a >= 0.9", 1.0, "E-X", b"k")
    _tok_b = gate_token("a >= 0.9", 1.0, "E-X", b"k", "cmd")
    _tok_c = gate_token("a >= 0.9", 1.0, "E-X", b"k", "cmd2")
    assert _tok_a != _tok_b and _tok_b != _tok_c

    # Tur-7/madde 2: bench'ler kapının KENDİ dizini altında geçici olarak yaşar —
    # OS temp'te (/tmp, %TEMP%) yaşarlarsa serbest-bölge kuralı Linux'ta yanlış
    # pozitif üretir; geçici dizin selfcheck bitince silinir.
    with tempfile.TemporaryDirectory(dir=os.path.dirname(os.path.abspath(__file__)),
                                     prefix="meth-selfcheck-") as td:
        bench = os.path.join(td, "fake_bench.py")
        with open(bench, "w", encoding="utf-8") as fh:
            fh.write('print("fake_accuracy=1.00 (40/40)")\n')
        rec = os.path.join(td, "E-001.md")
        with open(rec, "w", encoding="utf-8") as fh:
            fh.write(
                "## Deney: E-001 — selfcheck\n"
                "- **Durum:** planlandı\n"
                "- **Teori:** test teorisi\n"
                '- **Hipotez:** H-001: "fake_accuracy >= 0.90"\n'
                "- **Ölçüm metrikleri:** fake_accuracy >= 0.90\n"
                "- **Deney tasarımı:** birim test\n"
                "- **Kod kapsamı:** yok\n"
            )
        old = sys.argv
        sys.argv = ["run_experiment.py", "--record", rec,
                    "--run", f'"{sys.executable}" "{bench}"']
        assert main() == 0
        assert verify(rec) == 0  # genuine approval verifies
        forged = os.path.join(td, "E-001-forged.md")
        text = open(rec, encoding="utf-8").read()
        stripped = "\n".join(l for l in text.splitlines()
                             if "- **Kapı kanıtı:**" not in l)
        with open(forged, "w", encoding="utf-8") as fh:
            fh.write(stripped)
        assert verify(forged) == 1  # ONAYLANDI without token is forged
        # Threshold tamper after approval: edit the Hipotez claim, keep the token.
        tampered = os.path.join(td, "E-001-tampered.md")
        swapped = text.replace('H-001: "fake_accuracy >= 0.90"',
                               'H-001: "fake_accuracy >= 0.99"')
        with open(tampered, "w", encoding="utf-8") as fh:
            fh.write(swapped)
        assert verify(tampered) == 1  # edited Hipotez != gate claim is forged
        # Wrong secret: HMAC anahtarını bilmeden jeton yeniden üretilemez -> FORGED.
        wrongkey = os.path.join(td, "E-001-wrongkey.md")
        tok_re = re.search(r"(GATE-OK-[\w\-]+)", text)
        assert tok_re
        fake_tok = gate_token("fake_accuracy >= 0.90", 1.0, "E-001", b"wrong-secret-key")
        with open(wrongkey, "w", encoding="utf-8") as fh:
            fh.write(text.replace(tok_re.group(1), fake_tok))
        assert verify(wrongkey) == 1  # yanlış anahtarla üretilmiş jeton -> FORGED
        # Tur-7/madde 2: onay sonrası 'Ölçüm komutu'nu değiştirmek jetonu kırar (FORGED);
        # alanı silip eski-stil jetonla indirgemek de FORGED kalır (downgrade kapalı).
        cmd_line = re.search(r"- \*\*Ölçüm komutu:\*\* .*", text)
        assert cmd_line
        cmd_tamper = os.path.join(td, "E-001-cmdtamper.md")
        with open(cmd_tamper, "w", encoding="utf-8") as fh:
            fh.write(text.replace(cmd_line.group(0), "- **Ölçüm komutu:** python3 other_bench.py"))
        assert verify(cmd_tamper) == 1
        # Tur-7/madde 2 (secret'sız indirgeme): alanı SİLİP yeni-stil jetonu KORUMAK da
        # FORGED olur — komut-bağlı jeton, alansız kayıtta eski-stil jetonla doğrulanamaz.
        strip = os.path.join(td, "E-001-strip.md")
        with open(strip, "w", encoding="utf-8") as fh:
            fh.write("\n".join(l for l in text.splitlines()
                               if not l.startswith("- **Ölçüm komutu:**")) + "\n")
        assert verify(strip) == 1

        # --run mode: the gate parses the value from the measurement command's output.
        rec2 = os.path.join(td, "E-001-run.md")
        with open(rec2, "w", encoding="utf-8") as fh:
            fh.write(
                "## Deney: E-001 — selfcheck run\n"
                "- **Durum:** planlandı\n"
                "- **Teori:** test teorisi\n"
                '- **Hipotez:** H-001: "fake_accuracy >= 0.90"\n'
                "- **Ölçüm metrikleri:** fake_accuracy >= 0.90\n"
                "- **Deney tasarımı:** birim test\n"
                "- **Kod kapsamı:** yok\n"
            )
        sys.argv = ["run_experiment.py", "--record", rec2,
                    "--run", f'"{sys.executable}" "{bench}"']
        assert main() == 0  # parsed 1.0 >= 0.90 -> PASS
        assert verify(rec2) == 0
        # A script that prints no measured value must fail the gate without touching the record.
        rec3 = os.path.join(td, "E-001-novalue.md")
        with open(rec3, "w", encoding="utf-8") as fh:
            fh.write(
                "## Deney: E-001 — selfcheck novalue\n"
                "- **Durum:** planlandı\n"
                "- **Teori:** test teorisi\n"
                '- **Hipotez:** H-001: "accuracy >= 0.90"\n'
                "- **Ölçüm metrikleri:** accuracy >= 0.90\n"
                "- **Deney tasarımı:** birim test\n"
                "- **Kod kapsamı:** yok\n"
            )
        with open(bench, "w", encoding="utf-8") as fh:
            fh.write('print("hello")\n')
        before = open(rec3, encoding="utf-8").read()
        sys.argv = ["run_experiment.py", "--record", rec3,
                    "--run", f'"{sys.executable}" "{bench}"']
        assert main() == 2  # no measured value -> gate refuses
        assert open(rec3, encoding="utf-8").read() == before  # record untouched

        # Sample-size: small-n warns but still PASSes.
        with open(bench, "w", encoding="utf-8") as fh:
            fh.write('print("fake_accuracy=0.93 (14/15)")\n')
        rec4 = os.path.join(td, "E-001-smalln.md")
        with open(rec4, "w", encoding="utf-8") as fh:
            fh.write(
                "## Deney: E-001 — selfcheck small-n\n"
                "- **Durum:** planlandı\n"
                "- **Teori:** test teorisi\n"
                '- **Hipotez:** H-001: "accuracy >= 0.90"\n'
                "- **Ölçüm metrikleri:** accuracy >= 0.90\n"
                "- **Deney tasarımı:** birim test\n"
                "- **Kod kapsamı:** yok\n"
            )
        sys.argv = ["run_experiment.py", "--record", rec4,
                    "--run", f'"{sys.executable}" "{bench}"']
        assert main() == 0  # 0.93 >= 0.90 still PASSes
        assert "Belirsizlik:** n=15" in open(rec4, encoding="utf-8").read()
        assert verify(rec4) == 2  # small-n blocks code

        # Sample-size: sufficient-n writes 'yok' (affirmative no-warning).
        with open(bench, "w", encoding="utf-8") as fh:
            fh.write('print("fake_accuracy=1.00 (40/40)")\n')
        rec5 = os.path.join(td, "E-001-suff.md")
        with open(rec5, "w", encoding="utf-8") as fh:
            fh.write(
                "## Deney: E-001 — selfcheck sufficient-n\n"
                "- **Durum:** planlandı\n"
                "- **Teori:** test teorisi\n"
                '- **Hipotez:** H-001: "accuracy >= 0.90"\n'
                "- **Ölçüm metrikleri:** accuracy >= 0.90\n"
                "- **Deney tasarımı:** birim test\n"
                "- **Kod kapsamı:** yok\n"
            )
        sys.argv = ["run_experiment.py", "--record", rec5,
                    "--run", f'"{sys.executable}" "{bench}"']
        assert main() == 0
        assert "Belirsizlik:** yok" in open(rec5, encoding="utf-8").read()

        # --run requires the (x/y) denominator: a value-only bench is rejected so
        # 'n bilinmiyor' cannot bypass ADVISORY-BLOCK.
        with open(bench, "w", encoding="utf-8") as fh:
            fh.write('print("fake_score=0.95")\n')
        rec6 = os.path.join(td, "E-001-nounk.md")
        with open(rec6, "w", encoding="utf-8") as fh:
            fh.write(
                "## Deney: E-001 — selfcheck value-only\n"
                "- **Durum:** planlandı\n"
                "- **Teori:** test teorisi\n"
                '- **Hipotez:** H-001: "accuracy >= 0.90"\n'
                "- **Ölçüm metrikleri:** accuracy >= 0.90\n"
                "- **Deney tasarımı:** birim test\n"
                "- **Kod kapsamı:** yok\n"
            )
        before6 = open(rec6, encoding="utf-8").read()
        # Distinct from rec3 ('hello' prints no value at all): this bench DID print a
        # metric value, so the refusal must be specifically the missing-(x/y) error,
        # not the could-not-parse-value error. Capture exit code + stderr in one run.
        import contextlib, io as _io
        _err = _io.StringIO()
        sys.argv = ["run_experiment.py", "--record", rec6,
                    "--run", f'"{sys.executable}" "{bench}"']
        with contextlib.redirect_stderr(_err):
            _rc6 = main()
        assert _rc6 == 2  # no denominator -> gate refuses
        assert "no sample-size denominator" in _err.getvalue()
        assert open(rec6, encoding="utf-8").read() == before6  # record untouched

        # --measured / --metric / --n KALDIRILDI (güven sınırı): kapı ölçümü KENDİSİ
        # çalıştırır; operatör beyanlı değer yoktur. Kural 1 (metrik kimliği) ve Kural 4
        # (örneklem) her onayda mekaniktir — aşağıdaki rec9/rec10 bunu --run ile sınar.

        # Eski (ön-kural) kayıt: 'n bilinmiyor' itirafı + gerçek jeton -> kod BLOKLU (rc=2).
        rec_nunk = os.path.join(td, "E-001-nunk.md")
        text5 = open(rec5, encoding="utf-8").read()
        swapped_nunk = text5.replace(
            "- **Belirsizlik:** yok",
            "- **Belirsizlik:** n bilinmiyor (örneklem büyüklüğü ayrıştırılamadı)")
        with open(rec_nunk, "w", encoding="utf-8") as fh:
            fh.write(swapped_nunk)
        assert verify(rec_nunk) == 2  # n bilinmiyor ARTIK bloklar

        # Mod B (belgesel) doğrulama: eksiksiz kayıt OK, dürüstlük alanı boş -> UYARI.
        doc_ok = os.path.join(td, "B-001-ok.md")
        with open(doc_ok, "w", encoding="utf-8") as fh:
            fh.write("\n".join([
                "## Bulgu: B-001 — selfcheck",
                "- **Tarih:** 13.08.2026",
                "- **Durum:** tamamlandı",
                "- **Araştırma sorusu:** soru",
                "- **Bağlam:** bağlam",
                "- **Yöntem:** yöntem",
                "- **Bulgu:** bulgu",
                "- **Kanıt:** kanıt",
                "- **Karşıt kanıt:** yok",
                "- **Yorum:** yorum",
                "- **Belirsizlik:** küçük örneklem",
                "- **Karar:** ONAYLANDI — bulgu",
                "- **Sonraki adım:** kod",
                ""]))
        assert validate_doc(doc_ok) == 0
        doc_bad = os.path.join(td, "B-001-bad.md")
        with open(doc_bad, "w", encoding="utf-8") as fh:
            fh.write("\n".join([
                "## Bulgu: B-001 — selfcheck bad",
                "- **Tarih:** 13.08.2026",
                "- **Durum:** tamamlandı",
                "- **Araştırma sorusu:** soru",
                "- **Bağlam:** bağlam",
                "- **Yöntem:** yöntem",
                "- **Bulgu:** bulgu",
                "- **Kanıt:** <kanıt>",
                "- **Karşıt kanıt:**",
                "- **Yorum:** yorum",
                "- **Belirsizlik:**",
                "- **Karar:** ONAYLANDI",
                "- **Sonraki adım:** kod",
                ""]))
        assert validate_doc(doc_bad) == 1  # dürüstlük alanları boş -> sorun
        doc_modA = os.path.join(td, "E-002.md")
        with open(doc_modA, "w", encoding="utf-8") as fh:
            fh.write("## Deney: E-002\n- **Teori:** t\n")
        assert validate_doc(doc_modA) == 2  # Mod A --validate kapsamı dışı

        # Metric cross-check: mismatch is warned in the record.
        rec9 = os.path.join(td, "E-001-metmismatch.md")
        with open(rec9, "w", encoding="utf-8") as fh:
            fh.write("""## Deney: E-001 - selfcheck metric mismatch
- **Durum:** planlandi
- **Teori:** test teorisi
- **Hipotez:** H-001: "accuracy >= 0.90"
- **Ölçüm metrikleri:** accuracy >= 0.90
- **Deney tasarımı:** birim test
- **Kod kapsamı:** yok
""")
        with open(bench, "w", encoding="utf-8") as fh:
            fh.write('print("fake_accuracy=0.93 (14/15)")')
        sys.argv = ["run_experiment.py", "--record", rec9,
                    "--run", f'"{sys.executable}" "{bench}"']
        assert main() == 0
        assert "UYUMSUZ — ölçülen fake" in open(rec9, encoding="utf-8").read()
        assert verify(rec9) == 2  # metric mismatch blocks code

        # Metric cross-check: match writes uyumlu.
        rec10 = os.path.join(td, "E-001-metmatch.md")
        with open(rec10, "w", encoding="utf-8") as fh:
            fh.write("""## Deney: E-001 - selfcheck metric match
- **Durum:** planlandi
- **Teori:** test teorisi
- **Hipotez:** H-001: "grounding_accuracy >= 0.90"
- **Ölçüm metrikleri:** grounding_accuracy >= 0.90
- **Deney tasarımı:** birim test
- **Kod kapsamı:** yok
""")
        with open(bench, "w", encoding="utf-8") as fh:
            fh.write('print("grounding_accuracy=0.93 (14/15)")')
        sys.argv = ["run_experiment.py", "--record", rec10,
                    "--run", f'"{sys.executable}" "{bench}"']
        assert main() == 0
        assert "uyumlu (ölçülen grounding" in open(rec10, encoding="utf-8").read()

        # --dry-run: previews the decision WITHOUT writing to the record.
        rec_dry = os.path.join(td, "E-001-dryrun.md")
        with open(rec_dry, "w", encoding="utf-8") as fh:
            fh.write(
                "## Deney: E-001 — selfcheck dry-run\n"
                "- **Durum:** planlandı\n"
                "- **Teori:** test teorisi\n"
                '- **Hipotez:** H-001: "accuracy >= 0.90"\n'
                "- **Ölçüm metrikleri:** accuracy >= 0.90\n"
                "- **Deney tasarımı:** birim test\n"
                "- **Kod kapsamı:** yok\n"
            )
        with open(bench, "w", encoding="utf-8") as fh:
            fh.write('print("fake_accuracy=0.93 (14/15)")')
        before_dry = open(rec_dry, encoding="utf-8").read()
        _out = _io.StringIO()
        sys.argv = ["run_experiment.py", "--record", rec_dry,
                    "--run", f'"{sys.executable}" "{bench}"', "--dry-run"]
        with contextlib.redirect_stdout(_out):
            assert main() == 0
        assert "DRY-RUN" in _out.getvalue()
        assert "PASS" in _out.getvalue()
        assert "GATE-OK-E-001-" in _out.getvalue()  # would-be token previewed
        assert open(rec_dry, encoding="utf-8").read() == before_dry  # untouched
        assert "Karar" not in open(rec_dry, encoding="utf-8").read()
        # Template placeholder: '<...>' Karar (ör. `<kapı yazar: ONAYLANDI | REDDEDİLDİ — gerekçe>`)
        # karar DEĞİLDİR — kapı "already decided" diye reddetmemeli, --verify de FORGED dememeli.
        rec_ph = os.path.join(td, "E-001-placeholder.md")
        with open(rec_ph, "w", encoding="utf-8") as fh:
            fh.write(
                "## Deney: E-001 — selfcheck placeholder\n"
                "- **Tarih:** 13.08.2026\n"
                "- **Durum:** planlandı\n"
                "- **Teori:** test teorisi\n"
                '- **Hipotez:** H-001: "accuracy >= 0.90"\n'
                "- **Ölçüm metrikleri:** accuracy >= 0.90\n"
                "- **Deney tasarımı:** birim test\n"
                "- **Kod kapsamı:** yok\n"
                "- **Ham sonuçlar:** <sayılar — olduğu gibi>\n"
                "- **Belirsizlik:** <kapı yazar: örneklem küçük | yok | n bilinmiyor>\n"
                "- **Metrik:** <kapı yazar: uyumlu | UYUMSUZ | n/a>\n"
                "- **Karar:** <kapı yazar: ONAYLANDI | REDDEDİLDİ — gerekçe>\n"
                "- **Kapı kanıtı:** <kapı yazar: GATE-OK-...>\n"
                "- **Sonraki adım:** <kapı yazar: Kod'a geç | Teori'ye dön>\n"
            )
        _out_ph = _io.StringIO()
        sys.argv = ["run_experiment.py", "--record", rec_ph,
                    "--run", f'"{sys.executable}" "{bench}"', "--dry-run"]
        with contextlib.redirect_stdout(_out_ph):
            assert main() == 0  # placeholder karar bloklamaz
        assert "PASS" in _out_ph.getvalue()
        assert "already decided" not in _out_ph.getvalue()
        # --verify placeholder: undecided, FORGED DEĞİL
        _out_ph2 = _io.StringIO()
        sys.argv = ["run_experiment.py", "--verify", "--record", rec_ph]
        with contextlib.redirect_stdout(_out_ph2):
            assert verify(rec_ph) == 1
        assert "FORGED" not in _out_ph2.getvalue()
        assert "undecided" in _out_ph2.getvalue()
        # dry-run on a FAILing value also writes nothing.
        with open(bench, "w", encoding="utf-8") as fh:
            fh.write('print("fake_accuracy=0.50 (20/40)")')
        before_dry2 = open(rec_dry, encoding="utf-8").read()
        _out2 = _io.StringIO()
        sys.argv = ["run_experiment.py", "--record", rec_dry,
                    "--run", f'"{sys.executable}" "{bench}"', "--dry-run"]
        with contextlib.redirect_stdout(_out2):
            assert main() == 0
        assert "REDDEDİLDİ" in _out2.getvalue()
        assert open(rec_dry, encoding="utf-8").read() == before_dry2  # still untouched
        # dry-run with --run: the bench runs, the record stays untouched.
        with open(bench, "w", encoding="utf-8") as fh:
            fh.write('print("fake_accuracy=0.93 (14/15)")')
        before_dry3 = open(rec_dry, encoding="utf-8").read()
        _out3 = _io.StringIO()
        sys.argv = ["run_experiment.py", "--record", rec_dry,
                    "--run", f'"{sys.executable}" "{bench}"', "--dry-run"]
        with contextlib.redirect_stdout(_out3):
            assert main() == 0
        assert "DRY-RUN" in _out3.getvalue()
        assert "fake" in _out3.getvalue() or "uyumlu" in _out3.getvalue()
        assert open(rec_dry, encoding="utf-8").read() == before_dry3
        # after a real run the record is decided; dry-run then refuses as decided.
        sys.argv = ["run_experiment.py", "--record", rec_dry,
                    "--run", f'"{sys.executable}" "{bench}"']
        assert main() == 0
        before_dry4 = open(rec_dry, encoding="utf-8").read()
        _out4 = _io.StringIO()
        sys.argv = ["run_experiment.py", "--record", rec_dry,
                    "--run", f'"{sys.executable}" "{bench}"', "--dry-run"]
        with contextlib.redirect_stderr(_out4):
            assert main() == 2  # already decided -> refuses (dry-run included)
        assert open(rec_dry, encoding="utf-8").read() == before_dry4

        sys.argv = old
    if _old_env is None:
        os.environ.pop(SECRET_ENV, None)
    else:
        os.environ[SECRET_ENV] = _old_env
    print("selfcheck OK")


if __name__ == "__main__":
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    if "--selfcheck" in sys.argv:
        _selfcheck()
        sys.exit(0)
    sys.exit(main())
