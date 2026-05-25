from __future__ import annotations

import pytest

from mtgbench_harness.agents import CodexHeuristicAgent, FirstLegalAgent
from mtgbench_harness.argentum import agent_view, summarize_observation
from mtgbench_harness.card_tools import ScryfallClient, oracle_context_for_observation
from mtgbench_harness.codex_cli import CodexCliAgent
from mtgbench_harness.codex_surface import render_codex_prompt, validate_codex_choice
from mtgbench_harness.gym_adapter import ArgentumGymAdapter, MoveValidationError


def observation_with_actions() -> dict:
    return {
        "turnNumber": 1,
        "phase": "PRECOMBAT_MAIN",
        "step": "PRECOMBAT_MAIN",
        "stateDigest": "abc",
        "legalActions": [
            {"actionId": 0, "kind": "PassPriority", "description": "Pass priority", "affordable": True},
            {"actionId": 1, "kind": "PlayLand", "description": "Play Mountain", "affordable": True},
        ],
        "zones": [{"cards": [{"name": "Mountain"}]}],
    }


def test_summarize_observation_counts_legal_actions() -> None:
    summary = summarize_observation(observation_with_actions())
    assert summary["legalActionCount"] == 2
    assert summary["firstAction"]["kind"] == "PassPriority"


def test_codex_heuristic_prefers_non_pass_legal_action() -> None:
    assert CodexHeuristicAgent().choose_action(observation_with_actions()) == 1
    assert FirstLegalAgent().choose_action(observation_with_actions()) == 0


def test_agent_view_exposes_state_actions_and_visible_cards() -> None:
    view = agent_view(observation_with_actions())
    assert view["state"]["phase"] == "PRECOMBAT_MAIN"
    assert view["legalActions"][1]["description"] == "Play Mountain"
    assert view["visibleCards"] == ["Mountain"]


def test_codex_prompt_contains_tool_surface_and_legal_action_mask() -> None:
    prompt = render_codex_prompt(observation_with_actions(), oracle_context=[{"name": "Mountain", "oracleText": "{T}: Add {R}."}])
    assert "choose_action" in prompt
    assert "simulate_action" in prompt
    assert "{T}: Add {R}." in prompt
    assert '"actionId": 1' in prompt
    assert validate_codex_choice(observation_with_actions(), 1)["valid"] is True
    assert validate_codex_choice(observation_with_actions(), 999)["valid"] is False


def test_adapter_rejects_action_missing_from_current_legal_mask() -> None:
    adapter = ArgentumGymAdapter(client=None)  # type: ignore[arg-type]
    adapter.observation = observation_with_actions()
    with pytest.raises(MoveValidationError) as raised:
        adapter.validate_action(999)
    assert raised.value.valid_action_ids == [0, 1]


def test_codex_cli_agent_validates_parsed_action(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    schema = tmp_path / "schema.json"
    schema.write_text("{}")

    def fake_ask_codex(self: CodexCliAgent, prompt: str) -> dict:
        assert "legalActions" in prompt
        return {"actionId": 1, "reason": "Play the land instead of passing."}

    monkeypatch.setattr(CodexCliAgent, "_ask_codex", fake_ask_codex)
    agent = CodexCliAgent(cwd=tmp_path, schema_path=schema)
    assert agent.choose_action(observation_with_actions()) == 1
    assert agent.last_response["validation"]["valid"] is True


def test_oracle_context_for_observation_uses_visible_cards(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeScryfall(ScryfallClient):
        def named(self, card_name: str) -> dict:
            return {"name": card_name, "oracleText": f"oracle for {card_name}"}

    context = oracle_context_for_observation(observation_with_actions(), client=FakeScryfall())
    assert context == [{"name": "Mountain", "oracleText": "oracle for Mountain"}]
