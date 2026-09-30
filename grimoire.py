#!/usr/bin/env python3
"""
Grimoire: Semantic Router & Dispatcher for Local Agent Skills using Jev

Takes unstructured natural language prompts, applies strict schema-guided
intent classification via the TypeSafe Jev model, and deterministically
executes the corresponding local agent skill via subprocess.
"""

import json
import os
import subprocess
import sys
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv
import requests
import typer

# Initialize environment variables
load_dotenv()

app = typer.Typer(
    name="grimoire",
    help="Grimoire: Semantic router and execution gateway for local agent skills.",
    add_completion=False,
)

# Configuration
TYPESAFE_API_KEY: Optional[str] = os.getenv("TYPESAFE_API_KEY")
TYPESAFE_API_ENDPOINT: str = os.getenv(
    "TYPESAFE_API_ENDPOINT", "https://api.typesafe.ai/v1/jev/extract"
)

# The registered agent skills (our global triad + fallback)
REGISTERED_SKILLS: List[str] = [
    "project-scoper",
    "test-automation",
    "doc-updater",
    "unsupported",
]

# Strict JSON Schema definition for TypeSafe Jev model extraction
ROUTING_SCHEMA: Dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "GrimoireSkillRouting",
    "description": "Structured routing decision mapping intent to local skill execution",
    "type": "object",
    "properties": {
        "selected_skill": {
            "type": "string",
            "enum": REGISTERED_SKILLS,
            "description": "The specific local agent skill to summon.",
        },
        "confidence_score": {
            "type": "number",
            "minimum": 0.0,
            "maximum": 1.0,
            "description": "Classification confidence score between 0.0 and 1.0.",
        },
        "extracted_context": {
            "type": "string",
            "description": "The extracted constraints, target files, or specific execution directives.",
        },
    },
    "required": ["selected_skill", "confidence_score", "extracted_context"],
    "additionalProperties": False,
}


def query_typesafe_jev(prompt: str, schema: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sends the user's unstructured prompt and strict schema to the TypeSafe Jev endpoint.
    Raises an explicit error if the API key is missing, unreachable, or returns a non-200 status.
    """
    if not TYPESAFE_API_KEY:
        typer.secho(
            "Error: TYPESAFE_API_KEY is not set. Please define it in your .env file.",
            fg=typer.colors.RED,
            bold=True,
            err=True,
        )
        raise typer.Exit(code=1)

    payload = {
        "prompt": prompt,
        "schema": schema,
        "model": "jev-1",
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {TYPESAFE_API_KEY}",
    }

    try:
        response = requests.post(
            TYPESAFE_API_ENDPOINT,
            headers=headers,
            json=payload,
            timeout=10,
        )
    except requests.exceptions.RequestException as err:
        typer.secho(
            f"Error: Failed to connect to TypeSafe API at {TYPESAFE_API_ENDPOINT}: {err}",
            fg=typer.colors.RED,
            bold=True,
            err=True,
        )
        raise typer.Exit(code=1)

    if response.status_code != 200:
        typer.secho(
            f"Error: TypeSafe API returned HTTP status {response.status_code}: {response.text}",
            fg=typer.colors.RED,
            bold=True,
            err=True,
        )
        raise typer.Exit(code=1)

    try:
        return response.json()
    except json.JSONDecodeError as err:
        typer.secho(
            f"Error: Failed to decode JSON from TypeSafe API response: {err}",
            fg=typer.colors.RED,
            bold=True,
            err=True,
        )
        raise typer.Exit(code=1)


def dispatch_skill(selected_skill: str, extracted_context: str) -> None:
    """
    Executes the summoned agent skill deterministically via subprocess.
    """
    cmd = [
        "gemini-cli",
        "--skill",
        selected_skill,
        "--prompt",
        extracted_context,
    ]

    typer.secho(
        f"\n[⚡ Grimoire] Summoning Skill: {selected_skill}",
        fg=typer.colors.BRIGHT_MAGENTA,
        bold=True,
    )
    typer.secho(
        f"       Executing command: {' '.join(cmd)}\n",
        fg=typer.colors.CYAN,
    )

    try:
        result = subprocess.run(cmd, check=False)
        if result.returncode != 0:
            typer.secho(
                f"[!] Subprocess exited with code {result.returncode}",
                fg=typer.colors.YELLOW,
            )
    except FileNotFoundError:
        typer.secho(
            f"[!] 'gemini-cli' binary not found in system PATH.",
            fg=typer.colors.YELLOW,
        )


@app.command()
def main(
    prompt: str = typer.Argument(
        ...,
        help="Natural language prompt describing the development task.",
    ),
) -> None:
    """
    Grimoire: Semantic router for developer workflows.
    Evaluates prompts, matches them to typed skills via TypeSafe Jev,
    and executes them deterministically.
    """
    typer.secho(
        "📖 Reading from the Grimoire...",
        fg=typer.colors.MAGENTA,
        bold=True,
    )

    # 1. Classification via TypeSafe Jev
    classification = query_typesafe_jev(prompt=prompt, schema=ROUTING_SCHEMA)

    selected_skill = classification.get("selected_skill", "unsupported")
    confidence = classification.get("confidence_score", 0.0)
    context = classification.get("extracted_context", prompt)

    # 2. Display Classification Telemetry
    typer.secho(
        f"  • Selected Skill : {selected_skill}",
        fg=typer.colors.GREEN if selected_skill != "unsupported" else typer.colors.RED,
    )
    typer.secho(
        f"  • Confidence     : {confidence * 100:.1f}%",
        fg=typer.colors.BLUE,
    )
    typer.secho(
        f"  • Context        : {context}",
        fg=typer.colors.WHITE,
    )

    # 3. Handle Unsupported Intents Gracefully
    if selected_skill == "unsupported":
        typer.secho(
            "\n⚠️  [Grimoire Warning] The Grimoire does not have a spell inscribed for this intent.",
            fg=typer.colors.RED,
            bold=True,
        )
        typer.secho(
            "💡 Suggestion: Summon 'project-scoper' to design and forge a new skill specification.\n"
            "   Example: python3 grimoire.py 'Use project-scoper to design a new agent skill for database migrations'",
            fg=typer.colors.YELLOW,
        )
        raise typer.Exit(code=1)

    # 4. Dispatch Skill
    dispatch_skill(selected_skill=selected_skill, extracted_context=context)


if __name__ == "__main__":
    app()
