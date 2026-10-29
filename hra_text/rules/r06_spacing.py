"""R06. 문단 위/아래 간격 0, 줄 간격 160% (표 안 포함)."""

from ..hwpx.edit import change_para, para_line_spacing, para_margins
from . import register
from .base import Rule

LINE_PERCENT = 160


@register
class R06Spacing(Rule):
    RULE_ID = "R06"
    NAME = "문단 간격·줄 간격"

    def apply(self, doc):
        changes = []
        for p in self.formatted(doc):
            ps = doc.header.para(p.para_id)
            diff = {k: 0.0 for k in ("prev", "next") if ps.margins_pt.get(k) != 0.0}
            line_ok = ps.line_spacing == ("PERCENT", LINE_PERCENT)

            def mutate(el, diff=diff, line_ok=line_ok):
                para_margins(**diff)(el)
                if not line_ok:
                    para_line_spacing(LINE_PERCENT)(el)

            if (diff or not line_ok) and change_para(doc, p, mutate):
                for k in diff:
                    changes.append(self.change(p, k, ps.margins_pt.get(k), 0.0))
                if not line_ok:
                    changes.append(self.change(p, "line", ps.line_spacing[1], LINE_PERCENT,
                                               line_type=ps.line_spacing[0]))
        return changes
