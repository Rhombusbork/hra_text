"""메모(fieldBegin type=MEMO … fieldEnd) 삽입.

구조는 한글이 저장한 피드백 샘플과 같다:
  <hp:run><hp:ctrl><hp:fieldBegin type="MEMO" …><hp:parameters>…</hp:parameters>
          <hp:subList><hp:p styleIDRef=메모 …>메모 내용</hp:p>…</hp:subList></hp:fieldBegin></hp:ctrl>
          <hp:t>메모가 걸린 글자</hp:t><hp:ctrl><hp:fieldEnd beginIDRef=… fieldid=…/></hp:ctrl></hp:run>
"""

from __future__ import annotations

import random
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from lxml import etree

from .ns import NS, hp

if TYPE_CHECKING:
    from ..document import Document

MEMO_STYLE = "메모"
_FILETIME_EPOCH = datetime(1601, 1, 1, tzinfo=timezone.utc)


def existing_memo_count(doc: "Document") -> int:
    numbers = [0]
    for sec in doc.pkg.sections():
        for fb in sec.iter(hp("fieldBegin")):
            if fb.get("type") == "MEMO":
                n = fb.find("hp:parameters/hp:integerParam[@name='Number']", NS)
                numbers.append(int(n.text) if n is not None and n.text else 0)
    return max(numbers)


def _filetime(when: datetime) -> tuple[int, int]:
    ticks = int((when - _FILETIME_EPOCH).total_seconds() * 10_000_000)
    return ticks & 0xFFFFFFFF, ticks >> 32


def _memo_shapes(doc: "Document") -> tuple[str, str, str]:
    """메모 문단에 쓸 (styleIDRef, paraPrIDRef, charPrIDRef)."""
    h = doc.header
    sid = h.style_id(MEMO_STYLE) or h.style_id("바탕글") or "0"
    style = h._styles[sid]
    return sid, style.get("paraPrIDRef", "0"), style.get("charPrIDRef", "0")


def _ctrl(child: etree._Element) -> etree._Element:
    ctrl = etree.Element(hp("ctrl"))
    ctrl.append(child)
    return ctrl


def insert_memo(doc: "Document", para_el: etree._Element, lines: list[str], *,
                author: str, number: int, when: datetime | None = None,
                rng: random.Random | None = None) -> None:
    """para_el 의 글자 전체에 메모를 단다. 글자가 없는 문단이면 ValueError."""
    text_runs = [r for r in para_el.iterfind("hp:run", NS)
                 if any((t.text or "") or len(t) for t in r.iterfind("hp:t", NS))]
    if not text_runs:
        raise ValueError("메모를 달 글자가 없는 문단입니다")
    rng = rng or random.Random()
    when = when or datetime.now(timezone.utc)
    begin_id, field_id = rng.randrange(1, 2**31), rng.randrange(1, 2**31)
    low, high = _filetime(when)
    style_id, para_pr, char_pr = _memo_shapes(doc)

    fb = etree.Element(hp("fieldBegin"), id=str(begin_id), type="MEMO", name="", editable="1",
                       dirty="1", zorder=str(number), fieldid=str(field_id))
    params = etree.SubElement(fb, hp("parameters"), cnt="7", name="")
    for tag, name, value in (
        ("integerParam", "Prop", "0"),
        ("stringParam", "Command", f"MEMO/65535/{number}/{low}/{high}/{author}/\\;;"),
        ("stringParam", "ID", f"memo{number}"),
        ("integerParam", "Number", str(number)),
        ("stringParam", "Author", author),
        ("stringParam", "MemoShapeIDRef", "65535"),
        ("stringParam", "CreateDateTime", when.strftime("%Y-%m-%dT%H:%M:%SZ")),
    ):
        etree.SubElement(params, hp(tag), name=name).text = value
    sub = etree.SubElement(fb, hp("subList"), id="", textDirection="HORIZONTAL", lineWrap="BREAK",
                           vertAlign="TOP", linkListIDRef="0", linkListNextIDRef="0", textWidth="0",
                           textHeight="0", hasTextRef="0", hasNumRef="0")
    for line in lines:
        mp = etree.SubElement(sub, hp("p"), id="0", paraPrIDRef=para_pr, styleIDRef=style_id,
                              pageBreak="0", columnBreak="0", merged="0")
        run = etree.SubElement(mp, hp("run"), charPrIDRef=char_pr)
        etree.SubElement(run, hp("t")).text = line

    first, last = text_runs[0], text_runs[-1]
    first.find("hp:t", NS).addprevious(_ctrl(fb))
    last.findall("hp:t", NS)[-1].addnext(
        _ctrl(etree.Element(hp("fieldEnd"), beginIDRef=str(begin_id), fieldid=str(field_id))))
    doc.touched.add(para_el)
