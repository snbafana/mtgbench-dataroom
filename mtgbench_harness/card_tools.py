from __future__ import annotations

import json
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any

from mtgbench_harness.argentum import visible_card_names


@dataclass
class ScryfallClient:
    timeout: int = 20
    _cache: dict[str, dict[str, Any]] = field(default_factory=dict)

    def named(self, card_name: str) -> dict[str, Any]:
        cache_key = f"named:{card_name.lower()}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        url = "https://api.scryfall.com/cards/named?" + urllib.parse.urlencode({"exact": card_name})
        data = self._fetch(url)
        result = self._summarize_card(data)
        self._cache[cache_key] = result
        return result

    def search(self, query: str, *, limit: int = 5) -> list[dict[str, Any]]:
        cache_key = f"search:{query.lower()}:{limit}"
        if cache_key in self._cache:
            return self._cache[cache_key]["results"]
        url = "https://api.scryfall.com/cards/search?" + urllib.parse.urlencode({"q": query, "unique": "cards"})
        data = self._fetch(url)
        results = [self._summarize_card(card) for card in data.get("data", [])[:limit]]
        self._cache[cache_key] = {"results": results}
        return results

    def _fetch(self, url: str) -> dict[str, Any]:
        req = urllib.request.Request(
            url,
            headers={
                "accept": "application/json",
                "user-agent": "mtgbench-dataroom/0.1 (+local harness)",
            },
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as response:
            return json.loads(response.read().decode("utf-8"))

    @staticmethod
    def _summarize_card(card: dict[str, Any]) -> dict[str, Any]:
        faces = card.get("card_faces") or []
        oracle_text = card.get("oracle_text")
        if not oracle_text and faces:
            oracle_text = "\n---\n".join(face.get("oracle_text", "") for face in faces)
        return {
            "name": card.get("name"),
            "manaCost": card.get("mana_cost"),
            "typeLine": card.get("type_line"),
            "oracleText": oracle_text,
            "power": card.get("power"),
            "toughness": card.get("toughness"),
            "legalities": card.get("legalities", {}),
            "scryfallUri": card.get("scryfall_uri"),
        }


def oracle_context_for_observation(
    observation: dict[str, Any],
    *,
    client: ScryfallClient | None = None,
    limit: int = 6,
) -> list[dict[str, Any]]:
    scryfall = client or ScryfallClient()
    cards: list[dict[str, Any]] = []
    for name in visible_card_names(observation, limit=limit):
        try:
            cards.append(scryfall.named(name))
        except Exception as exc:  # noqa: BLE001 - card context should not break play loop.
            cards.append({"name": name, "error": f"{type(exc).__name__}: {exc}"})
    return cards
