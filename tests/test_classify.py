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
    assert roles["느낀 점 본문입니다."] == "REFLECTION"
    assert roles["메모 내용입니다."] == "SKIP"
    h1 = [t for t, r in _roles(doc) if r == "H1"]
    assert h1 == ["Ⅰ. 첫 장", "Ⅱ. 느낀 점"]
    toc_items = [t for t, r in _roles(doc) if r == "TOC_ITEM"]
    assert toc_items == ["Ⅰ. 첫 장"], "목차 안의 'Ⅰ.' 은 H1 이 아니다"


def test_tab_text_is_read(sample_hwpx):
    doc = Document.open(sample_hwpx)
    assert any("탭 뒤 글자" in p.text for p in doc.paras)


# ---- 로컬 실제 샘플 (커밋 안 됨): 사용자 확인을 거친 역할 개수 회귀 ----
FEEDBACK = local_samples("*경영서*_피드백.hwpx")
CLASSIC = local_samples("*고전*.hwp")


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
