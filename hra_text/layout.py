"""문단 줄 수 추정 (R18-f). 저장된 줄 나눔 기록(linesegarray)은 다른 도구로 만든 파일에서 믿을 수 없고
저장할 때 지우므로, 글자 폭으로 계산한다. 한글로 저장된 문서 2개의 본문 742문단에서 '3줄 이상' 판단이
모두 맞았다 (줄 수 자체는 98% 일치)."""

from __future__ import annotations

import math
import unicodedata
from typing import TYPE_CHECKING

from .hwpx.ns import NS

if TYPE_CHECKING:
    from .document import Document
    from .hwpx.section import Para

# 글자 폭 (글자 크기 대비 비율)
WIDE, SPACE, DIGIT, UPPER, LOWER, OTHER = 1.0, 0.3, 0.55, 0.62, 0.52, 0.4
FILL = 0.95  # 낱말 단위 줄바꿈 여유: 줄 폭의 95%만 채운다고 본다


def _char_factor(ch: str) -> float:
    if unicodedata.east_asian_width(ch) in ("W", "F") or "가" <= ch <= "힣":
        return WIDE
    if ch == " ":
        return SPACE
    if ch.isdigit():
        return DIGIT
    if ch.isupper():
        return UPPER
    if ch.isalpha():
        return LOWER
    return OTHER


def _line_width(doc: "Document", p: "Para") -> tuple[float, float]:
    """(줄 폭, 첫 줄 들여쓰기) HWPUNIT(1pt=100). 용지는 그 문단 구역의 정의를 쓴다."""
    secs = doc.pkg.sections()
    sec = secs[min(p.section, len(secs) - 1)]
    page = sec.find(".//hp:secPr/hp:pagePr", NS)
    width = 59528 - 8504 * 2  # A4, 좌우 30mm (구역 정의가 없을 때)
    if page is not None:
        m = page.find("hp:margin", NS)
        width = int(page.get("width")) - int(m.get("left", 0)) - int(m.get("right", 0))
    margins = doc.header.para(p.para_id).margins_pt
    width -= ((margins.get("left") or 0) + (margins.get("right") or 0)) * 100
    return width, (margins.get("intent") or 0) * 100


def estimate_lines(doc: "Document", p: "Para") -> int:
    """문단이 차지할 줄 수 추정 (줄바꿈 문자로 나뉜 줄은 따로 센다)."""
    width, indent = _line_width(doc, p)
    usable = width * FILL
    total, cur, first = 0, 0.0, True
    for r in p.runs:
        c = doc.header.char(r.char_id)
        size = c.size_pt * 100 * c.ratio / 100
        for ch in r.text:
            if ch == "\n":
                total += max(1, math.ceil((cur + (indent if first else 0)) / usable))
                cur, first = 0.0, False
                continue
            cur += size * _char_factor(ch) + size * c.spacing / 100
    total += max(1, math.ceil((cur + (indent if first else 0)) / usable))
    return total
