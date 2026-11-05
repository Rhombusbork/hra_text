"""변경 기록(Change) → 메모 계획 → 문서에 삽입 (FORMAT_RULES §3).

- 본문 문단: 수정된 문단 1개당 메모 1개 (여러 규칙은 한 메모에 줄을 나눠 적는다)
- 표: 표 1개당 메모 1개 (표 안 첫 글자 문단에 단다)
- 빈 줄·그림만 있는 문단: 같은 영역의 다음 글자 문단 메모에 합친다
- 바로 앞 메모와 고친 내용이 같으면 새 메모를 달지 않고 앞 메모에 "아래 … n개도 같은 문제" 한 줄
- 문구는 키워드 형식: '수정사항' + '- 항목: 이전 → 새' (FORMAT_RULES §3)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from lxml import etree

from .document import Document
from .hwpx.memo import existing_memo_count, insert_memo
from .hwpx.section import Para
from .model import Change
from .report import KEY_NAMES
from .rules.base import ORDER
from .rules.memo_templates import COMMON, MEMO_TEMPLATES

ALIGN_NAMES = {"JUSTIFY": "양쪽", "LEFT": "왼쪽", "RIGHT": "오른쪽", "CENTER": "가운데",
               "DISTRIBUTE": "배분", "DISTRIBUTE_SPACE": "나눔"}
PT_KEYS = {"size", "intent", "left", "right", "prev", "next"}
KEY_ORDER = ("guide", "page_num", "line_break", "leading_space", "spacing", "spacing_check", "treatAsChar", "style", "font", "size", "bold",
             "default", "align", "intent", "left", "right", "prev", "next", "line", "blank_lines",
             "toc", "toc_count")


@dataclass
class MemoPlan:
    target: etree._Element
    order: int
    kind: str = "para"  # para | table
    changes: list[Change] = field(default_factory=list)
    table_paras: set = field(default_factory=set)  # 표 메모: 수정된 셀 문단
    empty_paras: set = field(default_factory=set)  # 합쳐진 빈 줄


def _value(key: str, v) -> str:
    if v is None:
        return "글자 단위"
    if key == "align":
        return ALIGN_NAMES.get(v, str(v))
    if isinstance(v, bool):
        return "켬" if v else "끔"
    if key in PT_KEYS:
        return f"{v:g}pt"
    if key == "line":
        return f"{v}%"
    if key == "blank_lines":
        return f"{v}줄"
    if key == "leading_space":
        return f"{v}칸" if v else "없음"
    return str(v)



# ---------------------------------------------------------------- 대상 정하기
def _next_text_para(doc: Document, p: Para) -> Para | None:
    parent = p.el.getparent()
    siblings = [q for q in doc.paras if q.el.getparent() is parent and q.text.strip()]
    after = [q for q in siblings if q.index > p.index]
    before = [q for q in siblings if q.index < p.index]
    return after[0] if after else (before[-1] if before else None)


def _first_text_para_in_table(doc: Document, tbl) -> Para | None:
    for q in doc.paras:
        if q.top_cell is not None and q.top_cell.tbl is tbl and q.text.strip():
            return q
    return None


# 고치되 메모는 달지 않는 것 [U] 2026-10-29: 표지의 ■ 분류 표시·표지 제목의 들여쓰기
SILENT = {("CATEGORY", "intent"), ("COVER_TITLE", "intent")}


def plan(doc: Document, changes: list[Change]) -> list[MemoPlan]:
    by_el = {p.el: p for p in doc.paras}
    plans: dict[int, MemoPlan] = {}

    def get(target: Para, kind: str = "para") -> MemoPlan:
        key = id(target.el)
        if key not in plans:
            plans[key] = MemoPlan(target=target.el, order=target.index, kind=kind)
        return plans[key]

    obj_para = {id(o): q for q in doc.paras for o in q.tables + q.pictures}
    for c in changes:
        if (c.role, c.key) in SILENT:
            continue
        p = by_el.get(c.para_el)
        obj = c.extra.get("obj")
        if obj is not None and id(obj) in obj_para:  # R07: 옮겨진 개체가 지금 있는 문단 기준
            p = obj_para[id(obj)]
        if p is None:
            continue
        if obj is not None and obj.tag.endswith("}tbl"):
            target = _first_text_para_in_table(doc, obj) or _next_text_para(doc, p)
            if target is not None:
                get(target, "table").changes.append(c)
            continue
        if p.top_cell is not None or (p.role == "OBJECT" and p.tables):
            tbl = p.top_cell.tbl if p.top_cell is not None else p.tables[0]
            target = _first_text_para_in_table(doc, tbl) or _next_text_para(doc, p)
            if target is None:
                continue
            mp = get(target, "table")
            mp.changes.append(c)
            if p.top_cell is not None:
                mp.table_paras.add(p.el)
        elif not p.text.strip():
            target = _next_text_para(doc, p)
            if target is None:
                continue
            mp = get(target)
            if p.role == "EMPTY":
                mp.empty_paras.add(p.el)
            else:
                mp.changes.append(c)  # 그림만 있는 문단 등
        else:
            get(p).changes.append(c)
    return sorted(plans.values(), key=lambda m: m.order)


# ---------------------------------------------------------------- 문구 만들기
class Writer:
    """키워드 형식 메모 (FORMAT_RULES §3): 첫 줄 '수정사항'/'표 안 문단 n개 수정' + '- 항목: 이전 → 새' 줄들."""

    def _item(self, c: Change, name: str | None = None) -> str:
        return COMMON["item"].format(item=name or KEY_NAMES.get(c.key, c.key),
                                     old=_value(c.key, c.old), new=_value(c.key, c.new))

    def lines(self, mp: MemoPlan, same_below: int = 0) -> list[str]:
        if mp.table_paras:
            head = COMMON["table_head"].format(n=len(mp.table_paras))
        elif mp.kind == "table":
            head = COMMON["table_box"]  # 표를 담은 문단(표 자체)만 고친 경우
        else:
            head = COMMON["head"]
        out = [head]
        uniq: dict[tuple, Change] = {}
        for c in mp.changes:
            uniq.setdefault((c.rule_id, c.key, repr(c.old), repr(c.new), c.extra.get("kind")), c)
        ordered = sorted(uniq.values(), key=lambda c: (
            ORDER.index(c.rule_id), KEY_ORDER.index(c.key) if c.key in KEY_ORDER else 99))
        for c in ordered:
            out.append(self._line(c))
            if c.rule_id == "R07" and c.note:
                out.append(MEMO_TEMPLATES["R07"]["check"].format(kind=c.extra.get("kind", "개체")))
        if same_below:
            out.append(COMMON["same_below"].format(what="표" if mp.kind == "table" else "문단", n=same_below))
        if mp.empty_paras:
            out.append(COMMON["empty_lines"].format(n=len(mp.empty_paras)))
        return out if len(out) > 1 else []

    def _line(self, c: Change) -> str:
        t = MEMO_TEMPLATES
        if c.rule_id == "R15":
            return t["R15"]["guide"].format(text=c.old)
        if c.rule_id == "R16":
            return t["R16"]["page_num"]
        if c.rule_id == "R17":
            return t["R17"]["line_break"].format(n=c.new)
        if c.rule_id == "R14":
            return t["R14"][c.key].format(toc=c.old, h1=c.new)
        if c.rule_id == "R13":
            return t["R13"]["default"].format(item=c.extra.get("item", c.old))
        if c.rule_id == "R11":
            if c.key == "spacing_check":
                return t["R11"]["spacing_check"].format(text=c.old)
            return t["R11"]["spacing"].format(old=c.old, new=c.new)
        if c.rule_id == "R10":
            return t["R10"]["leading_space"].format(old=c.old)
        if c.rule_id == "R09":
            variant = c.extra.get("variant", "too_many")
            return t["R09"]["blank"].format(old=c.old, new=c.new, reason=t["R09"].get(variant, ""))
        if c.rule_id == "R07":
            return self._item(c, f"글자처럼 취급({c.extra.get('kind', '개체')})")
        return self._item(c)


def signature(mp: MemoPlan):
    """고친 내용의 정체: 같으면 앞 메모에 합친다. 고친 내용 없이 빈 줄만 있으면 합치지 않는다."""
    if not mp.changes:
        return None
    return mp.kind, frozenset((c.rule_id, c.key, repr(c.old), repr(c.new), c.extra.get("kind"), c.note)
                              for c in mp.changes)


def group_runs(plans: list[MemoPlan]) -> list[list[MemoPlan]]:
    """문서 순서로 이어지는 같은 고친 내용의 메모 계획을 한 묶음으로."""
    runs: list[list[MemoPlan]] = []
    for mp in plans:
        sig = signature(mp)
        if runs and sig is not None and signature(runs[-1][0]) == sig:
            runs[-1].append(mp)
        else:
            runs.append([mp])
    return runs


def add_memos(doc: Document, changes: list[Change], *, author: str = "neoju",
              when: datetime | None = None) -> int:
    """변경 기록으로 메모를 만들어 넣고, 넣은 메모 수를 돌려준다."""
    plans = plan(doc, changes)
    writer = Writer()
    number = existing_memo_count(doc)
    when = when or datetime.now(timezone.utc)
    added = 0
    for run in group_runs(plans):
        mp = run[0]
        lines = writer.lines(mp, same_below=len(run) - 1)
        if not lines:
            continue
        number += 1
        insert_memo(doc, mp.target, lines, author=author, number=number, when=when)
        added += 1
    if added:
        doc.reload()
    return added
