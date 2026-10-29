"""테스트용 합성 hwpx (실제 보고서 없이, 개인정보 없이 만든 최소 문서)."""

from __future__ import annotations

import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

import pytest

ROOT = Path(__file__).resolve().parent.parent
NS_DECL = (
    'xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph" '
    'xmlns:hh="http://www.hancom.co.kr/hwpml/2011/head" '
    'xmlns:hc="http://www.hancom.co.kr/hwpml/2011/core" '
    'xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section"'
)
DECL = '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>'


def _char(cid, height, color="#000000", bold=False, font="0"):
    return (
        f'<hh:charPr id="{cid}" height="{height}" textColor="{color}" shadeColor="none" '
        f'useFontSpace="0" useKerning="0" symMark="NONE" borderFillIDRef="1">'
        f'<hh:fontRef hangul="{font}" latin="{font}" hanja="{font}" japanese="{font}" '
        f'other="{font}" symbol="{font}" user="{font}"/>'
        '<hh:ratio hangul="100" latin="100" hanja="100" japanese="100" other="100" symbol="100" user="100"/>'
        '<hh:spacing hangul="0" latin="0" hanja="0" japanese="0" other="0" symbol="0" user="0"/>'
        + ("<hh:bold/>" if bold else "")
        + '<hh:underline type="NONE" shape="SOLID" color="#000000"/></hh:charPr>'
    )


def _margin(intent, left, prev, nxt, per_pt):
    v = lambda pt: round(pt * per_pt)  # noqa: E731
    return (
        f'<hh:margin><hc:intent value="{v(intent)}" unit="HWPUNIT"/><hc:left value="{v(left)}" unit="HWPUNIT"/>'
        f'<hc:right value="0" unit="HWPUNIT"/><hc:prev value="{v(prev)}" unit="HWPUNIT"/>'
        f'<hc:next value="{v(nxt)}" unit="HWPUNIT"/></hh:margin>'
    )


def _para(pid, align="JUSTIFY", intent=0.0, left=0.0, prev=0.0, nxt=0.0, line=160):
    ls = f'<hh:lineSpacing type="PERCENT" value="{line}" unit="HWPUNIT"/>'
    return (
        f'<hh:paraPr id="{pid}" tabPrIDRef="0" condense="0"><hh:align horizontal="{align}" vertical="BASELINE"/>'
        '<hh:breakSetting breakLatinWord="KEEP_WORD" breakNonLatinWord="KEEP_WORD" widowOrphan="0" '
        'keepWithNext="0" keepLines="0" pageBreakBefore="0" lineWrap="BREAK"/>'
        '<hp:switch><hp:case hp:required-namespace="http://www.hancom.co.kr/hwpml/2016/HwpUnitChar">'
        + _margin(intent, left, prev, nxt, 100) + ls
        + "</hp:case><hp:default>" + _margin(intent, left, prev, nxt, 200) + ls
        + '</hp:default></hp:switch><hh:border borderFillIDRef="1"/></hh:paraPr>'
    )


HEADER = (
    DECL + f"<hh:head {NS_DECL} version=\"1.4\" secCnt=\"1\"><hh:refList>"
    '<hh:fontfaces itemCnt="2">'
    '<hh:fontface lang="HANGUL" fontCnt="2"><hh:font id="0" face="맑은 고딕" type="TTF" isEmbedded="0"/>'
    '<hh:font id="1" face="굴림" type="TTF" isEmbedded="0"/></hh:fontface>'
    + "".join(
        f'<hh:fontface lang="{lang}" fontCnt="2"><hh:font id="0" face="맑은 고딕" type="TTF" isEmbedded="0"/>'
        f'<hh:font id="1" face="Calibri" type="TTF" isEmbedded="0"/></hh:fontface>'
        for lang in ("LATIN", "HANJA", "JAPANESE", "OTHER", "SYMBOL", "USER")
    )
    + "</hh:fontfaces>"
    '<hh:borderFills itemCnt="3">'
    '<hh:borderFill id="1" threeD="0" shadow="0"/>'
    '<hh:borderFill id="2" threeD="0" shadow="0"><hc:fillBrush><hc:gradation type="RADIAL" angle="90" '
    'centerX="0" centerY="0" step="255" colorNum="2" stepCenter="50" alpha="0"><hc:color value="#000000"/>'
    '<hc:color value="#FFFFFF"/></hc:gradation></hc:fillBrush></hh:borderFill>'
    '<hh:borderFill id="3" threeD="0" shadow="0"><hc:fillBrush><hc:winBrush faceColor="#DCDCDC" '
    'hatchColor="#000000" alpha="0"/></hc:fillBrush></hh:borderFill>'
    "</hh:borderFills>"
    '<hh:charProperties itemCnt="7">'
    + _char(0, 1000)
    + _char(1, 1200, bold=True)
    + _char(2, 3200, bold=True)
    + _char(3, 1200, color="#FFFFFF", bold=True)
    + _char(4, 1000, color="#FF0000")
    + _char(5, 800)
    + _char(6, 1050, font="1")
    + "</hh:charProperties>"
    '<hh:paraProperties itemCnt="4">'
    + _para(0)
    + _para(1, intent=10)
    + _para(2, align="CENTER")
    + _para(3, align="LEFT", intent=5, left=15, nxt=4, line=110)
    + "</hh:paraProperties>"
    '<hh:styles itemCnt="2">'
    '<hh:style id="0" type="PARA" name="바탕글" engName="Normal" paraPrIDRef="0" charPrIDRef="0" '
    'nextStyleIDRef="0" langID="1042" lockForm="0"/>'
    '<hh:style id="1" type="PARA" name="본문" engName="Body" paraPrIDRef="3" charPrIDRef="0" '
    'nextStyleIDRef="1" langID="1042" lockForm="0"/>'
    "</hh:styles></hh:refList></hh:head>"
)


def p(text="", char=0, para=0, style=0, inner="", after=""):
    body = escape(text).replace("\t", '<hp:tab width="1000" leader="0" type="1"/>')
    t = f"<hp:t>{body}</hp:t>" if text else ""
    return (
        f'<hp:p id="0" paraPrIDRef="{para}" styleIDRef="{style}" pageBreak="0" columnBreak="0" merged="0">'
        f'<hp:run charPrIDRef="{char}">{inner}{t}{after}</hp:run></hp:p>'
    )


def table(rows, *, treat_as_char=True, fill="1", col_span_first=1, vert_offset=0):
    """rows: [[cell_paragraphs_xml, ...], ...]"""
    n_rows, n_cols = len(rows), max(len(r) for r in rows)
    trs = []
    for ri, row in enumerate(rows):
        tcs = []
        for ci, cell in enumerate(row):
            span = col_span_first if (ri == 0 and ci == 0) else 1
            tcs.append(
                f'<hp:tc name="" header="0" hasMargin="0" protect="0" editable="0" dirty="0" '
                f'borderFillIDRef="{fill}"><hp:subList id="" textDirection="HORIZONTAL" lineWrap="BREAK" '
                f'vertAlign="CENTER">{cell}</hp:subList><hp:cellAddr colAddr="{ci}" rowAddr="{ri}"/>'
                f'<hp:cellSpan colSpan="{span}" rowSpan="1"/><hp:cellSz width="1000" height="1000"/></hp:tc>'
            )
        trs.append("<hp:tr>" + "".join(tcs) + "</hp:tr>")
    return (
        f'<hp:tbl id="1" rowCnt="{n_rows}" colCnt="{n_cols}" borderFillIDRef="1">'
        f'<hp:sz width="1000" height="1000"/><hp:pos treatAsChar="{int(treat_as_char)}" '
        f'vertRelTo="PARA" horzRelTo="PARA" vertOffset="{vert_offset}" horzOffset="0"/>'
        + "".join(trs) + "</hp:tbl>"
    )


MEMO = (
    '<hp:ctrl><hp:fieldBegin id="9" type="MEMO" name="" editable="1" dirty="1" fieldid="9">'
    '<hp:subList id="">' + p("메모 내용입니다.") + "</hp:subList></hp:fieldBegin></hp:ctrl>"
)
MEMO_END = '<hp:ctrl><hp:fieldEnd beginIDRef="9" fieldid="9"/></hp:ctrl>'

SECTION_BODY = "".join([
    p("■ 경영서", char=1),
    p(""),
    p("가짜 제목", char=2, para=2),
    p(para=2, inner=table([[p("목차", para=2)], [p("Ⅰ. 첫 장", char=1, para=2)]])),
    p(para=2, inner=table([[p("소    속", para=2), p("HRA 20기 0조", para=2)],
                          [p("발 표 자", para=2), p("홍길동", para=2)]])),
    # 떠 있는 표가 1단위 타이틀 칸 앞에 앵커됨 (경영서 샘플과 같은 구조)
    p(inner=table([[p("떠 있는 표", para=3)]], treat_as_char=False, vert_offset=3000)
      + table([[p("Ⅰ. 첫 장", char=3)]], fill="2")),
    p("1. 둘째 단위", char=1, para=1),
    p("1) 셋째 단위", char=1, para=1),
    p("① 넷째 단위", para=1),
    p("본문입니다\t탭 뒤 글자", para=1, inner=MEMO, after=MEMO_END),
    p("  앞에 공백이 있는 본문", char=6, para=3, style=1),
    p("본문내용(맑은 고딕, 10, 들여쓰기 10)", char=4, para=1),
    p("출처 : 가짜 출처", char=5, para=2),
    p("<1장 작성자: 홍길동>", char=5, para=2),
    p(para=0, inner=table([[p("배경", para=0), p("목적", para=0)]], treat_as_char=False)),
    p(inner=table([[p("Ⅱ. 느낀 점", char=3)]], fill="2")),
    p("홍길동", char=1, para=1),
    p("느낀 점 본문입니다.", para=1),
])

SECTION = DECL + f"<hs:sec {NS_DECL}>{SECTION_BODY}</hs:sec>"


def build_hwpx(path: Path, header: str = HEADER, section: str = SECTION) -> Path:
    with zipfile.ZipFile(path, "w") as z:
        z.writestr(zipfile.ZipInfo("mimetype"), "application/hwp+zip", compress_type=zipfile.ZIP_STORED)
        z.writestr("version.xml", DECL + "<hv:HCFVersion xmlns:hv=\"http://www.hancom.co.kr/hwpml/2011/version\"/>",
                   compress_type=zipfile.ZIP_DEFLATED)
        z.writestr("Contents/header.xml", header, compress_type=zipfile.ZIP_DEFLATED)
        z.writestr("Contents/section0.xml", section, compress_type=zipfile.ZIP_DEFLATED)
    return path


@pytest.fixture
def sample_hwpx(tmp_path) -> Path:
    return build_hwpx(tmp_path / "sample.hwpx")


def local_samples(pattern: str) -> list[Path]:
    """저장소에 커밋하지 않는 실제 샘플 (있을 때만 테스트)."""
    return sorted(ROOT.glob(pattern))
