#!/usr/bin/env python3
"""Generate expanded BMAD benchmark tasks (50 -> ~150) for more reliable SkillOpt training.

Each task is a methodology scenario. The guard/quality/deploy/stop/audit categories
test hook behavior; bridge/chain test methodology wiring.
"""
import json
import random
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"

random.seed(42)


def generate(task_type, question, ground_truth, expected_action, reference, skill_target, metric="exact_match"):
    return {
        "id": f"{task_type}-{len(_ALL[task_type])+1:03d}",
        "task_type": task_type,
        "question": question,
        "reference_text": reference,
        "expected_action": expected_action,
        "skill_target": skill_target,
        "hard_metric": metric,
        "ground_truth": ground_truth,
    }


_ALL = {
    "guard": [], "quality": [], "deploy": [], "stop": [],
    "audit": [], "bridge": [], "chain": [],
}


# ── GUARD (code write approval) ───────────────────────────────────────────────
guard_tasks = [
    ("Story S-001 has Status:done but docs/quality/ has no QR record. Guard should DENY the story write. Expected decision?",
     "DENY", "deny", "guard.py _validate_methodology_chain: done stories require QR"),
    ("Story frontmatter has experiment_refs: E-001 status PENDING. Guard should DENY. Expected decision?",
     "DENY", "deny", "guard.py: PENDING experiments block implementation"),
    ("Writing src/utils.py with no approved experiment record. Guard should DENY. Expected decision?",
     "DENY", "deny", "guard.py: code target requires approved experiment"),
    ("Writing scratch/notes.md (free zone). Guard should ALLOW. Expected decision?",
     "ALLOW", "allow", "guard.py: scratch is free zone"),
    ("Story references E-001 ONAYLANDI but the experiment record is not gate-verified (no valid HMAC token). Guard should DENY because the experiment is unverified. Expected decision?",
     "DENY", "deny", "guard.py verify_record: unverified experiment records are rejected (fail-closed)"),
    ("Terminal command references ~/.bmad/gate-key. Guard should DENY (secret). Expected decision?",
     "DENY", "deny", "guard.py _secret_ref: gate-key blocks"),
    ("Story AC-1 missing Type field (agent-verifiable/user-evaluable/hybrid). Guard should DENY. Expected decision?",
     "DENY", "deny", "guard.py: AC missing Type field"),
    ("Story references SP-002 but no SP record in docs/development/. Guard should DENY. Expected decision?",
     "DENY", "deny", "guard.py: SP ref without record"),
    ("Writing to tmp/scratch.py (free zone). Guard should ALLOW. Expected decision?",
     "ALLOW", "allow", "guard.py: tmp is free zone"),
    ("Story AC has Experiment=— (dash) but no [HYPOTHESIS] tag. Guard should DENY. Expected decision?",
     "DENY", "deny", "guard.py: Experiment=— requires HYPOTHESIS tag"),
    ("Writing to docs/design/architecture.md (non-code). Guard should ALLOW. Expected decision?",
     "ALLOW", "allow", "guard.py: docs md is non-code"),
    ("Story S-002 Status:review but no methodology record in docs/development/stories/. Guard should DENY. Expected decision?",
     "DENY", "deny", "guard.py: review status requires S record"),
    ("Writing to _bmad/helper.py (free zone). Guard should ALLOW. Expected decision?",
     "ALLOW", "allow", "guard.py: _bmad is free prefix"),
    ("Terminal command 'git apply patch.diff' where patch.diff does not exist. Guard cannot extract any write target from a missing patch file, so it should ALLOW (no targets to check). Expected decision?",
     "ALLOW", "allow", "guard.py: missing patch file yields no targets, so no approval required"),
    ("Story AC references E-005 which does not exist in docs/experiments/. Guard should DENY. Expected decision?",
     "DENY", "deny", "guard.py: missing experiment record"),
]
for q, gt, ea, ref in guard_tasks:
    _ALL["guard"].append(generate("guard", q, gt, ea, ref, "skills/bmad-dev-story/SKILL.md"))

# ── QUALITY (git commit gate) ─────────────────────────────────────────────────
quality_tasks = [
    ("git commit with done story lacking IR record. Quality gate should DENY. Expected decision?",
     "DENY", "deny", "guard.py quality: done without IR (Kapi 1)"),
    ("git commit with done story lacking QR record. Quality gate should DENY. Expected decision?",
     "DENY", "deny", "guard.py quality: done without QR (Kapi 3)"),
    ("git commit with done story referencing SP but no SP record. Quality gate should DENY. Expected decision?",
     "DENY", "deny", "guard.py quality: SP ref without record (Kapi 2)"),
    ("git commit with no done stories. Quality gate should ALLOW. Expected decision?",
     "ALLOW", "allow", "guard.py quality: no done stories"),
    ("git commit -am 'docs update' with all stories in-progress (not done). Quality gate should ALLOW. Expected decision?",
     "ALLOW", "allow", "guard.py quality: no done stories"),
    ("git commit with done story that HAS IR, QR, and SP records. Quality gate should ALLOW. Expected decision?",
     "ALLOW", "allow", "guard.py quality: all Kapi 1-3 pass"),
    ("git commit with 2 done stories, one has QR, one doesn't. Quality gate should DENY. Expected decision?",
     "DENY", "deny", "guard.py quality: any done story without QR"),
]
for q, gt, allow, ref in quality_tasks:
    _ALL["quality"].append(generate("quality", q, gt, allow, ref, "skills/bmad-code-review/SKILL.md"))

# ── deploy. (deploy gate) ────────────────────────────────────────────────────
deploy_tasks = [
    ("docker compose up with done stories missing PR record. Deploy gate should DENY. Expected decision?",
     "DENY", "deny", "guard.py deploy: done without PR (Kapi 4)"),
    ("terraform apply with done stories missing IR. Deploy gate should DENY. Expected decision?",
     "DENY", "deny", "guard.py deploy: done without IR (Kapi 1)"),
    ("kubectl apply with all records complete (IR,SP,QR,PR). Deploy gate should ALLOW. Expected decision?",
     "ALLOW", "allow", "guard.py deploy: all kapi pass"),
    ("git push origin main with no done stories. Deploy gate should ALLOW. Expected decision?",
     "ALLOW", "allow", "guard.py deploy: no done stories"),
    ("ansible playbook with done stories missing QR. Deploy gate should DENY. Expected decision?",
     "DENY", "deny", "guard.py deploy: done without QR (Kapi 3)"),
    ("docker deploy with done stories missing SP. Deploy gate should DENY. Expected decision?",
     "DENY", "deny", "guard.py deploy: done without SP (Kapi 2)"),
    ("git push origin production with done stories missing PR. Deploy gate should DENY. Expected decision?",
     "DENY", "deny", "guard.py deploy: PR required for prod push"),
]
for q, gt, allow, why in deploy_tasks:
    _ALL["deploy"].append(generate("deploy", q, gt, allow, why, "skills/bmad-code-review/SKILL.md"))

# ── stop. (stop gate) ────────────────────────────────────────────────────────
stop_tasks = [
    ("Stop requested with in-progress story in sprint-status.yaml. Stop hook should DENY. Expected decision?",
     "DENY", "deny", "stop.py _check_story_status: in-progress blocks"),
    ("Stop requested with unapproved code in src/. Stop hook should DENY. Expected decision?",
     "DENY", "deny", "stop.py: unapproved code blocks"),
    ("Stop requested with no issues. Stop hook should ALLOW. Expected decision?",
     "ALLOW", "allow", "stop.py: no issues"),
    ("Stop with unapproved changes only in scratch/. Stop hook should ALLOW. Expected decision?",
     "ALLOW", "allow", "stop.py: scratch is free"),
    ("Stop with changes in docs/ (non-code). Stop hook should ALLOW. Expected decision?",
     "ALLOW", "allow", "stop.py: md not scanned"),
    ("Stop with in-progress story but no unapproved code. Stop hook should DENY. Expected decision?",
     "DENY", "deny", "stop.py: incomplete story blocks"),
]
for q, gt, allow, why in stop_tasks:
    _ALL["stop"].append(generate("stop", q, gt, allow, why, "skills/bmad-dev-story/SKILL.md"))

# ── audit. (audit warnings) ──────────────────────────────────────────────────
audit_tasks = [
    ("File editor writes story S-001.md without [AC-XXX] identifiers. Audit should warn. What warning?",
     "AC metadata missing", "warn", "audit.py _validate_methodology_compliance", "contains"),
    ("File editor writes story without experiment_refs frontmatter. Audit should warn. What warning?",
     "experiment_refs missing", "warn", "audit.py compliance check", "contains"),
    ("File editor modifies QR record with no DoD items. Audit should KOPRU warn. What warning?",
     "KOPRU uyumsuzlugu", "warn", "audit.py _check_kopru_consumption", "contains"),
    ("Terminal runs ls. Audit should produce no warnings. Result?",
     "ALLOW", "allow", "audit.py: no file_editor", "exact_match"),
    ("File editor modifies done story S-002 with no QR record. Audit should KOPRU warn. What warning?",
     "KOPRU uyumsuzlugu", "warn", "audit.py kopru consumption", "contains"),
]
for q, gt, allow, why, met in audit_tasks:
    _ALL["audit"].append(generate("audit", q, gt, allow, why, "skills/bmad-dev-story/SKILL.md", met))

# ── bridge. (TOML bridge wiring) ─────────────────────────────────────────────
bridge_tasks = [
    ("Does custom/bmad-code-review.toml contain KOPRU activation_steps_append for QR?",
     "KOPRU", "present", "custom TOML bridge", "skills/bmad-code-review/SKILL.md", "contains"),
    ("Does custom/bmad-sprint-planning.toml contain KOPRU for SP?",
     "KOPRU", "present", "custom TOML bridge", "skills/bmad-sprint-planning/SKILL.md", "contains"),
    ("Does custom/bmad-check-implementation-readiness.toml contain KOPRU for IR?",
     "KOPRU", "present", "custom TOML bridge", "skills/bmad-check-implementation-readiness/SKILL.md", "contains"),
    ("Does custom/bmad-create-story.toml contain KOPRU for S?",
     "KOPRU", "present", "custom TOML bridge", "skills/bmad-create-story/SKILL.md", "contains"),
    ("Does custom/bmad-dev-story.toml contain KOPRU for story update?",
     "KOPRU", "present", "custom TOML bridge", "skills/bmad-dev-story/SKILL.md", "contains"),
    ("Do KOPRU TOMLs also contain DOGRULAMA verification?",
     "DOGRULAMA", "present", "check-plugin 2c", "skills/bmad-dev-story/SKILL.md", "contains"),
    ("Does resolve_customization.py merge 3 layers (base+team+user)?",
     "PASS", "pass", "resolve_customization deep_merge", "hooks/engine/resolve_customization.py", "exact_match"),
    ("Does customize.toml persistent_facts include research-methodology.md?",
     "research-methodology.md", "present", "check-plugin 2", "skills/bmad-dev-story/customize.toml", "contains"),
    ("Does customize.toml persistent_facts include project-context.md?",
     "project-context.md", "present", "check-plugin 2", "skills/bmad-dev-story/customize.toml", "contains"),
    ("Do dev-wing skills include development-methodology.md?",
     "development-methodology.md", "present", "check-plugin 2", "skills/bmad-dev-story/customize.toml", "contains"),
]
for q, gt, allow, why, skill_target, metric in bridge_tasks:
    _ALL["bridge"].append(generate("bridge", q, gt, allow, why, skill_target, metric))

# ── chain. (methodology chain integrity) ─────────────────────────────────────
chain_tasks = [
    ("Story S-001 done requires QR record in docs/quality/. Is the S->QR link present?",
     "S-001", "present", "guard methodology chain", "skills/bmad-code-review/SKILL.md", "contains"),
    ("Story S-001 references SP-003, requires SP record. Is SP->S link present?",
     "SP-003", "present", "guard methodology chain", "skills/bmad-sprint-planning/SKILL.md", "contains"),
    ("Done stories require IR record (Kapi 1). Is IR gate present?",
     "IR", "present", "guard _find_done_stories_without_ir", "skills/bmad-check-implementation-readiness/SKILL.md", "contains"),
    ("Deploy requires PR records (Kapi 4). Is PR gate present?",
     "PR", "present", "guard _find_done_stories_without_pr", "skills/bmad-code-review/SKILL.md", "contains"),
    ("Experiment E-001 ONAYLANDI gate token verified. Is E gate integrity present?",
     "VERIFIED", "verified", "guard verify_record", "skills/bmad-research-experiment/SKILL.md", "exact_match"),
    ("Full E->IR->SP->S->QR->PR chain complete. Are all links present?",
     "COMPLETE", "complete", "full chain", "skills/bmad-dev-story/SKILL.md", "all_present"),
    ("Story references E-002 REDDEDIDILDI. Should guard block?",
     "DENY", "deny", "guard experiment refs", "skills/bmad-dev-story/SKILL.md", "exact_match"),
    ("Story references E-003 that doesn't exist. Should guard block?",
     "DENY", "deny", "guard missing experiment", "skills/bmad-dev-story/SKILL.md", "exact_match"),
    ("check-plugin.sh runs. Is final status SAĞLIKLI?",
     "SAĞLIKLI", "healthy", "check-plugin", "commands/check-plugin.sh", "contains"),
    ("check-plugin.sh --negtest runs. Does it detect broken KOPRU MISS?",
     "MISS", "detected", "check-plugin negtest", "commands/check-plugin.sh", "contains"),
]
for q, gt, allow, why, ref_target, metric in chain_tasks:
    _ALL["chain"].append(generate("chain", q, gt, allow, why, ref_target, metric))

# ── Write per-category files + combined ──────────────────────────────────────
for cat, items in _ALL.items():
    out = DATA_DIR / f"{cat}_tasks.jsonl"
    with open(out, "w", encoding="utf-8") as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")
    print(f"  {cat}: {len(items)} tasks")

# Rebuild combined file
combined = []
for cat in sorted(_ALL):
    combined.extend(_ALL[cat])
with open(DATA_DIR / "all_tasks.jsonl", "w", encoding="utf-8") as f:
    for it in combined:
        f.write(json.dumps(it, ensure_ascii=False) + "\n")

total = sum(len(v) for v in _ALL.values())
print(f"\n  Total: {total} tasks")