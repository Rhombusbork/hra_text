"""명령행 진입점: hra-merge (합본 제작, 서식 교정과 별개)

  hra-merge 파일1 파일2 ... --cover 참고합본.hwpx [-o output/합본.hwpx] [--date "2026.11.07.(토)"]
  hra-merge --order 합본순서.txt --cover 참고합본.hwpx

파일은 적은 순서대로 합친다. 폴더를 주면 종류(고전·에세이·경영서·기업실무) → 파일 이름 순.
"""

from __future__ import annotations

import argparse
import re
import sys
import tempfile
from pathlib import Path

from .. import __version__
from ..document import Document
from ..hwpx.ns import NS as NS_P
from ..hwpx.package import HwpxPackage
from .core import (IdCounter, MergeResult, append_document, body_section, keep_schedule_only,
                   max_object_id, set_preview_text)
from .headermap import HeaderMerger
from .schedule import fill_schedule, para_text, replace_dates

KIND_ORDER = ("classic", "essay", "business", "case", "other")
KIND_NAMES = {"classic": "고전", "essay": "에세이", "business": "경영서", "case": "기업실무", "other": "기타"}


def doc_kind_and_title(doc: Document) -> tuple[str, str]:
    category = next((p.text for p in doc.paras if p.role == "CATEGORY"), "")
    has_h1 = any(p.role == "H1" for p in doc.paras)
    if "고전" in category:
        kind = "classic" if has_h1 else "essay"
    elif "경영" in category:
        kind = "business"
    elif "기업" in category:
        kind = "case"
    else:
        kind = "other"
    role = "READING_TITLE" if kind == "essay" else "COVER_TITLE"
    title = " ".join(p.text.strip() for p in doc.paras if p.role == role and p.text.strip())
    return kind, re.sub(r"\s+", " ", title).strip()


def read_order(path: Path) -> list[Path]:
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            p = Path(line)
            out.append(p if p.is_absolute() or p.exists() else path.parent / p)
    return out


def collect(inputs: list[str]) -> list[Path]:
    files: list[Path] = []
    for item in map(Path, inputs):
        if item.is_dir():
            files += sorted(p for p in item.iterdir() if p.suffix.lower() in (".hwp", ".hwpx"))
        else:
            files.append(item)
    return files


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="hra-merge", description="HRA 합본 만들기 (메모는 빼고, 서식 교정 없이 합친다)")
    ap.add_argument("--version", action="version", version=f"hra-merge {__version__}")
    ap.add_argument("inputs", nargs="*", help="합칠 hwp/hwpx 파일(적은 순서대로) 또는 폴더")
    ap.add_argument("--order", type=Path, help="합칠 파일 목록 (한 줄에 하나, # 주석)")
    ap.add_argument("--cover", type=Path, required=True, help="표지·일정표를 가져올 참고 합본 (hwpx)")
    ap.add_argument("-o", "--output", type=Path, default=Path("output/합본.hwpx"))
    ap.add_argument("--date", help='표지·일정표 날짜 (예: "2026.11.07.(토)"). 없으면 빈칸')
    args = ap.parse_args(argv)

    if args.order:
        files = read_order(args.order)
    else:
        files = collect(args.inputs)
    if not files:
        ap.error("합칠 파일이 없습니다")
    missing = [f for f in files if not f.exists()]
    if missing:
        ap.error("파일을 찾을 수 없습니다: " + ", ".join(map(str, missing)))

    with tempfile.TemporaryDirectory(prefix="hra_merge_") as work:
        docs = []
        for f in files:
            d = Document.open(f, work_dir=Path(work))
            kind, title = doc_kind_and_title(d)
            docs.append((f, d, kind, title))
        if not args.order and any(Path(i).is_dir() for i in args.inputs):
            docs.sort(key=lambda x: (KIND_ORDER.index(x[2]), x[0].name))

        target = HwpxPackage.open(args.cover)
        keep_schedule_only(target)
        for name in target.section_names():
            replace_dates(target.xml(name), args.date)
        titles: dict[str, list[str]] = {}
        for _, _, kind, title in docs:
            if kind in ("classic", "business", "case") and title and title not in titles.get(kind, []):
                titles.setdefault(kind, []).append(title)
        schedule = fill_schedule(body_section(target), titles)

        merger = HeaderMerger(target.header)
        new_id = IdCounter(max_object_id(target))
        result = MergeResult()
        for f, d, kind, title in docs:
            result.docs.append(append_document(target, merger, f, d.pkg, new_id))
        preview = "\n".join(para_text(p) for name in target.section_names()
                            for p in target.xml(name).iterfind("hp:p", NS_P))[:2000]
        set_preview_text(target, preview)
        out = target.save(args.output)

    print(f"합본: {out}")
    print("일정표: " + ", ".join(f"{KIND_NAMES.get(k, k)} {v}" for k, v in schedule.items()))
    print(f"날짜: {args.date or '빈칸 (직접 입력)'}")
    for i, ((f, _, kind, title), md) in enumerate(zip(docs, result.docs), 1):
        print(f"{i:>2}. [{KIND_NAMES[kind]}] {f.name}  — 제목 '{title}', 문단 {md.paragraphs}, "
              f"그림 {md.images}, 뺀 메모 {md.memos_removed}")
    return 0




if __name__ == "__main__":
    sys.exit(main())
