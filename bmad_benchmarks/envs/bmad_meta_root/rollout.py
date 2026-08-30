"""Rollout + scoring for bmad-meta-root benchmark.

Task: given an operation, classify correct root ({project-root} vs
{metodoloji-root}) and direction (output vs read).
Scoring: hard = both root and direction correct; soft = per-component.
"""

import json
import pathlib
import re
import sys

from skillopt.model import chat_target


# Words that signal the model is unsure — a classification that hedges is not a
# correct root answer even if it happens to echo a keyword from the prompt.
# ("belirsiz"/"kararsız" are deliberately excluded: a correct answer can say
# "belirsizlik içermez" — only strong hedging signals are fatal.)
_UNCERTAINTY_RE = re.compile(
    r"(?:bilmiyorum|emin değilim|emin degilim|farkında değilim|"
    r"not sure|unsure|i don't know|i dont know|unknown|sanırım|muhtemelen|"
    r"tahminen|tahmin ederim|zannet|kararsızım)"
)


def _score(output_text: str, item: dict) -> tuple[int, float]:
    lower = output_text.lower()
    checks = []

    # A hedged answer is never a correct classification — it signals the model
    # does not actually know the root, even if it repeats a keyword.
    if _UNCERTAINTY_RE.search(lower):
        return 0, 0.0

    # No minimum-length gate: a short but CORRECT classification ("project-root
    # output", "metodoloji-root oku") must pass. Echo/empty answers are already
    # rejected below because they lack the expected root/direction keywords.

    exp_root = item["expected_root"].lower()  # "project-root" | "metodoloji-root"
    exp_dir = item["expected_direction"].lower()  # "output" | "read"

    # 1. Root classification — the expected root must be present. There is NO
    # "contradiction" penalty: a correct answer may mention the other root in a
    # contrastive clause ("...project-root, not the plugin"), and that is still
    # a correct classification. A wrong root simply lacks the expected keyword
    # and fails here naturally.
    if exp_root == "project-root":
        root_ok = ("project" in lower) or ("hedef" in lower and "proje" in lower)
    else:
        root_ok = ("metodoloji" in lower) or ("plugin" in lower)
    checks.append(root_ok)

    # 2. Direction classification — same reasoning: presence of the expected
    # direction keyword; the opposite keyword in a contrastive clause is fine.
    if exp_dir == "output":
        dir_ok = ("output" in lower or "yaz" in lower or "oluştur" in lower or "üret" in lower)
    else:
        dir_ok = ("read" in lower or "oku" in lower or "yükle" in lower)
    checks.append(dir_ok)

    found = sum(checks)
    soft = found / len(checks) if checks else 1.0
    hard = 1 if soft >= 1.0 else 0
    return hard, soft


def _rollout_one(item: dict, skill_content: str, out_dir: pathlib.Path,
                  max_completion_tokens: int = 4096) -> dict:
    # The system prompt intentionally does NOT name the answer keywords
    # (project-root / metodoloji-root / output / read). The model must reason
    # from the operation and the skill's tables; echoing the prompt cannot
    # produce a passing answer. The scorer checks for exactly those keywords,
    # so leaving them out of the prompt closes the echo-leak.
    system_prompt = (
        f"{skill_content}\n\n"
        f"You classify a methodology path operation. Use the rules above to "
        f"decide which anchor the operation resolves against, and whether the "
        f"operation writes or reads. Explain your reasoning in your own words "
        f"in at least one full sentence — do not merely restate the categories."
    )
    user_prompt = (
        f"## Operation\n\n{item['operation']}\n\n"
        f"State the root anchor and the direction (does the operation produce "
        f"or consume?). Justify your answer briefly."
    )

    output_text, meta = chat_target(
        system=system_prompt,
        user=user_prompt,
        max_completion_tokens=max_completion_tokens,
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
        {"role": "assistant", "content": output_text},
    ]

    hard, soft = _score(output_text, item)

    pred_dir = out_dir / "predictions" / item["id"]
    pred_dir.mkdir(parents=True, exist_ok=True)
    (pred_dir / "conversation.json").write_text(
        json.dumps(messages, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    return {
        "id": item["id"],
        "hard": hard,
        "soft": soft,
        "task_type": item.get("task_type", "meta-root"),
        "expected_root": item["expected_root"],
        "expected_direction": item["expected_direction"],
        "predicted_output_length": len(output_text),
        "target_system_prompt": system_prompt[:500],
        "target_user_prompt": user_prompt[:500],
        "n_turns": 1,
    }


def run_batch(items: list[dict], skill_content: str, out_dir,
              workers: int = 1, max_completion_tokens: int = 4096) -> list[dict]:
    out_dir = pathlib.Path(out_dir)
    results = []
    for item in items:
        try:
            result = _rollout_one(item, skill_content, out_dir,
                                  max_completion_tokens=max_completion_tokens)
        except Exception as exc:
            result = {
                "id": item["id"], "hard": 0, "soft": 0.0,
                "task_type": item.get("task_type", "meta-root"),
                "error": str(exc), "n_turns": 0,
            }
        results.append(result)

    (out_dir / "rollouts.json").parent.mkdir(parents=True, exist_ok=True)
    (out_dir / "rollouts.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return results


def _selfcheck() -> None:
    """Assert the scorer is leak-tight, does not over-penalize, and covers all
    four root×direction combinations:
      - {project-root}+output (write)   — pass
      - {project-root}+read   (project source read) — pass
      - {metodoloji-root}+read (plugin source read) — pass
      - plugin-write trap     (answer is {project-root}+output) — pass
    Hedged / keywordless / wrong-root answers fail. Short-but-correct answers
    pass. Run: python3 rollout.py --selfcheck."""
    # All three valid combinations + the plugin-write trap answer pass.
    assert _score("Bu operasyon project-root altına story yazıyor — çıktı üretiyor.",
                  {"expected_root": "project-root", "expected_direction": "output"}) == (1, 1.0)
    assert _score("Manifestoyu project-root'taki docs/bmad kopyasından okuyorum — okuma işlemi.",
                  {"expected_root": "project-root", "expected_direction": "read"}) == (1, 1.0)
    assert _score("Bu, plugin kurulumundaki config'i okuyor, metodoloji-root'tan.",
                  {"expected_root": "metodoloji-root", "expected_direction": "read"}) == (1, 1.0)
    # Plugin-write trap: the write still lands in project-root (never the plugin).
    assert _score("Plugin'e yazmak yanlış; kayıt project-root altına oluşturulur — çıktı.",
                  {"expected_root": "project-root", "expected_direction": "output"}) == (1, 1.0)
    # Contrastive clauses naming the other root/direction are still correct.
    assert _score("Kayıt project-root'a yazılır, plugin'e değil — oluşturma işlemi.",
                  {"expected_root": "project-root", "expected_direction": "output"}) == (1, 1.0)
    assert _score("Şablonu metodoloji-root'tan kopyalar; okuyan işlem, çıktı üretmez.",
                  {"expected_root": "metodoloji-root", "expected_direction": "read"}) == (1, 1.0)
    # A bare prompt echo (no skill knowledge) must NOT pass.
    assert _score("The anchor is resolve and the operation writes.",
                  {"expected_root": "project-root", "expected_direction": "output"}) == (0, 0.0)
    # Hedged answers never pass.
    assert _score("Özür dilerim, bilmiyorum.",
                  {"expected_root": "project-root", "expected_direction": "output"}) == (0, 0.0)
    # Wrong-root answers fail (expected keyword absent); direction may still score.
    hard, soft = _score("Bu operasyon metodoloji-root'a yazılır.",
                        {"expected_root": "project-root", "expected_direction": "output"})
    assert hard == 0 and soft == 0.5  # root wrong -> hard 0; direction right -> soft 0.5
    # Short-but-correct answers pass — no minimum-length gate.
    assert _score("project-root output", {"expected_root": "project-root", "expected_direction": "output"}) == (1, 1.0)
    assert _score("metodoloji-root oku", {"expected_root": "metodoloji-root", "expected_direction": "read"}) == (1, 1.0)
    print("selfcheck OK")


if __name__ == "__main__":
    if "--selfcheck" in sys.argv:
        _selfcheck()
        sys.exit(0)
    sys.exit("rollout.py is a module — import run_batch via the adapter (or run --selfcheck)")
