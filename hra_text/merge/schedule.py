"""일정표 쪽 자동 수정.

참고 합본의 일정표를 그대로 둔 뒤:
- 날짜(표지·일정표 머리 칸): --date 로 바꾸거나, 없으면 빈칸 자리표시로
- 세션(■ 고전 명작 / ■ 특강 / ■ 경영서 리뷰 / ■ 케이스 스터디)별 표: 도서명(제목) 칸만 채우고
  발표자 칸은 비운다. 특강 내용 줄도 비운다.
- 해당 문서가 하나도 없는 세션(예: 경영서가 없는 날)은 세션째 지운다. 특강은 문서가 없으므로 늘 둔다.
"""

from __future__ import annotations

import copy
import re

from ..hwpx.ns import NS, hp
from ..hwpx.section import t_text

RE_DATE = re.compile(r"\d{4}\.\s*\d{1,2}\.\s*\d{1,2}\.\s*\([월화수목금토일]\)")
DATE_PLACEHOLDER = "20  .   .   .(  )"
# 세션 이름 → 문서 종류
SESSION_KIND = (("고전", "classic"), ("경영서", "business"), ("케이스", "case"), ("기업", "case"), ("특강", "lecture"))


def para_text(p) -> str:
    return "".join(t_text(t) for t in p.iter(hp("t")))


def replace_dates(root, date: str | None) -> int:
    n = 0
    for t in root.iter(hp("t")):
        if t.text and RE_DATE.search(t.text):
            t.text = RE_DATE.sub(date or DATE_PLACEHOLDER, t.text)
            n += 1
    return n


def _cells(tbl) -> dict[tuple[int, int], object]:
    out = {}
    for tc in tbl.iterfind("hp:tr/hp:tc", NS):
        a = tc.find("hp:cellAddr", NS)
        out[(int(a.get("rowAddr")), int(a.get("colAddr")))] = tc
    return out


def set_cell_lines(tc, lines: list[str]) -> None:
    """셀 글자를 lines 로 바꾼다. 첫 문단의 모양을 본떠 줄마다 문단 하나."""
    sub = tc.find("hp:subList", NS)
    paras = sub.findall("hp:p", NS)
    template = copy.deepcopy(paras[0])
    for p in paras:
        sub.remove(p)
    for arr in template.iter(hp("linesegarray")):
        arr.getparent().remove(arr)
    runs = template.findall("hp:run", NS)
    for r in runs[1:]:
        template.remove(r)
    run = runs[0] if runs else template.makeelement(hp("run"), charPrIDRef="0")
    for child in list(run):
        run.remove(child)
    if not runs:
        template.append(run)
    for line in lines or [""]:
        p = copy.deepcopy(template)
        r = p.find("hp:run", NS)
        t = r.makeelement(hp("t"))
        t.text = line or None
        r.append(t)
        sub.append(p)


def _sessions(sec):
    """일정표 문단을 세션 단위로: [(종류, [문단...]), ...]. 첫 ■ 앞(머리 칸)은 ('head', ...)."""
    sessions, current = [], ("head", [])
    for p in sec.findall("hp:p", NS):
        text = para_text(p).strip()
        if text.startswith("■"):
            sessions.append(current)
            kind = next((k for word, k in SESSION_KIND if word in text), "other")
            current = (kind, [p])
        else:
            current[1].append(p)
    sessions.append(current)
    return sessions


def fill_schedule(sec, titles: dict[str, list[str]]) -> dict[str, str]:
    """titles: {'classic': [...], 'business': [...], 'case': [...]}. 세션별 처리 결과를 돌려준다."""
    report = {}
    for kind, paras in _sessions(sec):
        if kind in ("head", "other"):
            continue
        if kind == "lecture":
            for p in paras[1:]:
                if para_text(p).strip():
                    for t in p.iter(hp("t")):
                        t.text = None
                        for c in list(t):
                            t.remove(c)
            report[kind] = "내용 비움"
            continue
        names = titles.get(kind, [])
        if not names:
            for p in paras:
                p.getparent().remove(p)
            report[kind] = "문서 없음 → 세션 삭제"
            continue
        tables = [t for p in paras for t in p.iterfind("hp:run/hp:tbl", NS)]
        for tbl in tables:
            cells = _cells(tbl)
            rows = sorted({r for r, _ in cells})
            last_col = max(c for _, c in cells)
            for (r, c), tc in cells.items():
                if r == rows[0]:
                    continue  # 머리행
                if c == 0:
                    set_cell_lines(tc, names if r == rows[1] else [""])
                elif c == last_col:
                    set_cell_lines(tc, [""])  # 발표자
        report[kind] = f"도서명 {len(names)}개"
    return report
