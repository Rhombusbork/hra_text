"""R02. 글꼴은 전부 "맑은 고딕" (모든 언어 슬롯)."""

from ..hwpx.edit import change_run, char_fonts
from ..hwpx.header import LANGS
from . import register
from .base import Rule

TARGET_FONT = "맑은 고딕"


@register
class R02Font(Rule):
    RULE_ID = "R02"
    NAME = "글꼴 맑은 고딕"

    def apply(self, doc):
        h = doc.header
        ids = {lang: h.font_id(lang, TARGET_FONT, create=True) for lang in LANGS}
        changes = []
        for p in self.formatted(doc):
            for r in self.text_runs(p):
                fonts = h.char(r.char_id).fonts
                wrong = sorted({f for f in fonts.values() if f != TARGET_FONT})
                if wrong and change_run(doc, p, r, char_fonts(ids)):
                    changes.append(self.change(p, "font", "/".join(wrong), TARGET_FONT, run=r))
        return changes
