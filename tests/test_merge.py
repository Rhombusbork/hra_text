"""9단계: 합본 제작 (hra-merge)."""

import pytest

from hra_text.hwpx.ns import NS, hp
from hra_text.hwpx.package import HwpxPackage
from hra_text.merge.cli import main as merge_main
from hra_text.merge.schedule import para_text
from hra_text.merge.verify import check, memo_count

from conftest import build_reference_hapbon, local_samples


def _texts(pkg, section=-1):
    sec = pkg.xml(pkg.section_names()[section])
    return [para_text(p).strip() for p in sec.iterfind("hp:p", NS)]


def _merge(tmp_path, *docs, date=None):
    ref = build_reference_hapbon(tmp_path / "ref.hwpx")
    out = tmp_path / "합본.hwpx"
    args = [str(d) for d in docs] + ["--cover", str(ref), "-o", str(out)]
    if date:
        args += ["--date", date]
    assert merge_main(args) == 0
    return HwpxPackage.open(out)


def test_merge_basic(sample_hwpx, tmp_path):
    pkg = _merge(tmp_path, sample_hwpx, date="2026.11.07.(토)")
    assert check(pkg) == []
    assert memo_count(pkg) == 0, "합본에는 메모를 넣지 않는다"
    cover = _texts(pkg, 0)
    assert "2026.11.07.(토)" in cover and "2026.10.24.(토)" not in cover
    body = _texts(pkg)
    assert "옛 문서 본문" not in body, "참고 합본의 옛 문서는 빠진다"
    assert "■ 고전 명작 (9:00~12:00)" not in body, "고전 문서가 없으면 고전 세션은 지운다"
    assert "■ 특강 (13:00~14:00)" in body and "옛 특강 제목" not in body, "특강은 두고 내용만 비운다"
    assert "가짜 제목" in body and "1. 둘째 단위" in body


def test_schedule_fills_title_and_clears_presenter(sample_hwpx, tmp_path):
    pkg = _merge(tmp_path, sample_hwpx)
    sec = pkg.xml(pkg.section_names()[-1])
    tables = [t for t in sec.iter(hp("tbl"))
              if any(para_text(q).strip() == "도서명 (저자)" for q in t.iter(hp("p")))]
    rows = [[para_text(tc).strip() for tc in tr.iterfind("hp:tc", NS)] for tr in tables[0].iterfind("hp:tr", NS)]
    assert rows == [["도서명 (저자)", "발표자"], ["가짜 제목", ""]]


def test_document_starts_on_new_page(sample_hwpx, tmp_path):
    pkg = _merge(tmp_path, sample_hwpx, sample_hwpx)
    sec = pkg.xml(pkg.section_names()[-1])
    starts = [para_text(p).strip() for p in sec.iterfind("hp:p", NS) if p.get("pageBreak") == "1"]
    assert len(starts) == 2


def test_images_pruned_and_ids_unique(sample_hwpx, tmp_path):
    pkg = _merge(tmp_path, sample_hwpx, sample_hwpx)
    names = [n for n in pkg.names() if n.startswith("BinData/")]
    assert names == ["BinData/image1.png"], "옛 문서 그림은 지우고 표지 그림은 둔다"
    assert check(pkg) == []  # 같은 문서를 두 번 넣어도 개체·필드 ID 가 겹치지 않는다


def test_header_reuses_identical_shapes(sample_hwpx, tmp_path):
    once = _merge(tmp_path, sample_hwpx)
    twice = _merge(tmp_path, sample_hwpx, sample_hwpx)
    count = lambda pkg: len(pkg.header.findall(".//hh:charProperties/hh:charPr", NS))  # noqa: E731
    assert count(once) == count(twice), "같은 글자 모양은 다시 추가하지 않는다"


def test_filled_cover_kept_as_is(sample_hwpx, tmp_path):
    """표지·일정표만 있는 파일(이미 채운 표지)은 일정표·날짜를 그대로 두고 문서만 붙인다."""
    ref = build_reference_hapbon(tmp_path / "표지.hwpx", old_doc=False)
    out = tmp_path / "합본.hwpx"
    assert merge_main([str(sample_hwpx), "--cover", str(ref), "-o", str(out)]) == 0
    pkg = HwpxPackage.open(out)
    assert check(pkg) == []
    assert "2026.10.24.(토)" in _texts(pkg, 0)
    body = _texts(pkg)
    for kept in ("■ 고전 명작 (9:00~12:00)", "옛 책읽고 발표홍길동", "옛 특강 제목", "옛 경영서김철수"):
        assert kept in "\n".join(body), kept
    assert "가짜 제목" in body
    starts = [p for p in pkg.xml(pkg.section_names()[-1]).iterfind("hp:p", NS) if p.get("pageBreak") == "1"]
    assert len(starts) == 1

    out2 = tmp_path / "합본2.hwpx"
    assert merge_main([str(sample_hwpx), "--cover", str(ref), "-o", str(out2), "--date", "2026.11.21.(토)"]) == 0
    assert "2026.11.21.(토)" in _texts(HwpxPackage.open(out2), 0), "--date 를 주면 날짜만 바꾼다"


def test_order_file(sample_hwpx, tmp_path):
    ref = build_reference_hapbon(tmp_path / "ref.hwpx")
    order = tmp_path / "합본순서.txt"
    order.write_text(f"# 순서\n{sample_hwpx}\n\n", encoding="utf-8")
    assert merge_main(["--order", str(order), "--cover", str(ref), "-o", str(tmp_path / "o.hwpx")]) == 0


# ---- 로컬 실제 샘플 ----
REFERENCE = local_samples("텍스트*.hwpx")
FIXED = local_samples("output/*_피드백.hwpx")


@pytest.mark.skipif(not (REFERENCE and FIXED), reason="로컬 샘플 없음")
def test_real_merge(tmp_path):
    out = tmp_path / "합본.hwpx"
    assert merge_main([str(f) for f in FIXED] + ["--cover", str(REFERENCE[0]), "-o", str(out)]) == 0
    pkg = HwpxPackage.open(out)
    assert check(pkg) == []
    assert memo_count(pkg) == 0
    pkg.header, pkg.sections()
    pkg.save(tmp_path / "again.hwpx")  # 다시 열고 저장 가능


# ---- 이미 만든 합본에 끼워 넣기 [U] 2026-11-20 ----
def _late_doc(tmp_path, name, title):
    from conftest import build_hwpx, p, section_xml
    body = p("■ 경영서", char=1) + p(title, char=1) + p("Ⅰ. 책 소개", char=1, para=1) + p("늦은 본문.", para=1)
    return build_hwpx(tmp_path / name, section=section_xml(body))


def test_insert_into_existing_hapbon(sample_hwpx, tmp_path, capsys):
    from hra_text.merge.insert import list_documents

    first = _merge(tmp_path, sample_hwpx, sample_hwpx, date="2026.11.21.(토)")
    hapbon = tmp_path / "합본.hwpx"
    assert [e.title for e in list_documents(first)] == ["가짜 제목", "가짜 제목"], "일정표 ■ 세션 줄은 문서가 아니다"
    late = _late_doc(tmp_path, "hra20_가나다-경영서(늦은 책).hwpx", "늦은 책")
    assert merge_main([str(late), "--insert", str(hapbon), "--at", "2"]) == 0
    out = tmp_path / "합본_추가.hwpx"
    pkg = HwpxPackage.open(out)
    assert check(pkg) == [] and memo_count(pkg) == 0
    assert [e.title for e in list_documents(pkg)] == ["가짜 제목", "늦은 책", "가짜 제목"]
    assert _texts(pkg)[:3] == _texts(first)[:3], "일정표는 그대로"
    assert "2026.11.21.(토)" in _texts(pkg, 0)
    assert HwpxPackage.open(hapbon).raw("Contents/section1.xml") == first.raw("Contents/section1.xml"), "받은 합본은 그대로"

    assert merge_main([str(late), "--insert", str(out), "-o", str(tmp_path / "끝.hwpx")]) == 0
    assert [e.title for e in list_documents(HwpxPackage.open(tmp_path / "끝.hwpx"))][-1] == "늦은 책", "--at 없으면 맨 뒤"

    capsys.readouterr()
    assert merge_main(["--list", str(out)]) == 0
    assert " 2. ■ 경영서  늦은 책" in capsys.readouterr().out


def test_insert_rejects_bad_position_and_overwrite(sample_hwpx, tmp_path):
    _merge(tmp_path, sample_hwpx)
    hapbon = tmp_path / "합본.hwpx"
    for extra in (["--at", "3"], ["-o", str(hapbon)], ["--cover", str(hapbon)]):
        with pytest.raises(SystemExit):
            merge_main([str(sample_hwpx), "--insert", str(hapbon), *extra])
