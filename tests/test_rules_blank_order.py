"""R18 11·12pt 줄 위 빈 줄, R19 경영서 이름 순서 (합성 문서, 개인정보 없음)."""

from conftest import build_hwpx, p, section_xml, table

from hra_text.document import Document
from hra_text.engine import run_rules


def _body_texts(doc):
    body = [q for q in doc.paras if q.container == "body" and q.depth == 0]
    return ["" if q.role == "EMPTY" else (q.text.strip() or "<개체>") for q in body]


def _after(texts, text):
    i = texts.index(text)
    return texts[i - 2:i]


def _run(path, tmp_path):
    doc = Document.open(path)
    changes = run_rules(doc)
    return Document.open(doc.save(tmp_path / "out.hwpx")), changes


# ---- R18 ----
def _r18_doc(tmp_path):
    body = "".join([
        p("표지 줄", char=1),
        p("Ⅰ. 첫 장", char=1, para=1),
        p("1. 둘째 단위", char=1, para=1),  # 1단위 바로 아래: 붙여 씀
        p("1) 셋째 단위", char=1, para=1),  # 2단위 바로 아래: 붙여 씀
        p("본문 하나.", para=1),
        p("2) 본문 바로 아래 제목", char=1, para=1),  # 넣음
        p("본문 둘.", para=1),
        p(""),
        p("3) 이미 한 줄", char=1, para=1),  # 그대로
        p("본문 셋.", para=1),
        p(""),
        p(""),
        p("4) 이미 두 줄", char=1, para=1),  # 그대로 (지우지 않음)
        p("① 넷째 단위", para=1),
        p("5) 4단위 아래 제목", char=1, para=1),  # 4단위는 내용: 넣음
        p("본문 넷.", para=1),
        p("Ⅱ. 둘째 장", char=1, para=1),  # 1단위는 대상 아님
        p("본문 다섯.", para=1),
        p("Chapter 2 시작", char=1),  # 제목처럼 보이는 줄: 넣음
        p("본문 여섯.", para=1),
        p("6) 쪽 나누기 제목", char=1, para=1).replace('pageBreak="0"', 'pageBreak="1"', 1),  # 쪽과 무관: 넣음
    ])
    return build_hwpx(tmp_path / "r18.hwpx", section=section_xml(body))


def test_r18_inserts_only_after_content(tmp_path):
    doc, changes = _run(_r18_doc(tmp_path), tmp_path)
    t = _body_texts(doc)
    assert _after(t, "1. 둘째 단위")[-1] == "Ⅰ. 첫 장"
    assert _after(t, "1) 셋째 단위")[-1] == "1. 둘째 단위"
    assert _after(t, "2) 본문 바로 아래 제목") == ["본문 하나.", ""]
    assert _after(t, "3) 이미 한 줄") == ["본문 둘.", ""]
    i = t.index("4) 이미 두 줄")
    assert t[i - 3:i] == ["본문 셋.", "", ""]
    assert _after(t, "5) 4단위 아래 제목") == ["① 넷째 단위", ""]
    assert _after(t, "Ⅱ. 둘째 장")[-1] == "본문 넷."
    assert _after(t, "Chapter 2 시작") == ["본문 다섯.", ""]
    assert _after(t, "6) 쪽 나누기 제목") == ["본문 여섯.", ""]
    assert t.index("표지 줄") == 0 and t[1] == "Ⅰ. 첫 장"
    assert len([c for c in changes if c.key == "blank_above"]) == 4


def test_r18_blank_format_and_page_break(tmp_path):
    doc, _ = _run(_r18_doc(tmp_path), tmp_path)
    body = [q for q in doc.paras if q.container == "body" and q.depth == 0]
    i = next(k for k, q in enumerate(body) if q.text.strip() == "6) 쪽 나누기 제목")
    blank, head = body[i - 1], body[i]
    assert blank.role == "EMPTY" and blank.el.get("pageBreak") == "0" and head.el.get("pageBreak") == "1"
    c = doc.header.char(blank.runs[0].char_id)
    assert (c.size_pt, c.bold) == (10.0, False)
    assert blank.para_id == head.para_id and blank.style_id == head.style_id


def test_r18_idempotent(tmp_path):
    doc, _ = _run(_r18_doc(tmp_path), tmp_path)
    assert not [c for c in run_rules(doc) if c.rule_id == "R18"]


# ---- R19 ----
def _r19_doc(tmp_path, category="■ 경영서", names=("사아자", "가나다")):
    cover = table([
        [p("소    속"), p("HRA 20기 0조")],
        [p("조    원"), p("경영학과 3학년 가나다") + p("철학과 2학년 라마바") + p("언론홍보학과 1학년 사아자")],
        [p("발 표 자"), p("가나다")],
    ])
    blocks = {
        "사아자": [p("사아자", char=1, para=1), p("사아자의 느낀 점.", para=1)],
        "가나다": [p("가나다", char=1, para=1), p("가나다 첫 문단.", para=1), p(""), p("가나다 둘째 문단.", para=1)],
    }
    reflection = []
    for k, n in enumerate(names):
        reflection += blocks[n] if n in blocks else [p(n, char=1, para=1), p(f"{n} 글.", para=1)]
        reflection.append(p(""))
    body = "".join([
        p(category, char=1),
        p(inner=cover),
        p("Ⅰ. 책 소개", char=1, para=1),
        p("책 본문.", para=1),
        p(inner=table([[p("Ⅳ. 느낀점", char=3)]], fill="2")),
        *reflection,
        p(inner=table([[p("Ⅴ. 부록", char=3)]], fill="2")),
        p("부록 본문.", para=1),
    ])
    return build_hwpx(tmp_path / "r19.hwpx", section=section_xml(body))


def test_r19_reorders_to_cover_and_reports_missing(tmp_path):
    from hra_text.memo import Writer, plan
    from hra_text.rules.r19_name_order import cover_members

    src = _r19_doc(tmp_path)
    assert cover_members(Document.open(src)) == ["가나다", "라마바", "사아자"]
    doc = Document.open(src)
    changes = run_rules(doc)
    lines = [ln for mp in plan(doc, changes) for ln in Writer().lines(mp)]
    out = Document.open(doc.save(tmp_path / "out.hwpx"))
    t = _body_texts(out)
    i = t.index("가나다")
    assert t[i - 1] == "<개체>", "느낀점 칸 바로 아래 첫 이름 (빈 줄 안 넣음)"
    assert t[i:i + 9] == ["가나다", "가나다 첫 문단.", "", "가나다 둘째 문단.", "",
                          "사아자", "사아자의 느낀 점.", "", "<개체>"]
    assert t[-1] == "부록 본문."
    assert "- 느낀 점 순서: 표지 조원 순서로" in lines
    assert "- 확인 필요: 느낀 점에 없는 조원 '라마바'" in lines


def test_r19_not_repeated_on_feedback_input(tmp_path):
    from hra_text.fixer import fix_document

    res = fix_document(_r19_doc(tmp_path), tmp_path / "o")
    again = run_rules(Document.open(res.feedback))
    assert not [c for c in again if c.rule_id == "R19"], "순서는 맞고, 같은 확인 메모는 다시 안 단다"


def test_r19_only_bizbook_and_no_duplicates(tmp_path):
    _, changes = _run(_r19_doc(tmp_path, category="■ 기업실무"), tmp_path)
    assert not [c for c in changes if c.rule_id == "R19"]
    (tmp_path / "d").mkdir()
    _, changes = _run(_r19_doc(tmp_path / "d", names=("사아자", "가나다", "사아자")), tmp_path / "d")
    assert not [c for c in changes if c.key == "name_order"], "같은 이름이 두 번이면 순서를 바꾸지 않는다"
