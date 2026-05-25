from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any


def default_explicit_config() -> dict[str, Any]:
    return {
        "players": [
            {"name": "Alice", "deck": {"type": "Explicit", "cards": {"Mountain": 17, "Raging Goblin": 3}}},
            {"name": "Bob", "deck": {"type": "Explicit", "cards": {"Mountain": 17, "Raging Goblin": 3}}},
        ],
        "skipMulligans": True,
        "startingPlayerIndex": 0,
    }


class ArgentumHttpError(RuntimeError):
    def __init__(self, method: str, path: str, status: int, body: str):
        super().__init__(f"{method} {path} failed with HTTP {status}: {body}")
        self.method = method
        self.path = path
        self.status = status
        self.body = body


@dataclass
class ArgentumClient:
    base_url: str = "http://localhost:8081"
    timeout: int = 20

    def _request(
        self,
        method: str,
        path: str,
        body: Any | None = None,
        query: dict[str, Any] | None = None,
    ) -> Any:
        payload = None if body is None else json.dumps(body).encode("utf-8")
        url = f"{self.base_url.rstrip('/')}{path}"
        if query:
            clean_query = {key: str(value).lower() if isinstance(value, bool) else str(value) for key, value in query.items()}
            url = f"{url}?{urllib.parse.urlencode(clean_query)}"
        req = urllib.request.Request(
            url,
            data=payload,
            method=method,
            headers={"content-type": "application/json", "accept": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read()
                if not raw:
                    return {"status": resp.status}
                return json.loads(raw.decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise ArgentumHttpError(method, path, exc.code, detail) from exc

    def health(self) -> Any:
        return self._request("GET", "/health")

    def schema_hash(self) -> Any:
        return self._request("GET", "/schema-hash")

    def list_envs(self) -> list[str]:
        return self._request("GET", "/envs")

    def create(self, config: dict[str, Any]) -> Any:
        return self._request("POST", "/envs", config)

    def reset(self, env_id: str, config: dict[str, Any]) -> Any:
        return self._request("POST", f"/envs/{env_id}/reset", config)

    def observe(self, env_id: str, *, reveal_all: bool | None = None) -> Any:
        query = None if reveal_all is None else {"revealAll": reveal_all}
        return self._request("GET", f"/envs/{env_id}", query=query)

    def step(self, env_id: str, action_id: int) -> Any:
        return self._request("POST", f"/envs/{env_id}/step", {"actionId": action_id})

    def step_batch(self, items: list[dict[str, Any]]) -> Any:
        return self._request("POST", "/envs/step-batch", items)

    def fork(self, env_id: str, count: int = 1) -> list[str]:
        return self._request("POST", f"/envs/{env_id}/fork", query={"count": count})

    def snapshot(self, env_id: str) -> Any:
        return self._request("POST", f"/envs/{env_id}/snapshot")

    def restore(self, env_id: str, handle: Any) -> Any:
        return self._request("POST", f"/envs/{env_id}/restore", {"handle": handle})

    def dispose(self, env_ids: str | list[str]) -> Any:
        ids = [env_ids] if isinstance(env_ids, str) else env_ids
        return self._request("DELETE", "/envs", {"envIds": ids})


def legal_actions(observation: dict[str, Any]) -> list[dict[str, Any]]:
    actions = observation.get("legalActions") or []
    return [action for action in actions if isinstance(action, dict)]


def summarize_action(action: dict[str, Any] | None) -> dict[str, Any] | None:
    if not action:
        return None
    return {
        "actionId": action.get("actionId"),
        "kind": action.get("kind"),
        "description": action.get("description"),
        "affordable": action.get("affordable"),
        "isManaAbility": action.get("isManaAbility"),
        "isDecisionOption": action.get("isDecisionOption"),
    }


def summarize_observation(observation: dict[str, Any]) -> dict[str, Any]:
    actions = legal_actions(observation)
    return {
        "schemaHash": observation.get("schemaHash"),
        "turnNumber": observation.get("turnNumber"),
        "phase": observation.get("phase"),
        "step": observation.get("step"),
        "terminated": observation.get("terminated"),
        "agentToAct": observation.get("agentToAct"),
        "activePlayerId": observation.get("activePlayerId"),
        "priorityPlayerId": observation.get("priorityPlayerId"),
        "legalActionCount": len(actions),
        "firstAction": summarize_action(actions[0] if actions else None),
        "stateDigest": observation.get("stateDigest"),
    }


def _collect_card_names(value: Any, names: set[str], *, limit: int) -> None:
    if len(names) >= limit:
        return
    if isinstance(value, dict):
        name = value.get("name") or value.get("cardName")
        if isinstance(name, str) and name and name != "Hidden":
            names.add(name)
        for child in value.values():
            _collect_card_names(child, names, limit=limit)
    elif isinstance(value, list):
        for child in value:
            _collect_card_names(child, names, limit=limit)


def visible_card_names(observation: dict[str, Any], *, limit: int = 24) -> list[str]:
    names: set[str] = set()
    _collect_card_names(observation.get("zones", []), names, limit=limit)
    return sorted(names)[:limit]


def agent_view(observation: dict[str, Any], *, max_actions: int = 12, max_cards: int = 24) -> dict[str, Any]:
    actions = legal_actions(observation)
    return {
        "state": summarize_observation(observation),
        "players": observation.get("players", []),
        "visibleCards": visible_card_names(observation, limit=max_cards),
        "legalActions": [summarize_action(action) for action in actions[:max_actions]],
        "omittedLegalActions": max(0, len(actions) - max_actions),
    }
