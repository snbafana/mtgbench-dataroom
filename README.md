# MTGBench Dataroom

Research repo for getting Codex-style agents to play Magic: The Gathering through an open rules engine.

The current verified path is:

1. Argentum `gym-server` produces observations and legal action masks.
2. `mtgbench_harness` renders a Codex-facing state/action/tool surface.
3. Local `codex exec` returns schema-valid JSON.
4. The harness validates the selected `actionId`.
5. Argentum executes the move.
6. The two-agent match runner routes each decision to the agent seated for the current Argentum player id.

## Quick Start

Install Python deps:

```bash
uv sync --dev
uv run pytest -q
```

Clone and run Argentum separately:

```bash
mkdir -p 05_evidence/repos
git clone --depth 1 https://github.com/wingedsheep/argentum-engine.git 05_evidence/repos/argentum-engine
cd 05_evidence/repos/argentum-engine
JAVA_HOME=/opt/homebrew/opt/openjdk@21 ./gradlew :gym-server:bootRun --no-daemon
```

From this repo root, run live smokes:

```bash
uv run python 02_prototypes/scripts/run_argentum_smokes.py --max-steps 64
```

Run a real Codex CLI episode:

```bash
uv run python 02_prototypes/scripts/run_codex_cli_episode.py --steps 8 --include-oracle-context
```

Run a two-agent Argentum match:

```bash
uv run python 02_prototypes/scripts/run_two_agent_match.py --agent-a first-legal --agent-b codex-heuristic --max-steps 128
```

## Dependencies

See [DEPENDENCIES.md](DEPENDENCIES.md).

Short version:

- `uv`
- Python 3.11+
- Java 21 for Argentum
- local `codex` CLI for real Codex episodes
- network access for Scryfall/source probes

Runtime Python code is stdlib-only. `pytest` is the only dev dependency.

## Read First

1. `06_decisions/0003-codex-cli-agent.md` - current Codex player decision.
2. `06_decisions/0004-two-agent-argentum-harness.md` - two-agent match runner decision.
3. `02_prototypes/results/two_agent_match_20260525T2031Z.md` - full heuristic-vs-heuristic game evidence.
4. `02_prototypes/results/codex_cli_episodes_20260525.md` - real Codex run evidence.
5. `06_decisions/0002-uv-harness-shape.md` - uv harness shape.
6. `03_architecture/implementation_detail.md` - proposed MTGBench architecture and first milestone.
7. `01_landscape/open_engines_and_products.md` - engine and product landscape.

## Layout

- `mtgbench_harness/`: reusable Python harness.
- `schemas/`: structured output schema for Codex action choices.
- `tests/`: pure uv/pytest checks.
- `02_prototypes/scripts/`: minimal runnable scripts.
- `02_prototypes/results/`: small evidence snapshots.
- `00_admin/`, `01_landscape/`, `03_architecture/`, `04_datasets/`, `06_decisions/`: research dataroom docs.
- `05_evidence/repos/`: ignored local engine checkouts.

## Minimal Scripts

- `02_prototypes/scripts/run_argentum_smokes.py`
- `02_prototypes/scripts/run_codex_cli_episode.py`
- `02_prototypes/scripts/run_two_agent_match.py`
- `02_prototypes/scripts/probe_mtg_sources.py`

## Evidence Snapshots

- `02_prototypes/results/codex_cli_episodes_20260525.md` - real Codex CLI episodes.
- `02_prototypes/results/two_agent_match_20260525T2031Z.md` - two-agent Argentum match summary, including full terminal heuristic game.
- `02_prototypes/results/two_agent_match_20260525T2030Z.json` - raw mixed-agent route smoke.
- `02_prototypes/results/argentum_smokes_20260525T2030Z.json` - raw 13-smoke live run with two-agent match coverage.
- `02_prototypes/results/argentum_harness_smokes_20260525T0339Z.md` - uv harness and live smoke summary.
- `02_prototypes/results/argentum_smokes_20260525T0339Z.json` - raw 12-smoke live run.
- `02_prototypes/results/source_probe_20260524T230431Z.json` - live API/source probe.
- `02_prototypes/results/magebench_smoke_20260524T2312Z.md` - mage-bench clone/build/run smoke.

## Current Status

Codex can legally play through the harness, including a 16-step episode that played `Mountain` and cast `Raging Goblin`. The two-agent Argentum runner can also complete a heuristic-vs-heuristic game to terminal state. The remaining research problem is action-window compression, hidden-information perspective handling, card/action coverage, and play quality, not basic move legality.

## Older Research Index

1. `03_architecture/implementation_detail.md` - proposed MTGBench architecture and first milestone.
2. `06_decisions/0001-first-engine-spike.md` - current engine decision.
3. `01_landscape/apis_and_data.md` - open card/data/API sources.
4. `01_landscape/open_engines_and_products.md` - engine and product landscape.
5. `01_landscape/game_ai_precedents.md` - LLM/game-agent precedent map.
