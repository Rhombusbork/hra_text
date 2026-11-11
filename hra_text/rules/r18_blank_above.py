"""R18. 내용 다음의 제목 줄(2·3·4단위·이름 줄·제목처럼 보이는 줄) 위, 그리고 긴 본문 문단 사이
(둘 중 하나라도 3줄 이상, R18-f)에 빈 줄이 없으면 한 줄 넣는다.

제목 바로 아래 제목(1단위 칸 아래 첫 2단위, 2단위 아래 3단위, 3단위 아래 ① 등)은 붙여 써서 제목 묶음의
맨 위만 띄운다. 4단위 다음 4단위(본문 없는 목록)도 붙인다. 이미 있는 빈 줄은 지우지도 더 넣지도 않는다.
1단위는 대상이 아니다. 쪽 위치와 관계없이 적용한다.
"""

from __future__ import annotations

from lxml import etree

from ..classify import TABLE_H1_BOX, table_kind
from ..hwpx.edit import char_bold, char_height
from ..hwpx.ns import hp
from ..layout import estimate_lines
from . import register
from .base import Rule
from .r03_size_bold import looks_like_heading

TARGET_ROLES = {"H2", "H3", "H4", "REFLECTION_NAME"}
LONG_LINES = 3  # R18-f
# 이 역할 바로 아래의 대상 줄은 붙여 쓴다 (R18-b)
HEADING_ROLES = {"H1", "H2", "H3", "REFLECTION_NAME", "CATEGORY", "COVER_TITLE",
                 "READING_TITLE", "READING_BYLINE"}


def _is_h1_box(doc, p) -> bool:
    return p.role == "OBJECT" and any(table_kind(doc, t) == TABLE_H1_BOX for t in p.tables)


def _is_target(doc, p) -> bool:
    return p.role in TARGET_ROLES or looks_like_heading(doc, p)


def _is_heading(doc, p) -> bool:
    return p.role in HEADING_ROLES or _is_h1_box(doc, p) or looks_like_heading(doc, p)


def _attached(doc, x, y) -> bool:
    """R18-b: y 를 x 바로 아래 붙여 쓰는가 (제목 바로 아래 제목, 4단위 다음 4단위)."""
    if _is_heading(doc, x):
        return True
    return x.role == "H4" and y.role == "H4"


def _long_body_pair(doc, x, y) -> bool:
    """R18-f: 본문끼리, 둘 중 하나라도 3줄 이상."""
    if x.role != "BODY" or y.role != "BODY" or looks_like_heading(doc, x) or looks_like_heading(doc, y):
        return False
    return estimate_lines(doc, x) >= LONG_LINES or estimate_lines(doc, y) >= LONG_LINES


def _blank_char_id(doc, p) -> str:
    """아래 줄 글자 모양에서 10pt 보통으로."""
    base = next((r.char_id for r in p.runs if r.text.strip()), p.runs[0].char_id if p.runs else "0")
    h = doc.header
    return h.derive_char(h.derive_char(base, char_height(10)), char_bold(False))


def _blank_para(doc, p) -> etree._Element:
    new = etree.Element(hp("p"), {k: p.el.get(k) for k in p.el.keys()})
    for attr in ("pageBreak", "columnBreak"):
        if new.get(attr) is not None:
            new.set(attr, "0")
    etree.SubElement(new, hp("run"), charPrIDRef=_blank_char_id(doc, p))
    return new


@register
class R18BlankAbove(Rule):
    RULE_ID = "R18"
    NAME = "제목 위·긴 본문 사이 빈 줄"

    def apply(self, doc):
        body = [p for p in doc.paras if p.container == "body" and p.depth == 0 and p.role != "SKIP"]
        first = next((i for i, p in enumerate(body) if p.role == "H1" or _is_h1_box(doc, p)), None)
        if first is None:
            return []
        changes = []
        for i in range(first + 1, len(body)):
            y = body[i]
            x = body[i - 1]
            if y.role == "EMPTY" or x.role == "EMPTY" or x.el.getparent() is not y.el.getparent():
                continue  # R18-c 이미 빈 줄 있음 / 구역이 다름
            if _is_target(doc, y):
                if _attached(doc, x, y):
                    continue  # R18-b 제목 바로 아래
            elif not _long_body_pair(doc, x, y):
                continue
            blank = _blank_para(doc, y)
            y.el.addprevious(blank)
            doc.touched.add(blank)
            changes.append(self.change(y, "blank_above", 0, 1))
        if changes:
            doc.reload()
        return changes
