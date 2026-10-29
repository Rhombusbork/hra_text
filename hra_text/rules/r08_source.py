"""R08. 출처·참고자료: 맑은 고딕 8pt, 진하게 X, 오른쪽 정렬, 들여쓰기·여백 0.
(스타일·글꼴·간격은 R01·R02·R06 이 이미 맞춘다.)"""

from ..hwpx.edit import change_para, change_run, char_bold, char_height, para_align, para_margins
from . import register
from .base import Rule

SIZE = 8
ALIGN = "RIGHT"


@register
class R08Source(Rule):
    RULE_ID = "R08"
    NAME = "출처"

    def apply(self, doc):
        h = doc.header
        changes = []
        for p in doc.paras:
            if p.role != "SOURCE":
                continue
            for r in self.text_runs(p):
                c = h.char(r.char_id)
                if c.size_pt != SIZE and change_run(doc, p, r, char_height(SIZE)):
                    changes.append(self.change(p, "size", c.size_pt, SIZE, run=r))
                if c.bold and change_run(doc, p, r, char_bold(False)):
                    changes.append(self.change(p, "bold", True, False, run=r))
            ps = h.para(p.para_id)
            if ps.align != ALIGN and change_para(doc, p, para_align(ALIGN)):
                changes.append(self.change(p, "align", ps.align, ALIGN))
            diff = {k: 0.0 for k in ("intent", "left", "right") if ps.margins_pt.get(k) != 0.0}
            if diff and change_para(doc, p, para_margins(**diff)):
                for k in diff:
                    changes.append(self.change(p, k, ps.margins_pt.get(k), 0.0))
        return changes
