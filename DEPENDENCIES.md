# Dependencies

## Required For Local Tests

| Dependency | Why |
|---|---|
| `uv` | Python environment and command runner |
| Python 3.11+ | Harness runtime |
| `pytest` | Dev/test dependency installed by `uv sync --dev` |

Runtime harness code currently uses only the Python standard library.

## Required For Live Argentum Smokes

| Dependency | Why |
|---|---|
| Java 21 | Argentum `gym-server` build/run |
| Argentum Engine | MTG rules engine and HTTP gym server |

Clone Argentum into the ignored evidence directory:

```bash
mkdir -p 05_evidence/repos
git clone --depth 1 https://github.com/wingedsheep/argentum-engine.git 05_evidence/repos/argentum-engine
```

Run the server:

```bash
cd 05_evidence/repos/argentum-engine
JAVA_HOME=/opt/homebrew/opt/openjdk@21 ./gradlew :gym-server:bootRun --no-daemon
```

## Required For Real Codex Episodes

| Dependency | Why |
|---|---|
| local `codex` CLI | Model-backed action selection via `codex exec` |
| Codex login | The shell does not need API keys if the CLI is already authenticated |

The harness invokes:

```bash
codex exec --ephemeral --skip-git-repo-check --sandbox read-only --output-schema schemas/codex_action.schema.json ...
```

## Optional Network Dependencies

| Source | Why |
|---|---|
| Scryfall API | Card oracle context for visible cards |
| MTGJSON | Bulk card/set/product data research |
| Commander Spellbook | Combo-task research |
| 17Lands public datasets | Draft/game-data research |

These are documented in `00_admin/source_ledger.csv`.
