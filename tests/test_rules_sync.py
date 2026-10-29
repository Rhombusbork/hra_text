"""docs/FORMAT_RULES.md ↔ 코드 동기화 검사 (CLAUDE.md "문서-코드 동기화 규칙")."""

import re
from pathlib import Path

from hra_text.rules import REGISTRY
from hra_text.rules.memo_templates import COMMON, MEMO_TEMPLATES

DOC = Path(__file__).resolve().parent.parent / "docs" / "FORMAT_RULES.md"
STATUSES = ("계획", "구현", "검증")


def _doc_rules() -> dict[str, dict]:
    """§2 규칙 목록의 `### Rxx.` 절을 {ID: {status, body}}로 읽는다."""
    text = DOC.read_text(encoding="utf-8")
    section = text.split("## 2. 규칙 목록", 1)[1].split("\n## 3.", 1)[0]
    parts = re.split(r"^### (R\d{2})\.", section, flags=re.M)
    rules = {}
    for rule_id, body in zip(parts[1::2], parts[2::2]):
        m = re.search(r"상태:\s*(\S+)", body)
        assert m, f"{rule_id}: '상태:' 표기가 없습니다"
        assert m.group(1) in STATUSES, f"{rule_id}: 알 수 없는 상태 {m.group(1)}"
        rules[rule_id] = {"status": m.group(1), "body": body}
    return rules


def test_doc_parses():
    assert _doc_rules(), "FORMAT_RULES.md 에서 규칙을 하나도 읽지 못했습니다"


def test_registered_rules_are_documented():
    doc = _doc_rules()
    for rule_id in REGISTRY:
        assert rule_id in doc, f"코드에만 있는 규칙 {rule_id}: FORMAT_RULES.md §2에 추가하세요"
        assert doc[rule_id]["status"] != "계획", f"{rule_id} 구현됨: 문서 상태를 '구현'으로 바꾸세요"


def test_implemented_rules_are_registered():
    for rule_id, info in _doc_rules().items():
        if info["status"] in ("구현", "검증"):
            assert rule_id in REGISTRY, f"문서상 {info['status']}인 {rule_id}가 코드에 없습니다"


def test_memo_templates_match_doc():
    doc = _doc_rules()
    for rule_id, templates in MEMO_TEMPLATES.items():
        assert rule_id in doc, f"메모 템플릿의 규칙 {rule_id}가 문서에 없습니다"
        for key, tpl in templates.items():
            assert tpl in doc[rule_id]["body"], f"{rule_id}.{key} 메모 문구가 문서와 다릅니다:\n{tpl}"


def test_common_memo_templates_in_section3():
    text = DOC.read_text(encoding="utf-8")
    section3 = text.split("## 3. 메모", 1)[1].split("\n## 4.", 1)[0]
    for key, tpl in COMMON.items():
        assert tpl in section3, f"COMMON.{key} 문구가 FORMAT_RULES §3 에 없습니다:\n{tpl}"
