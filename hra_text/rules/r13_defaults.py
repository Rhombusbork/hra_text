"""R13. 규칙에 없는 숨은 서식을 기본값으로 되돌린다.

글자: 기울임·밑줄·취소선·외곽선/그림자/양각/음각·글자 색·글자 음영·장평·자간·위/아래 첨자
문단: 문단 테두리/배경, 다음 문단과 함께
표: 셀 배경(셀 음영)은 건드리지 않는다, 표 안(TABLE_CELL) 글자 색도 받은 대로 [U] 2026-11-03
예외(템플릿 디자인): 1단위 타이틀 칸 흰 글씨, 표지 정보 표 회색 글씨, 하이퍼링크 글자(색·밑줄).
"""

from ..hwpx.edit import border_clean, change_para, change_run, link_runs
from ..hwpx.ns import NS
from . import register
from .base import Rule

KEEP_COLOR = {"H1": {"#FFFFFF"}, "COVER_TABLE": {"#E5E5E5"}}
KEEP_ANY_COLOR = {"TABLE_CELL"}  # 표 안 글자 색은 받은 대로 [U] 2026-11-03


def _char_fixes(el, *, keep_color: set, is_link: bool, keep_any_color: bool = False) -> list[tuple[str, callable]]:
    """(항목 이름, mutate) 목록 — 기본값과 다른 것만."""
    fixes = []
    if el.find("hh:italic", NS) is not None:
        fixes.append(("기울임", lambda e: e.remove(e.find("hh:italic", NS))))
    ul = el.find("hh:underline", NS)
    if ul is not None and ul.get("type", "NONE") != "NONE" and not is_link:
        fixes.append(("밑줄", lambda e: e.find("hh:underline", NS).set("type", "NONE")))
    so = el.find("hh:strikeout", NS)
    if so is not None and so.get("shape", "NONE") not in ("NONE", "3D"):
        fixes.append(("취소선", lambda e: e.find("hh:strikeout", NS).set("shape", "NONE")))
    for tag, name in (("outline", "외곽선"), ("shadow", "그림자")):
        x = el.find(f"hh:{tag}", NS)
        if x is not None and x.get("type", "NONE") != "NONE":
            fixes.append((name, lambda e, tag=tag: e.find(f"hh:{tag}", NS).set("type", "NONE")))
    for tag, name in (("emboss", "양각"), ("engrave", "음각"), ("supscript", "위 첨자"), ("subscript", "아래 첨자")):
        if el.find(f"hh:{tag}", NS) is not None:
            fixes.append((name, lambda e, tag=tag: e.remove(e.find(f"hh:{tag}", NS))))
    color = el.get("textColor", "#000000").upper()
    if color != "#000000" and color not in keep_color and not is_link and not keep_any_color:
        fixes.append(("글자 색", lambda e: e.set("textColor", "#000000")))
    shade = el.get("shadeColor", "none").upper()
    if shade not in ("NONE", "#FFFFFF"):
        fixes.append(("글자 음영", lambda e: e.set("shadeColor", "none")))
    ratio = el.find("hh:ratio", NS)
    if ratio is not None and any(v != "100" for v in ratio.attrib.values()):
        fixes.append(("장평", lambda e: [e.find("hh:ratio", NS).set(k, "100") for k in e.find("hh:ratio", NS).attrib]))
    spacing = el.find("hh:spacing", NS)
    if spacing is not None and any(v != "0" for v in spacing.attrib.values()):
        fixes.append(("자간", lambda e: [e.find("hh:spacing", NS).set(k, "0") for k in e.find("hh:spacing", NS).attrib]))
    return fixes


@register
class R13Defaults(Rule):
    RULE_ID = "R13"
    NAME = "숨은 서식 기본값"

    def apply(self, doc):
        h = doc.header
        changes = []
        for p in self.formatted(doc):
            links = link_runs(p.el)
            keep = KEEP_COLOR.get(p.role, set())
            keep_any_color = p.role in KEEP_ANY_COLOR
            for r in self.text_runs(p):
                for name, mutate in _char_fixes(h.char_element(r.char_id), keep_color=keep,
                                                is_link=r.el in links, keep_any_color=keep_any_color):
                    if change_run(doc, p, r, mutate):
                        changes.append(self.change(p, "default", name, "기본값", run=r, item=name))
            # 문단 테두리/배경, 다음 문단과 함께
            ps = h.para(p.para_id)
            if ps.border_fill and h.border_visible(ps.border_fill):
                clean = h.derive_border_fill(ps.border_fill, border_clean)
                if change_para(doc, p, lambda e, clean=clean: e.find("hh:border", NS).set("borderFillIDRef", clean)):
                    changes.append(self.change(p, "default", "문단 테두리·배경", "기본값", item="문단 테두리·배경"))
            if ps.keep_with_next and change_para(doc, p, lambda e: e.find("hh:breakSetting", NS).set("keepWithNext", "0")):
                changes.append(self.change(p, "default", "다음 문단과 함께", "기본값", item="다음 문단과 함께"))
        return changes
