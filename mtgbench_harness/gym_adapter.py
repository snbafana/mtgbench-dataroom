from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from mtgbench_harness.argentum import ArgentumClient, agent_view, default_explicit_config, legal_actions


class MoveValidationError(ValueError):
    def __init__(self, action_id: int, valid_action_ids: list[int]):
        super().__init__(f"actionId {action_id} is not legal in the current observation")
        self.action_id = action_id
        self.valid_action_ids = valid_action_ids


@dataclass
class ArgentumGymAdapter:
    """Gymnasium-shaped adapter over Argentum's HTTP gym-server."""

    client: ArgentumClient
    config: dict[str, Any] = field(default_factory=default_explicit_config)
    env_id: str | None = None
    observation: dict[str, Any] | None = None
    step_count: int = 0

    def reset(self) -> tuple[dict[str, Any], dict[str, Any]]:
        if self.env_id:
            self.close()
        created = self.client.create(self.config)
        self.env_id = str(created["envId"])
        self.observation = created["observation"]
        self.step_count = 0
        return self.observation, {"envId": self.env_id, "agentView": agent_view(self.observation)}

    def available_action_ids(self) -> list[int]:
        if self.observation is None:
            return []
        return [int(action["actionId"]) for action in legal_actions(self.observation)]

    def validate_action(self, action_id: int) -> None:
        valid = self.available_action_ids()
        if action_id not in valid:
            raise MoveValidationError(action_id, valid)

    def step(self, action_id: int) -> tuple[dict[str, Any], float, bool, bool, dict[str, Any]]:
        if not self.env_id or self.observation is None:
            raise RuntimeError("reset must be called before step")
        self.validate_action(action_id)
        self.observation = self.client.step(self.env_id, action_id)
        self.step_count += 1
        terminated = bool(self.observation.get("terminated"))
        reward = self._reward(self.observation)
        info = {
            "envId": self.env_id,
            "validatedActionId": action_id,
            "agentView": agent_view(self.observation),
        }
        return self.observation, reward, terminated, False, info

    def close(self) -> None:
        if self.env_id:
            self.client.dispose(self.env_id)
        self.env_id = None
        self.observation = None

    @staticmethod
    def _reward(observation: dict[str, Any]) -> float:
        if not observation.get("terminated"):
            return 0.0
        return 1.0 if observation.get("winnerId") == observation.get("perspectivePlayerId") else -1.0
