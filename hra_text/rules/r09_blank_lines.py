"""R09. 빈 줄 정리 (본문 영역, 표지 제외).

앞 문단(X)과 뒤 문단(Y) 사이 빈 줄 수 (줄이기만 하고 새로 넣지는 않는다):
- X 가 타이틀(1단위 칸·H2·H3·H4) → 0 (타이틀과 그 아래는 붙여 쓴다)
- 그 외 → 최대 1 (여러 줄이면 한 줄로)
건드리지 않는 빈 줄: Y 가 ■ 분류 표시(고전 '함께읽기용' 등 새 부분의 시작)일 때, 그리고
쪽 나누기·컨트롤·구역 정의가 든 문단.
"""

from ..classify import TABLE_H1_BOX, table_kind
from ..hwpx.ns import NS, hp
from . import register
from .base import Rule

HEADINGS_AFTER = {"H2", "H3", "H4"}  # 이 뒤는 붙여 쓴다


def _is_h1_box(doc, p) -> bool:
    return p.role == "OBJECT" and any(table_kind(doc, t) == TABLE_H1_BOX for t in p.tables)


def _removable(p) -> bool:
    if p.el.get("pageBreak") == "1":
        return False
    for run in p.el.iterfind("hp:run", NS):
        if any(child.tag != hp("t") for child in run):
            return False
    return True


@register
class R09BlankLines(Rule):
    RULE_ID = "R09"
    NAME = "빈 줄 정리"

    def apply(self, doc):
        body = [p for p in doc.paras if p.container == "body" and p.depth == 0 and p.role != "SKIP"]
        first_h1 = next((i for i, p in enumerate(body) if _is_h1_box(doc, p) or p.role == "H1"), None)
        if first_h1 is None:
            return []
        changes, structural = [], False
        i = first_h1
        while i < len(body):
            x = body[i]
            j = i + 1
            while j < len(body) and body[j].role == "EMPTY":
                j += 1
            if j >= len(body):
                break
            y = body[j]
            blanks = body[i + 1:j]
            if y.role == "CATEGORY":
                i = j
                continue
            if x.role in HEADINGS_AFTER or _is_h1_box(doc, x) or x.role == "H1":
                want, variant = 0, ("h2_h3" if x.role == "H2" and y.role == "H3" else "heading")
            else:
                want, variant = min(len(blanks), 1), "too_many"
            removable = [b for b in blanks if _removable(b)]
            if len(blanks) > want:
                extra = removable[: len(blanks) - want] if want == 0 else removable[1:][: len(blanks) - want]
                for b in extra:
                    b.el.getparent().remove(b.el)
                if extra:
                    structural = True
                    changes.append(self.change(y, "blank_lines", len(blanks), len(blanks) - len(extra),
                                               variant=variant))
            i = j
        if structural:
            doc.reload()
            for c in changes:
                doc.touched.add(c.para_el)
        return changes
