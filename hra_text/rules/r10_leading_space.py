"""R10. 문단 맨 앞 공백(띄어쓰기로 흉내 낸 들여쓰기) 제거. 들여쓰기는 R05 가 맞춘다."""

from ..hwpx.ns import NS, hp
from . import register
from .base import Rule

TARGET_ROLES = {"H1", "H2", "H3", "H4", "BODY", "AUTHOR_TAG", "REFLECTION_NAME", "REFLECTION"}
_BLANK_CHILDREN = (hp("tab"), hp("nbSpace"), hp("fwSpace"))
_SPACES = " \t　 "


def strip_leading(para_el) -> int:
    """맨 앞 공백을 지우고 지운 칸 수를 돌려준다. 글자가 나오면 멈춘다."""
    removed = 0
    for run in para_el.iterfind("hp:run", NS):
        for t in run.iterfind("hp:t", NS):
            while True:
                text = t.text or ""
                stripped = text.lstrip(_SPACES)
                removed += len(text) - len(stripped)
                t.text = stripped or None
                if stripped:
                    return removed
                first = t[0] if len(t) else None
                if first is None:
                    break  # 이 hp:t 는 비었다 → 다음 hp:t
                if first.tag not in _BLANK_CHILDREN:
                    return removed
                t.text = first.tail
                t.remove(first)
                removed += 1
        for child in run:
            if child.tag in (hp("tbl"), hp("pic")):
                return removed
    return removed


@register
class R10LeadingSpace(Rule):
    RULE_ID = "R10"
    NAME = "문단 앞 공백"

    def apply(self, doc):
        changes = []
        for p in self.formatted(doc):
            if p.role not in TARGET_ROLES or p.text[:1] not in _SPACES or not p.text.strip():
                continue
            n = strip_leading(p.el)
            if n:
                doc.touched.add(p.el)
                changes.append(self.change(p, "leading_space", n, 0))
        if changes:
            doc.reload()
        return changes
