"""명령행 진입점: hra-merge (합본 제작, 서식 교정과 별개)

  hra-merge 파일1 파일2 ... --cover 참고합본.hwpx [-o output/합본.hwpx] [--date "2026.11.07.(토)"]
  hra-merge --order 합본순서.txt --cover 참고합본.hwpx
  hra-merge --list 합본.hwpx                                  # 합본 속 문서 목록(번호)
  hra-merge 늦은파일.hwpx --insert 합본.hwpx [--at 3] [-o …]   # 3번 문서 자리에 끼워 넣기(없으면 맨 뒤)

파일은 적은 순서대로 합친다. 폴더를 주면 종류(고전·에세이·경영서·기업실무) → 파일 이름 순.
--cover 가 지난 합본(일정표 뒤에 옛 문서)이면 일정표를 새로 채우고, 표지·일정표만 있는 파일이면
이미 채운 표지로 보고 일정표를 받은 그대로 둔다 (날짜는 --date 를 줄 때만 바꾼다).
"""

from __future__ import annotations

import argparse
import re
import sys
import tempfile
from pathlib import Path

from .. import __version__
from ..document import Document
from ..hwpx.package import HwpxPackage
from ..rules.r20_category import category_from_filename
from .core import (IdCounter, MergeResult, append_document, body_section, keep_schedule_only,
                   max_object_id, refresh_preview)
from .insert import insert_documents, list_documents
from .headermap import HeaderMerger
from .schedule import fill_schedule, replace_dates

KIND_ORDER = ("classic", "essay", "business", "case", "other")
KIND_NAMES = {"classic": "고전", "essay": "에세이", "business": "경영서", "case": "기업실무", "other": "기타",
              "lecture": "특강"}


def doc_kind_and_title(doc: Document) -> tuple[str, str]:
    category = next((p.text for p in doc.paras if p.role == "CATEGORY"), "")
    if not category:  # ■ 분류 줄이 비어 있으면 파일 이름으로 (FORMAT_RULES R20)
        category = category_from_filename(doc.source) or ""
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
    ap.add_argument("--cover", type=Path, help="표지·일정표를 가져올 참고 합본 (hwpx)")
    ap.add_argument("-o", "--output", type=Path, help="결과 파일 (기본: output/합본.hwpx, 끼워 넣기는 합본이름_추가.hwpx)")
    ap.add_argument("--date", help='표지·일정표 날짜 (예: "2026.11.07.(토)"). 없으면 빈칸')
    ap.add_argument("--list", type=Path, metavar="합본", help="이미 만든 합본 속 문서 목록을 보여 준다")
    ap.add_argument("--insert", type=Path, metavar="합본", help="이미 만든 합본에 파일을 끼워 넣는다 (일정표는 그대로)")
    ap.add_argument("--at", type=int, help="--insert: 몇 번째 문서 자리에 넣을지 (--list 의 번호, 없으면 맨 뒤)")
    args = ap.parse_args(argv)

    if args.list:
        print_documents(HwpxPackage.open(args.list))
        return 0
    if args.insert:
        if args.cover or args.date:
            ap.error("--insert 에는 --cover·--date 를 쓰지 않습니다 (합본의 표지·일정표를 그대로 둡니다)")
        return insert_main(ap, args)
    if not args.cover:
        ap.error("--cover(참고 합본)가 필요합니다")
    args.output = args.output or Path("output/합본.hwpx")

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
        filled_cover = keep_schedule_only(target) == 0  # 옛 문서가 없으면 이미 채운 표지
        if args.date or not filled_cover:
            for name in target.section_names():
                replace_dates(target.xml(name), args.date)
        if filled_cover:
            schedule = None
        else:
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
        refresh_preview(target)
        out = target.save(args.output)

    print(f"합본: {out}")
    if schedule is None:
        print("일정표: 받은 표지 그대로 (표지·일정표만 있는 파일)")
        print(f"날짜: {args.date or '받은 표지 그대로'}")
    else:
        print("일정표: " + ", ".join(f"{KIND_NAMES.get(k, k)} {v}" for k, v in schedule.items()))
        print(f"날짜: {args.date or '빈칸 (직접 입력)'}")
    for i, ((f, _, kind, title), md) in enumerate(zip(docs, result.docs), 1):
        print(f"{i:>2}. [{KIND_NAMES[kind]}] {f.name}  — 제목 '{title}', 문단 {md.paragraphs}, "
              f"그림 {md.images}, 뺀 메모 {md.memos_removed}")
    return 0


def print_documents(pkg: HwpxPackage) -> None:
    entries = list_documents(pkg)
    print(f"합본 속 문서 {len(entries)}개 (--at 번호를 주면 그 문서 앞에 들어갑니다, {len(entries) + 1} = 맨 뒤)")
    for e in entries:
        print(f"{e.number:>2}. {e.category}  {e.title}")


def insert_main(ap, args) -> int:
    files = read_order(args.order) if args.order else collect(args.inputs)
    if not files:
        ap.error("넣을 파일이 없습니다")
    missing = [f for f in files if not f.exists()]
    if missing:
        ap.error("파일을 찾을 수 없습니다: " + ", ".join(map(str, missing)))
    out = args.output or args.insert.with_name(f"{args.insert.stem}_추가.hwpx")
    if out.resolve() == args.insert.resolve():
        ap.error("받은 합본은 덮어쓰지 않습니다. -o 로 다른 이름을 주세요")
    with tempfile.TemporaryDirectory(prefix="hra_merge_") as work:
        docs = [Document.open(f, work_dir=Path(work)) for f in files]
        target = HwpxPackage.open(args.insert)
        try:
            merged = insert_documents(target, [(f, d.pkg) for f, d in zip(files, docs)], args.at)
        except ValueError as e:
            ap.error(str(e))
        refresh_preview(target)
        out = target.save(out)
    print(f"합본: {out}")
    for f, d, md in zip(files, docs, merged):
        kind, title = doc_kind_and_title(d)
        print(f"넣음: [{KIND_NAMES[kind]}] {f.name}  — 제목 '{title}', 문단 {md.paragraphs}, 그림 {md.images}, "
              f"뺀 메모 {md.memos_removed}")
    print_documents(HwpxPackage.open(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
