"""규칙 기반 클래스와 실행 순서."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..model import Change

if TYPE_CHECKING:
    from ..document import Document
    from ..hwpx.section import Para

# CLAUDE.md "패스 순서". 아직 구현되지 않은 규칙은 건너뛴다.
ORDER = ("R15", "R16", "R10", "R11", "R01", "R02", "R03", "R13",
         "R04", "R05", "R06", "R07", "R08", "R09", "R14")

# 서식 규칙이 다루지 않는 역할 (지울 대상이거나 처리 밖)
NOT_FORMATTED = {"SKIP", "GUIDE"}


class Rule:
    RULE_ID = ""
    NAME = ""

    def apply(self, doc: "Document") -> list[Change]:
        raise NotImplementedError

    # 공통 도우미
    def change(self, para: "Para", key: str, old, new, *, run=None, note: str = "", **extra) -> Change:
        return Change(rule_id=self.RULE_ID, key=key, old=old, new=new, para_el=para.el,
                      path=para.path, role=para.role, text=para.text,
                      run_el=run.el if run is not None else None, note=note, extra=extra)

    @staticmethod
    def formatted(doc: "Document"):
        return [p for p in doc.paras if p.role not in NOT_FORMATTED]

    @staticmethod
    def text_runs(para: "Para"):
        """글자가 들어 있는 런 (공백 포함)."""
        return [r for r in para.runs if r.text]
