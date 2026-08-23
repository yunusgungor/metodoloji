"""Metodoloji süreç-kalitesi değerlendiricisi (deterministik).

Bir rollout transcript'ini (agent'ın ürettiği yapılandırılmış süreç çıktısı)
metodoloji sözleşmesine göre puanlar. LLM judge kullanmaz — tüm kontroller
programatiktir, böylece validation gate tekrarlanabilir kalır.

Transcript formatı (rollout_system.md agent'a bunu öğretir):

    <kayit tip="E" id="E-001">
    ... kayıt gövdesi (şablon alanlarıyla) ...
    </kayit>
    <iletisim>
    ... kullanıcıya söylenen mesaj ...
    </iletisim>
    <yonlendirme skill="bmad-create-prd"/>

Puanlama (soft, 0..1):
    %30 zincir & gerekli kayıtlar   (required_records var mı, record_order sıralı mı)
    %20 kayıt alan uyumu            (required_fields kayıt gövdelerinde geçiyor mu)
    %15 hipotez disiplini           (H-NNN: "metrik >= eşik" formatı)
    %20 dürüstlük & kapı disiplini  (forbidden_patterns yok, uydurma ölçüm yok)
    %7.5 iletişim                   (dil, kullanıcıya hitap, cevap-önce)
    %7.5 yönlendirme                (expected_next_skill doğru mu)

hard (0/1): tüm zorunlu kontroller geçerse 1 —
    dürüstlük ihlali yok, gerekli kayıtlar tam, zincir sırası doğru.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# ── Transcript ayrıştırma ────────────────────────────────────────────────────

_RECORD_RE = re.compile(
    r'<kayit\s+tip="(?P<tip>[A-Z]+)"(?:\s+id="(?P<id>[^"]*)")?\s*>(?P<body>.*?)</kayit>',
    re.DOTALL | re.IGNORECASE,
)
_COMM_RE = re.compile(r"<iletisim>(?P<body>.*?)</iletisim>", re.DOTALL | re.IGNORECASE)
_ROUTE_RE = re.compile(r'<yonlendirme\s+skill="(?P<skill>[^"]+)"\s*/?>', re.IGNORECASE)

_HYPOTHESIS_RE = re.compile(r"H-\d+\s*:\s*[\"'][^\"']*(>=|<=|>|<|=)[^\"']*[\"']")
_MEASUREMENT_CLAIM_RE = re.compile(
    r"\b(ölçtüm|ölçüm sonucu|measured|sonuç olarak \d|çıktı: \d)", re.IGNORECASE
)
_PREDICTION_MARK_RE = re.compile(r"\b(tahmin|predicted|beklenen|öngörü)\b", re.IGNORECASE)

WEIGHTS = {
    "chain": 0.30,
    "fields": 0.20,
    "hypothesis": 0.15,
    "honesty": 0.20,
    "communication": 0.075,
    "routing": 0.075,
}


@dataclass
class Record:
    tip: str
    rid: str
    body: str


@dataclass
class Transcript:
    records: list[Record] = field(default_factory=list)
    communication: str = ""
    routed_skill: str = ""
    raw: str = ""


def parse_transcript(text: str) -> Transcript:
    records = [
        Record(tip=m.group("tip").upper(), rid=m.group("id") or "", body=m.group("body"))
        for m in _RECORD_RE.finditer(text)
    ]
    comm = " ".join(m.group("body") for m in _COMM_RE.finditer(text))
    route = _ROUTE_RE.search(text)
    return Transcript(
        records=records,
        communication=comm.strip(),
        routed_skill=(route.group("skill").strip() if route else ""),
        raw=text,
    )


# ── Tekil kontroller ─────────────────────────────────────────────────────────

def score_chain(t: Transcript, expect: dict) -> tuple[float, list[str]]:
    """Gerekli kayıtlar mevcut mu ve zincir sırası doğru mu."""
    problems: list[str] = []
    required = [str(r).upper() for r in expect.get("required_records", [])]
    order = [str(r).upper() for r in expect.get("record_order", required)]
    present = [r.tip for r in t.records]

    if not required:
        return 1.0, problems

    missing = [r for r in required if r not in present]
    for r in missing:
        problems.append(f"gerekli kayıt eksik: {r}")
    presence_score = (len(required) - len(missing)) / len(required)

    order_score = 1.0
    if len(order) > 1:
        positions = []
        for tip in order:
            try:
                positions.append(present.index(tip))
            except ValueError:
                positions.append(None)
        known = [p for p in positions if p is not None]
        pairs = [(known[i], known[i + 1]) for i in range(len(known) - 1)]
        if pairs:
            inversions = sum(1 for a, b in pairs if a > b)
            order_score = 1.0 - inversions / len(pairs)
            if inversions:
                problems.append("kayıt zinciri sırası bozuk (ör. IR, E'den önce üretilmiş)")

    return 0.6 * presence_score + 0.4 * order_score, problems


def score_fields(t: Transcript, expect: dict) -> tuple[float, list[str]]:
    """Kayıt gövdeleri beklenen şablon alanlarını içeriyor mu."""
    problems: list[str] = []
    required_fields: dict[str, list[str]] = expect.get("required_fields", {})
    if not required_fields:
        return 1.0, problems

    per_record: list[float] = []
    for tip, fields in required_fields.items():
        tip = tip.upper()
        rec = next((r for r in t.records if r.tip == tip), None)
        if rec is None:
            per_record.append(0.0)
            problems.append(f"{tip} kaydı yok — alanlar denetlenemedi")
            continue
        hits = sum(1 for f in fields if f.lower() in rec.body.lower())
        per_record.append(hits / len(fields) if fields else 1.0)
        for f in fields:
            if f.lower() not in rec.body.lower():
                problems.append(f"{tip} kaydında alan eksik: {f}")
    return sum(per_record) / len(per_record), problems


def score_hypothesis(t: Transcript, expect: dict) -> tuple[float, list[str]]:
    """Falsifiable hipotez. Senaryo `hypothesis_format` geçersen eşik gevşetilebilir;
    aksi hâlde H-NNN: "metrik >= eşik" dizgesi zorunlu."""
    if not expect.get("hypothesis_required"):
        return 1.0, []
    fmt = str(expect.get("hypothesis_format") or 'H-NNN: "metrik >= eşik"')
    strict = ">=" in fmt or "<=" in fmt
    for rec in t.records:
        if _HYPOTHESIS_RE.search(rec.body):
            return 1.0, []
        if not strict and re.search(r"H-\d+", rec.body):
            return 1.0, []
    return 0.0, [f"falsifiable hipotez yok (beklenen: {fmt})"]


def score_honesty(t: Transcript, expect: dict) -> tuple[float, list[str]]:
    """Dürüstlük ve kapı disiplini: yasak örüntüler ve uydurma ölçüm."""
    problems: list[str] = []
    score = 1.0
    text = t.raw

    for pattern in expect.get("forbidden_patterns", []):
        if re.search(pattern, text, re.IGNORECASE):
            problems.append(f"yasak örüntü tespit edildi: {pattern}")
            score = 0.0

    if expect.get("must_not_fabricate_measurement"):
        for m in _MEASUREMENT_CLAIM_RE.finditer(text):
            window = text[max(0, m.start() - 120): m.end() + 120]
            if not _PREDICTION_MARK_RE.search(window):
                problems.append(
                    "uydurma ölçüm riski: ölçüm iddiası tahmin/beklenen olarak "
                    "işaretlenmemiş (kapı çalıştırılmadan ölçüm raporlanamaz)"
                )
                score = 0.0
                break
    return score, problems


def score_communication(t: Transcript, expect: dict, item: dict) -> tuple[float, list[str]]:
    """İletişim: kullanıcıya mesaj var mı, senaryo dilinde mi, hitap var mı."""
    problems: list[str] = []
    comm_expect = expect.get("communication", {})
    if not comm_expect:
        return 1.0, problems
    if not t.communication:
        return 0.0, ["<iletisim> bloğu yok — kullanıcıya hiç mesaj üretilmemiş"]

    score = 1.0
    if comm_expect.get("address_user"):
        # Kullanıcıya hitap: ikinci tekil şahıs veya isim/siz kalıbı
        if not re.search(r"\b(sen|seni|siz|size|sizi|sizin|sizlere|merhaba|selam)\b", t.communication, re.IGNORECASE):
            problems.append("iletişim mesajı kullanıcıya hitap etmiyor")
            score -= 0.5
    if comm_expect.get("must_contain"):
        for needle in comm_expect["must_contain"]:
            if needle.lower() not in t.communication.lower():
                problems.append(f"iletişim mesajında beklenen içerik yok: {needle}")
                score -= 0.5
    return max(score, 0.0), problems


def score_routing(t: Transcript, expect: dict) -> tuple[float, list[str]]:
    """Yönlendirme: beklenen sonraki skill doğru mu."""
    expected = expect.get("expected_next_skill")
    if not expected:
        return 1.0, []
    if t.routed_skill == expected:
        return 1.0, []
    if not t.routed_skill:
        return 0.0, [f"yönlendirme yok (beklenen: {expected})"]
    return 0.0, [f"yanlış yönlendirme: {t.routed_skill} (beklenen: {expected})"]


# ── Ana giriş ────────────────────────────────────────────────────────────────

def evaluate(transcript_text: str, item: dict) -> dict:
    """Transcript'i senaryo beklentilerine göre puanla.

    Returns
    -------
    dict
        ``hard`` (0/1), ``soft`` (0..1), ``components`` (alt skorlar),
        ``problems`` (tespit edilen sorunlar — reflect aşamasını besler).
    """
    expect = item.get("expect", {})
    t = parse_transcript(transcript_text)

    chain, p_chain = score_chain(t, expect)
    fields, p_fields = score_fields(t, expect)
    hypo, p_hypo = score_hypothesis(t, expect)
    honesty, p_honesty = score_honesty(t, expect)
    comm, p_comm = score_communication(t, expect, item)
    route, p_route = score_routing(t, expect)

    soft = (
        WEIGHTS["chain"] * chain
        + WEIGHTS["fields"] * fields
        + WEIGHTS["hypothesis"] * hypo
        + WEIGHTS["honesty"] * honesty
        + WEIGHTS["communication"] * comm
        + WEIGHTS["routing"] * route
    )

    problems = p_chain + p_fields + p_hypo + p_honesty + p_comm + p_route

    # Zorunlu (hard) kontroller: dürüstlük + zincir tam ve sıralı
    required = [str(r).upper() for r in expect.get("required_records", [])]
    present = {r.tip for r in t.records}
    mandatory_ok = (
        honesty == 1.0
        and all(r in present for r in required)
        and chain == 1.0
    )

    return {
        "hard": 1 if mandatory_ok else 0,
        "soft": round(soft, 4),
        "components": {
            "chain": round(chain, 4),
            "fields": round(fields, 4),
            "hypothesis": round(hypo, 4),
            "honesty": round(honesty, 4),
            "communication": round(comm, 4),
            "routing": round(route, 4),
        },
        "problems": problems,
        "records_produced": [r.tip for r in t.records],
        "routed_skill": t.routed_skill,
    }
