"""R14. 목차 항목과 본문 1단위 타이틀 대조 (메모만, 자동 수정 안 함).
표지 정보 표의 글자 서식은 R03·R04·R06 이 맞춘다."""

import re

from ..hwpx.memo import memo_texts
from . import register
from .base import Rule


def _norm(text: str) -> str:
    return re.sub(r"\s+", "", text)


@register
class R14Toc(Rule):
    RULE_ID = "R14"
    NAME = "목차 대조"

    def apply(self, doc):
        toc = [p for p in doc.paras if p.role == "TOC_ITEM"]
        h1 = [p for p in doc.paras if p.role == "H1"]
        if not toc:
            return []
        # 이미 목차 지적 메모가 달린 문서(이 프로그램 결과를 다시 넣은 경우)는 또 지적하지 않는다
        toc_table = toc[0].top_cell.tbl if toc[0].top_cell is not None else toc[0].el
        if any("목차" in m and "확인 부탁드립니다" in m for m in memo_texts(toc_table)):
            return []
        changes = []
        for t, h in zip(toc, h1):
            if _norm(t.text) != _norm(h.text):
                changes.append(self.change(t, "toc", t.text.strip(), h.text.strip(), check=True))
        if len(toc) != len(h1):
            changes.append(self.change(toc[0], "toc_count", len(toc), len(h1), check=True))
        return changes
