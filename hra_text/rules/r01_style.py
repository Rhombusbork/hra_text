"""R01. 스타일은 전부 "바탕글"."""

from . import register
from .base import Rule

TARGET_STYLE = "바탕글"


@register
class R01Style(Rule):
    RULE_ID = "R01"
    NAME = "스타일 바탕글"

    def apply(self, doc):
        target = doc.header.style_id(TARGET_STYLE)
        if target is None:
            raise ValueError(f"문서에 '{TARGET_STYLE}' 스타일이 없습니다")
        changes = []
        for p in self.formatted(doc):
            if p.style_id != target:
                old = doc.header.style_name(p.style_id)
                p.el.set("styleIDRef", target)
                doc.touched.add(p.el)
                changes.append(self.change(p, "style", old, TARGET_STYLE))
        return changes
