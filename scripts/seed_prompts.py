#!/usr/bin/env python3
"""Seed MLflow Prompt Registry with starter prompts.

Idempotent: skips prompts that already exist.
Usage: uv run python scripts/seed_prompts.py
"""

from __future__ import annotations

import os
import sys

import mlflow

TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5050")

PROMPTS = [
    {
        "name": "assistant",
        "template": (
            "You are a helpful AI assistant. Respond clearly and concisely.\n\n"
            "User: {{ message }}\nAssistant:"
        ),
        "commit_message": "Initial general assistant prompt",
        "tags": {"use_case": "general"},
    },
    {
        "name": "summarizer",
        "template": (
            "Summarize the following text in {{ num_sentences }} sentences. "
            "Be factual and concise.\n\n"
            "Text: {{ text }}\n\nSummary:"
        ),
        "commit_message": "Initial summarization prompt",
        "tags": {"use_case": "summarization"},
    },
]


def prompt_exists(name: str) -> bool:
    """Check if a prompt already exists in the registry."""
    try:
        mlflow.genai.load_prompt(f"prompts:/{name}/1")
        return True
    except Exception:
        return False


def seed() -> None:
    mlflow.set_tracking_uri(TRACKING_URI)
    print(f"MLflow tracking URI: {TRACKING_URI}")

    for defn in PROMPTS:
        name = defn["name"]
        if prompt_exists(name):
            print(f"  [skip] '{name}' already exists")
            continue

        prompt = mlflow.genai.register_prompt(
            name=name,
            template=defn["template"],
            commit_message=defn["commit_message"],
            tags=defn["tags"],
        )
        print(f"  [created] '{name}' v{prompt.version}")

        mlflow.genai.set_prompt_alias(name=name, alias="production", version=int(prompt.version))
        print(f"  [alias] '{name}' → production = v{prompt.version}")

    print("Done.")


if __name__ == "__main__":
    try:
        seed()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
