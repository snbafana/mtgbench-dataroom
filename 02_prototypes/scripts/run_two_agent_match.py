#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from mtgbench_harness.agents import Agent, CodexHeuristicAgent, FirstLegalAgent
from mtgbench_harness.argentum import ArgentumClient
from mtgbench_harness.codex_cli import CodexCliAgent
from mtgbench_harness.match import run_two_agent_match


def default_output_path() -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return Path("02_prototypes") / "results" / f"two_agent_match_{stamp}.json"


def build_agent(name: str, args: argparse.Namespace) -> Agent:
    if name == "first-legal":
        return FirstLegalAgent()
    if name == "codex-heuristic":
        return CodexHeuristicAgent()
    if name == "codex-cli":
        return CodexCliAgent(
            model=args.codex_model,
            timeout_seconds=args.codex_timeout_seconds,
            cwd=Path.cwd(),
            schema_path=Path("schemas/codex_action.schema.json"),
            include_oracle_context=args.include_oracle_context,
        )
    raise ValueError(f"unknown agent: {name}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a two-agent match against Argentum.")
    parser.add_argument("--base-url", default="http://localhost:8081")
    parser.add_argument("--agent-a", choices=["first-legal", "codex-heuristic", "codex-cli"], default="first-legal")
    parser.add_argument("--agent-b", choices=["first-legal", "codex-heuristic", "codex-cli"], default="codex-heuristic")
    parser.add_argument("--max-steps", type=int, default=128)
    parser.add_argument("--codex-model", default=None)
    parser.add_argument("--codex-timeout-seconds", type=int, default=180)
    parser.add_argument("--include-oracle-context", action="store_true")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    output = args.output or default_output_path()
    output.parent.mkdir(parents=True, exist_ok=True)

    result: dict
    return_code = 0
    try:
        result = run_two_agent_match(
            ArgentumClient(args.base_url),
            build_agent(args.agent_a, args),
            build_agent(args.agent_b, args),
            max_steps=args.max_steps,
        )
        result["ok"] = True
    except Exception as exc:  # noqa: BLE001 - persist failure evidence.
        result = {
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
            "baseUrl": args.base_url,
            "agents": {"A": args.agent_a, "B": args.agent_b},
            "maxSteps": args.max_steps,
        }
        return_code = 1

    result["baseUrl"] = args.base_url
    result["writtenAt"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")

    print(f"wrote {output}")
    print(
        "ok={ok} steps={steps} terminated={terminated} truncated={truncated}".format(
            ok=result.get("ok"),
            steps=result.get("steps"),
            terminated=result.get("terminated"),
            truncated=result.get("truncated"),
        )
    )
    return return_code


if __name__ == "__main__":
    sys.exit(main())
