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
    assert (tag["sizes"], tag["align"]) == ({8.0}, "CENTER"), "작성자 표기는 받은 대로 (합성 문서: 8pt 가운데)"


def test_name_line_kept_as_is(sample_hwpx, tmp_path):
    """이름 줄은 크기·진하게·정렬·들여쓰기를 받은 대로 [U] 2026-11-04 (합성 문서: 12pt 진하게, 들여쓰기 10pt)."""
    doc, changes = _fixed(sample_hwpx, tmp_path)
    f = _fmt(doc, _para(doc, "홍길동", "REFLECTION_NAME"))
    assert (f["sizes"], f["bold"], f["intent"]) == ({12.0}, {True}, 10.0)
    assert not [c for c in changes if c.role == "REFLECTION_NAME" and c.key in ("size", "bold", "align", "intent")]


def test_three_digit_heading_numbers():
    """2·3단위 번호는 세 자리까지 [U] 2026-11-04."""
    from hra_text.classify import RE_H2, RE_H3

    assert all(RE_H2.match(t) for t in ("1. 제목", "01. 제목", "068. 제목"))
    assert all(RE_H3.match(t) for t in ("1) 제목", "001) 제목", "100) 제목"))
    assert not RE_H2.match("1.5 제목") and not RE_H2.match("1000. 제목")


def test_object_paragraph_alignment_kept(sample_hwpx, tmp_path):
    """표 위치(표 바깥 문단 정렬)는 받은 대로 둔다."""
    doc, _ = _fixed(sample_hwpx, tmp_path)
    kinds = {}
    for p in doc.paras:
        if p.role == "OBJECT":
            kinds[p.tables[0].findtext(".//hp:t", namespaces=NS)] = doc.header.para(p.para_id).align
    assert kinds["목차"] == "CENTER"  # 합성 문서에서 원래 가운데
    assert kinds["소    속"] == "CENTER"  # 원래 가운데 → 그대로
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


def _modifications(changes):
    """알림만 하는 변경(R14 등 check)은 빼고 실제로 고친 것."""
    return [c for c in changes if not c.extra.get("check")]


def test_idempotent(sample_hwpx, tmp_path):
    doc, _ = _fixed(sample_hwpx, tmp_path)
    assert _modifications(run_rules(doc)) == []


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
    assert _modifications(run_rules(ours)) == [], "결과를 다시 고치면 바뀌는 게 없어야 한다"


# ---- R17 줄바꿈으로 이어진 제목·본문 나누기 ----
def _lb_p(runs, para=1):
    """줄바꿈 문단: runs = [(글자, charPr), ...], 글자 속 '\\n' 은 hp:lineBreak."""
    from xml.sax.saxutils import escape

    body = "".join(
        f'<hp:run charPrIDRef="{c}"><hp:t>{escape(t).replace(chr(10), "<hp:lineBreak/>")}</hp:t></hp:run>'
        for t, c in runs)
    return (f'<hp:p id="0" paraPrIDRef="{para}" styleIDRef="0" pageBreak="0" columnBreak="0" '
            f'merged="0">{body}</hp:p>')


def _r17_doc(tmp_path):
    from conftest import MEMO, MEMO_END, build_hwpx, p, section_xml

    body = "".join([
        _lb_p([("표지 줄\n", 0), ("1) 표지 안 번호", 1)]),  # 첫 1단위 타이틀 앞: 나누지 않음
        p("Ⅰ. 첫 장", char=1, para=1),
        _lb_p([("본문 끝 문장이다.\n\n", 0), ("  2) 본문 뒤에 붙은 제목", 1)]),  # 본문 + 제목
        _lb_p([("3) 제목 아래 본문", 1), ("\n 제목 아래 본문입니다.", 0)]),  # 제목 + 본문
        p(""),
        p("4) 다음 제목", char=1, para=1),
        _lb_p([("목록 앞 본문\n1) 진하지 않은 목록\n2) 두 번째 목록", 0)]),  # R17-b: 목록은 본문
        _lb_p([("본문 첫 줄\n본문 둘째 줄", 0)]),  # 줄 역할 하나
        _lb_p([("맨 끝에만 줄바꿈\n", 0)]),
        p("5) 컨트롤 든 문단", char=1, para=1, inner=MEMO,
          after=MEMO_END).replace("컨트롤 든 문단</hp:t>", "컨트롤 든 문단<hp:lineBreak/>컨트롤 뒤 본문</hp:t>"),
    ])
    return build_hwpx(tmp_path / "r17.hwpx", section=section_xml(body))


def test_r17_splits_heading_and_body_lines(tmp_path):
    doc, changes = _fixed(_r17_doc(tmp_path), tmp_path)
    r17 = [c for c in changes if c.rule_id == "R17"]
    assert [(c.old, c.new) for c in r17] == [(3, 3), (2, 2)]
    h = _fmt(doc, _para(doc, "2) 본문 뒤에 붙은 제목", "H3"))
    assert (h["sizes"], h["bold"], h["intent"]) == ({11.0}, {True}, 10.0)
    b = _fmt(doc, _para(doc, "제목 아래 본문입니다.", "BODY"))
    assert (b["sizes"], b["bold"]) == ({10.0}, {False})
    assert _fmt(doc, _para(doc, "3) 제목 아래 본문", "H3"))["sizes"] == {11.0}
    # 앞 공백은 R10 이 지운다
    assert any(p.text == "2) 본문 뒤에 붙은 제목" for p in doc.paras)


def test_r17_keeps_blank_lines(tmp_path):
    """나눈 뒤에도 빈 줄 수는 받은 대로: 원래 빈 문단, 연달은 줄바꿈으로 생긴 빈 줄 모두 남는다."""
    doc, _ = _fixed(_r17_doc(tmp_path), tmp_path)
    body = [p for p in doc.paras if p.container == "body"]
    i = next(i for i, p in enumerate(body) if p.text == "제목 아래 본문입니다.")
    assert body[i + 1].role == "EMPTY" and body[i + 2].text == "4) 다음 제목"
    # 줄바꿈 두 번(빈 줄 1개)은 빈 문단 1개가 된다
    j = next(i for i, p in enumerate(body) if p.text == "본문 끝 문장이다.")
    assert body[j + 1].role == "EMPTY" and body[j + 2].text == "2) 본문 뒤에 붙은 제목"


def test_r17_leaves_other_line_breaks(tmp_path):
    doc, _ = _fixed(_r17_doc(tmp_path), tmp_path)
    texts = [p.text for p in doc.paras if p.container == "body"]
    assert "목록 앞 본문\n1) 진하지 않은 목록\n2) 두 번째 목록" in texts  # R17-b
    assert "본문 첫 줄\n본문 둘째 줄" in texts
    assert "맨 끝에만 줄바꿈\n" in texts
    assert "표지 줄\n1) 표지 안 번호" in texts
    assert any(t.startswith("5) 컨트롤 든 문단\n") for t in texts)


def test_r17_memo_and_idempotent(tmp_path):
    from hra_text.memo import Writer, plan

    doc = Document.open(_r17_doc(tmp_path))
    changes = run_rules(doc)
    lines = [ln for mp in plan(doc, changes) for ln in Writer().lines(mp)]
    assert "- 줄바꿈(Shift+Enter) → 문단 나누기: 문단 3개로" in lines
    out = Document.open(doc.save(tmp_path / "once.hwpx"))
    assert _modifications(run_rules(out)) == []


# ---- §1 장 번호 2단위, R03-d 제목처럼 보이는 본문 줄 [U] 2026-11-10 ----
def test_chapter_number_is_h2():
    from hra_text.classify import RE_H2

    for s in ("1장. 시작", "14장: 운동에 참여하기", "제2장. 정의", " 3 장 . 학습", "1. 시작", "068. 세 자리"):
        assert RE_H2.match(s), s
    for s in ("5장에서 중요한 가정을 찾았다", "14장은 공부 자료다", "1.5배 늘었다", "2장 분량으로 썼다"):
        assert not RE_H2.match(s), s


def _heading_look_doc(tmp_path):
    from conftest import build_hwpx, p, section_xml

    body = "".join([
        p("표지의 진한 줄", char=1),  # 표지 영역: R03-d 대상 아님
        p("Ⅰ. 첫 장", char=1, para=1),
        p("1장. 시작", char=1),  # 장 번호 → H2
        p("Chapter 1 시작", char=1),  # 번호 모양 모름 → 제목처럼 보임
        p("본문인데 진하게 12pt로 쓴 문장입니다.", char=1),  # 마침표로 끝남 → 본문
        p("진하지 않은 12pt 줄", char=6),  # 10.5pt 보통 → 본문
        p("보통 본문", char=0),
    ])
    return build_hwpx(tmp_path / "look.hwpx", section=section_xml(body))


def test_r03d_heading_look_kept_with_memo(tmp_path):
    from hra_text.memo import Writer, plan

    doc = Document.open(_heading_look_doc(tmp_path))
    changes = run_rules(doc)
    out = Document.open(doc.save(tmp_path / "out.hwpx"))
    h2 = _fmt(out, _para(out, "1장. 시작", "H2"))
    assert (h2["sizes"], h2["bold"]) == ({12.0}, {True})
    look = _fmt(out, _para(out, "Chapter 1 시작", "BODY"))
    assert (look["sizes"], look["bold"]) == ({12.0}, {True}), "크기·진하게 받은 대로"
    assert look["intent"] == 10.0, "다른 규칙은 그대로"
    for text in ("본문인데 진하게 12pt로 쓴 문장입니다.", "표지의 진한 줄"):
        f = _fmt(out, _para(out, text))
        assert f["bold"] == {False} or text == "표지의 진한 줄"
    assert _fmt(out, _para(out, "본문인데 진하게 12pt로 쓴 문장입니다."))["sizes"] == {10.0}
    checks = [c for c in changes if c.key == "heading_check"]
    assert [c.old for c in checks] == ["Chapter 1 시작"]
    lines = [ln for mp in plan(doc, changes) for ln in Writer().lines(mp)]
    assert "- 확인 필요: 제목처럼 보이는 줄 'Chapter 1 시작' (크기·진하게 받은 대로)" in lines


def test_r03d_not_repeated_on_feedback_input(tmp_path):
    from hra_text.fixer import fix_document

    res = fix_document(_heading_look_doc(tmp_path), tmp_path / "o1")
    again = run_rules(Document.open(res.feedback))
    assert not [c for c in again if c.key == "heading_check"], "_피드백을 다시 넣으면 같은 지적 안 함"
