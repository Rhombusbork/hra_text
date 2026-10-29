"""규칙이 만들어 내는 변경 기록. 메모(6단계)와 변경 내역 보고서가 이 기록을 쓴다."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from lxml import etree


@dataclass
class Change:
    rule_id: str  # FORMAT_RULES 규칙 ID (예: "R03")
    key: str  # 바뀐 항목 (예: "size", "bold", "align", "intent")
    old: Any
    new: Any
    para_el: etree._Element  # 바뀐 문단 (메모를 달 위치)
    path: str  # 사람이 읽는 위치 (예: s0/p38)
    role: str
    text: str  # 문단 글자 (보고서용)
    run_el: etree._Element | None = None  # 런 단위 변경이면 그 런
    note: str = ""  # 부가 설명 (예: 위치 확인 필요)
    extra: dict = field(default_factory=dict)
