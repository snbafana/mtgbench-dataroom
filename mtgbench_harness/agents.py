from __future__ import annotations

from typing import Any, Protocol

from mtgbench_harness.argentum import legal_actions


class Agent(Protocol):
    name: str

    def choose_action(self, observation: dict[str, Any]) -> int:
        ...


class FirstLegalAgent:
    name = "first-legal"

    def choose_action(self, observation: dict[str, Any]) -> int:
        actions = legal_actions(observation)
        if not actions:
            raise ValueError("observation has no legal actions")
        return int(actions[0]["actionId"])


class CodexHeuristicAgent:
    """A deterministic placeholder for the future Codex tool agent.

    It only chooses from the server-provided legal action mask. The scoring is
    intentionally simple so smokes verify harness behavior, not Magic strength.
    """

    name = "codex-heuristic"

    def choose_action(self, observation: dict[str, Any]) -> int:
        actions = legal_actions(observation)
        if not actions:
            raise ValueError("observation has no legal actions")
        ranked = sorted(actions, key=self._score_action, reverse=True)
        return int(ranked[0]["actionId"])

    @staticmethod
    def _score_action(action: dict[str, Any]) -> int:
        text = f"{action.get('kind', '')} {action.get('description', '')}".lower()
        score = 0
        if action.get("affordable") is False:
            score -= 100
        if "pass" in text:
            score -= 10
        if "play" in text and "land" in text:
            score += 35
        if "cast" in text:
            score += 30
        if "attack" in text:
            score += 25
        if "activate" in text:
            score += 20
        if "block" in text:
            score += 15
        if action.get("isDecisionOption"):
            score += 5
        return score
