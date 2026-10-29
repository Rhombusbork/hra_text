"""6단계: 메모 삽입 (FORMAT_RULES §3)."""

from datetime import datetime, timezone

from lxml import etree

from hra_text.document import Document
from hra_text.engine import run_rules
from hra_text.hwpx.ns import NS, hp
from hra_text.memo import add_memos
from hra_text.rules.memo_templates import COMMON, MEMO_TEMPLATES

WHEN = datetime(2026, 10, 29, 12, 0, tzinfo=timezone.utc)


def _fixed_with_memos(path, tmp_path):
    doc = Document.open(path)
    texts_before = [p.text for p in doc.paras if p.role != "SKIP"]
    changes = run_rules(doc)
    n = add_memos(doc, changes, when=WHEN)
    out = Document.open(doc.save(tmp_path / "out.hwpx"))
    return out, n, texts_before


def _memos(doc):
    """[(메모가 걸린 문단 글자, [메모 줄...])]"""
    out = []
    for sec in doc.pkg.sections():
        for fb in sec.iter(hp("fieldBegin")):
            if fb.get("type") != "MEMO":
                continue
            para = fb.getparent().getparent().getparent()
            anchor = "".join(t.text or "" for t in para.iterfind("hp:run/hp:t", NS)).strip()
            lines = ["".join(t.text or "" for t in q.iter(hp("t")))
                     for q in fb.find("hp:subList", NS).iterfind("hp:p", NS)]
            out.append((anchor, lines))
    return out


def test_memo_structure_pairs_and_params(sample_hwpx, tmp_path):
    doc, n, _ = _fixed_with_memos(sample_hwpx, tmp_path)
    sec = doc.pkg.sections()[0]
    begins = [fb for fb in sec.iter(hp("fieldBegin")) if fb.get("type") == "MEMO"]
    ends = {e.get("beginIDRef"): e.get("fieldid") for e in sec.iter(hp("fieldEnd"))}
    assert n == len(begins) - 1  # 합성 문서에 원래 메모 1개
    for fb in begins:
        assert ends.get(fb.get("id")) == fb.get("fieldid")
    numbers = [int(num.text) for fb in begins
               if (num := fb.find("hp:parameters/hp:integerParam[@name='Number']", NS)) is not None]
    assert len(numbers) == n
    assert len(set(numbers)) == len(numbers)


def test_text_unchanged_by_memos(sample_hwpx, tmp_path):
    doc, _, before = _fixed_with_memos(sample_hwpx, tmp_path)
    after = [p.text for p in doc.paras if p.role != "SKIP"]
    strip = lambda xs: sorted(x for x in xs if x.strip())  # noqa: E731 (R07 분리로 빈 문단은 늘 수 있음)
    assert strip(before) == strip(after)


def test_first_full_sentence_then_short(sample_hwpx, tmp_path):
    doc, _, _ = _fixed_with_memos(sample_hwpx, tmp_path)
    all_lines = [l for _, lines in _memos(doc) for l in lines]
    full_style = MEMO_TEMPLATES["R01"]["style"].format(old="본문")
    assert full_style in all_lines
    assert all_lines.count(COMMON["help"]) == 1


def test_body_memo_lists_every_fix(sample_hwpx, tmp_path):
    doc, _, _ = _fixed_with_memos(sample_hwpx, tmp_path)
    memo = dict(_memos(doc))["앞에 공백이 있는 본문"]
    joined = "\n".join(memo)
    for word in ("바탕글", "맑은 고딕", "10", "양쪽", "들여쓰기", "왼쪽 여백", "아래 간격", "줄 간격"):
        assert word in joined, word


def test_table_gets_single_memo(sample_hwpx, tmp_path):
    doc, _, _ = _fixed_with_memos(sample_hwpx, tmp_path)
    memos = dict(_memos(doc))
    assert "떠 있는 표" in memos
    assert any("글자처럼 취급" in l for l in memos["떠 있는 표"])
    assert memos["떠 있는 표"][0] == COMMON["table_head"].format(n=1)


def test_existing_memo_kept_and_memo_paras_skipped(sample_hwpx, tmp_path):
    doc, _, _ = _fixed_with_memos(sample_hwpx, tmp_path)
    assert any(lines == ["메모 내용입니다."] for _, lines in _memos(doc))
    assert all(p.role == "SKIP" for p in doc.paras if p.container == "memo")


def test_rerun_adds_nothing(sample_hwpx, tmp_path):
    doc, _, _ = _fixed_with_memos(sample_hwpx, tmp_path)
    changes = run_rules(doc)
    assert changes == []
    assert add_memos(doc, changes) == 0


def test_memo_uses_memo_style_when_present(sample_hwpx, tmp_path):
    # 합성 문서에는 '메모' 스타일이 없으므로 바탕글로 대체된다
    doc, _, _ = _fixed_with_memos(sample_hwpx, tmp_path)
    sec = doc.pkg.sections()[0]
    fb = next(fb for fb in sec.iter(hp("fieldBegin")) if fb.get("type") == "MEMO" and
              fb.find("hp:parameters/hp:stringParam[@name='Author']", NS).text == "neoju")
    sid = fb.find("hp:subList/hp:p", NS).get("styleIDRef")
    assert doc.header.style_name(sid) in ("메모", "바탕글")
