"""합본 만들기: 참고 합본(표지·일정표) + 제출 문서들을 순서대로 이어 붙인다.

- 참고 합본의 구역 0(표지)은 그대로, 구역 1은 일정표 쪽(첫 쪽 나누기 전)만 남긴다.
- 제출 문서는 본문 문단을 통째로 가져와 첫 문단에 쪽 나누기를 넣는다.
- 가져올 때: header ID 다시 매기기, 그림 복사, 구역 정의·쪽 번호·머리말 제거, 메모 제거,
  개체·필드 ID 다시 매기기, 레이아웃 캐시 삭제. 서식 교정은 하지 않는다.
"""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass, field
from pathlib import Path

from ..hwpx.ns import NS, hc, hp
from ..hwpx.package import HwpxPackage
from .headermap import NONE_REF, HeaderMerger

OPF = "http://www.idpf.org/2007/opf/"
HPF = "Contents/content.hpf"
REF_ATTRS = {"charPrIDRef": "char", "paraPrIDRef": "para", "styleIDRef": "style",
             "borderFillIDRef": "border"}
# 문서마다 따로인 구역 설정 — 합본 본문 구역 설정을 따르므로 가져오지 않는다
DROP_CTRL_CHILDREN = {hp("colPr"), hp("pageNum"), hp("pageHiding"), hp("header"), hp("footer")}
OBJECT_TAGS = {hp(t) for t in ("tbl", "pic", "rect", "ellipse", "line", "arc", "polygon", "curve",
                               "connectLine", "container", "ole", "equation", "textart", "video", "chart")}


@dataclass
class MergedDoc:
    path: Path
    paragraphs: int
    images: int
    memos_removed: int


@dataclass
class MergeResult:
    docs: list[MergedDoc] = field(default_factory=list)


# ---------------------------------------------------------------- 참고 합본 준비
def body_section(pkg: HwpxPackage):
    names = pkg.section_names()
    return pkg.xml(names[-1])


def keep_schedule_only(pkg: HwpxPackage) -> int:
    """본문 구역에서 첫 쪽 나누기 문단부터 끝까지 지운다 (일정표 쪽만 남김). 남은 문단 수."""
    sec = body_section(pkg)
    paras = sec.findall("hp:p", NS)
    cut = next((i for i, p in enumerate(paras) if i > 0 and p.get("pageBreak") == "1"), len(paras))
    for p in paras[cut:]:
        sec.remove(p)
    prune_unused_images(pkg)
    return cut


def _manifest(pkg: HwpxPackage):
    return pkg.xml(HPF).find(f"{{{OPF}}}manifest") if HPF in pkg.names() else None


def _used_images(pkg: HwpxPackage) -> set[str]:
    used = set()
    for name in pkg.section_names() + ["Contents/header.xml"]:
        for img in pkg.xml(name).iter(hc("img")):
            used.add(img.get("binaryItemIDRef"))
    return used


def prune_unused_images(pkg: HwpxPackage) -> None:
    manifest = _manifest(pkg)
    if manifest is None:
        return
    used = _used_images(pkg)
    for item in list(manifest):
        href = item.get("href", "")
        if href.startswith("BinData/") and item.get("id") not in used:
            manifest.remove(item)
            pkg.remove(href)


# ---------------------------------------------------------------- 그림 가져오기
def import_images(target: HwpxPackage, src: HwpxPackage) -> dict[str, str]:
    """원본 그림 ID → 합본 그림 ID. 합본에 파일과 목록을 추가한다."""
    src_manifest, dst_manifest = _manifest(src), _manifest(target)
    if src_manifest is None:
        return {}
    if dst_manifest is None:
        raise ValueError("참고 합본에 Contents/content.hpf 가 없습니다")
    used = _used_images(src)
    numbers = [int(m.group(1)) for i in dst_manifest if (m := re.match(r"image(\d+)$", i.get("id", "")))]
    nxt = max(numbers, default=0) + 1
    mapping = {}
    for item in src_manifest:
        sid, href = item.get("id"), item.get("href", "")
        if not href.startswith("BinData/") or sid not in used:
            continue
        ext = Path(href).suffix
        new_id, new_href = f"image{nxt}", f"BinData/image{nxt}{ext}"
        nxt += 1
        target.add(new_href, src.raw(href), compress_type=src.info(href).compress_type)
        new_item = copy.deepcopy(item)
        new_item.set("id", new_id)
        new_item.set("href", new_href)
        dst_manifest.append(new_item)
        mapping[sid] = new_id
    return mapping


# ---------------------------------------------------------------- 본문 가져오기
def _strip_memos(root) -> int:
    begins = [fb for fb in root.iter(hp("fieldBegin")) if fb.get("type") == "MEMO"]
    ids = {fb.get("id") for fb in begins}
    for fb in begins:
        ctrl = fb.getparent()
        ctrl.getparent().remove(ctrl)
    for fe in list(root.iter(hp("fieldEnd"))):
        if fe.get("beginIDRef") in ids:
            ctrl = fe.getparent()
            ctrl.getparent().remove(ctrl)
    return len(begins)


def _strip_section_settings(p) -> None:
    for sec_pr in p.findall("hp:run/hp:secPr", NS):
        sec_pr.getparent().remove(sec_pr)
    for ctrl in p.findall("hp:run/hp:ctrl", NS):
        if any(child.tag in DROP_CTRL_CHILDREN for child in ctrl):
            ctrl.getparent().remove(ctrl)


class IdCounter:
    def __init__(self, start: int):
        self.n = start

    def __call__(self) -> str:
        self.n += 1
        return str(self.n)


def max_object_id(pkg: HwpxPackage) -> int:
    best = 0
    for name in pkg.section_names():
        for el in pkg.xml(name).iter():
            if el.tag in OBJECT_TAGS or el.tag == hp("fieldBegin"):
                for attr in ("id", "fieldid"):
                    v = el.get(attr, "")
                    if v.isdigit() and int(v) < 2**31:
                        best = max(best, int(v))
    return best


def import_body(src: HwpxPackage, maps: dict, bin_map: dict, new_id: IdCounter) -> tuple[list, int]:
    """원본의 모든 구역 본문 문단을 복사해 ID 를 바꾼 목록과, 지운 메모 수."""
    paras = []
    for name in src.section_names():
        for p in src.xml(name).iterfind("hp:p", NS):
            paras.append(copy.deepcopy(p))
    memos = 0
    for p in paras:
        _strip_section_settings(p)
        memos += _strip_memos(p)
        for arr in p.iter(hp("linesegarray")):
            arr.getparent().remove(arr)
    field_ids: dict[str, tuple[str, str]] = {}
    for p in paras:
        for el in p.iter():
            if not isinstance(el.tag, str):
                continue
            for attr, kind in REF_ATTRS.items():
                v = el.get(attr)
                if v is not None and v != NONE_REF:
                    el.set(attr, maps[kind].get(v, v))
            if el.tag == hc("img") and el.get("binaryItemIDRef") in bin_map:
                el.set("binaryItemIDRef", bin_map[el.get("binaryItemIDRef")])
            if el.tag in OBJECT_TAGS and el.get("id"):
                el.set("id", new_id())
            if el.tag == hp("fieldBegin"):
                old = (el.get("id"), el.get("fieldid"))
                field_ids[old[0]] = (new_id(), new_id())
                el.set("id", field_ids[old[0]][0])
                el.set("fieldid", field_ids[old[0]][1])
    for p in paras:
        for fe in p.iter(hp("fieldEnd")):
            if fe.get("beginIDRef") in field_ids:
                begin, fid = field_ids[fe.get("beginIDRef")]
                fe.set("beginIDRef", begin)
                fe.set("fieldid", fid)
    if paras:
        paras[0].set("pageBreak", "1")
    return paras, memos


def append_document(target: HwpxPackage, merger: HeaderMerger, src_path: Path, src: HwpxPackage,
                    new_id: IdCounter) -> MergedDoc:
    bin_map = import_images(target, src)
    maps = merger.import_header(src.header, bin_map)
    paras, memos = import_body(src, maps, bin_map, new_id)
    sec = body_section(target)
    for p in paras:
        sec.append(p)
    return MergedDoc(path=src_path, paragraphs=len(paras), images=len(bin_map), memos_removed=memos)


def set_preview_text(target: HwpxPackage, text: str) -> None:
    if "Preview/PrvText.txt" in target.names():
        target.add("Preview/PrvText.txt", text.replace("\n", "\r\n").encode("utf-8"),
                   compress_type=target.info("Preview/PrvText.txt").compress_type)


