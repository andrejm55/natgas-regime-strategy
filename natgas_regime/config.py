from __future__ import annotations
from pathlib import Path
from typing import Any
import yaml


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def load_yaml(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    if not p.is_absolute():
        p = project_root() / p
    with p.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def resolve_path(path: str | Path) -> Path:
    p = Path(path)
    if p.is_absolute():
        return p
    return project_root() / p

