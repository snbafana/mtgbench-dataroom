#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from mtgbench_harness.argentum import ArgentumClient, summarize_observation
from mtgbench_harness.codex_cli import CodexCliAgent
from mtgbench_harness.gym_adapter import ArgentumGymAdapter


def default_output_path() -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return Path("02_prototypes") / "results" / f"codex_cli_episode_{stamp}.json"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a short Codex CLI episode against Argentum.")
    parser.add_argument("--base-url", default="http://localhost:8081")
    parser.add_argument("--steps", type=int, default=1)
    parser.add_argument("--model", default=None)
    parser.add_argument("--timeout-seconds", type=int, default=180)
    parser.add_argument("--include-oracle-context", action="store_true")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    output = args.output or default_output_path()
    output.parent.mkdir(parents=True, exist_ok=True)

    adapter = ArgentumGymAdapter(ArgentumClient(args.base_url))
    agent = CodexCliAgent(
        model=args.model,
        timeout_seconds=args.timeout_seconds,
        cwd=Path.cwd(),
        schema_path=Path("schemas/codex_action.schema.json"),
        include_oracle_context=args.include_oracle_context,
    )
    trace: list[dict] = []
    ok = False
    try:
        observation, info = adapter.reset()
        trace.append({"event": "reset", "observation": summarize_observation(observation)})
        for _ in range(args.steps):
            before = summarize_observation(observation)
            action_id = agent.choose_action(observation)
            observation, reward, terminated, truncated, step_info = adapter.step(action_id)
            trace.append(
                {
                    "event": "codex_step",
                    "actionId": action_id,
                    "before": before,
                    "codexResponse": agent.last_response,
                    "reward": reward,
                    "terminated": terminated,
                    "truncated": truncated,
                    "observation": summarize_observation(observation),
                }
            )
            if terminated:
                break
        ok = True
        return_code = 0
    except Exception as exc:  # noqa: BLE001 - persist failure evidence.
        trace.append({"event": "error", "error": f"{type(exc).__name__}: {exc}"})
        return_code = 1
    finally:
        adapter.close()

    result = {
        "ok": ok,
        "baseUrl": args.base_url,
        "requestedSteps": args.steps,
        "model": args.model,
        "writtenAt": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "trace": trace,
    }
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(f"wrote {output}")
    print(f"ok={ok} events={len(trace)}")
    return return_code


if __name__ == "__main__":
    sys.exit(main())
