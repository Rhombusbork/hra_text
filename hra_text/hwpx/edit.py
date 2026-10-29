"""XML 수정 도우미. 규칙은 이 함수들로만 글자/문단 모양을 바꾼다.

글자/문단 모양은 공유 객체이므로 직접 고치지 않고 Header.derive_* 로 새 조합 ID를 받아
IDRef 만 바꾼다. 바뀐 문단은 doc.touched 에 기록해 두었다가 저장 직전에 레이아웃 캐시
(hp:linesegarray)를 지운다 — 한글이 열면서 다시 계산한다.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from lxml import etree

from .header import LANGS, set_line_spacing_percent, set_margin_pt  # noqa: F401 (재노출)
from .ns import NS, hh, hp

if TYPE_CHECKING:
    from ..document import Document
    from .section import Para, Run

_FONTREF_ATTR = {lang: lang.lower() for lang in LANGS}
# charPr 자식 순서 (OWPML 스키마) — bold 를 넣을 자리 찾기용
_CHAR_ORDER = ("fontRef", "ratio", "spacing", "relSz", "offset", "italic", "bold", "underline",
               "strikeout", "outline", "shadow", "emboss", "engrave", "supscript", "subscript")


def touch(doc: "Document", para_el: etree._Element) -> None:
    doc.touched.add(para_el)


def change_para(doc: "Document", para: "Para", mutate: Callable[[etree._Element], None]) -> bool:
    """문단 모양을 mutate 로 바꾼 조합으로 교체. 실제로 바뀌었으면 True."""
    old = para.el.get("paraPrIDRef")
    new = doc.header.derive_para(old, mutate)
    if new == old:
        return False
    para.el.set("paraPrIDRef", new)
    touch(doc, para.el)
    return True


def change_run(doc: "Document", para: "Para", run: "Run", mutate: Callable[[etree._Element], None]) -> bool:
    old = run.el.get("charPrIDRef")
    new = doc.header.derive_char(old, mutate)
    if new == old:
        return False
    run.el.set("charPrIDRef", new)
    run.char_id = new
    touch(doc, para.el)
    return True


# ---- charPr 변경 함수 (derive_char 의 mutate 로 사용) ----
def char_height(pt: float) -> Callable[[etree._Element], None]:
    def mutate(el):
        el.set("height", str(round(pt * 100)))
    return mutate


def char_bold(on: bool) -> Callable[[etree._Element], None]:
    def mutate(el):
        existing = el.find("hh:bold", NS)
        if on and existing is None:
            _insert_in_order(el, etree.Element(hh("bold")))
        elif not on and existing is not None:
            el.remove(existing)
    return mutate


def char_fonts(font_ids: dict[str, str]) -> Callable[[etree._Element], None]:
    """font_ids: {"HANGUL": "0", ...} — fontRef 의 언어별 글꼴 ID."""
    def mutate(el):
        ref = el.find("hh:fontRef", NS)
        if ref is None:
            ref = etree.Element(hh("fontRef"))
            el.insert(0, ref)
        for lang, fid in font_ids.items():
            ref.set(_FONTREF_ATTR[lang], fid)
    return mutate


def _insert_in_order(parent: etree._Element, child: etree._Element) -> None:
    name = etree.QName(child).localname
    rank = _CHAR_ORDER.index(name)
    for i, existing in enumerate(parent):
        other = etree.QName(existing).localname
        if other in _CHAR_ORDER and _CHAR_ORDER.index(other) > rank:
            parent.insert(i, child)
            return
    parent.append(child)


# ---- paraPr 변경 함수 ----
def para_align(align: str) -> Callable[[etree._Element], None]:
    def mutate(el):
        a = el.find("hh:align", NS)
        if a is None:
            a = etree.SubElement(el, hh("align"), vertical="BASELINE")
        a.set("horizontal", align)
    return mutate


def para_margins(**pts: float) -> Callable[[etree._Element], None]:
    """para_margins(intent=10, left=0) — hp:case/hp:default 모두에 같은 pt."""
    def mutate(el):
        for key, pt in pts.items():
            set_margin_pt(el, key, pt)
    return mutate


def para_line_spacing(percent: int) -> Callable[[etree._Element], None]:
    def mutate(el):
        set_line_spacing_percent(el, percent)
    return mutate


def drop_layout_cache(doc: "Document") -> None:
    """바뀐 문단의 lineseg 캐시 삭제 (저장 직전)."""
    for p in doc.touched:
        for arr in p.findall("hp:linesegarray", NS):
            p.remove(arr)


# ---- 테두리/배경 (borderFill) 변경 함수 ----
def border_no_fill(el) -> None:
    """배경(fillBrush)만 지운다. 테두리 선은 그대로."""
    for brush in el.findall("hc:fillBrush", NS):
        el.remove(brush)


def border_clean(el) -> None:
    """테두리 선도 배경도 없게 (문단 테두리/배경 제거용)."""
    border_no_fill(el)
    for side in ("leftBorder", "rightBorder", "topBorder", "bottomBorder"):
        b = el.find(f"hh:{side}", NS)
        if b is not None:
            b.set("type", "NONE")


def link_runs(para_el) -> set:
    """하이퍼링크(fieldBegin type=HYPERLINK ~ fieldEnd) 안에 있는 글자 런."""
    open_ids: set[str] = set()
    links = set()
    for run in para_el.iterfind("hp:run", NS):
        for child in run:
            if child.tag == hp("ctrl"):
                for f in child:
                    if f.tag == hp("fieldBegin") and f.get("type") == "HYPERLINK":
                        open_ids.add(f.get("id"))
                    elif f.tag == hp("fieldEnd"):
                        open_ids.discard(f.get("beginIDRef"))
            elif child.tag == hp("t") and open_ids:
                links.add(run)
    return links
