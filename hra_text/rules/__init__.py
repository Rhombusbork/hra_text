"""규칙 레지스트리. 규칙 모듈은 FORMAT_RULES.md의 ID를 RULE_ID로 갖고 여기에 등록된다."""

from __future__ import annotations

import importlib
import pkgutil

REGISTRY: dict[str, type] = {}


def register(rule_cls):
    rule_id = rule_cls.RULE_ID
    if rule_id in REGISTRY:
        raise ValueError(f"중복 규칙 ID: {rule_id}")
    REGISTRY[rule_id] = rule_cls
    return rule_cls


def _load_all() -> None:
    for mod in pkgutil.iter_modules(__path__):
        if mod.name.startswith("r") and mod.name[1:3].isdigit():
            importlib.import_module(f"{__name__}.{mod.name}")


_load_all()
