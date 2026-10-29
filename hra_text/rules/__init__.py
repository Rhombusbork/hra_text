"""규칙 레지스트리. 규칙 모듈은 FORMAT_RULES.md의 ID를 RULE_ID로 갖고 여기에 등록된다."""

from __future__ import annotations

import importlib
import pkgutil

REGISTRY: dict[str, type] = {}


def register(rule_cls):
    rule_id = rule_cls.RULE_ID
    if rule_id in REGISTRY:
        raise ValueError(f"중복 규칙 ID: {rule_id}")
    REGISTRY[rule_id] = rule_cls
    return rule_cls


# 배포판(PyInstaller)에서 모듈 목록 찾기가 안 될 때를 대비한 고정 목록. 규칙 파일을 추가하면 여기에도 추가.
RULE_MODULES = ("r01_style", "r02_font", "r03_size_bold", "r04_align", "r05_indent", "r06_spacing",
                "r07_objects", "r08_source", "r09_blank_lines", "r10_leading_space", "r11_spacing",
                "r13_defaults", "r14_toc", "r15_guide", "r16_page_number")


def _load_all() -> None:
    found = {m.name for m in pkgutil.iter_modules(__path__) if m.name.startswith("r") and m.name[1:3].isdigit()}
    for name in sorted(found | set(RULE_MODULES)):
        importlib.import_module(f"{__name__}.{name}")


_load_all()
