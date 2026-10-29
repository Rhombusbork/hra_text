"""R11. 띄어쓰기 (규칙·사전 기반).

R11-a 확실한 패턴만 자동 수정 (예: 경영학과4학년 → 경영학과 4학년)
R11-b 사전(spacing_dict.tsv)에 있는 것 자동 수정
R11-c 사전에 없는데 한글이 14자 이상 공백 없이 붙어 있으면 고치지 않고 확인 메모만 (check)
"""

import re
from pathlib import Path

from ..hwpx.memo import memo_texts
from ..hwpx.ns import NS
from . import register
from .base import Rule

DICT_PATH = Path(__file__).with_name("spacing_dict.tsv")
PATTERNS = [
    (re.compile(r"(\S+학과)(\d+학년)"), r"\1 \2"),
]
RE_LONG = re.compile(r"[가-힣]{14,}")
NOT_CHECKED = {"SKIP", "GUIDE"}


def load_dict(path: Path = DICT_PATH) -> list[tuple[str, str]]:
    pairs = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        wrong, right = line.split("\t")
        pairs.append((wrong, right))
    return pairs


def _text_holders(para_el):
    """(요소, 속성) — hp:t 의 text 와 안쪽 요소 tail."""
    for t in para_el.iterfind("hp:run/hp:t", NS):
        yield t, "text"
        for child in t:
            yield child, "tail"


@register
class R11Spacing(Rule):
    RULE_ID = "R11"
    NAME = "띄어쓰기"

    def __init__(self, pairs: list[tuple[str, str]] | None = None):
        self.pairs = pairs if pairs is not None else load_dict()

    def apply(self, doc):
        changes, edited = [], False
        for p in doc.paras:
            if p.role in NOT_CHECKED:
                continue
            for holder, attr in _text_holders(p.el):
                value = getattr(holder, attr)
                if not value:
                    continue
                new = value
                for wrong, right in self.pairs:
                    if wrong in new:
                        new = new.replace(wrong, right)
                        changes.append(self.change(p, "spacing", wrong, right))
                for pattern, repl in PATTERNS:
                    for m in pattern.finditer(new):
                        changes.append(self.change(p, "spacing", m.group(0), m.expand(repl)))
                    new = pattern.sub(repl, new)
                if new != value:
                    setattr(holder, attr, new)
                    doc.touched.add(p.el)
                    edited = True
        if edited:
            doc.reload()
        # 사전에 없는 긴 붙은 글자: 확인 메모만 (이미 같은 메모가 있으면 생략)
        for p in doc.paras:
            if p.role in NOT_CHECKED:
                continue
            existing = " ".join(memo_texts(p.el))
            for m in RE_LONG.finditer(p.text):
                if m.group() not in existing:
                    changes.append(self.change(p, "spacing_check", m.group(), m.group(), check=True))
        return changes
