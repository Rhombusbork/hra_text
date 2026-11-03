"""R03. 역할별 글자 크기·진하게 (FORMAT_RULES R03 표). SOURCE·AUTHOR_TAG 크기는 표에 있으나
SOURCE 는 R08 이 출처 전용 메모와 함께 처리한다."""

from ..hwpx.edit import change_run, char_bold, char_height
from . import register
from .base import Rule

# 이미 8pt 인 글자는 크기를 바꾸지 않는다 (참고자료·출처 목록 등) [U] 2026-11-04
KEEP_SIZE_PT = 8.0

# 역할: (크기 pt, 진하게) — None 이면 받은 대로
EXPECTED = {
    "CATEGORY": (12, True),
    "COVER_TITLE": (32, True),
    "TOC_TITLE": (16, False),
    "TOC_ITEM": (12, True),
    "INTRO_TITLE": (None, None),  # 책 소개 표 제목·그림 칸은 받은 대로 [U] 2026-11-03
    "INTRO_IMAGE": (None, None),
    "INTRO_BODY": (10, False),
    "READING_TITLE": (12, True),
    "READING_BYLINE": (11, False),
    "COVER_TABLE": (11, True),
    "H1": (12, True),
    "H2": (12, True),
    "H3": (11, True),
    "H4": (10, False),
    "REFLECTION_NAME": (11, True),  # 느낀 점 이름 줄 11pt 진하게 [U] 2026-11-03
    "BODY": (10, False),
    "REFLECTION": (10, False),
    "TABLE_CELL": (10, None),  # 표 안 진하게는 받은 대로 [U] 2026-11-03
    "AUTHOR_TAG": (None, None),  # 작성자 표기는 받은 대로 [U] 2026-11-03
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
                if (size is not None and c.size_pt != size and c.size_pt != KEEP_SIZE_PT
                        and change_run(doc, p, r, char_height(size))):
                    changes.append(self.change(p, "size", c.size_pt, size, run=r))
                if bold is not None and c.bold != bold and change_run(doc, p, r, char_bold(bold)):
                    changes.append(self.change(p, "bold", c.bold, bold, run=r))
        return changes
