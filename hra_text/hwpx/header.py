"""header.xml 레지스트리: 스타일·글꼴·글자 모양(charPr)·문단 모양(paraPr).

charPr/paraPr 는 여러 문단이 같은 ID를 공유한다. 값을 바꿀 때는 원본을 고치지 말고
`derive_char` / `derive_para` 로 "원본 + 변경"의 새 조합 ID를 얻어 IDRef만 바꾼다.
같은 조합이 이미 있으면 그 ID를 재사용한다.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Callable

from lxml import etree

from .ns import HWPUNITCHAR, NS, hc, hh

LANGS = ("HANGUL", "LATIN", "HANJA", "JAPANESE", "OTHER", "SYMBOL", "USER")
_FONTREF_ATTR = {lang: lang.lower() for lang in LANGS}
MARGIN_KEYS = ("intent", "left", "right", "prev", "next")


# ---------------------------------------------------------------- 읽기용 값 객체
@dataclass(frozen=True)
class CharShape:
    id: str
    size_pt: float
    bold: bool
    italic: bool
    underline: bool
    strikeout: bool
    text_color: str
    shade_color: str
    fonts: dict  # {"HANGUL": "맑은 고딕", ...}
    ratio: int  # 장평(한글)
    spacing: int  # 자간(한글)
    sup: bool
    sub: bool


@dataclass(frozen=True)
class ParaShape:
    id: str
    align: str  # JUSTIFY/LEFT/RIGHT/CENTER/DISTRIBUTE/DISTRIBUTE_SPACE
    margins_pt: dict  # {"intent":10.0, "left":0, "right":0, "prev":0, "next":0} — None이면 글자 단위
    line_spacing: tuple  # (type, value)
    keep_with_next: bool
    page_break_before: bool
    border_fill: str


# ---------------------------------------------------------------- 단위 변환
def _margin_holders(para_pr: etree._Element) -> list[tuple[etree._Element, int]]:
    """paraPr 안의 (hh:margin 요소, 1pt 당 값) 목록. FORMAT_RULES §0 ※ 참고."""
    holders = []
    for case in para_pr.iterfind("hp:switch/hp:case", NS):
        if case.get(f"{{{NS['hp']}}}required-namespace") == HWPUNITCHAR:
            m = case.find("hh:margin", NS)
            if m is not None:
                holders.append((m, 100))
    for m in para_pr.iterfind("hp:switch/hp:default/hh:margin", NS):
        holders.append((m, 200))
    for m in para_pr.iterfind("hh:margin", NS):
        holders.append((m, 200))
    return holders


def _line_spacings(para_pr: etree._Element) -> list[tuple[etree._Element, int]]:
    out = []
    for case in para_pr.iterfind("hp:switch/hp:case", NS):
        if case.get(f"{{{NS['hp']}}}required-namespace") == HWPUNITCHAR:
            ls = case.find("hh:lineSpacing", NS)
            if ls is not None:
                out.append((ls, 100))
    for ls in para_pr.iterfind("hp:switch/hp:default/hh:lineSpacing", NS):
        out.append((ls, 200))
    for ls in para_pr.iterfind("hh:lineSpacing", NS):
        out.append((ls, 200))
    return out


def _canonical(el: etree._Element) -> bytes:
    """id 속성을 뺀 정규형 (같은 조합 판정용)."""
    c = copy.deepcopy(el)
    c.attrib.pop("id", None)
    return etree.tostring(c, method="c14n")


# ---------------------------------------------------------------- 레지스트리
class Header:
    def __init__(self, root: etree._Element):
        self.root = root
        self._char = {e.get("id"): e for e in root.iterfind(".//hh:charProperties/hh:charPr", NS)}
        self._para = {e.get("id"): e for e in root.iterfind(".//hh:paraProperties/hh:paraPr", NS)}
        self._styles = {e.get("id"): e for e in root.iterfind(".//hh:styles/hh:style", NS)}
        self._border = {e.get("id"): e for e in root.iterfind(".//hh:borderFills/hh:borderFill", NS)}
        self._fonts = {
            ff.get("lang"): ff for ff in root.iterfind(".//hh:fontfaces/hh:fontface", NS)
        }
        self._char_keys = {_canonical(e): i for i, e in self._char.items()}
        self._para_keys = {_canonical(e): i for i, e in self._para.items()}
        self._border_keys = {_canonical(e): i for i, e in self._border.items()}

    # ---- 스타일 ----
    def style_name(self, style_id: str) -> str:
        s = self._styles.get(style_id)
        return s.get("name") if s is not None else f"?{style_id}"

    def style_id(self, name: str) -> str | None:
        for i, s in self._styles.items():
            if s.get("name") == name:
                return i
        return None

    # ---- 글꼴 ----
    def font_face(self, lang: str, font_id: str) -> str:
        ff = self._fonts.get(lang)
        if ff is None:
            return "?"
        f = ff.find(f"hh:font[@id='{font_id}']", NS)
        return f.get("face") if f is not None else "?"

    def font_id(self, lang: str, face: str, *, create: bool = False) -> str | None:
        ff = self._fonts[lang]
        for f in ff.iterfind("hh:font", NS):
            if f.get("face") == face:
                return f.get("id")
        if not create:
            return None
        new_id = str(len(ff.findall("hh:font", NS)))
        etree.SubElement(ff, hh("font"), id=new_id, face=face, type="TTF", isEmbedded="0")
        ff.set("fontCnt", str(len(ff.findall("hh:font", NS))))
        return new_id

    # ---- 글자 모양 ----
    def char_element(self, char_id: str) -> etree._Element:
        return self._char[char_id]

    def char(self, char_id: str) -> CharShape:
        e = self._char[char_id]
        ref = e.find("hh:fontRef", NS)
        fonts = {
            lang: self.font_face(lang, ref.get(attr)) for lang, attr in _FONTREF_ATTR.items()
        } if ref is not None else {}
        ul = e.find("hh:underline", NS)
        so = e.find("hh:strikeout", NS)
        ratio = e.find("hh:ratio", NS)
        spacing = e.find("hh:spacing", NS)
        return CharShape(
            id=char_id,
            size_pt=int(e.get("height", "1000")) / 100,
            bold=e.find("hh:bold", NS) is not None,
            italic=e.find("hh:italic", NS) is not None,
            underline=ul is not None and ul.get("type", "NONE") != "NONE",
            strikeout=so is not None and so.get("shape", "NONE") not in ("NONE", "3D"),
            text_color=e.get("textColor", "#000000").upper(),
            shade_color=e.get("shadeColor", "none").upper(),
            fonts=fonts,
            ratio=int(ratio.get("hangul", "100")) if ratio is not None else 100,
            spacing=int(spacing.get("hangul", "0")) if spacing is not None else 0,
            sup=e.find("hh:supscript", NS) is not None,
            sub=e.find("hh:subscript", NS) is not None,
        )

    def derive_char(self, base_id: str, mutate: Callable[[etree._Element], None]) -> str:
        """base charPr 를 복사해 mutate 를 적용한 조합의 ID (없으면 새로 추가)."""
        return self._derive(self._char, self._char_keys, ".//hh:charProperties", base_id, mutate)

    # ---- 문단 모양 ----
    def para_element(self, para_id: str) -> etree._Element:
        return self._para[para_id]

    def para(self, para_id: str) -> ParaShape:
        e = self._para[para_id]
        align = e.find("hh:align", NS)
        brk = e.find("hh:breakSetting", NS)
        border = e.find("hh:border", NS)
        margins: dict = {}
        holders = _margin_holders(e)
        if holders:
            # 1pt=200 형태(hp:default 또는 일반)를 기준으로 읽는다
            m, per_pt = next((h for h in holders if h[1] == 200), holders[0])
            for key in MARGIN_KEYS:
                v = m.find(f"hc:{key}", NS)
                if v is None:
                    margins[key] = 0.0
                elif v.get("unit") == "CHAR":
                    margins[key] = None
                else:
                    margins[key] = int(v.get("value", "0")) / per_pt
        ls = _line_spacings(e)
        line = (ls[-1][0].get("type"), int(ls[-1][0].get("value"))) if ls else ("PERCENT", 160)
        return ParaShape(
            id=para_id,
            align=align.get("horizontal") if align is not None else "JUSTIFY",
            margins_pt=margins,
            line_spacing=line,
            keep_with_next=brk is not None and brk.get("keepWithNext") == "1",
            page_break_before=brk is not None and brk.get("pageBreakBefore") == "1",
            border_fill=border.get("borderFillIDRef") if border is not None else "",
        )

    def derive_para(self, base_id: str, mutate: Callable[[etree._Element], None]) -> str:
        return self._derive(self._para, self._para_keys, ".//hh:paraProperties", base_id, mutate)

    # ---- 테두리/배경 ----
    def border_fill(self, bf_id: str) -> etree._Element | None:
        return self._border.get(bf_id)

    def fill_color(self, bf_id: str) -> str | None:
        """셀 배경: 단색 "#RRGGBB", 그라데이션 "GRAD:#색1,#색2", 그림 "IMAGE", 없으면 None."""
        bf = self._border.get(bf_id)
        if bf is None:
            return None
        brush = bf.find("hc:fillBrush", NS)
        if brush is None:
            return None
        grad = brush.find("hc:gradation", NS)
        if grad is not None:
            colors = [c.get("value", "").upper() for c in grad.iterfind("hc:color", NS)]
            return "GRAD:" + ",".join(colors)
        if brush.find("hc:imgBrush", NS) is not None:
            return "IMAGE"
        win = brush.find("hc:winBrush", NS)
        if win is None:
            return None
        face = win.get("faceColor", "none")
        return None if face.lower() == "none" else face.upper()

    def border_visible(self, bf_id: str) -> bool:
        """테두리 선이 하나라도 있거나 배경이 있으면 True (문단 테두리/배경 판정용)."""
        bf = self._border.get(bf_id)
        if bf is None:
            return False
        for side in ("leftBorder", "rightBorder", "topBorder", "bottomBorder"):
            b = bf.find(f"hh:{side}", NS)
            if b is not None and b.get("type", "NONE") != "NONE":
                return True
        fill = self.fill_color(bf_id)
        return fill is not None and fill != "#FFFFFF"

    def derive_border_fill(self, base_id: str, mutate: Callable[[etree._Element], None]) -> str:
        return self._derive(self._border, self._border_keys, ".//hh:borderFills", base_id, mutate)

    # ---- 공통 ----
    def _derive(self, table, keys, container_xpath, base_id, mutate) -> str:
        new = copy.deepcopy(table[base_id])
        mutate(new)
        key = _canonical(new)
        if key in keys:
            return keys[key]
        container = self.root.find(container_xpath, NS)
        new_id = str(max(int(i) for i in table) + 1)
        new.set("id", new_id)
        container.append(new)
        container.set("itemCnt", str(len(container)))
        table[new_id] = new
        keys[key] = new_id
        return new_id


# ---------------------------------------------------------------- 변경 도우미 (규칙에서 사용)
def set_margin_pt(para_pr: etree._Element, key: str, pt: float) -> None:
    """모든 margin 형태(hp:case 1pt=100, hp:default/일반 1pt=200)에 같은 pt 를 쓴다."""
    for m, per_pt in _margin_holders(para_pr):
        v = m.find(f"hc:{key}", NS)
        if v is None:
            v = etree.SubElement(m, hc(key))
        v.set("value", str(round(pt * per_pt)))
        v.set("unit", "HWPUNIT")


def set_line_spacing_percent(para_pr: etree._Element, percent: int) -> None:
    for ls, _ in _line_spacings(para_pr):
        ls.set("type", "PERCENT")
        ls.set("value", str(percent))
        ls.set("unit", "HWPUNIT")

