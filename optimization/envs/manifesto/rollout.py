"""Manifesto benchmark rollout — uses LLM with manifesto as system prompt.

The "skill" being optimized IS the manifesto document. The LLM reads it
and answers questions about BMAD rules. We score whether it correctly
follows the rules defined in the manifesto.
"""
from __future__ import annotations

import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from skillopt.model import chat_target

from .evaluator import evaluate_task

# Configure openai_compatible backend
if not os.environ.get("REFLACT_MODEL_BACKEND"):
    os.environ["REFLACT_MODEL_BACKEND"] = "openai_compatible"
if not os.environ.get("OPENAI_COMPATIBLE_BASE_URL"):
    os.environ["OPENAI_COMPATIBLE_BASE_URL"] = "http://localhost:20128/v1"
if not os.environ.get("OPENAI_COMPATIBLE_API_KEY"):
    os.environ["OPENAI_COMPATIBLE_API_KEY"] = "sk-2d3c99a72a01cbcc-smtwcf-24b76850"
if not os.environ.get("OPENAI_COMPATIBLE_MODEL"):
    os.environ["OPENAI_COMPATIBLE_MODEL"] = "th/qwen3.8-27b:free"

from skillopt.model import set_backend
set_backend("openai_compatible")


def _build_system_prompt(skill_content: str) -> str:
    """Build system prompt from manifesto content."""
    return (
        "Sen bir BMAD metodolojisi uzmanısın. Aşağıdaki metodoloji belgelerini "
        "okuduktan sonra, verilen soruları bu belgelere dayanarak cevaplayacaksın.\n\n"
        "KURALLAR:\n"
        "- Cevaplarını SADECE okuduğun belgelere göre ver\n"
        "- Belgede olmayan bilgiyi uydurma\n"
        "- Sorulan spesifik bilgiyi doğrudan ve kısa cevapla\n"
        "- İngilizce terimler yerine Türkçe terimleri tercih et\n\n"
        "METODOLOJİ BELGELERİ:\n\n"
        f"{skill_content}\n\n"
        "Şimdi soruları cevapla."
    )


def _process_one(item, skill_content, out_root, max_completion_tokens=4096):
    item_id = str(item.get("id", "unknown"))
    question = str(item.get("question", ""))
    system_prompt = _build_system_prompt(skill_content)

    t0 = time.time()
    try:
        raw = chat_target(
            system=system_prompt,
            user=question,
            max_completion_tokens=max_completion_tokens,
        )
        response = raw[0] if isinstance(raw, tuple) else raw
        if response is None:
            response = ""
        elapsed = time.time() - t0
    except Exception as e:
        elapsed = time.time() - t0
        response = f"ERROR: {e}"

    scores = evaluate_task(item, response)

    pred_dir = os.path.join(out_root, "predictions", item_id)
    os.makedirs(pred_dir, exist_ok=True)
    with open(os.path.join(pred_dir, "conversation.json"), "w", encoding="utf-8") as f:
        json.dump({
            "id": item_id,
            "system_prompt": system_prompt[:500] + "...",
            "user_prompt": question,
            "response": response,
            "ground_truth": item.get("ground_truth", ""),
            "hard": scores["hard"],
            "soft": scores["soft"],
            "elapsed_s": round(elapsed, 2),
        }, f, indent=2, ensure_ascii=False)

    return {
        "id": item_id,
        "hard": scores["hard"],
        "soft": scores["soft"],
        "predicted_answer": response[:200],
        "question": question,
        "task_type": item.get("task_type", "manifesto"),
        "fail_reason": "" if scores["hard"] else f"expected={item.get('ground_truth','?')} missing",
        "elapsed_s": round(elapsed, 2),
    }


def run_batch(items, out_root, skill_content, workers=4, max_completion_tokens=4096):
    os.makedirs(out_root, exist_ok=True)
    results = []

    completed_path = os.path.join(out_root, "results.jsonl")
    completed_ids = set()
    if os.path.exists(completed_path):
        with open(completed_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                    completed_ids.add(str(rec.get("id", "")))
                    results.append(rec)
                except json.JSONDecodeError:
                    pass

    pending = [item for item in items if str(item.get("id", "")) not in completed_ids]
    if not pending:
        return results

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(_process_one, item, skill_content, out_root, max_completion_tokens): item
            for item in pending
        }
        for future in as_completed(futures):
            try:
                result = future.result()
                results.append(result)
                with open(completed_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(result, ensure_ascii=False) + "\n")
            except Exception as e:
                item = futures[future]
                results.append({
                    "id": str(item.get("id", "")),
                    "hard": 0, "soft": 0.0,
                    "predicted_answer": f"ERROR: {e}",
                    "question": item.get("question", ""),
                    "task_type": "manifesto",
                    "fail_reason": f"exception: {e}",
                })

    all_results = []
    if os.path.exists(completed_path):
        with open(completed_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    all_results.append(json.loads(line))
    return all_results
