from __future__ import annotations

from typing import Any

import pytest

from mtgbench_harness.match import acting_player_id, run_two_agent_match


def observation(
    player_id: str,
    action_id: int,
    *,
    terminated: bool = False,
    winner_id: str | None = None,
    players: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "schemaHash": "test",
        "turnNumber": 1,
        "phase": "MAIN",
        "step": "MAIN",
        "terminated": terminated,
        "winnerId": winner_id,
        "agentToAct": player_id,
        "activePlayerId": player_id,
        "priorityPlayerId": player_id,
        "stateDigest": f"digest-{player_id}-{action_id}-{terminated}",
        "players": players or [],
        "legalActions": []
        if terminated
        else [
            {
                "actionId": action_id,
                "kind": "TestAction",
                "description": f"Action {action_id}",
                "affordable": True,
            }
        ],
    }


class FakeClient:
    base_url = "fake://argentum"

    def __init__(self, observations: list[dict[str, Any]]):
        self.observations = observations
        self.index = 0
        self.actions: list[int] = []
        self.disposed: list[Any] = []

    def create(self, config: dict[str, Any]) -> dict[str, Any]:
        self.config = config
        return {"envId": "env-1", "observation": self.observations[0]}

    def step(self, env_id: str, action_id: int) -> dict[str, Any]:
        assert env_id == "env-1"
        self.actions.append(action_id)
        self.index += 1
        return self.observations[self.index]

    def dispose(self, env_ids: Any) -> dict[str, int]:
        self.disposed.append(env_ids)
        return {"status": 204}


class RecordingAgent:
    def __init__(self, name: str):
        self.name = name
        self.seen_players: list[str] = []

    def choose_action(self, observation: dict[str, Any]) -> int:
        self.seen_players.append(acting_player_id(observation))
        return int(observation["legalActions"][0]["actionId"])


def test_two_agent_match_routes_by_acting_player_until_terminal() -> None:
    client = FakeClient(
        [
            observation("p1", 11),
            observation("p2", 22),
            observation("p2", 0, terminated=True, winner_id="p2"),
        ]
    )
    agent_a = RecordingAgent("agent-a")
    agent_b = RecordingAgent("agent-b")

    result = run_two_agent_match(client, agent_a, agent_b, max_steps=8)

    assert client.actions == [11, 22]
    assert client.disposed == ["env-1"]
    assert agent_a.seen_players == ["p1"]
    assert agent_b.seen_players == ["p2"]
    assert result["terminated"] is True
    assert result["truncated"] is False
    assert result["winnerId"] == "p2"
    assert result["winnerSeat"] == "B"
    assert result["playerSeats"] == {"A": "p1", "B": "p2"}
    assert [event["seat"] for event in result["trace"] if event["event"] == "step"] == ["A", "B"]


def test_two_agent_match_uses_player_names_when_observation_exposes_players() -> None:
    players = [{"id": "bob-id", "name": "Bob"}, {"id": "alice-id", "name": "Alice"}]
    client = FakeClient(
        [
            observation("bob-id", 31, players=players),
            observation("alice-id", 32, players=players),
            observation("alice-id", 0, terminated=True, winner_id="alice-id", players=players),
        ]
    )
    agent_a = RecordingAgent("alice-agent")
    agent_b = RecordingAgent("bob-agent")

    result = run_two_agent_match(client, agent_a, agent_b, max_steps=8)

    assert client.actions == [31, 32]
    assert agent_a.seen_players == ["alice-id"]
    assert agent_b.seen_players == ["bob-id"]
    assert result["winnerSeat"] == "A"
    assert [event["seat"] for event in result["trace"] if event["event"] == "step"] == ["B", "A"]


def test_two_agent_match_truncates_at_max_steps() -> None:
    client = FakeClient(
        [
            observation("p1", 41),
            observation("p2", 42),
        ]
    )

    result = run_two_agent_match(client, RecordingAgent("a"), RecordingAgent("b"), max_steps=1)

    assert client.actions == [41]
    assert result["steps"] == 1
    assert result["terminated"] is False
    assert result["truncated"] is True


def test_two_agent_match_requires_positive_max_steps() -> None:
    with pytest.raises(ValueError, match="max_steps"):
        run_two_agent_match(FakeClient([observation("p1", 1)]), RecordingAgent("a"), RecordingAgent("b"), max_steps=0)
