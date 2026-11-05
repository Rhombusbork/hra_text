from collections import Counter

import pytest

from hra_text.document import Document

from conftest import local_samples


def _roles(doc):
    return [(p.text.strip(), p.role) for p in doc.paras if p.role not in ("EMPTY",)]


def test_synthetic_roles(sample_hwpx):
    doc = Document.open(sample_hwpx)
    roles = dict((t, r) for t, r in _roles(doc) if t)
    assert roles["■ 경영서 발표자용"] == "CATEGORY"  # 일부만 빨간 글씨 → 역할은 CATEGORY
    assert roles["가짜 제목"] == "COVER_TITLE"
    assert roles["목차"] == "TOC_TITLE"
    assert roles["소    속"] == "COVER_TABLE"
    assert roles["1. 둘째 단위"] == "H2"
    assert roles["1) 셋째 단위"] == "H3"
    assert roles["① 넷째 단위"] == "H4"
    assert roles["본문입니다\t탭 뒤 글자"] == "BODY"
    assert roles["앞에 공백이 있는 본문"] == "BODY"
    assert roles["본문내용(맑은 고딕, 10, 들여쓰기 10)"] == "GUIDE"
    assert roles["출처 : 가짜 출처"] == "SOURCE"
    assert roles["<1장 작성자: 홍길동>"] == "AUTHOR_TAG"
    assert roles["배경"] == "TABLE_CELL"
    assert roles["홍길동"] == "REFLECTION_NAME"
    assert roles["느낀 점 본문입니다."] == "BODY"
    assert roles["메모 내용입니다."] == "SKIP"
    h1 = [t for t, r in _roles(doc) if r == "H1"]
    assert h1 == ["Ⅰ. 첫 장", "Ⅱ. 느낀 점"]
    toc_items = [t for t, r in _roles(doc) if r == "TOC_ITEM"]
    assert toc_items == ["Ⅰ. 첫 장"], "목차 안의 'Ⅰ.' 은 H1 이 아니다"


def test_tab_text_is_read(sample_hwpx):
    doc = Document.open(sample_hwpx)
    assert any("탭 뒤 글자" in p.text for p in doc.paras)


# ---- 로컬 실제 샘플 (커밋 안 됨): 사용자 확인을 거친 역할 개수 회귀 ----
FEEDBACK = local_samples("*경영서*가이드)_피드백.hwpx")  # 사용자 피드백 원본 (프로그램 결과 _피드백 제외)
CLASSIC = local_samples("*OOO-고전*.hwp")  # 고전 템플릿만 (실제 제출본 제외)


@pytest.mark.skipif(not FEEDBACK, reason="로컬 샘플 없음")
def test_feedback_sample_roles():
    c = Counter(p.role for p in Document.open(FEEDBACK[0]).paras)
    assert c["H1"] == 4
    assert c["REFLECTION_NAME"] == 6
    assert c["AUTHOR_TAG"] == 6
    assert c["INTRO_TITLE"] == 2


@pytest.mark.skipif(not CLASSIC, reason="로컬 샘플 없음")
def test_classic_template_roles():
    c = Counter(p.role for p in Document.open(CLASSIC[0]).paras)
    assert c["H1"] == 6  # Ⅰ~Ⅴ + "1단위 타이틀" 예시 칸
    assert c["GUIDE"] == 3
    assert c["CATEGORY"] == 2
    assert (c["READING_TITLE"], c["READING_BYLINE"]) == (1, 1)


ESSAYS = local_samples("*에세이*.hwp")


@pytest.mark.skipif(not ESSAYS, reason="로컬 샘플 없음")
@pytest.mark.parametrize("src", ESSAYS, ids=lambda p: p.stem[:12])
def test_essay_is_reading_format(src, tmp_path):
    """에세이 = 고전 함께읽기용 형식: 제목·작성자 줄을 본문으로 착각하지 않는다."""
    from hra_text.engine import run_rules

    doc = Document.open(src, work_dir=tmp_path)
    c = Counter(p.role for p in doc.paras)
    assert (c["READING_TITLE"], c["READING_BYLINE"]) == (1, 1)
    changes = run_rules(doc)
    assert all(ch.rule_id == "R10" for ch in changes), "에세이는 (문단 앞 공백 외) 고칠 게 없어야 한다"


def test_photo_table_outside_intro_section_is_normal_table(tmp_path):
    """사진이 든 2×2 병합 표라도 '책 소개/저자 소개' 아래가 아니면 일반 표 (기업실무 사진 표)."""
    from conftest import PIC, SECTION, build_hwpx, p, table

    photo = p(inner=table([[p("③매장 분위기")], [p(inner=PIC.format(ref="image1")), p("설명")]], col_span_first=2))
    doc = Document.open(build_hwpx(tmp_path / "s.hwpx", section=SECTION.replace(
        p("느낀 점 본문입니다.", para=1), p("느낀 점 본문입니다.", para=1) + photo)))
    roles = {q.text.strip(): q.role for q in doc.paras if q.text.strip()}
    assert roles["③매장 분위기"] == "TABLE_CELL"


def test_author_tag_detection():
    from hra_text.classify import AUTHOR_TAG_MAX_LEN, RE_AUTHOR_TAG

    def is_tag(t):
        return bool(RE_AUTHOR_TAG.search(t)) and len(t.strip()) <= AUTHOR_TAG_MAX_LEN

    assert is_tag("<9~58.p 작성자: 김지섭>")
    assert is_tag("<111~153p 작성자 : 경제학과 최형기>")  # 샘플 최장 25자
    assert is_tag("<262~298p 작성자 : 오현주><p.262~298>")  # 꺾쇠 두 쌍
    assert not is_tag("<듀얼 브레인>은 필독서다. 작성자는 이선 몰릭이다 >")  # 작성자가 꺾쇠 밖
    assert not is_tag("<" + "가" * 31 + " 작성자: 홍길동>")  # 꺾쇠 안이 30자를 넘음
    assert not is_tag("익명이라는 이유만으로 게시물을 일괄 삭제하거나 작성자를 처벌하는 방식은 바람직하지 않다")


def test_name_line_needs_name_written_in_document(tmp_path):
    """이름 줄은 위치가 아니라 문서에 적힌 이름(표지 표 등)과 같은지로 판별 [U] 2026-11-04."""
    from conftest import SECTION, build_hwpx, p

    extra = p("홍길동", char=1, para=1) + p("들어가며", char=1, para=1)  # 느낀 점 영역 밖
    section = SECTION.replace(p("1. 둘째 단위", char=1, para=1), extra + p("1. 둘째 단위", char=1, para=1))
    doc = Document.open(build_hwpx(tmp_path / "n.hwpx", section=section))
    roles = [(q.text.strip(), q.role) for q in doc.paras
             if q.cell is None and q.text.strip() in ("홍길동", "들어가며")]
    assert roles == [("홍길동", "REFLECTION_NAME"), ("들어가며", "BODY"), ("홍길동", "REFLECTION_NAME")]
