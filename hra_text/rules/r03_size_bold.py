"""R03. 역할별 글자 크기·진하게 (FORMAT_RULES R03 표). SOURCE·AUTHOR_TAG 크기는 표에 있으나
SOURCE 는 R08 이 출처 전용 메모와 함께 처리한다."""

from ..hwpx.edit import change_run, char_bold, char_height
from . import register
from .base import Rule

# 역할: (크기 pt, 진하게)
EXPECTED = {
    "CATEGORY": (12, True),
    "COVER_TITLE": (32, True),
    "TOC_TITLE": (16, False),
    "TOC_ITEM": (12, True),
    "INTRO_TITLE": (12, True),
    "INTRO_IMAGE": (10, False),
    "INTRO_BODY": (10, False),
    "READING_TITLE": (12, True),
    "READING_BYLINE": (11, False),
    "COVER_TABLE": (11, True),
    "H1": (12, True),
    "H2": (12, True),
    "H3": (11, True),
    "H4": (10, False),
    "REFLECTION_NAME": (10, True),
    "BODY": (10, False),
    "REFLECTION": (10, False),
    "TABLE_CELL": (10, False),
    "AUTHOR_TAG": (8, False),
}


@register
class R03SizeBold(Rule):
    RULE_ID = "R03"
    NAME = "글자 크기·진하게"

    def apply(self, doc):
        h = doc.header
        changes = []
        for p in self.formatted(doc):
            if p.role not in EXPECTED:
                continue
            size, bold = EXPECTED[p.role]
            for r in self.text_runs(p):
                c = h.char(r.char_id)
                if c.size_pt != size and change_run(doc, p, r, char_height(size)):
                    changes.append(self.change(p, "size", c.size_pt, size, run=r))
                if c.bold != bold and change_run(doc, p, r, char_bold(bold)):
                    changes.append(self.change(p, "bold", c.bold, bold, run=r))
        return changes
