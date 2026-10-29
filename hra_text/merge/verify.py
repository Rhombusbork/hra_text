"""hwpx 안의 참조가 모두 맞는지 검사 (합본 결과 확인용). 문제 목록을 돌려준다 (비면 정상)."""

from __future__ import annotations

from collections import Counter

from ..hwpx.ns import NS, hc, hp
from ..hwpx.package import HwpxPackage
from .core import HPF, OBJECT_TAGS, OPF
from .headermap import NONE_REF

LISTS = {"charPrIDRef": ".//hh:charProperties/hh:charPr", "paraPrIDRef": ".//hh:paraProperties/hh:paraPr",
         "styleIDRef": ".//hh:styles/hh:style", "borderFillIDRef": ".//hh:borderFills/hh:borderFill"}


def check(pkg: HwpxPackage) -> list[str]:
    problems = []
    ids = {attr: {e.get("id") for e in pkg.header.iterfind(xp, NS)} for attr, xp in LISTS.items()}
    manifest = pkg.xml(HPF).find(f"{{{OPF}}}manifest") if HPF in pkg.names() else None
    images = {i.get("id"): i.get("href") for i in manifest} if manifest is not None else {}
    for href in images.values():
        if href.startswith("BinData/") and href not in pkg.names():
            problems.append(f"목록에 있는 그림 파일 없음: {href}")
    object_ids = Counter()
    for name in pkg.section_names():
        root = pkg.xml(name)
        begins, ends = set(), set()
        for el in root.iter():
            if not isinstance(el.tag, str):
                continue
            for attr, valid in ids.items():
                v = el.get(attr)
                if v is not None and v != NONE_REF and v not in valid:
                    problems.append(f"{name}: {etree_name(el)} {attr}={v} 가 header 에 없음")
            if el.tag == hc("img") and el.get("binaryItemIDRef") not in images:
                problems.append(f"{name}: 그림 {el.get('binaryItemIDRef')} 이(가) 목록에 없음")
            if el.tag in OBJECT_TAGS and el.get("id"):
                object_ids[el.get("id")] += 1
            if el.tag == hp("fieldBegin"):
                begins.add(el.get("id"))
            if el.tag == hp("fieldEnd"):
                ends.add(el.get("beginIDRef"))
        if begins != ends:
            problems.append(f"{name}: 필드 시작/끝 짝이 안 맞음 {len(begins ^ ends)}개")
    dup = [i for i, n in object_ids.items() if n > 1 and i != "0"]
    if dup:
        problems.append(f"개체 ID 중복 {len(dup)}개 (예: {dup[:3]})")
    return problems


def etree_name(el) -> str:
    return el.tag.split("}")[-1]


def memo_count(pkg: HwpxPackage) -> int:
    return sum(1 for n in pkg.section_names() for fb in pkg.xml(n).iter(hp("fieldBegin")) if fb.get("type") == "MEMO")
