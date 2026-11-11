"""메모 문구 (키워드 형식). 원본은 docs/FORMAT_RULES.md 이며, 이 값은 문서의 해당 절에 그대로 있어야 한다
(tests/test_rules_sync.py 가 검사). 규칙 템플릿은 §2 각 규칙 절, 공통 템플릿은 §3.
따로 정하지 않은 규칙(R01~R06, R08 등)은 COMMON["item"] 한 줄 형식을 쓴다."""

from __future__ import annotations

MEMO_TEMPLATES: dict[str, dict[str, str]] = {
    "R03": {
        "heading_check": "- 확인 필요: 제목처럼 보이는 줄 '{text}' (크기·진하게 받은 대로)",
    },
    "R07": {
        "check": "- 확인 필요: {kind} 배치 (원래 쪽 기준 위치)",
    },
    "R10": {
        "leading_space": "- 문단 앞 공백: {old}칸 삭제",
    },
    "R11": {
        "spacing": "- 띄어쓰기: '{old}' → '{new}'",
        "spacing_check": "- 확인 필요: 띄어쓰기 '{text}'",
    },
    "R13": {
        "default": "- {item}: 기본값으로",
    },
    "R14": {
        "toc": "- 확인 필요: 목차 '{toc}' / 본문 '{h1}'",
        "toc_count": "- 확인 필요: 목차 {toc}개 / 본문 1단위 타이틀 {h1}개",
    },
    "R15": {
        "guide": "- 삭제: 양식 안내 문구 '{text}'",
    },
    "R16": {
        "page_num": "- 삭제: 쪽 번호",
    },
    "R18": {
        "blank_above": "- 빈 줄: 위에 1줄 넣음",
    },
    "R19": {
        "name_order": "- 느낀 점 순서: 표지 조원 순서로",
        "name_missing": "- 확인 필요: 느낀 점에 없는 조원 '{names}'",
    },
    "R17": {
        "line_break": "- 줄바꿈(Shift+Enter) → 문단 나누기: 문단 {n}개로",
    },
}

# FORMAT_RULES §3 공통 문구
COMMON: dict[str, str] = {
    "head": "수정사항",
    "table_head": "표 안 문단 {n}개 수정",
    "table_box": "표 수정",
    "item": "- {item}: {old} → {new}",
    "same_below": "- 같은 수정: 아래 {what} {n}개",
    "empty_lines": "- 위쪽 빈 줄 {n}개: 같은 기준으로 수정",
}
