"""7단계 규칙: R15 안내문, R16 쪽 번호, R10 앞 공백, R13 숨은 서식, R09 빈 줄, R14 목차."""

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
    assert {"기울임", "밑줄", "글자 색", "셀 음영"} <= items


def test_r13_removes_normal_table_cell_fill_only(sample_hwpx, tmp_path):
    doc, _ = _run(sample_hwpx, tmp_path)
    h = doc.header
    normal = _para(doc, "배경")
    assert h.fill_color(normal.cell.border_fill_id) is None
    h1 = _para(doc, "Ⅰ. 첫 장", "H1")
    assert h.fill_color(h1.cell.border_fill_id).startswith("GRAD:"), "1단위 타이틀 칸 배경 유지"


def test_r09_blank_lines(sample_hwpx, tmp_path):
    doc, changes = _run(sample_hwpx, tmp_path)
    body = [p for p in doc.paras if p.container == "body" and p.depth == 0]
    texts = [p.text.strip() if p.role != "EMPTY" else "" for p in body]
    i = texts.index("1. 둘째 단위")
    assert texts[i + 1] == "1) 셋째 단위", "2단위·3단위 타이틀은 붙여 쓴다"
    j = texts.index("본문입니다→탭 뒤 글자".replace("→", "\t"))
    assert texts[j + 1] == "" and texts[j + 2] == "강조한 본문", "빈 줄 여러 개는 한 줄로"
    variants = {c.extra.get("variant") for c in changes if c.rule_id == "R09"}
    assert {"h2_h3", "too_many"} <= variants
    k = texts.index("가짜 제목")
    assert texts[k - 1] == "", "표지 영역 빈 줄은 건드리지 않는다"


def test_r14_toc_count_mismatch_is_memo_only(sample_hwpx, tmp_path):
    doc, changes = _run(sample_hwpx, tmp_path)
    r14 = [c for c in changes if c.rule_id == "R14"]
    assert [(c.key, c.old, c.new) for c in r14] == [("toc_count", 1, 2)]
    assert all(c.extra.get("check") for c in r14)


def test_cleanup_idempotent(sample_hwpx, tmp_path):
    doc, _ = _run(sample_hwpx, tmp_path)
    assert [c for c in run_rules(doc) if not c.extra.get("check")] == []
