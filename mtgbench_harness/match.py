from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from mtgbench_harness.agents import Agent
from mtgbench_harness.argentum import ArgentumClient, default_explicit_config, summarize_observation
from mtgbench_harness.gym_adapter import ArgentumGymAdapter


def acting_player_id(observation: dict[str, Any]) -> str:
    for key in ("agentToAct", "priorityPlayerId", "activePlayerId"):
        value = observation.get(key)
        if isinstance(value, str) and value:
            return value
    raise ValueError("observation does not identify the acting player")


def _player_id(player: dict[str, Any]) -> str | None:
    for key in ("id", "playerId", "uuid"):
        value = player.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _seed_seats_from_players(observation: dict[str, Any], config: dict[str, Any], labels: tuple[str, str]) -> dict[str, str]:
    players = observation.get("players")
    if not isinstance(players, list):
        return {}

    config_names = [player.get("name") for player in config.get("players", []) if isinstance(player, dict)]
    name_to_label = {
        name: labels[index]
        for index, name in enumerate(config_names[: len(labels)])
        if isinstance(name, str) and name
    }

    seats: dict[str, str] = {}
    for index, player in enumerate(players[: len(labels)]):
        if not isinstance(player, dict):
            continue
        player_id = _player_id(player)
        if not player_id:
            continue
        label = name_to_label.get(player.get("name"))
        if label is None and index < len(labels):
            label = labels[index]
        if label:
            seats[player_id] = label
    return seats


@dataclass
class AgentRouter:
    """Assigns newly seen Argentum player ids to the two configured agents."""

    agent_a: Agent
    agent_b: Agent
    config: dict[str, Any]
    labels: tuple[str, str] = ("A", "B")
    player_seats: dict[str, str] = field(default_factory=dict)

    def seed(self, observation: dict[str, Any]) -> None:
        if not self.player_seats:
            self.player_seats.update(_seed_seats_from_players(observation, self.config, self.labels))

    def agent_for(self, observation: dict[str, Any]) -> tuple[str, str, Agent]:
        self.seed(observation)
        player_id = acting_player_id(observation)
        if player_id not in self.player_seats:
            if len(self.player_seats) >= len(self.labels):
                known = ", ".join(sorted(self.player_seats))
                raise ValueError(f"acting player {player_id} is not one of the two match players: {known}")
            self.player_seats[player_id] = self.labels[len(self.player_seats)]
        seat = self.player_seats[player_id]
        agent = self.agent_a if seat == self.labels[0] else self.agent_b
        return seat, player_id, agent

    def winner_seat(self, observation: dict[str, Any]) -> str | None:
        winner_id = observation.get("winnerId")
        if not isinstance(winner_id, str):
            return None
        return self.player_seats.get(winner_id)

    def summary(self) -> dict[str, str | None]:
        seats_by_label = {label: None for label in self.labels}
        for player_id, label in self.player_seats.items():
            seats_by_label[label] = player_id
        return seats_by_label


def _agent_name(agent: Agent) -> str:
    return str(getattr(agent, "name", agent.__class__.__name__))


def _last_response(agent: Agent) -> Any | None:
    response = getattr(agent, "last_response", None)
    return response if response is not None else None


def run_two_agent_match(
    client: ArgentumClient,
    agent_a: Agent,
    agent_b: Agent,
    *,
    max_steps: int = 256,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if max_steps < 1:
        raise ValueError("max_steps must be at least 1")

    match_config = config or default_explicit_config()
    adapter = ArgentumGymAdapter(client, config=match_config)
    router = AgentRouter(agent_a=agent_a, agent_b=agent_b, config=match_config)
    trace: list[dict[str, Any]] = []
    observation: dict[str, Any] | None = None
    info: dict[str, Any] = {}
    terminated = False

    try:
        observation, info = adapter.reset()
        router.seed(observation)
        trace.append(
            {
                "event": "reset",
                "observation": summarize_observation(observation),
                "playerSeats": router.summary(),
            }
        )

        while not terminated and adapter.step_count < max_steps:
            seat, player_id, agent = router.agent_for(observation)
            action_id = int(agent.choose_action(observation))
            before = summarize_observation(observation)
            observation, reward, terminated, truncated, info = adapter.step(action_id)
            decision: dict[str, Any] = {
                "event": "step",
                "step": adapter.step_count,
                "seat": seat,
                "playerId": player_id,
                "agent": _agent_name(agent),
                "actionId": action_id,
                "before": before,
                "reward": reward,
                "terminated": terminated,
                "truncated": truncated,
                "observation": summarize_observation(observation),
                "playerSeats": router.summary(),
            }
            response = _last_response(agent)
            if response is not None:
                decision["agentResponse"] = response
            trace.append(decision)

        truncated = not terminated and adapter.step_count >= max_steps
        winner_id = observation.get("winnerId") if observation else None
        return {
            "envId": info.get("envId"),
            "agents": {
                "A": _agent_name(agent_a),
                "B": _agent_name(agent_b),
            },
            "playerSeats": router.summary(),
            "steps": adapter.step_count,
            "maxSteps": max_steps,
            "terminated": terminated,
            "truncated": truncated,
            "winnerId": winner_id,
            "winnerSeat": router.winner_seat(observation or {}),
            "finalObservation": summarize_observation(observation) if observation else None,
            "trace": trace,
        }
    finally:
        adapter.close()
