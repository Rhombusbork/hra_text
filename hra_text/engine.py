"""규칙 실행: FORMAT_RULES 순서(rules.base.ORDER)대로 등록된 규칙을 적용한다."""

from __future__ import annotations

from .document import Document
from .model import Change
from .rules import REGISTRY
from .rules.base import ORDER


def run_rules(doc: Document, only: set[str] | None = None) -> list[Change]:
    unknown = (only or set()) - set(REGISTRY)
    if unknown:
        raise ValueError(f"구현되지 않은 규칙: {', '.join(sorted(unknown))}")
    changes: list[Change] = []
    for rule_id in ORDER:
        if rule_id in REGISTRY and (only is None or rule_id in only):
            changes += REGISTRY[rule_id]().apply(doc)
    return changes
