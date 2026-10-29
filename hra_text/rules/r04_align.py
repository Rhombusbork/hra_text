"""R04. 정렬 (FORMAT_RULES R04 표). SOURCE 는 R08 이 처리.
개체 문단(표·그림을 담은 문단 = 표 위치)은 받은 대로 둔다."""

from ..hwpx.edit import change_para, para_align
from . import register
from .base import Rule

CENTER_ROLES = {"COVER_TITLE", "TOC_TITLE", "TOC_ITEM", "COVER_TABLE", "INTRO_TITLE",
                "INTRO_IMAGE", "READING_TITLE"}
RIGHT_ROLES = {"AUTHOR_TAG", "READING_BYLINE"}
# SOURCE 는 R08, OBJECT(표 위치)는 받은 대로 [U] 2026-10-29
NOT_HANDLED = {"SOURCE", "OBJECT"}


def expected_align(doc, para) -> str:
    if para.role in CENTER_ROLES:
        return "CENTER"
    if para.role in RIGHT_ROLES:
        return "RIGHT"
    return "JUSTIFY"


@register
class R04Align(Rule):
    RULE_ID = "R04"
    NAME = "정렬"

    def apply(self, doc):
        changes = []
        for p in self.formatted(doc):
            if p.role in NOT_HANDLED:
                continue
            want = expected_align(doc, p)
            have = doc.header.para(p.para_id).align
            if have != want and change_para(doc, p, para_align(want)):
                changes.append(self.change(p, "align", have, want))
        return changes
