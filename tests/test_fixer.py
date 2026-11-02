"""결과 두 개: _피드백(메모) + _수정본(메모 없음, 최종본). 같은 수정이고 메모만 다르다."""

from lxml import etree

from hra_text.compare import snapshot
from hra_text.document import Document
from hra_text.fixer import fix_document
from hra_text.hwpx.memo import strip_memos
from hra_text.hwpx.ns import hp


def _memo_count(path):
    doc = Document.open(path)
    return sum(1 for sec in doc.pkg.sections() for fb in sec.iter(hp("fieldBegin")) if fb.get("type") == "MEMO")


def _content(path):
    doc = Document.open(path)
    return [(p.text, tuple(sorted(snapshot(doc, p).items()))) for p in doc.paras if p.role != "SKIP"]


def test_two_outputs_same_fixes_memo_only_differs(sample_hwpx, tmp_path):
    r = fix_document(sample_hwpx, tmp_path / "결과")
    assert r.feedback.name == "sample_피드백.hwpx" and r.clean.name == "sample_수정본.hwpx"
    assert r.report.name == "sample_변경내역.txt" and r.report.is_file()
    assert r.memos > 0 and _memo_count(r.feedback) > 0
    assert _memo_count(r.clean) == 0, "수정본에는 메모가 하나도 없어야 한다 (원래 있던 메모 포함)"
    assert _content(r.feedback) == _content(r.clean), "글자·서식은 두 파일이 같아야 한다"


def test_clean_file_needs_no_further_fixing(sample_hwpx, tmp_path):
    """수정본을 다시 넣어도 실제로 고칠 것은 없다 (목차 대조 같은 '알림'만 다시 나올 수 있음)."""
    from hra_text.engine import run_rules

    r = fix_document(sample_hwpx, tmp_path / "1")
    changes = run_rules(Document.open(r.clean))
    assert [c for c in changes if not c.extra.get("check")] == []


def test_no_memo_option_makes_only_clean(sample_hwpx, tmp_path):
    r = fix_document(sample_hwpx, tmp_path, memo=False)
    assert r.feedback is None and r.clean.is_file()
    assert not list(tmp_path.glob("*_피드백.hwpx"))


def test_unique_names_do_not_overwrite(sample_hwpx, tmp_path):
    first = fix_document(sample_hwpx, tmp_path, unique=True)
    second = fix_document(sample_hwpx, tmp_path, unique=True)
    assert second.clean != first.clean and second.feedback != first.feedback
    assert first.clean.is_file() and second.clean.is_file()


def test_strip_memos_reports_paragraphs():
    root = etree.fromstring(
        '<s xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph"><hp:p><hp:run>'
        '<hp:ctrl><hp:fieldBegin id="1" type="MEMO"/></hp:ctrl><hp:t>글자</hp:t>'
        '<hp:ctrl><hp:fieldEnd beginIDRef="1"/></hp:ctrl></hp:run></hp:p></s>')
    n, paras = strip_memos(root)
    assert n == 1 and len(paras) == 1
    assert etree.tostring(root).count(b"ctrl") == 0
    assert root.findtext(".//{http://www.hancom.co.kr/hwpml/2011/paragraph}t") == "글자"
