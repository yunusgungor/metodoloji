"""BMAD Benchmark Rollout — executes tasks against the target model using skill as system prompt."""
from __future__ import annotations

import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from skillopt.model import chat_target

from .evaluator import evaluate_task


def _build_system_prompt(skill_content: str) -> str:
    """Build system prompt from skill document."""
    return (
        "You are a BMAD methodology expert. You analyze scenarios and determine "
        "the correct action according to the BMAD methodology rules.\n\n"
        "Based on the following skill instructions:\n\n"
        f"{skill_content}\n\n"
        "Analyze the given scenario and respond with a clear, concise answer. "
        "For deny/allow questions, respond with exactly DENY or ALLOW. "
        "For present/absent questions, respond with PRESENT or ABSENT. "
        "For warning questions, describe the expected warning."
    )


def _process_one(
    item: dict,
    skill_content: str,
    out_root: str,
    max_completion_tokens: int = 4096,
    task_timeout: int = 60,
) -> dict:
    """Process a single benchmark task: call model, score, persist trajectory."""
    item_id = str(item.get("id", "unknown"))
    question = str(item.get("question", ""))

    system_prompt = _build_system_prompt(skill_content)

    # Call the target model
    t0 = time.time()
    try:
        response = chat_target(
            system=system_prompt,
            user=question,
            max_completion_tokens=max_completion_tokens,
            temperature=0.0,
        )
        elapsed = time.time() - t0
    except Exception as e:
        elapsed = time.time() - t0
        response = f"ERROR: {e}"

    # Extract predicted action from response
    predicted_action = _extract_action(response, item)

    # Score
    scores = evaluate_task(item, predicted_action)

    # Persist trajectory
    pred_dir = os.path.join(out_root, "predictions", item_id)
    os.makedirs(pred_dir, exist_ok=True)

    with open(os.path.join(pred_dir, "conversation.json"), "w", encoding="utf-8") as f:
        json.dump({
            "id": item_id,
            "system_prompt": system_prompt,
            "user_prompt": question,
            "response": response,
            "predicted_action": predicted_action,
            "ground_truth": item.get("ground_truth", ""),
            "expected_action": item.get("expected_action", ""),
            "elapsed_s": round(elapsed, 2),
        }, f, indent=2, ensure_ascii=False)

    with open(os.path.join(pred_dir, "target_system_prompt.txt"), "w", encoding="utf-8") as f:
        f.write(system_prompt)

    with open(os.path.join(pred_dir, "target_user_prompt.txt"), "w", encoding="utf-8") as f:
        f.write(question)

    return {
        "id": item_id,
        "hard": scores["hard"],
        "soft": scores["soft"],
        "predicted_answer": predicted_action,
        "question": question,
        "task_type": item.get("task_type", "bmad"),
        "fail_reason": "" if scores["hard"] else f"expected={item.get('expected_action','?')} got={predicted_action}",
        "elapsed_s": round(elapsed, 2),
    }


def _extract_action(response: str, item: dict) -> str:
    """Extract the predicted action from model response.

    Looks for key action words: DENY, ALLOW, PRESENT, ABSENT, WARN, VERIFIED, etc.
    """
    upper = response.upper().strip()
    expected = str(item.get("expected_action", "")).upper()

    # Direct match
    action_map = {
        "DENY": ["DENY", "RED", "BLOCK", "BLOCKED"],
        "ALLOW": ["ALLOW", "GREEN", "PASS", "PERMIT"],
        "WARN": ["WARN", "WARNING", "UYARI"],
        "PRESENT": ["PRESENT", "EXISTS", "VAR", "MEVCUT"],
        "ABSENT": ["ABSENT", "MISSING", "YOK"],
        "VERIFIED": ["VERIFIED", "VALID", "DOGRU", "GEÇTİ"],
        "HEALTHY": ["SAĞLIKLI", "HEALTHY", "HEALTH"],
        "DETECTED": ["DETECTED", "YAKALANDI", "FOUND"],
        "COMPLETE": ["COMPLETE", "TAM", "FULL"],
    }

    for key, keywords in action_map.items():
        for kw in keywords:
            if kw in upper:
                return key

    # Fallback: return first significant word
    words = upper.split()
    for word in words:
        if len(word) > 2 and word.isalpha():
            return word

    return "UNKNOWN"


def run_batch(
    items: list[dict],
    out_root: str,
    skill_content: str,
    workers: int = 4,
    max_completion_tokens: int = 4096,
    task_timeout: int = 60,
) -> list[dict]:
    """Run a batch of benchmark tasks concurrently.

    Returns list of rollout result dicts conforming to RolloutResult.
    """
    os.makedirs(out_root, exist_ok=True)
    results: list[dict] = []

    # Resume support: skip completed items
    completed_path = os.path.join(out_root, "results.jsonl")
    completed_ids: set[str] = set()
    if os.path.exists(completed_path):
        with open(completed_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                    completed_ids.add(str(rec.get("id", "")))
                except json.JSONDecodeError:
                    pass

    pending = [item for item in items if str(item.get("id", "")) not in completed_ids]
    if not pending:
        # Load all from results
        with open(completed_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    results.append(json.loads(line))
        return results

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(
                _process_one, item, skill_content, out_root,
                max_completion_tokens, task_timeout,
            ): item
            for item in pending
        }
        for future in as_completed(futures):
            try:
                result = future.result()
                results.append(result)
                # Append to results.jsonl
                with open(completed_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(result, ensure_ascii=False) + "\n")
                hard = result.get("hard", 0)
                print(f"    [{result['id']}] hard={hard} soft={result.get('soft', 0):.2f}")
            except Exception as e:
                item = futures[future]
                results.append({
                    "id": str(item.get("id", "")),
                    "hard": 0,
                    "soft": 0.0,
                    "predicted_answer": f"ERROR: {e}",
                    "question": item.get("question", ""),
                    "task_type": item.get("task_type", "bmad"),
                    "fail_reason": f"exception: {e}",
                })

    # Load existing results for final tally
    all_results = []
    if os.path.exists(completed_path):
        with open(completed_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    all_results.append(json.loads(line))

    return all_results
