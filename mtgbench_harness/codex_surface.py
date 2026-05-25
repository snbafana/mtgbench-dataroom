from __future__ import annotations

import json
from typing import Any

from mtgbench_harness.argentum import agent_view, legal_actions


TOOL_SPECS: list[dict[str, Any]] = [
    {
        "name": "choose_action",
        "purpose": "Commit one legal actionId from the current Argentum observation.",
        "input": {"actionId": "integer"},
    },
    {
        "name": "get_oracle_text",
        "purpose": "Look up exact oracle text for a visible or named card.",
        "input": {"cardName": "string"},
    },
    {
        "name": "search_cards",
        "purpose": "Search the local Scryfall/MTGJSON card warehouse.",
        "input": {"query": "string"},
    },
    {
        "name": "simulate_action",
        "purpose": "Use fork/snapshot support to inspect an action line without mutating the source env.",
        "input": {"actionId": "integer", "rolloutSteps": "integer"},
    },
]


def render_codex_prompt(observation: dict[str, Any], *, oracle_context: list[dict[str, Any]] | None = None) -> str:
    view = agent_view(observation)
    payload = {
        "state": view["state"],
        "visibleCards": view["visibleCards"],
        "oracleContext": oracle_context or [],
        "legalActions": view["legalActions"],
        "tools": TOOL_SPECS,
    }
    return "\n".join(
        [
            "You are playing Magic: The Gathering through Argentum.",
            "Choose exactly one actionId from legalActions. Do not invent actions.",
            "Use tool calls for card text or simulation only when needed.",
            json.dumps(payload, indent=2, sort_keys=True),
        ]
    )


def validate_codex_choice(observation: dict[str, Any], action_id: int) -> dict[str, Any]:
    ids = [int(action["actionId"]) for action in legal_actions(observation)]
    return {"actionId": action_id, "validActionIds": ids, "valid": action_id in ids}
