"""Metodoloji rollout — chat harness üzerinden süreç simülasyonu.

Her senaryo için target model, sabit metodoloji sözleşmesi + eğitilen süreç
rehberi (skill_content) + senaryo ile tek tur çalışır ve yapılandırılmış süreç
transcript'i üretir. Transcript deterministik evaluator ile skorlanır ve
reflect aşaması için ``predictions/<id>/conversation.json`` olarak saklanır.

Public API
----------
- :func:`process_one`  — tek senaryo çalıştır + skorla
- :func:`run_batch`    — paralel toplu çalıştırma
"""
from __future__ import annotations

import json
import os
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait

from skillopt.envs.metodoloji.evaluator import evaluate
from skillopt.model import chat_target

PROMPTS_DIR = os.path.join(os.path.dirname(__file__), "prompts")

# Sabit sözleşme özeti — optimizer'ın edit alanı DIŞINDA. Metodolojinin
# değiştirilemez çekirdeği; eğitilen skill yalnızca bunun üstüne rehberlik eder.
FIXED_CONTRACT = """\
# Sabit Metodoloji Sözleşmesi (DEĞİŞTİRİLEMEZ)

- Kayıt zinciri: E (deney) → IR (hazırlık) → SP (sprint planı) → S (story) → QR (kalite) → PR (üretim).
  Zincir atlanamaz; her çıktı moduna uygun kanıt kapısından geçmeden kodlaştırılamaz.
- Her araştırma çıktısı bir iddiadır ve falsifiable hipotez olarak yazılır: H-NNN: "metrik >= eşik".
- Kapı çalıştırılmadan ölçüm raporlanamaz; öngörüler "tahmin/beklenen" olarak işaretlenir.
- REDDEDİLDİ kaydı ONAYLANDI'ya çevrilmez; kapı kanıtı uydurulamaz.
- Kullanıcıyla senaryonun dilinde (Türkçe) iletişim kurulur; <iletisim> bloğunda
  kullanıcıya doğrudan hitap et ("siz/seni"), talebini özetle, planını ve sonraki
  adımını kısaca açıkla.
"""


def _load_prompt(name: str) -> str:
    with open(os.path.join(PROMPTS_DIR, f"{name}.md"), encoding="utf-8") as f:
        return f.read()


def build_system(skill_content: str) -> str:
    skill_section = ""
    if skill_content.strip():
        skill_section = f"## Süreç Rehberi (eğitilen skill — buna uy)\n{skill_content.strip()}\n\n"
    return _load_prompt("rollout_system").format(
        fixed_contract=FIXED_CONTRACT,
        skill_section=skill_section,
    )


def build_user(item: dict) -> str:
    parts = []
    if item.get("context"):
        parts.append(f"## Proje Bağlamı\n{item['context']}")
    parts.append(f"## Kullanıcı İsteği\n{item['user_request']}")
    return "\n\n".join(parts)


def process_one(
    item: dict,
    out_root: str,
    skill_content: str,
    max_completion_tokens: int = 8192,
    exec_timeout: int = 300,
    **_: object,
) -> dict:
    """Tek senaryoyu çalıştır ve skorla."""
    item_id = str(item["id"])
    result = {
        "id": item_id,
        "task_type": item.get("task_type", "unknown"),
        "task_description": str(item.get("user_request", ""))[:400],
        "hard": 0,
        "soft": 0.0,
        "components": {},
        "problems": [],
        "response": "",
        "fail_reason": "",
        "agent_ok": False,
    }

    pred_dir = os.path.join(out_root, "predictions", item_id)
    os.makedirs(pred_dir, exist_ok=True)
    conv_path = os.path.join(pred_dir, "conversation.json")
    if os.path.exists(conv_path):  # resume desteği
        try:
            with open(conv_path, encoding="utf-8") as f:
                cached = json.load(f)
            meta_path = os.path.join(pred_dir, "result.json")
            if os.path.exists(meta_path):
                with open(meta_path, encoding="utf-8") as f:
                    return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass

    system = build_system(skill_content)
    user = build_user(item)

    try:
        response, raw = chat_target(
            system=system,
            user=user,
            max_completion_tokens=max_completion_tokens,
            reasoning_effort="low",
            timeout=exec_timeout,
        )
        result["response"] = response or ""
        result["agent_ok"] = True
    except Exception as exc:  # backend hatası — item'ı sıfırla ama batch'i öldürme
        result["fail_reason"] = f"{type(exc).__name__}: {exc}"
        response = ""

    if result["agent_ok"]:
        scores = evaluate(result["response"], item)
        result.update(
            hard=scores["hard"],
            soft=scores["soft"],
            components=scores["components"],
            problems=scores["problems"],
        )
        if not result["hard"] and not result["fail_reason"]:
            result["fail_reason"] = "; ".join(scores["problems"][:5]) or "mandatory checks failed"

    conversation = [
        {"role": "user", "content": user},
        {"role": "agent", "content": result["response"]},
        {
            "role": "system",
            "content": json.dumps(
                {
                    "hard": result["hard"],
                    "soft": result["soft"],
                    "components": result["components"],
                    "problems": result["problems"],
                },
                ensure_ascii=False,
            ),
        },
    ]
    with open(conv_path, "w", encoding="utf-8") as f:
        json.dump(conversation, f, ensure_ascii=False, indent=2)
    with open(os.path.join(pred_dir, "result.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    return result


def run_batch(
    items: list[dict],
    out_root: str,
    skill_content: str,
    workers: int = 8,
    max_completion_tokens: int = 8192,
    exec_timeout: int = 300,
    **kwargs: object,
) -> list[dict]:
    """Senaryoları paralel çalıştır. Resume-aware (conversation.json varsa atlar)."""
    results: dict[str, dict] = {}
    pending = list(items)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(
                process_one,
                item=item,
                out_root=out_root,
                skill_content=skill_content,
                max_completion_tokens=max_completion_tokens,
                exec_timeout=exec_timeout,
                **kwargs,
            ): str(item["id"])
            for item in pending
        }
        todo = set(futures)
        while todo:
            done, todo = wait(todo, return_when=FIRST_COMPLETED)
            for fut in done:
                item_id = futures[fut]
                try:
                    results[item_id] = fut.result()
                except Exception as exc:
                    results[item_id] = {
                        "id": item_id,
                        "hard": 0,
                        "soft": 0.0,
                        "agent_ok": False,
                        "fail_reason": f"worker crash: {type(exc).__name__}: {exc}",
                    }
    return [results[str(item["id"])] for item in items]
