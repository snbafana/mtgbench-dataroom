from __future__ import annotations

import json
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mtgbench_harness.card_tools import ScryfallClient, oracle_context_for_observation
from mtgbench_harness.codex_surface import render_codex_prompt, validate_codex_choice


class CodexCliError(RuntimeError):
    pass


@dataclass
class CodexCliAgent:
    """Agent that asks local `codex exec` to choose one legal action."""

    name: str = "codex-cli"
    model: str | None = None
    timeout_seconds: int = 180
    codex_bin: str = "codex"
    cwd: Path = Path(".")
    schema_path: Path = Path("schemas/codex_action.schema.json")
    include_oracle_context: bool = False
    scryfall: ScryfallClient | None = None
    last_response: dict[str, Any] | None = None

    def choose_action(self, observation: dict[str, Any]) -> int:
        oracle_context = None
        if self.include_oracle_context:
            oracle_context = oracle_context_for_observation(observation, client=self.scryfall)
        prompt = render_codex_prompt(observation, oracle_context=oracle_context)
        response = self._ask_codex(prompt)
        action_id = int(response["actionId"])
        validation = validate_codex_choice(observation, action_id)
        self.last_response = {**response, "validation": validation}
        if not validation["valid"]:
            raise CodexCliError(f"codex chose illegal action {action_id}; valid actions: {validation['validActionIds']}")
        return action_id

    def _ask_codex(self, prompt: str) -> dict[str, Any]:
        with tempfile.TemporaryDirectory(prefix="mtgbench-codex-") as tmp:
            out_path = Path(tmp) / "last_message.json"
            command = [
                self.codex_bin,
                "exec",
                "--ephemeral",
                "--skip-git-repo-check",
                "--sandbox",
                "read-only",
                "--output-schema",
                str(self.schema_path),
                "--output-last-message",
                str(out_path),
            ]
            if self.model:
                command.extend(["--model", self.model])
            command.append(prompt)
            completed = subprocess.run(
                command,
                cwd=self.cwd,
                check=False,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
            )
            if completed.returncode != 0:
                raise CodexCliError(
                    "codex exec failed with "
                    f"exit={completed.returncode}, stdout={completed.stdout[-2000:]}, stderr={completed.stderr[-2000:]}"
                )
            if not out_path.exists():
                raise CodexCliError(f"codex did not write {out_path}; stdout={completed.stdout[-2000:]}")
            raw = out_path.read_text().strip()
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise CodexCliError(f"codex output was not JSON: {raw[:2000]}") from exc
            if not isinstance(parsed, dict) or "actionId" not in parsed:
                raise CodexCliError(f"codex output missing actionId: {parsed!r}")
            return parsed
