"""문단별 역할·서식 표 (사람이 분류 결과와 서식을 확인하는 용도)."""

from __future__ import annotations

from collections import Counter

from .document import Document


def _fmt_pt(v) -> str:
    if v is None:
        return "글자"
    return f"{v:g}"


def para_rows(doc: Document, *, include_skip: bool = False) -> list[dict]:
    rows = []
    h = doc.header
    for p in doc.paras:
        if p.role == "SKIP" and not include_skip:
            continue
        ps = h.para(p.para_id)
        chars = [h.char(r.char_id) for r in p.runs if r.text.strip()] or [
            h.char(r.char_id) for r in p.runs[:1]
        ]
        sizes = sorted({c.size_pt for c in chars})
        bold = {c.bold for c in chars}
        fonts = sorted({c.fonts.get("HANGUL", "?") for c in chars})
        colors = sorted({c.text_color for c in chars} - {"#000000"})
        objs = []
        for t in p.tables:
            pos = t.find("{http://www.hancom.co.kr/hwpml/2011/paragraph}pos")
            objs.append(f"표{t.get('rowCnt')}x{t.get('colCnt')}" + ("" if pos is not None and pos.get("treatAsChar") == "1" else "(!글자취급X)"))
        for pic in p.pictures:
            pos = pic.find("{http://www.hancom.co.kr/hwpml/2011/paragraph}pos")
            objs.append("그림" + ("" if pos is not None and pos.get("treatAsChar") == "1" else "(!글자취급X)"))
        cell_fill = h.fill_color(p.cell.border_fill_id) if p.cell is not None else None
        m = ps.margins_pt
        rows.append({
            "path": p.path,
            "role": p.role,
            "style": h.style_name(p.style_id),
            "font": "/".join(fonts),
            "size": "/".join(f"{s:g}" for s in sizes),
            "bold": "B" if bold == {True} else ("b?" if len(bold) > 1 else ""),
            "color": "/".join(colors),
            "align": ps.align,
            "indent": _fmt_pt(m.get("intent")),
            "left": _fmt_pt(m.get("left")),
            "prev_next": f"{_fmt_pt(m.get('prev'))}/{_fmt_pt(m.get('next'))}",
            "line": f"{ps.line_spacing[1]}" + ("%" if ps.line_spacing[0] == "PERCENT" else ps.line_spacing[0]),
            "fill": cell_fill or "",
            "objects": " ".join(objs),
            "text": p.text.replace("\t", "→").replace("\n", "⏎"),
        })
    return rows


def render(doc: Document, *, width: int = 50, include_skip: bool = False) -> str:
    rows = para_rows(doc, include_skip=include_skip)
    head = f"{'경로':<22} {'역할':<15} {'스타일':<8} {'크기':>6} {'B':<2} {'정렬':<8} {'들여':>4} {'왼':>3} {'위/아래':>7} {'줄':>5}  내용"
    lines = [head, "-" * len(head)]
    for r in rows:
        extra = " ".join(x for x in (r["objects"], f"색{r['color']}" if r["color"] else "",
                                     f"셀배경{r['fill']}" if r["fill"] else "",
                                     r["font"] if r["font"] not in ("맑은 고딕", "") else "") if x)
        text = r["text"][:width]
        lines.append(
            f"{r['path']:<22} {r['role']:<15} {r['style']:<8} {r['size']:>6} {r['bold']:<2} "
            f"{r['align']:<8} {r['indent']:>4} {r['left']:>3} {r['prev_next']:>7} {r['line']:>5}  "
            f"{text}{'  [' + extra + ']' if extra else ''}"
        )
    counts = Counter(r["role"] for r in rows)
    lines.append("")
    lines.append("역할 개수: " + ", ".join(f"{k} {v}" for k, v in counts.most_common()))
    return "\n".join(lines)
