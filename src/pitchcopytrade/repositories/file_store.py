from __future__ import annotations

import json
from pathlib import Path
from tempfile import NamedTemporaryFile

from pitchcopytrade.core.config import get_settings


class FileDataStore:
    DATASETS = (
        "roles",
        "users",
        "authors",
        "lead_sources",
        "instruments",
        "strategies",
        "bundles",
        "bundle_members",
        "products",
        "legal_documents",
        "payments",
        "subscriptions",
        "user_consents",
        "recommendations",
        "recommendation_legs",
        "recommendation_attachments",
    )

    def __init__(self, root_dir: str | Path | None = None) -> None:
        settings = get_settings()
        self.root_dir = Path(root_dir or settings.storage.json_root)

    def bootstrap(self) -> None:
        self.root_dir.mkdir(parents=True, exist_ok=True)

    def load_dataset(self, dataset_name: str) -> list[dict]:
        self.bootstrap()
        path = self._path_for(dataset_name)
        if not path.exists():
            return []
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise ValueError(f"Dataset {dataset_name} must contain a JSON array")
        return payload

    def save_dataset(self, dataset_name: str, records: list[dict]) -> None:
        self.bootstrap()
        path = self._path_for(dataset_name)
        with NamedTemporaryFile("w", encoding="utf-8", dir=str(path.parent), delete=False) as handle:
            json.dump(records, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            temp_path = Path(handle.name)
        temp_path.replace(path)

    def load_all(self) -> dict[str, list[dict]]:
        return {dataset: self.load_dataset(dataset) for dataset in self.DATASETS}

    def save_many(self, datasets: dict[str, list[dict]]) -> None:
        for dataset_name, records in datasets.items():
            self.save_dataset(dataset_name, records)

    def _path_for(self, dataset_name: str) -> Path:
        return self.root_dir / f"{dataset_name}.json"
