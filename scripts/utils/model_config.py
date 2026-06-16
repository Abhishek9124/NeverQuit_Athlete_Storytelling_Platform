"""Single source of truth for every model the pipeline uses.

All agents, the LLM client, and the admin dashboard read model selection from
here — so swapping or adding a model is a one-line change in *one* file instead
of editing the client, six agents, and the dashboard separately.

Each role's model id is overridable by its env var, with no code change:

    NVIDIA_MODEL        — research / discovery / qa / social / translation
    NVIDIA_STORY_MODEL  — story writer

Token budgets and reasoning behaviour are declared per role below.
"""
from __future__ import annotations
import os

# Default per-call output budget. Override per role in ROLES if a task needs more.
DEFAULT_MAX_TOKENS = 20000

# Model families that expose a thinking / reasoning budget. The LLM client only
# attaches reasoning kwargs for these families, so requesting reasoning for any
# other model is a harmless no-op.
_REASONING_FAMILIES = ("nemotron", "glm")

# ── Per-role model configuration ───────────────────────────────────────────
#   env        : environment variable that overrides the model id
#   default    : model id used when the env var is unset
#   reasoning  : whether to request the model's thinking budget for this role
#   max_tokens : per-call output budget
ROLES: dict[str, dict] = {
    "discovery": {
        "env": "NVIDIA_MODEL",
        "default": "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning",
        "reasoning": False,
        "max_tokens": DEFAULT_MAX_TOKENS,
    },
    "research": {
        "env": "NVIDIA_MODEL",
        "default": "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning",
        "reasoning": True,
        "max_tokens": DEFAULT_MAX_TOKENS,
    },
    "story": {
        "env": "NVIDIA_STORY_MODEL",
        "default": "openai/gpt-oss-120b",
        "reasoning": False,
        "max_tokens": DEFAULT_MAX_TOKENS,
    },
    "qa": {
        "env": "NVIDIA_MODEL",
        "default": "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning",
        "reasoning": False,
        "max_tokens": DEFAULT_MAX_TOKENS,
    },
    "social": {
        "env": "NVIDIA_MODEL",
        "default": "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning",
        "reasoning": False,
        "max_tokens": DEFAULT_MAX_TOKENS,
    },
    "translation": {
        "env": "NVIDIA_MODEL",
        "default": "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning",
        "reasoning": False,
        "max_tokens": DEFAULT_MAX_TOKENS,
    },
}


def supports_reasoning(model_id: str) -> bool:
    """True if `model_id` belongs to a family that exposes a reasoning budget."""
    m = (model_id or "").lower()
    return any(fam in m for fam in _REASONING_FAMILIES)


def model_for(role: str) -> str:
    """Resolve the active model id for a role (env override wins over default)."""
    cfg = ROLES[role]
    return os.getenv(cfg["env"]) or cfg["default"]


def config_for(role: str) -> dict:
    """Resolved call settings for a role: {model, reasoning, max_tokens}."""
    cfg = ROLES[role]
    return {
        "model": model_for(role),
        "reasoning": cfg["reasoning"],
        "max_tokens": cfg["max_tokens"],
    }


# ── Selectable research models for the admin dashboard ─────────────────────
# The admin "Research" tool lets an editor pick which model builds the dossier.
# Exactly one entry should carry "default": True.
RESEARCH_MODEL_CHOICES: dict[str, dict] = {
    "gpt_oss": {
        "label": "GPT-OSS 120B  ✦ same as story writer",
        "model": "openai/gpt-oss-120b",
        "default": True,
        "description": "Slow but extremely thorough — same model that writes stories. ~60-90s.",
    },
    "nemotron": {
        "label": "NVIDIA Nemotron (Reasoning)",
        "model": "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning",
        "default": False,
        "description": "Advanced reasoning with focused thinking (~20-30s)",
    },
    "deepseek": {
        "label": "DeepSeek v4 Pro",
        "model": "deepseek-ai/deepseek-v4-pro",
        "default": False,
        "description": "Fast, high-quality research (~15-25s)",
    },
    "glm": {
        "label": "GLM 5.1 (Thinking)",
        "model": "z-ai/glm-5.1",
        "default": False,
        "description": "Advanced thinking model (~15-25s)",
    },
}


def default_research_key() -> str:
    """Key of the research model marked as default (falls back to 'nemotron')."""
    return next((k for k, v in RESEARCH_MODEL_CHOICES.items() if v.get("default")), "nemotron")
