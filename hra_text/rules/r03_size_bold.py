"""R03. 역할별 글자 크기·진하게 (FORMAT_RULES R03 표). SOURCE·AUTHOR_TAG 크기는 표에 있으나
SOURCE 는 R08 이 출처 전용 메모와 함께 처리한다."""

from ..classify import TABLE_H1_BOX, table_kind
from ..hwpx.edit import change_run, char_bold, char_height
from ..hwpx.memo import memo_texts
from . import register
from .base import Rule

# 이미 8pt 인 글자는 크기를 바꾸지 않는다 (참고자료·출처 목록 등) [U] 2026-11-04
KEEP_SIZE_PT = 8.0

# R03-d 제목처럼 보이는 본문 줄 [U] 2026-11-10
HEADING_LOOK_MIN_PT = 12.0
HEADING_LOOK_MAX_LEN = 40
HEADING_LOOK_MARK = "제목처럼 보이는 줄"


def looks_like_heading(doc, p) -> bool:
    """R03-d: BODY 한 줄, 40자 이하, 마침표로 안 끝남, 보이는 글자 모두 진하게, 가장 큰 글자 12pt 이상."""
    text = p.text.strip()
    if p.role != "BODY" or "\n" in text or text.endswith("."):
        return False
    if len("".join(text.split())) > HEADING_LOOK_MAX_LEN:
        return False
    chars = [doc.header.char(r.char_id) for r in p.runs if r.text.strip()]
    return bool(chars) and all(c.bold for c in chars) and max(c.size_pt for c in chars) >= HEADING_LOOK_MIN_PT


def _body_area(doc) -> set:
    """첫 1단위 타이틀 다음의 바깥 본문 문단 (표지 영역 제외)."""
    body = [p for p in doc.paras if p.container == "body" and p.depth == 0]
    first = next((i for i, p in enumerate(body)
                  if p.role == "H1" or (p.role == "OBJECT"
                                        and any(table_kind(doc, t) == TABLE_H1_BOX for t in p.tables))), None)
    return set() if first is None else {id(p.el) for p in body[first + 1:]}


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
    "REFLECTION_NAME": (None, None),  # 이름 줄은 받은 대로 [U] 2026-11-04
    "BODY": (10, False),
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
        area = _body_area(doc)
        for p in self.formatted(doc):
            if p.role not in EXPECTED:
                continue
            if id(p.el) in area and looks_like_heading(doc, p):  # R03-d: 크기·진하게 받은 대로 + 확인
                text = p.text.strip()
                if not any(HEADING_LOOK_MARK in m for m in memo_texts(p.el)):
                    changes.append(self.change(p, "heading_check", text, text, check=True))
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
