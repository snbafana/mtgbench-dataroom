#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from mtgbench_harness.argentum import ArgentumClient
from mtgbench_harness.smokes import run_smokes


def default_output_path() -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return Path("02_prototypes") / "results" / f"argentum_smokes_{stamp}.json"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Argentum-backed MTGBench smoke tests.")
    parser.add_argument("--base-url", default="http://localhost:8081")
    parser.add_argument("--max-steps", type=int, default=12)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    output = args.output or default_output_path()
    output.parent.mkdir(parents=True, exist_ok=True)
    result = run_smokes(ArgentumClient(args.base_url), max_steps=args.max_steps)
    result["writtenAt"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")

    print(f"wrote {output}")
    print(f"passed={result['passed']} failed={result['failed']}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
