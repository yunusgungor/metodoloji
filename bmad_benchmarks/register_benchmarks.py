"""Register BMAD benchmarks with SkillOpt.

Import this module to register all BMAD environment adapters
with SkillOpt's built-in registry. Call register() before training.

Usage:
    from bmad_benchmarks.register_benchmarks import register
    register()
"""

_ENV_REGISTRY: dict = {}


def register():
    """Register all BMAD benchmark adapters."""
    try:
        from bmad_benchmarks.envs.bmad_code_review.adapter import BmadCodeReviewAdapter
        _ENV_REGISTRY["bmad-code-review"] = BmadCodeReviewAdapter
    except ImportError:
        pass

    try:
        from bmad_benchmarks.envs.bmad_create_story.adapter import BmadCreateStoryAdapter
        _ENV_REGISTRY["bmad-create-story"] = BmadCreateStoryAdapter
    except ImportError:
        pass

    try:
        from bmad_benchmarks.envs.bmad_architecture.adapter import BmadArchitectureAdapter
        _ENV_REGISTRY["bmad-architecture"] = BmadArchitectureAdapter
    except ImportError:
        pass

    try:
        from bmad_benchmarks.envs.bmad_prd.adapter import BmadPrdAdapter
        _ENV_REGISTRY["bmad-prd"] = BmadPrdAdapter
    except ImportError:
        pass

    try:
        from bmad_benchmarks.envs.bmad_test_design.adapter import BmadTestDesignAdapter
        _ENV_REGISTRY["bmad-test-design"] = BmadTestDesignAdapter
    except ImportError:
        pass

    return _ENV_REGISTRY
