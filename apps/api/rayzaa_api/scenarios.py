from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .schemas import ScenarioMetadata


def load_scenarios(fixture_dir: Path) -> dict[str, dict[str, Any]]:
    scenarios: dict[str, dict[str, Any]] = {}
    for path in fixture_dir.glob("scenario_*.json"):
        payload = json.loads(path.read_text())
        scenarios[payload["id"]] = payload
    return scenarios


def scenario_metadata(scenarios: dict[str, dict[str, Any]]) -> list[ScenarioMetadata]:
    return [
        ScenarioMetadata(
            id=item["id"],
            title=item["title"],
            subtitle=item["subtitle"],
            description=item["description"],
            total_steps=len(item["events"]),
        )
        for item in scenarios.values()
    ]
