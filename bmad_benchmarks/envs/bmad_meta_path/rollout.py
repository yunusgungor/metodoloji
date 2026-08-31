from .._base_.rollout import run_batch as _run_batch


def _score(output_text, item):
    lower = output_text.lower()
    checks = []
    exp_root = item.get("expected_root", "project-root").lower()
    if exp_root == "project-root":
        checks.append("project" in lower or ("hedef" in lower and "proje" in lower))
    else:
        checks.append("metodoloji" in lower or "plugin" in lower)
    checks.append(item["expected_path"].lower() in lower)
    status_vals = [s.strip().lower() for s in item["expected_status"].split("|") if s.strip()]
    checks.append(any(v in lower for v in status_vals))
    found = sum(checks)
    soft = found / len(checks) if checks else 1.0
    hard = 1 if soft >= 1.0 else 0
    return hard, soft


def _prompt(item, skill_content):
    system = (
        f"{skill_content}\n\n"
        f"You state the exact path where a methodology record must be created."
    )
    user = (
        f"## Record to produce\n\n{item['stage']}\n\n"
        f"State the full path (root + relative), and the allowed status values."
    )
    return system, user


def run_batch(items, skill_content, out_dir, workers=1, max_completion_tokens=4096):
    return _run_batch(items, skill_content, out_dir, _score, _prompt,
                      max_completion_tokens=max_completion_tokens,
                      workers=workers, default_task_type="meta-path")


def _selfcheck():
    item = {"expected_root": "project-root",
            "expected_path": "docs/development/stories/S-",
            "expected_status": "planlandı | devam ediyor | tamamlandı"}
    assert _score("Kayıt project-root/docs/development/stories/S-001.md olarak oluşturulur; "
                  "durum: tamamlandı.", item) == (1, 1.0)
    assert _score("Kayıt metodoloji-root/docs/development/stories/S-001.md; durum: tamamlandı.",
                  item)[0] == 0
    assert _score("Kayıt project-root/docs/quality/QR-001.md; durum: tamamlandı.",
                  item)[0] == 0
    assert _score("Kayıt project-root/docs/development/stories/S-001.md olarak oluşturulur.",
                  item)[0] == 0
    print("selfcheck OK")


if __name__ == "__main__":
    import sys
    if "--selfcheck" in sys.argv:
        _selfcheck()
        sys.exit(0)
    sys.exit("rollout.py is a module — import run_batch via the adapter (or run --selfcheck)")
