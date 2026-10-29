"""문단 역할 분류 (docs/FORMAT_RULES.md §1).

규칙은 모두 이 역할을 보고 기대값을 정한다. 분류 기준을 바꾸면 FORMAT_RULES §1 도 같이 고친다.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .document import Document
    from .hwpx.section import Para

# 역할 ID (FORMAT_RULES §1 표와 같아야 한다)
GUIDE = "GUIDE"
CATEGORY = "CATEGORY"
COVER_TITLE = "COVER_TITLE"
TOC_TITLE = "TOC_TITLE"
TOC_ITEM = "TOC_ITEM"
COVER_TABLE = "COVER_TABLE"
H1 = "H1"
H2 = "H2"
H3 = "H3"
H4 = "H4"
BODY = "BODY"
SOURCE = "SOURCE"
AUTHOR_TAG = "AUTHOR_TAG"
TABLE_CELL = "TABLE_CELL"
OBJECT = "OBJECT"
EMPTY = "EMPTY"
REFLECTION_NAME = "REFLECTION_NAME"
REFLECTION = "REFLECTION"
INTRO_TITLE = "INTRO_TITLE"
INTRO_IMAGE = "INTRO_IMAGE"
INTRO_BODY = "INTRO_BODY"
READING_TITLE = "READING_TITLE"
READING_BYLINE = "READING_BYLINE"
SKIP = "SKIP"

ROLES = (
    GUIDE, CATEGORY, COVER_TITLE, TOC_TITLE, TOC_ITEM, COVER_TABLE, H1, H2, H3, H4, BODY,
    SOURCE, AUTHOR_TAG, TABLE_CELL, OBJECT, EMPTY, REFLECTION_NAME, REFLECTION,
    INTRO_TITLE, INTRO_IMAGE, INTRO_BODY, READING_TITLE, READING_BYLINE, SKIP,
)

# 표 종류
TABLE_TOC = "TOC"
TABLE_COVER = "COVER"
TABLE_INTRO = "INTRO"
TABLE_H1_BOX = "H1_BOX"
TABLE_NORMAL = "NORMAL"

GUIDE_COLOR = "#FF0000"
RE_H1 = re.compile(r"^\s*[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ]\s*\.")
RE_H2 = re.compile(r"^\s*\d{1,2}\.(?!\d)\s*\S")
RE_H3 = re.compile(r"^\s*\d{1,2}\)\s*\S")
RE_H4 = re.compile(r"^\s*[①-⑳]")
RE_SOURCE = re.compile(r"^\s*(사진\s*)?(출처|참고\s*자료|자료)\s*[:：]")
RE_AUTHOR_TAG = re.compile(r"^\s*<[^>]*작성자\s*[:：][^>]*>\s*$")
RE_NAME = re.compile(r"^[가-힣]{2,4}$")
RE_BYLINE = re.compile(r"HRA\s*\d+\s*기")
REFLECTION_WORDS = ("느낀 점", "느낀점", "소감", "후기")
COVER_LABELS = {"소속", "조원", "발표자", "담당교수", "발표일"}
COVER_TITLE_MIN_PT = 20
H1_BOX_TEXT_COLOR = "#FFFFFF"  # 템플릿의 1단위 타이틀 칸: 검정 그라데이션 배경 + 흰 글씨
INTRO_SECTION_WORDS = ("소개",)  # Ⅰ. 책 소개 / Ⅱ. 저자 소개


def _squash(s: str) -> str:
    return re.sub(r"\s+", "", s)


def _top_index(para: "Para") -> int:
    """가장 바깥 본문 문단의 번호 (s0/p21/... → 21). 구역이 여러 개면 (구역, 번호)로 정렬 가능."""
    sec, top = para.path.split("/")[:2]
    return int(sec[1:]) * 1_000_000 + int(top[1:])


def _table_texts(doc: "Document") -> dict[int, list[str]]:
    """표(id) → 그 표 셀 안 문단 텍스트 목록 (중첩 표 포함)."""
    texts: dict[int, list[str]] = {}
    for p in doc.paras:
        if p.cell is not None:
            texts.setdefault(id(p.cell.tbl), []).append(p.text)
    return texts


def _tc_span(tc) -> tuple[int, int]:
    span = tc.find("{http://www.hancom.co.kr/hwpml/2011/paragraph}cellSpan")
    if span is None:
        return 1, 1
    return int(span.get("colSpan", "1")), int(span.get("rowSpan", "1"))


def _is_h1_box(doc: "Document", p: "Para") -> bool:
    """1x1 표 안의 흰 글씨 문단이면 1단위 타이틀 칸 (배경은 검정 그라데이션이라 글씨 색으로 판별)."""
    tbl = p.cell.tbl
    if tbl.get("rowCnt") != "1" or tbl.get("colCnt") != "1":
        return False
    visible = [r for r in p.runs if r.text.strip()]
    return bool(visible) and all(
        doc.header.char(r.char_id).text_color == H1_BOX_TEXT_COLOR for r in visible
    )


def _is_intro_table(tbl, has_pic: bool, in_intro_section: bool) -> bool:
    """책 소개/저자 소개 표: 2x2, 첫 줄이 한 칸으로 병합된 제목 칸."""
    if tbl.get("rowCnt") != "2" or tbl.get("colCnt") != "2":
        return False
    first = tbl.find("{http://www.hancom.co.kr/hwpml/2011/paragraph}tr/{http://www.hancom.co.kr/hwpml/2011/paragraph}tc")
    if first is None or _tc_span(first)[0] != 2:
        return False
    return has_pic or in_intro_section


def is_guide_run(doc: "Document", char_id: str) -> bool:
    return doc.header.char(char_id).text_color == GUIDE_COLOR


def classify(doc: "Document") -> None:
    paras = doc.paras
    table_texts = _table_texts(doc)
    toc_tables = {t for t, ts in table_texts.items() if any(x.strip() == "목차" for x in ts)}
    cover_tables = {
        t for t, ts in table_texts.items()
        if len({_squash(x) for x in ts} & COVER_LABELS) >= 2
    }

    def is_h1(p: "Para") -> bool:
        if p.cell is not None and _is_h1_box(doc, p):
            return True
        if not RE_H1.match(p.text):
            return False
        return p.cell is None or id(p.cell.tbl) not in toc_tables

    # 1단위 타이틀이 들어 있는 바깥 문단 → 그 아래 영역의 시작점
    h1_text_by_top: dict[int, str] = {}
    for p in paras:
        if p.container in ("body", "cell") and is_h1(p):
            h1_text_by_top.setdefault(_top_index(p), p.text)
    first_h1_top = min(h1_text_by_top, default=10**12)

    # 책 소개/저자 소개 표, 그리고 그림이 든 셀
    # 그림 칸: 그림이 있거나 "그림"(템플릿 자리표시) 문단이 있는 셀 전체
    pic_cells = {
        id(p.cell.tc) for p in paras
        if p.cell is not None and (p.pictures or _squash(p.text).startswith("그림"))
    }
    pic_tables = {id(p.top_cell.tbl) for p in paras if p.top_cell is not None and p.pictures}
    intro_tables: set[int] = set()
    section_h1 = ""
    for p in paras:
        if _top_index(p) in h1_text_by_top:
            section_h1 = h1_text_by_top[_top_index(p)]
        if p.cell is None:
            in_intro = any(w in section_h1 for w in INTRO_SECTION_WORDS)
            for tbl in p.tables:
                if _is_intro_table(tbl, id(tbl) in pic_tables, in_intro):
                    intro_tables.add(id(tbl))

    current_h1 = ""
    current_top = -1
    seen_category = 0
    reading_part = False  # 고전 '함께읽기용' 부분 (두 번째 ■ 이후)
    reading_title_done = False

    for p in paras:
        top = _top_index(p)
        if top != current_top:
            current_top = top
            if top in h1_text_by_top:
                current_h1 = h1_text_by_top[top]
                reading_part = False

        if p.container not in ("body", "cell"):
            p.role = SKIP
            continue

        text = p.text
        stripped = text.strip()
        visible_runs = [r for r in p.runs if r.text.strip()]

        if visible_runs and all(is_guide_run(doc, r.char_id) for r in visible_runs):
            p.role = GUIDE
            continue

        # 표 안
        if p.cell is not None:
            tbl = id(p.top_cell.tbl)
            if tbl in intro_tables and p.cell.tbl is p.top_cell.tbl:
                if RE_SOURCE.match(text):
                    p.role = SOURCE
                elif p.cell.row == 0:
                    p.role = INTRO_TITLE
                elif id(p.cell.tc) in pic_cells:
                    p.role = INTRO_IMAGE
                else:
                    p.role = INTRO_BODY
            elif tbl in toc_tables:
                p.role = TOC_TITLE if stripped == "목차" else (TOC_ITEM if stripped else EMPTY)
            elif tbl in cover_tables:
                p.role = COVER_TABLE
            elif is_h1(p):
                p.role = H1
            elif RE_SOURCE.match(text):
                p.role = SOURCE
            else:
                p.role = TABLE_CELL
            continue

        # 본문
        if stripped.startswith("■"):
            seen_category += 1
            p.role = CATEGORY
            if seen_category > 1:
                reading_part, reading_title_done = True, False
            continue
        if p.is_empty:
            p.role = EMPTY
            continue
        if not stripped:
            p.role = OBJECT
            continue
        if is_h1(p):
            p.role = H1
            continue

        if top < first_h1_top:  # 표지 영역
            sizes = [doc.header.char(r.char_id).size_pt for r in visible_runs]
            p.role = COVER_TITLE if sizes and max(sizes) >= COVER_TITLE_MIN_PT else BODY
            continue

        if reading_part:
            if not reading_title_done:
                p.role, reading_title_done = READING_TITLE, True
                continue
            if RE_BYLINE.search(text) and len(stripped) <= 40:
                p.role = READING_BYLINE
                continue

        if RE_SOURCE.match(text):
            p.role = SOURCE
        elif RE_AUTHOR_TAG.match(text):
            p.role = AUTHOR_TAG
        elif RE_H2.match(text):
            p.role = H2
        elif RE_H3.match(text):
            p.role = H3
        elif RE_H4.match(text):
            p.role = H4
        elif any(w in current_h1 for w in REFLECTION_WORDS):
            p.role = REFLECTION_NAME if RE_NAME.match(stripped) else REFLECTION
        else:
            p.role = BODY

    # 표 종류 (R04 등에서 개체 문단 정렬을 정할 때 사용): id(hp:tbl) → 종류
    kinds: dict[int, str] = {}
    for p in paras:
        if p.role == H1 and p.cell is not None:
            kinds[id(p.cell.tbl)] = TABLE_H1_BOX
    kinds.update({t: TABLE_TOC for t in toc_tables})
    kinds.update({t: TABLE_COVER for t in cover_tables})
    kinds.update({t: TABLE_INTRO for t in intro_tables})
    doc.table_kinds = kinds


def table_kind(doc: "Document", tbl) -> str:
    return getattr(doc, "table_kinds", {}).get(id(tbl), TABLE_NORMAL)
