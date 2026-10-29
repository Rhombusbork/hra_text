"""규칙 레지스트리. 규칙 모듈은 FORMAT_RULES.md의 ID를 RULE_ID로 갖고 여기에 등록된다."""

from __future__ import annotations

REGISTRY: dict[str, object] = {}


def register(rule_cls):
    rule_id = rule_cls.RULE_ID
    if rule_id in REGISTRY:
        raise ValueError(f"중복 규칙 ID: {rule_id}")
    REGISTRY[rule_id] = rule_cls
    return rule_cls
