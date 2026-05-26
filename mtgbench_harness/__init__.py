"""Prototype harness pieces for MTGBench."""

from mtgbench_harness.agents import CodexHeuristicAgent, FirstLegalAgent
from mtgbench_harness.argentum import ArgentumClient, default_explicit_config, summarize_observation
from mtgbench_harness.codex_cli import CodexCliAgent
from mtgbench_harness.codex_surface import render_codex_prompt, validate_codex_choice
from mtgbench_harness.gym_adapter import ArgentumGymAdapter, MoveValidationError
from mtgbench_harness.match import AgentRouter, acting_player_id, run_two_agent_match

__all__ = [
    "ArgentumClient",
    "ArgentumGymAdapter",
    "CodexCliAgent",
    "CodexHeuristicAgent",
    "FirstLegalAgent",
    "MoveValidationError",
    "AgentRouter",
    "acting_player_id",
    "default_explicit_config",
    "render_codex_prompt",
    "run_two_agent_match",
    "summarize_observation",
    "validate_codex_choice",
]
