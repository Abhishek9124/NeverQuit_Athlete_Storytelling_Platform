"""Deprecated alias kept for older pipeline imports.

All current LLM calls route through NVIDIA's OpenAI-compatible API.
"""
from scripts.utils.nvidia_client import complete, complete_json, MODEL, client, parse_json  # noqa: F401
