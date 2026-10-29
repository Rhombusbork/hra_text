"""가져오는 문서의 header 항목을 합본 header 로 옮기고, 옛 ID → 새 ID 지도를 만든다.

참조 관계 (옮기는 순서):
  글꼴 → 테두리/배경(그림 참조) → 글자 모양(글꼴·테두리) → 탭 → 번호 매기기·글머리표(글자 모양)
  → 문단 모양(탭·번호·글머리표·테두리) → 스타일(문단·글자 모양, 다음 스타일)
같은 내용(정규형)이 이미 합본에 있으면 그 ID를 쓰고, 없으면 새 ID로 추가한다.
스타일은 이름이 같으면 합본 스타일을 쓴다.
"""

from __future__ import annotations

import copy

from lxml import etree

from ..hwpx.ns import NS, hc

NONE_REF = "4294967295"  # '참조 없음'
LANG_ATTRS = ("hangul", "latin", "hanja", "japanese", "other", "symbol", "user")
LANG_OF_ATTR = {a: a.upper() for a in LANG_ATTRS}


def _canonical(el) -> bytes:
    c = copy.deepcopy(el)
    c.attrib.pop("id", None)
    return etree.tostring(c, method="c14n")


class _Table:
    """header 의 한 목록 (예: hh:charProperties/hh:charPr)."""

    def __init__(self, root, container: str, item: str):
        self.container = root.find(f".//hh:{container}", NS)
        if self.container is None:
            ref_list = root.find("hh:refList", NS)
            self.container = etree.SubElement(ref_list, f"{{{NS['hh']}}}{container}", itemCnt="0")
        self.item = item
        self.by_key = {_canonical(e): e.get("id") for e in self.items()}

    def items(self):
        return self.container.findall(f"hh:{self.item}", NS)

    def put(self, el) -> str:
        key = _canonical(el)
        if key in self.by_key:
            return self.by_key[key]
        ids = [int(e.get("id")) for e in self.items()]
        new_id = str(max(ids) + 1 if ids else 0)
        new = copy.deepcopy(el)
        new.set("id", new_id)
        self.container.append(new)
        self.container.set("itemCnt", str(len(self.items())))
        self.by_key[key] = new_id
        return new_id


class HeaderMerger:
    def __init__(self, target_root):
        self.root = target_root
        self.fonts = {ff.get("lang"): ff for ff in target_root.iterfind(".//hh:fontfaces/hh:fontface", NS)}
        self.border = _Table(target_root, "borderFills", "borderFill")
        self.char = _Table(target_root, "charProperties", "charPr")
        self.tab = _Table(target_root, "tabProperties", "tabPr")
        self.numbering = _Table(target_root, "numberings", "numbering")
        self.bullet = _Table(target_root, "bullets", "bullet")
        self.para = _Table(target_root, "paraProperties", "paraPr")
        self.styles = {s.get("name"): s.get("id") for s in target_root.iterfind(".//hh:styles/hh:style", NS)}
        self.style_container = target_root.find(".//hh:styles", NS)

    # ---- 글꼴 ----
    def _font(self, lang: str, src_font) -> str:
        ff = self.fonts[lang]
        for f in ff.iterfind("hh:font", NS):
            if f.get("face") == src_font.get("face"):
                return f.get("id")
        new = copy.deepcopy(src_font)
        new.set("id", str(len(ff.findall("hh:font", NS))))
        ff.append(new)
        ff.set("fontCnt", str(len(ff.findall("hh:font", NS))))
        return new.get("id")

    def import_header(self, src_root, bin_map: dict[str, str]) -> dict[str, dict[str, str]]:
        m: dict[str, dict[str, str]] = {k: {} for k in
                                        ("font", "border", "char", "tab", "numbering", "bullet", "para", "style")}
        fonts: dict[tuple[str, str], str] = {}
        for ff in src_root.iterfind(".//hh:fontfaces/hh:fontface", NS):
            lang = ff.get("lang")
            for f in ff.iterfind("hh:font", NS):
                fonts[(lang, f.get("id"))] = self._font(lang, f)

        for bf in src_root.iterfind(".//hh:borderFills/hh:borderFill", NS):
            el = copy.deepcopy(bf)
            for img in el.iter(hc("img")):
                ref = img.get("binaryItemIDRef")
                if ref in bin_map:
                    img.set("binaryItemIDRef", bin_map[ref])
            m["border"][bf.get("id")] = self.border.put(el)

        def ref(kind, value):
            return value if value in (None, NONE_REF) else m[kind].get(value, value)

        for cp in src_root.iterfind(".//hh:charProperties/hh:charPr", NS):
            el = copy.deepcopy(cp)
            if el.get("borderFillIDRef"):
                el.set("borderFillIDRef", ref("border", el.get("borderFillIDRef")))
            fr = el.find("hh:fontRef", NS)
            if fr is not None:
                for attr in LANG_ATTRS:
                    if fr.get(attr) is not None:
                        fr.set(attr, fonts.get((LANG_OF_ATTR[attr], fr.get(attr)), fr.get(attr)))
            m["char"][cp.get("id")] = self.char.put(el)

        for tp in src_root.iterfind(".//hh:tabProperties/hh:tabPr", NS):
            m["tab"][tp.get("id")] = self.tab.put(tp)

        for kind, xpath in (("numbering", ".//hh:numberings/hh:numbering"), ("bullet", ".//hh:bullets/hh:bullet")):
            table = getattr(self, kind)
            for n in src_root.iterfind(xpath, NS):
                el = copy.deepcopy(n)
                for head in el.iter(f"{{{NS['hh']}}}paraHead"):
                    if head.get("charPrIDRef"):
                        head.set("charPrIDRef", ref("char", head.get("charPrIDRef")))
                for img in el.iter(hc("img")):
                    if img.get("binaryItemIDRef") in bin_map:
                        img.set("binaryItemIDRef", bin_map[img.get("binaryItemIDRef")])
                m[kind][n.get("id")] = table.put(el)

        for pp in src_root.iterfind(".//hh:paraProperties/hh:paraPr", NS):
            el = copy.deepcopy(pp)
            if el.get("tabPrIDRef"):
                el.set("tabPrIDRef", ref("tab", el.get("tabPrIDRef")))
            heading = el.find("hh:heading", NS)
            if heading is not None and heading.get("type") in ("NUMBER", "OUTLINE", "BULLET"):
                kind = "bullet" if heading.get("type") == "BULLET" else "numbering"
                if heading.get("idRef") not in (None, "0"):
                    heading.set("idRef", ref(kind, heading.get("idRef")))
            for border in el.iter(f"{{{NS['hh']}}}border"):
                if border.get("borderFillIDRef"):
                    border.set("borderFillIDRef", ref("border", border.get("borderFillIDRef")))
            m["para"][pp.get("id")] = self.para.put(el)

        src_styles = list(src_root.iterfind(".//hh:styles/hh:style", NS))
        added = []
        for st in src_styles:
            name = st.get("name")
            if name in self.styles:
                m["style"][st.get("id")] = self.styles[name]
                continue
            el = copy.deepcopy(st)
            el.set("paraPrIDRef", ref("para", el.get("paraPrIDRef")))
            el.set("charPrIDRef", ref("char", el.get("charPrIDRef")))
            new_id = str(max(int(s.get("id")) for s in self.style_container.findall("hh:style", NS)) + 1)
            el.set("id", new_id)
            self.style_container.append(el)
            self.styles[name] = new_id
            m["style"][st.get("id")] = new_id
            added.append(el)
        for el in added:  # 다음 스타일은 모든 스타일 지도가 생긴 뒤
            el.set("nextStyleIDRef", m["style"].get(el.get("nextStyleIDRef"), el.get("id")))
        self.style_container.set("itemCnt", str(len(self.style_container.findall("hh:style", NS))))
        return m
