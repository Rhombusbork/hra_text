"""R16. 쪽 번호 제거 (쪽 번호 매기기 hp:pageNum, 머리말/꼬리말의 쪽 번호 자동 번호)."""

from ..hwpx.ns import NS, hp
from . import register
from .base import Rule


def _page_number_ctrls(section):
    for ctrl in section.iter(hp("ctrl")):
        for child in ctrl:
            if child.tag == hp("pageNum") or (child.tag == hp("autoNum") and child.get("numType") == "PAGE"):
                yield ctrl
                break


@register
class R16PageNumber(Rule):
    RULE_ID = "R16"
    NAME = "쪽 번호 제거"

    def apply(self, doc):
        removed = 0
        for sec in doc.pkg.sections():
            for ctrl in list(_page_number_ctrls(sec)):
                para = next((a for a in ctrl.iterancestors() if a.tag == hp("p")), None)
                ctrl.getparent().remove(ctrl)
                if para is not None:
                    doc.touched.add(para)
                removed += 1
        if not removed:
            return []
        doc.reload()
        first = next((p for p in doc.paras if p.container == "body" and p.text.strip()), None)
        return [self.change(first, "page_num", removed, 0)] if first is not None else []
