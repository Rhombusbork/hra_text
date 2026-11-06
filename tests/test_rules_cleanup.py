"""7단계 규칙: R15 안내문, R16 쪽 번호, R10 앞 공백, R13 숨은 서식, R14 목차. (R09 빈 줄 정리는 폐기 — 빈 줄은 받은 대로)"""

from hra_text.document import Document
from hra_text.engine import run_rules
from hra_text.hwpx.ns import NS, hp


def _run(path, tmp_path, only=None):
    doc = Document.open(path)
    changes = run_rules(doc, only)
    return Document.open(doc.save(tmp_path / "out.hwpx")), changes


def _texts(doc):
    return [p.text for p in doc.paras if p.container in ("body", "cell")]


def _para(doc, text, role=None):
    return next(p for p in doc.paras if p.text.strip() == text and (role is None or p.role == role))


def test_r15_removes_red_guide_text(sample_hwpx, tmp_path):
    doc, changes = _run(sample_hwpx, tmp_path)
    texts = _texts(doc)
    assert not any("본문내용(맑은 고딕" in t for t in texts), "빨간 안내문 문단은 지워진다"
    assert "■ 경영서" in [t.strip() for t in texts], "일부만 빨간 문단은 빨간 글자만 지운다"
    assert not any("발표자용" in t for t in texts)
    assert {c.old for c in changes if c.rule_id == "R15"} == {"발표자용", "본문내용(맑은 고딕, 10, 들여쓰기 10)"}


def test_r15b_removes_template_notes(tmp_path):
    from conftest import SECTION, build_hwpx

    path = build_hwpx(tmp_path / "s.hwpx", section=SECTION.replace("가짜 제목", "가짜 제목(맑은 고딕, 32, 진하게)"))
    doc, changes = _run(path, tmp_path)
    assert "가짜 제목" in [p.text.strip() for p in doc.paras]
    assert "(맑은 고딕, 32, 진하게)" in {c.old for c in changes if c.rule_id == "R15"}


def test_r16_removes_page_number(sample_hwpx, tmp_path):
    doc, changes = _run(sample_hwpx, tmp_path)
    left = [e.get("pos") for e in doc.pkg.sections()[0].iter(hp("pageNum"))]
    assert left == ["NONE"], "보이는 쪽 번호만 지우고 '쪽 번호 없음' 설정은 둔다"
    assert [c.key for c in changes if c.rule_id == "R16"] == ["page_num"]


def test_r10_strips_leading_spaces(sample_hwpx, tmp_path):
    doc, _ = _run(sample_hwpx, tmp_path)
    assert "앞에 공백이 있는 본문" in [p.text for p in doc.paras]


def test_r13_resets_hidden_formatting_but_keeps_links_and_h1(sample_hwpx, tmp_path):
    doc, changes = _run(sample_hwpx, tmp_path)
    h = doc.header
    c = h.char(_para(doc, "강조한 본문").runs[0].char_id)
    assert (c.italic, c.underline, c.text_color) == (False, False, "#000000")
    link_para = _para(doc, "링크 앞 링크 글자")
    link = h.char(link_para.runs[1].char_id)
    assert (link.text_color, link.underline) == ("#0000FF", True), "하이퍼링크 색·밑줄은 유지"
    h1 = _para(doc, "Ⅰ. 첫 장", "H1")
    assert h.char(h1.runs[0].char_id).text_color == "#FFFFFF", "1단위 타이틀 칸 흰 글씨 유지"
    items = {c.extra.get("item") for c in changes if c.rule_id == "R13"}
    assert {"기울임", "밑줄", "글자 색"} <= items
    assert "셀 음영" not in items, "셀 음영은 받은 대로 둔다"


def test_table_cell_fill_kept(sample_hwpx, tmp_path):
    """표 안 셀 음영은 받은 대로 둔다 [U] 2026-11-03."""
    doc, _ = _run(sample_hwpx, tmp_path)
    h = doc.header
    assert h.fill_color(_para(doc, "배경").cell.border_fill_id) == "#FFFF00"
    h1 = _para(doc, "Ⅰ. 첫 장", "H1")
    assert h.fill_color(h1.cell.border_fill_id).startswith("GRAD:"), "1단위 타이틀 칸 배경 유지"


def test_table_cell_align_bold_color_kept_size_fixed(tmp_path):
    """표 안: 정렬·진하게·글자 색은 받은 대로, 글자 크기·글꼴은 맞춘다 [U] 2026-11-03."""
    from conftest import SECTION, build_hwpx, p, table

    cell = p("가운데 머리칸", char=1, para=2) + p("색 글자", char=7, para=0)
    section = SECTION.replace(p("느낀 점 본문입니다.", para=1),
                              p("느낀 점 본문입니다.", para=1) + p(inner=table([[cell]])))
    doc, _ = _run(build_hwpx(tmp_path / "s.hwpx", section=section), tmp_path)
    h = doc.header
    head = _para(doc, "가운데 머리칸")
    c = h.char(head.runs[0].char_id)
    assert (h.para(head.para_id).align, c.bold, c.size_pt) == ("CENTER", True, 10.0)
    colored = h.char(_para(doc, "색 글자").runs[0].char_id)
    assert colored.text_color == "#00AA00", "표 안 글자 색은 받은 대로"
    assert (colored.italic, colored.underline) == (False, False), "기울임·밑줄은 표 안이어도 기본값으로"


def test_blank_lines_kept_as_is(sample_hwpx, tmp_path):
    """R09 폐기 [U] 2026-11-06: 빈 줄 수는 받은 대로 (타이틀 아래·여러 줄·표지 모두)."""
    def blanks(doc):
        body = [p for p in doc.paras if p.container == "body" and p.depth == 0]
        return ["" if p.role == "EMPTY" else (p.text.strip() or "<개체>") for p in body]

    before = blanks(Document.open(sample_hwpx))
    doc, changes = _run(sample_hwpx, tmp_path)
    texts = blanks(doc)
    i = texts.index("1. 둘째 단위")
    assert texts[i + 1] == "" and texts[i + 2] == "1) 셋째 단위", "타이틀 아래 빈 줄도 그대로"
    j = texts.index("본문입니다\t탭 뒤 글자")
    assert texts[j + 1:j + 4] == ["", "", ""] and texts[j + 4] == "강조한 본문", "여러 줄도 그대로"
    assert texts.count("") == before.count(""), "빈 줄 수가 바뀌면 안 된다"
    assert not any(c.key == "blank_lines" for c in changes)


def test_r14_toc_count_mismatch_is_memo_only(sample_hwpx, tmp_path):
    doc, changes = _run(sample_hwpx, tmp_path)
    r14 = [c for c in changes if c.rule_id == "R14"]
    assert [(c.key, c.old, c.new) for c in r14] == [("toc_count", 1, 2)]
    assert all(c.extra.get("check") for c in r14)


def test_cleanup_idempotent(sample_hwpx, tmp_path):
    doc, _ = _run(sample_hwpx, tmp_path)
    assert [c for c in run_rules(doc) if not c.extra.get("check")] == []


def test_r11_spacing_dict_pattern_and_check(tmp_path):
    from conftest import SECTION, build_hwpx

    section = SECTION.replace("느낀 점 본문입니다.", "경영학과4학년 직종별유연근무제제안 가나다라마바사아자차카타파하거너")
    doc, changes = _run(build_hwpx(tmp_path / "s.hwpx", section=section), tmp_path)
    text = next(p.text for p in doc.paras if "경영학과" in p.text)
    assert "경영학과 4학년 직종별 유연근무제 제안" in text
    r11 = [(c.key, c.old) for c in changes if c.rule_id == "R11"]
    assert ("spacing", "경영학과4학년") in r11 and ("spacing", "직종별유연근무제제안") in r11
    assert ("spacing_check", "가나다라마바사아자차카타파하거너") in r11, "사전에 없는 긴 덩어리는 확인 메모만"
    assert "가나다라마바사아자차카타파하거너" in text, "확인만 하고 고치지 않는다"


def test_r11_dict_file_is_well_formed():
    from hra_text.rules.r11_spacing import load_dict

    pairs = load_dict()
    assert pairs and all(w.replace(" ", "") == r.replace(" ", "") for w, r in pairs), \
        "사전은 띄어쓰기만 바꿔야 한다 (글자가 달라지면 안 됨)"


def test_small_right_paragraph_untouched(tmp_path):
    """이미 8pt·오른쪽 정렬인 문단은 어떤 수정도 하지 않는다 [U] 2026-11-03."""
    from conftest import HEADER, SECTION, _para as make_para, build_hwpx, p

    header = HEADER.replace('<hh:paraProperties itemCnt="4">', '<hh:paraProperties itemCnt="5">').replace(
        "</hh:paraProperties>", make_para(4, align="RIGHT", intent=10, nxt=4, line=110) + "</hh:paraProperties>")
    right8 = p("출처 모음 : 가짜 자료1", char=5, para=4, style=1)
    section = SECTION.replace(p("느낀 점 본문입니다.", para=1), p("느낀 점 본문입니다.", para=1) + right8)
    doc, changes = _run(build_hwpx(tmp_path / "s.hwpx", header=header, section=section), tmp_path)
    q = _para(doc, "출처 모음 : 가짜 자료1")
    assert q.role == "KEEP"
    assert not [c for c in changes if c.text.strip() == "출처 모음 : 가짜 자료1"]
    ps = doc.header.para(q.para_id)
    assert (ps.align, ps.margins_pt["intent"], ps.line_spacing[1]) == ("RIGHT", 10.0, 110)
    assert doc.header.style_name(q.style_id) == "본문", "스타일도 그대로"


def test_8pt_text_keeps_size(tmp_path):
    """이미 8pt인 글자는 크기를 바꾸지 않는다 (정렬 등 다른 서식은 규칙대로) [U] 2026-11-04."""
    from conftest import SECTION, build_hwpx, p

    small = p("참고자료 목록 가짜 줄", char=5, para=3, style=1)  # 8pt, 왼쪽 정렬, 본문 스타일
    section = SECTION.replace(p("느낀 점 본문입니다.", para=1), p("느낀 점 본문입니다.", para=1) + small)
    doc, _ = _run(build_hwpx(tmp_path / "s.hwpx", section=section), tmp_path)
    q = _para(doc, "참고자료 목록 가짜 줄")
    assert doc.header.char(q.runs[0].char_id).size_pt == 8.0
    assert doc.header.para(q.para_id).align == "JUSTIFY"
    assert doc.header.style_name(q.style_id) == "바탕글"
