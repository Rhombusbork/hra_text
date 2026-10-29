"""문서 = hwpx 패키지 + header 레지스트리 + 문단 목록."""

from __future__ import annotations

import tempfile
from pathlib import Path

from .convert import hwp_to_hwpx
from .hwpx.header import Header
from .hwpx.package import HwpxPackage
from .hwpx.section import Para, iter_paragraphs


class Document:
    def __init__(self, pkg: HwpxPackage, source: Path):
        self.pkg = pkg
        self.source = source  # 사용자가 준 원본 경로 (hwp 일 수 있음)
        self.header = Header(pkg.header)
        self.paras: list[Para] = []
        self.touched: set = set()  # 수정한 문단 요소 (저장 전 레이아웃 캐시 삭제)
        self.table_kinds: dict[int, str] = {}
        self.reload()

    @classmethod
    def open(cls, path: Path | str, *, work_dir: Path | None = None) -> "Document":
        """hwpx 는 그대로, hwp 는 work_dir(기본: 임시 폴더)에 hwpx 사본을 만든 뒤 연다."""
        path = Path(path)
        if path.suffix.lower() == ".hwp":
            work_dir = Path(work_dir or tempfile.mkdtemp(prefix="hra_"))
            path_hwpx = hwp_to_hwpx(path, work_dir / (path.stem + ".hwpx"))
            return cls(HwpxPackage.open(path_hwpx), path)
        return cls(HwpxPackage.open(path), path)

    def reload(self) -> None:
        """XML 구조를 바꾼 뒤(문단 추가/삭제) 문단 목록을 다시 만든다."""
        from .classify import classify

        self.paras = iter_paragraphs(self.pkg.sections())
        classify(self)

    def save(self, dst: Path | str) -> Path:
        dst = Path(dst).resolve()
        if dst == self.source.resolve():
            raise ValueError("원본을 덮어쓸 수 없습니다.")
        from .hwpx.edit import drop_layout_cache

        drop_layout_cache(self)
        return self.pkg.save(dst)
