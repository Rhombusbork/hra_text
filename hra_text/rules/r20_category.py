"""R20. ■ 분류 줄이 없고 첫 줄이 비어 있으면 파일 이름으로 분류 글자(■ 고전명작 등)를 넣는다.

제출자가 `■ 고전명작` 글자만 지우고 빈 줄(12pt 진하게)을 남긴 경우. 크기·진하게는 R03 이 맞춘다.
빈 줄의 글자 모양이 양식 안내문 색(붉은 글씨)이면 넣은 글자가 R15 에 지워지므로 검정으로 바꾼다.
첫 줄이 비어 있지 않거나 파일 이름으로 종류를 모르면 확인 메모만 단다. 합본(merge/cli.py)도
같은 category_from_filename 으로 종류를 정한다.
"""

from __future__ import annotations

import re
from pathlib import Path

from ..hwpx.memo import memo_texts
from ..hwpx.ns import NS, hp
from . import register
from .base import Rule

# 파일 이름의 종류 낱말 → 분류 글자 (앞의 것부터 찾는다: 에세이도 ■ 고전명작)
FILENAME_KINDS = (("에세이", "■ 고전명작"), ("고전", "■ 고전명작"), ("경영서", "■ 경영서"), ("기업실무", "■ 기업실무"))
CHECK_MARK = "분류 줄 없음"


def category_from_filename(path: Path | str) -> str | None:
    stem = Path(path).stem
    for word, category in FILENAME_KINDS:
        if re.search(rf"[-_]\s*{word}", stem):
            return category
    return None


def _set_text(doc, p_el, text: str) -> None:
    """마지막 글자 런에 text 를 넣는다. 그 런이 양식 안내문 색(붉은 글씨)이면 검정으로 (R15 가 지우지 않게)."""
    runs = p_el.findall("hp:run", NS)
    if not runs:
        runs = [p_el.makeelement(hp("run"), charPrIDRef="0")]
        p_el.append(runs[0])
    run = next((r for r in reversed(runs) if r.find("hp:t", NS) is not None), runs[-1])
    for t in run.findall("hp:t", NS):
        run.remove(t)
    t = run.makeelement(hp("t"))
    t.text = text
    run.append(t)
    old = run.get("charPrIDRef")
    new = doc.header.derive_char(old, lambda el: el.set("textColor", "#000000"))
    if new != old:
        run.set("charPrIDRef", new)


@register
class R20Category(Rule):
    RULE_ID = "R20"
    NAME = "빈 분류 줄 채우기"

    def apply(self, doc):
        if any(p.role == "CATEGORY" for p in doc.paras):
            return []
        body = [p for p in doc.paras if p.container == "body" and p.depth == 0 and p.role != "SKIP"]
        if not body:
            return []
        category = category_from_filename(doc.source)
        first = body[0]
        if category and first.is_empty:
            _set_text(doc, first.el, category)
            doc.touched.add(first.el)
            doc.reload()
            para = next(p for p in doc.paras if p.el is first.el)
            return [self.change(para, "category", "", category)]
        anchor = next((p for p in body if p.text.strip()), None)
        if anchor is None or any(CHECK_MARK in m for m in memo_texts(anchor.el)):
            return []
        return [self.change(anchor, "category_check", "", "", check=True)]
