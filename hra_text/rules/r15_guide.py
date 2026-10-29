"""R15. 양식 안내문(붉은 글씨 #FF0000) 삭제. 글자가 모두 지워진 문단은 문단째 지운다."""

from ..classify import GUIDE_COLOR
from ..hwpx.ns import NS, hp
from . import register
from .base import Rule, text_anchor


def _deletable(para_el) -> bool:
    """글자를 지운 뒤 지워도 되는 문단인가 (개체·컨트롤·구역 정의·쪽 나누기가 없을 때만)."""
    if para_el.get("pageBreak") == "1":
        return False
    for run in para_el.iterfind("hp:run", NS):
        for child in run:
            if child.tag != hp("t"):
                return False
            if (child.text or "").strip() or len(child):
                return False
    return True


@register
class R15Guide(Rule):
    RULE_ID = "R15"
    NAME = "양식 안내문 삭제"

    def apply(self, doc):
        changes, removed_any = [], False
        for p in doc.paras:
            if p.container not in ("body", "cell"):
                continue
            red = [r for r in p.runs if r.text.strip() and doc.header.char(r.char_id).text_color == GUIDE_COLOR]
            if not red:
                continue
            text = " ".join(r.text.strip() for r in red)
            for r in red:
                for t in r.el.findall("hp:t", NS):
                    r.el.remove(t)
                if len(r.el) == 0 and len(p.el.findall("hp:run", NS)) > 1:
                    p.el.remove(r.el)
            doc.touched.add(p.el)
            remaining = "".join(r.text for r in p.runs if r not in red)
            whole = not remaining.strip() and _deletable(p.el)
            anchor = text_anchor(doc, p) if whole else p
            if whole and p.el.getparent() is not None and len(p.el.getparent().findall("hp:p", NS)) > 1:
                p.el.getparent().remove(p.el)
                removed_any = True
            if anchor is not None:
                changes.append(self.change(anchor, "guide", text, "", deleted_para=whole))
        if changes or removed_any:
            doc.reload()
        return changes
