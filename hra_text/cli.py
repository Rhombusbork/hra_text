"""명령행 진입점: hra-fix"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .convert import ConvertError, hwp_to_hwpx


def _cmd_convert(args: argparse.Namespace) -> int:
    out_dir = Path(args.output)
    failed = 0
    for src in _collect(args.inputs, ".hwp"):
        dst = out_dir / (src.stem + ".hwpx")
        try:
            hwp_to_hwpx(src, dst)
            print(f"OK   {src.name} -> {dst}")
        except ConvertError as e:
            failed += 1
            print(f"FAIL {e}", file=sys.stderr)
    return 1 if failed else 0


def _cmd_dump(args: argparse.Namespace) -> int:
    from .document import Document
    from .dump import render

    for src in _collect(args.inputs, ".hwp") + _collect(args.inputs, ".hwpx"):
        doc = Document.open(src)
        text = render(doc, width=args.width, include_skip=args.all)
        if args.output:
            out = Path(args.output) / (src.stem + "_dump.txt")
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(text + "\n", encoding="utf-8")
            print(f"OK   {src.name} -> {out}")
        else:
            print(f"===== {src.name}")
            print(text)
    return 0


def _cmd_fix(args: argparse.Namespace) -> int:
    from .fixer import fix_document

    only = {r.strip().upper() for r in args.rules.split(",")} if args.rules else None
    for src in _collect(args.inputs, ".hwp") + _collect(args.inputs, ".hwpx"):
        r = fix_document(src, Path(args.output), author=args.author, only=only, memo=not args.no_memo)
        names = " + ".join(p.name for p in (r.feedback, r.clean) if p is not None)
        print(f"OK   {src.name} -> {names}  (변경 {r.changes}건, 문단 {r.paragraphs}개, 메모 {r.memos}개)")
    return 0


def _cmd_compare(args: argparse.Namespace) -> int:
    from .compare import compare, render
    from .document import Document

    diffs, stats = compare(Document.open(args.ours), Document.open(args.reference))
    print(render(diffs, stats, examples=args.examples))
    return 0


def _collect(inputs: list[str], suffix: str) -> list[Path]:
    files: list[Path] = []
    for item in map(Path, inputs):
        if item.is_dir():
            files += sorted(p for p in item.iterdir() if p.suffix.lower() == suffix)
        elif item.suffix.lower() == suffix:
            files.append(item)
    return files


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="hra-fix", description="HRA 보고서 서식 자동 교정")
    parser.add_argument("--version", action="version", version=f"hra-fix {__version__}")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("convert", help="hwp → hwpx 변환 (원본은 그대로 둠)")
    p.add_argument("inputs", nargs="+", help="hwp 파일 또는 폴더")
    p.add_argument("-o", "--output", default="output", help="출력 폴더 (기본: output)")
    p.set_defaults(func=_cmd_convert)

    p = sub.add_parser("dump", help="문단별 역할·서식 표 출력")
    p.add_argument("inputs", nargs="+", help="hwp/hwpx 파일 또는 폴더")
    p.add_argument("-o", "--output", help="지정하면 폴더에 <이름>_dump.txt 로 저장")
    p.add_argument("--width", type=int, default=50, help="내용 표시 글자 수")
    p.add_argument("--all", action="store_true", help="메모·머리말 등(SKIP)도 표시")
    p.set_defaults(func=_cmd_dump)

    p = sub.add_parser("fix", help="양식에 맞게 수정: <이름>_피드백.hwpx(메모) + <이름>_수정본.hwpx(메모 없음) (원본 유지)")
    p.add_argument("inputs", nargs="+", help="hwp/hwpx 파일 또는 폴더")
    p.add_argument("-o", "--output", default="output", help="출력 폴더 (기본: output)")
    p.add_argument("--rules", help="적용할 규칙만 (예: R01,R03). 기본: 구현된 전부")
    p.add_argument("--no-memo", action="store_true", help="메모 단 _피드백 파일은 만들지 않고 _수정본만")
    p.add_argument("--author", default="neoju", help="메모 작성자 이름 (기본: neoju)")
    p.set_defaults(func=_cmd_fix)

    p = sub.add_parser("compare", help="우리 결과와 사람이 고친 수정본의 서식 비교")
    p.add_argument("ours", help="우리 결과 (hwpx)")
    p.add_argument("reference", help="사람이 고친 수정본 (hwp/hwpx)")
    p.add_argument("--examples", type=int, default=3, help="항목별 예시 수")
    p.set_defaults(func=_cmd_compare)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
