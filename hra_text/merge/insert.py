"""이미 만든 합본에 문서 끼워 넣기 (늦게 온 제출본).

합본 본문 구역에서 '쪽 나누기 + ■ 분류 줄' 문단을 문서 시작으로 본다 (일정표의 ■ 세션 줄은 쪽 나누기가 없다).
가져오기는 합본 만들 때와 같은 append_document 를 쓰고, 고른 문서 앞에 끼워 넣는다.
표지·일정표와 합본에서 손으로 고친 내용은 건드리지 않는다.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..hwpx.ns import NS, hp
from ..hwpx.package import HwpxPackage
from .core import IdCounter, MergedDoc, append_document, body_section, max_object_id
from .headermap import HeaderMerger
from .schedule import para_text


@dataclass
class DocEntry:
    number: int  # 1부터
    para: object  # 시작 문단(hp:p)
    category: str  # ■ 분류 줄 글자
    title: str  # 분류 줄 다음 첫 글자 줄 (표지 제목)


def _is_start(p) -> bool:
    return p.get("pageBreak") == "1" and para_text(p).strip().startswith("■")


def list_documents(pkg: HwpxPackage) -> list[DocEntry]:
    paras = body_section(pkg).findall("hp:p", NS)
    starts = [i for i, p in enumerate(paras) if i > 0 and _is_start(p)]
    out = []
    for n, i in enumerate(starts):
        end = starts[n + 1] if n + 1 < len(starts) else len(paras)
        title = next((para_text(q).strip() for q in paras[i + 1:end]
                      if q.find(f".//{hp('tbl')}") is None and para_text(q).strip()), "")
        out.append(DocEntry(n + 1, paras[i], para_text(paras[i]).strip(), title))
    return out


def insert_documents(target: HwpxPackage, docs: list[tuple[Path, HwpxPackage]], at: int | None) -> list[MergedDoc]:
    """docs 를 at 번째 문서 자리에 순서대로 넣는다 (at=None 또는 문서 수+1 이면 맨 뒤)."""
    entries = list_documents(target)
    if at is not None and not 1 <= at <= len(entries) + 1:
        raise ValueError(f"넣을 자리는 1~{len(entries) + 1} 사이여야 합니다 (합본 속 문서 {len(entries)}개)")
    before = entries[at - 1].para if at is not None and at <= len(entries) else None
    merger = HeaderMerger(target.header)
    new_id = IdCounter(max_object_id(target))
    return [append_document(target, merger, path, pkg, new_id, before=before) for path, pkg in docs]
