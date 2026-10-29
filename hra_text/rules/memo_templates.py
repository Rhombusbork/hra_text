"""메모 문구. 원본은 docs/FORMAT_RULES.md 이며, 이 값은 문서의 해당 규칙 절에 그대로 있어야 한다
(tests/test_rules_sync.py 가 검사)."""

from __future__ import annotations

# {규칙 ID: {키: 템플릿}}
MEMO_TEMPLATES: dict[str, dict[str, str]] = {}
