"""변경 내역 보고서 (사람이 읽는 텍스트)."""

from __future__ import annotations

from collections import Counter, defaultdict

from .model import Change
from .rules import REGISTRY

KEY_NAMES = {
    "style": "스타일", "font": "글꼴", "size": "글자 크기", "bold": "진하게", "align": "정렬",
    "intent": "들여쓰기", "left": "왼쪽 여백", "right": "오른쪽 여백", "prev": "문단 위 간격",
    "next": "문단 아래 간격", "line": "줄 간격", "treatAsChar": "글자처럼 취급",
}


def _fmt(v) -> str:
    if v is True:
        return "켬"
    if v is False:
        return "끔"
    if v is None:
        return "글자 단위"
    if isinstance(v, float):
        return f"{v:g}"
    return str(v)


def render(changes: list[Change], *, title: str = "", memos: int | None = None) -> str:
    lines = [f"# 변경 내역 {title}".rstrip(), ""]
    if memos is not None:
        lines.append(f"단 메모 수: {memos}")
    counts = Counter(c.rule_id for c in changes)
    lines.append("규칙별 변경 수: " + (", ".join(
        f"{rid}({REGISTRY[rid].NAME}) {n}" for rid, n in sorted(counts.items())) or "없음"))
    lines.append(f"수정된 문단 수: {len({id(c.para_el) for c in changes})}")
    lines.append("")
    by_rule: dict[str, list[Change]] = defaultdict(list)
    for c in changes:
        by_rule[c.rule_id].append(c)
    for rid in sorted(by_rule):
        lines.append(f"## {rid} {REGISTRY[rid].NAME}")
        for c in by_rule[rid]:
            note = f"  ※ {c.note}" if c.note else ""
            lines.append(
                f"- {c.path:<20} {c.role:<15} {KEY_NAMES.get(c.key, c.key)}: "
                f"{_fmt(c.old)} → {_fmt(c.new)}  | {c.text.strip()[:40]}{note}"
            )
        lines.append("")
    return "\n".join(lines)
