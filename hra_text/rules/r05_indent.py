"""R05. 들여쓰기·왼쪽/오른쪽 여백 (FORMAT_RULES R05 표). SOURCE 는 R08 이 처리.
빈 줄(EMPTY)은 보이지 않으므로 건드리지 않는다."""

from ..hwpx.edit import change_para, para_margins
from . import register
from .base import Rule

INDENT_10 = {"H2", "H3", "H4", "BODY", "REFLECTION_NAME", "REFLECTION"}
SKIP_ROLES = {"SOURCE", "EMPTY"}
KEYS = ("intent", "left", "right")


def expected_margins(role: str) -> dict[str, float]:
    return {"intent": 10.0 if role in INDENT_10 else 0.0, "left": 0.0, "right": 0.0}


@register
class R05Indent(Rule):
    RULE_ID = "R05"
    NAME = "들여쓰기·여백"

    def apply(self, doc):
        changes = []
        for p in self.formatted(doc):
            if p.role in SKIP_ROLES:
                continue
            want = expected_margins(p.role)
            have = doc.header.para(p.para_id).margins_pt
            diff = {k: v for k, v in want.items() if have.get(k) != v}
            if diff and change_para(doc, p, para_margins(**diff)):
                for k, v in diff.items():
                    changes.append(self.change(p, k, have.get(k), v))
        return changes
