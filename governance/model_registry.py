from __future__ import annotations

import json
import os
import time
from typing import Any


def _generate_model_id(name: str, version: str) -> str:
    return f"{name}__v{version}__{int(time.time() * 1000)}"


class ModelRegistry:
    def __init__(self, filepath: str = "data/governance/model_registry.json") -> None:
        self.filepath = filepath
        self._models: list[dict[str, Any]] = []
        self._load()

    def register(
        self,
        name: str,
        version: str,
        metrics: dict[str, float],
        path: str,
        timestamp: str | None = None,
    ) -> str:
        model_id = _generate_model_id(name, version)
        entry: dict[str, Any] = {
            "model_id": model_id,
            "name": name,
            "version": version,
            "metrics": metrics,
            "path": path,
            "created_at": timestamp or time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        self._models.append(entry)
        self._save()
        return model_id

    def get_latest(self, name: str) -> dict[str, Any] | None:
        versions = [m for m in self._models if m["name"] == name]
        if not versions:
            return None
        return max(versions, key=lambda m: m["created_at"])

    def list_models(self, name: str | None = None) -> list[dict[str, Any]]:
        if name is None:
            return list(self._models)
        return [m for m in self._models if m["name"] == name]

    def compare(self, name: str, version_a: str, version_b: str) -> dict[str, Any]:
        def find(name: str, version: str) -> dict[str, Any] | None:
            for m in self._models:
                if m["name"] == name and m["version"] == version:
                    return m
            return None

        a = find(name, version_a)
        b = find(name, version_b)
        if a is None or b is None:
            missing = "version_a" if a is None else "version_b"
            return {"error": f"{missing} not found for {name}"}

        metrics_a = a["metrics"]
        metrics_b = b["metrics"]
        all_keys = set(metrics_a.keys()) | set(metrics_b.keys())
        deltas: dict[str, float] = {}
        for key in all_keys:
            va = metrics_a.get(key, 0.0)
            vb = metrics_b.get(key, 0.0)
            deltas[key] = round(vb - va, 6)

        return {
            "name": name,
            "version_a": version_a,
            "version_b": version_b,
            "metrics_a": metrics_a,
            "metrics_b": metrics_b,
            "deltas": deltas,
            "improvement_count": sum(1 for v in deltas.values() if v > 0),
            "regression_count": sum(1 for v in deltas.values() if v < 0),
        }

    def _load(self) -> None:
        if not os.path.exists(self.filepath):
            self._models = []
            return
        try:
            with open(self.filepath) as f:
                data = json.load(f)
            self._models = data if isinstance(data, list) else []
        except (json.JSONDecodeError, OSError):
            self._models = []

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
        with open(self.filepath, "w") as f:
            json.dump(self._models, f, indent=2)
