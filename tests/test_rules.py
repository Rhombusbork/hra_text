"""R01~R08 규칙 동작 (합성 문서) + 로컬 샘플 회귀."""

import pytest

from hra_text.document import Document
from hra_text.engine import run_rules
from hra_text.hwpx.ns import NS

from conftest import local_samples


def _fixed(sample_hwpx, tmp_path, only=None):
    doc = Document.open(sample_hwpx)
    changes = run_rules(doc, only)
    out = doc.save(tmp_path / "out.hwpx")
    return Document.open(out), changes


def _para(doc, text, role=None):
    found = [p for p in doc.paras if p.text.strip() == text and (role is None or p.role == role)]
    assert found, f"문단 없음: {text}"
    return found[0]


def _fmt(doc, p):
    h = doc.header
    ps = h.para(p.para_id)
    chars = [h.char(r.char_id) for r in p.runs if r.text]
    return {
        "style": h.style_name(p.style_id),
        "sizes": {c.size_pt for c in chars},
        "bold": {c.bold for c in chars},
        "fonts": {f for c in chars for f in c.fonts.values()},
        "align": ps.align,
        **ps.margins_pt,
        "line": ps.line_spacing,
    }


def test_body_paragraph_fully_normalized(sample_hwpx, tmp_path):
    doc, _ = _fixed(sample_hwpx, tmp_path)
    f = _fmt(doc, _para(doc, "앞에 공백이 있는 본문"))
    assert f["style"] == "바탕글"  # R01 (본문 → 바탕글)
    assert f["fonts"] == {"맑은 고딕"}  # R02 (굴림/Calibri)
    assert f["sizes"] == {10.0} and f["bold"] == {False}  # R03 (10.5pt)
    assert f["align"] == "JUSTIFY"  # R04 (LEFT)
    assert (f["intent"], f["left"], f["right"]) == (10.0, 0.0, 0.0)  # R05 (5pt, 15pt)
    assert (f["prev"], f["next"], f["line"]) == (0.0, 0.0, ("PERCENT", 160))  # R06 (4pt, 110%)


def test_headings_and_h4(sample_hwpx, tmp_path):
    doc, _ = _fixed(sample_hwpx, tmp_path)
    assert _fmt(doc, _para(doc, "1. 둘째 단위"))["sizes"] == {12.0}
    h3 = _fmt(doc, _para(doc, "1) 셋째 단위"))
    assert (h3["sizes"], h3["bold"], h3["intent"]) == ({11.0}, {True}, 10.0)
    h4 = _fmt(doc, _para(doc, "① 넷째 단위"))
    assert (h4["sizes"], h4["bold"]) == ({10.0}, {False})


def test_h1_box_keeps_design_and_zero_indent(sample_hwpx, tmp_path):
    doc, _ = _fixed(sample_hwpx, tmp_path)
    p = _para(doc, "Ⅰ. 첫 장", "H1")
    f = _fmt(doc, p)
    assert (f["sizes"], f["bold"], f["intent"]) == ({12.0}, {True}, 0.0)
    assert doc.header.char(p.runs[0].char_id).text_color == "#FFFFFF"


def test_source_and_author_tag(sample_hwpx, tmp_path):
    doc, _ = _fixed(sample_hwpx, tmp_path)
    src = _fmt(doc, _para(doc, "출처 : 가짜 출처"))
    assert (src["sizes"], src["align"], src["intent"]) == ({8.0}, "RIGHT", 0.0)  # R08
    tag = _fmt(doc, _para(doc, "<1장 작성자: 홍길동>"))
    assert (tag["sizes"], tag["align"]) == ({8.0}, "RIGHT")


def test_reflection_name_stays_bold(sample_hwpx, tmp_path):
    doc, _ = _fixed(sample_hwpx, tmp_path)
    f = _fmt(doc, _para(doc, "홍길동", "REFLECTION_NAME"))
    assert (f["sizes"], f["bold"], f["intent"]) == ({10.0}, {True}, 10.0)


def test_object_paragraph_alignment_by_table_kind(sample_hwpx, tmp_path):
    doc, _ = _fixed(sample_hwpx, tmp_path)
    kinds = {}
    for p in doc.paras:
        if p.role == "OBJECT":
            kinds[p.tables[0].findtext(".//hp:t", namespaces=NS)] = doc.header.para(p.para_id).align
    assert kinds["목차"] == "CENTER"
    assert kinds["소    속"] == "RIGHT"
    assert kinds["배경"] == "JUSTIFY"


def test_floating_objects_become_inline(sample_hwpx, tmp_path):
    doc, changes = _fixed(sample_hwpx, tmp_path)
    for p in doc.paras:
        for obj in p.tables + p.pictures:
            assert obj.find("hp:pos", NS).get("treatAsChar") == "1", p.path
    assert sum(c.key == "treatAsChar" for c in changes) == 2


def test_floating_table_moved_after_h1_box(sample_hwpx, tmp_path):
    """떠 있던 표가 타이틀 칸 앞에 앵커돼 있어도, 결과에선 타이틀 칸 다음 문단에 온다."""
    doc, _ = _fixed(sample_hwpx, tmp_path)
    order = [p.text.strip() for p in doc.paras
             if p.role != "TOC_ITEM" and p.text.strip() in ("Ⅰ. 첫 장", "떠 있는 표")]
    assert order == ["Ⅰ. 첫 장", "떠 있는 표"]
    h1, floating = _para(doc, "Ⅰ. 첫 장", "H1"), _para(doc, "떠 있는 표")
    assert h1.path.split("/")[1] != floating.path.split("/")[1], "서로 다른 바깥 문단이어야 한다"


def test_memo_and_guide_untouched(sample_hwpx, tmp_path):
    doc, changes = _fixed(sample_hwpx, tmp_path)
    assert not [c for c in changes if c.role in ("SKIP", "GUIDE")]


def test_shared_para_shape_not_modified_in_place(sample_hwpx, tmp_path):
    doc = Document.open(sample_hwpx)
    before = doc.header.para("3").margins_pt
    run_rules(doc)
    assert doc.header.para("3").margins_pt == before


def test_idempotent(sample_hwpx, tmp_path):
    doc, _ = _fixed(sample_hwpx, tmp_path)
    assert run_rules(doc) == []


def test_only_selected_rules(sample_hwpx, tmp_path):
    _, changes = _fixed(sample_hwpx, tmp_path, only={"R01"})
    assert {c.rule_id for c in changes} == {"R01"}
    with pytest.raises(ValueError):
        run_rules(Document.open(sample_hwpx), {"R99"})


def test_original_file_unchanged(sample_hwpx, tmp_path):
    before = sample_hwpx.read_bytes()
    _fixed(sample_hwpx, tmp_path)
    assert sample_hwpx.read_bytes() == before


# ---- 로컬 실제 샘플 회귀 (커밋 안 됨) ----
BEFORE = local_samples("*기업실무*재제출*.hwp")
AFTER = [p for p in local_samples("*기업실무(AI*.hwp") if "재제출" not in p.name]
# 사용자 수정본이 규칙과 다른 곳 (수정 누락으로 확인되었거나 규칙상 우리 쪽이 맞는 것)
KNOWN_REFERENCE_MISSES = {
    ("TABLE_CELL", "align"), ("TABLE_CELL", "style"), ("TABLE_CELL", "size"),
    ("TABLE_CELL", "prev"), ("TABLE_CELL", "next"), ("TABLE_CELL", "line"),
    ("TOC_ITEM", "style"), ("TOC_ITEM", "next"), ("TOC_ITEM", "line"),
    ("SOURCE", "size"), ("SOURCE", "align"), ("SOURCE", "intent"),  # [U] 2026-10-29 수정 누락
    ("H2", "size"), ("H2", "bold"),
}


@pytest.mark.skipif(not (BEFORE and AFTER), reason="로컬 샘플 없음")
def test_regression_against_user_correction(tmp_path):
    from hra_text.compare import compare

    doc = Document.open(BEFORE[0], work_dir=tmp_path)
    run_rules(doc)
    ours = Document.open(doc.save(tmp_path / "ours.hwpx"))
    diffs, stats = compare(ours, Document.open(AFTER[0], work_dir=tmp_path))
    assert stats["matched"] > 500
    unexpected = {(d.role, d.attr) for d in diffs} - KNOWN_REFERENCE_MISSES
    assert not unexpected, unexpected
    assert run_rules(ours) == [], "결과를 다시 고치면 바뀌는 게 없어야 한다"
