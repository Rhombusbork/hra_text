"""한 파일 서식 교정 → 결과 파일들. 명령행(hra-fix fix)·창(HRA_Tool)·메일 자동 교정이 모두 이것을 쓴다.

결과 (같은 수정, 메모만 다름):
  {이름}_피드백.hwpx   고친 곳마다 메모 (확인용)
  {이름}_수정본.hwpx   메모 없음 (최종본 — 합본에 쓰는 파일). 원래 문서에 있던 메모도 지운다.
  {이름}_변경내역.txt  무엇을 고쳤는지 목록
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path

FEEDBACK_SUFFIX = "_피드백"
CLEAN_SUFFIX = "_수정본"
REPORT_SUFFIX = "_변경내역"


@dataclass
class FixResult:
    feedback: Path | None  # 메모 없이 만들라고 하면 None
    clean: Path
    report: Path
    changes: int
    memos: int
    paragraphs: int


def unique_path(path: Path) -> Path:
    """같은 이름이 있으면 '이름(2).hwpx' 처럼 비어 있는 이름."""
    if not path.exists():
        return path
    for i in range(2, 1000):
        cand = path.with_name(f"{path.stem}({i}){path.suffix}")
        if not cand.exists():
            return cand
    raise FileExistsError(path)


def output_paths(src: Path, out_dir: Path, *, unique: bool = False) -> tuple[Path, Path, Path]:
    pick = unique_path if unique else (lambda p: p)
    return (pick(out_dir / f"{src.stem}{FEEDBACK_SUFFIX}.hwpx"),
            pick(out_dir / f"{src.stem}{CLEAN_SUFFIX}.hwpx"),
            pick(out_dir / f"{src.stem}{REPORT_SUFFIX}.txt"))


def fix_document(src: Path, out_dir: Path, *, author: str = "neoju", only: set[str] | None = None,
                 memo: bool = True, unique: bool = False) -> FixResult:
    from .document import Document
    from .engine import run_rules
    from .hwpx.memo import strip_memos
    from .memo import add_memos
    from .report import render

    src, out_dir = Path(src), Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    feedback_path, clean_path, report_path = output_paths(src, out_dir, unique=unique)
    with tempfile.TemporaryDirectory(prefix="hra_fix_") as work:
        doc = Document.open(src, work_dir=Path(work))
        changes = run_rules(doc, only)
        n_paras = len({id(c.para_el) for c in changes})
        memos = 0
        feedback = None
        if memo:
            memos = add_memos(doc, changes, author=author)
            feedback = doc.save(feedback_path)
        # 같은 문서에서 메모만 모두 지워 최종본으로
        for sec in doc.pkg.sections():
            _, paras = strip_memos(sec)
            doc.touched |= paras
        clean = doc.save(clean_path)
    report_path.write_text(render(changes, title=src.name, memos=memos) + "\n", encoding="utf-8")
    return FixResult(feedback=feedback, clean=clean, report=report_path, changes=len(changes),
                     memos=memos, paragraphs=n_paras)
