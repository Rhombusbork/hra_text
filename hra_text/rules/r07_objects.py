"""R07. 표·그림은 "글자처럼 취급". 들여쓰기 0 은 R05(OBJECT 역할)가 맞춘다.

떠 있던 개체가 다른 개체·글자와 같은 문단에 있으면, 옵션만 켜면 개체가 문단 안 앵커 위치로
끌려와 순서가 바뀐다 (예: 책 소개 표가 'Ⅰ. 책 소개' 칸 앞으로). 문단 기준(vertRelTo=PARA)으로
떠 있던 개체는 화면 세로 위치(vertOffset) 순서대로 각자 새 문단으로 옮겨 원래 문단 뒤에 둔다.
쪽/용지 기준으로 떠 있던 개체는 순서를 확신할 수 없어 옵션만 켜고 위치 확인을 요청한다.
"""

from lxml import etree

from ..hwpx.ns import NS, hp
from . import register
from .base import Rule

OBJECT_TAGS = (hp("tbl"), hp("pic"))


def _objects(para_el):
    """문단 직속 런의 개체를 문서 순서대로: [(run, obj), ...]"""
    return [(r, o) for r in para_el.iterfind("hp:run", NS) for o in r if o.tag in OBJECT_TAGS]


def _is_floating(obj) -> bool:
    pos = obj.find("hp:pos", NS)
    return pos is None or pos.get("treatAsChar") != "1"


def _kind(obj) -> str:
    return "표" if obj.tag == hp("tbl") else "사진"


def _new_para_after(anchor_el, template_el, run_el, obj) -> etree._Element:
    new = etree.Element(hp("p"), {k: template_el.get(k) for k in template_el.keys()})
    new.set("pageBreak", "0")
    run = etree.SubElement(new, hp("run"), charPrIDRef=run_el.get("charPrIDRef"))
    run_el.remove(obj)
    run.append(obj)
    anchor_el.addnext(new)
    return new


@register
class R07Objects(Rule):
    RULE_ID = "R07"
    NAME = "글자처럼 취급"

    def apply(self, doc):
        changes = []
        moved_any = False
        for p in list(self.formatted(doc)):
            objs = _objects(p.el)
            floating = [(r, o) for r, o in objs if _is_floating(o)]
            if not floating:
                continue
            has_other = bool(p.text.strip()) or len(objs) > len(floating) or len(floating) > 1
            movable = [(r, o) for r, o in floating
                       if o.find("hp:pos", NS) is not None
                       and o.find("hp:pos", NS).get("vertRelTo") == "PARA"]
            uncertain = has_other and len(movable) < len(floating)

            if has_other and movable and not uncertain:
                # 떠 있는 개체를 세로 위치 순서로 뒤 문단에 하나씩
                movable.sort(key=lambda ro: int(ro[1].find("hp:pos", NS).get("vertOffset", "0")))
                inline_left = len(objs) > len(floating) or bool(p.text.strip())
                anchor = p.el
                for i, (r, o) in enumerate(movable):
                    if not inline_left and i == 0:
                        continue  # 첫 개체는 원래 문단에 남긴다
                    anchor = _new_para_after(anchor, p.el, r, o)
                    doc.touched.add(anchor)
                    moved_any = True

            for _, o in floating:
                pos = o.find("hp:pos", NS)
                if pos is None:
                    continue
                pos.set("treatAsChar", "1")
                doc.touched.add(p.el)
                changes.append(self.change(
                    p, "treatAsChar", False, True, kind=_kind(o),
                    note="원래 위치가 쪽 기준이라 배치 확인 필요" if uncertain else "",
                ))
        if moved_any:
            doc.reload()
        return changes
