"""Rollout + scoring for bmad-meta-path benchmark.

Task: given a record to produce, state the correct full path under the
correct root. Scoring checks root + exact path fragment + status values.
"""

import json
import pathlib
import sys

from skillopt.model import chat_target


def _score(output_text: str, item: dict) -> tuple[int, float]:
    lower = output_text.lower()
    checks = []

    # 1. Root correct (project-root for outputs)
    exp_root = item.get("expected_root", "project-root").lower()
    if exp_root == "project-root":
        checks.append("project" in lower or ("hedef" in lower and "proje" in lower))
    else:
        checks.append("metodoloji" in lower or "plugin" in lower)

    # 2. Path fragment (e.g. "docs/development/stories/S-")
    path_frag = item["expected_path"].lower()
    checks.append(path_frag in lower)

    # 3. Status values present
    status_vals = [s.strip().lower() for s in item["expected_status"].split("|") if s.strip()]
    checks.append(any(v in lower for v in status_vals))

    found = sum(checks)
    soft = found / len(checks) if checks else 1.0
    hard = 1 if soft >= 1.0 else 0
    return hard, soft


def _rollout_one(item: dict, skill_content: str, out_dir: pathlib.Path,
                  max_completion_tokens: int = 4096) -> dict:
    system_prompt = (
        f"{skill_content}\n\n"
        f"You state the exact path where a methodology record must be created."
    )
    user_prompt = (
        f"## Record to produce\n\n{item['stage']}\n\n"
        f"State the full path (root + relative), and the allowed status values."
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
        "task_type": item.get("task_type", "meta-path"),
        "expected_path": item.get("expected_path", ""),
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
                "task_type": item.get("task_type", "meta-path"),
                "error": str(exc), "n_turns": 0,
            }
        results.append(result)

    (out_dir / "rollouts.json").parent.mkdir(parents=True, exist_ok=True)
    (out_dir / "rollouts.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return results


def _selfcheck() -> None:
    """Assert the meta-path scorer: correct root+path+status passes; a wrong
    path or missing status fails. Run: python3 rollout.py --selfcheck."""
    item = {"expected_root": "project-root",
            "expected_path": "docs/development/stories/S-",
            "expected_status": "planlandı | devam ediyor | tamamlandı"}
    # Correct answer passes.
    assert _score("Kayıt project-root/docs/development/stories/S-001.md olarak oluşturulur; "
                  "durum: tamamlandı.", item) == (1, 1.0)
    # Wrong root fails.
    assert _score("Kayıt metodoloji-root/docs/development/stories/S-001.md; durum: tamamlandı.",
                  item)[0] == 0
    # Wrong path fragment fails.
    assert _score("Kayıt project-root/docs/quality/QR-001.md; durum: tamamlandı.",
                  item)[0] == 0
    # Missing status fails.
    assert _score("Kayıt project-root/docs/development/stories/S-001.md olarak oluşturulur.",
                  item)[0] == 0
    print("selfcheck OK")


if __name__ == "__main__":
    if "--selfcheck" in sys.argv:
        _selfcheck()
        sys.exit(0)
    sys.exit("rollout.py is a module — import run_batch via the adapter (or run --selfcheck)")
