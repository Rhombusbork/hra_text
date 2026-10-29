"""본문 순회: 문단(본문/표 셀) 목록과 문단별 텍스트·런 정보.

- 메모 내용(fieldBegin[MEMO]/subList), 머리말/꼬리말, 각주/미주, 글상자 안 문단은
  `container` 로 구분해서 돌려준다. 서식 규칙은 기본적으로 body/cell 만 다룬다.
- 텍스트는 `hp:t` 의 text + 안쪽 요소(hp:tab, hp:lineBreak …)의 tail 까지 읽는다.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from lxml import etree

from .ns import NS, hp

_INLINE_CHARS = {hp("tab"): "\t", hp("lineBreak"): "\n", hp("nbSpace"): " ", hp("fwSpace"): " "}
_SKIP_CONTAINERS = {
    hp("fieldBegin"): "memo",  # 메모 등 필드 안 subList
    hp("header"): "header_footer",
    hp("footer"): "header_footer",
    hp("footNote"): "note",
    hp("endNote"): "note",
    hp("drawText"): "textbox",
}


def t_text(t: etree._Element) -> str:
    parts = [t.text or ""]
    for child in t:
        parts.append(_INLINE_CHARS.get(child.tag, ""))
        parts.append(child.tail or "")
    return "".join(parts)


@dataclass
class Run:
    el: etree._Element
    char_id: str
    text: str


@dataclass
class CellInfo:
    tbl: etree._Element
    tc: etree._Element
    row: int
    col: int
    border_fill_id: str


@dataclass
class Para:
    el: etree._Element
    index: int  # 문서 전체 순번
    section: int
    path: str  # 예: s0/p12, s0/p20/t0/r1c0/p0
    container: str  # body | cell | memo | header_footer | note | textbox
    cell: CellInfo | None
    depth: int  # 표 중첩 깊이
    top_cell: CellInfo | None = None  # 가장 바깥 표의 셀 (표 안 문단일 때)
    runs: list[Run] = field(default_factory=list)
    tables: list[etree._Element] = field(default_factory=list)  # 이 문단 직속 표
    pictures: list[etree._Element] = field(default_factory=list)  # 이 문단 직속 그림
    role: str = ""  # classify 가 채움

    @property
    def text(self) -> str:
        return "".join(r.text for r in self.runs)

    @property
    def style_id(self) -> str:
        return self.el.get("styleIDRef")

    @property
    def para_id(self) -> str:
        return self.el.get("paraPrIDRef")

    @property
    def is_empty(self) -> bool:
        return not self.text.strip() and not self.tables and not self.pictures


def _runs(p: etree._Element) -> tuple[list[Run], list, list]:
    runs, tables, pics = [], [], []
    for r in p.iterfind("hp:run", NS):
        text = "".join(t_text(t) for t in r.iterfind("hp:t", NS))
        runs.append(Run(el=r, char_id=r.get("charPrIDRef"), text=text))
        tables += r.findall("hp:tbl", NS)
        pics += r.findall("hp:pic", NS)
    return runs, tables, pics


def iter_paragraphs(sections: list[etree._Element]) -> list[Para]:
    out: list[Para] = []

    def walk_sublist(container_el, prefix, section, container, cell, top_cell, depth):
        for i, p in enumerate(container_el.iterfind("hp:p", NS)):
            visit(p, f"{prefix}/p{i}", section, container, cell, top_cell, depth)

    def visit(p, path, section, container, cell, top_cell, depth):
        runs, tables, pics = _runs(p)
        out.append(Para(el=p, index=len(out), section=section, path=path, container=container,
                        cell=cell, depth=depth, top_cell=top_cell,
                        runs=runs, tables=tables, pictures=pics))
        # 표 셀
        for ti, tbl in enumerate(tables):
            for tc in tbl.iterfind("hp:tr/hp:tc", NS):
                addr = tc.find("hp:cellAddr", NS)
                row, col = int(addr.get("rowAddr")), int(addr.get("colAddr"))
                info = CellInfo(tbl=tbl, tc=tc, row=row, col=col,
                                border_fill_id=tc.get("borderFillIDRef"))
                sub = tc.find("hp:subList", NS)
                if sub is not None:
                    walk_sublist(sub, f"{path}/t{ti}/r{row}c{col}", section,
                                 "cell" if container in ("body", "cell") else container,
                                 info, top_cell or info, depth + 1)
        # 메모·머리말·각주·글상자 등
        for ci, el in enumerate(_special_containers(p)):
            kind = _SKIP_CONTAINERS[el.tag]
            for sub in el.iterfind("hp:subList", NS):
                walk_sublist(sub, f"{path}/{kind}{ci}", section, kind, None, None, depth)

    for si, sec in enumerate(sections):
        for pi, p in enumerate(sec.iterfind("hp:p", NS)):
            visit(p, f"s{si}/p{pi}", si, "body", None, None, 0)
    return out


def _special_containers(p: etree._Element):
    """문단 직속 런 안의 메모/머리말/각주/글상자 요소 (표 안쪽은 그 표의 문단이 따로 처리)."""
    stack = [c for r in p.iterfind("hp:run", NS) for c in reversed(r)]
    while stack:
        el = stack.pop()
        if el.tag == hp("tbl") or not isinstance(el.tag, str):
            continue
        if el.tag in _SKIP_CONTAINERS:
            yield el
            continue
        stack.extend(reversed(el))
