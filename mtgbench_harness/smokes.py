from __future__ import annotations

import time
from typing import Any, Callable

from mtgbench_harness.agents import CodexHeuristicAgent, FirstLegalAgent
from mtgbench_harness.argentum import (
    ArgentumClient,
    ArgentumHttpError,
    agent_view,
    default_explicit_config,
    legal_actions,
    summarize_observation,
)
from mtgbench_harness.codex_surface import render_codex_prompt, validate_codex_choice
from mtgbench_harness.gym_adapter import ArgentumGymAdapter, MoveValidationError
from mtgbench_harness.match import run_two_agent_match


SmokeFn = Callable[[], dict[str, Any]]


def _run_named(name: str, fn: SmokeFn) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        details = fn()
        return {"name": name, "ok": True, "elapsedMs": round((time.perf_counter() - started) * 1000), "details": details}
    except Exception as exc:  # noqa: BLE001 - smoke output should preserve failures.
        return {
            "name": name,
            "ok": False,
            "elapsedMs": round((time.perf_counter() - started) * 1000),
            "error": f"{type(exc).__name__}: {exc}",
        }


def _create(client: ArgentumClient) -> tuple[str, dict[str, Any]]:
    created = client.create(default_explicit_config())
    return str(created["envId"]), created["observation"]


def run_smokes(client: ArgentumClient, *, max_steps: int = 12) -> dict[str, Any]:
    def health_schema() -> dict[str, Any]:
        return {"health": client.health(), "schemaHash": client.schema_hash()}

    def create_observe_dispose() -> dict[str, Any]:
        env_id, opening = _create(client)
        try:
            observed = client.observe(env_id)
            return {
                "envId": env_id,
                "opening": summarize_observation(opening),
                "observed": summarize_observation(observed),
            }
        finally:
            client.dispose(env_id)

    def local_validation_rejects_illegal_move() -> dict[str, Any]:
        adapter = ArgentumGymAdapter(client)
        try:
            observation, _ = adapter.reset()
            valid = adapter.available_action_ids()
            try:
                adapter.step(999999)
            except MoveValidationError as exc:
                return {"validActionIds": valid, "rejectedActionId": exc.action_id}
            raise AssertionError("invalid action was not rejected locally")
        finally:
            adapter.close()

    def server_rejects_bad_action() -> dict[str, Any]:
        env_id, opening = _create(client)
        try:
            try:
                client.step(env_id, 999999)
            except ArgentumHttpError as exc:
                return {"status": exc.status, "opening": summarize_observation(opening)}
            raise AssertionError("server accepted an out-of-range action")
        finally:
            client.dispose(env_id)

    def first_legal_episode() -> dict[str, Any]:
        return run_two_agent_match(client, FirstLegalAgent(), FirstLegalAgent(), max_steps=max_steps)

    def codex_heuristic_episode() -> dict[str, Any]:
        return run_two_agent_match(client, CodexHeuristicAgent(), CodexHeuristicAgent(), max_steps=max_steps)

    def first_vs_codex_heuristic_match() -> dict[str, Any]:
        return run_two_agent_match(client, FirstLegalAgent(), CodexHeuristicAgent(), max_steps=max_steps)

    def snapshot_restore_roundtrip() -> dict[str, Any]:
        env_id, opening = _create(client)
        try:
            start_digest = opening.get("stateDigest")
            handle = client.snapshot(env_id)
            action_id = int(legal_actions(opening)[0]["actionId"])
            after_step = client.step(env_id, action_id)
            restored = client.restore(env_id, handle)
            return {
                "snapshot": handle,
                "startDigest": start_digest,
                "afterStepDigest": after_step.get("stateDigest"),
                "restoredDigest": restored.get("stateDigest"),
                "restoredMatchesStart": restored.get("stateDigest") == start_digest,
            }
        finally:
            client.dispose(env_id)

    def fork_two_envs() -> dict[str, Any]:
        env_id, opening = _create(client)
        fork_ids: list[str] = []
        try:
            fork_ids = [str(item) for item in client.fork(env_id, count=2)]
            source_before = client.observe(env_id)
            fork_obs = [client.observe(fork_id) for fork_id in fork_ids]
            action_id = int(legal_actions(fork_obs[0])[0]["actionId"])
            fork_after = client.step(fork_ids[0], action_id)
            source_after = client.observe(env_id)
            return {
                "sourceDigestBefore": source_before.get("stateDigest"),
                "sourceDigestAfter": source_after.get("stateDigest"),
                "forkDigests": [obs.get("stateDigest") for obs in fork_obs],
                "steppedForkDigest": fork_after.get("stateDigest"),
                "sourceUnchanged": source_before.get("stateDigest") == source_after.get("stateDigest"),
            }
        finally:
            client.dispose([env_id, *fork_ids])

    def step_batch_two_envs() -> dict[str, Any]:
        envs: list[str] = []
        try:
            first_id, first_obs = _create(client)
            second_id, second_obs = _create(client)
            envs.extend([first_id, second_id])
            response = client.step_batch(
                [
                    {"envId": first_id, "actionId": int(legal_actions(first_obs)[0]["actionId"])},
                    {"envId": second_id, "actionId": int(legal_actions(second_obs)[0]["actionId"])},
                ]
            )
            return {"resultCount": len(response), "envIds": [item.get("envId") for item in response]}
        finally:
            client.dispose(envs)

    def reveal_all_toggle() -> dict[str, Any]:
        env_id, _ = _create(client)
        try:
            hidden = client.observe(env_id, reveal_all=False)
            revealed = client.observe(env_id, reveal_all=True)
            return {
                "hiddenBytes": len(str(hidden)),
                "revealedBytes": len(str(revealed)),
                "hidden": summarize_observation(hidden),
                "revealed": summarize_observation(revealed),
            }
        finally:
            client.dispose(env_id)

    def codex_agent_view_surface() -> dict[str, Any]:
        env_id, opening = _create(client)
        try:
            view = agent_view(opening)
            return {
                "stateKeys": sorted(view["state"].keys()),
                "legalActionCount": len(view["legalActions"]),
                "visibleCardCount": len(view["visibleCards"]),
                "firstAction": view["legalActions"][0] if view["legalActions"] else None,
            }
        finally:
            client.dispose(env_id)

    def codex_prompt_and_choice_validation() -> dict[str, Any]:
        env_id, opening = _create(client)
        try:
            prompt = render_codex_prompt(opening)
            action_id = CodexHeuristicAgent().choose_action(opening)
            validation = validate_codex_choice(opening, action_id)
            assert validation["valid"], validation
            return {
                "promptChars": len(prompt),
                "containsLegalActions": "legalActions" in prompt,
                "containsToolSpecs": "choose_action" in prompt and "simulate_action" in prompt,
                "chosenAction": validation,
            }
        finally:
            client.dispose(env_id)

    smoke_fns: list[tuple[str, SmokeFn]] = [
        ("health_schema", health_schema),
        ("create_observe_dispose", create_observe_dispose),
        ("local_validation_rejects_illegal_move", local_validation_rejects_illegal_move),
        ("server_rejects_bad_action", server_rejects_bad_action),
        ("first_legal_episode", first_legal_episode),
        ("codex_heuristic_episode", codex_heuristic_episode),
        ("first_vs_codex_heuristic_match", first_vs_codex_heuristic_match),
        ("snapshot_restore_roundtrip", snapshot_restore_roundtrip),
        ("fork_two_envs", fork_two_envs),
        ("step_batch_two_envs", step_batch_two_envs),
        ("reveal_all_toggle", reveal_all_toggle),
        ("codex_agent_view_surface", codex_agent_view_surface),
        ("codex_prompt_and_choice_validation", codex_prompt_and_choice_validation),
    ]
    results = [_run_named(name, fn) for name, fn in smoke_fns]
    return {
        "baseUrl": client.base_url,
        "maxSteps": max_steps,
        "ok": all(result["ok"] for result in results),
        "passed": sum(1 for result in results if result["ok"]),
        "failed": sum(1 for result in results if not result["ok"]),
        "results": results,
    }
