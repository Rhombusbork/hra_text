"""hra-write: 간단한 마크다운 원고 → 기존 hwpx 보고서를 틀로 삼아 새 hwpx 만들기.

Claude 가 한글 보고서를 쓸 때 hwpx XML 을 직접 다루지 않고(토큰 절약) 원고만 쓰게 하려는 도구다.
틀 문서의 표지(■ 분류·제목·목차·소속 표)는 그대로 두고 글자만 바꾸며, 본문은 틀 속 같은 역할의
문단(H1 표, H2, H3, H4, 본문, 출처, 소개 표)을 복제해 채운다. 서식 마무리는 이어서 `hra-fix fix` 로 한다.
원고 형식은 docs/WRITE.md.
"""

from __future__ import annotations

import argparse
import copy
import random
import re
import struct
import sys
import zipfile
from pathlib import Path

from lxml import etree

HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"
HC = "http://www.hancom.co.kr/hwpml/2011/core"
OPF = "http://www.idpf.org/2007/opf/"
XML_DECL = b'<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>'


def q(tag: str) -> str:
    p, t = tag.split(":")
    return "{%s}%s" % ({"hp": HP, "hc": HC, "opf": OPF}[p], t)


# ---------------------------------------------------------------- 원고 읽기

def parse_manuscript(text: str):
    meta, blocks = {}, []
    lines = text.splitlines()
    i = 0
    if lines and lines[0].strip() == "---":
        i = 1
        while lines[i].strip() != "---":
            k, _, v = lines[i].partition(":")
            meta[k.strip()] = v.strip()
            i += 1
        i += 1
    intro = None
    for raw in lines[i:]:
        s = raw.strip()
        if not s or s.startswith("<!--"):
            continue
        m = re.match(r"^\[소개:\s*(.+?)\s*\|\s*(.+?)\s*\]$", s)
        if m:
            intro = {"kind": "INTRO", "title": m[1], "image": m[2], "items": []}
            blocks.append(intro)
            continue
        if s == "[/소개]":
            intro = None
            continue
        if s.startswith("> "):
            item = ("SRC", s[2:].strip())
        elif s.startswith("#### "):
            item = ("H4", s[5:])
        elif s.startswith("### "):
            item = ("H3", s[4:])
        elif s.startswith("## "):
            item = ("H2", s[3:])
        elif s.startswith("# "):
            item = ("H1", s[2:])
        else:
            item = ("BODY", s)
        if intro is not None:
            intro["items"].append(item)
        else:
            blocks.append({"kind": item[0], "text": item[1]})
    return meta, blocks


# ---------------------------------------------------------------- XML 도움

def all_text_nodes(el):
    return list(el.iter(q("hp:t")))


def set_para_text(p, text: str):
    """문단(또는 표 칸 문단)의 글자를 바꾼다: 첫 run 의 첫 hp:t 에 넣고 나머지 글자는 지운다."""
    for lsa in p.findall(q("hp:linesegarray")):
        p.remove(lsa)
    ts = [t for t in p.iter(q("hp:t"))]
    if ts:
        ts[0].text = text
        for c in list(ts[0]):
            ts[0].remove(c)
        for t in ts[1:]:
            t.getparent().remove(t)
    else:
        run = p.find(q("hp:run"))
        t = etree.SubElement(run, q("hp:t"))
        t.text = text


def fresh_ids(el):
    for tag in ("hp:tbl", "hp:pic"):
        for o in el.iter(q(tag)):
            o.set("id", str(random.randint(10**9, 2 * 10**9)))
    for lsa in list(el.iter(q("hp:linesegarray"))):
        lsa.getparent().remove(lsa)


def cell_paras(tbl_para, r, c):
    for tc in tbl_para.iter(q("hp:tc")):
        a = tc.find(q("hp:cellAddr"))
        if a.get("rowAddr") == str(r) and a.get("colAddr") == str(c):
            return tc.find(q("hp:subList")), tc.find(q("hp:subList")).findall(q("hp:p"))
    raise KeyError((r, c))


def jpeg_size(data: bytes):
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return struct.unpack(">II", data[16:24])
    i = 2
    while i < len(data):
        if data[i] != 0xFF:
            i += 1
            continue
        m = data[i + 1]
        if m in (0xC0, 0xC1, 0xC2):
            h, w = struct.unpack(">HH", data[i + 5:i + 9])
            return w, h
        i += 2 + struct.unpack(">H", data[i + 2:i + 4])[0]
    raise ValueError("그림 크기를 읽지 못함")


# ---------------------------------------------------------------- 만들기

def find_text_para(top, text):
    for p in top:
        if any(text in (t.text or "") for t in all_text_nodes(p)):
            return p
    raise KeyError(text)


def build(template: Path, manuscript: Path, out: Path):
    meta, blocks = parse_manuscript(manuscript.read_text(encoding="utf-8"))
    base = manuscript.parent
    z = zipfile.ZipFile(template)
    files = {i.filename: z.read(i.filename) for i in z.infolist()}
    infos = z.infolist()
    sec = etree.fromstring(files["Contents/section0.xml"])
    hpf = etree.fromstring(files["Contents/content.hpf"])
    top = list(sec)

    # 틀 문단 고르기 (역할은 hra-fix dump 기준. 틀 문서가 바뀌면 여기 위치를 맞춘다)
    h1_idx = next(i for i, p in enumerate(top) if p.find(".//" + q("hp:tbl")) is not None
                  and re.match(r"^Ⅰ\.", "".join(t.text or "" for t in all_text_nodes(p))))
    proto = {"H1": top[h1_idx], "INTRO": top[h1_idx + 1]}
    for p in top[h1_idx:]:
        if p.find(".//" + q("hp:tbl")) is not None:
            continue
        txt = "".join(t.text or "" for t in all_text_nodes(p)).strip()
        role = ("H2" if re.match(r"^\d+\.\s", txt) else "H3" if re.match(r"^\d+\)\s", txt)
                else "H4" if re.match(r"^[①-⑳]", txt) else "SRC" if txt.startswith("출처")
                else "EMPTY" if not txt else "BODY")
        proto.setdefault(role, p)
    proto = {k: copy.deepcopy(v) for k, v in proto.items()}

    # 표지: 제목, 목차, 소속 표
    cover = top[:h1_idx]
    title_p = next(p for p in cover if p.find(".//" + q("hp:tbl")) is None
                   and "".join(t.text or "" for t in all_text_nodes(p)).strip())
    titles = [p for p in cover if p.find(".//" + q("hp:tbl")) is None
              and "".join(t.text or "" for t in all_text_nodes(p)).strip()]
    title_p = titles[1] if len(titles) > 1 else titles[0]  # [0] 은 ■ 분류
    set_para_text(title_p, meta.get("제목", ""))
    tbls = [p for p in cover if p.find(".//" + q("hp:tbl")) is not None]
    toc, info = tbls[0], tbls[-1]
    sub, ps = cell_paras(toc, 1, 0)
    for p in ps[1:]:
        sub.remove(p)
    for k, h in enumerate(b["text"] for b in blocks if b["kind"] == "H1"):
        p = ps[0] if k == 0 else copy.deepcopy(ps[0])
        set_para_text(p, h)
        if k:
            sub.append(p)
    for r, key in enumerate(["소속", "발표자", "담당교수", "발표일"]):
        if key in meta:
            sub, ps = cell_paras(info, r, 1)
            set_para_text(ps[0], meta[key])

    # 본문 지우고 새로 채우기
    for p in top[h1_idx:]:
        sec.remove(p)
    manifest = hpf.find(q("opf:manifest"))
    for it in list(manifest):
        if it.get("href", "").startswith("BinData/"):
            manifest.remove(it)
            files.pop(it.get("href"), None)
    img_no = [0]

    def add(role, text=None):
        p = copy.deepcopy(proto[role])
        fresh_ids(p)
        if text is not None:
            set_para_text(p if role != "H1" else p.find(".//" + q("hp:tc") + "//" + q("hp:p")), text)
        sec.append(p)
        return p

    prev = None
    for b in blocks:
        k = b["kind"]
        if k in ("H1", "H2", "H3", "H4", "INTRO") and prev not in (None, "H1", "H2", "H3", "H4", "INTRO", "EMPTY"):
            add("EMPTY")
        if k == "INTRO":
            p = add("INTRO")
            sub, ps = cell_paras(p, 0, 0)
            set_para_text(ps[0], b["title"])
            sub, ps = cell_paras(p, 1, 1)
            body_proto = copy.deepcopy(ps[0])
            src_proto = copy.deepcopy(ps[-1])
            for x in ps:
                sub.remove(x)
            for role, t in b["items"]:
                x = copy.deepcopy(src_proto if role == "SRC" else body_proto)
                set_para_text(x, t)
                sub.append(x)
            # 그림 바꾸기
            data = (base / b["image"]).read_bytes()
            w, h = jpeg_size(data)
            img_no[0] += 1
            iid = f"image{img_no[0]}"
            ext = Path(b["image"]).suffix.lower().lstrip(".")
            href = f"BinData/{iid}.{ext}"
            files[href] = data
            it = etree.SubElement(manifest, q("opf:item"))
            it.set("id", iid); it.set("href", href)
            it.set("media-type", "image/jpeg" if ext in ("jpg", "jpeg") else "image/png")
            it.set("isEmbeded", "1")
            manifest.append(manifest.find(q("opf:item") + "[@id='settings']"))
            pic = p.find(".//" + q("hp:pic"))
            ow, oh = w * 75, h * 75
            cw = int(pic.find(q("hp:sz")).get("width"))
            ch = round(cw * h / w)
            pic.find(q("hp:orgSz")).attrib.update(dict(width=str(ow), height=str(oh)))
            for tag in ("hp:curSz", "hp:sz"):
                pic.find(q(tag)).attrib.update(dict(width=str(cw), height=str(ch)))
            pic.find(q("hp:rotationInfo")).attrib.update(dict(centerX=str(cw // 2), centerY=str(ch // 2)))
            pic.find(q("hp:renderingInfo")).find(q("hc:scaMatrix")).attrib.update(dict(
                e1=f"{cw / ow:.6f}", e5=f"{ch / oh:.6f}"))
            rect = pic.find(q("hp:imgRect"))
            for name, (x, y) in zip(("pt0", "pt1", "pt2", "pt3"), ((0, 0), (ow, 0), (ow, oh), (0, oh))):
                rect.find(q("hc:" + name)).attrib.update(dict(x=str(x), y=str(y)))
            pic.find(q("hp:imgClip")).attrib.update(dict(left="0", right=str(ow), top="0", bottom=str(oh)))
            pic.find(q("hp:imgDim")).attrib.update(dict(dimwidth=str(ow), dimheight=str(oh)))
            pic.find(q("hc:img")).set("binaryItemIDRef", iid)
            sc = pic.find(q("hp:shapeComment"))
            if sc is not None:
                sc.text = "그림입니다."
        else:
            add("SRC" if k == "SRC" else k, b["text"])
        prev = k

    files["Contents/section0.xml"] = XML_DECL + etree.tostring(sec, encoding="UTF-8", xml_declaration=False)
    files["Contents/content.hpf"] = XML_DECL + etree.tostring(hpf, encoding="UTF-8", xml_declaration=False)
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as o:
        o.writestr(zipfile.ZipInfo("mimetype"), files.pop("mimetype"), compress_type=zipfile.ZIP_STORED)
        names = [i.filename for i in infos if i.filename in files] + [n for n in files if n not in {i.filename for i in infos}]
        for n in names:
            o.writestr(n, files[n])
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(prog="hra-write", description="마크다운 원고 → 틀 hwpx 를 복제해 보고서 hwpx 만들기")
    ap.add_argument("template", type=Path, help="틀로 쓸 hwpx (같은 종류의 잘 고쳐진 보고서)")
    ap.add_argument("manuscript", type=Path, help="원고 .md (형식: docs/WRITE.md)")
    ap.add_argument("-o", "--out", type=Path, required=True)
    a = ap.parse_args(argv)
    print(build(a.template, a.manuscript, a.out))


if __name__ == "__main__":
    sys.exit(main())
