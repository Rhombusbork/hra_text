"""R17. 줄바꿈(Shift+Enter)으로 제목·본문이 이어진 문단을 진짜 문단으로 나눈다.

문단 역할은 첫 줄로만 정해지므로, 한 문단에 '28) 제목' 줄과 본문 줄이 섞여 있으면 R03 이 문단 전체를
한 크기로 맞춘다. 서식 규칙보다 먼저 줄바꿈 자리에서 문단을 나눠
줄마다 제 역할을 받게 한다. 나눈 뒤의 앞 공백·크기·들여쓰기는 R10·R03·R05 가 맞추고, 빈 줄 수는 받은 대로 둔다.
"""

from __future__ import annotations

import copy

from lxml import etree

from ..classify import RE_H1, RE_H2, RE_H3, RE_H4, TABLE_H1_BOX, table_kind
from ..hwpx.ns import NS, hp
from . import register
from .base import Rule

TARGET_ROLES = {"H1", "H2", "H3", "H4", "BODY"}
HEADING_PATTERNS = (("H1", RE_H1), ("H2", RE_H2), ("H3", RE_H3), ("H4", RE_H4))
HEADING_LOOK_PT = 11.0  # R17-b: 둘째 줄부터는 진하게이거나 이 크기 이상이어야 제목으로 본다


def _pattern_role(text: str) -> str:
    for role, rx in HEADING_PATTERNS:
        if rx.match(text):
            return role
    return "BODY"


def _tokens(para_el) -> list[tuple]:
    """문단 글자를 (charPr, 종류, 값) 목록으로: text | inline(탭 등) | br(줄바꿈)."""
    out = []
    for run in para_el.iterfind("hp:run", NS):
        cp = run.get("charPrIDRef")
        for t in run.iterfind("hp:t", NS):
            if t.text:
                out.append((cp, "text", t.text))
            for sub in t:
                if sub.tag == hp("lineBreak"):
                    out.append((cp, "br", None))
                else:
                    e = copy.deepcopy(sub)
                    e.tail = None
                    out.append((cp, "inline", e))
                if sub.tail:
                    out.append((cp, "text", sub.tail))
    return out


def _split_lines(tokens) -> list[tuple[list, str]]:
    """줄바꿈마다 끊은 [(그 줄의 토큰들, 빈 줄일 때 쓸 charPr)]."""
    lines, cur = [], []
    last_cp = tokens[0][0] if tokens else "0"
    for tk in tokens:
        last_cp = tk[0]
        if tk[1] == "br":
            lines.append((cur, last_cp))
            cur = []
        else:
            cur.append(tk)
    lines.append((cur, last_cp))
    return lines


def _line_text(line) -> str:
    return "".join(v for _, kind, v in line if kind == "text")


def _looks_like_heading(doc, line) -> bool:
    """R17-b: 보이는 글자의 절반 이상이 진하게이거나 11pt 이상."""
    total = heading = 0
    for cp, kind, v in line:
        if kind != "text":
            continue
        n = sum(1 for ch in v if not ch.isspace())
        if not n:
            continue
        c = doc.header.char(cp)
        total += n
        if c.bold or c.size_pt >= HEADING_LOOK_PT:
            heading += n
    return total > 0 and heading * 2 >= total


def _line_roles(doc, lines) -> list[str]:
    roles = []
    for i, (line, _) in enumerate(lines):
        text = _line_text(line)
        if not text.strip():
            continue
        role = _pattern_role(text)
        if i > 0 and role != "BODY" and not _looks_like_heading(doc, line):
            role = "BODY"
        roles.append(role)
    return roles


def _splittable(para_el) -> bool:
    """글자(hp:t)만 든 문단만 나눈다: 표·그림·컨트롤(메모·필드·구역 정의 등)이 있으면 건너뜀."""
    for run in para_el.iterfind("hp:run", NS):
        if any(child.tag != hp("t") for child in run):
            return False
    return True


def _build_para(src_el, line, empty_cp: str, first: bool) -> etree._Element:
    new = etree.Element(hp("p"), {k: src_el.get(k) for k in src_el.keys()})
    if not first:
        for attr in ("pageBreak", "columnBreak"):
            if new.get(attr) is not None:
                new.set(attr, "0")
    if not line:
        etree.SubElement(new, hp("run"), charPrIDRef=empty_cp)
        return new
    run = t = None
    for cp, kind, v in line:
        if run is None or run.get("charPrIDRef") != cp:
            run = etree.SubElement(new, hp("run"), charPrIDRef=cp)
            t = etree.SubElement(run, hp("t"))
        if kind == "text":
            if len(t):
                t[-1].tail = (t[-1].tail or "") + v
            else:
                t.text = (t.text or "") + v
        else:
            t.append(v)
    return new


@register
class R17LineBreak(Rule):
    RULE_ID = "R17"
    NAME = "줄바꿈 문단 나누기"

    def apply(self, doc):
        body = [p for p in doc.paras if p.container == "body" and p.depth == 0]
        first_h1 = next((i for i, p in enumerate(body)
                         if p.role == "H1" or (p.role == "OBJECT"
                                               and any(table_kind(doc, t) == TABLE_H1_BOX for t in p.tables))),
                        None)
        if first_h1 is None:
            return []
        changes = []
        for p in body[first_h1:]:
            if p.role not in TARGET_ROLES or p.el.find(".//hp:lineBreak", NS) is None:
                continue
            if not _splittable(p.el):
                continue
            lines = _split_lines(_tokens(p.el))
            if len(set(_line_roles(doc, lines))) < 2:
                continue
            new = [_build_para(p.el, line, cp, i == 0) for i, (line, cp) in enumerate(lines)]
            parent = p.el.getparent()
            at = parent.index(p.el)
            parent.remove(p.el)
            for k, el in enumerate(new):
                parent.insert(at + k, el)
                doc.touched.add(el)
            anchor = next((el for el, (line, _) in zip(new, lines) if _line_text(line).strip()), new[0])
            c = self.change(p, "line_break", len(lines), len(new))
            c.para_el = anchor
            changes.append(c)
        if changes:
            doc.reload()
        return changes
