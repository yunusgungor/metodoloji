#!/usr/bin/env python3
"""9Router chat shim for run_evals.py (stdlib only, no deps).

Usage: run_9router.py "<prompt>" <cwd> — calls
$NINEROUTER_URL/v1/chat/completions with $NINEROUTER_MODEL, prints a two-line
JSONL transcript on stdout:
  {"type":"assistant","message":{"content":[{"type":"text","text":"..."}]}}
  {"type":"result","usage":{"input_tokens":N,"output_tokens":M}}
run_evals.py's account_transcript() understands both lines, so token counts
survive. Exit non-zero (→ "error" status) when env is missing or the call fails.
"""
import json
import os
import sys
import urllib.request


def fail(msg: str) -> int:
    print(f"9router shim: {msg}", file=sys.stderr)
    return 1


def main() -> int:
    if len(sys.argv) < 3:
        return fail("usage: run_9router.py <prompt> <cwd>")
    url = os.environ.get("NINEROUTER_URL", "").rstrip("/")
    key = os.environ.get("NINEROUTER_KEY", "")
    model = os.environ.get("NINEROUTER_MODEL", "")
    if not url or not model:
        return fail("NINEROUTER_URL and NINEROUTER_MODEL must be set")
    prompt = sys.argv[1]
    body = json.dumps({
        "model": model,
        "stream": False,
        "messages": [
            {"role": "system", "content": (
                "You are the bmad-research-experiment skill. Enforce the "
                "Theory-Hypothesis-Experiment-Measurement-Approval gate. "
                "Never approve a hypothesis without a measurement. "
                "The gate command is: python3 "
                "{skill-root}/scripts/run_experiment.py --record "
                "docs/experiments/<id>.md --run \"<measurement command>\"; "
                "use --dry-run for format checks (a --run without it WRITES "
                "a real decision). Records live under docs/experiments/.")},
            {"role": "user", "content": prompt},
        ],
    }).encode()
    req = urllib.request.Request(
        url + "/v1/chat/completions", data=body,
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {key}"})
    try:
        with urllib.request.urlopen(req, timeout=280) as r:
            res = json.loads(r.read().decode())
    except Exception as e:  # noqa: BLE001 — shim reports, runner records
        return fail(f"chat call failed: {e}")
    try:
        text = res["choices"][0]["message"]["content"] or ""
        usage = res.get("usage", {})
    except (KeyError, IndexError, TypeError) as e:
        return fail(f"unexpected response shape: {e}")
    print(json.dumps({"type": "assistant",
                      "message": {"content": [{"type": "text",
                                               "text": text}]}}))
    print(json.dumps({"type": "result", "usage": {
        "input_tokens": usage.get("prompt_tokens", 0),
        "output_tokens": usage.get("completion_tokens", 0)}}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
