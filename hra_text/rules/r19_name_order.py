"""R19. 경영서 마지막 이름 나열 구역(느낀 점)을 표지 '조원' 칸 순서로 맞춘다.

한 사람 몫 = 이름 줄부터 다음 이름 줄 앞까지의 글자 문단(끝의 빈 줄 제외). 덩어리 사이 빈 줄 자리는
그대로 두고 덩어리만 바꿔 끼운다. 표지에 없는 이름은 원래 순서대로 맨 뒤, 같은 이름이 두 번이면
순서를 바꾸지 않는다. 표지 조원 중 이름 줄이 없는 사람은 확인 메모로 알린다.
"""

from __future__ import annotations

import re

from ..classify import TABLE_H1_BOX, table_kind
from ..hwpx.memo import memo_texts
from . import register
from .base import Rule

NOT_NAME_SUFFIX = re.compile(r"(학과|학년|학부|전공|대학|대학교)$")
MISSING_MARK = "느낀 점에 없는 조원"
END_ROLES = {"H1", "CATEGORY"}


def _squash(s: str) -> str:
    return re.sub(r"\s+", "", s)


def cover_members(doc) -> list[str]:
    """표지 정보 표 '조원' 칸의 이름들 (R19-a). 없으면 []."""
    by_tbl: dict[int, list] = {}
    for p in doc.paras:
        if p.role == "COVER_TABLE" and p.cell is not None:
            by_tbl.setdefault(id(p.cell.tbl), []).append(p)
    for paras in by_tbl.values():
        label = next((p for p in paras if p.cell.col == 0 and _squash(p.text) == "조원"), None)
        if label is None:
            continue
        names = []
        for p in paras:
            if p.cell.row == label.cell.row and p.cell.col > 0:
                for word in re.split(r"[^가-힣]+", p.text):
                    if 2 <= len(word) <= 4 and not NOT_NAME_SUFFIX.search(word) and word not in names:
                        names.append(word)
        return names
    return []


def _is_bizbook(doc) -> bool:
    return any(p.role == "CATEGORY" and "경영서" in _squash(p.text) for p in doc.paras)


def _name_area(doc, body):
    """이름 줄이 처음 나오는 곳부터 다음 1단위·■ 분류 전까지 (같은 구역 안)."""
    start = next((i for i, p in enumerate(body) if p.role == "REFLECTION_NAME"), None)
    if start is None:
        return []
    area = []
    for p in body[start:]:
        if p.role in END_ROLES or (p.role == "OBJECT" and any(table_kind(doc, t) == TABLE_H1_BOX
                                                               for t in p.tables)):
            break
        if p.el.getparent() is not body[start].el.getparent():
            break
        area.append(p)
    return area


def _segments(area):
    """[('block'|'gap', [Para…])] — 블록은 이름 줄부터 다음 이름 줄 앞까지(끝 빈 줄 제외)."""
    segs = []
    for p in area:
        if p.role == "REFLECTION_NAME":
            segs.append(["block", [p]])
        elif p.role == "EMPTY":
            if segs and segs[-1][0] == "gap":
                segs[-1][1].append(p)
            else:
                segs.append(["gap", [p]])
        else:
            if segs[-1][0] == "gap":  # 빈 줄 다음에 이어지는 같은 사람 글: 빈 줄을 블록 안으로
                gap = segs.pop()[1]
                segs[-1][1].extend(gap)
            segs[-1][1].append(p)
    return segs


@register
class R19NameOrder(Rule):
    RULE_ID = "R19"
    NAME = "경영서 이름 순서"

    def apply(self, doc):
        if not _is_bizbook(doc):
            return []
        members = cover_members(doc)
        if not members:
            return []
        body = [p for p in doc.paras if p.container == "body" and p.depth == 0 and p.role != "SKIP"]
        area = _name_area(doc, body)
        if not area:
            return []
        segs = _segments(area)
        blocks = [s[1] for s in segs if s[0] == "block"]
        names = [b[0].text.strip() for b in blocks]
        changes = []

        missing = [m for m in members if m not in names]
        if len(set(names)) == len(names):  # R19-c 같은 이름 두 번이면 순서를 바꾸지 않는다
            rank = {m: i for i, m in enumerate(members)}
            order = sorted(range(len(blocks)), key=lambda k: (rank.get(names[k], len(members)), k))
            if order != list(range(len(blocks))):
                new_blocks = iter([blocks[k] for k in order])
                seq = [el for kind, paras in segs
                       for el in [q.el for q in (next(new_blocks) if kind == "block" else paras)]]
                parent = area[0].el.getparent()
                at = parent.index(area[0].el)
                for el in seq:
                    parent.remove(el)
                for k, el in enumerate(seq):
                    parent.insert(at + k, el)
                first = blocks[order[0]][0]
                doc.touched.update(q.el for b in blocks for q in b)
                changes.append(self.change(first, "name_order", "·".join(names),
                                           "·".join(names[k] for k in order)))
        anchor = changes[0].para_el if changes else blocks[0][0].el
        if missing and not any(MISSING_MARK in m for m in memo_texts(anchor)):
            changes.append(self.change(next(p for p in area if p.el is anchor), "name_missing",
                                       ", ".join(missing), ", ".join(missing), check=True))
        if any(c.key == "name_order" for c in changes):
            doc.reload()
        return changes
