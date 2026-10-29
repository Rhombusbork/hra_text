"""두 문서의 서식 비교 (우리 결과 vs 사용자가 직접 고친 수정본).

글자 내용으로 문단을 짝지은 뒤(difflib), 짝지은 문단의 서식 항목을 비교한다.
내용 자체(띄어쓰기 등)가 달라진 문단은 짝이 안 맞을 수 있어 '짝 없음'으로 따로 센다.
"""

from __future__ import annotations

import difflib
import re
from collections import Counter, defaultdict
from dataclasses import dataclass

from .document import Document
from .hwpx.section import Para

ATTRS = ("style", "size", "bold", "align", "intent", "left", "prev", "next", "line")
ATTR_NAMES = {"style": "스타일", "size": "크기", "bold": "진하게", "align": "정렬", "intent": "들여쓰기",
              "left": "왼쪽 여백", "prev": "위 간격", "next": "아래 간격", "line": "줄 간격"}


def _key(text: str) -> str:
    return re.sub(r"\s+", "", text)


def snapshot(doc: Document, p: Para) -> dict:
    h = doc.header
    ps = h.para(p.para_id)
    chars = [h.char(r.char_id) for r in p.runs if r.text.strip()]
    return {
        "style": h.style_name(p.style_id),
        "size": tuple(sorted({c.size_pt for c in chars})),
        "bold": tuple(sorted({c.bold for c in chars})),
        "align": ps.align,
        "intent": ps.margins_pt.get("intent"),
        "left": ps.margins_pt.get("left"),
        "prev": ps.margins_pt.get("prev"),
        "next": ps.margins_pt.get("next"),
        "line": ps.line_spacing[1],
    }


@dataclass
class Diff:
    role: str
    attr: str
    ours: object
    ref: object
    text: str
    path: str


def compare(ours: Document, ref: Document) -> tuple[list[Diff], dict]:
    a = [p for p in ours.paras if p.role != "SKIP" and p.text.strip()]
    b = [p for p in ref.paras if p.role != "SKIP" and p.text.strip()]
    sm = difflib.SequenceMatcher(a=[_key(p.text) for p in a], b=[_key(p.text) for p in b], autojunk=False)
    diffs: list[Diff] = []
    matched = 0
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag != "equal":
            continue
        for pa, pb in zip(a[i1:i2], b[j1:j2]):
            matched += 1
            sa, sb = snapshot(ours, pa), snapshot(ref, pb)
            for attr in ATTRS:
                if sa[attr] != sb[attr]:
                    diffs.append(Diff(pa.role, attr, sa[attr], sb[attr], pa.text.strip(), pa.path))
    stats = {"ours": len(a), "ref": len(b), "matched": matched}
    return diffs, stats


def render(diffs: list[Diff], stats: dict, *, examples: int = 3) -> str:
    lines = [
        f"글자 문단: 우리 {stats['ours']}개 / 수정본 {stats['ref']}개 / 내용이 같아 짝지은 문단 {stats['matched']}개",
        f"서식이 다른 항목: {len(diffs)}건 (짝지은 문단 기준)",
        "",
    ]
    groups: dict[tuple, list[Diff]] = defaultdict(list)
    for d in diffs:
        groups[(d.role, d.attr, repr(d.ours), repr(d.ref))].append(d)
    counts = Counter({k: len(v) for k, v in groups.items()})
    for (role, attr, ours, ref), n in counts.most_common():
        lines.append(f"[{n:>3}건] {role:<15} {ATTR_NAMES[attr]}: 우리 {ours} / 수정본 {ref}")
        for d in groups[(role, attr, ours, ref)][:examples]:
            lines.append(f"         {d.path:<20} {d.text[:45]}")
    return "\n".join(lines)
