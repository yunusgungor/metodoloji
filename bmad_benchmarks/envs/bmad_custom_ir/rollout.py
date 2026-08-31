from .._base_.rollout import run_custom_batch

_FIELDS = [
    ("Research Inputs", "research_inputs"),
    ("Design Docs", "design_docs"),
    ("Dependencies", "dependencies"),
]


def run_batch(items, skill_content, out_dir, workers=1, max_completion_tokens=4096):
    return run_custom_batch(
        items, skill_content, out_dir, "Implementation Readiness (IR)", _FIELDS,
        "custom-ir", workers=workers, max_completion_tokens=max_completion_tokens,
    )
