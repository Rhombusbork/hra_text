"""R04. 정렬 (FORMAT_RULES R04 표). SOURCE 는 R08 이 처리."""

from ..classify import TABLE_COVER, TABLE_TOC, table_kind
from ..hwpx.edit import change_para, para_align
from . import register
from .base import Rule

CENTER_ROLES = {"COVER_TITLE", "TOC_TITLE", "TOC_ITEM", "COVER_TABLE", "INTRO_TITLE",
                "INTRO_IMAGE", "READING_TITLE"}
RIGHT_ROLES = {"AUTHOR_TAG", "READING_BYLINE"}
HANDLED_ELSEWHERE = {"SOURCE"}  # R08
# 개체 문단은 담긴 표의 종류로 정한다 (목차 표는 가운데, 표지 정보 표는 오른쪽, 그 외는 양쪽 = 왼쪽에 붙음)
OBJECT_ALIGN = {TABLE_TOC: "CENTER", TABLE_COVER: "RIGHT"}


def expected_align(doc, para) -> str:
    if para.role in CENTER_ROLES:
        return "CENTER"
    if para.role in RIGHT_ROLES:
        return "RIGHT"
    if para.role == "OBJECT":
        for tbl in para.tables:
            kind = table_kind(doc, tbl)
            if kind in OBJECT_ALIGN:
                return OBJECT_ALIGN[kind]
    return "JUSTIFY"


@register
class R04Align(Rule):
    RULE_ID = "R04"
    NAME = "정렬"

    def apply(self, doc):
        changes = []
        for p in self.formatted(doc):
            if p.role in HANDLED_ELSEWHERE:
                continue
            want = expected_align(doc, p)
            have = doc.header.para(p.para_id).align
            if have != want and change_para(doc, p, para_align(want)):
                changes.append(self.change(p, "align", have, want))
        return changes
