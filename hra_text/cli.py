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

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
